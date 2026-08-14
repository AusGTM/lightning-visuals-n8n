---
schema_version: 1
open_count: 10
waived_count: 0
fixed_count: 5
total_count: 15
last_updated: 2026-08-14T02:30:00.000Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
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
| 7 | 44 | deviation | scripts/verify_live_write_safety.py |  | Interim window until 44-03 deploys: live verifier's new 'drain authority' line reports FAIL (ALLOW_SJ3_DRAIN_WRITES not yet in live content) — plan-accepted, closed by the 44-03 deploy+bounce | open |  | 2026-08-10T01:45:26.187Z |  |
| 8 | 47.5 | deviation | scripts/build_cloud_workflows.py |  | ENRICH_CO_GATE is shared by three workflows; only wf_enrichment_cloud has a Parse HubSpot Event node, so the request-level $() read is try/catch-guarded and fails to false | open |  | 2026-08-12T05:46:01.400Z |  |
| 9 | 49 | unmet-truth | .planning/phases/49-re-score-strategy-reporting/49-PARITY-VERDICT.json |  | Company 9605273630 (Port Macquarie Race Club): lv_icp_tier stuck at C, expected B. lv_icp_fit_score correctly 45 (all five components correct new-weight values). Root cause: components already carried correct new-weight values before W1 opened (hs_lastmodifieddate 2026-08-12), so W1's PATCH was value-identical and HubSpot fired no property-change event, so WF1 (4625147345) never re-enrolled to re-grade the tier. See PORTAL-FACTS.md 2026-08-13 entry and .planning/TIER-DERIVATION-SPIKE-2026-08-13.md (Phase 50: deriving lv_icp_tier as a calculation_equation property removes the enrollment-event dependency and fixes this class as a side effect). | open |  | 2026-08-13T06:18:42.909Z |  |
| 10 | 49 | unmet-truth | .planning/phases/49-re-score-strategy-reporting/49-PARITY-VERDICT.json |  | Company 9604738976 (Bunbury Turf Club): lv_icp_tier stuck at C, expected B. lv_icp_fit_score correctly 45. Same root cause as 9605273630 (same-value PATCH fires no HubSpot property-change event, so WF1 never re-enrolled). See PORTAL-FACTS.md 2026-08-13 entry and .planning/TIER-DERIVATION-SPIKE-2026-08-13.md (Phase 50 fix). | open |  | 2026-08-13T06:18:43.064Z |  |
| 11 | 49 | unmet-truth | .planning/phases/49-re-score-strategy-reporting/49-PARITY-VERDICT.json |  | Company 17696004613 (Pinjarra Park): lv_icp_tier stuck at C, expected B. lv_icp_fit_score correctly 45. Same root cause as 9605273630 (same-value PATCH fires no HubSpot property-change event, so WF1 never re-enrolled). See PORTAL-FACTS.md 2026-08-13 entry and .planning/TIER-DERIVATION-SPIKE-2026-08-13.md (Phase 50 fix). | open |  | 2026-08-13T06:18:43.201Z |  |
| 12 | 49 | unmet-truth | .planning/phases/49-re-score-strategy-reporting/49-PARITY-VERDICT.json |  | Company 19100977027 (Newcastle Harness Racing Club): lv_icp_tier stuck at C, expected B. lv_icp_fit_score correctly 45. Same root cause as 9605273630 (same-value PATCH fires no HubSpot property-change event, so WF1 never re-enrolled). See PORTAL-FACTS.md 2026-08-13 entry and .planning/TIER-DERIVATION-SPIKE-2026-08-13.md (Phase 50 fix). | open |  | 2026-08-13T06:18:43.329Z |  |
| 13 | 50 | unmet-truth | .planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md |  | lv_icp_tier_derived's veto guard (coalesce(lv_anti_icp_flag, 0) = 1) never fires live: all 6 of the 6 scored companies carrying lv_anti_icp_flag=true (Supertech Electronics 15274105699, Queensland Racing Integrity Commission 16047156820, Jam TV 17317850381, Big Screen Video 17791151956, Sportsbet 17861423879, Simtech LED 18047161864) derive a score-based tier instead of "D" -- the correctly-excluded Tier D bucket empties from 6 to 0 on the derived property. Re-run twice, byte-identical both times (not settling lag); independently re-confirmed via a direct single-record re-GET on 3 of the 6. Never actually verified against a real true-flag record before Phase 50 Plan 03's live run: the spike's Round 2 ("7/7") was formula-grammar acceptance only (HTTP 200 on property create), and D-05's null probe (Plan 01) never set lv_anti_icp_flag on its disposable company. lv_icp_tier_derived is currently WORSE than the stale lv_icp_tier enum for vetoed records and must not be treated as authoritative for them until the guard is fixed and re-proven. Blocks D-06 (retire lv_icp_tier) and D-08 (switch off WF1) until resolved. See .planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md's D-07 verdict and SEVERITY callout. RESOLVED WITH EVIDENCE (2026-08-14, Phase 50 Plan 06): the veto guard now reads a new numeric mirror property, lv_anti_icp_flag_num (calculation_equation reads only numeric properties -- the boolean was unreadable, D-20), derived once and serialized twice (src/icp_scoring.py::anti_icp_flag_properties, scripts/build_cloud_workflows.py Decide Company Action -- commit 13fac29), backfilled onto the 6 live-vetoed companies (the phase's one D-16 deviation, commit b12266a) and the formula corrected to read it (commit b12266a). Re-running D-07's gate live confirms all 6 (Supertech Electronics, Queensland Racing Integrity Commission, Jam TV, Big Screen Video, Sportsbet, Simtech LED) now correctly derive D; Simtech LED was polled to D under a live formula recompute (D-22). Full trail: 50-TIER-PARITY-EVIDENCE.md's 2026-08-14 post-correction section, 50-MIRROR-BACKFILL.md. | fixed |  | 2026-08-13T22:01:07.000Z | 2026-08-13T23:33:15.932Z |
| 14 | 50 | unmet-truth | .planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md |  | Company 14752488879 (Coffs Harbour Racing Club): a 5th instance of the WF1-staleness class ids 9-12 already log -- lv_icp_tier reads Unscored while lv_icp_fit_score is 25 (correctly C per config/icp_scoring.yaml's tier_rules, and lv_icp_tier_derived correctly reads C). Not one of WINDOWS.md ids 9-12; discovered live during Phase 50 Plan 03's D-07 parity gate run, same root cause (a value-identical PATCH fires no HubSpot property-change event, so WF1 never (re-)enrolled). Unlike the veto-guard defect (id 13), the derived property is CORRECT here and the stale enum is wrong -- this is evidence FOR lv_icp_tier_derived, not against it. | open |  | 2026-08-13T22:01:07.000Z |  |
| 15 | 50 | deviation | .planning/phases/50-derived-tier-property/50-RETIREMENT-RECORD.md |  | lv_icp_tier archive blocked live: HubSpot rejected DELETE /crm/v3/properties/companies/lv_icp_tier with 400 CANNOT_DELETE_PROPERTY_IN_USE -- WF1's (4625147345) workflow actions still reference the property as a write target, and HubSpot counts this as "in use" regardless of the workflow's isEnabled state. Not anticipated by 50-RESEARCH.md or 50-NULL-PROBE.json (RESEARCH Q6). WF1 itself IS switched off live and verified (D-08 complete). Neither deleting WF1 nor editing its actions to strip the reference was attempted -- both are outside this plan's authorised means (the former violates the plan's explicit "WF1 is not deleted" prohibition; the latter forfeits the proven one-action rollback mechanism in 50-ROLLBACK-DRILL.md). Retirement (D-06) and the dependent relabel (D-15's fallback) are deferred pending a fresh operator decision among 3 documented options. | open |  | 2026-08-14T02:30:00.000Z |  |

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
  },
  {
    "id": 7,
    "kind": "deviation",
    "phase": "44",
    "file": "scripts/verify_live_write_safety.py",
    "line": null,
    "description": "Interim window until 44-03 deploys: live verifier's new 'drain authority' line reports FAIL (ALLOW_SJ3_DRAIN_WRITES not yet in live content) — plan-accepted, closed by the 44-03 deploy+bounce",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-10T01:45:26.187Z",
    "resolved_at": null
  },
  {
    "id": 8,
    "kind": "deviation",
    "phase": "47.5",
    "file": "scripts/build_cloud_workflows.py",
    "line": null,
    "description": "ENRICH_CO_GATE is shared by three workflows; only wf_enrichment_cloud has a Parse HubSpot Event node, so the request-level $() read is try/catch-guarded and fails to false",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-12T05:46:01.400Z",
    "resolved_at": null
  },
  {
    "id": 9,
    "kind": "unmet-truth",
    "phase": "49",
    "file": ".planning/phases/49-re-score-strategy-reporting/49-PARITY-VERDICT.json",
    "line": null,
    "description": "Company 9605273630 (Port Macquarie Race Club): lv_icp_tier stuck at C, expected B. lv_icp_fit_score correctly 45 (all five components correct new-weight values). Root cause: components already carried correct new-weight values before W1 opened (hs_lastmodifieddate 2026-08-12), so W1's PATCH was value-identical and HubSpot fired no property-change event, so WF1 (4625147345) never re-enrolled to re-grade the tier. See PORTAL-FACTS.md 2026-08-13 entry and .planning/TIER-DERIVATION-SPIKE-2026-08-13.md (Phase 50: deriving lv_icp_tier as a calculation_equation property removes the enrollment-event dependency and fixes this class as a side effect).",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-13T06:18:42.909Z",
    "resolved_at": null
  },
  {
    "id": 10,
    "kind": "unmet-truth",
    "phase": "49",
    "file": ".planning/phases/49-re-score-strategy-reporting/49-PARITY-VERDICT.json",
    "line": null,
    "description": "Company 9604738976 (Bunbury Turf Club): lv_icp_tier stuck at C, expected B. lv_icp_fit_score correctly 45. Same root cause as 9605273630 (same-value PATCH fires no HubSpot property-change event, so WF1 never re-enrolled). See PORTAL-FACTS.md 2026-08-13 entry and .planning/TIER-DERIVATION-SPIKE-2026-08-13.md (Phase 50 fix).",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-13T06:18:43.064Z",
    "resolved_at": null
  },
  {
    "id": 11,
    "kind": "unmet-truth",
    "phase": "49",
    "file": ".planning/phases/49-re-score-strategy-reporting/49-PARITY-VERDICT.json",
    "line": null,
    "description": "Company 17696004613 (Pinjarra Park): lv_icp_tier stuck at C, expected B. lv_icp_fit_score correctly 45. Same root cause as 9605273630 (same-value PATCH fires no HubSpot property-change event, so WF1 never re-enrolled). See PORTAL-FACTS.md 2026-08-13 entry and .planning/TIER-DERIVATION-SPIKE-2026-08-13.md (Phase 50 fix).",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-13T06:18:43.201Z",
    "resolved_at": null
  },
  {
    "id": 12,
    "kind": "unmet-truth",
    "phase": "49",
    "file": ".planning/phases/49-re-score-strategy-reporting/49-PARITY-VERDICT.json",
    "line": null,
    "description": "Company 19100977027 (Newcastle Harness Racing Club): lv_icp_tier stuck at C, expected B. lv_icp_fit_score correctly 45. Same root cause as 9605273630 (same-value PATCH fires no HubSpot property-change event, so WF1 never re-enrolled). See PORTAL-FACTS.md 2026-08-13 entry and .planning/TIER-DERIVATION-SPIKE-2026-08-13.md (Phase 50 fix).",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-13T06:18:43.329Z",
    "resolved_at": null
  },
  {
    "id": 13,
    "kind": "unmet-truth",
    "phase": "50",
    "file": ".planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md",
    "line": null,
    "description": "lv_icp_tier_derived's veto guard (coalesce(lv_anti_icp_flag, 0) = 1) never fires live: all 6 of the 6 scored companies carrying lv_anti_icp_flag=true (Supertech Electronics 15274105699, Queensland Racing Integrity Commission 16047156820, Jam TV 17317850381, Big Screen Video 17791151956, Sportsbet 17861423879, Simtech LED 18047161864) derive a score-based tier instead of \"D\" -- the correctly-excluded Tier D bucket empties from 6 to 0 on the derived property. Re-run twice, byte-identical both times (not settling lag); independently re-confirmed via a direct single-record re-GET on 3 of the 6. Never actually verified against a real true-flag record before Phase 50 Plan 03's live run: the spike's Round 2 (\"7/7\") was formula-grammar acceptance only (HTTP 200 on property create), and D-05's null probe (Plan 01) never set lv_anti_icp_flag on its disposable company. lv_icp_tier_derived is currently WORSE than the stale lv_icp_tier enum for vetoed records and must not be treated as authoritative for them until the guard is fixed and re-proven. Blocks D-06 (retire lv_icp_tier) and D-08 (switch off WF1) until resolved. See .planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md's D-07 verdict and SEVERITY callout. RESOLVED WITH EVIDENCE (2026-08-14, Phase 50 Plan 06): the veto guard now reads a new numeric mirror property, lv_anti_icp_flag_num (calculation_equation reads only numeric properties -- the boolean was unreadable, D-20), derived once and serialized twice (src/icp_scoring.py::anti_icp_flag_properties, scripts/build_cloud_workflows.py Decide Company Action -- commit 13fac29), backfilled onto the 6 live-vetoed companies (the phase's one D-16 deviation, commit b12266a) and the formula corrected to read it (commit b12266a). Re-running D-07's gate live confirms all 6 (Supertech Electronics, Queensland Racing Integrity Commission, Jam TV, Big Screen Video, Sportsbet, Simtech LED) now correctly derive D; Simtech LED was polled to D under a live formula recompute (D-22). Full trail: 50-TIER-PARITY-EVIDENCE.md's 2026-08-14 post-correction section, 50-MIRROR-BACKFILL.md.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-13T22:01:07.000Z",
    "resolved_at": "2026-08-13T23:33:15.932Z"
  },
  {
    "id": 14,
    "kind": "unmet-truth",
    "phase": "50",
    "file": ".planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md",
    "line": null,
    "description": "Company 14752488879 (Coffs Harbour Racing Club): a 5th instance of the WF1-staleness class ids 9-12 already log -- lv_icp_tier reads Unscored while lv_icp_fit_score is 25 (correctly C per config/icp_scoring.yaml's tier_rules, and lv_icp_tier_derived correctly reads C). Not one of WINDOWS.md ids 9-12; discovered live during Phase 50 Plan 03's D-07 parity gate run, same root cause (a value-identical PATCH fires no HubSpot property-change event, so WF1 never (re-)enrolled). Unlike the veto-guard defect (id 13), the derived property is CORRECT here and the stale enum is wrong -- this is evidence FOR lv_icp_tier_derived, not against it.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-13T22:01:07.000Z",
    "resolved_at": null
  },
  {
    "id": 15,
    "kind": "deviation",
    "phase": "50",
    "file": ".planning/phases/50-derived-tier-property/50-RETIREMENT-RECORD.md",
    "line": null,
    "description": "lv_icp_tier archive blocked live: HubSpot rejected DELETE /crm/v3/properties/companies/lv_icp_tier with 400 CANNOT_DELETE_PROPERTY_IN_USE -- WF1's (4625147345) workflow actions still reference the property as a write target, and HubSpot counts this as \"in use\" regardless of the workflow's isEnabled state. Not anticipated by 50-RESEARCH.md or 50-NULL-PROBE.json (RESEARCH Q6). WF1 itself IS switched off live and verified (D-08 complete). Neither deleting WF1 nor editing its actions to strip the reference was attempted -- both are outside this plan's authorised means (the former violates the plan's explicit \"WF1 is not deleted\" prohibition; the latter forfeits the proven one-action rollback mechanism in 50-ROLLBACK-DRILL.md). Retirement (D-06) and the dependent relabel (D-15's fallback) are deferred pending a fresh operator decision among 3 documented options.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-14T02:30:00.000Z",
    "resolved_at": null
  }
]
````
