"""FR-020 (creator voice profile and guardrails) — Week 1 basics only;
full voice-sample/guardrail usage in generation prompts lands in Week 2."""

from httpx import AsyncClient

from tests.conftest import make_user


async def test_get_brand_profile_creates_defaults(client: AsyncClient, as_user):
    as_user(make_user())

    res = await client.get("/api/brand-profile")
    assert res.status_code == 200
    body = res.json()
    assert body["wpm"] == 150
    assert body["timezone"] == "Europe/London"
    assert body["translation"] == "WEB"


async def test_update_brand_profile_persists_and_versions(client: AsyncClient, as_user):
    as_user(make_user())

    res = await client.patch(
        "/api/brand-profile",
        json={"tone": "Warm and direct", "wpm": 140, "phrases_avoid": ["just"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["tone"] == "Warm and direct"
    assert body["wpm"] == 140
    assert body["version_no"] == 2

    res = await client.get("/api/brand-profile")
    assert res.json()["tone"] == "Warm and direct"
