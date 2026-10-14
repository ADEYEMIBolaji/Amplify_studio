-- Amplify Studio — initial schema
-- Mirrors FRD v1.1 section 5 (Data model) in full. Tables for later-week
-- features (scripts, media, posts, metrics, ...) are created now so the
-- project state machine (FRD section 1.1) can check real preconditions
-- from Week 1 onward, even though most are only populated starting in
-- later sprint weeks. See docs/frd.md for field-by-field provenance.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Core / auth
-- ---------------------------------------------------------------------------

create table public.users (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.workspaces (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.users (id) on delete cascade,
  name text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index workspaces_owner_id_idx on public.workspaces (owner_id);

-- Helper used by RLS policies below. Backend connects with the service
-- role and bypasses RLS entirely (FRD section 1) — this is defense in
-- depth for any direct client access, not the primary authorisation path.
create or replace function public.is_workspace_owner(ws_id uuid)
returns boolean
language sql
security definer
stable
as $$
  select exists (
    select 1 from public.workspaces w
    where w.id = ws_id and w.owner_id = auth.uid()
  );
$$;

-- ---------------------------------------------------------------------------
-- Brand profile, topic tags (FR-020, FR-021)
-- ---------------------------------------------------------------------------

create table public.brand_profiles (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null unique references public.workspaces (id) on delete cascade,
  tone text,
  voice_samples_json jsonb not null default '[]'::jsonb,
  phrases_prefer text[] not null default '{}',
  phrases_avoid text[] not null default '{}',
  tradition text,
  guardrails_json jsonb not null default '[]'::jsonb,
  avoid_topics text[] not null default '{}',
  translation text not null default 'WEB',
  english_variant text not null default 'UK',
  wpm integer not null default 150,
  timezone text not null default 'Europe/London',
  subtitle_style_json jsonb not null default '{}'::jsonb,
  platform_flags_json jsonb not null default '{}'::jsonb,
  version_no integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.topic_tags (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  name text not null,
  archived boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, name)
);

create index topic_tags_workspace_id_idx on public.topic_tags (workspace_id);

-- ---------------------------------------------------------------------------
-- Projects and state machine (FR-002, FRD section 1.1)
-- ---------------------------------------------------------------------------

create table public.projects (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  title text not null,
  topic text not null,
  topic_tag_id uuid references public.topic_tags (id),
  audience text,
  status text not null default 'idea' check (status in (
    'idea', 'scripting', 'script_approved', 'recorded', 'subtitled',
    'ready', 'scheduled', 'published', 'measured'
  )),
  target_duration_seconds integer,
  actual_duration_seconds integer,
  hook_type text check (hook_type in ('question', 'bold_claim', 'story', 'scripture_first', 'other')),
  cta_type text check (cta_type in ('follow', 'comment', 'share', 'save', 'other')),
  format text check (format in ('teaching', 'devotional', 'testimony', 'qa')),
  length_bucket text check (length_bucket in ('under_45s', '45_90s', '90_180s')),
  approved_script_version_id uuid,
  archived_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index projects_workspace_id_idx on public.projects (workspace_id);
create index projects_workspace_id_status_idx on public.projects (workspace_id, status);

create table public.project_state_events (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  from_state text,
  to_state text not null,
  created_at timestamptz not null default now()
);

create index project_state_events_project_id_idx on public.project_state_events (project_id);

-- ---------------------------------------------------------------------------
-- Scripture (FR-003, FR-023)
-- ---------------------------------------------------------------------------

create table public.translations (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  name text not null,
  source_type text not null check (source_type in ('local', 'service', 'owner')),
  licence_notes text,
  quotation_limit_notes text,
  enabled boolean not null default true
);

create table public.scripture_references (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  book text not null,
  chapter integer not null,
  verse_start integer not null,
  verse_end integer,
  reference text not null,
  translation text not null,
  source text not null check (source in ('ai', 'user')),
  verified_by uuid references public.users (id),
  verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index scripture_references_project_id_idx on public.scripture_references (project_id);

-- ---------------------------------------------------------------------------
-- Script, hooks (FR-004, FR-005, FR-022)
-- ---------------------------------------------------------------------------

create table public.hook_variants (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  text text not null,
  hook_type text not null check (hook_type in ('question', 'bold_claim', 'story', 'scripture_first', 'other')),
  selected boolean not null default false,
  ai_job_id uuid,
  created_at timestamptz not null default now()
);

create index hook_variants_project_id_idx on public.hook_variants (project_id);

create table public.script_versions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  version_no integer not null,
  sections_json jsonb not null,
  source text not null check (source in ('ai', 'manual', 'mixed')),
  ai_job_id uuid,
  approved boolean not null default false,
  created_at timestamptz not null default now(),
  unique (project_id, version_no)
);

create index script_versions_project_id_idx on public.script_versions (project_id);

alter table public.projects
  add constraint projects_approved_script_version_id_fkey
  foreign key (approved_script_version_id) references public.script_versions (id);

-- ---------------------------------------------------------------------------
-- Media, transcripts (FR-007, FR-008, FR-009, FR-024)
-- ---------------------------------------------------------------------------

create table public.media_assets (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  object_key text not null,
  kind text not null check (kind in ('source', 'render', 'srt')),
  status text not null default 'pending',
  duration_seconds numeric,
  width integer,
  height integer,
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index media_assets_project_id_idx on public.media_assets (project_id);

create table public.transcripts (
  id uuid primary key default gen_random_uuid(),
  media_asset_id uuid not null references public.media_assets (id) on delete cascade,
  segments_json jsonb not null default '[]'::jsonb,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index transcripts_media_asset_id_idx on public.transcripts (media_asset_id);

create table public.custom_vocabulary (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  term text not null,
  created_at timestamptz not null default now(),
  unique (workspace_id, term)
);

-- ---------------------------------------------------------------------------
-- Publishing (FR-010, FR-011, FR-012, FR-026, FR-027)
-- ---------------------------------------------------------------------------

create table public.social_posts (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references public.projects (id) on delete cascade,
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  platform text not null check (platform in ('instagram', 'tiktok', 'facebook', 'x')),
  caption text,
  hashtags text[] not null default '{}',
  cta text,
  media_asset_id uuid references public.media_assets (id),
  status text not null default 'draft' check (status in ('draft', 'ready', 'published')),
  scheduled_at timestamptz,
  timezone text not null default 'Europe/London',
  posting_slot text check (posting_slot in ('morning', 'midday', 'evening')),
  published_at timestamptz,
  external_post_id text,
  external_url text,
  is_historical boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index social_posts_workspace_id_idx on public.social_posts (workspace_id);
create index social_posts_project_id_idx on public.social_posts (project_id);
create index social_posts_platform_idx on public.social_posts (workspace_id, platform);

create table public.reminders (
  id uuid primary key default gen_random_uuid(),
  social_post_id uuid not null references public.social_posts (id) on delete cascade,
  channel text not null default 'email',
  send_at timestamptz not null,
  sent_at timestamptz,
  created_at timestamptz not null default now()
);

create index reminders_social_post_id_idx on public.reminders (social_post_id);

-- ---------------------------------------------------------------------------
-- Growth Lab (FR-013 to FR-019, FR-028, FR-029)
-- ---------------------------------------------------------------------------

create table public.mapping_templates (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  platform text not null,
  column_map_json jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.import_batches (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  platform text not null,
  mapping_template_id uuid references public.mapping_templates (id),
  file_name text,
  row_count integer not null default 0,
  error_count integer not null default 0,
  committed_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.metric_snapshots (
  id uuid primary key default gen_random_uuid(),
  social_post_id uuid not null references public.social_posts (id) on delete cascade,
  platform text not null,
  captured_at timestamptz not null,
  days_since_publish integer,
  reach integer,
  impressions integer,
  views integer,
  likes integer,
  comments integer,
  shares integer,
  saves integer,
  watch_seconds_avg numeric,
  completion_rate numeric,
  profile_visits integer,
  import_batch_id uuid references public.import_batches (id),
  created_at timestamptz not null default now(),
  unique (social_post_id, captured_at)
);

create index metric_snapshots_social_post_id_idx on public.metric_snapshots (social_post_id);

create table public.follower_snapshots (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  platform text not null,
  captured_at timestamptz not null,
  follower_count integer not null,
  created_at timestamptz not null default now(),
  unique (workspace_id, platform, captured_at)
);

create index follower_snapshots_workspace_id_idx on public.follower_snapshots (workspace_id, platform);

create table public.experiments (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  hypothesis text not null,
  variable text not null check (variable in ('hook', 'topic', 'length', 'cta', 'posting_slot')),
  metric text not null,
  status text not null default 'open' check (status in ('open', 'closed')),
  outcome text check (outcome in ('supported', 'not_supported', 'inconclusive')),
  outcome_note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.experiment_posts (
  experiment_id uuid not null references public.experiments (id) on delete cascade,
  social_post_id uuid not null references public.social_posts (id) on delete cascade,
  variant text,
  primary key (experiment_id, social_post_id)
);

create table public.weekly_reviews (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  week_start date not null,
  report_json jsonb not null default '{}'::jsonb,
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (workspace_id, week_start)
);

-- ---------------------------------------------------------------------------
-- AI provenance, audit (FRD section 1 "AI provenance", NFR Security)
-- ---------------------------------------------------------------------------

create table public.ai_jobs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  type text not null,
  status text not null default 'pending' check (status in ('pending', 'running', 'succeeded', 'failed')),
  model_id text,
  prompt_version text,
  input_hash text,
  result_json jsonb,
  error_code text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index ai_jobs_workspace_id_idx on public.ai_jobs (workspace_id);

create table public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces (id) on delete cascade,
  actor_id uuid references public.users (id),
  action text not null,
  entity text not null,
  entity_id uuid,
  created_at timestamptz not null default now()
);

create index audit_logs_workspace_id_idx on public.audit_logs (workspace_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Row-level security (defense in depth; backend uses the service role and
-- enforces workspace ownership explicitly in every handler — FRD section 1)
-- ---------------------------------------------------------------------------

alter table public.workspaces enable row level security;
alter table public.brand_profiles enable row level security;
alter table public.topic_tags enable row level security;
alter table public.projects enable row level security;
alter table public.project_state_events enable row level security;
alter table public.scripture_references enable row level security;
alter table public.hook_variants enable row level security;
alter table public.script_versions enable row level security;
alter table public.media_assets enable row level security;
alter table public.transcripts enable row level security;
alter table public.custom_vocabulary enable row level security;
alter table public.social_posts enable row level security;
alter table public.reminders enable row level security;
alter table public.mapping_templates enable row level security;
alter table public.import_batches enable row level security;
alter table public.metric_snapshots enable row level security;
alter table public.follower_snapshots enable row level security;
alter table public.experiments enable row level security;
alter table public.experiment_posts enable row level security;
alter table public.weekly_reviews enable row level security;
alter table public.ai_jobs enable row level security;
alter table public.audit_logs enable row level security;

create policy workspaces_owner_only on public.workspaces
  using (owner_id = auth.uid()) with check (owner_id = auth.uid());

create policy brand_profiles_owner_only on public.brand_profiles
  using (is_workspace_owner(workspace_id)) with check (is_workspace_owner(workspace_id));

create policy topic_tags_owner_only on public.topic_tags
  using (is_workspace_owner(workspace_id)) with check (is_workspace_owner(workspace_id));

create policy projects_owner_only on public.projects
  using (is_workspace_owner(workspace_id)) with check (is_workspace_owner(workspace_id));

create policy project_state_events_owner_only on public.project_state_events
  using (exists (select 1 from public.projects p where p.id = project_id and is_workspace_owner(p.workspace_id)));

create policy scripture_references_owner_only on public.scripture_references
  using (exists (select 1 from public.projects p where p.id = project_id and is_workspace_owner(p.workspace_id)));

create policy hook_variants_owner_only on public.hook_variants
  using (exists (select 1 from public.projects p where p.id = project_id and is_workspace_owner(p.workspace_id)));

create policy script_versions_owner_only on public.script_versions
  using (exists (select 1 from public.projects p where p.id = project_id and is_workspace_owner(p.workspace_id)));

create policy media_assets_owner_only on public.media_assets
  using (exists (select 1 from public.projects p where p.id = project_id and is_workspace_owner(p.workspace_id)));

create policy transcripts_owner_only on public.transcripts
  using (exists (
    select 1 from public.media_assets m
    join public.projects p on p.id = m.project_id
    where m.id = media_asset_id and is_workspace_owner(p.workspace_id)
  ));

create policy custom_vocabulary_owner_only on public.custom_vocabulary
  using (is_workspace_owner(workspace_id)) with check (is_workspace_owner(workspace_id));

create policy social_posts_owner_only on public.social_posts
  using (is_workspace_owner(workspace_id)) with check (is_workspace_owner(workspace_id));

create policy reminders_owner_only on public.reminders
  using (exists (select 1 from public.social_posts sp where sp.id = social_post_id and is_workspace_owner(sp.workspace_id)));

create policy mapping_templates_owner_only on public.mapping_templates
  using (is_workspace_owner(workspace_id)) with check (is_workspace_owner(workspace_id));

create policy import_batches_owner_only on public.import_batches
  using (is_workspace_owner(workspace_id)) with check (is_workspace_owner(workspace_id));

create policy metric_snapshots_owner_only on public.metric_snapshots
  using (exists (select 1 from public.social_posts sp where sp.id = social_post_id and is_workspace_owner(sp.workspace_id)));

create policy follower_snapshots_owner_only on public.follower_snapshots
  using (is_workspace_owner(workspace_id)) with check (is_workspace_owner(workspace_id));

create policy experiments_owner_only on public.experiments
  using (is_workspace_owner(workspace_id)) with check (is_workspace_owner(workspace_id));

create policy experiment_posts_owner_only on public.experiment_posts
  using (exists (select 1 from public.experiments e where e.id = experiment_id and is_workspace_owner(e.workspace_id)));

create policy weekly_reviews_owner_only on public.weekly_reviews
  using (is_workspace_owner(workspace_id)) with check (is_workspace_owner(workspace_id));

create policy ai_jobs_owner_only on public.ai_jobs
  using (is_workspace_owner(workspace_id)) with check (is_workspace_owner(workspace_id));

create policy audit_logs_owner_only on public.audit_logs
  using (is_workspace_owner(workspace_id));

-- ---------------------------------------------------------------------------
-- Seed data: allowlisted translations (FR-023). Verse text itself is not
-- stored here — only licence metadata. The WEB text lives in a local data
-- file loaded by the backend (see apps/api/app/providers), not the DB.
-- ---------------------------------------------------------------------------

insert into public.translations (code, name, source_type, licence_notes, quotation_limit_notes, enabled)
values
  ('WEB', 'World English Bible', 'local', 'Public domain worldwide.', 'No limit.', true),
  ('OWNER', 'Owner-pasted text', 'owner', 'Supplied by the Owner at time of use; not redistributed.', 'Owner is responsible for their own usage rights.', true);
