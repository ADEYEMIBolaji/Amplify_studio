"""AT-03 (Video, transcription half): transcribe, edit a subtitle's text and
timing, mark reviewed (advances to Subtitled per the state machine), and
export SRT (FR-008, FR-009).
"""

from httpx import AsyncClient

from tests.conftest import make_user


async def _uploaded_asset(client: AsyncClient) -> dict:
    project = (await client.post("/api/projects", json={"title": "Sermon clip", "topic": "Hope"})).json()
    session = (
        await client.post(
            "/api/media/uploads",
            json={
                "project_id": project["id"],
                "filename": "clip.mp4",
                "content_type": "video/mp4",
                "total_size": 20,
                "chunk_size": 10,
            },
        )
    ).json()
    await client.put(f"/api/media/uploads/{session['id']}/chunks/0", content=b"0123456789")
    await client.put(f"/api/media/uploads/{session['id']}/chunks/1", content=b"abcdefghij")
    complete = (await client.post(f"/api/media/uploads/{session['id']}/complete")).json()
    asset = (await client.get(f"/api/media/{complete['media_asset_id']}")).json()
    return {"project": project, "asset": asset}


async def test_transcribe_produces_timecoded_segments(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _uploaded_asset(client)

    res = await client.post(f"/api/media/{ctx['asset']['id']}/transcribe")
    assert res.status_code == 202
    assert res.json()["status"] == "succeeded"

    transcript = (await client.get(f"/api/media/{ctx['asset']['id']}/transcript")).json()
    assert len(transcript["segments"]) > 0
    for segment in transcript["segments"]:
        assert segment["end"] > segment["start"]
    assert transcript["reviewed_at"] is None


async def test_edit_subtitle_text_and_timing_persists(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _uploaded_asset(client)
    await client.post(f"/api/media/{ctx['asset']['id']}/transcribe")
    transcript = (await client.get(f"/api/media/{ctx['asset']['id']}/transcript")).json()

    edited = transcript["segments"]
    edited[0] = {"start": 0.0, "end": 2.5, "text": "Corrected opening line."}
    res = await client.patch(f"/api/transcripts/{transcript['id']}", json={"segments": edited})
    assert res.status_code == 200

    refetched = (await client.get(f"/api/media/{ctx['asset']['id']}/transcript")).json()
    assert refetched["segments"][0]["text"] == "Corrected opening line."
    assert refetched["segments"][0]["end"] == 2.5


async def test_review_transcript_advances_to_subtitled_state(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _uploaded_asset(client)
    await client.post(f"/api/media/{ctx['asset']['id']}/transcribe")
    transcript = (await client.get(f"/api/media/{ctx['asset']['id']}/transcript")).json()

    project_id = ctx["project"]["id"]
    v1 = (await client.post(f"/api/projects/{project_id}/outline")).json()
    await client.post(f"/api/scripts/{v1['id']}/approve")
    refs = (await client.get(f"/api/projects/{project_id}/references")).json()
    for ref in refs:
        await client.post(f"/api/references/{ref['id']}/verify")

    assert (
        await client.post(f"/api/projects/{project_id}/transition", json={"target_state": "scripting"})
    ).status_code == 200
    assert (
        await client.post(f"/api/projects/{project_id}/transition", json={"target_state": "script_approved"})
    ).status_code == 200
    assert (
        await client.post(f"/api/projects/{project_id}/transition", json={"target_state": "recorded"})
    ).status_code == 200

    res = await client.post(f"/api/projects/{project_id}/transition", json={"target_state": "subtitled"})
    assert res.status_code == 409  # not reviewed yet

    await client.post(f"/api/transcripts/{transcript['id']}/review")

    res = await client.post(f"/api/projects/{project_id}/transition", json={"target_state": "subtitled"})
    assert res.status_code == 200


async def test_export_srt_matches_transcript_segments(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _uploaded_asset(client)
    await client.post(f"/api/media/{ctx['asset']['id']}/transcribe")
    transcript = (await client.get(f"/api/media/{ctx['asset']['id']}/transcript")).json()

    res = await client.post(f"/api/media/{ctx['asset']['id']}/export-srt")
    assert res.status_code == 201
    srt_asset = res.json()
    assert srt_asset["kind"] == "srt"
    assert srt_asset["status"] == "ready"

    download_path = srt_asset["download_url"].split("/api/media/signed/")[1]
    srt_text = (await client.get(f"/api/media/signed/{download_path}")).content.decode()
    assert "1\n" in srt_text
    assert transcript["segments"][0]["text"] in srt_text
    assert "-->" in srt_text


async def test_export_srt_without_transcript_fails(client: AsyncClient, as_user):
    as_user(make_user())
    ctx = await _uploaded_asset(client)

    res = await client.post(f"/api/media/{ctx['asset']['id']}/export-srt")
    assert res.status_code == 409


async def test_vocabulary_seed_and_custom_additions(client: AsyncClient, as_user):
    as_user(make_user())

    res = await client.get("/api/vocabulary")
    body = res.json()
    assert "Yahweh" in body["seed"]
    assert body["custom"] == []

    res = await client.post("/api/vocabulary", json={"term": "Nehemiah's wall"})
    assert res.status_code == 201

    res = await client.get("/api/vocabulary")
    assert any(t["term"] == "Nehemiah's wall" for t in res.json()["custom"])

    res = await client.post("/api/vocabulary", json={"term": "Nehemiah's wall"})
    assert res.status_code == 409
