---
schema_version: 1
open_count: 2
waived_count: 0
fixed_count: 2
total_count: 4
last_updated: 2026-08-06T10:13:15.258Z
---

# Broken Windows Ledger

> Cross-phase defect register. `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 20 | deviation | n8n/code/lushaRequest.js |  | Plan 20-04 Task 2 Reuse (stored-id re-enrichment) not implemented: docs/LUSHA-V3-CONTRACT.md confirms the free path requires POST /v3/contacts/enrich {ids,reveal} (a different endpoint/body than lushaContactBody's search-and-enrich), and that endpoint's response envelope was never live-probed. Needs a follow-up Lusha probe before implementation. | fixed |  | 2026-07-30T04:30:31.257Z | 2026-07-30T05:06:02.452Z |
| 2 | 40 | deviation | n8n/wf_enrichment_cloud.json |  | ALLOW_HUBSPOT_RECORD_WRITES baked "false" in every build — no enrichment run (poller or webhook) can PATCH a real HubSpot record today. Investigated 2026-08-06 (fix-40): permanently flipping WRITE_SAFETY_DEFAULTS is NOT a simple flag flip — it is a load-bearing safety invariant across scripts/deploy_n8n_workflows.py's ENABLE_BAKED_FLAGS overlay, operator-claude-plugin's arm_for_dispatch/armed_window arm-verify-disarm cycle (Phase 28), and scripts/verify_live_write_safety.py's dedicated live-state verifier — flipping it broke 64 tests across both packages in a spike and reverted. Rule 4 (architectural decision), not auto-fixable this session. TWO scoped mechanisms already exist needing NO code change: (1) operator-claude-plugin's arm_for_dispatch()/armed_window arms writes for exactly one manual dispatch, record-scoped, then disarms — usable TODAY via the enrich-records skill for a manual per-record D-02 refresh. (2) deploy_n8n_workflows.py's `ENABLE_BAKED_FLAGS=ALLOW_HUBSPOT_RECORD_WRITES,TEST_RECORD_IDS=<id>` deploy-time overlay, for a scripted canary. NEITHER covers the autonomous SJ-1/SJ-2/SJ-3 scheduled poller (nothing arms a cron tick) — a persistent write path for the scheduled refresh mechanism, and for 40-05's veto-branch deletion, requires an operator decision between a new bounded "scheduled arm" companion job or the permanent-flip refactor. | open |  | 2026-08-06T07:49:45.000Z |  |
| 3 | 40 | deviation | scripts/build_cloud_workflows.py |  | SJ-3 Dispatch To Enrichment errors "Missing node to start execution" (live n8n executions 1891/1893) — LV Enrichment (Cloud template) has no Execute Workflow Trigger, so the 15-min lv_enrichment_requested poller can never reach enrichment. Blocks the entire scheduled-maintenance refresh mechanism (SJ-1/SJ-2/SJ-3), not just the veto fields. | fixed |  | 2026-08-06T07:49:45.000Z | 2026-08-06T10:13:15.258Z |
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
    "description": "ALLOW_HUBSPOT_RECORD_WRITES baked \"false\" in every build — no enrichment run (poller or webhook) can PATCH a real HubSpot record today. Investigated 2026-08-06 (fix-40): permanently flipping WRITE_SAFETY_DEFAULTS is NOT a simple flag flip — it is a load-bearing safety invariant across scripts/deploy_n8n_workflows.py's ENABLE_BAKED_FLAGS overlay, operator-claude-plugin's arm_for_dispatch/armed_window arm-verify-disarm cycle (Phase 28), and scripts/verify_live_write_safety.py's dedicated live-state verifier — flipping it broke 64 tests across both packages in a spike and reverted. Rule 4 (architectural decision), not auto-fixable this session. TWO scoped mechanisms already exist needing NO code change: (1) operator-claude-plugin's arm_for_dispatch()/armed_window arms writes for exactly one manual dispatch, record-scoped, then disarms — usable TODAY via the enrich-records skill for a manual per-record D-02 refresh. (2) deploy_n8n_workflows.py's ENABLE_BAKED_FLAGS=ALLOW_HUBSPOT_RECORD_WRITES,TEST_RECORD_IDS=<id> deploy-time overlay, for a scripted canary. NEITHER covers the autonomous SJ-1/SJ-2/SJ-3 scheduled poller (nothing arms a cron tick) — a persistent write path for the scheduled refresh mechanism, and for 40-05's veto-branch deletion, requires an operator decision between a new bounded scheduled-arm companion job or the permanent-flip refactor.",
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
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-06T07:49:45.000Z",
    "resolved_at": "2026-08-06T10:13:15.258Z"
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
