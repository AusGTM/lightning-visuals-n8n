---
schema_version: 1
open_count: 2
waived_count: 0
fixed_count: 4
total_count: 6
last_updated: 2026-08-07T19:53:39.099Z
---

# Broken Windows Ledger

> Cross-phase defect register. `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 20 | deviation | n8n/code/lushaRequest.js |  | Plan 20-04 Task 2 Reuse (stored-id re-enrichment) not implemented: docs/LUSHA-V3-CONTRACT.md confirms the free path requires POST /v3/contacts/enrich {ids,reveal} (a different endpoint/body than lushaContactBody's search-and-enrich), and that endpoint's response envelope was never live-probed. Needs a follow-up Lusha probe before implementation. | fixed |  | 2026-07-30T04:30:31.257Z | 2026-07-30T05:06:02.452Z |
| 2 | 40 | deviation | operator-claude-plugin/scripts/scheduled_arm.py |  | ALLOW_HUBSPOT_RECORD_WRITES baked "false" in every build — no enrichment run (poller or webhook) can PATCH a real HubSpot record without an explicit, bounded arm. Investigated 2026-08-06 (fix-40): permanently flipping WRITE_SAFETY_DEFAULTS is NOT a simple flag flip — it is a load-bearing safety invariant across scripts/deploy_n8n_workflows.py's ENABLE_BAKED_FLAGS overlay, operator-claude-plugin's arm_for_dispatch/armed_window arm-verify-disarm cycle (Phase 28), and scripts/verify_live_write_safety.py's dedicated live-state verifier — flipping it broke 64 tests across both packages in a spike and reverted. Rule 4 (architectural decision), not auto-fixable that session; the operator's resolution decision (2026-08-06, ad-hoc scheduled-arm build step) was to build the scheduled poller's own companion rather than the permanent-flip refactor. RESOLUTION BUILT (2026-08-06, ad-hoc): operator-claude-plugin/scripts/scheduled_arm.py — a new, test-locked, offline-tested module reusing n8n_arming.armed_window UNCHANGED. It reads SJ-3's most-recently-matched batch off n8n's own execution history (executions_client, no HubSpot credential, D-05), arms the enrichment workflow's write gate bounded to exactly that batch, re-dispatches the same batch via the existing external webhook path (enrichment.dispatch_enrichment — the same mechanism the manual enrich-records skill already uses), then disarms — guaranteed, even when the dispatch fails (22 offline tests, tests/test_scheduled_arm.py). Investigated and rejected the in-n8n placement (nodes spliced into LV Scheduled Maintenance itself): SJ-3's search->dispatch runs inside ONE n8n execution with no external hook point, n8n has no way to fire a workflow on demand (control_actions.start_scheduled_scan's own documented 405), and an in-n8n arm would have to replicate arm_for_dispatch's deactivate->PUT->activate bounce from INSIDE a running execution using a Code-node-embedded N8N_API_KEY — a strictly larger blast radius with none of this module's test coverage; see scheduled_arm.py's own module docstring for the full reasoning. STILL OPEN: WRITE_SAFETY_DEFAULTS remains globally "false" at build time (no permanent flip, per the operator's explicit instruction) — the companion only grants a bounded, per-cycle window. Deploy-pending is the CRON JOB, not an n8n workflow: the companion needs no new n8n deploy (it operates against the already-deployed enrichment workflow's existing write-safety Code node and existing webhook endpoints, unchanged since 40-03/WINDOWS.md #3) — what remains is the operator (a) adding n8n_api_key-capable scheduled-arm config, (b) exporting ALLOW_N8N_ARM=true in the cron's own environment (never set by this session), and (c) scheduling `python3 operator-claude-plugin/scripts/scheduled_arm.py` on a cron cadence, then confirming one live cycle actually PATCHes a disposable company's lv_anti_icp_flag. RESOLVED WITH EVIDENCE (2026-08-06/07): operator ran one companion cycle (ALLOW_N8N_ARM=true python3 operator-claude-plugin/scripts/scheduled_arm.py) against disposable company 280155690475 — outcome "dispatched", arm scoped via TEST_RECORD_IDS to exactly that record, PATCH landed lv_anti_icp_flag="true"/lv_anti_icp_reason="Non-ANZ geography" as strings, disarm confirmed independently (all 5 write-safety flags back to false/empty, no node disagreement). Full trail: .planning/phases/40-scoring-engine-remediation-notes/VETO-WRITE-EVIDENCE.md. | fixed |  | 2026-08-06T07:49:45.000Z | 2026-08-06T20:31:52.869Z |
| 3 | 40 | deviation | scripts/build_cloud_workflows.py |  | SJ-3 Dispatch To Enrichment errors "Missing node to start execution" (live n8n executions 1891/1893) — LV Enrichment (Cloud template) has no Execute Workflow Trigger, so the 15-min lv_enrichment_requested poller can never reach enrichment. Blocks the entire scheduled-maintenance refresh mechanism (SJ-1/SJ-2/SJ-3), not just the veto fields. RESOLVED WITH EVIDENCE (2026-08-06): live SJ-3 tick (execution 1931) matched a disposable company and dispatched into LV Enrichment (Cloud template) sub-execution 1932 end-to-end with zero errors — no "Missing node to start execution" on this or two subsequent ticks (1934, 1937). Full trail: .planning/phases/40-scoring-engine-remediation-notes/VETO-WRITE-EVIDENCE.md. | fixed |  | 2026-08-06T07:49:45.000Z | 2026-08-06T10:13:15.258Z |
| 4 | 40 | deviation | tests/test_scoring_parity.py | 377 | test_veto_clear_after_correction patches "enrichment_requested" instead of "lv_enrichment_requested" (the real SJ-3 poller-search property) — the same wrong-property bug found and fixed in docs/OPERATOR-VETO-REFRESH.md's first draft. As written, this live test's refresh step will never actually trigger a poller pickup. | fixed |  | 2026-08-06T07:49:45.000Z | 2026-08-06T22:39:58.019Z |
| 5 | 40 | deviation | tests/test_scoring_parity.py |  | veto_set/multiple_reasons/veto_clear (5 live test cases) structurally cannot pass without an armed n8n pipeline write-gate window (scheduled_arm.py, VETO-01/VETO-02) -- confirmed empirically in 40-07, not this plan's scope per 40-03/40-05/40-06 precedent. UPDATE (2026-08-07): all three hard vetoes and the symmetric clear are now live-PATCH-proven via scheduled_arm.py (VETO-WRITE-EVIDENCE.md) -- VETO-01/VETO-02 marked complete in REQUIREMENTS.md. Two real defects were found and fixed along the way (scheduled_arm.py's missing dispatch-chunking against the backend's per-request record cap; the company existingRecord fetch's missing lv_country_region_normalized, which fired a spurious non-ANZ veto on true-AU/NZ companies). Left open: the structural condition itself is unchanged -- these 5 pytest live cases still require a per-run bounded arm window to execute (RUN_LIVE_PARITY + an armed scheduled_arm.py cycle in the SAME run), which remains the deliberate operational model, not a defect to close. | open |  | 2026-08-06T22:39:50.576Z |  |
| 6 | 43 | deviation | tests/test_review_flag_eq_filter.py |  | test_corrected_string_patch_is_matched_by_the_awaiting_review_eq_filter flakes on first run: PATCHes a brand-new company then searches immediately, with no wait for HubSpot search-index lag (~20s observed). Direct reproduction with a poll confirms the EQ filter itself matches correctly; the test lacks a poll/wait between create+patch and search. | open |  | 2026-08-07T19:53:39.099Z |  |

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
    "file": "operator-claude-plugin/scripts/scheduled_arm.py",
    "line": null,
    "description": "ALLOW_HUBSPOT_RECORD_WRITES baked \"false\" in every build — no enrichment run (poller or webhook) can PATCH a real HubSpot record without an explicit, bounded arm. Investigated 2026-08-06 (fix-40): permanently flipping WRITE_SAFETY_DEFAULTS is NOT a simple flag flip — it is a load-bearing safety invariant across scripts/deploy_n8n_workflows.py's ENABLE_BAKED_FLAGS overlay, operator-claude-plugin's arm_for_dispatch/armed_window arm-verify-disarm cycle (Phase 28), and scripts/verify_live_write_safety.py's dedicated live-state verifier — flipping it broke 64 tests across both packages in a spike and reverted. Rule 4 (architectural decision), not auto-fixable that session; the operator's resolution decision (2026-08-06, ad-hoc scheduled-arm build step) was to build the scheduled poller's own companion rather than the permanent-flip refactor. RESOLUTION BUILT (2026-08-06, ad-hoc): operator-claude-plugin/scripts/scheduled_arm.py — a new, test-locked, offline-tested module reusing n8n_arming.armed_window UNCHANGED. It reads SJ-3's most-recently-matched batch off n8n's own execution history (executions_client, no HubSpot credential, D-05), arms the enrichment workflow's write gate bounded to exactly that batch, re-dispatches the same batch via the existing external webhook path (enrichment.dispatch_enrichment — the same mechanism the manual enrich-records skill already uses), then disarms — guaranteed, even when the dispatch fails (22 offline tests, tests/test_scheduled_arm.py). Investigated and rejected the in-n8n placement (nodes spliced into LV Scheduled Maintenance itself): SJ-3's search->dispatch runs inside ONE n8n execution with no external hook point, n8n has no way to fire a workflow on demand (control_actions.start_scheduled_scan's own documented 405), and an in-n8n arm would have to replicate arm_for_dispatch's deactivate->PUT->activate bounce from INSIDE a running execution using a Code-node-embedded N8N_API_KEY — a strictly larger blast radius with none of this module's test coverage; see scheduled_arm.py's own module docstring for the full reasoning. STILL OPEN: WRITE_SAFETY_DEFAULTS remains globally \"false\" at build time (no permanent flip, per the operator's explicit instruction) — the companion only grants a bounded, per-cycle window. Deploy-pending is the CRON JOB, not an n8n workflow: the companion needs no new n8n deploy (it operates against the already-deployed enrichment workflow's existing write-safety Code node and existing webhook endpoints, unchanged since 40-03/WINDOWS.md #3) — what remains is the operator (a) adding n8n_api_key-capable scheduled-arm config, (b) exporting ALLOW_N8N_ARM=true in the cron's own environment (never set by this session), and (c) scheduling `python3 operator-claude-plugin/scripts/scheduled_arm.py` on a cron cadence, then confirming one live cycle actually PATCHes a disposable company's lv_anti_icp_flag. RESOLVED WITH EVIDENCE (2026-08-06/07): operator ran one companion cycle (ALLOW_N8N_ARM=true python3 operator-claude-plugin/scripts/scheduled_arm.py) against disposable company 280155690475 — outcome \"dispatched\", arm scoped via TEST_RECORD_IDS to exactly that record, PATCH landed lv_anti_icp_flag=\"true\"/lv_anti_icp_reason=\"Non-ANZ geography\" as strings, disarm confirmed independently (all 5 write-safety flags back to false/empty, no node disagreement). Full trail: .planning/phases/40-scoring-engine-remediation-notes/VETO-WRITE-EVIDENCE.md.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-06T07:49:45.000Z",
    "resolved_at": "2026-08-06T20:31:52.869Z"
  },
  {
    "id": 3,
    "kind": "deviation",
    "phase": "40",
    "file": "scripts/build_cloud_workflows.py",
    "line": null,
    "description": "SJ-3 Dispatch To Enrichment errors \"Missing node to start execution\" (live n8n executions 1891/1893) — LV Enrichment (Cloud template) has no Execute Workflow Trigger, so the 15-min lv_enrichment_requested poller can never reach enrichment. Blocks the entire scheduled-maintenance refresh mechanism (SJ-1/SJ-2/SJ-3), not just the veto fields. RESOLVED WITH EVIDENCE (2026-08-06): live SJ-3 tick (execution 1931) matched a disposable company and dispatched into LV Enrichment (Cloud template) sub-execution 1932 end-to-end with zero errors — no \"Missing node to start execution\" on this or two subsequent ticks (1934, 1937). Full trail: .planning/phases/40-scoring-engine-remediation-notes/VETO-WRITE-EVIDENCE.md.",
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
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-06T07:49:45.000Z",
    "resolved_at": "2026-08-06T22:39:58.019Z"
  },
  {
    "id": 5,
    "kind": "deviation",
    "phase": "40",
    "file": "tests/test_scoring_parity.py",
    "line": null,
    "description": "veto_set/multiple_reasons/veto_clear (5 live test cases) structurally cannot pass without an armed n8n pipeline write-gate window (scheduled_arm.py, VETO-01/VETO-02) -- confirmed empirically in 40-07, not this plan's scope per 40-03/40-05/40-06 precedent. UPDATE (2026-08-07): all three hard vetoes and the symmetric clear are now live-PATCH-proven via scheduled_arm.py (VETO-WRITE-EVIDENCE.md) -- VETO-01/VETO-02 marked complete in REQUIREMENTS.md. Two real defects were found and fixed along the way (scheduled_arm.py's missing dispatch-chunking against the backend's per-request record cap; the company existingRecord fetch's missing lv_country_region_normalized, which fired a spurious non-ANZ veto on true-AU/NZ companies). Left open: the structural condition itself is unchanged -- these 5 pytest live cases still require a per-run bounded arm window to execute (RUN_LIVE_PARITY + an armed scheduled_arm.py cycle in the SAME run), which remains the deliberate operational model, not a defect to close.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-06T22:39:50.576Z",
    "resolved_at": null
  },
  {
    "id": 6,
    "kind": "deviation",
    "phase": "43",
    "file": "tests/test_review_flag_eq_filter.py",
    "line": null,
    "description": "test_corrected_string_patch_is_matched_by_the_awaiting_review_eq_filter flakes on first run: PATCHes a brand-new company then searches immediately, with no wait for HubSpot search-index lag (~20s observed). Direct reproduction with a poll confirms the EQ filter itself matches correctly; the test lacks a poll/wait between create+patch and search.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-07T19:53:39.099Z",
    "resolved_at": null
  }
]
````
