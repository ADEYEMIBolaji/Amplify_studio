"""Processes one media_jobs row: normalize, transcribe, or render.

Called inline right after a job is enqueued (so the fake providers feel
instant for the single-user pilot) and also by the worker's poll loop,
which exists to pick up anything left `pending` after a crash — that's
the actual value of tracking status/retry_count in the DB rather than
just awaiting the call directly.
"""

import tempfile
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CustomVocabulary, MediaAsset, MediaJob, Transcript
from app.providers.storage import get_storage_provider
from app.providers.transcription import get_transcription_provider
from app.providers.video import VideoProcessorUnavailableError, get_video_processor
from app.providers.vocabulary_seed import SEED_VOCABULARY
from app.services.captions import SubtitleStyle, build_ass, build_caption_events


async def _run_normalize(db: AsyncSession, job: MediaJob, asset: MediaAsset) -> dict:
    storage = get_storage_provider()
    processor = get_video_processor()
    data = storage.read(asset.object_key)

    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / f"input{Path(asset.object_key).suffix}"
        output_path = Path(tmp) / f"output{Path(asset.object_key).suffix}"
        input_path.write_bytes(data)

        info = processor.normalize(input_path, output_path)
        storage.save(asset.object_key, output_path.read_bytes())

    asset.duration_seconds = info.duration_seconds
    asset.width = info.width
    asset.height = info.height
    asset.metadata_json = {**asset.metadata_json, "codec": info.codec, "degraded": info.is_degraded}
    asset.status = "ready"
    return {"duration_seconds": info.duration_seconds, "degraded": info.is_degraded}


async def _run_transcribe(db: AsyncSession, job: MediaJob, asset: MediaAsset) -> dict:
    storage = get_storage_provider()
    provider = get_transcription_provider()
    data = storage.read(asset.object_key)

    result = await db.execute(
        select(CustomVocabulary.term).where(CustomVocabulary.workspace_id == job.workspace_id)
    )
    vocabulary = SEED_VOCABULARY + [row for row in result.scalars().all()]

    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / f"input{Path(asset.object_key).suffix}"
        input_path.write_bytes(data)
        draft = await provider.transcribe(
            media_path=input_path,
            duration_seconds=float(asset.duration_seconds or 30),
            vocabulary=vocabulary,
        )

    transcript = Transcript(
        media_asset_id=asset.id,
        segments_json=[{"start": s.start, "end": s.end, "text": s.text} for s in draft.segments],
    )
    db.add(transcript)
    asset.status = "ready"
    return {"language": draft.language, "segment_count": len(draft.segments)}


async def _run_render(db: AsyncSession, job: MediaJob, asset: MediaAsset) -> dict:
    """FR-009 burn-in render. `asset` is the render asset (created up front
    with status `processing`); the source is never modified — the render is
    written to its own object key."""
    meta = asset.metadata_json
    source = await db.get(MediaAsset, uuid.UUID(meta["source_media_asset_id"]))
    transcript = await db.get(Transcript, uuid.UUID(meta["transcript_id"]))
    if source is None or transcript is None:
        raise LookupError("Render source or transcript no longer exists.")

    style = SubtitleStyle.model_validate(meta["style"])
    storage = get_storage_provider()
    processor = get_video_processor()

    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / f"input{Path(source.object_key).suffix}"
        subtitle_path = Path(tmp) / "captions.ass"
        output_path = Path(tmp) / "render.mp4"
        input_path.write_bytes(storage.read(source.object_key))
        subtitle_path.write_text(build_ass(transcript.segments_json, style), encoding="utf-8")

        info = processor.render_captions(input_path, output_path, subtitle_path, meta.get("fit_mode"))
        storage.save(asset.object_key, output_path.read_bytes())

    caption_count = len(build_caption_events(transcript.segments_json, style))
    asset.duration_seconds = info.duration_seconds
    asset.width = info.width
    asset.height = info.height
    asset.metadata_json = {
        **meta,
        "codec": info.codec,
        "degraded": info.is_degraded,
        "caption_count": caption_count,
    }
    asset.status = "ready"
    return {"caption_count": caption_count, "degraded": info.is_degraded}


async def process_job(db: AsyncSession, job: MediaJob) -> None:
    job.status = "running"
    await db.flush()

    asset = await db.get(MediaAsset, job.media_asset_id)
    if asset is None:
        job.status = "failed"
        job.error_code = "media_asset_not_found"
        return

    try:
        if job.job_type == "normalize":
            result = await _run_normalize(db, job, asset)
        elif job.job_type == "transcribe":
            result = await _run_transcribe(db, job, asset)
        elif job.job_type == "render":
            result = await _run_render(db, job, asset)
        else:
            raise NotImplementedError(f"Job type '{job.job_type}' is not implemented.")

        job.status = "succeeded"
        job.result_json = result
    except VideoProcessorUnavailableError as exc:
        job.retry_count += 1
        job.error_code = "video_processor_unavailable"
        job.status = "failed" if job.retry_count >= job.max_retries else "pending"
        asset.status = "failed"
        _ = exc
    except Exception as exc:  # noqa: BLE001 — isolate failures per job, never crash the caller
        job.retry_count += 1
        job.error_code = type(exc).__name__
        job.status = "failed" if job.retry_count >= job.max_retries else "pending"
        asset.status = "failed"
