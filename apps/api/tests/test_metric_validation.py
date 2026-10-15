"""FR-014: validation, duplicate handling, and the "fell below an earlier
snapshot" flag.
"""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from tests.conftest import TestSessionLocal, make_user

PUBLISHED_AT = datetime(2026, 6, 1, tzinfo=UTC)


async def _published_post(client: AsyncClient) -> dict:
    project = (await client.post("/api/projects", json={"title": "Validation post", "topic": "Trust"})).json()
    await client.post(f"/api/projects/{project['id']}/outline")
    posts = (
        await client.post(f"/api/projects/{project['id']}/repurpose", json={"platforms": ["instagram"]})
    ).json()
    post = posts[0]
    await client.post(f"/api/posts/{post['id']}/publish", json={"external_url": "https://example.com/p/y"})

    from sqlalchemy import select as sa_select

    from app.db.models import SocialPost

    async with TestSessionLocal() as db:
        row = (await db.execute(sa_select(SocialPost).where(SocialPost.id == post["id"]))).scalar_one()
        row.published_at = PUBLISHED_AT
        await db.commit()
    return post


async def test_negative_count_rejected(client: AsyncClient, as_user):
    as_user(make_user())
    post = await _published_post(client)

    res = await client.post(
        "/api/metrics/manual",
        json={"social_post_id": post["id"], "captured_at": PUBLISHED_AT.isoformat(), "reach": -5},
    )
    assert res.status_code == 400
    assert res.json()["code"] == "negative_count"


async def test_completion_rate_out_of_range_rejected(client: AsyncClient, as_user):
    as_user(make_user())
    post = await _published_post(client)

    res = await client.post(
        "/api/metrics/manual",
        json={"social_post_id": post["id"], "captured_at": PUBLISHED_AT.isoformat(), "completion_rate": 150},
    )
    assert res.status_code == 400
    assert res.json()["code"] == "completion_rate_out_of_range"


async def test_captured_at_before_publish_rejected(client: AsyncClient, as_user):
    as_user(make_user())
    post = await _published_post(client)

    res = await client.post(
        "/api/metrics/manual",
        json={
            "social_post_id": post["id"],
            "captured_at": (PUBLISHED_AT - timedelta(days=1)).isoformat(),
            "reach": 10,
        },
    )
    assert res.status_code == 400
    assert res.json()["code"] == "captured_at_before_publish"


async def test_duplicate_snapshot_requires_explicit_choice(client: AsyncClient, as_user):
    as_user(make_user())
    post = await _published_post(client)
    captured = PUBLISHED_AT + timedelta(days=7)

    await client.post(
        "/api/metrics/manual",
        json={"social_post_id": post["id"], "captured_at": captured.isoformat(), "reach": 100},
    )

    res = await client.post(
        "/api/metrics/manual",
        json={"social_post_id": post["id"], "captured_at": captured.isoformat(), "reach": 200},
    )
    assert res.status_code == 409
    assert res.json()["code"] == "duplicate_snapshot"

    res = await client.post(
        "/api/metrics/manual",
        json={
            "social_post_id": post["id"],
            "captured_at": captured.isoformat(),
            "reach": 200,
            "on_duplicate": "update",
        },
    )
    assert res.status_code == 201
    assert res.json()["reach"] == 200

    snapshots = (await client.get(f"/api/posts/{post['id']}/metrics")).json()
    assert len(snapshots) == 1  # updated in place, not duplicated


async def test_duplicate_skip_leaves_existing_value(client: AsyncClient, as_user):
    as_user(make_user())
    post = await _published_post(client)
    captured = PUBLISHED_AT + timedelta(days=7)

    await client.post(
        "/api/metrics/manual",
        json={"social_post_id": post["id"], "captured_at": captured.isoformat(), "reach": 100},
    )
    res = await client.post(
        "/api/metrics/manual",
        json={
            "social_post_id": post["id"],
            "captured_at": captured.isoformat(),
            "reach": 999,
            "on_duplicate": "skip",
        },
    )
    assert res.status_code == 201
    assert res.json()["reach"] == 100  # unchanged


async def test_cumulative_dip_is_flagged_not_rejected(client: AsyncClient, as_user):
    as_user(make_user())
    post = await _published_post(client)

    await client.post(
        "/api/metrics/manual",
        json={
            "social_post_id": post["id"],
            "captured_at": (PUBLISHED_AT + timedelta(days=3)).isoformat(),
            "reach": 500,
        },
    )
    res = await client.post(
        "/api/metrics/manual",
        json={
            "social_post_id": post["id"],
            "captured_at": (PUBLISHED_AT + timedelta(days=7)).isoformat(),
            "reach": 300,  # lower than the earlier snapshot — impossible for a cumulative metric
        },
    )
    assert res.status_code == 201  # flagged, not blocked
    assert "reach" in res.json()["flagged_fields"]


async def test_missing_fields_are_null_not_zero(client: AsyncClient, as_user):
    as_user(make_user())
    post = await _published_post(client)

    res = await client.post(
        "/api/metrics/manual",
        json={
            "social_post_id": post["id"],
            "captured_at": (PUBLISHED_AT + timedelta(days=7)).isoformat(),
            "reach": 100,
        },
    )
    body = res.json()
    assert body["likes"] is None
    assert body["saves"] is None
    assert body["completion_rate"] is None
