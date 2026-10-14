import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CustomVocabulary, Workspace
from app.deps import DbSession, get_current_workspace
from app.errors import ConflictError, NotFoundError
from app.models.schemas import CustomVocabularyCreate, CustomVocabularyOut
from app.providers.vocabulary_seed import SEED_VOCABULARY

router = APIRouter(prefix="/api/vocabulary", tags=["vocabulary"])


@router.get("", response_model=dict)
async def list_vocabulary(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-008: the seeded biblical-name list plus the Owner's own additions."""
    result = await db.execute(
        select(CustomVocabulary).where(CustomVocabulary.workspace_id == workspace.id)
    )
    custom = list(result.scalars().all())
    return {
        "seed": SEED_VOCABULARY,
        "custom": [CustomVocabularyOut.model_validate(c) for c in custom],
    }


@router.post("", response_model=CustomVocabularyOut, status_code=201)
async def add_vocabulary_term(
    payload: CustomVocabularyCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> CustomVocabulary:
    existing = await db.execute(
        select(CustomVocabulary).where(
            CustomVocabulary.workspace_id == workspace.id, CustomVocabulary.term == payload.term
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"'{payload.term}' is already in your vocabulary.")

    term = CustomVocabulary(workspace_id=workspace.id, term=payload.term)
    db.add(term)
    await db.commit()
    await db.refresh(term)
    return term


@router.delete("/{term_id}", status_code=204)
async def delete_vocabulary_term(
    term_id: uuid.UUID,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> None:
    term = await db.get(CustomVocabulary, term_id)
    if term is None or term.workspace_id != workspace.id:
        raise NotFoundError("Vocabulary term not found.")
    await db.delete(term)
    await db.commit()
