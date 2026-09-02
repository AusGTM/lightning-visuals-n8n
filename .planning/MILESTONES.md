# Milestones

## v1.1 Unattended Session Runs (Defined 2026-08-25 — IN FLIGHT, not shipped)

**Requirements:** `.planning/milestones/v1.1-REQUIREMENTS.md`. **Roadmap:** `.planning/milestones/v1.1-ROADMAP.md` — ~~5 phases, 53–57~~ **phases 53–61** (52 stays v1.0's). **UAT evidence:** `.planning/quick/260825-contact-company-association/UAT.md` (G-1..G-4).

**Progress (2026-09-02):** complete — 53 (GRANT-01 ticked on walk run 3, 2026-08-29), 54, 57, 58,
59, **61**. Absorbed into 61 by operator decision D-61-08 — 55 (async run) and 56 (unattended pair
pipeline). Open — **60** (review-lane authority). **Phase 62** ("Suggest the contacts nobody
named") has executed: 6 plans, verification `human_needed` at 13/13 must-haves, UAT partial (3
items blocked on a live attended sitting). **Phase 63** ("The unattended lane actually runs
unattended") was numbered 2026-09-02 and is not yet planned. Requirements closed to date:
INPUT-01, INPUT-03, INPUT-04, INPUT-05, GRANT-01, GRANT-03, GRANT-05, RUN-01, RUN-02, RUN-03,
RUN-04, RUN-05, AFTER-02, AFTER-03, VOCAB-05, SUGGEST-01, SUGGEST-02, SUGGEST-04, SUGGEST-05
(SUGGEST-03 amended, not closed, per D-62-07).

**Phase 61 (2026-08-30)** landed `linkedin_url` as a third identity group across both lanes, a
confidence decision table plus a durable held-rows queue with per-hold-code resume fingerprints,
a run manifest and run state, async submit/progress off the ~100s synchronous window, one grant
across ingest/enrich/create/associate, and substrate-3 scale-up fan-out behind an off-by-default
flag. All five cloud workflows were deployed, bounced and exercised by **disarmed** runs only
(executions `12040`, `12044`–`12047`). Suites at close: root python 3539 passed / 154 skipped;
node 844 pass / 0 fail.

**Phase 57 ("Ceilings, refusal-before-start, and post-run proof") completed 2026-09-01,** landing
per-run ceilings, allowance sampling and refusal-before-start, and the end-of-run report joining
all five durable stores. **The first live unattended, credit-spending batch has still NOT run** —
naming Phase 57 as the pending gate is now stale (57 shipped); what remains before that first run
is tracked against Phase 60 and Phase 63.

**Decisions taken 2026-08-25:** the grant is operator-openable in Claude (the `ALLOW_N8N_ARM` env var stops being the interactive authority); grant first, then a single async pass; first slice is the full pair pipeline with creates included.

**Source:** a UAT walkthrough with the end client, 2026-08-25. Their verdict: the flow is
"incredibly halting" — every send needs its own preview, arming phrase and confirmation, which
is unfeasible at scale. They want one grant at the start of a session and an unattended run
through to HubSpot write.

**The distinction the milestone turns on:** this is two requests, not one. Fewer decisions is a
consent problem; finishing a batch of hundreds is a throughput problem, and auto-approval does
not touch it — the per-request ceiling is a measured 2 records against n8n Cloud's ~100 s
response window, and every record costs executions against a 2,500/month plan. Building only
the consent half produces a system that asks once and then takes hours anyway.

**What may not regress:** record-scoped write allowlists (the backend must stay incapable of
writing a record outside the run), guaranteed disarm with `disarm_failed` reported loudly, cost
ceilings that bind before spend, per-record audit stamps, and the held-row contract — a contact
whose company cannot be resolved is held, never landed to keep a batch moving.


## v0.8 Execution Budget Safety (Shipped: 2026-08-11)

**Phases completed:** 2 phases (44–45), 6 plans, 9 tasks

**Closeout:** verified_closeout — both phases `phase_complete: true` / `verification_status: passed`
(Phase 44's `44-VERIFICATION.md` was written retroactively at close, 5/5 must-haves, after the
phase was found sealed at plan level only). Requirements 15/15. Closing gates: pytest 2498
passed / 121 skipped, node 658 passed. Known deferred items: 3 (see STATE.md Deferred Items).

**The problem this milestone solved:** SJ-3 could spend the entire monthly execution budget on
work it was structurally unable to complete — 61 stuck `lv_enrichment_requested` flags re-dispatched
every 15 minutes, once burning ~182k executions/month against a 2,500/month plan.

**Key accomplishments:**

- **The gate.** SJ-3's poller now filters dispatch through the shared write-safety predicate per
  record. A gate-closed tick dispatches zero sub-executions and costs exactly 1 execution — never
  1 + N — and reports a distinct, named, non-error outcome, because disarmed is the normal resting
  state rather than a failure.

- **The drain.** On a gate-closed tick SJ-3 clears `lv_enrichment_requested` on every record it
  declined, through a write path narrow enough to touch only that one flag. The queue drains to
  zero over subsequent ticks instead of re-accumulating, and a drained record stays distinguishable
  from an enriched one — nothing downstream may read the cleared flag as evidence of processing.

- **The cap.** A single tick dispatches at most a build-time-derived cap (40 at the shipped daily
  cadence), computed inside `build_cloud_workflows.py` from `config/execution_budget.yaml` and the
  same schedule tuple that bakes the real trigger — never a hardcoded constant, so the bound cannot
  silently drift when a trigger is re-timed. A capped tick always logs found-vs-dispatched; silent
  truncation is forbidden. A drift test fails if the shipped schedule's monthly execution floor
  exceeds a configured share of the plan allowance — the check the v0.7 schedule (2.6x over budget
  while doing no work) would have failed.

- **Proven live, not just tested.** Execution 11820: gate-closed tick, verbatim `gate_closed`
  outcome carrying cap 40, drain read-back `requested=false` / `status=skipped` on a disposable
  record (deleted afterward, 0 leaked). Recorded honestly in `44-LIVE-EVIDENCE.md`: the observed
  tick was operator-fired `mode=manual`, because n8n exposes no run-now API for schedule triggers
  (405) and the natural daily tick was ~21h out — the schedule's own firing is proven separately
  by prior tick history.

- **The alarm.** A sweep condition that samples the n8n execution rate over an honestly-observed
  window and fires before the monthly allowance is exhausted, backed by a time-windowed executions
  read that also closed the sweep's own fixed-page re-notify defect (RB-8). Plus a cadence budget
  floor with single-shot overrides: a re-timing that would breach the configured share of the plan
  allowance is refused at the control surface.

- **The alarm's own false-positive, caught before it shipped.** Post-execution code review found
  1 Critical + 5 Warnings, all six fixed and re-verified. CR-01: the alarm fired on a single
  extrapolated sample when retained history held nothing older than the 24h window, and its notice
  blamed n8n pruning that never happened. An unanchored sub-hour sample now stays silent while a
  page-cap-truncated read — a real fast runaway — still fires.

**Shipped inert:** the burn-rate alarm, cadence budget floor and time-windowed lookback all ship
with no cron or launchd installed. That is an admin action and an accepted limit, not a gap.

---

## v0.7 HubSpot Scoring Engine Remediation (Shipped: 2026-08-08)

**Phases completed:** 5 phases (39–43), 23 plans

**Key accomplishments:**

- The ICP rubric was implemented twice — correctly in `src/icp_scoring.py` (oracle only, zero
  production callers) and incorrectly as four live HubSpot workflows nobody knew existed until
  the `automation` scope was granted. All ten validated defects (F1–F10) are fixed **in place**
  on the HubSpot-resident path (Phase 39 decision: the lead-scoring tool cannot write
  `lv_icp_fit_score`, so it was rejected despite being available).

- Engine correct end to end: `lv_produces_content` contributes +20, scoring reads the canonical
  `lv_*` inputs the pipeline actually writes (not native `country`/`annualrevenue`), revenue
  decay lands in the rubric-correct band at every boundary, the gambling deduction is
  independent of org type and never sets the veto flag, sub-15 without a veto no longer grades
  D, all three hard vetoes write flag + reason, vetoes clear on correction, and a flag change
  alone moves the tier.

- **Parity harness instead of eyeballing the UI** (`scripts/run_scoring_parity.py`): recomputes
  via the oracle and asserts against live HubSpot, with a false-green guard that fails when zero
  assertions execute. Every F-defect had been invisible in the HubSpot UI.

- 66 web-researched companies landed as a real scoreable population with provenance at **zero
  provider spend**, and scored automatically on the actual write path (A:7 B:18 C:17 D:24).

- Schema reconciled: `config/hubspot_properties.yaml` is a full 32-property live mirror at zero
  drift, with a standing checker (`scripts/check_schema_drift.py`) and a machine-checked
  do-not-archive invariant. Live derivation found zero orphans — Phase 40 left no debris.

- Pipeline hygiene: boolean write sites coerced to strings at two shared choke points, the
  dormant veto site hardened, `lv_icp_score_breakdown` given a producer, and the closed-lost
  reason signal consumed.

- **Post-milestone, same day:** Phase 41 exposed that `lv_icp_fit_score`'s formula blanked
  entirely on any null term, so 63 of 66 records had no score while the sweep still said PASS.
  Spiked the grammar (the API's 400 body enumerates it), applied a null-safe formula live, and
  added a detector for the blank-score condition the harness structurally could not see.

**Closeout:** REQUIREMENTS 16/16; ROADMAP 5/5 phases Complete; suites 2427 pytest / 636 node;
arming grep 0; all n8n write gates disarmed at rest; live parity PASS with 0 real findings;
schema drift exit 0. No milestone git tag (semver-release-tag namespace precedent from
v0.3/v0.4/v0.6).

---

## v0.6 Claude Plugin Entrypoint (Shipped: 2026-08-04)

**Phases completed:** 10 phases (23–32), workstream `plugin-entrypoint`

**Key accomplishments:**

- Shipped `operator-claude-plugin/`: a conversational front door over the n8n backend — tabular + non-tabular ingestion (prose, foreign JSON, URLs, screenshots), enrichment lane with cost guard, per-record outcome reporting with safe retry, backend status surface, allowlisted control actions, notices + unattended sweep, and review-queue triage. 49/49 requirements complete.
- Every dangerous capability behind a uniform `ALLOW_*` gate (exact-string `true`, D-34), session arms separate from env gates, single-record `TEST_RECORD_*` allowlists, and symmetric `--expect-armed` read-backs. Committed workflow artifacts always disarmed; every arm/disarm bounces active workflows (stored-vs-running gap, proven live).
- Phase 31 (inserted): HubSpot enum validate-and-refuse across staging AND both review paths — preview and submit return identical explicit refusals; `not_allowlisted` distinct from workflow error (BUGS 28/29/30 closed on live evidence).
- Phase 32 (inserted): LLM-free unattended sweep trigger — deterministic sh wrapper under real cron, zero credentials, loud on its own failure; NOTICE-03 sealed by RB-8 re-run (`claude -p` under cron fails silently — never reintroduce).
- Armed canaries RB-3/7/8/9 all passed with single-record blast radius. RB-9 close (2026-08-04) demonstrated REVIEW-04 live: a human approve stamped `source: human` / `human_approved` / timestamp / reason with the superseded machine source readable, and the D-31 probe recorded the decision endpoint withholding a `manual_protected` field (backstop path explicitly not proven).

**Closeout:** REQUIREMENTS 49/49 complete; STATE 10/10 phases; closing gates 1784 pytest / 550 node / armed-literal grep 0 / live tenant disarmed PASS. Carried opens (tracked in HANDOFF/todos): sweep lookback time-window + workflow-name notices, Phase 26 thin-response reason, versioned-cache config orphan, RB-3 canary contact cleanup. No milestone git tag (semver-release-tag namespace precedent from v0.3/v0.4).

---

## v0.4 Reachability & Verification Debt (Shipped: 2026-07-29)

**Phases completed:** 3 phases, 6 plans, 17 tasks

**Key accomplishments:**

- BUG 23 fixed: enrichment `contact:create` made structurally reachable — contacts-lane `HubSpot Search`/`HubSpot Fetch By Id` swapped to the credential-bound httpRequest envelope, byte-identical pins retired with rationale, dual live canary proved match-path regression AND create-path reachability (write-gated), deployment restored disarmed.
- Added `_industryText` to `normalizeProviders.js` so ZoomInfo's and Lusha's company mappers emit the NAICS entry's human-readable name (or nothing) instead of a bare numeric code, closing the gap where a code could win the industry waterfall purely on source trust.
- Wired `lv_sponsorship_reliant` (companies research fold) and `lv_persona_group` (contacts winners loop) into their merge calls via one array entry and one dot-access if-block, closing both Phase-15-carried-forward copy-loop gaps at the wiring level; both fields still have no producer.
- Both Phase-18 verification gaps closed end-to-end: the research prompt now actually asks for `lv_sponsorship_reliant` and a new provider-mapper producer actually emits `lv_persona_group` — both proven live-reachable through compiled node bodies fed by recorded fixtures, not hand-constructed test rows.
- Reconstructed and re-executed all six v0.3 `/gsd-verify-work` re-runs against current code — surfacing BUG 26 (live n8n Cloud deployment had drifted behind git) along the way. Same-day operator runbook closed everything: Step-0 redeploy (BUG 26 resolved), armed `company:update` canary (execution 108, write proven on the allowlisted record only, disarm read back). Final ledger: **6/6 passed, zero residual operator debt**.

**Closeout:** verified — all 3 phases `verification_status: passed`; pre-close artifact audit all-clear; v4 requirements 8/8 complete. No `v0.4-MILESTONE-AUDIT.md` was run (accepted: the phase-level verifier chain + 6/6 ledger covered the same ground). No git tag created — repo tag namespace uses semver release tags (`v0.4.0`/`v0.5.0`); a `v0.4` milestone tag would collide confusingly (same precedent as the untagged v0.3 close). Legacy v1/v2 requirement sections in the archived REQUIREMENTS.md carry historical unchecked rows from already-archived milestones, not v0.4 gaps.

---
