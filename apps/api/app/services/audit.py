import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


def record(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    entity: str,
    entity_id: uuid.UUID | None,
) -> None:
    db.add(
        AuditLog(
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
        )
    )
