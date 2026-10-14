import hashlib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AiJob


def record(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    job_type: str,
    model_id: str,
    prompt_version: str,
    input_payload: str,
    result_json: dict,
) -> AiJob:
    """FRD section 1 'AI provenance': every AI call records model ID, prompt
    template version and input hash so outputs are reproducible and auditable."""
    job = AiJob(
        workspace_id=workspace_id,
        type=job_type,
        status="succeeded",
        model_id=model_id,
        prompt_version=prompt_version,
        input_hash=hashlib.sha256(input_payload.encode()).hexdigest(),
        result_json=result_json,
    )
    db.add(job)
    return job
