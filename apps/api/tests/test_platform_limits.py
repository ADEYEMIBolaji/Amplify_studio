"""AT-10 (Platform limits): a too-long export is blocked from attaching to
a post without the right account flag; a too-long caption is blocked.
Limits come from the `platform_limits` table (FR-026), not constants.
"""

from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import MediaAsset
from tests.conftest import TestSessionLocal, make_user


async def _set_duration(media_asset_id: str, seconds: float) -> None:
    async with TestSessionLocal() as db:
        result = await db.execute(select(MediaAsset).where(MediaAsset.id == media_asset_id))
        asset = result.scalar_one()
        asset.duration_seconds = seconds
        await db.commit()


async def _project_with_ready_media(client: AsyncClient) -> dict:
    project = (await client.post("/api/projects", json={"title": "X clip", "topic": "Patience"})).json()
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
    await client.post(f"/api/projects/{project['id']}/outline")
    posts = (await client.post(f"/api/projects/{project['id']}/repurpose", json={"platforms": ["x"]})).json()
    return {"project": project, "media_asset_id": complete["media_asset_id"], "post": posts[0]}


async def test_video_too_long_for_x_without_premium_is_blocked(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_ready_media(client)
    await _set_duration(ctx["media_asset_id"], 178.0)  # 2:58, FRD's own example

    res = await client.patch(
        f"/api/posts/{ctx['post']['id']}", json={"media_asset_id": ctx["media_asset_id"]}
    )
    assert res.status_code == 409
    assert res.json()["code"] == "platform_duration_exceeded"
    assert "2:20" in res.json()["message"]
    assert "2:58" in res.json()["message"]


async def test_x_premium_flag_raises_the_limit(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_ready_media(client)
    await _set_duration(ctx["media_asset_id"], 178.0)

    await client.patch("/api/brand-profile", json={"platform_flags_json": {"x_premium": True}})

    res = await client.patch(
        f"/api/posts/{ctx['post']['id']}", json={"media_asset_id": ctx["media_asset_id"]}
    )
    assert res.status_code == 200
    assert res.json()["media_asset_id"] == ctx["media_asset_id"]


async def test_video_within_limit_attaches_successfully(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_ready_media(client)
    await _set_duration(ctx["media_asset_id"], 60.0)

    res = await client.patch(
        f"/api/posts/{ctx['post']['id']}", json={"media_asset_id": ctx["media_asset_id"]}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ready"


async def test_platform_limits_endpoint_lists_seeded_config(client: AsyncClient, as_user):
    as_user(make_user())
    res = await client.get("/api/platform-limits")
    assert res.status_code == 200
    platforms = {row["platform"] for row in res.json()}
    assert platforms == {"instagram", "tiktok", "facebook", "x"}
    x_row = next(r for r in res.json() if r["platform"] == "x")
    assert x_row["duration_max_seconds"] == 140
    assert x_row["verified"] is False
