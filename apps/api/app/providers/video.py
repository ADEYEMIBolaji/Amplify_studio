"""VideoProcessor — FFmpeg-backed normalisation and rendering (FR-007, FR-009).

Unlike LLMProvider/TranscriptionProvider, there's no "which vendor" decision
here — FFmpeg is the chosen tool (CLAUDE.md: "Media: FFmpeg in the worker
container"). The interface split exists because this dev machine has no
FFmpeg binary installed (it's expected to run inside the worker container,
not on a bare host), so `FfmpegVideoProcessor` shells out for real while
`FakeVideoProcessor` stands in for local dev/test — selected the same way
the other providers are, not silently swapped.
"""

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


class VideoProcessor(ABC):
    @abstractmethod
    def probe(self, input_path: Path) -> VideoInfo: ...

    @abstractmethod
    def normalize(self, input_path: Path, output_path: Path) -> VideoInfo:
        """HEVC -> H.264, apply rotation metadata, convert VFR -> CFR (FR-007)."""
        ...

    @abstractmethod
    def render_captions(self, input_path: Path, output_path: Path, srt_path: Path, style: dict) -> VideoInfo:
        """Burn-in render with safe zones and loudness normalisation (FR-009, stretch)."""
        ...


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
                "-show_entries", "stream=width,height,codec_name,duration",
                "-of", "csv=p=0", str(input_path),
            ],
            capture_output=True, text=True, check=True,
        )
        width_str, height_str, codec, duration_str = result.stdout.strip().split(",")
        return VideoInfo(
            duration_seconds=float(duration_str),
            width=int(width_str),
            height=int(height_str),
            codec=codec,
            rotation_degrees=0,
        )

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

    def render_captions(self, input_path: Path, output_path: Path, srt_path: Path, style: dict) -> VideoInfo:
        font_size = style.get("font_size", 24)
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(input_path),
                "-vf", f"subtitles={srt_path}:force_style='Fontsize={font_size}'",
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(output_path),
            ],
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

    def render_captions(self, input_path: Path, output_path: Path, srt_path: Path, style: dict) -> VideoInfo:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.read_bytes())
        return self.probe(output_path)


def get_video_processor() -> VideoProcessor:
    if settings.video_processor == "ffmpeg":
        return FfmpegVideoProcessor()
    return FakeVideoProcessor()
