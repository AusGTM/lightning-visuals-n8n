---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 03
subsystem: n8n-workflow-generation
tags: [n8n, merge-node, enrichment-lane, sentinel-pattern, offline-walker]
status: partial
requires: ["70-02"]
provides:
  - enrichment-lane-convergence-merges
affects:
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_enrichment_local_live.json
  - n8n/wf_enrichment_local.json
requirements-completed: [D-70-01]
requirements-not-started: [D-70-02, D-70-07, D-70-08]
tech-stack:
  added: []
  patterns:
    - starved-lane sentinel (additional fan-out edge delivering a `{}` marker
      directly to a specific starved Merge input, bypassing all intermediate
      business/HTTP/provider logic)
    - first-line identity-drop filter on converged Code nodes
      (`Object.keys(it.json || {}).length > 0`) so a sentinel marker is never
      processed as a real row
key-files:
  created:
    - tests/n8n/enrichmentConvergenceMerge.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - tests/n8n/lib/walkWorkflow.mjs
    - tests/test_merge_helpers.py
    - tests/fixtures/companies_jscode_frozen.json
    - tests/n8n/asyncAck.test.mjs
    - tests/n8n/companyNameFallbackFlow.test.mjs
    - tests/n8n/companyRecomputeLaneFlow.test.mjs
    - tests/n8n/linkedinLaneFlow.test.mjs
    - tests/n8n/researchErrorGateFlow.test.mjs
    - tests/n8n/scaleUpFanOutFlow.test.mjs
    - tests/test_cloud_companies_branch.py
    - tests/test_cloud_contacts_branch.py
    - tests/test_enrichment_lane_dedup.py
    - tests/test_fetch_by_id_topology.py
    - tests/test_remaining_credits_response.py
decisions:
  - "classify_convergence had a bug: it returned fan_in for Parse HubSpot Event's
    real 3-source shape (should be entry_points) because it required ALL
    ancestor-set pairs disjoint instead of ANY. Fixed to fire entry_points on any
    disjoint pair. Rule 1 (bug fix), confirmed against the real built graph."
  - "The offline walker (tests/n8n/lib/walkWorkflow.mjs) could not evaluate real
    IF-node expressions using \$(...) or Code nodes using \$runIndex — both are
    used by nodes already in the committed graph outside this plan's scope. Added
    minimal, backward-compatible support (Rule 3, blocking issue) rather than
    hand-rolling a narrower test harness."
  - "Sentinel markers cannot rely on cascading through an intermediate Code
    node's own output once that node has the identity-drop filter — an
    all-marker input wave collapses to zero items there. Every sentinel targets
    the SPECIFIC downstream merge input it protects directly, never a shared
    upstream marker relying on propagation."
  - "Respond to Webhook (fan_in, 4 sources: Build Async Ack, Build Response,
    Build Scale Up Ack, IF List Expanded) was left unmerged deliberately — that
    convergence is Task 2 (D-70-07)'s ack-only redesign, not this task's scope."
  - "9 provider-gate IF-bypass chains (e.g. IF Apollo Enabled <- IF Lusha
    Enabled / Lusha Enrich) classify as fan_in but were left unmerged on
    purpose (class b): one branch is a fast-path bypass of the other, not two
    independent producers that both need to fire before the converged node
    runs once. Merging these would force every gate-skip to wait on a lane that
    never executes."
patterns-established:
  - "starved-lane sentinel: an additional fan-out edge from a single-producer
    upstream node (e.g. Build Identity, Parse HubSpot Event, Enrichment Gate,
    Contact Research Trigger Gate, Decide Action) feeding a narrow Code node
    that computes whether real content will ever reach a specific Merge input
    for the current batch shape, and if not, emits a `{}` marker DIRECTLY to
    that input — never through the business/IF/HTTP chain it starves around, so
    no marker can accidentally trigger a paid provider call or a write attempt."
coverage:
  D-70-01: "done — 6 real convergence points now sit behind an explicit Merge
    (Build Response Merge, Enrichment Gate Merge, Company Gate Merge, Merge
    Winners Fan-In, Merge Company Fan-In, Decide Company Action Merge) in
    wf_enrichment_cloud.json, mirrored in wf_enrichment_local_live.json (Merge
    Winners Fan-In, Merge Company Fan-In). Parse HubSpot Event (entry_points,
    3 alternate triggers) correctly gets none. 9 provider-gate bypass chains
    (class b) correctly left unmerged. Proven via 11 offline-walker tests in
    tests/n8n/enrichmentConvergenceMerge.test.mjs covering single-lane,
    absent-lane, recompute, and mixed-batch shapes, plus a manual probe of the
    lane-none contact-skip terminal (1 real row reaches Build Response, no
    stall)."
  D-70-02: "not started — settings.executionOrder untouched, as the plan
    requires; no action needed for this to remain true, but the requirement's
    own verification step was not separately re-run this task."
  D-70-07: "not started — Respond to Webhook still has 4 inbound edges;
    async_ack flag still present in Parse HubSpot Event and
    operator-claude-plugin/scripts/chunking.py's dispatch_plan."
  D-70-08: "not started — review-decision lane (Build Review Response, Review
    Extract Record, Review Queue Rows) carries no Merge yet."
actuals:
  tokens: 210000
  tasks: 1
  commits: 1
  plan_head_before: 5fa9d4b
metrics:
  duration: "~4.5h"
  completed: "2026-09-10"
---

# Phase 70 Plan 03: One Merge, One Result Channel — Task 1 Summary

Added a real n8n Merge node in front of every genuine fan-in convergence point in the
enrichment lane (contacts + companies branches of `wf_enrichment_cloud.json`, mirrored
in `wf_enrichment_local_live.json`), backed by a starved-lane sentinel network so every
Merge input is guaranteed to fire on any batch shape without ever cascading a marker into
a paid provider call, an Anthropic research/judge call, or a HubSpot write attempt.

## What shipped (Task 1 of 3 — D-70-01 only)

Only Task 1 of this plan's three tasks is complete. Tasks 2 (D-70-07, ack-only webhook +
refusal rows) and 3 (D-70-08, review-decision lane merges) were not started this session
— see "Deviations" below for why, and "Coverage" above for the per-requirement state.

### The 6 merged convergence points (`wf_enrichment_cloud.json`)

| Merge node | Converges | Real (non-sentinel) sources |
| --- | --- | --- |
| `Build Response Merge` | every terminal branch of both contacts and companies | `HubSpot Create`, `HubSpot Update`, `Skip (NoOp)`, `Adapt Company Create`, `HubSpot Company Update`, `IF Enrich`(1), `IF Company Enrich`(1), `Unsupported Object Type`, `IF Company Skip`, `Build Research Failure Response` |
| `Enrichment Gate Merge` | the 5 contact identity lanes | `Adapt Search`, `Adapt Fetch By Id`, `Adapt Name Search`, `Adapt Linkedin Search`, `IF Name Searchable` |
| `Company Gate Merge` | the 2 company identity lanes | `Adapt Company Fetch By Id`, `Adapt Company Name Search` |
| `Merge Winners Fan-In` | contact waterfall + research/judge escalation | `Apply Contact Judge Verdict`, `IF Contact Needs Judge`, `IF Contact Research Needed` |
| `Merge Company Fan-In` | company waterfall + research/judge escalation | `Apply Judge Verdict`, `IF Needs Judge`, `IF Research Needed` |
| `Decide Company Action Merge` | companies recompute lane | `Merge Company`, `IF Company Recompute` |

`Parse HubSpot Event` (3 alternate entry-point triggers: `Execute Workflow Trigger`,
`IF List Expanded`, `IF List Input`) correctly classifies `entry_points` and gets no
Merge — exactly one of its three sources ever runs per execution, so a Merge there would
hang forever.

9 provider-gate IF-bypass chains (e.g. `IF Apollo Enabled` fed by both `IF Lusha
Enabled`'s false-lane bypass and `Lusha Enrich`'s success output) classify `fan_in` but
are deliberately left unmerged — one branch is always a fast-path bypass of the other,
never two independent producers, so merging would force a skipped provider lane to be
waited on.

`Respond to Webhook` (4 sources) is also `fan_in` and also left unmerged — that
convergence belongs to Task 2's ack-only redesign, out of scope here.

### The sentinel network

32 starved-lane sentinel nodes in the built `wf_enrichment_cloud.json` (measured:
`nodes.filter(n => n.name.includes("Sentinel")).length`), organized by what they protect:
pre-fork absence, per-identity-lane absence (contacts: 5, companies: 2), recompute
present/absent, waterfall-absent, research/judge none-needed, and create/enrich-split
absence. 8 more in `wf_enrichment_local_live.json` for its 2 merges. `wf_enrichment_local.json`
(the fully local/offline variant) is unchanged — it has no branching to converge.

Node counts (measured against the committed JSON):

| Workflow | Before | After | Δ merges | Δ sentinels |
| --- | --- | --- | --- | --- |
| `wf_enrichment_cloud.json` | 123 | 161 | +6 | +32 |
| `wf_enrichment_local_live.json` | 46 | 56 | +2 | +8 |
| `wf_enrichment_local.json` | 10 | 10 | 0 | 0 |

(`wf_contact_ingest_cloud.json`'s 9 merges / 2 sentinels predate this plan — landed in
70-02 — and are unchanged by Task 1.)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `classify_convergence` misclassified `Parse HubSpot Event`**
- **Found during:** Task 1, initial design pass over the real graph.
- **Issue:** the pairwise-ancestor-disjoint check required ALL pairs disjoint to return
  `entry_points`; `Parse HubSpot Event`'s real 3-source shape has some overlapping and
  some disjoint pairs, so it fell through to `fan_in` — which would have caused
  `splice_merge_before` to wrap it in a Merge that hangs on every execution (only one of
  the three triggers ever runs).
- **Fix:** changed to return `entry_points` on the first disjoint pair found, `fan_in`
  otherwise.
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Commit:** `8171d2a`

**2. [Rule 3 - Blocking issue] Offline walker couldn't execute the real graph**
- **Found during:** Task 1, first attempt to run the acceptance tests against the
  committed workflow.
- **Issue:** `tests/n8n/lib/walkWorkflow.mjs`'s `evalExpr`/`runCode` never injected a
  `

 resolver or `$runIndex`, both used by nodes already in the graph outside this
  plan's scope (e.g. `IF Bare Event`, `nodeRunRecovery.js`'s carry-read sites).
- **Fix:** threaded `ctx` through `evalExpr`/`resolveValue`/`evaluateIfConditions`,
  added a `makeDollar(ctx.runData, ctx.runIndex)` injection, and defined `$runIndex` in
  `runCode`.
- **Files modified:** `tests/n8n/lib/walkWorkflow.mjs`
- **Commit:** `8171d2a`

### Scope note (not a deviation — explicit deferral)

The plan's own estimate (72,000 tokens, `confidence: low`, 3 tasks) assumed roughly 17
convergence points needing merges, with `alwaysOutputData` on the relevant IF nodes as
the starvation-avoidance mechanism. The real graph has 6 mergeable convergences, but
needed a ~32-node starved-lane sentinel network per workflow instead of `alwaysOutputData`
(rejected in 70-02 precedent as racy per-branch). Task 1 alone consumed the plan's full
estimated budget. Per the executor's atomic close-out invariant and the advisor's
guidance, Tasks 2 and 3 were not started this session rather than shipped half-done;
they remain open work for a follow-on plan/continuation. `70-DEFERRED-GATES.md` Gate 1
(disarmed Merge probe, blocking-human) is unaffected by this partial completion.

## Verification performed

- `node --test tests/n8n/*.test.mjs`: 987/987 pass (includes the new
  `tests/n8n/enrichmentConvergenceMerge.test.mjs`, 11 tests).
- `.venv/bin/python -m pytest -q`: 4629 passed, 154 skipped.
- `operator-claude-plugin/tests/`: 2850 passed, 5 skipped.
- Builder idempotency: two consecutive `python3 scripts/build_cloud_workflows.py` runs
  produce byte-identical JSON.
- Manual probe (this session, post-summary-recovery): a single unmatchable contact row
  (lane `none`, no email/linkedin/name+company) walked end to end with no stall and
  arrived at `Build Response` as exactly 1 real item — confirms the identity-drop filter
  does not also drop real skip-lane rows.
- All disarmed write-safety constants (`ALLOW_HUBSPOT_CREATE`, `ALLOW_HUBSPOT_RECORD_WRITES`,
  `ALLOW_HUBSPOT_REVIEW_WRITES`) confirmed still `"false"` in the committed JSON.
- `settings.executionOrder` confirmed absent from all 5 cloud workflows (D-70-02's
  requirement — untouched, as required).

## Self-Check: PASSED

- `n8n/wf_enrichment_cloud.json`: FOUND, 161 nodes, 6 merge nodes, 32 sentinel nodes.
- `n8n/wf_enrichment_local_live.json`: FOUND, 56 nodes, 2 merge nodes, 8 sentinel nodes.
- `tests/n8n/enrichmentConvergenceMerge.test.mjs`: FOUND.
- Commit `8171d2a`: FOUND in `git log --oneline --all`.
