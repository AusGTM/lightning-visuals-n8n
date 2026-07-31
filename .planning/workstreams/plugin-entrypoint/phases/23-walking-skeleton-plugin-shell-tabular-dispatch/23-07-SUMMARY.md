---
phase: 23-walking-skeleton-plugin-shell-tabular-dispatch
plan: 07
subsystem: deploy-safety
tags: [read-back, write-safety, armed-window, operator-runbook, gap-closure]
requires: []
provides:
  - "discovery-scoped arm/disarm read-back covering every deployed workflow"
  - "--expect-armed, a symmetric expected-armed flag set"
  - "runbook command lines the fixed CLI accepts (RB-3, RB-9, 23 Section B)"
affects:
  - "23-06 Section B (unblocked)"
  - "30-07 armed review canary (unblocked)"
tech-stack:
  added: []
  patterns:
    - "coverage discovered from fetched artifacts, never enumerated in code"
    - "symmetric expectation: naming a flag narrows nothing else"
    - "a scan matching nothing fails rather than passing"
key-files:
  created: []
  modified:
    - scripts/verify_live_write_safety.py
    - tests/test_verify_live_write_safety.py
    - .planning/workstreams/plugin-entrypoint/OPERATOR-RUNBOOK.md
    - .planning/workstreams/plugin-entrypoint/phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-OPERATOR-RUNBOOK.md
    - .planning/workstreams/plugin-entrypoint/phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-CONTEXT.md
decisions:
  - "D-19: coverage is discovered from the fetched workflows, with no narrowing argument"
  - "D-19b: a node is judged on the constants it declares, not on a required set of five"
  - "D-19c: --expect-armed is symmetric; the default preserves Phase 22's exact meaning"
metrics:
  duration: ~50 min
  completed: 2026-07-31
status: complete
---

# Phase 23 Plan 07: Fix the arm/disarm read-back Summary

The read-back that closes both remaining armed windows now discovers its own coverage — 11 declaring
nodes across 8 workflows instead of the 2 it hardcoded — and takes `--expect-armed`, so 23-06's
record-writes-plus-create window and 30-07's review-writes window are each expressible and each
yields a passing verdict for a backend armed exactly as its runbook intends.

## What was wrong

`scripts/verify_live_write_safety.py` is the independent re-read that closes an armed window; in
this repo a window is never closed by a deploy's exit code (Phase 19's BUG 26). Three defects were
found in it on 2026-07-31 by three independent routes:

1. **Blind coverage.** It hardcoded `ENRICHMENT_WORKFLOW_NAME` (line 60) and a two-name `Decide*`
   tuple (line 64) and took no workflow argument. Confirmed by re-derivation during this plan: it
   inspected **2 of 11 declaring nodes** and **no node at all in `LV Contact Ingest (Cloud
   template)`** — the lane 23-06's canary fires at. Its `disarmed PASS` was a confident pass for a
   lane it never looked at. Found by the operator walking 23-06 Section B live.
2. **Rejected a correct armed state.** The armed branch baked in Phase 22's canary scope (record
   writes only, everything else disabled), so it reported FAILURE for a backend armed exactly as
   23-06's Step 3 arms it. A read-back that fails a correct state trains an operator to fire through
   a failure. Found by reading Step 3b against the script.
3. **Re-typed boolean set** — already fixed by 30-01 before this plan; `ALLOW_HUBSPOT_REVIEW_WRITES`
   had been invisible, so an armed instance reported `disarmed PASS`.

## What was built

**Task 1 — coverage follows the deployed artifacts.** `_find_live_enrichment_workflow()`, the
workflow-name constant and the node-name tuple are gone. `_fetch_all_live_workflows()` fetches every
deployed workflow and re-fetches each by id for node detail; `_declaring_nodes()` returns one entry
per node whose `jsCode` declares at least one checked constant. `verify()` now takes a **list** of
workflows. A node declaring a subset is judged on exactly what it declares — the contact lane's
`Decide Action` really does declare only `ALLOW_HUBSPOT_CREATE` (23-01, D-16a/b), and the old
"must declare all five" rule would have reported it broken on every run. Nothing is lost: which node
declares what stays pinned by `tests/test_write_gate_coverage.py`. Every reason names **workflow then
node**, because two workflows contain a node called `Decide Action`. A scan discovering **zero**
declaring nodes fails with an explicit reason rather than passing quietly. The report prints its own
`coverage:` line. There is deliberately **no workflow-selection argument** (27-04's D-07 reasoning) —
a scan that can be narrowed can go blind again, one flag at a time.

**Task 2 — a symmetric armed expectation.** `--expect-armed FLAG,FLAG` takes the same
comma-separated shape the operator already types into `ENABLE_BAKED_FLAGS`. For each declared boolean
the expected literal is the enabled one when named and the **disabled** one otherwise — naming a flag
says it must read enabled and says nothing else. Unknown names and an explicitly empty set raise
`ValueError`; the CLI validates before the credentials check, so a typo can never silently expect
nothing nor spend a request. `--expect-armed` is rejected under the disarmed expectation. Omitting it
under `armed` means record writes alone, which is precisely what the script meant before, so an
operator who forgets it gets the **stricter** verdict. A declaring node whose allowlist constants are
all empty under an armed expectation is its own finding, since `_writeSafetyAllows()` returns false
on empty — that state grants nothing while every flag reads `true`. The expected-armed set is printed
in the report header and carried in the JSON verdict.

**Task 3 — the runbooks and CONTEXT.** Both runbooks' now-obsolete defect blocks and the all-workflow
shell workaround were removed and retitled for the one finding still standing (23-01 committed but
not deployed, with its inserted Steps 2b/2c). Step 3b in both gained `--expect-armed`, and RB-9 gained
an armed read-back it previously could not perform at all. D-19 (with D-19a–d) is recorded in
`23-CONTEXT.md` so the next planner reads the correction rather than re-litigating it.

## The two command lines the armed windows should use

**23-06 Section B, Step 3b** (record writes + create, allowlisted to the canary domain):

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation armed --allowlist australiagtm.com --expect-armed ALLOW_HUBSPOT_RECORD_WRITES,ALLOW_HUBSPOT_CREATE
```

**30-07 / RB-9, step 3b** (review writes alone, allowlisted to one record id):

```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation armed --allowlist <RECORD_ID> --expect-armed ALLOW_HUBSPOT_REVIEW_WRITES
```

Both are symmetric: every write-enabling boolean not named is still asserted disabled in every
declaring node of every workflow.

## Evidence

Coverage, re-derived from the committed artifacts during this plan (numbers were **not** copied from
the plan — they changed twice on 2026-07-31):

```
ALLOW_HUBSPOT_CREATE: 11   ALLOW_HUBSPOT_RECORD_WRITES: 10   ALLOW_HUBSPOT_REVIEW_WRITES: 10
distinct declaring nodes: 11
```

Running the fixed `verify()` offline over the eight committed `n8n/wf_*.json` artifacts:

```
workflows scanned: 8 | declaring nodes: 11 | ok: True
```

All 11 discovered, including the three in `LV Contact Ingest (Cloud template)`, the two in
`LV Review Decision (Cloud)` and the four in `LV Scheduled Maintenance (Cloud)` — every one of which
the previous version was blind to. **Zero-discovery confirmed to fail:**

```
ZERO-DISCOVERY ok: False
reason: zero declaring nodes found across 1 fetched workflow(s): no node declares any of …
```

## Verification

| Check | Result |
|---|---|
| `.venv/bin/python -m pytest tests/test_verify_live_write_safety.py -q` | 37 passed (was 17) |
| `.venv/bin/python -m pytest -q` (full) | **1370 passed, 1 skipped** (baseline 1350/1; +20 new tests, no regressions) |
| `node --test tests/n8n/<file>.test.mjs` × 42, file form | **474 passed, 0 failed** (baseline 474/0 — unchanged, no n8n artifact touched) |
| plugin suite, pytest from `operator-claude-plugin/` | **521 passed** (baseline 521 — unchanged) |
| `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` | **0 everywhere** — nothing armed |
| `grep -cE 'requests\.(post\|put\|patch\|delete)' scripts/verify_live_write_safety.py` | 0 — still read-only |
| `grep -v '^\s*#' … \| grep -c 'WRITE_DECISION_NODE_NAMES'` / `'ENRICHMENT_WORKFLOW_NAME'` | 0 / 0 |
| `grep -c 'BOOLEAN_CONSTANTS' scripts/verify_live_write_safety.py` | 3 — 30-01's derivation preserved |
| `--help \| grep -c 'expect-armed'` | 5, zero network calls |
| Task 3's one-line grep gate (both runbooks + D-19 + no stale fraction) | exits 0 |

No live network call was made at any point. Nothing was armed, deployed, activated, or written to
HubSpot.

## Deviations from Plan

**None affecting behaviour.** Two notes on execution:

1. **Task 1 was implemented once with Task 2's `--expect-armed` included, then split back out**
   before committing, so Task 2's tests were genuinely written against code that did not yet exist
   rather than against code already in the tree. Net effect on the repo: none; the commit sequence is
   the honest TDD one (test → feat, twice).
2. **Tracer feedback gate (Task 1, `type="tracer"`) was satisfied by re-running its `<verify>`
   end-to-end** — `tests/test_verify_live_write_safety.py` 24 passed plus the full suite at 1357 with
   no regressions — rather than by returning an interactive checkpoint, since the tracer's verify is
   fully automated and the executor was directed to run the plan to completion. Recorded here so the
   substitution is visible.

## Third caller, deliberately not rewritten

`.planning/workstreams/milestone/phases/22-armed-e2e-enrichment-canary/22-OPERATOR-RUNBOOK.md`
carries three invocations (plus two in 22-02/22-04 summaries). They pass `--expectation armed
--allowlist 9604614548` with no `--expect-armed`, which under the preserved default means record
writes armed and every other boolean disabled — **exactly** what they meant when written. Phase 22 is
complete; its evidence trail was left alone.

## Operator to-do — one file this plan deliberately did not touch

`.planning/workstreams/plugin-entrypoint/STATE.md` (~line 280) carries the same stale claim that the
read-back covers one workflow and two nodes. It is **operator-held and uncommitted** (mid-23-06), so
this plan left it alone by instruction. **The operator should refresh that line when they commit
their 23-06 work.** `HANDOFF.md` §1 and §4 carry the same claim and are likewise out of scope here.

## Known Stubs

None. No stub, TODO, FIXME, skipped test or unrun `<verify>` was introduced by this plan.

## Threat Flags

None. This plan introduces no new network endpoint, auth path, file access pattern or schema change;
the only script it touches lost capability (hardcoded scope) and gained none — it remains read-only,
asserted by a grep gate for mutating HTTP verbs and by the hermetic fixture that makes any live
request raise.

## Self-Check: PASSED

- `scripts/verify_live_write_safety.py` — FOUND
- `tests/test_verify_live_write_safety.py` — FOUND
- `.planning/workstreams/plugin-entrypoint/OPERATOR-RUNBOOK.md` — FOUND
- `.../23-OPERATOR-RUNBOOK.md` — FOUND
- `.../23-CONTEXT.md` — FOUND (D-19 present)
- Commits `26b4b79`, `81c673b`, `9cb1341`, `df0e20b`, `739a38f` — all FOUND in `git log`
