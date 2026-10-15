import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Experiment, ExperimentPost, Project, SocialPost, Workspace
from app.deps import DbSession, get_current_workspace
from app.errors import BadRequestError, NotFoundError
from app.models.schemas import ExperimentCreate, ExperimentOut, ExperimentUpdate
from app.services.insights import GROUP_DIMENSIONS, get_post_tags

router = APIRouter(prefix="/api/experiments", tags=["experiments"])

VARIABLE_TO_DIMENSION = {
    "hook": "hook_type",
    "topic": "topic_tag_id",
    "length": "length_bucket",
    "cta": "cta_type",
    "posting_slot": "posting_slot",
}


async def _get_owned_experiment(
    db: AsyncSession, workspace: Workspace, experiment_id: uuid.UUID
) -> Experiment:
    experiment = await db.get(Experiment, experiment_id)
    if experiment is None or experiment.workspace_id != workspace.id:
        raise NotFoundError("Experiment not found.")
    return experiment


async def _compute_confounders(
    db: AsyncSession, experiment: Experiment, post_ids: list[uuid.UUID]
) -> list[str]:
    """FR-018: tags that differ between the compared posts, other than the
    primary variable, surfaced as possible confounders."""
    primary_dimension = VARIABLE_TO_DIMENSION.get(experiment.variable)
    tag_sets: list[dict] = []
    for post_id in post_ids:
        post = await db.get(SocialPost, post_id)
        if post is None:
            continue
        project = await db.get(Project, post.project_id) if post.project_id else None
        tag_sets.append(get_post_tags(post, project))

    confounders = []
    for dimension in GROUP_DIMENSIONS:
        if dimension == primary_dimension:
            continue
        values = {t.get(dimension) for t in tag_sets}
        if len(values) > 1:
            confounders.append(dimension)
    return confounders


async def _to_out(db: AsyncSession, experiment: Experiment) -> dict:
    result = await db.execute(
        select(ExperimentPost.social_post_id).where(ExperimentPost.experiment_id == experiment.id)
    )
    post_ids = [row[0] for row in result.all()]
    confounders = await _compute_confounders(db, experiment, post_ids)
    return {
        "id": experiment.id,
        "workspace_id": experiment.workspace_id,
        "hypothesis": experiment.hypothesis,
        "variable": experiment.variable,
        "metric": experiment.metric,
        "status": experiment.status,
        "outcome": experiment.outcome,
        "outcome_note": experiment.outcome_note,
        "post_ids": [str(p) for p in post_ids],
        "confounders": confounders,
        "created_at": experiment.created_at,
        "updated_at": experiment.updated_at,
    }


@router.post("", response_model=ExperimentOut, status_code=201)
async def create_experiment(
    payload: ExperimentCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-018: hypothesis, one primary variable, comparison posts, metric;
    other differing tags are surfaced as possible confounders."""
    if payload.variable not in VARIABLE_TO_DIMENSION:
        raise BadRequestError(f"'{payload.variable}' is not a valid variable.")

    for post_id in payload.post_ids:
        post = await db.get(SocialPost, post_id)
        if post is None or post.workspace_id != workspace.id:
            raise NotFoundError(f"Post {post_id} not found.")

    experiment = Experiment(
        workspace_id=workspace.id,
        hypothesis=payload.hypothesis,
        variable=payload.variable,
        metric=payload.metric,
    )
    db.add(experiment)
    await db.flush()

    for post_id in payload.post_ids:
        db.add(
            ExperimentPost(
                experiment_id=experiment.id,
                social_post_id=post_id,
                variant=payload.variants.get(str(post_id)),
            )
        )

    await db.commit()
    await db.refresh(experiment)
    return await _to_out(db, experiment)


@router.get("", response_model=list[ExperimentOut])
async def list_experiments(
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> list[dict]:
    result = await db.execute(select(Experiment).where(Experiment.workspace_id == workspace.id))
    return [await _to_out(db, e) for e in result.scalars().all()]


@router.patch("/{experiment_id}", response_model=ExperimentOut)
async def update_experiment(
    experiment_id: uuid.UUID,
    payload: ExperimentUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: AsyncSession = DbSession,
) -> dict:
    """FR-018: Owner records outcome (supported / not_supported /
    inconclusive) with a note."""
    experiment = await _get_owned_experiment(db, workspace, experiment_id)

    if payload.outcome is not None:
        if payload.outcome not in {"supported", "not_supported", "inconclusive"}:
            raise BadRequestError(f"'{payload.outcome}' is not a valid outcome.")
        experiment.outcome = payload.outcome
        experiment.status = "closed"
    if payload.outcome_note is not None:
        experiment.outcome_note = payload.outcome_note
    if payload.status is not None:
        experiment.status = payload.status

    await db.commit()
    await db.refresh(experiment)
    return await _to_out(db, experiment)
