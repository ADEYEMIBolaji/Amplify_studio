"""FR-029 (follower snapshots) and AT-14 (historical baseline import)."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient

from tests.conftest import make_user

PUBLISHED_AT = datetime.now(UTC) - timedelta(days=30)
SNAPSHOT_AT = PUBLISHED_AT + timedelta(days=7)


async def test_add_and_list_follower_snapshots(client: AsyncClient, as_user):
    as_user(make_user())

    res = await client.post(
        "/api/follower-snapshots",
        json={"platform": "instagram", "captured_at": "2026-06-01T00:00:00Z", "follower_count": 1000},
    )
    assert res.status_code == 201

    res = await client.get("/api/follower-snapshots", params={"platform": "instagram"})
    assert res.status_code == 200
    assert res.json()[0]["follower_count"] == 1000


async def test_negative_follower_count_rejected(client: AsyncClient, as_user):
    as_user(make_user())

    res = await client.post(
        "/api/follower-snapshots",
        json={"platform": "instagram", "captured_at": "2026-06-01T00:00:00Z", "follower_count": -10},
    )
    assert res.status_code == 400


async def test_import_ten_historical_posts_labelled_historical(client: AsyncClient, as_user):
    as_user(make_user())

    for i in range(10):
        res = await client.post(
            "/api/posts/historical",
            json={
                "platform": "instagram",
                "external_url": f"https://www.instagram.com/reel/Historical{i}/",
                "published_at": PUBLISHED_AT.isoformat(),
                "tags_json": {"topic": "testimony"},
                "snapshots": [{"captured_at": SNAPSHOT_AT.isoformat(), "reach": 100 + i}],
            },
        )
        assert res.status_code == 201
        body = res.json()
        assert body["is_historical"] is True
        assert body["project_id"] is None
        assert body["status"] == "published"
        assert body["tags_json"] == {"topic": "testimony"}

    result = await client.get(
        "/api/analytics/overview", params={"platform": "instagram", "range_days": 90}
    )
    assert result.status_code == 200
    assert result.json()["current"]["data_coverage"]["total"] == 10


async def test_historical_import_parses_external_post_id(client: AsyncClient, as_user):
    as_user(make_user())

    res = await client.post(
        "/api/posts/historical",
        json={
            "platform": "tiktok",
            "external_url": "https://www.tiktok.com/@someuser/video/7123456789",
            "published_at": PUBLISHED_AT.isoformat(),
        },
    )
    assert res.json()["external_post_id"] == "7123456789"
