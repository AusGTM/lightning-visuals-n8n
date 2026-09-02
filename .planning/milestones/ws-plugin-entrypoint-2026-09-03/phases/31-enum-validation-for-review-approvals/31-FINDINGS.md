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

**Status: OBSERVED — RUN 2026-08-03, all six steps PASS.** Run by the session agent at the
operator's standing autonomous-run directive; disarmed deploys + activation are the
established operator-directed line (HANDOFF §5). No arming variable of any kind was set.

### Step 1 — starting state (read-only)

- **Verdict observed:** `VERDICT: disarmed PASS`
- **Declaring-node count (before):** `coverage: 5 workflow(s) fetched, 11 declaring node(s) found`

### Step 2 — record active workflow set (before)

- **Active (4):** LV Scheduled Maintenance, LV Enrichment, LV Contact Ingest, LV Backend Status
- **Inactive (1):** LV Review Decision

### Step 3 — disarmed deploy

- No `ENABLE_BAKED_FLAGS`, no arming variable. `DRY_RUN=false ALLOW_N8N_DEPLOY=true` only.
- **Result:** all five workflows `updated ... (200)`

### Step 4 — bounce every workflow active in step 2

- **Result:** `deactivate=200 activate=200` for all four; all restored active. (LV Review
  Decision was inactive at step 2, so it gets no bounce and stays off — the PUT alone
  updates its stored content, and there is no running instance to reload.)

### Step 5 — read back (after)

- **Verdict observed:** `VERDICT: disarmed PASS`
- **Declaring-node count (after):** `coverage: 5 workflow(s) fetched, 12 declaring node(s) found`
- **11 → 12 is exactly the predicted +1** — `Build Review Decision` (31-02) now declares the
  write-safety constants. The count moving is the proof the deploy landed; an unchanged
  count would have meant it did not.

### Step 6 — active set comparison

- **Active workflows (after):** identical to step 2 — 4 active, LV Review Decision off.
- **Matches step 2 exactly:** YES

### Anything that did not match the prediction

Nothing. Every step behaved as the plan predicted, including the declaring-node increment.

### Out of scope for this task

Re-running RB-9 step 8 needs a FRESH `needs_review` fixture — company `9604614548` was
cleared manually 2026-08-03. That re-run is RB-9's business, not this task's; this task
is complete at step 6. **Note for that re-run: the live tenant now carries the Phase 31
fix, so an `industry` approve against a fresh fixture should be REFUSED explicitly
(naming the value and property) rather than 400ing — that refusal is the fix working.**

---

## RB-9 step 8 re-run — the fix proven live, 2026-08-03

**All probes PASS.** Fixture: MRC `9604614548` re-seeded with its VERBATIM pre-fix legacy
candidate (recovered from the 30-07 snapshot) — deliberately the wild-data case the staging
guard can no longer produce but the endpoint must still survive.

| Probe | Pre-fix behaviour | Post-fix observed |
|---|---|---|
| UNARMED dry_run approve (BUG 29) | `outcome: applied` for an impossible write | **`outcome: refused`**, `would_write: []`, message names the value, the property, `148 options`, and closest labels (`arts and crafts, entertainment, performing arts`) |
| ARMED approve (BUG 28) | HubSpot 400, n8n execution `error` (1173) | **`outcome: refused`** with the same explicit message; `verify_decision` → `not_written`; every review-workflow execution `success` (1204-1208, zero errors) |
| Reject (regression) | worked | still works — `rejected` / `verified` / `mismatched: []`, record stayed queued with candidate intact |
| Blast radius | — | `neighbors_changed: 0`; target changed only the review fields + timestamp |

**Armed window:** deploy rewrote both flags **11×** (the 31-02 declaring node included),
all five workflows bounced, `armed PASS` at 12 declaring nodes. Closed in the amended
order (deactivate review wf → disarmed redeploy → bounce 4 actives → `disarmed PASS`,
12 nodes). Gate variables all unset after.

**Fixture cleared:** MRC returned to resolved state (`needs_review: false`, candidate
empty, `industry: SPORTS`, reject reason retained as audit).

**BUGS 28, 29, 30 are closed on live evidence, not just tests.** BUG 30's
`not_allowlisted` body was proven by the two-sided suite rather than live (hitting it live
needs a flagged record outside the allowlist — a second fixture for no additional
information).
