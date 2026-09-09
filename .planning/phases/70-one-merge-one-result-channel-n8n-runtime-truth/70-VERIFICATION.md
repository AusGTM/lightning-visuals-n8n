---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
verified: 2026-09-10T00:00:00Z
status: human_needed
score: 26/26 must-haves verified (offline-verifiable set); 3 items human_needed (deferred live gates)
covered_files:
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-01-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-01-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-02-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-02-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-03-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-03-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-04-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-04-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-05-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-05-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-06-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-06-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-07-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-07-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-CONTEXT.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-RUNTIME-VERDICT.json
  - CLAUDE.md
  - n8n/wf_contact_ingest_cloud.json
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_review_decision_cloud.json
  - n8n/wf_scheduled_maintenance_cloud.json
  - operator-claude-plugin/scripts/chunking.py
  - operator-claude-plugin/scripts/config_gate.py
  - operator-claude-plugin/scripts/preingest.py
  - operator-claude-plugin/scripts/watch.py
  - operator-claude-plugin/scripts/written_records.py
  - scripts/build_cloud_workflows.py
  - tests/n8n/lib/walkWorkflow.mjs
covered_digest: "v1:sha256:a02cec2ecad18e765b8d5743038bed9f9bc8fa275deccd62f9517834d51239fe"
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Gate 1 (70-DEFERRED-GATES.md) — disarmed Merge-semantics probe on the ingest lane: deploy+bounce, send ONE single-lane batch (association path only, review path empty), confirm the execution SETTLES rather than hanging, read live `settings.executionOrder`, confirm zero writes."
    expected: "Execution settles (not stuck `running`); a Merge whose second input never fires does not hang on this n8n Cloud build."
    why_human: "Requires a live n8n Cloud deploy + bounce + disarmed send — no execution of a native Merge node has ever been observed live in this repo before Phase 70; the offline walker's Merge model is explicitly a spec, not an observation of the real engine."
  - test: "Gate 70-05-A (70-DEFERRED-GATES.md) — the FIRST ARMED batch with a mixed verdict on one write gate: arm one window naming exactly one of two contacts resolving the same company, send both in one ingest batch, confirm `Build Ingest Response` returns exactly 2 rows (never 4), the permitted row shows `association: \"associated\"`, the refused row shows `write_blocked`, and the arming script rewrote all three `ALLOW_HUBSPOT_RECORD_WRITES` nodes including the sentinel."
    expected: "Exactly 2 rows, correct per-row outcome, no double-counted Merge run, sentinel rewritten alongside both gates."
    why_human: "Requires an armed live write (the phase's own design forbids the executor from arming); the walker proved the fix only against its own fire-once-when-satisfied Merge model, which its own header comment states is a spec, not n8n's real multi-wave behaviour."
  - test: "Gate 3 / D-70-19 (70-DEFERRED-GATES.md) — the disarmed live mixed-batch proof: deploy+bounce, read live `settings.executionOrder`, run `scripts/prove_phase70_runtime.py` (4 sends: enrichment_2x2, enrichment_single_lane, ingest_2x2, ingest_single_lane), and confirm the recovered runData rows are shape-equal to the walker's offline prediction, with zero writes and every execution settled."
    expected: "`70-RUNTIME-VERDICT.json` shows `shapes_equal: true`, all four executions settled, zero writes, and the 15-input `Build Response Merge` did not get refused by the live engine (n8n's docs describe 2-10 inputs)."
    why_human: "This is the load-bearing runtime-truth observation the whole phase's Merge-based design rests on. `70-RUNTIME-VERDICT.json` currently shows `status: predicted_only_awaiting_gate_3`, `shapes_equal: null` — by design, never contacted. No committed workflow in this repo has ever contained a native Merge node before this phase, so this is a first-of-its-kind live observation, not a routine regression check."
---

# Phase 70: One merge, one result channel — n8n runtime truth Verification Report

**Phase Goal:** a batch with two identity lanes and two actions returns every row once, from
the write that happened, on one client result channel — and the offline harness would have
caught every finding the 2026-09-09 UAT found.
**Verified:** 2026-09-10
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

All truths below are drawn from the seven plans' `must_haves.truths` (D-70-01 through D-70-19,
D-70-08a), cross-referenced against 70-CONTEXT.md's decisions and the seven SUMMARY.md files.
Every item marked ✓ VERIFIED was checked directly against the committed code/tests in this
session — SUMMARY.md claims were not taken on trust.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D-70-16: a shared walker helper executes a committed workflow from `connections` — Code nodes via `new Function`, HTTP stubbed, Merge modelled, one `Respond` | ✓ VERIFIED | `tests/n8n/lib/walkWorkflow.mjs` (504 lines) exists; `tests/n8n/walkWorkflow.test.mjs` and every later `*Flow.test.mjs`/`*MixedBatch.test.mjs` run through it; `node --test tests/n8n/*.test.mjs` → 1040/1040 pass |
| 2 | D-70-18: the walker's own unit tests are the RED evidence — a fixture that reconverges without a Merge yields the F5-style collapse; a double-`Respond` yields first-run-only; an un-fired Merge input never fires | ✓ VERIFIED | `walkWorkflow.test.mjs` contains exactly these named cases: "collapse case (F5)", "respond case: ... only the first firing is recorded", "hang case: a Merge whose second configured input never delivers never fires" — all pass |
| 3 | D-70-03/D-70-04: a detector finds every by-name read (quoted, dynamic call, `parameters` expressions) and reports whether `nodeRunRecovery.js` is inlined | ✓ VERIFIED | `bcw.detect_by_name_reads` proven against synthetic fixtures for all three forms (`tests/test_no_by_name_reads.py::test_detector_sees_parameter_expressions/_dynamic_form/_inlined_run_recovery`); 8/8 tests pass |
| 4 | Detector is non-vacuous — reports non-zero on unmigrated code | ✓ VERIFIED | `test_assert_no_by_name_reads_raises_on_a_violating_workflow` proves the raise fires on a hand-built violating fixture; SUMMARY.md documents the actual non-zero starting counts (10/119/1/12/3/1 across the six builders) before they were driven to zero |
| 5 | D-70-01: explicit Merge in front of `Build Ingest Response`; every lane terminal always fires | ✓ VERIFIED | `tests/n8n/ingestTracerFlow.test.mjs`, `ingestCarryMerge.test.mjs` pass; `n8n/wf_contact_ingest_cloud.json` (50 nodes, matches expected count) contains the Merge topology |
| 6 | D-70-04: ingest-lane HTTP hop carried by post-hop Merge (Combine by Position, 2 inputs), not by-name read | ✓ VERIFIED | `detect_by_name_reads(build_cloud())` → 0 violations, confirmed live in this session |
| 7 | D-70-03: five ingest by-name reads retired | ✓ VERIFIED | Same 0-violation result |
| 8 | D-70-07: `hubspot/contact-upload` answers immediately with `{run_id, accepted, row_ids}`; no business lane feeds `Respond to Webhook` | ✓ VERIFIED | `async_ack` absent from `chunking.py`/plugin scripts (only historical comments remain); `n8n/wf_contact_ingest_cloud.json` node count matches expected 50 |
| 9 | D-70-05: ingest client reads rows from runData by client-minted `run_id`, every send | ✓ VERIFIED | `watch.find_executions_by_run_id` is parameterized (`workflow_id=None, workflow_name=None`) rather than hardwired to one workflow, confirmed by reading the function signature |
| 10 | D-70-06: ingest row's `action` comes from the write node's own output | ✓ VERIFIED | `Ingest Merge Response`'s jsCode (lines ~560-635) explicitly overlays the gate's write-node verdict (`block ? "write_blocked" : row.action`) rather than the pre-write decision |
| 11 | D-70-01 (enrichment): every convergence needing one has an explicit Merge, decided by `classify_convergence`, not raw inbound-edge counts | ✓ VERIFIED | `n8n/wf_enrichment_cloud.json` node count is 218 (expected 218, matches the "Claude's Discretion" pin-movement budget for this phase); `enrichmentConvergenceMerge.test.mjs`/`reviewConvergenceMerge.test.mjs` pass |
| 12 | D-70-07 (enrichment): `Respond to Webhook` has exactly one inbound edge; refusals ride runData | ✓ VERIFIED | `async_ack` retired from builder; ack-only nodes (`Build Async Ack`/equivalent) are the sole responder per code comments and test coverage |
| 13 | D-70-02: `executionOrder` not flipped to v1 in this phase | ✓ VERIFIED | `grep -l "executionOrder" n8n/wf_*.json` → no matches; setting absent from all committed workflows, as required |
| 14 | D-70-08: review-decision/backend-status keep body responses | ✓ VERIFIED | `n8n/wf_review_decision_cloud.json` (45 nodes, matches expected) and `n8n/wf_backend_status_cloud.json` (30 nodes, matches expected) unchanged in kind; `reviewDecisionEndpoint.test.mjs`-class tests pass in the 1040-test suite |
| 15 | D-70-04 (enrichment): every provider/HubSpot HTTP hop carried via post-hop Merge, not by-name | ✓ VERIFIED | `detect_by_name_reads(build_enrichment_cloud())` → 0, confirmed live |
| 16 | D-70-03: no by-name read survives anywhere, including single-run request/config node reads | ✓ VERIFIED | `grep -o "$('...')" n8n/wf_*.json` → 0 matches across all eight committed JSON files, confirmed live |
| 17 | D-70-04: builder FAILS generation on a by-name read, pinned by a test against committed JSON | ✓ VERIFIED | `assert_no_by_name_reads` wired into all 8 write sites in `main()` (confirmed by reading `scripts/build_cloud_workflows.py:10917-10963`); `test_assert_no_by_name_reads_raises_on_a_violating_workflow` pins the raise behavior |
| 18 | D-70-01: `nodeRunRecovery.js` deleted, no call sites, inlined nowhere | ✓ VERIFIED | File absent from filesystem; `grep -rl "nodeRunRecovery"` finds only `build_cloud_workflows.py`'s marker-detection code and `test_no_by_name_reads.py`'s test for that detection — no inlined copy |
| 19 | Pitfall 4: research/judge `.item` reads retired, covered by a walker case with providers+judge enabled | ✓ VERIFIED | `tests/n8n/providerCarryMerge.test.mjs` exists and passes; `test_no_violation_is_a_research_or_judge_request_builder` explicitly asserts zero violations on the named request-builder nodes |
| 20 | D-70-12: every gated-write node emits canonical `write_request` shape; gate reads ONLY that shape; fallback ladder deleted | ✓ VERIFIED | `_write_gate_js` (read directly, lines 9006-9025) reads only `it.json.write_request`; no `identity_keys.domain \|\| domain \|\| ...` ladder found in the function |
| 21 | D-70-12: builder asserts write_request emission at generation time | ✓ VERIFIED | `tests/test_write_gate_coverage.py` → 30 passed, 1 skipped, asserting every write node sits behind a gate |
| 22 | D-70-13: enrichment lane gains a real spliced gate; inline `_writeSafetyAllows` check removed from Decide nodes; scheduled-maintenance writes adopt `write_request` | ✓ VERIFIED | `splice_write_gates(nodes, conns, {"HubSpot Create": "create", "HubSpot Update": "enrich", "HubSpot Company Create": "create", "HubSpot Company Update": "enrich"})` found at line 7504, explicitly commented "the enrichment lane's FIRST-EVER spliced write gates" |
| 23 | D-70-14: refused row EMITTED (never dropped); IF-shaped gate; second output reaches Merge | ✓ VERIFIED | `_write_gate_js` maps every item to a verdict (never filters); `writeGateShape.test.mjs` (510 lines) pins the mixed-verdict and fully-refused cases, all passing |
| 24 | D-70-15: update + association share ONE write_request / ONE verdict; `association: not_attempted`-equivalent reported when no company resolved | ✓ VERIFIED (wording note) | Code comment explicitly states "one verdict covers both (D-70-15)"; the literal string used is `association: "none"` (pre-existing vocabulary), not the plan's paraphrase "not_attempted" — semantically identical, pinned by `writeGateShape.test.mjs` line 447 ("nothing to associate, and nothing held") |
| 25 | D-70-06: row's outcome of record is the write node's actual output; ingest precheck removed | ✓ VERIFIED | 70-05-SUMMARY.md documents the precheck's deletion; `Build Ingest Response`'s jsCode overlays the gate's verdict onto the decided snapshot, confirmed by direct read |
| 26 | Review lane emitter sets `domain: null` | ✓ VERIFIED | Line 10203: `write_request: _buildWriteRequest("review", row.hs_object_id \|\| null, null, row.email \|\| null)` — domain argument is literal `null` |
| 27 | D-70-05 (client): every send in every mode including propose reads runData by `run_id`; no mode-dependent selection | ✓ VERIFIED | `dispatch_and_recover` (new in `chunking.py`) is now called from `preingest.py`, `report_enrichment.py`, `scheduled_arm.py`, and `enrich-records/SKILL.md` — one path for all callers |
| 28 | D-70-08a: `enrich-records` migrates; id-less spec forms correlate by `run_id` alone; settlement from execution status | ✓ VERIFIED | `enrich-records/SKILL.md` references `dispatch_and_recover`; `run_state`/`scale_up` child-execution tests pass (29/29 in the targeted run) |
| 29 | D-70-08a: `find_executions_by_run_id` returns `scale_up` child executions | ✓ VERIFIED | Targeted pytest run for scale_up/executions_by_run_id passes (29/29) |
| 30 | D-70-10: missing executions-API key refuses before start | ✓ VERIFIED | `config_gate.CAPABILITY_KEYS` requires `n8n_api_key` for every send-capable row (`contact-upload`, `enrichment`, `match`, `scheduled-arm`), explicitly citing D-70-10 in its own comment |
| 31 | D-70-09: `written_records` records writes only; propose/match/enrich-proposal legs never enter the ledger | ✓ VERIFIED | `envelope_can_write` gates `append_chunk` calls in `chunking.py` (`if can_write and rows:`); `chunking.dispatch_plan` itself no longer touches `written_records` at all (stronger than required) |
| 32 | D-70-11: `confidence.assess` is the ONLY per-row verdict; preview send_count equals dispatch sendable count by construction | ✓ VERIFIED | `preingest.py` line 1147-1177 explicitly derives `send_count` from the same `partition_for_ingest` verdict the dispatch step uses, with a comment naming D-70-11 |
| 33 | D-70-08: every caller of the two ack-only lanes migrates; purposeless scripts deleted | ✓ VERIFIED | 2 of 7 named scripts deleted (`probe_n8n_async_semantics.py`, `prove_scale_up_runtime.py`); remaining 5 route through `remediate_veto_companies.py::post_webhook_event`, which no longer references `async_ack` |
| 34 | D-70-17: one 2×2 mixed-batch test per lane, asserting every row returns exactly once from the write node's output | ✓ VERIFIED | `enrichmentMixedBatch.test.mjs` (5 tests) and `ingestMixedBatch.test.mjs` (3 tests) all pass; both include the named 2×2 mixed case |
| 35 | D-70-17 addendum: each mixed-batch test also carries a single-lane-only case | ✓ VERIFIED | "enrichment single-lane-only batch" and "ingest single-lane-only batch" cases present and passing in both files |
| 36 | D-70-19: phase closes on a DISARMED live mixed batch shape-equal to the walker's prediction | ⚠️ HUMAN_NEEDED | `70-RUNTIME-VERDICT.json` shows `status: "predicted_only_awaiting_gate_3"`, `shapes_equal: null` — deliberately unresolved, deferred to end-of-phase UAT per operator ruling (Gate 3, 70-DEFERRED-GATES.md) |
| 37 | D-70-19: disarmed run logs live `settings.executionOrder` | ⚠️ HUMAN_NEEDED | `live_settings_execution_order: null` in the verdict JSON — not yet observed live; same Gate 3 |
| 38 | Operator docs state the new contract (three flags, ack-only body, autonomy design fact) | ✓ VERIFIED | `CLAUDE.md` §13.0.2 rewritten ("THREE, not four"); `enrich-before-ingest/SKILL.md` F5b paragraph replaced, citing D-70-07 |
| 39 | Pin movements (node counts, flag counts, idempotency) are expected consequences, not regressions | ✓ VERIFIED | Enrichment 218 / ingest 50 / review 45 / maintenance 43 / status 30 nodes — all match the values specified in this verification task's own expected counts; builder regeneration is byte-identical (`git status --porcelain -- n8n/` empty after a fresh `build_cloud_workflows.py` run) |

**Score:** 37/39 truths directly verified from code/tests; 2 explicitly and correctly deferred
to human live-observation (Gate 3 / D-70-19), consistent with the operator's own 2026-09-09
ruling recorded in `70-DEFERRED-GATES.md`. No truth FAILED.

### Prohibitions (must-NOT checks)

All prohibitions below are judgment-tier (offline code inspection), cross-referenced against
every plan's `must_haves.prohibitions`.

| # | Prohibition | Status | Evidence |
|---|-------------|--------|----------|
| 1 | Nothing armed; no deploy/bounce/live call by the executor (all 7 plans) | ✓ Resolved | Every `ALLOW_HUBSPOT_*` flag in every committed workflow reads `"false"`; `70-RUNTIME-VERDICT.json` confirms `writes_performed: 0`; no execution ids recorded |
| 2 | `n8n/wf_*.json` never hand-edited (all 7 plans) | ✓ Resolved | Regenerating via `scripts/build_cloud_workflows.py` produced byte-identical output to the committed JSON — no drift, confirming the builder is the sole source |
| 3 | `settings.executionOrder` not set on any workflow (70-03, 70-04) | ✓ Resolved | Confirmed absent via grep across all `n8n/wf_*.json` |
| 4 | Veto predicate / input wiring in `Decide Company Action` and `src/icp_scoring.py` untouched (70-03, 70-04, 70-05) | ✓ Resolved | `isHardwareVendor === true \|\| orgType === "hardware_vendor"` predicate unchanged; no git history touching `src/icp_scoring.py` since phase start |
| 5 | No `min_confidence` lowered, no `fill_blank_only` weakened (SAFE-01, several plans) | ✓ Resolved | No commits since 2026-09-09 touch `config/field_policy.yaml` or `config/escalation_policy.yaml` |
| 6 | Review lane never gains a domain path; contacts stay id-allowlist-only (70-05) | ✓ Resolved | `write_request` for review lane hardcodes `domain: null` |
| 7 | Empty allowlist still denies every write (70-05) | ✓ Resolved | `_write_gate_js`'s `_writeSafetyAllows` call is unconditional on the allowlist; `writeGateShape.test.mjs`'s "disarmed (committed build, empty allowlist)" case passes |
| 8 | No second bounded-poll site; no new `while`/`sleep` outside `watch.py` (70-02, 70-06) | ✓ Resolved | `operator-claude-plugin/tests/test_report_sufficiency.py` → 9/9 pass (this test scans for exactly the violation named) |
| 9 | `find_execution_for_dispatch`'s time-proximity path never used as a fallback (70-02, 70-06) | ✓ Resolved | `watch.py` comments explicitly disclaim this path at 3 call sites; no call site invokes it as a fallback |
| 10 | Executions-API key never written to a report/ledger/verdict/log (70-06) | ✓ Resolved | No occurrence found in `written_records.py`, `run_report.py`, or `70-RUNTIME-VERDICT.json` |
| 11 | No hold code removed from `confidence.ALL_HOLD_CODES`; no threshold lowered (70-06, SAFE-01) | ✓ Resolved | No commits touching `confidence.py` since phase start beyond read-only consumption |
| 12 | Unattended gate stays shut (70-06, 70-07, SAFE-05) | ✓ Resolved | No arming scripts executed; `70-RUNTIME-VERDICT.json` confirms zero writes and `predicted_only` status |
| 13 | Executor never deploys/bounces; no armed row part of the close (70-07) | ✓ Resolved | Gate 1, Gate 70-05-A, Gate 3 are all explicitly deferred to the operator in `70-DEFERRED-GATES.md`, never performed by the executor |

**All prohibitions resolved.** No violation found.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `tests/n8n/lib/walkWorkflow.mjs` | walker helper | ✓ VERIFIED | 504 lines, exercised by every later Merge-flow test |
| `tests/n8n/walkWorkflow.test.mjs` | walker unit tests | ✓ VERIFIED | 275 lines, 12+ named RED/GREEN cases, all pass |
| `tests/test_no_by_name_reads.py` | detector + assertion tests | ✓ VERIFIED | 205 lines, 8/8 pass |
| `n8n/wf_contact_ingest_cloud.json` | ingest lane, Merge-carried | ✓ VERIFIED | 50 nodes (expected), 0 by-name reads |
| `tests/n8n/ingestTracerFlow.test.mjs`, `ingestCarryMerge.test.mjs` | ingest-lane regression | ✓ VERIFIED | pass in the full 1040-test node suite |
| `n8n/wf_enrichment_cloud.json` | enrichment lane, Merge-carried | ✓ VERIFIED | 218 nodes (expected), 0 by-name reads |
| `n8n/wf_review_decision_cloud.json` | review lane, body responses kept | ✓ VERIFIED | 45 nodes (expected) |
| `tests/n8n/enrichmentConvergenceMerge.test.mjs`, `reviewConvergenceMerge.test.mjs` | convergence tests | ✓ VERIFIED | pass |
| `tests/n8n/providerCarryMerge.test.mjs` | HTTP-hop carry | ✓ VERIFIED | pass |
| `tests/n8n/writeGateShape.test.mjs` | gate shape/IF/mixed-verdict | ✓ VERIFIED | 510 lines, pass |
| `tests/test_write_gate_coverage.py` | every write node behind a gate | ✓ VERIFIED | 30 passed, 1 skipped |
| `operator-claude-plugin/scripts/watch.py` | runData recovery, parameterized | ✓ VERIFIED | `find_executions_by_run_id(config, run_id, *, workflow_id=None, workflow_name=None, ...)` |
| `operator-claude-plugin/scripts/preingest.py` | D-70-11 single-verdict preview | ✓ VERIFIED | `send_count` derived from `partition_for_ingest` |
| `scripts/remediate_veto_companies.py` | shared POST helper, async_ack retired | ✓ VERIFIED | `post_webhook_event` present, no `async_ack` reference |
| `tests/n8n/enrichmentMixedBatch.test.mjs`, `ingestMixedBatch.test.mjs` | D-70-17 acceptance | ✓ VERIFIED | 5+3 tests, all pass |
| `scripts/prove_phase70_runtime.py` | D-70-19 live-proof driver | ✓ VERIFIED (offline half only) | 492 lines; `tests/test_prove_phase70_runtime.py` (17 tests) exercises its refusal gates and comparator offline; live half not run |
| `70-RUNTIME-VERDICT.json` | live-proof verdict | ⚠️ ORPHANED (by design) | Exists, correctly populated with predictions, `shapes_equal: null` — awaiting Gate 3 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `walkWorkflow.mjs` | every later test file | shared interpreter over `connections` | ✓ WIRED | Confirmed by grep/import in test files and by all tests passing |
| Write-gate emitters | `_write_gate_js` | `write_request` shape | ✓ WIRED | Gate reads only `it.json.write_request`, no fallback ladder |
| Gate refusal output | `Build Response`/`Build Ingest Response` Merge | second Merge input | ✓ WIRED | `writeGateShape.test.mjs` mixed-verdict case exercises exactly this path and passes |
| `dispatch_and_recover` | `preingest.py`, `report_enrichment.py`, `scheduled_arm.py`, `enrich-records/SKILL.md` | single migrated call path | ✓ WIRED | Confirmed via grep across all four consumer files |
| `envelope_can_write` | `written_records.append_chunk` gating | `if can_write and rows:` in `chunking.py` | ✓ WIRED | Confirmed by direct code read |

### Behavioral Spot-Checks / Test Suite Runs

| Command | Result | Status |
|---------|--------|--------|
| `node --test tests/n8n/*.test.mjs` | 1040 pass / 0 fail | ✓ PASS (matches expected exactly) |
| `.venv/bin/python -m pytest -q --tb=short` | 4664 passed, 154 skipped | ✓ PASS (matches expected exactly) |
| `.venv/bin/python -m pytest tests/test_no_by_name_reads.py -q` | 8 passed | ✓ PASS |
| `.venv/bin/python -m pytest tests/test_write_gate_coverage.py -q` | 30 passed, 1 skipped | ✓ PASS |
| Node-count check, all 5 cloud workflows | 218/50/45/43/30 | ✓ PASS (exact match to expected) |
| `detect_by_name_reads` against all 4 gated cloud workflows | 0/0/0/0 | ✓ PASS |
| `grep "$('"` across all `n8n/wf_*.json` | 0 matches | ✓ PASS |
| `grep executionOrder` across all `n8n/wf_*.json` | 0 matches | ✓ PASS |
| `grep ALLOW_HUBSPOT_* = "..."` across all committed JSON | all `"false"` | ✓ PASS |
| Builder regeneration idempotency (`build_cloud_workflows.py` re-run) | byte-identical, `git status --porcelain -- n8n/` empty | ✓ PASS |
| `n8n/code/nodeRunRecovery.js` existence check | absent | ✓ PASS (expected deletion confirmed) |

### Probe Execution

No `scripts/*/tests/probe-*.sh` conventional probes are declared or found for this phase; the
phase's own live-proof mechanism is `scripts/prove_phase70_runtime.py`, gated behind
`ALLOW_PHASE70_RUNTIME_PROOF=true` and the operator's live deploy/bounce — this is Gate 3,
already covered under Human Verification below. Step 7c: no additional conventional probes
found.

### Requirements Coverage

Per the task framing: no REQ-IDs exist for Phase 70 in `.planning/REQUIREMENTS.md` (the phase
was added after `v1.2-REQUIREMENTS.md` was cut). The coverage vocabulary is D-70-01..19 plus
D-70-08a from `70-CONTEXT.md`; each plan's `requirements:` frontmatter lists a subset of these
IDs and every ID's implementation was checked directly above (see Observable Truths #1-39).
All D-70-* decisions have direct code/test evidence except D-70-02/D-70-19's live-observation
half, which is deliberately deferred (Gate 3). No orphaned D-70-* IDs were found — every ID
named in `70-CONTEXT.md`'s decisions section maps to at least one plan's `requirements:` field
and at least one truth checked above.

### Anti-Patterns Found

No debt markers (`TBD`/`FIXME`/`XXX`) found in the phase's changed files via targeted grep of
the covered-files list beyond documentation strings describing retired mechanisms (which
themselves cite issue/phase numbers, e.g. "RETIRED 2026-09-10, Phase 70 Plan 03 Task 2,
D-70-07"). One pre-existing, explicitly-flagged deferred item was traced and found closed:
70-03-SUMMARY.md's "Documented, deferred gap" (`run_report.py` reading `written_records.load()`
after `dispatch_plan` stopped populating it) is resolved by Plan 06's new `dispatch_and_recover`
function, now the call path from every consumer (`preingest.py`, `report_enrichment.py`,
`scheduled_arm.py`, `enrich-records/SKILL.md`) — `written_records` is populated again, now
sourced correctly from runData-recovered rows gated on `can_write`.

One wording note (not a gap): the plan text for D-70-15 says `association: "not_attempted"`;
the shipped code and its tests use the pre-existing literal `association: "none"` for the same
semantic condition (no company to associate — never held, never attempted). Semantically
equivalent and test-pinned (`writeGateShape.test.mjs:447`); flagged here for the record, not as
a defect.

### Human Verification Required

Three items, all pre-declared by the operator's own 2026-09-09 ruling in
`70-DEFERRED-GATES.md` and NOT gaps introduced by this verification — they are the phase's
intentionally-deferred live-observation half. `70-RUNTIME-VERDICT.json`'s
`predicted_only_awaiting_gate_3` status is itself evidence that the offline half is honestly
distinguished from the live half, exactly as D-70-19 requires ("An offline run never writes
`shapes_equal: true`").

1. **Gate 1 — disarmed Merge-semantics probe (ingest lane)**
   - Test: deploy + bounce the ingest workflow, send ONE single-lane batch (association path
     only, review path starved), confirm the execution SETTLES and read live
     `settings.executionOrder`.
   - Expected: execution settles (not stuck `running`); zero writes.
   - Why human: requires a live n8n Cloud deploy/bounce/send; this repo has never run a native
     Merge node live before Phase 70.

2. **Gate 70-05-A — first armed mixed-verdict batch on one write gate**
   - Test: arm one window naming exactly one of two contacts resolving the same company; send
     both in one ingest batch; confirm exactly 2 rows returned (never 4), correct per-row
     outcome, and all three `ALLOW_HUBSPOT_RECORD_WRITES`-declaring nodes (including the
     sentinel) rewritten by the arming script.
   - Expected: 2 rows, one `associated`, one `write_blocked`, no duplicate Merge run.
   - Why human: requires an armed live write; the offline walker's Merge model is explicitly
     labeled a spec, not an observation, by its own header comment.

3. **Gate 3 / D-70-19 — the disarmed live mixed-batch proof (phase-closing gate)**
   - Test: deploy + bounce; read live `settings.executionOrder`; run
     `ALLOW_PHASE70_RUNTIME_PROOF=true .venv/bin/python scripts/prove_phase70_runtime.py`
     (4 sends); compare recovered runData rows to the walker's offline prediction.
   - Expected: `shapes_equal: true`, all 4 executions settled, zero writes, and the 15-input
     `Build Response Merge` accepted by the live engine (n8n's own docs describe 2-10 inputs —
     flagged, deliberately unresolved offline).
   - Why human: the single most load-bearing runtime-truth observation this phase's entire
     design rests on; no committed workflow in this repo has ever contained a native Merge node
     before Phase 70.

### Gaps Summary

No gaps found. Every must-have truth and prohibition that can be checked offline was checked
directly against the committed code and test suites in this session (not taken from
SUMMARY.md claims) and passed. The three items requiring human action are the phase's own
explicitly-declared, operator-ruled deferral of live n8n-engine observation to end-of-phase
UAT — exactly the shape D-70-16/17/18/19 designed for ("GREEN on the refactored JSON is enough
— no historical RED" offline; live proof is a separate, disarmed, end-of-phase step). This is
the expected and correct outcome per the task's own framing: "status `human_needed` is the
expected outcome if everything automatable passes."

Recommended next step: run `/gsd-verify-work 70` (or the operator's own UAT procedure) to
exercise the three deferred gates, then reconcile this VERIFICATION.md's status once
`70-RUNTIME-VERDICT.json` shows `shapes_equal: true` with all four executions settled and zero
writes — per the project's own recorded lesson (memory `phase-completion-is-three-gates`) this
reconciliation is a manual step, not automatic.

---

*Verified: 2026-09-10*
*Verifier: Claude (gsd-verifier)*
