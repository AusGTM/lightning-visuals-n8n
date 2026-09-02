---
phase: 63-the-unattended-lane-actually-runs-unattended
plan: 05
subsystem: n8n
tags: [deploy, n8n-cloud, disarmed-proof, DROP]

# Dependency graph
requires:
  - phase: 63-the-unattended-lane-actually-runs-unattended
    provides: "63-04's DROP outcome — the throughput todo's lever-2 entry already amended, scripts/build_cloud_workflows.py and every n8n/wf_*.json untouched by that lever"
provides:
  - "63-DEPLOY-RECORD.md — dated evidence that the running n8n Cloud instance now stores the committed workflow JSON (Phase 62's num_associated_contacts and sourceByField), bounced and proven by a disarmed execution rather than a stored read-back"
  - "Closure of the divergence between committed and live workflow JSON open since Phase 62 regenerated all six workflows on 2026-09-02 without deploying (CLAUDE.md §13.0.2)"
  - "The lever-3 max_uses fact (WEB_RESEARCH_MAX_SEARCHES = 5, confirmed in both Build Research Request and Build Contact Research Request) recorded for a later phase, unchanged"
affects: [any-future-63-B-revisit, future-n8n-deploys]

# Actuals (#2632)
actuals:
  tokens: 1700
  tasks: 2
  commits: 1

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deploy-bounce-prove: PUT the workflow set, deactivate/activate each affected workflow, independently re-read the node count, then send one disarmed request and read its execution back to prove the RUNNING instance (not the stored copy) reloaded"

key-files:
  created:
    - .planning/phases/63-the-unattended-lane-actually-runs-unattended/63-DEPLOY-RECORD.md
  modified: []

key-decisions:
  - "Deployed the whole regenerated 5-workflow set in one PUT rather than a single --only file, per the plan's own instruction — the divergence spans several workflows (num_associated_contacts on the companies branch of enrichment, sourceByField on Merge Contacts in contact ingest) and splitting it would leave a partial instance."
  - "This deploy carries Phase 62's change alone, not two phases' worth, because 63-04 took the DROP branch — the judge routing lever was evaluated by offline replay and rejected before this plan ran, so scripts/build_cloud_workflows.py and every n8n/wf_*.json carried no judge-model-routing edit to deploy. The DEPLOY-RECORD states this explicitly rather than using the SHIP-branch wording."
  - "The throughput todo was left completely untouched by this plan — its lever-2 amendment was already made by 63-04 Task 3, and the plan's own instruction says not to write it twice on the DROP branch. Lever-3's observed max_uses value (5) went into the deploy record, not into a second todo edit, since the plan scopes the todo amendment to the SHIP-branch lever-2 entry only."

requirements-completed: [2026-08-04-enrichment-throughput-ceiling]

coverage:
  - id: D1
    description: "Dry run named all five wf_*_cloud.json workflows for update with no REFUSED line and an empty deploy-time overlay, then the live PUT updated all five (200 each)"
    verification:
      - kind: other
        ref: ".venv/bin/python scripts/deploy_n8n_workflows.py (plan's own verify command, output: no REFUSED, named all 5 workflows)"
        status: pass
      - kind: other
        ref: "deploy_n8n_workflows._requested_overlay_flags() (plan's own verify command, output: {})"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every affected workflow was deactivated/reactivated after the PUT and independently re-read active with a node count matching the locally built JSON exactly (enrichment 123)"
    verification:
      - kind: other
        ref: "prove_scale_up_runtime._api GET /workflows/{id} over all 5 workflow ids (plan's own verify command for the enrichment workflow: ACTIVE True NODES 123)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Stored read-back confirms the DROP branch (Build Judge Request carries only claude-sonnet-5, no cheap-model constant) and Phase 62's two changes (num_associated_contacts, sourceByField) in the post-bounce GET"
    verification:
      - kind: other
        ref: "GET /workflows/950HPb7a1GgSAIyZ and /workflows/AwbBeShdPgV48eiY post-bounce, grep of jsCode/jsonBody strings"
        status: pass
    human_judgment: false
  - id: D4
    description: "One disarmed recompute POST for Melbourne Racing Club (9604614548) returned write_blocked, and its execution (12070) read back with includeData=true shows no provider/write/Anthropic node ran"
    verification:
      - kind: other
        ref: "post_webhook_event(recompute=True) response + GET /executions/12070?includeData=true (plan's own acceptance criteria)"
        status: pass
    human_judgment: false
  - id: D5
    description: "63-DEPLOY-RECORD.md tags its live observations, states the cost line, and states what the judge routing proof does not cover"
    verification:
      - kind: other
        ref: "grep -c \"[observed live]\" / grep -c \"nothing armed\" / grep -c num_associated_contacts on 63-DEPLOY-RECORD.md (plan's own verify commands, all non-zero)"
        status: pass
      - kind: e2e
        ref: "node --test tests/n8n/*.test.mjs (862 pass / 0 fail)"
        status: pass
    human_judgment: false

duration: ~30min
completed: 2026-09-02
status: complete
---

# Phase 63 Plan 05: Deploy, Bounce, Prove Summary

**Deployed the committed n8n workflow JSON to n8n Cloud disarmed (all 5 `wf_*_cloud.json` files, empty deploy-time overlay), bounced every affected workflow with an independently re-read node count, and proved the running instance reloaded with one disarmed recompute execution (12070, `write_blocked`, no provider/write/Anthropic node ran) — closing the divergence Phase 62 left open on 2026-09-02.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-09-02 (this session)
- **Completed:** 2026-09-02T06:45:59Z
- **Tasks:** 2 of 2
- **Files modified:** 1 created

## Accomplishments

- Dry-ran `scripts/deploy_n8n_workflows.py` first: named all five cloud workflows for update, zero for create, no `REFUSED` line, and `_requested_overlay_flags()` returned an empty mapping — the JSON about to land matches the JSON the test suites already ran against.
- Deployed the whole regenerated set with `DRY_RUN=false ALLOW_N8N_DEPLOY=true`: all five workflows PUT with HTTP 200.
- Bounced (deactivate → activate) every affected workflow and independently re-read each one active with a matching node count: Backend Status 17, Contact Ingest 29, Enrichment 123, Review Decision 26, Scheduled Maintenance 39 — all unchanged from the locally built JSON, confirming this deploy edited `jsCode`/`jsonBody` strings only and added no node.
- Read back the stored content post-bounce and confirmed it matches the DROP branch (`Build Judge Request` carries only `claude-sonnet-5`, no cheap-model constant) and closes Phase 62's divergence (`num_associated_contacts` present on the companies-search node; `sourceByField` present on `Merge Contacts` in the contact-ingest workflow).
- Opportunistically recorded the lever-3 fact: `WEB_RESEARCH_MAX_SEARCHES = 5` is baked into both `Build Research Request` and `Build Contact Research Request`, feeding `max_uses: 5` on the `web_search_20250305` tool — the previously-unconfirmed value the throughput todo's item 3 asked about, now observed and unchanged.
- Sent one disarmed recompute POST for Melbourne Racing Club (`9604614548`) via `remediate_veto_companies.post_webhook_event(..., recompute=True)`. Response: `write_blocked`. Read execution `12070` back with `includeData=true`: status `success`, mode `webhook`, terminal node `Build Response`, and confirmed none of the 22 nodes that ran match any provider/write/Anthropic marker — zero provider credits, zero Anthropic calls, zero HubSpot writes.
- Wrote `63-DEPLOY-RECORD.md` naming every workflow id, its post-bounce node count, the stored read-back assertions, the proof execution's id/status/terminal action, the observed `max_uses` value, an explicit "what this does not prove" section (judge-routing adequacy is 63-03's offline replay by design, and moot here since DROP shipped no judge-model change), and the cost line.
- `node --test tests/n8n/*.test.mjs`: 862 pass / 0 fail, unaffected by this plan.

## Task Commits

1. **Task 1 + Task 2: Deploy, bounce, prove, and record** - `dda049c` (docs) — both tasks land in one commit because Task 1 (the live deploy/bounce action) produces no local repo diff of its own; its evidence and Task 2's proof-execution evidence are both captured in the single `63-DEPLOY-RECORD.md` this commit creates.

**Plan metadata:** commit pending (this SUMMARY)

## Files Created/Modified

- `.planning/phases/63-the-unattended-lane-actually-runs-unattended/63-DEPLOY-RECORD.md` - Dated evidence of what was PUT, bounced, read back, and proven by execution; states the DROP-branch scope, the cost line, and what the deploy does not prove.

## Decisions Made

- Deployed the whole 5-workflow set rather than `--only` a single file, per the plan's own instruction — the divergence spans multiple workflows and a partial deploy would leave the instance inconsistent.
- The throughput todo (`2026-08-04-enrichment-throughput-ceiling.md`) was left completely untouched. Its lever-2 amendment already exists from 63-04 Task 3; the plan's acceptance criteria explicitly forbid a second amendment on the DROP branch. The observed `max_uses` value went into the deploy record instead of a second todo edit.
- Fixed a line-wrap in the deploy record's cost-line sentence mid-task (Rule 1, trivial self-fix) — the phrase "nothing armed" had wrapped across a Markdown line break, which would have made the plan's own `grep -c "nothing armed"` verify command fail on a technicality despite the content being correct. Rewrapped onto one line; re-ran the verify, passed.

## Deviations from Plan

None beyond the trivial line-wrap fix noted above (not a Rule 1-4 deviation in the substantive sense — no behavior changed, only a Markdown line break was removed so the plan's own grep-based verify command could match text that was already present).

**Total deviations:** 0 substantive.
**Impact on plan:** None.

## Issues Encountered

None. Every verify command in both tasks passed on first or second (post-line-wrap-fix) attempt; no auth gates, no credential resolution failures, no unbound-node refusals.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Both 63-A (sweep launcher, 63-01/63-02) and 63-B (judge lever, 63-03/63-04 DROP) are complete, and this plan closes the deploy divergence D-63-08 flagged. Phase 63 is now fully executed across all five plans.
- **Nothing is armed.** The write allowlist stayed empty throughout this plan — confirmed both by the empty `ENABLE_BAKED_FLAGS` overlay at deploy time and by the `write_blocked` response on the proof execution. The first live UNATTENDED, credit-spending batch still has NOT run (D-63-09 unchanged).
- CLAUDE.md §13.0.2's "committed JSON is now AHEAD of the live instance" note is now stale in the direction of resolution — the running instance holds the committed JSON as of execution `12070` (2026-09-02T06:43Z). A future phase should update that section to record the close.
- The lever-3 fact (`max_uses = 5`) is now an observed starting point rather than an open question, for whichever future phase revisits the throughput todo's remaining levers (1 and 3).

---
*Phase: 63-the-unattended-lane-actually-runs-unattended*
*Completed: 2026-09-02*

## Self-Check: PASSED

`.planning/phases/63-the-unattended-lane-actually-runs-unattended/63-DEPLOY-RECORD.md` confirmed present on disk. Commit `dda049c` confirmed present in `git log --oneline --all`. All of Task 1's and Task 2's `<verify>` commands re-ran clean at write time: dry-run named 5 updates / 0 REFUSED, overlay `{}`, post-bounce `ACTIVE True NODES 123` for the enrichment workflow, `grep -c "[observed live]"` = 3, `grep -c "nothing armed"` = 1, `grep -c num_associated_contacts` = 2, `node --test tests/n8n/*.test.mjs` = 862 pass / 0 fail.
