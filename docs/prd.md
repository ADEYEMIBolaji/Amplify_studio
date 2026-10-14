Version 1.1 \| 14 October 2026 \| Owner: Bee \| Status: Revised
build-ready draft

# 0. Document control

| **Version** | **Date**    | **Summary**                                                                                                                                                                                                                                                                                                                                                                            |
|-------------|-------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1.0         | 14 Oct 2026 | Build-ready draft.                                                                                                                                                                                                                                                                                                                                                                     |
| 1.1         | 14 Oct 2026 | Aligned with FRD v1.1: recording approach defined; hook variants, voice profile and guardrails specified; verse-text licensing rule; content tags for Growth Lab; median reach and defined metric formulas; historical baseline; publishing reminders; platform video limits; home dashboard; realistic insight timeline; scope cut line; decisions log and traceability matrix added. |

Tags: **new** added in v1.1; **revised** changed in v1.1. Companion
document: Amplify Studio MVP FRD v1.1.

# 1. Executive summary

- Amplify Studio is a private, single-creator web application for
  planning, scripting, recording, preparing, publishing and learning
  from Christian talking-to-camera teachings and devotionals. Growth
  intelligence is a core product capability, not an optional analytics
  add-on.

- **revised** Primary workflow: topic → scripture review and
  verification → hook variants and script → teleprompter and record
  (in-app or second device) → upload/subtitles → platform-specific copy
  → export/manual publish with reminders → metrics → next experiment.

# 2. Problem, user and jobs to be done

- Primary user: Christian creator making 30–180 second talking-to-camera
  teachings and devotionals, publishing to Instagram, TikTok, Facebook
  and X.

- Jobs: reduce scripting and production time; preserve biblical accuracy
  and authentic voice; publish consistently; identify content patterns
  associated with reach, retention, shares and follower growth.

- **revised** Initial scope: private one-user product, responsive
  desktop/mobile, UK English by default. Future: church media teams and
  other creators.

- **new** Context: the creator often records on the same phone they
  script on, so the prompter and recording experience must work on a
  single mobile device or clearly support a second device.

# 3. Goals and non-goals

- **revised** Goals: draft a script within 5 minutes of user time;
  support 3–5 posts/week; provide a single project record from idea to
  post; establish platform-specific reach/follower baselines (including
  pre-launch history) and produce weekly evidence-linked recommendations
  once enough data exists.

- Non-goals: guaranteed follower gains, engagement bots, fake followers,
  mass unsolicited messaging, autonomous ad spend, universal platform
  direct publishing, multi-tenant billing, full video editing suite.

# 4. MVP capabilities and priorities **revised**

Capabilities are numbered for traceability (section 10). Items marked
stretch are inside P0 intent but are the first to move to the next
release if the six-week plan runs over.

| **ID** | **Capability**                                                                                                                                                                                     | **Priority**               |
|--------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------|
| C-01   | Topic intake with content tags (topic, hook type, length, CTA, format) **revised**                                                                                                                 | P0                         |
| C-02   | Scripture references with verification checklist; AI cites placeholders only; verse text only from licensed or public-domain sources **revised**                                                   | P0                         |
| C-03   | Structured five-part script with 2–3 hook variants, editable sections, versions with AI/manual provenance **revised**                                                                              | P0                         |
| C-04   | Creator voice profile with theological tradition, guardrails and topics to avoid **revised**                                                                                                       | P0                         |
| C-05   | Teleprompter: Prompter-only mode (second device) with countdown, pause and screen-awake **revised**                                                                                                | P0                         |
| C-06   | In-app Record mode with prompter overlay **new**                                                                                                                                                   | P0 stretch (decision D-01) |
| C-07   | Resumable video upload with iPhone format handling **revised**                                                                                                                                     | P0                         |
| C-08   | Transcription with biblical-name vocabulary; editable subtitle text and timing **revised**                                                                                                         | P0                         |
| C-09   | 9:16 export: SRT first; styled burn-in with safe zones and loudness normalisation **revised**                                                                                                      | P0 (burn-in stretch)       |
| C-10   | Instagram/TikTok/Facebook/X captions, hashtags and CTAs with character limits **revised**                                                                                                          | P0                         |
| C-11   | Platform video-length and format checks (e.g. X 2:20 non-Premium) **new**                                                                                                                          | P0                         |
| C-12   | Content calendar with timezone, manual publishing status, external URL and publishing reminders **revised**                                                                                        | P0                         |
| C-13   | Home dashboard: next action, pipeline, posting adherence, trends **new**                                                                                                                           | P0                         |
| C-14   | Manual metric entry and follower snapshots; historical baseline import **revised**                                                                                                                 | P0                         |
| C-15   | CSV import with per-platform column mapping and validation **revised**                                                                                                                             | P0 stretch                 |
| C-16   | Per-platform dashboard with 28-day vs prior period, metrics compared at equal post age, median reach **revised**                                                                                   | P0                         |
| C-17   | Weekly evidence-linked recommendations and review; experiment log **revised**                                                                                                                      | P0                         |
| C-18   | Data export and deletion **new**                                                                                                                                                                   | P0                         |
| P1     | Approved platform API connections, scheduled publishing where authorised, richer retention metrics, clip suggestions, thumbnail testing, licensed Bible text service integration, malware scanning | P1                         |
| P2     | Team workflows, churches, subscription billing, paid ad campaign automation                                                                                                                        | P2                         |

# 5. Success metrics and measurement **revised**

| **Metric**                  | **Definition**                                                                            | **Target / use**                                                        |
|-----------------------------|-------------------------------------------------------------------------------------------|-------------------------------------------------------------------------|
| Posting adherence           | Posts marked published ÷ posts scheduled, per week                                        | ≥80%                                                                    |
| Script draft time           | User time from project creation to first complete draft (p90, excluding provider outages) | ≤5 minutes                                                              |
| Export success              | Successful renders ÷ render attempts on valid inputs in testing                           | ≥95%                                                                    |
| Weekly review               | Weeks with a review marked complete ÷ weeks in pilot                                      | Tracked                                                                 |
| Organic reach per post      | Median reach at day 7 after publishing, per platform                                      | Baseline vs follow-up                                                   |
| Net new followers           | Follower snapshot at period end − at period start, per platform                           | Baseline vs follow-up                                                   |
| Followers per 1,000 reached | Net new followers ÷ total post reach × 1,000                                              | Only when snapshots sit within 2 days of period boundaries and ≥5 posts |
| Share rate / save rate      | Shares ÷ reach; saves ÷ reach (where the platform supplies saves)                         | Per platform                                                            |
| Watch time / completion     | Median platform-reported values                                                           | Within platform only                                                    |

- Use a 28-day baseline (built from historical import where needed) and
  a comparable 28-day follow-up; segment by platform, content tags and
  posting volume. Mark metrics unavailable rather than fabricating them.
  No promise of causality or growth.

- **new** Expectation: at 3–5 posts/week split across topics,
  comparisons need ≥5 posts per group, so the first recommendations are
  likely after roughly 4–8 weeks. The pilot should be judged on this
  timeline.

# 6. Experience and screens **revised**

- Home dashboard: next action per project, content pipeline by state,
  weekly posting adherence, reach and follower trends, active
  experiments.

- Ideas/Bible study: topic, audience, content tags, passages, scripture
  verification status.

- Script Studio: 2–3 hook variants, editable five-part script with
  scripture placeholders, length estimate, versioning with provenance,
  teleprompter.

- Record: Prompter-only mode; Record mode with prompter overlay where
  supported.

- Video Studio: upload, transcription, subtitle text and timing
  correction, SRT and 9:16 export, platform checks.

- Repurpose: platform captions, hashtags and CTAs with live character
  counts.

- Calendar: date/time with timezone, platform, status, reminders and
  published state.

- Growth Lab: manual entry, follower snapshots, historical and CSV
  import, comparative dashboard, recommendation evidence, experiment
  log, weekly review.

- Settings: profile, content voice and guardrails, preferred
  translation, words-per-minute, subtitle style, time zone, platform
  account flags (e.g. X Premium), data export and deletion.

# 7. Constraints and risk controls **revised**

- Human review mandatory for theology, references, claims and
  publication.

- **revised** Bible text: AI never writes verse text. Quotations come
  only from an allowlisted translation with recorded licence notes and
  quotation limits, or are pasted by the creator. In the UK the KJV is
  under Crown copyright and is not assumed to be public domain.

- Growth suggestions must not imply guaranteed algorithmic outcomes;
  identify observational signals, sample sizes and possible confounders.

- Private storage, access control, deletion and backups; no public
  exposure of unpublished sermons.

- No unauthorised scraping, engagement manipulation or automation that
  violates platform rules.

- **new** Platform limits change. Caption and video limits are
  configuration, verified against platform documentation before launch.

- **new** UK GDPR: recordings of the creator's face and voice are
  processed by transcription and AI providers; select providers with
  suitable data processing terms, a known storage region and no training
  on inputs.

# 8. Release gates and pilot **revised**

- End-to-end project flow works through the state machine; script edits
  persist; AI output contains placeholders only; source references can
  be marked verified; teleprompter works on mobile with countdown, pause
  and screen-awake; SRT export and 9:16 output usable; platform length
  checks block invalid attachments; reminders fire at the correct local
  time; metrics import validation works without summing cumulative
  values; weekly insights show underlying evidence; all private objects
  require authentication; FRD acceptance tests AT-01 to AT-15 pass.

- **revised** Pilot: import the previous 28 days of posts as baseline,
  then create and publish 12–20 real posts; compare with baseline;
  record time saved per post and rate recommendation usefulness. Use
  results to prioritise the next version.

# 9. Decisions and open questions **new**

| **ID**       | **Question**                                                | **Proposed default**                                                                    |
|--------------|-------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| D-01         | In-app recording or second-device prompter for v1?          | Prompter-only in P0; Record mode as stretch                                             |
| D-02         | Where does verse text come from?                            | Public-domain translation held locally plus creator-pasted text; licensed service in P1 |
| D-03 to D-05 | Transcription provider, LLM provider, worker host and queue | See FRD section 10                                                                      |
| D-06         | Reminder channel                                            | Email first                                                                             |
| D-07         | Current platform caption and video limits                   | Verify before launch                                                                    |

# 10. Traceability matrix **new**

| **Capability**                            | **FRD requirements**   | **Acceptance tests** |
|-------------------------------------------|------------------------|----------------------|
| C-01 Topic intake and tags                | FR-002, FR-021         | AT-01, AT-06         |
| C-02 Scripture                            | FR-003, FR-004, FR-023 | AT-02                |
| C-03 Script and hooks                     | FR-004, FR-005, FR-022 | AT-01                |
| C-04 Voice profile                        | FR-020                 | AT-01                |
| C-05 Teleprompter                         | FR-006                 | AT-08                |
| C-06 Record mode                          | FR-024                 | AT-09                |
| C-07 Upload                               | FR-007                 | AT-03                |
| C-08 Transcription                        | FR-008                 | AT-03                |
| C-09 Export                               | FR-009                 | AT-03                |
| C-10 Captions                             | FR-010                 | AT-04, AT-10         |
| C-11 Platform checks                      | FR-026                 | AT-10                |
| C-12 Calendar and reminders               | FR-011, FR-012, FR-027 | AT-04, AT-11, AT-12  |
| C-13 Home dashboard                       | FR-025                 | AT-04                |
| C-14 Manual metrics and baseline          | FR-013, FR-028, FR-029 | AT-05, AT-14         |
| C-15 CSV import                           | FR-013, FR-014         | AT-05                |
| C-16 Growth dashboard                     | FR-015, FR-016         | AT-05                |
| C-17 Recommendations, review, experiments | FR-017, FR-018, FR-019 | AT-06, AT-13         |
| C-18 Export and deletion                  | FR-030                 | AT-15                |
| Security and access                       | FR-001, NFR Security   | AT-07                |
