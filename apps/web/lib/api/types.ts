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
  version_no: number;
}
