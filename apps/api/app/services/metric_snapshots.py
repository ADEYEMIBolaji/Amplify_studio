"""Metric snapshot ingestion — FR-013, FR-014.

Snapshots are cumulative lifetime totals as of captured_at. This module is
the one place that derives days_since_publish, rejects malformed input, and
flags (never silently "corrects") a snapshot whose cumulative counts are
lower than an earlier one for the same post.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MetricSnapshot, SocialPost
from app.errors import BadRequestError, ConflictError

COUNT_FIELDS = ("reach", "impressions", "views", "likes", "comments", "shares", "saves", "profile_visits")
CUMULATIVE_FIELDS = ("reach", "impressions", "views", "likes", "comments", "shares", "saves")


def validate_snapshot_values(values: dict) -> None:
    for field in COUNT_FIELDS:
        value = values.get(field)
        if value is not None and value < 0:
            raise BadRequestError(f"'{field}' cannot be negative.", code="negative_count")

    completion_rate = values.get("completion_rate")
    if completion_rate is not None and not (0 <= completion_rate <= 100):
        raise BadRequestError(
            "'completion_rate' must be between 0 and 100.", code="completion_rate_out_of_range"
        )

    watch_seconds_avg = values.get("watch_seconds_avg")
    if watch_seconds_avg is not None and watch_seconds_avg < 0:
        raise BadRequestError("'watch_seconds_avg' cannot be negative.", code="negative_count")


def compute_days_since_publish(captured_at: datetime, published_at: datetime | None) -> int | None:
    if published_at is None:
        return None
    return (captured_at.date() - published_at.date()).days


def flagged_fields_below_earlier(new_values: dict, earlier: MetricSnapshot) -> list[str]:
    """FR-014: 'a snapshot whose cumulative values fall below an earlier
    snapshot for the same post is flagged for review' — flagged, not
    rejected; the Owner decides what to do with it."""
    flagged = []
    for field in CUMULATIVE_FIELDS:
        new_value = new_values.get(field)
        old_value = getattr(earlier, field)
        if new_value is not None and old_value is not None and new_value < old_value:
            flagged.append(field)
    return flagged


async def find_duplicate(
    db: AsyncSession, social_post_id, captured_at: datetime
) -> MetricSnapshot | None:
    """FR-014 duplicate key: platform + external post ID + captured_at
    DATE. social_post_id already scopes platform/external ID uniquely, so
    comparing by date for the same post is equivalent."""
    result = await db.execute(
        select(MetricSnapshot).where(MetricSnapshot.social_post_id == social_post_id)
    )
    for snap in result.scalars().all():
        if snap.captured_at.date() == captured_at.date():
            return snap
    return None


async def find_earlier_snapshot(
    db: AsyncSession, social_post_id, before: datetime
) -> MetricSnapshot | None:
    result = await db.execute(
        select(MetricSnapshot)
        .where(MetricSnapshot.social_post_id == social_post_id, MetricSnapshot.captured_at < before)
        .order_by(MetricSnapshot.captured_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def ingest_snapshot(
    db: AsyncSession,
    *,
    post: SocialPost,
    captured_at: datetime,
    values: dict,
    on_duplicate: str | None = None,
) -> tuple[MetricSnapshot, list[str]]:
    """Returns (snapshot, flagged_fields). Raises ConflictError on an
    unresolved duplicate (FR-014: Owner must choose update or skip)."""
    validate_snapshot_values(values)

    if post.published_at and captured_at.date() < post.published_at.date():
        raise BadRequestError(
            "captured_at is before this post's published_at — a snapshot can't predate publication.",
            code="captured_at_before_publish",
        )

    duplicate = await find_duplicate(db, post.id, captured_at)
    if duplicate is not None:
        if on_duplicate == "skip":
            return duplicate, []
        if on_duplicate != "update":
            raise ConflictError(
                "A snapshot already exists for this post on this date. "
                "Resubmit with on_duplicate='update' or 'skip'.",
                code="duplicate_snapshot",
            )
        for field in COUNT_FIELDS + ("watch_seconds_avg", "completion_rate"):
            if field in values:
                setattr(duplicate, field, values[field])
        earlier = await find_earlier_snapshot(db, post.id, duplicate.captured_at)
        flagged = flagged_fields_below_earlier(values, earlier) if earlier else []
        await db.flush()
        return duplicate, flagged

    earlier = await find_earlier_snapshot(db, post.id, captured_at)
    flagged = flagged_fields_below_earlier(values, earlier) if earlier else []

    snapshot = MetricSnapshot(
        social_post_id=post.id,
        platform=post.platform,
        captured_at=captured_at,
        days_since_publish=compute_days_since_publish(captured_at, post.published_at),
        **values,
    )
    db.add(snapshot)
    await db.flush()
    return snapshot, flagged
