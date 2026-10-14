import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TopicTag, Workspace
from app.deps import DbSession, get_current_workspace
from app.errors import ConflictError, NotFoundError
from app.models.schemas import TopicTagCreate, TopicTagOut, TopicTagUpdate

router = APIRouter(prefix="/api/topic-tags", tags=["topic-tags"])


@router.get("", response_model=list[TopicTagOut])
async def list_topic_tags(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> list[TopicTag]:
    result = await db.execute(
        select(TopicTag).where(TopicTag.workspace_id == workspace.id).order_by(TopicTag.name)
    )
    return list(result.scalars().all())


@router.post("", response_model=TopicTagOut, status_code=201)
async def create_topic_tag(
    payload: TopicTagCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> TopicTag:
    tag = TopicTag(workspace_id=workspace.id, name=payload.name)
    db.add(tag)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(f"A topic tag named '{payload.name}' already exists.") from exc
    await db.refresh(tag)
    return tag


@router.patch("/{tag_id}", response_model=TopicTagOut)
async def update_topic_tag(
    tag_id: uuid.UUID,
    payload: TopicTagUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> TopicTag:
    tag = await db.get(TopicTag, tag_id)
    if tag is None or tag.workspace_id != workspace.id:
        raise NotFoundError("Topic tag not found.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tag, field, value)
    await db.commit()
    await db.refresh(tag)
    return tag
