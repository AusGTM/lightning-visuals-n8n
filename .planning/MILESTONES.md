# Milestones

## v1.1 Unattended Session Runs (Shipped: 2026-09-04)

**Phases completed:** 10 phases, 62 plans, 162 tasks

**Key accomplishments:**

- One-record ZoomInfo-to-HubSpot backfill dry run, live-proven end to end with zero writes and a measured (not inferred) per-match credit cost
- D-02 gap-fill research lane, D-04 skip contract, D-03 sizing gate, and a live 10-record capped-sample dry run -- 8 pre-registered predictions plus 2 reasoned skips, zero HubSpot writes, zero n8n executions
- PLAN COMPLETE -- operator approved 2026-08-19 after five checkpoint rounds. Read-only before-snapshot of all 66 already-scored companies committed, COVERAGE.md/51-VALIDATION.md reconciled with zero divergence, a live HubSpot/ZoomInfo country-conflict guard shipped and proven, a field-policy promotion gate and a majority-of-3 research vote shipped to address research-answer instability, a Sonnet judge escalation wired in for genuine lv_produces_content conflicts (CLAUDE.md SS15.1), the dry-run predictions regenerated under that judge lane (Run 3: Gold Coast and Warwick -- the two apparent Tier B rows from Run 2 -- both settle at Tier C; Tasmanian also flipped fresh), and (Run 4) the 3 unresolved-conflict rows flagged `lv_icp_needs_review=true` with a specific reason, at zero additional API spend. No Tier A or Tier B has been produced anywhere in this population across three independent research runs. n8n's matching country blind spot is recorded as tracked debt (WINDOWS.md id 19), not fixed, per explicit operator ruling. Final totals: 13 ZoomInfo credits, 103 Anthropic calls, zero HubSpot writes, zero n8n executions.
- An admin sets one key in `operator.local.json`, the operator opens a grant in conversation, and a dispatch arms live HubSpot writes with no shell environment variable anywhere — bounded to the named batch by a scope check inside `arm_for_dispatch` itself.
- The grant now shows its arithmetic before the yes, ends in named ways that can be reported, refuses the next send after a revoke, and — the two defences 53-CONTEXT asked the planner to surface rather than assume — refuses to open over a backend that is already armed and closes itself when it can no longer confirm the backend is disarmed.
- An admin sets one key and sees from inside Claude that they have set it; an operator revokes a grant by name; the plugin's own description of what it can do names the grant path; and one function turns an open grant into a dispatch's `armed` argument without ever widening the window past the send's own records.
- Read the real execution cost of one record out of live n8n history (1 execution for a single-record post-fix send, vs. 3 for the pre-F2 double/triple-blocked pass), found that `envelope()`'s own execution-count formula DIFFERS from that measurement, relabelled the Anthropic dollar figure from a false MEASURED to PROJECTED, and put the SJ-3 scheduled-poller's still-open double pass on the ledger.
- Two shapes that still cost a second full pass — an identity hold and a look-only rehearsal — now say so where the operator reads them, and the milestone's own G-3 text no longer describes a defect that shipped a day earlier.
- One real flagged HubSpot contact was approved through the deployed review-decision endpoint under an operator-authorized, record-scoped armed window — the clear-and-stamp branch only — and the window was disarmed and independently reverified closed immediately after.
- The execution allowance is now a binding preflight refusal and a pre-send mid-run stop — D-57-00 overturns D-53-02's "ceiling discloses, never constrains" ruling, and all four production dispatch paths carry it in one spend vocabulary.
- A disarmed, test-proved live probe observed ZoomInfo's balance as readable (9381 credits, zero measured spend), closing G-4's ZoomInfo half by observation with no code fix, and three unreadable-balance causes are now regression-pinned as distinct in the cost/write tri-state.
- One end-of-run report joins all five durable stores plus a new per-run audit record and renders AFTER-01's five contents with named contradictions and a stated-gap discipline; both lanes call it and record their ephemeral facts as observed; the regenerated ingest workflow is deployed, bounced and read-back-verified live; and the operator authorised a SMALL, supervised first live batch rather than the first unattended one — D-61-08's gate stays shut.
- Extended the Phase-35 contact extraction validator to a second record type — companies — with a name-alone identity rule, per-type dedupe, and six documented source adapters, without touching a single line of `enrichment.py`'s already-shipped companies envelope form.
- Live execution (11972) confirms `mode: "propose"` rides the recompute lane to `Decide Company Action` and forces a non-writing `"proposed"` action; operator deferred the backend research-node extension to a later phase.
- A pure decision module turns a batch of proposed company domains into a decided set atomically — one shared host guard, no silent default, no dropped row — and the operator's live walk of the resulting confirm table came back APPROVED with no wording flagged.
- Backend domain research is now a priced, declinable envelope line -- `cost_guard.research_line` never renders a fabricated or zero-standing-in-for-unknown figure, and `company_domain.decline_research` converges a struck line onto the exact same name-only code path a manual decline already uses -- while Task 3's backend extension stays deferred, exactly as the operator decided at 58-02's checkpoint, with zero code touched.
- Native `country`, `city`, and `numberofemployees` now travel from provider payload to the HubSpot PATCH body on the company enrichment lane, blank-fill only, proven live on execution 11980 against Series Futsal Victoria itself. The record's own retro-fix landed by a different path than planned -- the operator's own walk session armed a full re-enrich before Task 4 resumed, achieving the plan's goal but also regressing the record with a false Non-ANZ veto (root cause scoped out to gap-closure plan 58-06); Task 4 then executed as a corrective window instead, clearing the veto without re-running the same wrong provider match.
- A cross-provider disagreement on any of five decision-driving company fields — starting with the exact `lv_country_region_normalized`/`country` shape that fired a false Non-ANZ veto on Series Futsal Victoria in execution 11983 — can no longer promote unadjudicated and flip `lv_anti_icp_flag`; it is withheld, the record is flagged naming the disagreeing sources, and the existing Sonnet judge can resolve it (including a resolution that legitimately fires the veto). Tasks 1-3 complete and live-proven (execution 11987); Task 4 resolved by the operator 2026-08-26 -- plan complete.
- A new `written_records.py` module classifies every n8n dispatch response into written/created_id_unknown/not_written and `chunking.dispatch_plan` flushes it into a durable JSON file per chunk, inline in the loop, so a run that dies mid-way or is revoked-but-completing still shows what actually landed in HubSpot.
- Root `tests/conftest.py` autouse fixture strips `ANTHROPIC_API_KEY`/`HUBSPOT_PRIVATE_APP_TOKEN` from every test by default, gated on `RUN_LIVE_PARITY` (not a nonexistent pytest marker), with both branches proven — the default strip in-process, the opt-in preserve via subprocess.
- The two-lane grant's operator-facing warning ("the HubSpot write is authorized BEFORE the enriched preview exists") is retired at all four surfaces -- `write_grant.py`, SKILL.md (two locations), and README.md -- replaced by a plain non-blocking statement plus a pointer to the post-run `written_records.json` list, with every pinning test re-pointed via a negative assertion rather than relaxed, shipped as plugin 0.22.0.
- Shipped the plugin's first `hooks/` directory: a `SessionStart` hook that tells the operator, once per session and non-blockingly, that once enrichment and writing to HubSpot start the run continues to completion -- a revoke refuses the NEXT send, and a dispatch already running finishes its remaining chunks -- proven by a subprocess contract test rather than by starting a Claude session, and released as plugin 0.23.0.
- `chunking.dispatch_plan`'s `RecordSpecError` handler now relays the gate's own message and its `resolvable` tuple instead of a generic placeholder — closing the one severed integration link that kept GATE-02 through GATE-05's D-59-08 resolve-and-propose payload from ever reaching the operator.
- Closed gap 3 of `59-VERIFICATION.md`: `dispatch_plan` now catches a written-records bookkeeping failure (raised or falsey-returned) in one guard, keeps sending every remaining chunk, and reports an incomplete written-records list loudly across four surfaces instead of letting it crash the dispatch silently.
- "review" is now a real grantable lane end to end — one Python arm implementation shared by dispatch and review via an `authority=` keyword, `submit_decision` gated by `write_grant.authorize_send` instead of the retired `ALLOW_REVIEW_SUBMIT` shell variable, and `disarm` rebuilt to derive what it rewrites from what a workflow actually declares.
- Guardrail A now reads all five overlayable write-safety constants (not four) so a stuck-open `ALLOW_HUBSPOT_REVIEW_WRITES` refuses the next grant by name, and `write_grant.authorize_review_batch` gives a triage sitting one arm/disarm round trip instead of one per decision — with `preflight_before_send` structurally unable to trip over that same batch window's own arm.
- A review approve/reject now lands in the run's `written_records-<run_id>.json` artifact through a new `classify_review_item`, which maps the review endpoint's seven-word outcome vocabulary onto the artifact's existing eight-word one — and no bookkeeping failure of either shape (`OSError` or `WrittenRecordsError`) can stop or hide the write's own outcome.
- The retired `ALLOW_REVIEW_SUBMIT` shell-variable gate is gone from every operator-facing surface — the backend's own refusal message, `review-triage/SKILL.md`'s new grant-authorized batch-window sitting, the two dispatch skills' three-lane grant notes, the README/USAGE gate tables, and a `CHANGELOG.md` entry that records Phase 60's reversal of 30-01's design as a reversal — shipped as plugin `v0.35.0`.
- Operator chose HubSpot-object-plus-client-manifest for async run state; all six previously-open premises closed by n8n docs and a live disarmed probe, with sub-workflow dispatch surfacing as 61-05's strongest candidate.
- A LinkedIn-only row now routes to a dedicated `linkedin` match lane, reaches a HubSpot search that filters on the property that actually exists (both `lv_linkedin_url` and native `hs_linkedin_url`, over a written-down variant set), and comes back with a verified verdict — closing the exact defect that halted walk run 4.
- A LinkedIn-URL-only row — the exact walk-failure row from 53-WALK-RECORD-3.md FINDING D — now passes every identity gate in the plugin (YAML, columnMap.js, extraction.py), with its rejection message derived from config instead of hard-coded, and its waterfall findings routed through the existing D-59-08 resolutions loop instead of a second proposal surface.
- A deterministic confidence table over signals the pipeline already produces, a durable held-rows queue with a per-hold-code resume fingerprint that never re-spends provider credit, and a batch that reaches its last row whatever any single row does — the concrete answer to Finding F's "no self-assessment of confidence, and therefore no autonomy."
- `run_state.py` (substrate-1 async-ack shape) reports live progress over `run_manifest.py`'s per-row verdicts; `chunking.py`/`watch.py` gained per-chunk manifest merge and a four-sentence resume-or-disclose report; deployed to all five cloud workflows and proven live with one bounded, disarmed, zero-spend run (execution `12040`).
- `suggest_contacts.py` + `role_classify.py`: a company with zero associated contacts, discovered via the existing sitemap ladder, role-filtered, deduped against known contacts, and synthesised into a row `extraction.validate()` accepts on identity group 2 — proved end to end in one offline tracer test.
- `scripts/role_vocabulary.py` (repo root, credential- and portal-guarded) sweeps live contact `jobtitle` values and clusters them with one cached Haiku call into a committed YAML; `role_classify.py` gained the loader/offer/select trio that carries the vocabulary's evidence status all the way to the operator-facing menu, and SUGGEST-03 was amended — not closed — to permit that disclosed fallback.
- `cost_guard.suggestion_line()` prices a suggestion round as a two-component worst-case ceiling (unmeasured stage-1 page fetches, stage-2 Lusha-contact credits), and `write_grant.envelope()`/`plan_grant()` fold that allowance into the SAME opening grant envelope the operator already opens for enrichment — one disclosure, one yes, and an over-budget round refused before it starts using Phase 57's existing `CEILING_OVER` split offer.
- `sourceByField` mirrors `confidenceByField` on the Phase 15 provenance blob, wired through a round-level envelope flag (never a row column); `num_associated_contacts` rides HubSpot's own read-only rollup onto the enrichment response, with a client-side outcome-contract version widened to accept both the deployed and the regenerated producer.
- `skills/suggest-contacts/SKILL.md` composes plans 62-01 through 62-04 into one 9-step, auto-offered round; `enrich-records/SKILL.md` now prices the round into the SAME grant a company batch already opens and raises the offer unprompted at the end of every run; released as plugin 0.36.0.
- `suggest_contacts.CapRefused` + `suggest_contacts.agreed_cap()`: the per-company cap that bounds a suggestion round's stage-2 provider spend is now validated in code at the sole function that applies it, and an operator-chosen cap above the grant's priced ceiling is refused by a real function instead of by SKILL.md prose alone — closing the gap `62-VERIFICATION.md`/`62-REVIEW.md` independently found and live-reproduced (CR-01/WR-01).
- A CRM-recorded bare domain (`bunburyturfclub.com.au`) now reaches a real, host-bound fetch ladder through both `discovery_plan` and `next_candidates`, closing the gap that made 83.5% of this portal's companies-with-a-website report "no people page" when the real problem was a malformed URL.
- Two seam functions (`mint_row_ids`, `rejoin_enriched`) close G-62-4's blocker — the documented suggest-contacts round could not dispatch stage 2 at all, because nothing ever called `preingest.build_rows_spec`.
- Replaced `classify_title`'s exact-label-only match with a token-contiguous-run, longest-wins, entity-aware matcher, and expanded the shipped fallback vocabulary from 8 generic corporate roles to 17, adding the racing-club governance titles measured live on 2026-09-03 (43 people named, 2 selected before this change).
- `same_host` now treats a single leading `www.` label as the same host as its apex — narrowly, in one shared helper, with the attacker-suffix/subdomain/port/dotless boundaries each pinned by their own test — and the round ships as 0.38.2 alongside 62-08's and 62-09's fixes.
- Merge Winners' 3-edge fan-in runs once per branch when a 2-row batch's rows diverge (one needs research, one does not); watch._build_response_rows and report_enrichment.enrichment_row_ledger took `runs[0]` only and silently dropped the other branch's row — proven live on executions 12096/12098, fixed with one shared `report.all_node_items` helper, and the synchronous path's identical exposure is named for the operator rather than guessed at.
- `partition_for_dispatch` now refuses to send a suggested row whose enriched email's domain is unrelated to the company that named the person — closing the measured defect where a US insurer's employee (`craig.smith@thehartford.com`) was one of the two rows that would have advanced from Roma Turf Club's own board page — shipped as plugin 0.38.3.
- Durable-home `/bin/sh` shim resolves the newest installed plugin version at every scheduled fire (D-63-01), a loud-but-non-refusing staleness self-check lands inside `lv-sweep-run.sh` (D-63-02), both reusing `durable_paths.py`'s existing version ordering (D-63-04), and `SWEEP-CRON-TEMPLATE.md` now pins the shim with a documented one-time re-point.
- A temporary, uniquely-labelled launchd agent proved the sweep launcher shim resolves and follows a simulated plugin update under a genuine scheduled fire — run three times live, every run exiting 0 with the registration independently confirmed removed — closing the sweep-crontab todo that the shim alone (63-01) could not close on its own.
- Offline replay of claude-sonnet-5 vs claude-haiku-4-5 over real stored n8n judge inputs returned DROP — one material `decision` disagreement plus a confidence_band-only corpus of 3 (below the fixed minimum of 10) — so the cheaper-model routing lever (D-63-05) does not ship and 63-04 lands 63-A alone.

---

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
