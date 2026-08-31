---
phase: 57-ceilings-refusal-before-start-and-post-run-proof
plan: 04
subsystem: testing
tags: [zoominfo, apollo, cost_guard, write_grant, backend_status, pytest, n8n]

requires:
  - phase: 57-ceilings-refusal-before-start-and-post-run-proof
    provides: "D-57-02's tri-state honesty requirement (an unreadable balance is `unknown`, never headroom) and the RUN-05/AFTER prohibition on unattended spend against an unread balance"
provides:
  - "A disarmed, gated live probe (scripts/prove_zoominfo_balance.py) whose network abstinence is proved by test rather than asserted"
  - "A recorded live verdict for G-4's ZoomInfo half: readable, 9381 raw credits, zero measured Lusha delta"
  - "Three distinguishable unreadable-balance-cause fixtures (http_403, provider_error, unrecognized_response_shape) and regression tests pinning that none of the three can render as headroom, a zero, or a default"
affects: ["57-05"]

actuals:
  tokens: 7182
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Gate-by-injectable-transport: a probe script's entry point takes an injectable transport so a test can assert ZERO calls reached it, rather than reading source for a gate's text"
    - "Cause-distinguishing fixtures: three separate pytest fixtures (http_403 / provider_error / unrecognized_response_shape) instead of one generic 'unreadable' fixture, because the three causes imply three different fixes"

key-files:
  created:
    - scripts/prove_zoominfo_balance.py
    - operator-claude-plugin/tests/test_prove_zoominfo_balance.py
    - .planning/phases/57-ceilings-refusal-before-start-and-post-run-proof/57-ZOOMINFO-BALANCE-VERDICT.json
  modified:
    - operator-claude-plugin/tests/conftest.py
    - operator-claude-plugin/tests/test_cost_guard.py

key-decisions:
  - "Task 2 checkpoint: operator selected option-run. The probe was invoked once, live, against the deployed instance."
  - "No code fix was written for either provider. Apollo's http_403 is a permanent structural fact (non-master key); ZoomInfo's live verdict came back `readable`, so there was nothing to fix — writing a fix before observing would have risked patching a cause the current code had already removed (the missing Accept header fix predates this phase)."
  - "Added a third fixture, backend_status_zoominfo_unrecognized_response_shape, beyond the two the behavior section named, because the plan invited it ('three causes with three different fixes deserve three fixtures') and it cost one more _balance() call."

requirements-completed: [G-4]

coverage:
  - id: D1
    description: "A disarmed ZoomInfo balance probe exists whose gate (ALLOW_ZOOMINFO_BALANCE_PROBE read as the exact string \"true\") and instance guard are proved by zero calls reaching an injected transport double, not by a string/AST check"
    requirement: G-4
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_prove_zoominfo_balance.py -q"
        status: pass
    human_judgment: false
  - id: D2
    description: "The live probe was run once against the deployed instance under the operator's option-run selection; the verdict (readable, 9381 raw credits, zero measured Lusha delta) is recorded on disk and mapped to the G-4 closure table's CLOSED row"
    requirement: G-4
    verification:
      - kind: manual_procedural
        ref: "57-ZOOMINFO-BALANCE-VERDICT.json (live artifact, single non-repeatable invocation)"
        status: pass
    human_judgment: true
    rationale: "A live network observation against a production instance cannot be re-verified by an automated test without repeating the live call the plan explicitly gates behind a human decision."
  - id: D3
    description: "The three unreadable-balance causes (http_403 refused, provider_error transport-errored, unrecognized_response_shape body-unparseable) are distinguishable in fixtures and in cost_guard's tri-state, and none of them ever renders as headroom, a zero, or a default"
    requirement: G-4
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_cost_guard.py -q"
        status: pass
    human_judgment: false

duration: unknown (continuation across two agent sessions; Task 3 alone was a single short session)
completed: 2026-08-31
status: complete
---

# Phase 57 Plan 04: ZoomInfo balance probe, checkpoint decision, and cause-discrimination fixtures Summary

**A disarmed, test-proved live probe observed ZoomInfo's balance as readable (9381 credits, zero measured spend), closing G-4's ZoomInfo half by observation with no code fix, and three unreadable-balance causes are now regression-pinned as distinct in the cost/write tri-state.**

## Performance

- **Tasks:** 3 (Task 1 by a prior agent, Task 2 executed by the orchestrator between agent sessions, Task 3 by this continuation agent)
- **Files modified:** 5 (2 created by Task 1, 1 verdict artifact from Task 2, 2 modified by Task 3)
- **Commits:** 3

## Accomplishments

- **Task 1:** `scripts/prove_zoominfo_balance.py` — a gated, injectable-transport probe whose zero-network-call abstinence on every refusal path (gate absent, gate truthy-but-not-`"true"`, wrong instance) is proved by a test double under the `no_network` fixture, and whose gate-on path is pinned to exactly two status POSTs to one host (the probe read, then the immediate re-read supplying `lusha_after`).
- **Task 2 (checkpoint, already executed before this session):** operator selected **option-run**. The probe was invoked once against the deployed instance. **Verdict, recorded verbatim in `57-ZOOMINFO-BALANCE-VERDICT.json`:**

  ```json
  {
    "premise": "zoominfo-balance-probe",
    "verdict": "readable",
    "zoominfo_raw_credits": 9381,
    "zoominfo_http_status_present": false,
    "zoominfo_http_status": null,
    "zoominfo_error": null,
    "checked_at": "2026-08-31T07:15:27.490088+00:00",
    "instance_host": "alexherman.app.n8n.cloud",
    "lusha_before": 3894,
    "lusha_after": 3894,
    "lusha_delta": 0,
    "lusha_after_cost_unmeasured": true,
    "lusha_after_cost_unmeasured_reason": "Request #2 exists only to supply lusha_after; its own credit cost is not measured, because measuring it would need a third read, whose cost would need a fourth, and so on. lusha_delta measures request #1's (the probe's) cost only, not the full two-request run."
  }
  ```

  **G-4 closure-table row: `readable` — CLOSED.** One of two provider balances (ZoomInfo) now reads; Apollo's `http_403` remains disclosed as a permanent, structural blind spot no code change in this repo can remove. The 2026-08-25 walk's `provider_error` observation is gone — the missing `Accept: application/vnd.api+json` header fix already in current code was, in fact, the cause, and no further code change was needed or written.

  One operational note for the next `prove_*` invocation: the first attempt refused with "instance guard refused: `N8N_URL` does not match the expected instance" — correct fail-closed behaviour, not a defect. `_instance_ok()` reads the `N8N_URL` environment variable (mirroring `deploy_n8n_workflows.py` and `prove_async_recovery.py`), and it was not exported in the shell. The successful re-run exported `N8N_URL` from `config_gate.load_config()['n8n_url']` — the same value the request itself uses — so the guard checked exactly the instance that was then contacted.

- **Task 3:** Two new `conftest.py` fixtures — `backend_status_zoominfo_provider_error` and `backend_status_zoominfo_unrecognized_response_shape` — join the existing Apollo `http_403` fixture, each mirroring the real node logic (`ENRICH_STATUS_BUILD_RESPONSE`'s `error = status ? ("http_" + status) : "provider_error"` branch, and `backendStatus.js`'s `deriveSourceHealth` per-status-shape derivation) rather than an invented shape. Seven new tests in `test_cost_guard.py` pin that `cost_guard.compare()` returns `unknown` (never `ok`/`insufficient`) carrying the cause-specific reason for all three fixtures, that `remaining_credits` is always `None` (never `0`), and that `write_grant._headroom()` renders `unconfirmed` for every one of them.

## Task Commits

1. **Task 1: A disarmed ZoomInfo balance probe, gate proved by absence of network calls** — `d549b5b` (feat) — completed by a prior agent
2. **Task 2: Run the probe live, or decline (checkpoint)** — `92b3557` (docs) — verdict artifact committed by this agent after the orchestrator executed the checkpoint
3. **Task 3: Tell the two unreadable-balance causes apart in fixtures and in the tri-state** — `7b06b8b` (test)

No separate plan-metadata commit was required beyond the above; this SUMMARY and STATE/ROADMAP updates are captured in the final metadata commit.

## Files Created/Modified

- `scripts/prove_zoominfo_balance.py` — the gated, injectable-transport live probe (Task 1)
- `operator-claude-plugin/tests/test_prove_zoominfo_balance.py` — zero-network-call and two-request-protocol tests (Task 1)
- `.planning/phases/57-ceilings-refusal-before-start-and-post-run-proof/57-ZOOMINFO-BALANCE-VERDICT.json` — the live verdict (Task 2)
- `operator-claude-plugin/tests/conftest.py` — added `backend_status_zoominfo_provider_error` and `backend_status_zoominfo_unrecognized_response_shape` fixtures (Task 3)
- `operator-claude-plugin/tests/test_cost_guard.py` — added the three-cause discrimination test suite (Task 3)

## Decisions Made

- Operator selected **option-run** at the Task 2 checkpoint: the live probe was worth the two status reads to settle G-4's ZoomInfo half by observation rather than ship another milestone on a nine-day-old walk note.
- No production code was changed for either provider. Apollo's `http_403` is a permanent structural fact outside this repo's control; the live ZoomInfo verdict came back `readable`, so D-57-02's disclosure-not-guess-a-fix instruction meant there was nothing to patch — the already-shipped `Accept` header fix (`build_cloud_workflows.py:4614-4630`) is confirmed sufficient by the observation itself.
- A third fixture (`unrecognized_response_shape`) was added beyond the plan's two-fixture minimum, since `<action>` explicitly invited it ("three causes with three different fixes deserve three fixtures") and it cost one additional `_balance()` call plus one additional test.

## Deviations from Plan

None that changed scope. One acceptance-criterion command in Task 3 does not behave as literally written, pre-existing and unrelated to this task's changes:

- `.venv/bin/python -m pytest operator-claude-plugin/tests -k backend_status_unknown_balance -q` returns pytest exit code 5 ("no tests collected"), both before and after this task's changes (verified via `git stash`) — `-k` filters on test *node names*, and `backend_status_unknown_balance` is a fixture name used as a test *parameter*, not a substring of any existing test function name. No test currently in the suite has that string in its name. This is a pre-existing imprecision in how the acceptance criterion was phrased, not a regression: the underlying intent — "the existing Apollo disclosure cover is unbroken" — is verified instead by the full plugin suite (`operator-claude-plugin/tests -q`: 1941 passed / 5 skipped, up from the prior baseline of 1935 passed / 5 skipped, the +6 being this task's new tests) and by `test_provider_error_and_http_403_are_distinguishable_error_labels`, which reads the Apollo fixture's `error` field directly and asserts it is still `"http_403"`.

## Issues Encountered

None during Task 3. Task 1/Task 2's operational note (the `N8N_URL` export requirement for the instance guard) is recorded above under Accomplishments rather than here, since it was correct fail-closed behaviour rather than a problem.

## Verification Results

- `.venv/bin/python -m pytest operator-claude-plugin/tests/test_cost_guard.py -q` — 36 passed
- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — 1941 passed, 5 skipped
- `.venv/bin/python -m pytest -q` (root suite) — 3605 passed, 154 skipped
- `node --test tests/n8n/*.test.mjs` — 844/844 passed
- `git diff --stat operator-claude-plugin/scripts/` — empty (no production module changed by Task 3)
- `grep -c "backend_status_zoominfo_provider_error" operator-claude-plugin/tests/conftest.py` — 1

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

G-4 is closed per the objective's closure table (`readable` row): both provider balances that were previously unreadable now have a clear, disclosed status — Apollo permanently (`http_403`, structural, outside this repo), ZoomInfo by direct live observation (`readable`, no fix needed). 57-05 can rely on `cost_guard`/`write_grant`'s tri-state distinguishing all three unreadable-balance causes when it builds the post-run report. Nothing further in this plan arms a write, dispatches an enrichment, or spends a provider credit beyond the two measured status reads already recorded in the verdict.

## Self-Check: PASSED

All created/modified files confirmed on disk; all three commits (`d549b5b`, `92b3557`, `7b06b8b`) confirmed in `git log --oneline --all`.

---
*Phase: 57-ceilings-refusal-before-start-and-post-run-proof*
*Plan: 04*
*Completed: 2026-08-31*
