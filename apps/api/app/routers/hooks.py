import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HookVariant, Project, Workspace
from app.deps import DbSession, get_current_workspace
from app.errors import NotFoundError
from app.models.schemas import HookSelectRequest, HookVariantOut
from app.providers.factory import get_llm_provider
from app.routers.brand_profile import _get_or_create as get_or_create_brand_profile
from app.routers.projects import _get_owned_project
from app.services import ai_jobs

router = APIRouter(tags=["hooks"])


@router.get("/api/projects/{project_id}/hooks", response_model=list[HookVariantOut])
async def list_hooks(
    project_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> list[HookVariant]:
    project = await _get_owned_project(db, workspace, project_id)
    result = await db.execute(select(HookVariant).where(HookVariant.project_id == project.id))
    return list(result.scalars().all())


@router.post("/api/projects/{project_id}/hooks", response_model=list[HookVariantOut], status_code=201)
async def generate_hooks(
    project_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> list[HookVariant]:
    """FR-022: generate 2-3 hook variants, each labelled with its hook type.
    Unused variants from a prior call are retained for future experiments."""
    project = await _get_owned_project(db, workspace, project_id)
    profile = await get_or_create_brand_profile(db, workspace)

    provider = get_llm_provider()
    draft = await provider.generate_hooks(topic=project.topic, brand_profile=profile)

    job = ai_jobs.record(
        db,
        workspace_id=workspace.id,
        job_type="hook_variants",
        model_id=draft.model_id,
        prompt_version=draft.prompt_version,
        input_payload=f"{project.id}:{project.topic}:{profile.version_no}",
        result_json={"hooks": [{"text": h.text, "hook_type": h.hook_type} for h in draft.hooks]},
    )
    await db.flush()

    variants = [
        HookVariant(project_id=project.id, text=hook.text, hook_type=hook.hook_type, ai_job_id=job.id)
        for hook in draft.hooks
    ]
    db.add_all(variants)
    await db.commit()
    for v in variants:
        await db.refresh(v)
    return variants


@router.patch("/api/hooks/{hook_id}", response_model=HookVariantOut)
async def select_hook(
    hook_id: uuid.UUID,
    payload: HookSelectRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> HookVariant:
    """FR-022: Owner selects one hook variant as used; selection drives the
    project's hook_type content tag (FR-021)."""
    hook = await db.get(HookVariant, hook_id)
    if hook is None:
        raise NotFoundError("Hook variant not found.")
    project = await db.get(Project, hook.project_id)
    if project is None or project.workspace_id != workspace.id:
        raise NotFoundError("Hook variant not found.")

    if payload.selected:
        result = await db.execute(select(HookVariant).where(HookVariant.project_id == project.id))
        for other in result.scalars().all():
            other.selected = other.id == hook.id
        project.hook_type = hook.hook_type
    else:
        hook.selected = False

    await db.commit()
    await db.refresh(hook)
    return hook
