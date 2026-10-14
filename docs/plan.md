# Amplify Studio — build plan

Mapped to FRD section 9 (Sprint sequence) and PRD section 10 (Traceability matrix). Each week
lists must-ship and stretch scope, with the FR/AT IDs it covers. Stretch items are the first to
move to the next release if a week overruns (per FRD section 9 note and the Working Agreement
rule 5: flag risk early, don't quietly cut scope).

No application code is written until this plan is approved.

---

## Week 1 — Foundation, auth, projects, state machine — ✅ done (2026-10-14)

Delivered: Next.js/FastAPI scaffolding, full schema migration (see CLAUDE.md "Schema note"),
Supabase auth wiring (login page, session-refresh proxy, per-user workspace provisioning),
project CRUD + archive, the full forward/backward state machine with real precondition checks
against later-week tables, topic tags, brand profile basics, and workspace-ownership checks on
every handler (tested — AT-07 partial). 19 backend tests (pytest) + 3 frontend tests (Vitest) all
pass; `ruff`, `mypy`, `eslint`, `tsc --noEmit`, and `next build` all pass clean.

Stubbed/deferred: audit log has no viewer UI (writes happen, nothing surfaces them yet — this was
always this week's stretch item); `docker-compose.yml` is written but untested (no Docker in this
build environment — verify once Docker is available); no Supabase project is linked yet, so the
backend runs against local SQLite and the frontend auth flow is wired but unverified against a
real Supabase instance; home dashboard shows only a pipeline-by-state placeholder (full FR-025
version is Week 5); Playwright is configured but has no e2e spec yet (first one comes with Week 2
once there's a full idea→script flow worth covering end to end).

**Decisions made (flagging, not asking):** Supabase CLI SQL migrations + SQLAlchemy Core (no ORM
migration generation) — matches the plan's open item. Full data-model schema created in Week 1
rather than growing it per-week, since FRD section 5 already specifies it completely and it lets
the state machine's later-state conditions be real checks instead of stubs.

**Needs you:** (1) a Supabase project — create one and share the URL/keys so Week 2 can run
against real auth/DB instead of local SQLite; (2) confirm the `docs/design/` handoff is coming, or
confirm Tailwind-default styling is fine through the pilot.

**Must ship**
- Repo scaffolding: `apps/web` (Next.js/TS/Tailwind), `apps/api` (FastAPI/Python 3.12),
  `supabase/migrations`, `docker-compose.yml`, `.env.example`.
- Supabase project wiring: Auth (single Owner account), Postgres, private Storage bucket.
  Migrations for `users`, `workspaces`, `brand_profiles` (basic fields only), `projects`,
  `topic_tags`, `project_state_events`, `audit_logs`.
- Auth flow: unauthenticated → redirect to login; authenticated Owner sees only their workspace;
  session expiry/revocation. — **FR-001**
- Projects CRUD (create/edit/archive; title, topic, audience, scripture ref placeholder,
  target_duration_seconds, actual_duration_seconds) with draft save/resume. — **FR-002**
- Project state machine (Idea → Scripting → Script approved → Recorded → Subtitled → Ready →
  Scheduled → Published → Measured) as a backend service + `project_state_events` log; forward
  transitions validate entry conditions, Owner can move back to any earlier state. —
  **FR-002, state machine (FRD 1.1)**
- Brand profile basics: tone, preferred translation, UK/US English, wpm (default 150), timezone
  (default Europe/London). Full guardrails/voice-sample fields land Week 2 alongside FR-020 use.
- Topic tags: Owner-managed controlled list, CRUD. — **FR-021** (partial — tag storage only;
  hook/length/CTA/format tags land with scripting in Week 2)
- Workspace-ownership check middleware/dependency in every FastAPI handler from day one (not
  bolted on later) — this is the pattern every later router must follow.
- Test: one workspace cannot read another workspace's project via API. — **AT-07** (partial;
  extended as media/other resources are added in later weeks)

**Stretch (cut first)**
- Audit log UI/consumption (the `audit_logs` table and writes exist, but no viewer screen).

**Decisions needed before/during this week**
- Confirm migration tooling: Supabase CLI migrations vs. SQLAlchemy/Alembic. Default: Supabase CLI
  SQL migrations, consumed by FastAPI via SQLAlchemy core (no ORM-driven schema). State in
  CLAUDE.md once decided.

---

## Week 2 — Script, hooks, scripture, teleprompter (Prompter-only) — ✅ done (2026-10-14)

Delivered: everything in "Must ship" below shipped. `LLMProvider`/`FakeLLMProvider` interface;
AI outline generation producing the 5-part structured script with per-section provenance
(`ai`/`manual`, rolled up to the version's `ai`/`manual`/`mixed`); manual edits always create a
new version rather than mutating one in place; section regeneration blocked with
`manual_edit_would_be_overwritten` (409) unless `confirm: true`; hook variants (2-3, labelled,
selectable, unused ones retained); scripture references auto-synced from `{{Book Ch:V}}`
placeholders found in generated text, with verify/unverify-on-edit and an Owner-paste path;
`validate_no_quoted_verse_text` rejects AI output that quotes a known verse verbatim; verse
expansion from the local WEB sample or Owner-pasted text, "Unavailable" otherwise; Script Studio
UI (hooks, section editor with save/regenerate, version history/restore, approve, reference
verification); full-screen teleprompter (font size, speed, mirror, 3-2-1 countdown, tap
pause/resume, Screen Wake Lock with an on-screen fallback notice, auto-scroll); voice-profile
Settings page. 14 new backend tests (30 total) + 2 new frontend test files (3 files, 5 tests
total, one covering the new Settings page) all pass; `ruff`, `mypy`, `eslint`, `tsc --noEmit`,
`next build` all pass clean; first Playwright e2e spec added and run against a live `next dev`
server.

**Known limitation (flagging, not hiding):** the local WEB verse corpus
(`apps/api/app/providers/data/web_sample.json`) seeds only ~10 commonly-cited verses, not the full
Bible. `expand-verses` correctly reports any reference outside that set as "Unavailable" and the
UI offers the Owner-paste fallback — the mechanism is real and tested (see
`test_expand_verses_reports_unavailable_outside_local_sample`), but coverage is deliberately small
for Week 2. Expanding it is pure data entry (add entries to that JSON file) whenever you want
broader coverage — let me know if you'd like that prioritised before Week 3, or want a path to a
full local WEB text file instead.

**Not done (scope note, not a cut):** FR-021's "tags required before Ready" gate isn't wired into
the state machine yet. Nothing can reach Ready until Week 3-4 ship rendering/platform checks, so
there was nothing to gate yet — this is picked up when the Ready transition becomes reachable.

**Must ship**
- Creator voice profile completion: tone descriptors, 2–5 sample scripts, preferred/avoid phrases,
  theological tradition, doctrinal guardrails, topics to avoid, versioned edits. — **FR-020**
- `LLMProvider` interface + `FakeLLMProvider` for dev/test. Real provider deferred (D-04).
- AI outline/script generation: structured JSON (hook, biblical context, main teaching, practical
  application, closing CTA); word count + estimated spoken duration (`word_count ÷ wpm`);
  regenerate a single section; **never** overwrite manual edits without explicit confirmation. —
  **FR-004**
- Verse-text placeholder rule enforced server-side: AI output validated to reject any quoted verse
  text, only `{{Book Ch:V}}` accepted. — **FR-004 (verse-text rule), FR-023 (allowlist model)**
- `translations` table seeded with local WEB text; Owner-paste path for verse expansion; expansion
  endpoint `POST /api/scripts/{id}/expand-verses`. Licensed Bible service **not** built (stretch,
  below). — **FR-023**
- Scripture references: structured storage (book/chapter/verse range/translation), `source`
  (ai|user), `verified_by`/`verified_at`; Script approved transition blocked while any reference
  unverified. — **FR-003**
- Script versions: persisted per accepted edit/generation with source (ai|manual|mixed), AI job
  reference, restore action, one version markable approved. — **FR-005**
- Hook variants: generate 2–3 per project, labelled by hook type; Owner selects one as used;
  unused variants retained. Selection drives the hook-type content tag. — **FR-022, FR-021**
  (hook_type/length_bucket/cta_type/format tags completed here, required before Ready state)
- `ai_jobs` provenance: model ID, prompt template version, input hash recorded per call.
- Teleprompter, Prompter-only mode: adjustable font size/speed, mirrored mode, pause, 3-2-1
  countdown, tap-to-pause/resume, adjustable start position, Screen Wake Lock API with fallback,
  placeholders rendered as expanded verse text. — **FR-006**
- Tests: script create/edit/version/restore round-trip; placeholder rejection on quoted verse
  text; unverified reference blocks Script approved; teleprompter behaviour on a mobile browser
  (countdown, pause, 3-minute wake lock, mirrored mode). — **AT-01, AT-02, AT-08**

**Stretch (cut first)**
- Verse expansion from a licensed Bible text service (D-02) — ship local WEB + Owner-paste first.

---

## Week 3 — Upload, transcription, subtitles, SRT export — ✅ done (2026-10-14)

Delivered: chunked resumable upload (`media_upload_sessions`) — a dropped connection loses at most
the in-flight chunk, resumed by probing which chunk indices already landed; MIME/extension/size
validation; `StorageProvider` abstraction with a filesystem-backed `LocalStorageProvider` giving
real HMAC-signed, time-limited download URLs (simulating Supabase Storage's signed-URL property
until a project exists); `VideoProcessor` abstraction (`normalize`/`render_captions`) with a real
FFmpeg-shelling implementation plus a `FakeVideoProcessor` fallback; `TranscriptionProvider` +
`FakeTranscriptionProvider`; a `media_jobs` table (same pattern as `ai_jobs`) giving every
normalize/transcribe/render a status, retry count and idempotency key, processed inline for
instant pilot-scale UX with a worker poll loop (`app/worker/main.py`) as crash-recovery backstop;
subtitle text/timing correction that persists; "mark reviewed" wired into the state machine's
Subtitled condition (built in Week 1, exercised for the first time here); SRT export; seeded
biblical-name vocabulary + Owner additions; a Video Studio page (upload progress, transcribe,
subtitle editor, SRT download). 13 new backend tests (43 total) all passing; `ruff`, `mypy`,
`eslint`, `tsc`, `next build` all pass clean.

**Known limitation (flagging, not hiding):** this dev machine has no `ffmpeg`/`ffprobe` binary, so
every upload runs through `FakeVideoProcessor` — it copies the file through unchanged and marks
the result `metadata_json.degraded: true` rather than claiming real HEVC→H.264/CFR normalisation
happened. The real `FfmpegVideoProcessor` is written and will run as soon as `VIDEO_PROCESSOR=ffmpeg`
is set somewhere `ffmpeg`/`ffprobe` are actually on PATH (the worker container, per CLAUDE.md) —
it just hasn't been exercised against a real video file yet. Test before relying on it for a real
upload.

**Stretch not attempted this week:** burn-in rendering (styled captions, safe zones, loudness
normalisation) — `VideoProcessor.render_captions` exists but has no router wired to it yet. This
was always the first thing to cut if the week was tight (per the plan's own stretch-cut order),
and SRT-only export is sufficient to keep moving; happy to prioritise it ahead of Week 4 if you'd
rather have it sooner.

**Must ship**
- Resumable upload endpoint; MP4/MOV accepted within configurable limits (default ≤500MB, ≤5min);
  MIME/extension/container validation; private storage; progress/failure/retry; HEVC→H.264
  normalisation, rotation metadata applied, VFR→CFR conversion. — **FR-007**
- `TranscriptionProvider` interface + `FakeTranscriptionProvider` for dev/test. Real provider
  deferred (D-03).
- Async transcription with timecoded segments; text and segment start/end correction persisted;
  default language English (UK); custom vocabulary (seeded biblical names/terms + Owner additions)
  passed to provider where supported; "subtitles reviewed" advances state. — **FR-008**
- Custom vocabulary storage/management (seed list + Owner additions). — supports FR-008
- SRT export (ships before burn-in per FRD section 9/PRD D-07 default). — **FR-009** (SRT path)
- Media pipeline API: resumable upload, transcribe job, render job, `GET /api/jobs/{id}` status.
- Tests: upload an HEVC MOV, transcribe, edit a subtitle's text and timing, download SRT; retry on
  dropped connection resumes rather than restarting. — **AT-03** (partial — burn-in/safe-zone
  checks land Week 4 stretch)

**Stretch (cut first)**
- Burn-in render with styling (font/size/colour/background box), safe zones (clear of bottom
  20%/right 12%, configurable), centre-crop/blurred-pad for non-9:16 sources, loudness
  normalisation to ≈−14 LUFS integrated. — **FR-009** (burn-in path). If time allows, this
  completes AT-03's render/safe-zone assertion; otherwise it moves to the next release and AT-03
  is accepted against SRT-only for the pilot.

---

## Week 4 — Captions, platform checks, calendar, publishing evidence, reminders

**Must ship**
- Repurpose: platform captions/hashtags/CTAs for Instagram, TikTok, Facebook, X, generated from
  approved script + voice profile; each separately editable; live remaining-character counts;
  limits enforced from configuration (not constants). — **FR-010**
- Platform constraint config table + validation: duration/aspect/file-size checks before export
  attaches to a planned post; blocking message with specifics; Owner-settable account flags (e.g.
  X Premium) that change limits; defaults per FR-026 table, flagged as "verify before launch". —
  **FR-026**
- Calendar: platform-specific planned posts, `scheduled_at` stored UTC + Owner IANA timezone
  (default Europe/London), status draft/ready/published, attached export + external URL, no
  automated posting. Correct local-time display across BST/GMT. — **FR-011**
- Publication evidence: mark published, record publish time, link to live post, allow
  reversal/correction; external post ID parsed from URL where pattern allows. — **FR-012**
- Publishing reminders: email provider interface (console-logged in dev per D-06), fires at
  scheduled time (and optionally T-30min) with caption, export download link, "Mark published"
  action; stops once published. — **FR-027**
- Tests: distinct per-platform captions within limits + calendar entries + mark-published with URL
  parsing (**AT-04**); 2:58s export blocked from X without Premium flag, 2,300-char IG caption
  blocked (**AT-10**); 09:00 Europe/London post around the October clock change displays/reminds
  at 09:00 local (**AT-11**); reminder sends with download link and stops after publish
  (**AT-12**).

**Stretch (cut first)**
- In-app Record mode (front camera via browser media APIs, prompter overlay, retake/review/keep,
  1080×1920 capture, graceful fallback to Prompter-only on denied/unsupported camera access). —
  **FR-024**, test **AT-09**. Ships only if D-01 is confirmed as must-ship; otherwise moves to next
  release.

---

## Week 5 — Growth Lab: metrics, baseline, dashboards

**Must ship**
- Manual metrics entry form (platform, post, captured_at, reach, impressions, views, likes,
  comments, shares, saves, watch_seconds_avg, completion_rate, profile_visits); missing fields
  stored as `null`, never `0`. — **FR-013** (manual path)
- Snapshot model: cumulative-as-of-`captured_at` semantics; `days_since_publish` derived per
  snapshot; post matching by `external_post_id` then URL; unmatched rows linkable manually or as
  historical.
- Validation: reject negative counts/malformed dates/out-of-range percentages; duplicate detection
  by platform+external_post_id+captured_at date with update/skip choice and old-vs-new preview;
  flag snapshots whose cumulative values fall below an earlier snapshot. — **FR-014**
- Follower snapshots: weekly prompt per platform, manual form, dashboard shows last-captured date
  per platform. — **FR-029**
- Historical baseline import: pre-existing posts (no project required) with platform, URL,
  publication date, tags, metric snapshots; labelled historical in reports. — **FR-028**
- Metrics calculations service, built against a hand-calculated fixture: median day-7 reach
  (window day 6–8, configurable to day 3/28); engagement/share/save rate per available platform
  inputs; net follower change with low-confidence flag outside ±2 days of window boundary;
  followers-per-1,000-reached only when both snapshots within 2 days of boundary and ≥5 posts;
  posting adherence. Never sum reach across platforms; never rank platforms on mismatched-input
  formulas. — **FR-015**
- Growth dashboard: platform filter, 7/28/90-day ranges (28 default), current vs. preceding
  equal-length period, trend, denominator, data coverage, missing-metric flags, persistent
  low-sample label on 7-day range. — **FR-016**
- Home dashboard: next action per project (from state machine), pipeline count by state, weekly
  posting adherence (current + previous week), reach/follower trend sparklines, active
  experiments. — **FR-025**
- Tests: hand-calculated fixture validates median reach, follower delta, and the "never sum
  cumulative as daily" rule (**AT-05**); 10 historical posts import into baseline, labelled
  historical (**AT-14**).

**Stretch (cut first)**
- CSV import with per-platform column mapping, saved mapping templates, unmapped-column preview
  listing. — **FR-013** (CSV path), supports **AT-05**'s CSV-specific assertion. Manual entry
  covers AT-05's calculation-correctness assertions even if this slips.

---

## Week 6 — Recommendations, weekly review, experiments, QA, pilot start

**Must ship**
- Rule-based recommendations: topic share-rate differences, hook-type comparisons, high-saves
  posts, underperforming retention, consistency gaps; grouping via FR-021 tags within one
  platform; shown only when each group has ≥5 posts (configurable) and relative difference ≥20%
  (configurable), else insufficient-data message with count still needed; every recommendation
  cites underlying posts/metrics. — **FR-017**
- Experiments: hypothesis, variable (hook/topic/length/CTA/posting slot), comparison posts, dates,
  metric, outcome; change-one-variable guidance; other differing tags surfaced as possible
  confounders; Owner records outcome (supported/not supported/inconclusive) + note. — **FR-018**
- Weekly review: on-demand report (best/worst posts, platform changes, data gaps, 1–3 suggested
  experiments, no causal-claim language); Owner marks complete (`reviewed_at`); missing follower
  snapshot prompts entry. — **FR-019**
- Data export and deletion API (**must exist** even if UI is stretch, per FRD section 9): export
  all workspace data (JSON/CSV + media links); delete project/media asset/whole workspace,
  removing stored objects, DB rows, and ageing out of backups within stated retention. — **FR-030**
- Full QA pass against **AT-01 through AT-15**; fix regressions found.
- Security re-check: workspace-isolation test extended to cover every resource type added since
  Week 1 (projects, media, posts, metrics, exports). — **AT-07**
- Private pilot start: import previous 28 days as baseline (via Week 5's historical import), begin
  creating/publishing real posts per PRD section 8.
- Tests: insufficient-data warning below 5 posts, recommendation + evidence link at ≥20% with
  sufficient data, no growth-guarantee language (**AT-06**); weekly review contents and
  `reviewed_at` (**AT-13**); export returns all workspace data, delete removes media/rows
  (**AT-15**).

**Stretch (cut first)**
- Data export/deletion **UI** (API must already exist as must-ship above) — console/admin-only
  trigger is acceptable for pilot if the UI slips.

---

## Running risk list
- D-01 (recording approach), D-03 (transcription provider), D-04 (LLM provider), D-05 (worker
  host/queue) are open. Provider interfaces mean D-03/D-04 don't block any week's must-ship scope —
  fakes stand in until chosen. D-05 affects Week 1 infra setup; default is a container host +
  Postgres-backed queue, revisit only if volume/latency needs force a rethink.
- D-07 (platform limits) defaults are seeded from the FRD table but are explicitly unverified
  against live platform documentation — flagged as a pre-launch task, not a Week 4 blocker.
- `docs/design/` has no handoff yet. UI ships to Tailwind defaults + FRD section 6 screen
  descriptions until a handoff arrives; if one lands mid-build, affected screens get a follow-up
  pass rather than blocking the week they land in.
- Burn-in rendering (Week 3) and in-app Record mode (Week 4) are the two must-ship-adjacent
  features already flagged as likely-to-slip stretch in the FRD itself — tracked, not a new risk.

## Traceability summary
All FR-001–FR-030 and AT-01–AT-15 are covered above; see PRD section 10 for the capability-level
cross-reference (C-01…C-18) if a capability-first view is needed instead of the week-first view
here.
