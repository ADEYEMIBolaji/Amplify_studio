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


class SectionOut(BaseModel):
    text: str
    source: str  # ai | manual


class ScriptVersionOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    version_no: int
    sections: dict[str, SectionOut]
    source: str  # ai | manual | mixed (rollup)
    approved: bool
    ai_job_id: uuid.UUID | None
    word_count: int
    estimated_duration_seconds: float
    created_at: datetime

    model_config = {"from_attributes": True}


class ScriptManualEditRequest(BaseModel):
    sections: dict[str, str] = Field(min_length=1)


class RegenerateSectionRequest(BaseModel):
    section: str
    confirm: bool = False


class HookVariantOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    text: str
    hook_type: str
    selected: bool

    model_config = {"from_attributes": True}


class HookSelectRequest(BaseModel):
    selected: bool = True


# ---------------------------------------------------------------------------
# Scripture references — FR-003, FR-023
# ---------------------------------------------------------------------------


class ScriptureReferenceCreate(BaseModel):
    reference: str = Field(description="e.g. 'John 3:16' or '1 Corinthians 13:4-7'")
    translation: str = "WEB"


class ScriptureReferenceUpdate(BaseModel):
    reference: str | None = None
    translation: str | None = None
    pasted_text: str | None = None


class ScriptureReferenceOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    book: str
    chapter: int
    verse_start: int
    verse_end: int | None
    reference: str
    translation: str
    source: str  # ai | user
    verified_by: uuid.UUID | None
    verified_at: datetime | None
    pasted_text: str | None

    model_config = {"from_attributes": True}


class ExpandedReferenceOut(BaseModel):
    reference: str
    text: str | None
    translation: str
    unavailable: bool = False


class ExpandVersesResponse(BaseModel):
    sections: dict[str, str]
    references: list[ExpandedReferenceOut]


class MediaUploadInitRequest(BaseModel):
    project_id: uuid.UUID
    filename: str
    content_type: str
    total_size: int = Field(gt=0)
    chunk_size: int = Field(default=5_000_000, gt=0)


class MediaUploadSessionOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    total_size: int
    chunk_size: int
    total_chunks: int
    received_chunks: list[int]
    status: str

    model_config = {"from_attributes": True}


class MediaUploadCompleteOut(BaseModel):
    media_asset_id: uuid.UUID
    job_id: uuid.UUID


class MediaAssetOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    kind: str
    status: str
    duration_seconds: float | None
    width: int | None
    height: int | None
    metadata_json: dict
    download_url: str | None = None

    model_config = {"from_attributes": True}


class MediaJobOut(BaseModel):
    id: uuid.UUID
    media_asset_id: uuid.UUID
    job_type: str
    status: str
    retry_count: int
    error_code: str | None
    result_json: dict | None

    model_config = {"from_attributes": True}


class TranscriptSegmentSchema(BaseModel):
    start: float
    end: float
    text: str


class TranscriptOut(BaseModel):
    id: uuid.UUID
    media_asset_id: uuid.UUID
    segments: list[TranscriptSegmentSchema]
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class TranscriptUpdateRequest(BaseModel):
    segments: list[TranscriptSegmentSchema] = Field(min_length=1)


class CustomVocabularyOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    term: str

    model_config = {"from_attributes": True}


class CustomVocabularyCreate(BaseModel):
    term: str = Field(min_length=1, max_length=100)


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
