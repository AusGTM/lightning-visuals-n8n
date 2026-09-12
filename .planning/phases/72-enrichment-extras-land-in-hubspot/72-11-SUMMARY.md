---
phase: 72-enrichment-extras-land-in-hubspot
plan: 11
subsystem: n8n-enrichment
tags: [n8n, enrichment, mergeContacts, mergeCompanies, overflow-slot, non-clobber, gap-closure, tracer]

requires:
  - phase: 72-enrichment-extras-land-in-hubspot
    provides: plan 05/06's overflow-slot routing (lv_phone_2/lv_mobilephone_2) and 72-VERIFICATION.md's gap 3 / 72-REVIEW.md's WR-02, which diagnosed this exact case-sensitivity defect
provides:
  - "case-insensitive overflow dedup key in mergeContacts.js and mergeCompanies.js, matching src/merge_policy.py's route_overflow and both files' own has_conflict() convention"
  - "a mixed-case agreeing-candidates fixture pinned in both JS suites and the Python oracle, so the divergence cannot silently return"
  - "a reviewed, node-scoped re-baseline of the frozen companies jsCode fixture"
affects: []

actuals:
  tokens: 1526
  tasks: 3
  commits: 3
plan_head_before: 08ccc3b7f1e30d98dbfff4c3e59b0015cdaabeb7

tech-stack:
  added: []
  patterns:
    - "overflow-slot dedup key folds case on both sides (String(...).toLowerCase()) before comparison, mirroring the pre-existing has_conflict() convention across all three merge engines"

key-files:
  created: []
  modified:
    - n8n/code/mergeContacts.js
    - n8n/code/mergeCompanies.js
    - tests/n8n/overflowSlots.test.mjs
    - tests/test_merge_policy.py
    - tests/fixtures/companies_jscode_frozen.json
    - n8n/wf_contact_ingest_cloud.json
    - n8n/wf_contact_ingest_local.json
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_review_decision_cloud.json
    - n8n/wf_scheduled_maintenance_cloud.json

key-decisions:
  - "Case-INSENSITIVE was chosen as the parity direction (not moving Python to case-sensitive), because it is what src/merge_policy.py already does, what has_conflict() already does in all three engines, and correct on the merits: this dedup is generic over emails/URLs (case-insensitive in practice) and phone values (already digits-only post-normalization, unaffected either way)."
  - "src/merge_policy.py received no code edit — it was verified conformant (route_overflow already lower-cases both sides) and that verification is recorded in the Task 2 commit body, per the Phase 46 'one commit, three engines' rule, rather than silently assumed unchanged."
  - "The frozen companies jsCode fixture was re-baselined only after diffing old vs new and confirming 'Merge Company' was the only frozen node that changed, and that every changed line was the dedup-loop code or its comment — the explicit reviewed act tests/test_companies_factory_frozen.py's header requires."

requirements-completed: [D-72-09, D-72-11, D-72-12]

coverage:
  - id: D1
    description: "Two candidates whose normalized values differ only in case collapse to ONE candidate in mergeContacts.js, mergeCompanies.js, and src/merge_policy.py — no phantom overflow slot (lv_phone_2) is manufactured by any of the three engines."
    requirement: "D-72-09"
    verification:
      - kind: unit
        ref: "tests/n8n/overflowSlots.test.mjs#mergeContacts overflow: mixed-case agreeing candidates on phone do not manufacture lv_phone_2 (WR-02)"
        status: pass
      - kind: unit
        ref: "tests/n8n/overflowSlots.test.mjs#mergeCompanies overflow: mixed-case agreeing candidates on phone do not manufacture lv_phone_2 (WR-02)"
        status: pass
      - kind: unit
        ref: "tests/test_merge_policy.py#test_route_overflow_mixed_case_agreeing_candidates_do_not_manufacture_an_overflow"
        status: pass
    human_judgment: false
  - id: D2
    description: "The seven workflows that inline mergeContacts.js/mergeCompanies.js are regenerated with the fix and are idempotent; wf_backend_status_cloud.json (inlines no merge engine) is unchanged; all node counts are unchanged."
    requirement: "D-72-11"
    verification:
      - kind: unit
        ref: "scripts/build_cloud_workflows.py regeneration + git status --porcelain n8n/ (manual command, logged below)"
        status: pass
    human_judgment: false
  - id: D3
    description: "The frozen companies jsCode byte-identity guard is re-baselined against the corrected engine, with a recorded diff review proving the delta is scoped to the dedup loop and its comment in the 'Merge Company' node only."
    requirement: "D-72-12"
    verification:
      - kind: unit
        ref: "tests/test_companies_factory_frozen.py (4 tests)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-09-13
status: complete
---

# Phase 72 Plan 11: Case-insensitive overflow dedup across all three merge engines Summary

**Fixed a case-sensitivity divergence (WR-02) where mergeContacts.js and mergeCompanies.js manufactured a phantom `lv_phone_2` overflow write for two providers agreeing on a phone value that differed only in case, while the Python oracle already treated them as one candidate.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 3
- **Files modified:** 12 (2 engine files, 2 test files, 1 frozen fixture, 7 regenerated workflows)

## Accomplishments
- Reproduced WR-02 offline with a mixed-case agreeing-candidates fixture in both JS suites (RED) and confirmed the Python oracle was already case-insensitive via a parity pin (GREEN from the start)
- Folded case in both JS engines' overflow dedup key and its comparison predicate, kept the two loops byte-identical to each other, and confirmed `src/merge_policy.py` needed no edit
- Regenerated exactly the seven workflows that inline these modules, with all node counts unchanged and `wf_backend_status_cloud.json` untouched
- Re-baselined the frozen companies jsCode fixture as an explicit reviewed act, confirming only the `Merge Company` node changed and only on the dedup-loop lines

## Task Commits

1. **Task 1: RED — a mixed-case agreeing-candidates fixture in both suites** - `c0e90ddb` (test)
2. **Task 2: case-insensitive overflow dedup in both JS engines, one commit with the oracle** - `e2ea2653` (fix)
3. **Task 3: re-baseline the frozen companies jsCode fixture as an explicit, reviewed act** - `6e1442e8` (test)

## Files Created/Modified
- `n8n/code/mergeContacts.js` - overflow dedup key/predicate now `.toLowerCase()`'d on both sides; comment updated to name the convention
- `n8n/code/mergeCompanies.js` - identical fix, kept byte-identical to mergeContacts.js's loop
- `tests/n8n/overflowSlots.test.mjs` - two new mixed-case agreeing-candidates cases (one per JS engine)
- `tests/test_merge_policy.py` - one new parity-pin test asserting the Python oracle was already case-insensitive
- `tests/fixtures/companies_jscode_frozen.json` - re-baselined `Merge Company` entries for both `cloud` and `local_live` variants
- `n8n/wf_contact_ingest_cloud.json`, `n8n/wf_contact_ingest_local.json`, `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local.json`, `n8n/wf_enrichment_local_live.json`, `n8n/wf_review_decision_cloud.json`, `n8n/wf_scheduled_maintenance_cloud.json` - regenerated via `scripts/build_cloud_workflows.py` to inline the fixed modules; node counts unchanged (78/13/287/10/82/55/43)

## Decisions Made
- Case-insensitive is the correct parity direction (see key-decisions above) — Python was not touched, both JS engines moved to match it.
- The frozen fixture re-baseline was preceded by a full diff of old vs new fixture content, confirming the blast radius was exactly the one node and exactly the dedup-loop lines, before accepting the new fixture — this satisfies the test file's "reviewed act" requirement rather than a routine regeneration.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

The first two `git commit -m "$(cat <<'EOF' ... EOF)"` invocations failed with a bash heredoc/quoting syntax error (unrelated to file content — no problematic characters were present). Worked around by writing the commit message to a scratch file and using `git commit -F <file>` for all three task commits. No impact on task content or verification.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Gap G3 (D-72-09) from 72-VERIFICATION.md and review finding WR-02 are closed. All three gap-closure plans for this phase (G1/72-09, G2/72-10, G3/72-11) are now complete. Ready for phase-level re-verification / seal.

---
*Phase: 72-enrichment-extras-land-in-hubspot*
*Completed: 2026-09-13*
