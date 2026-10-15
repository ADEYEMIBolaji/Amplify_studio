"""Rule-based recommendations — FR-017, non-negotiable rule 5 (Honest insights).

Every comparison requires >= insight_min_group_size posts per group
(configurable) and >= insight_min_relative_difference (configurable); below
either threshold, nothing is claimed — either an explicit "insufficient
data" entry naming the count still needed, or silence (when there's
genuinely nothing to compare). Every recommendation cites the specific
post IDs behind it. Wording is deliberately factual/observational —
"had a higher X in this period" — never causal ("because") or
growth-promising ("will", "guarantee").
"""

import statistics
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import MetricSnapshot, Project, SocialPost
from app.services.metrics import select_window_snapshot

GROUP_DIMENSIONS = ("hook_type", "topic_tag_id", "format", "length_bucket", "posting_slot")
HIGH_PERFORMER_MULTIPLIER = 1.5
UNDERPERFORMER_MULTIPLIER = 0.5
CONSISTENCY_TARGET = 0.80  # PRD section 5 success metric: posting adherence >= 80%

DISCLAIMER = "This reflects an observed pattern in this period, not a guarantee of future results."


@dataclass
class PostMetricPoint:
    post_id: uuid.UUID
    caption: str | None
    tags: dict
    share_rate: float | None
    save_rate: float | None
    completion_rate: float | None


@dataclass
class GroupComparison:
    dimension: str
    metric: str
    group_a: str
    group_b: str
    value_a: float
    value_b: float
    better_group: str
    relative_difference: float
    post_ids_a: list[str]
    post_ids_b: list[str]
    summary: str


@dataclass
class InsufficientData:
    dimension: str
    metric: str
    group_counts: dict[str, int]
    min_required: int
    posts_still_needed: int


@dataclass
class HighlightPost:
    post_id: str
    caption: str | None
    metric: str
    value: float
    baseline_median: float
    summary: str


@dataclass
class InsightsResult:
    platform: str
    comparisons: list[GroupComparison] = field(default_factory=list)
    insufficient_data: list[InsufficientData] = field(default_factory=list)
    high_savers: list[HighlightPost] = field(default_factory=list)
    underperformers: list[HighlightPost] = field(default_factory=list)
    consistency_warning: str | None = None


def get_post_tags(post: SocialPost, project: Project | None) -> dict:
    if project is not None:
        return {
            "topic_tag_id": str(project.topic_tag_id) if project.topic_tag_id else None,
            "hook_type": project.hook_type,
            "cta_type": project.cta_type,
            "format": project.format,
            "length_bucket": project.length_bucket,
            "posting_slot": post.posting_slot,
        }
    tags = post.tags_json or {}
    return {
        "topic_tag_id": tags.get("topic_tag_id"),
        "hook_type": tags.get("hook_type"),
        "cta_type": tags.get("cta_type"),
        "format": tags.get("format"),
        "length_bucket": tags.get("length_bucket"),
        "posting_slot": post.posting_slot,
    }


async def _collect_post_points(
    db: AsyncSession, workspace_id, platform: str, target_day: int, window_days: int
) -> list[PostMetricPoint]:
    result = await db.execute(
        select(SocialPost).where(
            SocialPost.workspace_id == workspace_id,
            SocialPost.platform == platform,
            SocialPost.status == "published",
        )
    )
    posts = list(result.scalars().all())
    if not posts:
        return []

    post_ids = [p.id for p in posts]
    snap_result = await db.execute(select(MetricSnapshot).where(MetricSnapshot.social_post_id.in_(post_ids)))
    snaps_by_post: dict = defaultdict(list)
    for snap in snap_result.scalars().all():
        snaps_by_post[snap.social_post_id].append(snap)

    project_ids = [p.project_id for p in posts if p.project_id]
    projects_by_id: dict = {}
    if project_ids:
        proj_result = await db.execute(select(Project).where(Project.id.in_(project_ids)))
        projects_by_id = {p.id: p for p in proj_result.scalars().all()}

    points = []
    for post in posts:
        window_snap = select_window_snapshot(snaps_by_post.get(post.id, []), target_day, window_days)
        if window_snap is None:
            continue
        tags = get_post_tags(post, projects_by_id.get(post.project_id))
        reach = window_snap.reach
        share_rate = window_snap.shares / reach if window_snap.shares is not None and reach else None
        save_rate = window_snap.saves / reach if window_snap.saves is not None and reach else None
        points.append(
            PostMetricPoint(
                post_id=post.id,
                caption=post.caption,
                tags=tags,
                share_rate=share_rate,
                save_rate=save_rate,
                completion_rate=(
                    float(window_snap.completion_rate) if window_snap.completion_rate is not None else None
                ),
            )
        )
    return points


async def _consistency_warning(db: AsyncSession, workspace_id, platform: str) -> str | None:
    """FR-017 'consistency gaps': posting adherence below the PRD's own
    80% success-metric target over the last 4 weeks, with the actual
    counts — not a causal claim, just the numbers."""
    window_start = datetime.now(UTC) - timedelta(weeks=4)
    result = await db.execute(
        select(SocialPost).where(
            SocialPost.workspace_id == workspace_id,
            SocialPost.platform == platform,
            SocialPost.scheduled_at >= window_start,
        )
    )
    scheduled = list(result.scalars().all())
    if not scheduled:
        return None

    published_count = sum(1 for p in scheduled if p.status == "published")
    adherence = published_count / len(scheduled)
    if adherence >= CONSISTENCY_TARGET:
        return None

    return (
        f"Posting adherence over the last 4 weeks was {adherence:.0%} "
        f"({published_count} of {len(scheduled)} scheduled posts published), "
        f"below the {CONSISTENCY_TARGET:.0%} target. {DISCLAIMER}"
    )


def _relative_difference(higher: float, lower: float) -> float:
    if lower > 0:
        return (higher - lower) / lower
    return 1.0 if higher > 0 else 0.0


def _compare_dimension(
    points: list[PostMetricPoint], dimension: str, metric: str, min_group_size: int, min_relative_diff: float
) -> GroupComparison | InsufficientData | None:
    groups: dict[str, list[PostMetricPoint]] = defaultdict(list)
    for point in points:
        value = point.tags.get(dimension)
        if value is not None and getattr(point, metric) is not None:
            groups[value].append(point)

    if not groups:
        return None  # no posts carry this tag at all — nothing to report

    group_counts = {k: len(v) for k, v in groups.items()}
    qualifying = {k: v for k, v in groups.items() if len(v) >= min_group_size}

    if len(qualifying) < 2:
        smallest_qualifying_gap = min_group_size - max(group_counts.values(), default=0)
        return InsufficientData(
            dimension=dimension,
            metric=metric,
            group_counts=group_counts,
            min_required=min_group_size,
            posts_still_needed=max(smallest_qualifying_gap, 1),
        )

    medians = {k: statistics.median(getattr(p, metric) for p in v) for k, v in qualifying.items()}
    best = max(medians, key=lambda k: medians[k])
    worst = min(medians, key=lambda k: medians[k])
    if best == worst:
        return None

    rel_diff = _relative_difference(medians[best], medians[worst])
    if rel_diff < min_relative_diff:
        return None

    return GroupComparison(
        dimension=dimension,
        metric=metric,
        group_a=best,
        group_b=worst,
        value_a=medians[best],
        value_b=medians[worst],
        better_group=best,
        relative_difference=rel_diff,
        post_ids_a=[str(p.post_id) for p in qualifying[best]],
        post_ids_b=[str(p.post_id) for p in qualifying[worst]],
        summary=(
            f"Posts tagged {dimension}='{best}' had a {metric.replace('_', ' ')} of "
            f"{medians[best]:.1%} (median, {len(qualifying[best])} posts), versus "
            f"{medians[worst]:.1%} for {dimension}='{worst}' ({len(qualifying[worst])} posts) "
            f"— a {rel_diff:.0%} relative difference. {DISCLAIMER}"
        ),
    )


async def build_insights(
    db: AsyncSession, *, workspace_id, platform: str, target_day: int = 7, window_days: int = 1
) -> InsightsResult:
    settings = get_settings()
    points = await _collect_post_points(db, workspace_id, platform, target_day, window_days)

    result = InsightsResult(platform=platform)

    for dimension in GROUP_DIMENSIONS:
        comparison = _compare_dimension(
            points,
            dimension,
            "share_rate",
            settings.insight_min_group_size,
            settings.insight_min_relative_difference,
        )
        if isinstance(comparison, GroupComparison):
            result.comparisons.append(comparison)
        elif isinstance(comparison, InsufficientData):
            result.insufficient_data.append(comparison)

    save_points: list[tuple[PostMetricPoint, float]] = [
        (p, p.save_rate) for p in points if p.save_rate is not None
    ]
    if len(save_points) >= settings.insight_min_group_size:
        median_save = statistics.median(value for _, value in save_points)
        if median_save > 0:
            for p, save_rate in save_points:
                if save_rate >= median_save * HIGH_PERFORMER_MULTIPLIER:
                    result.high_savers.append(
                        HighlightPost(
                            post_id=str(p.post_id),
                            caption=p.caption,
                            metric="save_rate",
                            value=save_rate,
                            baseline_median=median_save,
                            summary=(
                                f"This post's save rate ({save_rate:.1%}) was notably higher than the "
                                f"platform median ({median_save:.1%}) over this period. {DISCLAIMER}"
                            ),
                        )
                    )

    completion_points: list[tuple[PostMetricPoint, float]] = [
        (p, p.completion_rate) for p in points if p.completion_rate is not None
    ]
    if len(completion_points) >= settings.insight_min_group_size:
        median_completion = statistics.median(value for _, value in completion_points)
        if median_completion > 0:
            for p, completion_rate in completion_points:
                if completion_rate <= median_completion * UNDERPERFORMER_MULTIPLIER:
                    result.underperformers.append(
                        HighlightPost(
                            post_id=str(p.post_id),
                            caption=p.caption,
                            metric="completion_rate",
                            value=completion_rate,
                            baseline_median=median_completion,
                            summary=(
                                f"This post's completion rate ({completion_rate:.1f}%) was notably "
                                f"below the platform median ({median_completion:.1f}%) over this "
                                f"period — worth reviewing. {DISCLAIMER}"
                            ),
                        )
                    )

    result.consistency_warning = await _consistency_warning(db, workspace_id, platform)

    return result
