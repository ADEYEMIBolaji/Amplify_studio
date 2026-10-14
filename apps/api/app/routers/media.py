import uuid
from math import ceil

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MediaAsset, MediaJob, MediaUploadSession, Project, Workspace
from app.deps import DbSession, get_current_workspace
from app.errors import BadRequestError, ConflictError, NotFoundError
from app.models.schemas import (
    MediaAssetOut,
    MediaJobOut,
    MediaUploadCompleteOut,
    MediaUploadInitRequest,
    MediaUploadSessionOut,
)
from app.providers.storage import (
    ObjectNotFoundError,
    SignedUrlExpiredError,
    SignedUrlInvalidError,
    get_storage_provider,
)
from app.routers.projects import _get_owned_project
from app.services.media_jobs import process_job

router = APIRouter(tags=["media"])

ALLOWED_EXTENSIONS = {".mp4", ".mov"}
ALLOWED_CONTENT_TYPES = {"video/mp4", "video/quicktime"}


def _session_to_out(session: MediaUploadSession) -> dict:
    return {
        "id": session.id,
        "project_id": session.project_id,
        "filename": session.filename,
        "total_size": session.total_size,
        "chunk_size": session.chunk_size,
        "total_chunks": session.total_chunks,
        "received_chunks": sorted(session.received_chunks),
        "status": session.status,
    }


async def _get_owned_session(
    db: AsyncSession, workspace: Workspace, session_id: uuid.UUID
) -> MediaUploadSession:
    session = await db.get(MediaUploadSession, session_id)
    if session is None or session.workspace_id != workspace.id:
        raise NotFoundError("Upload session not found.")
    return session


async def _get_owned_asset(db: AsyncSession, workspace: Workspace, asset_id: uuid.UUID) -> MediaAsset:
    asset = await db.get(MediaAsset, asset_id)
    if asset is None:
        raise NotFoundError("Media asset not found.")
    project = await db.get(Project, asset.project_id)
    if project is None or project.workspace_id != workspace.id:
        raise NotFoundError("Media asset not found.")
    return asset


def _asset_to_out(asset: MediaAsset) -> dict:
    download_url = None
    if asset.status == "ready":
        from app.config import get_settings

        settings = get_settings()
        storage = get_storage_provider()
        download_url = storage.signed_url(asset.object_key, settings.signed_url_expiry_seconds)

    return {
        "id": asset.id,
        "project_id": asset.project_id,
        "kind": asset.kind,
        "status": asset.status,
        "duration_seconds": float(asset.duration_seconds) if asset.duration_seconds is not None else None,
        "width": asset.width,
        "height": asset.height,
        "metadata_json": asset.metadata_json,
        "download_url": download_url,
    }


@router.post("/api/media/uploads", response_model=MediaUploadSessionOut, status_code=201)
async def init_upload(
    payload: MediaUploadInitRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-007: resumable upload — the client uploads fixed-size chunks and can
    probe which ones already landed after a dropped connection."""
    project = await _get_owned_project(db, workspace, payload.project_id)

    from app.config import get_settings

    settings = get_settings()
    if payload.total_size > settings.max_upload_bytes:
        raise BadRequestError(
            f"File is too large — max {settings.max_upload_bytes // (1024 * 1024)} MB.",
            code="upload_too_large",
        )

    import os

    ext = os.path.splitext(payload.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise BadRequestError(f"'{ext}' is not an accepted video format (mp4, mov only).")
    if payload.content_type not in ALLOWED_CONTENT_TYPES:
        raise BadRequestError(f"'{payload.content_type}' is not an accepted video content type.")

    total_chunks = ceil(payload.total_size / payload.chunk_size)
    session = MediaUploadSession(
        workspace_id=workspace.id,
        project_id=project.id,
        filename=payload.filename,
        content_type=payload.content_type,
        total_size=payload.total_size,
        chunk_size=payload.chunk_size,
        total_chunks=total_chunks,
        received_chunks=[],
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_to_out(session)


@router.get("/api/media/uploads/{upload_id}", response_model=MediaUploadSessionOut)
async def get_upload_session(
    upload_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    session = await _get_owned_session(db, workspace, upload_id)
    return _session_to_out(session)


@router.put("/api/media/uploads/{upload_id}/chunks/{chunk_index}", response_model=MediaUploadSessionOut)
async def upload_chunk(
    upload_id: uuid.UUID,
    chunk_index: int,
    request: Request,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    session = await _get_owned_session(db, workspace, upload_id)
    if session.status != "pending":
        raise ConflictError("This upload session is no longer accepting chunks.")
    if chunk_index < 0 or chunk_index >= session.total_chunks:
        raise BadRequestError(f"Chunk index out of range (expected 0-{session.total_chunks - 1}).")

    body = await request.body()
    storage = get_storage_provider()
    storage.save(f"_uploads/{session.id}/{chunk_index}.part", body)

    if chunk_index not in session.received_chunks:
        session.received_chunks = sorted([*session.received_chunks, chunk_index])

    await db.commit()
    await db.refresh(session)
    return _session_to_out(session)


@router.post(
    "/api/media/uploads/{upload_id}/complete",
    response_model=MediaUploadCompleteOut,
    status_code=202,
)
async def complete_upload(
    upload_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    session = await _get_owned_session(db, workspace, upload_id)
    if session.status != "pending":
        raise ConflictError("This upload session was already completed or aborted.")

    expected = set(range(session.total_chunks))
    missing = expected - set(session.received_chunks)
    if missing:
        raise ConflictError(f"Missing chunk(s): {sorted(missing)[:5]}{'…' if len(missing) > 5 else ''}")

    storage = get_storage_provider()
    import os

    ext = os.path.splitext(session.filename)[1].lower()
    object_key = f"source/{workspace.id}/{session.project_id}/{session.id}{ext}"

    combined = bytearray()
    for i in range(session.total_chunks):
        combined.extend(storage.read(f"_uploads/{session.id}/{i}.part"))
    storage.save(object_key, bytes(combined))

    for i in range(session.total_chunks):
        storage.delete(f"_uploads/{session.id}/{i}.part")

    asset = MediaAsset(
        project_id=session.project_id,
        object_key=object_key,
        kind="source",
        status="processing",
        metadata_json={"original_filename": session.filename, "content_type": session.content_type},
    )
    db.add(asset)
    await db.flush()

    job = MediaJob(workspace_id=workspace.id, media_asset_id=asset.id, job_type="normalize")
    db.add(job)
    await db.flush()

    session.status = "completed"
    await process_job(db, job)
    await db.commit()
    await db.refresh(asset)
    await db.refresh(job)

    return {"media_asset_id": asset.id, "job_id": job.id}


@router.get("/api/media/{asset_id}", response_model=MediaAssetOut)
async def get_media_asset(
    asset_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    asset = await _get_owned_asset(db, workspace, asset_id)
    return _asset_to_out(asset)


@router.get("/api/projects/{project_id}/media", response_model=list[MediaAssetOut])
async def list_project_media(
    project_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> list[dict]:
    project = await _get_owned_project(db, workspace, project_id)
    result = await db.execute(select(MediaAsset).where(MediaAsset.project_id == project.id))
    return [_asset_to_out(a) for a in result.scalars().all()]


@router.post("/api/media/{asset_id}/transcribe", response_model=MediaJobOut, status_code=202)
async def transcribe_media(
    asset_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> MediaJob:
    asset = await _get_owned_asset(db, workspace, asset_id)
    if asset.status != "ready":
        raise ConflictError("The source video must finish processing before it can be transcribed.")

    job = MediaJob(workspace_id=workspace.id, media_asset_id=asset.id, job_type="transcribe")
    db.add(job)
    await db.flush()
    await process_job(db, job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/api/jobs/{job_id}", response_model=MediaJobOut)
async def get_job(
    job_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> MediaJob:
    job = await db.get(MediaJob, job_id)
    if job is None or job.workspace_id != workspace.id:
        raise NotFoundError("Job not found.")
    return job


@router.get("/api/media/signed/{token}")
async def download_signed(token: str) -> Response:
    """Resolves a signed URL token to the underlying private object.
    Deliberately unauthenticated by Bearer token — the signature and expiry
    embedded in the token itself are what makes this safe (FRD rule 8)."""
    storage = get_storage_provider()
    try:
        key = storage.resolve_signed_token(token)
        data = storage.read(key)
    except SignedUrlExpiredError as exc:
        raise BadRequestError("This link has expired.", code="signed_url_expired") from exc
    except (SignedUrlInvalidError, ObjectNotFoundError) as exc:
        raise NotFoundError("Not found.") from exc

    return Response(content=data, media_type="application/octet-stream")
