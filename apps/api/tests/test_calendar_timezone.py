"""AT-11 (Timezone): a post scheduled for 09:00 Europe/London computes the
correct UTC instant on both sides of the October clock change (2026-10-25
is when UK clocks go back), proving the scheduling conversion is DST-aware
rather than a fixed offset.
"""

from datetime import UTC, datetime

from httpx import AsyncClient

from tests.conftest import make_user


async def _project_with_post(client: AsyncClient) -> dict:
    project = (await client.post("/api/projects", json={"title": "Daily word", "topic": "Rest"})).json()
    await client.post(f"/api/projects/{project['id']}/outline")
    posts = (
        await client.post(f"/api/projects/{project['id']}/repurpose", json={"platforms": ["instagram"]})
    ).json()
    return {"project": project, "post": posts[0]}


async def test_bst_schedule_converts_to_correct_utc(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_post(client)

    # 2026-06-15 is during British Summer Time (UTC+1).
    res = await client.patch(
        f"/api/posts/{ctx['post']['id']}",
        json={"scheduled_at_local": "2026-06-15T09:00:00", "timezone": "Europe/London"},
    )
    assert res.status_code == 200
    scheduled_at = datetime.fromisoformat(res.json()["scheduled_at"])
    assert scheduled_at.astimezone(UTC).hour == 8
    assert res.json()["posting_slot"] == "morning"


async def test_gmt_schedule_after_clock_change_converts_to_correct_utc(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_post(client)

    # 2026-10-26 is the day after UK clocks go back (last Sunday in October).
    res = await client.patch(
        f"/api/posts/{ctx['post']['id']}",
        json={"scheduled_at_local": "2026-10-26T09:00:00", "timezone": "Europe/London"},
    )
    assert res.status_code == 200
    scheduled_at = datetime.fromisoformat(res.json()["scheduled_at"])
    assert scheduled_at.astimezone(UTC).hour == 9
    assert res.json()["posting_slot"] == "morning"


async def test_evening_slot_is_computed_in_local_time_not_utc(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_post(client)

    # 19:00 BST == 18:00 UTC; the slot must be computed from the local hour.
    res = await client.patch(
        f"/api/posts/{ctx['post']['id']}",
        json={"scheduled_at_local": "2026-06-15T19:00:00", "timezone": "Europe/London"},
    )
    assert res.json()["posting_slot"] == "evening"


async def test_invalid_timezone_rejected(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_post(client)

    res = await client.patch(
        f"/api/posts/{ctx['post']['id']}",
        json={"scheduled_at_local": "2026-06-15T09:00:00", "timezone": "Mars/Olympus_Mons"},
    )
    assert res.status_code == 400
