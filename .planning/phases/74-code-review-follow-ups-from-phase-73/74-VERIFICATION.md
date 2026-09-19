---
phase: 74-code-review-follow-ups-from-phase-73
verified: 2026-09-19T10:47:37Z
status: passed
score: 16/16 must-haves verified
covered_files:
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-01-PLAN.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-01-SUMMARY.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-02-PLAN.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-02-SUMMARY.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-03-PLAN.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-03-SUMMARY.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-04-PLAN.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-04-SUMMARY.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-05-PLAN.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-05-SUMMARY.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-06-PLAN.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-06-SUMMARY.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-CONTEXT.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-DISCUSSION-LOG.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-PATTERNS.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-RESEARCH.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-UAT.md
  - .planning/phases/74-code-review-follow-ups-from-phase-73/74-VALIDATION.md
covered_digest: "v1:sha256:05bebab261a632aace8866e084ba370da8fdd73ec7a8823298278bed67235833"
behavior_unverified: 0
overrides_applied: 0
---

# Phase 74: Code-review follow-ups from phase 73 Verification Report

**Phase Goal:** close the 16 findings in `73-REVIEW.md` (4 blocker, 12 warning) that were
triaged 2026-09-18 as non-breaking and carried out of phase 73, in the roadmap's stated fix
order, regenerate JSON, keep suites green, and have the disarmed deploy be the operator's step.
**Verified:** 2026-09-19
**Status:** passed
**Re-verification:** No — initial verification

## Method

No previous VERIFICATION.md existed for this phase (Step 0 checked). No `success_criteria`
array is attached to this roadmap entry and no `REQUIREMENTS.md` ids map to Phase 74 (confirmed
by grep — zero hits for `Phase 74`, `D-74-`, `CR-0[1-4]`, `WR-0[1-9]`, `WR-1[0-2]` in
`.planning/REQUIREMENTS.md`), so must-haves were derived (Option C) directly from the 16
`73-REVIEW.md` findings plus the phase's own `74-CONTEXT.md` decisions D-74-01..D-74-14, exactly
as the phase brief instructs. Every plan's `requirements:` frontmatter field was cross-checked
against the full CR-01..04 / WR-01..12 / D-74-01..14 id set — all 30 ids are claimed by at least
one of the six plans; none are orphaned, none are claimed by zero plans.

All claims below were checked against the actual code, not SUMMARY.md prose: each finding's
fix was located directly in the file `73-REVIEW.md` named, the suites were run fresh in this
session (not read from a SUMMARY's stated pass count), and the disarmed live gate's operator
confirmation was cross-read in `74-UAT.md` rather than assumed from a plan's "complete" status.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | CR-03: an unjoined create (`create_outcome` `none`/`refused`) is reported and persisted as `create_unconfirmed` → `FAILED`, never as a successful create or `created_id_unknown` | ✓ VERIFIED | `scripts/build_cloud_workflows.py:899-928,1000,1039-1040` (`BUILD_CREATE_FAILURE_ROW_JS` widened filter, `BUILD_INGEST_RESPONSE`'s `unconf` join); `operator-claude-plugin/scripts/written_records.py:216` (`"create_unconfirmed": FAILED`); test `operator-claude-plugin/tests/test_written_records.py::test_create_unconfirmed_is_failed_never_a_success_shaped_outcome` passes (ran live) |
| 2 | CR-02: classification of `HubSpot Create`'s error branch no longer depends on a guessed n8n error-item shape — an explicit `_create_error` stamp is tested first | ✓ VERIFIED | `n8n/code/pairCreateOutcome.js:93,109-115` (`_isStampedError` checked before `_isCarriedRow`/`_isSuccessResponse`); `Create Error Stamp` node present in generated `n8n/wf_contact_ingest_cloud.json` (grep count 4) |
| 3 | CR-04: the runData freezer redacts `headers`/`error`/`request`/`options`/`config` (plus the empirically-found `zoom_token`/`access_token`) at any depth, applied per node-run so `run.error` is covered; all 7 pre-existing fixtures re-redacted; a directory-wide value-shape guard exists | ✓ VERIFIED | `scripts/freeze_execution_rundata.py` `_scrub`/`_SENSITIVE_KEYS`; `node --test tests/n8n/frozenFixtureSecrets.test.mjs` → 2/2 pass (ran live); zero `eyJ` (JWT-shaped) occurrences in `exec_12434`, `exec_12449`, and all 5 Phase-70 fixtures (checked directly, all 0) |
| 4 | CR-01: the `set_always_output_data(["HubSpot Create"])` builder comment (`scripts/build_cloud_workflows.py`, ~line 2266-2296) is corrected to say what execution `12522` showed — output 0 padded, output 1 (error edge) absent, one v1 end-of-run drain, `alwaysOutputData` kept for the all-rejected-batch case only, not the error branch; `walkWorkflow.mjs` models `alwaysOutputData` as padding **output index 0 only**; CLAUDE.md §13.0.3 gains the row | ✓ VERIFIED | read `scripts/build_cloud_workflows.py:2266-2296` directly: the comment now states “ensureAlwaysOutputData rescues ONLY output index 0, never output 1... alwaysOutputData is KEPT... not for the error branch, but because it DOES rescue output 0... on an ALL-REJECTED batch”, citing execution `12522`'s exact item counts; `tests/n8n/lib/walkWorkflow.mjs:534` (`outputIndex === 0` guard, no per-node exemption); CLAUDE.md line 2869 (`[documented]`+`[observed live]` row) |
| 5 | WR-01/WR-02: contact-upload grant-preview execution count survives a missing chunk-ceiling config key; basis/providers taken per-lane, not borrowed from the enrichment lane | ✓ VERIFIED | `operator-claude-plugin/scripts/write_grant.py:190` (`CONTACT_UPLOAD_BASIS`), `:536,593,601,604,613` (per-lane branching); `test_write_grant.py`'s two new cases pass |
| 6 | WR-05: `backfill_missing_identity`'s ledger is keyed by `(lane, id)`; an id ambiguous across lanes is skipped, never last-lane-wins | ✓ VERIFIED | `operator-claude-plugin/scripts/report_enrichment.py:223,259-261` (ambiguity-is-skip logic); two new `test_report_enrichment.py` cases pass |
| 7 | WR-06: `dispatch_and_recover` returns `excluded_marker_count` (non-zero only) instead of discarding it; D-74-13's recovery bound honours the config override end to end | ✓ VERIFIED | `operator-claude-plugin/scripts/chunking.py:691-693,718-722`; `test_chunking.py`'s WR-06 and D-74-13 cases (incl. the advisor-caught per-row-floor pin) pass |
| 8 | WR-03: `csv_dedupe.py`'s CLI resolves `column_mapping_path` through the same `config_gate.load_config()` reader `preview.py` uses | ✓ VERIFIED | `operator-claude-plugin/scripts/csv_dedupe.py:153,180` (`_resolve_configured_mapping_path`); 3 new tests pass |
| 9 | WR-04: `preview.py`'s `--collapsed` sidecar raises `CollapsedBlockError` naming the path on a read failure, instead of silently rendering "no duplicates" | ✓ VERIFIED | `operator-claude-plugin/scripts/preview.py:155,162,180,302` (`CollapsedBlockError`/`read_collapsed_block`); 4 new tests pass |
| 10 | WR-07/D-74-02: `Ingest Merge Response`'s write-gated create-failure input has a gated starved-lane sentinel covering the zero-create and writes-refused cases | ✓ VERIFIED | `scripts/build_cloud_workflows.py:2355-2368` (`Create Failure Row Sentinel` + gate); node present in generated `wf_contact_ingest_cloud.json` (grep count 7); 3 direct sentinel-gate-delivery tests added in the follow-up commit `fd20d725` (a real, non-vacuous test after an advisor-caught vacuous first attempt) |
| 11 | WR-08: `walkWorkflow.mjs`'s stale JSDoc sentence (claiming a plain-array stub always yields one output) is corrected to match the always-two-output implementation | ✓ VERIFIED | read `tests/n8n/lib/walkWorkflow.mjs` directly: the stale “yields exactly one output even on such a node” sentence is gone (grep for it returns nothing); the corrected sentence is present at line 356 (“...and ALSO yields both outputs on such a node”), consistent with the implementation at lines 299-321 (`{ success: raw, error: [] }`) |
| 12 | WR-09: `review_decision.verify_decision`'s leg-1 comparison tests key presence before value equality, so an approved-but-dropped blank patch key is caught | ✓ VERIFIED | `operator-claude-plugin/scripts/review_decision.py:382-386,501,518,550`; 4 new `test_review_decision.py` cases pass |
| 13 | WR-10: `extract_js_const` raises on an unbalanced (silently truncated) extraction instead of splicing broken text into a generated Code node | ✓ VERIFIED | `scripts/build_cloud_workflows.py` `extract_js_const` balanced-bracket guard; `tests/test_extract_js_const.py` (new file, 4 cases) passes |
| 14 | WR-11/WR-12: `csv_dedupe._canonical_rows` walks the header by index (never `zip()`-truncates a short row); `apply_dedupe`'s default output lands beside the input's own resolved path, never a bare-stem-keyed shared scratch dir | ✓ VERIFIED | `operator-claude-plugin/scripts/csv_dedupe.py:44` (`_canonical_rows`), `:131` (`out_dir = ... path.parent`); new tests in `test_csv_dedupe.py` pass |
| 15 | Both regenerated `n8n/*.json` bodies match the generator exactly (no hand-edits), and both full suites are green | ✓ VERIFIED | Ran live in this session: `.venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/` → exit 0; `node --test tests/n8n/*.test.mjs` → 1321 pass / 0 fail; `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider` → 5170 passed / 160 skipped — all three figures match the phase's own stated expectations exactly |
| 16 | D-74-11: the end-of-phase disarmed deploy/bounce/proof-send gate ran, nothing armed, and the operator confirmed the gate closed | ✓ VERIFIED | `74-UAT.md` Task 1 (two scoped `--only` deploys + one bounce, both live bodies read back with every `ALLOW_*` flag `"false"`), Task 2 (exactly 2 executions, `12676`/`12677`, both frozen and guard-clean), Task 4 "Operator confirmation" section (operator replied "confirmed" 2026-09-19, all 6 `<how-to-verify>` items independently re-corroborated read-only by the orchestrator before the reply) |

**Score:** 16/16 truths verified (0 present-but-behavior-unverified)

### Deferred Items

None — no gap in this phase's scope was pushed to a later phase.

### Advisory (New Scope, Unevidenced)

Not applicable — this is an initial verification, not a re-verification round.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/freeze_execution_rundata.py` | widened `_scrub`, `--rescrub` mode | ✓ VERIFIED | present, wired, exercised by `tests/test_freeze_execution_rundata.py` |
| `tests/n8n/frozenFixtureSecrets.test.mjs` | directory-wide secret-shape guard | ✓ VERIFIED | 2/2 pass, ran live |
| `tests/n8n/fixtures/frozen/exec_12522.runData.json` | D-74-03 fidelity fixture | ✓ VERIFIED | exists, used by `walkerEngineFidelityV1.test.mjs` |
| `tests/n8n/fixtures/frozen/exec_12676.runData.json`, `exec_12677.runData.json` | live-gate proof fixtures | ✓ VERIFIED | exist, guard-clean, cited in `74-UAT.md` |
| `n8n/code/pairCreateOutcome.js` | stamp-first classification | ✓ VERIFIED | wired into `Create Carry Merge` via `Create Error Stamp` node |
| `scripts/build_cloud_workflows.py` | `Create Error Stamp`, `Create Failure Row Sentinel`, `Companies Research Errored Sentinel`, `extract_js_const` guard | ✓ VERIFIED | all four present, all generate into the committed JSON |
| `n8n/wf_contact_ingest_cloud.json` | regenerated, 101 nodes | ✓ VERIFIED | node count 101 confirmed by direct JSON parse; matches `74-05-SUMMARY.md`'s and `74-UAT.md`'s stated live count |
| `n8n/wf_enrichment_cloud.json` | regenerated, 289 nodes | ✓ VERIFIED | node count 289 confirmed by direct JSON parse; matches `74-04-SUMMARY.md`'s and `74-UAT.md`'s stated live count |
| `operator-claude-plugin/scripts/write_grant.py`, `report_enrichment.py`, `chunking.py`, `csv_dedupe.py`, `preview.py`, `review_decision.py`, `written_records.py` | WR-01..WR-12 fixes | ✓ VERIFIED | each fix located directly in the named file/line, each with a passing new test |
| `CLAUDE.md` §13.0.1/§13.0.3 | rewritten stale claims, two new rows | ✓ VERIFIED | read directly; both rows present with `[documented]`/`[observed live]` tags and execution citations |
| `operator-claude-plugin/.claude-plugin/plugin.json`, `CHANGELOG.md` | version bump | ✓ VERIFIED | `"version": "0.52.0"`, one new CHANGELOG entry |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `HubSpot Create` error output | `Create Error Stamp` | generated edge, index 1 | ✓ WIRED | `ingestCarryMerge.test.mjs`'s updated structural assertion (special-cases output 1 to expect the stamp node) passes live |
| `Create Error Stamp` | `pairCreateOutcome.js` (`Create Carry Merge`) | `_create_error` field | ✓ WIRED | `pairCreateOutcome.test.mjs` stamp-beats-shape cases pass |
| `BUILD_CREATE_FAILURE_ROW_JS` | `BUILD_INGEST_RESPONSE` | `create_outcome`/`action` fields on the emitted row | ✓ WIRED | `ingestCreateErrorLane.test.mjs`, `ingestMixedBatch.test.mjs` graph-level cases pass |
| `written_records.classify_item` | `ACTION_TO_OUTCOME["create_unconfirmed"]` | dict lookup | ✓ WIRED | `test_written_records.py` mapping test passes |
| `Create Failure Row Sentinel` | `Ingest Merge Response` input 5 | `_append_merge_input`-derived index | ✓ WIRED | Python walk of generated graph confirms exactly two producers on input 5; 3 direct gate-delivery tests pass |
| `Companies Research Errored Sentinel` | `Merge Company Fan-In` inputs 1/2 | `_add_starved_lane_sentinel` | ✓ WIRED | `enrichmentConvergenceMerge.test.mjs` D-74-14 case (all-errored/mixed/no-error batches) passes |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full node test suite | `node --test tests/n8n/*.test.mjs` | 1321 pass / 0 fail | ✓ PASS |
| Full python test suite | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider` | 5170 passed / 160 skipped | ✓ PASS |
| Generated JSON matches generator | `.venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/` | exit 0 | ✓ PASS |
| Secret-shape guard over frozen fixtures | `node --test tests/n8n/frozenFixtureSecrets.test.mjs` | 2/2 pass | ✓ PASS |
| `create_unconfirmed` mapping | `pytest -k create_unconfirmed` (written_records) | 2 passed | ✓ PASS |
| No debt markers in phase-touched core files | `grep -n -E "TBD|FIXME|XXX"` over the 11 primary changed files | 0 hits | ✓ PASS |

All checks above were run live in this verification session, not read from a SUMMARY's stated
figure.

### Probe Execution

Not applicable — no `scripts/*/tests/probe-*.sh` files are declared by this phase's PLAN/SUMMARY,
and this is not a migration/tooling phase in the probe-bearing sense. The phase's own live gate
(deploy/bounce/proof-send) is a distinct mechanism, already recorded under Truth 16 above and
independently corroborated in `74-UAT.md` — not re-run here per the task's explicit instruction
not to deploy, bounce, send, or arm anything.

### Requirements Coverage

No `REQUIREMENTS.md` ids map to Phase 74 (confirmed: zero grep hits). This phase is keyed
entirely on `73-REVIEW.md`'s 16 findings (CR-01..04, WR-01..12) and `74-CONTEXT.md`'s decisions
D-74-01..D-74-14, all of which are covered above as observable truths. Cross-referencing every
plan's `requirements:` frontmatter field against the full id set: all 16 findings and all 14
decisions are claimed by at least one plan; none orphaned.

| Finding/Decision | Claimed by | Status |
|---|---|---|
| CR-01 | 74-01, 74-04, 74-05 | ✓ SATISFIED |
| CR-02 | 74-05 | ✓ SATISFIED |
| CR-03 | 74-05 (D-74-06) | ✓ SATISFIED |
| CR-04 | 74-01 (D-74-07/08/09) | ✓ SATISFIED |
| WR-01, WR-02 | 74-02 | ✓ SATISFIED |
| WR-03, WR-04, WR-09, WR-11, WR-12 | 74-03 | ✓ SATISFIED |
| WR-05, WR-06 | 74-02 | ✓ SATISFIED |
| WR-07 | 74-05 (D-74-02) | ✓ SATISFIED |
| WR-08 | 74-04 | ✓ SATISFIED |
| WR-10 | 74-05 | ✓ SATISFIED |
| D-74-12 (MN-01) | 74-04, 74-06 | ✓ SATISFIED (searched, stays genuinely open per its own trigger — not a gap; correct disposition per D-74-12's own instruction) |
| D-74-13 (Stage D) | 74-02, 74-06 | ✓ SATISFIED (bound-resolution wiring done; Stage D surfacing confirmed as already-derivable no-op; the separate Stage D todo correctly stays pending its own trigger) |
| D-74-11 | 74-06 | ✓ SATISFIED |
| D-74-14 | 74-04, 74-06 | ✓ SATISFIED |

### Anti-Patterns Found

None. Scanned the 11 primary files this phase changed for `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/
`PLACEHOLDER` — zero debt markers (one incidental match, `REDACTED_PLACEHOLDER`, is the
freezer's own intended redaction-constant name, not a stub marker).

### Human Verification Required

None. The phase's one live-gate checkpoint (D-74-11) was already run end-to-end and confirmed
by the operator in `74-UAT.md`'s Task 4 "Operator confirmation" section on 2026-09-19, with the
orchestrator's independent read-only re-corroboration recorded immediately above it. Per this
task's explicit instruction, those six items are not re-listed here as outstanding.

Two coverage rows in `74-06-SUMMARY.md` (D3/D4) were marked `human_judgment: true` at execution
time because the live trace diverged from the plan's literal predicted node ("Create Carry
Merge" vs. the two bypass sentinels that actually fired on the all-update batch; two Merge
double-fires that needed tracing to confirm benign-vs-lossy). Both were resolved through the
same Task 4 operator confirmation and independent orchestrator re-check already covered above —
no further human action is outstanding.

## Gaps Summary

None. All 4 blocker findings (CR-01..04) and all 12 warning findings (WR-01..12) are fixed in
code with a passing test each, cross-checked directly against the file:line `73-REVIEW.md`
named. All 14 context decisions (D-74-01..D-74-14) were honored, including both amendments
(D-74-01 ruled B' — no new producer on the error input, only the explicit stamp; D-74-03 landed
with no per-node exemption, closing the sibling gap D-74-14 named). Both regenerated cloud
workflow JSON bodies match their generator exactly. Both full suites are green at the exact
figures the phase declared (1321/0 node, 5170/160 pytest). The end-of-phase disarmed live gate
ran, nothing was armed at any point, and the operator confirmed closure. Two open todos (MN-01,
Stage D) correctly remain open on their own unfired triggers — this is the documented, intended
disposition per D-74-12/D-74-13, not an unaddressed gap.

---

_Verified: 2026-09-19_
_Verifier: Claude (gsd-verifier)_
