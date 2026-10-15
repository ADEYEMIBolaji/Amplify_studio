"""AT-03 (Video, render half) / FR-009: burn-in render of reviewed subtitles
into a 1080x1920 MP4 with captions inside the safe zone, brand-profile
styling, centre-crop/blurred-pad choice for non-9:16 sources, source
preserved — and the Ready state gated on a render that passes platform
constraint checks (FRD 1.1, FR-026).

Caption geometry and the FFmpeg command are pure functions, tested directly
here because this machine (and CI) only has `FakeVideoProcessor`.
"""

import json
from pathlib import Path, PureWindowsPath

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

import app.services.media_jobs as media_jobs
from app.providers.video import (
    FakeVideoProcessor,
    VideoInfo,
    build_render_command,
    build_render_filtergraph,
    parse_probe_json,
)
from app.services.captions import (
    FRAME_HEIGHT,
    SubtitleStyle,
    build_ass,
    build_caption_events,
    caption_bounds,
    safe_zone_px,
    wrap_text,
)
from tests.conftest import make_user

# ---------------------------------------------------------------------------
# Caption layout (pure)
# ---------------------------------------------------------------------------


def test_at03_wrap_respects_32_characters_per_line():
    text = "For I know the plans I have for you, declares the Lord, plans to prosper you and not to harm you"
    lines = wrap_text(text, 32)
    assert all(len(line) <= 32 for line in lines)
    assert " ".join(lines) == text


def test_wrap_hard_splits_a_word_longer_than_the_line():
    lines = wrap_text("Mahershalalhashbaz" * 3, 20)
    assert all(len(line) <= 20 for line in lines)
    assert "".join(lines) == "Mahershalalhashbaz" * 3


def test_at03_long_segment_splits_into_two_line_captions_with_contiguous_timing():
    style = SubtitleStyle()
    segment = {
        "start": 10.0,
        "end": 16.0,
        "text": "Grace is not a reward for the faithful, it is the gift that makes us faithful in the "
        "first place, and it was never ours to earn.",
    }
    events = build_caption_events([segment], style)

    assert len(events) > 1
    assert all(len(e.lines) <= 2 for e in events)
    assert all(len(line) <= 32 for e in events for line in e.lines)
    assert events[0].start == 10.0
    assert events[-1].end == 16.0
    for prev, nxt in zip(events, events[1:], strict=False):
        assert prev.end == pytest.approx(nxt.start)


def test_empty_and_zero_length_segments_are_skipped():
    style = SubtitleStyle()
    events = build_caption_events(
        [{"start": 0, "end": 1, "text": "   "}, {"start": 2, "end": 2, "text": "x"}], style
    )
    assert events == []


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"safe_zone_bottom_pct": 25, "safe_zone_right_pct": 15},
        {"font_size": 36, "max_chars_per_line": 40},
        {"font_size": 60, "max_chars_per_line": 24, "max_lines": 3},
        {"background_box": False},
    ],
)
def test_at03_captions_stay_inside_the_safe_zone(overrides):
    style = SubtitleStyle(**overrides)
    zone = safe_zone_px(style)
    for line_count in range(1, style.max_lines + 1):
        box = caption_bounds(style, line_count)
        assert box.bottom <= zone.bottom, f"{line_count} line(s) overlap the bottom safe zone"
        assert box.right <= zone.right, f"{line_count} line(s) overlap the right safe zone"
        assert box.left >= zone.left
        assert box.top > 0


def test_default_safe_zone_is_bottom_20_and_right_12_percent():
    zone = safe_zone_px(SubtitleStyle())
    assert zone.bottom == pytest.approx(FRAME_HEIGHT * 0.8)
    assert zone.right == pytest.approx(1080 * 0.88)


def test_style_rejects_a_font_too_large_for_the_line_length():
    with pytest.raises(ValidationError, match="won't fit inside the caption safe zone"):
        SubtitleStyle(font_size=80, max_chars_per_line=32)


def test_ass_file_pins_frame_size_alignment_and_margins():
    style = SubtitleStyle(text_colour="#FFCC00", background_opacity=0.5)
    ass = build_ass([{"start": 0, "end": 2, "text": "Hello {\\b1} world"}], style)

    assert "PlayResX: 1080" in ass
    assert "PlayResY: 1920" in ass
    style_line = next(line for line in ass.splitlines() if line.startswith("Style: Default,"))
    fields = style_line.removeprefix("Style: ").split(",")
    assert fields[3] == "&H0000CCFF"  # #FFCC00 as ASS &HAABBGGRR
    assert fields[6] == "&H80000000"  # 50% black box (alpha 0x80)
    assert fields[15] == "3"  # BorderStyle 3 = opaque box
    assert fields[18] == "2"  # bottom-centre alignment
    # MarginV reserves the bottom 20% plus the box padding.
    assert int(fields[21]) >= FRAME_HEIGHT * 0.2

    dialogue = next(line for line in ass.splitlines() if line.startswith("Dialogue:"))
    assert "{" not in dialogue.split(",,", 1)[1]  # transcript text can't inject override tags
    assert "\\b1" not in dialogue


# ---------------------------------------------------------------------------
# FFmpeg command + probe parsing (pure)
# ---------------------------------------------------------------------------


def test_vertical_source_is_scaled_without_crop_or_pad():
    graph = build_render_filtergraph(720, 1280, None, Path("/tmp/c.ass"))
    assert "scale=1080:1920" in graph
    assert "crop" not in graph and "boxblur" not in graph
    assert graph.endswith("[v]")


def test_landscape_source_crop_and_blurred_pad():
    crop = build_render_filtergraph(1920, 1080, "crop", Path("/tmp/c.ass"))
    assert "force_original_aspect_ratio=increase" in crop and "crop=1080:1920" in crop

    pad = build_render_filtergraph(1920, 1080, "pad", Path("/tmp/c.ass"))
    assert "boxblur" in pad and "overlay=(W-w)/2:(H-h)/2" in pad

    with pytest.raises(ValueError):
        build_render_filtergraph(1920, 1080, None, Path("/tmp/c.ass"))


def test_render_command_outputs_h264_and_normalises_loudness():
    cmd = build_render_command(
        Path("in.mov"), Path("out.mp4"), Path("/tmp/c.ass"), 1080, 1920, None
    )
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "loudnorm=I=-14" in cmd[cmd.index("-af") + 1]
    assert "0:a?" in cmd  # silent sources still render


def test_subtitle_path_is_escaped_for_the_filtergraph():
    graph = build_render_filtergraph(1080, 1920, None, Path(PureWindowsPath(r"C:\Temp\it's\c.ass")))
    assert "C\\:/Temp/it\\'s/c.ass" in graph


def test_probe_swaps_dimensions_for_rotated_iphone_footage():
    raw = json.dumps(
        {
            "streams": [
                {
                    "codec_name": "hevc",
                    "width": 1920,
                    "height": 1080,
                    "side_data_list": [{"rotation": -90}],
                }
            ],
            "format": {"duration": "42.5"},
        }
    )
    info = parse_probe_json(raw)
    assert (info.width, info.height) == (1080, 1920)
    assert info.rotation_degrees == 270
    assert info.duration_seconds == 42.5
    assert info.codec == "hevc"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


async def _subtitled_project(client: AsyncClient, *, review: bool = True) -> dict:
    project = (await client.post("/api/projects", json={"title": "Sermon clip", "topic": "Hope"})).json()
    session = (
        await client.post(
            "/api/media/uploads",
            json={
                "project_id": project["id"],
                "filename": "clip.mp4",
                "content_type": "video/mp4",
                "total_size": 10,
                "chunk_size": 10,
            },
        )
    ).json()
    await client.put(f"/api/media/uploads/{session['id']}/chunks/0", content=b"0123456789")
    complete = (await client.post(f"/api/media/uploads/{session['id']}/complete")).json()
    source_id = complete["media_asset_id"]
    await client.post(f"/api/media/{source_id}/transcribe")
    transcript = (await client.get(f"/api/media/{source_id}/transcript")).json()
    if review:
        await client.post(f"/api/transcripts/{transcript['id']}/review")
    return {"project": project, "source_id": source_id, "transcript": transcript}


async def _advance_to_subtitled(client: AsyncClient, project_id: str) -> None:
    v1 = (await client.post(f"/api/projects/{project_id}/outline")).json()
    await client.post(f"/api/scripts/{v1['id']}/approve")
    for ref in (await client.get(f"/api/projects/{project_id}/references")).json():
        await client.post(f"/api/references/{ref['id']}/verify")
    for state in ("scripting", "script_approved", "recorded", "subtitled"):
        res = await client.post(f"/api/projects/{project_id}/transition", json={"target_state": state})
        assert res.status_code == 200, (state, res.json())


async def test_at03_render_produces_vertical_mp4_and_preserves_source(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _subtitled_project(client)
    source_before = (await client.get(f"/api/media/{ctx['source_id']}")).json()

    res = await client.post(f"/api/media/{ctx['source_id']}/render", json={})
    assert res.status_code == 202
    job = res.json()
    assert job["job_type"] == "render"
    assert job["status"] == "succeeded"
    assert job["result_json"]["caption_count"] >= len(ctx["transcript"]["segments"])

    render = (await client.get(f"/api/media/{job['media_asset_id']}")).json()
    assert render["kind"] == "render"
    assert render["status"] == "ready"
    assert (render["width"], render["height"]) == (1080, 1920)
    assert render["metadata_json"]["source_media_asset_id"] == ctx["source_id"]
    assert render["metadata_json"]["degraded"] is True  # fake processor — never claims a real burn-in
    assert render["download_url"]

    download = await client.get("/api/media/signed/" + render["download_url"].split("/api/media/signed/")[1])
    assert download.status_code == 200

    source_after = (await client.get(f"/api/media/{ctx['source_id']}")).json()
    assert source_after["status"] == "ready"
    assert source_after["download_url"] is not None
    assert source_after["metadata_json"] == source_before["metadata_json"]


async def test_render_requires_reviewed_subtitles(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _subtitled_project(client, review=False)

    res = await client.post(f"/api/media/{ctx['source_id']}/render", json={})
    assert res.status_code == 409
    assert "reviewed" in res.json()["message"]


async def test_render_uses_brand_profile_subtitle_style(client: AsyncClient, as_user):
    as_user(make_user())
    profile = (await client.get("/api/brand-profile")).json()
    assert profile["subtitle_style_json"]["max_chars_per_line"] == 32  # FRD defaults shown
    assert profile["subtitle_style_json"]["safe_zone_bottom_pct"] == 20

    res = await client.patch(
        "/api/brand-profile",
        json={"subtitle_style_json": {"font_size": 40, "text_colour": "#FFEE00", "background_box": False}},
    )
    assert res.status_code == 200
    assert res.json()["subtitle_style_json"]["font_size"] == 40

    ctx = await _subtitled_project(client)
    job = (await client.post(f"/api/media/{ctx['source_id']}/render", json={})).json()
    render = (await client.get(f"/api/media/{job['media_asset_id']}")).json()
    assert render["metadata_json"]["style"]["font_size"] == 40
    assert render["metadata_json"]["style"]["text_colour"] == "#FFEE00"


async def test_invalid_subtitle_style_is_rejected(client: AsyncClient, as_user):
    as_user(make_user())
    res = await client.patch("/api/brand-profile", json={"subtitle_style_json": {"font_size": 90}})
    assert res.status_code == 400
    assert "safe zone" in res.json()["message"]

    res = await client.patch("/api/brand-profile", json={"subtitle_style_json": {"text_colour": "yellow"}})
    assert res.status_code == 400


class _LandscapeProcessor(FakeVideoProcessor):
    def probe(self, input_path: Path) -> VideoInfo:
        info = super().probe(input_path)
        info.width, info.height = 1920, 1080
        return info


async def test_at03_non_vertical_source_needs_crop_or_pad_choice(
    client: AsyncClient, as_user, monkeypatch
):
    as_user(make_user())
    monkeypatch.setattr(media_jobs, "get_video_processor", lambda: _LandscapeProcessor())
    ctx = await _subtitled_project(client)
    monkeypatch.undo()

    res = await client.post(f"/api/media/{ctx['source_id']}/render", json={})
    assert res.status_code == 400
    assert res.json()["code"] == "fit_mode_required"

    res = await client.post(f"/api/media/{ctx['source_id']}/render", json={"fit_mode": "pad"})
    assert res.status_code == 202
    render = (await client.get(f"/api/media/{res.json()['media_asset_id']}")).json()
    assert render["metadata_json"]["fit_mode"] == "pad"

    res = await client.post(f"/api/media/{ctx['source_id']}/render", json={"fit_mode": "stretch"})
    assert res.status_code == 400


async def test_rerender_keeps_earlier_renders(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _subtitled_project(client)
    await client.post(f"/api/media/{ctx['source_id']}/render", json={})
    await client.post(f"/api/media/{ctx['source_id']}/render", json={})

    assets = (await client.get(f"/api/projects/{ctx['project']['id']}/media")).json()
    renders = [a for a in assets if a["kind"] == "render"]
    assert len(renders) == 2
    assert all(r["created_at"] for r in renders)


async def test_ready_state_requires_a_render_passing_platform_limits(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _subtitled_project(client)
    project_id = ctx["project"]["id"]
    await _advance_to_subtitled(client, project_id)

    res = await client.post(f"/api/projects/{project_id}/transition", json={"target_state": "ready"})
    assert res.status_code == 409  # no render yet

    await client.post(f"/api/media/{ctx['source_id']}/render", json={})
    res = await client.post(f"/api/projects/{project_id}/transition", json={"target_state": "ready"})
    assert res.status_code == 200


async def test_ready_state_blocked_when_render_fails_every_platform(client: AsyncClient, as_user):
    """A 20-minute render exceeds every seeded platform's duration limit."""
    as_user(make_user())
    ctx = await _subtitled_project(client)
    project_id = ctx["project"]["id"]
    await _advance_to_subtitled(client, project_id)

    class _LongRender(FakeVideoProcessor):
        def render_captions(self, input_path, output_path, subtitle_path, fit_mode):
            info = super().render_captions(input_path, output_path, subtitle_path, fit_mode)
            info.duration_seconds = 20 * 60
            return info

    original = media_jobs.get_video_processor
    media_jobs.get_video_processor = lambda: _LongRender()  # type: ignore[assignment]
    try:
        await client.post(f"/api/media/{ctx['source_id']}/render", json={})
    finally:
        media_jobs.get_video_processor = original  # type: ignore[assignment]

    res = await client.post(f"/api/projects/{project_id}/transition", json={"target_state": "ready"})
    assert res.status_code == 409


async def test_at07_cannot_render_another_workspaces_video(client: AsyncClient, as_user):
    as_user(make_user("owner-a@example.com"))
    ctx = await _subtitled_project(client)

    as_user(make_user("owner-b@example.com"))
    res = await client.post(f"/api/media/{ctx['source_id']}/render", json={})
    assert res.status_code == 404
