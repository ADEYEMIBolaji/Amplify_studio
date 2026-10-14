"""FR-012 (Publication evidence) / AT-04 (Distribution): mark published
with a live URL, parse the external post ID where the platform's URL
pattern allows, and allow reversal.
"""

from httpx import AsyncClient

from tests.conftest import make_user


async def _project_with_post(client: AsyncClient, platform="instagram") -> dict:
    project = (await client.post("/api/projects", json={"title": "Daily word", "topic": "Rest"})).json()
    await client.post(f"/api/projects/{project['id']}/outline")
    posts = (
        await client.post(f"/api/projects/{project['id']}/repurpose", json={"platforms": [platform]})
    ).json()
    return {"project": project, "post": posts[0]}


async def test_publish_sets_status_and_parses_external_id(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_post(client, "instagram")

    res = await client.post(
        f"/api/posts/{ctx['post']['id']}/publish",
        json={"external_url": "https://www.instagram.com/reel/Cabc123XYZ/"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "published"
    assert body["published_at"] is not None
    assert body["external_post_id"] == "Cabc123XYZ"


async def test_publish_parses_x_status_url(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_post(client, "x")

    res = await client.post(
        f"/api/posts/{ctx['post']['id']}/publish",
        json={"external_url": "https://x.com/someuser/status/1234567890123456789"},
    )
    assert res.json()["external_post_id"] == "1234567890123456789"


async def test_publish_with_unparseable_url_leaves_external_id_null(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_post(client, "facebook")

    res = await client.post(
        f"/api/posts/{ctx['post']['id']}/publish",
        json={"external_url": "https://facebook.com/somepage/posts/999"},
    )
    assert res.status_code == 200
    assert res.json()["external_post_id"] is None
    assert res.json()["external_url"] == "https://facebook.com/somepage/posts/999"


async def test_unpublish_reverses_publication(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_post(client)
    await client.post(
        f"/api/posts/{ctx['post']['id']}/publish",
        json={"external_url": "https://www.instagram.com/p/XYZ999/"},
    )

    res = await client.post(f"/api/posts/{ctx['post']['id']}/unpublish")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] != "published"
    assert body["published_at"] is None
    assert body["external_url"] is None
    assert body["external_post_id"] is None


async def test_calendar_lists_posts_in_range(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _project_with_post(client)
    await client.patch(
        f"/api/posts/{ctx['post']['id']}",
        json={"scheduled_at_local": "2026-06-15T09:00:00", "timezone": "Europe/London"},
    )

    res = await client.get(
        "/api/calendar", params={"from": "2026-06-01T00:00:00Z", "to": "2026-06-30T00:00:00Z"}
    )
    assert res.status_code == 200
    assert len(res.json()) == 1

    res = await client.get(
        "/api/calendar", params={"from": "2026-07-01T00:00:00Z", "to": "2026-07-30T00:00:00Z"}
    )
    assert res.json() == []
