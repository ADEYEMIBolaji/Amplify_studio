import uuid
from datetime import UTC

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthUser, get_current_auth_user
from app.db.models import Project, Workspace
from app.deps import DbSession, get_current_workspace
from app.errors import NotFoundError
from app.models.schemas import ProjectCreate, ProjectOut, ProjectTransition, ProjectUpdate
from app.services import audit, state_machine

router = APIRouter(prefix="/api/projects", tags=["projects"])


async def _get_owned_project(db: AsyncSession, workspace: Workspace, project_id: uuid.UUID) -> Project:
    # FR-001 / NFR Security (AT-07): every lookup is scoped to the caller's own
    # workspace_id explicitly — the service role bypasses RLS, so this check
    # is what actually prevents cross-workspace access, not a formality.
    project = await db.get(Project, project_id)
    if project is None or project.workspace_id != workspace.id:
        raise NotFoundError("Project not found.")
    return project


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> list[Project]:
    result = await db.execute(
        select(Project).where(Project.workspace_id == workspace.id).order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    payload: ProjectCreate,
    auth_user: AuthUser = Depends(get_current_auth_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> Project:
    project = Project(workspace_id=workspace.id, **payload.model_dump())
    db.add(project)
    await db.flush()
    audit.record(
        db,
        workspace_id=workspace.id,
        actor_id=auth_user.id,
        action="project.created",
        entity="project",
        entity_id=project.id,
    )
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> Project:
    return await _get_owned_project(db, workspace, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    auth_user: AuthUser = Depends(get_current_auth_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> Project:
    project = await _get_owned_project(db, workspace, project_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    audit.record(
        db,
        workspace_id=workspace.id,
        actor_id=auth_user.id,
        action="project.updated",
        entity="project",
        entity_id=project.id,
    )
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/{project_id}/archive", response_model=ProjectOut)
async def archive_project(
    project_id: uuid.UUID,
    auth_user: AuthUser = Depends(get_current_auth_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> Project:
    from datetime import datetime

    project = await _get_owned_project(db, workspace, project_id)
    project.archived_at = datetime.now(UTC)
    audit.record(
        db,
        workspace_id=workspace.id,
        actor_id=auth_user.id,
        action="project.archived",
        entity="project",
        entity_id=project.id,
    )
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/{project_id}/transition", response_model=ProjectOut)
async def transition_project(
    project_id: uuid.UUID,
    payload: ProjectTransition,
    auth_user: AuthUser = Depends(get_current_auth_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> Project:
    project = await _get_owned_project(db, workspace, project_id)
    await state_machine.transition(db, project, payload.target_state)
    audit.record(
        db,
        workspace_id=workspace.id,
        actor_id=auth_user.id,
        action="project.transitioned",
        entity="project",
        entity_id=project.id,
    )
    await db.commit()
    await db.refresh(project)
    return project
