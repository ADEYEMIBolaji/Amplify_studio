import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MediaAsset, ScriptVersion, SocialPost, Workspace
from app.deps import DbSession, get_current_workspace
from app.errors import BadRequestError, ConflictError, NotFoundError
from app.models.schemas import (
    PublishRequest,
    RepurposeRequest,
    SocialPostOut,
    SocialPostUpdate,
)
from app.providers.factory import get_llm_provider
from app.routers.brand_profile import _get_or_create as get_or_create_brand_profile
from app.routers.projects import _get_owned_project
from app.services import ai_jobs
from app.services import posts as posts_service
from app.services import reminders as reminders_service
from app.services.platform_limits import (
    check_caption_against_limits,
    check_media_against_limits,
    get_effective_limits,
)
from app.services.scripts import get_latest_version

router = APIRouter(tags=["posts"])

VALID_PLATFORMS = {"instagram", "tiktok", "facebook", "x"}


async def _get_owned_post(db: AsyncSession, workspace: Workspace, post_id: uuid.UUID) -> SocialPost:
    post = await db.get(SocialPost, post_id)
    if post is None or post.workspace_id != workspace.id:
        raise NotFoundError("Post not found.")
    return post


@router.post("/api/projects/{project_id}/repurpose", response_model=list[SocialPostOut], status_code=201)
async def repurpose(
    project_id: uuid.UUID,
    payload: RepurposeRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> list[SocialPost]:
    """FR-010: platform captions/hashtags/CTAs from the approved script."""
    project = await _get_owned_project(db, workspace, project_id)
    profile = await get_or_create_brand_profile(db, workspace)

    unknown = [p for p in payload.platforms if p not in VALID_PLATFORMS]
    if unknown:
        raise BadRequestError(f"Unknown platform(s): {', '.join(unknown)}")

    version: ScriptVersion | None = None
    if project.approved_script_version_id:
        version = await db.get(ScriptVersion, project.approved_script_version_id)
    if version is None:
        version = await get_latest_version(db, project.id)
    if version is None:
        raise ConflictError("Generate a script before creating platform captions.")

    script_sections = {name: section["text"] for name, section in version.sections_json.items()}
    provider = get_llm_provider()
    posts: list[SocialPost] = []

    for platform in payload.platforms:
        draft = await provider.generate_caption(
            platform=platform, topic=project.topic, script_sections=script_sections, brand_profile=profile
        )
        job = ai_jobs.record(
            db,
            workspace_id=workspace.id,
            job_type="repurpose",
            model_id=draft.model_id,
            prompt_version=draft.prompt_version,
            input_payload=f"{project.id}:{platform}:{version.id}",
            result_json={"caption": draft.caption, "hashtags": draft.hashtags, "cta": draft.cta},
        )
        await db.flush()

        result = await db.execute(
            select(SocialPost).where(SocialPost.project_id == project.id, SocialPost.platform == platform)
        )
        post = result.scalars().first()
        if post is None:
            post = SocialPost(project_id=project.id, workspace_id=workspace.id, platform=platform)
            db.add(post)

        post.caption = draft.caption
        post.hashtags = draft.hashtags
        post.cta = draft.cta
        posts.append(post)
        _ = job

    await db.commit()
    for post in posts:
        await db.refresh(post)
    return posts


@router.get("/api/projects/{project_id}/posts", response_model=list[SocialPostOut])
async def list_project_posts(
    project_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> list[SocialPost]:
    project = await _get_owned_project(db, workspace, project_id)
    result = await db.execute(select(SocialPost).where(SocialPost.project_id == project.id))
    return list(result.scalars().all())


@router.get("/api/calendar", response_model=list[SocialPostOut])
async def get_calendar(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> list[SocialPost]:
    """FR-011: planned posts. scheduled_at is UTC; `timezone` on each post is
    the Owner's IANA zone for display — convert client-side for correct
    BST/GMT rendering rather than trusting a fixed offset."""
    query = select(SocialPost).where(SocialPost.workspace_id == workspace.id)
    if from_ is not None:
        query = query.where(SocialPost.scheduled_at >= from_)
    if to is not None:
        query = query.where(SocialPost.scheduled_at <= to)
    result = await db.execute(query.order_by(SocialPost.scheduled_at))
    return list(result.scalars().all())


@router.patch("/api/posts/{post_id}", response_model=SocialPostOut)
async def update_post(
    post_id: uuid.UUID,
    payload: SocialPostUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> SocialPost:
    post = await _get_owned_post(db, workspace, post_id)
    profile = await get_or_create_brand_profile(db, workspace)

    next_caption = payload.caption if payload.caption is not None else post.caption
    next_hashtags = payload.hashtags if payload.hashtags is not None else post.hashtags
    if payload.caption is not None or payload.hashtags is not None:
        limits = await get_effective_limits(db, post.platform, profile)
        check_caption_against_limits(next_caption, next_hashtags, limits)
        post.caption = next_caption
        post.hashtags = next_hashtags

    if payload.cta is not None:
        post.cta = payload.cta

    if payload.media_asset_id is not None:
        asset = await db.get(MediaAsset, payload.media_asset_id)
        if asset is None or asset.project_id != post.project_id:
            raise NotFoundError("Media asset not found for this project.")
        if asset.status != "ready":
            raise ConflictError("This export hasn't finished processing yet.")
        limits = await get_effective_limits(db, post.platform, profile)
        check_media_against_limits(asset, limits)  # FR-026
        post.media_asset_id = asset.id
        post.status = "ready" if post.status == "draft" else post.status

    if payload.scheduled_at_local is not None:
        timezone = payload.timezone or profile.timezone
        scheduled_at = posts_service.local_to_utc(payload.scheduled_at_local, timezone)
        post.scheduled_at = scheduled_at
        post.timezone = timezone
        post.posting_slot = posts_service.compute_posting_slot(scheduled_at, timezone)
        await reminders_service.schedule_reminders(db, post)

    if payload.status is not None:
        if payload.status not in {"draft", "ready", "published"}:
            raise BadRequestError(f"'{payload.status}' is not a valid post status.")
        post.status = payload.status

    await db.commit()
    await db.refresh(post)
    return post


@router.post("/api/posts/{post_id}/publish", response_model=SocialPostOut)
async def publish_post(
    post_id: uuid.UUID,
    payload: PublishRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> SocialPost:
    """FR-012: publication evidence. Parses the external post ID where the
    platform's URL pattern allows, so CSV metric imports (Week 5) can match."""
    post = await _get_owned_post(db, workspace, post_id)
    post.status = "published"
    post.published_at = payload.published_at or datetime.now(UTC)
    post.external_url = payload.external_url
    post.external_post_id = posts_service.parse_external_post_id(post.platform, payload.external_url)

    await reminders_service.cancel_reminders(db, post.id)  # FR-027: reminders stop once published

    await db.commit()
    await db.refresh(post)
    return post


@router.post("/api/posts/{post_id}/unpublish", response_model=SocialPostOut)
async def unpublish_post(
    post_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> SocialPost:
    """FR-012: 'allow reversal and corrections'."""
    post = await _get_owned_post(db, workspace, post_id)
    post.status = "ready" if post.media_asset_id else "draft"
    post.published_at = None
    post.external_url = None
    post.external_post_id = None

    await db.commit()
    await db.refresh(post)
    return post
