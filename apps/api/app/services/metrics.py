"""Metrics calculations — FR-015, non-negotiable rule 4.

Hard rules enforced throughout this module:
  - metric_snapshots are cumulative lifetime totals as of captured_at, never
    daily increments — we always pick ONE snapshot per post per window, we
    never sum snapshots for the same post.
  - comparisons use values at a standard post age (default day 7, window
    day 6-8), not "latest available" — posts without a snapshot in the
    window are excluded and counted in data coverage, not treated as zero.
  - reach per post is the MEDIAN across eligible posts; "total reach in
    window" (used only for followers-per-1000) is a SUM — these are
    deliberately different aggregations for different FRD-specified
    metrics, not an inconsistency.
  - never sum reach across platforms; every query here is scoped to one
    platform at a time.
  - missing values are None, surfaced as "Unavailable", never coerced to 0.

Two aggregation choices the FRD's FR-015 table doesn't fully specify are
documented inline where they're made (engagement/share/save rate
cross-post aggregation; the day-28 window width).
"""

import statistics
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FollowerSnapshot, MetricSnapshot, SocialPost

DAY_WINDOWS = {3: 1, 7: 1, 28: 3}  # target_day -> +/- window_days (FRD only pins down day 7's 6-8 window)
FOLLOWER_BOUNDARY_TOLERANCE_DAYS = 2
MIN_POSTS_FOR_FOLLOWERS_PER_1000 = 5


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def select_window_snapshot(
    snapshots: list[MetricSnapshot], target_day: int, window_days: int
) -> MetricSnapshot | None:
    """Among a post's snapshots, picks the one closest to target_day within
    [target_day - window_days, target_day + window_days]. Never averages or
    sums multiple snapshots for the same post."""
    candidates = [
        s
        for s in snapshots
        if s.days_since_publish is not None and abs(s.days_since_publish - target_day) <= window_days
    ]
    if not candidates:
        return None

    def _distance(snap: MetricSnapshot) -> tuple[int, datetime]:
        days = snap.days_since_publish
        assert days is not None  # guaranteed by the filter above
        return abs(days - target_day), snap.captured_at

    return min(candidates, key=_distance)


@dataclass
class DataCoverage:
    eligible: int
    total: int


@dataclass
class PlatformPeriodMetrics:
    platform: str
    start: datetime
    end: datetime
    target_day: int
    window_days: int
    reach_median: float | None
    reach_mean: float | None  # secondary only, per FR-015
    engagement_per_reach: float | None
    share_rate: float | None
    save_rate: float | None
    watch_seconds_avg: float | None
    completion_rate: float | None
    net_follower_change: float | None
    net_follower_change_low_confidence: bool
    followers_per_1000_reached: float | None
    posting_adherence: float | None
    data_coverage: DataCoverage


async def _eligible_posts_with_snapshots(
    db: AsyncSession, workspace_id, platform: str, start: datetime, end: datetime
) -> list[tuple[SocialPost, list[MetricSnapshot]]]:
    result = await db.execute(
        select(SocialPost).where(
            SocialPost.workspace_id == workspace_id,
            SocialPost.platform == platform,
            SocialPost.status == "published",
            SocialPost.published_at >= start,
            SocialPost.published_at < end,
        )
    )
    posts = list(result.scalars().all())
    if not posts:
        return []

    post_ids = [p.id for p in posts]
    snap_result = await db.execute(select(MetricSnapshot).where(MetricSnapshot.social_post_id.in_(post_ids)))
    snapshots_by_post: dict = {}
    for snap in snap_result.scalars().all():
        snapshots_by_post.setdefault(snap.social_post_id, []).append(snap)

    return [(p, snapshots_by_post.get(p.id, [])) for p in posts]


async def _follower_change(
    db: AsyncSession, workspace_id, platform: str, start: datetime, end: datetime
) -> tuple[float | None, bool]:
    result = await db.execute(
        select(FollowerSnapshot)
        .where(FollowerSnapshot.workspace_id == workspace_id, FollowerSnapshot.platform == platform)
        .order_by(FollowerSnapshot.captured_at)
    )
    snapshots = list(result.scalars().all())
    if not snapshots:
        return None, False

    def nearest(target: datetime) -> FollowerSnapshot:
        return min(snapshots, key=lambda s: abs((s.captured_at - target).total_seconds()))

    start_snap = nearest(start)
    end_snap = nearest(end)
    low_confidence = (
        abs((start_snap.captured_at - start).days) > FOLLOWER_BOUNDARY_TOLERANCE_DAYS
        or abs((end_snap.captured_at - end).days) > FOLLOWER_BOUNDARY_TOLERANCE_DAYS
    )
    return float(end_snap.follower_count - start_snap.follower_count), low_confidence


async def _posting_adherence(
    db: AsyncSession, workspace_id, platform: str, start: datetime, end: datetime
) -> float | None:
    scheduled_result = await db.execute(
        select(SocialPost).where(
            SocialPost.workspace_id == workspace_id,
            SocialPost.platform == platform,
            SocialPost.scheduled_at >= start,
            SocialPost.scheduled_at < end,
        )
    )
    scheduled = list(scheduled_result.scalars().all())
    if not scheduled:
        return None
    published_count = sum(1 for p in scheduled if p.status == "published")
    return published_count / len(scheduled)


async def compute_platform_period_metrics(
    db: AsyncSession,
    *,
    workspace_id,
    platform: str,
    start: datetime,
    end: datetime,
    target_day: int = 7,
) -> PlatformPeriodMetrics:
    window_days = DAY_WINDOWS.get(target_day, 1)
    pairs = await _eligible_posts_with_snapshots(db, workspace_id, platform, start, end)

    reach_values: list[float] = []
    engagement_rates: list[float] = []
    share_rates: list[float] = []
    save_rates: list[float] = []
    watch_values: list[float] = []
    completion_values: list[float] = []
    eligible_count = 0

    for _post, snapshots in pairs:
        snap = select_window_snapshot(snapshots, target_day, window_days)
        if snap is None:
            continue
        eligible_count += 1

        if snap.reach is not None:
            reach_values.append(float(snap.reach))

            # Engagement/share/save rate are each computed per eligible post
            # then aggregated with the median, matching the FRD's general
            # preference for median over mean elsewhere in FR-015 — the FRD
            # doesn't pin down the cross-post aggregation for these three,
            # so this is a documented choice, not a spec requirement.
            engagement_inputs = [
                v for v in (snap.likes, snap.comments, snap.shares, snap.saves) if v is not None
            ]
            if engagement_inputs and snap.reach > 0:
                engagement_rates.append(sum(engagement_inputs) / snap.reach)
            if snap.shares is not None and snap.reach > 0:
                share_rates.append(snap.shares / snap.reach)
            if snap.saves is not None and snap.reach > 0:
                save_rates.append(snap.saves / snap.reach)

        if snap.watch_seconds_avg is not None:
            watch_values.append(float(snap.watch_seconds_avg))
        if snap.completion_rate is not None:
            completion_values.append(float(snap.completion_rate))

    net_follower_change, low_confidence = await _follower_change(db, workspace_id, platform, start, end)

    total_reach_in_window = sum(reach_values) if reach_values else 0.0
    followers_per_1000 = None
    if (
        net_follower_change is not None
        and not low_confidence
        and eligible_count >= MIN_POSTS_FOR_FOLLOWERS_PER_1000
        and total_reach_in_window > 0
    ):
        followers_per_1000 = net_follower_change / total_reach_in_window * 1000

    posting_adherence = await _posting_adherence(db, workspace_id, platform, start, end)

    return PlatformPeriodMetrics(
        platform=platform,
        start=start,
        end=end,
        target_day=target_day,
        window_days=window_days,
        reach_median=median(reach_values),
        reach_mean=(sum(reach_values) / len(reach_values)) if reach_values else None,
        engagement_per_reach=median(engagement_rates),
        share_rate=median(share_rates),
        save_rate=median(save_rates),
        watch_seconds_avg=median(watch_values),
        completion_rate=median(completion_values),
        net_follower_change=net_follower_change,
        net_follower_change_low_confidence=low_confidence,
        followers_per_1000_reached=followers_per_1000,
        posting_adherence=posting_adherence,
        data_coverage=DataCoverage(eligible=eligible_count, total=len(pairs)),
    )
