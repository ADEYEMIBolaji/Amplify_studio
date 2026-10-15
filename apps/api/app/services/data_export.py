"""Data export and deletion — FR-030.

Export returns everything in the workspace as JSON (media as signed
download links, never raw bytes inline). Deletion removes storage objects
explicitly (the filesystem/Supabase Storage isn't covered by SQL cascade)
and then the DB row, which cascades to every workspace-scoped child table —
see supabase/migrations/0001_init.sql, every workspace_id FK is
`on delete cascade`.
"""

import json
import uuid
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import (
    AiJob,
    BrandProfile,
    CustomVocabulary,
    Experiment,
    FollowerSnapshot,
    HookVariant,
    MediaAsset,
    MetricSnapshot,
    Project,
    Reminder,
    ScriptureReference,
    ScriptVersion,
    SocialPost,
    TopicTag,
    Transcript,
    WeeklyReview,
    Workspace,
)
from app.providers.storage import get_storage_provider


def _json_default(value):
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    raise TypeError(f"Not JSON serialisable: {type(value)}")


def _row_to_dict(row) -> dict:
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


async def _reminder_rows(db: AsyncSession, post_ids: list[uuid.UUID]) -> list[dict]:
    if not post_ids:
        return []
    result = await db.execute(select(Reminder).where(Reminder.social_post_id.in_(post_ids)))
    return [_row_to_dict(r) for r in result.scalars().all()]


async def export_workspace(db: AsyncSession, workspace: Workspace) -> dict:
    """FR-030: export all workspace data (JSON here; CSV is a documented gap
    — see docs/plan.md Week 6 notes) plus signed media links."""
    settings = get_settings()
    storage = get_storage_provider()

    project_result = await db.execute(select(Project).where(Project.workspace_id == workspace.id))
    projects = list(project_result.scalars().all())
    project_ids = [p.id for p in projects]

    async def rows_for(model, *, by_project: bool = False, by_workspace: bool = True):
        if by_project and project_ids:
            result = await db.execute(select(model).where(model.project_id.in_(project_ids)))
        elif by_workspace:
            result = await db.execute(select(model).where(model.workspace_id == workspace.id))
        else:
            return []
        return [_row_to_dict(r) for r in result.scalars().all()]

    media_assets: list[MediaAsset] = []
    if project_ids:
        media_result = await db.execute(select(MediaAsset).where(MediaAsset.project_id.in_(project_ids)))
        media_assets = list(media_result.scalars().all())
    media_rows = []
    for asset in media_assets:
        row = _row_to_dict(asset)
        row["download_url"] = (
            storage.signed_url(asset.object_key, settings.signed_url_expiry_seconds)
            if asset.status == "ready"
            else None
        )
        media_rows.append(row)

    transcript_rows = []
    if media_assets:
        asset_ids = [a.id for a in media_assets]
        result = await db.execute(select(Transcript).where(Transcript.media_asset_id.in_(asset_ids)))
        transcript_rows = [_row_to_dict(t) for t in result.scalars().all()]

    social_post_result = await db.execute(select(SocialPost).where(SocialPost.workspace_id == workspace.id))
    social_posts = list(social_post_result.scalars().all())
    post_ids = [p.id for p in social_posts]

    metric_rows = []
    if post_ids:
        result = await db.execute(select(MetricSnapshot).where(MetricSnapshot.social_post_id.in_(post_ids)))
        metric_rows = [_row_to_dict(m) for m in result.scalars().all()]

    brand_profile_result = await db.execute(
        select(BrandProfile).where(BrandProfile.workspace_id == workspace.id)
    )
    brand_profile = brand_profile_result.scalar_one_or_none()

    return {
        "workspace": _row_to_dict(workspace),
        "brand_profile": _row_to_dict(brand_profile) if brand_profile else None,
        "topic_tags": await rows_for(TopicTag),
        "custom_vocabulary": await rows_for(CustomVocabulary),
        "projects": [_row_to_dict(p) for p in projects],
        "script_versions": await rows_for(ScriptVersion, by_project=True, by_workspace=False),
        "hook_variants": await rows_for(HookVariant, by_project=True, by_workspace=False),
        "scripture_references": await rows_for(ScriptureReference, by_project=True, by_workspace=False),
        "media_assets": media_rows,
        "transcripts": transcript_rows,
        "social_posts": [_row_to_dict(p) for p in social_posts],
        "metric_snapshots": metric_rows,
        "follower_snapshots": await rows_for(FollowerSnapshot),
        "reminders": await _reminder_rows(db, post_ids),
        "experiments": await rows_for(Experiment),
        "weekly_reviews": await rows_for(WeeklyReview),
        "ai_jobs": await rows_for(AiJob),
    }


def export_to_json(export: dict) -> str:
    return json.dumps(export, default=_json_default, indent=2)


async def _delete_media_objects(db: AsyncSession, asset_ids: list[uuid.UUID]) -> None:
    if not asset_ids:
        return
    storage = get_storage_provider()
    result = await db.execute(select(MediaAsset).where(MediaAsset.id.in_(asset_ids)))
    for asset in result.scalars().all():
        if storage.exists(asset.object_key):
            storage.delete(asset.object_key)


async def delete_project(db: AsyncSession, project: Project) -> None:
    """FR-030: deleting a project removes its media objects and DB rows
    (the latter via cascading FKs — see module docstring)."""
    result = await db.execute(select(MediaAsset.id).where(MediaAsset.project_id == project.id))
    await _delete_media_objects(db, [row[0] for row in result.all()])
    await db.delete(project)


async def delete_media_asset(db: AsyncSession, asset: MediaAsset) -> None:
    await _delete_media_objects(db, [asset.id])
    await db.delete(asset)


async def delete_workspace(db: AsyncSession, workspace: Workspace) -> None:
    project_result = await db.execute(select(Project.id).where(Project.workspace_id == workspace.id))
    project_ids = [row[0] for row in project_result.all()]
    if project_ids:
        asset_result = await db.execute(select(MediaAsset.id).where(MediaAsset.project_id.in_(project_ids)))
        await _delete_media_objects(db, [row[0] for row in asset_result.all()])
    await db.delete(workspace)
