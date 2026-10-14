from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PlatformLimit, Workspace
from app.deps import DbSession, get_current_workspace
from app.models.schemas import PlatformLimitOut
from app.services.platform_limits import ensure_seeded

router = APIRouter(prefix="/api/platform-limits", tags=["platform-limits"])


@router.get("", response_model=list[PlatformLimitOut])
async def list_platform_limits(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> list[PlatformLimit]:
    """FR-026: seeded config the frontend uses for live character counts —
    not hard-coded constants. `verified: false` means not yet checked
    against current platform documentation (decision D-07)."""
    await ensure_seeded(db)
    result = await db.execute(select(PlatformLimit).order_by(PlatformLimit.platform))
    return list(result.scalars().all())
