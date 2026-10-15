from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PROJECT_STATES, FollowerSnapshot, Project, SocialPost, Workspace
from app.deps import DbSession, get_current_workspace

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

NEXT_ACTIONS: dict[str, str] = {
    "idea": "Generate a script",
    "scripting": "Pick a hook and approve a script version",
    "script_approved": "Record your video",
    "recorded": "Transcribe and review the subtitles",
    "subtitled": "Export and attach it to a platform post",
    "ready": "Schedule it on the calendar",
    "scheduled": "Publish it when it goes live",
    "published": "Add metrics once they're available",
    "measured": "Review it in Growth Lab",
}


async def _posting_adherence_for_window(
    db: AsyncSession, workspace_id, start: datetime, end: datetime
) -> float | None:
    result = await db.execute(
        select(SocialPost).where(
            SocialPost.workspace_id == workspace_id,
            SocialPost.scheduled_at >= start,
            SocialPost.scheduled_at < end,
        )
    )
    scheduled = list(result.scalars().all())
    if not scheduled:
        return None
    published = sum(1 for p in scheduled if p.status == "published")
    return published / len(scheduled)


@router.get("/home")
async def get_home_dashboard(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-025: next action per project, pipeline by state, weekly posting
    adherence, reach/follower trends, active experiments."""
    result = await db.execute(
        select(Project).where(Project.workspace_id == workspace.id, Project.archived_at.is_(None))
    )
    projects = list(result.scalars().all())

    next_actions = [
        {
            "project_id": p.id,
            "title": p.title,
            "status": p.status,
            "next_action": NEXT_ACTIONS.get(p.status, "Continue this project"),
        }
        for p in projects
    ]
    pipeline_counts = {state: sum(1 for p in projects if p.status == state) for state in PROJECT_STATES}

    now = datetime.now(UTC)
    this_week_start = now - timedelta(days=7)
    last_week_start = this_week_start - timedelta(days=7)
    adherence_this_week = await _posting_adherence_for_window(db, workspace.id, this_week_start, now)
    adherence_last_week = await _posting_adherence_for_window(
        db, workspace.id, last_week_start, this_week_start
    )

    platforms = ["instagram", "tiktok", "facebook", "x"]
    last_follower_snapshot_at: dict[str, datetime | None] = {}
    follower_trend: dict[str, list[dict]] = {}
    for platform in platforms:
        follower_result = await db.execute(
            select(FollowerSnapshot)
            .where(FollowerSnapshot.workspace_id == workspace.id, FollowerSnapshot.platform == platform)
            .order_by(FollowerSnapshot.captured_at.desc())
            .limit(12)
        )
        snapshots = list(follower_result.scalars().all())
        last_follower_snapshot_at[platform] = snapshots[0].captured_at if snapshots else None
        follower_trend[platform] = [
            {"captured_at": s.captured_at, "follower_count": s.follower_count} for s in reversed(snapshots)
        ]

    reach_trend: dict[str, list[dict]] = {}
    for platform in platforms:
        from app.db.models import MetricSnapshot

        post_result = await db.execute(
            select(SocialPost.id, SocialPost.published_at).where(
                SocialPost.workspace_id == workspace.id,
                SocialPost.platform == platform,
                SocialPost.status == "published",
            )
        )
        posts = {row.id: row.published_at for row in post_result.all()}
        if not posts:
            reach_trend[platform] = []
            continue

        metric_result = await db.execute(
            select(MetricSnapshot)
            .where(
                MetricSnapshot.social_post_id.in_(posts.keys()),
                MetricSnapshot.days_since_publish.between(6, 8),
            )
            .order_by(MetricSnapshot.captured_at)
        )
        reach_trend[platform] = [
            {"date": posts[s.social_post_id], "reach": s.reach}
            for s in metric_result.scalars().all()
            if s.reach is not None
        ][-12:]

    return {
        "next_actions": next_actions,
        "pipeline_counts": pipeline_counts,
        "posting_adherence_this_week": adherence_this_week,
        "posting_adherence_last_week": adherence_last_week,
        "last_follower_snapshot_at": last_follower_snapshot_at,
        "reach_trend": reach_trend,
        "follower_trend": follower_trend,
        "active_experiments": [],  # Experiments ship Week 6 (FR-018)
    }
