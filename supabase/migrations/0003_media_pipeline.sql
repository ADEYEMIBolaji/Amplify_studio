-- Media pipeline — FR-007 (resumable upload), FR-008 (transcription),
-- FR-009 (export). Mirrors FRD section 1 "Async jobs for transcription,
-- rendering and AI tasks ... retry policy, job statuses and idempotency
-- keys" — ai_jobs already covers AI tasks (Week 2); media_jobs is the same
-- pattern for upload normalisation, transcription and rendering.

create table public.media_upload_sessions (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  project_id uuid not null references public.projects (id) on delete cascade,
  filename text not null,
  content_type text not null,
  total_size bigint not null,
  chunk_size integer not null,
  total_chunks integer not null,
  received_chunks jsonb not null default '[]'::jsonb,
  status text not null default 'pending' check (status in ('pending', 'completed', 'aborted')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index media_upload_sessions_workspace_id_idx on public.media_upload_sessions (workspace_id);

alter table public.media_upload_sessions enable row level security;

create policy media_upload_sessions_owner_only on public.media_upload_sessions
  using (is_workspace_owner(workspace_id)) with check (is_workspace_owner(workspace_id));

create table public.media_jobs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  media_asset_id uuid not null references public.media_assets (id) on delete cascade,
  job_type text not null check (job_type in ('normalize', 'transcribe', 'render')),
  status text not null default 'pending' check (status in ('pending', 'running', 'succeeded', 'failed')),
  idempotency_key text,
  retry_count integer not null default 0,
  max_retries integer not null default 3,
  error_code text,
  result_json jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (idempotency_key)
);

create index media_jobs_workspace_id_idx on public.media_jobs (workspace_id);
create index media_jobs_status_idx on public.media_jobs (status);

alter table public.media_jobs enable row level security;

create policy media_jobs_owner_only on public.media_jobs
  using (is_workspace_owner(workspace_id)) with check (is_workspace_owner(workspace_id));
