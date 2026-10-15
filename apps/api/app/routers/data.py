import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthUser, get_current_auth_user
from app.db.models import Workspace
from app.deps import DbSession, get_current_workspace
from app.routers.media import _get_owned_asset
from app.routers.projects import _get_owned_project
from app.services import audit, data_export

router = APIRouter(tags=["data"])


@router.post("/api/export")
async def export_workspace_data(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> Response:
    """FR-030: export all workspace data as JSON, with signed links for
    media instead of raw file bytes."""
    export = await data_export.export_workspace(db, workspace)
    body = data_export.export_to_json(export)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="amplify-studio-export-{workspace.id}.json"'},
    )


@router.delete("/api/projects/{project_id}", status_code=204)
async def delete_project_endpoint(
    project_id: uuid.UUID,
    auth_user: AuthUser = Depends(get_current_auth_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> None:
    """FR-030: removes the project's media objects and DB rows."""
    project = await _get_owned_project(db, workspace, project_id)
    audit.record(
        db, workspace_id=workspace.id, actor_id=auth_user.id, action="project.deleted",
        entity="project", entity_id=project.id,
    )
    await data_export.delete_project(db, project)
    await db.commit()


@router.delete("/api/media/{asset_id}", status_code=204)
async def delete_media_asset_endpoint(
    asset_id: uuid.UUID,
    auth_user: AuthUser = Depends(get_current_auth_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> None:
    asset = await _get_owned_asset(db, workspace, asset_id)
    audit.record(
        db, workspace_id=workspace.id, actor_id=auth_user.id, action="media.deleted",
        entity="media_asset", entity_id=asset.id,
    )
    await data_export.delete_media_asset(db, asset)
    await db.commit()


@router.delete("/api/workspace", status_code=204)
async def delete_workspace_endpoint(
    auth_user: AuthUser = Depends(get_current_auth_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> None:
    """FR-030: deletes the entire workspace — irreversible.

    No audit_logs row is written for this action: audit_logs.workspace_id
    cascades on delete, so a record scoped to a workspace that no longer
    exists would be unreachable (and immediately deleted) anyway.
    """
    _ = auth_user
    await data_export.delete_workspace(db, workspace)
    await db.commit()
