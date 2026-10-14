"""AT-03 (Video, upload half): resumable chunked upload, including a
simulated dropped-connection resume, MIME/extension validation, and private
signed-URL-only access to the resulting object (FR-007, FRD rule 8).
"""


from httpx import AsyncClient

from tests.conftest import make_user


async def _create_project(client: AsyncClient) -> dict:
    return (await client.post("/api/projects", json={"title": "Sermon clip", "topic": "Hope"})).json()


async def _init_upload(client: AsyncClient, project_id: str, total_size=20, chunk_size=10) -> dict:
    return (
        await client.post(
            "/api/media/uploads",
            json={
                "project_id": project_id,
                "filename": "clip.mov",
                "content_type": "video/quicktime",
                "total_size": total_size,
                "chunk_size": chunk_size,
            },
        )
    ).json()


async def test_init_upload_rejects_disallowed_extension(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)

    res = await client.post(
        "/api/media/uploads",
        json={
            "project_id": project["id"],
            "filename": "clip.avi",
            "content_type": "video/avi",
            "total_size": 100,
        },
    )
    assert res.status_code == 400


async def test_init_upload_rejects_oversized_file(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)

    res = await client.post(
        "/api/media/uploads",
        json={
            "project_id": project["id"],
            "filename": "clip.mp4",
            "content_type": "video/mp4",
            "total_size": 600 * 1024 * 1024,
        },
    )
    assert res.status_code == 400
    assert res.json()["code"] == "upload_too_large"


async def test_chunked_upload_completes_and_normalizes(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)
    session = await _init_upload(client, project["id"])
    assert session["total_chunks"] == 2

    await client.put(f"/api/media/uploads/{session['id']}/chunks/0", content=b"0123456789")
    await client.put(f"/api/media/uploads/{session['id']}/chunks/1", content=b"abcdefghij")

    res = await client.post(f"/api/media/uploads/{session['id']}/complete")
    assert res.status_code == 202
    body = res.json()

    asset = (await client.get(f"/api/media/{body['media_asset_id']}")).json()
    assert asset["status"] == "ready"
    assert asset["metadata_json"]["degraded"] is True  # FakeVideoProcessor — no ffmpeg in this environment
    assert asset["download_url"] is not None


async def test_dropped_connection_resumes_without_restarting(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)
    session = await _init_upload(client, project["id"])

    await client.put(f"/api/media/uploads/{session['id']}/chunks/0", content=b"0123456789")

    # "Dropped connection": client only knows chunk 0 made it, checks before resuming.
    probe = (await client.get(f"/api/media/uploads/{session['id']}")).json()
    assert probe["received_chunks"] == [0]

    await client.put(f"/api/media/uploads/{session['id']}/chunks/1", content=b"abcdefghij")
    res = await client.post(f"/api/media/uploads/{session['id']}/complete")
    assert res.status_code == 202


async def test_complete_fails_with_missing_chunks(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)
    session = await _init_upload(client, project["id"])

    await client.put(f"/api/media/uploads/{session['id']}/chunks/0", content=b"0123456789")
    res = await client.post(f"/api/media/uploads/{session['id']}/complete")
    assert res.status_code == 409


async def test_media_download_requires_valid_signed_token(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)
    session = await _init_upload(client, project["id"])
    await client.put(f"/api/media/uploads/{session['id']}/chunks/0", content=b"0123456789")
    await client.put(f"/api/media/uploads/{session['id']}/chunks/1", content=b"abcdefghij")
    complete = (await client.post(f"/api/media/uploads/{session['id']}/complete")).json()
    asset = (await client.get(f"/api/media/{complete['media_asset_id']}")).json()

    download_path = asset["download_url"].split("/api/media/signed/")[1]
    res = await client.get(f"/api/media/signed/{download_path}")
    assert res.status_code == 200
    assert res.content == b"0123456789abcdefghij"

    res = await client.get("/api/media/signed/not-a-real-token")
    assert res.status_code == 404


async def test_cannot_access_another_workspaces_upload_session(client: AsyncClient, as_user):
    owner_a = make_user("a@example.com")
    owner_b = make_user("b@example.com")

    as_user(owner_a)
    project = await _create_project(client)
    session = await _init_upload(client, project["id"])

    as_user(owner_b)
    res = await client.get(f"/api/media/uploads/{session['id']}")
    assert res.status_code == 404
    res = await client.put(f"/api/media/uploads/{session['id']}/chunks/0", content=b"x" * 10)
    assert res.status_code == 404
