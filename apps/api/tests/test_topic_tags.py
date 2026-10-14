"""FR-021 (content attribute tags) — Owner-managed controlled topic list."""

from httpx import AsyncClient

from tests.conftest import make_user


async def test_create_and_list_topic_tags(client: AsyncClient, as_user):
    as_user(make_user())

    res = await client.post("/api/topic-tags", json={"name": "Forgiveness"})
    assert res.status_code == 201

    res = await client.get("/api/topic-tags")
    assert [t["name"] for t in res.json()] == ["Forgiveness"]


async def test_duplicate_topic_tag_name_rejected(client: AsyncClient, as_user):
    as_user(make_user())

    await client.post("/api/topic-tags", json={"name": "Grace"})
    res = await client.post("/api/topic-tags", json={"name": "Grace"})
    assert res.status_code == 409


async def test_archive_topic_tag(client: AsyncClient, as_user):
    as_user(make_user())

    created = (await client.post("/api/topic-tags", json={"name": "Patience"})).json()
    res = await client.patch(f"/api/topic-tags/{created['id']}", json={"archived": True})
    assert res.status_code == 200
    assert res.json()["archived"] is True
