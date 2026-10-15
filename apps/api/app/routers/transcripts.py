import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import MediaAsset, MediaJob, Project, Transcript, Workspace
from app.deps import DbSession, get_current_workspace
from app.errors import BadRequestError, ConflictError, NotFoundError
from app.models.schemas import (
    MediaAssetOut,
    MediaJobOut,
    RenderRequest,
    TranscriptOut,
    TranscriptUpdateRequest,
)
from app.providers.storage import get_storage_provider
from app.providers.video import is_vertical_9_16
from app.routers.brand_profile import _get_or_create as get_or_create_brand_profile
from app.routers.media import _asset_to_out, _get_owned_asset
from app.services.captions import style_from_profile
from app.services.media_jobs import process_job
from app.services.srt import build_srt

router = APIRouter(tags=["transcripts"])


def _transcript_to_out(transcript: Transcript) -> dict:
    return {
        "id": transcript.id,
        "media_asset_id": transcript.media_asset_id,
        "segments": transcript.segments_json,
        "reviewed_at": transcript.reviewed_at,
    }


async def _get_owned_transcript(
    db: AsyncSession, workspace: Workspace, transcript_id: uuid.UUID
) -> Transcript:
    transcript = await db.get(Transcript, transcript_id)
    if transcript is None:
        raise NotFoundError("Transcript not found.")
    asset = await db.get(MediaAsset, transcript.media_asset_id)
    if asset is None:
        raise NotFoundError("Transcript not found.")
    project = await db.get(Project, asset.project_id)
    if project is None or project.workspace_id != workspace.id:
        raise NotFoundError("Transcript not found.")
    return transcript


@router.get("/api/media/{asset_id}/transcript", response_model=TranscriptOut)
async def get_transcript(
    asset_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    asset = await _get_owned_asset(db, workspace, asset_id)
    result = await db.execute(
        select(Transcript).where(Transcript.media_asset_id == asset.id).order_by(Transcript.created_at.desc())
    )
    transcript = result.scalars().first()
    if transcript is None:
        raise NotFoundError("No transcript yet for this media asset.")
    return _transcript_to_out(transcript)


@router.patch("/api/transcripts/{transcript_id}", response_model=TranscriptOut)
async def update_transcript(
    transcript_id: uuid.UUID,
    payload: TranscriptUpdateRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-008: correct segment text and/or timing; edits persist."""
    transcript = await _get_owned_transcript(db, workspace, transcript_id)
    transcript.segments_json = [s.model_dump() for s in payload.segments]
    await db.commit()
    await db.refresh(transcript)
    return _transcript_to_out(transcript)


@router.post("/api/transcripts/{transcript_id}/review", response_model=TranscriptOut)
async def review_transcript(
    transcript_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-008: Owner marks subtitles reviewed, which the state machine's
    Subtitled-state condition checks (app/services/state_machine.py)."""
    transcript = await _get_owned_transcript(db, workspace, transcript_id)
    transcript.reviewed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(transcript)
    return _transcript_to_out(transcript)


@router.post("/api/media/{asset_id}/export-srt", response_model=MediaAssetOut, status_code=201)
async def export_srt(
    asset_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-009: SRT export, available ahead of styled burn-in rendering."""
    asset = await _get_owned_asset(db, workspace, asset_id)
    result = await db.execute(
        select(Transcript).where(Transcript.media_asset_id == asset.id).order_by(Transcript.created_at.desc())
    )
    transcript = result.scalars().first()
    if transcript is None:
        raise ConflictError("Transcribe this video before exporting subtitles.")

    srt_text = build_srt(transcript.segments_json)
    storage = get_storage_provider()
    object_key = f"srt/{workspace.id}/{asset.project_id}/{asset.id}.srt"
    storage.save(object_key, srt_text.encode("utf-8"))

    srt_asset = MediaAsset(
        project_id=asset.project_id,
        object_key=object_key,
        kind="srt",
        status="ready",
        metadata_json={"source_media_asset_id": str(asset.id)},
    )
    db.add(srt_asset)
    await db.commit()
    await db.refresh(srt_asset)

    settings = get_settings()
    out = _asset_to_out(srt_asset)
    out["download_url"] = storage.signed_url(srt_asset.object_key, settings.signed_url_expiry_seconds)
    return out


@router.post("/api/media/{asset_id}/render", response_model=MediaJobOut, status_code=202)
async def render_video(
    asset_id: uuid.UUID,
    payload: RenderRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> MediaJob:
    """FR-009 / AT-03: burn the reviewed subtitles into a 1080x1920 H.264
    MP4, styled from the brand profile and kept inside the safe zone. The
    source is preserved; each render is a new `render` asset (earlier ones
    may already be attached to posts, so they're never replaced)."""
    source = await _get_owned_asset(db, workspace, asset_id)
    if source.kind != "source":
        raise BadRequestError("Only an uploaded source video can be rendered.")
    if source.status != "ready":
        raise ConflictError("The source video must finish processing before it can be rendered.")

    result = await db.execute(
        select(Transcript)
        .where(Transcript.media_asset_id == source.id)
        .order_by(Transcript.created_at.desc())
    )
    transcript = result.scalars().first()
    if transcript is None:
        raise ConflictError("Transcribe this video before rendering captions.")
    if transcript.reviewed_at is None:
        # Burned-in captions can't be corrected after export, unlike an SRT.
        raise ConflictError(
            "Mark the subtitles reviewed before rendering — burned-in captions can't be edited later."
        )

    if not is_vertical_9_16(source.width, source.height) and payload.fit_mode is None:
        raise BadRequestError(
            f"This video is {source.width}x{source.height}, not 9:16 — choose centre-crop or "
            "blurred-background pad before rendering.",
            code="fit_mode_required",
        )

    profile = await get_or_create_brand_profile(db, workspace)
    try:
        style = style_from_profile(profile.subtitle_style_json)
    except ValidationError as exc:
        raise BadRequestError("Your saved subtitle style is invalid — fix it in Settings.") from exc

    render_id = uuid.uuid4()
    render = MediaAsset(
        id=render_id,
        project_id=source.project_id,
        object_key=f"render/{workspace.id}/{source.project_id}/{render_id}.mp4",
        kind="render",
        status="processing",
        metadata_json={
            "source_media_asset_id": str(source.id),
            "transcript_id": str(transcript.id),
            "fit_mode": None if is_vertical_9_16(source.width, source.height) else payload.fit_mode,
            "style": style.model_dump(),
        },
    )
    db.add(render)
    await db.flush()

    job = MediaJob(workspace_id=workspace.id, media_asset_id=render.id, job_type="render")
    db.add(job)
    await db.flush()
    await process_job(db, job)
    await db.commit()
    await db.refresh(job)
    return job
