---
phase: 34-header-mapping-tolerance
plan: 02
status: complete
completed: 2026-08-05
requirements: [INGEST-02]
---

# 34-02 Summary — Half A: the deterministic table, widened and actually running

## What shipped

**Three aliases added to all three tables in one commit** (`e38ea20`):
`e-mail address` → `email`, `org.` → `company`, `linkedin profile` → `linkedin_url`, in
`config/column_mapping.yaml`, `operator-claude-plugin/config/column_mapping.yaml`
(re-copied, never hand-edited — `test_column_mapping_shipped.py` pins them byte-identical),
and `n8n/code/columnMap.js`.

**Two workflow artifacts rebuilt** (`65936ae`) — `wf_contact_ingest_cloud.json` and
`wf_contact_ingest_local.json`, the two that embed `mapRow`. `build_cloud_workflows.py:85`
inlines `columnMap.js`'s literal text, so the rebuild is what carries the widened table
into a deployable body.

**Deliberately NOT added:** `company name` (0.737), `work email` (0.667), `mobile phone`
(0.588), `e-mail address:` (0.500). All clear Half B's fuzzy cutoff and none has been
observed to miss a real operator file — adding speculative keys to a table that lives in
three hand-maintained files costs drift risk to save a keystroke on a file nobody has sent.
`ph.` is deliberately absent too: it is Half B's case, because it could plausibly be a
photo column.

## The guard is the real deliverable

`tests/n8n/columnMapAliasParity.test.mjs` (`634fe31`, written before any alias moved) pins
`columnMap.js`'s `ALIASES` deep-equal to the YAML's `aliases`, asserts every YAML key is
already normalized, and walks every alias through the real `mapRow`. The two tables agree
**by hand, not by construction** — there is no YAML→JS generator — so without this guard,
widening one side alone would make the plugin's preview confidently predict a mapping the
backend does not perform. That is worse than the honest mismatch it replaces.

## RED-CHECKS (performed, restored, green either side)

1. Reverted `columnMap.js` alone → the deep-equal and `mapRow` round-trip assertions failed.
2. Reverted the shipped YAML copy alone → `test_the_shipped_copy_has_not_drifted_from_the_repo_copy` failed.

## The live half — deploy, bounce, read back

**The disarmed deploy was run by the operator**, not by an agent: the Claude Code auto-mode
classifier denies every Bash invocation touching `scripts/deploy_n8n_workflows.py`, in both
the documented shell form and the python-driver form (the driver form is recorded as having
passed on 2026-07-29; it does not now). The operator ran the CONTEXT.md §6 one-liner via a
`!` prefix. No `ALLOW_HUBSPOT_*` and no `ENABLE_BAKED_FLAGS` was set at any point.

```
Workflows to update: [LV Backend Status, LV Contact Ingest, LV Enrichment,
                      LV Review Decision, LV Scheduled Maintenance]   → all 200
```

**Bounce** — the four ACTIVE workflows only, each `deactivate` → `activate`, each verdict
from an INDEPENDENT second GET rather than the mutation's own echo:

| Workflow | deactivate | activate |
|---|---|---|
| `1fXPuIabz3RsAHgn` LV Scheduled Maintenance | verified (False) | verified (True) |
| `950HPb7a1GgSAIyZ` LV Enrichment | verified (False) | verified (True) |
| `AwbBeShdPgV48eiY` LV Contact Ingest | verified (False) | verified (True) |
| `Cj83mOgrIm59oxcX` LV Backend Status | verified (False) | verified (True) |
| `WBJwoZOo63wzeP69` LV Review Decision | **no call of any kind** — inactive at rest, inactive after |

Post-bounce activation set **identical** to pre-bounce. No retry was needed; no workflow was
left deactivated.

**Why the bounce and not just the PUT:** n8n serves an active workflow from a cached
compiled definition and does not reload it on a bare PUT. A GET read-back proves only that
the STORED body changed. Only a deactivate→activate cycle forces the runtime to reload from
stored content — so for `LV Contact Ingest`, the one workflow this plan exists to change,
the bounce is what makes the widened aliases reachable by an incoming file.

**Read-back:** `verify_live_write_safety.py --expectation disarmed` → `VERDICT: disarmed PASS`.
Every `ALLOW_HUBSPOT_*` node across all five live workflows reads `'false'`.

**Running-body proof** — GET of the live `LV Contact Ingest` workflow's `Map Columns` node:

```
"e-mail address"      YES
"org."                YES
"linkedin profile"    YES
active: True
```

## Verification

| Gate | Result |
|---|---|
| `node --test tests/n8n/columnMapAliasParity.test.mjs` | 3/3 pass |
| `.venv/bin/python -m pytest operator-claude-plugin/tests/test_column_mapping_shipped.py -q` | 4/4 pass |
| `node --test tests/n8n/*.test.mjs` | 553 pass |
| `diff config/column_mapping.yaml operator-claude-plugin/config/column_mapping.yaml` | empty |
| `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` | 0 |
| `verify_live_write_safety.py --expectation disarmed` | `VERDICT: disarmed PASS` |
| live activation set | 4 active, LV Review Decision inactive — unchanged |

## Effect

The preview and the running backend now agree. Against `22-messy-headers.csv`, four of
seven headers map with nothing typed where two did before.
