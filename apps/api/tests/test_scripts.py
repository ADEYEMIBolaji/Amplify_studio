"""AT-01 (Creation): generate a structured script with 2-3 hook variants,
select a hook, edit a section, verify edits persist after "refresh", restore
a previous version, and confirm version provenance is tracked.
"""

from httpx import AsyncClient

from tests.conftest import make_user


async def _create_project(client: AsyncClient, title="Faith in hard seasons", topic="Trust") -> dict:
    return (await client.post("/api/projects", json={"title": title, "topic": topic})).json()


async def test_generate_hooks_returns_two_to_three_labelled_variants(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)

    res = await client.post(f"/api/projects/{project['id']}/hooks")
    assert res.status_code == 201
    hooks = res.json()
    assert 2 <= len(hooks) <= 3
    for hook in hooks:
        assert hook["hook_type"] in {"question", "bold_claim", "story", "scripture_first", "other"}
        assert hook["selected"] is False


async def test_select_hook_sets_project_hook_type_and_deselects_others(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)
    hooks = (await client.post(f"/api/projects/{project['id']}/hooks")).json()

    chosen = hooks[0]
    res = await client.patch(f"/api/hooks/{chosen['id']}", json={"selected": True})
    assert res.status_code == 200
    assert res.json()["selected"] is True

    others = (await client.get(f"/api/projects/{project['id']}/hooks")).json()
    assert sum(1 for h in others if h["selected"]) == 1

    updated_project = (await client.get(f"/api/projects/{project['id']}")).json()
    assert updated_project["hook_type"] == chosen["hook_type"]


async def test_generate_outline_creates_version_with_placeholders_only(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)

    res = await client.post(f"/api/projects/{project['id']}/outline")
    assert res.status_code == 201
    version = res.json()
    assert version["version_no"] == 1
    assert version["source"] == "ai"
    assert version["word_count"] > 0
    assert version["estimated_duration_seconds"] > 0

    biblical_context = version["sections"]["biblical_context"]["text"]
    assert "{{" in biblical_context and "}}" in biblical_context

    refs = (await client.get(f"/api/projects/{project['id']}/references")).json()
    assert len(refs) >= 1
    assert refs[0]["source"] == "ai"
    assert refs[0]["verified_at"] is None


async def test_manual_edit_creates_new_version_and_persists(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)
    v1 = (await client.post(f"/api/projects/{project['id']}/outline")).json()

    res = await client.patch(
        f"/api/scripts/{v1['id']}", json={"sections": {"closing_cta": "Comment 'AMEN' if this blessed you."}}
    )
    assert res.status_code == 201
    v2 = res.json()
    assert v2["version_no"] == 2
    assert v2["sections"]["closing_cta"]["source"] == "manual"
    assert v2["sections"]["closing_cta"]["text"] == "Comment 'AMEN' if this blessed you."
    assert v2["source"] == "mixed"

    # "Refresh": re-fetch and confirm the edit is still there.
    refetched = (await client.get(f"/api/scripts/{v2['id']}")).json()
    assert refetched["sections"]["closing_cta"]["text"] == "Comment 'AMEN' if this blessed you."


async def test_regenerate_section_blocked_without_confirm_when_manually_edited(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)
    v1 = (await client.post(f"/api/projects/{project['id']}/outline")).json()
    v2 = (
        await client.patch(f"/api/scripts/{v1['id']}", json={"sections": {"main_teaching": "My own words."}})
    ).json()

    res = await client.post(f"/api/scripts/{v2['id']}/regenerate-section", json={"section": "main_teaching"})
    assert res.status_code == 409
    assert res.json()["code"] == "manual_edit_would_be_overwritten"

    res = await client.post(
        f"/api/scripts/{v2['id']}/regenerate-section", json={"section": "main_teaching", "confirm": True}
    )
    assert res.status_code == 201
    assert res.json()["sections"]["main_teaching"]["source"] == "ai"


async def test_restore_previous_version(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)
    v1 = (await client.post(f"/api/projects/{project['id']}/outline")).json()
    await client.patch(f"/api/scripts/{v1['id']}", json={"sections": {"hook": "Edited hook"}})

    res = await client.post(f"/api/scripts/{v1['id']}/restore")
    assert res.status_code == 201
    restored = res.json()
    assert restored["version_no"] == 3
    assert restored["sections"]["hook"]["text"] == v1["sections"]["hook"]["text"]


async def test_approve_version_sets_project_approved_script(client: AsyncClient, as_user):
    as_user(make_user())
    project = await _create_project(client)
    v1 = (await client.post(f"/api/projects/{project['id']}/outline")).json()

    res = await client.post(f"/api/scripts/{v1['id']}/approve")
    assert res.status_code == 200
    assert res.json()["approved"] is True

    updated_project = (await client.get(f"/api/projects/{project['id']}")).json()
    assert updated_project["approved_script_version_id"] == v1["id"]
