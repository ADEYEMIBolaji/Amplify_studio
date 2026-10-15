import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FollowerSnapshot, SocialPost, Workspace
from app.deps import DbSession, get_current_workspace
from app.errors import NotFoundError
from app.models.schemas import (
    AnalyticsOverviewOut,
    FollowerSnapshotCreate,
    FollowerSnapshotOut,
    HistoricalPostCreate,
    MetricSnapshotCreate,
    MetricSnapshotOut,
    RecommendationsOut,
    SocialPostOut,
)
from app.services import metric_snapshots as snapshot_service
from app.services import posts as posts_service
from app.services.insights import build_insights
from app.services.metrics import PlatformPeriodMetrics, compute_platform_period_metrics

router = APIRouter(tags=["metrics"])

VALUE_FIELDS = (
    "reach", "impressions", "views", "likes", "comments", "shares", "saves",
    "watch_seconds_avg", "completion_rate", "profile_visits",
)


def _metrics_to_out(metrics: PlatformPeriodMetrics, range_days: int) -> dict:
    return {
        "platform": metrics.platform,
        "start": metrics.start,
        "end": metrics.end,
        "target_day": metrics.target_day,
        "window_days": metrics.window_days,
        "reach_median": metrics.reach_median,
        "reach_mean": metrics.reach_mean,
        "engagement_per_reach": metrics.engagement_per_reach,
        "share_rate": metrics.share_rate,
        "save_rate": metrics.save_rate,
        "watch_seconds_avg": metrics.watch_seconds_avg,
        "completion_rate": metrics.completion_rate,
        "net_follower_change": metrics.net_follower_change,
        "net_follower_change_low_confidence": metrics.net_follower_change_low_confidence,
        "followers_per_1000_reached": metrics.followers_per_1000_reached,
        "posting_adherence": metrics.posting_adherence,
        "data_coverage": {"eligible": metrics.data_coverage.eligible, "total": metrics.data_coverage.total},
        "low_sample": range_days == 7,  # FR-016: persistent low-sample label on the 7-day range
    }


@router.post("/api/metrics/manual", response_model=MetricSnapshotOut, status_code=201)
async def add_manual_metric(
    payload: MetricSnapshotCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-013 (manual path), FR-014 (validation, duplicates, dip flagging)."""
    post = await db.get(SocialPost, payload.social_post_id)
    if post is None or post.workspace_id != workspace.id:
        raise NotFoundError("Post not found.")

    values = {f: getattr(payload, f) for f in VALUE_FIELDS if getattr(payload, f) is not None}
    snapshot, flagged = await snapshot_service.ingest_snapshot(
        db, post=post, captured_at=payload.captured_at, values=values, on_duplicate=payload.on_duplicate
    )
    await db.commit()
    await db.refresh(snapshot)

    out = MetricSnapshotOut.model_validate(snapshot).model_dump()
    out["flagged_fields"] = flagged
    return out


@router.get("/api/posts/{post_id}/metrics", response_model=list[MetricSnapshotOut])
async def list_post_metrics(
    post_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> list[dict]:
    post = await db.get(SocialPost, post_id)
    if post is None or post.workspace_id != workspace.id:
        raise NotFoundError("Post not found.")

    from app.db.models import MetricSnapshot

    result = await db.execute(
        select(MetricSnapshot)
        .where(MetricSnapshot.social_post_id == post.id)
        .order_by(MetricSnapshot.captured_at)
    )
    return [
        {**MetricSnapshotOut.model_validate(s).model_dump(), "flagged_fields": []}
        for s in result.scalars().all()
    ]


@router.post("/api/follower-snapshots", response_model=FollowerSnapshotOut, status_code=201)
async def add_follower_snapshot(
    payload: FollowerSnapshotCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> FollowerSnapshot:
    """FR-029: weekly follower-count prompt, manual entry."""
    snapshot = FollowerSnapshot(
        workspace_id=workspace.id,
        platform=payload.platform,
        captured_at=payload.captured_at,
        follower_count=payload.follower_count,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


@router.get("/api/follower-snapshots", response_model=list[FollowerSnapshotOut])
async def list_follower_snapshots(
    platform: str | None = Query(default=None),
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> list[FollowerSnapshot]:
    query = select(FollowerSnapshot).where(FollowerSnapshot.workspace_id == workspace.id)
    if platform:
        query = query.where(FollowerSnapshot.platform == platform)
    result = await db.execute(query.order_by(FollowerSnapshot.captured_at.desc()))
    return list(result.scalars().all())


@router.post("/api/posts/historical", response_model=SocialPostOut, status_code=201)
async def import_historical_post(
    payload: HistoricalPostCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> SocialPost:
    """FR-028: posts published before Amplify Studio, no project required,
    feeding the baseline period but labelled historical in reports."""
    post = SocialPost(
        workspace_id=workspace.id,
        project_id=None,
        platform=payload.platform,
        status="published",
        published_at=payload.published_at,
        external_url=payload.external_url,
        external_post_id=posts_service.parse_external_post_id(payload.platform, payload.external_url),
        is_historical=True,
        tags_json=payload.tags_json,
    )
    db.add(post)
    await db.flush()

    for snap_payload in payload.snapshots:
        values = {f: getattr(snap_payload, f) for f in VALUE_FIELDS if getattr(snap_payload, f) is not None}
        await snapshot_service.ingest_snapshot(
            db, post=post, captured_at=snap_payload.captured_at, values=values, on_duplicate="update"
        )

    await db.commit()
    await db.refresh(post)
    return post


@router.get("/api/analytics/overview", response_model=AnalyticsOverviewOut)
async def analytics_overview(
    platform: str = Query(...),
    range_days: int = Query(default=28),
    target_day: int = Query(default=7),
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-016: current vs. preceding equal-length period, one platform at a
    time — never summed or ranked across platforms."""
    now = datetime.now(UTC)
    current_start = now - timedelta(days=range_days)
    previous_start = current_start - timedelta(days=range_days)

    current = await compute_platform_period_metrics(
        db, workspace_id=workspace.id, platform=platform, start=current_start, end=now, target_day=target_day
    )
    previous = await compute_platform_period_metrics(
        db,
        workspace_id=workspace.id,
        platform=platform,
        start=previous_start,
        end=current_start,
        target_day=target_day,
    )

    return {
        "current": _metrics_to_out(current, range_days),
        "previous": _metrics_to_out(previous, range_days),
    }


@router.get("/api/analytics/recommendations", response_model=RecommendationsOut)
async def analytics_recommendations(
    platform: str = Query(...),
    target_day: int = Query(default=7),
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-017: rule-based recommendations, each requiring >=5 posts per
    group (configurable) and >=20% relative difference (configurable),
    always citing evidence. AT-06."""
    result = await build_insights(db, workspace_id=workspace.id, platform=platform, target_day=target_day)
    return {
        "platform": result.platform,
        "comparisons": [vars(c) for c in result.comparisons],
        "insufficient_data": [vars(i) for i in result.insufficient_data],
        "high_savers": [vars(h) for h in result.high_savers],
        "underperformers": [vars(h) for h in result.underperformers],
        "consistency_warning": result.consistency_warning,
    }
