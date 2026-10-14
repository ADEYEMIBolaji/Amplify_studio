# Amplify Studio — CLAUDE.md

## Project summary
Amplify Studio is a **private, single-creator** web app for a Christian creator who makes 30–180s
talking-to-camera teachings/devotionals for Instagram, TikTok, Facebook and X. It covers the full
lifecycle: idea → scripture verification → hook/script → teleprompter/record → upload/transcribe/export
→ platform captions → calendar/publish (manual) → metrics → evidence-linked insights.

Source of truth: [docs/prd.md](docs/prd.md) and [docs/frd.md](docs/frd.md) (converted from the
`.docx` originals in the repo root via `pandoc`). The FRD is authoritative on behaviour — cite
`FR-xxx` / `AT-xx` IDs in code comments, commit messages and test names. No `docs/design/` handoff
exists yet; until one is added, UI follows Tailwind defaults with a mobile-first layout inferred
from FRD section 6 (Experience and screens).

Single Owner role in v1 (no multi-tenant auth UX), but every table carries `workspace_id` and every
API handler must enforce workspace ownership explicitly, because the backend connects to Supabase
with the **service role**, which bypasses Postgres RLS (FRD section 1, NFR Security, AT-07).

## Stack
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind, mobile-first.
- **Backend:** FastAPI (Python 3.12), Pydantic v2 models, typed JSON responses, consistent error
  codes (400/401/403/404/409/429/5xx), async work returns `202 { job_id }`.
- **Data/auth/storage:** Supabase — Postgres, Auth, private Storage buckets. Schema changes go
  through migrations only. UUID PKs, `created_at`/`updated_at` on every table, RLS by
  `workspace_id` (defense-in-depth even though the backend uses the service role).
- **Background jobs:** Postgres-backed queue (no extra infra for v1) for transcription, FFmpeg
  rendering and AI tasks. Jobs carry idempotency keys, retry counts/policy and a status column.
- **Media:** FFmpeg inside the worker container.
- **AI / transcription:** behind `LLMProvider` / `TranscriptionProvider` interfaces with a `Fake*`
  implementation for local dev and tests. Real providers chosen later per D-03/D-04. All provider
  config via environment variables; never hard-code provider SDK calls outside the provider module.
- **Local dev:** `docker-compose` (Supabase CLI as an alternative) — one command brings up web,
  api, worker, Postgres. `.env.example` kept current.
- **Tests:** pytest (backend), Vitest (frontend unit), Playwright (key e2e flows). Test names
  reference `AT-xx` where applicable.

## Folder structure
```
/
├── docs/
│   ├── prd.md, frd.md              # converted source of truth (do not hand-edit; regenerate via pandoc if source docx changes)
│   ├── plan.md                     # sprint plan, must-ship/stretch, FR/AT mapping
│   └── design/                     # Claude Design handoff — not yet provided
├── apps/
│   ├── web/                        # Next.js App Router app
│   │   ├── app/                    # routes: dashboard, ideas, scripts, record, video, repurpose, calendar, growth-lab, settings
│   │   ├── components/
│   │   ├── lib/                    # api client, types shared with backend contracts
│   │   └── tests/                  # Vitest + Playwright
│   └── api/                        # FastAPI app
│       ├── app/
│       │   ├── routers/            # one module per FRD domain (projects, scripts, media, posts, metrics, ...)
│       │   ├── models/             # Pydantic schemas
│       │   ├── db/                 # SQLAlchemy models / Supabase migrations
│       │   ├── providers/          # LLMProvider, TranscriptionProvider + Fake implementations
│       │   ├── services/           # business logic (state machine, metrics calc, insights rules)
│       │   └── worker/             # queue consumer, FFmpeg jobs, AI jobs
│       └── tests/                  # pytest
├── supabase/
│   └── migrations/                 # SQL migrations, timestamped
├── docker-compose.yml
├── .env.example
└── CLAUDE.md
```
(Structure is created incrementally as each sprint week is built — see [docs/plan.md](docs/plan.md).)

## Commands
_Filled in once scaffolding exists in Week 1. Placeholder targets:_
- Dev: `docker-compose up` (web on :3000, api on :8000)
- Frontend test: `cd apps/web && npm run test` (Vitest), `npm run test:e2e` (Playwright)
- Backend test: `cd apps/api && pytest`
- Lint: `cd apps/web && npm run lint`; `cd apps/api && ruff check .`
- Type check: `cd apps/web && npm run typecheck`; `cd apps/api && mypy app`
- Migrate: `supabase migration up` (or `alembic upgrade head` if SQLAlchemy migrations are used instead — decide in Week 1 and update this line)

## Coding conventions
- UK English throughout the UI (copy, labels, error messages, dates).
- Timestamps: store UTC; always carry/display the Owner's IANA timezone (default `Europe/London`).
  Never do naive local-time arithmetic — use a tz-aware library on both frontend and backend. Test
  across the BST/GMT boundary (AT-11).
- Platform limits (caption length, video duration/aspect/size) live in configuration (DB or config
  table), never as hard-coded constants (FR-026).
- Every FastAPI handler that touches a workspace-scoped resource must explicitly filter/check
  `workspace_id` against the authenticated Owner's workspace — do not rely on RLS alone.
- AI output is validated server-side to reject quoted scripture text; only `{{Book Ch:V}}`-style
  placeholders are accepted from AI. Placeholder expansion only reads from the `translations`
  allowlist (local WEB copy or Owner-pasted text), never an assumed-public-domain text (KJV is
  Crown-copyrighted in the UK — do not treat it as public domain).
- Manual script edits are never silently overwritten by AI regeneration — always version and
  confirm before replacing a manually-edited section (FR-004, FR-005).
- Metrics: see non-negotiable rule 4 below — imported values are cumulative snapshots, compare at
  equal post age, reach is median, missing is `null`/"Unavailable" not `0`, never sum reach across
  platforms.
- No code implementing auto-posting, scraping, or engagement automation — publishing stays manual
  with reminders only.
- Cite `FR-xxx`/`AT-xx` IDs in commit messages, PR-equivalent summaries, and test names for
  anything implementing a specific requirement.

## Non-negotiable rules
1. **Authorisation:** every API handler checks workspace ownership explicitly (service role
   bypasses RLS). A test must prove one workspace can't read another's data or media (AT-07).
2. **Scripture:** AI never writes verse text, only `{{Book Ch:V}}` placeholders; validate and
   reject quoted verse text in AI output. Placeholders expand only from the allowlisted
   translations table (local WEB, or Owner-pasted, labelled as such). KJV ≠ public domain in the
   UK. A project cannot reach "Script approved" while any scripture reference is unverified
   (FR-003, FR-023).
3. **Manual edits are sacred:** never overwrite a manually edited script section without explicit
   Owner confirmation. Version every accepted change with provenance (`ai`/`manual`/`mixed`)
   (FR-004, FR-005).
4. **Metrics correctness** (FR-013–FR-015): imported values are cumulative snapshots as of a
   capture date — never summed as daily figures. Compare posts at equal age (default: snapshot
   nearest day 7, window day 6–8). Reach per post is the **median**. Missing values are `null`,
   never `0`, shown as "Unavailable". Never sum reach across platforms or rank platforms on
   formulas with different inputs. Unit-test against a hand-calculated fixture.
5. **Honest insights:** recommendations require ≥5 posts per group (configurable) and ≥20%
   difference (configurable), and must link to evidence. Never claim causality or promise growth
   (FR-017, FR-019).
6. **No automation against platform rules:** no auto-posting, scraping or engagement automation in
   v1. Publishing is manual with reminders.
7. **Time:** UTC + IANA timezone (default `Europe/London`) on every scheduled/timestamped record.
   Test across the BST/GMT clock change (AT-11).
8. **Privacy:** media private, served only via signed URLs (default 15-minute expiry). Secrets
   server-side only. Provide data export and deletion (FR-030). UK English throughout.
9. **Platform limits** are configuration, not hard-coded constants (FR-026).

## Open decisions and their current defaults
(From PRD section 9 / FRD section 10 — change only on explicit instruction.)
- **D-01** Recording: Prompter-only is must-ship (Week 2); in-app Record mode is a Week 4 stretch.
- **D-02** Verse text: local WEB copy + Owner-pasted text only; no licensed service yet.
- **D-03** Transcription provider: not yet chosen — build behind `TranscriptionProvider` interface
  with a fake for dev/test.
- **D-04** LLM provider: not yet chosen — build behind `LLMProvider` interface with a fake for
  dev/test.
- **D-05** Worker host/queue: container host + Postgres-backed queue to start (no Redis yet).
- **D-06** Reminders: email first (provider interface), console-logged in development.
- **D-07** Platform limits: seeded defaults per FRD FR-026 table; must be verified against current
  platform docs before launch — treat as config, not fact.
- Ship SRT export before styled burn-in rendering (Week 3). CSV import with column mapping is a
  Week 5 stretch, after manual metric entry works.

## Status
Project not yet scaffolded. See [docs/plan.md](docs/plan.md) for the sprint plan — awaiting
approval before any application code is written.
