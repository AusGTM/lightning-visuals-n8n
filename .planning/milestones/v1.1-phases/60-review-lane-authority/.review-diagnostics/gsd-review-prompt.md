# Cross-AI Plan Review Request

You are reviewing implementation plans for a software project phase.
Provide structured feedback on plan quality, completeness, and risks.

## Project Context
# lv-n8n-poc

## What This Is

A local-first Python MVP that proves Lightning Visuals' HubSpot → n8n waterfall
enrichment + ICP scoring system before any production wiring. It scores companies
against a governing-body-first ICP rubric using mock ZoomInfo/Apollo/Lusha adapters,
mock Claude web research, a Haiku→Sonnet LLM cascade, and a non-clobber merge policy —
emitting dry-run HubSpot PATCH payloads. It is internal RevOps tooling for LV's sales
team, not a customer-facing product.

## Current State (as of 2026-08-30)

**In flight: v1.1 — Unattended Session Runs (phases 53–61).** Complete: 53, 54, 58, 59, 61.
Absorbed into 61 by operator decision D-61-08: 55 (async run) and 56 (unattended pair pipeline).
Open: **Phase 57 — the next phase** (ceilings, refusal-before-start, post-run proof) and Phase 60
(review-lane authority). Phase 61 closed 2026-08-30 with 6/6 plans and 12/12 verification; all
five cloud workflows are deployed and bounced but were exercised by **disarmed** runs only.
**The first live unattended, credit-spending batch has NOT run — it is gated on Phase 57.**
Detail: `.planning/ROADMAP.md`, `.planning/milestones/v1.1-ROADMAP.md`.

**v1.0 Direct Backfill & Scoring Coverage is paused:** Phase 51 complete, **Phase 52 deferred by
the operator 2026-08-25** in favour of v1.1. The v1.0 requirements are the root
`.planning/REQUIREMENTS.md`; v1.1's live in `.planning/milestones/v1.1-REQUIREMENTS.md`.

### Prior state (as of 2026-08-19), retained

**Shipped: v0.9 — ICP Rubric Calibration & Veto Remediation.** 6 phases, 35 plans, 18
requirements, all verified `passed`. Archived at `.planning/milestones/v0.9-ROADMAP.md`.

The ICP tier is no longer written by a workflow. `lv_icp_tier_derived` is a HubSpot calculated
property computed server-side from `lv_icp_fit_score` and `lv_anti_icp_flag_num`, both written
by the n8n pipeline as plain numerics. There is no property-change event anywhere in the path,
which is what retired the stale-tier bug class rather than its instances. The old `lv_icp_tier`
enum is archived and the workflow that wrote it (`4625147345`) is deleted.

Load-bearing constraint discovered this milestone, worth carrying forward: HubSpot's
`calculation_equation` reads **only numeric properties** — booleans evaluate as null even when
set, enumerations are rejected at create. Anything a formula needs must be written as a number
first. And calculated values backfill ~70–130s after their inputs change, so a read issued
immediately after a write returns null for a property that will compute correctly.

**Next milestone — v1.0 Direct Backfill & Scoring Coverage.** Backfill the ~646 never-scored
companies with ZoomInfo firmographics plus targeted research, in-session, writing the scoring
inputs and the six numeric properties HubSpot's calculation engine reads. No n8n executions — the
operator has no credits for it, and none are needed: HubSpot already derives score and tier from
those six numbers on its own. Decisions in `.planning/MILESTONE-CONTEXT.md`.


## Shipped Milestone: v0.9 ICP Rubric Calibration & Veto Remediation (2026-08-19)

*(Was headed "Current Milestone" — corrected 2026-08-30; v0.9 shipped, the current milestone is
v1.1. The goal/feature text below is the v0.9 record as written at the time.)*

**Goal:** The ICP rubric reflects who Lightning Visuals actually wins, and every scored company
carries a score derived from that rubric rather than from a stale or false one.

**Target features:**
- **Rubric recalibration** — resolve whether `individual_club_team: 5` inverts GTM priority.
  Racing clubs cap at tier C (35–45) while governing bodies reach tier A (80) on org_type alone.
  If clubs are the core market the weighting is backwards. This is the question that triggered
  the blank-region investigation and is still unanswered.
- **Veto remediation** — clear the 17 false non-ANZ vetoes. The code fix is deployed, bounced and
  live-proven; the records need a deliberate armed write window, because SJ-3 correctly declined
  to dispatch through a closed gate and self-drained their flags.
- **Enrichment coverage** — 18 of 66 scored companies have no `lv_org_type` at all. The rubric
  cannot outperform its inputs, so coverage is a scoring-quality ceiling, not a separate concern.
- **Weight validation against outcomes** — the revenue-band deductions (−5 at 500–750M, −50 at
  1.2B+) and the gambling −20 were set by judgement and have never been checked against won/lost
  deals.
- **Loss-reason capture** — start filling `lv_closed_lost_reason` (exists on Deals, 0% filled
  across 59 examined closed-lost deals). This is the evidence that makes future recalibration
  empirical rather than intuitive.
- **Re-score strategy** — with no `lv_icp_scoring_version`, any rubric change implies re-scoring
  the whole population. Plan that against the 2,500/month execution budget deliberately.

**Key context:**
- The pipeline is **disarmed at rest** — `ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`
  and `ALLOW_HUBSPOT_REVIEW_WRITES` are baked `"false"` in the deployed workflow. No re-score of
  any kind lands until a window is opened deliberately. Every write item in this milestone


## Phase 60: Review-lane authority
### Roadmap Section
### Phase 60: Review-lane authority

**Status: PLANNED 2026-09-01** — 4 plans, 3 waves (`60-01`..`60-04`). Context, research, pattern
map and validation strategy all gathered 2026-09-01 (`60-CONTEXT.md`, `60-DISCUSSION-LOG.md`,
`60-RESEARCH.md`, `60-PATTERNS.md`, `60-VALIDATION.md`). Split out of Phase 59 by operator
decision 2026-08-28 (`59-CONTEXT.md` D-59-03).

**Goal**: Approving or rejecting one flagged HubSpot record costs the operator zero manual admin
round trips. Today it costs two: an admin setting `ALLOW_REVIEW_SUBMIT=true` as a shell env var,
and a separate admin-run deploy that bakes `ALLOW_HUBSPOT_REVIEW_WRITES` plus the record's id
into the deployed `LV Review Decision (Cloud)` workflow — G-2's shape, still live on this one
lane (`54-LIVE-PROOF.md`).

**The decisions this phase implements** (locked in `60-CONTEXT.md`, do not re-litigate):
D-60-01 review becomes grantable, deliberately reversing 30-01's D-02/D-08e separation (option
(b) of the three the roadmap offered) · D-60-02 one grant covers all three lanes (enrichment,
contacts, review) together · D-60-03 the grant's own record-scoping bounds which flagged records
review may approve — the same "narrower than the grant, never wider" rule dispatch follows, and
what keeps D-60-02 from being a blank check · D-60-04 `ALLOW_REVIEW_SUBMIT` is retired, with
grant-authorization taking its place as the gate · D-60-05 `ALLOW_HUBSPOT_REVIEW_WRITES` is wired
into `n8n_arming`'s existing overlay mechanism (already one of its five overlayable flags, never
wired for review), removing the deploy round trip · D-60-06 one arm window covers a batch of
review decisions per session rather than one per decision.

**Not an option** (carried from the checklist entry): deleting `ALLOW_REVIEW_SUBMIT` with no
replacement — that leaves the lane's only authority behind a deploy an operator cannot run.
D-60-04 retires it only because D-60-01 puts grant-authorization behind it first.

**Recorded-edit discipline required**: `write_grant.py:64-82`'s comment block documents why the
review lane is currently excluded from `LANES`. This phase reverses that decision — the comment
is AMENDED with a dated addendum (mirroring the D-59-07 amendment below it in the same file),
never silently deleted.

**Depends on**: Phase 53 (the grant machinery this folds review into), Phase 30 (the review lane
and the separation being reversed)

**Requirements**: none mapped — `milestones/v1.1-REQUIREMENTS.md` carries no review-lane id; this
phase is driven by D-59-03 and `60-CONTEXT.md`'s D-60-01..08. The decision ids are the coverage
contract in place of REQ ids, and each plan's `requirements` frontmatter carries the D-60-NN ids
it implements. The spec-less probe fallback records a SKIP for this phase: no `SPEC.md` and no
requirement ids, so no probe predicates were generated.

**Two additions research made that CONTEXT.md did not name**, both in scope by consequence:
Guardrail A was structurally blind to a stuck-open `ALLOW_HUBSPOT_REVIEW_WRITES` the moment
review became grantable (plan 02), and `n8n/code/reviewDecision.js`'s `not_allowlisted` message
becomes false once a grant can set the allowlist dynamically (plan 04, changed at its source and
regenerated — never a hand-edit of the JSON).

**Plans**: 4 plans

- [ ] 60-01-PLAN.md — TRACER: `"review"` becomes a grantable lane end-to-end (LANES, `REVIEW_FLAGS`,
      `arm_for_review`, `submit_decision`'s grant gate), with the two reversed-design tests rewritten
      under recorded-edit discipline. D-60-01/02/03/04/05/07. Wave 1.
- [ ] 60-02-PLAN.md — Guardrail A learns to see a stuck-open review authorization; `authorize_review_batch`
      and the one-window-per-sitting lifecycle (normal, out-of-scope, crashed, revoked). D-60-06. Wave 2.
- [ ] 60-03-PLAN.md — review writes land in the per-run `written_records-<run_id>.json` artifact, in its
      existing vocabulary, with the bookkeeping structurally unable to stop a write. D-60-08. Wave 2.
- [ ] 60-04-PLAN.md — operator surfaces and release: the corrected backend message (regenerated), the
      review-triage skill on the grant, three-lane grants in the dispatch skills, truthful gate tables,
      CHANGELOG and version `0.35.0`. Wave 3.

**Nothing in these plans arms, deploys, writes to HubSpot or calls a provider.** This phase's own
live proof is a supervised operator walk (`60-VALIDATION.md` § Manual-Only Verifications), not an
executor task — the arming gates are what would be under test.



### Requirements Addressed
NOTE: this milestone's requirements file is `.planning/milestones/v1.1-REQUIREMENTS.md` (below). The root `.planning/REQUIREMENTS.md` is v1.0's and does NOT apply to this phase. No requirement id maps to Phase 60 — the coverage contract is the decision ids D-60-01..08 in CONTEXT.md.

# Requirements — Milestone v1.1: Unattended Session Runs

**Defined:** 2026-08-25. **Status:** ~~DEFINED, NOT STARTED (phases unplanned)~~ **IN FLIGHT**
(updated 2026-08-30). Phases 53–61: 53, 54, 58, 59 and **61** complete; 55 and 56 absorbed into 61
(D-61-08); **57 is next** and 60 is open.
**Prior milestone:** v1.0 Direct Backfill & Scoring Coverage — Phase 51 complete, **Phase 52
deferred by the operator 2026-08-25** in favour of this milestone. Its requirements are the root
`.planning/REQUIREMENTS.md`; nothing in this milestone is tracked there.

**The first live unattended, credit-spending batch has NOT run.** Phase 61's backend is deployed
and disarmed-proven; the live run is gated on Phase 57 (D-61-08). RUN-05 and AFTER-03 are now
ticked; **AFTER-01 remains PARTIAL** (57-05), which is the run requirement still standing between
here and that gate.

Source evidence: a UAT walkthrough with the end client, 2026-08-25. The operator's verdict was
that the flow is *"incredibly halting"* — every send needs its own preview, its own arming
phrase and its own confirmation, and **that becomes unfeasible at scale**. The request is a
grant given **once, at the start of a session**, after which the system runs a batch through
ingest → enrichment → HubSpot write without asking again.

## Live evidence (client UAT, 2026-08-25)

A verification session walked the documented operator path for ONE contact
(`347569451461`) and recorded four gaps. Details:
`.planning/quick/260825-contact-company-association/UAT.md`.

- **G-1 (major)** — three separate arming surfaces to reach one write: the client-side
  phrase, the backend `arm_dispatch` confirmation, and the `ALLOW_N8N_ARM` environment
  variable. Each defensible alone; nobody had walked all three from the operator's chair.
- **G-2 (blocker)** — `n8n_arming._arm_gate()` requires `ALLOW_N8N_ARM=true` **in the
  session's environment**, which an operator in Claude Desktop cannot set. The documented
  operator path therefore ends in a refusal only an admin with terminal access can clear.
  Every write this client has seen land was landed by an admin from a terminal. This is
  the mechanism v1.1's "one grant at session start" would have to be built on, so the
  milestone must decide who may grant and how before anything else.
- **G-3 (major)** — arming re-runs the waterfall. The first dispatch derives everything and
  returns `write_blocked`; the arm cycle re-sends the same providers so the values can
  land. **Two full provider passes per record, one thrown away by design** — at scale that
  doubles both the provider bill and the execution count. A grant opened *before* the run
  removes the second pass entirely.

  **Amendment, 2026-08-27 (Phase 54):** the mechanism above is closed. Both
  `n8n_arming.arm_for_dispatch` and `write_grant.authorize_ungranted_send` (plugin
  0.18.0, 2026-08-25) now open the armed window before the dispatch, for granted and
  ungranted sends alike — there is no live `write_blocked`-then-manually-rearm ceremony
  left to re-run. Live-verified by the operator walk on 2026-08-26. The measured saving
  is in `.planning/phases/54-single-pass-armed-dispatch/54-MEASUREMENT.md`: one real
  n8n execution for a single-record, single-ask, post-fix send (execution `11960`),
  against three for the pre-fix triple-refused pass on the same record. Two shapes
  still cost two full passes by design, and neither is this defect: a look-only
  rehearsal (propose mode, never writes) and an identity hold awaiting the operator's
  confirmation (a same-surname, same-company match, held rather than written over).
  The scheduled poller's own double pass is a separate, recorded residual
  (OP-54-02, `.planning/WINDOWS.md` entry 27) — architecturally the same shape,
  deliberately left unfixed because headless/cron paths are out of this milestone's
  scope (D-1.1-01).
- **G-4 (minor)** — two of three provider balances read `unknown` in the same preview
  (Apollo `http_403`, expected; ZoomInfo `provider_error`, new and probably transient). Thin
  cover for an unattended run that spends against them.
  *ZoomInfo half CLOSED 2026-08-31 (57-04): a disarmed live probe against the deployed instance
  observed the balance as `readable` (9381 raw credits, zero measured Lusha delta) — the
  2026-08-25 `provider_error` is gone and needed no code fix; the `Accept:
  application/vnd.api+json` header was already correct in current code. Apollo's `http_403`
  stays disclosed as a permanent, structural blind spot — a non-master API key, unfixable in
  this repo. Lusha: project memory records it live-validated in an earlier phase (the Lusha v3
  migration), but that predates this phase's G-4 work and was not re-verified here — 57-05
  reports it as unconfirmed-by-this-phase, not asserted readable. Both halves' disclosure text,
  and which part of spend is therefore bounded, ships in 57-05's end-of-run report.*

## What the operator is actually asking for

Two different things arrive in one sentence, and the milestone fails if it only builds one:

1. **Fewer decisions.** One grant per session, not one per send.
2. **Higher throughput.** A batch of hundreds must complete without a human sitting in the
   loop between chunks.

The second is not a consent problem and no amount of auto-approval solves it. Today's
per-request ceiling is **2 records** — a measured bound, not a preference: the full-waterfall
probe (B4, 2026-08-03) ran one record in 37.44 s against n8n Cloud's ~100 s response window,
and `SJ-3` fans out one sub-execution per record against a **2,500 execution/month plan**. A
500-contact batch is ~250 requests and, at one execution per record plus overhead, a
meaningful fraction of the monthly allowance. Auto-approving 250 prompts still leaves an
operator watching a progress bar for hours and a plan that may not have the executions to
finish.

## What must NOT be lost

The confirmation surface is not ceremony; each gate exists because something went wrong
without it. A standing grant must keep every one of these properties, or it is a regression
wearing a feature's clothes:

- **Record-scoped writes.** `_writeSafetyAllows` denies unless the record's id or domain is in
  the allowlist, and an empty allowlist denies everything. Arming a session must widen the
  allowlist to *the batch*, never to *everything* — the deployed backend must remain incapable
  of writing a record that was not in the run.
- **Guaranteed disarm.** `armed_window` disarms on the way out even when the dispatch raises,
  and a `disarm_failed` is its own loudly-reported state. A session-long window must disarm on
  session end, on error, and on operator interrupt.
- **Cost ceilings that bind before spend, not after.** Provider credits, Anthropic dollars and
  n8n executions each need a per-run ceiling the run refuses to cross, in the shape
  `n8n_cadence.check_budget_floor` already uses (arithmetic shown at proposal time, not after
  a yes).
- **Per-record auditability.** Every write still stamps source, confidence, evidence URL and
  timestamp. A run nobody watched needs a stronger audit trail than one somebody did.
- **The held-row contract.** A contact whose company cannot be resolved is held, not landed
  (2026-08-25). Unattended running must collect held rows for review, never resolve them by
  guessing to keep a batch moving.

## Requirements

### GRANT — one decision, explicitly bounded

- [x] **GRANT-01**: An operator can open a **session grant** in one exchange, stating what it
  covers: object types, the record set, whether creates are included, and its ceilings.
  *TICKED 2026-08-29 on walk run 3 (`53-WALK-RECORD-2.md` § "WALK RUN 3"), under the operator's
  explicit authorisation. The same record walked end to end under **one grant, one yes**:
  extraction → unarmed match → grant → arm → enrich → merge → strip → CSV → arm → HubSpot create.
  Contact `348695309760` created and auto-associated to Series Futsal Victoria `283816805830` by
  domain, independently confirmed by re-probe; backend `VERDICT: disarmed PASS` after; grant
  closed `batch_complete`. **Two limitations recorded, not waived:** it ran from Claude Code
  **with a terminal**, so the composition is proven and the operator's own constraint set is not;
  and it ran against the **repo** at plugin 0.28.1 rather than the installed plugin. A
  Claude-Desktop walk on the installed plugin is the only thing that proves G-2 is truly gone —
  walk run 4 attempted exactly that on 2026-08-30 and halted before the grant was opened
  (`53-WALK-RECORD-3.md` FINDING D), which is what caused Phase 61. The partial notes below are
  the build history and are retained.*
  *Partial (53-01): the grant's SHAPE ships — `write_grant.plan_grant`/`open_grant` state
  object type, record set, lanes and creates, behind a proposal plus an explicit yes. The
  ceilings are 53-02 T1 and the one-exchange operator surface is 53-03 T2.*
  *Partial updated (53-02): the ceilings now ship — `envelope()` states them and the grant
  carries them unchanged. Only the one-exchange operator surface (53-03 T2) is outstanding.*
  *Partial updated (53-03): the surface an operator reaches now exists — an admin sets
  `allow_write_grants` in `operator.local.json` and `init_check` reports back that they have
  (its own `settings` section, deliberately not a capability row), `control_actions`'
  out-of-allowlist wording names the grant path so an operator asking to turn writes on for a
  batch is pointed at it rather than refused, and `write_grant.authorize_send` bridges an open
  grant to a dispatch's `armed` argument. NOT closed: no lane SKILL invokes any of this yet, so
  the exchange is reachable in Python and not yet from the operator's chair — that is 53-04,
  along with the blocking operator walk of the whole path from Claude Desktop.*
  *Partial updated (53-04): the exchange is now reachable from the operator's chair — every
  lane skill carries the grant branch inside its own arming step, `backend-control` lists
  opening/revoking/closing a grant, and the README tells an admin which key to set and an
  operator what a grant is, what it is bounded to and how it ends. Released as 0.15.0. NOT
  ticked: this requirement's evidence is the operator walk (53-04 task 3, a blocking
  checkpoint), which is outstanding. Ticking it on tests alone would be exactly the claim G-2
  disproved — every component correct, the composition broken.*
- [ ] **GRANT-02**: The grant's envelope is shown as arithmetic before it is accepted — record
  count, worst-case provider credits, worst-case Anthropic dollars, projected n8n executions
  against the remaining monthly allowance.
  *Partial (53-02): `write_grant.envelope()` computes all four figures at plan time and
  attaches them to the grant unchanged, an unreadable balance reads `unconfirmed` rather than
  as headroom, and the rendered block carries the rate table's date and age. TWO halves are
  NOT closed and are deliberately visible in the block itself: the projection is against the
  plan's CONFIGURED monthly allowance, not what is left of it this month (n8n exposes no usage
  endpoint to an API key — Phase 57 samples the remainder), and D-53-02 records that this
  ceiling DISCLOSES rather than constrains. The operator surface that shows it is 53-03 T2.*
- [x] **GRANT-03**: A grant is **scoped to a named batch**, not to a duration alone. "Everything
  for the next hour" is not expressible; "these 340 contacts, creates included" is.
  *Complete (53-01): a grant cannot be planned over an empty record set, and
  `n8n_arming.arm_for_dispatch`'s own grant branch refuses — before any transport is
  constructed — any record id, domain or workflow id outside the grant's lists
  (`test_write_grant.py::test_a_record_outside_the_grant_is_refused_before_any_transport_call`
  and siblings).*
- [ ] **GRANT-04**: A grant expires on: batch completion, ceiling breach, operator revocation,
  session end, or an unhandled error. Each expiry disarms the backend and is reported.
  *Partial (53-02): the five reasons are named constants (`write_grant.GRANT_04_REASONS`) and
  `close_grant` RAISES on a free-text reason, so every close is reportable. The disarm clause
  is VACUOUS on completion, revocation and session end — per-send `armed_window`s leave no
  window open at close time — and REAL on guardrail B's two paths, which attempt a disarm,
  carry its verdict and close either way. Not closed: `ceiling_breach` has no producer until
  Phase 57, and the surface that REPORTS an expiry to the operator is 53-03.*
  *Partial updated (53-04): the surface that reports an expiry now exists — `backend-control`
  names what closes a grant on its own (completion, session end, error, ceiling breach, two
  consecutive disarm failures) and that a free-text close reason raises rather than being
  accepted; the README lists the same set for the operator. Still not closed: `ceiling_breach`
  has no producer until Phase 57.*
- [x] **GRANT-05**: Revocation mid-run is possible and takes effect at the **next send**
  (re-scoped by the operator 2026-08-25, from "within one chunk boundary"). `chunking.dispatch_plan`
  loops its chunks internally with no grant-aware hook, so a dispatch already running completes its
  remaining chunks under the arm it opened with — at a 2-record chunk ceiling that can be many chunks.
  Chunk-granular revocation would mean making the shared dispatch loop grant-aware and is not in v1.1.
  *Complete (53-02): `write_grant.revoke()` closes the grant and `check_before_send` refuses
  the next send by name. The limitation is pinned by driving a REAL 3-chunk `dispatch_plan`
  with a mid-run revocation — every remaining chunk still goes
  (`test_write_grant.py::test_a_revocation_midway_does_not_stop_a_running_dispatch`), plus a
  signature test that notices if `dispatch_plan` ever gains a `grant` parameter.*
  *Reachability added (53-03): `write_grant.revoke_grant()` is the operator-facing name a
  request maps onto, and it is IDEMPOTENT — an already-closed grant comes back unchanged
  rather than re-closed, which is what stops a plain re-close from overwriting a
  guardrail-B `two_consecutive_disarm_failures` reason with `operator_revocation`. `revoke`
  is kept as an alias over the same implementation. The next-send-not-mid-dispatch scope is
  in the docstring an operator reads, pinned by
  `test_write_grant_surface.py::test_revoke_grants_docstring_states_what_a_revocation_does_not_stop`
  and by a signature test that reddens if `dispatch_plan` ever becomes grant-aware.*
- [ ] **GRANT-06**: No grant can be inferred, defaulted, remembered across sessions, or written
  to disk. Nothing about today's "never persisted" property changes.
  *Partial (53-01): holds for everything 53-01 built — no file, no environment variable, no
  default for an absent grant, pinned by
  `test_write_grant.py::test_nothing_about_a_grant_is_written_to_disk_or_to_the_environment`.
  Stays open until 53-02..04 have shipped their own surfaces under the same prohibition.*
  *Partial updated (53-02): holds for the envelope, the lifetime constants and both
  guardrails — re-pinned by
  `test_write_grant_guardrails.py::test_nothing_a_guardrail_writes_reaches_disk`, and neither
  guardrail is reachable by an env var, a config key or a phrase (T-53-12). 53-03/53-04 still
  owe their own.*
  *Partial updated (53-03): holds over the operator surface too. `init_check` READS the
  settings file and never writes it, never creates it as a side effect of reporting, and never
  migrates a file into having the key — pinned by
  `test_write_grant_surface.py::test_init_check_neither_writes_nor_migrates_a_grant_into_the_settings_file`.
  No default is supplied for the key anywhere (the shipped example carries the JSON boolean
  `false`, asserted by its own test, because `--create` copies the example verbatim), and
  `authorize_send` and `revoke_grant` add no persistence — re-pinned by
  `test_no_grant_and_no_bridge_state_reaches_disk_or_the_environment`. 53-04 still owes its
  own, over the skills and the release.*
  *Partial updated (53-04): holds over this plan's surfaces, which are prose and a version string — nothing written, nothing defaulted, nothing remembered across sessions. The skills state the grant is never written to disk and ends with the conversation, and `test_enrich_before_ingest_skill_contract.py`'s never-written-to-disk pin is untouched.*

### RUN — the batch actually completes

- [x] **RUN-01**: A batch runs ingest → enrichment → HubSpot write end to end with no operator
  input between chunks.
  *61-05: async run shape ships (submit returns a handle without holding a request open,
  progress readable mid-run, resume-or-fail-loudly). Live-observed on one bounded, disarmed
  chunk (execution `12040`) — the first unattended multi-chunk batch is 61-06's, still gated
  on Phase 57's ceilings per D-61-08.*
- [x] **RUN-02**: Chunk failures do not abandon the batch; failed records are collected and
  re-sendable as one well-formed request (today's `failed_batch`, carried through).
  *61-04 + 61-06 (`61-VERIFICATION.md` truth 7): `held_queue.py`/`run_manifest.py` collect held
  and failed rows and `chunking.failed_batch`'s existing re-sendable specification is reused
  unchanged. The association-or-hold contract is enforced with exactly ONE implementation — the
  ingest lane — because the enrichment lane's own contacts-create path downgrades an armed create
  to `review` rather than duplicating the resolve+associate subgraph.
  `tests/n8n/pairPipelineAssociationFlow.test.mjs` asserts the held case is NOT landed.*
- [x] **RUN-03**: Throughput is designed against the measured bounds, not assumed away — the
  2-record request ceiling, the ~100 s response window, and the execution budget. If the
  answer is an async submit-and-poll shape rather than synchronous chunking, that is a
  milestone decision to take deliberately.
  *61-05: async submit-and-poll (substrate 1) selected deliberately over substrate 3 at this
  scale, per 61-01's spike verdict and the operator's checkpoint decision.*
- [x] **RUN-04**: A run reports progress the operator can read while it runs — records done,
  held, failed, spend so far against ceiling.
  *61-05: `run_state.py` reports done/held/failed/spend with the `total = pending+running+
  done+held+failed` invariant asserted.*
- [x] **RUN-05**: A run that would exhaust the monthly execution allowance refuses **before
  starting**, with the arithmetic, and offers a smaller batch.
  *57-01: `write_grant.allowance_headroom`/`ceiling_verdict` sample the monthly remainder and
  `plan_grant` refuses a `CEILING_OVER` batch before anything is armed, with the arithmetic
  named. 57-03: `write_grant.split_for_allowance` makes the refusal concrete — the grant scope
  is projected FROM the split work (never cut in parallel with it, REVIEW-57-H1), and the
  refusal now carries the smaller affordable batch and a named remainder queued for a future,
  separately-authorised run (D-57-04/D-57-05, GRANT-06 preserved).*

### AFTER — what the operator reads instead of watching

- [ ] **AFTER-01**: One end-of-run report: per-record outcome, association outcome, held rows
  named individually with reasons, spend actuals vs ceiling, and the disarm verdict.
  *Partial (57-05): `run_report.build_run_report` joins all five durable stores
  (`written_records`, `run_state`, `run_manifest`, `held_queue`, `remainder_queue`) plus the
  run-audit record, keyed by `(row_id, lane)` so a row with events on two lanes keeps both, and
  renders AFTER-01's five contents in one block — including held/gated rows named individually,
  every cross-store contradiction named rather than resolved, and a `REPORT INCOMPLETE` banner
  when any store degrades. Both lane runbooks call it at end of run, pinned by a test that
  compiles their real code. NOT closed: the pair pipeline's final ingest leg strips `row_id`
  (`extraction.strip_row_id`), so those rows join by `hs_object_id` where one exists and are
  otherwise kept and rendered UNJOINABLE rather than dropped — a known, named gap in the join,
  disclosed in the report's own `gaps`, not a silent one. The report is authorised for its first
  exercise against a real run in Task 4's small operator-supervised batch, run outside this
  phase.*
- [x] **AFTER-02**: Held and failed rows land in a queue that survives the session.
  *61-04 + 61-06 (`61-VERIFICATION.md` truth 10): `held_queue.py` persists through
  `durable_paths._atomic_write_0600` (0600, forbidden-name-refusing), carries the hold reason and
  a per-hold-code resume fingerprint, and is ONE global file rather than per-run — D-61-07's "one
  review queue, cleared in a single pass" is a durable backlog across runs. The end-of-run review
  reuses the existing `approve`/`deny`/`pick`/`email:` decision vocabulary; no second vocabulary
  was invented.*
- [x] **AFTER-03**: The report distinguishes "written" from "would have been written" — a
  gated record must never read as a completed one.
  *57-02: `written_records`/`report_enrichment` widened to an eight-word vocabulary
  (`written`/`write_attempted`/`created_id_unknown`/`written_id_unknown`/`gated`/`held`/
  `failed`/`no_action`), both resolved through one pure `outcome_for_action` function.
  `gated` (`write_blocked`) is distinct from `written`/`write_attempted` on both client
  surfaces, pinned by a cross-module agreement test over all ten backend actions.*
  *57-05: the operator-facing half closes here. `run_report`'s rendered block imports and reuses
  those same outcome words rather than restating a third copy, and a test asserts the `gated`
  and `written` renderings are distinct strings. Both lane runbooks now state AFTER-03's rule
  where the operator actually reads it: a gated row would have been written and is recoverable
  by opening a grant and re-sending — never reported as a failure, and never as a completed
  write.*

## Added after the Phase 53 walk (operator, 2026-08-25)

Both came from the operator saying ordinary sentences and hitting a wall. They are recorded
as their own phases (58, 59) because each is larger than the fix that surfaced it.

> **Correction, 2026-08-30.** Only the INPUT half kept its number: Phase 58 shipped it
> (complete 2026-08-26). **Phase 59 was reassigned** to "Frictionless write path" (complete
> 2026-08-29), so the SUGGEST block below has NO phase number and is not scheduled — see
> `v1.1-ROADMAP.md` § Phase 59 for the same note. INPUT-05 was added later (2026-08-30) and
> closed by Phase 61.

### INPUT — take what the operator actually has

- [x] **INPUT-01**: A company can be named by **anything the operator holds**: a screenshot of
  a website or a search-results page, a pasted block of text, a URL of any kind, a name with
  no domain at all. The contact lane has had this since Phase 35 (`extraction.md`'s adapters
  for pasted text, foreign JSON, a public URL, operator screenshots). The company lane has
  never had it.
  Closed 2026-08-26 by plans 58-01, 58-05, 58-06 (all complete). 58-06's own contribution: a
  disagreement between providers about a fact that can disqualify a company (starting with the
  exact region-conflict shape that caused a false Non-ANZ veto in execution 11983) can no
  longer resolve to a confident wrong answer — it is withheld, flagged, and routed to the
  existing judge, so the operator's disagreement surfaces as a disagreement rather than a
  silent misclassification. Operator-accepted 2026-08-26 (Task 4).
- [ ] **INPUT-02**: When the input carries no usable domain, the system **finds one** rather
  than asking the operator to. The backend already has the tool — `Claude Web Research` in
  the companies branch — and it is already used for org-type and content signals. Researching
  a company's own website from its name, or from a LinkedIn page, is the same call.
  **Left open — residual recorded 2026-08-26** (`58-SPIKE-VERDICT.md`, operator decision
  `defer-residual`): the backend research node was not extended to seek a domain this phase.
  Claude-in-conversation already proposes a domain from what it sees in most cases (free,
  instant), and the operator confirms/corrects/denies it — the gap is rows where Claude cannot
  confidently propose a domain AND the operator cannot supply one; those fall to the
  accept-by-name path (0.16.0) rather than a backend-researched domain. Carried forward to a
  later phase.
- [x] **INPUT-03**: A researched domain is **confirmed before it is written**, not accepted
  silently. Getting this wrong creates a company under the wrong domain, which is the dedupe
  anchor for everything after it.
  Closed 2026-08-26 by plans 58-02, 58-03 (both complete).
- [x] **INPUT-05**: A **contact** identified by a strong identity key alone — a LinkedIn URL, an
  email — resolves through **match, then enrich**, without the operator being asked for fields
  the backend does not need. Added 2026-08-30 after walk run 4 failed on exactly this
  (`53-WALK-RECORD-3.md` FINDING D): the plugin demanded a company before it would act, while
  `n8n/code/resolveIdentity.js:76-78` treats `linkedin_url` as a **strong** HubSpot match key
  (same tier as email) and `n8n/code/lushaRequest.js:79-91` accepts a Lusha v3 enrich body
  carrying `linkedinUrl` alone. Both operations the plugin refused were keyed on what the
  operator had already supplied.
  **This does not loosen the no-invention rule** — the operator supplies the key, a licensed
  provider returns sourced fields, the operator confirms. A searched-and-sourced value is not an
  invented one; the fix is separating those two, not weakening either. `extraction.md`'s verbatim
  no-invention sentence stays as-is.
  **Operator priority, stated 2026-08-30:** *"we are prioritising speed and efficiency, and
  relying on the plugin to propose best effort completion using the services n8n gives it in the
  backend"* — an exception per ingestion is the failure mode, not the safety net.
  Owned by **Phase 61**. Closed 2026-08-30 by plans 61-02 (backend linkedin match lane) and
  61-03 (front-end identity acceptance: `required_identity.any_of` gained `linkedin_url` as a
  third group in both YAML copies and `columnMap.js`, the rejection message is now derived from
  config, and a waterfall-found value is proposed through the existing D-59-08
  resolutions/provider_result loop) — both plans complete.
- [x] **INPUT-04**: A refusal is a last resort and must always name what would make it work.
  *"A blanket refusal is not useful because the operator does not want to research that"*
  (operator, 2026-08-25). The guard that survives is **never silently invent a domain** — a
  profile URL is dropped, never passed through as one — not "go and find one yourself".
  Partially shipped 0.16.0: a company with a name and an unusable URL is now accepted and
  looked up by name.
  Closed 2026-08-26 by plans 58-01, 58-03, 58-04 (all complete).

### VOCAB — the operator never has to speak the system's language

Found repeatedly across the 2026-08-25 walk, each time by the operator rejecting a script
written in the implementer's register.

- [ ] **VOCAB-01**: An operator never has to know the word "grant", or ask for one by name.
  They say what they want done — *"update John Tsatsimas from Football NSW"* — and the SYSTEM
  offers the permission it needs, at the moment it needs it: *"to update him I need permission
  to write to HubSpot — just his record. OK?"*. One yes. Today the operator must open a grant
  explicitly, which is the system making its own internals the user's vocabulary.
- [ ] **VOCAB-02**: No step of any documented walk, runbook or skill instruction may require
  words a non-technical operator would not say unprompted. "Enrichment lane", "no creates",
  "record id", "dispatch", "arm" are the system's words, not theirs.
- [ ] **VOCAB-03**: Where the system must name a constraint, it names the CONSEQUENCE in the
  operator's terms, not the mechanism: not *"creates are excluded"* but *"I won't add anyone
  new, only fill in people already there"*.
- [x] **VOCAB-05**: **The arming phrase dies.** *(implemented 2026-08-25, plugin 0.17.0 — walk still to confirm the wording works, per VOCAB-04.)* An operator answers the question they were
  asked, in their own words — "yes", "go ahead", "do it", "please" — and that arms the send it
  answers. Requiring the literal string "arm the enrichment" makes the operator speak the
  system's language at the exact moment they are trying to say yes, and it rejected a plain
  "yes" that answered the system's own "Proceed?" (observed live, 2026-08-25 walk).

  **The safety property that must survive is NOT the wording — it is that consent is
  unambiguous and attached.** What made the phrase safe was never its spelling: it was that a
  casual "ok" could not become a write. That is preserved by binding the affirmative to
  *this send's shown consequence in the same turn*:
    - an affirmative that answers the send proposal just shown → arms that send, nothing else;
    - an affirmative floating free, answering nothing, or answering a different question → does
      NOT arm; ask once more, naming what will happen;
    - ambiguity resolves to not-armed, always. `armed` still has no default in code
      (`dispatch()` raises without it) — that is the structural guarantee and it does not move.

  Scope: `enrich-records`, `contact-upload`, `enrich-before-ingest`, `review-triage`, and the
  phrase pins in `test_enrich_skill_contract.py`,
  `test_enrich_before_ingest_skill_contract.py`, `test_preingest_preview.py`. Those pins are
  rewritten in place with the reason recorded, never deleted — the same discipline as the
  arm/probe parity pin and the D-53-05 ordering pin.

- [ ] **VOCAB-04**: The test for all three is a walk transcript, not a review: if the operator
  has to be told what to type, the wording failed.

### SUGGEST — the contacts the operator did not name

> **SUGGEST-01..05 are PHASE 62** (numbered 2026-08-30 by the operator, scheduled after
> Phase 57). They spent a period unnumbered after "Phase 59" was reassigned to the as-built
> Frictionless write path — scope that was real but that no index pointed at. Still open.

- [ ] **SUGGEST-01**: After companies are ingested or enriched with no contacts named, the
  system **suggests contacts worth enriching** rather than stopping. An enriched company with
  nobody at it is not a lead.
- [ ] **SUGGEST-02**: For a bulk company list the suggestion is **categorical, not per-record**
  — the operator picks roles ("CEO", "CMO", "Head of Broadcast") once and the system applies
  them across the batch. Asking per company does not scale, which is the same complaint that
  started this milestone.
- [ ] **SUGGEST-03**: The role vocabulary is **derived from this portal's own contact records**,
  not invented and not a generic B2B list. Sample the `jobtitle` values already in HubSpot,
  cluster them, and offer the ones that actually recur — the buying committee Lightning Visuals
  actually sells to, evidenced rather than assumed. `scripts/inventory_org_type_values.py` is
  the existing pattern for inventorying a property's live values.
- [ ] **SUGGEST-04**: Suggested contacts are **proposed, never auto-created**. They are people
  who are not in HubSpot yet, so they land through the existing pre-ingest path with its match
  lane, its held rows and its association contract — a suggestion must not become a silent
  write.
- [ ] **SUGGEST-05**: The cost of a suggestion round is shown before it is spent. Provider
  people-search by company + title (Apollo and ZoomInfo both support it) is a per-company
  call, so a 300-company list is 300 calls and must be priced as one decision, not discovered
  mid-run.

## Decisions taken (operator, 2026-08-25)

- **D-1.1-01** — the grant is **operator-openable in Claude**: an admin enables the capability
  once in the settings file, the operator opens a session grant in conversation. The
  `ALLOW_N8N_ARM` env var stops being the authority for interactive runs (it remains the
  authority for headless/cron paths, which have no operator to confirm anything). This is what
  makes G-2 tractable.
- **D-1.1-02** — **grant first, then a single async pass**: the grant opens before the run, so
  each record is enriched once and written in the same pass (G-3's double spend disappears),
  and the run submits-and-polls rather than blocking on the ~100 s response window.
- **D-1.1-03** — the first slice is the **full pair pipeline**, creates included. Largest blast
  radius, so the ceiling and post-run-proof work ships inside the milestone.

Roadmap: `.planning/milestones/v1.1-ROADMAP.md` (~~phases 53–57~~ **phases 53–61**, corrected
2026-08-30 — 58, 59 and 61 were added after these decisions were taken, and 55/56 were folded
into 61 by D-61-08).

## Decisions still open

> **Status, 2026-08-30.** #1 was settled by Phase 53: the grant is **client-side**, a plain
> JSON-shaped dict held in the conversation — no file, no env var, no default (GRANT-06 /
> D-53-03). #5 is Phase 57's work by design (it owns the sampled allowance). #2, #3 and #4 are
> **not** recorded as decided anywhere this pass could find; treat them as still open going into
> Phase 57, which is where #3's "what proves after the fact that nothing outside the batch was
> touched" already sits as AFTER-01/AFTER-03.

1. **Where the grant lives.** Client-side (the plugin holds it for the conversation) or
   backend-side (a longer armed window with a batch allowlist)? The existing
   `scripts/scheduled_arm.py` is prior art for the second: it already runs an unattended armed
   window with a 2-record chunk cap for the SJ-3 poller.
2. **Creates under a standing grant.** `ALLOW_HUBSPOT_CREATE` is a separate key today. Does a
   session grant include creation by default, or does creation stay a per-batch decision?
3. **Blast radius if the allowlist is wrong.** A 340-record allowlist is 340 records the
   backend may write unattended. What re-reads it, and what proves after the fact that nothing
   outside the batch was touched?
4. **Interaction with the schedulers.** SJ-1/SJ-2/SJ-3 and the dedupe/review jobs share the
   same execution budget. A session grant must not starve them, or must explicitly pause them.
5. **Where the ceiling numbers come from.** `config/cost_rates.json` is dated (measured
   2026-07-30) and n8n exposes no usage endpoint to an API key — the execution budget has to be
   sampled, as `n8n_cadence` already does.

## Open questions for the operator

- What batch size does "at scale" mean in practice — hundreds per session, or thousands?
- Who may open a session grant: any operator, or a named role?
- On a partial run (ceiling hit at record 200 of 340), continue next session automatically or
  wait for a fresh grant?
- Is a nightly unattended run acceptable, or must a human always be present at the start?

## Non-goals

- Removing the record-scoped allowlist, in any form.
- A persisted or cross-session grant.
- Auto-resolving held rows to keep a batch moving.


### User Decisions (CONTEXT.md)
# Phase 60: Review-lane authority - Context

**Gathered:** 2026-09-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Give the review lane (approving or rejecting one flagged HubSpot record) the same
once-per-session grant authority the enrichment and contact-ingest lanes already have,
closing BOTH manual round trips a human currently has to do to approve a single flagged
record: (1) an admin setting `ALLOW_REVIEW_SUBMIT=true` as a shell env var on their own
machine, and (2) a separate admin-run deploy that bakes `ALLOW_HUBSPOT_REVIEW_WRITES` plus
the record's id into the deployed `LV Review Decision (Cloud)` n8n workflow.

This phase does NOT touch the ingest → enrich → write path itself, does not change
enrichment or contact-ingest behavior beyond adding "review" as a third grantable lane, and
does not change what a reviewer sees before approving (the dry-run exact-write preview via
`preview_decision` stays exactly as it is — deliberately ungated, unaffected by any of this).

</domain>

<decisions>
## Implementation Decisions

### Authority model

- **D-60-01:** Review-lane approval authority reverses Phase 30-01's deliberate separation
  (D-02/D-08e) between dispatch grants and review writeback. Chosen over (a) an admin
  config key that keeps the two authorities separate, and (c) accepting the current
  two-round-trip flow as correct for occasional triage. — **Reversibility:** costly —
  undoing this means re-excluding `ALLOW_HUBSPOT_REVIEW_WRITES` from whatever grantable-lane
  set this phase builds, and re-standing-up `ALLOW_REVIEW_SUBMIT` as review's sole
  independent gate (D-60-04 retires it).
- **D-60-02:** A single grant covers all three lanes together (enrichment, contacts,
  review) — opening one grant authorizes all three, not a separate deliberate "yes" per
  lane. This mirrors D-53-05's existing precedent (one grant already spans enrichment +
  contacts) rather than inventing a new per-lane consent model. — **Reversibility:**
  costly — separating review back into its own deliberately-opened grant would need
  re-adding a lane-selection step to whatever grant-opening flow this phase builds.
- **D-60-03:** The grant's existing record-scoping (ids/domains named when it is opened)
  bounds which flagged records can be approved via review, exactly the same "narrower than
  the grant, never wider" rule dispatch sends already follow (`write_grant.authorize_send`).
  A grant opened over records A/B/C cannot approve a review decision on record D. This is
  what keeps D-60-02's combined-lane choice from being a blank check on every flagged record
  in the system — only records already named in the grant get review authority too.
  — **Reversibility:** reversible.
- **D-60-04:** The client-side `ALLOW_REVIEW_SUBMIT` shell-env kill switch
  (`review_decision.py:SUBMIT_ENV_VAR`) is retired. Grant-authorization
  (`write_grant.authorize_send` / `authorize_ungranted_send`) becomes the gate
  `submit_decision()` checks instead — the same authorization call enrichment already uses,
  not a second copy of the check. — **Reversibility:** reversible.

### Round-trip closure — dynamic backend arm

- **D-60-05:** This phase also wires `ALLOW_HUBSPOT_REVIEW_WRITES` into the same dynamic
  arm-window mechanism (`n8n_arming.py`) dispatch already uses, so a grant's review decision
  needs zero manual admin deploy. Without this, D-60-01/D-60-02 would remove the friction
  that mattered least (a client-side env var) while leaving the friction that mattered most
  (a human running a deploy) untouched. — **Reversibility:** reversible — additive; the
  existing deploy-time-baked path (`deploy_n8n_workflows.py::enable_baked_flags`) is not
  removed, only bypassed when a grant arms dynamically instead.
- **Load-bearing implementation note (Claude's discretion on the mechanism, not asked as a
  question):** `ALLOW_HUBSPOT_REVIEW_WRITES` already shares the SAME `TEST_RECORD_IDS` /
  `TEST_RECORD_DOMAINS` allowlist as the dispatch flags in the deployed workflow node — it
  is one of `n8n_arming.OVERLAYABLE_FLAGS`'s five names, just never included in
  `DISPATCH_FLAGS`. A review arm window must set `ALLOW_HUBSPOT_REVIEW_WRITES=true` on the
  allowlisted records **without** setting `ALLOW_HUBSPOT_RECORD_WRITES=true` for them —
  arming review on a record must never incidentally open dispatch-write eligibility for
  that same record. The separate `WRITE_ENABLING_FLAGS` booleans already make this safe by
  construction (the shared allowlist alone authorizes nothing without its own boolean); the
  planner should add a `REVIEW_FLAGS` (or similarly named) constant analogous to
  `DISPATCH_FLAGS`, not extend `DISPATCH_FLAGS` itself.
- **`write_grant.LANES` currently maps 2 lane names → 2 workflow names**
  (`{"enrichment": ..., "contacts": ...}`, `write_grant.py:83-86`). Add `"review"` →
  `"LV Review Decision (Cloud)"` (the workflow's actual `name` field, confirmed live from
  `n8n/wf_review_decision_cloud.json`; no existing Python constant names it yet — the
  planner should add one, e.g. `REVIEW_WORKFLOW_NAME`, mirroring
  `ENRICHMENT_WORKFLOW_NAME` / `CONTACT_INGEST_WORKFLOW_NAME`'s placement pattern).
- **Recorded-edit discipline required, matching D-53-05's own precedent (the roadmap
  explicitly calls this out):** `write_grant.py:64-82`'s comment block documents WHY the
  review lane is currently excluded from `LANES` (30-01 D-02/D-08e). This phase reverses
  that decision — the comment must be AMENDED with a dated addendum explaining the reversal
  and why (mirroring the D-59-07 amendment already sitting a few lines below it in the same
  file), never silently deleted or rewritten as if the old design never existed.

### Arm granularity

- **D-60-06:** One arm window covers a whole batch of review decisions in a session,
  rather than opening and disarming a fresh window for every single decision. Chosen over
  per-decision arm/disarm (which would exactly mirror how each enrichment SEND already
  opens its own window under `authorize_send`) because triaging several flagged records in
  one sitting shouldn't cost an arm/disarm round trip to n8n per record.
  — **Reversibility:** costly — a batch-scoped window's lifecycle (open once, handle a
  disarm-on-crash mid-batch, handle what happens if one decision in the batch fails) is
  more involved to build than per-decision arm/disarm; reversing to per-decision later means
  re-deriving that lifecycle from scratch rather than trimming an existing one.
- **Note for planner:** D-60-03's record-scoping still applies per decision inside the
  batch — the batch arm's allowlist is fixed to the grant's own record list at open time
  (per D-60-02/D-60-03), it does not grow as the operator triages records one by one.

### Answered during planning (raised by 60-RESEARCH.md's open questions, 2026-09-01)

- **D-60-07:** A `reject` decision works with **no grant open**. This preserves, symmetrically,
  the exact property the retired `ALLOW_REVIEW_SUBMIT` carve-out existed for
  (`review_decision.py`'s `is_undoing`): a closed authority must never be able to strand a
  flagged record mid-decision. A reject promotes nothing — it records a reason and leaves the
  record in the queue — so it carries none of the risk the grant exists to gate. The session arm
  (`review_armed`) is unaffected and still required, exactly as it is today for both approve and
  reject. **The `is_undoing` carve-out therefore SURVIVES D-60-04's retirement of the env var —
  it is re-pointed at the grant check, not deleted.** — **Reversibility:** reversible.
- **D-60-08:** Review-lane writes **DO** appear in the per-run `written_records-<run_id>.json`
  artifact (D-59-07/D-59-09), against 60-RESEARCH.md's own recommendation to treat it as out of
  scope — operator's call, 2026-09-01. Rationale: one artifact should answer "what did this
  session write to HubSpot" across all three lanes now that all three are grantable.
  — **Reversibility:** costly — review decisions go through `review_decision.submit_decision`,
  never `chunking.dispatch_plan`, so this is new plumbing rather than a reused call site;
  removing it later means unpicking a second writer of that artifact.
  **Constraints the planner must carry over from the artifact's own decisions:** the run must be
  keyed by a `run_id` the same way a dispatch run is (D-59-09: one artifact per run, readers glob
  and union — never a shared append); and per D-59-10 a written-records failure must **never**
  stop or abort a review write, it is recorded in the outcome and surfaced loudly instead.

### Claude's Discretion

- The exact mechanism for a `REVIEW_FLAGS`-style constant and where the review-specific
  arm/disarm wrapper function lives (new function in `n8n_arming.py`, or a `write_grant.py`
  call site composing the existing generic overlay primitives directly) — both are
  consistent with the existing architecture; pick whichever produces the smaller diff.
- Whether the batch arm's disarm-on-crash path reuses `n8n_arming.armed_window`'s existing
  context-manager guarantee (arm → run caller's decisions → disarm, including on the
  exception path) as-is, or needs a review-specific variant — the existing
  `armed_window.__exit__`'s "never swallow the body's exception, still disarm" guarantee
  should carry over unchanged; only the flags set at arm/disarm time differ from dispatch.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Why this phase exists and what it must not re-litigate
- `.planning/phases/59-frictionless-write-path/59-CONTEXT.md` § D-59-03 — the operator
  decision that split this phase out, the three roadmap options, and why deleting
  `ALLOW_REVIEW_SUBMIT` with nothing behind it is explicitly not an option.
- `.planning/ROADMAP.md` (search "Phase 60: Review-lane authority") — the phase's
  roadmap entry, including the exact three options and the "not an option" constraint.

### Current review-lane authority code (all three gates, as they exist today)
- `operator-claude-plugin/scripts/review_decision.py` — the client-side module this phase
  changes. Full docstring documents all three current gates (`ALLOW_REVIEW_SUBMIT`, the
  session arm `review_armed`, backend `ALLOW_HUBSPOT_REVIEW_WRITES`) and D-01/D-04's
  requirement that the session arm never persist to disk or outlive the session — that
  constraint is unaffected by folding review into a grant, since grants themselves are
  also session-scoped, not persisted.
- `operator-claude-plugin/scripts/n8n_arming.py` — the dynamic arm/disarm overlay
  mechanism this phase extends to review. `OVERLAY_DISABLED_LITERALS` (5 flags, including
  `ALLOW_HUBSPOT_REVIEW_WRITES`), `DISPATCH_FLAGS` (the 4 dispatch already uses),
  `WRITE_ENABLING_FLAGS`, `ALLOWLIST_FLAGS`, and the `armed_window` context manager (arm,
  run caller's dispatch, guaranteed disarm including on the exception path).
- `operator-claude-plugin/scripts/write_grant.py` — the grant machinery this phase folds
  review into. `LANES` (lines 64-86, including the comment block D-60-01/D-60-05 requires
  amending), `authorize_send`/`authorize_ungranted_send` (the authorization calls
  `submit_decision` should route through per D-60-04), `plan_grant`/`open_grant`, the
  per-send record-scoping this phase's D-60-03 extends to review.
- `n8n/wf_review_decision_cloud.json` — the deployed workflow this phase's dynamic arm
  targets (`name: "LV Review Decision (Cloud)"`). Never hand-edit; regenerate via
  `scripts/build_cloud_workflows.py` per the project's standing rule.

### Skill-side entry point (likely touched during planning/execution)
- `operator-claude-plugin/skills/review-triage/` — the skill an operator invokes to
  triage flagged records; wherever it currently checks `ALLOW_REVIEW_SUBMIT`/session-arm
  and calls `submit_decision` is where the new grant-authorization call replaces the old
  env-var check.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `write_grant.authorize_send` / `authorize_ungranted_send` — already return the identical
  `{armed, workflow_id, grant, refusal, detail}` shape regardless of which authorized the
  send; the review lane's decision call can use the exact same pattern enrichment's dispatch
  already does (see `operator-claude-plugin/skills/enrich-records/SKILL.md` step 8's code
  block for the canonical shape).
- `n8n_arming.armed_window` — the context-manager arm/dispatch/disarm lifecycle, including
  the guaranteed-disarm-on-exception behavior this phase's batch arm needs.

### Established Patterns
- Per-send/per-decision record-scoping ("narrower than the grant, never wider") — D-60-03
  extends this exact rule to review rather than inventing a new one.
- Recorded-edit discipline (D-53-05's own precedent) for amending a comment that documents
  a now-reversed design decision, rather than deleting it — D-60-05 requires this for
  `write_grant.py:64-82`.

### Integration Points
- `write_grant.LANES` gains a third entry (`"review"`).
- `n8n_arming.py` gains a `REVIEW_FLAGS`-analog constant and (per Claude's discretion above)
  a review-specific arm wrapper.
- `review_decision.py::submit_decision` loses its `ALLOW_REVIEW_SUBMIT` check
  (`submit_enabled()`) and gains a grant-authorization check in its place.

</code_context>

<specifics>
## Specific Ideas

No UI/UX-level specifics were raised — this phase is authorization plumbing, not a
reviewer-facing workflow change. The exact-write preview (`preview_decision`) stays exactly
as it is today; nothing about what a reviewer sees before approving changes.

</specifics>

<deferred>
## Deferred Ideas

None raised during this discussion — no scope creep occurred; all three areas stayed within
the phase's authorization-plumbing boundary.

### Reviewed Todos (not folded)
- `2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md` — surfaced by todo matching at
  score 0.2 (below the 0.4 fold threshold); already noted as unrelated to this phase's
  subject in `59-CONTEXT.md`'s own deferred section. Left in the backlog.

</deferred>

---

*Phase: 60-review-lane-authority*
*Context gathered: 2026-09-01*


### Research Findings
# Phase 60: Review-lane authority - Research

**Researched:** 2026-09-01
**Domain:** Internal authorization plumbing (Python plugin client + n8n Cloud workflow write-safety gate) — no new external dependency, no UI, no HubSpot schema change.
**Confidence:** HIGH

## Summary

This phase is pure composition of machinery that already exists and is already proven live: `write_grant.py`'s grant/lane model, `n8n_arming.py`'s bidirectional overlay-and-verify setter, and the review workflow's own write-safety gate. Every one of the five specific unknowns the phase brief asked this research to close was resolved by reading the actual files, not by inference — and the answer to all five is the same shape: **the review lane already declares its write-safety constants in the identical form the dispatch lanes do, using the identical shared gate function, so D-60-05's dynamic arm can be built by extending the *client-side* Python (`write_grant.LANES`, a new `n8n_arming.REVIEW_FLAGS`-style constant, a new arm/disarm pair or parameterization) with ZERO changes to `n8n/wf_review_decision_cloud.json` and ZERO changes to `scripts/build_cloud_workflows.py`'s generated JS.**

The one thing this research found that CONTEXT.md's own analysis did not name: **Guardrail A (the dirty-backend refusal `write_grant.guardrail_a` runs before opening any grant) is currently blind to a stuck-open `ALLOW_HUBSPOT_REVIEW_WRITES`, on every lane, including the review lane itself, once it exists.** Two module-level constants — `write_grant.py`'s own local `WRITE_ENABLING_FLAGS` tuple (line 1556, DELIBERATELY 2 items, dispatch-only) and `read_live_write_state`'s per-lane read loop (line 1599, iterates `n8n_arming.DISPATCH_FLAGS`, 4 items) — never read or report `ALLOW_HUBSPOT_REVIEW_WRITES` at all. Today this is inert because review has no `workflow_ids` entry for Guardrail A to iterate over. The moment `"review"` joins `LANES`, Guardrail A will read the review workflow's dispatch flags (harmlessly — the review workflow also declares them, unused) but will **never notice a previous crashed session left `ALLOW_HUBSPOT_REVIEW_WRITES=true` armed on it.** This is exactly the failure category D-53-03 built Guardrail A to catch, and closing it is now in scope by consequence of D-60-01/D-60-05 even though CONTEXT.md's decisions do not name it directly. See Common Pitfalls.

**Primary recommendation:** Do the arm/disarm split by **parameterizing**, not duplicating: `n8n_arming.arm_for_dispatch`/`disarm`/`armed_window` are 90% generic (`n8n_control.apply_mutation` + `set_write_safety` + `n8n_read.read_write_safety` already take a `targets`/`flags` argument or can trivially be threaded one). Add `REVIEW_FLAGS = ("ALLOW_HUBSPOT_REVIEW_WRITES", "TEST_RECORD_IDS", "TEST_RECORD_DOMAINS")` next to `DISPATCH_FLAGS`, and either (a) give `arm_for_dispatch`/`disarm` a `flags=DISPATCH_FLAGS` keyword the review path overrides, or (b) add a thin `arm_for_review`/`disarm_review` pair that composes the same primitives with `REVIEW_FLAGS` and a `{"ALLOW_HUBSPOT_REVIEW_WRITES": True, ...}` target (no `allow_create` concept on this lane at all). Widen `write_grant.py`'s own dirty-backend detection (`WRITE_ENABLING_FLAGS` local tuple + `read_live_write_state`'s flag loop) to also read `ALLOW_HUBSPOT_REVIEW_WRITES`, and update the two hard-coded test fixtures this will touch (see Common Pitfalls and Validation Architecture).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-60-01:** Review-lane approval authority reverses Phase 30-01's deliberate separation
  (D-02/D-08e) between dispatch grants and review writeback. Chosen over (a) an admin
  config key that keeps the two authorities separate, and (c) accepting the current
  two-round-trip flow as correct for occasional triage. — **Reversibility:** costly —
  undoing this means re-excluding `ALLOW_HUBSPOT_REVIEW_WRITES` from whatever grantable-lane
  set this phase builds, and re-standing-up `ALLOW_REVIEW_SUBMIT` as review's sole
  independent gate (D-60-04 retires it).
- **D-60-02:** A single grant covers all three lanes together (enrichment, contacts,
  review) — opening one grant authorizes all three, not a separate deliberate "yes" per
  lane. This mirrors D-53-05's existing precedent (one grant already spans enrichment +
  contacts) rather than inventing a new per-lane consent model. — **Reversibility:**
  costly — separating review back into its own deliberately-opened grant would need
  re-adding a lane-selection step to whatever grant-opening flow this phase builds.
- **D-60-03:** The grant's existing record-scoping (ids/domains named when it is opened)
  bounds which flagged records can be approved via review, exactly the same "narrower than
  the grant, never wider" rule dispatch sends already follow (`write_grant.authorize_send`).
  A grant opened over records A/B/C cannot approve a review decision on record D. This is
  what keeps D-60-02's combined-lane choice from being a blank check on every flagged record
  in the system — only records already named in the grant get review authority too.
  — **Reversibility:** reversible.
- **D-60-04:** The client-side `ALLOW_REVIEW_SUBMIT` shell-env kill switch
  (`review_decision.py:SUBMIT_ENV_VAR`) is retired. Grant-authorization
  (`write_grant.authorize_send` / `authorize_ungranted_send`) becomes the gate
  `submit_decision()` checks instead — the same authorization call enrichment already uses,
  not a second copy of the check. — **Reversibility:** reversible.

- **D-60-05:** This phase also wires `ALLOW_HUBSPOT_REVIEW_WRITES` into the same dynamic
  arm-window mechanism (`n8n_arming.py`) dispatch already uses, so a grant's review decision
  needs zero manual admin deploy. Without this, D-60-01/D-60-02 would remove the friction
  that mattered least (a client-side env var) while leaving the friction that mattered most
  (a human running a deploy) untouched. — **Reversibility:** reversible — additive; the
  existing deploy-time-baked path (`deploy_n8n_workflows.py::enable_baked_flags`) is not
  removed, only bypassed when a grant arms dynamically instead.
- **Load-bearing implementation note (Claude's discretion on the mechanism, not asked as a
  question):** `ALLOW_HUBSPOT_REVIEW_WRITES` already shares the SAME `TEST_RECORD_IDS` /
  `TEST_RECORD_DOMAINS` allowlist as the dispatch flags in the deployed workflow node — it
  is one of `n8n_arming.OVERLAYABLE_FLAGS`'s five names, just never included in
  `DISPATCH_FLAGS`. A review arm window must set `ALLOW_HUBSPOT_REVIEW_WRITES=true` on the
  allowlisted records **without** setting `ALLOW_HUBSPOT_RECORD_WRITES=true` for them —
  arming review on a record must never incidentally open dispatch-write eligibility for
  that same record. The separate `WRITE_ENABLING_FLAGS` booleans already make this safe by
  construction (the shared allowlist alone authorizes nothing without its own boolean); the
  planner should add a `REVIEW_FLAGS` (or similarly named) constant analogous to
  `DISPATCH_FLAGS`, not extend `DISPATCH_FLAGS` itself.
- **`write_grant.LANES` currently maps 2 lane names → 2 workflow names**
  (`{"enrichment": ..., "contacts": ...}`, `write_grant.py:83-86`). Add `"review"` →
  `"LV Review Decision (Cloud)"` (the workflow's actual `name` field, confirmed live from
  `n8n/wf_review_decision_cloud.json`; no existing Python constant names it yet — the
  planner should add one, e.g. `REVIEW_WORKFLOW_NAME`, mirroring
  `ENRICHMENT_WORKFLOW_NAME` / `CONTACT_INGEST_WORKFLOW_NAME`'s placement pattern).
- **Recorded-edit discipline required, matching D-53-05's own precedent (the roadmap
  explicitly calls this out):** `write_grant.py:64-82`'s comment block documents WHY the
  review lane is currently excluded from `LANES` (30-01 D-02/D-08e). This phase reverses
  that decision — the comment must be AMENDED with a dated addendum explaining the reversal
  and why (mirroring the D-59-07 amendment already sitting a few lines below it in the same
  file), never silently deleted or rewritten as if the old design never existed.

- **D-60-06:** One arm window covers a whole batch of review decisions in a session,
  rather than opening and disarming a fresh window for every single decision. Chosen over
  per-decision arm/disarm (which would exactly mirror how each enrichment SEND already
  opens its own window under `authorize_send`) because triaging several flagged records in
  one sitting shouldn't cost an arm/disarm round trip to n8n per record.
  — **Reversibility:** costly — a batch-scoped window's lifecycle (open once, handle a
  disarm-on-crash mid-batch, handle what happens if one decision in the batch fails) is
  more involved to build than per-decision arm/disarm; reversing to per-decision later means
  re-deriving that lifecycle from scratch rather than trimming an existing one.
- **Note for planner:** D-60-03's record-scoping still applies per decision inside the
  batch — the batch arm's allowlist is fixed to the grant's own record list at open time
  (per D-60-02/D-60-03), it does not grow as the operator triages records one by one.

### Claude's Discretion

- The exact mechanism for a `REVIEW_FLAGS`-style constant and where the review-specific
  arm/disarm wrapper function lives (new function in `n8n_arming.py`, or a `write_grant.py`
  call site composing the existing generic overlay primitives directly) — both are
  consistent with the existing architecture; pick whichever produces the smaller diff.
- Whether the batch arm's disarm-on-crash path reuses `n8n_arming.armed_window`'s existing
  context-manager guarantee (arm → run caller's decisions → disarm, including on the
  exception path) as-is, or needs a review-specific variant — the existing
  `armed_window.__exit__`'s "never swallow the body's exception, still disarm" guarantee
  should carry over unchanged; only the flags set at arm/disarm time differ from dispatch.

### Deferred Ideas (OUT OF SCOPE)

None raised during this discussion — no scope creep occurred; all three areas stayed within
the phase's authorization-plumbing boundary. One reviewed-but-not-folded todo:
`2026-08-04-sweep-crontab-pins-a-versioned-plugin-path.md` (unrelated subject, left in the
backlog).

</user_constraints>

<phase_requirements>
## Phase Requirements

None mapped. `milestones/v1.1-REQUIREMENTS.md` carries no review-lane requirement ID
[VERIFIED: .planning/milestones/v1.1-REQUIREMENTS.md — grepped for "review", no G-/REQ-ID
governs this lane]. This phase is driven entirely by `59-CONTEXT.md` § D-59-03 and
`60-CONTEXT.md`'s D-60-01..06, reproduced verbatim above.
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Grant authority / lane resolution | Plugin client (Python, operator's machine) | — | `write_grant.py` never touches HubSpot directly; it authorizes and arms |
| Dynamic write-safety overlay (arm/disarm) | Plugin client → n8n Cloud API (PUT workflow) | — | `n8n_arming.py` rewrites deployed JS `const` literals via the n8n management API, never the webhook path |
| Write-safety gate evaluation | n8n Cloud (deployed workflow) | — | `_writeSafetyAllows()`, baked into every write-gate Code node, evaluated at request time inside n8n — this phase does not touch it |
| Review decision computation (`buildReviewDecision`) | n8n Cloud (deployed workflow) | — | `n8n/code/reviewDecision.js`, inlined via `scripts/build_cloud_workflows.py`; unaffected by this phase |
| Operator consent / conversation UX | Plugin skill (`review-triage/SKILL.md`) | Plugin client (`review_decision.py`) | The skill decides what to say and when to call `submit_decision`; the module decides whether the call is gated |

## Standard Stack

No new library, package, or service is introduced by this phase. It composes existing
in-repo Python modules (`write_grant.py`, `n8n_arming.py`, `review_decision.py`,
`n8n_read.py`, `n8n_control.py`) and touches zero external dependencies.

**Installation:** none.

## Package Legitimacy Audit

Not applicable — this phase installs no external package.

## Architecture Patterns

### System Architecture Diagram — current (two independent gates) vs. this phase's target

```
CURRENT (two disconnected authorities):

  Operator "approve record X"
        |
        v
  review-triage skill --yes--> review_decision.submit_decision()
        |                              |
        | checks (client-side)         | checks
        v                              v
  ALLOW_REVIEW_SUBMIT (shell env,   review_armed (per-decision,
  admin-only, machine-local)        conversation-scoped)
        |                              |
        +------------------+-----------+
                           v
              POST hubspot/review/decision
                           |
                           v
          n8n: Build Review Decision node
          computes _writeSafetyAllows("review", id, domain)
                           |
                           v
          ALLOW_HUBSPOT_REVIEW_WRITES (baked constant,
          only settable by an ADMIN-RUN DEPLOY today)
          + shared TEST_RECORD_IDS / TEST_RECORD_DOMAINS


TARGET (D-60-01..06 — review folded into the grant, dynamically armed):

  Operator "yes" to plan_grant() proposal, lanes=[enrichment, contacts, review]
        |
        v
  write_grant.open_grant()  -->  grant{lanes:[...,"review"], record_ids, record_domains,
                                        workflow_ids:{..., "review": <id>}}
        |
        | one batch, D-60-06
        v
  n8n_arming.armed_review_window(review_workflow_id, grant.record_ids,
                                  grant.record_domains, config, grant=grant)
        |  arms ONLY: ALLOW_HUBSPOT_REVIEW_WRITES=true, TEST_RECORD_IDS/DOMAINS
        |  (never touches ALLOW_HUBSPOT_RECORD_WRITES / ALLOW_HUBSPOT_CREATE)
        v
  for each record the operator triages in this batch:
        review-triage skill --yes(per-record, unchanged UX)--> submit_decision(
            ..., authorized_by=write_grant.authorize_send(grant, lane="review", ...))
        |
        v
  POST hubspot/review/decision  -- same endpoint, same gate, unchanged n8n JSON --
        |
        v
  disarm on batch end / crash (armed_window.__exit__, unchanged guarantee)
```

The n8n-side boxes at the bottom of both diagrams are byte-identical — this phase changes
nothing below the webhook. Everything new is above it.

### Pattern 1: Parameterize the arm/disarm pair rather than duplicate it
**What:** `n8n_arming.arm_for_dispatch` / `disarm` / `armed_window` already delegate all
their actual mutation and verification work to lane-agnostic primitives:
`set_write_safety(workflow, targets)` (rewrites any subset of the 5 `OVERLAYABLE_FLAGS`),
`n8n_control.apply_mutation(workflow_id, mutate_fn, allowed_node_names, config,
verify_fn=..., transport=...)` (generic fetch→mutate→PUT→verify cycle), and
`n8n_read.read_write_safety` (generic reader, discovers declaring nodes dynamically — never
a hardcoded list). The only lane-specific things `arm_for_dispatch` hardcodes are (a) which
flags to target (`DISPATCH_FLAGS`) and (b) the `targets` dict it builds
(`ALLOW_HUBSPOT_RECORD_WRITES` + optional `ALLOW_HUBSPOT_CREATE` + the two allowlist
flags).
**When to use:** Exactly this phase's situation — a second lane needing the identical
arm→verify→disarm lifecycle against a different flag.
**Example (verified read of the real function, not paraphrased):**
```python
# Source: operator-claude-plugin/scripts/n8n_arming.py:299-420 (arm_for_dispatch, abridged)
targets = {
    "ALLOW_HUBSPOT_RECORD_WRITES": True,
    "TEST_RECORD_IDS": ",".join(ids),
    "TEST_RECORD_DOMAINS": ",".join(domains),
}
if allow_create:
    targets["ALLOW_HUBSPOT_CREATE"] = True
...
result = n8n_control.apply_mutation(
    workflow_id, _mutate, _declaring_nodes(original), config,
    verify_fn=_verify, transport=transport,
    action=f"arm live writes on {workflow_id} for {len(ids)} id(s) and "
           f"{len(domains)} domain(s)")
```
The review analog needs only a different `targets` dict
(`{"ALLOW_HUBSPOT_REVIEW_WRITES": True, "TEST_RECORD_IDS": ..., "TEST_RECORD_DOMAINS": ...}`,
never `ALLOW_HUBSPOT_RECORD_WRITES`/`ALLOW_HUBSPOT_CREATE`) and a different flag list fed to
`_declaring_nodes`/`_verify`/`disarmed_targets`. `n8n_arming.OVERLAY_DISABLED_LITERALS`
already has the disarmed literal for `ALLOW_HUBSPOT_REVIEW_WRITES` (`n8n_arming.py:49`), so
`disarmed_targets("ALLOW_HUBSPOT_REVIEW_WRITES", "TEST_RECORD_IDS", "TEST_RECORD_DOMAINS")`
already works with zero changes to `disarmed_targets` itself.

### Pattern 2: The shared allowlist is the safety property, and it already generalizes
**What:** `set_write_safety` and the whole verify-then-refuse mechanism operate on
whatever flag names appear in `targets`; they never assume DISPATCH_FLAGS. The empty-
allowlist refusal in `arm_for_dispatch` ("the deployed `_writeSafetyAllows()` returns
false when both allowlists are empty...") is a general truth about the shared gate, true
for `action === "review"` exactly as for `action === "create"`/`"enrich"`
[VERIFIED: scripts/build_cloud_workflows.py:1177-1194 — the single `_writeSafetyAllows`
body baked into every gate node, quoted below].
**When to use:** Reuse this refusal verbatim in a review-specific arm function; do not
re-derive it.

### Anti-Patterns to Avoid
- **Do not touch `n8n/wf_review_decision_cloud.json` by hand, or add a node to it via
  `scripts/build_cloud_workflows.py`.** Nothing in this phase requires it — the JSON
  already declares `ALLOW_HUBSPOT_REVIEW_WRITES` in the exact rewritable form
  `n8n_arming.set_write_safety`'s regex targets (verified below). Regenerating the
  workflow when no generator change is needed just adds diff noise and deploy risk.
- **Do not extend `DISPATCH_FLAGS` to include `ALLOW_HUBSPOT_REVIEW_WRITES`.** CONTEXT.md's
  load-bearing note is explicit and the live JS gate (quoted below) proves why: arming
  `ALLOW_HUBSPOT_REVIEW_WRITES=true` must never make `_writeSafetyAllows("create"/"enrich",
  ...)` return `true` for the same allowlisted record, and vice versa. Keep the two
  boolean flags on two separate constant tuples so a caller can never blend them by
  accident (`test_write_grant.py::test_the_review_lane_is_not_grantable` half-pins exactly
  this — see Common Pitfalls for the half that needs rewriting).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rewriting a deployed workflow's `const` literal safely | A second regex / string-replace | `n8n_arming.set_write_safety` (bidirectional, fail-closed re-scan via the shipped `n8n_read.read_write_safety`) | Already handles multi-node declaration desync, already tested, already the writer half of the reader every status surface uses |
| Fetch→mutate→verify→restore-active-state cycle against the n8n API | A bespoke PUT+GET pair | `n8n_control.apply_mutation` | Already restores the workflow's prior active/inactive state, already refuses on out-of-allowlist diffs (T-28-06), already used by both `arm_for_dispatch` and `disarm` |
| Deciding whether a send is inside a grant's scope | A second scope-check function | `write_grant.covers` | "the ONE implementation of the scope question" per its own docstring — a review-specific reimplementation would immediately diverge in wording from the dispatch refusal |
| Resolving a workflow name to an id | A hand-rolled n8n API list-and-filter | `executions_client.resolve_workflow_id(config, transport, workflow_name=...)` | Generic over `workflow_name`, already process-cached, already used by both existing lanes — needs zero code change for a third lane, only a new name constant |

**Key insight:** every primitive this phase needs already exists and is already lane-generic
except two module-level constants that were deliberately scoped to 2 lanes before review
existed (`n8n_arming.DISPATCH_FLAGS`, `write_grant.WRITE_ENABLING_FLAGS`). The work is almost
entirely "add a third value/branch to an existing generic mechanism," not "build a new
mechanism."

## Common Pitfalls

### Pitfall 1: Guardrail A cannot see a stuck-open review authorization
**What goes wrong:** `write_grant.guardrail_a` (the "refuse to open a grant over a backend
where writes are already live" check, D-53-03) reads live write state via
`read_live_write_state`, which loops `for flag in n8n_arming.DISPATCH_FLAGS:`
[VERIFIED: operator-claude-plugin/scripts/write_grant.py:1599 — `for flag in
n8n_arming.DISPATCH_FLAGS:`] — 4 flags, never `ALLOW_HUBSPOT_REVIEW_WRITES`. Separately,
`write_grant.py` defines its OWN local `WRITE_ENABLING_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES",
"ALLOW_HUBSPOT_CREATE")` [VERIFIED: operator-claude-plugin/scripts/write_grant.py:1556] —
a 2-item tuple, distinct from and shadowing the name of `n8n_arming.WRITE_ENABLING_FLAGS`
(a 3-item frozenset that DOES include the review flag, at `n8n_arming.py:54-56`). Once
`"review"` is added to `LANES` and a grant's `workflow_ids` dict gets a `"review"` entry,
Guardrail A will read the review workflow's dispatch flags (harmless, since the review
workflow declares all 5 and the dispatch ones are unused there) but will structurally
never notice `ALLOW_HUBSPOT_REVIEW_WRITES=true` left armed by a crashed prior session — the
exact scenario Guardrail A exists to catch (D-53-03's own words: "found a state IT DID NOT
CREATE").
**Why it happens:** Both constants were written correctly for a 2-lane world (D-02/D-08e
deliberately kept review's authority off Guardrail A's radar, because review had no
`workflow_ids` entry to iterate). D-60-01 changes that premise without either constant
being touched.
**How to avoid:** Widen `read_live_write_state`'s per-lane flag loop and `write_grant.py`'s
local `WRITE_ENABLING_FLAGS` to also read/report `ALLOW_HUBSPOT_REVIEW_WRITES`. The
cheapest correct fix is almost certainly to swap the read loop's `n8n_arming.DISPATCH_FLAGS`
for `n8n_arming.OVERLAYABLE_FLAGS` (all 5) unconditionally per lane — every currently
deployed cloud workflow already declares all 5 via the single shared `WRITE_SAFETY_GATE_JS`
block [VERIFIED: ran `n8n/wf_enrichment_cloud.json` and `n8n/wf_contact_ingest_cloud.json`
through a declaration scan this session — both declare `ALLOW_HUBSPOT_REVIEW_WRITES` on
their own write-gate nodes (`Decide Company Action`/`Decide Action`,
`HubSpot Update Write Gate`/`HubSpot Associate Company Write Gate`/`HubSpot Create Write
Gate`) even though those workflows never branch on it] — so this is not overreach, it
matches deployed reality on lanes that exist today too.
**Warning signs:** `guardrail_a` returning `None` (proceed) on a grant that includes the
review lane even though a previous session's review batch crashed mid-window — silent,
because nothing surfaces an absence of a check.

### Pitfall 2: Widening the guardrail's flag set will break existing test fixtures, on purpose
**What goes wrong:** `operator-claude-plugin/tests/test_write_grant_guardrails.py`'s
`_gate()` helper builds a mock workflow's `jsCode` declaring exactly 4 constants
(`ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`, `TEST_RECORD_IDS`,
`TEST_RECORD_DOMAINS`) [VERIFIED: operator-claude-plugin/tests/test_write_grant_guardrails.py:37-42
— `def _gate(record_writes='"false"', create='"false"', ids='""', domains='""'):` followed
by exactly those 4 `const` lines]. `n8n_read.read_write_safety` returns `{"value": None,
"nodes": [], "disagreement": None}` for a flag with zero declaring nodes
[VERIFIED: operator-claude-plugin/scripts/n8n_read.py:452-453 — `if not distinct: return
{"value": None, "nodes": [], "disagreement": None}`]. If Pitfall 1's fix widens the read
loop to check `ALLOW_HUBSPOT_REVIEW_WRITES` unconditionally, every existing guardrail test
using `_gate()`/`_workflow()` will suddenly read `flags["ALLOW_HUBSPOT_REVIEW_WRITES"] =
None` → `readable = False` (since the widened `WRITE_ENABLING_FLAGS` would require it
non-`None`) → **every currently-passing "disarmed backend proceeds" test starts refusing.**
**Why it happens:** The test fixtures were written to match a 2-lane world's real declared
shape and never needed to change, until this phase widens what "real declared shape" means.
**How to avoid:** Update `_gate()` in the same commit that widens the guardrail's flag set,
adding the review constant with its disarmed literal (`'"false"'`) as a fifth line — a
one-line fixture change, not a redesign. `test_write_gate_coverage.py` (referenced in
`scripts/build_cloud_workflows.py:8165`'s comment) is a separate test that walks the real
committed JSON and is unaffected either way, since this phase changes no JSON.
**Warning signs:** A wave of guardrail-A tests failing with "its write-safety state could
not be read at all" immediately after widening the flag list — that message is
`_live_write_faults`'s literal wording for `readable=False`
[VERIFIED: operator-claude-plugin/scripts/write_grant.py:1618-1622].

### Pitfall 3: Two tests currently assert the design this phase reverses — by name
**What goes wrong:** `operator-claude-plugin/tests/test_write_grant.py` has:
```python
# Source: operator-claude-plugin/tests/test_write_grant.py:602-617 (verbatim)
def test_plan_grant_refuses_an_unknown_lane_by_name(granting_config,
                                                    stub_module_transport_factory):
    transport = stub_module_transport_factory(_plan_reads())

    result = _proposal(granting_config, transport, lanes=("review",))

    assert result["outcome"] == write_grant.REFUSED
    assert "review" in result["detail"]
    assert transport.calls == []


def test_the_review_lane_is_not_grantable(granting_config, stub_module_transport_factory):
    """30-01's D-02/D-08e: review writeback is a SEPARATE authority. A dispatch grant must
    not reach it."""
    assert "review" not in write_grant.LANES
    assert "ALLOW_HUBSPOT_REVIEW_WRITES" not in n8n_arming.DISPATCH_FLAGS
```
Once `"review"` joins `LANES`, `test_plan_grant_refuses_an_unknown_lane_by_name`'s
`lanes=("review",)` call stops refusing and the test fails outright — it must be
repurposed onto a genuinely-unknown lane name (e.g. `lanes=("bogus",)`) rather than
deleted, so the "unknown lane refuses by name" behavior stays pinned.
`test_the_review_lane_is_not_grantable`'s FIRST assertion (`"review" not in
write_grant.LANES`) becomes false and must be inverted with the recorded-edit discipline
D-60-05 already calls for; its SECOND assertion (`"ALLOW_HUBSPOT_REVIEW_WRITES" not in
n8n_arming.DISPATCH_FLAGS`) stays TRUE after this phase (the load-bearing note is explicit
that `DISPATCH_FLAGS` must never gain this flag) and should be preserved, ideally in a
renamed test asserting the SEPARATION survives even though the lane is now grantable.
**Why it happens:** These tests were written to pin exactly the design D-60-01 reverses;
CONTEXT.md's own recorded-edit-discipline instruction (for the `write_grant.py:64-82`
comment) applies with equal force to these two tests.
**How to avoid:** Rewrite both in the same commit that adds `"review"` to `LANES`, with a
docstring/comment naming this phase and dated, mirroring the D-59-07 amendment style
already present in `write_grant.py`. Do not silently delete
`test_the_review_lane_is_not_grantable` — repurpose it to assert the surviving half of the
separation (arming review grants nothing on dispatch, and vice versa), which is exactly
what `tests/n8n/reviewWriteFlagSeparation.test.mjs` already independently proves at the JS
level (see Validation Architecture).

### Pitfall 4: `submit_decision`'s two other gates must not silently vanish
**What goes wrong:** D-60-04 retires the `ALLOW_REVIEW_SUBMIT` env check specifically. It
says nothing about the session arm (`review_armed`) or the `is_undoing`/`reject` carve-out.
A literal reading of "grant-authorization becomes THE gate" could tempt an implementation
that also drops the per-decision `review_armed` confirmation the skill still asks for in
Step 6 of `review-triage/SKILL.md` — but nothing in D-60-01..06 authorizes removing the
per-record "read the exact write back and get an explicit yes" ritual, and the skill's own
Step 6 language ("A yes here authorizes this record's write and nothing else") is
unaffected by which authority sits underneath it.
**Why it happens:** `submit_decision`'s current code checks THREE things in sequence
(`is_undoing(decision) or submit_enabled()`, then `review_armed`, then does the POST)
[VERIFIED: operator-claude-plugin/scripts/review_decision.py:243-249 — `if not
is_undoing(decision) and not submit_enabled(): return _unavailable(...)` then `if not
review_armed: return _unavailable(...)`]. Swapping gate 1 for a grant-authorization call is
a one-line-shaped change that is easy to over-apply to gate 2 by accident.
**How to avoid:** Keep `review_armed` as a separate, still-required argument;
`submit_decision`'s new first check becomes something shaped like `write_grant.check_before_send`
or the `armed`/`refusal` fields `authorize_send` already returns, composed BEFORE the
existing `review_armed` check, not replacing it. `is_undoing("reject")`'s bypass of gate 1
(`review_decision.py:100-103`, `UNDOING_DECISIONS = ("reject",)`) needs an explicit design
decision under grant-authorization: does a reject still bypass the grant check the way it
bypassed the env var? The rationale for the original carve-out ("a closed kill switch must
not be able to strand a record mid-decision") arguably still applies to "no grant is open" —
this is an Open Question below, not resolved by CONTEXT.md.

### Pitfall 5: `n8n/code/reviewDecision.js`'s own message is now stale text, not stale code
**What goes wrong:** The `not_allowlisted` refusal message says: *"an administrator adds
records to that allowlist at deploy time"* [VERIFIED: n8n/code/reviewDecision.js:226-228 —
`message: "this record is not on the backend's TEST_RECORD_* allowlist, so nothing was "
+ "sent to HubSpot and the record is unchanged — an administrator adds records to " +
"that allowlist at deploy time"`]. After this phase ships, that will often be false — the
allowlist can also be set dynamically by a grant's arm window, with no admin and no deploy.
**Why it happens:** This string was accurate in the pre-D-60-05 world; it is
operator-facing text baked into the deployed workflow JSON.
**How to avoid:** This is a `scripts/build_cloud_workflows.py` string edit (regenerating
`wf_review_decision_cloud.json`) — the ONE part of this phase that legitimately does touch
the generated JSON, and only the message text, not the gate logic. `test_review_outcome_parity.py`
does not pin message text (only outcome literals), so this edit is low-risk, but must still
go through `scripts/build_cloud_workflows.py`, never a hand-edit of the JSON (project rule).

## Code Examples

### The shared write-safety gate the review lane already uses (unchanged by this phase)
```javascript
// Source: scripts/build_cloud_workflows.py:1177-1194 (WRITE_SAFETY_GATE_JS, verbatim) —
// baked into "Build Review Decision", "Review Decision Update Write Gate" and
// "Review Contact Decision Update Write Gate" in the committed
// n8n/wf_review_decision_cloud.json (confirmed via live read of that file this session)
function _writeSafetyAllows(action, hsObjectId, domain) {
  if (action === "review") {
    if (String(ALLOW_HUBSPOT_REVIEW_WRITES).toLowerCase() !== "true") return false;
  } else {
    if (String(ALLOW_HUBSPOT_RECORD_WRITES).toLowerCase() !== "true") return false;
    if (action === "create" && String(ALLOW_HUBSPOT_CREATE).toLowerCase() !== "true") return false;
  }
  const allowedDomains = String(TEST_RECORD_DOMAINS).split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  const allowedIds = String(TEST_RECORD_IDS).split(",").map((s) => s.trim()).filter(Boolean);
  if (!allowedDomains.length && !allowedIds.length) return false;
  if (hsObjectId && allowedIds.indexOf(String(hsObjectId)) !== -1) return true;
  if (domain && allowedDomains.indexOf(String(domain).toLowerCase()) !== -1) return true;
  return false;
}
```
The declared constants immediately above this function in the committed workflow, read
directly this session:
```javascript
// Source: n8n/wf_review_decision_cloud.json, node "Build Review Decision" (also
// "Review Decision Update Write Gate" and "Review Contact Decision Update Write Gate"),
// verified by scanning the committed JSON this session
const ALLOW_HUBSPOT_REVIEW_WRITES = "false";
const ALLOW_HUBSPOT_RECORD_WRITES = "false";
const ALLOW_HUBSPOT_CREATE = "false";
const TEST_RECORD_IDS = "";
const TEST_RECORD_DOMAINS = "";
```
This is the EXACT `const NAME = <literal>;` shape `n8n_arming.set_write_safety`'s regex
targets (`rf"const\s+{re.escape(flag)}\s*=\s*[^;]+;"`,
`operator-claude-plugin/scripts/n8n_arming.py:136`) — no drift, no adaptation needed.

### The lane table this phase extends
```python
# Source: operator-claude-plugin/scripts/write_grant.py:83-86 (verbatim, current state)
LANES = {
    "enrichment": scheduled_arm.ENRICHMENT_WORKFLOW_NAME,
    "contacts": executions_client.CONTACT_INGEST_WORKFLOW_NAME,
}
```
```python
# Source: n8n/wf_review_decision_cloud.json (verified live this session)
# wf.get("name") == "LV Review Decision (Cloud)"
```

### The overlay flag table review already belongs to
```python
# Source: operator-claude-plugin/scripts/n8n_arming.py:46-57 (verbatim, current state)
OVERLAY_DISABLED_LITERALS = {
    "ALLOW_HUBSPOT_RECORD_WRITES": '"false"',
    "ALLOW_HUBSPOT_CREATE": '"false"',
    "ALLOW_HUBSPOT_REVIEW_WRITES": '"false"',
    "TEST_RECORD_IDS": '""',
    "TEST_RECORD_DOMAINS": '""',
}
OVERLAYABLE_FLAGS = frozenset(OVERLAY_DISABLED_LITERALS)
WRITE_ENABLING_FLAGS = frozenset({
    "ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE", "ALLOW_HUBSPOT_REVIEW_WRITES",
})
ALLOWLIST_FLAGS = frozenset({"TEST_RECORD_IDS", "TEST_RECORD_DOMAINS"})

DISPATCH_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE",
                  "TEST_RECORD_IDS", "TEST_RECORD_DOMAINS")
```
`ALLOW_HUBSPOT_REVIEW_WRITES` is already `[OVERLAYABLE]` (line 49) and already counted in
`n8n_arming.WRITE_ENABLING_FLAGS` (lines 54-56) — this phase needs a `REVIEW_FLAGS` tuple
analogous to `DISPATCH_FLAGS`, e.g. `("ALLOW_HUBSPOT_REVIEW_WRITES", "TEST_RECORD_IDS",
"TEST_RECORD_DOMAINS")`, never a change to `OVERLAY_DISABLED_LITERALS` or
`OVERLAYABLE_FLAGS` (both already correct) and never a change to `DISPATCH_FLAGS` itself.

### The build-time generator (confirms no JSON hand-edit is needed)
```python
# Source: scripts/build_cloud_workflows.py:8167-8168 (verbatim) — the ONE call site that
# wires the review lane's write nodes to the shared gate
splice_write_gates(nodes, conns, {"Review Decision Update": "review",
                                  "Review Contact Decision Update": "review"})
```
`build_review_decision_cloud()` (the function containing this call, at
`scripts/build_cloud_workflows.py:7841`) is the sole generator of
`n8n/wf_review_decision_cloud.json`. This phase's client-side change requires no edit here.

## Runtime State Inventory

Not applicable — this is not a rename/refactor/migration phase. No stored data, live
service config, OS-registered state, secret/env-var name, or build artifact carries a
string this phase renames.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The smallest-diff design for the arm/disarm split is to parameterize `arm_for_dispatch`/`disarm` with a `flags=` argument rather than write a fully separate `arm_for_review`/`disarm_review` pair. | Architecture Patterns, Pattern 1 | If the planner instead duplicates the ~120-line `arm_for_dispatch` body, the two copies drift over time (e.g. a future fix to the fail-closed re-scan lands in one but not the other). Low risk to correctness today, real risk to maintainability later. Recorded as [ASSUMED] because CONTEXT.md explicitly left this to Claude's Discretion ("pick whichever produces the smaller diff") and only a planner with the full diff in hand can measure that. |
| A2 | Widening `read_live_write_state`'s flag loop to `n8n_arming.OVERLAYABLE_FLAGS` (all 5, unconditionally per lane) is the right fix for Pitfall 1, rather than a lane-keyed flag map (dispatch flags for enrichment/contacts, review flag only for review). | Common Pitfalls, Pitfall 1 | The uniform-5-flags approach is simpler and matches deployed reality (verified: all cloud workflows using the shared gate already declare all 5), but it does mean Guardrail A will report `ALLOW_HUBSPOT_CREATE`/`ALLOW_HUBSPOT_RECORD_WRITES` state on the review workflow too (harmless, since those flags are functionally inert there) and `ALLOW_HUBSPOT_REVIEW_WRITES` state on the enrichment/contacts workflows too (also harmless for the same reason). If a future workflow is added that does NOT use the shared `WRITE_SAFETY_GATE_JS` block, this assumption would need re-checking. |
| A3 | `submit_decision`'s `is_undoing("reject")` env-var bypass should also bypass whatever replaces `submit_enabled()` under grant-authorization (i.e. a reject still needs no open grant). | Common Pitfalls, Pitfall 4 | Not stated by D-60-04. If wrong, a reject would start requiring an open grant, which would strand a rejection exactly the way the original carve-out was designed to prevent — this is an Open Question, not a decision, and the planner should surface it for confirmation rather than assume either answer. |

## Open Questions

1. **Does a `reject` decision need an open grant at all, under D-60-04?**
   - What we know: today, `is_undoing("reject")` bypasses `ALLOW_REVIEW_SUBMIT` specifically
     (`review_decision.py:100-103`, `SUBMIT_ENV_VAR` check only) but NOT the session arm
     (`review_armed` is still required for both approve and reject).
   - What's unclear: D-60-04 says grant-authorization "becomes the gate `submit_decision()`
     checks instead" of the env var — it does not say whether a reject should also be able
     to proceed with NO grant open at all (the way it could proceed today with the env var
     unset, since the env-var-bypass existed specifically so a closed kill switch could
     never strand a record).
   - Recommendation: surface this explicitly to the operator during planning/discuss rather
     than assume either direction — the original rationale ("a rejection records a reason
     and leaves the record in the queue... blocking that would strand a record") reads as
     applying to "no grant open" symmetrically with "env var unset," but CONTEXT.md never
     says so.

2. **Should the review lane's writes appear in the D-59-07/D-59-09 `written_records-<run_id>.json` artifact?**
   - What we know: the dispatch lanes (enrichment, contacts) now write a durable
     per-run record of what actually landed in HubSpot, specifically so a partial or
     revoked run's writes are still visible (D-59-07/D-59-09, `written_records.py`).
     Review decisions also write to HubSpot (an approve promotes a candidate; a reject
     writes a reason) but go through `review_decision.submit_decision`, never through
     `chunking.dispatch_plan`, so they are NOT captured by that artifact today.
   - What's unclear: 60-CONTEXT.md's decisions do not mention this at all — it may be
     intentionally out of scope (review already has its own audit trail via
     `lv_enrichment_provenance` and `lv_enrichment_reviewed_by`/`_at`, stamped by
     `reviewApply` on the record itself, which arguably makes a separate written-records
     entry redundant for this lane).
   - Recommendation: treat as explicitly out of scope for this phase (CONTEXT.md's phase
     boundary paragraph says the phase "does not change what a reviewer sees before
     approving" and never proposes a new artifact) unless the operator raises it in
     discuss-phase.

3. **Where should `REVIEW_WORKFLOW_NAME` live?**
   - What we know: `ENRICHMENT_WORKFLOW_NAME` lives in `scheduled_arm.py` (which also uses
     it for the scheduled-maintenance poller, independent of `write_grant.LANES`);
     `CONTACT_INGEST_WORKFLOW_NAME` lives in `executions_client.py` (the module that
     defines `resolve_workflow_id`, whose default parameter it is, and is also read by
     `report.py`-family consumers). Verified: grepping the whole plugin `scripts/` tree,
     the review lane has NO other consumer today besides `write_grant.LANES` — no
     scheduled poller, no report reader references a "review" workflow name.
   - What's unclear: there is no natural "owner" module for this constant the way the
     other two have one, since review has no scheduled-arm analog and no executions-report
     consumer.
   - Recommendation: place it directly in `write_grant.py` beside `LANES` (smallest diff,
     matches its single actual consumer today) rather than manufacturing a new module or
     forcing it into `executions_client.py` where it would be an orphaned constant with no
     use besides being a default nobody defaults to.

## Environment Availability

Not applicable — this phase adds no new external dependency, tool, or service. It uses the
n8n Cloud API and HubSpot credentials this plugin already requires and already probes via
`config_gate.load_config()`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python plugin/backend) + Node's built-in `node:test` (n8n JS logic) |
| Config file | none dedicated — `operator-claude-plugin/tests/conftest.py` provides fixtures/autouse guards; `tests/conftest.py` provides the root suite's |
| Quick run command (plugin) | `.venv/bin/python -m pytest operator-claude-plugin/tests -q` |
| Quick run command (root) | `.venv/bin/python -m pytest -q` |
| n8n JS logic | `node --test tests/n8n/*.test.mjs` — GLOB form; the directory form is broken on node 24 (repo-documented gotcha, do not use `tests/n8n/`) |

### Phase Requirements → Test Map
No REQ-IDs are mapped to this phase (see Phase Requirements above). The behaviors below are
derived directly from D-60-01..06 and must each have a passing/updated test before this
phase can be called done.

| Behavior (from decision) | Test Type | Automated Command | File Exists? |
|---|---|---|---|
| `"review"` is a valid, grantable lane (D-60-01/D-60-02) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -k lane -x` | ❌ needs new/rewritten test — see Pitfall 3 |
| Review decisions cannot exceed the grant's record scope (D-60-03) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -k covers -x` | ✅ `write_grant.covers` already generically scope-checked; a review-specific case should be added alongside the existing ones |
| `submit_decision` no longer reads `ALLOW_REVIEW_SUBMIT`; grant-authorization gates it instead (D-60-04) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_decision.py -x` | ✅ file exists, ~15 tests currently pin the env-var gate and need rewriting (see Pitfall 4/Common Pitfalls) |
| Arming review sets `ALLOW_HUBSPOT_REVIEW_WRITES` dynamically, never touching `ALLOW_HUBSPOT_RECORD_WRITES`/`ALLOW_HUBSPOT_CREATE` (D-60-05, load-bearing note) | unit + n8n JS | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_control_flag_parity.py -x` (parity unaffected, should already be green) AND `node --test tests/n8n/reviewWriteFlagSeparation.test.mjs` (already pins the separation direction from the JS side; must stay green unmodified) | ✅ both exist; the JS test needs NO change (proves the JSON-side invariant this phase must not violate); a new Python-side test proving `arm_for_review` never sets `ALLOW_HUBSPOT_RECORD_WRITES` should be added |
| Guardrail A detects a dirty `ALLOW_HUBSPOT_REVIEW_WRITES` state before opening a grant (consequence of D-60-01, this research's own finding, Pitfall 1) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant_guardrails.py -x` | ❌ needs a new test case; existing `_gate()` fixture needs the one-line update from Pitfall 2 |
| One arm window covers a whole batch of decisions (D-60-06) | unit | new test module or additions to `test_write_grant.py`/`test_write_grant_guardrails.py` exercising the batch-scoped arm/disarm lifecycle | ❌ needs new test — no existing test exercises a multi-decision single-window lifecycle for ANY lane today (dispatch's `authorize_send` is per-send, not batch-scoped, so this is genuinely new coverage, not a copy of an existing pattern) |
| `write_grant.py:64-82`'s exclusion comment is amended, not deleted (recorded-edit discipline) | manual/code-review | `git diff` review of the comment block | N/A — a documentation/process check, not a runnable test |
| `n8n/code/reviewDecision.js`'s stale `not_allowlisted` message text (Pitfall 5) | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_outcome_parity.py -x` (outcome vocabulary parity, unaffected by a message-text edit) | ✅ exists, should stay green through the text edit since it only pins outcome literals, not message strings |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest operator-claude-plugin/tests -q` (fast,
  no network — `conftest.py`'s autouse `no_network` guard blocks any real transport)
- **Per wave merge:** the full three-part suite — `.venv/bin/python -m pytest -q`,
  `.venv/bin/python -m pytest operator-claude-plugin/tests -q`, and
  `node --test tests/n8n/*.test.mjs`
- **Phase gate:** all three suites green before `/gsd-verify-work`; this phase performs
  no live HubSpot or n8n writes (READ-ONLY research; the plan itself should stage a
  disarmed-by-default implementation and treat any live arm/disarm proof as a separate,
  explicitly-approved verification step, mirroring how Phase 53/59's own live walks were
  gated)

### Wave 0 Gaps
- [ ] A new unit test module (or additions to `test_write_grant_guardrails.py`) covering
      the batch-scoped review arm/disarm lifecycle (D-60-06) — no existing fixture covers
      a multi-decision single window for any lane.
- [ ] `test_write_grant.py::test_the_review_lane_is_not_grantable` and
      `test_plan_grant_refuses_an_unknown_lane_by_name` need rewriting in the same commit
      that adds `"review"` to `LANES` (Pitfall 3).
- [ ] `test_write_grant_guardrails.py`'s `_gate()`/`_workflow()` fixtures need a fifth
      declared constant (`ALLOW_HUBSPOT_REVIEW_WRITES`) if Guardrail A's flag-read is
      widened (Pitfall 2).
- [ ] No test framework install needed — pytest and node:test are both already the
      project's standing tools.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V4 Access Control | yes | This IS the phase's subject: which authority (env var vs. session arm vs. grant) may enable a write, and to which records. Reuse `write_grant.covers`'s "narrower than the grant, never wider" scope check rather than inventing a parallel one for review. |
| V2 Authentication | no | Unaffected — `X-Enrichment-Secret` header auth on the webhook, `X-N8N-API-KEY` on the management API, both unchanged |
| V5 Input Validation | no (unchanged) | `review_decision.py::_request_body` already sends only 6 fixed keys; this phase changes which gate evaluates the request, not the request shape |
| V6 Cryptography | n/a | No cryptographic material touched |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Authority collapse — arming one lane accidentally grants another (dispatch write vs. review write) | Elevation of Privilege | Keep `REVIEW_FLAGS` and `DISPATCH_FLAGS` on two separate constant tuples/target dicts (never merge); `tests/n8n/reviewWriteFlagSeparation.test.mjs` already proves the JSON-side gate keeps them separate — this phase's Python-side change must not undermine that by, e.g., a shared `targets` dict built from a union of both flag sets |
| Stuck-open authorization surviving a crashed session (Guardrail A blind spot, Pitfall 1) | Tampering / Repudiation | Widen Guardrail A's flag-read to include `ALLOW_HUBSPOT_REVIEW_WRITES`, per this research's central finding |
| Scope widening — a grant opened over records A/B approving a review decision on record D | Elevation of Privilege | `write_grant.covers`'s existing symmetric ids/domains check (D-60-03), reused unchanged for the review lane |

## Sources

### Primary (HIGH confidence — read directly this session)
- `operator-claude-plugin/scripts/write_grant.py` (full read, both halves — lines 1-1073 and 1074-1752)
- `operator-claude-plugin/scripts/n8n_arming.py` (full read)
- `operator-claude-plugin/scripts/review_decision.py` (full read)
- `operator-claude-plugin/scripts/executions_client.py` (partial read, resolver + constant)
- `n8n/wf_review_decision_cloud.json` (read via `json.load` + targeted regex scans this session — name field, declaring nodes, gate function bodies)
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_contact_ingest_cloud.json` (targeted declaration scans this session, confirming shared-gate reality)
- `n8n/code/reviewDecision.js` (partial read, `buildReviewDecision` + message text)
- `scripts/build_cloud_workflows.py` (targeted reads: `WRITE_SAFETY_GATE_JS`, `build_review_decision_cloud`, `REVIEW_BUILD_DECISION`)
- `operator-claude-plugin/scripts/n8n_read.py::read_write_safety` (full function read)
- `operator-claude-plugin/scripts/n8n_control.py::apply_mutation` (signature + docstring read)
- `operator-claude-plugin/tests/test_write_grant.py`, `test_write_grant_guardrails.py`, `test_review_decision.py` (grep + targeted reads), `test_control_flag_parity.py` (full read), `test_review_outcome_parity.py` (full read)
- `tests/n8n/reviewWriteFlagSeparation.test.mjs`, `reviewAllowlistRefusal.test.mjs` (partial reads)
- `operator-claude-plugin/skills/review-triage/SKILL.md` (full read)
- `.planning/phases/60-review-lane-authority/60-CONTEXT.md`, `.planning/phases/59-frictionless-write-path/59-CONTEXT.md`, `.planning/ROADMAP.md` (Phase 60 entry), `.planning/STATE.md`, `.planning/milestones/v1.1-REQUIREMENTS.md` (grep)

### Secondary (MEDIUM confidence)
- None — every claim above a `[VERIFIED]` tag was checked directly against source this session; no web search or documentation lookup was needed for this internal-plumbing phase.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: N/A — no new dependency
- Architecture: HIGH — every mechanism cited was read directly, not inferred, including the exact JS gate function and the exact Python constants this phase must add/extend
- Pitfalls: HIGH — Pitfalls 1-3 were discovered by executing the actual read/scan against the actual files this session, not by pattern-matching the phase description; Pitfall 4/5 are direct readings of the modules named in CONTEXT.md's canonical refs

**Research date:** 2026-09-01
**Valid until:** This research is tied to the current state of `n8n/wf_review_decision_cloud.json`, `write_grant.py`, and `n8n_arming.py` as committed on 2026-09-01. It should be re-verified if any of those three files change materially before this phase is planned/executed (e.g. if a concurrent phase touches Guardrail A or the review workflow first).


### Plan 1 of 4
---
phase: 60-review-lane-authority
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - operator-claude-plugin/scripts/n8n_arming.py
  - operator-claude-plugin/scripts/write_grant.py
  - operator-claude-plugin/scripts/review_decision.py
  - operator-claude-plugin/tests/test_write_grant.py
  - operator-claude-plugin/tests/test_review_decision.py
  - operator-claude-plugin/tests/test_control_arming.py
  - operator-claude-plugin/tests/test_write_grant_surface.py
autonomous: true
requirements: [D-60-01, D-60-02, D-60-03, D-60-04, D-60-05, D-60-07]
user_setup: []

estimate:
  tokens: 90000
  raw_tokens: 90000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "D-60-01: `\"review\"` is a grantable lane — `write_grant.LANES` resolves it to the deployed `LV Review Decision (Cloud)` workflow, and the comment block that documented the old exclusion is AMENDED with a dated addendum, never deleted."
    - "D-60-02: one grant covers all three lanes — `plan_grant(lanes=[\"enrichment\", \"contacts\", \"review\"])` returns a proposal whose `workflow_ids` carries all three, with no per-lane consent step anywhere."
    - "D-60-03: a review decision on a record outside the grant's own id/domain set is REFUSED by the same `write_grant.covers` check dispatch sends already use — no second scope-check function exists."
    - "D-60-04: `submit_decision` reads no shell environment variable; grant-authorization via `write_grant.authorize_send(..., lane=\"review\")` is gate 1, composed BEFORE the still-required `review_armed` gate 2."
    - "D-60-05: arming review sets `ALLOW_HUBSPOT_REVIEW_WRITES` plus the two allowlist constants and NEVER `ALLOW_HUBSPOT_RECORD_WRITES` or `ALLOW_HUBSPOT_CREATE`, through the same `n8n_arming` overlay dispatch already uses, with zero change to any `n8n/wf_*.json`."
    - "D-60-07: a `reject` decision still succeeds with NO grant open — the `is_undoing` carve-out survives, re-pointed at the grant check rather than deleted — while `review_armed` remains required for approve and reject alike."
  artifacts:
    - operator-claude-plugin/scripts/n8n_arming.py
    - operator-claude-plugin/scripts/write_grant.py
    - operator-claude-plugin/scripts/review_decision.py
    - operator-claude-plugin/tests/test_write_grant.py
    - operator-claude-plugin/tests/test_review_decision.py
  key_links:
    - "`write_grant.LANES[\"review\"]` -> `executions_client.resolve_workflow_id` -> the live `LV Review Decision (Cloud)` id, resolved by NAME at plan time exactly as the two existing lanes are."
    - "`review_decision.submit_decision(grant=...)` -> `write_grant.authorize_send(lane=\"review\")` -> `write_grant.covers` — the one scope implementation, shared with dispatch."
    - "`n8n_arming.arm_for_review` -> `set_write_safety({ALLOW_HUBSPOT_REVIEW_WRITES: True, ...})` -> the deployed `_writeSafetyAllows(\"review\", ...)` branch, unchanged."
---

<objective>
Make `"review"` a real grantable lane and prove it end-to-end: an admin-set settings key,
a planned grant naming the review lane, an explicit yes, a dynamically armed review window
that touches only `ALLOW_HUBSPOT_REVIEW_WRITES`, one submitted decision authorized by that
grant, and a verified disarm — with no shell environment variable anywhere on the path.

Purpose: this is the phase's tracer. Every layer the phase will touch (the overlay setter,
the grant/lane table, the client-side decision gate, the test suite) is wired on ONE path
first, so an architectural dead end surfaces after one commit instead of four.

Output: `REVIEW_WORKFLOW_NAME`, `LANES["review"]`, `REVIEW_FLAGS`, the `authority` keyword,
`arm_for_review` / `armed_review_window`, a grant-gated `submit_decision`, and the two
reversed-design tests rewritten under recorded-edit discipline.

**Spec-less probe fallback: SKIPPED, recorded not silent.** This phase has no requirement
IDs and no `SPEC.md`, so the spec-less probe fallback generates no probe predicates this
run. The `requirements` frontmatter carries the D-60-NN decision ids as the coverage
contract instead, per the phase brief.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/60-review-lane-authority/60-CONTEXT.md
@.planning/phases/60-review-lane-authority/60-RESEARCH.md
@.planning/phases/60-review-lane-authority/60-PATTERNS.md
@.planning/phases/60-review-lane-authority/60-VALIDATION.md
</context>

<tasks>

<task type="tracer" tdd="true">
  <name>Task 1: End-to-end "a grant approves one flagged record" — one path only</name>

  <read_first>
    - operator-claude-plugin/scripts/n8n_arming.py (whole file — 514 lines; the flag tables at 46-57, `DISPATCH_FLAGS` at 184, `_declaring_nodes`/`_assert_only_declaration_lines_changed` at 259-296 which ALREADY take a `flags=` parameter, `arm_for_dispatch` 299-420, `disarm` 423-472, `armed_window` 475-513)
    - operator-claude-plugin/scripts/write_grant.py lines 1-120 (module docstring, the review-exclusion comment block at 64-72, the D-59-07 amendment at 74-90 whose STYLE the new addendum copies, `LANES` at 83-86)
    - operator-claude-plugin/scripts/write_grant.py lines 846-1120 (`plan_grant`, including the unknown-lane refusal at 914-923, and `open_grant`)
    - operator-claude-plugin/scripts/write_grant.py lines 1143-1205 (`covers`) and 1292-1352 (`authorize_send`)
    - operator-claude-plugin/scripts/review_decision.py (whole file — 371 lines; the three-gate docstring at 15-53, the retiring constants at 83-120, `submit_decision` at 228-252, the `__main__` diagnostic at 361-370)
    - operator-claude-plugin/tests/test_write_grant.py lines 1-60 (the module docstring and the gate/workflow fixtures at ~38) and 595-625 (the two tests this task rewrites)
    - .planning/phases/60-review-lane-authority/60-PATTERNS.md (the verbatim analog excerpts for all three files)
  </read_first>

  <files>operator-claude-plugin/scripts/n8n_arming.py, operator-claude-plugin/scripts/write_grant.py, operator-claude-plugin/scripts/review_decision.py, operator-claude-plugin/tests/test_write_grant.py</files>

  <behavior>
    - Test 1 (the tracer, one function, red first): with `allow_write_grants` true in config
      and a stubbed module transport, `plan_grant(lanes=["review"], record_ids=["9605284724"])`
      returns a proposal; `open_grant(proposal, "yes", config)` returns an open grant whose
      `workflow_ids["review"]` is the resolved review workflow id; `armed_review_window` over
      that grant arms; `submit_decision(..., grant=grant, review_armed=True)` POSTs once and
      returns the endpoint's five-key contract; the window's `disarm_result` is `DISARMED`.
    - Test 2: across that whole walk, the workflow PUT payload never sets
      `ALLOW_HUBSPOT_RECORD_WRITES` or `ALLOW_HUBSPOT_CREATE` to `"true"` — asserted against
      the recorded PUT body, not against the returned dict.
    - Test 3: `submit_decision` with `grant=None` and `decision="approve"` refuses with reason
      `grant_not_authorized`, and the transport call log is EMPTY (no request was built).
    - Test 4: `submit_decision` with `grant=None` and `decision="reject"` PROCEEDS (D-60-07),
      and still refuses when `review_armed` is falsey.
    - Test 5: a grant opened over record A refuses a review decision on record B, and the
      refusal names B.
  </behavior>

  <action>
In `n8n_arming.py`: add `REVIEW_FLAGS = ("ALLOW_HUBSPOT_REVIEW_WRITES", "TEST_RECORD_IDS", "TEST_RECORD_DOMAINS")` directly below `DISPATCH_FLAGS`, with a comment stating it is a SEPARATE tuple and that `DISPATCH_FLAGS` must never gain the review flag (`test_control_arming.py` line 334 and `test_write_grant.py` both pin that and must stay green). Add `AUTHORITY_DISPATCH = "dispatch"`, `AUTHORITY_REVIEW = "review"` and `FLAGS_BY_AUTHORITY = {AUTHORITY_DISPATCH: DISPATCH_FLAGS, AUTHORITY_REVIEW: REVIEW_FLAGS}`. Give `arm_for_dispatch` a keyword-only `authority=AUTHORITY_DISPATCH` parameter appended after `grant`; inside it, resolve `flags = FLAGS_BY_AUTHORITY[authority]` and return a `REFUSED` dict naming the permitted values for any other authority (fail closed, before the transport is built). Build the targets dict by branch: for `AUTHORITY_REVIEW` it is exactly `{"ALLOW_HUBSPOT_REVIEW_WRITES": True, "TEST_RECORD_IDS": ..., "TEST_RECORD_DOMAINS": ...}` and never carries either dispatch boolean, so the create fail-safe check below it is skipped; the dispatch branch is byte-unchanged. Thread `flags` into the `prior` read, the two `_declaring_nodes(...)` calls and `_assert_only_declaration_lines_changed(...)` — all three already accept a `flags` argument, so no new parameter is invented. Add a public `arm_for_review(workflow_id, record_ids, record_domains, config, transport=None, grant=None)` that delegates to `arm_for_dispatch(..., allow_create=False, authority=AUTHORITY_REVIEW)`, with a docstring saying the shared body is deliberate (one arm implementation, one set of guarantees) and that the historical function name is why it delegates rather than duplicating.

Still in `n8n_arming.py`: change `disarm` so its targets are computed from the flags the fetched workflow ACTUALLY declares — `[flag for flag in sorted(OVERLAYABLE_FLAGS) if n8n_read.read_write_safety(original, flag).get("nodes")]`, falling back to `DISPATCH_FLAGS` when the workflow could not be read as a dict. Record in the docstring that disarm now means "put every write-safety constant this workflow declares back to its rest state", that this is what lets guardrail B's `_close_with_disarm` clear a stuck review authorization it did not open, and that it also clears a deploy-baked review arm on that workflow — a deliberate fail-safe, not an accident. Compute `_verify` and `expected` over that same derived list so a 4-constant test fixture still verifies exactly its 4. Give `armed_window.__init__` a keyword-only `authority=AUTHORITY_DISPATCH` passed through to `arm_for_dispatch` in `__enter__`; `__exit__` is unchanged because disarm no longer needs an authority. Add a module-level `armed_review_window(workflow_id, record_ids, record_domains, config, transport=None, grant=None)` factory returning `armed_window(..., allow_create=False, authority=AUTHORITY_REVIEW)`.

In `write_grant.py`: add `REVIEW_LANE = "review"` and `REVIEW_WORKFLOW_NAME = "LV Review Decision (Cloud)"` immediately above `LANES`, then add the `LANES[REVIEW_LANE] = REVIEW_WORKFLOW_NAME` entry. Directly below the existing `# D-59-07 AMENDMENT (operator, 2026-08-28):` block, append a new `# D-60-01/D-60-05 AMENDMENT (operator, 2026-09-01):` block in that same register — dated, naming Phase 60, stating that 30-01's D-02/D-08e separation between dispatch grants and review writeback is REVERSED because the two round trips it cost (a shell variable an operator in Claude Desktop cannot set, plus an admin-run deploy) made the documented operator path unreachable from the operator's chair; and stating what still holds: the review flag stays out of `DISPATCH_FLAGS`, arming review still grants nothing on the dispatch path, and the grant's record scoping still bounds every decision. Leave the original paragraph at lines 64-72 unedited — it is the code's own record of why the old design existed.

Still in `write_grant.py`: rewrite `plan_grant`'s unknown-lane refusal so it no longer asserts the review lane is not grantable (it now is) — keep the sentence naming the unknown lane(s) and listing `', '.join(sorted(LANES))`, and drop only the trailing claim about review. In `_consequence`, replace the multi-lane sentence that says the grant covers "both lanes at once" with wording derived from `len(lane_names)` and the lane names themselves, so a three-lane grant is described accurately; the per-lane sentence loop above it already names every lane individually and needs no change.

In `review_decision.py`: retire the environment kill switch. Delete the module constants that hold the variable name and its accepted value, delete the boolean helper that read it (the one sitting between those constants and `is_undoing`), delete the `_ENV_REFUSAL` message, and drop the now-unused `os` import. Amend the module docstring's numbered gate 1 and the paragraph beneath it with a dated `D-60-04 AMENDMENT (operator, 2026-09-01)` addendum in the same recorded-edit register used in `write_grant.py`: gate 1 is now grant-authorization, checked before any transport exists, and property (c) — the un-doing carve-out — SURVIVES, re-pointed at the grant check per D-60-07, because a closed authority must never strand a flagged record mid-decision. Add `GRANT_REFUSAL_REASON = "grant_not_authorized"` and a `_GRANT_REFUSAL` operator-facing message saying no write grant covering this record is open, that opening one is something the operator can do in this conversation once an n8n admin has enabled write grants, and that previewing and rejecting both still work without one. Give `submit_decision` a keyword `grant=None` between `review_armed` and `preview`; its new first gate is: when `is_undoing(decision)` is false, call `write_grant.authorize_send(grant, lane=write_grant.REVIEW_LANE, record_ids=[str(record_id)], record_domains=[])` and return `_unavailable(GRANT_REFUSAL_REASON, message=...)` when `armed` is falsey — preferring the authorization's own `detail` as the message when it carries one, so a scope refusal names the offending record instead of being reworded. Import `write_grant` inside the function body, matching this repo's cycle-avoidance house style. Leave the `review_armed` check exactly where it is, second and still required for both decisions. Rewrite the `__main__` diagnostic to report the grant-gate contract instead of an environment variable, printing no config value and no secret.

In `test_write_grant.py`: rewrite the two tests that pin the reversed design, under recorded-edit discipline — each keeps a docstring naming Phase 60, D-60-01 and the date 2026-09-01, and says what it used to assert and why that changed. Repoint the unknown-lane refusal test at a genuinely unknown lane name so the "unknown lane refuses by name" behavior stays pinned, and invert the not-grantable test into one asserting that the lane IS grantable while the flag-set SEPARATION survives — keep its second assertion, that the review flag is absent from `DISPATCH_FLAGS`, verbatim. Then add the tracer test as one function walking the whole path (behaviors 1 and 2 above), plus the three gate tests (behaviors 3-5), placed beside the existing grant tests.
  </action>

  <verify>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_review_decision.py operator-claude-plugin/tests/test_control_arming.py operator-claude-plugin/tests/test_control_flag_parity.py -x</automated>
    <fails_when>non-zero exit, or the word "failed" or "error" appears in the pytest summary line</fails_when>
    <automated>grep -c 'SUBMIT_ENV_VAR =' operator-claude-plugin/scripts/review_decision.py; grep -c 'def submit_enabled' operator-claude-plugin/scripts/review_decision.py</automated>
    <fails_when>either command prints anything other than `0`</fails_when>
    <automated>node --test tests/n8n/reviewWriteFlagSeparation.test.mjs</automated>
    <fails_when>non-zero exit, or the summary reports `fail 1` or higher</fails_when>
    <automated>git status --porcelain n8n/ | wc -l</automated>
    <fails_when>prints anything other than `0` — this task changes no workflow JSON</fails_when>
  </verify>

  <acceptance_criteria>
    - Source assertion: `grep -c 'REVIEW_FLAGS' operator-claude-plugin/scripts/n8n_arming.py` is at least 2, and `python3 -c "import sys; sys.path.insert(0,'operator-claude-plugin/scripts'); import n8n_arming; assert 'ALLOW_HUBSPOT_REVIEW_WRITES' not in n8n_arming.DISPATCH_FLAGS; assert 'ALLOW_HUBSPOT_RECORD_WRITES' not in n8n_arming.REVIEW_FLAGS"` exits 0.
    - Source assertion: `write_grant.LANES` has exactly three keys and `write_grant.LANES["review"] == "LV Review Decision (Cloud)"`.
    - Source assertion: the original review-exclusion paragraph is still present — `grep -c 'THE REVIEW LANE IS DELIBERATELY NOT GRANTABLE' operator-claude-plugin/scripts/write_grant.py` prints `1` — AND a dated `D-60-01/D-60-05 AMENDMENT` block follows it.
    - Behavior assertion: the tracer test records exactly one PUT that arms, one POST to the decision endpoint, and one PUT that disarms — and no recorded PUT body contains `ALLOW_HUBSPOT_RECORD_WRITES = "true"`.
    - Behavior assertion: an approve with no grant leaves the stub transport's call log empty; a reject with no grant reaches the POST.
    - Test command: the four-file pytest command above exits 0.
  </acceptance_criteria>

  <reversibility rating="costly">D-60-01/D-60-02: reversing means re-excluding the review flag from the grantable set and re-standing-up an independent review gate. D-60-03/D-60-04/D-60-05/D-60-07 within this task are reversible.</reversibility>

  <done>`"review"` is a grantable lane end-to-end: a planned-and-opened grant arms the review workflow through `n8n_arming`, gates `submit_decision`, bounds it to the grant's records, and disarms — with no environment variable read anywhere on the path, no workflow JSON changed, and the two reversed-design tests rewritten rather than deleted.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Rewrite the review-decision suite onto the grant gate</name>

  <read_first>
    - operator-claude-plugin/tests/test_review_decision.py (whole file — 502 lines; the two env fixtures at 42 and 47, the kill-switch section starting at 50, and the near-miss table at 82-102)
    - operator-claude-plugin/scripts/review_decision.py as left by Task 1
    - operator-claude-plugin/tests/conftest.py (the `stub_module_transport_factory` fixture and the autouse network guard)
    - .planning/phases/60-review-lane-authority/60-VALIDATION.md (rows for D-60-04 and D-60-07)
  </read_first>

  <files>operator-claude-plugin/tests/test_review_decision.py</files>

  <behavior>
    - Every test that currently sets or deletes the retired environment variable is repointed
      at a grant fixture: an open grant covering the record under test, a grant covering a
      DIFFERENT record, a closed grant, and `None`.
    - The near-miss table that pinned `"1"`/`"yes"`/`"TRUE"`/`"True"` as not-on is replaced by
      the grant-state near-miss set: `None`, a closed grant, a grant whose `lanes` omits
      `"review"`, a dict that is not a grant at all — each refuses with
      `grant_not_authorized` and an empty transport call log.
    - A reject proceeds under every one of those four states (D-60-07) and still refuses when
      `review_armed` is falsey.
    - `preview_decision` remains ungated: it works with no grant, no arm, and a closed grant.
    - The retired variable name appears in the file only inside a dated recorded-edit comment,
      never in a live assertion.
  </behavior>

  <action>
Rewrite `test_review_decision.py`'s gate-1 section against the grant. Delete the two monkeypatch fixtures that manipulated the retired environment variable and replace them with grant fixtures built through the real `write_grant.plan_grant`/`open_grant` pair where a transport stub makes that cheap, or with the minimal literal grant dict shape `covers` accepts (`kind`, `state`, `lanes`, `workflow_ids`, `record_ids`, `record_domains`) where it does not — prefer the real functions, and say in a comment which tests use which and why, so a later reader does not read the literal dicts as a second grant implementation. Head the rewritten section with a dated block comment naming Phase 60 and D-60-04/D-60-07, stating what these tests used to assert (an environment kill switch an admin set out of band), why that changed, and that the un-doing carve-out is re-pointed rather than removed. Keep the file's existing `stub_module_transport_factory` discipline throughout — no new fixture and no conftest edit. Assert the empty-call-log property on every refusal, because "no request was even built" is the property that made the old gate worth having and it must survive the swap. Leave the preview tests untouched apart from confirming they need no grant.
  </action>

  <verify>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_decision.py -q</automated>
    <fails_when>non-zero exit, or the summary line reports any failed or errored test</fails_when>
    <automated>grep -v '^#' operator-claude-plugin/tests/test_review_decision.py | grep -c 'submit_enabled'</automated>
    <fails_when>prints anything other than `0`</fails_when>
  </verify>

  <acceptance_criteria>
    - Test command: `.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_decision.py -q` exits 0 with zero skips introduced by this task.
    - Behavior assertion: a test exists in which an OPEN grant covering record X still refuses a decision on record Y, and the refusal message names Y.
    - Behavior assertion: a test exists in which `decision="reject"` succeeds with `grant=None` and `review_armed=True`, and another in which it refuses with `review_armed=False`.
    - Source assertion: `grep -c 'D-60-04' operator-claude-plugin/tests/test_review_decision.py` is at least 1 — the recorded-edit note is present.
    - CLI output: `.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_decision.py --collect-only -q | tail -1` reports a test count no lower than the pre-change count.
  </acceptance_criteria>

  <reversibility rating="reversible">D-60-04/D-60-07 are test-level re-pointings; reverting is a symmetric rewrite.</reversibility>

  <done>The review-decision suite pins the grant gate and the surviving un-doing carve-out, reads no environment variable, and every refusal still proves an empty transport call log.</done>
</task>

<task type="auto">
  <name>Task 3: Full-suite sweep and the plan's own commit</name>

  <read_first>
    - .planning/phases/60-review-lane-authority/60-VALIDATION.md § Sampling Rate
    - operator-claude-plugin/scripts/n8n_arming.py and operator-claude-plugin/scripts/write_grant.py as left by Task 1
  </read_first>

  <files>operator-claude-plugin/tests/test_control_arming.py, operator-claude-plugin/tests/test_write_grant_surface.py</files>

  <action>
Run all three suites and repair only what Task 1's two structural changes legitimately moved. Two shapes of breakage are expected and neither is a reason to weaken an assertion: (a) a test asserting `disarm`'s `observed` dict has exactly the four dispatch keys, now correct for whatever the fixture declares — update the fixture's expectation to the flags its own gate declares, never by loosening the comparison; (b) a test driving `arm_for_dispatch` positionally past `grant` — the new `authority` parameter is keyword-only precisely so this cannot happen, so if it does, the parameter was not made keyword-only and that is the fix. Any test failing for a third reason is a real defect in Task 1 and must be fixed in the source, not in the test. Do not touch `tests/n8n/reviewWriteFlagSeparation.test.mjs` — it pins the JSON-side invariant this phase must not violate, and it must pass unmodified.
  </action>

  <verify>
    <automated>.venv/bin/python -m pytest -q</automated>
    <fails_when>non-zero exit, or the summary line reports any failed or errored test</fails_when>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests -q</automated>
    <fails_when>non-zero exit, or the summary line reports any failed or errored test</fails_when>
    <automated>node --test tests/n8n/*.test.mjs</automated>
    <fails_when>non-zero exit, or the summary reports `fail 1` or higher</fails_when>
    <automated>git diff --stat -- tests/n8n/reviewWriteFlagSeparation.test.mjs | wc -l</automated>
    <fails_when>prints anything other than `0`</fails_when>
  </verify>

  <acceptance_criteria>
    - Test command: all three suite commands above exit 0.
    - CLI output: the root suite's pass count is at or above 3539 and the n8n suite's is at or above 844 (the Phase 61 close figures) — a lower count means tests were removed rather than repaired.
    - Source assertion: `tests/n8n/reviewWriteFlagSeparation.test.mjs` has no diff against `HEAD`.
    - Behavior assertion: no assertion was deleted to make a suite pass — `git diff -U0 -- operator-claude-plugin/tests | grep -c '^-[[:space:]]*assert '` is reviewed and every removal is accounted for by a rewritten test in Task 1 or Task 2.
  </acceptance_criteria>

  <done>All three suites are green, no assertion was weakened to get there, and the JSON-side flag-separation test passes unmodified.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| conversation → plugin client | An operator's "yes" becomes an authority object; nothing in the conversation may fabricate one that arms a backend whose admin never enabled write grants. |
| plugin client → n8n management API | A PUT rewrites `const` literals inside a deployed workflow; the diff must reach nothing but declaration lines. |
| n8n workflow → HubSpot | `_writeSafetyAllows("review", ...)` is the last gate before a PATCH; this plan changes its INPUTS, never the function. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-60-01 | Elevation of Privilege | `n8n_arming.arm_for_review` targets dict | high | mitigate | The review targets dict is built in its own branch and can never contain `ALLOW_HUBSPOT_RECORD_WRITES` or `ALLOW_HUBSPOT_CREATE`; `REVIEW_FLAGS` and `DISPATCH_FLAGS` stay separate tuples that no code path unions. Pinned by a Python test on the recorded PUT body and by `reviewWriteFlagSeparation.test.mjs` unmodified. |
| T-60-02 | Elevation of Privilege | `submit_decision` gate 1 | high | mitigate | Authorization routes through the single `write_grant.covers` implementation via `authorize_send(lane="review")`; no second scope check is written. A grant over A refuses a decision on B, pinned by test. |
| T-60-03 | Spoofing | a hand-built grant-shaped dict | high | mitigate | `covers` refuses anything whose `kind` is not `write_grant.KIND`, and `_arm_gate` re-reads the admin's settings key from config on every arm rather than trusting the grant object. Unchanged by this plan and asserted to stay so. |
| T-60-04 | Denial of Service | the retired kill switch | medium | accept | Retiring `ALLOW_REVIEW_SUBMIT` removes an out-of-band admin stop. Accepted per D-60-04: the admin's `allow_write_grants` settings key replaces it and is checked on every arm, and `n8n_arming.disarm` stays ungated so nothing can strand an armed backend. |
| T-60-05 | Tampering | the arming PUT's blast radius | medium | mitigate | `_assert_only_declaration_lines_changed` is threaded the review flag set, so a review arm that reached beyond its declaration lines refuses exactly as a dispatch arm does. |
| T-60-SC | Tampering | npm/pip/cargo installs | high | mitigate | Not applicable — this plan installs no package. `60-RESEARCH.md` § Package Legitimacy Audit records the same. No install task exists, so no legitimacy checkpoint is required. |
</threat_model>

<artifacts_this_phase_produces>
## Artifacts this phase produces (whole phase, not only this plan)

**New constants**
- `n8n_arming.REVIEW_FLAGS` — `("ALLOW_HUBSPOT_REVIEW_WRITES", "TEST_RECORD_IDS", "TEST_RECORD_DOMAINS")` (plan 01)
- `n8n_arming.AUTHORITY_DISPATCH`, `n8n_arming.AUTHORITY_REVIEW`, `n8n_arming.FLAGS_BY_AUTHORITY` (plan 01)
- `write_grant.REVIEW_LANE` = `"review"` (plan 01)
- `write_grant.REVIEW_WORKFLOW_NAME` = `"LV Review Decision (Cloud)"` (plan 01)
- `write_grant.LANES["review"]` — the third lane entry (plan 01)
- `review_decision.GRANT_REFUSAL_REASON` = `"grant_not_authorized"` and `review_decision._GRANT_REFUSAL` (plan 01)
- `written_records.REVIEW_OUTCOME_TO_OUTCOME` (plan 03)

**New functions / signatures**
- `n8n_arming.arm_for_review(workflow_id, record_ids, record_domains, config, transport=None, grant=None)` (plan 01)
- `n8n_arming.armed_review_window(workflow_id, record_ids, record_domains, config, transport=None, grant=None)` (plan 01)
- `arm_for_dispatch(..., *, authority=AUTHORITY_DISPATCH)` and `armed_window(..., *, authority=AUTHORITY_DISPATCH)` — new keyword-only parameter (plan 01)
- `n8n_arming.disarm` — targets now derived from the flags the fetched workflow declares (plan 01)
- `review_decision.submit_decision(..., grant=None, ..., run_id=None)` — two new keywords (plans 01 and 03)
- `write_grant.authorize_review_batch(grant)` (plan 02)
- `written_records.classify_review_item(item)` (plan 03)
- `written_records.append_chunk(..., classify=classify_item)` — new keyword (plan 03)

**Retired**
- `review_decision.SUBMIT_ENV_VAR`, `SUBMIT_ENV_VALUE`, `submit_enabled()`, `_ENV_REFUSAL` (plan 01)

**Widened**
- `write_grant.WRITE_ENABLING_FLAGS` — 2 items → 3 (plan 02)
- `write_grant.read_live_write_state` / `guardrail_a` — read all five overlayable flags (plan 02)

**New / rewritten tests**
- `test_write_grant.py`: the review tracer walk; the repointed unknown-lane refusal; the inverted grantable-lane test keeping the flag-separation half; the out-of-scope review refusal (plan 01)
- `test_review_decision.py`: the grant-state near-miss set; the surviving un-doing carve-out (plans 01, 02)
- `test_write_grant_guardrails.py`: `_gate()` gains a fifth constant; the dirty-review-flag refusal; the batch-window lifecycle including revoke-mid-batch (plan 02)
- `test_written_records.py`: review-outcome mapping; a poisoned reason that never raises; an append failure that never aborts the write (plan 03)

**New / changed files**
- `n8n/code/reviewDecision.js` — the `not_allowlisted` message text (plan 04)
- `n8n/wf_review_decision_cloud.json` — regenerated, message text only (plan 04)
- `operator-claude-plugin/skills/review-triage/SKILL.md`, `skills/enrich-records/SKILL.md`, `skills/enrich-before-ingest/SKILL.md`, `README.md`, `USAGE.md`, `CHANGELOG.md` (plan 04)
- `operator-claude-plugin/.claude-plugin/plugin.json` — version `0.34.0` → `0.35.0` (plan 04)
</artifacts_this_phase_produces>

<verification>
- All three suites green: `.venv/bin/python -m pytest -q`, `.venv/bin/python -m pytest operator-claude-plugin/tests -q`, `node --test tests/n8n/*.test.mjs`.
- `git status --porcelain n8n/` is empty — this plan changes no workflow JSON and no generator.
- The review-exclusion comment survives with a dated addendum beside it.
- Nothing is armed, nothing is deployed, no HubSpot request and no provider call is made.
</verification>

<success_criteria>
A grant naming the review lane can be planned, opened, used to arm the review workflow, used to authorize one decision, and disarmed — entirely from Python driven by tests, with `ALLOW_HUBSPOT_RECORD_WRITES` never set true on that path and no shell environment variable read.
</success_criteria>

<output>
Create `.planning/phases/60-review-lane-authority/60-01-SUMMARY.md` when done
</output>


### Plan 2 of 4
---
phase: 60-review-lane-authority
plan: 02
type: execute
wave: 2
depends_on: ["60-01"]
files_modified:
  - operator-claude-plugin/scripts/write_grant.py
  - operator-claude-plugin/tests/test_write_grant_guardrails.py
  - operator-claude-plugin/tests/test_write_grant.py
  - operator-claude-plugin/tests/test_write_grant_surface.py
autonomous: true
requirements: [D-60-03, D-60-05, D-60-06]
user_setup: []

estimate:
  tokens: 62000
  raw_tokens: 62000
  tasks: 2
  confidence: low

must_haves:
  truths:
    - "D-60-06: ONE arm window covers a whole batch of review decisions — the window's allowlist is fixed to the grant's own record list at open time, it never grows as records are triaged, and it disarms on the normal exit, on a mid-batch exception, and after a mid-batch revocation."
    - "D-60-03: inside that batch window, EACH decision is still scoped per record through `write_grant.authorize_send(lane=\"review\")` — a record the grant does not name is refused even while the window is open."
    - "D-60-05 consequence (research finding, Pitfall 1): Guardrail A can now SEE a stuck-open `ALLOW_HUBSPOT_REVIEW_WRITES` and refuses to open a grant over it — the blind spot that would otherwise let a crashed prior session's review authorization survive unnoticed."
  artifacts:
    - operator-claude-plugin/scripts/write_grant.py
    - operator-claude-plugin/tests/test_write_grant_guardrails.py
  key_links:
    - "`write_grant.read_live_write_state` -> all five `n8n_arming.OVERLAYABLE_FLAGS` -> `_live_write_faults` -> `guardrail_a`'s refusal, which now names a live review flag."
    - "`write_grant.authorize_review_batch(grant)` -> `n8n_arming.armed_review_window(grant.record_ids, grant.record_domains)` -> per-decision `authorize_send(lane=\"review\", record_ids=[one])`."
---

<objective>
Close the two gaps Plan 01's tracer leaves open: the dirty-backend guardrail cannot yet see a
stuck-open review authorization, and there is no batch-scoped window for a triage session.

Purpose: Guardrail A exists to catch an authorization a previous session left live. The
moment review became grantable it acquired exactly that failure mode and exactly that blind
spot. D-60-06's batch window is the other half — a triage sitting should cost one arm/disarm
round trip, not one per record, without loosening the per-record scope check.

Output: a widened Guardrail A that reads all five overlayable flags, the test fixtures that
widening legitimately breaks, `authorize_review_batch`, and a lifecycle test covering the
normal, crashed and revoked exits.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/60-review-lane-authority/60-CONTEXT.md
@.planning/phases/60-review-lane-authority/60-RESEARCH.md
@.planning/phases/60-review-lane-authority/60-PATTERNS.md
@.planning/phases/60-review-lane-authority/60-01-SUMMARY.md
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Teach Guardrail A to see a stuck-open review authorization</name>

  <read_first>
    - operator-claude-plugin/scripts/write_grant.py lines 1520-1752 (the guardrail A/B asymmetry comment, the local `WRITE_ENABLING_FLAGS` at 1556, `_enabled`, `read_live_write_state` at 1572-1609 including the `DISPATCH_FLAGS` loop at 1599 and the `readable` line at 1605, `_live_write_faults`, `guardrail_a` including its flag-render line at 1663, `_close_with_disarm`, `preflight_before_send`)
    - operator-claude-plugin/scripts/n8n_arming.py lines 46-57 (`OVERLAYABLE_FLAGS`, the module-level `WRITE_ENABLING_FLAGS` frozenset that ALREADY includes the review flag, `ALLOWLIST_FLAGS`)
    - operator-claude-plugin/tests/test_write_grant_guardrails.py lines 1-145 (the `_gate()` helper at 37-42, `_workflow()` at 44-60, and the armed-backend test at 119-140 whose `live_flags` list assertion is order-sensitive)
    - operator-claude-plugin/tests/test_write_grant.py line ~38 and operator-claude-plugin/tests/test_write_grant_surface.py line ~39 (the two other four-constant gate fixtures that drive `plan_grant`)
    - .planning/phases/60-review-lane-authority/60-RESEARCH.md § Common Pitfalls, Pitfalls 1 and 2
  </read_first>

  <files>operator-claude-plugin/scripts/write_grant.py, operator-claude-plugin/tests/test_write_grant_guardrails.py, operator-claude-plugin/tests/test_write_grant.py, operator-claude-plugin/tests/test_write_grant_surface.py</files>

  <behavior>
    - Test 1: a workflow whose gate declares `ALLOW_HUBSPOT_REVIEW_WRITES` enabled while both
      dispatch booleans read disabled REFUSES the open, and the refusal names the review flag
      and the allowlist currently in force.
    - Test 2: the existing armed-backend test still reports `live_flags` as exactly
      `["ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE"]` when the review flag reads
      disabled — the widening must not reorder or pollute that list.
    - Test 3: a workflow that declares only the four dispatch constants and none of the review
      one is `readable: False` and refuses — an unreadable state is never evidence of a
      disarmed backend, and this is the direction the widening deliberately fails in.
    - Test 4: a fully disarmed five-constant workflow still proceeds (`guardrail_a` returns
      `None`).
  </behavior>

  <action>
Widen the local `WRITE_ENABLING_FLAGS` tuple in `write_grant.py` to three items by APPENDING `"ALLOW_HUBSPOT_REVIEW_WRITES"` last — order is load-bearing because `_live_write_faults` builds `live_flags` by iterating it and an existing test asserts that list exactly. Amend the comment above it with a dated `D-60-01 consequence (2026-09-01)` note: review became grantable, so a stuck-open review authorization is now exactly the kind of state Guardrail A exists to find, and a two-flag tuple was structurally unable to find it. Change `read_live_write_state`'s per-lane loop from `n8n_arming.DISPATCH_FLAGS` to `sorted(n8n_arming.OVERLAYABLE_FLAGS)` and change `guardrail_a`'s flag-render expression to iterate that same sorted list, so what the refusal prints and what the check read are one list. Update `read_live_write_state`'s docstring: it reads all five overlayable constants per lane, uniformly, because every deployed workflow built from the shared write-safety gate declares all five regardless of which ones it branches on — verified against the committed enrichment, contacts and review workflow JSON — so this is not overreach onto lanes that predate review.

Then fix the fixtures the widening legitimately breaks. In `test_write_grant_guardrails.py`, give `_gate()` a fifth keyword defaulting to the disarmed literal and emit a fifth `const` line for the review flag; thread it through `_workflow()`. Do the same to the four-constant gate builders in `test_write_grant.py` and `test_write_grant_surface.py`. Add a dated comment at `_gate()` saying the fifth constant matches the deployed shape and that omitting it makes every disarmed-backend test read as unreadable — the failure mode is loud, and this note is what stops a future reader from "fixing" it by narrowing the guardrail instead. Then run the whole plugin suite: any OTHER fixture that drives `plan_grant` or `guardrail_a` through a four-constant gate will surface as "its write-safety state could not be read at all"; add the fifth constant to those too, and never loosen the `readable` check to accommodate one.

Add the four tests above beside the existing guardrail-A cases.
  </action>

  <verify>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant_guardrails.py operator-claude-plugin/tests/test_write_grant.py operator-claude-plugin/tests/test_write_grant_surface.py -x</automated>
    <fails_when>non-zero exit, or the phrase "could not be read at all" appears in a failure message from a test that is supposed to proceed</fails_when>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests -q</automated>
    <fails_when>non-zero exit, or the summary line reports any failed or errored test</fails_when>
  </verify>

  <acceptance_criteria>
    - Source assertion: `python3 -c "import sys; sys.path.insert(0,'operator-claude-plugin/scripts'); import write_grant; assert write_grant.WRITE_ENABLING_FLAGS[-1] == 'ALLOW_HUBSPOT_REVIEW_WRITES' and len(write_grant.WRITE_ENABLING_FLAGS) == 3"` exits 0.
    - Source assertion: `grep -v '^#' operator-claude-plugin/scripts/write_grant.py | grep -c 'for flag in n8n_arming.DISPATCH_FLAGS'` prints `0`.
    - Behavior assertion: a grant plan over a backend whose ONLY live flag is the review flag returns `outcome == write_grant.REFUSED` with `faults[lane]["live_flags"] == ["ALLOW_HUBSPOT_REVIEW_WRITES"]`.
    - Behavior assertion: the pre-existing armed-backend test's `live_flags` assertion passes unmodified.
    - Test command: the plugin suite exits 0 with no test skipped or deleted to get there.
  </acceptance_criteria>

  <reversibility rating="reversible">Narrowing the read back to the dispatch flags is a two-line revert; the fixture fifth constant is harmless if left.</reversibility>

  <done>Guardrail A reads all five overlayable constants per lane, refuses an open over a backend where only the review flag is live, names it in the refusal, and every fixture that drives it declares the shape a real deployed workflow has.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: One batch window for a triage sitting</name>

  <read_first>
    - operator-claude-plugin/scripts/write_grant.py lines 1292-1352 (`authorize_send`, especially the two "WHAT IT DELIBERATELY DOES NOT DO" paragraphs — the new function diverges from the first of them and must say so) and 1143-1205 (`covers`)
    - operator-claude-plugin/scripts/write_grant.py lines 1446-1500 (`record_send_outcome`) and 1254-1290 (`revoke_grant`)
    - operator-claude-plugin/scripts/write_grant.py lines 1720-1752 (`preflight_before_send` — the trap named in this task's action)
    - operator-claude-plugin/scripts/n8n_arming.py lines 475-513 (`armed_window`, and `armed_review_window` as Plan 01 left it)
    - operator-claude-plugin/tests/test_write_grant_guardrails.py (the guardrail-B lifecycle tests, as the shape to mirror)
    - .planning/phases/60-review-lane-authority/60-CONTEXT.md § D-60-06 and its "Note for planner"
  </read_first>

  <files>operator-claude-plugin/scripts/write_grant.py, operator-claude-plugin/tests/test_write_grant_guardrails.py</files>

  <behavior>
    - Test 1: `authorize_review_batch` on an open three-lane grant returns `armed: True`, the
      review workflow id, and the grant's OWN `record_ids`/`record_domains` lists.
    - Test 2: on a grant whose `lanes` omits `"review"` it returns `armed: False` with a
      refusal naming the lane; on a closed grant it refuses naming the close reason.
    - Test 3: one window, three decisions — the arm PUT happens once, three decision POSTs
      follow, the disarm PUT happens once, and the allowlist in the arm PUT is the grant's
      record list and does not change between decisions.
    - Test 4: a decision on a record the grant does not name is refused by `authorize_send`
      WHILE the window is open, and the window still disarms on exit.
    - Test 5: an exception raised by the second of three decisions propagates AND the window
      still disarms (the `armed_window.__exit__` guarantee, unchanged).
    - Test 6: `revoke_grant` called after the first decision makes the second decision's
      `authorize_send` refuse (the grant is closed), and the window still disarms on exit.
  </behavior>

  <action>
Add `authorize_review_batch(grant)` to `write_grant.py`, placed directly below `authorize_send` so a reader meets them together. It returns the same `{armed, workflow_id, grant, refusal, detail}` shape every other authorization in this module returns, PLUS `record_ids` and `record_domains` — the grant's own lists, normalised through `_normalise`. Compose the refusal through `check_before_send(grant, lane=REVIEW_LANE, workflow_id=..., record_ids=grant's ids, record_domains=grant's domains)` so a closed grant, a missing lane and a bad kind all refuse in the existing wordings rather than in new ones. Give it a docstring that states the deliberate divergence plainly: `authorize_send` refuses to return a record list precisely so a caller cannot widen a per-send window to the grant's whole batch, and this function returns one on purpose because D-60-06 makes the review window batch-scoped — its allowlist IS the grant's scope, fixed at open time, and it must never grow as records are triaged. Say what still bounds it: `covers` already refused anything outside the grant before this returned, and every individual decision is still scoped per record through `authorize_send(lane=REVIEW_LANE, record_ids=[that one record])`, so the window being wide never widens what a decision may approve. Say what it is not for: it takes a lane argument nowhere and refuses on any grant not covering review, so a dispatch caller cannot reach it by passing a different lane name.

Record one trap in the same docstring, because it is invisible and expensive: `preflight_before_send` must NOT be called on the review lane while the batch window is open. Now that the local `WRITE_ENABLING_FLAGS` includes the review flag, that pre-flight would read the window's own arm as "writes still live", close the grant and disarm mid-batch. Guardrail B's pre-send read is for the per-send dispatch shape where no window is open between sends; the batch window's own guaranteed disarm is what covers this lane instead.

Add the six tests above to `test_write_grant_guardrails.py`, in a new section headed with a dated comment naming D-60-06 and stating that no existing test in this repo exercised a multi-decision single window for any lane, so this coverage is genuinely new rather than a copy. Drive them through the existing `stub_module_transport_factory` recorder and assert on the recorded call sequence, not only on returned dicts — the "arm once, disarm once" property is only visible in the call log.
  </action>

  <verify>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant_guardrails.py -x</automated>
    <fails_when>non-zero exit, or the summary line reports any failed or errored test</fails_when>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests -q && .venv/bin/python -m pytest -q</automated>
    <fails_when>non-zero exit from either suite, or either summary line reports a failed or errored test</fails_when>
  </verify>

  <acceptance_criteria>
    - Behavior assertion: in the three-decision test, the recorded transport shows exactly two PUTs (one arm, one disarm) and three POSTs to the decision path.
    - Behavior assertion: the arm PUT's `TEST_RECORD_IDS` literal equals the grant's own comma-joined ids, and is byte-identical before and after each decision.
    - Behavior assertion: the crashed-mid-batch test asserts the original exception type propagates AND `window.disarm_result["outcome"]` is `n8n_arming.DISARMED`.
    - Behavior assertion: the revoked-mid-batch test asserts the second `authorize_send` returns `armed: False` with a detail naming the close reason, and the disarm still ran.
    - Source assertion: `grep -c 'preflight_before_send' operator-claude-plugin/scripts/write_grant.py` is at least 2 — the trap note references it by name in `authorize_review_batch`'s docstring.
    - Test command: both suite commands above exit 0.
  </acceptance_criteria>

  <reversibility rating="costly">D-60-06: a batch-scoped window's lifecycle (open once, disarm on crash mid-batch, behave under a mid-batch revocation) is more involved to build than per-decision arm/disarm; reversing to per-decision means re-deriving that lifecycle rather than trimming this one.</reversibility>

  <done>`authorize_review_batch` exists, one window covers a whole triage sitting with an allowlist fixed to the grant at open time, every decision inside it is still scoped per record, and the window disarms on the normal, crashed and revoked exits — all three proven from the recorded call log.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| a previous session → this session's grant open | State this process did not create: a backend left armed by a session that died mid-window. |
| batch window → the individual decisions inside it | The window is grant-wide; each decision must still be record-scoped. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-60-06 | Tampering / Repudiation | `guardrail_a` blind to `ALLOW_HUBSPOT_REVIEW_WRITES` | high | mitigate | Widen `read_live_write_state` to all five overlayable flags and the local `WRITE_ENABLING_FLAGS` to include the review flag, so a stuck-open review authorization refuses the next grant open by name. Task 1's Test 1 pins it. |
| T-60-07 | Elevation of Privilege | the batch window's grant-wide allowlist | high | mitigate | The window's allowlist is fixed to the grant's own list at open time and never grows; every decision inside it still passes `authorize_send(lane="review", record_ids=[one record])`, so a wide window never widens what a decision may approve. Task 2's Test 4 pins it. |
| T-60-08 | Denial of Service | `preflight_before_send` on the review lane mid-batch | medium | mitigate | Documented as prohibited in `authorize_review_batch`'s own docstring: with the widened flag set it would read the window's own arm as live, close the grant and disarm mid-batch. The batch window's guaranteed disarm covers this lane instead. |
| T-60-09 | Repudiation | a crashed or revoked batch leaving the review flag live | high | mitigate | `armed_window.__exit__`'s existing "never swallow the body's exception, still disarm" guarantee is reused unchanged; Tests 5 and 6 prove the disarm ran on both exits. Plan 01's widened `disarm` clears every declared overlayable constant, so guardrail B's own close path can clear a review arm too. |
| T-60-SC | Tampering | npm/pip/cargo installs | low | accept | No package is installed by this plan; `60-RESEARCH.md` records the same. No install task exists. |
</threat_model>

<artifacts_this_plan_produces>
- `write_grant.WRITE_ENABLING_FLAGS` widened from 2 to 3 items (review flag appended last, order load-bearing)
- `write_grant.read_live_write_state` / `guardrail_a` now read `sorted(n8n_arming.OVERLAYABLE_FLAGS)`
- `write_grant.authorize_review_batch(grant)` — new function returning `{armed, workflow_id, grant, refusal, detail, record_ids, record_domains}`
- `_gate()` / gate-builder fixtures in `test_write_grant_guardrails.py`, `test_write_grant.py`, `test_write_grant_surface.py` gain a fifth declared constant
- New tests: a dirty-review-flag refusal, an unreadable-review-flag refusal, and the six-case batch-window lifecycle (normal, out-of-scope, crashed, revoked)

The full phase-level artifact list is in `60-01-PLAN.md` § Artifacts this phase produces.
</artifacts_this_plan_produces>

<verification>
- `.venv/bin/python -m pytest -q` and `.venv/bin/python -m pytest operator-claude-plugin/tests -q` both green.
- `node --test tests/n8n/*.test.mjs` green — this plan touches no JS and no workflow JSON.
- `git status --porcelain n8n/` empty.
- Nothing armed, nothing deployed, no HubSpot request, no provider call.
</verification>

<success_criteria>
A grant cannot be opened over a backend where a review authorization is stuck live, and a
triage sitting costs exactly one arm and one disarm however many records it works — with
every individual decision still bounded by the grant's own record set.
</success_criteria>

<output>
Create `.planning/phases/60-review-lane-authority/60-02-SUMMARY.md` when done
</output>


### Plan 3 of 4
---
phase: 60-review-lane-authority
plan: 03
type: execute
wave: 2
depends_on: ["60-01"]
files_modified:
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/scripts/review_decision.py
  - operator-claude-plugin/tests/test_written_records.py
  - operator-claude-plugin/tests/test_review_decision.py
autonomous: true
requirements: [D-60-08]
user_setup: []

estimate:
  tokens: 60000
  raw_tokens: 60000
  tasks: 2
  confidence: low

must_haves:
  truths:
    - "D-60-08: a review decision appears in the per-run `written_records-<run_id>.json` artifact, so one artifact answers \"what did this session write to HubSpot\" across all three grantable lanes."
    - "D-60-08 carries D-59-09: the artifact is keyed by a `run_id` minted once per triage batch — one file per run, readers glob and union, never a shared append."
    - "D-60-08 carries D-59-10: a written-records failure NEVER stops or aborts a review write — the write's own outcome is returned regardless, with the bookkeeping failure recorded in the returned envelope and surfaced loudly."
  artifacts:
    - operator-claude-plugin/scripts/written_records.py
    - operator-claude-plugin/scripts/review_decision.py
    - operator-claude-plugin/tests/test_written_records.py
  key_links:
    - "`review_decision.submit_decision(run_id=...)` -> `written_records.append_chunk(run_id, 0, response_item, classify=classify_review_item)` -> `durable_paths._atomic_write_0600`, called AFTER the POST returns, never before."
    - "`classify_review_item` -> `REVIEW_OUTCOME_TO_OUTCOME` -> the SAME eight-word vocabulary `report_enrichment` and `run_report` already key on, so no downstream reader learns a new word."
---

<objective>
Make a review decision show up in the run's durable "what actually got written" artifact,
using the artifact's existing per-run file, existing entry shape and existing eight-word
outcome vocabulary — and make it structurally impossible for that bookkeeping to stop a
write.

Purpose: now that all three lanes are grantable, one artifact should answer "what did this
session write to HubSpot" for all three. Review decisions go through `submit_decision`, never
`chunking.dispatch_plan`, so this is new plumbing rather than a reused call site — and the
review response's five-key contract carries no `action`, no `hs_object_id` and no `row_id`,
so `classify_item` cannot be pointed at it as-is.

Output: `classify_review_item`, `REVIEW_OUTCOME_TO_OUTCOME`, a `classify=` keyword on
`append_chunk`, a `run_id` keyword on `submit_decision`, and the two failure-mode tests that
prove the write always wins over the bookkeeping.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/60-review-lane-authority/60-CONTEXT.md
@.planning/phases/60-review-lane-authority/60-RESEARCH.md
@.planning/phases/60-review-lane-authority/60-PATTERNS.md
@.planning/phases/59-frictionless-write-path/59-CONTEXT.md
@.planning/phases/60-review-lane-authority/60-01-SUMMARY.md
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: A review decision, in the artifact's own vocabulary</name>

  <read_first>
    - operator-claude-plugin/scripts/written_records.py (whole file; especially the module docstring, `_FORBIDDEN_NAME_MARKERS` at 180-183 — note `arm`, `grant` and `permission` are SUBSTRING markers — the eight outcome constants at 137-156, `WRITE_ACTIONS`/`ACTION_TO_OUTCOME` at 158-176, `written_records_path` at 206-216, `outcome_for_action` at 219-245, `classify_item` at 248-304, `append_chunk` at 353-405)
    - operator-claude-plugin/scripts/review_decision.py as Plan 01 left it (the outcome vocabulary at 96-98, `_unavailable` at 148-150, `_post_decision`'s success return at 202-210, `submit_decision`)
    - operator-claude-plugin/scripts/report_enrichment.py lines 100-115 (the counter keyed on `written_records.ALL_OUTCOMES`, the reason review outcomes must map INTO that vocabulary rather than add words to it)
    - operator-claude-plugin/scripts/run_report.py lines 697-712 (`_build_run_report`'s glob-and-filter-by-run_id read, the consumer of these entries)
    - .planning/phases/60-review-lane-authority/60-PATTERNS.md § written_records.py (the shape-mismatch analysis)
  </read_first>

  <files>operator-claude-plugin/scripts/written_records.py, operator-claude-plugin/tests/test_written_records.py</files>

  <behavior>
    - Test 1: `classify_review_item` on an `applied` approve with a record id returns an entry
      whose `outcome` is `WRITE_ATTEMPTED`, `action` is `review_approve`, `hs_object_id` is the
      record id, and `reason`/`row_id`/`association` are all `None`.
    - Test 2: `rejected` maps the same way with `action` `review_reject`.
    - Test 3: `not_allowlisted` maps to `GATED`; `stale`, `no_candidate` and `not_flagged` map
      to `NO_ACTION`; `refused` maps to `FAILED`.
    - Test 4: an `{available: False, ...}` envelope and an unrecognised outcome word both map
      to `FAILED` — never to a silent success.
    - Test 5: every value `classify_review_item` can produce for `outcome` is in
      `written_records.ALL_OUTCOMES` — derived from the constant, not restated.
    - Test 6: the entry's key set is exactly `classify_item`'s seven keys, so `run_report` and
      `report_enrichment` need no change.
    - Test 7: `append_chunk(..., classify=classify_review_item)` writes a document at
      `written_records_path(run_id)` whose `run_id` field is that run id, and appends to a
      second call rather than replacing it.
  </behavior>

  <action>
Add `REVIEW_OUTCOME_TO_OUTCOME` to `written_records.py`, directly below `ACTION_TO_OUTCOME`, mapping the review endpoint's seven outcome words onto the existing eight-word vocabulary: `applied` and `rejected` to `WRITE_ATTEMPTED`; `not_allowlisted` to `GATED`; `stale`, `no_candidate` and `not_flagged` to `NO_ACTION`; `refused` to `FAILED`. Comment the two choices a reader will question. First, why `WRITE_ATTEMPTED` and not `WRITTEN`: `outcome_for_action`'s own rule is that an id known before the write proves only that the write was attempted, and a review decision always names its record up front, so `WRITE_ATTEMPTED` is the honest word — and the response's `verified` field is explicitly documented in `review_decision.verify_decision` as a convenience and never the authority, so this module must not promote an entry on the strength of it. Second, why `not_allowlisted` is `GATED` and not `FAILED`: it is the deployed write gate refusing, the same event `write_blocked` already maps to `GATED` for dispatch, and calling one of them a failure and the other a gate would split one fact across two words.

Add `classify_review_item(item)` beside `classify_item`, pure and no I/O, raising `WrittenRecordsError` on a non-dict for the same fail-loud reason. It reads `object_type`, `record_id`/`hs_object_id`, `decision` and `outcome` off the item and emits EXACTLY `classify_item`'s seven keys: `object_type` (defaulting to `"contacts"`, matching `classify_item`'s own default so one convention exists), `action` as `review_approve` or `review_reject` derived from the decision word (anything else is `review_unknown`), `hs_object_id`, `outcome` from the mapping with `FAILED` as the total fallback, and `reason`, `row_id`, `association` all `None`. Document why `reason` is deliberately `None` and must stay so: the operator's own words already live on the record itself in `lv_enrichment_review_reason`, so the artifact loses nothing by omitting them — and free operator prose containing `arm`, `grant` or `permission` would trip `_looks_forbidden`, which is a substring check, and raise on a bookkeeping write that must never be able to raise. Run the same `_looks_forbidden` sweep over the finished entry that `classify_item` runs, so the Phase 23 D-11 guarantee holds identically on this path.

Give `append_chunk` a keyword-only `classify=classify_item` parameter and call `classify(item)` in its comprehension instead of the hard-coded name. Amend its docstring's "two call sites" paragraph to three, naming `review_decision.submit_decision` as the third and stating that its `chunk_index` is always `0` because that function sends exactly one request per decision, exactly as `dispatch.dispatch` already does — and that entries accumulate across decisions because a document already at this path is always this run's own earlier writes (D-59-09).

Add the seven tests above to `test_written_records.py`, in a section headed with a dated comment naming D-60-08 and stating why the review response could not be fed to `classify_item` unmodified: it carries no `action` key at all, so `outcome_for_action(None, ...)` would resolve every single review decision through the `FAILED` fallback — an approve that landed would be filed as a failure. Keep the file's existing discipline of redirecting `written_records_path` to a `tmp_path` through monkeypatch; never touch the operator's real durable directory.
  </action>

  <verify>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py -x</automated>
    <fails_when>non-zero exit, or the summary line reports any failed or errored test</fails_when>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_run_report.py operator-claude-plugin/tests/test_report_enrichment.py -q</automated>
    <fails_when>non-zero exit — a review entry must not change what an existing artifact reader sees</fails_when>
  </verify>

  <acceptance_criteria>
    - Source assertion: `python3 -c "import sys; sys.path.insert(0,'operator-claude-plugin/scripts'); import written_records as w; assert set(w.REVIEW_OUTCOME_TO_OUTCOME.values()) <= w.ALL_OUTCOMES"` exits 0.
    - Behavior assertion: `classify_review_item({'outcome': 'applied', 'decision': 'approve', 'record_id': '9605284724', 'object_type': 'companies'})` returns a dict whose keys equal `classify_item`'s key set and whose `reason` is `None`.
    - Behavior assertion: `classify_review_item({'available': False, 'reason': 'endpoint_unreachable'})` returns `outcome == written_records.FAILED`.
    - Behavior assertion: an item whose `decision` is the string `"approve"` but whose operator-supplied text elsewhere contains a forbidden marker still classifies without raising, because no free text reaches the entry.
    - Test command: both pytest commands above exit 0.
  </acceptance_criteria>

  <reversibility rating="costly">D-60-08: review decisions never pass through `chunking.dispatch_plan`, so this is a second writer of the artifact rather than a reused call site; removing it later means unpicking that second writer.</reversibility>

  <done>A review decision maps into the artifact's existing seven-key entry and eight-word outcome vocabulary, carries no free text, and `append_chunk` can write it without a second atomic-write implementation.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Wire it at the write, and make the bookkeeping unable to stop it</name>

  <read_first>
    - operator-claude-plugin/scripts/review_decision.py as Plan 01 left it (`submit_decision`, `_post_decision`, `_unavailable`)
    - operator-claude-plugin/scripts/chunking.py lines 530-560 (the canonical `append_chunk` call site, INSIDE the loop immediately after the response is appended — the placement rule this task copies) and lines 25-45 (the docstring paragraph on the two ways `append_chunk` can go short)
    - operator-claude-plugin/scripts/dispatch.py lines 95-115 (the single-request call site, the closer analog for review)
    - operator-claude-plugin/scripts/run_state.py (`new_run_id` — the minter the skills already use)
    - operator-claude-plugin/scripts/remainder_queue.py lines 225-240 (the precedent for a catch WIDER than `OSError`, and its stated reason)
    - .planning/phases/59-frictionless-write-path/59-CONTEXT.md § D-59-09 and D-59-10
  </read_first>

  <files>operator-claude-plugin/scripts/review_decision.py, operator-claude-plugin/tests/test_review_decision.py</files>

  <behavior>
    - Test 1: `submit_decision(..., run_id="r-1")` on a successful approve writes one entry to
      `written_records_path("r-1")`, and the returned envelope is unchanged from the no-run_id
      case apart from a new `written_records` key reporting `True`.
    - Test 2: with `run_id=None` nothing is written and no path is resolved — the artifact is
      opt-in, and a caller that never passes a run id behaves exactly as before this plan.
    - Test 3: the append is called AFTER the POST — a transport whose POST raises never
      reaches the artifact, and the returned envelope is the ordinary `endpoint_unreachable`
      one.
    - Test 4 (D-59-10, the load-bearing one): with `append_chunk` monkeypatched to raise
      `OSError`, `submit_decision` still returns the write's own outcome, and the envelope's
      `written_records` key reports the failure rather than swallowing it.
    - Test 5 (D-59-10, second shape): with `append_chunk` monkeypatched to raise
      `WrittenRecordsError`, the same holds — this is the shape that DOES propagate out of
      `append_chunk` by design, so the review call site is the one that must contain it.
    - Test 6: three decisions under one `run_id` produce three entries in ONE file, and a
      fourth decision under a different `run_id` produces a separate file.
  </behavior>

  <action>
Give `submit_decision` a keyword-only `run_id=None` appended after `transport`. After `_post_decision` returns and only then, when `run_id` is not None, build the item the classifier reads — `object_type`, the record id, the decision word and the response's `outcome` — and call `written_records.append_chunk(run_id, 0, item, classify=written_records.classify_review_item)` inside a `try` whose `except` catches `Exception`, not `OSError`. Say why the wider catch, citing `remainder_queue.py`'s own precedent: `append_chunk` swallows `OSError` but deliberately propagates `WrittenRecordsError`, and on the dispatch path that propagation is correct because a shape defect there is a defect in the backend's own response — but here the item is built locally and a bookkeeping refusal must never convert into a mid-decision stop, which is exactly what D-59-10 forbids. Attach the result to the returned envelope under a `written_records` key: `True` on success, `False` when the append returned falsey, and a short refusal string naming the exception TYPE (never its text, which can carry a path or a header) when it raised. Do not swallow it silently and do not log it away — the key is what makes the failure loud. Import `written_records` at module top level; it imports only `durable_paths` and stdlib, so there is no cycle and no client/backend boundary crossing.

Amend `submit_decision`'s docstring with the run-id contract: `run_id` is minted ONCE per triage batch by the caller through `run_state.new_run_id()`, before any HTTP call, the same idiom `enrich-records/SKILL.md` already uses for a dispatch run; it is never generated inside this function, because a per-decision id would scatter one sitting across N files and defeat the one-artifact-per-run rule (D-59-09). State that `run_id=None` writes nothing at all, so every existing caller is unaffected.

Add the six tests above to `test_review_decision.py`, monkeypatching `written_records.written_records_path` to a `tmp_path` file exactly as `test_written_records.py` does, so the operator's real durable directory is never touched.
  </action>

  <verify>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_decision.py operator-claude-plugin/tests/test_written_records.py -x</automated>
    <fails_when>non-zero exit, or the summary line reports any failed or errored test</fails_when>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests -q && .venv/bin/python -m pytest -q</automated>
    <fails_when>non-zero exit from either suite, or either summary line reports a failed or errored test</fails_when>
  </verify>

  <acceptance_criteria>
    - Behavior assertion: with `append_chunk` raising `OSError`, `submit_decision`'s return value still carries the endpoint's `outcome` and `would_write`, and `result["written_records"]` is a non-`True` value naming the exception type.
    - Behavior assertion: the same holds with `WrittenRecordsError` — this is the case the wider catch exists for and it must be a separate test, not a parametrisation that could be deleted as a duplicate.
    - Behavior assertion: with `run_id=None`, `written_records.written_records_path` is never called (assert via a monkeypatched spy).
    - Source assertion: `grep -c 'except Exception' operator-claude-plugin/scripts/review_decision.py` is at least 2 — the pre-existing transport catch plus this one — and the new one sits AFTER the `_post_decision` call, not around it.
    - Test command: both suite commands above exit 0.
  </acceptance_criteria>

  <reversibility rating="costly">D-60-08, as above: this is the second writer of the artifact.</reversibility>

  <done>A review decision under a run id lands in that run's own written-records file, the append happens only after the write already happened, and no bookkeeping failure of either shape can stop, abort or hide a review write.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator free text → durable disk | A review reason is the operator's own words; the artifact must never persist an arming-, grant- or secret-shaped value (Phase 23 D-11). |
| bookkeeping → the live write | A durable-state failure must never be able to stop or reverse a HubSpot write already in flight (D-59-10). |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-60-10 | Information Disclosure | the review entry's `reason` field | high | mitigate | The entry's `reason` is fixed at `None` — operator prose never reaches disk through this path; the reason already lives on the HubSpot record. `_looks_forbidden` still sweeps every finished entry, so the Phase 23 D-11 guarantee holds identically. Pinned by a test that feeds a marker-bearing input and asserts no raise and no persisted text. |
| T-60-11 | Denial of Service | `append_chunk` raising into a live decision | high | mitigate | The review call site catches `Exception`, not `OSError`, because `WrittenRecordsError` propagates out of `append_chunk` by design. Two separate tests pin both raise shapes returning the write's outcome intact. |
| T-60-12 | Repudiation | a review write missing from the run's artifact | medium | mitigate | The append is keyed by the batch's own `run_id` and happens immediately after the POST, so a session that dies later still leaves every decision that landed before the crash on disk — the same partial-run guarantee D-59-07 gives dispatch. |
| T-60-13 | Tampering | a review outcome word leaking into downstream readers | medium | mitigate | `REVIEW_OUTCOME_TO_OUTCOME`'s values are asserted to be a subset of `ALL_OUTCOMES`, so `report_enrichment`'s counter and `run_report`'s record builder need no change and cannot meet an unknown word. |
| T-60-SC | Tampering | npm/pip/cargo installs | low | accept | No package is installed by this plan; `60-RESEARCH.md` records the same. |
</threat_model>

<artifacts_this_plan_produces>
- `written_records.REVIEW_OUTCOME_TO_OUTCOME` — the review-to-shared outcome map
- `written_records.classify_review_item(item)` — pure, seven-key, `reason=None` by design
- `written_records.append_chunk(..., classify=classify_item)` — new keyword-only parameter
- `review_decision.submit_decision(..., run_id=None)` — new keyword; envelope gains a `written_records` key
- New tests: the seven mapping/shape cases, and the six wiring cases including both raise shapes

The full phase-level artifact list is in `60-01-PLAN.md` § Artifacts this phase produces.
</artifacts_this_plan_produces>

<verification>
- `.venv/bin/python -m pytest -q` and `.venv/bin/python -m pytest operator-claude-plugin/tests -q` both green.
- `node --test tests/n8n/*.test.mjs` green — this plan touches no JS.
- `git status --porcelain n8n/` empty.
- No test writes to the operator's real durable directory: `test_written_records.py`'s existing pytest guard stays in force and every new test monkeypatches the path.
</verification>

<success_criteria>
One file per run answers "what did this session write to HubSpot" for the review lane as well
as the two dispatch lanes, in the vocabulary every existing reader already speaks — and no
failure of that bookkeeping, of either raise shape, can stop or hide a review write.
</success_criteria>

<output>
Create `.planning/phases/60-review-lane-authority/60-03-SUMMARY.md` when done
</output>


### Plan 4 of 4
---
phase: 60-review-lane-authority
plan: 04
type: execute
wave: 3
depends_on: ["60-01", "60-02", "60-03"]
files_modified:
  - n8n/code/reviewDecision.js
  - n8n/wf_review_decision_cloud.json
  - operator-claude-plugin/skills/review-triage/SKILL.md
  - operator-claude-plugin/skills/enrich-records/SKILL.md
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - operator-claude-plugin/README.md
  - operator-claude-plugin/USAGE.md
  - operator-claude-plugin/CHANGELOG.md
  - operator-claude-plugin/.claude-plugin/plugin.json
autonomous: true
requirements: [D-60-01, D-60-02, D-60-04, D-60-05, D-60-06, D-60-08]
user_setup: []

estimate:
  tokens: 66000
  raw_tokens: 66000
  tasks: 3
  confidence: low

must_haves:
  truths:
    - "D-60-04: no operator-facing surface tells anyone to set a shell environment variable to approve a record — the retired gate is gone from the skill, the README gate table and the USAGE admin table, replaced by the grant the operator can open in conversation."
    - "D-60-02: the two dispatch skills open their grant naming all three lanes, so a grant opened for an enrichment or ingest batch also authorizes review on those same records with no second deliberate yes."
    - "D-60-06: the review-triage skill opens ONE arm window for the sitting and closes it once, rather than arming per record; D-60-01's grant is what authorizes it and D-60-05's dynamic arm is what removes the admin deploy."
    - "D-60-08: the skill mints one `run_id` per triage batch and reports, at the end, the records that run actually wrote — read from that run's own artifact, never the path-less aggregate."
    - "The deployed backend no longer tells an operator that only an administrator can add records to the allowlist at deploy time — a grant now sets it dynamically. The text is corrected at its source and the workflow JSON is REGENERATED, never hand-edited."
  artifacts:
    - operator-claude-plugin/skills/review-triage/SKILL.md
    - n8n/wf_review_decision_cloud.json
    - operator-claude-plugin/CHANGELOG.md
    - operator-claude-plugin/.claude-plugin/plugin.json
  key_links:
    - "`n8n/code/reviewDecision.js` -> `scripts/build_cloud_workflows.py::build_review_decision_cloud` -> `n8n/wf_review_decision_cloud.json` — the ONLY route by which that JSON may change."
    - "`review-triage/SKILL.md` step 6 -> `write_grant.authorize_review_batch` -> `n8n_arming.armed_review_window` -> per-record `write_grant.authorize_send(lane=\"review\")` -> `review_decision.submit_decision(grant=..., run_id=...)`."
    - "`.claude-plugin/plugin.json` version -> the marketplace Update button — an unbumped string means the operator never sees any of this."
---

<objective>
Make the operator-facing surfaces tell the truth this phase created, and release it.

Purpose: plans 01-03 changed what the system CAN do. Until the skill, the two dispatch
skills, the README gate table, the USAGE admin table and the backend's own refusal message
say so — and until the version string moves — an installed operator still reads that only an
admin can approve a flagged record, and still runs the old code.

Output: the corrected backend message (regenerated, never hand-edited), a review-triage skill
that opens one grant-authorized window per sitting, three-lane grants in the dispatch skills,
truthful gate tables, a CHANGELOG section and version `0.35.0`.
</objective>

<execution_context>
@~/.claude/gsd-core/workflows/execute-plan.md
@~/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/60-review-lane-authority/60-CONTEXT.md
@.planning/phases/60-review-lane-authority/60-RESEARCH.md
@.planning/phases/60-review-lane-authority/60-PATTERNS.md
@.planning/phases/60-review-lane-authority/60-01-SUMMARY.md
@.planning/phases/60-review-lane-authority/60-02-SUMMARY.md
@.planning/phases/60-review-lane-authority/60-03-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Correct the backend's now-false refusal message, at its source</name>

  <read_first>
    - n8n/code/reviewDecision.js around lines 218-235 (the `writeAllowed === false` branch and its message, plus the comment above it explaining why `not_allowlisted` is a distinct outcome from `refused`)
    - scripts/build_cloud_workflows.py lines 7700-7740 (the inline list that pulls `reviewDecision.js` into the built node) and 8160-8175 (`splice_write_gates` for the two review write nodes)
    - scripts/build_cloud_workflows.py's `main()` (the tail of the file — it regenerates EVERY workflow JSON, which is why the acceptance criterion below checks that only one changed)
    - operator-claude-plugin/tests/test_review_outcome_parity.py (it pins the outcome literals against this file and the committed JSON as text — it must stay green through a message-text edit)
    - CLAUDE.md § 10.3.1 and § 13.0 (the standing rule: never hand-edit `n8n/wf_*.json`)
  </read_first>

  <files>n8n/code/reviewDecision.js, n8n/wf_review_decision_cloud.json</files>

  <precondition>The repo venv can import the builder — `.venv/bin/python -c "import sys; sys.path.insert(0, 'scripts'); import build_cloud_workflows"` exits 0. The builder has import-time side effects and a sibling-module import (`gen_taxonomy_js`) that system python does not satisfy; halt and report rather than regenerating with the wrong interpreter.</precondition>

  <action>
In `n8n/code/reviewDecision.js`'s `writeAllowed === false` branch, replace the trailing clause of the `not_allowlisted` message — the one asserting that only an administrator can put records on the allowlist, and only while deploying — with wording that is true after this phase: the allowlist is set either by a deploy or, now, dynamically for the duration of one authorized window, and the operator's route is to open a write grant covering this record rather than to find an admin. Keep the first half of the message byte-identical (that this record is not on the backend's allowlist, that nothing was sent to HubSpot, and that the record is unchanged) — it is still exactly true and is what the outcome means. Keep the outcome literal `not_allowlisted` untouched; `test_review_outcome_parity.py` pins it against this file and the committed JSON as text. Add a short dated comment above the message naming Phase 60 and D-60-05, recording that this string was accurate before a grant could arm the allowlist and is being corrected rather than rewritten, so a reader does not have to date it from `git blame`.

Then regenerate the workflow JSON by running the builder — never by editing `n8n/wf_review_decision_cloud.json`. The builder rewrites every workflow file, so inspect the resulting `git status` before staging: only the review workflow may differ. Any other workflow showing a diff is pre-existing generator drift, not this phase's work — STOP and report it in the summary rather than committing it alongside a message-text change.
  </action>

  <verify>
    <automated>.venv/bin/python scripts/build_cloud_workflows.py</automated>
    <fails_when>non-zero exit, or the run prints a traceback instead of one `wrote n8n/...` line per workflow</fails_when>
    <automated>git status --porcelain n8n/ | awk '{print $2}'</automated>
    <fails_when>the output is anything other than exactly the two lines `n8n/code/reviewDecision.js` and `n8n/wf_review_decision_cloud.json`</fails_when>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_review_outcome_parity.py -x</automated>
    <fails_when>non-zero exit, or the summary line reports any failed or errored test</fails_when>
    <automated>node --test tests/n8n/*.test.mjs</automated>
    <fails_when>non-zero exit, or the summary reports `fail 1` or higher</fails_when>
  </verify>

  <acceptance_criteria>
    - Source assertion: `grep -c 'that allowlist at deploy time' n8n/code/reviewDecision.js` prints `0`, and the same grep over `n8n/wf_review_decision_cloud.json` prints `0` — the regeneration actually carried the edit through.
    - Source assertion: `grep -c '"not_allowlisted"' n8n/code/reviewDecision.js` is unchanged from before the edit.
    - CLI output: `git status --porcelain n8n/` lists exactly the two files named above.
    - Source assertion: `git diff --stat -- tests/n8n/reviewWriteFlagSeparation.test.mjs | wc -l` prints `0`.
    - Test command: the parity test and the full n8n glob suite both exit 0.
  </acceptance_criteria>

  <reversibility rating="reversible">A message-text edit plus a regeneration; reverting is the same two steps.</reversibility>

  <done>The deployed review workflow no longer tells an operator that only an admin can open the allowlist, the correction went through the generator, and exactly one workflow JSON changed.</done>
</task>

<task type="auto">
  <name>Task 2: Rewrite the review-triage skill onto the grant, and open three-lane grants</name>

  <read_first>
    - operator-claude-plugin/skills/review-triage/SKILL.md (whole file — 188 lines; step 1's arming statement, step 6's env-var paragraph and its `submit_decision` call, step 7's verdict reporting, and the closing "What this skill never asks the operator to do")
    - operator-claude-plugin/skills/enrich-records/SKILL.md lines 320-425 (step 8's authorize -> arm -> act -> disarm block — the canonical shape to mirror; note it is EXECUTABLE Python that `test_write_grant.py` `compile()`s, so any edit must stay compilable) and its step 10 end-of-run report call
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md lines 55-95 (the two-lane grant paragraph and the `lanes=[...]` sentence)
    - operator-claude-plugin/tests/test_skill_sequence_coverage.py lines 300-310 (the two symbols review-triage's SKILL.md must keep mentioning)
    - operator-claude-plugin/scripts/write_grant.py and review_decision.py as plans 01-03 left them (the real signatures the skill must call)
  </read_first>

  <files>operator-claude-plugin/skills/review-triage/SKILL.md, operator-claude-plugin/skills/enrich-records/SKILL.md, operator-claude-plugin/skills/enrich-before-ingest/SKILL.md</files>

  <action>
Rewrite `review-triage/SKILL.md` around the grant. Step 1's opening statement changes from "review writeback is disarmed" to the accurate two-part position: nothing reaches HubSpot until the operator says yes to a specific record's exact write, AND a write grant covering that record must be open — which the operator can open in this conversation once an n8n admin has set `allow_write_grants`, with no shell and no deploy. Add a new step between the current 3 and 4, or fold into step 3, that opens the sitting: mint `run_id = run_state.new_run_id()` before any HTTP call; if a grant is already open from an enrichment or ingest batch and covers the records to be triaged, reuse it; otherwise plan and open one over the ids the operator is about to work, naming `lanes=["review"]` and passing `providers=[]` — a review batch spends no provider credit, and passing the configured selection would price the envelope against credits this sitting will not touch. Then open ONE `n8n_arming.armed_review_window` over `write_grant.authorize_review_batch(grant)`'s returned record lists and hold it for the whole sitting (D-60-06), closing it once at the end and on any exception, through the context manager's own guarantee. Say plainly, in the skill's own voice, that the window is grant-wide but every decision inside it is still checked per record, so a record the grant does not name is refused even mid-sitting.

Rewrite step 6. The per-record ritual is UNCHANGED and must be said to be unchanged: read the exact write back, get an explicit yes for this record, and that yes is `review_armed=True` for that one submit and nothing else — VOCAB-05 still holds, an operator saying yes must never have to produce the system's wording. What changes is only the authority underneath it: `submit_decision` now takes `grant=` and `run_id=`, and refuses with reason `grant_not_authorized` when no open grant covers this record. Delete the paragraph telling the operator that an administrator must set an environment variable and that this skill cannot set it — that refusal no longer exists; put in its place the grant refusal's handling, which is genuinely actionable: relay the message, and offer to open a grant covering this record rather than sending them to an admin. Keep the sentence that a yes here does not arm the contact-upload or enrichment lanes and vice versa — the per-record consent is still lane-specific even though one grant now spans three lanes; the grant is the authority, the yes is still the act.

Step 7 gains the end-of-run account: after the sitting, read this run's own artifact through `written_records.load(path=written_records.written_records_path(run_id))` — never the path-less aggregate, which would fold in previous runs — and tell the operator which records this sitting wrote. Say that a decision whose bookkeeping failed still landed and is reported as such from the `written_records` key on the submit envelope, because the write always wins over the log (D-59-10). Rewrite the closing "What this skill never asks the operator to do" section: the environment variable is gone from the list; what remains is a missing config key and the admin's `allow_write_grants` settings key. Keep every mention of `review_queue.policy_class` and `review_queue.record_link` — a skill-coverage test asserts both by name.

In `enrich-records/SKILL.md` and `enrich-before-ingest/SKILL.md`, add `"review"` to the lanes each opens its grant with, citing D-60-02 in one sentence each: one grant covers all three lanes together, so a record enriched or ingested under this grant can also be triaged in the same sitting without a second deliberate yes — bounded, as always, to the grant's own records. In `enrich-records/SKILL.md` the edit lands inside the executable Python block, which an AST test compiles: keep it compilable and keep every existing name binding. In `enrich-before-ingest/SKILL.md`, update the surrounding prose that says the grant spans "both of this flow's lanes" so the count is right.
  </action>

  <verify>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests/test_skill_sequence_coverage.py operator-claude-plugin/tests/test_enrich_skill_contract.py operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py -x</automated>
    <fails_when>non-zero exit, or the summary line reports any failed or errored test</fails_when>
    <automated>.venv/bin/python -m pytest operator-claude-plugin/tests -q</automated>
    <fails_when>non-zero exit, or the summary line reports any failed or errored test</fails_when>
    <automated>grep -c 'ALLOW_REVIEW_SUBMIT' operator-claude-plugin/skills/review-triage/SKILL.md</automated>
    <fails_when>prints anything other than `0`</fails_when>
  </verify>

  <acceptance_criteria>
    - Source assertion: `grep -c 'authorize_review_batch' operator-claude-plugin/skills/review-triage/SKILL.md` is at least 1, and `grep -c 'new_run_id' operator-claude-plugin/skills/review-triage/SKILL.md` is at least 1.
    - Source assertion: `grep -c 'review_queue.policy_class' operator-claude-plugin/skills/review-triage/SKILL.md` and `grep -c 'review_queue.record_link'` are both at least 1 — the skill-coverage test's two pinned symbols survive.
    - Source assertion: `grep -c '"review"' operator-claude-plugin/skills/enrich-records/SKILL.md` is at least 1 and `grep -c 'D-60-02' operator-claude-plugin/skills/enrich-records/SKILL.md` is at least 1; the same two hold for `enrich-before-ingest/SKILL.md`.
    - Behavior assertion: the Python block in `enrich-records/SKILL.md` still compiles — the existing AST test in `test_write_grant.py` passes unmodified.
    - Behavior assertion: the review skill still states that a yes covers this record's write and nothing else, and still states that the exact-write preview works without any authority.
    - Test command: the plugin suite exits 0.
  </acceptance_criteria>

  <reversibility rating="costly">D-60-02: reversing the combined-lane grant means re-adding a lane-selection step to the grant-opening flow these edits remove. D-60-06's one-window-per-sitting is likewise costly to unpick. The review-triage rewrite itself is reversible.</reversibility>

  <done>The review-triage skill opens one grant-authorized window per sitting, mints one run id, reports what that run wrote, and asks nobody to set an environment variable; the two dispatch skills open three-lane grants citing D-60-02.</done>
</task>

<task type="auto">
  <name>Task 3: Truthful gate tables, CHANGELOG, and the version bump that ships it</name>

  <read_first>
    - operator-claude-plugin/README.md lines 585-615 (the three-gate table for a review decision and the two paragraphs below it)
    - operator-claude-plugin/USAGE.md lines 198-212 (the "why it's the admin" table, including the review-approval row)
    - operator-claude-plugin/CHANGELOG.md lines 1-20 (the Unreleased heading and the release rule stated at the top) and its final section (the four-step release checklist)
    - operator-claude-plugin/.claude-plugin/plugin.json (current version `0.34.0`)
    - .planning/phases/60-review-lane-authority/60-01-SUMMARY.md, 60-02-SUMMARY.md, 60-03-SUMMARY.md (what actually shipped, for the CHANGELOG entry — write the entry from these, never from this plan's intentions)
  </read_first>

  <files>operator-claude-plugin/README.md, operator-claude-plugin/USAGE.md, operator-claude-plugin/CHANGELOG.md, operator-claude-plugin/.claude-plugin/plugin.json</files>

  <action>
In `README.md`, rewrite the review-decision gate table. It is still three gates and they are still all required, so keep the table's shape and its "any one closed and nothing is written" framing. Row one becomes the write grant covering this record — where it lives is the conversation, who opens it is the operator, once an n8n admin has set `allow_write_grants` in `operator.local.json`. Row two, the per-record arm, is unchanged. Row three, the backend constant and its record allowlist, keeps its process/machine distinction but its "who opens it" becomes the grant's own arm window as well as a deploy. Rewrite the paragraph beneath it: the trap it warned about — two similarly-named variables in different processes — is retired along with the variable, so replace it with the distinction that actually matters now, which is that the client-side authority and the backend constant are still two separate things and the grant is what closes both in one step. Keep the closing statement that the skill will never ask the operator to set any of these and will name which gate is closed and who can open it — it is still true and it is the load-bearing promise. Keep the sentence that the review arm and the contact-dispatch arm are separate in both directions; that separation survives this phase at the flag level and is worth a reader knowing.

In `USAGE.md`, rewrite the review-approval row of the admin table. It is no longer an admin's job at all in the common case: the operator opens a grant in conversation. What remains the admin's is the one-time `allow_write_grants` settings key — fold the row into that, or point it at the existing arming row, whichever leaves one true statement rather than two overlapping ones.

Then release. Cut a `## [0.35.0] - <today's date>` section in `CHANGELOG.md` beneath an emptied Unreleased heading, describing what actually shipped from the three summaries: the review lane became grantable; the shell environment variable that gated review submission is retired and grant authorization took its place; a rejection still works with no grant open; arming review is dynamic and never touches the dispatch write flags; one window covers a whole triage sitting; the dirty-backend guardrail can now see a stuck-open review authorization; review writes appear in the per-run written-records artifact. Note the reversal explicitly — 30-01's D-02/D-08e separation between dispatch grants and review writeback is deliberately undone, with the record kept in `write_grant.py`'s own dated addendum — because a CHANGELOG that presents a reversal as a feature is how a later reader loses the reason the old design existed. In the same commit, set `.claude-plugin/plugin.json`'s version to `0.35.0`: the release checklist at the bottom of the CHANGELOG says the bump and the section cut are one commit, and an unbumped string leaves the Update button greyed out however much shipped. Do not push and do not touch the marketplace clone — steps 3 and 4 of that checklist are the operator's, not this plan's.
  </action>

  <verify>
    <automated>.venv/bin/python -c "import json; v=json.load(open('operator-claude-plugin/.claude-plugin/plugin.json'))['version']; assert v=='0.35.0', v; print('version', v)"</automated>
    <fails_when>non-zero exit, or the printed version is anything other than `0.35.0`</fails_when>
    <automated>grep -c '^## \[0.35.0\]' operator-claude-plugin/CHANGELOG.md</automated>
    <fails_when>prints anything other than `1`</fails_when>
    <automated>grep -c 'ALLOW_REVIEW_SUBMIT' operator-claude-plugin/README.md operator-claude-plugin/USAGE.md</automated>
    <fails_when>either file's count is anything other than `0`</fails_when>
    <automated>.venv/bin/python -m pytest -q && .venv/bin/python -m pytest operator-claude-plugin/tests -q && node --test tests/n8n/*.test.mjs</automated>
    <fails_when>non-zero exit from any of the three, or any summary line reports a failed, errored or `fail 1`-or-higher result</fails_when>
  </verify>

  <acceptance_criteria>
    - Source assertion: the version is exactly `0.35.0` and the CHANGELOG's `## [0.35.0]` section and that bump are in ONE commit (`git show --stat HEAD` lists both files).
    - Source assertion: the Unreleased heading is still present and its body is empty.
    - Source assertion: the retired variable name appears nowhere in `README.md` or `USAGE.md`; the only surviving mentions repo-wide are the historical CHANGELOG entry at line ~1605 and the dated recorded-edit notes in `write_grant.py`, `review_decision.py` and `test_review_decision.py`.
    - Behavior assertion: the README gate table still lists three gates and still says any one closed means nothing is written.
    - Test command: all three suites exit 0.
  </acceptance_criteria>

  <reversibility rating="reversible">Documentation and a version string; a revert is a symmetric edit.</reversibility>

  <done>Every operator-facing surface describes the authority that now exists, the CHANGELOG records the reversal as a reversal, and the version string moved so an installed operator can actually receive it.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| documentation → operator behaviour | A gate table that overstates what is required trains an operator to look for an admin who is no longer needed; one that understates it trains them to expect a write that will not happen. |
| generator → deployed workflow JSON | The JSON is a build artifact; a hand-edit silently diverges from its source and survives until the next regeneration erases it. |
| repo → installed plugin copy | An unbumped version string means none of this phase reaches the operator at all. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-60-14 | Repudiation | a hand-edited `wf_review_decision_cloud.json` | high | mitigate | The message is changed in `n8n/code/reviewDecision.js` and the JSON is REGENERATED via `scripts/build_cloud_workflows.py`; the acceptance criterion greps the built JSON to prove the edit travelled, and `git status --porcelain n8n/` proves exactly two files changed. |
| T-60-15 | Spoofing | a gate table implying an authority that no longer exists | medium | mitigate | The README and USAGE rows are rewritten to name the grant and the admin's one remaining settings key; a negative grep proves the retired variable name is gone from both. |
| T-60-16 | Elevation of Privilege | three-lane grants in the dispatch skills | high | mitigate | D-60-02 is the operator's own decision and D-60-03 bounds it: the grant's record set is unchanged, so the collapse widens WHEN the approval is given and never WHAT it covers. `_consequence()` (plan 01) names every lane individually at the yes, so the operator reads all three before consenting. |
| T-60-17 | Repudiation | shipping code an operator never receives | medium | mitigate | The version bump and CHANGELOG cut are asserted to be one commit, per the release checklist this repo already keeps. Steps 3 and 4 (push, refresh the marketplace clone) stay the operator's, and are named as such rather than silently assumed. |
| T-60-SC | Tampering | npm/pip/cargo installs | low | accept | No package is installed by this plan; `60-RESEARCH.md` records the same. |
</threat_model>

<artifacts_this_plan_produces>
- `n8n/code/reviewDecision.js` — corrected `not_allowlisted` message text with a dated note
- `n8n/wf_review_decision_cloud.json` — regenerated (message text only; no node, no gate, no topology change)
- `operator-claude-plugin/skills/review-triage/SKILL.md` — grant-opened sitting, one batch window, one `run_id`, end-of-run written-records account, no environment variable
- `operator-claude-plugin/skills/enrich-records/SKILL.md`, `skills/enrich-before-ingest/SKILL.md` — three-lane grants citing D-60-02
- `operator-claude-plugin/README.md`, `USAGE.md` — truthful gate tables
- `operator-claude-plugin/CHANGELOG.md` — a `## [0.35.0]` section recording the reversal as a reversal
- `operator-claude-plugin/.claude-plugin/plugin.json` — version `0.35.0`

The full phase-level artifact list is in `60-01-PLAN.md` § Artifacts this phase produces.
</artifacts_this_plan_produces>

<verification>
- All three suites green: `.venv/bin/python -m pytest -q`, `.venv/bin/python -m pytest operator-claude-plugin/tests -q`, `node --test tests/n8n/*.test.mjs`.
- `git status --porcelain n8n/` names exactly `n8n/code/reviewDecision.js` and `n8n/wf_review_decision_cloud.json`.
- `tests/n8n/reviewWriteFlagSeparation.test.mjs` passes unmodified.
- Version is `0.35.0` and the CHANGELOG section is cut in the same commit.
- Nothing is armed, nothing is deployed to n8n, no HubSpot request and no provider call is made. This phase's own live proof belongs to the supervised operator walk in `60-VALIDATION.md` § Manual-Only Verifications, not to an executor task.
</verification>

<success_criteria>
An operator reading any surface of this plugin learns that approving a flagged record needs a
grant they can open in conversation and a yes to that record's exact write — and nothing they
have to ask an administrator for — and an installed copy can actually receive that change.
</success_criteria>

<output>
Create `.planning/phases/60-review-lane-authority/60-04-SUMMARY.md` when done
</output>


## Review Instructions

**Verify against source — do not review the plan text in isolation.** The plans reference real files, functions, and tests in this repo. You have repo access; use it.
1. Open the referenced files and check each claim against the actual code.
2. For every strength or concern, cite concrete `path/to/file:line` evidence plus the mechanism.
3. When a plan asserts a mechanism works (a guard, a flag separation, a test that exercises a path), trace whether it actually does what is claimed — do not take the plan's word for it.
4. If you cannot read the repo, say so explicitly and downgrade that finding to an open question rather than asserting it.

Findings citing `file:line` evidence are weighted far more heavily than impressionistic ones; a review that only restates the plan's own claims has low value.

Analyze each plan and provide:

1. **Summary** — One-paragraph assessment
2. **Strengths** — What's well-designed (bullet points)
3. **Concerns** — Potential issues, gaps, risks (bullets, each tagged HIGH/MEDIUM/LOW)
4. **Suggestions** — Specific improvements
5. **Risk Assessment** — Overall risk level (LOW/MEDIUM/HIGH) with justification

Focus on:
- Missing edge cases or error handling
- Dependency ordering issues (this phase has 3 waves; wave 2 runs 60-02 and 60-03 in parallel)
- Scope creep or over-engineering
- **Security considerations — this phase WIDENS a write authority.** The review lane was deliberately excluded from write grants by an earlier phase (30-01 D-02/D-08e); this phase reverses that on purpose. Scrutinize whether the reversal is bounded as claimed.
- Whether the plans actually achieve the phase goal

**Specific claims worth independent scrutiny — each is load-bearing and each could be wrong:**
- `disarm` is changed to clear every overlayable constant the *fetched workflow actually declares*, rather than a fixed tuple. Does this weaken any existing disarm guarantee? Does it behave correctly when the workflow read fails?
- The plans claim widening `write_grant.py`'s local `WRITE_ENABLING_FLAGS` breaks `test_write_grant_guardrails.py`'s `_gate()` fixture, and fix both in one task. Verify the coupling is real and that one task genuinely covers it.
- A claimed trap: calling `preflight_before_send` on the review lane *inside* an open review batch window would read the window's own arm as "writes still live" and disarm mid-batch. Is the prohibition sufficient, or does something still reach that path?
- `classify_review_item` deliberately sets `reason=None` because `_looks_forbidden` is a substring check on `arm`/`grant`/`permission` and operator free text could raise on a bookkeeping write that must never raise. Is dropping the reason the right trade, and is the forbidden-name scan actually the constraint claimed?
- D-60-07: a `reject` works with NO grant open, so a closed authority cannot strand a flagged record. Does any plan path let that carve-out authorize more than a reject?
