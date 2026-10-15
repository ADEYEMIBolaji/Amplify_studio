"""FR-025: next action per project, pipeline by state, weekly posting
adherence, follower/reach trends.
"""

from httpx import AsyncClient

from tests.conftest import make_user


async def test_home_dashboard_empty_state(client: AsyncClient, as_user):
    as_user(make_user())

    res = await client.get("/api/dashboard/home")
    assert res.status_code == 200
    body = res.json()
    assert body["next_actions"] == []
    assert body["pipeline_counts"]["idea"] == 0
    assert body["posting_adherence_this_week"] is None  # no posts scheduled -> unavailable, not 0
    assert body["active_experiments"] == []


async def test_home_dashboard_lists_next_action_per_project(client: AsyncClient, as_user):
    as_user(make_user())
    await client.post("/api/projects", json={"title": "Idea stage", "topic": "Grace"})

    res = await client.get("/api/dashboard/home")
    body = res.json()
    assert len(body["next_actions"]) == 1
    assert body["next_actions"][0]["status"] == "idea"
    assert "script" in body["next_actions"][0]["next_action"].lower()
    assert body["pipeline_counts"]["idea"] == 1


async def test_archived_projects_excluded_from_dashboard(client: AsyncClient, as_user):
    as_user(make_user())
    created = (await client.post("/api/projects", json={"title": "Old", "topic": "X"})).json()
    await client.post(f"/api/projects/{created['id']}/archive")

    res = await client.get("/api/dashboard/home")
    assert res.json()["next_actions"] == []


async def test_follower_snapshot_shows_on_dashboard(client: AsyncClient, as_user):
    as_user(make_user())
    await client.post(
        "/api/follower-snapshots",
        json={"platform": "instagram", "captured_at": "2026-06-01T00:00:00Z", "follower_count": 500},
    )

    res = await client.get("/api/dashboard/home")
    body = res.json()
    assert body["last_follower_snapshot_at"]["instagram"] is not None
    assert body["last_follower_snapshot_at"]["tiktok"] is None
