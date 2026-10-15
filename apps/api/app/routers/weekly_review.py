import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WeeklyReview, Workspace
from app.deps import DbSession, get_current_workspace
from app.errors import NotFoundError
from app.models.schemas import WeeklyReviewOut
from app.services.weekly_review import generate_weekly_report

router = APIRouter(prefix="/api/reports/weekly", tags=["weekly-review"])


def _most_recent_monday() -> date:
    today = datetime.now(UTC).date()
    return today - timedelta(days=today.weekday())


def _to_out(review: WeeklyReview) -> dict:
    return {
        "id": review.id,
        "workspace_id": review.workspace_id,
        "week_start": review.week_start.isoformat(),
        "report_json": review.report_json,
        "reviewed_at": review.reviewed_at,
    }


@router.get("", response_model=WeeklyReviewOut)
async def get_weekly_review(
    week_start: date | None = Query(default=None),
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-019: generates (or refreshes) the on-demand weekly report. A
    completed review's reviewed_at is preserved across regeneration."""
    target_week = week_start or _most_recent_monday()
    report = await generate_weekly_report(db, workspace.id, target_week)

    result = await db.execute(
        select(WeeklyReview).where(
            WeeklyReview.workspace_id == workspace.id, WeeklyReview.week_start == target_week
        )
    )
    review = result.scalar_one_or_none()
    if review is None:
        review = WeeklyReview(workspace_id=workspace.id, week_start=target_week, report_json=report)
        db.add(review)
    else:
        review.report_json = report

    await db.commit()
    await db.refresh(review)
    return _to_out(review)


@router.post("/{review_id}/complete", response_model=WeeklyReviewOut)
async def complete_weekly_review(
    review_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-019: Owner marks the review complete, feeding the 'weekly review
    completed' success metric (PRD section 5)."""
    review = await db.get(WeeklyReview, review_id)
    if review is None or review.workspace_id != workspace.id:
        raise NotFoundError("Weekly review not found.")

    review.reviewed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(review)
    return _to_out(review)
