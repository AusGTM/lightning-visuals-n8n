# Phase 73 Plan 07 — Operator Gate Record (73-UAT.md)

This file is the single gate record for phase 73: Task 1's pre-flight (Claude, offline),
Task 2's release cut, and Task 3's live attempt-3 record (operator only, per D-73-18).

---

## Pre-flight (Task 1 — Claude, 2026-09-16, offline)

### 1. Idempotent regeneration

```
.venv/bin/python scripts/build_cloud_workflows.py
git status --porcelain -- n8n/
```

Regeneration ran clean; `git status --porcelain -- n8n/` printed nothing. **Zero diff —
the committed tree is exactly what the builder produces.**

### 2. Node counts, reconciled against the six SUMMARYs

| Workflow | Node count (this run) | Reconciliation |
|---|---|---|
| `wf_backend_status_cloud.json` | 30 | Unchanged from the pre-phase-73 baseline (CLAUDE.md §13.0.2, Phase 72 gate: 30). 73-05 (F-B6) added a second outbound edge on `Build Credit Status` to an existing node — an edge, not a node — matching 73-05-SUMMARY.md's own description ("`Build Credit Status` now has two outbound edges instead of one"). |
| `wf_contact_ingest_cloud.json` | 80 | +2 from the pre-phase-73 baseline (69 → 78 at Phase 72 gate). Verified by walking `git log` per-commit node counts on this file: 78 held through 73-02's throttle widen and 73-03's companies-domain-IN-query change (param/logic edits, no new nodes), then 79 after 73-06's "identity-join HubSpot Create's outcome, replacing positional pairing" commit (+1, the pair node) and 80 after 73-06's "the create_failed refusal lane (D-73-01)" commit (+1, the failure-row node) — exactly the two nodes 73-06-SUMMARY.md names ("the pair node, the failure-row node, and the `alwaysOutputData` fix", the last of which is a property flag, not a node). |
| `wf_contact_ingest_local.json` | 13 | Unchanged (stable baseline; no plan in this phase modified the local ingest lane). |
| `wf_enrichment_cloud.json` | 287 | Unchanged from the pre-phase-73 baseline (287, Phase 72 gate). 73-03 touched this file for the companies freemail refusal and the domain IN-query, but reused existing conflict-detection/decide nodes rather than adding new ones — consistent with 73-03-SUMMARY.md recording no node-count claim and describing only jsCode/config changes. |
| `wf_enrichment_local.json` | 10 | Unchanged (stable baseline). |
| `wf_enrichment_local_live.json` | 82 | Unchanged from the pre-phase-73 baseline (82, Phase 72 gate). 73-03-SUMMARY.md explicitly records this file was touched by shared-constant changes only in Tasks 1–2 and NOT by Task 3 (its own `ENRICH_DECIDE_CO_LOCAL` node is a dry-run echo), so no node-count change is expected. |
| `wf_review_decision_cloud.json` | 55 | Unchanged (stable baseline, Phase 72 gate: 55). 73-02's `reviewApply()` array-serialization fix (F-E1) is a jsCode edit inside the existing node, not a new node — matches 73-02-SUMMARY.md's description of the fix location. |
| `wf_scheduled_maintenance_cloud.json` | 43 | Unchanged (stable baseline, Phase 72 gate: 43). 73-02 regenerated this file only because it inlines the same `reviewApply.js` source as the review-decision lane. |

Every count reconciles to a named change from a specific plan/commit in this phase, or to the
pre-phase-73 baseline where no plan claimed a node-level change. No unexplained count.

### 3. Execution order and armed-write check

```
.venv/bin/python -c "import json,glob,sys; bad=[p for p in glob.glob('n8n/wf_*.json') if json.load(open(p)).get('settings',{}).get('executionOrder')!='v1']; print('NON_V1:',bad); sys.exit(1 if bad else 0)"
# -> NON_V1: []  (exit 0)

/usr/bin/grep -c 'ALLOW_HUBSPOT_RECORD_WRITES = "true"' n8n/wf_contact_ingest_cloud.json n8n/wf_enrichment_cloud.json
# -> both 0

/usr/bin/grep -oE 'ALLOW_[A-Z_]+ = .true.' n8n/wf_*.json | sort -u
# -> (no output — no ALLOW_* flag is true anywhere in any generated body)
```

Every generated body carries `settings.executionOrder: "v1"` and zero armed write flags.

### 4. Both suites, against HEAD baselines

| Suite | Baseline | This run |
|---|---|---|
| `node --test tests/n8n/*.test.mjs` | 1170 pass / 0 fail | **1215 pass / 0 fail** |
| `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider tests/ operator-claude-plugin/tests/` | 4952 passed / 154 skipped | **4990 passed / 154 skipped** |

Both suites are at or above baseline. Zero failures.

### 5. Todo triage (CLAUDE.md §31 zero-inbox)

```
.venv/bin/python scripts/todo_triage.py
```

```
question   major    2026-08-04-enrichment-throughput-ceiling.md
design     major    2026-09-04-company-domain-has-no-candidate-source.md
question   major    2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md
design     minor    2026-09-12-enrichment-lane-and-companies-branch-have-no-property-history-hop.md
defect     minor    2026-09-12-rows-to-resume-current-outcomes-never-wired-fingerprint-branch-dead.md
counts: {'question': 2, 'design': 2, 'defect': 1} | debt (defect): 1
```

Exit code 0, `.venv/bin/python -m pytest -q tests/test_todo_triage.py` passes (2/2). All five
pending todos are typed (`question`/`design`/`defect`) and pre-date this phase — none was
opened by phase 73's own plans, and none requires a decision to reach this gate.
**`.planning/todos/pending/` contains no untriaged file.**

### Pre-flight verdict

All five checks pass. The tree is deployable, idempotent, disarmed, green, and zero-inbox.
Handed to the operator for Task 3.

---

## Release (Task 2 — Claude, 2026-09-16)

`operator-claude-plugin/.claude-plugin/plugin.json` bumped to `0.50.0`; matching
`CHANGELOG.md` entry added in the same commit. `tests/stress-tests/RUNBOOK.md` restart step 4
corrected: two of the three companies-CSV known-gap rows (freemail, LinkedIn-only/name-only)
now exercise this phase's fixes rather than documenting open gaps; only the name+TLD case
(Perth Racing, F-B2, D-73-07) remains a documented known gap. Nothing pushed.

---

## Attempt 3, Stages A–F (Task 3 — OPERATOR, pending)

*To be completed by the operator after deploy, bounce, read-back, snapshot, and reset. See
Task 3 in `73-07-PLAN.md` for the exact commands and required record shape.*
