# 54-06 Deploy Record — review-decision workflow, contacts baseline widened + stale comments fixed

**Date:** 2026-08-27
**Workflow deployed:** `LV Review Decision (Cloud)`, id `WBJwoZOo63wzeP69`
**Nodes deployed (node-scoped `allowed_node_names`):** `Build Review Decision`,
`Review Contact Fetch By Id`, `Review Contact Verify Fetch`,
`Review Queue Contact Search`, `Sticky Note 1` — exactly the five nodes Tasks 1 and 2
changed. `Review Queue Contact Search`'s `parameters` were byte-identical before and
after (Task 1 kept the queue set's membership unchanged), so it was allowlisted but not
actually mutated; leaving it out of `allowed_node_names` would have made
`assert_only_allowlisted_change` refuse the whole deploy before any network call, since
`Sticky Note 1`'s content genuinely did change.
**Mechanism:** `operator-claude-plugin/scripts/n8n_control.apply_mutation` — fetch
fresh, mutate a deep copy of the FIVE named nodes' `parameters` only (id, `credentials`,
`onError`, `position`, `type`, `typeVersion` all come from the live node unchanged — the
local build has no `credentials` key on the HTTP nodes, since n8n injects that
server-side on first save; replacing the whole node dict would have dropped live
HubSpot auth), refuse (`assert_only_allowlisted_change`) unless every other
node/connection/setting is byte-identical, deactivate, PUT, restore the prior `active`
state (the bounce, D-18), independent re-GET, verdict from that re-GET compared to the
requested value.
**Driver:** a scratch script (`deploy_54_06.py`, not committed — a one-off driver for
this task, per the plan's own execution-budget framing and 54-04's precedent), reading
credentials via `config_gate.load_config()` from
`operator-claude-plugin/config/operator.local.json` (present and valid in this
environment; not the root `.env`, which this session cannot read per project memory
`env-file-permission-blocked`).

## Pre-flight: confirmed only `parameters` differs on the five allowlisted nodes

Before mutating, a live-vs-local diff of `parameters` on all five nodes found exactly:
`Build Review Decision.jsCode` (85236 -> 86729 chars), `Review Contact Fetch By Id
.jsonBody` and `Review Contact Verify Fetch.jsonBody` (504 -> 651 chars each, the
widened contacts set), and `Sticky Note 1.content` (2201 -> 2361 chars, the rewritten
Contacts paragraph). `Review Queue Contact Search.parameters` had zero diff — confirming
Task 1 left the queue set's live-equivalent membership unchanged. No other key on any of
the five nodes differed (id, type, typeVersion, onError, credentials, position all
matched).

## Step 1 — Resolve and confirm unique

Live workflow resolved by name (`LV Review Decision (Cloud)` -> `WBJwoZOo63wzeP69`),
confirmed unique among 5 live workflows before mutating.

## Step 2 — Deploy

Pre-deploy fresh GET (baseline):
- node count: 26
- `active`: True
- `Build Review Decision` jsCode length: 85236 chars
- WR-03 marker (`NOT symmetric across policies`) present in live code: **False** —
  confirms the live instance still carried the pre-fix ENUM GUARD text before this
  deploy.
- `Review Contact Fetch By Id` requests `mobilephone`: **False** — confirms the live
  instance still ran the pre-widened contacts baseline before this deploy.

`apply_mutation` result: `verdict = "verified"`, `detail = None`. The requested value
(the local built nodes' `parameters`, taken from `n8n/wf_review_decision_cloud.json` as
committed in this plan's Task 1/Task 2 commits) was returned by `apply_mutation`'s own
internal post-mutation GET and matched exactly.

## Step 3 — Bounce

`apply_mutation` found the workflow's prior `active` state was `true`, so its sequence
was: `POST /deactivate` (ok) -> `PUT` (ok) -> `POST /activate` to restore the prior
active state (ok) — the deactivate/PUT/reactivate cycle IS the bounce; a bare PUT alone
never reloads a running instance (project memory `n8n-stored-vs-running-content`). No
separate bounce call was needed or made outside this sequence.

## Step 4 — Independent read-back (fresh GET, distinct from the PUT response)

A SECOND, separate GET was issued after `apply_mutation` returned (i.e. after its own
internal post-mutation GET already verified) — this is the read-back this record
reports, not the PUT's own response body and not `apply_mutation`'s internal read:

- node count: **26** (matches Task 1/2's local built count; unchanged)
- `active`: **True** (matches prior state)
- `Build Review Decision` jsCode byte-for-byte equal to the local committed
  `n8n/wf_review_decision_cloud.json`'s `Build Review Decision` node: **True**
- `Review Contact Fetch By Id` requests the widened contacts set (`mobilephone`
  present): **True**
- `Review Contact Verify Fetch` requests the widened contacts set (`mobilephone`
  present): **True**
- `Review Queue Contact Search` does NOT request `mobilephone` (queue read stays
  narrow, per Task 1's WR-02 fix): **True**
- `Sticky Note 1` no longer claims a permanent no-write (`ever produced in this
  deployment` absent from the live content): **True**

Every read-back reported in this record is a fresh GET, never a stored/cached value and
never the PUT's own echo.

## Step 5 — Read-only write-safety verifier

Ran `scripts/verify_live_write_safety.py` (disarmed expectation, the default — no
`--expectation armed` flag passed) against the whole live n8n instance immediately after
the deploy and bounce, with `N8N_URL`/`N8N_API_KEY` exported in-process from
`operator-claude-plugin/config/operator.local.json` (never printed). Coverage: 5
workflows fetched, 15 declaring nodes found (discovered, not a fixed list — per the
script's own D-19 design).

Relevant to this deploy, `LV Review Decision (Cloud)`'s three declaring nodes all read:

```
node 'Build Review Decision': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
node 'Review Decision Update Write Gate': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
node 'Review Contact Decision Update Write Gate': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
```

Every other of the 5 live workflows' declaring nodes read identically disarmed (both
record-write flags false, review-write flag false, both allowlists empty). The one
opposite-polarity constant this script checks separately, `ALLOW_SJ3_DRAIN_WRITES`,
reads `"true"` everywhere it is declared (14 nodes), matching its own PASS expectation
(D-05 — the drain must rest armed, not the record-write flags).

**Overall verdict printed by the script: `VERDICT: disarmed PASS`.**

## Step 6 — Active state

Confirmed twice: once in Step 4's independent fresh GET (`active: True`) and again
implicitly by Step 5's verifier successfully reading live content off the workflow. The
workflow is active after this deploy, matching its state before the deploy (prior
`active` was also `true` — `apply_mutation` restores the prior state, it does not force
a state).

## n8n executions consumed

**0.** Listed the 5 most recent executions for `LV Review Decision (Cloud)` via
`n8n_read.recent_executions` immediately after the deploy: the newest is `12001`,
`startedAt: 2026-08-27T03:38:16.631Z` — this session's own earlier 54-05 live-proof
executions (`11997`-`12001`), unrelated to this deploy and predating it. Deactivate/
PUT/activate and every GET this task performed are administrative API calls, not
workflow triggers, and none of them appear as an execution. Provider credits: 0 (no
provider adapter node is on this workflow). Anthropic calls: 0 (this workflow has no
LLM node).

## The maintenance workflow's TWO stranded deltas — committed, NOT deployed

`n8n/wf_scheduled_maintenance_cloud.json` changed in both Task 1 (contacts property
split reaches its `Apply Review` node, which embeds `reviewApply.js`/
`mergeContacts.js`, even though its own call site is unchanged — still two arguments)
and Task 2 (the corrected `reviewApply.js` header ships verbatim into the same inlined
node). Confirmed live: the deployed `LV Scheduled Maintenance (Cloud)` workflow's
`Apply Review` node still lacks the `NOT symmetric across policies` marker — untouched
by this deploy, exactly as intended.

This is a **standing decision, not an oversight**, unchanged from 54-04: deploying the
maintenance workflow here would have put a scheduled-job workflow's own bounce inside
this task's blast radius for no gain this task's own scope needs (54-04's own record
gave the identical reasoning for its one stranded delta). This file now carries TWO
committed-but-undeployed deltas layered on top of each other — 54-04's original
(mergeContacts inline fix) plus this plan's (contacts baseline widening + comment
fixes) — and both ride the next maintenance-workflow deploy, whenever that next deploy
happens.

## Nothing armed

This task made no call into either of this repo's live-write-granting helpers, made no
widening of `TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS`, and made no flip of
`ALLOW_HUBSPOT_RECORD_WRITES`/`ALLOW_HUBSPOT_CREATE`/`ALLOW_HUBSPOT_REVIEW_WRITES`. The
only content that changed live is the five allowlisted nodes' `parameters`, and Step 5's
independent read-only verifier confirms that logic still runs disarmed everywhere it
declares a write-safety constant.
