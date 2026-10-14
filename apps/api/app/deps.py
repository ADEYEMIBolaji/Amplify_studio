from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthUser, get_current_auth_user
from app.db.base import get_db
from app.db.models import User, Workspace

DbSession = Depends(get_db)


async def get_current_workspace(
    auth_user: AuthUser = Depends(get_current_auth_user),
    db: AsyncSession = DbSession,
) -> Workspace:
    """Returns the single workspace owned by the authenticated user, provisioning
    the user/workspace rows on first call (v1 is single-Owner — one workspace each).
    """
    user = await db.get(User, auth_user.id)
    if user is None:
        user = User(id=auth_user.id, email=auth_user.email)
        db.add(user)
        await db.flush()

    result = await db.execute(select(Workspace).where(Workspace.owner_id == auth_user.id))
    workspace = result.scalar_one_or_none()
    if workspace is None:
        workspace = Workspace(owner_id=auth_user.id, name=f"{auth_user.email}'s workspace")
        db.add(workspace)
        await db.flush()

    return workspace
