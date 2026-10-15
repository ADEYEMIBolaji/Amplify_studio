"""AT-06 (Insight quality): with fewer than five comparable posts, show
insufficient-data warning with count needed; with sufficient data and a
>=20% difference, display a recommendation with linked evidence; no
growth guarantees anywhere in the wording.
"""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select as sa_select

from app.db.models import SocialPost
from tests.conftest import TestSessionLocal, make_user

FORBIDDEN_PHRASES = ("will grow", "causes", "proven to", "because this")
# Note: "guarantee" itself is allowed — the required disclaimer says "not a
# guarantee", which is the honest framing the rule actually wants.


async def _create_post_with_tags(
    client: AsyncClient, platform: str, hook_type: str | None, reach: int, shares: int
) -> dict:
    project = (await client.post("/api/projects", json={"title": "Insight post", "topic": "Hope"})).json()
    if hook_type:
        # Approve a hook of the desired type so the project carries that tag.
        hooks = (await client.post(f"/api/projects/{project['id']}/hooks")).json()
        matching = next((h for h in hooks if h["hook_type"] == hook_type), hooks[0])
        await client.patch(f"/api/hooks/{matching['id']}", json={"selected": True})

    await client.post(f"/api/projects/{project['id']}/outline")
    posts = (
        await client.post(f"/api/projects/{project['id']}/repurpose", json={"platforms": [platform]})
    ).json()
    post = posts[0]
    await client.post(f"/api/posts/{post['id']}/publish", json={"external_url": "https://example.com/p/z"})

    published_at = datetime.now(UTC) - timedelta(days=10)
    async with TestSessionLocal() as db:
        row = (await db.execute(sa_select(SocialPost).where(SocialPost.id == post["id"]))).scalar_one()
        row.published_at = published_at
        await db.commit()

    await client.post(
        "/api/metrics/manual",
        json={
            "social_post_id": post["id"],
            "captured_at": (published_at + timedelta(days=7)).isoformat(),
            "reach": reach,
            "shares": shares,
        },
    )
    return post


async def test_insufficient_data_warning_names_the_count_needed(client: AsyncClient, as_user):
    as_user(make_user())
    for _ in range(3):
        await _create_post_with_tags(client, "instagram", "question", reach=100, shares=10)

    res = await client.get("/api/analytics/recommendations", params={"platform": "instagram"})
    assert res.status_code == 200
    body = res.json()
    assert body["comparisons"] == []
    insufficient = [i for i in body["insufficient_data"] if i["dimension"] == "hook_type"]
    assert len(insufficient) == 1
    assert insufficient[0]["posts_still_needed"] >= 1
    assert insufficient[0]["group_counts"]["question"] == 3


async def test_recommendation_shown_with_sufficient_data_and_evidence(client: AsyncClient, as_user):
    as_user(make_user())
    # 5 "question" posts with a high share rate, 5 "story" posts with a much lower one.
    for _ in range(5):
        await _create_post_with_tags(client, "tiktok", "question", reach=100, shares=30)  # 30% share rate
    for _ in range(5):
        await _create_post_with_tags(client, "tiktok", "story", reach=100, shares=5)  # 5% share rate

    res = await client.get("/api/analytics/recommendations", params={"platform": "tiktok"})
    body = res.json()
    comparisons = [c for c in body["comparisons"] if c["dimension"] == "hook_type"]
    assert len(comparisons) == 1
    comparison = comparisons[0]
    assert comparison["better_group"] == "question"
    assert comparison["relative_difference"] >= 0.20
    assert len(comparison["post_ids_a"]) == 5
    assert len(comparison["post_ids_b"]) == 5

    full_text = " ".join(
        [comparison["summary"]]
        + [h["summary"] for h in body["high_savers"]]
        + [h["summary"] for h in body["underperformers"]]
    ).lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in full_text


async def test_small_relative_difference_produces_no_recommendation(client: AsyncClient, as_user):
    as_user(make_user())
    for _ in range(5):
        await _create_post_with_tags(client, "facebook", "question", reach=100, shares=10)
    for _ in range(5):
        await _create_post_with_tags(client, "facebook", "story", reach=100, shares=11)

    res = await client.get("/api/analytics/recommendations", params={"platform": "facebook"})
    body = res.json()
    assert all(c["dimension"] != "hook_type" for c in body["comparisons"])
    assert all(i["dimension"] != "hook_type" for i in body["insufficient_data"])


async def test_no_posts_returns_empty_recommendations(client: AsyncClient, as_user):
    as_user(make_user())
    res = await client.get("/api/analytics/recommendations", params={"platform": "x"})
    assert res.status_code == 200
    body = res.json()
    assert body["comparisons"] == []
    assert body["insufficient_data"] == []
    assert body["high_savers"] == []
    assert body["underperformers"] == []
