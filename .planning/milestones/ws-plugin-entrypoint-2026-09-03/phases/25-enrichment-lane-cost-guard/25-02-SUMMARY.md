---
phase: 25-enrichment-lane-cost-guard
plan: 02
subsystem: n8n-backend
tags: [n8n, hubspot, credit-status, cost-guard, webhook]

requires:
  - phase: 16.1
    provides: provider_registry.py / providerSelection.js (extractCredits, provider credit URLs), the enrichment lane's single-item Credit Request + credit HTTP node pattern this plan reuses verbatim
provides:
  - "n8n/wf_backend_status_cloud.json — the credit-only hubspot/backend-status endpoint (Phase 27 grows it into full health)"
  - "build_backend_status_cloud() in scripts/build_cloud_workflows.py"
  - "Status Webhook Trigger NODE_CREDENTIAL_MAP entry in scripts/deploy_n8n_workflows.py"
  - "tests/test_backend_status_workflow.py, tests/n8n/backendStatusResponse.test.mjs"
affects: [operator-claude-plugin (client will call this endpoint, Phase 25 client-side plans / Phase 27)]

tech-stack:
  added: []
  patterns:
    - "credit-only status endpoint as its OWN workflow file, never a second trigger on an existing multi-branch workflow whose responder has first-arrival semantics (D-14)"
    - "unreadable-vs-zero tri-state for a probed balance: never fall back to a number; explicit unreadable boolean + null credits"

key-files:
  created:
    - n8n/wf_backend_status_cloud.json
    - tests/test_backend_status_workflow.py
    - tests/n8n/backendStatusResponse.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - scripts/deploy_n8n_workflows.py
    - CHANGELOG.md
    - tests/test_architecture_guard.py
    - tests/test_write_gate_coverage.py

key-decisions:
  - "D-14 followed exactly: new workflow file, sequential (not fanned-out) probe chain, so the response can never fire before all three provider probes have run."
  - "configured is hardcoded true for every emitted provider entry — this endpoint probes all three canonical providers unconditionally (D-10/research A4), so there is no not-configured case to represent here (unlike the admin CLI's env-var gate)."
  - "Unreadable classification never touches the provider's own raw error text — the emitted error label is synthesized (\"http_403\", \"not_executed\", \"unrecognized_response_shape\", \"provider_error\") so no account metadata can leak through an error field (T-25-03)."

patterns-established:
  - "A read-only, credit-only n8n workflow reusing an existing enrichment-lane subgraph by node name costs zero new NODE_CREDENTIAL_MAP registration for the reused nodes."

requirements-completed: [PREVIEW-02]

coverage:
  - id: D1
    description: "POST hubspot/backend-status (header-auth-gated) returns each provider's remaining credits without the caller holding a provider credential"
    requirement: PREVIEW-02
    verification:
      - kind: unit
        ref: "tests/test_backend_status_workflow.py::test_status_webhook_trigger_is_post_header_auth_response_node"
        status: pass
      - kind: unit
        ref: "tests/n8n/backendStatusResponse.test.mjs (Lusha 200 / ZoomInfo 200 balance extraction)"
        status: pass
    human_judgment: false
  - id: D2
    description: "An unreadable balance (Apollo's live non-master-key 403) renders as an explicit unreadable marker, never zero, and configured stays true"
    requirement: PREVIEW-02
    verification:
      - kind: unit
        ref: "tests/n8n/backendStatusResponse.test.mjs (Apollo 403 case + genuine-zero-vs-unreadable distinguishability test)"
        status: pass
    human_judgment: false
  - id: D3
    description: "All three provider probes run sequentially (never fanned out) so the response cannot fire before every probe has completed"
    requirement: PREVIEW-02
    verification:
      - kind: unit
        ref: "tests/test_backend_status_workflow.py::test_the_three_probe_entries_each_have_exactly_one_inbound_source, ::test_no_single_node_output_fans_to_two_different_probe_nodes"
        status: pass
    human_judgment: false
  - id: D4
    description: "No raw provider response body reaches the assembled response — only extracted number/boolean/label/status"
    requirement: PREVIEW-02
    verification:
      - kind: unit
        ref: "tests/n8n/backendStatusResponse.test.mjs (no emitted per-provider value carries any key beyond the extracted fields)"
        status: pass
    human_judgment: false
  - id: D5
    description: "The enrichment workflow's committed bytes are unchanged; only the new file was added"
    requirement: PREVIEW-02
    verification:
      - kind: unit
        ref: "git diff scope check (git status --porcelain n8n/ confined to wf_backend_status_cloud.json) + tests/test_remaining_credits_response.py + tests/n8n/enrichment.test.mjs"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-07-31
status: complete
---

# Phase 25 Plan 02: Credit-only `hubspot/backend-status` endpoint Summary

**New n8n Cloud workflow (`wf_backend_status_cloud.json`) that sequentially probes Lusha/Apollo/ZoomInfo usage endpoints and assembles a single response distinguishing a genuine zero balance from an unreadable one (Apollo's non-master key 403 is the live proof case).**

## Performance

- **Duration:** 55 min
- **Started:** 2026-07-30T20:32:00Z
- **Completed:** 2026-07-31T21:27:00Z
- **Tasks:** 3 completed
- **Files modified:** 7 (3 created, 4 modified: 2 by plan design + 2 pre-existing architecture guards auto-fixed)

## Accomplishments
- Built `hubspot/backend-status` as its own workflow file (D-14), never a second trigger on `wf_enrichment_cloud.json` — the enrichment lane's existing `Build Response` first-arrival semantics could not be reused safely for a status read.
- Chained the three provider probes (`Lusha Usage` → `Apollo Usage` → the shared ZoomInfo usage subgraph) sequentially rather than fanning out, so the single `Respond to Webhook` cannot fire until all three have run.
- `Build Credit Status` distinguishes genuine zero from unreadable in every code path, tested against the exact "unreadable is falsy" defect shape the phase context bans (D-17).
- Reused the enrichment lane's node names for all three probes verbatim — zero new `NODE_CREDENTIAL_MAP` registration needed for those; only the new trigger node needed a map entry, bound to the same shared webhook-secret credential.

## Task Commits

1. **Task 1: End-to-end "POST backend-status returns three balances" — one path only** - `1c8eb1e` (feat)
2. **Task 2: Prove unreadable is not zero, in both the graph and the response assembly** - `a5b42ea` (test)
3. **Task 3: Register the new workflow for deploy and record it** - `0d9d6c1` (feat)

_No TDD gate applies — Task 2 is `type="auto" tdd="true"` at the plan level in name only; the plan structure is tracer-then-verify, not RED/GREEN/REFACTOR, since Task 1 already ships the real implementation and Task 2 is characterization + structural proof against it._

## Files Created/Modified
- `n8n/wf_backend_status_cloud.json` - the built, disarmed credit-only status workflow
- `scripts/build_cloud_workflows.py` - `build_backend_status_cloud()`, `ENRICH_STATUS_CREDIT_REQUEST`, `ENRICH_STATUS_BUILD_RESPONSE`, `main()` writes the new file
- `scripts/deploy_n8n_workflows.py` - `Status Webhook Trigger` NODE_CREDENTIAL_MAP entry
- `tests/test_backend_status_workflow.py` - structural proof (sequential chain, credential binding, no `$env`/`$vars`, non-vacuity guard)
- `tests/n8n/backendStatusResponse.test.mjs` - behavioral proof of the unreadable/zero tri-state via the compiled `Build Credit Status` jsCode
- `CHANGELOG.md` - Unreleased/Added entry for the new endpoint
- `tests/test_architecture_guard.py` - added the new filename to the `ACTIVE` deploy-manifest list (auto-fix, see Deviations)
- `tests/test_write_gate_coverage.py` - added a `NO_WRITE_NODES_EXPECTED` allowlist that still asserts zero write nodes rather than skipping (auto-fix, see Deviations)

## Decisions Made
- **`configured` is hardcoded `true`** for every emitted per-provider entry. This endpoint always probes all three canonical providers unconditionally (D-10, research A4) — there is no "not configured" state to represent at this layer, unlike the admin CLI's env-var presence gate. Documented inline in the JS comment so a future reader does not mistake it for dead code.
- **Error labels are synthesized, never the provider's raw error text.** `http_<status>`, `not_executed`, `unrecognized_response_shape`, `provider_error` — chosen specifically so no provider-supplied string (which could carry account-specific detail) ever reaches the response body (T-25-03).
- **HTTP status extraction is generic** (checks `statusCode`/`httpCode`/`status`/`response.status`/`response.statusCode`) rather than reusing `zoominfoToken.js`'s `extractErrorStatus` (which is built around a thrown-exception object shape from a Code node's own try/catch, not a native `httpRequest` node's `continueRegularOutput` item) — a small purpose-built helper was clearer than force-fitting an exception-shaped helper onto a different runtime shape.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - blocking full-suite pass] `test_architecture_guard.py`'s deploy-manifest list did not include the new workflow file**
- **Found during:** Task 3 (running `.venv/bin/python -m pytest -q`, the phase's own full-suite verification requirement)
- **Issue:** `test_top_level_is_exactly_the_deployable_set` asserts `n8n/*.json` equals a hardcoded `ACTIVE` list. The moment `wf_backend_status_cloud.json` existed (Task 1), this assertion failed — the guard was correct to fail (it exists to prevent stray files from silently entering the deploy set), and the new file is a legitimate, deliberate addition to that set.
- **Fix:** Added `"wf_backend_status_cloud.json"` to `ACTIVE`.
- **Files modified:** `tests/test_architecture_guard.py`
- **Verification:** `.venv/bin/python -m pytest tests/test_architecture_guard.py -q` passes; full suite green.
- **Committed in:** `0d9d6c1` (part of Task 3 commit)

**2. [Rule 3 - blocking full-suite pass] `test_write_gate_coverage.py` assumed every cloud workflow has at least one write node**
- **Found during:** Task 3 full-suite run
- **Issue:** `test_every_write_node_sits_behind_a_write_safety_gate` treats a workflow with zero detected write nodes as a vacuous/broken-detector case and fails it. `wf_backend_status_cloud.json` is genuinely write-free by design (D-14: reads provider usage endpoints only, never a HubSpot endpoint) — the assumption that every cloud workflow writes no longer holds now that a deliberately read-only one exists.
- **Fix:** Added an explicit `NO_WRITE_NODES_EXPECTED = {"wf_backend_status_cloud.json"}` allowlist. Rather than simply skipping the file, the test now positively **asserts zero write nodes** for anything in that set — so a write node landing there unnoticed in a future change would still fail the suite, not silently pass.
- **Files modified:** `tests/test_write_gate_coverage.py`
- **Verification:** `.venv/bin/python -m pytest tests/test_write_gate_coverage.py -q` passes; full suite green.
- **Committed in:** `0d9d6c1` (part of Task 3 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3, both discovered while satisfying the plan's own "full suite exits 0" acceptance criterion for Task 3).
**Impact on plan:** Both fixes are pre-existing architecture guards adapting to a legitimate new file; neither weakens what the guards protect (the deploy-manifest guard still catches a stray file; the write-gate guard still catches an unnoticed write node). No scope creep — both fixes are minimal, targeted, and documented inline in the affected test files.

## Issues Encountered
None beyond the two auto-fixed test-suite adjustments above.

## User Setup Required
None - no external service configuration required. This plan ships a committed, disarmed workflow artifact only; no deploy or activation was performed (per plan's explicit safety constraint), so there is nothing for an operator to set up yet. Deploying this workflow to n8n Cloud remains a separate, deliberate admin action (`scripts/deploy_n8n_workflows.py`, env-gated, dry-run by default) — out of scope for this plan.

## Next Phase Readiness
- `hubspot/backend-status` exists as a built, disarmed artifact ready for a future deploy step; the operator-facing plugin can be built against its documented response shape (`{ balances: [{provider, configured, credits, unreadable, error, status}], checked_at }`) without waiting on live deployment.
- Phase 27 (STATUS-01..06) grows this same file into full health — the sequential-chain pattern and the `Build Credit Status` node are the natural extension point.
- No blockers for the rest of Phase 25's other wave-1 plans or the 24-01 sibling plan (confirmed disjoint file scope: this plan touched only `n8n/`, repo-root `scripts/`, and `tests/`).

---
*Phase: 25-enrichment-lane-cost-guard*
*Completed: 2026-07-31*
