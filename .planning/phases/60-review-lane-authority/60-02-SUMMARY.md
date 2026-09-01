---
phase: 60-review-lane-authority
plan: 02
subsystem: auth
tags: [python, pytest, hubspot, n8n, write-grant, guardrail, batch-window]

requires:
  - phase: 60-review-lane-authority
    plan: 01
    provides: "review" as a third grantable lane, n8n_arming.arm_for_review/armed_review_window (authority=AUTHORITY_REVIEW), review_decision.submit_decision gated by write_grant.authorize_send(lane="review")
provides:
  - "Guardrail A reads all five n8n_arming.OVERLAYABLE_FLAGS per lane (was DISPATCH_FLAGS, 4) so a stuck-open ALLOW_HUBSPOT_REVIEW_WRITES refuses the next grant open, by name"
  - "write_grant.authorize_review_batch(grant) — a batch-scoped review window whose allowlist is fixed to the grant's own record list at open time, never widened as records are triaged"
  - "preflight_before_send narrowed on the review lane only, so the batch window it authorizes cannot trip over its own arm"
affects: [60-03-written-records, 60-04-skill-docs]

actuals:
  tokens: 10245
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "guardrail-read widening derives its render list from the SAME sorted(OVERLAYABLE_FLAGS) it iterates to build the fault, so what a refusal prints and what it read can never diverge"
    - "a narrowed liveness check derived from the same tuple it narrows (WRITE_ENABLING_FLAGS minus one flag) rather than a second literal list, so the widened and narrowed sets can never drift apart"
    - "a batch-scoped authorization function returns the grant's OWN record list on purpose, documented as the deliberate divergence from a per-send authorization that refuses to"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/write_grant.py
    - operator-claude-plugin/tests/test_write_grant_guardrails.py
    - operator-claude-plugin/tests/test_write_grant.py
    - operator-claude-plugin/tests/test_write_grant_surface.py
    - operator-claude-plugin/tests/test_chunking.py
    - operator-claude-plugin/tests/test_unattended_pair_composition.py

key-decisions:
  - "T-60-06: WRITE_ENABLING_FLAGS widened from 2 to 3 items, review flag appended LAST (order load-bearing — an existing test pins the exact live_flags list) and read_live_write_state/guardrail_a widened from DISPATCH_FLAGS (4) to sorted(OVERLAYABLE_FLAGS) (5), uniformly per lane"
  - "T-60-08/MEDIUM-1: preflight_before_send excludes ONLY the review flag, and ONLY on the review lane, deriving the narrowed set from WRITE_ENABLING_FLAGS rather than a second literal — a live dispatch flag on the review workflow still closes the grant"
  - "authorize_review_batch returns record_ids/record_domains, the one deliberate divergence from authorize_send's refusal to do so, because D-60-06 makes the window's allowlist the grant's own scope rather than one send's"

requirements-completed: [D-60-03, D-60-05, D-60-06]

coverage:
  - id: D1
    description: "Guardrail A refuses to open a grant over a backend where ONLY the review authorization is stuck live, naming the flag and the allowlist in force"
    requirement: D-60-05
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py#test_a_stuck_open_review_flag_refuses_the_open_and_names_it"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py#test_the_armed_backend_refusal_still_names_only_the_two_dispatch_flags"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py#test_a_workflow_declaring_only_the_four_dispatch_constants_is_unreadable_and_refuses"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py#test_a_fully_disarmed_five_constant_workflow_still_proceeds"
        status: pass
    human_judgment: false
  - id: D2
    description: "authorize_review_batch scopes one arm/disarm to a whole triage sitting; every individual decision inside it is still scoped per record"
    requirement: D-60-06
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py#test_authorize_review_batch_on_a_three_lane_grant_returns_armed_with_the_grants_own_records"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py#test_authorize_review_batch_costs_exactly_one_arm_and_one_disarm_across_three_decisions"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py#test_a_decision_outside_the_grants_records_refuses_but_the_window_still_disarms"
        status: pass
    human_judgment: false
  - id: D3
    description: "the batch window survives a mid-batch exception and a mid-batch revocation, disarming on both exits, exactly as the per-send window already did"
    requirement: D-60-06
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py#test_an_exception_mid_batch_propagates_and_the_window_still_disarms"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py#test_a_mid_batch_revocation_refuses_the_next_decision_but_the_window_still_disarms"
        status: pass
    human_judgment: false
  - id: D4
    description: "the batch window's own arm cannot trip preflight_before_send on the review lane; a live dispatch flag on that same workflow still trips it"
    requirement: D-60-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py#test_a_review_lane_preflight_does_not_trip_over_its_own_batch_arm"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant_guardrails.py#test_a_review_lane_preflight_still_closes_on_a_live_dispatch_flag"
        status: pass
    human_judgment: false

duration: ~14min
completed: 2026-09-01
status: complete
---

# Phase 60 Plan 02: Guardrail widening + one batch window for review triage Summary

**Guardrail A now reads all five overlayable write-safety constants (not four) so a stuck-open `ALLOW_HUBSPOT_REVIEW_WRITES` refuses the next grant by name, and `write_grant.authorize_review_batch` gives a triage sitting one arm/disarm round trip instead of one per decision — with `preflight_before_send` structurally unable to trip over that same batch window's own arm.**

## Performance

- **Duration:** ~14 min
- **Completed:** 2026-09-01T17:09:59+10:00
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- `write_grant.WRITE_ENABLING_FLAGS` widened from 2 items to 3, appending `"ALLOW_HUBSPOT_REVIEW_WRITES"` LAST (order load-bearing: `_live_write_faults` builds `live_flags` by iterating this tuple, and an existing test pins the exact pre-widening list for the armed-backend case)
- `read_live_write_state`'s per-lane read loop and `guardrail_a`'s flag-render expression both swapped from `n8n_arming.DISPATCH_FLAGS` (4) to `sorted(n8n_arming.OVERLAYABLE_FLAGS)` (5) — one list feeding both what the guardrail reads and what its refusal prints, so the two can never diverge
- Fixed the fixture breakage the widening legitimately causes: every four-constant gate builder driving `plan_grant`/`guardrail_a` gained a fifth `ALLOW_HUBSPOT_REVIEW_WRITES` constant (disarmed default) — the three plan-listed files plus two more discovered by running the full plugin suite exactly as the plan's own action text instructed (`test_chunking.py`, `test_unattended_pair_composition.py`), both of which started failing "its write-safety state could not be read at all" the moment the widening landed
- `write_grant.authorize_review_batch(grant)` added directly below `authorize_send`: returns the grant's own `record_ids`/`record_domains` — the one deliberate divergence from `authorize_send`, which refuses to return a record list on purpose — because D-60-06 makes the review window's allowlist the grant's whole batch scope, fixed at open time, never widened as records are triaged
- `preflight_before_send` narrowed on the review lane only: liveness there is evaluated over `WRITE_ENABLING_FLAGS` with the review flag excluded, derived from that same tuple (never a second literal), so Task 1's widening cannot make a mid-batch pre-flight read the batch window's own arm as a stuck-open authorization and disarm itself mid-sitting. A live DISPATCH flag on the review workflow still closes the grant exactly as before.
- 12 new tests added to `test_write_grant_guardrails.py`: 4 pinning the widened Guardrail A read (Task 1), 8 pinning the batch window's full lifecycle and the MEDIUM-1 pre-flight guard (Task 2) — including the "no existing test in this repo exercised a multi-decision single window for any lane" coverage gap the plan named explicitly

## Task Commits

Each task was committed atomically:

1. **Task 1: Teach Guardrail A to see a stuck-open review authorization** - `56d1143` (feat)
2. **Task 2: One batch window for a triage sitting** - `b3c2337` (feat)

**Plan metadata:** committed with this SUMMARY.

## Files Created/Modified
- `operator-claude-plugin/scripts/write_grant.py` — `WRITE_ENABLING_FLAGS` widened to 3 (dated D-60-01-consequence comment); `read_live_write_state`/`guardrail_a` read `sorted(OVERLAYABLE_FLAGS)`; `authorize_review_batch` added; `preflight_before_send` narrowed on the review lane with a dated MEDIUM-1 amendment in its own docstring
- `operator-claude-plugin/tests/test_write_grant_guardrails.py` — `_gate()`/`_workflow()` gained a fifth `review_writes` parameter and constant line; 12 new tests across two dated sections (Task 1's widened-guardrail-A cases, Task 2's D-60-06 batch-window section) plus review-lane fixture helpers (`_review_workflow`, `_armed_review_workflow`, `_review_workflow_list`, `_all_lanes_workflow_list`, `_open_review_grant`, `_put_body_jscode`)
- `operator-claude-plugin/tests/test_write_grant.py` — `_base_workflow` gained the fifth constant
- `operator-claude-plugin/tests/test_write_grant_surface.py` — `_base_workflow` gained the fifth constant
- `operator-claude-plugin/tests/test_chunking.py` — `_base_workflow` gained the fifth constant (deviation, see below)
- `operator-claude-plugin/tests/test_unattended_pair_composition.py` — `_base_workflow` gained the fifth constant (deviation, see below)

## Decisions Made
- Followed the plan's Task 1/Task 2 actions as written; no architectural deviations.
- `_put_body_jscode` helper added (not named in the plan) to read a recorded PUT's `jsCode` declaration lines directly rather than string-searching a `json.dumps` of the body — the JSON-escaped dump double-escapes the embedded quotes inside `jsCode` and never matches a plain substring search. Chosen over relaxing the assertion, since the plan's own acceptance criterion needs the allowlist literal actually verified in the PUT body.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Two more four-constant gate fixtures broke under the widened guardrail read, exactly as Task 1's action text anticipated**
- **Found during:** Task 1, running the plan's own required "run the whole plugin suite" step
- **Issue:** `test_chunking.py` and `test_unattended_pair_composition.py` each carry their own `_base_workflow()` builder (duplicated verbatim from `test_write_grant.py`'s, per that file's own comment — "sibling test modules importing each other is fragile under pytest's default import mode") that also drives `write_grant.plan_grant`/`guardrail_a`. Both declared only the four dispatch constants, so the widened read reported them `readable: False` and 4 tests started failing "its write-safety state could not be read at all" / refusing the whole grant.
- **Fix:** Added the fifth `ALLOW_HUBSPOT_REVIEW_WRITES` constant (disarmed default) to both fixtures, identical in shape to the fix already applied to the three plan-listed files.
- **Files modified:** `operator-claude-plugin/tests/test_chunking.py`, `operator-claude-plugin/tests/test_unattended_pair_composition.py`
- **Verification:** `operator-claude-plugin/tests -q` returned to 2149 passed / 5 skipped (from 4 failures) before Task 1's new tests were added; the plan's own action text explicitly authorizes this exact fix ("add the fifth constant to those too, and never loosen the `readable` check").
- **Committed in:** `56d1143`

---

**Total deviations:** 1 auto-fixed (1 blocking — the plan's own action text names this exact fix as the required response, so this is execution of an explicit instruction rather than an unplanned deviation in the usual sense; recorded here because the two files are outside the plan's declared `files_modified`).
**Impact on plan:** No scope creep — both fixture edits are the one-line addition Pitfall 2 describes, applied to two more instances of the same pre-existing pattern. No test was weakened, skipped, or deleted to reach green.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None - no external service configuration required. Nothing was armed, nothing was deployed, no HubSpot request and no provider call was made — every test drives `stub_module_transport_factory`/`stub_post_transport_factory` recorders, never a real transport.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/write_grant.py` — FOUND
- `operator-claude-plugin/tests/test_write_grant_guardrails.py` — FOUND
- `operator-claude-plugin/tests/test_write_grant.py` — FOUND
- `operator-claude-plugin/tests/test_write_grant_surface.py` — FOUND
- `operator-claude-plugin/tests/test_chunking.py` — FOUND
- `operator-claude-plugin/tests/test_unattended_pair_composition.py` — FOUND
- Commit `56d1143` — FOUND in `git log`
- Commit `b3c2337` — FOUND in `git log`
- `operator-claude-plugin/tests -q`: 2158 passed, 5 skipped (baseline 2145/5 at plan start)
- Root `pytest -q`: 3828 passed, 154 skipped (baseline 3815/154 at plan start)
- `node --test tests/n8n/*.test.mjs`: 848 pass, 0 fail (unchanged — this plan touches no JS/workflow JSON)
- `git status --porcelain n8n/` — empty
- Source assertion: `write_grant.WRITE_ENABLING_FLAGS[-1] == "ALLOW_HUBSPOT_REVIEW_WRITES"` and `len(...) == 3` — confirmed
- Source assertion: `grep -v '^#' write_grant.py | grep -c 'for flag in n8n_arming.DISPATCH_FLAGS'` — `0`
- Source assertion: `grep -c 'preflight_before_send' write_grant.py` — `3` (≥2 required)

## Next Phase Readiness
- Ready for 60-03 (written-records / review_decision.py — this plan touched neither, per the concurrency note).
- `write_grant.authorize_review_batch` and the narrowed `preflight_before_send` are available for 60-03/60-04 to build a triage-sitting caller on, with no further changes to the guardrail or batch-window machinery expected.
- No blockers. Nothing armed.

---
*Phase: 60-review-lane-authority*
*Completed: 2026-09-01*
