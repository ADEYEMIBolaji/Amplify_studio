import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthUser, get_current_auth_user
from app.db.models import Project, ScriptureReference, Workspace
from app.deps import DbSession, get_current_workspace
from app.errors import NotFoundError
from app.models.schemas import ScriptureReferenceCreate, ScriptureReferenceOut, ScriptureReferenceUpdate
from app.routers.projects import _get_owned_project
from app.services.scripture import parse_reference

router = APIRouter(tags=["references"])


async def _get_owned_reference(
    db: AsyncSession, workspace: Workspace, reference_id: uuid.UUID
) -> ScriptureReference:
    ref = await db.get(ScriptureReference, reference_id)
    if ref is None:
        raise NotFoundError("Scripture reference not found.")
    project = await db.get(Project, ref.project_id)
    if project is None or project.workspace_id != workspace.id:
        raise NotFoundError("Scripture reference not found.")
    return ref


@router.get("/api/projects/{project_id}/references", response_model=list[ScriptureReferenceOut])
async def list_references(
    project_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> list[ScriptureReference]:
    project = await _get_owned_project(db, workspace, project_id)
    result = await db.execute(select(ScriptureReference).where(ScriptureReference.project_id == project.id))
    return list(result.scalars().all())


@router.post("/api/projects/{project_id}/references", response_model=ScriptureReferenceOut, status_code=201)
async def create_reference(
    project_id: uuid.UUID,
    payload: ScriptureReferenceCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> ScriptureReference:
    """FR-003: the Owner may add a reference directly (source=user), e.g.
    when scripting without AI or adding a passage the AI didn't cite."""
    project = await _get_owned_project(db, workspace, project_id)
    book, chapter, verse_start, verse_end = parse_reference(payload.reference)

    ref = ScriptureReference(
        project_id=project.id,
        book=book,
        chapter=chapter,
        verse_start=verse_start,
        verse_end=verse_end,
        reference=payload.reference,
        translation=payload.translation,
        source="user",
    )
    db.add(ref)
    await db.commit()
    await db.refresh(ref)
    return ref


@router.patch("/api/references/{reference_id}", response_model=ScriptureReferenceOut)
async def update_reference(
    reference_id: uuid.UUID,
    payload: ScriptureReferenceUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> ScriptureReference:
    ref = await _get_owned_reference(db, workspace, reference_id)

    if payload.reference is not None:
        book, chapter, verse_start, verse_end = parse_reference(payload.reference)
        ref.book, ref.chapter, ref.verse_start, ref.verse_end = book, chapter, verse_start, verse_end
        ref.reference = payload.reference
        # Editing the reference invalidates any prior verification — the
        # Owner is now pointing at different scripture (FR-003).
        ref.verified_by = None
        ref.verified_at = None

    if payload.translation is not None:
        ref.translation = payload.translation
    if payload.pasted_text is not None:
        ref.pasted_text = payload.pasted_text

    await db.commit()
    await db.refresh(ref)
    return ref


@router.post("/api/references/{reference_id}/verify", response_model=ScriptureReferenceOut)
async def verify_reference(
    reference_id: uuid.UUID,
    auth_user: AuthUser = Depends(get_current_auth_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> ScriptureReference:
    """FR-003: a project cannot reach Script approved while any reference is
    unverified — this is the only way a reference becomes verified."""
    ref = await _get_owned_reference(db, workspace, reference_id)
    ref.verified_by = auth_user.id
    ref.verified_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(ref)
    return ref
