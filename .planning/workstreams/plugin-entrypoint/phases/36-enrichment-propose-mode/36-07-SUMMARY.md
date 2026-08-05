---
phase: 36-enrichment-propose-mode
plan: 07
subsystem: n8n-cloud-workflows
tags: [n8n, hubspot, contact-ingest, scheduled-poller, enrichment-handoff]

requires:
  - phase: 36-06
    provides: DECIDE_CLOUD's create-only identity-seed block (BUG 19) and the deployed
      ALLOW_HUBSPOT_CREATE-gated create branch this plan stamps
provides:
  - "DECIDE_CLOUD's create branch stamps `lv_enrichment_requested = \"true\"` on every
    newly created contact, so the already-deployed 15-minute scheduled poller
    (n8n/wf_scheduled_maintenance_cloud.json) sweeps it without further operator action"
affects: [37-enrich-before-ingest, 37-09-uat]

actuals:
  tokens: 3527
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Work-queue flag vs write gate: a poller-searched property stamped inside an
      already-gated branch grants no permission of its own — distinguish explicitly
      from ALLOW_HUBSPOT_* arming constants"

key-files:
  created: []
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_contact_ingest_cloud.json
    - tests/test_create_payload_identity.py

key-decisions:
  - "Stamp lives inside DECIDE_CLOUD's existing create-only block (BUG 19's identity-seed
    branch), not in the shared _hs_http_create_node helper — the helper is used by both
    the ingest and enrichment lanes and editing it would stamp both."
  - "Value is the string \"true\", never a JS boolean — the poller's HubSpot search filter
    is `operator: EQ, value: \"true\"`; a boolean serializes to something that filter does
    not match, and the handoff would silently never fire."
  - "Used the deployed prefixed property name `lv_enrichment_requested` (confirmed at
    scripts/build_cloud_workflows.py:5570-5625, SJ-1/SJ-2 Set Requested), not the
    unprefixed spelling CLAUDE.md's design doc uses for the same concept."

patterns-established:
  - "Character-index test idiom (36-04's `if`-to-`return` ordering pin) reused to prove a
    new assignment sits inside a specific branch rather than merely appearing in the
    source somewhere."

requirements-completed: [DISPATCH-01, DISPATCH-02]

coverage:
  - id: D1
    description: "A contact CREATED by the ingest lane carries lv_enrichment_requested = \"true\" in its create body, inside the existing create-only block, provable by character index."
    requirement: DISPATCH-01
    verification:
      - kind: unit
        ref: "tests/test_create_payload_identity.py::test_the_create_body_carries_the_enrichment_handoff_flag"
        status: pass
      - kind: unit
        ref: "tests/test_create_payload_identity.py::test_the_handoff_flag_assignment_sits_inside_the_create_block"
        status: pass
      - kind: other
        ref: "python -c assertion against n8n/wf_contact_ingest_cloud.json's built Decide Action jsCode (Task 1 verify block)"
        status: pass
    human_judgment: false
  - id: D2
    description: "A contact UPDATED by the ingest lane does not receive the stamp; exactly one assignment exists in the built code, and the unprefixed spelling is never assigned."
    requirement: DISPATCH-02
    verification:
      - kind: unit
        ref: "tests/test_create_payload_identity.py::test_the_handoff_flag_is_stamped_exactly_once"
        status: pass
      - kind: unit
        ref: "tests/test_create_payload_identity.py::test_the_unprefixed_spelling_is_never_assigned"
        status: pass
    human_judgment: false
  - id: D3
    description: "Only n8n/wf_contact_ingest_cloud.json regenerates; builder is idempotent; arming grep stays 0; all suites at or above baseline; deploy script not run."
    verification:
      - kind: other
        ref: "Task 1/Task 2 automated verify blocks — ONLY_INGEST_MOVED, ARMING_GREP_CLEAN, IDEMPOTENT; repo pytest 2134/6, plugin pytest 1215/5, node --test 621"
        status: pass
    human_judgment: false

duration: ~15min
completed: 2026-08-05
status: complete
---

# Phase 36 Plan 07: Ingest Create Payload Stamps the Poller Queue Flag Summary

**DECIDE_CLOUD's create branch now stamps `lv_enrichment_requested = "true"` on every newly created contact, so the already-deployed 15-minute scheduled poller sweeps it without any client-side call — closing 37-07's paused checkpoint with the operator's option-b ruling.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 2
- **Files modified:** 3 (1 builder line + generated JSON regen + 2 test file edits)

## Accomplishments

- Added one assignment, `properties.lv_enrichment_requested = "true";`, inside DECIDE_CLOUD's existing `if (action === "create")` block (the same branch BUG 19's identity seed uses), directly below the three identity-seed lines.
- Regenerated `n8n/wf_contact_ingest_cloud.json` — confirmed it is the ONLY `n8n/*.json` that moved.
- Added four structural tests to `tests/test_create_payload_identity.py`, all individually red-checked:
  1. the flag is assigned onto the create payload (assignment-target form, not a bare grep)
  2. the assignment's character index falls strictly inside the create block (between the `if` and the following `return { json: {`)
  3. the assignment occurs exactly once in the built source (guards against a hoisted stamp re-queuing every matched record on every update)
  4. the unprefixed spelling `enrichment_requested` is never assigned (assignment-target form, because the prefixed name contains the unprefixed one as a substring — a naive `not in` check would fail on correct code)

## Task Commits

1. **Task 1: stamp the create body, regenerate, prove it in the built artifact** — `bed5ee4` (feat)
2. **Task 2: pin the negatives — update path clean, prefixed name only — and run the gates** — `2455e70` (test)

## Files Created/Modified

- `scripts/build_cloud_workflows.py` — `DECIDE_CLOUD`'s create-only block gains the queue-flag stamp, with a comment recording the 37-CONTEXT.md §13(b) origin, the not-arming distinction, and the create-only rationale.
- `n8n/wf_contact_ingest_cloud.json` — regenerated; `Decide Action` node's `jsCode` carries the stamp.
- `tests/test_create_payload_identity.py` — four new tests under a clearly-headed section distinct from BUG 19's identity-rule tests.

## Decisions Made

- Stamp placed in `DECIDE_CLOUD` only, not `_hs_http_create_node` (shared with the enrichment lane) — see key-decisions above.
- String `"true"`, not a boolean — matches the poller's `EQ` filter literal.
- `lv_-`prefixed property name, read from the builder's own SJ-1/SJ-2 `Set Requested` calls rather than retyped from CLAUDE.md's unprefixed design-doc spelling.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' verification blocks passed as specified; every new assertion was red-checked individually (moved-above-`if`, removed entirely, duplicated, and unprefixed-spelling substitution) before being restored.

## Not Arming — restated

`lv_enrichment_requested` is a **work-queue flag** the scheduled poller searches for, not a write gate. It is emitted strictly inside a branch already reachable only when `ALLOW_HUBSPOT_CREATE` is armed, so it can only ever annotate a record the backend was already permitted to create — it widens no blast radius. The disarmed-artifact grep (`ALLOW_HUBSPOT_[A-Z_]* = "true"` over `n8n/*.json`) still reports 0, confirmed in Task 2's verify block.

## Backstop (carried forward, not proven by this plan)

This plan queues each created contact **exactly once** — the stamp is written on the create body itself, so there is no second pass that could double-queue it. It does **not** prevent redundant work on a record that is already enriched; that is the poller's own staleness and status gating (SJ-2's re-verified-since-scan-started skip, RT-5 confirmation via the Company Gate). Live verification of that backstop is 37-09's walk, not this plan.

## Suite Gates (measured)

| Gate | Result | Baseline |
|---|---|---|
| `.venv/bin/python -m pytest -q` | 2134 passed, 6 skipped | 2130/6 (+4 new tests) |
| `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` | 1215 passed, 5 skipped | 1215/5 — unchanged |
| `node --test tests/n8n/*.test.mjs` (file glob) | 621 pass | 621 — unchanged |
| `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` | 0 for every file | 0 |
| Builder idempotency (`git diff --stat n8n/` after second run) | empty | empty |
| `scripts/deploy_n8n_workflows.py` | not run | not run |

No plugin file changed; `operator-claude-plugin/scripts/report.py`'s `queue_handoff_ids` is exactly as 37-07 shipped it.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. This stamp rides Phase 36's already-scheduled cloud deploy (36-05's operator-run checkpoint); no separate action needed.

## Next Phase Readiness

- 37-CONTEXT.md §13(b)'s post-ingest handoff half is now implemented at the ingest-lane level; the pre-ingest run-manifest/idempotent-resume half (§13(a)) remains 37's own scope.
- 37-09's live walk is the point where the backstop claim above (poller staleness gating prevents redundant enrichment) gets its first live proof.

---
*Phase: 36-enrichment-propose-mode*
*Completed: 2026-08-05*

## Self-Check: PASSED
