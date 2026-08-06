---
phase: 40-scoring-engine-remediation-notes
plan: 03
subsystem: infra
tags: [n8n, hubspot, icp-scoring, veto, code-node, live-validation]

requires:
  - phase: 40-scoring-engine-remediation-notes/40-01
    provides: PORTAL-FACTS.md (lv_icp_tier enum, D-05 API round-trip verdict), flow
      tooling (scripts/fetch_hubspot_flow.py, scripts/put_hubspot_flow.py)
  - phase: 40-scoring-engine-remediation-notes/40-02
    provides: tests/scoring_fixtures.py (disposable_company()/settle()/fetch_for_parity()),
      tests/test_scoring_parity.py's live veto_set/veto_clear/tier_on_flag_change tests
provides:
  - lv_anti_icp_flag/lv_anti_icp_reason derived inside ENRICH_DECIDE_CO_CLOUD from
    lv_country_region_normalized/lv_produces_content/lv_is_hardware_vendor, byte-identical
    to src/icp_scoring.py's hard-veto block, recomputed every run
  - DEFAULT_COMPANY_POLICY's veto entries hardened to min_confidence:80 (P2 closed)
  - docs/OPERATOR-VETO-REFRESH.md — the D-02 refresh procedure, plus two newly-discovered
    infrastructure blockers that currently prevent it from completing
affects: [40-05-revenue-boundary-fix, 40-06-tier-and-veto-workflow, 41-backfill]

actuals:
  tokens: 53600
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Live webhook-trigger validation bypassing a broken scheduled-poller dispatch: POST
      directly to the target workflow's own Webhook Trigger (X-Enrichment-Secret header)
      to exercise a Code node's logic on a real n8n Cloud run when the normal dispatch
      path is unavailable"
    - "n8n Execute-Workflow 'call another workflow' mode requires the CALLED workflow to
      expose an Execute Workflow Trigger node — a workflow whose only entry point is a
      Webhook Trigger cannot be reached this way ('Missing node to start execution')"

key-files:
  created:
    - docs/OPERATOR-VETO-REFRESH.md
  modified:
    - n8n/code/mergeCompanies.js
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_review_decision_cloud.json
    - n8n/wf_scheduled_maintenance_cloud.json
    - tests/fixtures/companies_jscode_frozen.json
    - tests/test_cloud_companies_branch.py

key-decisions:
  - "Task 3's live validation used a direct webhook POST to LV Enrichment (Cloud
    template)'s own Webhook Trigger, not the documented SJ-3 poller — SJ-3's dispatch to
    that workflow was found broken (see Known Blockers) partway through validation, so
    the webhook path was the only way left to exercise the live Code node at all."
  - "VETO-01/VETO-02 left unmarked in REQUIREMENTS.md. The derivation code is fully
    verified (byte-identical port, offline+build-invariant tests, live webhook execution
    confirms it computes a correctly-formatted string flag/reason) but a live HubSpot
    PATCH landing on a real record — the bar this plan's own <verification> block and
    D-13 set — could not be proven, because record writes are globally disabled in the
    currently deployed build (see Known Blockers). Marking these complete would
    contradict the evidence."

patterns-established:
  - "The veto derivation lives in the Decide node, never as a mergeCompanies() candidate
    — the pattern any future derived (not provider-supplied) field on the same node
    should follow."

requirements-completed: []

coverage:
  - id: D1
    description: "DEFAULT_COMPANY_POLICY's lv_anti_icp_flag/lv_anti_icp_reason entries
      hardened from min_confidence:0 to 80 (P2 closed); guarded by a test that fails if
      either drops back below 80."
    requirement: "VETO-01"
    verification:
      - kind: unit
        ref: "tests/test_cloud_companies_branch.py::test_merge_companies_veto_policy_entries_carry_a_real_min_confidence"
        status: pass
    human_judgment: false
  - id: D2
    description: "ENRICH_DECIDE_CO_CLOUD derives lv_anti_icp_flag/lv_anti_icp_reason from
      the three canonical veto inputs on every run, as quoted string literals, with
      reason strings and join separator byte-identical to config/icp_scoring.yaml and
      src/icp_scoring.py."
    requirement: "VETO-01"
    verification:
      - kind: unit
        ref: "tests/test_cloud_companies_branch.py::test_decide_company_action_derives_both_veto_fields_via_regionkey_and_boolish"
        status: pass
      - kind: unit
        ref: "tests/test_cloud_companies_branch.py::test_decide_company_action_veto_reason_strings_match_the_rubric_yaml_verbatim"
        status: pass
      - kind: unit
        ref: "tests/test_cloud_companies_branch.py::test_decide_company_action_veto_flag_assignment_is_a_quoted_string_literal"
        status: pass
      - kind: unit
        ref: "tests/test_cloud_companies_branch.py::test_decide_company_action_veto_reason_join_separator_matches_the_oracle"
        status: pass
      - kind: unit
        ref: "tests/test_cloud_companies_branch.py::test_veto_fields_never_enter_enrich_merge_co_candidate_lists"
        status: pass
    human_judgment: false
  - id: D3
    description: "A live n8n Cloud run (direct webhook trigger, bypassing the broken SJ-3
      poller) executes the deployed Decide Company Action node and returns
      lv_anti_icp_flag/lv_anti_icp_reason as correctly-formatted quoted strings — proves
      the derivation runs on the real bounced deploy, not just in the build script."
    requirement: "VETO-01"
    verification:
      - kind: manual_procedural
        ref: "live POST to {N8N_URL}/webhook/hubspot/enrichment/event, 2026-08-06 — response
          body: lv_anti_icp_flag:\"true\", lv_anti_icp_reason:\"Non-ANZ geography\" (see
          Live Validation Findings below for full evidence and caveats)"
        status: pass
    human_judgment: true
    rationale: "Confirms the code executes live and formats correctly, but does NOT
      confirm the PATCH lands on a real HubSpot record (blocked by
      ALLOW_HUBSPOT_RECORD_WRITES=false) or that the derivation reads a genuinely-matched
      record's actual current inputs (identity resolution did not succeed in this run) —
      a human must read the full findings below before treating VETO-01 as live-proven."
  - id: D4
    description: "D-02's operator refresh procedure is documented in
      docs/OPERATOR-VETO-REFRESH.md, including the corrected lv_enrichment_requested
      property name and the two infrastructure blockers discovered while validating it."
    requirement: "VETO-02"
    verification: []
    human_judgment: true
    rationale: "The procedure is written down but is currently non-functional end-to-end
      (both blockers below must be fixed before an operator can actually use it) —
      requires a human decision on priority/scheduling for the fixes, not something this
      plan's tests can auto-pass."

duration: ~66min (includes an operator checkpoint pause between Task 2 and Task 3, plus
  ~40min of live-poller/webhook validation polling)
completed: 2026-08-06
status: complete
---

# Phase 40 Plan 03: Veto Ownership Pipeline Summary

**Ported the oracle's hard-veto derivation into `ENRICH_DECIDE_CO_CLOUD` (byte-identical to `src/icp_scoring.py`) and hardened its dead policy path — live validation confirms the code executes and formats correctly on the real deployed build, but also surfaced two pre-existing infrastructure defects (global write-lock, broken poller dispatch) that block proving a real HubSpot PATCH lands.**

## Performance

- **Duration:** ~66 min total elapsed (Tasks 1-2: ~7 min; operator checkpoint pause for
  the armed deploy + bounce; Task 3 validation: ~45 min, most of it spent polling a
  15-minute scheduler and then diagnosing why it never fired)
- **Started:** 2026-08-06T16:43:12+10:00
- **Completed:** 2026-08-06T17:49:45+10:00
- **Tasks:** 3 (2 `auto`, 1 `checkpoint:human-verify` — deploy handled by the operator,
  live-write proof attempted by this continuation agent)
- **Files modified:** 9 (2 hand-edited, 6 regenerated build artifacts, 1 new doc)

## Accomplishments
- `DEFAULT_COMPANY_POLICY`'s `lv_anti_icp_flag`/`lv_anti_icp_reason` entries raised from
  `min_confidence: 0` to `80` (D-04/P2 closed), guarded by a test that fails if either
  regresses
- `ENRICH_DECIDE_CO_CLOUD` now derives both veto fields from `lv_country_region_normalized`,
  `lv_produces_content`, and `lv_is_hardware_vendor` on every run — `_regionKey()`/`_boolish()`
  helpers, reason strings and join separator (`"; "`) byte-identical to
  `config/icp_scoring.yaml`/`src/icp_scoring.py`, assigned as quoted string literals
  (D-04/P4 closed)
- Deliberately NOT added to `ENRICH_MERGE_CO`'s candidate lists (40-RESEARCH.md Pitfall 4)
  — a dedicated test asserts this
- Operator armed the deploy (all 5 cloud workflows updated, 200) and bounced the affected
  workflows (deactivate/activate 200 pairs, final read-back confirmed all active)
- `docs/OPERATOR-VETO-REFRESH.md` written, then corrected (wrong property name found) and
  extended with a **Known Blockers** section documenting two infrastructure defects found
  during live validation
- Live validation performed against real n8n Cloud + HubSpot portal 22617666; findings
  below

## Task Commits

1. **Task 1: Harden dead veto policy entries (D-04/P2)** - `12a5827` (feat)
2. **Task 2: Port oracle hard-veto branch into ENRICH_DECIDE_CO_CLOUD (D-01)** - `691e78e` (feat)
3. **Task 3 (checkpoint half): disarmed deploy diff review + operator doc** - `523ab59` (docs)
4. **Task 3 (validation half): fix property-name bug + record two live blockers** - `03a8c83` (docs)

**Plan metadata:** pending (this commit)

## Files Created/Modified
- `n8n/code/mergeCompanies.js` - `DEFAULT_COMPANY_POLICY` veto entries hardened to `min_confidence: 80`
- `scripts/build_cloud_workflows.py` - `ENRICH_DECIDE_CO_CLOUD` gains the veto-derivation block (`_regionKey`, `_boolish`)
- `n8n/wf_enrichment_cloud.json` + 3 sibling `wf_*.json` - regenerated build artifacts (mergeCompanies.js is inlined into multiple nodes/workflows)
- `tests/fixtures/companies_jscode_frozen.json` - re-baselined to match the regenerated inline JS
- `tests/test_cloud_companies_branch.py` - 9 new assertions across both tasks (policy threshold, derivation presence, candidate-list exclusion, reason-string parity, string-literal assignment, join separator)
- `docs/OPERATOR-VETO-REFRESH.md` - the D-02 refresh procedure, corrected property name, and the Known Blockers section

## Decisions Made
- **Live validation used a direct webhook POST, not the documented SJ-3 poller.** The
  poller's dispatch step was found broken partway through validation (see Findings below);
  POSTing directly to `LV Enrichment (Cloud template)`'s own Webhook Trigger
  (`X-Enrichment-Secret` header) was the only remaining way to exercise the live Decide
  Company Action node.
- **VETO-01/VETO-02 left unmarked complete in REQUIREMENTS.md.** The derivation code is
  fully verified statically (byte-identical port, 9 passing tests) and was confirmed
  executing correctly on a live, bounced n8n Cloud run — but the plan's own
  `<verification>` bar ("the operator ... confirmed a live run writes the flag as a
  quoted string" on a real record) could not be met, because HubSpot writes are globally
  disabled in the currently deployed build. Marking the requirement complete would
  overstate what was actually proven.
- **All 6 disposable HubSpot companies created during validation were deleted** (204s
  confirmed individually plus a final `assert_no_disposables_survive()` sweep) — two were
  orphaned mid-validation when a `run_in_background`-launched Python process was killed by
  the harness before its `finally` block ran; both were found and cleaned up via a direct
  `delete_record` call once identified.

## Live Validation Findings (Task 3)

The checkpoint's remaining item was: confirm a live enrichment run writes
`lv_anti_icp_flag` as a string `"true"`/`"false"`. Three attempts were made, in order,
each revealing more of the picture:

**Attempt 1 — SJ-3 poller (the documented refresh path).** Created two disposable
companies (`lv_country_region_normalized` = `AU` and `US` respectively) with
`lv_enrichment_requested = "true"`, then polled `lv_anti_icp_flag` for up to 18 minutes
each. Both stayed `null` the entire time, and `lv_enrichment_status` never left `null`
either — the poller never appeared to touch either record.

**Diagnosis via the n8n executions API** (`/api/v1/executions`, workflow `LV Scheduled
Maintenance (Cloud)`): SJ-3 runs every 15 minutes as expected, and its search correctly
found all 4 outstanding disposable companies (`total: 4`, confirmed via a direct
`search_records` call reproducing the exact SJ-3 filter). But the very next node, **`SJ-3
Dispatch To Enrichment`, errors every time with `NodeOperationError: Missing node to
start execution`** (live executions 1891 and 1893, both reproduced). Root cause: that
node calls `LV Enrichment (Cloud template)` via n8n's Execute-Workflow "call another
workflow" mode, which requires the called workflow to expose an **Execute Workflow
Trigger** node — but `LV Enrichment (Cloud template)`'s only entry point is a **Webhook
Trigger**. n8n has no valid start node to begin execution, so the dispatch fails before
ever reaching Decide Company Action. **This is pre-existing and unrelated to 40-03** —
neither commit in this plan touches SJ-3's dispatch node or the target workflow's trigger
set; `scripts/build_cloud_workflows.py`'s SJ-3 wiring (lines ~5573-5595) has looked this
way since it was written. It also means **the entire poller-driven `lv_enrichment_requested`
mechanism has never successfully dispatched an enrichment run** — not just for the veto,
for anything.

**Attempt 2 — direct webhook trigger, bare object_id.** Bypassed SJ-3 by POSTing directly
to `LV Enrichment (Cloud template)`'s own Webhook Trigger
(`{N8N_URL}/webhook/hubspot/enrichment/event`, header `X-Enrichment-Secret`) with a
HubSpot-shaped event payload (`objectId`, `objectType: "company"`, `subscriptionType`,
`occurredAt`). This reached Decide Company Action and returned, synchronously, in the
webhook's own HTTP response:

```json
{"action":"write_blocked","properties":{"lv_anti_icp_flag":"true","lv_anti_icp_reason":"Non-ANZ geography","lv_enrichment_status":"complete"}}
```

Two things, both real signal: (1) the derivation genuinely ran on the live, bounced
deploy and produced a correctly-formatted quoted-string flag with a reason string that
matches `config/icp_scoring.yaml` verbatim — direct evidence the ported code works live,
not just in the build script; (2) `"action":"write_blocked"` — nothing was actually
PATCHed to HubSpot.

**Attempt 3 — direct webhook trigger, with a matching `domain`.** Companies resolve
identity by `domain` (not `object_id` — confirmed in `ENRICH_BUILD_CO_IDENTITY`/`HubSpot
Company Search`), so attempt 2's bare-`objectId` event never matched the record and the
derivation fell back to absent inputs (which correctly fires the non-ANZ veto per this
plan's own `<behavior>` contract — "any other value, including empty or absent, resolves
to non_anz and fires it" — so attempt 2's output was internally consistent, just not
reflective of the record's real properties). Attempt 3 set a real `domain` on the
disposable company and included it in the webhook event for both an AU (no-veto) and a US
(veto) case. Both still returned identical "Non-ANZ geography" output — company identity
resolution still did not pick up the freshly-patched `domain` within this validation's
time-box (root cause not further diagnosed; possibly a HubSpot search-index propagation
race between the `domain` PATCH and the immediately-following webhook POST, possibly a gap
specific to this direct-field test-payload shim per the code's own comment that "a genuine
HubSpot event carries none of these fields" — this is a company-identity-resolution
question, out of this validation task's scope to chase further).

**Root cause discovered independent of both attempts — the actual headline finding:**
reading `Decide Company Action`'s built `jsCode` in the currently deployed workflow
confirms `ALLOW_HUBSPOT_RECORD_WRITES = "false"` is baked in at build time
(`scripts/build_cloud_workflows.py`'s `WRITE_SAFETY_DEFAULTS`, a Python-source literal
compiled into the Code node, not an env var). **This has been `"false"` in every build
this repo has ever produced** — 40-03 did not introduce it, and it is why the webhook
response showed `write_blocked` regardless of identity resolution. **No enrichment run —
poller or webhook — can PATCH a real HubSpot company record right now.** This also
explains PORTAL-FACTS.md's observation that 0/712 companies carry a real
`lv_icp_fit_score` outside 40-01's own flow-validation disposables: the pipeline has never
had live writes enabled in this portal.

**Consequence for the phase.** T-40-11 in this plan's own threat register ("veto ownership
handed to a pipeline that was never bounced, leaving no writer at all") was mitigated by
requiring the operator to confirm a bounced, live run wrote the flag before 40-05 deletes
HubSpot's own veto writer. That confirmation could not be obtained — not because the bounce
failed (it didn't; the operator's deploy/bounce is independently confirmed working and the
derivation code is confirmed correct), but because record writes are globally off. **40-05
should not delete the Geography flow's veto branch until `ALLOW_HUBSPOT_RECORD_WRITES` is
enabled (a deliberate, staged rollout decision per CLAUDE.md §25.5, not something this
validation task should flip unilaterally) and at least one live run is confirmed to
actually PATCH a real record** — otherwise the portal would be left with zero working veto
writers, exactly the DoS scenario T-40-11 exists to prevent.

All 6 disposable companies created across the three attempts were deleted (204 each,
individually confirmed) plus a final portal-wide sweep (`assert_no_disposables_survive()`)
confirming zero `ZZ-SCORING-TEST-DELETE-ME-*` companies remain.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Wrong property name in `docs/OPERATOR-VETO-REFRESH.md`'s refresh step**
- **Found during:** Task 3 validation, before attempting the live run
- **Issue:** The doc's step 2 said `Set enrichment_requested = true` — that property name
  (no `lv_` prefix) belongs to the old local-first MVP Python prototype
  (`src/merge_policy.py`, `CLAUDE.md`), not the cloud pipeline. The real poller-search
  property, confirmed in `scripts/build_cloud_workflows.py`'s SJ-3 filter, is
  `lv_enrichment_requested`. Following the doc as written would have set a property the
  poller never reads, silently never triggering a refresh.
- **Fix:** Corrected to `lv_enrichment_requested`, with an inline note distinguishing it
  from the unrelated local-MVP property.
- **Files modified:** `docs/OPERATOR-VETO-REFRESH.md`
- **Verification:** Cross-checked against `scripts/build_cloud_workflows.py` lines
  5588/5122/5124/416/2631/5591/5624/5663 and `40-PATTERNS.md`/`40-RESEARCH.md`, which both
  independently use the `lv_`-prefixed name.
- **Committed in:** `03a8c83`

**2. [Rule 2 - Missing Critical] Live-validation blockers undocumented**
- **Found during:** Task 3 validation
- **Issue:** The doc as first written implied the refresh path works today. It doesn't —
  two separate infrastructure defects (SJ-3's dispatch error, the global
  `ALLOW_HUBSPOT_RECORD_WRITES=false` write-lock) block it end-to-end. An operator
  following the doc as originally written would wait 15 minutes for nothing, repeatedly,
  with no explanation.
- **Fix:** Added a "KNOWN BLOCKERS" section with full evidence (execution IDs, error
  text, root cause) for both defects, placed before the refresh-path steps so an operator
  sees it first.
- **Files modified:** `docs/OPERATOR-VETO-REFRESH.md`
- **Verification:** Both defects independently reproduced live (SJ-3: executions 1891/1893;
  write-lock: webhook response `action:"write_blocked"` plus direct read of the deployed
  `jsCode`'s `ALLOW_HUBSPOT_RECORD_WRITES` constant).
- **Committed in:** `03a8c83`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing-critical-context). Both are
documentation corrections/additions triggered by genuine live-validation findings — no
code in Tasks 1-2 needed any fix; both discovered defects (SJ-3 dispatch wiring,
`ALLOW_HUBSPOT_RECORD_WRITES`) are pre-existing and out of this plan's `files_modified`
scope to fix (Rule 4 territory — an Execute Workflow Trigger addition and a rollout-gate
flip are both architectural/operator decisions, not auto-fixable).

## Issues Encountered
- `run_in_background: true` on the Bash tool silently killed the second live-validation
  script partway through its poll (no error, no notification, process just stopped
  existing) — two disposable companies were orphaned as a result. Recovered by switching
  to `nohup ... & disown` for subsequent long-running scripts, and by finding and manually
  deleting the two orphans once identified via a direct HubSpot search for the disposable
  name prefix.
- `tests/scoring_fixtures.py`'s `settle()` false-positive-converges on a property that has
  never changed yet (two consecutive `null` reads count as "stable"), which would make
  `tests/test_scoring_parity.py`'s live veto tests report a fast, clean-looking failure
  rather than a genuine 15-minute wait — worth knowing before anyone runs
  `RUN_LIVE_PARITY=true` against those tests expecting them to wait out a real poller
  cycle. Not fixed here (`tests/scoring_fixtures.py`/`tests/test_scoring_parity.py` are
  40-02's files, out of this plan's `files_modified` scope).
- `tests/test_scoring_parity.py::test_veto_clear_after_correction` (40-02) also uses the
  wrong `enrichment_requested` property name (same bug as deviation #1 above) — flagged
  here for whoever owns that file next; not fixed in this plan for the same scope reason.

## User Setup Required
None - no new external service configuration. The operator already completed the
deploy/bounce steps this plan's checkpoint required (confirmed working). The two blockers
found during validation (SJ-3 dispatch, `ALLOW_HUBSPOT_RECORD_WRITES`) require an operator
decision, not a one-time setup step — see Live Validation Findings above.

## Next Phase Readiness
- **40-05 (Geography flow veto-branch deletion) should not proceed** until
  `ALLOW_HUBSPOT_RECORD_WRITES` is enabled for a build and at least one live run is
  confirmed to actually PATCH `lv_anti_icp_flag` onto a real record — otherwise the portal
  would be left with zero working veto writers (T-40-11's exact DoS scenario). This
  supersedes the plan's own T-40-11 mitigation text, which assumed the write-lock would
  not be a factor.
- SJ-3's dispatch defect (Execute Workflow Trigger missing on `LV Enrichment (Cloud
  template)`) blocks the ENTIRE `lv_enrichment_requested`-driven refresh mechanism, not
  just the veto fields — SJ-1 and SJ-2 both rely on the same downstream dispatch (they set
  `lv_enrichment_requested=true` and wait for SJ-3 to pick it up), so this affects every
  scheduled maintenance job in the phase, not only D-02.
- The derivation code itself (Tasks 1-2) is done, tested, and confirmed executing
  correctly on the live bounced deploy — no further code work is needed for VETO-01's
  mechanism once the two blockers above are cleared by whoever owns that decision.
- `docs/OPERATOR-VETO-REFRESH.md`'s Known Blockers section is the authoritative record for
  whoever picks up the SJ-3/write-lock fix next.

---
*Phase: 40-scoring-engine-remediation-notes*
*Completed: 2026-08-06*

## Self-Check: PASSED

All key files confirmed present on disk (`n8n/code/mergeCompanies.js`,
`scripts/build_cloud_workflows.py`, `n8n/wf_enrichment_cloud.json`,
`tests/test_cloud_companies_branch.py`, `docs/OPERATOR-VETO-REFRESH.md`, this SUMMARY).
All 4 commits (`12a5827`, `691e78e`, `523ab59`, `03a8c83`) confirmed present in
`git log --oneline --all`.
