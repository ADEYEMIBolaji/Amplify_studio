"""AT-15: export returns all workspace data; deleting a project removes
its media objects and rows (FR-030).
"""

import json

from httpx import AsyncClient

from tests.conftest import make_user


async def _project_with_media(client: AsyncClient) -> dict:
    project = (await client.post("/api/projects", json={"title": "Export me", "topic": "Hope"})).json()
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
    return {"project": project, "media_asset_id": complete["media_asset_id"]}


async def test_export_returns_all_workspace_data(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_media(client)
    await client.post(
        "/api/follower-snapshots",
        json={"platform": "instagram", "captured_at": "2026-06-01T00:00:00Z", "follower_count": 100},
    )

    res = await client.post("/api/export")
    assert res.status_code == 200
    body = json.loads(res.content)

    assert len(body["projects"]) == 1
    assert body["projects"][0]["title"] == "Export me"
    assert len(body["media_assets"]) == 1
    assert body["media_assets"][0]["download_url"] is not None
    assert len(body["follower_snapshots"]) == 1
    assert body["workspace"]["id"] == ctx["project"]["workspace_id"]


async def test_delete_project_removes_media_object_and_row(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_media(client)

    asset = (await client.get(f"/api/media/{ctx['media_asset_id']}")).json()
    download_path = asset["download_url"].split("/api/media/signed/")[1]
    assert (await client.get(f"/api/media/signed/{download_path}")).status_code == 200

    res = await client.delete(f"/api/projects/{ctx['project']['id']}")
    assert res.status_code == 204

    # The object itself is gone from storage, not just the DB row referencing it.
    assert (await client.get(f"/api/media/signed/{download_path}")).status_code == 404
    assert (await client.get(f"/api/media/{ctx['media_asset_id']}")).status_code == 404
    assert (await client.get(f"/api/projects/{ctx['project']['id']}")).status_code == 404


async def test_delete_media_asset_removes_storage_object(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_media(client)

    res = await client.delete(f"/api/media/{ctx['media_asset_id']}")
    assert res.status_code == 204
    assert (await client.get(f"/api/media/{ctx['media_asset_id']}")).status_code == 404


async def test_delete_workspace_removes_everything(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_media(client)

    res = await client.delete("/api/workspace")
    assert res.status_code == 204

    # A brand-new request from the same user re-provisions an empty workspace.
    res = await client.get("/api/projects")
    assert res.status_code == 200
    assert res.json() == []
    assert (await client.get(f"/api/projects/{ctx['project']['id']}")).status_code == 404
