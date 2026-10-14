"""AT-07 (Security): a user must never be able to read or modify another
workspace's data via the API, even though the backend connects to Supabase
with the service role and bypasses RLS (FRD section 1, non-negotiable rule 1).
"""

from httpx import AsyncClient

from tests.conftest import make_user


async def test_cannot_read_another_workspaces_project(client: AsyncClient, as_user):
    owner_a = make_user("a@example.com")
    owner_b = make_user("b@example.com")

    as_user(owner_a)
    created = (await client.post("/api/projects", json={"title": "A's project", "topic": "Secret"})).json()

    as_user(owner_b)
    res = await client.get(f"/api/projects/{created['id']}")
    assert res.status_code == 404

    res = await client.get("/api/projects")
    assert res.json() == []


async def test_cannot_update_another_workspaces_project(client: AsyncClient, as_user):
    owner_a = make_user("a@example.com")
    owner_b = make_user("b@example.com")

    as_user(owner_a)
    created = (await client.post("/api/projects", json={"title": "A's project", "topic": "Secret"})).json()

    as_user(owner_b)
    res = await client.patch(f"/api/projects/{created['id']}", json={"title": "Hijacked"})
    assert res.status_code == 404

    as_user(owner_a)
    res = await client.get(f"/api/projects/{created['id']}")
    assert res.json()["title"] == "A's project"


async def test_cannot_archive_or_transition_another_workspaces_project(client: AsyncClient, as_user):
    owner_a = make_user("a@example.com")
    owner_b = make_user("b@example.com")

    as_user(owner_a)
    created = (await client.post("/api/projects", json={"title": "A's project", "topic": "Secret"})).json()

    as_user(owner_b)
    assert (await client.post(f"/api/projects/{created['id']}/archive")).status_code == 404
    assert (
        await client.post(f"/api/projects/{created['id']}/transition", json={"target_state": "scripting"})
    ).status_code == 404


async def test_each_owner_gets_own_workspace(client: AsyncClient, as_user):
    owner_a = make_user("a@example.com")
    owner_b = make_user("b@example.com")

    as_user(owner_a)
    await client.post("/api/projects", json={"title": "A1", "topic": "X"})

    as_user(owner_b)
    res = await client.get("/api/projects")
    assert res.json() == []

    await client.post("/api/projects", json={"title": "B1", "topic": "Y"})
    res = await client.get("/api/projects")
    assert len(res.json()) == 1
    assert res.json()[0]["title"] == "B1"
