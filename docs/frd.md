Version 1.1 \| 14 October 2026 \| Owner: Bee \| Status: Revised
build-ready draft

# 0. Document control

| **Version** | **Date**    | **Summary**                                                                                                                                                                                                                                                                                                                                                                                                                                        |
|-------------|-------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1.0         | 14 Oct 2026 | Build-ready draft.                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| 1.1         | 14 Oct 2026 | Review changes applied: in-app recording and prompter modes; verse-text placeholder rule; content attribute tags; cumulative metric snapshots compared at equal post age; median reach; per-platform metric formulas; historical baseline import; project state machine; publishing reminders; platform video limits; data model and API gaps closed; acceptance tests and sprint plan revised. Original FR numbers kept; new FRs start at FR-020. |

Tags used below: **new** a requirement added in v1.1; **revised** an
original requirement changed in v1.1. Requirements without a tag are
unchanged. Companion document: Amplify Studio MVP PRD v1.1 (traceability
matrix in PRD section 10).

# 1. Architecture and roles

- Single authenticated Owner role in v1; workspace_id on all business
  records for future multi-tenancy. Next.js/TypeScript UI,
  FastAPI/Python backend, PostgreSQL/Supabase (auth, database, private
  storage), background queue, transcription provider, FFmpeg and LLM
  provider.

- Async jobs for transcription, rendering and AI tasks; signed
  upload/download URLs; retry policy, job statuses and idempotency keys.

- **revised** **Authorisation:** FastAPI connects with the Supabase
  service role, which bypasses row-level security. Every FastAPI handler
  must therefore check workspace ownership explicitly; RLS remains as a
  second layer for any direct client access.

- **new** **Worker hosting:** FFmpeg and transcription workers run on a
  container host that supports long-running processes (not serverless
  functions). Host and queue technology are open decisions (see section
  10).

- **new** **AI provenance:** every AI call records model ID, prompt
  template version and input hash on the related ai_jobs row so outputs
  are reproducible and auditable.

## **new** 1.1 Project state machine

A project moves through the states below. Transitions forward require
the listed conditions; the Owner may move a project back to any earlier
state. State changes are logged.

| **State**       | **Entry condition**                                                                                      |
|-----------------|----------------------------------------------------------------------------------------------------------|
| Idea            | Project created with title and topic.                                                                    |
| Scripting       | At least one script version exists.                                                                      |
| Script approved | Owner approves a script version; all scripture references verified (FR-003).                             |
| Recorded        | A source video is uploaded or recorded in-app and passes validation (FR-007, FR-024).                    |
| Subtitled       | Transcript exists and Owner marks subtitles reviewed (FR-008).                                           |
| Ready           | Export rendered and passes platform constraint checks for at least one target platform (FR-009, FR-026). |
| Scheduled       | At least one planned post has a scheduled time (FR-011).                                                 |
| Published       | At least one post is marked published with a live URL (FR-012).                                          |
| Measured        | At least one metric snapshot imported for a published post (FR-013).                                     |

# 2. Functional requirements — creation

## FR-001 Account access

Given unauthenticated access, redirect to login; authenticated Owner
sees only own workspace; sessions expire and can be revoked.

## FR-002 Projects **revised**

Create/edit/archive project with title, topic, audience, scripture,
target duration, workflow state (section 1.1); save drafts and resume.
Project also stores content attribute tags (FR-021). v1.1: data model
now carries audience, target_duration_seconds and
actual_duration_seconds as separate fields.

## FR-003 Biblical references **revised**

Store structured references (book, chapter, verse range) and
translation. Each reference records source (ai \| user), verified_by and
verified_at. AI-proposed references are shown as unverified. A project
cannot enter Script approved while any reference is unverified. The
system never generates verse text itself (see FR-023).

## FR-004 AI outline and script **revised**

Generate structured JSON: hook, biblical context, main teaching,
practical application, closing CTA; show word count and estimated spoken
duration; regenerate selected section only; never overwrite manual edits
without confirmation.

- **Verse-text rule:** the AI may cite scripture only as placeholders,
  e.g. {{John 3:16}}. Prompt and output validation reject quoted verse
  text; placeholders are expanded only by FR-023.

- **Duration estimate:** spoken duration = word count ÷
  words-per-minute. Default 150 wpm, editable in brand profile; after
  five recordings the system suggests a personal rate from actual
  duration ÷ script word count.

- **Inputs:** prompt includes creator voice profile and guardrails
  (FR-020) and target duration.

## FR-005 Script versions **revised**

Persist each accepted edit or generation as a version with timestamp,
source (ai \| manual \| mixed), AI job reference where applicable, and
restore action. One version per project may be marked approved.

## FR-006 Teleprompter **revised**

Display approved script with adjustable font size, speed, mirrored mode
and pause; mobile responsive. v1.1 additions: 3-2-1 countdown, tap
anywhere to pause/resume, adjustable start position, screen kept awake
(Screen Wake Lock API with graceful fallback), and placeholders shown
with expanded verse text. Supports Prompter-only mode (second device)
and Record mode (FR-024).

## FR-020 Creator voice profile and guardrails **new**

Owner maintains a profile with: tone descriptors, 2–5 sample scripts or
transcripts in their own words, preferred phrases, phrases to avoid,
theological tradition and doctrinal guardrails, topics to avoid or
handle with care, preferred translation and UK/US English. The profile
is injected into every script, hook and caption prompt. Edits are
versioned.

## FR-021 Content attribute tags **new**

Each project stores tags used by Growth Lab grouping: topic tag (from an
Owner-managed controlled list), hook type (question \| bold claim \|
story \| scripture-first \| other), length bucket (auto from duration:
\<45s, 45–90s, 90–180s), CTA type (follow \| comment \| share \| save \|
other) and format (teaching \| devotional \| testimony \| Q&A).
Post-level tag: posting slot (auto from scheduled time: morning \|
midday \| evening). Tags are required before a project can enter Ready.

## FR-022 Hook variants **new**

Generate 2–3 hook variants per project, each labelled with its hook
type. Owner selects one as used; selection is stored and drives the hook
type tag (FR-021). Unused variants are retained for future experiments.

## FR-023 Verse text insertion **new**

Placeholders are expanded to verse text only from an allowlisted
translation source: (a) a public-domain translation held locally (e.g.
World English Bible), (b) a licensed Bible text service, subject to its
terms, or (c) text pasted by the Owner, labelled as Owner-supplied. Each
translation in the allowlist records licence notes and any quotation
limits. Expanded text is shown with translation abbreviation. Note: in
the UK the KJV is under Crown copyright, so it is not treated as public
domain by default.

## FR-024 In-app recording **new**

Record mode uses the device front camera via browser media APIs with the
teleprompter overlaid near the lens. Supports retake, review and keep;
kept takes upload via FR-007 as the project source video. Records at
1080x1920 where the device allows. If camera access is unsupported or
denied, the UI offers Prompter-only mode and upload. (Scope decision
D-01 in section 10.)

# 3. Functional requirements — media and publishing

## FR-007 Upload **revised**

Accept MP4/MOV within configurable limits (defaults: ≤500 MB, ≤5
minutes); validate MIME, extension and container content; private
storage; progress, failure and retry. Uploads are resumable so a dropped
mobile connection does not restart the file. Ingest normalises HEVC to
H.264, applies rotation metadata and converts variable to constant frame
rate.

## FR-008 Transcription **revised**

Async transcription with timecoded segments; allow correction of text
and of segment start/end timing; persist edits. Language default English
(UK). A custom vocabulary of biblical names and terms (seeded list plus
Owner additions) is passed to the provider where supported. Owner marks
subtitles reviewed to advance state.

## FR-009 Subtitle export **revised**

Render 1080x1920 H.264 MP4 with burn-in subtitles; preserve original
source; handle failures and return downloadable asset. v1.1 additions:

- Subtitle style from brand profile: font, size, colour, background box;
  default maximum 32 characters per line and 2 lines per caption.

- Captions kept inside a safe zone that avoids platform UI overlays
  (default: clear of the bottom 20% and right 12% of the frame;
  configurable).

- Non-9:16 sources: Owner chooses centre-crop or blurred-background pad
  before render.

- Audio loudness normalised to approximately −14 LUFS integrated.

- SRT file export available alongside, or instead of, burn-in (SRT ships
  first; see sprint plan).

## FR-010 Repurpose **revised**

Generate separately editable captions, hashtags and CTAs for Instagram,
TikTok, Facebook and X from the approved script and voice profile;
enforce configured character and hashtag limits per platform; show
remaining characters live.

## FR-011 Calendar **revised**

Create platform-specific planned post with schedule time stored in UTC
plus the Owner's IANA timezone (default Europe/London), status
draft/ready/published; attach exported media and URL; no automated
posting in v1. The calendar displays local time correctly across BST/GMT
changes.

## FR-012 Publication evidence **revised**

Owner may mark published, record publication time and link to live post;
allow reversal and corrections. The system parses the external post ID
from the URL where the platform URL pattern allows, so CSV metrics can
be matched (FR-013).

## FR-025 Home dashboard **new**

Landing screen shows: next action per active project (from the state
machine), pipeline count by state, weekly posting adherence (published ÷
scheduled for the current and previous week), reach and follower trend
sparklines, and active experiments.

## FR-026 Platform video constraints **new**

Before an export is attached to a planned post, validate duration,
aspect ratio and file size against per-platform configuration. Failing
checks block the attachment with a clear message (e.g. 'X allows 2:20 on
non-Premium accounts; this video is 2:58'). Owner may set an account
flag (e.g. X Premium) that changes limits. Defaults are seeded config
and must be verified against platform documentation before launch:

| **Platform**      | **Caption limit (default)**  | **Video length check (default)**         |
|-------------------|------------------------------|------------------------------------------|
| Instagram (Reels) | 2,200 characters             | ≤ 3 min                                  |
| TikTok            | 4,000 characters             | ≤ 10 min                                 |
| Facebook (Reels)  | Configurable                 | Configurable; verify current Reels limit |
| X                 | 280 characters (non-Premium) | ≤ 2 min 20 s (non-Premium)               |

## FR-027 Publishing reminders **new**

At each planned post's scheduled time (and optionally 30 minutes
before), send an email or web push reminder containing the caption, a
download link for the export and a 'Mark published' action. Reminders
stop once the post is marked published.

# 4. Functional requirements — Growth Lab

## FR-013 Metrics intake **revised**

Manual form and CSV import for platform, post, captured_at, reach,
impressions, views, likes, comments, shares, saves, average watch
seconds, completion %, profile visits and follower snapshots. Optional
fields permitted; missing ≠ zero.

- **Snapshot model:** imported values are treated as cumulative lifetime
  totals as of captured_at, never as daily increments. The system
  derives days_since_publish for each snapshot.

- **Column mapping:** one saved mapping template per platform export
  format; unmapped columns are ignored and listed in the preview.

- **Post matching:** rows match social_posts by external_post_id, then
  by external URL; unmatched rows can be linked manually or imported as
  historical posts (FR-028).

## FR-014 Validation **revised**

Reject negative counts, malformed dates and out-of-range percentages;
detect duplicates by platform + external post ID + captured_at date;
provide row-level error report and preview before commit. Duplicate
policy: the preview shows old versus new values and the Owner chooses
update or skip per batch. A snapshot whose cumulative values fall below
an earlier snapshot for the same post is flagged for review.

## FR-015 Metrics calculations **revised**

All post-level comparisons use values at a standard post age: the
snapshot nearest to day 7 (window day 6–8) by default, configurable to
day 3 or day 28. Posts without a snapshot in the window are excluded and
counted in data coverage. Never sum reach across platforms as unique
people, and never rank platforms against each other on formulas whose
inputs differ.

| **Metric**                      | **Formula**                                                          | **Notes**                                                                                                 |
|---------------------------------|----------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------|
| Reach per post                  | Median of day-7 reach across eligible posts                          | Eligible = published, platform match, has day-7 snapshot. Mean shown as secondary only.                   |
| Engagement per reach            | (likes + comments + shares + saves) ÷ reach                          | Computed only with the inputs that platform provides; formula shown per platform (e.g. X excludes saves). |
| Share rate                      | shares ÷ reach                                                       | Requires shares and reach.                                                                                |
| Save rate                       | saves ÷ reach                                                        | Not available on platforms without saves; shown as unavailable.                                           |
| Net follower change             | Follower snapshot nearest window end − snapshot nearest window start | Flagged low confidence if either snapshot is more than 2 days from the boundary.                          |
| Followers per 1,000 reached     | Net follower change ÷ total post reach in window × 1,000             | Shown only when both follower snapshots are within 2 days of the boundaries and ≥5 posts in window.       |
| Average watch time / completion | Median of platform-reported values                                   | Platform definitions differ; compared within platform only.                                               |
| Posting adherence               | Posts published ÷ posts scheduled in period                          | Used by FR-025 and PRD success metrics.                                                                   |

## FR-016 Growth dashboard **revised**

Show platform filter, 7/28/90 day ranges (28 default), current versus
preceding equal-length period, trend, denominator, data coverage and
missing metric flags. The 7-day range carries a persistent low-sample
label.

## FR-017 Recommendations **revised**

Rule-based insights initially: topic share-rate differences, hook type
comparisons, posts with high saves, underperforming retention,
consistency gaps. Grouping uses FR-021 tags within one platform. A
recommendation is shown only when each compared group has ≥5 posts
(configurable) and the relative difference is ≥20% (configurable);
otherwise show an insufficient-data message with the count still needed.
Cite underlying posts and metrics. At 3–5 posts per week, first
recommendations are expected after roughly 4–8 weeks.

## FR-018 Experiments **revised**

Create hypothesis, variable (hook/topic/length/CTA/posting slot),
comparison posts, dates, metric and outcome; recommend changing one
primary variable at a time. Show other tags that differ between compared
posts as possible confounders. Owner records outcome (supported / not
supported / inconclusive) with a note.

## FR-019 Weekly review **revised**

Generate an on-demand weekly report with best/worst posts, platform
changes, data gaps, 1–3 suggested experiments and no unsupported claims
of causality. Owner marks the review complete (reviewed_at), which feeds
the 'weekly review completed' success metric. A missing follower
snapshot for the week prompts entry (FR-029).

## FR-028 Historical baseline import **new**

Owner can import posts published before Amplify Studio (no project
required) with platform, URL, publication date, available tags and
metric snapshots. Historical posts feed the baseline period but are
labelled as historical in reports.

## FR-029 Follower snapshot prompts **new**

Each week, prompt the Owner to enter the follower count per platform
(manual form; CSV allowed). Dashboard shows when the last snapshot per
platform was taken.

## FR-030 Data export and deletion **new**

Owner can export all workspace data (JSON/CSV plus media links) and
delete a project, a media asset or the whole workspace. Deletion removes
stored objects and database rows; backups age out within the stated
retention period.

# 5. Data model **revised**

Changes from v1.0 are tagged. Use UUID PKs, foreign keys, unique
constraints, workspace RLS, created_at/updated_at timestamps, indexes on
workspace/date/platform and schema migrations.

| **Table**                                 | **Fields**                                                                                                                                                                                                             | **Change**  |
|-------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|
| users                                     | id, email                                                                                                                                                                                                              |             |
| workspaces                                | id, owner_id, name                                                                                                                                                                                                     |             |
| brand_profiles                            | id, workspace_id, tone, voice_samples_json, phrases_prefer, phrases_avoid, tradition, guardrails_json, avoid_topics, translation, english_variant, wpm, timezone, subtitle_style_json, platform_flags_json, version_no | **revised** |
| projects                                  | id, workspace_id, title, topic, topic_tag_id, audience, status, target_duration_seconds, actual_duration_seconds, hook_type, cta_type, format, length_bucket, approved_script_version_id                               | **revised** |
| topic_tags                                | id, workspace_id, name, archived                                                                                                                                                                                       | **new**     |
| project_state_events                      | id, project_id, from_state, to_state, created_at                                                                                                                                                                       | **new**     |
| scripture_references                      | id, project_id, book, chapter, verse_start, verse_end, reference, translation, source (ai\|user), verified_by, verified_at                                                                                             | **revised** |
| translations                              | id, code, name, source_type (local\|service\|owner), licence_notes, quotation_limit_notes, enabled                                                                                                                     | **new**     |
| hook_variants                             | id, project_id, text, hook_type, selected, ai_job_id                                                                                                                                                                   | **new**     |
| script_versions                           | id, project_id, version_no, sections_json, source (ai\|manual\|mixed), ai_job_id, approved, created_at                                                                                                                 | **revised** |
| media_assets                              | id, project_id, object_key, kind (source\|render\|srt), status, duration_seconds, width, height, metadata_json                                                                                                         | **revised** |
| transcripts                               | id, media_asset_id, segments_json, reviewed_at                                                                                                                                                                         | **revised** |
| custom_vocabulary                         | id, workspace_id, term                                                                                                                                                                                                 | **new**     |
| social_posts                              | id, project_id (nullable), workspace_id, platform, caption, hashtags, cta, media_asset_id, status, scheduled_at (UTC), timezone, posting_slot, published_at, external_post_id, external_url, is_historical             | **revised** |
| metric_snapshots (replaces metrics_daily) | id, social_post_id, platform, captured_at, days_since_publish, reach, impressions, views, likes, comments, shares, saves, watch_seconds_avg, completion_rate, profile_visits, import_batch_id                          | **revised** |
| import_batches                            | id, workspace_id, platform, mapping_template_id, file_name, row_count, error_count, committed_at                                                                                                                       | **new**     |
| mapping_templates                         | id, workspace_id, platform, column_map_json                                                                                                                                                                            | **new**     |
| follower_snapshots                        | id, workspace_id, platform, captured_at, follower_count                                                                                                                                                                |             |
| experiments                               | id, workspace_id, hypothesis, variable, metric, status, outcome, outcome_note                                                                                                                                          | **revised** |
| experiment_posts                          | experiment_id, social_post_id, variant                                                                                                                                                                                 |             |
| weekly_reviews                            | id, workspace_id, week_start, report_json, reviewed_at                                                                                                                                                                 | **new**     |
| reminders                                 | id, social_post_id, channel, send_at, sent_at                                                                                                                                                                          | **new**     |
| ai_jobs                                   | id, workspace_id, type, status, model_id, prompt_version, input_hash, result_json, error_code                                                                                                                          | **revised** |
| audit_logs                                | id, workspace_id, actor_id, action, entity, entity_id, created_at                                                                                                                                                      | **new**     |

# 6. API contracts **revised**

Return typed JSON, consistent errors (400 validation, 401
authentication, 403 forbidden, 404 missing, 409 conflict, 429 rate
limit, 5xx service failure); async requests return 202 with job_id.

| **Method and path**                                                                               | **Purpose**                                           | **Change**  |
|---------------------------------------------------------------------------------------------------|-------------------------------------------------------|-------------|
| POST /api/projects; GET /api/projects; PATCH /api/projects/{id}                                   | Projects CRUD                                         |             |
| POST /api/projects/{id}/transition                                                                | Move project state (validates section 1.1 conditions) | **new**     |
| POST /api/projects/{id}/references; PATCH /api/references/{id}; POST /api/references/{id}/verify  | Scripture references and verification                 | **new**     |
| POST /api/projects/{id}/outline; POST /api/projects/{id}/scripts; PATCH /api/scripts/{id}         | Outline and script                                    |             |
| POST /api/projects/{id}/hooks; PATCH /api/hooks/{id}                                              | Hook variants and selection                           | **new**     |
| POST /api/scripts/{id}/expand-verses                                                              | Expand placeholders from allowlisted translation      | **new**     |
| GET /api/brand-profile; PATCH /api/brand-profile                                                  | Voice profile, guardrails, settings                   | **new**     |
| GET/POST /api/topic-tags; PATCH /api/topic-tags/{id}                                              | Controlled topic list                                 | **new**     |
| POST /api/media/uploads (resumable); POST /api/media/{id}/transcribe; POST /api/media/{id}/render | Media pipeline                                        | **revised** |
| PATCH /api/transcripts/{id}; POST /api/transcripts/{id}/review                                    | Subtitle correction and review                        | **new**     |
| GET /api/jobs/{id}                                                                                | Job status                                            |             |
| POST /api/projects/{id}/repurpose                                                                 | Platform captions                                     |             |
| POST /api/posts; PATCH /api/posts/{id}; POST /api/posts/{id}/publish; GET /api/calendar           | Planned posts and publication evidence                | **revised** |
| POST /api/posts/historical                                                                        | Historical baseline import                            | **new**     |
| POST /api/metrics/import/preview; POST /api/metrics/import/commit; POST /api/metrics/manual       | Metric snapshots                                      |             |
| GET/POST /api/mapping-templates                                                                   | CSV column mappings                                   | **new**     |
| POST /api/follower-snapshots; GET /api/follower-snapshots                                         | Follower counts                                       | **new**     |
| GET /api/analytics/overview; GET /api/analytics/recommendations                                   | Dashboard and insights                                |             |
| POST /api/experiments; GET /api/experiments; PATCH /api/experiments/{id}                          | Experiments and outcomes                              | **revised** |
| GET /api/reports/weekly; POST /api/reports/weekly/{id}/complete                                   | Weekly review                                         | **revised** |
| GET /api/dashboard/home                                                                           | Home dashboard                                        | **new**     |
| POST /api/export; DELETE /api/projects/{id}; DELETE /api/media/{id}; DELETE /api/workspace        | Data export and deletion                              | **new**     |

# 7. Non-functional requirements **revised**

- Security: authentication, explicit workspace ownership checks in every
  API handler, signed media URLs (default 15-minute expiry), server-side
  API secrets, encrypted transport, strict file validation, lightweight
  audit log of state changes, publication, deletion and export. Malware
  scanning deferred to multi-user release.

- Reliability: retry transient background failures, no duplicate exports
  on retries, recover from worker crashes, daily database backups and
  tested restore procedure.

- Performance targets: ordinary UI response p95 under 2 seconds on
  normal broadband; system script generation under 60 seconds for
  typical prompts (supports the PRD user-time goal of a draft within 5
  minutes); long media tasks show progress rather than blocking UI.

- AI cost control: per-day job limit and monthly spend alert, both
  configurable.

- Accessibility: keyboard navigation, sufficient contrast, mobile
  teleprompter controls, editable captions.

- Privacy (UK GDPR): recordings contain the Owner's face and voice.
  Transcription and LLM providers are data processors; confirm data
  processing terms, storage region and that inputs are not used for
  model training. Stated retention policy for media, transcripts and
  backups; user deletion controls (FR-030).

# 8. Acceptance tests **revised**

| **ID**                      | **Scenario**                                                                                                                                                                                                                                                             | **Change**  |
|-----------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|
| AT-01 Creation              | Given a topic and passage, generate a structured script with 2–3 hook variants; select a hook; edit one section; refresh and verify edits remain; restore previous version; version shows source ai/manual.                                                              | **revised** |
| AT-02 Biblical verification | Unverified AI-suggested scripture prevents Script approved; verified references permit transition. Generated script contains placeholders only; any quoted verse text in AI output is rejected; expansion uses an allowlisted translation.                               | **revised** |
| AT-03 Video                 | Upload valid recording (including an iPhone HEVC MOV), transcribe, edit a subtitle's text and timing, render and download playable vertical MP4 with captions inside the safe zone; download SRT.                                                                        | **revised** |
| AT-04 Distribution          | Create distinct platform captions within limits and calendar entries; mark published with a live URL; external post ID parsed; dashboard updates.                                                                                                                        | **revised** |
| AT-05 Analytics             | Import valid CSV via mapping template; reject negative reach; duplicate shows update/skip choice; cumulative snapshots not summed; show missing metrics as unavailable; median day-7 reach and follower delta recalculated accurately against a hand-calculated fixture. | **revised** |
| AT-06 Insight quality       | With fewer than five comparable posts, show insufficient-data warning with count needed; with sufficient data and ≥20% difference, display recommendation and linked evidence; no growth guarantees.                                                                     | **revised** |
| AT-07 Security              | User cannot access another workspace ID or private media object via UI or FastAPI; signed URLs expire.                                                                                                                                                                   | **revised** |
| AT-08 Teleprompter          | On a mobile browser: countdown runs, tap pauses/resumes, speed and font adjust, screen stays awake for 3 minutes, mirrored mode works.                                                                                                                                   | **new**     |
| AT-09 Recording             | Record mode captures a take with prompter overlay, retake works, kept take uploads; denied camera permission falls back to Prompter-only mode.                                                                                                                           | **new**     |
| AT-10 Platform limits       | A 2:58 export cannot be attached to an X post without the Premium flag; a 2,300-character Instagram caption is blocked.                                                                                                                                                  | **new**     |
| AT-11 Timezone              | A post scheduled for 09:00 Europe/London on the day after the October clock change displays and reminds at 09:00 local.                                                                                                                                                  | **new**     |
| AT-12 Reminders             | Reminder sends at scheduled time with download link; marking published stops further reminders.                                                                                                                                                                          | **new**     |
| AT-13 Weekly review         | Report lists best/worst posts, data gaps and 1–3 experiments, contains no causal claims; marking complete sets reviewed_at.                                                                                                                                              | **new**     |
| AT-14 Historical import     | Import 10 pre-existing posts without projects; they appear in baseline period labelled historical.                                                                                                                                                                       | **new**     |
| AT-15 Export and delete     | Export returns all workspace data; deleting a project removes its media objects and rows.                                                                                                                                                                                | **new**     |

# 9. Sprint sequence **revised**

Each week has a must-ship scope and a stretch scope that moves to the
following release if the week runs over. Timing is an estimate, not a
guarantee.

| **Week** | **Must ship**                                                                                                               | **Stretch (cut first)**                                                              |
|----------|-----------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| 1        | Foundation, auth, projects, state machine, brand profile basics, topic tags                                                 | Audit log                                                                            |
| 2        | Script, hook variants, versions, scripture references and verification, placeholder rule, teleprompter (Prompter-only mode) | Verse expansion from licensed service (use local public-domain + Owner-pasted first) |
| 3        | Resumable upload and ingest normalisation, transcription, subtitle editing, SRT export                                      | Burn-in render with styling and safe zones                                           |
| 4        | Captions and hashtags, platform constraint checks, calendar with timezone, publication evidence, reminders                  | In-app Record mode (FR-024), unless D-01 makes it must-ship                          |
| 5        | Growth Lab: manual metrics, follower snapshots, historical import, metric calculations, dashboard, home dashboard           | CSV import with mapping templates                                                    |
| 6        | Recommendations, weekly review, experiment log, QA against AT-01–AT-15, private pilot start                                 | Data export and delete UI (API must exist)                                           |

# 10. Open decisions **new**

| **ID** | **Decision**                                                               | **Proposed default**                                                                      | **Status**     |
|--------|----------------------------------------------------------------------------|-------------------------------------------------------------------------------------------|----------------|
| D-01   | Recording approach: in-app Record mode vs Prompter-only on a second device | Prompter-only P0; Record mode as Week 4 stretch                                           | Open — confirm |
| D-02   | Verse text source                                                          | Local public-domain translation (e.g. WEB) plus Owner-pasted text; licensed service later | Open — confirm |
| D-03   | Transcription provider                                                     | Provider supporting custom vocabulary and UK English, with no training on inputs          | Open           |
| D-04   | LLM provider and model                                                     | Choose provider with no-training data terms; record model ID per job                      | Open           |
| D-05   | Worker host and queue                                                      | Container host for FFmpeg workers; Postgres-backed or Redis queue                         | Open           |
| D-06   | Reminder channel                                                           | Email first; web push if time allows                                                      | Open           |
| D-07   | Platform limits                                                            | Verify FR-026 defaults against current platform documentation before launch               | Open — verify  |
