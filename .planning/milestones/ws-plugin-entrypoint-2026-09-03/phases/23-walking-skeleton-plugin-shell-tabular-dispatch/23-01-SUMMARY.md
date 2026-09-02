---
phase: 23-walking-skeleton-plugin-shell-tabular-dispatch
plan: 01
subsystem: infra
tags: [n8n, hubspot, write-gate, code-generation, python, javascript]

requires: []
provides:
  - "Decide Action (contact-ingest Cloud workflow) reads the deploy-time-overlayable ALLOW_HUBSPOT_CREATE constant instead of a Set-Config-seeded row field, so an armed deploy can actually create a net-new contact"
  - "Regression tests pinning both the disarmed (review) and overlay-armed (create) behaviour of Decide Action, plus the HubSpot Create Write Gate's allowlist requirement"
affects: [plugin-entrypoint-phase-23, contact-upload-lane]

tech-stack:
  added: []
  patterns:
    - "Deploy-time-overlayable write-safety constant baked at the build site (not at the module-level jsCode template), reusing an existing flag rather than adding a new overlayable name"

key-files:
  created:
    - tests/n8n/contactCreateGateFlow.test.mjs
    - tests/test_contact_create_overlay.py
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_contact_ingest_cloud.json
    - CHANGELOG.md

key-decisions:
  - "Reused the existing ALLOW_HUBSPOT_CREATE overlayable constant rather than adding a fifth flag (D-16a) — keeps _OVERLAYABLE_FLAGS pinned at four names and gets the TEST_RECORD_* allowlist fail-safe for contact creation for free."
  - "Composed the constant declaration at the build_cloud() call site (prepended to DECIDE_CLOUD's jsCode only, for the 'Decide Action' node) rather than inside DECIDE_CLOUD's module-level string, because _write_safety_const is defined later in the module (D-16b)."
  - "Left Set Config's row-seeded allow_create=false in place for the LOCAL/dry-run echo lane (DECIDE_LOCAL), which legitimately still reads a row field; only the Cloud Decide Action changed."

requirements-completed: [DISPATCH-01]

coverage:
  - id: D1
    description: "A disarmed (committed) deploy of wf_contact_ingest_cloud.json still routes a net-new contact row to action=review"
    requirement: "DISPATCH-01"
    verification:
      - kind: unit
        ref: "tests/n8n/contactCreateGateFlow.test.mjs#Decide Action: committed (disarmed) build routes a net_new row to review"
        status: pass
      - kind: unit
        ref: "tests/test_write_gate_coverage.py::test_committed_write_safety_constants_are_all_disabled"
        status: pass
    human_judgment: false
  - id: D2
    description: "An overlay-armed deploy (ALLOW_HUBSPOT_CREATE enabled the same way enable_baked_flags() enables it) routes the same net-new row to action=create, seeding email/firstname/lastname"
    requirement: "DISPATCH-01"
    verification:
      - kind: unit
        ref: "tests/n8n/contactCreateGateFlow.test.mjs#Decide Action: overlay-enabled build routes the SAME net_new row to create"
        status: pass
      - kind: unit
        ref: "tests/test_contact_create_overlay.py::test_enable_baked_flags_rewrites_the_create_constant_in_three_or_more_nodes"
        status: pass
    human_judgment: false
  - id: D3
    description: "Arming contact creation still cannot happen without a TEST_RECORD_* allowlist in the same invocation (write-gate two-key convention preserved)"
    requirement: "DISPATCH-01"
    verification:
      - kind: unit
        ref: "tests/n8n/contactCreateGateFlow.test.mjs#HubSpot Create Write Gate: a create-action row is dropped with an empty allowlist, and passes once armed with a matching domain"
        status: pass
    human_judgment: false
  - id: D4
    description: "lookup_failed still downgrades a create to review even when the create constant is armed (fail-closed override preserved)"
    verification:
      - kind: unit
        ref: "tests/n8n/contactCreateGateFlow.test.mjs#Decide Action: lookup_failed still downgrades a create to review even when armed"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-07-30
status: complete
---

# Phase 23 Plan 01: Contact-Ingest Create-Gate Fix Summary

**Decide Action (contact-ingest Cloud workflow) now reads the existing overlayable `ALLOW_HUBSPOT_CREATE` constant instead of a `Set Config`-seeded row field, so an armed deploy can finally create a net-new contact — with two new offline test files pinning both the disarmed and armed behaviour and the allowlist requirement.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-30T13:03:00Z (approx.)
- **Completed:** 2026-07-30T13:28:32Z
- **Tasks:** 3
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments
- Closed backend blocker D-15: the contact-upload lane's create decision no longer reads a hardcoded row field (`Set Config`'s `allow_create: false`) that could never be created from `false` by any deploy-time mechanism.
- `Decide Action` (`DECIDE_CLOUD`) now declares and reads `ALLOW_HUBSPOT_CREATE` — the SAME overlayable constant its downstream `HubSpot Create Write Gate` already reads — composed at the `build_cloud()` call site rather than baked into the shared module-level template string.
- Two new regression test files (one Node, one Python) prove: disarmed build routes `net_new` to `review`; overlay-armed build (via the exact literal swap `enable_baked_flags()` performs) routes the same row to `create` with identity seeded onto the payload (BUG 19 behaviour preserved); the write gate still drops a `create`-action row until both write-safety booleans AND a matching `TEST_RECORD_DOMAINS`/`TEST_RECORD_IDS` entry are present; `lookup_failed` still forces `review` even when armed.
- Backend `CHANGELOG.md` records the fix as a deliberate Phase 23 backend gate change (D-17), distinct from the plugin's own client-scoped changelog.

## Task Commits

Each task was committed atomically:

1. **Task 1: Bake the overlayable create constant into the contact lane's Decide Action** - `87cdd19` (fix)
2. **Task 2: Regression tests — disarmed routes to review, overlay routes to create** - `db4e037` (test)
3. **Task 3: Record the gate fix in the backend changelog** - `24063d1` (docs)

_Note: this plan's tasks were not TDD-gated per-task (Task 1 is `type="tracer" tdd="true"` but its own commit already carries the fixed, verified behaviour; Task 2 supplies the standalone regression coverage as its own commit)._

## Files Created/Modified
- `scripts/build_cloud_workflows.py` - `DECIDE_CLOUD`'s `allow_create` now derives from `ALLOW_HUBSPOT_CREATE` (coerced via `String(...).toLowerCase() === "true"`, identifier name unchanged for `test_create_payload_identity.py`); `build_cloud()`'s node-assembly loop composes `_write_safety_const("ALLOW_HUBSPOT_CREATE") + "\n" + DECIDE_CLOUD` for the "Decide Action" node only; `Set Config`'s comment updated to point at the new gate location while its row seed stays for the LOCAL/dry-run lane.
- `n8n/wf_contact_ingest_cloud.json` - rebuilt via `python scripts/build_cloud_workflows.py`; diff confined to this one file (verified: `git diff --name-only -- n8n/` listed exactly this path before commit).
- `tests/n8n/contactCreateGateFlow.test.mjs` - executes the committed workflow's `Decide Action` and `HubSpot Create Write Gate` jsCode via `new Function` (same mechanism n8n's Code node uses), covering disarmed/armed/lookup_failed/allowlist behaviours.
- `tests/test_contact_create_overlay.py` - calls `scripts.deploy_n8n_workflows.enable_baked_flags()` against the committed contact workflow; asserts the create-constant rewrite count exceeds 2 (the two pre-existing write gates), asserts no fail-closed `ValueError`, and asserts the committed file carries only the disabled literal.
- `CHANGELOG.md` - one Unreleased/Fixed entry naming the contact-upload lane and the `ALLOW_HUBSPOT_CREATE` fix explicitly.

## Decisions Made
- Reused the existing `ALLOW_HUBSPOT_CREATE` overlayable constant rather than introducing a fifth overlay flag (D-16a) — required because `tests/test_enabled_build_invariants.py::test_overlayable_flags_is_a_strict_subset_of_config_flag_defaults` pins `_OVERLAYABLE_FLAGS` to exactly four names, and reuse keeps the `_requested_overlay_flags` "no write without an allowlist" fail-safe applying to contact creation automatically.
- Composed the declaration at the `build_cloud()` build site rather than at `DECIDE_CLOUD`'s module-level definition (D-16b) — `_write_safety_const` is defined later in the module (would raise `NameError` at import time if called inline), and placing the read in `Decide Action` (not `Set Config`) avoids the BUG 12/BUG 21 row-loss family, since `Extract From File` emits fresh items that drop anything seeded upstream of it.
- Did not OR the deploy-time constant with the row's own `allow_create` value — the constant is the sole authority on the Cloud lane per the plan's explicit instruction.

## Deviations from Plan

None in implementation - plan executed exactly as written. The plan's `<read_first>` guidance (constant name, gate location, node names, test idioms) matched the actual codebase exactly; no rule 1-4 deviations were needed.

**Requirements-tracking note (not a code deviation):** this plan's frontmatter lists `requirements: [DISPATCH-01]`, but `DISPATCH-01`'s actual text ("Approved row batches POST to `hubspot/contact-upload` with the correct header auth and body encoding") is delivered by the plugin's `dispatch.py`, attributed in this phase's artifact index to plans 23-03→23-05, not to this backend-gate fix. Marking `DISPATCH-01` `Done` in `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` now — before the POST mechanism itself exists — would be inaccurate, so this plan does not run `requirements mark-complete` for it. Leaving it `Pending` until the plan that actually implements the POST closes it.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required. This plan changes only the builder script and the committed (still-disarmed) workflow artifact; no deploy was performed.

## Next Phase Readiness
- The contact-upload lane's create gate now matches the two-key write-gate convention used everywhere else in this repo; a future deploy with `ENABLE_BAKED_FLAGS=ALLOW_HUBSPOT_RECORD_WRITES,ALLOW_HUBSPOT_CREATE,TEST_RECORD_DOMAINS=<domain>` (or `TEST_RECORD_IDS=<id>`) will actually be able to create a test contact, which the walking skeleton's later plans (23-03 through 23-05, plugin packaging) can demonstrate end-to-end without any further backend change.
- No blockers for downstream plugin-packaging plans in this phase; this plan touched no file under `operator-claude-plugin/`, preserving success criterion 4.

---
*Phase: 23-walking-skeleton-plugin-shell-tabular-dispatch*
*Completed: 2026-07-30*

## Self-Check: PASSED

All created/modified files confirmed present on disk; all three task commits (`87cdd19`, `db4e037`, `24063d1`) confirmed present in `git log --oneline --all`.
