---
phase: 43-pipeline-scoring-hygiene-explainability
plan: 01
subsystem: pipeline
tags: [n8n, hubspot, boolean-coercion, review-queue, icp-scoring, jest-free-node-test]

# Dependency graph
requires:
  - phase: 40-scoring-engine-remediation-notes
    provides: "DEFAULT_COMPANY_POLICY's veto_output min_confidence already raised to 80 (D-04/P2)"
  - phase: 36-enrichment-propose-mode
    provides: "the 36-07 boolean-to-quoted-string EQ-filter fix idiom this plan replicates at 4 more sites"
provides:
  - "Every boolean-valued HubSpot property write in the pipeline emits the string \"true\"/\"false\" (D-07, 6 write sites)"
  - "mergeCompanies.js's promote branch coerces boolean candidates at the moment of promotion (D-09/D-10, PIPE-02 closed)"
  - "tests/test_review_flag_eq_filter.py — live-gated EQ-filter proof, authored, ready for 43-04"
affects: [43-04-live-verification, 43-05-deploy]

actuals:
  tokens: 4800
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Boolean-coercion at the properties-finalization loop (extends the pre-existing BUG-27 array-join loop with a typeof-boolean branch) as the single choke point every promoted HubSpot property patch passes through"
    - "Defence-in-depth: coercion at BOTH the wrapper-loop choke point (build_cloud_workflows.py) AND the JS module's own promote-branch assignment (mergeCompanies.js), so a candidate is correct at birth, not only correct downstream"

key-files:
  created:
    - tests/test_review_flag_eq_filter.py
  modified:
    - n8n/code/reviewApply.js
    - n8n/code/mergeCompanies.js
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_review_decision_cloud.json
    - n8n/wf_scheduled_maintenance_cloud.json
    - tests/test_cloud_companies_branch.py
    - tests/fixtures/companies_jscode_frozen.json
    - tests/n8n/reviewLoop.test.mjs
    - tests/n8n/reviewDecisionEndpoint.test.mjs
    - tests/n8n/mergeCompanies.test.mjs
    - tests/n8n/sponsorshipReliantCopyLoop.test.mjs

key-decisions:
  - "D-07's six-site inventory fixed exactly at the BROKEN rows (1-5); rows 6-8 verified unchanged and given a NEW regression test so a future edit to an already-fixed site fails here too, not silently"
  - "PIPE-02's min_confidence was read-and-left-alone (already 80, Phase 40 D-04) — only coercion was added, proven statically per D-10 with zero calls to mergeCompanies() in the test body"
  - "The mergeCompanies.js coercion applies to the ONE shared promote-branch assignment (canonicalPatch[field] = value), not a veto-only branch — it therefore also fixes live boolean promotions (lv_produces_content, lv_sponsorship_reliant) as a byproduct, which is why 2 node-test fixtures needed updating"

patterns-established:
  - "Anchored-grep/regex assertions on the assignment/key form (never a bare substring) are the standing idiom for proving a coercion fix landed and rejecting the broken form it replaced"

requirements-completed: [PIPE-01, PIPE-02]

coverage:
  - id: D1
    description: "Every BROKEN boolean-writer inventory row (1-5) emits the quoted string \"true\"/\"false\"; rows 6-8 verified still-correct"
    requirement: PIPE-01
    verification:
      - kind: unit
        ref: "tests/test_cloud_companies_branch.py::test_review_apply_clearpatch_boolean_keys_are_quoted_string_literals"
        status: pass
      - kind: unit
        ref: "tests/test_cloud_companies_branch.py::test_decide_company_action_needs_review_flag_assignment_is_a_quoted_string_literal"
        status: pass
      - kind: unit
        ref: "tests/test_cloud_companies_branch.py::test_bug27_finalization_loops_coerce_booleans_alongside_the_array_join"
        status: pass
      - kind: unit
        ref: "tests/test_cloud_companies_branch.py::test_inventory_rows_6_7_8_remain_already_correct"
        status: pass
    human_judgment: false
  - id: D2
    description: "The HubSpot EQ filter actually matches the corrected write (not just an offline grep) — resolves 43-RESEARCH.md Pitfall 5's write-behavior uncertainty"
    requirement: PIPE-01
    verification:
      - kind: integration
        ref: "tests/test_review_flag_eq_filter.py::test_corrected_string_patch_is_matched_by_the_awaiting_review_eq_filter (RUN_LIVE_PARITY=true, live HubSpot, executed by operator in 43-04)"
        status: unknown
    human_judgment: true
    rationale: "Requires live HUBSPOT_PRIVATE_APP_TOKEN credentials this session did not have (.env is Read/Bash permission-blocked); authored and offline-skip-verified here, execution deferred to 43-04 per the plan's explicit design"
  - id: D3
    description: "mergeCompanies.js's veto_output policy entries carry both a real min_confidence (verified, untouched) and boolean-string coercion at the promote branch, proven statically without driving the dead veto path"
    requirement: PIPE-02
    verification:
      - kind: unit
        ref: "tests/test_cloud_companies_branch.py::test_merge_companies_veto_policy_entries_carry_a_real_min_confidence"
        status: pass
      - kind: unit
        ref: "tests/test_cloud_companies_branch.py::test_merge_companies_promote_branch_coerces_boolean_candidates_statically"
        status: pass
      - kind: unit
        ref: "tests/test_cloud_companies_branch.py::test_company_canonical_patch_never_contains_a_derived_icp_output_field (dead-path proof, unmodified)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-07
status: complete
---

# Phase 43 Plan 01: Boolean Coercion & Veto Hardening Summary

**Closed PIPE-01 (6-site boolean-to-string coercion sweep across the review-queue write
path) and PIPE-02 (mergeCompanies.js promote-branch hardening) entirely offline —
regenerated all 8 n8n workflow JSONs from the builder, added 6 new anchored offline tests,
and authored a live-gated EQ-filter proof module ready for 43-04. No deploy performed.**

## Performance

- **Duration:** ~25 min (commit span; includes full-suite reruns after each task)
- **Started:** 2026-08-07T08:37:00Z (approx, session start)
- **Completed:** 2026-08-07T08:57:48+10:00 (last task commit)
- **Tasks:** 3
- **Files modified:** 13 (1 created, 12 modified) across the 3 task commits

## Accomplishments

- **Task 1 (tracer):** `reviewApply.js`'s `clearPatch` object's two boolean keys
  (`lv_enrichment_needs_review`, `lv_enrichment_review_approved`) now hold quoted string
  `"false"` instead of a bare JS boolean — the single shared fix site for both HubSpot
  PATCH consumers (`ENRICH_APPLY_REVIEW` / "Apply Review" and `buildReviewDecision`'s
  approve branch / "Build Review Decision"). Red-checked manually (see below).
- **Task 2:** The remaining 3 BROKEN inventory rows fixed at their two shared choke
  points: `ENRICH_DECIDE_CO_CLOUD`'s needs-review branch now emits `"true"`, and the
  pre-existing BUG-27 array-join loop in both `ENRICH_DECIDE_CO_CLOUD` (companies) and
  `ENRICH_DECIDE_CLOUD` (contacts) gained a second branch coercing any boolean-typed
  value to its quoted string form — closing the class for
  `lv_produces_content`/`lv_sponsorship_reliant`/`lv_is_hardware_vendor`/
  `lv_is_gambling_operator` with no per-field enumeration. New live-gated
  `tests/test_review_flag_eq_filter.py` authored (skips cleanly offline, zero network
  calls when `RUN_LIVE_PARITY` is unset).
- **Task 3:** `mergeCompanies.js`'s promote branch now coerces a boolean-typed candidate
  to its quoted string form at the moment of promotion — defence-in-depth alongside
  Task 2's wrapper-loop fix. `min_confidence` (already 80, Phase 40 D-04) was read and
  left alone; the dead-veto-path proof test stays byte-identical.
- All 8 `n8n/*.json` workflows regenerated via `scripts/build_cloud_workflows.py`
  (never hand-edited); regeneration confirmed idempotent (a final re-run produced zero
  diff).

## Task Commits

1. **Task 1: End-to-end slice — reviewApply clearPatch literals** — `f7edd13` (fix)
2. **Task 2: Coerce remaining broken write sites (needs-review branch + 2 finalization loops)** — `c85e2f1` (fix)
3. **Task 3: Harden mergeCompanies.js promote-branch coercion** — `fa4dbd9` (fix)

**Plan metadata:** committed as part of this SUMMARY (docs commit follows)

## Files Created/Modified

- `n8n/code/reviewApply.js` — `clearPatch`'s two boolean keys quoted (Task 1)
- `n8n/code/mergeCompanies.js` — promote-branch boolean coercion (Task 3); policy object (lines 34-70) untouched
- `scripts/build_cloud_workflows.py` — needs-review assignment quoted; boolean-coercion branch added to both properties-finalization loops (Task 2)
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local_live.json`, `n8n/wf_review_decision_cloud.json`, `n8n/wf_scheduled_maintenance_cloud.json` — regenerated (only files whose content actually changed; the other 4 of the 8 built files were rewritten byte-identical)
- `tests/test_cloud_companies_branch.py` — 6 new test functions; 2 pre-existing tests (min_confidence, dead-path proof) confirmed unmodified by diff
- `tests/test_review_flag_eq_filter.py` — new, live-gated, authored for 43-04
- `tests/fixtures/companies_jscode_frozen.json` — re-baselined (explicit, reviewed act, per its own header comment) to match Task 3's mergeCompanies.js edit
- `tests/n8n/reviewLoop.test.mjs`, `tests/n8n/reviewDecisionEndpoint.test.mjs`, `tests/n8n/mergeCompanies.test.mjs`, `tests/n8n/sponsorshipReliantCopyLoop.test.mjs` — updated fixtures that asserted the old bare-boolean shape (expected fallout of Tasks 1-3, not scope creep — see Deviations)

## Decisions Made

None beyond what 43-CONTEXT.md/43-RESEARCH.md already locked (D-07 through D-11). Where
this plan left the exact inventory ordering to Claude's discretion, it was executed
exactly as the plan's `<boolean_writer_inventory>` table specified, row by row.

## Boolean-Writer Inventory: Per-Row Outcome

| # | Site | Field(s) | Status before | Outcome |
|---|------|----------|----------------|---------|
| 1 | `reviewApply.js` clearPatch | `lv_enrichment_needs_review` | BROKEN | FIXED (Task 1) |
| 2 | `reviewApply.js` clearPatch | `lv_enrichment_review_approved` | BROKEN | FIXED (Task 1) |
| 3 | `ENRICH_DECIDE_CO_CLOUD` needs-review branch | `lv_enrichment_needs_review` | BROKEN | FIXED (Task 2) |
| 4 | `mergeCompanies()` candidate promotion, `ENRICH_DECIDE_CO_CLOUD` loop | `lv_produces_content`, `lv_sponsorship_reliant`, `lv_is_hardware_vendor`, `lv_is_gambling_operator` | BROKEN | FIXED (Task 2, loop) + FIXED (Task 3, promote-branch) |
| 5 | `ENRICH_DECIDE_CLOUD` loop (contacts, defensive parity) | same class | BROKEN | FIXED (Task 2) |
| 6 | `lv_anti_icp_flag`/`lv_anti_icp_reason` veto assignment | — | ALREADY FIXED (Phase 40 D-04) | VERIFIED unchanged, new regression test added |
| 7 | `ENRICH_DEDUPE_SWEEP` contacts writer | `lv_enrichment_needs_review` | ALREADY FIXED | VERIFIED unchanged, new regression test added |
| 8 | `DECIDE_CLOUD` create branch (36-07) | `lv_enrichment_requested` | ALREADY FIXED | VERIFIED unchanged, new regression test added |
| 9 | — | `lv_icp_needs_review` | NO PIPELINE WRITER | nothing to fix; HubSpot-native workflows own it (unchanged) |

## D-08 Red-Check Procedure (Task 1)

Reverted `n8n/code/reviewApply.js`'s `lv_enrichment_needs_review: "false"` back to its
bare-boolean form (`lv_enrichment_needs_review: false`), regenerated the workflows, and
ran `test_review_apply_clearpatch_boolean_keys_are_quoted_string_literals` —
**FAILED** as expected (`AssertionError: Apply Review in wf_scheduled_maintenance_cloud.json
missing the quoted-string clearPatch assignment for lv_enrichment_needs_review`). Restored
the fix, regenerated again, re-ran the full `tests/test_cloud_companies_branch.py` suite —
**19/19 passed**. The negative assertions in the test (`f'{field}: false,' not in code`)
are the permanent red-check going forward.

## mergeCompanies.js Policy-Object Confirmation (Task 3)

Read `DEFAULT_COMPANY_POLICY` (lines 34-70) and confirmed both `lv_anti_icp_flag` and
`lv_anti_icp_reason` already declare `min_confidence: 80` (Phase 40 D-04) — **not
touched**. `git diff --stat n8n/code/mergeCompanies.js` confirms the only change is the
promote-branch assignment (`canonicalPatch[field] = ...`) at line ~240, nine lines
inserted, one line changed, zero lines touched in the policy-object range. The existing
`test_merge_companies_veto_policy_entries_carry_a_real_min_confidence` and
`test_company_canonical_patch_never_contains_a_derived_icp_output_field` both pass, and
`git diff` on the latter's function body is empty (byte-identical, confirmed).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug/expected fallout] Updated 6 node-test fixtures that asserted the
pre-fix bare-boolean shape**
- **Found during:** Task 2 (`tests/n8n/reviewLoop.test.mjs`,
  `tests/n8n/reviewDecisionEndpoint.test.mjs` — 3 assertions) and Task 3
  (`tests/n8n/mergeCompanies.test.mjs`, `tests/n8n/sponsorshipReliantCopyLoop.test.mjs` —
  2 assertions)
- **Issue:** These tests directly call `reviewApply()`/`mergeCompanies()` and assert the
  exact shape of `clearPatch`/`canonicalPatch`. Fixing the boolean-coercion bugs these
  tasks target necessarily changes that shape (`false` → `"false"`, `true` → `"true"`) —
  not a bug in the fix, but an assertion written against the old (broken) behavior.
- **Fix:** Updated each assertion to expect the corrected quoted-string value; where the
  provenance blob's own `value` field carries the raw candidate type unaffected by the
  canonicalPatch-only coercion (Task 3), split the assertion to check both fields
  correctly (`tests/n8n/mergeCompanies.test.mjs`).
- **Files modified:** `tests/n8n/reviewLoop.test.mjs`,
  `tests/n8n/reviewDecisionEndpoint.test.mjs`, `tests/n8n/mergeCompanies.test.mjs`,
  `tests/n8n/sponsorshipReliantCopyLoop.test.mjs`
- **Verification:** `node --test tests/n8n/*.test.mjs` — 636 passed, 0 failed, after each
  fix; not in the plan's declared `<files>` lists for Tasks 2/3, but required to satisfy
  those tasks' own acceptance criteria ("`node --test` reports at least 636 passing, 0
  failing")
- **Committed in:** `c85e2f1` (Task 2), `fa4dbd9` (Task 3)

**2. [Rule 1 - Bug/expected fallout] Re-baselined `tests/fixtures/companies_jscode_frozen.json`**
- **Found during:** Task 3, after the full suite run surfaced 4 failures in
  `tests/test_companies_factory_frozen.py`
- **Issue:** That module's own header comment states the fixture is "re-baselined ONLY
  by an explicit, reviewed act — never as a routine 'make the test pass' step." Task 3's
  `mergeCompanies.js` edit changes the "Merge Company" node's inlined jsCode by design —
  this is exactly the explicit, reviewed act the fixture's own doctrine anticipates
  (mirrors the precedent set by Phase 40's commit `12a5827`, which re-baselined the same
  fixture for the same reason: a `mergeCompanies.js` policy edit).
- **Fix:** Regenerated the fixture from a fresh `build_enrichment_cloud()` /
  `build_enrichment_local_live()` call, extracting the same 7 frozen node names the test
  module itself extracts.
- **Files modified:** `tests/fixtures/companies_jscode_frozen.json`
- **Verification:** `tests/test_companies_factory_frozen.py` — 4/4 passed after
  re-baseline
- **Committed in:** `fa4dbd9` (Task 3)

---

**Total deviations:** 2 auto-fixed (both Rule 1, both direct, necessary consequences of
the coercion fixes this plan exists to make — no scope creep, no unplanned feature work).
**Impact on plan:** Both deviations were required to keep the full test suite green after
landing the plan's own intended changes; neither touches code outside what Tasks 2/3
already modified.

## Issues Encountered

None beyond the expected test-fixture fallout documented above.

## CRITICAL: Undeployed State — Deploy Deliberately NOT Performed

**This plan regenerated all 8 `n8n/*.json` files (repo-side changes only) and never ran
`scripts/deploy_n8n_workflows.py` or any live PUT against n8n Cloud.** Per this plan's
explicit constraints:

- **Phase 41's arm window may still be open** (66 real customer records, per STATE.md at
  session start) — deploying now would silently rebake write-safety constants to
  disarmed, closing that window mid-run without the operator's knowledge.
- **The repo's `n8n/*.json` now contains UNDEPLOYED Phase 43 changes** (the boolean
  coercion fixes above) while whatever Phase 41 arm state exists remains live in the
  actually-running n8n Cloud workflows. Any deploy performed before Phase 41 is
  confirmed disarmed would (a) push these unproven Phase 43 changes live for the first
  time, AND (b) close the Phase 41 arm window as a side effect of the same PUT.
- The post-regeneration arming grep (`grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"'
  n8n/*.json`) reads **0 for all 8 files**, confirming the regenerated JSON itself is
  disarmed-by-default, as always — this says nothing about what is currently live.
- **Deploy is out of scope for this plan by design** — it belongs to 43-05, gated behind
  explicit proof that Phase 41 has disarmed. No task in this plan touched
  `scripts/deploy_n8n_workflows.py`, and none should have.

## User Setup Required

None — no external service configuration required. `tests/test_review_flag_eq_filter.py`
requires live `HUBSPOT_PRIVATE_APP_TOKEN` credentials and `RUN_LIVE_PARITY=true` to
execute its 2 tests; this session had neither (`.env` is Read/Bash permission-blocked per
repo convention) and the module is designed to skip cleanly offline, which it does
(confirmed: 2 skipped, 0 network calls).

## Next Phase Readiness

- PIPE-01 and PIPE-02 are closed offline. `tests/test_review_flag_eq_filter.py` is
  authored and ready for the operator to run in 43-04 with live credentials
  (`RUN_LIVE_PARITY=true`) — this is the one still-open proof (D2 in the coverage table
  above): whether HubSpot's EQ filter actually matches the corrected write, not just
  whether the JS emits the right string offline.
- No deploy has occurred. 43-05 (or whichever plan owns the deploy step) must first
  confirm Phase 41's arm window is closed before running
  `scripts/deploy_n8n_workflows.py` against these regenerated workflows — see the
  CRITICAL section above.
- Full baselines confirmed at or above the plan's stated thresholds:
  `.venv/bin/python -m pytest -q` → 2397 passed, 122 skipped (baseline: 2392/≥2392);
  `node --test tests/n8n/*.test.mjs` → 636 passed, 0 failed (baseline: 636/0);
  `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` → 1286 passed, 5 skipped
  (baseline: 1286/≥1286); arming grep → 0 for all 8 files.

## Self-Check: PASSED

All 7 declared files confirmed present on disk; all 3 task commit hashes (`f7edd13`,
`c85e2f1`, `fa4dbd9`) confirmed present in `git log --oneline --all`.

---
*Phase: 43-pipeline-scoring-hygiene-explainability*
*Completed: 2026-08-07*
