"""FR-010 (Repurpose): distinct platform captions/hashtags/CTAs generated
from the approved script, enforcing configured per-platform limits — not
hard-coded constants (FR-026). Part of AT-04.
"""

from httpx import AsyncClient

from tests.conftest import make_user


async def _project_with_script(client: AsyncClient) -> dict:
    project = (await client.post("/api/projects", json={"title": "Grace clip", "topic": "Grace"})).json()
    await client.post(f"/api/projects/{project['id']}/outline")
    return project


async def test_repurpose_creates_distinct_posts_per_platform(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _project_with_script(client)

    res = await client.post(
        f"/api/projects/{project['id']}/repurpose",
        json={"platforms": ["instagram", "tiktok", "x"]},
    )
    assert res.status_code == 201
    posts = res.json()
    assert {p["platform"] for p in posts} == {"instagram", "tiktok", "x"}
    captions = {p["platform"]: p["caption"] for p in posts}
    assert captions["instagram"] != captions["x"]
    for post in posts:
        assert post["status"] == "draft"
        assert len(post["hashtags"]) > 0


async def test_repurpose_without_script_is_blocked(client: AsyncClient, as_user):
    as_user(make_user())
    project = (await client.post("/api/projects", json={"title": "No script", "topic": "Hope"})).json()

    res = await client.post(f"/api/projects/{project['id']}/repurpose", json={"platforms": ["instagram"]})
    assert res.status_code == 409


async def test_repurpose_rejects_unknown_platform(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _project_with_script(client)

    res = await client.post(f"/api/projects/{project['id']}/repurpose", json={"platforms": ["myspace"]})
    assert res.status_code == 400


async def test_editing_caption_enforces_platform_limit(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _project_with_script(client)
    posts = (
        await client.post(f"/api/projects/{project['id']}/repurpose", json={"platforms": ["x"]})
    ).json()
    post = posts[0]

    res = await client.patch(f"/api/posts/{post['id']}", json={"caption": "x" * 300})
    assert res.status_code == 400
    assert res.json()["code"] == "caption_too_long"

    res = await client.patch(f"/api/posts/{post['id']}", json={"caption": "x" * 100})
    assert res.status_code == 200
