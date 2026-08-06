---
schema_version: 1
open_count: 3
waived_count: 0
fixed_count: 1
total_count: 4
last_updated: 2026-08-06T07:49:45.000Z
---

# Broken Windows Ledger

> Cross-phase defect register. `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 20 | deviation | n8n/code/lushaRequest.js |  | Plan 20-04 Task 2 Reuse (stored-id re-enrichment) not implemented: docs/LUSHA-V3-CONTRACT.md confirms the free path requires POST /v3/contacts/enrich {ids,reveal} (a different endpoint/body than lushaContactBody's search-and-enrich), and that endpoint's response envelope was never live-probed. Needs a follow-up Lusha probe before implementation. | fixed |  | 2026-07-30T04:30:31.257Z | 2026-07-30T05:06:02.452Z |
| 2 | 40 | deviation | n8n/wf_enrichment_cloud.json |  | ALLOW_HUBSPOT_RECORD_WRITES baked "false" in every build (WRITE_SAFETY_DEFAULTS, scripts/build_cloud_workflows.py) — no enrichment run (poller or webhook) can PATCH a real HubSpot record until this is flipped, rebuilt, and redeployed. Blocks 40-05's Geography-flow veto-branch deletion (would leave zero working veto writers, T-40-11's DoS scenario) until a live write is confirmed landing. | open |  | 2026-08-06T07:49:45.000Z |  |
| 3 | 40 | deviation | scripts/build_cloud_workflows.py |  | SJ-3 Dispatch To Enrichment errors "Missing node to start execution" (live n8n executions 1891/1893) — LV Enrichment (Cloud template) has no Execute Workflow Trigger, so the 15-min lv_enrichment_requested poller can never reach enrichment. Blocks the entire scheduled-maintenance refresh mechanism (SJ-1/SJ-2/SJ-3), not just the veto fields. | open |  | 2026-08-06T07:49:45.000Z |  |
| 4 | 40 | deviation | tests/test_scoring_parity.py | 377 | test_veto_clear_after_correction patches "enrichment_requested" instead of "lv_enrichment_requested" (the real SJ-3 poller-search property) — the same wrong-property bug found and fixed in docs/OPERATOR-VETO-REFRESH.md's first draft. As written, this live test's refresh step will never actually trigger a poller pickup. | open |  | 2026-08-06T07:49:45.000Z |  |

````json
[
  {
    "id": 1,
    "kind": "deviation",
    "phase": "20",
    "file": "n8n/code/lushaRequest.js",
    "line": null,
    "description": "Plan 20-04 Task 2 Reuse (stored-id re-enrichment) not implemented: docs/LUSHA-V3-CONTRACT.md confirms the free path requires POST /v3/contacts/enrich {ids,reveal} (a different endpoint/body than lushaContactBody's search-and-enrich), and that endpoint's response envelope was never live-probed. Needs a follow-up Lusha probe before implementation.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-07-30T04:30:31.257Z",
    "resolved_at": "2026-07-30T05:06:02.452Z"
  },
  {
    "id": 2,
    "kind": "deviation",
    "phase": "40",
    "file": "n8n/wf_enrichment_cloud.json",
    "line": null,
    "description": "ALLOW_HUBSPOT_RECORD_WRITES baked \"false\" in every build (WRITE_SAFETY_DEFAULTS, scripts/build_cloud_workflows.py) — no enrichment run (poller or webhook) can PATCH a real HubSpot record until this is flipped, rebuilt, and redeployed. Blocks 40-05's Geography-flow veto-branch deletion (would leave zero working veto writers, T-40-11's DoS scenario) until a live write is confirmed landing.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-06T07:49:45.000Z",
    "resolved_at": null
  },
  {
    "id": 3,
    "kind": "deviation",
    "phase": "40",
    "file": "scripts/build_cloud_workflows.py",
    "line": null,
    "description": "SJ-3 Dispatch To Enrichment errors \"Missing node to start execution\" (live n8n executions 1891/1893) — LV Enrichment (Cloud template) has no Execute Workflow Trigger, so the 15-min lv_enrichment_requested poller can never reach enrichment. Blocks the entire scheduled-maintenance refresh mechanism (SJ-1/SJ-2/SJ-3), not just the veto fields.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-06T07:49:45.000Z",
    "resolved_at": null
  },
  {
    "id": 4,
    "kind": "deviation",
    "phase": "40",
    "file": "tests/test_scoring_parity.py",
    "line": 377,
    "description": "test_veto_clear_after_correction patches \"enrichment_requested\" instead of \"lv_enrichment_requested\" (the real SJ-3 poller-search property) — the same wrong-property bug found and fixed in docs/OPERATOR-VETO-REFRESH.md's first draft. As written, this live test's refresh step will never actually trigger a poller pickup.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-06T07:49:45.000Z",
    "resolved_at": null
  }
]
````
