# Roadmap: v0.6 Claude Plugin Entrypoint

## Overview

v0.6 makes Claude the **only** interface to the n8n backend that v0.2–v0.5 built: both the
ingestion front door and the control panel. The operator is non-technical, works in Claude
Desktop, and never opens n8n — so anything n8n would show in its own UI (failed executions,
dead credentials, exhausted quotas, stuck locks, review queues) has to arrive here instead,
and anything an admin would do with a script has to be either doable in the conversation or
plainly named as someone else's job. "Run this command" is never an acceptable answer to the
operator.

The ingestion half is deliberately narrow, because the backend already maps columns, normalizes AU phones, verifies emails, resolves identity,
dedupes and routes create/update — all server-side inside `hubspot/contact-upload`. The
plugin does **not** re-implement any of it. Its job is narrow and sits either side of
that pipe: turn *non-tabular* input into rows over the canonical contact props, show the
operator exactly what will be sent and what it will cost, POST it, and report what
happened to each record.

The control-plane half is additive, not a replacement: phases 27–30 layer read, control,
notice, and triage over the same plugin shell.

The journey starts with a walking skeleton — one input shape (a spreadsheet), one lane
(contact-upload), disarmed — so something is demonstrable before any breadth. Then the
other input adapters and the extraction guarantees that make an extracted row
trustworthy. Then the second lane (enrichment on records that already exist) with the
cost guard that keeps a batch from burning provider credits blind. Then outcome
reporting and safe retry.

**Safety posture, inherited and non-negotiable:** every write path in this repo is
disarmed by default and requires a deliberate operator arming step (the two-key gate that
phases 19–22 all follow). The plugin ships disarmed. An approved batch still does not
leave the machine until the operator enables live writes — and that permission is
**conversation-scoped**: it lapses when the session ends and is never inherited. Because the
operator cannot run a command, the plugin performs the arming write itself, restricted to an
allowlist and verified by read-back (Phase 28). That is a real widening of what the plugin may
do to n8n, and the allowlist plus the confirm-and-verify loop is what keeps it bounded.

**Phase numbering continues from the archived v0.5 milestone (ended at phase 22), so
phase directories never collide with phases 20–22.**

## Phases

**Phase Numbering:**

- Integer phases (23, 24, …): Planned milestone work
- Decimal phases (23.1, 23.2): Urgent insertions (marked INSERTED)

- [x] **Phase 23: Walking Skeleton — Plugin Shell & Tabular Dispatch** - A spreadsheet goes in conversationally, an approved preview goes out to `hubspot/contact-upload`, and nothing sends unless armed
- [x] **Phase 24: Non-Tabular Input Adapters** - Prose, foreign JSON, public URLs, and web-page screenshots become canonical rows with provenance — or a named error
- [x] **Phase 25: Enrichment Lane & Cost Guard** - Existing HubSpot records can be enriched, and no batch launches without a cost estimate and a chunking plan
- [x] **Phase 26: Outcome Reporting & Safe Retry** - Per-record outcomes replace bare HTTP statuses, and a partial failure is re-sendable without duplicates
- [x] **Phase 27: Backend Status Surface** - An n8n-side health endpoint plus a plain-language read of what the backend is doing, in text or as a dashboard
- [x] **Phase 28: Control Actions** - Run it, turn it on and off, reschedule it, and enable live writes for one conversation — all confirmed and read-back verified
- [x] **Phase 29: Notices & Unattended Sweep** - Runs report themselves when they settle, and a sweep speaks up when something needs a human while nobody is watching
- [x] **Phase 30: Review-Queue Triage** - Conflicts get resolved conversationally, with the decision written back as a human decision
- [x] **Phase 31: Enum Validation for Review Approvals** - Enum-bound candidates are validated against HubSpot's real option set before they are offered, refusals are explicit at every layer, and silence stops meaning two opposite things
- [x] **Phase 32: LLM-Free Sweep Trigger** - The unattended sweep fires under real cron with no credentials and no LLM, and a trigger that cannot run says so loudly instead of impersonating a healthy backend
- [x] **Phase 33: Durable Operator State** - Config and the dashboard pointer survive a plugin update on their own, so an operator never runs a terminal command to keep working after installing a new version
- [ ] **Phase 34: Header Mapping Tolerance** - A spreadsheet whose headers the backend does not recognise is corrected with the operator, not silently guessed at and not dead-ended

## Phase Details

### Phase 23: Walking Skeleton — Plugin Shell & Tabular Dispatch

**Goal**: An operator can, inside a Claude session, hand the plugin a contact spreadsheet, approve an exact preview of what would be sent, and — only after explicitly arming — have it land in `hubspot/contact-upload`.
**Depends on**: Nothing (first phase)
**Requirements**: INGEST-02, STRUCT-01, PREVIEW-01, PREVIEW-04, DISPATCH-01, DISPATCH-03, PLUGIN-01, PLUGIN-02, PLUGIN-03, PLUGIN-04
**Success Criteria** (what must be TRUE):

  1. The operator invokes the entrypoint conversationally in a Claude session — installed as a plugin, not a hand-run script — and it states up front which endpoint it targets and whether dispatch is currently armed.
  2. Pointing it at a CSV or XLSX with arbitrary, uncleaned headers produces a preview showing the exact body to be sent (canonical contact props only, the shape the existing `Map Columns` node accepts unchanged) and the row count; declining the preview sends nothing and costs nothing.
  3. With live writes off — the default — an *approved* batch is still not sent: the operator is told plainly that sending is off and how to turn it on for this conversation. With it on, the same batch POSTs to `hubspot/contact-upload` with header auth and a binary CSV body that the workflow's `Extract From File` node parses, and n8n returns per-row items.
  4. Every file the client adds lives under `operator-claude-plugin/`, with its own README and CHANGELOG, and no backend file is modified to make the client work — the client is replaceable without touching `n8n/`, `config/`, or the enrichment `src/` modules.
  5. With the endpoint URL or auth secret missing from admin-provisioned configuration (which lives outside the plugin source and is never committed), the plugin refuses before any network call and says in plain language what is not configured and who can fix it — the operator is never shown a key, asked to paste one, or left staring at a socket error.

**Plans**: 5/7 plans executed

Plans:
**Wave 1**

- [x] 23-01-PLAN.md — Backend gate fix: the contact lane's create decision reads the deploy-time-overlayable write-safety constant (D-15/D-16, must land first)
- [x] 23-02-PLAN.md — Early Code-tab smoke test: does an attached file resolve to a readable path, and can that session run the scripts (D-14a)
- [x] 23-03-PLAN.md — Wave 0: plugin test package, autouse network guard, own requirements.txt, config example + gitignore entry

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 23-04-PLAN.md — Tracer: config gate → file read → disarmed dispatch, plus the plugin manifest, the skill, and the no-backend-imports guard

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 23-05-PLAN.md — Adaptive preview with display-only column labelling, skill preview/approve wording, operator docs, PLUGIN-02 reconciliation

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 23-06-PLAN.md — Manual gates: Desktop install/invocation, and one human-executed armed canary that creates a contact

**Gap closure** *(no in-phase dependency — must land BEFORE 23-06 Section B resumes)*

- [ ] 23-07-PLAN.md — Fix the armed/disarmed read-back: discovered coverage over every deployed workflow, an explicit expected-armed flag set, and both operator runbooks brought back into agreement (D-19)

### Phase 24: Non-Tabular Input Adapters

**Goal**: Input that is not already a table — pasted prose, a foreign-shaped JSON blob, a public URL, a screenshot of a web page — becomes canonical rows the operator can audit and trust, or an error they can act on.
**Depends on**: Phase 23 (reuses its preview/approve/dispatch shell; each adapter feeds the same choke point)
**Requirements**: INGEST-01, INGEST-03, INGEST-05, INGEST-06, INGEST-07, STRUCT-02, STRUCT-03, STRUCT-04
**Success Criteria** (what must be TRUE):

  1. Pasting freeform text — an email signature block, a typed list of names and companies — yields rows over the canonical props only, and the preview shows for each row which span of the pasted input produced it.
  2. A JSON array in a shape the alias table has never seen translates into canonical rows, with keys that could not be mapped reported to the operator rather than silently dropped.
  3. A public URL is fetched with the native `web_fetch` tool (honest client, robots.txt respected) and contact/company fields extracted from the page content; a page that yields nothing usable says so instead of producing empty rows.
  4. One or more screenshots of a web page — a speaker list, a staff directory, a search-results page the operator captured themselves — yield canonical rows, with each row's provenance naming the image it came from and where on it. Multiple screenshots of one page (a scrolled sequence) are read as a single source without duplicating rows that appear in the overlap.
  5. A field absent from the source stays absent in the row — never inferred, guessed, or filled from the model's own knowledge. A prose entry with no email address does not acquire one, and a screenshot value the image renders ambiguously (truncated, cut off, unreadable glyph) is surfaced for operator confirmation rather than completed by guessing.
  6. Rows failing the identity rule (`email` OR `firstname`+`lastname`+`company`) appear in a separate rejected list with a per-row reason and are excluded from the dispatch payload; unreadable, empty, or unsupported input produces a named error, never a silent zero-row success.

**Plans**: 3 plans

Plans:

- [x] 24-01-PLAN.md — Extraction validator spine: artifact handoff, identity pre-flight, canonical-key reporting, provenance strip (wave 1)
- [ ] 24-02-PLAN.md — Screenshot overlap dedupe on the identity key, and one-list ambiguity aggregation (wave 2)
- [ ] 24-03-PLAN.md — The extraction contract: prose, foreign-JSON, URL and screenshot adapters wired into the Phase 23 skill (wave 2)

### Phase 25: Enrichment Lane & Cost Guard

**Goal**: An operator can trigger enrichment on records that already exist in HubSpot, and cannot launch a batch on either lane without first seeing what it will cost and how it will be split.
**Depends on**: Phase 23 (dispatch shell and arming gate); sequenced after Phase 24 so the cost guard covers every input path that can produce a batch. Builds the credit-only slice of the n8n-side status endpoint that Phase 27 later grows into full health — the client holds no provider credentials and cannot read balances directly
**Requirements**: INGEST-04, DISPATCH-02, PREVIEW-02, PREVIEW-03
**Success Criteria** (what must be TRUE):

  1. **[AMENDED by 25-BLOCKERS.md §"View resolution" — saved views scoped out]** Naming existing HubSpot records — record IDs or a HubSpot list — produces an enrichment request with no row structuring involved, previewed and approved through the same gate as any other batch. *A saved **view** is refused with a redirect to saving it as a list, because HubSpot exposes no public API for views and no evidence of one was found. Lists themselves are supported and were probed live on 2026-07-31 — `crm.lists.read` granted, HTTP 200, 102 members read — so this is the small amendment (views only), not the large one (lists and views). Seventh accepted requirement amendment in this milestone; INGEST-04 is reworded to match.*
  2. **[AMENDED by 25-CONTEXT.md D-05 — the shipped client default is the full waterfall]** An approved enrichment POSTs to `hubspot/enrichment/event` with header auth in the envelope shape `Parse HubSpot Event` accepts, carrying an explicit provider selection resolved from a per-batch override over an admin default that ships as the full waterfall — and that resolved selection is stated in the preview before approval, every time, whatever it resolved to. The backend enables no provider when a request carries no recognizable selection, so a malformed or selection-less request burns nothing. *The original wording folded the backend's fail-closed behaviour and the client's own default into one sentence, reading as though staying silent enabled nothing; with a permissive client default, staying silent enables everything. The user was shown that conflict and chose the default-on behaviour, mitigated by the mandatory preview display above and by the backend's fail-closed parser. Second accepted requirement amendment in this milestone.*
  3. Every preview — both lanes — shows an estimated provider-credit and Anthropic-token cost for the batch, derived from the repo's measured per-record rates rather than a guess, and warns when the estimate exceeds the credits actually remaining. Remaining balances arrive from the n8n-side status endpoint, never from the client calling a provider directly; a balance that cannot be read reads "unknown" and the warning says so rather than assuming headroom.
  4. A batch above the configured size limit is shown in the preview already split — chunk count and rows per chunk — before approval, and dispatch sends exactly that plan.

**Plans**: 7/7 plans executed

Plans:
**Wave 1**

- [x] 25-01-PLAN.md — Blockers first: live `crm.lists.read` scope probe, chunk-timing measurement, and the recorded saved-view decision (D-02a, D-11a)
- [x] 25-02-PLAN.md — n8n credit-only `hubspot/backend-status` endpoint, with unreadable proven distinct from zero (D-10)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 25-03-PLAN.md — n8n list resolution on the enrichment webhook: additive branch, bounded expansion, view refusal (D-01/D-02)
- [x] 25-04-PLAN.md — Client tracer: provider-selection resolution, enrichment envelope, disarmed dispatch, and the documented full-waterfall default (D-03/D-04/D-06a)
- [x] 25-05-PLAN.md — Dated plugin-local rate table, batch estimate, status-endpoint balance client, tri-state comparison (D-07/D-08/D-09/D-10)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 25-06-PLAN.md — Chunk plan computed once, sequential dispatch that skips a failure, failed chunks returned as a re-sendable batch (D-11/D-12/D-13)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 25-07-PLAN.md — Cost block on both lanes, the enrichment skill, operator docs, and the criterion-2 and view-scope amendments (D-05, D-02a)

### Phase 26: Outcome Reporting & Safe Retry

**Goal**: After a send, the operator can see what happened to each individual record and can re-send only the part that did not land.
**Depends on**: Phase 25 (both lanes must dispatch before their outcomes can be parsed; retry safety needs the per-record outcome to identify what to re-send)
**Requirements**: REPORT-01, REPORT-02, REPORT-03, DISPATCH-04
**Success Criteria** (what must be TRUE):

  1. After a contact-upload dispatch the operator sees a per-record outcome — created, updated/matched, needs_review, or rejected with its reason — instead of a bare HTTP status.
  2. **[AMENDED by 26-CONTEXT.md D-10a / D-10b — ICP-tier clause removed]** After an enrichment dispatch the operator sees, per record and without leaving the session, the needs-review flag alongside remaining provider credits as reported by the n8n-side status endpoint (or the enrichment response's own `remaining_credits`) — the client never queries a provider itself. *ICP tier, fit score and anti-ICP flag are deliberately absent: HubSpot owns those derived outputs by the Phase 15 "Approach C" decision (`src/merge_policy.py:347`, `n8n/code/mergeCompanies.js:53`, `config/field_policy.yaml:97`), so the backend has nothing to hand back and the report shows neither a value nor a placeholder. REPORT-02 in REQUIREMENTS.md should be reworded to match before this phase seals — fourth accepted requirement amendment in this milestone.*
  3. When the n8n run is still in flight or the response came back partial, the report says so explicitly, shows the state it does know, and tells the operator how to re-check — it never presents an incomplete run as a finished one.
  4. A failed or partially-failed dispatch names the specific rows that did not land, and re-sending exactly those rows does not create duplicates of records the earlier attempt already accepted.

**Plans**: 3 plans

Plans:

- [x] 26-01-PLAN.md — Contact-lane per-record ledger from the decision node, executions-API fallback, run handle, and honest in-flight framing (REPORT-01, REPORT-03)
- [ ] 26-02-PLAN.md — Enrichment-lane review flag and remaining credits, with unknown kept distinct from zero and no ICP surface (REPORT-02)
- [ ] 26-03-PLAN.md — Failing rows named and classified by what a re-send can fix; retry routes through the one armed dispatch path (DISPATCH-04)

### Phase 27: Backend Status Surface

**Goal**: The operator can ask what the backend is doing and get a truthful, plain-language answer — without ever opening n8n, and without the plugin holding a provider credential.
**Depends on**: Phase 25 (which builds the first, credit-only slice of the n8n status endpoint for its cost guard; this phase generalizes that endpoint into full health)
**Requirements**: STATUS-01, STATUS-02, STATUS-03, STATUS-04, STATUS-05, STATUS-06
**Success Criteria** (what must be TRUE):

  1. Asking "what's the backend doing?" returns, per workflow: on or off, whether live writes are currently enabled, when it last ran and whether that run succeeded, and what is in flight — read from the n8n API, not asserted from local config.
  2. A failed execution is reported by cause in plain language — expired credential, rate limit, exhausted quota, malformed record — and names whether the operator or an admin can fix it. No status codes, no stack traces, no "check the n8n UI".
  3. Provider credit balances and remaining headroom reach the operator through the n8n-side status endpoint. The plugin never holds a provider or HubSpot credential, and a provider whose balance cannot be read (Apollo's key is not master — it 403s) shows as unknown, never as zero or healthy.
  4. Wedged runs (an execution still running past a configured threshold), records queued but never processed, and the review backlog are surfaced with counts, so a silently wedged backend is visible without anyone thinking to look. *(Amended by 27-CONTEXT.md D-07a/D-07b/D-07d — the original wording named a HubSpot lock property that does not exist in this portal's schema, and a runtime status value nothing in the pipeline ever writes. "Stuck" is redefined against the executions API. Third accepted requirement amendment in this milestone.)*
  5. Status is conversational text by default; on request a dashboard Artifact carries the same data stamped with its fetch time, and refreshing re-publishes to the same URL rather than minting a second one.

**Plans**: 5 plans

Plans:
**Wave 1**

- [ ] 27-01-PLAN.md — Backend: grow `hubspot/backend-status` from credits-only to full health — queued and review-backlog counts for both object types, plus credential health, with unknown never collapsing to zero
- [ ] 27-02-PLAN.md — Failure-cause translation: the static signature table and D-05's guardrail (unmatched errors labelled as interpretation, raw text redacted, attribution defaulted to an admin)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 27-03-PLAN.md — Tracer: one workflow end to end — config gate, read-only n8n API client, write-safety literal read, backend-status POST, unknown rendering

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 27-04-PLAN.md — Full picture: every workflow with no allowlist, stuck-by-execution-age, per-node error harvesting, and the conversational answer plus its skill

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 27-05-PLAN.md — Dashboard Artifact, the two-field identifier store with a 30-day default TTL and garbage collection, and one human checkpoint for same-URL refresh across sessions

### Phase 28: Control Actions

**Goal**: The operator can operate the backend — start it, stop it, reschedule it, allow it to write — entirely from the conversation, with every mutation confirmed in advance and verified after.
**Depends on**: Phase 27 (nothing may be flipped that cannot first be read; every mutation's confirmation and read-back verification is built on that read surface)
**Requirements**: CONTROL-01, CONTROL-02, CONTROL-03, CONTROL-04, CONTROL-05, CONTROL-06, CONTROL-07
**Success Criteria** (what must be TRUE):

  1. The operator can start either built ingestion lane (both are: contact upload and enrichment), and is told the run started and how its outcome will come back — no scripts, no terminal, no n8n UI. *(Off-cycle scheduled-scan execution removed — no endpoint to execute a workflow by id exists; probed 405 on this tenant, 28-FINDINGS.md Q2. D-05a/b/c.)*
  2. The operator can turn a workflow on or off, and enable, disable, or re-time a scheduled job in plain terms ("check every 15 minutes" → "hourly") — cron syntax never appears.
  3. The operator can enable live writes for the current conversation only. It lapses when the conversation ends, is never inherited by a later session, and every status readout states plainly whether it is currently on.
  4. Every mutation states its consequence before it happens ("this lets enrichment overwrite company fields in HubSpot"), shows what will change, and waits for explicit confirmation. The mutation set is allowlisted — write-safety flag overlay, Schedule Trigger cadence, a Schedule Trigger node's `disabled` boolean, workflow active state — and any other workflow-JSON change is refused rather than attempted. *(The `disabled` item is D-25, amendment #6: five Schedule Triggers share one workflow.)*
  5. After every mutation the plugin re-reads the backend and reports verified or failed. A `200` from n8n is never reported as success on its own, and the inverse action is stated at the moment the change lands.

**Plans**: 6 plans

Plans:
**Wave 1**

- [ ] 28-01-PLAN.md — Tracer: the mutation pipeline end to end (fetch, four-key PUT filter, structural allowlist diff, prior-active-restoring bracket, independent read-back) proven on workflow on/off

**Wave 2** *(blocked on Wave 1)*

- [ ] 28-02-PLAN.md — Live semantics probes, human-executed, arming nothing: the no-op GET→PUT round-trip, the execute-endpoint check, and whether the deactivate→PUT→activate bracket is actually effective

**Wave 3** *(blocked on Wave 2)*

- [ ] 28-03-PLAN.md — Arming lifecycle: bidirectional write-safety setter, record-scoped arm, read-back-verified disarm, loud disarm failure
- [ ] 28-04-PLAN.md — Cadence in plain terms: read, describe, parse-or-refuse, one-node mutation; plus the per-job schedule enable/disable decision

**Wave 4** *(blocked on Wave 3)*

- [ ] 28-05-PLAN.md — Operator surface: one confirmation choke point, the backend-control skill, lane starts, and the CONTROL-01 amendment

**Wave 5** *(blocked on Wave 4)*

- [ ] 28-06-PLAN.md — Manual gates: one human-executed armed canary bounded to a single record, plus control-surface documentation

### Phase 29: Notices & Unattended Sweep

**Goal**: The operator learns that something needs them without having to think to ask — during a session, and while no session is open.
**Depends on**: Phase 28 (a notice is only actionable if the fix is reachable from the conversation; the sweep's messages point at the controls Phase 28 exposes)
**Requirements**: NOTICE-01, NOTICE-02, NOTICE-03, NOTICE-04, NOTICE-05
**Success Criteria** (what must be TRUE):

  1. After a dispatch the plugin keeps watching and reports back unprompted when the run settles, with per-record outcomes and the cost actually incurred — the operator does not have to ask twice.
  2. The watch is bounded, and a run still unsettled at the bound is reported as still running with how to re-check. It never simply stops talking.
  3. A sweep running with no session open pushes a notification when something needs a human: a failed scheduled run, a credential or auth failure, an exhausted quota, a stuck lock, or a review backlog past its threshold.
  4. The sweep is silent when the backend is healthy, and each notice it does send states whether the operator or an admin can act on it.
  5. The sweep is read-only by construction: it burns no provider credits, enables no writes, dispatches nothing. A sweep that fires while live writes are off changes nothing about that.

**Plans**: 6 plans

Plans:
**Wave 1**

- [ ] 29-01-PLAN.md — Platform probes: can a scheduled routine invoke this plugin's own skill, where does its notice land, and does Desktop chat follow up unprompted (D-04, bonus-only)
- [ ] 29-02-PLAN.md — Wave 0: sweep fixtures including the two deceptively-healthy payloads, plus the measured watch bound from data the ledger already fetches (D-06a)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 29-03-PLAN.md — Tracer: one condition end to end (read → classify → attribute → notice), plus NOTICE-05's import-graph guard proven to bite (D-02a)
- [x] 29-04-PLAN.md — The bounded in-session watch: two terminal reports and no third, per-record outcomes and cost actually incurred (D-05a, D-07)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 29-05-PLAN.md — The remaining conditions: credential failure and exhausted quota as new judgment over existing data, failed scheduled run past its swallowed-error blind spot, review backlog, stuck-armed backstop; silence when healthy

**Wave 4** *(blocked on Wave 3 completion)*

- [~] 29-06-PLAN.md — Ship it: the sweep skill, the scheduled-routine template, the two-part install docs, and one live gate proving a notice arrives with no session open

### Phase 30: Review-Queue Triage

**Goal**: Records the backend flagged for human judgment get that judgment in the conversation, and the CRM records that a person decided.
**Depends on**: Phase 28 (reuses the confirm-then-verify gate machinery for a second, distinct write path) and Phase 27 (the queue is surfaced there before it can be worked here)
**Requirements**: REVIEW-01, REVIEW-02, REVIEW-03, REVIEW-04, REVIEW-05
**Success Criteria** (what must be TRUE):

  1. The queue lists each record's conflict in plain language — the competing values, which source said what, evidence links, and a link to the HubSpot record — so a non-technical operator can actually adjudicate it.
  2. Resolving a review conversationally writes the decision back, honoring the existing field-policy ownership classes: a `manual_protected` value is never overwritten by a review decision, and the non-clobber policy is not re-implemented here.
  3. Review writeback is gated by its own session-scoped confirmation, separate from dispatch arming. Ungated, it shows the exact property write it would make and makes none.
  4. Every decision stamps human source, timestamp, and the operator's stated reason into the existing source-metadata fields, so the audit trail distinguishes a person's call from a model's.
  5. Rejecting a record records the reason and leaves it in the queue. Review flags are never silently cleared, and a record never leaves the queue without a recorded decision.

**Plans**: 7 plans

Plans:
**Wave 1**

- [x] 30-01-PLAN.md — Review writeback gets its own backend arming flag, separate from dispatch arming in both directions, and the pinned four-name overlayable set is deliberately widened to five

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 30-02-PLAN.md — Tracer: one rejection end to end — webhook, refetch, decision module, dry-run preview, disarmed write gate, single-property PATCH

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 30-03-PLAN.md — Approve through the existing `reviewApply` compare-and-set, stamped as a human decision in the provenance blob; contacts routed through the same endpoint

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 30-04-PLAN.md — `hubspot/review/queue`: one authenticated, provably read-only call returning the flagged backlog with its stored conflict detail

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 30-05-PLAN.md — Client: plain-language conflict rendering, display-only field-policy labelling, HubSpot record links

**Wave 6** *(blocked on Wave 5 completion)*

- [x] 30-06-PLAN.md — Client: session-scoped review arm, the backend's own exact-write display, read-back verification, and the review-triage skill

**Wave 7** *(blocked on Wave 6 completion)*

- [x] 30-07-PLAN.md — Admin runbook plus the one human-executed armed canary on a single allowlisted record, closed by a read-back-verified disarm

### Phase 31: Enum Validation for Review Approvals

**Goal**: A review approval can never carry a value HubSpot will refuse — enum-bound candidates are validated against the property's real option set before they are offered, and when something is refused, every layer says so explicitly instead of failing silently or lying.
**Depends on**: Phase 30 (the review decision path this hardens) and Phase 25 (the enrichment staging that produces candidates)
**Requirements**: REVIEW-02, REVIEW-05 (hardening); BUGS 28/29/30 from `.planning/todos/pending/2026-08-03-fix-bugs-28-30-enum-validation-for-review-approvals.md`
**Success Criteria** (what must be TRUE):

  1. A generated enum-options module (values AND labels, built from the HubSpot property schema snapshot, following the `taxonomy.generated.js` pattern) is the single source of truth for what HubSpot's enum properties accept, and a pinning test fails when the snapshot and the generated module drift.
  2. Enrichment staging (`mergeCompanies.js`) never offers an approvable candidate whose value HubSpot's enum will refuse: exact case-insensitive label→value matches are normalized to the internal value (`Sports` → `SPORTS`); everything else stays staged-only with an explicit validation status naming why. NO general mapping layer — decided 2026-08-03.
  3. `reviewDecision.js` validates enum-bound values in the shared patch path, so BOTH `dry_run` preview and apply refuse an invalid value explicitly, naming the value and the property — a preview can no longer answer `applied` for a write that would 400 (BUG 29).
  4. The review write gate answers an explicit refusal body on an allowlist drop instead of dropping the row silently, so the client can distinguish "not allowlisted" from "workflow error" (BUG 30) — and OPERATOR-RUNBOOK RB-9's diagnostic advice is corrected to match.
  5. Both sides of every touched contract are pinned by tests that read both sides (python + n8n), per the milestone's five-times-burned rule; committed workflow artifacts remain disarmed, and the fix reaches the live tenant only via a disarmed redeploy + bounce.

**Plans:** 3 plans

Plans:
- [x] 31-01-PLAN.md — The enum spine: generated options module, the shared validator, refusal on the approve path (tracer) and at enrichment staging, plus the snapshot/policy currency pins
- [x] 31-02-PLAN.md — BUG 30: an explicit `not_allowlisted` refusal body, the client's corrected `unparseable_response` meaning with a two-sided outcome pin, and RB-9's diagnostic advice
- [x] 31-03-PLAN.md — Close-out: the two-sided contract inventory, the disarmed-artifact gate, and the operator-directed disarmed redeploy + bounce

### Phase 32: LLM-Free Sweep Trigger

**Goal**: NOTICE-03 actually holds — the sweep reaches the operator with no session open, under the real cron host, with nothing in the trigger path that can silently die; and when the trigger itself cannot run, the operator is told instead of being shown what health looks like.
**Depends on**: Phase 29 (the sweep it triggers; RB-8's failure is this phase's reason to exist)
**Requirements**: NOTICE-03, NOTICE-05 (install docs change); todo `.planning/todos/pending/2026-08-03-sweep-cron-credentials-block-notice-03.md` (solution SETTLED AND PROVEN — do not relitigate)
**Success Criteria** (what must be TRUE):

  1. A shipped `sh` wrapper (in `skills/backend-sweep/`) runs `sweep_entry.py` directly, posts one `osascript` banner per notice, appends the full JSON to the log, and needs no LLM, no Anthropic credential, and nothing outside `/usr/bin:/bin` plus the named python — proven by the 2026-08-03 `env -i` and real-cron fires (22:54:21).
  2. A trigger that cannot run is LOUD: non-zero exit AND a banner telling the operator the sweep itself is broken. "Never fired" and "healthy" are no longer indistinguishable.
  3. `SWEEP-CRON-TEMPLATE.md` is rewritten around the wrapper: no `claude -p`, no prompt file, a documented venv step (the plugin's own `requirements.txt`), cadence reasoning retained.
  4. `29-HOST-PROBE.md` D-01 is amended: the host is cron/launchd → the plugin's own Python. The amendment records WHY the original probe misled — it ran `claude -p` interactively, inheriting credentials the cron host never has (verification one layer from the claim).
  5. The wrapper's contract with `sweep_entry.py`'s output shape is pinned by a two-sided test (the shell side read as text, the python side executed), and the plugin suite stays green.

**Plans**: 2 plans

Plans:
- [x] 32-01-PLAN.md — ship `lv-sweep-run.sh` + its two-sided contract test, rewrite `SWEEP-CRON-TEMPLATE.md` around it, amend D-01, update README/CHANGELOG/STATE (wave 1, autonomous)
- [x] 32-02-PLAN.md — rewrite RB-8 for the new trigger, run it live as the phase exit gate, record the observed outcome (wave 2, blocking human checkpoint)

### Phase 33: Durable Operator State

**Goal**: An operator who updates the plugin keeps working with no terminal step. Both pieces of per-operator state — the config that holds their credentials and the dashboard Artifact pointer that makes STATUS-05 true — live outside the versioned install directory, migrate themselves once from wherever they are now, and leave no credential copy behind in a dead install.
**Depends on**: Phase 23 (config_gate, the resolution point), Phase 27 (artifact_store, the dashboard pointer)
**Requirements**: PLUGIN-02 (config setup is a one-time operator step), PLUGIN-03 (name what is broken and who fixes it), STATUS-05 (same dashboard URL across sessions — currently resting on a pointer that no install directory holds); Out-of-Scope line "Operator-run commands, scripts, or config files … Terminal instructions to the operator are a requirement failure"
**Success Criteria** (what must be TRUE):

  1. Config resolves from a version-independent home and survives an update with NO operator action: explicit path argument, then `LV_OPERATOR_CONFIG`, then the durable home, then the same-install legacy path, then — once — the newest sibling install's config, which is migrated up. The sibling scan is what makes the update that INTRODUCES durability free; without it this phase's own release costs one hand-copy.
  2. The dashboard Artifact pointer gets the identical treatment. `artifact_store.DEFAULT_STATE_PATH` currently sits in `PLUGIN_ROOT/state/`, so STATUS-05's cross-session guarantee has been silently false since the first update — no install directory on this machine holds a pointer.
  3. A migrated config is written `0600`, and the dead install's copy is removed after the new one is verified readable. Three stale install directories currently each hold a full copy of `webhook_secret` and `n8n_api_key`.
  4. `initialize` reports the REAL resolved path (durable home, not `PLUGIN_ROOT/config/`) and says nothing about migration having happened unless it happened. Migration runs at config RESOLUTION, not only in `initialize` — an operator who never types `/initialize` must not lose config on their next update.
  5. Every path is pinned at the ENTRYPOINT layer against an isolated plugin root: resolution order, the one-time sibling migration, the `0600` mode, and the durable pointer surviving a simulated version bump. Asserting on the resolver function alone is what shipped the 0.6.1 and 0.6.2 defects in opposite directions.
  6. Nothing regresses: the legacy same-install path still resolves, the plugin suite stays green, and no secret value ever reaches a log line or a refusal message.

**Plans**: 4 plans

Plans:

**Wave 1**

- [x] 33-01-PLAN.md — Tracer: durable config home resolved through one shared module, steps 1–4, pinned at the CLI against a fake HOME

**Wave 2** *(blocked on Wave 1)*

- [x] 33-02-PLAN.md — Step 5: the one-time sibling scan, atomic 0600 write, and verify-then-delete behind a one-way decision gate

**Wave 3** *(blocked on Wave 2)*

- [x] 33-03-PLAN.md — The dashboard pointer gets identical treatment (STATUS-05 across an update), and `initialize` reports the real resolved path

**Wave 4** *(blocked on Wave 3)*

- [x] 33-04-PLAN.md — Doc truth sweep, plugin 0.7.0 release cut, and RB-10: one real migration observed on this host

### Phase 34: Header Mapping Tolerance

**Goal**: A spreadsheet whose headers the backend does not recognise is corrected with the operator, not silently guessed at and not dead-ended. Unambiguous near-misses map deterministically; the genuinely ambiguous tail is suggested and confirmed per header; what cannot be honestly resolved is refused with its reason named.
**Depends on**: Phase 23 (preview + `Map Columns` contract), Phase 33 (0.7.3 shipped `column_mapping.yaml`, which is what made the mismatch visible at all)
**Requirements**: INGEST-02 (CSV/XLSX read without pre-cleaning the headers — the requirement UAT 2.2 fails against), INGEST-06 (clear, actionable error when an input cannot be used), STRUCT-01 (canonical contact props only — `Map Columns` accepts the payload unchanged), STRUCT-04 (ambiguity is flagged for operator confirmation, never resolved by guessing), PREVIEW-01 (the operator sees the exact payload before anything is sent)
**Success Criteria** (what must be TRUE):

  1. `config/column_mapping.yaml` and `n8n/code/columnMap.js` are pinned equal by a test that passes against today's two copies BEFORE any alias moves. The two agree by hand, not by construction — `build_cloud_workflows.py` does not generate one from the other, so widening one alone makes the preview predict a mapping the backend will not perform. A confidently wrong preview is worse than today's honest mismatch.
  2. The unambiguous near-misses map in BOTH files: `e-mail address`, `org.`, `linkedin profile`. These are lookups, not judgment. The backend is rebuilt, redeployed disarmed, and every active workflow bounced — a bare PUT never reloads a running workflow, and a read-back only proves stored content.
  3. `Ph.` is suggested, never assumed. The operator confirms each non-exact match individually; the plugin then corrects the header row of the file it sends and re-previews so the real mapping prediction is visible before approval. `Ph.` could plausibly be a photo column — confirmation is load-bearing, not ceremonial.
  4. `Full Name` is refused with its reason named, not split. Splitting a name is a data transform, and this system deliberately has no name-splitter; a refusal that says so beats a guess that mangles "van der Berg".
  5. No header is ever rewritten without an explicit operator yes, proven by a test at the layer the operator reaches — the CLI driven as a subprocess against an isolated plugin root, not the mapping function in isolation. The client never maps data; the backend's `Map Columns` stays the single authority on what a header means.
  6. The scope amendment is recorded as entry 6 in STATE.md's "Accepted requirement amendments" table: suggestion with per-header confirmation is permitted in the client; silent client-side column mapping remains excluded. A scope line that moves silently is how the next reader concludes the exclusion never meant anything.
  7. Suites stay green (plugin 960/5, python 1841/6, node 550, disarmed-artifact gate 0), the plugin version is bumped in the same commit as the CHANGELOG cut, and the marketplace clone is refreshed. UAT 2.2 is re-walked and re-marked BY THE OPERATOR — a verified fix and an observed pass are different claims.

**Plans**: TBD


## v0.6 Progress

**Execution Order:**
Phases execute in numeric order: 23 → 24 → 25 → 26 → 27 → 28 → 29 → 30.

The first four build the ingestion front door (skeleton, input breadth, second lane + cost
guard, outcome reporting). The last four build the control plane on top of it: read the
backend truthfully, then operate it, then have it speak up unprompted, then work the queue it
surfaces. Read before write, and write before unattended — a notice is only worth sending if
the operator can act on it without leaving the conversation.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 23. Walking Skeleton — Plugin Shell & Tabular Dispatch | 7/7 | Complete | 2026-08-03 (RB-3 armed canary) |
| 24. Non-Tabular Input Adapters | all | Complete | 2026-07-31 |
| 25. Enrichment Lane & Cost Guard | all | Complete | 2026-08-01 (B4 measured) |
| 26. Outcome Reporting & Safe Retry | all | Complete | 2026-07-31 |
| 27. Backend Status Surface | all | Complete | 2026-08-03 (RB-4) |
| 28. Control Actions | all | Complete | 2026-08-03 (RB-7 armed canary) |
| 29. Notices & Unattended Sweep | all | Complete | 2026-08-03 (via Phase 32, RB-8 re-run) |
| 30. Review-Queue Triage | 7/7 | Complete | 2026-08-04 (RB-9 close: REVIEW-04 + D-31 probe) |
| 33. Durable Operator State | 4/4 | Complete | 2026-08-04 (RB-10 walked: migration proven, pointer defect found + fixed in 0.7.2) |

## Coverage

49 / 49 v0.6 requirements mapped to exactly one phase each. No orphans, no duplicates.
Traceability table lives in `REQUIREMENTS.md`.

## Notes for Planning

- **Do not rebuild the backend.** Column mapping, phone/email normalization, verification,
  identity resolution, dedupe and create/update routing are n8n-side and stay there. The
  plugin's only mapping responsibility is producing canonical-prop rows from *non-tabular*
  sources; tabular input passes through to the existing `Map Columns` node.

- **XLSX is not a wire format.** `Extract From File` on the contact-upload workflow runs
  `operation: csv`, so an XLSX input has to be read locally and sent as CSV bytes.
  `src/file_loader.py` already reads CSV/TSV/JSON/XLSX into `list[dict]` — reuse it rather
  than adding a parser.

- **The `providers` field is the burn gate.** `Parse HubSpot Event` treats an absent or
  unrecognized `providers` value as *no providers enabled*. Any enrichment payload the
  plugin builds must set it explicitly and deliberately.

- **Response-shape risk for REPORT-01.** `hubspot/contact-upload` uses
  `responseMode: lastNode` across a branching graph (`HubSpot Update` / `HubSpot Create` /
  `Set Review`), so the HTTP response may not carry every row's outcome. Phase 26 planning
  should verify what actually comes back before assuming a complete per-record ledger is
  available from the response alone; the n8n executions API (already used by
  `scripts/enrichment_cost_ledger.py`) is the fallback source.

- **The client is a separate implementation living in `operator-claude-plugin/`.** Backend
  directories (`n8n/`, `config/`, `scripts/`, and the enrichment modules in `src/`) are not this
  milestone's to edit — the one exception is the new n8n-side status endpoint, which is backend
  work and belongs in `n8n/`. The client talks to the backend over the documented HTTP contract
  only, never by importing enrichment logic, so a Slack bot or web app can replace it later
  without a backend change. `src/file_loader.py` reuse is a co-location convenience (file reading
  is client-side work, not backend logic) and is documented as such — not a licence to import
  merge policy, scoring, or provider code.

- **The plugin holds no provider credentials.** ZoomInfo/Apollo/Lusha and HubSpot creds live in
  n8n, managed by an admin there. So `scripts/check_provider_credits.py`'s direct-to-provider
  reads are an *admin* tool, not a model for the plugin. Credit balances reach the operator
  through a new n8n-side status endpoint. Phase 25 builds the credit-only slice it needs for
  PREVIEW-02; Phase 27 generalizes the same endpoint to full health. Plan them as one endpoint
  grown twice, not two endpoints.

- **Arming is a workflow write, not a runtime setting.** `ALLOW_*` write gates are compiled into
  the workflows' Code nodes by `deploy_n8n_workflows.py` via the `ENABLE_BAKED_FLAGS` overlay,
  and schedule cadence lives in Schedule Trigger parameters — both mean `PUT /api/v1/workflows/{id}`.
  Phase 28 therefore performs a real workflow write, restricted to that allowlist and nothing
  else. `enable_baked_flags()` already fails closed on a flag that did not land; reuse it rather
  than hand-rolling the rewrite. Note the standing constraint: agent tooling in this repo is
  blocked from performing arming writes, so Phase 28's armed path needs a human in the loop to
  execute and verify even though the operator-facing design is a yes/no in chat.

- **Session-scoped arming is the plugin's own state, not n8n's.** n8n's baked flag is persistent
  by nature; the conversation-scoped permission lives in the plugin and gates whether it will
  use it. Both states must appear in status (CONTROL-04, STATUS-01) — "n8n allows writes" and
  "I am willing to write right now" are different facts and conflating them is how a silent
  live send happens.

- **Cost rates already measured.** Per-record provider match rates and Lusha credit burn
  (~4.65 credits/reveal under v2; v3 flat ~1cr/contact) plus the Anthropic token probe live
  in the v0.5 artifacts and `scripts/enrichment_cost_ledger.py` /
  `scripts/check_provider_credits.py`. PREVIEW-02 derives from those, it does not re-measure.

- **Screenshots arrive as attachments, not captures.** INGEST-07 reads images the operator
  hands over in-session; the plugin drives no browser and logs into nothing. Planning must not
  reach for browser automation here — that would recreate the scraping path this milestone
  excludes. Extraction is a vision read on the attached image; the confidence signal it needs
  is "is this glyph legible", not "is this fact true".

- **Out of scope, do not plan phases for:** anti-bot-detection or user-agent spoofing for URL
  ingestion, authenticated/paywalled scraping, automated screenshot capture, company-object
  ingestion, scheduled/unattended runs, and write-back of corrections from the plugin.
