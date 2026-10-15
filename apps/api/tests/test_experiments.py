"""FR-018: experiments — hypothesis, one primary variable, comparison
posts, confounder detection, and Owner-recorded outcome.
"""

from httpx import AsyncClient

from tests.conftest import make_user


async def _post_with_hook(client: AsyncClient, hook_type: str, project_title: str) -> dict:
    project = (await client.post("/api/projects", json={"title": project_title, "topic": "Hope"})).json()
    hooks = (await client.post(f"/api/projects/{project['id']}/hooks")).json()
    matching = next((h for h in hooks if h["hook_type"] == hook_type), hooks[0])
    await client.patch(f"/api/hooks/{matching['id']}", json={"selected": True})
    await client.post(f"/api/projects/{project['id']}/outline")
    posts = (
        await client.post(f"/api/projects/{project['id']}/repurpose", json={"platforms": ["instagram"]})
    ).json()
    return posts[0]


async def test_create_experiment_and_detect_no_confounders(client: AsyncClient, as_user):
    as_user(make_user())
    post_a = await _post_with_hook(client, "question", "A")
    post_b = await _post_with_hook(client, "story", "B")

    res = await client.post(
        "/api/experiments",
        json={
            "hypothesis": "Question hooks outperform story hooks on share rate.",
            "variable": "hook",
            "metric": "share_rate",
            "post_ids": [post_a["id"], post_b["id"]],
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "open"
    assert body["outcome"] is None
    assert set(body["post_ids"]) == {post_a["id"], post_b["id"]}
    # hook_type is the primary variable, so it must never appear as its own confounder.
    assert "hook_type" not in body["confounders"]


async def test_confounder_detected_when_other_tags_differ(client: AsyncClient, as_user):
    as_user(make_user())
    post_a = await _post_with_hook(client, "question", "A")
    post_b = await _post_with_hook(client, "question", "B")  # same hook_type as post_a

    tag_a = (await client.post("/api/topic-tags", json={"name": "Forgiveness"})).json()
    tag_b = (await client.post("/api/topic-tags", json={"name": "Patience"})).json()
    await client.patch(f"/api/projects/{post_a['project_id']}", json={"topic_tag_id": tag_a["id"]})
    await client.patch(f"/api/projects/{post_b['project_id']}", json={"topic_tag_id": tag_b["id"]})

    res = await client.post(
        "/api/experiments",
        json={
            "hypothesis": "Testing hook type with differing topics as a confounder.",
            "variable": "hook",
            "metric": "share_rate",
            "post_ids": [post_a["id"], post_b["id"]],
        },
    )
    assert res.status_code == 201
    assert "topic_tag_id" in res.json()["confounders"]


async def test_experiment_rejects_invalid_variable(client: AsyncClient, as_user):
    as_user(make_user())
    post_a = await _post_with_hook(client, "question", "A")
    post_b = await _post_with_hook(client, "story", "B")

    res = await client.post(
        "/api/experiments",
        json={
            "hypothesis": "x",
            "variable": "not_a_real_variable",
            "metric": "share_rate",
            "post_ids": [post_a["id"], post_b["id"]],
        },
    )
    assert res.status_code == 400


async def test_record_experiment_outcome(client: AsyncClient, as_user):
    as_user(make_user())
    post_a = await _post_with_hook(client, "question", "A")
    post_b = await _post_with_hook(client, "story", "B")

    created = (
        await client.post(
            "/api/experiments",
            json={
                "hypothesis": "Question hooks outperform story hooks.",
                "variable": "hook",
                "metric": "share_rate",
                "post_ids": [post_a["id"], post_b["id"]],
            },
        )
    ).json()

    res = await client.patch(
        f"/api/experiments/{created['id']}",
        json={"outcome": "supported", "outcome_note": "Question hook had a higher share rate this round."},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["outcome"] == "supported"
    assert body["status"] == "closed"


async def test_record_experiment_rejects_invalid_outcome(client: AsyncClient, as_user):
    as_user(make_user())
    post_a = await _post_with_hook(client, "question", "A")
    post_b = await _post_with_hook(client, "story", "B")
    created = (
        await client.post(
            "/api/experiments",
            json={
                "hypothesis": "x",
                "variable": "hook",
                "metric": "share_rate",
                "post_ids": [post_a["id"], post_b["id"]],
            },
        )
    ).json()

    res = await client.patch(f"/api/experiments/{created['id']}", json={"outcome": "maybe"})
    assert res.status_code == 400
