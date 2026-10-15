"""AT-13 (Weekly review): report lists best/worst posts, data gaps and
1-3 experiments, contains no causal claims; marking complete sets
reviewed_at.
"""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select as sa_select

from app.db.models import SocialPost
from tests.conftest import TestSessionLocal, make_user

FORBIDDEN_PHRASES = ("will grow", "causes", "proven to")
# Note: "guarantee" itself is allowed — the required disclaimer says "not a
# guarantee", which is the honest framing the rule actually wants.


async def _published_post_this_week(client: AsyncClient, reach: int) -> dict:
    project = (await client.post("/api/projects", json={"title": "Weekly post", "topic": "Peace"})).json()
    await client.post(f"/api/projects/{project['id']}/outline")
    posts = (
        await client.post(f"/api/projects/{project['id']}/repurpose", json={"platforms": ["instagram"]})
    ).json()
    post = posts[0]
    await client.post(f"/api/posts/{post['id']}/publish", json={"external_url": "https://example.com/p/w"})

    published_at = datetime.now(UTC) - timedelta(days=1)
    async with TestSessionLocal() as db:
        row = (await db.execute(sa_select(SocialPost).where(SocialPost.id == post["id"]))).scalar_one()
        row.published_at = published_at
        await db.commit()

    await client.post(
        "/api/metrics/manual",
        json={"social_post_id": post["id"], "captured_at": datetime.now(UTC).isoformat(), "reach": reach},
    )
    return post


async def test_weekly_review_lists_best_and_worst_posts(client: AsyncClient, as_user):
    as_user(make_user())
    await _published_post_this_week(client, reach=500)
    await _published_post_this_week(client, reach=50)

    res = await client.get("/api/reports/weekly")
    assert res.status_code == 200
    body = res.json()
    assert len(body["report_json"]["best_posts"]) >= 1
    assert body["report_json"]["best_posts"][0]["reach"] == 500


async def test_weekly_review_flags_missing_follower_snapshot(client: AsyncClient, as_user):
    as_user(make_user())
    res = await client.get("/api/reports/weekly")
    gaps = res.json()["report_json"]["data_gaps"]
    assert any("follower snapshot" in g.lower() for g in gaps)


async def test_weekly_review_contains_no_causal_claims(client: AsyncClient, as_user):
    as_user(make_user())
    await _published_post_this_week(client, reach=100)

    res = await client.get("/api/reports/weekly")
    full_text = str(res.json()["report_json"]).lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in full_text


async def test_mark_weekly_review_complete_sets_reviewed_at(client: AsyncClient, as_user):
    as_user(make_user())
    created = (await client.get("/api/reports/weekly")).json()
    assert created["reviewed_at"] is None

    res = await client.post(f"/api/reports/weekly/{created['id']}/complete")
    assert res.status_code == 200
    assert res.json()["reviewed_at"] is not None

    # Regenerating the same week's report must not clear reviewed_at.
    refreshed = (await client.get("/api/reports/weekly")).json()
    assert refreshed["reviewed_at"] is not None
