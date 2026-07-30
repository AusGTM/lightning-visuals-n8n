---
phase: 22-armed-e2e-enrichment-canary
plan: 02
subsystem: infra
tags: [n8n, hubspot, write-safety, read-back, canary]

requires:
  - phase: 22-armed-e2e-enrichment-canary
    provides: "Plan 01's read-only HubSpot snapshot/compare tool and cost-ledger token extraction, and its committed pre-canary live snapshot"
provides:
  - "scripts/verify_live_write_safety.py — read-only live read-back verifier with disarmed (default) and armed expectations, checking both write-decision Code nodes at once"
  - "A proven-green live disarmed baseline against the current deployment, recorded verbatim below"
affects: [22-03, 22-04]

tech-stack:
  added: []
  patterns:
    - "Checked-constant-set imported directly from the overlay's own spec (deploy_n8n_workflows._OVERLAY_FLAG_SPEC), pinned equal by test — the overlay and its read-back can never drift apart"
    - "Per-node, per-constant report always printed before the verdict, so an operator can read what the live artifact says even on a pass — same convention as verify_live_lusha_urls.py"

key-files:
  created:
    - scripts/verify_live_write_safety.py
    - tests/test_verify_live_write_safety.py
  modified: []

key-decisions:
  - "Armed expectation checks the live allowlist as whichever of TEST_RECORD_IDS/TEST_RECORD_DOMAINS is non-empty on that node, compared against the single --allowlist value the operator expects — matches how the canary only ever arms one allowlist constant at a time (per 22-RESEARCH.md's arm command form)"
  - "verify() is a pure function over an already-fetched workflow dict, fully offline-testable; main() only adds the live fetch, argument parsing, and printing — same separation as verify_live_lusha_urls.py"
  - "A missing write-decision node or a node missing one of the four constants is an explicit reason string in the report, never a raised exception — the same fail-closed-but-never-crash contract as check_provider_credits.py's extractors"

patterns-established:
  - "Third live-read-back verifier in this repo following the same shape (skip-to-exit-0 on missing creds, pure verify() over a fetched dict, single greppable VERDICT line, --json for machine-readable evidence)"

requirements-completed: [REQ-armed-e2e-canary]

coverage:
  - id: D1
    description: "Read-only live write-safety verifier reads both write-decision Code nodes (Decide Action, Decide Company Action) and reports a disarmed or armed verdict over all four write-safety constants per node"
    requirement: "REQ-armed-e2e-canary"
    verification:
      - kind: unit
        ref: "tests/test_verify_live_write_safety.py -q (15 tests: disarmed pass/fail, armed pass/fail, missing-node/missing-constant, spec parity, CLI refusal, output-discipline, no-creds skip)"
        status: pass
      - kind: integration
        ref: "live disarmed run against the deployed LV Enrichment (Cloud template) workflow — verbatim output quoted below"
        status: pass
    human_judgment: false
  - id: D2
    description: "The verifier's checked constant set is pinned equal to deploy_n8n_workflows._OVERLAY_FLAG_SPEC's key set so the overlay and its read-back cannot silently drift apart"
    requirement: "REQ-armed-e2e-canary"
    verification:
      - kind: unit
        ref: "tests/test_verify_live_write_safety.py::test_checked_constants_match_overlay_spec"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-30
status: complete
---

# Phase 22 Plan 02: Live write-safety read-back verifier Summary

**One command reads the live enrichment workflow's two write-decision nodes and refuses to call the run disarmed or armed unless all eight write-safety literals across both lanes agree — proven green against the current deployment before anything is armed.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-30T08:41:28Z
- **Tasks:** 2/2 completed
- **Files modified:** 2 created (scripts/verify_live_write_safety.py, tests/test_verify_live_write_safety.py)

## Accomplishments

- Built `scripts/verify_live_write_safety.py`, a read-only live read-back verifier that reports, per write-decision node (`Decide Action` for contacts, `Decide Company Action` for companies), the live literal values of `ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`, `TEST_RECORD_IDS`, and `TEST_RECORD_DOMAINS`, against a disarmed (default) or armed expectation.
- Disarmed passes only when both nodes carry both write flags disabled and both allowlist constants empty; a single still-enabled flag or a single leftover allowlist value fails the check, naming the offending node.
- Armed passes only when record writes read enabled on both nodes, the requested allowlist value is present on both, and the create flag still reads disabled on both — an over-armed create flag fails regardless of everything else.
- The checked constant set is imported directly from `scripts/deploy_n8n_workflows.py`'s `_OVERLAY_FLAG_SPEC` and pinned equal to it by test, so the overlay and its read-back can never silently diverge.
- Ran the verifier live in its disarmed expectation against the deployed `LV Enrichment (Cloud template)` workflow: **the resting deployment reads clean today** — both nodes report all four constants disabled/empty, closing the loop this whole plan exists to prove (see verbatim output below).

## Task Commits

Each task was committed atomically:

1. **Task 1: The live write-safety read-back verifier, with armed and disarmed expectations** - `4ee6704` (feat)
2. **Task 2: Live baseline — prove the disarmed expectation passes against the current deployment** - no code change; the live run itself is the deliverable, recorded verbatim below (per the plan, this task's file scope is the same script, unmodified)

**Plan metadata:** committed with this SUMMARY (docs: complete plan)

_Note: Task 2 is a live-only verification step per the plan — it produces evidence, not a diff, so there is no separate commit beyond this SUMMARY._

## Files Created/Modified

- `scripts/verify_live_write_safety.py` - read-only live read-back verifier; disarmed/armed expectations over both write-decision Code nodes
- `tests/test_verify_live_write_safety.py` - 15 offline tests covering the full behaviour table, spec parity, CLI refusal, output discipline, and the no-credentials skip

## Decisions Made

- Armed expectation resolves the "live allowlist" as whichever of `TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS` is non-empty on a given node, compared against the single `--allowlist` value supplied — this matches the canary's own arm command form (`ENABLE_BAKED_FLAGS="ALLOW_HUBSPOT_RECORD_WRITES,TEST_RECORD_IDS=<id>"`, per `22-RESEARCH.md` Pattern 1), which only ever arms one allowlist constant per invocation.
- `verify()` stays pure over an already-fetched workflow dict (no network), matching `verify_live_lusha_urls.py`'s separation, so the whole behaviour table is testable offline with hand-built minimal workflow dicts rather than the full committed `n8n/wf_enrichment_cloud.json` fixture.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. This plan's live step (Task 2) is a read-only GET, already covered by the existing n8n Cloud credentials this repo's other live scripts use.

## Live Disarmed Baseline (Task 2 evidence)

Command run (in-process dotenv wrapper, per the established idiom):

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')"
```

Verbatim output:

```
workflow: 'LV Enrichment (Cloud template)'
expectation: disarmed
node 'Decide Action': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS=''
node 'Decide Company Action': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS=''
VERDICT: disarmed PASS
```

Exit code: `0`.

**Finding: none.** The resting deployment is genuinely disarmed today — both write-decision nodes (contacts lane `Decide Action` and companies lane `Decide Company Action`) report `ALLOW_HUBSPOT_RECORD_WRITES=false`, `ALLOW_HUBSPOT_CREATE=false`, `TEST_RECORD_IDS=""`, and `TEST_RECORD_DOMAINS=""`. This establishes the pre-canary baseline: a post-canary failure of this same command in a later plan is unambiguously caused by that canary's arming, not by pre-existing drift.

## Next Phase Readiness

The armed window now has a mechanical closing gate proven green against the live deployment before anything is armed. Plan 03/04 (the operator runbook and the armed fire itself) can cite this exact command and its passing baseline as the "before" read-back, and re-run it after the canary's disarm step as the "after" read-back — per `22-RESEARCH.md` Pattern 2 and the roadmap's closing criterion ("the run closes disarmed and audited"). No blockers.

## Self-Check: PASSED

- `scripts/verify_live_write_safety.py` — FOUND
- `tests/test_verify_live_write_safety.py` — FOUND
- commit `4ee6704` — FOUND in `git log --oneline --all`

---
*Phase: 22-armed-e2e-enrichment-canary*
*Completed: 2026-07-30*
