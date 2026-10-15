// Mirrors apps/api/app/models/schemas.py — keep in sync when FR-002 fields change.

export const PROJECT_STATES = [
  "idea",
  "scripting",
  "script_approved",
  "recorded",
  "subtitled",
  "ready",
  "scheduled",
  "published",
  "measured",
] as const;

export type ProjectState = (typeof PROJECT_STATES)[number];

export interface Project {
  id: string;
  workspace_id: string;
  title: string;
  topic: string;
  topic_tag_id: string | null;
  audience: string | null;
  status: ProjectState;
  target_duration_seconds: number | null;
  actual_duration_seconds: number | null;
  hook_type: string | null;
  cta_type: string | null;
  format: string | null;
  length_bucket: string | null;
  approved_script_version_id: string | null;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreateInput {
  title: string;
  topic: string;
  audience?: string;
  target_duration_seconds?: number;
  topic_tag_id?: string;
}

export interface ProjectUpdateInput {
  title?: string;
  topic?: string;
  audience?: string;
  target_duration_seconds?: number;
  topic_tag_id?: string;
}

export interface TopicTag {
  id: string;
  workspace_id: string;
  name: string;
  archived: boolean;
}

export const SCRIPT_SECTIONS = [
  "hook",
  "biblical_context",
  "main_teaching",
  "practical_application",
  "closing_cta",
] as const;

export type ScriptSection = (typeof SCRIPT_SECTIONS)[number];

export interface SectionContent {
  text: string;
  source: "ai" | "manual";
}

export interface ScriptVersion {
  id: string;
  project_id: string;
  version_no: number;
  sections: Record<ScriptSection, SectionContent>;
  source: "ai" | "manual" | "mixed";
  approved: boolean;
  ai_job_id: string | null;
  word_count: number;
  estimated_duration_seconds: number;
  created_at: string;
}

export type HookType = "question" | "bold_claim" | "story" | "scripture_first" | "other";

export interface HookVariant {
  id: string;
  project_id: string;
  text: string;
  hook_type: HookType;
  selected: boolean;
}

export interface ScriptureReference {
  id: string;
  project_id: string;
  book: string;
  chapter: number;
  verse_start: number;
  verse_end: number | null;
  reference: string;
  translation: string;
  source: "ai" | "user";
  verified_by: string | null;
  verified_at: string | null;
  pasted_text: string | null;
}

export interface ExpandedReference {
  reference: string;
  text: string | null;
  translation: string;
  unavailable: boolean;
}

export interface ExpandVersesResponse {
  sections: Record<ScriptSection, string>;
  references: ExpandedReference[];
}

export interface MediaUploadSession {
  id: string;
  project_id: string;
  filename: string;
  total_size: number;
  chunk_size: number;
  total_chunks: number;
  received_chunks: number[];
  status: "pending" | "completed" | "aborted";
}

export type MediaAssetKind = "source" | "render" | "srt";

export interface MediaAsset {
  id: string;
  project_id: string;
  kind: MediaAssetKind;
  status: string;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  metadata_json: Record<string, unknown>;
  download_url: string | null;
}

export interface MediaJob {
  id: string;
  media_asset_id: string;
  job_type: "normalize" | "transcribe" | "render";
  status: "pending" | "running" | "succeeded" | "failed";
  retry_count: number;
  error_code: string | null;
  result_json: Record<string, unknown> | null;
}

export interface TranscriptSegmentItem {
  start: number;
  end: number;
  text: string;
}

export interface Transcript {
  id: string;
  media_asset_id: string;
  segments: TranscriptSegmentItem[];
  reviewed_at: string | null;
}

export type Platform = "instagram" | "tiktok" | "facebook" | "x";
export type PostStatus = "draft" | "ready" | "published";

export interface SocialPost {
  id: string;
  project_id: string | null;
  workspace_id: string;
  platform: Platform;
  caption: string | null;
  hashtags: string[];
  cta: string | null;
  media_asset_id: string | null;
  status: PostStatus;
  scheduled_at: string | null;
  timezone: string;
  posting_slot: "morning" | "midday" | "evening" | null;
  published_at: string | null;
  external_post_id: string | null;
  external_url: string | null;
  is_historical: boolean;
  created_at: string;
  updated_at: string;
}

export interface PlatformLimit {
  platform: Platform;
  caption_max_chars: number;
  caption_max_chars_premium: number | null;
  duration_max_seconds: number;
  duration_max_seconds_premium: number | null;
  hashtag_max_count: number | null;
  aspect_ratio: string;
  verified: boolean;
  notes: string | null;
}

export interface MetricSnapshot {
  id: string;
  social_post_id: string;
  platform: Platform;
  captured_at: string;
  days_since_publish: number | null;
  reach: number | null;
  impressions: number | null;
  views: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  saves: number | null;
  watch_seconds_avg: number | null;
  completion_rate: number | null;
  profile_visits: number | null;
  flagged_fields: string[];
}

export interface FollowerSnapshot {
  id: string;
  workspace_id: string;
  platform: Platform;
  captured_at: string;
  follower_count: number;
}

export interface DataCoverage {
  eligible: number;
  total: number;
}

export interface PlatformPeriodMetrics {
  platform: Platform;
  start: string;
  end: string;
  target_day: number;
  window_days: number;
  reach_median: number | null;
  reach_mean: number | null;
  engagement_per_reach: number | null;
  share_rate: number | null;
  save_rate: number | null;
  watch_seconds_avg: number | null;
  completion_rate: number | null;
  net_follower_change: number | null;
  net_follower_change_low_confidence: boolean;
  followers_per_1000_reached: number | null;
  posting_adherence: number | null;
  data_coverage: DataCoverage;
  low_sample: boolean;
}

export interface AnalyticsOverview {
  current: PlatformPeriodMetrics;
  previous: PlatformPeriodMetrics;
}

export interface NextAction {
  project_id: string;
  title: string;
  status: string;
  next_action: string;
}

export interface TrendPoint {
  captured_at?: string;
  date?: string;
  follower_count?: number;
  reach?: number | null;
}

export interface HomeDashboard {
  next_actions: NextAction[];
  pipeline_counts: Record<string, number>;
  posting_adherence_this_week: number | null;
  posting_adherence_last_week: number | null;
  last_follower_snapshot_at: Record<Platform, string | null>;
  reach_trend: Record<Platform, TrendPoint[]>;
  follower_trend: Record<Platform, TrendPoint[]>;
  active_experiments: unknown[];
}

export interface BrandProfile {
  id: string;
  workspace_id: string;
  tone: string | null;
  voice_samples_json: string[];
  phrases_prefer: string[];
  phrases_avoid: string[];
  tradition: string | null;
  guardrails_json: string[];
  avoid_topics: string[];
  translation: string;
  english_variant: string;
  wpm: number;
  timezone: string;
  platform_flags_json: Record<string, boolean>;
  version_no: number;
}
