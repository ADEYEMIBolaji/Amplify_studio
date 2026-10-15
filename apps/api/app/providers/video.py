"""VideoProcessor — FFmpeg-backed normalisation and rendering (FR-007, FR-009).

Unlike LLMProvider/TranscriptionProvider, there's no "which vendor" decision
here — FFmpeg is the chosen tool (CLAUDE.md: "Media: FFmpeg in the worker
container"). The interface split exists because this dev machine has no
FFmpeg binary installed (it's expected to run inside the worker container,
not on a bare host), so `FfmpegVideoProcessor` shells out for real while
`FakeVideoProcessor` stands in for local dev/test — selected the same way
the other providers are, not silently swapped.
"""

import json
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.config import get_settings

settings = get_settings()


class VideoProcessorUnavailableError(Exception):
    pass


@dataclass
class VideoInfo:
    duration_seconds: float
    width: int
    height: int
    codec: str
    rotation_degrees: int
    is_degraded: bool = False  # True when produced by the fake processor


FIT_MODES = ("crop", "pad")
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920


def is_vertical_9_16(width: int | None, height: int | None) -> bool:
    if not width or not height:
        return False
    return abs(width / height - 9 / 16) <= 0.01


class VideoProcessor(ABC):
    @abstractmethod
    def probe(self, input_path: Path) -> VideoInfo: ...

    @abstractmethod
    def normalize(self, input_path: Path, output_path: Path) -> VideoInfo:
        """HEVC -> H.264, apply rotation metadata, convert VFR -> CFR (FR-007)."""
        ...

    @abstractmethod
    def render_captions(
        self, input_path: Path, output_path: Path, subtitle_path: Path, fit_mode: str | None
    ) -> VideoInfo:
        """FR-009: 1080x1920 H.264 MP4 with the ASS captions burned in and
        audio normalised to about -14 LUFS. `fit_mode` ("crop" or "pad") is
        required when the source isn't already 9:16."""
        ...


def parse_probe_json(raw: str) -> VideoInfo:
    """ffprobe `-of json` output -> VideoInfo. JSON rather than CSV because
    ffprobe prints CSV fields in its own internal order, not the order they
    were requested in. Width/height are the *display* dimensions — swapped
    when rotation metadata says 90/270 (typical of iPhone portrait MOVs)."""
    data = json.loads(raw)
    stream = (data.get("streams") or [{}])[0]
    rotation = 0
    tag_rotate = (stream.get("tags") or {}).get("rotate")
    if tag_rotate is not None:
        rotation = int(float(tag_rotate))
    for side_data in stream.get("side_data_list") or []:
        if "rotation" in side_data:
            rotation = int(float(side_data["rotation"]))
    rotation %= 360

    width, height = int(stream["width"]), int(stream["height"])
    if rotation in (90, 270):
        width, height = height, width

    duration = stream.get("duration") or (data.get("format") or {}).get("duration") or 0
    return VideoInfo(
        duration_seconds=float(duration),
        width=width,
        height=height,
        codec=str(stream.get("codec_name", "unknown")),
        rotation_degrees=rotation,
    )


def _escape_filter_path(path: Path) -> str:
    # Inside a quoted FFmpeg filter argument, `:` must still be escaped
    # (Windows drive letters), as must `\` and `'`.
    text = path.as_posix()
    for char in ("\\", ":", "'"):
        text = text.replace(char, "\\" + char)
    return text


def build_render_filtergraph(
    source_width: int, source_height: int, fit_mode: str | None, subtitle_path: Path
) -> str:
    """FR-009 video filtergraph -> `[v]`. 9:16 sources are scaled straight to
    1080x1920; others are centre-cropped, or padded onto a blurred, filled
    copy of themselves ("blurred-background pad"), per the Owner's choice."""
    w, h = TARGET_WIDTH, TARGET_HEIGHT
    subs = f"ass='{_escape_filter_path(subtitle_path)}'"
    if is_vertical_9_16(source_width, source_height):
        return f"[0:v]scale={w}:{h},setsar=1,{subs}[v]"
    if fit_mode == "crop":
        return (
            f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},setsar=1,{subs}[v]"
        )
    if fit_mode == "pad":
        return (
            "[0:v]split=2[bg][fg];"
            f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},boxblur=20:5[bgb];"
            f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1,{subs}[v]"
        )
    raise ValueError("A non-9:16 source needs fit_mode 'crop' or 'pad'.")


def build_render_command(
    input_path: Path,
    output_path: Path,
    subtitle_path: Path,
    source_width: int,
    source_height: int,
    fit_mode: str | None,
) -> list[str]:
    return [
        "ffmpeg", "-y", "-i", str(input_path),
        "-filter_complex", build_render_filtergraph(source_width, source_height, fit_mode, subtitle_path),
        "-map", "[v]", "-map", "0:a?",
        # Single-pass loudnorm lands within about 1 LU of target — FR-009 asks
        # for "approximately -14 LUFS". loudnorm upsamples internally, so
        # resample back to a delivery rate.
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]


class FfmpegVideoProcessor(VideoProcessor):
    def __init__(self) -> None:
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise VideoProcessorUnavailableError(
                "ffmpeg/ffprobe not found on PATH — this processor only runs inside the worker container."
            )

    def probe(self, input_path: Path) -> VideoInfo:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries",
                "stream=width,height,codec_name,duration:stream_tags=rotate:"
                "stream_side_data=rotation:format=duration",
                "-of", "json", str(input_path),
            ],
            capture_output=True, text=True, check=True,
        )
        return parse_probe_json(result.stdout)

    def normalize(self, input_path: Path, output_path: Path) -> VideoInfo:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(input_path),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30",
                "-c:a", "aac", str(output_path),
            ],
            capture_output=True, check=True,
        )
        return self.probe(output_path)

    def render_captions(
        self, input_path: Path, output_path: Path, subtitle_path: Path, fit_mode: str | None
    ) -> VideoInfo:
        source = self.probe(input_path)
        subprocess.run(
            build_render_command(
                input_path, output_path, subtitle_path, source.width, source.height, fit_mode
            ),
            capture_output=True, check=True,
        )
        return self.probe(output_path)


class FakeVideoProcessor(VideoProcessor):
    """Copies the input through unchanged and reports plausible metadata.
    Marks every result `is_degraded=True` so callers never claim real
    normalisation/rendering happened when it didn't (no silent success)."""

    def probe(self, input_path: Path) -> VideoInfo:
        size = input_path.stat().st_size if input_path.exists() else 0
        return VideoInfo(
            duration_seconds=round(max(size / (500 * 1024), 1.0), 1),
            width=1080,
            height=1920,
            codec="h264",
            rotation_degrees=0,
            is_degraded=True,
        )

    def normalize(self, input_path: Path, output_path: Path) -> VideoInfo:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return self.probe(output_path)

    def render_captions(
        self, input_path: Path, output_path: Path, subtitle_path: Path, fit_mode: str | None
    ) -> VideoInfo:
        # Captions are NOT burned in here — the copy is marked degraded and
        # the UI says so. The ASS file is still built upstream, so caption
        # layout is exercised even without FFmpeg.
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return self.probe(output_path)


def get_video_processor() -> VideoProcessor:
    if settings.video_processor == "ffmpeg":
        return FfmpegVideoProcessor()
    return FakeVideoProcessor()
