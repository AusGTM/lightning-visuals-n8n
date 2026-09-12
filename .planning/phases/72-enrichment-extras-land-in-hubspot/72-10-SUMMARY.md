---
phase: 72-enrichment-extras-land-in-hubspot
plan: 10
subsystem: n8n-enrichment
tags: [n8n, enrichment, mergeContacts, mergeCompanies, non-clobber, gap-closure, tdd, tracer]

requires:
  - phase: 72-enrichment-extras-land-in-hubspot
    provides: plan 05/06's widened ENRICH_MERGE/ENRICH_MERGE_CO overflow candidates (lv_phone_2/lv_mobilephone_2, state/hs_state_code/phone) and 72-VERIFICATION.md's gap 2 / 72-REVIEW.md's CR-01, which diagnosed this exact defect
provides:
  - "HS_SEARCH_BODY_EXPR and HS_CO_SEARCH_BODY_EXPR widened to match their cloud siblings' non-clobber-critical fetch lists, so the local-live lane's existingRecord carries every protect_if_current_present field the shared merge engine can candidate"
  - "a derived non-clobber fetch-gate assertion in fieldProducerMatrix.test.mjs, scoped by protect_if_current_present rather than REQUIRED, covering NEVER_CHASE and overflow-slot fields no earlier assertion could reach"
affects: [72-12]

actuals:
  tokens: 3200
  tasks: 2
  commits: 2
plan_head_before: 94f08ce3a8f4118efba710cf0a749fdc0117e1d1

tech-stack:
  added: []
  patterns:
    - "a merge-lane fetch-gate assertion derived from field_policy.yaml's protect_if_current_present flag (not REQUIRED), discovered via a call-site shorthand + module-inlined predicate rather than a hardcoded node/file name"

key-files:
  created: []
  modified:
    - tests/n8n/fieldProducerMatrix.test.mjs
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_local_live.json

key-decisions:
  - "Node selection for the new assertion requires BOTH the ENRICH_MERGE/ENRICH_MERGE_CO wrapper's call-site shorthand (`rankedByField }` / `rankedByField,`) AND one of the two merge modules being inlined verbatim (`function mergeContacts` / `function mergeCompanies`) — not the shorthand alone. A Phase 72 Plan 06 comment on the unrelated \"Normalize + Score Company\" node (\"...opts.rankedByField, exactly like...\") contains the same literal substring without being a merge call site; without the module-inlined check it would be misclassified as a sixth/seventh selected node with no merge module to assign a lane. This resolves the plan's stated '(verified) exactly five nodes' claim, which the shorthand-alone reading does not reproduce (it selects seven)."
  - "protect_if_current_present: true is the correct derived candidate set for the new assertion, not promote_to_canonical or REQUIRED — it is the only flag that covers both NEVER_CHASE write-map-only fields and the promote_to_canonical:false overflow slots (lv_phone_2/lv_mobilephone_2), which is exactly what CR-01 found un-fetched."
  - "REQUIRED lists are left untouched on both widened constants — the added fields stay write-map-only by design (NEVER_CHASE), so a scheduled tick never marks a record incomplete and buys provider credits chasing a state code or overflow phone number no provider is asked to return."

requirements-completed: [D-72-01, D-72-06]

coverage:
  - id: D1
    description: "A derived test proves, offline, that CR-01's defect class (a protect_if_current_present field un-fetched on an overflow-capable merge lane) is caught for every such lane across every generated n8n/wf_*.json file — not hardcoded to the two fields CR-01 happened to find."
    requirement: "D-72-01"
    verification:
      - kind: unit
        ref: "tests/n8n/fieldProducerMatrix.test.mjs#non-clobber fetch gate (CR-01): every protect_if_current_present field is fetched, on every overflow-capable shared merge lane"
        status: pass
    human_judgment: false
  - id: D2
    description: "wf_enrichment_local_live.json's contacts and companies merge lanes fetch every protect_if_current_present field their shared merge engine (ENRICH_MERGE/ENRICH_MERGE_CO) can candidate — lv_phone_2/lv_mobilephone_2 (contacts) and lv_phone_2/state/hs_state_code/phone (companies) — closing the exact gap G2 named."
    requirement: "D-72-06"
    verification:
      - kind: unit
        ref: "tests/n8n/fieldProducerMatrix.test.mjs#non-clobber fetch gate (CR-01) — GREEN after Task 2, was RED after Task 1"
        status: pass
      - kind: integration
        ref: "node --test tests/n8n/*.test.mjs (1168/1168, full suite)"
        status: pass
      - kind: integration
        ref: ".venv/bin/python -m pytest tests/ operator-claude-plugin/tests/ (4947 passed, 154 skipped, unchanged from baseline)"
        status: pass
    human_judgment: false
  - id: D3
    description: "No cloud workflow JSON changed in this plan — regeneration touched only n8n/wf_enrichment_local_live.json, and its node count stayed 82."
    verification:
      - kind: unit
        ref: "git status --porcelain n8n/ after regeneration lists only n8n/wf_enrichment_local_live.json"
        status: pass
      - kind: unit
        ref: "json.load(...)['nodes'] length == 82"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-09-13
status: complete
---

# Phase 72 Plan 10: Local-live merge lanes fetch every non-clobber-critical overflow field (G2/CR-01) Summary

**`HS_SEARCH_BODY_EXPR`/`HS_CO_SEARCH_BODY_EXPR` widened to mirror their cloud siblings' non-clobber fetch lists, closing the local-live lane's silent-overwrite gap on `lv_phone_2`/`lv_mobilephone_2`/`state`/`hs_state_code`/`phone`, proven by a new derived `protect_if_current_present`-scoped fetch-gate assertion that goes RED on CR-01's exact defect and GREEN after the fix.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-09-13T04:12:00Z
- **Completed:** 2026-09-13T04:37:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added a new derived assertion to `tests/n8n/fieldProducerMatrix.test.mjs` that checks every `protect_if_current_present: true` field (not just `REQUIRED` members, which Assertions 2/2b already covered) is fetched by every overflow-capable `ENRICH_MERGE`/`ENRICH_MERGE_CO` merge lane, across every generated `n8n/wf_*.json` file — no hardcoded field, node, or file name.
- Confirmed RED exactly as CR-01 predicted: `wf_enrichment_local_live.json:Merge Winners (contacts)` missing `lv_phone_2, lv_mobilephone_2`; `wf_enrichment_local_live.json:Merge Company (companies)` missing `state, hs_state_code, phone, lv_phone_2`. Zero violations on `wf_enrichment_cloud.json`.
- Widened `HS_SEARCH_BODY_EXPR` (contacts) and `HS_CO_SEARCH_BODY_EXPR` (companies) in `scripts/build_cloud_workflows.py` to mirror exactly what Phase 72 Plans 05/06 already did to their cloud siblings (`ENRICH_CONTACT_SEARCH_PROPERTIES_CSV`/`ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`), with comments naming the gap-closure plan and the consequence of omission.
- Regenerated `n8n/wf_enrichment_local_live.json` — only that file changed, node count unchanged at 82.
- Full regression confirmed: `node --test tests/n8n/*.test.mjs` (1168/1168, up from 1167 baseline — the one new assertion) and `.venv/bin/python -m pytest tests/ operator-claude-plugin/tests/` (4947 passed, 154 skipped, unchanged from baseline).

## Task Commits

1. **Task 1: RED — a derived fetch-gate assertion for every non-clobber-critical field on every overflow-capable merge lane** - `436dd445` (test)
2. **Task 2: widen both local-live fetch constants to their cloud siblings' non-clobber-critical set** - `455b0173` (fix)

_This plan carries no separate plan-metadata commit for the tracer's RED task — the tracer feedback gate ran between the two task commits (both `<verify>` blocks re-confirmed, matching the plan's exact predicted RED shape) and required no additional commit of its own._

## Files Created/Modified
- `tests/n8n/fieldProducerMatrix.test.mjs` — extended `yamlFieldBlock` with `protect_if_current_present`, added the new "non-clobber fetch gate (CR-01)" assertion and its `findOverflowMergeNodes`/`laneOfMergeNode`/`searchNodesForLane`/`protectedFieldsByLane` helpers
- `scripts/build_cloud_workflows.py` — widened `HS_SEARCH_BODY_EXPR` and `HS_CO_SEARCH_BODY_EXPR` with the six fields CR-01 named, plus explanatory comments
- `n8n/wf_enrichment_local_live.json` — regenerated (two search nodes' `properties` array only; node count unchanged at 82)

## Decisions Made
See `key-decisions` in frontmatter. The load-bearing one: the new assertion's node-selection predicate requires the ENRICH_MERGE/ENRICH_MERGE_CO wrapper's call-site shorthand (`rankedByField }` / `rankedByField,`) **AND** one of the two merge modules inlined verbatim, not the shorthand text alone — a Phase 72 Plan 06 comment on an unrelated node ("Normalize + Score Company") happens to contain the identical shorthand substring in prose, and would otherwise be misclassified as a sixth/seventh selected node with no merge module to assign a lane to.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in plan narrative, not in code] The plan's node-selection description under-specified the predicate needed to reach "exactly five nodes"**
- **Found during:** Task 1 (writing the RED assertion)
- **Issue:** The plan's `<action>` text described node selection as "every node ... whose `parameters.jsCode` contains the WRAPPER'S CALL-SITE SHORTHAND ... i.e. the literal `rankedByField }` or `rankedByField,`" and separately, as a distinct step, "Lane per node: whichever module is inlined ... Under the shorthand predicate exactly one of the two is present in every selected node (verified)." Testing the shorthand-alone predicate against the current repo (post-72-06) selects **seven** nodes, not five: in addition to the five genuine `ENRICH_MERGE`/`ENRICH_MERGE_CO` call sites, `wf_enrichment_cloud.json:Normalize + Score Company` and `wf_enrichment_local_live.json:Normalize + Score Company` are also selected, because both carry a Phase 72 Plan 06 comment — `// ... via mergeCompanies()'s\n  // opts.rankedByField.` and `// ... admitted below via opts.rankedByField, which` — whose text contains the literal substring `rankedByField,` without being a merge call site at all. Neither node inlines `function mergeContacts` or `function mergeCompanies`, so asserting "exactly one of the two present" on them (as the plan's lane-classification step directs) would fail with `lanes.length === 0`, not report a clean "protected but not fetched" violation, breaking the RED shape the acceptance criteria require.
- **Fix:** Made the module-inlined check part of the SAME selection predicate (an `&&`, not a separate downstream classification step run after selection): a node is in scope only when it BOTH carries the shorthand text AND inlines one of the two merge modules verbatim. This reproduces the plan's own "(verified) exactly five nodes" claim precisely (confirmed empirically: exactly `Merge Winners` x3 — `wf_enrichment_cloud.json`, `wf_enrichment_local_live.json`, `wf_enrichment_local.json` — and `Merge Company` x2 — `wf_enrichment_cloud.json`, `wf_enrichment_local_live.json`), and the subsequent "assert exactly one lane" check then holds trivially true for every selected node, exactly as the plan describes it should.
- **Files modified:** `tests/n8n/fieldProducerMatrix.test.mjs` (the combined predicate is in `findOverflowMergeNodes`, not a separate step).
- **Verification:** Confirmed via a standalone script (not committed) that the combined predicate selects exactly the 5 expected `{file, node, lane}` triples before writing the final assertion; the committed test's RED output then matched the plan's acceptance criteria byte-for-byte on first run.
- **Committed in:** `436dd445` (the RED task commit already reflects the fix — no separate correction commit needed since this was caught before writing the assertion, not after).
- **Not escalated to a checkpoint:** the fix is a mechanical tightening of an already-specified predicate (add the module-inlined condition the plan's own "lane per node" step already names, as a filter rather than a post-hoc assertion) — no architectural fork, no scope change, and the resulting behavior matches every acceptance criterion the plan specifies (RED message text, excluded files, `noFetchNode` exception) exactly.

---

**Total deviations:** 1 auto-resolved (Rule 1 — plan-narrative under-specification, corrected during Task 1 before any assertion was committed; no functional ambiguity in the final result).
**Impact on plan:** None on scope, fields widened, or files touched. Only the internal node-selection mechanics of the new test differ from a literal reading of the plan's two-step description, and the result reproduces the plan's own stated expectation exactly.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- G2 is closed offline: both local-live merge lanes now fetch every `protect_if_current_present` field their shared merge engine can candidate, and a derived guard (not a hardcoded pin) would catch a recurrence for any future overflow-capable field on any future lane.
- **Not closed live.** This plan deployed nothing and armed nothing, per its own instructions (`n8n/wf_enrichment_local_live.json` is the docker-replica lane; `scripts/deploy_n8n_workflows.py` globs `wf_*_cloud.json` only, so this file is never pushed by that script regardless). No cloud workflow JSON changed in this plan.
- 72-VERIFICATION.md's gap 2 / 72-REVIEW.md's CR-01 is resolved by this plan's code and test changes; per this plan's `affects:` field, 72-12 is where any consolidated live read-back across all of Phase 72's gap-closure plans (G1/G2/G3) should be confirmed.

---
*Phase: 72-enrichment-extras-land-in-hubspot*
*Completed: 2026-09-13*

## Self-Check: PASSED
