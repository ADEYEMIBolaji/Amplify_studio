"""AT-02 (Biblical verification): unverified AI-suggested scripture blocks
Script approved; verified references permit the transition. Generated
script contains placeholders only; quoted verse text is rejected; expansion
uses an allowlisted translation.
"""

import pytest
from httpx import AsyncClient

from app.errors import BadRequestError
from app.services.scripture import validate_no_quoted_verse_text, validate_sections
from tests.conftest import make_user


async def _create_project(client: AsyncClient) -> dict:
    return (await client.post("/api/projects", json={"title": "Peace in storms", "topic": "Fear"})).json()


def test_validate_rejects_quoted_verse_text():
    with pytest.raises(BadRequestError) as exc_info:
        validate_no_quoted_verse_text(
            "Remember what it says: 'For God so loved the world, that he gave his one and only Son, "
            "that whoever believes in him should not perish, but have eternal life.'"
        )
    assert exc_info.value.code == "verse_text_not_allowed"


def test_validate_allows_placeholder_citation():
    validate_sections({"biblical_context": "As {{John 3:16}} reminds us, God's love is for everyone."})


async def test_script_approved_blocked_until_references_verified(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)
    await client.post(f"/api/projects/{project['id']}/outline")

    res = await client.post(
        f"/api/projects/{project['id']}/transition", json={"target_state": "scripting"}
    )
    assert res.status_code == 200

    res = await client.post(
        f"/api/projects/{project['id']}/transition", json={"target_state": "script_approved"}
    )
    assert res.status_code == 409  # no approved script version yet, and refs unverified

    v1 = (await client.get(f"/api/projects/{project['id']}/scripts")).json()[0]
    await client.post(f"/api/scripts/{v1['id']}/approve")

    refs = (await client.get(f"/api/projects/{project['id']}/references")).json()
    res = await client.post(
        f"/api/projects/{project['id']}/transition", json={"target_state": "script_approved"}
    )
    assert res.status_code == 409  # approved script exists, but reference still unverified

    for ref in refs:
        await client.post(f"/api/references/{ref['id']}/verify")

    res = await client.post(
        f"/api/projects/{project['id']}/transition", json={"target_state": "script_approved"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "script_approved"


async def test_editing_reference_clears_verification(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)
    await client.post(f"/api/projects/{project['id']}/outline")
    ref = (await client.get(f"/api/projects/{project['id']}/references")).json()[0]

    await client.post(f"/api/references/{ref['id']}/verify")
    res = await client.patch(f"/api/references/{ref['id']}", json={"reference": "Psalm 23:1"})
    assert res.status_code == 200
    assert res.json()["verified_at"] is None


async def test_expand_verses_uses_local_web_translation(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)
    await client.post(f"/api/projects/{project['id']}/references", json={"reference": "John 3:16"})
    v1 = (await client.post(f"/api/projects/{project['id']}/outline")).json()

    res = await client.post(f"/api/scripts/{v1['id']}/expand-verses")
    assert res.status_code == 200
    body = res.json()
    john_ref = next(r for r in body["references"] if r["reference"] == "John 3:16")
    assert john_ref["translation"] == "WEB"
    assert john_ref["unavailable"] is False
    assert "God so loved the world" in john_ref["text"]


async def test_expand_verses_reports_unavailable_outside_local_sample(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)
    await client.post(
        f"/api/projects/{project['id']}/references", json={"reference": "Revelation 21:4"}
    )
    v1 = (await client.post(f"/api/projects/{project['id']}/outline")).json()

    res = await client.post(f"/api/scripts/{v1['id']}/expand-verses")
    body = res.json()
    rev_ref = next(r for r in body["references"] if r["reference"] == "Revelation 21:4")
    assert rev_ref["unavailable"] is True
    assert rev_ref["text"] is None


async def test_expand_verses_prefers_owner_pasted_text(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)
    created = (
        await client.post(f"/api/projects/{project['id']}/references", json={"reference": "Revelation 21:4"})
    ).json()
    await client.patch(
        f"/api/references/{created['id']}", json={"pasted_text": "He will wipe away every tear."}
    )
    v1 = (await client.post(f"/api/projects/{project['id']}/outline")).json()

    res = await client.post(f"/api/scripts/{v1['id']}/expand-verses")
    body = res.json()
    rev_ref = next(r for r in body["references"] if r["reference"] == "Revelation 21:4")
    assert rev_ref["translation"] == "Owner-supplied"
    assert rev_ref["text"] == "He will wipe away every tear."
