---
phase: 21-transport-schema-hygiene
plan: 01
subsystem: infra
tags: [n8n, hubspot, dedupe, transport-migration, httpRequest, workflow-hygiene]

# Dependency graph
requires:
  - phase: 17-bug23-contact-create-reachable
    provides: "_hs_http_search_node (the credential-bound httpRequest search transport)
      and the BUG-10/22/23 migration pattern this plan finishes applying"
provides:
  - "Dedupe Search (candidate contacts) on the credential-bound httpRequest envelope —
    zero-hit results now yield an empty-results envelope instead of silently stopping
    the chain"
  - "The native-search node builder deleted outright, with zero textual residue of its
    identifier anywhere in the repo"
  - "A zero-native-search-operation predicate (parametrized over every cloud workflow)
    and a dedupe-lane classify-only predicate (exactly one write node, explicit
    property-key allowlist)"
  - "scripts/verify_live_no_native_search.py — read-only live read-back verifier"
  - "Live confirmation: the deployed LV Scheduled Maintenance (Cloud) workflow serves
    zero native HubSpot search nodes, disarmed"
affects: [22-armed-pipeline-activation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Read-back-as-a-distinct-step (third instance in this repo, after
      rollback_canary_proof.py and verify_live_lusha_urls.py): a redeploy's 200/exit-0
      proves the request succeeded, never that the live artifact is current. The
      pre-redeploy read-back here caught the same BUG-26-shaped drift Phase 20 Plan 05
      found — the live deployment was still serving the pre-Task-1 native search node."
    - "Retiring a permanently-vacuous vacuity guard rather than leaving it to fail
      forever: when a migration removes the last member of a guarded node class, the
      guard that checks 'is this class non-empty' becomes unsatisfiable by
      construction, not just today — the correct fix is to delete it with a comment
      naming its httpRequest-transport successor, not to patch it into a false pass."

key-files:
  created:
    - scripts/verify_live_no_native_search.py
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_scheduled_maintenance_cloud.json
    - tests/test_hubspot_native_operation_validity.py
    - tests/test_write_gate_coverage.py
    - tests/test_hubspot_node_auth.py

key-decisions:
  - "Retired tests/test_hubspot_node_auth.py's native-node CSV-vs-list pair
    (test_hubspot_properties_are_a_list_not_a_csv_string + its vacuity guard
    test_at_least_one_node_actually_requests_properties) rather than leave them
    failing: Task 1 removed the last native node anywhere in the repo carrying
    additionalFields.properties, so that guarded class is now PERMANENTLY empty
    (SJ-1/SJ-2's remaining native nodes use updateFields.customPropertiesUi, never
    additionalFields.properties). The defect class stays fully covered by the
    existing httpRequest-transport equivalent pair, which already applies to every
    search node going forward."
  - "The dedupe-lane classify-only allowlist is a single key
    (lv_enrichment_needs_review), narrower than the plan's own placeholder wording
    ('the needs-review flag and its reason field') — the sweep's to_review_reason
    field is row metadata that never reaches _hs_http_patch_node's
    {\"properties\": $json.properties} body, so it was never a second write surface
    to allowlist."
  - "Proceeded with the disarmed redeploy updating all three cloud workflows (not just
    the maintenance one) — deploy_n8n_workflows.py's diff always lists every
    name-matched live workflow for update regardless of whether its content changed;
    this is the same behavior Phase 20 Plan 05 exercised (also updated all three for a
    change scoped to one workflow), and Contact Ingest/Enrichment's committed JSON was
    unchanged by this plan so their PUT was a content no-op."

patterns-established:
  - "A migration that deletes the last member of an old code path must grep the whole
    repo (not just the plan's files_modified list) for both the identifier's textual
    residue AND any vacuity guard whose covered class the deletion might empty out."

requirements-completed: [REQ-dedupe-transport-swap]

coverage:
  - id: D1
    description: "Dedupe Search (candidate contacts) issues a credential-bound
      httpRequest POST to /crm/v3/objects/contacts/search; zero-hit results yield an
      empty-results envelope instead of stopping the chain"
    requirement: "REQ-dedupe-transport-swap"
    verification:
      - kind: unit
        ref: "tests/test_hubspot_native_operation_validity.py::test_no_native_hubspot_search_operation_remains_in_any_cloud_workflow"
        status: pass
      - kind: unit
        ref: "tests/test_deploy_credential_binding.py -q (unchanged, passes post-swap)"
        status: pass
      - kind: manual_procedural
        ref: "Live read-back (scripts/verify_live_no_native_search.py) post-redeploy: Dedupe Search (candidate contacts) reports type=httpRequest, url=.../crm/v3/objects/contacts/search"
        status: pass
    human_judgment: false
  - id: D2
    description: "No node of type n8n-nodes-base.hubspot carrying operation 'search'
      exists in any committed OR live cloud workflow; SJ-1/SJ-2's native
      company:update nodes remain untouched so the operation-validity guard stays
      non-vacuous"
    requirement: "REQ-dedupe-transport-swap"
    verification:
      - kind: unit
        ref: "tests/test_hubspot_native_operation_validity.py::test_no_native_hubspot_search_operation_remains_in_any_cloud_workflow, ::test_the_guard_is_actually_looking_at_something, ::test_the_guard_rejects_the_two_inputs_it_was_built_from"
        status: pass
      - kind: manual_procedural
        ref: "Non-vacuity proven by simulated revert (Dedupe Search node's type/parameters hand-edited back to native+search in the built JSON, test failed naming the node, then a clean rebuild restored the correct artifact)"
        status: pass
      - kind: manual_procedural
        ref: "Live read-back (scripts/verify_live_no_native_search.py) post-redeploy: verdict line reports 0 native search nodes across all 3 swept live workflows"
        status: pass
    human_judgment: false
  - id: D3
    description: "The dedupe lane remains classify-only: exactly one write node
      (Dedupe Set Needs Review) and its emitted property keys are a subset of an
      explicit allowlist"
    requirement: "REQ-dedupe-transport-swap"
    verification:
      - kind: unit
        ref: "tests/test_write_gate_coverage.py::test_dedupe_lane_has_exactly_one_gated_write_node, ::test_dedupe_lane_emits_only_allowlisted_property_keys"
        status: pass
    human_judgment: false
  - id: D4
    description: "Both full suites remain green: Python offline suite (with the
      retired vacuity-guard pair accounted for) and the unchanged JS suite"
    requirement: "REQ-dedupe-transport-swap"
    verification:
      - kind: unit
        ref: ".venv/bin/python -m pytest -q (607 passed: 611 baseline - 7 retired parametrized instances + 3 new tests)"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs (352 passed, unchanged)"
        status: pass
    human_judgment: false

# Metrics
duration: ~50min
completed: 2026-07-30
status: complete
---

# Phase 21 Plan 01: Dedupe Search Transport Swap Summary

**Dedupe Search (candidate contacts) moved onto the credential-bound httpRequest envelope, the native-search node builder deleted with zero textual residue, two new guard predicates added, and a disarmed live redeploy + read-back confirmed the class is closed both locally and in production.**

## Performance

- **Duration:** ~50 min
- **Started:** 2026-07-30T06:15:00Z (approx.)
- **Completed:** 2026-07-30T07:07:00Z
- **Tasks:** 3
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments

- Swapped the `dedupe_search` call site in `scripts/build_cloud_workflows.py` from the
  native-search node builder to `_hs_http_search_node`, same node name, resource, filter
  groups, and properties CSV — no adapter or wrapper change needed, since
  `ENRICH_EXTRACT_SEARCH_ROWS` already checks `res.results` first. Deleted the retired
  helper function entirely and scrubbed every textual reference to its identifier from
  comments and docstrings across `scripts/build_cloud_workflows.py` and
  `tests/test_hubspot_native_operation_validity.py` — confirmed by
  `grep -rnF "_hs_search_node" scripts/ tests/ n8n/ | grep -v "_hs_http_search_node"`
  printing nothing. Rebuild touched only `n8n/wf_scheduled_maintenance_cloud.json`.
- Added `test_no_native_hubspot_search_operation_remains_in_any_cloud_workflow` (scoped
  to the `search` operation only, leaving SJ-1/SJ-2's native `company:update` nodes and
  `test_the_guard_is_actually_looking_at_something`'s non-vacuity intact) and two
  dedupe-lane classify-only predicates (`test_dedupe_lane_has_exactly_one_gated_write_node`,
  `test_dedupe_lane_emits_only_allowlisted_property_keys`) pinning
  `Dedupe Set Needs Review` as the sole write node and `lv_enrichment_needs_review` as
  the sole property key the sweep may ever PATCH.
- Proved non-vacuity by hand-reverting the built JSON's Dedupe Search node back to the
  native shape, watching the new predicate fail naming the offending node, then
  restoring via a clean rebuild.
- Wrote `scripts/verify_live_no_native_search.py`, a read-only live verifier reusing
  `deploy_n8n_workflows.py`'s auth/URL helpers. It sweeps every live workflow (not just
  the named maintenance one) for native search nodes, prints the maintenance workflow's
  full node inventory (name/type/method/url — never a credential), and reports a
  machine-greppable verdict line.
- **The pre-redeploy read-back caught live deployment drift** (same BUG-26 shape Phase
  20 Plan 05 found): the deployed `LV Scheduled Maintenance (Cloud)` workflow was still
  serving the OLD native `Dedupe Search` node — this repo's Task-1 rebuild had never
  been pushed. Ran the disarmed redeploy (`DRY_RUN=false ALLOW_N8N_DEPLOY=true`, no
  `ENABLE_BAKED_FLAGS`) — all three cloud workflows updated (200 each), no activation
  performed, write-safety constants stayed committed-false. Post-redeploy read-back:
  0 native search nodes across all 3 live workflows; `Dedupe Search (candidate
  contacts)` now reports `type=httpRequest`, `url=.../crm/v3/objects/contacts/search`.
- Retired a now-permanently-vacuous vacuity guard in `tests/test_hubspot_node_auth.py`
  (see Deviations) so the offline suite stays green without papering over the check's
  actual purpose.
- Both full suites green: `.venv/bin/python -m pytest -q` (607 passed) and
  `node --test tests/n8n/*.test.mjs` (352 passed, unchanged — no `.mjs` module touched).

## Task Commits

Each task was committed atomically:

1. **Task 1: Swap the dedupe search onto the httpRequest envelope and delete the dead native-search helper** - `7cc2c7f` (feat)
2. **Task 2: Close the class — zero-native-search predicate + dedupe-lane classify-only predicate** - `32d2ac0` (test)
3. **Task 3: Disarmed redeploy + live read-back proving the served workflow has no native search node** - `5b8c058` (feat, includes the Rule-1/Rule-3 test-file fix)

## Files Created/Modified

- `scripts/build_cloud_workflows.py` - dedupe_search call site swapped to
  `_hs_http_search_node`; the retired native-search helper deleted; six comment/
  docstring sites rewritten to remove the retired identifier
- `n8n/wf_scheduled_maintenance_cloud.json` - rebuilt; only this workflow changed
- `tests/test_hubspot_native_operation_validity.py` - new zero-native-search-operation
  predicate; one comment rewritten to remove the retired identifier
- `tests/test_write_gate_coverage.py` - two new dedupe-lane classify-only predicates
- `tests/test_hubspot_node_auth.py` - retired the now-permanently-vacuous native-node
  CSV-vs-list pair (see Deviations)
- `scripts/verify_live_no_native_search.py` - new read-only live read-back verifier

## Decisions Made

See `key-decisions` in the frontmatter. In summary: retired a permanently-vacuous test
pair rather than patch it into a false pass; scoped the classify-only allowlist to the
single property key the sweep actually PATCHes (not the plan's placeholder "flag and
reason" pairing, since the reason field never reaches HubSpot); and treated the
"update all three workflows" deploy behavior as expected, matching Phase 20 Plan 05's
own precedent rather than a scope violation.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1/3 - Bug/Blocking] Retired a vacuity guard Task 1 made permanently unsatisfiable**
- **Found during:** Task 3 (running the full offline suite before the live steps)
- **Issue:** `tests/test_hubspot_node_auth.py::test_at_least_one_node_actually_requests_properties`
  is a vacuity guard for `test_hubspot_properties_are_a_list_not_a_csv_string`, both
  scoped to native `n8n-nodes-base.hubspot` nodes carrying `additionalFields.properties`.
  Task 1 deleted the last such node anywhere in the repo (the old Dedupe Search), so the
  guarded class is now empty — and will stay empty forever, since the two remaining
  native nodes (SJ-1/SJ-2 `Set Requested`) are `update` operations using
  `updateFields.customPropertiesUi`, never `additionalFields.properties`.
- **Fix:** Deleted both tests and replaced them with a comment explaining why, following
  this file's own stated design philosophy ("a guard that silently stops applying is
  worse than no guard") — the defect class (CSV vs. real JSON array reaching HubSpot's
  search API) stays fully covered by the pre-existing httpRequest-transport equivalent
  pair (`test_hubspot_httprequest_search_properties_are_a_real_json_array_never_a_csv_string`
  + its own vacuity guard), which already applies to every search node going forward.
- **Files modified:** `tests/test_hubspot_node_auth.py`
- **Verification:** `.venv/bin/python -m pytest -q` — 607 passed (611 baseline − 7
  retired parametrized instances + 3 new tests from Task 2)
- **Committed in:** `5b8c058` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1/3 — a passing test's guarded class went
permanently empty as a direct, foreseeable consequence of Task 1's own deletion).
**Impact on plan:** Necessary to keep the offline suite meaningfully green; no scope
creep — the retirement only removes a check that could never again assert anything, and
documents its successor inline.

## Issues Encountered

- The live pre-redeploy read-back found the deployed `LV Scheduled Maintenance (Cloud)`
  workflow predated this plan's Task 1 rebuild (BUG-26-shaped deployment drift, same
  class Phase 20 Plan 05 caught for Lusha). Resolved by the disarmed redeploy in Task 3;
  the post-redeploy read-back confirms the live artifact now matches the committed
  build exactly.

## User Setup Required

None - no external service configuration required. The `.env` file with `N8N_URL` /
`N8N_API_KEY` (agent-blocked from direct reads, loaded in-process via `load_dotenv()`
per project constraints) was already present and sufficient for both the redeploy and
the read-back; no new operator action is pending.

## Next Phase Readiness

- `Dedupe Search (candidate contacts)` is no longer a "known, unfixed concern" — the
  BUG-10/22/23 native-search retirement is fully closed, locally and live, before Phase
  22 arms the pipeline (this weekly sweep has never run activated).
- Plans 21-02/21-03/21-04 (country-region field policy, org_type schema migration, and
  whatever follows) are unaffected by this plan's scope — no shared files besides the
  generic `tests/test_hubspot_node_auth.py` change, which is orthogonal to their
  concerns.

## Self-Check: PASSED

- FOUND: `scripts/verify_live_no_native_search.py`
- FOUND: `n8n/wf_scheduled_maintenance_cloud.json`
- FOUND commit `7cc2c7f` (Task 1)
- FOUND commit `32d2ac0` (Task 2)
- FOUND commit `5b8c058` (Task 3)

---
*Phase: 21-transport-schema-hygiene*
*Completed: 2026-07-30*
