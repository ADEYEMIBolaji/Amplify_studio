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
