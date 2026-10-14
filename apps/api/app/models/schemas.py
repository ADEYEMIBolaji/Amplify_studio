import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import PROJECT_STATES

# ---------------------------------------------------------------------------
# Projects — FR-002
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    topic: str = Field(min_length=1, max_length=200)
    audience: str | None = None
    target_duration_seconds: int | None = Field(default=None, ge=1, le=180)
    topic_tag_id: uuid.UUID | None = None


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    topic: str | None = Field(default=None, min_length=1, max_length=200)
    audience: str | None = None
    target_duration_seconds: int | None = Field(default=None, ge=1, le=180)
    topic_tag_id: uuid.UUID | None = None


class ProjectTransition(BaseModel):
    target_state: str = Field(description=f"One of: {', '.join(PROJECT_STATES)}")


class ProjectOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    topic: str
    topic_tag_id: uuid.UUID | None
    audience: str | None
    status: str
    target_duration_seconds: int | None
    actual_duration_seconds: int | None
    hook_type: str | None
    cta_type: str | None
    format: str | None
    length_bucket: str | None
    approved_script_version_id: uuid.UUID | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Topic tags — FR-021
# ---------------------------------------------------------------------------


class TopicTagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TopicTagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    archived: bool | None = None


class TopicTagOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    archived: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Brand profile — FR-020
# ---------------------------------------------------------------------------


class BrandProfileUpdate(BaseModel):
    tone: str | None = None
    voice_samples_json: list[str] | None = None
    phrases_prefer: list[str] | None = None
    phrases_avoid: list[str] | None = None
    tradition: str | None = None
    guardrails_json: list[str] | None = None
    avoid_topics: list[str] | None = None
    translation: str | None = None
    english_variant: str | None = None
    wpm: int | None = Field(default=None, ge=80, le=220)
    timezone: str | None = None


class BrandProfileOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    tone: str | None
    voice_samples_json: list
    phrases_prefer: list
    phrases_avoid: list
    tradition: str | None
    guardrails_json: list
    avoid_topics: list
    translation: str
    english_variant: str
    wpm: int
    timezone: str
    version_no: int

    model_config = {"from_attributes": True}
