# Phase 31 Plan 03 — Findings

**Written:** 2026-08-03 (Task 1 automated; Task 2 pending operator gate)

## Task 1 — contract inventory (automated, complete)

`tests/test_phase31_two_sided_contracts.py` created. `PHASE_31_CONTRACTS` names the five
rows the plan specifies; three tests: row-shape guard, pin-existence-and-non-empty guard,
side-file-existence guard.

Fail-on-drift demonstrated live: moved `tests/test_hubspot_enums_generated_currency.py`
out of `tests/` → `test_every_pin_named_in_the_table_exists_on_disk_and_is_non_empty`
failed naming the missing file → restored → passed again.

Closing gate, run before the commit:

| Check | Result |
|---|---|
| `.venv/bin/python -m pytest tests/test_phase31_two_sided_contracts.py operator-claude-plugin/tests/test_control_disarmed_artifacts.py -q` | 26 passed, 5 skipped |
| `.venv/bin/python -m pytest -q` (full suite) | 1700 passed, 6 skipped (pre-phase baseline 1697 passed, 6 skipped — net +3) |
| `node --test tests/n8n/*.test.mjs` (full suite) | 550 pass, 0 fail (unchanged from pre-phase baseline) |
| `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` | 0 across all files |

Note (plan-path inaccuracy, same as 31-01/31-02): the plan's `<verify>` names
`tests/test_control_disarmed_artifacts.py`; the real path is
`operator-claude-plugin/tests/test_control_disarmed_artifacts.py` (root `pytest -q`
already collects it, confirmed unaffected — 23 passed / 5 skipped standalone).

Commit: `7654034` — `test(31-03): inventory the phase's five two-sided contracts`.

## Task 2 — operator gate: disarmed redeploy and bounce

**Status: TO-BE-OBSERVED.** The steps below are not automated — they require the
operator's own shell with `.env` sourced and `N8N_EXPECTED_URL` pinned to the tenant.
This agent does not read `.env` and does not run any of these commands itself.

### Step 1 — starting state (read-only)

- Command: `.venv/bin/python scripts/verify_live_write_safety.py --expectation disarmed`
- Expected verdict: `disarmed PASS`
- **Verdict observed:** TO-BE-OBSERVED
- **Declaring-node count (before):** TO-BE-OBSERVED

### Step 2 — record active workflow set (before)

- **Active workflows (before):** TO-BE-OBSERVED

### Step 3 — disarmed deploy

- Command: `scripts/deploy_n8n_workflows.py` (no `ENABLE_BAKED_FLAGS`, no arming variable)
- Expected: `200` per workflow
- **Result:** TO-BE-OBSERVED

### Step 4 — bounce every workflow active in step 2

- Deactivate then activate each; each pair expected `200`
- **Result:** TO-BE-OBSERVED

### Step 5 — read back (after)

- Command: `.venv/bin/python scripts/verify_live_write_safety.py --expectation disarmed`
- Expected verdict: `disarmed PASS`, declaring-node count >= step 1's count (31-02 added
  one declaring node to `wf_review_decision_cloud.json`'s `Build Review Decision`)
- **Verdict observed:** TO-BE-OBSERVED
- **Declaring-node count (after):** TO-BE-OBSERVED

### Step 6 — active set comparison

- **Active workflows (after):** TO-BE-OBSERVED
- **Matches step 2 exactly:** TO-BE-OBSERVED

### Anything that did not match the prediction

TO-BE-OBSERVED

### Out of scope for this task

Re-running RB-9 step 8 needs a FRESH `needs_review` fixture — company `9604614548` was
cleared manually 2026-08-03. That re-run is RB-9's business, not this task's; this task
is complete at step 6.
