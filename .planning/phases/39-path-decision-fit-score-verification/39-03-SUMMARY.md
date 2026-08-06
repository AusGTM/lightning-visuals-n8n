---
phase: 39-path-decision-fit-score-verification
plan: 03
subsystem: infra
tags: [hubspot-api, requests, pytest, tdd, disposable-probe]

requires:
  - phase: 39-01
    provides: "feat/v0.7-scoring-remediation branch; tests/test_scoring_probe_helpers.py scaffold; two-key/portal-guard gate triad precedent"
provides:
  - "src/hubspot_client.py::delete_record() — the fifth thin CRUD wrapper, dry-run-safe by default"
  - "scripts/probe_scoring_recalc_latency.py — two-key-gated disposable-company recalc-latency probe (D-03/D-04)"
  - "9 additional unit tests in tests/test_scoring_probe_helpers.py (3 delete_record, 9 pure latency helpers... see coverage below)"
affects: [39-04-decision-record]

actuals:
  tokens: 4630
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Median-of-3 latency measurement as a pure, unit-tested function (statistics.median), never inlined into a live polling loop"
    - "Fixed-boundary band classification (a/b/c) as a pure function with inclusive upper edges, tested one step either side of each edge"
    - "Guaranteed-teardown try/finally wrapping a disposable live-API artifact's lifecycle, independent of measurement success/failure"

key-files:
  created:
    - scripts/probe_scoring_recalc_latency.py
  modified:
    - src/hubspot_client.py
    - tests/test_scoring_probe_helpers.py

key-decisions:
  - "FLIP_PROPERTY_NAME chosen as lv_org_type: the plan left the scoring-input property to flip unspecified (any trivial rubric line works, per D-03/39-04), but the orchestration needs one concrete, generic property. lv_org_type is the property named in 39-04-PLAN.md Task 1's own example criterion ('lv_org_type is known'), is already taxonomy-controlled in this repo, and needs no operator input to pick a valid in-vocab flip value — reuses the same taxonomy.DEFAULT_ORG_TYPE / taxonomy.ORG_TYPES pattern probe_org_type_migration.py already established for exactly this kind of disposable in-vocab/out-of-vocab pairing."
  - "DECIDE-01 is NOT marked complete in REQUIREMENTS.md by this plan — same rationale as 39-01: it is the single requirement spanning all 4 plans of Phase 39, satisfied only once 39-DECISION.md lands in plan 39-04."

patterns-established:
  - "Fifth CRUD wrapper convention: delete_record(object_type, record_id, dry_run=True) matches create_record/patch_record's exact shape — dry-run short-circuits before any network call, prints only method+url (never headers/token), returns {\"dry_run\": True}; live branch returns the raw response object (not .json()) since HubSpot's 204 delete has no body."

requirements-completed: []

coverage:
  - id: D1
    description: "delete_record() added to src/hubspot_client.py, dry-run-safe by default, matching the existing four wrappers' signature convention exactly (TDD: RED test committed before GREEN implementation)."
    requirement: DECIDE-01
    verification:
      - kind: unit
        ref: "tests/test_scoring_probe_helpers.py::test_delete_record_dry_run_default_makes_no_network_call_and_prints_no_auth, test_delete_record_dry_run_explicit_true_matches_default, test_delete_record_live_calls_requests_delete_and_returns_response"
        status: pass
      - kind: other
        ref: "grep -c 'def delete_record' src/hubspot_client.py == 1; grep -c 'requests.delete' src/hubspot_client.py == 1; inspect.signature shows dry_run default True"
        status: pass
    human_judgment: false
  - id: D2
    description: "median_latency, classify_latency_band, find_score_property_name landed as pure functions in scripts/probe_scoring_recalc_latency.py, each tested one step either side of every D-04 band boundary (600.0/600.1, 3600.0/3600.1) plus the None-is-c and negative-raises edge cases (TDD: RED test committed before GREEN implementation)."
    requirement: DECIDE-01
    verification:
      - kind: unit
        ref: "tests/test_scoring_probe_helpers.py — 9 new tests covering median odd-count/noisy-sample/empty, band a/b/c edges (both sides), None->c, negative->raises, find_score_property_name found/absent"
        status: pass
      - kind: other
        ref: "grep -c constants in scripts/probe_scoring_recalc_latency.py == 5 (BAND_A_MAX_SECONDS, BAND_B_MAX_SECONDS, POLL_INTERVAL_SECONDS, POLL_TIMEOUT_SECONDS, SAMPLE_COUNT)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Two-key-gated (DRY_RUN=false AND ALLOW_HUBSPOT_SCORING_PROBE=true) disposable-company probe orchestration: precondition hard-fail on missing score property (exit 2), create/flip/poll/median/classify, guaranteed teardown (try/finally) deleting the disposable company and asserting 204, evidence JSON with an explicit measurement_contract."
    requirement: DECIDE-01
    verification:
      - kind: other
        ref: "env -u HUBSPOT_PRIVATE_APP_TOKEN .venv/bin/python scripts/probe_scoring_recalc_latency.py -> exit 0, prints 'skipped', no HTTP call"
        status: pass
      - kind: other
        ref: "HUBSPOT_PRIVATE_APP_TOKEN=dummy HUBSPOT_PORTAL_ID=99999999 -> exit 1, prints 'REFUSED', no HTTP call"
        status: pass
      - kind: other
        ref: "HUBSPOT_PRIVATE_APP_TOKEN=dummy HUBSPOT_PORTAL_ID=22617666 (not armed) -> exit 0, prints both DRY_RUN and ALLOW_HUBSPOT_SCORING_PROBE"
        status: pass
      - kind: other
        ref: "grep -c 'ALLOW_HUBSPOT_SCORING_PROBE' >= 2 (5 hits); grep -c 'ALLOW_HUBSPOT_PROPERTY_WRITES' == 0; grep -c 'time.monotonic' >= 2 (3 hits); grep -c 'delete_record' >= 1, inside try/finally; grep -c 'COMPANY_NAME_PREFIX' >= 2 (3 hits), no argparse/getenv override"
        status: pass
    human_judgment: true
    rationale: "The armed live path (creating/flipping/deleting a real disposable company against portal 22617666 and measuring actual recalc latency) is deliberately not exercised by this executor session — .env is Read/Bash permission-blocked, and per this plan's environment notes the armed run is explicitly reserved for plan 39-04 with the operator driving it after building a scoring criterion in-portal. Only the disarmed gate paths and pure functions are verifiable here."

duration: 8min
completed: 2026-08-06
status: complete
---

# Phase 39 Plan 03: Recalc-Latency Probe (delete_record + pure helpers + orchestration) Summary

**Added the missing `delete_record()` HubSpot client primitive and a two-key-gated `scripts/probe_scoring_recalc_latency.py` that creates a disposable company, times three property-flip-to-recalc round trips with a monotonic clock, bands the median against D-04's fixed a/b/c edges, and guarantees teardown even on failure — all built and unit-tested without ever touching a live HubSpot record.**

## Performance

- **Duration:** ~8 min (git commit span; read-first context gathering not counted)
- **Started:** 2026-08-06 (continuation from 39-01/39-02 on feat/v0.7-scoring-remediation)
- **Completed:** 2026-08-06T13:27:19+10:00
- **Tasks:** 3 (Task 1 and Task 2 both TDD; Task 3 orchestration, non-TDD per plan)
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments
- `delete_record(object_type, record_id, dry_run=True)` lands in `src/hubspot_client.py`, the one genuinely missing primitive research identified — matches `create_record`/`patch_record`'s exact dry-run-first, no-token-echo shape, returns the raw response object on the live path since HubSpot's 204 delete has no JSON body.
- `median_latency`, `classify_latency_band`, `find_score_property_name` land as pure, network-free functions in `scripts/probe_scoring_recalc_latency.py`, with the D-04 band edges (600s, 3600s) tested one step either side of each boundary so no future reader has to interpret where a boundary sits.
- The full two-key-gated orchestration (`main()`) lands: credential gate → portal gate → arming gate → hard-fail precondition (no score property = exit 2, never poll a property that can't change) → create disposable company → flip×3/poll/median → guaranteed-teardown delete with a 204 assertion → PASS/FAIL print, mirroring `scripts/rollback_canary_proof.py`'s convention exactly.
- All three disarmed-invocation paths (no credentials, wrong portal, not two-key armed) verified live in this session: correct exit codes, correct printed markers, zero HTTP calls attempted.

## Task Commits

1. **Task 1: Add delete_record() — the one missing client primitive** (TDD):
   - RED: `b90ef8a` — `test(39-03): add failing tests for delete_record()`
   - GREEN: `93296de` — `feat(39-03): add delete_record() — the missing CRUD wrapper`
2. **Task 2: Pure latency helpers — median, band classification, score-property discovery** (TDD):
   - RED: `3635eef` — `test(39-03): add failing tests for latency probe pure helpers`
   - GREEN: `d4b32f9` — `feat(39-03): pure latency helpers — median, D-04 band classification, score-property discovery`
3. **Task 3: Two-key-gated disposable-company probe orchestration** (auto, non-TDD per plan):
   - `9d0a7ea` — `feat(39-03): two-key-gated disposable-company recalc-latency probe orchestration`

**Plan metadata:** commit follows this SUMMARY (see final commit below).

## Files Created/Modified
- `src/hubspot_client.py` - Added `delete_record()`, the fifth thin CRUD wrapper.
- `scripts/probe_scoring_recalc_latency.py` - New: module docstring, gate triad, module constants (band edges, poll interval/timeout, sample count, disposable-artifact prefix, flip-property choice), 3 pure functions, network orchestration (`_list_company_properties`, `_disposable_company_name`, `_run_one_sample`), and `main()`.
- `tests/test_scoring_probe_helpers.py` - Added 12 new tests: 3 for `delete_record` (dry-run default, dry-run explicit, live), 9 for the pure latency helpers (median odd-count/noisy-sample/empty, band edges both sides of both boundaries, None→c, negative→raises, score-property-name found/absent).

## Decisions Made
- **`FLIP_PROPERTY_NAME = "lv_org_type"`** — the plan deliberately left the scoring-input property to flip unspecified (D-03/39-04: "any trivial rubric line works"), since only the operator's in-portal criterion determines what's evaluable. `lv_org_type` is the property named in 39-04-PLAN.md Task 1's own example criterion (`lv_org_type is known`), is already taxonomy-controlled in this repo (`src/taxonomy.py`), and needs no operator input to derive a valid initial/target value pair — reuses `taxonomy.DEFAULT_ORG_TYPE` / `taxonomy.ORG_TYPES` exactly the way `scripts/probe_org_type_migration.py` already does for its own in-vocab/out-of-vocab probe values. A module constant, no CLI/env override, consistent with the plan's disposable-artifact-naming discipline for `COMPANY_NAME_PREFIX`.
- **DECIDE-01 left unmarked in REQUIREMENTS.md** — same rationale carried from 39-01: the requirement spans all 4 plans of Phase 39 and completes only when `39-DECISION.md` lands in plan 39-04.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed a literal `ALLOW_HUBSPOT_PROPERTY_WRITES` string from the module docstring**
- **Found during:** Task 3 verification (acceptance criterion: `grep -c 'ALLOW_HUBSPOT_PROPERTY_WRITES' scripts/probe_scoring_recalc_latency.py` must output 0)
- **Issue:** The module docstring explained *why* the phase-scoped flag was chosen by naming the generic flag it was deliberately distinct from — but naming it literally violated the plan's own verification rule (`<verification>`: "No script in this plan references ALLOW_HUBSPOT_PROPERTY_WRITES"), which exists specifically so a stale flag from a migration script can never be mistaken for arming this probe.
- **Fix:** Reworded the docstring sentence to describe the distinction without spelling out the other flag's literal name.
- **Files modified:** `scripts/probe_scoring_recalc_latency.py`
- **Verification:** `grep -c 'ALLOW_HUBSPOT_PROPERTY_WRITES' scripts/probe_scoring_recalc_latency.py` now outputs 0; full suite still green.
- **Committed in:** `9d0a7ea` (folded into the Task 3 commit — caught before that commit was made)

---

**Total deviations:** 1 auto-fixed (Rule 1, self-caught during acceptance verification before commit)
**Impact on plan:** No scope creep. The fix was a docstring wording change with no code-behavior impact, caught by the plan's own acceptance grep before the commit landed.

## Issues Encountered
None beyond the deviation above. The module docstring (arming requirement, operator invocation one-liner, what the probe measures vs. the criteria-edit bulk recalc) was written in full during Task 2's file creation rather than deferred to Task 3 as the plan's task split implied — a harmless implementation-order choice, since Task 3's acceptance criteria only check the docstring's *content* (which was already correct), not which task's diff introduced it.

## User Setup Required
None for this plan. The armed live run (Task 3's actual measurement against portal 22617666) requires the operator to first build one trivial scoring criterion in-portal — that is plan 39-04's Task 1, a `checkpoint:human-verify`, not this plan's responsibility. This plan's environment notes explicitly scoped this session to disarmed/unit-tested work only.

## Next Phase Readiness
- `delete_record()`, `median_latency`, `classify_latency_band`, `find_score_property_name`, and the full two-key-gated `main()` orchestration are all built, unit-tested, and verified disarmed — ready for plan 39-04 to invoke live.
- 39-04's exact operator invocation command (`ALLOW_HUBSPOT_SCORING_PROBE=true DRY_RUN=false .venv/bin/python -c "..."`) is carried verbatim in this script's module docstring, matching the `.env`-in-process convention documented in `39-RESEARCH.md`.
- **Outstanding:** the operator must build one trivial company-fit-score criterion in the lead-scoring tool (Settings → Account & Billing → Products & Add-ons) before running the probe live — the precondition check (Step 4 of `main()`) will hard-fail with exit code 2 and a clear message if that hasn't happened yet.

---
*Phase: 39-path-decision-fit-score-verification*
*Completed: 2026-08-06*

## Self-Check: PASSED
All created/modified files found on disk. All 5 task commit hashes found in git log.
