import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthUser, get_current_auth_user
from app.db.models import Project, ScriptVersion, Workspace
from app.deps import DbSession, get_current_workspace
from app.errors import BadRequestError, ConflictError, NotFoundError
from app.models.schemas import (
    ExpandedReferenceOut,
    ExpandVersesResponse,
    RegenerateSectionRequest,
    ScriptManualEditRequest,
    ScriptVersionOut,
)
from app.providers.factory import get_llm_provider
from app.providers.llm import SCRIPT_SECTIONS
from app.routers.brand_profile import _get_or_create as get_or_create_brand_profile
from app.routers.projects import _get_owned_project
from app.services import ai_jobs
from app.services import scripts as scripts_service
from app.services.scripture import (
    expand_placeholders_in_text,
    expand_reference,
    sync_references_from_sections,
    validate_sections,
)

router = APIRouter(tags=["scripts"])


async def _get_owned_version(db: AsyncSession, workspace: Workspace, version_id: uuid.UUID) -> ScriptVersion:
    version = await db.get(ScriptVersion, version_id)
    if version is None:
        raise NotFoundError("Script version not found.")
    project = await db.get(Project, version.project_id)
    if project is None or project.workspace_id != workspace.id:
        raise NotFoundError("Script version not found.")
    return version


def _to_out(version: ScriptVersion, wpm: int) -> dict:
    return {
        "id": version.id,
        "project_id": version.project_id,
        "version_no": version.version_no,
        "sections": version.sections_json,
        "source": version.source,
        "approved": version.approved,
        "ai_job_id": version.ai_job_id,
        "word_count": scripts_service.word_count(version.sections_json),
        "estimated_duration_seconds": scripts_service.estimate_duration_seconds(version.sections_json, wpm),
        "created_at": version.created_at,
    }


@router.get("/api/projects/{project_id}/scripts", response_model=list[ScriptVersionOut])
async def list_script_versions(
    project_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> list[dict]:
    project = await _get_owned_project(db, workspace, project_id)
    profile = await get_or_create_brand_profile(db, workspace)
    result = await db.execute(
        select(ScriptVersion)
        .where(ScriptVersion.project_id == project.id)
        .order_by(ScriptVersion.version_no.desc())
    )
    return [_to_out(v, profile.wpm) for v in result.scalars().all()]


@router.get("/api/scripts/{version_id}", response_model=ScriptVersionOut)
async def get_script_version(
    version_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    version = await _get_owned_version(db, workspace, version_id)
    profile = await get_or_create_brand_profile(db, workspace)
    return _to_out(version, profile.wpm)


@router.post("/api/projects/{project_id}/outline", response_model=ScriptVersionOut, status_code=201)
async def generate_outline(
    project_id: uuid.UUID,
    auth_user: AuthUser = Depends(get_current_auth_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-004: generate a structured script. Uses the selected hook variant's
    text (FR-022) if one exists, otherwise the provider drafts its own hook."""
    project = await _get_owned_project(db, workspace, project_id)
    profile = await get_or_create_brand_profile(db, workspace)

    from app.db.models import HookVariant

    result = await db.execute(
        select(HookVariant).where(HookVariant.project_id == project.id, HookVariant.selected.is_(True))
    )
    selected_hook = result.scalar_one_or_none()

    provider = get_llm_provider()
    draft = await provider.generate_script(
        topic=project.topic,
        audience=project.audience,
        target_duration_seconds=project.target_duration_seconds,
        brand_profile=profile,
        hook_text=selected_hook.text if selected_hook else None,
    )

    validate_sections(draft.sections)
    await sync_references_from_sections(
        db, project_id=project.id, sections=draft.sections, default_translation=profile.translation
    )

    job = ai_jobs.record(
        db,
        workspace_id=workspace.id,
        job_type="script_outline",
        model_id=draft.model_id,
        prompt_version=draft.prompt_version,
        input_payload=f"{project.id}:{project.topic}:{profile.version_no}",
        result_json=draft.sections,
    )
    await db.flush()

    version_no = await scripts_service.next_version_no(db, project.id)
    version = ScriptVersion(
        project_id=project.id,
        version_no=version_no,
        sections_json={name: {"text": text, "source": "ai"} for name, text in draft.sections.items()},
        source="ai",
        ai_job_id=job.id,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return _to_out(version, profile.wpm)


@router.patch("/api/scripts/{version_id}", response_model=ScriptVersionOut, status_code=201)
async def edit_script_section(
    version_id: uuid.UUID,
    payload: ScriptManualEditRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-005: a manual edit is never applied in place — it always creates a
    new version, so the prior (ai/manual/mixed) version is preserved and
    restorable."""
    base = await _get_owned_version(db, workspace, version_id)
    profile = await get_or_create_brand_profile(db, workspace)

    unknown = set(payload.sections) - set(SCRIPT_SECTIONS)
    if unknown:
        raise BadRequestError(f"Unknown script section(s): {', '.join(sorted(unknown))}")

    new_sections = dict(base.sections_json)
    for section, text in payload.sections.items():
        new_sections[section] = {"text": text, "source": "manual"}

    version_no = await scripts_service.next_version_no(db, base.project_id)
    new_version = ScriptVersion(
        project_id=base.project_id,
        version_no=version_no,
        sections_json=new_sections,
        source=scripts_service.rollup_source(new_sections),
    )
    db.add(new_version)
    await db.commit()
    await db.refresh(new_version)
    return _to_out(new_version, profile.wpm)


@router.post("/api/scripts/{version_id}/regenerate-section", response_model=ScriptVersionOut, status_code=201)
async def regenerate_section(
    version_id: uuid.UUID,
    payload: RegenerateSectionRequest,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-004: regenerate one section only. Never overwrites a manually
    edited section without explicit confirmation (FR-005)."""
    base = await _get_owned_version(db, workspace, version_id)
    project = await db.get(Project, base.project_id)
    assert project is not None  # guaranteed by _get_owned_version's own lookup
    profile = await get_or_create_brand_profile(db, workspace)

    if payload.section not in SCRIPT_SECTIONS:
        raise BadRequestError(f"'{payload.section}' is not a valid script section.")

    current = base.sections_json.get(payload.section, {"text": "", "source": "ai"})
    if current["source"] == "manual" and not payload.confirm:
        raise ConflictError(
            "This section was manually edited. Resubmit with confirm=true to let AI overwrite it.",
            code="manual_edit_would_be_overwritten",
        )

    provider = get_llm_provider()
    other_sections = {k: v["text"] for k, v in base.sections_json.items() if k != payload.section}
    draft = await provider.regenerate_section(
        section=payload.section,
        topic=project.topic,
        brand_profile=profile,
        other_sections=other_sections,
    )
    validate_sections({payload.section: draft.text})
    await sync_references_from_sections(
        db,
        project_id=project.id,
        sections={payload.section: draft.text},
        default_translation=profile.translation,
    )

    job = ai_jobs.record(
        db,
        workspace_id=workspace.id,
        job_type="script_section_regenerate",
        model_id=draft.model_id,
        prompt_version=draft.prompt_version,
        input_payload=f"{project.id}:{payload.section}:{profile.version_no}",
        result_json={payload.section: draft.text},
    )
    await db.flush()

    new_sections = dict(base.sections_json)
    new_sections[payload.section] = {"text": draft.text, "source": "ai"}
    version_no = await scripts_service.next_version_no(db, base.project_id)
    new_version = ScriptVersion(
        project_id=base.project_id,
        version_no=version_no,
        sections_json=new_sections,
        source=scripts_service.rollup_source(new_sections),
        ai_job_id=job.id,
    )
    db.add(new_version)
    await db.commit()
    await db.refresh(new_version)
    return _to_out(new_version, profile.wpm)


@router.post("/api/scripts/{version_id}/restore", response_model=ScriptVersionOut, status_code=201)
async def restore_script_version(
    version_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-005 'restore action': copies an older version's content into a new,
    current version rather than rewriting history."""
    base = await _get_owned_version(db, workspace, version_id)
    profile = await get_or_create_brand_profile(db, workspace)

    version_no = await scripts_service.next_version_no(db, base.project_id)
    new_version = ScriptVersion(
        project_id=base.project_id,
        version_no=version_no,
        sections_json=dict(base.sections_json),
        source=base.source,
        ai_job_id=base.ai_job_id,
    )
    db.add(new_version)
    await db.commit()
    await db.refresh(new_version)
    return _to_out(new_version, profile.wpm)


@router.post("/api/scripts/{version_id}/approve", response_model=ScriptVersionOut)
async def approve_script_version(
    version_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    version = await _get_owned_version(db, workspace, version_id)
    profile = await get_or_create_brand_profile(db, workspace)

    result = await db.execute(select(ScriptVersion).where(ScriptVersion.project_id == version.project_id))
    for other in result.scalars().all():
        other.approved = other.id == version.id

    project = await db.get(Project, version.project_id)
    assert project is not None  # guaranteed by _get_owned_version's own lookup
    project.approved_script_version_id = version.id

    await db.commit()
    await db.refresh(version)
    return _to_out(version, profile.wpm)


@router.post("/api/scripts/{version_id}/expand-verses", response_model=ExpandVersesResponse)
async def expand_verses(
    version_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-023: expand {{Book Ch:V}} placeholders to real verse text, only from
    the allowlisted translation source (local WEB sample or Owner-pasted)."""
    from app.db.models import ScriptureReference

    version = await _get_owned_version(db, workspace, version_id)

    result = await db.execute(
        select(ScriptureReference).where(ScriptureReference.project_id == version.project_id)
    )
    references = {ref.reference: ref for ref in result.scalars().all()}

    expanded_sections = {
        name: expand_placeholders_in_text(section["text"], references)
        for name, section in version.sections_json.items()
    }
    expanded_references = [
        ExpandedReferenceOut(**expand_reference(ref)) for ref in references.values()
    ]
    return {"sections": expanded_sections, "references": expanded_references}
