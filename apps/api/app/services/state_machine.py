"""Project state machine — FRD section 1.1.

Forward transitions move exactly one state at a time and must satisfy the
listed entry condition; the Owner may move a project back to any earlier
state freely. Every transition is logged to project_state_events.

Most entry conditions reference tables that later sprint weeks populate
(script_versions in Week 2, media_assets in Week 3, social_posts/
metric_snapshots in Weeks 4-5) — the tables already exist from the Week 1
migration, so these checks are real from day one even though most projects
won't be able to satisfy them until the relevant feature ships.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    PROJECT_STATES,
    BrandProfile,
    MediaAsset,
    MetricSnapshot,
    PlatformLimit,
    Project,
    ProjectStateEvent,
    ScriptureReference,
    ScriptVersion,
    SocialPost,
    Transcript,
)
from app.errors import BadRequestError, ConflictError
from app.services.platform_limits import (
    check_media_against_limits,
    ensure_seeded,
    get_effective_limits,
)

NEXT_STATE = {state: PROJECT_STATES[i + 1] for i, state in enumerate(PROJECT_STATES[:-1])}


async def _has_script_version(db: AsyncSession, project_id) -> bool:
    result = await db.execute(
        select(ScriptVersion.id).where(ScriptVersion.project_id == project_id).limit(1)
    )
    return result.first() is not None


async def _script_approved_ok(db: AsyncSession, project: Project) -> bool:
    if project.approved_script_version_id is None:
        return False
    result = await db.execute(
        select(ScriptureReference.id).where(
            ScriptureReference.project_id == project.id,
            ScriptureReference.verified_at.is_(None),
        ).limit(1)
    )
    return result.first() is None


async def _has_recorded_source(db: AsyncSession, project_id) -> bool:
    result = await db.execute(
        select(MediaAsset.id).where(
            MediaAsset.project_id == project_id,
            MediaAsset.kind == "source",
            MediaAsset.status == "ready",
        ).limit(1)
    )
    return result.first() is not None


async def _has_reviewed_transcript(db: AsyncSession, project_id) -> bool:
    result = await db.execute(
        select(Transcript.id)
        .join(MediaAsset, MediaAsset.id == Transcript.media_asset_id)
        .where(MediaAsset.project_id == project_id, Transcript.reviewed_at.is_not(None))
        .limit(1)
    )
    return result.first() is not None


async def _has_ready_render(db: AsyncSession, project: Project) -> bool:
    """FRD 1.1 Ready: "Export rendered and passes platform constraint checks
    for at least one target platform (FR-009, FR-026)"."""
    result = await db.execute(
        select(MediaAsset).where(
            MediaAsset.project_id == project.id,
            MediaAsset.kind == "render",
            MediaAsset.status == "ready",
        )
    )
    renders = result.scalars().all()
    if not renders:
        return False

    profile_result = await db.execute(
        select(BrandProfile).where(BrandProfile.workspace_id == project.workspace_id)
    )
    profile = profile_result.scalar_one_or_none() or BrandProfile(platform_flags_json={})
    await ensure_seeded(db)
    platforms = (await db.execute(select(PlatformLimit.platform))).scalars().all()
    for platform in platforms:
        limits = await get_effective_limits(db, platform, profile)
        for render in renders:
            try:
                check_media_against_limits(render, limits)
            except ConflictError:
                continue
            return True
    return False


async def _has_scheduled_post(db: AsyncSession, project_id) -> bool:
    result = await db.execute(
        select(SocialPost.id).where(
            SocialPost.project_id == project_id,
            SocialPost.scheduled_at.is_not(None),
        ).limit(1)
    )
    return result.first() is not None


async def _has_published_post(db: AsyncSession, project_id) -> bool:
    result = await db.execute(
        select(SocialPost.id).where(
            SocialPost.project_id == project_id,
            SocialPost.status == "published",
            SocialPost.external_url.is_not(None),
        ).limit(1)
    )
    return result.first() is not None


async def _has_measured_post(db: AsyncSession, project_id) -> bool:
    result = await db.execute(
        select(MetricSnapshot.id)
        .join(SocialPost, SocialPost.id == MetricSnapshot.social_post_id)
        .where(SocialPost.project_id == project_id)
        .limit(1)
    )
    return result.first() is not None


CONDITIONS = {
    "scripting": lambda db, project: _has_script_version(db, project.id),
    "script_approved": _script_approved_ok,
    "recorded": lambda db, project: _has_recorded_source(db, project.id),
    "subtitled": lambda db, project: _has_reviewed_transcript(db, project.id),
    "ready": _has_ready_render,
    "scheduled": lambda db, project: _has_scheduled_post(db, project.id),
    "published": lambda db, project: _has_published_post(db, project.id),
    "measured": lambda db, project: _has_measured_post(db, project.id),
}


async def transition(db: AsyncSession, project: Project, target_state: str) -> None:
    if target_state not in PROJECT_STATES:
        raise BadRequestError(f"'{target_state}' is not a valid project state.")

    current_index = PROJECT_STATES.index(project.status)
    target_index = PROJECT_STATES.index(target_state)
    from_state = project.status

    if target_index == current_index:
        raise ConflictError(f"Project is already in '{target_state}'.")

    if target_index < current_index:
        project.status = target_state
        db.add(ProjectStateEvent(project_id=project.id, from_state=from_state, to_state=target_state))
        return

    if target_index != current_index + 1:
        raise ConflictError(
            "Projects move forward one state at a time — complete the intermediate states first."
        )

    condition = CONDITIONS[target_state]
    if not await condition(db, project):
        raise ConflictError(f"Project does not yet meet the requirements to enter '{target_state}'.")

    project.status = target_state
    db.add(ProjectStateEvent(project_id=project.id, from_state=from_state, to_state=target_state))
