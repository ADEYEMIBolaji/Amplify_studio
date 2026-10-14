from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BrandProfile, Workspace
from app.deps import DbSession, get_current_workspace
from app.models.schemas import BrandProfileOut, BrandProfileUpdate

router = APIRouter(prefix="/api/brand-profile", tags=["brand-profile"])


async def _get_or_create(db: AsyncSession, workspace: Workspace) -> BrandProfile:
    result = await db.execute(select(BrandProfile).where(BrandProfile.workspace_id == workspace.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = BrandProfile(workspace_id=workspace.id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


@router.get("", response_model=BrandProfileOut)
async def get_brand_profile(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> BrandProfile:
    return await _get_or_create(db, workspace)


@router.patch("", response_model=BrandProfileOut)
async def update_brand_profile(
    payload: BrandProfileUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> BrandProfile:
    profile = await _get_or_create(db, workspace)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    profile.version_no += 1
    await db.commit()
    await db.refresh(profile)
    return profile
