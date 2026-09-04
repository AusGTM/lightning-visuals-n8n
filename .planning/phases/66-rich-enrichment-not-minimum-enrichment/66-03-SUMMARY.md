---
phase: 66-rich-enrichment-not-minimum-enrichment
plan: 03
subsystem: enrichment
tags: [n8n, report, hubspot, contacts-waterfall, operator-report]

requires:
  - phase: 66-01
    provides: "Contacts REQUIRED already widened to all 12 policy keys; the fetch-list non-clobber fix, so existingRecord genuinely reflects stored phone/email"
  - phase: 66-02
    provides: "Companies REQUIRED widened + the matrix discipline this plan's threat register borrows (derive, never hardcode)"
provides:
  - "A three-state per-row contactability marker (complete / email_only / none) stamped at Build Response, the one convergence point every enrichment terminal reaches"
  - "Decide Action (contacts, CLOUD) now carries existingRecord and merge forward by name — an additive fix to a pre-existing gap that would otherwise have made contactability uncomputable for the normal enrich/create path"
  - "operator-claude-plugin/scripts/report_enrichment.py: contactability surfaced per row (_build_row_report, serving both build_enrichment_report and build_sync_report) plus a batch-level contactability_counts tally with an explicit unknown bucket"
affects: []

actuals:
  tokens: 5100
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Carry-BY-NAME idiom reused a third time: existingRecord/merge added to Decide Action's explicit return object, mirroring the existing scored/material_conflicts/judge_confidence_by_field precedent (Phase 61 Plan 04 Task 1)"
    - "Post-run state = union(existingRecord, merge.canonicalPatch), read field-by-field via a small _postRunFieldValue helper, never the raw provider return"
    - "Absent-tolerant Python read of an optional backend field, modeled on _match_info_for_row's existing pattern: unrecognised or missing -> None, never inferred, never raised"

key-files:
  created: []
  modified:
    - scripts/build_cloud_workflows.py
    - tests/n8n/outcomeContractFlow.test.mjs
    - n8n/wf_enrichment_cloud.json
    - operator-claude-plugin/scripts/report_enrichment.py
    - operator-claude-plugin/tests/test_report_enrichment.py

key-decisions:
  - "D-66-05/D-66-06: three contact states — complete / email_only / none — plus an explicit absence value (null) for companies rows. Either phone field (phone or mobilephone) satisfies the phone half; ZoomInfo's directPhone/hasDirectPhone verified-dial fields are 400/unentitled on this account, so requiring a mobile specifically would make 'complete' largely unreachable."
  - "existingRecord/merge do not reach Build Response through Decide Action's own return object today (its explicit field list drops both) — traced by reading the real jsCode rather than assuming the plan's key_links were already wired. Fixed by carrying them forward additively, the same idiom already used for scored/material_conflicts/judge_confidence_by_field, rather than computing the marker earlier (which would have violated 'computed at the one convergence point, never duplicated per-terminal')."
  - "OUTCOME_CONTRACT_VERSION stays at 2 — preingest.py refuses any unknown version outright and the installed marketplace clone does not self-refresh, so a bump would refuse every row rather than degrade an additive key."
  - "Python-side contactability read is structurally None for every row build_enrichment_report reads (the executions-API ledger reads Decide Action/Decide Company Action, a node BEFORE Build Response computes the marker) — this is by construction, not staleness, and the absent-tolerant read handles it identically to an unrefreshed deployment. Documented rather than 'fixed' — extending enrichment_row_ledger to read Build Response instead is out of this plan's scope and not requested by D-66-06."
  - "The batch tally (contactability_counts) is added only to build_enrichment_report's return dict, not to build_sync_report's return shape — build_sync_report returns (rows, reason), never 'the report object' the plan's artifacts table and acceptance criteria name."
  - "contactability_fields (which field satisfied each half) is stamped in the n8n response body but deliberately NOT surfaced as a second Python report key — the plan's Task 2 action names exactly one key to add to _build_row_report, and nothing downstream needs the sub-object today."

patterns-established: []

requirements-completed: [RICH-01]

coverage:
  - id: D1
    description: "A contacts row whose post-run state (existingRecord union merge.canonicalPatch) carries both an email and a phone field stamps 'complete'; email with phone fields blank stamps 'email_only'; neither stamps 'none'; a value promoted THIS run (blank-to-filled) counts identically to one already stored."
    requirement: "RICH-01"
    verification:
      - kind: unit
        ref: "tests/n8n/outcomeContractFlow.test.mjs#D-66-06: a contacts row whose post-run state carries an email AND a phone stamps the complete state"
        status: pass
      - kind: unit
        ref: "tests/n8n/outcomeContractFlow.test.mjs#D-66-06: post-run state is the union of existingRecord and this run's promoted patch — a blank email promoted THIS run reads as complete"
        status: pass
      - kind: unit
        ref: "tests/n8n/outcomeContractFlow.test.mjs#D-66-06: a row with neither email nor phone stamps a third, distinct state"
        status: pass
    human_judgment: false
  - id: D2
    description: "Either phone field (phone or mobilephone) satisfies the phone half of the completeness marker — a landline alone counts, a mobile alone counts."
    requirement: "RICH-01"
    verification:
      - kind: unit
        ref: "tests/n8n/outcomeContractFlow.test.mjs#D-66-06: either phone field satisfies the phone half — a landline alone counts"
        status: pass
    human_judgment: false
  - id: D3
    description: "A companies row stamps the absence value explicitly (null), never a missing key, at both the n8n response layer and the Python report layer. The batch tally counts contacts rows only and never folds an unstamped row into complete or email_only."
    requirement: "RICH-01"
    verification:
      - kind: unit
        ref: "tests/n8n/outcomeContractFlow.test.mjs#D-66-06: a companies row stamps the absence value explicitly, never a missing key"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_report_enrichment.py#test_build_enrichment_report_contactability_counts_bucket_stamped_rows_correctly"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_report_enrichment.py#test_build_enrichment_report_contactability_counts_unstamped_fixture_rows_are_unknown"
        status: pass
    human_judgment: false
  - id: D4
    description: "OUTCOME_CONTRACT_VERSION is unchanged, pinned by an assertion so a later accidental bump fails the suite here; the client parser (preingest.py) and every plugin skill are untouched by this plan."
    requirement: "RICH-01"
    verification:
      - kind: unit
        ref: "tests/n8n/outcomeContractFlow.test.mjs#D-66-06: outcome_contract_version is UNCHANGED by this task — a later accidental bump fails here"
        status: pass
      - kind: other
        ref: "git diff --exit-code -- operator-claude-plugin/scripts/preingest.py operator-claude-plugin/skills/ config/field_policy.yaml n8n/code/mergeContacts.js scripts/ (n8n/ subset excluded)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Nothing anywhere branches, holds, filters, refuses, prompts or reorders on the new value — it is stamped and rendered only."
    requirement: "RICH-01"
    verification: []
    human_judgment: true
    rationale: "A negative claim (absence of any consuming branch) is not something a single test can positively prove; verified by direct code review of every edit site plus the explicit no-branching comments left at both the n8n emission site and the Python render site, and by confirming no gate/skill/hold file changed in this plan's diff."

duration: 40min
completed: 2026-09-04
status: complete
---

# Phase 66 Plan 03: Phone+email completeness, visible in the report Summary

**Stamped a three-state (complete / email_only / none) contactability marker at the enrichment backend's single response convergence point, computed from the record's post-run state, and rendered it per row plus as a batch tally in the operator's report — flagged only, never a gate.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-09-04T07:35:00Z
- **Completed:** 2026-09-04T08:16:06Z
- **Tasks:** 2
- **Files modified:** 5 (2 test files extended, 2 source files edited, 1 regenerated n8n workflow)

## Accomplishments
- `Build Response` (`ENRICH_BUILD_RESPONSE` in `scripts/build_cloud_workflows.py`) now stamps `contactability` (`"complete"` / `"email_only"` / `"none"`, or explicit `null` for a companies row) and a small `contactability_fields` object naming which field satisfied each half — computed from the POST-RUN state (`existingRecord` union `merge.canonicalPatch`), never the raw provider return, so a value this run promoted counts identically to one already on file.
- Traced the real jsCode rather than assuming the plan's stated inputs already reached `Build Response`: `Decide Action` (contacts, CLOUD variant) previously dropped `existingRecord`/`merge` from its own explicit return object, which would have made the marker uncomputable for the ordinary enrich/create path. Fixed by carrying both forward additively, the same "carry BY NAME" idiom already established for `scored`/`material_conflicts`/`judge_confidence_by_field`.
- Either phone field (`phone` or `mobilephone`) satisfies the phone half — the account has no entitlement to ZoomInfo's verified-direct-dial fields (`directPhone`/`hasDirectPhone`, 400 on this account), so the achievable ceiling is a landline plus a mobile, and requiring a mobile specifically would make "complete" largely unreachable (D-66-05).
- `operator-claude-plugin/scripts/report_enrichment.py`'s `_build_row_report` surfaces the same value per row — one edit serving both `build_enrichment_report` (executions-API path) and `build_sync_report` (synchronous webhook-body path) — read defensively, mirroring `_match_info_for_row`'s existing absent-tolerant pattern.
- `build_enrichment_report` gains a `contactability_counts` batch tally, contacts rows only, with an explicit `unknown` bucket for any row the backend did not stamp.
- `OUTCOME_CONTRACT_VERSION` stays at 2, pinned by an assertion.

## Task Commits

Each task was committed atomically:

1. **Task 1: Stamp per-row contactability at the backend's single response convergence point** - `5acdbe5` (feat)
2. **Task 2: Render completeness in the operator's report — per row and as a batch count** - `7a4a57e` (feat)

**Plan metadata:** committed separately below.

## Files Created/Modified
- `scripts/build_cloud_workflows.py` - `ENRICH_BUILD_RESPONSE` gains `_contactability()` + the three-state constants + the `_postRunFieldValue` helper and the two new response keys; `ENRICH_DECIDE_CLOUD` (contacts `Decide Action`) additively carries `existingRecord`/`merge` forward
- `tests/n8n/outcomeContractFlow.test.mjs` - 7 new tests exercising the real regenerated jsCode end to end (complete / email_only / none / either-phone-field / post-run-union / companies-absence / version-pinned)
- `n8n/wf_enrichment_cloud.json` - regenerated via `scripts/build_cloud_workflows.py`, never hand-edited; only the `Decide Action` and `Build Response` nodes' `jsCode` changed; node count unchanged at 123. The other 7 `n8n/wf_*.json` files regenerate byte-identical — none of them use these two node builders.
- `operator-claude-plugin/scripts/report_enrichment.py` - `_contactability_for_row` (absent-tolerant read), `_empty_contactability_counts`, `contactability` key on `_build_row_report`'s returned dict, `contactability_counts` on `build_enrichment_report`'s returned dict (both the malformed-input early-return and the normal path)
- `operator-claude-plugin/tests/test_report_enrichment.py` - 7 new tests: per-row surfacing, absent/unrecognised-value handling, `build_sync_report` carrying a stamped value, two `contactability_counts` bucketing tests (unstamped-fixture and synthetic-stamped), and a malformed-input never-raises test

## Decisions Made
- Both key decisions and the coverage/deviation details are recorded in the frontmatter's `key-decisions` above — the single biggest one being that `existingRecord`/`merge` did NOT already reach `Build Response` (contrary to what the plan's `key_links` implied) and needed an additive carry-forward fix in `Decide Action` itself, discovered by reading the actual committed jsCode rather than trusting the plan's framing.
- `contactability_fields` (which field satisfied each half) is emitted in the n8n response body per the plan's action text, but deliberately not surfaced as a second Python report key — Task 2's action names exactly one key to add to `_build_row_report`, and nothing downstream needs the sub-object yet.
- The Python-side executions-API path (`build_enrichment_report`) will always read `contactability` as `None` for every row, by construction (`enrichment_row_ledger` reads `Decide Action`/`Decide Company Action`, a node earlier in the graph than `Build Response`), not because of any deployment staleness. Documented in code comments rather than "fixed" — widening `enrichment_row_ledger` to also read `Build Response` is out of this plan's scope.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `Decide Action` (contacts) silently dropped `existingRecord`/`merge` before `Build Response` could ever read them**
- **Found during:** Task 1, while tracing whether the plan's stated `row.existingRecord`/`row.merge.canonicalPatch` inputs were genuinely reachable at `Build Response`.
- **Issue:** `ENRICH_DECIDE_CLOUD`'s explicit return object (an enumerated field list, not a spread) omitted both `existingRecord` and `merge`. Any row that passed through the normal contacts enrich/create path (the overwhelming majority of rows) would have reached `Build Response` with both fields missing, making the completeness marker permanently `"none"` for those rows — a false negative, not an honest unknown.
- **Fix:** Added `existingRecord: row.existingRecord ?? null` and `merge: row.merge ?? null` to `ENRICH_DECIDE_CLOUD`'s return object, following the same carry-BY-NAME idiom already used for `scored`/`material_conflicts`/`judge_confidence_by_field` (with an inline comment explaining why `properties` alone is insufficient).
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Verification:** `tests/n8n/outcomeContractFlow.test.mjs`'s new tests drive the row through the REAL `runDecideAction` → `runBuildResponse` chain (the same pattern the pre-existing tests in that file already use), so the fix is proven end to end, not just at `Build Response` in isolation.
- **Committed in:** `5acdbe5` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — Rule 1). **Impact on plan:** Necessary for the plan's own stated behavior to hold true on the real code path; no scope creep — the fix is additive, touches no gate, no policy file, and no merge module.

## Issues Encountered
None beyond the deviation above, which was caught and fixed within Task 1 before any test was allowed to go green.

## User Setup Required
None - no external service configuration required. Nothing is armed and nothing is deployed to n8n Cloud (CLAUDE.md §13.0.2's undeployed delta grows further, deliberately — this plan adds a fifth regenerate-and-commit-without-deploy round on top of the ones already recorded there).

## Next Phase Readiness
- Final `node --test tests/n8n/*.test.mjs`: **938 pass / 0 fail** (baseline 931 + 7 new tests, all in `outcomeContractFlow.test.mjs`).
- Final `cd operator-claude-plugin && ../.venv/bin/python -m pytest tests/ -q`: **2489 passed / 5 skipped** (baseline + 7 new tests).
- Final repo-root `.venv/bin/python -m pytest -x -q`: **4247 passed / 154 skipped** (baseline 4240 + 7).
- `n8n/wf_enrichment_cloud.json` node count unchanged at 123.
- `config/field_policy.yaml`, `n8n/code/mergeContacts.js`, `operator-claude-plugin/scripts/preingest.py`, and every file under `operator-claude-plugin/skills/` are byte-unchanged (`git diff --exit-code` clean on all).
- Phase 66 is now feature-complete across all three plans (66-01: contacts chase + LinkedIn producer; 66-02: companies gate widened from the derived matrix; 66-03: phone+email completeness visible in the report). No blockers for phase closure.

---
*Phase: 66-rich-enrichment-not-minimum-enrichment*
*Completed: 2026-09-04*

## Self-Check: PASSED

All claimed files found on disk; both task commit hashes (`5acdbe5`, `7a4a57e`) found in git log.
