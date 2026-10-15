import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.types import GUID, UTCDateTime

# Mirrors supabase/migrations/0001_init.sql, which is the schema's source of
# truth (FRD section 5). Keep both in sync when a field changes.

PROJECT_STATES = (
    "idea",
    "scripting",
    "script_approved",
    "recorded",
    "subtitled",
    "ready",
    "scheduled",
    "published",
    "measured",
)


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    owner_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class BrandProfile(Base):
    __tablename__ = "brand_profiles"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("workspaces.id"), nullable=False, unique=True
    )
    tone: Mapped[str | None] = mapped_column(Text, nullable=True)
    voice_samples_json: Mapped[list] = mapped_column(JSON, default=list)
    phrases_prefer: Mapped[list] = mapped_column(JSON, default=list)
    phrases_avoid: Mapped[list] = mapped_column(JSON, default=list)
    tradition: Mapped[str | None] = mapped_column(Text, nullable=True)
    guardrails_json: Mapped[list] = mapped_column(JSON, default=list)
    avoid_topics: Mapped[list] = mapped_column(JSON, default=list)
    translation: Mapped[str] = mapped_column(String, default="WEB")
    english_variant: Mapped[str] = mapped_column(String, default="UK")
    wpm: Mapped[int] = mapped_column(Integer, default=150)
    timezone: Mapped[str] = mapped_column(String, default="Europe/London")
    subtitle_style_json: Mapped[dict] = mapped_column(JSON, default=dict)
    platform_flags_json: Mapped[dict] = mapped_column(JSON, default=dict)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TopicTag(Base):
    __tablename__ = "topic_tags"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    topic_tag_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("topic_tags.id"), nullable=True)
    audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="idea")
    target_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hook_type: Mapped[str | None] = mapped_column(String, nullable=True)
    cta_type: Mapped[str | None] = mapped_column(String, nullable=True)
    format: Mapped[str | None] = mapped_column(String, nullable=True)
    length_bucket: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_script_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ProjectStateEvent(Base):
    __tablename__ = "project_state_events"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("projects.id"), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String, nullable=True)
    to_state: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ScriptureReference(Base):
    __tablename__ = "scripture_references"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("projects.id"), nullable=False)
    book: Mapped[str] = mapped_column(String, nullable=False)
    chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    verse_start: Mapped[int] = mapped_column(Integer, nullable=False)
    verse_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference: Mapped[str] = mapped_column(String, nullable=False)
    translation: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    pasted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Translation(Base):
    __tablename__ = "translations"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    licence_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    quotation_limit_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class HookVariant(Base):
    __tablename__ = "hook_variants"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("projects.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    hook_type: Mapped[str] = mapped_column(String, nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_job_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ScriptVersion(Base):
    __tablename__ = "script_versions"
    __table_args__ = (UniqueConstraint("project_id", "version_no"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("projects.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    sections_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    ai_job_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("projects.id"), nullable=False)
    object_key: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending")
    duration_seconds: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    media_asset_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("media_assets.id"), nullable=False)
    segments_json: Mapped[list] = mapped_column(JSON, default=list)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class CustomVocabulary(Base):
    __tablename__ = "custom_vocabulary"
    __table_args__ = (UniqueConstraint("workspace_id", "term"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False)
    term: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class SocialPost(Base):
    __tablename__ = "social_posts"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("projects.id"), nullable=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags: Mapped[list] = mapped_column(JSON, default=list)
    cta: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("media_assets.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, default="draft")
    scheduled_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    timezone: Mapped[str] = mapped_column(String, default="Europe/London")
    posting_slot: Mapped[str | None] = mapped_column(String, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    external_post_id: Mapped[str | None] = mapped_column(String, nullable=True)
    external_url: Mapped[str | None] = mapped_column(String, nullable=True)
    is_historical: Mapped[bool] = mapped_column(Boolean, default=False)
    tags_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    social_post_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("social_posts.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String, default="email")
    send_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class MappingTemplate(Base):
    __tablename__ = "mapping_templates"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    column_map_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    mapping_template_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("mapping_templates.id"), nullable=True
    )
    file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    committed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    __table_args__ = (UniqueConstraint("social_post_id", "captured_at"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    social_post_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("social_posts.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(nullable=False)
    days_since_publish: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)
    watch_seconds_avg: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    completion_rate: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    profile_visits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("import_batches.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class FollowerSnapshot(Base):
    __tablename__ = "follower_snapshots"
    __table_args__ = (UniqueConstraint("workspace_id", "platform", "captured_at"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(nullable=False)
    follower_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    variable: Mapped[str] = mapped_column(String, nullable=False)
    metric: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="open")
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ExperimentPost(Base):
    __tablename__ = "experiment_posts"

    experiment_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("experiments.id"), primary_key=True)
    social_post_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("social_posts.id"), primary_key=True)
    variant: Mapped[str | None] = mapped_column(String, nullable=True)


class WeeklyReview(Base):
    __tablename__ = "weekly_reviews"
    __table_args__ = (UniqueConstraint("workspace_id", "week_start"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    report_json: Mapped[dict] = mapped_column(JSON, default=dict)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AiJob(Base):
    __tablename__ = "ai_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending")
    model_id: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String, nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class MediaUploadSession(Base):
    __tablename__ = "media_upload_sessions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("projects.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    total_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False)
    total_chunks: Mapped[int] = mapped_column(Integer, nullable=False)
    received_chunks: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class MediaJob(Base):
    __tablename__ = "media_jobs"
    __table_args__ = (UniqueConstraint("idempotency_key"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False)
    media_asset_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("media_assets.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending")
    idempotency_key: Mapped[str | None] = mapped_column(String, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PlatformLimit(Base):
    __tablename__ = "platform_limits"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    platform: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    caption_max_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    caption_max_chars_premium: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_max_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_max_seconds_premium: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hashtag_max_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aspect_ratio: Mapped[str] = mapped_column(String, default="9:16")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
