---
schema_version: 1
open_count: 17
waived_count: 3
fixed_count: 8
total_count: 28
last_updated: 2026-09-03T07:16:45.755Z
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
| 15 | 50 | deviation | .planning/phases/50-derived-tier-property/50-RETIREMENT-RECORD.md |  | lv_icp_tier archive blocked live: HubSpot rejected DELETE /crm/v3/properties/companies/lv_icp_tier with 400 CANNOT_DELETE_PROPERTY_IN_USE -- WF1's (4625147345) workflow actions still reference the property as a write target, and HubSpot counts this as "in use" regardless of the workflow's isEnabled state. Not anticipated by 50-RESEARCH.md or 50-NULL-PROBE.json (RESEARCH Q6). WF1 itself IS switched off live and verified (D-08 complete). Neither deleting WF1 nor editing its actions to strip the reference was attempted -- both are outside this plan's authorised means (the former violates the plan's explicit "WF1 is not deleted" prohibition; the latter forfeits the proven one-action rollback mechanism in 50-ROLLBACK-DRILL.md). Retirement (D-06) and the dependent relabel (D-15's fallback) were deferred pending a fresh operator decision among 3 documented options. RESOLVED WITH EVIDENCE (2026-08-14, same-date second live window, Phase 50 Plan 05): the operator selected option 3 -- delete WF1 entirely -- explicitly overriding D-08 (D-24, 50-CONTEXT.md). scripts/put_hubspot_flow.py gained a --delete mode; WF1 deleted (204, independently re-read 404); the archive retried and succeeded (204, confirmed absent and present under ?archived=true); lv_icp_tier_derived relabelled to "ICP Tier" in the same window and verified by a two-point D-22 poll. Rollback is now rebuild-from-JSON via POST /automation/v4/flows, not a one-action re-enable -- docs/OPERATOR-TIER-ROLLBACK.md's 2026-08-14 amendment states the mechanism is gone. Full trail: 50-RETIREMENT-RECORD.md's "D-24 resolution" section. | fixed |  | 2026-08-14T02:30:00.000Z | 2026-08-14T02:23:24.962Z |
| 16 | 47 | deviation | docs/OPERATOR-VETO-REFRESH.md |  | Phase 47 declared ONE armed write window and spent FIVE. Genuinely disclosed at the time in 47-04-SUMMARY.md, 47-RUN-REPORT.md and REQUIREMENTS.md's VETO-02 row, but never registered in this cross-phase ledger -- the register /gsd-ship actually gates on -- so a disclosure present in three phase-local documents was invisible to the one check designed to catch it. Recorded retrospectively by Phase 47's first verification run (2026-08-19, 8 days late; the phase had been sealed without a verifier ever running). No record was harmed: the overrun was in window COUNT, not scope -- every window stayed record-scoped and each disarm was read back and confirmed. Registered for ledger completeness and as the standing reminder that a per-phase disclosure is not a ledger entry. | waived | Historical, retroactively unfixable: the five windows were spent on 2026-08-12 and every one was record-scoped with a read-back-confirmed disarm. The defect this entry records is the MISSING LEDGER ROW, and appending this row is itself the remedy -- there is no further action available. Not marked 'fixed', because that would imply the overrun was undone; it was not, it was disclosed. Waived so the ledger stays honest without blocking ship on a closed piece of history. | 2026-08-18T23:18:10.283Z | 2026-08-18T23:18:22.149Z |
| 17 | 50 | unmet-truth | tests/test_scoring_parity.py | 289 | The @live parity tests still assert against lv_icp_tier, which Phase 50 archived on 2026-08-14 (7 references: lines 289, 292, 401, 403, 404, 427, 494, including settle()/settle_until() polls that will now block to timeout rather than fail fast). They are env-gated behind RUN_LIVE_PARITY, so the offline suite stays green and nothing caught it -- 2821 offline tests pass. Correct migration is to lv_icp_tier_derived, whose values these assertions already match, EXCEPT that it is computed server-side with a ~70-130s backfill, so the settle helpers' timeouts must be re-checked against that latency rather than assumed. Surfaced by Phase 47.5's retrospective verification as a forward-looking item; not a 47.5 defect. Left OPEN deliberately -- unlike the historical entries this one is fixable, and it will bite the next person to run the live suite. | open |  | 2026-08-18T23:22:00.492Z |  |
| 18 | 50 | unmet-truth | scripts/run_scoring_parity.py | 313 | Residual lv_icp_tier readers after the 2026-08-19 confirmation-path fix (0e351e1). Phase 50 archived the property, and an archived HubSpot property returns its frozen last value rather than erroring or nulling, so every reader below silently reports dead data. CORRECT BY DESIGN, leave alone: sweep_tier_dependents.py:51 (TARGET_PROPERTY -- its whole job is finding references to the OLD property) and check_tier_derived_parity.py:186 (compares old against derived; needs both). ARGUABLY CORRECT: snapshot_hubspot_schema.py:45 (schema audit -- records what exists, and the archived property does still exist). GENUINELY STALE, needs repointing to lv_icp_tier_derived: run_scoring_parity.py:258/301/306/313 -- highest value, its tier_match is ANDed into the pass condition so the whole sweep verdict now rests on dead data (docs/OPERATOR-RESCORE.md's 2026-08-19 amendment already redirects operators to check_tier_derived_parity.py, but the script itself was left unfixed); build_loss_reason_report.py:128/211; simulate_rubric_weights.py:163; enrich_coverage_companies.py:321/513/787; build_rescore_report.py:84; build_cloud_workflows.py:1794/6564 (property FETCH lists -- lowest severity, HubSpot ignores unknown names, but they pull a dead field into every record read). Deliberately NOT fixed in one sweep during a milestone seal: each needs its own judgement about whether the derived value is the right substitute, and a blanket rename would be exactly the unreviewed change this ledger exists to prevent. | open |  | 2026-08-19T00:42:55.199Z |  |
| 19 | 51 | deviation | n8n/code/normalizeProviders.js | 420 | n8n has the same country blind spot scripts/backfill_dry_run.py's guard fixes in the dry-run lane, and the operator ruled: record it, do not touch n8n (zero n8n changes/executions is v1.0's binding constraint; a fix needs a redeploy with no credits budgeted). Phase 46 parity rule does NOT compel a fix -- that rule binds the two SCORING engines (src/icp_scoring.py <-> Decide Company Action), and the guard lives in the ENRICHMENT lane, in neither. Defect: normalizeProviders.js:420-422 pushes lv_country_region_normalized straight from ZoomInfo's raw.country; nothing in the path compares it against the record's own native HubSpot country. mergeCompanies.js gates the candidate against the existing DERIVED region, not the native field, so a provider country that contradicts the record's own country is never detected. Why latent, not live: lv_country_region_normalized is system_owned, min_confidence 75. A ZoomInfo-only candidate scores 0.45A + 0.2R + 0.25G + 0.1T with A=0.6, G=0 (sole source), T=0.85 -> 0.355 + 0.2R, max approx 0.555 on fresh data -- under the gate. How it becomes reachable: add a claude_web research candidate that AGREES with the wrong country and the agreement term G goes to 1, taking the combined score to approx 0.90 -- clears 75, promotes, and fires a false non-ANZ hard veto on a real company. Reference implementation: scripts/backfill_dry_run.py's build_candidate_patch guard (HubSpot's own country wins a contradiction; the disagreement is recorded visibly via country_conflict, never resolved silently) -- Gold Coast Turf Club 9604630690 is the live proof case (checkpoint round 1/2, Phase 51-03). CAVEAT (unverified, not measured fact): the score-vs-threshold arithmetic above assumes the 0-1 candidate score is compared against the 0-100 min_confidence threshold -- the natural reading given judge.js:286 divides confidence by 100 to produce accuracy, but this was NOT confirmed live. A future phase must confirm the scale before acting on this entry. | open |  | 2026-08-19T07:46:45.009Z |  |
| 20 | 260823-ono | deviation | scripts/check_tier_derived_parity.py |  | Quick task 260823-ono (metro peak-body named-account override): MRC (Melbourne Racing Club, 9604614548) now diverges between lv_icp_tier (archived, frozen at 'C') and lv_icp_tier_derived (correctly floors to 'B' via lv_named_account_score_floor=60). Pre-registered in KNOWN_STUCK_TRANSITIONS before the CP2 formula push / CP3 record PATCH, not discovered after. Permanent by construction: lv_icp_tier was archived in Phase 50 (D-24) and can never be recalculated again -- unlike WINDOWS.md ids 9-12/14 (WF1-staleness, fixable in principle by a fresh non-identical write), this divergence never closes. The derived value is the correct one. | waived | deliberate consequence of the approved lv_named_account_score_floor=60 override; the archived enum is frozen by construction and the derived value is the correct one | 2026-08-23T08:58:13.393Z | 2026-08-23T08:58:35.792Z |
| 21 | 260823-ono | deviation | scripts/check_tier_derived_parity.py |  | Quick task 260823-ono (metro peak-body named-account override): Perth Racing (9604794662) now diverges between lv_icp_tier (archived; live-read 2026-08-23 shows the key entirely absent -- it was never enriched before this override, so the archived enum never held a value) and lv_icp_tier_derived (correctly floors to 'B' via lv_named_account_score_floor=60 on all-blank inputs). Pre-registered in KNOWN_STUCK_TRANSITIONS as (None, 'B') before the CP2 formula push / CP3 record PATCH, not discovered after. Same class as MRC's entry (permanent by construction, archived property frozen forever) and the same polarity as WINDOWS.md id 14, NOT the WF1-staleness cause of ids 9-12: the derived value is the correct one. | waived | deliberate consequence of the approved lv_named_account_score_floor=60 override; the archived enum is frozen by construction and the derived value is the correct one | 2026-08-23T08:58:20.790Z | 2026-08-23T08:58:35.944Z |
| 22 | 260823-ono | deviation | scripts/backfill_dry_run.py |  | Quick task 260823-ono (metro peak-body named-account override): a forward-looking CLASS, not one script (same pattern as WINDOWS.md id 18) -- oracle consumers whose fetch lists lack lv_named_account_score_floor will under-score the five named accounts (ATC, MRC, SSR, BRC, Perth Racing), scoring them without the score floor. scripts/backfill_dry_run.py is the Phase-52-urgent instance: build_dry_run_row builds HubSpotRecord(properties={}) and PAYLOAD_INPUT_PROPS has no entry for the number property, so a dry-run row for any of the five would compute the pre-floor score. simulate_rubric_weights.py and enrich_coverage_companies.py are in the same family (same missing-fetch-list shape). tests/scoring_fixtures.py::FIT_SCORE_PROPS was updated in this same commit (the oracle's own comparison-harness read path), but that fix does not propagate to these other consumers. | open |  | 2026-08-23T08:58:29.783Z |  |
| 23 | 53 | stub | operator-claude-plugin/scripts/write_grant.py |  | grant['envelope'] is always None -- GRANT-02's arithmetic is 53-02 T1 (deliberate seam, initialised so 53-02 fills rather than reshapes) | fixed | filled by 53-02 T1: plan_grant computes write_grant.envelope() and attaches it | 2026-08-25T06:10:09.375Z | 2026-08-25T00:00:00.000Z |
| 24 | 53 | stub | operator-claude-plugin/scripts/write_grant.py |  | grant['consecutive_disarm_failures'] is always 0 -- D-53-04's guardrail B is 53-02 T2/T3 (deliberate seam) | fixed | filled by 53-02 T2/T3: record_send_outcome writes the counter and guardrail B bounds it | 2026-08-25T06:10:09.525Z | 2026-08-25T00:00:00.000Z |
| 25 | 53 | stub | operator-claude-plugin/scripts/write_grant.py |  | CLOSED_CEILING_BREACH has no producer in Phase 53 -- nothing here measures spend as it happens, so the reason is reachable only by a caller that supplies it. Phase 57 makes it fire on its own. | open |  | 2026-08-25T00:00:00.000Z |  |
| 26 | 53 | deviation | operator-claude-plugin/scripts/write_grant.py |  | envelope()'s projected_executions (1 webhook execution per chunk + 1 sub-execution per record) is PROJECTED, never measured -- nobody has counted executions for a multi-chunk grant end to end. NARROWED 2026-08-27 (Phase 54-01, 54-MEASUREMENT.md): the chunk_count==1 (single-record) case IS now measured against live execution history (executions 11934/11935/11937 pre-F2, 11956/11958/11960 post-fix; execution 11960 isolates one bare-object dispatch to exactly one measured n8n execution) -- and the measurement DIFFERS from the projection (measured 1, projected chunk_count+record_count=2 for that same record set), the first real data point against this formula. What remains genuinely open, unchanged from the original claim: the MULTI-CHUNK case (chunk_count > 1, several webhook executions in one grant) has still never been counted end to end -- this plan's execution budget named no multi-chunk send in reachable history to read. | open |  | 2026-08-25T00:00:00.000Z |  |
| 27 | 54 | deviation | operator-claude-plugin/scripts/scheduled_arm.py |  | The SJ-3 scheduled-poller companion's double pass, recorded per OP-54-02: scheduled_arm.py's companion cannot straddle SJ-3's own in-n8n Execute-Workflow dispatch (that dispatch runs unarmed, always returns write_blocked, inside SJ-3's own single n8n execution with no external hook point), so every record SJ-3 matches costs one unarmed full waterfall that is always refused, plus one armed re-run through this companion's own external webhook path -- two full passes per flagged record, daily (the SJ-3 cadence), bounded by the flagged-record count, arming admin-only via ALLOW_N8N_ARM (the headless/cron authority, unchanged, D-1.1-01). This is architecturally the same full-pass-refused-then-full-pass-again shape G-3 names for the interactive lanes, and it is NOT fixed by F2 (F2 only touches the interactive lane skills' arm-before-dispatch ordering) or by this phase's measurement task. DELIBERATELY LEFT UNFIXED BY OPERATOR RULING OP-54-02, not overlooked -- the v1.1 milestone's D-1.1-01 explicitly carves headless/cron paths out of the grant redesign, and this phase's scope is measuring and naming the interactive case honestly, not rebuilding the scheduled companion's architecture. | open |  | 2026-08-27T00:00:00.000Z |  |
| 28 | 49 | deviation | scripts/rescore_population.py |  | Phase 49's W1 armed window made one undeclared batch_update_companies() call directly against 4 company ids, OUTSIDE the driver's own two-key (DRY_RUN=false + ALLOW_SCORE_BACKFILL=true) arming ceremony -- a plain Python call in a diagnostic shell with no arm keys set. Genuinely disclosed at the time in 49-W1-ARM-RECORD.md:200-210 and 49-RUN-REPORT.md:23, and the declared-vs-actual accounting tables correctly recorded HubSpot batch calls Declared 2 / Actual 3, but it was never registered in this cross-phase ledger -- the register /gsd-ship actually gates on. Same shape as id 16, whose closing sentence is the precedent: a per-phase disclosure is not a ledger entry. Recorded retrospectively 2026-09-03 by the cross-phase secure-phase sweep (49-SECURITY.md Divergence 2), 21 days late. NO RECORD WAS HARMED: the bypass call mutated nothing (byte-identical values, confirmed by an unchanged hs_lastmodifieddate before and after) and the values sent were the five legitimate component properties. The gate was not defeated -- it was bypassed by not using the driver. MECHANISM NOW CLOSED (2026-09-03, commit a4de6f4, threat T-49-43): src/hubspot_client.py::batch_update_companies gained the generalized two-key arm gate (DRY_RUN=false AND one of four registered arm keys, BATCH_WRITE_ARM_KEYS) plus a FORBIDDEN_PROPS disjointness floor, both unconditional ValueError raises on the live-POST path, so the gate now travels with the write and this exact call would be refused today. Five refusal tests, all perturbation-proved RED-then-GREEN. The historical call itself is not undone -- it cannot be; what is fixed is the reachable path. NOT registered here and left to operator judgement: the same run report's W2 arm-cycle excess (2) and Anthropic call excess (2 vs 1). | open |  | 2026-09-03T07:16:45.755Z |  |

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
    "description": "lv_icp_tier archive blocked live: HubSpot rejected DELETE /crm/v3/properties/companies/lv_icp_tier with 400 CANNOT_DELETE_PROPERTY_IN_USE -- WF1's (4625147345) workflow actions still reference the property as a write target, and HubSpot counts this as \"in use\" regardless of the workflow's isEnabled state. Not anticipated by 50-RESEARCH.md or 50-NULL-PROBE.json (RESEARCH Q6). WF1 itself IS switched off live and verified (D-08 complete). Neither deleting WF1 nor editing its actions to strip the reference was attempted -- both are outside this plan's authorised means (the former violates the plan's explicit \"WF1 is not deleted\" prohibition; the latter forfeits the proven one-action rollback mechanism in 50-ROLLBACK-DRILL.md). Retirement (D-06) and the dependent relabel (D-15's fallback) were deferred pending a fresh operator decision among 3 documented options. RESOLVED WITH EVIDENCE (2026-08-14, same-date second live window, Phase 50 Plan 05): the operator selected option 3 -- delete WF1 entirely -- explicitly overriding D-08 (D-24, 50-CONTEXT.md). scripts/put_hubspot_flow.py gained a --delete mode; WF1 deleted (204, independently re-read 404); the archive retried and succeeded (204, confirmed absent and present under ?archived=true); lv_icp_tier_derived relabelled to \"ICP Tier\" in the same window and verified by a two-point D-22 poll. Rollback is now rebuild-from-JSON via POST /automation/v4/flows, not a one-action re-enable -- docs/OPERATOR-TIER-ROLLBACK.md's 2026-08-14 amendment states the mechanism is gone. Full trail: 50-RETIREMENT-RECORD.md's \"D-24 resolution\" section.",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-08-14T02:30:00.000Z",
    "resolved_at": "2026-08-14T02:23:24.962Z"
  },
  {
    "id": 16,
    "kind": "deviation",
    "phase": "47",
    "file": "docs/OPERATOR-VETO-REFRESH.md",
    "line": null,
    "description": "Phase 47 declared ONE armed write window and spent FIVE. Genuinely disclosed at the time in 47-04-SUMMARY.md, 47-RUN-REPORT.md and REQUIREMENTS.md's VETO-02 row, but never registered in this cross-phase ledger -- the register /gsd-ship actually gates on -- so a disclosure present in three phase-local documents was invisible to the one check designed to catch it. Recorded retrospectively by Phase 47's first verification run (2026-08-19, 8 days late; the phase had been sealed without a verifier ever running). No record was harmed: the overrun was in window COUNT, not scope -- every window stayed record-scoped and each disarm was read back and confirmed. Registered for ledger completeness and as the standing reminder that a per-phase disclosure is not a ledger entry.",
    "status": "waived",
    "reason": "Historical, retroactively unfixable: the five windows were spent on 2026-08-12 and every one was record-scoped with a read-back-confirmed disarm. The defect this entry records is the MISSING LEDGER ROW, and appending this row is itself the remedy -- there is no further action available. Not marked 'fixed', because that would imply the overrun was undone; it was not, it was disclosed. Waived so the ledger stays honest without blocking ship on a closed piece of history.",
    "recorded_at": "2026-08-18T23:18:10.283Z",
    "resolved_at": "2026-08-18T23:18:22.149Z"
  },
  {
    "id": 17,
    "kind": "unmet-truth",
    "phase": "50",
    "file": "tests/test_scoring_parity.py",
    "line": 289,
    "description": "The @live parity tests still assert against lv_icp_tier, which Phase 50 archived on 2026-08-14 (7 references: lines 289, 292, 401, 403, 404, 427, 494, including settle()/settle_until() polls that will now block to timeout rather than fail fast). They are env-gated behind RUN_LIVE_PARITY, so the offline suite stays green and nothing caught it -- 2821 offline tests pass. Correct migration is to lv_icp_tier_derived, whose values these assertions already match, EXCEPT that it is computed server-side with a ~70-130s backfill, so the settle helpers' timeouts must be re-checked against that latency rather than assumed. Surfaced by Phase 47.5's retrospective verification as a forward-looking item; not a 47.5 defect. Left OPEN deliberately -- unlike the historical entries this one is fixable, and it will bite the next person to run the live suite.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-18T23:22:00.492Z",
    "resolved_at": null
  },
  {
    "id": 18,
    "kind": "unmet-truth",
    "phase": "50",
    "file": "scripts/run_scoring_parity.py",
    "line": 313,
    "description": "Residual lv_icp_tier readers after the 2026-08-19 confirmation-path fix (0e351e1). Phase 50 archived the property, and an archived HubSpot property returns its frozen last value rather than erroring or nulling, so every reader below silently reports dead data. CORRECT BY DESIGN, leave alone: sweep_tier_dependents.py:51 (TARGET_PROPERTY -- its whole job is finding references to the OLD property) and check_tier_derived_parity.py:186 (compares old against derived; needs both). ARGUABLY CORRECT: snapshot_hubspot_schema.py:45 (schema audit -- records what exists, and the archived property does still exist). GENUINELY STALE, needs repointing to lv_icp_tier_derived: run_scoring_parity.py:258/301/306/313 -- highest value, its tier_match is ANDed into the pass condition so the whole sweep verdict now rests on dead data (docs/OPERATOR-RESCORE.md's 2026-08-19 amendment already redirects operators to check_tier_derived_parity.py, but the script itself was left unfixed); build_loss_reason_report.py:128/211; simulate_rubric_weights.py:163; enrich_coverage_companies.py:321/513/787; build_rescore_report.py:84; build_cloud_workflows.py:1794/6564 (property FETCH lists -- lowest severity, HubSpot ignores unknown names, but they pull a dead field into every record read). Deliberately NOT fixed in one sweep during a milestone seal: each needs its own judgement about whether the derived value is the right substitute, and a blanket rename would be exactly the unreviewed change this ledger exists to prevent.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-19T00:42:55.199Z",
    "resolved_at": null
  },
  {
    "id": 19,
    "kind": "deviation",
    "phase": "51",
    "file": "n8n/code/normalizeProviders.js",
    "line": 420,
    "description": "n8n has the same country blind spot scripts/backfill_dry_run.py's guard fixes in the dry-run lane, and the operator ruled: record it, do not touch n8n (zero n8n changes/executions is v1.0's binding constraint; a fix needs a redeploy with no credits budgeted). Phase 46 parity rule does NOT compel a fix -- that rule binds the two SCORING engines (src/icp_scoring.py <-> Decide Company Action), and the guard lives in the ENRICHMENT lane, in neither. Defect: normalizeProviders.js:420-422 pushes lv_country_region_normalized straight from ZoomInfo's raw.country; nothing in the path compares it against the record's own native HubSpot country. mergeCompanies.js gates the candidate against the existing DERIVED region, not the native field, so a provider country that contradicts the record's own country is never detected. Why latent, not live: lv_country_region_normalized is system_owned, min_confidence 75. A ZoomInfo-only candidate scores 0.45A + 0.2R + 0.25G + 0.1T with A=0.6, G=0 (sole source), T=0.85 -> 0.355 + 0.2R, max approx 0.555 on fresh data -- under the gate. How it becomes reachable: add a claude_web research candidate that AGREES with the wrong country and the agreement term G goes to 1, taking the combined score to approx 0.90 -- clears 75, promotes, and fires a false non-ANZ hard veto on a real company. Reference implementation: scripts/backfill_dry_run.py's build_candidate_patch guard (HubSpot's own country wins a contradiction; the disagreement is recorded visibly via country_conflict, never resolved silently) -- Gold Coast Turf Club 9604630690 is the live proof case (checkpoint round 1/2, Phase 51-03). CAVEAT (unverified, not measured fact): the score-vs-threshold arithmetic above assumes the 0-1 candidate score is compared against the 0-100 min_confidence threshold -- the natural reading given judge.js:286 divides confidence by 100 to produce accuracy, but this was NOT confirmed live. A future phase must confirm the scale before acting on this entry.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-19T07:46:45.009Z",
    "resolved_at": null
  },
  {
    "id": 20,
    "kind": "deviation",
    "phase": "260823-ono",
    "file": "scripts/check_tier_derived_parity.py",
    "line": null,
    "description": "Quick task 260823-ono (metro peak-body named-account override): MRC (Melbourne Racing Club, 9604614548) now diverges between lv_icp_tier (archived, frozen at 'C') and lv_icp_tier_derived (correctly floors to 'B' via lv_named_account_score_floor=60). Pre-registered in KNOWN_STUCK_TRANSITIONS before the CP2 formula push / CP3 record PATCH, not discovered after. Permanent by construction: lv_icp_tier was archived in Phase 50 (D-24) and can never be recalculated again -- unlike WINDOWS.md ids 9-12/14 (WF1-staleness, fixable in principle by a fresh non-identical write), this divergence never closes. The derived value is the correct one.",
    "status": "waived",
    "reason": "deliberate consequence of the approved lv_named_account_score_floor=60 override; the archived enum is frozen by construction and the derived value is the correct one",
    "recorded_at": "2026-08-23T08:58:13.393Z",
    "resolved_at": "2026-08-23T08:58:35.792Z"
  },
  {
    "id": 21,
    "kind": "deviation",
    "phase": "260823-ono",
    "file": "scripts/check_tier_derived_parity.py",
    "line": null,
    "description": "Quick task 260823-ono (metro peak-body named-account override): Perth Racing (9604794662) now diverges between lv_icp_tier (archived; live-read 2026-08-23 shows the key entirely absent -- it was never enriched before this override, so the archived enum never held a value) and lv_icp_tier_derived (correctly floors to 'B' via lv_named_account_score_floor=60 on all-blank inputs). Pre-registered in KNOWN_STUCK_TRANSITIONS as (None, 'B') before the CP2 formula push / CP3 record PATCH, not discovered after. Same class as MRC's entry (permanent by construction, archived property frozen forever) and the same polarity as WINDOWS.md id 14, NOT the WF1-staleness cause of ids 9-12: the derived value is the correct one.",
    "status": "waived",
    "reason": "deliberate consequence of the approved lv_named_account_score_floor=60 override; the archived enum is frozen by construction and the derived value is the correct one",
    "recorded_at": "2026-08-23T08:58:20.790Z",
    "resolved_at": "2026-08-23T08:58:35.944Z"
  },
  {
    "id": 22,
    "kind": "deviation",
    "phase": "260823-ono",
    "file": "scripts/backfill_dry_run.py",
    "line": null,
    "description": "Quick task 260823-ono (metro peak-body named-account override): a forward-looking CLASS, not one script (same pattern as WINDOWS.md id 18) -- oracle consumers whose fetch lists lack lv_named_account_score_floor will under-score the five named accounts (ATC, MRC, SSR, BRC, Perth Racing), scoring them without the score floor. scripts/backfill_dry_run.py is the Phase-52-urgent instance: build_dry_run_row builds HubSpotRecord(properties={}) and PAYLOAD_INPUT_PROPS has no entry for the number property, so a dry-run row for any of the five would compute the pre-floor score. simulate_rubric_weights.py and enrich_coverage_companies.py are in the same family (same missing-fetch-list shape). tests/scoring_fixtures.py::FIT_SCORE_PROPS was updated in this same commit (the oracle's own comparison-harness read path), but that fix does not propagate to these other consumers.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-23T08:58:29.783Z",
    "resolved_at": null
  },
  {
    "id": 23,
    "kind": "stub",
    "phase": "53",
    "file": "operator-claude-plugin/scripts/write_grant.py",
    "line": null,
    "description": "grant['envelope'] is always None -- GRANT-02's arithmetic is 53-02 T1 (deliberate seam, initialised so 53-02 fills rather than reshapes)",
    "status": "fixed",
    "reason": "filled by 53-02 T1: plan_grant computes write_grant.envelope() and attaches it",
    "recorded_at": "2026-08-25T06:10:09.375Z",
    "resolved_at": "2026-08-25T00:00:00.000Z"
  },
  {
    "id": 24,
    "kind": "stub",
    "phase": "53",
    "file": "operator-claude-plugin/scripts/write_grant.py",
    "line": null,
    "description": "grant['consecutive_disarm_failures'] is always 0 -- D-53-04's guardrail B is 53-02 T2/T3 (deliberate seam)",
    "status": "fixed",
    "reason": "filled by 53-02 T2/T3: record_send_outcome writes the counter and guardrail B bounds it",
    "recorded_at": "2026-08-25T06:10:09.525Z",
    "resolved_at": "2026-08-25T00:00:00.000Z"
  },
  {
    "id": 25,
    "kind": "stub",
    "phase": "53",
    "file": "operator-claude-plugin/scripts/write_grant.py",
    "line": null,
    "description": "CLOSED_CEILING_BREACH has no producer in Phase 53 -- nothing here measures spend as it happens, so the reason is reachable only by a caller that supplies it. Phase 57 makes it fire on its own.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-25T00:00:00.000Z",
    "resolved_at": null
  },
  {
    "id": 26,
    "kind": "deviation",
    "phase": "53",
    "file": "operator-claude-plugin/scripts/write_grant.py",
    "line": null,
    "description": "envelope()'s projected_executions (1 webhook execution per chunk + 1 sub-execution per record) is PROJECTED, never measured -- nobody has counted executions for a multi-chunk grant end to end. NARROWED 2026-08-27 (Phase 54-01, 54-MEASUREMENT.md): the chunk_count==1 (single-record) case IS now measured against live execution history (executions 11934/11935/11937 pre-F2, 11956/11958/11960 post-fix; execution 11960 isolates one bare-object dispatch to exactly one measured n8n execution) -- and the measurement DIFFERS from the projection (measured 1, projected chunk_count+record_count=2 for that same record set), the first real data point against this formula. What remains genuinely open, unchanged from the original claim: the MULTI-CHUNK case (chunk_count > 1, several webhook executions in one grant) has still never been counted end to end -- this plan's execution budget named no multi-chunk send in reachable history to read.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-25T00:00:00.000Z",
    "resolved_at": null
  },
  {
    "id": 27,
    "kind": "deviation",
    "phase": "54",
    "file": "operator-claude-plugin/scripts/scheduled_arm.py",
    "line": null,
    "description": "The SJ-3 scheduled-poller companion's double pass, recorded per OP-54-02: scheduled_arm.py's companion cannot straddle SJ-3's own in-n8n Execute-Workflow dispatch (that dispatch runs unarmed, always returns write_blocked, inside SJ-3's own single n8n execution with no external hook point), so every record SJ-3 matches costs one unarmed full waterfall that is always refused, plus one armed re-run through this companion's own external webhook path -- two full passes per flagged record, daily (the SJ-3 cadence), bounded by the flagged-record count, arming admin-only via ALLOW_N8N_ARM (the headless/cron authority, unchanged, D-1.1-01). This is architecturally the same full-pass-refused-then-full-pass-again shape G-3 names for the interactive lanes, and it is NOT fixed by F2 (F2 only touches the interactive lane skills' arm-before-dispatch ordering) or by this phase's measurement task. DELIBERATELY LEFT UNFIXED BY OPERATOR RULING OP-54-02, not overlooked -- the v1.1 milestone's D-1.1-01 explicitly carves headless/cron paths out of the grant redesign, and this phase's scope is measuring and naming the interactive case honestly, not rebuilding the scheduled companion's architecture.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-27T00:00:00.000Z",
    "resolved_at": null
  },
  {
    "id": 28,
    "kind": "deviation",
    "phase": "49",
    "file": "scripts/rescore_population.py",
    "line": null,
    "description": "Phase 49's W1 armed window made one undeclared batch_update_companies() call directly against 4 company ids, OUTSIDE the driver's own two-key (DRY_RUN=false + ALLOW_SCORE_BACKFILL=true) arming ceremony -- a plain Python call in a diagnostic shell with no arm keys set. Genuinely disclosed at the time in 49-W1-ARM-RECORD.md:200-210 and 49-RUN-REPORT.md:23, and the declared-vs-actual accounting tables correctly recorded HubSpot batch calls Declared 2 / Actual 3, but it was never registered in this cross-phase ledger -- the register /gsd-ship actually gates on. Same shape as id 16, whose closing sentence is the precedent: a per-phase disclosure is not a ledger entry. Recorded retrospectively 2026-09-03 by the cross-phase secure-phase sweep (49-SECURITY.md Divergence 2), 21 days late. NO RECORD WAS HARMED: the bypass call mutated nothing (byte-identical values, confirmed by an unchanged hs_lastmodifieddate before and after) and the values sent were the five legitimate component properties. The gate was not defeated -- it was bypassed by not using the driver. MECHANISM NOW CLOSED (2026-09-03, commit a4de6f4, threat T-49-43): src/hubspot_client.py::batch_update_companies gained the generalized two-key arm gate (DRY_RUN=false AND one of four registered arm keys, BATCH_WRITE_ARM_KEYS) plus a FORBIDDEN_PROPS disjointness floor, both unconditional ValueError raises on the live-POST path, so the gate now travels with the write and this exact call would be refused today. Five refusal tests, all perturbation-proved RED-then-GREEN. The historical call itself is not undone -- it cannot be; what is fixed is the reachable path. NOT registered here and left to operator judgement: the same run report's W2 arm-cycle excess (2) and Anthropic call excess (2 vs 1).",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-09-03T07:16:45.755Z",
    "resolved_at": null
  }
]
````
