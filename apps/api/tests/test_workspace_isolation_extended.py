"""AT-07 (Security), extended: every resource type added since Week 1 must
also be unreachable cross-workspace, even though the backend's Postgres
connection uses the service role and bypasses RLS entirely (FRD section 1,
non-negotiable rule 1). See tests/test_workspace_isolation.py for the
original Week 1 coverage (projects).
"""

from httpx import AsyncClient

from tests.conftest import make_user


async def _owner_a_post(client: AsyncClient, as_user) -> dict:
    owner_a = make_user("a@example.com")
    as_user(owner_a)
    project = (await client.post("/api/projects", json={"title": "A's project", "topic": "Secret"})).json()
    await client.post(f"/api/projects/{project['id']}/outline")
    posts = (
        await client.post(f"/api/projects/{project['id']}/repurpose", json={"platforms": ["instagram"]})
    ).json()
    return {"project": project, "post": posts[0]}


async def test_cannot_read_another_workspaces_post_or_its_metrics(client: AsyncClient, as_user):
    ctx = await _owner_a_post(client, as_user)
    await client.post(
        "/api/metrics/manual",
        json={"social_post_id": ctx["post"]["id"], "captured_at": "2026-06-01T00:00:00Z", "reach": 100},
    )

    owner_b = make_user("b@example.com")
    as_user(owner_b)

    assert (await client.get(f"/api/posts/{ctx['post']['id']}/metrics")).status_code == 404
    assert (
        await client.patch(f"/api/posts/{ctx['post']['id']}", json={"caption": "hijacked"})
    ).status_code == 404
    assert (
        await client.post(f"/api/posts/{ctx['post']['id']}/publish", json={"external_url": "https://x.com/y"})
    ).status_code == 404
    assert (
        await client.post(
            "/api/metrics/manual",
            json={"social_post_id": ctx["post"]["id"], "captured_at": "2026-06-02T00:00:00Z", "reach": 1},
        )
    ).status_code == 404


async def test_cannot_access_another_workspaces_media(client: AsyncClient, as_user):
    owner_a = make_user("a@example.com")
    as_user(owner_a)
    project = (await client.post("/api/projects", json={"title": "A's project", "topic": "Secret"})).json()
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

    owner_b = make_user("b@example.com")
    as_user(owner_b)
    assert (await client.get(f"/api/media/{complete['media_asset_id']}")).status_code == 404
    assert (await client.delete(f"/api/media/{complete['media_asset_id']}")).status_code == 404
    assert (await client.get(f"/api/media/uploads/{session['id']}")).status_code == 404


async def test_cannot_access_another_workspaces_experiments(client: AsyncClient, as_user):
    ctx = await _owner_a_post(client, as_user)
    project_b_posts = []
    for _ in range(2):
        proj = (await client.post("/api/projects", json={"title": "second", "topic": "x"})).json()
        await client.post(f"/api/projects/{proj['id']}/outline")
        res = await client.post(f"/api/projects/{proj['id']}/repurpose", json={"platforms": ["instagram"]})
        p = res.json()[0]
        project_b_posts.append(p["id"])

    created = (
        await client.post(
            "/api/experiments",
            json={"hypothesis": "x", "variable": "hook", "metric": "share_rate", "post_ids": project_b_posts},
        )
    ).json()

    owner_b = make_user("b@example.com")
    as_user(owner_b)
    assert (await client.get("/api/experiments")).json() == []
    assert (
        await client.patch(f"/api/experiments/{created['id']}", json={"outcome": "supported"})
    ).status_code == 404
    _ = ctx


async def test_cannot_access_another_workspaces_weekly_review(client: AsyncClient, as_user):
    owner_a = make_user("a@example.com")
    as_user(owner_a)
    created = (await client.get("/api/reports/weekly")).json()

    owner_b = make_user("b@example.com")
    as_user(owner_b)
    assert (await client.post(f"/api/reports/weekly/{created['id']}/complete")).status_code == 404


async def test_cannot_delete_another_workspaces_project(client: AsyncClient, as_user):
    owner_a = make_user("a@example.com")
    as_user(owner_a)
    project = (await client.post("/api/projects", json={"title": "A's project", "topic": "Secret"})).json()

    owner_b = make_user("b@example.com")
    as_user(owner_b)
    assert (await client.delete(f"/api/projects/{project['id']}")).status_code == 404

    as_user(owner_a)
    assert (await client.get(f"/api/projects/{project['id']}")).status_code == 200


async def test_export_only_contains_own_workspace_data(client: AsyncClient, as_user):
    owner_a = make_user("a@example.com")
    as_user(owner_a)
    await client.post("/api/projects", json={"title": "A's project", "topic": "Secret"})

    owner_b = make_user("b@example.com")
    as_user(owner_b)
    await client.post("/api/projects", json={"title": "B's project", "topic": "Other"})

    res = await client.post("/api/export")
    body = res.json()
    assert len(body["projects"]) == 1
    assert body["projects"][0]["title"] == "B's project"
