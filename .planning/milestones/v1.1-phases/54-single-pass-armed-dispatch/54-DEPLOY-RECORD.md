# 54-04 Deploy Record — review-decision workflow, contacts approve now writes

**Date:** 2026-08-27
**Workflow deployed:** `LV Review Decision (Cloud)`, id `WBJwoZOo63wzeP69`
**Node deployed:** `Build Review Decision` (the sole node that inlines
`n8n/code/reviewDecision.js`/`n8n/code/reviewApply.js`)
**Mechanism:** `operator-claude-plugin/scripts/n8n_control.apply_mutation` — fetch fresh,
mutate a deep copy of the ONE named node, refuse (`assert_only_allowlisted_change`) unless
every other node/connection/setting is byte-identical, deactivate, PUT, restore the prior
`active` state (the bounce, D-18), independent re-GET, verdict from that re-GET compared
to the requested value. Not `scripts/deploy_n8n_workflows.py`: that script deploys every
locally-diffed `wf_*_cloud.json` in one pass with no per-workflow filter, and Task 1
rebuilt TWO files (this workflow and the maintenance workflow) — using it here would have
put the maintenance workflow's delta live too, which this task explicitly must not do.
`apply_mutation` is scoped to one `workflow_id` by construction, so the maintenance
workflow is structurally unreachable from this deploy.
**Driver:** a scratch script (`deploy_review_decision.py`, not committed — a one-off
driver for this task, per the plan's own execution-budget framing), reading credentials
via `config_gate.load_config()` from `operator-claude-plugin/config/operator.local.json`
(present and valid in this environment; not the root `.env`, which this session cannot
read per project memory `env-file-permission-blocked`).

## Step 1 — Deploy

Live workflow resolved by name (`LV Review Decision (Cloud)` -> `WBJwoZOo63wzeP69`),
confirmed unique among 5 live workflows before mutating.

Pre-deploy fresh GET (baseline):
- node count: 26
- `Build Review Decision` jsCode length: 66010 chars
- contacts-branch marker (`acknowledged — this contact's value was already written by the
  permissive`) present in live code: **False** — confirms the live instance still ran the
  pre-54-03 `no_candidate` behavior before this deploy.

`apply_mutation` result: `verdict = "verified"`, `detail = None`. The requested value
(the local built node's `jsCode`, taken from `n8n/wf_review_decision_cloud.json` as
committed in this plan's Task 1) was returned by `apply_mutation`'s own internal
post-mutation GET and matched exactly.

## Step 2 — Bounce

`apply_mutation` found the workflow's prior `active` state was `true`, so its sequence
was: `POST /deactivate` (ok) -> `PUT` (ok) -> `POST /activate` to restore the prior active
state (ok) — the deactivate/PUT/reactivate cycle IS the bounce; a bare PUT alone never
reloads a running instance (project memory `n8n-stored-vs-running-content`). No separate
bounce call was needed or made outside this sequence.

## Step 3 — Independent read-back (fresh GET, distinct from the PUT response)

A SECOND, separate GET was issued after `apply_mutation` returned (i.e. after its own
internal post-mutation GET already verified) — this is the read-back this record reports,
not the PUT's own response body and not `apply_mutation`'s internal read:

- node count: **26** (matches Task 1's local built count of 26; unchanged)
- contacts-branch marker present in the deployed `Build Review Decision` jsCode: **True**
- `P_CONTACT_PROVENANCE` present: **True**
- deployed jsCode byte-for-byte equal to the local committed
  `n8n/wf_review_decision_cloud.json`'s `Build Review Decision` node: **True**
- `active`: **True**

This is stated explicitly per the plan's instruction: every read-back reported in this
record is a fresh GET, never a stored/cached value and never the PUT's own echo.

## Step 4 — Read-only write-safety verifier

Ran `scripts/verify_live_write_safety.py` (disarmed expectation, the default — no
`--expectation armed` flag passed) against the whole live n8n instance immediately after
the deploy and bounce, with `N8N_URL`/`N8N_API_KEY` exported in-process from
`operator-claude-plugin/config/operator.local.json` (never printed). Coverage: 5
workflows fetched, 15 declaring nodes found (discovered, not a fixed list — per the
script's own D-19 design).

Relevant to this deploy, `LV Review Decision (Cloud)`'s two declaring nodes both read:

```
node 'Build Review Decision': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
node 'Review Decision Update Write Gate': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
node 'Review Contact Decision Update Write Gate': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
```

Every other of the 5 live workflows' declaring nodes read identically disarmed (both
record-write flags false, review-write flag false, both allowlists empty). The one
opposite-polarity constant this script checks separately, `ALLOW_SJ3_DRAIN_WRITES`, reads
`"true"` everywhere it is declared, matching its own PASS expectation (D-05 — the drain
must rest armed, not the record-write flags).

**Overall verdict printed by the script: `VERDICT: disarmed PASS`.**

The review write flag is not enabled anywhere, both record allowlists (`TEST_RECORD_IDS`,
`TEST_RECORD_DOMAINS`) are empty everywhere, including on the two nodes this deploy just
touched or that sit downstream of it.

## Step 5 — Active state

Confirmed twice: once in Step 3's independent fresh GET (`active: True`) and again
implicitly by Step 4's verifier successfully reading live content off the workflow (an
inactive/unreachable workflow would not change this script's coverage count, but the
Step 3 read is the authoritative direct confirmation). The workflow is active after this
deploy, matching its state before the deploy (prior `active` was also `true` —
`apply_mutation` restores the prior state, it does not force a state).

## n8n executions consumed

**0.** Confirmed by listing the 5 most recent executions for
`LV Review Decision (Cloud)` via `executions_client.list_executions` immediately after
the deploy: the newest is `11971`, `startedAt: 2026-08-25T23:10:23.422Z` — two days before
this deploy (2026-08-27) and unrelated to it. Deactivate/PUT/activate and every GET this
task performed are administrative API calls, not workflow triggers, and none of them
appear as an execution. Provider credits: 0 (no provider adapter node is on this
workflow). Anthropic calls: 0 (this workflow has no LLM node).

## The maintenance workflow's delta — committed, NOT deployed

`n8n/wf_scheduled_maintenance_cloud.json` also changed in Task 1 (its `Apply Review` node
embeds the same `reviewApply.js` module, so the third-parameter default addition reaches
it too, even though its own call site is unchanged — still two arguments,
`reviewApply(candidateJson, row)`). That file's local change is **committed in this
plan's Task 1 commit but is NOT deployed by this task.** Confirmed live: the deployed
`LV Scheduled Maintenance (Cloud)` workflow's `Apply Review` node jsCode is still the
PRE-Task-1 content (39 nodes, no "THIRD PARAMETER" comment present) — untouched by this
deploy, exactly as intended. It rides the next maintenance-workflow deploy, whenever that
next deploy happens; deploying it here would have put a scheduled-job workflow's own
bounce inside this phase's blast radius for no gain this task's own scope needs.

## Nothing armed

This task made no call into either of this repo's live-write-granting helpers, made no
widening of `TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS`, and made no flip of
`ALLOW_HUBSPOT_RECORD_WRITES`/`ALLOW_HUBSPOT_CREATE`/`ALLOW_HUBSPOT_REVIEW_WRITES`. The
only content that changed live is the `Build Review Decision` Code node's logic, and Step
4's independent read-only verifier confirms that logic still runs disarmed everywhere it
declares a write-safety constant.
