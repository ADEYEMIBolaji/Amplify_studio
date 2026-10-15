"""AT-05 (Analytics): median day-7 reach and follower delta recalculated
accurately against a hand-calculated fixture; cumulative snapshots never
summed; missing metrics shown as unavailable, never zero.

Hand-calculated fixture for 6 published Instagram posts, each with a single
day-7 snapshot:
    reach:  100, 150, 200, 250, 300, 400
    sorted: 100, 150, 200, 250, 300, 400  (already sorted)
    median = average of the two middle values (200, 250) = 225.0
    mean   = (100+150+200+250+300+400) / 6 = 233.333...

Engagement inputs on the 250-reach post: likes=20, comments=5, shares=0,
saves=None (platform doesn't report saves) -> engagement = 25/250 = 0.10.
Only one post has saves populated (reach=100, saves=10) -> save_rate
median = 10/100 = 0.10 (the only value, so the median is itself).
"""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from app.services.metrics import compute_platform_period_metrics, median, select_window_snapshot
from tests.conftest import TestSessionLocal, make_user

PUBLISHED_AT = datetime(2026, 6, 1, tzinfo=UTC)
DAY7 = PUBLISHED_AT + timedelta(days=7)


def test_median_helper_matches_hand_calculation():
    assert median([100, 150, 200, 250, 300, 400]) == 225.0
    assert median([]) is None
    assert median([42]) == 42


def test_select_window_snapshot_picks_closest_within_window():
    class FakeSnap:
        def __init__(self, days, captured_at):
            self.days_since_publish = days
            self.captured_at = captured_at

    snaps = [
        FakeSnap(5, datetime(2026, 1, 1)),
        FakeSnap(7, datetime(2026, 1, 3)),
        FakeSnap(9, datetime(2026, 1, 5)),
    ]
    picked = select_window_snapshot(snaps, target_day=7, window_days=1)
    assert picked.days_since_publish == 7

    # day 9 is outside the window=1 around day 7 -> should not be picked
    # when the exact-day snapshot is removed, nothing in range remains.
    assert select_window_snapshot(snaps[2:], target_day=7, window_days=1) is None


async def _create_published_post(client: AsyncClient, platform: str) -> dict:
    project = (await client.post("/api/projects", json={"title": "Fixture post", "topic": "Peace"})).json()
    await client.post(f"/api/projects/{project['id']}/outline")
    posts = (
        await client.post(f"/api/projects/{project['id']}/repurpose", json={"platforms": [platform]})
    ).json()
    post = posts[0]
    res = await client.post(
        f"/api/posts/{post['id']}/publish", json={"external_url": "https://example.com/p/x"}
    )
    body = res.json()
    # Force a known published_at via direct DB access — the publish endpoint
    # defaults to "now", but this fixture needs exact, hand-calculable dates.
    from sqlalchemy import select as sa_select

    from app.db.models import SocialPost

    async with TestSessionLocal() as db:
        result = await db.execute(sa_select(SocialPost).where(SocialPost.id == body["id"]))
        row = result.scalar_one()
        row.published_at = PUBLISHED_AT
        await db.commit()
    return body


async def _add_snapshot(client: AsyncClient, post_id: str, **fields) -> None:
    res = await client.post(
        "/api/metrics/manual",
        json={"social_post_id": post_id, "captured_at": DAY7.isoformat(), **fields},
    )
    assert res.status_code == 201, res.text


async def test_median_reach_matches_hand_calculated_fixture(client: AsyncClient, as_user):
    as_user(make_user())
    reach_values = [100, 150, 200, 250, 300, 400]
    for reach in reach_values:
        post = await _create_published_post(client, "instagram")
        await _add_snapshot(client, post["id"], reach=reach)

    from sqlalchemy import select as sa_select

    from app.db.models import Workspace

    async with TestSessionLocal() as db:
        ws = (await db.execute(sa_select(Workspace))).scalars().first()
        metrics = await compute_platform_period_metrics(
            db,
            workspace_id=ws.id,
            platform="instagram",
            start=PUBLISHED_AT - timedelta(days=1),
            end=PUBLISHED_AT + timedelta(days=30),
        )

    assert metrics.reach_median == 225.0
    assert round(metrics.reach_mean, 2) == 233.33
    assert metrics.data_coverage.eligible == 6
    assert metrics.data_coverage.total == 6


async def test_engagement_and_save_rate_skip_missing_platform_fields(client: AsyncClient, as_user):
    as_user(make_user())
    post_a = await _create_published_post(client, "x")  # X never reports saves
    await _add_snapshot(client, post_a["id"], reach=250, likes=20, comments=5, shares=0)

    post_b = await _create_published_post(client, "x")
    await _add_snapshot(client, post_b["id"], reach=100, saves=10)

    from sqlalchemy import select as sa_select

    from app.db.models import Workspace

    async with TestSessionLocal() as db:
        ws = (await db.execute(sa_select(Workspace))).scalars().first()
        metrics = await compute_platform_period_metrics(
            db,
            workspace_id=ws.id,
            platform="x",
            start=PUBLISHED_AT - timedelta(days=1),
            end=PUBLISHED_AT + timedelta(days=30),
        )

    # Only post_a has engagement inputs (likes/comments/shares); its rate is
    # the only value, so the median equals it exactly: 25/250 = 0.10.
    assert round(metrics.engagement_per_reach, 2) == 0.10
    # Only post_b has saves; save_rate median is 10/100 = 0.10.
    assert round(metrics.save_rate, 2) == 0.10


async def test_posts_without_a_day7_snapshot_are_excluded_not_zeroed(client: AsyncClient, as_user):
    as_user(make_user())
    post_with_data = await _create_published_post(client, "tiktok")
    await _add_snapshot(client, post_with_data["id"], reach=500)

    # A second post with no snapshot at all.
    await _create_published_post(client, "tiktok")

    from sqlalchemy import select as sa_select

    from app.db.models import Workspace

    async with TestSessionLocal() as db:
        ws = (await db.execute(sa_select(Workspace))).scalars().first()
        metrics = await compute_platform_period_metrics(
            db,
            workspace_id=ws.id,
            platform="tiktok",
            start=PUBLISHED_AT - timedelta(days=1),
            end=PUBLISHED_AT + timedelta(days=30),
        )

    assert metrics.reach_median == 500.0  # the un-snapshotted post is excluded, not treated as 0 reach
    assert metrics.data_coverage.eligible == 1
    assert metrics.data_coverage.total == 2


async def test_cumulative_snapshots_are_never_summed_across_dates(client: AsyncClient, as_user):
    """Two snapshots for the same post at different dates must not be added
    together — only the day-7-window one is used."""
    as_user(make_user())
    post = await _create_published_post(client, "facebook")

    await client.post(
        "/api/metrics/manual",
        json={
            "social_post_id": post["id"],
            "captured_at": (PUBLISHED_AT + timedelta(days=1)).isoformat(),
            "reach": 50,
        },
    )
    await _add_snapshot(client, post["id"], reach=300)  # day 7

    from sqlalchemy import select as sa_select

    from app.db.models import Workspace

    async with TestSessionLocal() as db:
        ws = (await db.execute(sa_select(Workspace))).scalars().first()
        metrics = await compute_platform_period_metrics(
            db,
            workspace_id=ws.id,
            platform="facebook",
            start=PUBLISHED_AT - timedelta(days=1),
            end=PUBLISHED_AT + timedelta(days=30),
        )

    # If the two snapshots were wrongly summed this would be 350.
    assert metrics.reach_median == 300.0
