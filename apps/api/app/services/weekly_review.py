"""Weekly review — FR-019. On-demand report: best/worst posts, platform
changes, data gaps, 1-3 suggested experiments, no causal-claim language
(reuses the same honest-wording discipline as app/services/insights.py).
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FollowerSnapshot, MetricSnapshot, SocialPost
from app.services.insights import DISCLAIMER, build_insights
from app.services.metrics import compute_platform_period_metrics

PLATFORMS = ("instagram", "tiktok", "facebook", "x")
DIMENSION_TO_VARIABLE = {
    "hook_type": "hook",
    "topic_tag_id": "topic",
    "length_bucket": "length",
    "cta_type": "cta",
    "posting_slot": "posting_slot",
}
FOLLOWER_SNAPSHOT_STALENESS_DAYS = 9
MAX_SUGGESTED_EXPERIMENTS = 3


async def _week_posts_with_latest_reach(
    db: AsyncSession, workspace_id, start: datetime, end: datetime
) -> list[dict]:
    result = await db.execute(
        select(SocialPost).where(
            SocialPost.workspace_id == workspace_id,
            SocialPost.status == "published",
            SocialPost.published_at >= start,
            SocialPost.published_at < end,
        )
    )
    posts = list(result.scalars().all())
    if not posts:
        return []

    post_ids = [p.id for p in posts]
    snap_result = await db.execute(
        select(MetricSnapshot).where(MetricSnapshot.social_post_id.in_(post_ids)).order_by(MetricSnapshot.captured_at)
    )
    latest_by_post: dict = {}
    for row in snap_result.scalars().all():
        latest_by_post[row.social_post_id] = row  # last write wins — already ordered ascending

    entries = []
    for post in posts:
        latest = latest_by_post.get(post.id)
        if latest is None or latest.reach is None:
            continue
        entries.append(
            {
                "post_id": str(post.id),
                "platform": post.platform,
                "caption": post.caption,
                "reach": latest.reach,
            }
        )
    return entries


async def _data_gaps(db: AsyncSession, workspace_id, week_end: datetime) -> list[str]:
    gaps = []
    for platform in PLATFORMS:
        result = await db.execute(
            select(FollowerSnapshot)
            .where(FollowerSnapshot.workspace_id == workspace_id, FollowerSnapshot.platform == platform)
            .order_by(FollowerSnapshot.captured_at.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        if latest is None or (week_end - latest.captured_at).days > FOLLOWER_SNAPSHOT_STALENESS_DAYS:
            gaps.append(
                f"No recent follower snapshot for {platform} — enter one in Growth Lab (FR-029)."
            )
    return gaps


async def _suggested_experiments(db: AsyncSession, workspace_id) -> list[dict]:
    suggestions: list[dict] = []
    for platform in PLATFORMS:
        if len(suggestions) >= MAX_SUGGESTED_EXPERIMENTS:
            break
        insights = await build_insights(db, workspace_id=workspace_id, platform=platform)
        for comparison in insights.comparisons:
            if len(suggestions) >= MAX_SUGGESTED_EXPERIMENTS:
                break
            variable = DIMENSION_TO_VARIABLE.get(comparison.dimension, comparison.dimension)
            suggestions.append(
                {
                    "platform": platform,
                    "variable": variable,
                    "hypothesis": (
                        f"Posting more {platform} content tagged {comparison.dimension}="
                        f"'{comparison.better_group}' may be worth testing deliberately — "
                        f"it outperformed '{comparison.group_b}' on {comparison.metric} in the data so far. "
                        f"{DISCLAIMER}"
                    ),
                    "evidence": comparison.summary,
                }
            )
    return suggestions


async def generate_weekly_report(db: AsyncSession, workspace_id, week_start: date) -> dict:
    start_dt = datetime.combine(week_start, datetime.min.time(), tzinfo=UTC)
    end_dt = start_dt + timedelta(days=7)
    previous_start_dt = start_dt - timedelta(days=7)

    entries = await _week_posts_with_latest_reach(db, workspace_id, start_dt, end_dt)
    sorted_entries = sorted(entries, key=lambda e: e["reach"], reverse=True)
    best_posts = sorted_entries[:3]
    worst_posts = sorted_entries[-3:] if len(sorted_entries) > 3 else []

    platform_changes = {}
    for platform in PLATFORMS:
        current = await compute_platform_period_metrics(
            db, workspace_id=workspace_id, platform=platform, start=start_dt, end=end_dt
        )
        previous = await compute_platform_period_metrics(
            db, workspace_id=workspace_id, platform=platform, start=previous_start_dt, end=start_dt
        )
        if current.data_coverage.total == 0 and previous.data_coverage.total == 0:
            continue
        platform_changes[platform] = {
            "reach_median_current": current.reach_median,
            "reach_median_previous": previous.reach_median,
            "posting_adherence_current": current.posting_adherence,
            "data_coverage": {
                "eligible": current.data_coverage.eligible,
                "total": current.data_coverage.total,
            },
        }

    return {
        "week_start": week_start.isoformat(),
        "best_posts": best_posts,
        "worst_posts": worst_posts,
        "platform_changes": platform_changes,
        "data_gaps": await _data_gaps(db, workspace_id, end_dt),
        "suggested_experiments": await _suggested_experiments(db, workspace_id),
        "disclaimer": DISCLAIMER,
    }
