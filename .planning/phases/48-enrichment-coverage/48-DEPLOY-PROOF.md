# Phase 48 Plan 04: Deploy Proof (D-04 gate — `IF Research Errored`)

Written by Task 1 (baseline + ready-to-paste operator commands). Task 3 appends the
post-bounce live-execution proof after the operator confirms the deploy and bounce are
done. Nothing in this document was produced by a command that set `ALLOW_N8N_DEPLOY` or
ran the deploy script with `DRY_RUN=false` — every read below is a read-only GET or the
deploy script's default disarmed dry run.

## Task 1 — Pre-deploy baseline and ready-to-paste operator commands

### 1. Pre-deploy live baseline (read-only GET)

GET issued 2026-08-12T21:37:42Z against `LV Enrichment (Cloud template)`
(`950HPb7a1GgSAIyZ`) via `operator-claude-plugin/scripts/n8n_read.get_workflow` (the
plugin's read-only module — no activate/deactivate/PUT/PATCH/DELETE path exists in it),
authenticated through `config_gate.load_config()` — never `.env` directly, per the
project's `.env` Read/Bash permission block.

| Field | Value |
|---|---|
| `active` | `true` |
| `updatedAt` | `2026-08-12T07:07:10.392Z` |
| Node count | **109** |
| `IF Research Errored` present | **NO — absent** |
| `Build Research Failure Response` present | **NO — absent** |

Full 109-name baseline node list (sorted), captured at the same GET:

```
Adapt Company Fetch By Id
Adapt Company Search
Adapt Fetch By Id
Adapt Name Search
Adapt Search
Apollo Match
Apollo Org
Apollo Usage
Apply Contact Judge Verdict
Apply Judge Verdict
Build Company Identity
Build Company Requests
Build Contact Judge Request
Build Contact Research Request
Build Identity
Build Judge Request
Build Research Request
Build Response
Claude Web Research
Company Gate
Contact Judge Call
Contact Judge Gate
Contact Research Trigger Gate
Contact Web Research
Credit Request
Decide Action
Decide Company Action
Enrichment Gate
Execute Workflow Trigger
Expand List To Events
HubSpot Company Create
HubSpot Company Fetch By Id
HubSpot Company Search
HubSpot Company Update
HubSpot Create
HubSpot Fetch By Id
HubSpot List By Name
HubSpot List Memberships
HubSpot Name Search
HubSpot Search
HubSpot Update
IF Apollo Credit Requested
IF Apollo Enabled
IF Apollo Org Enabled
IF Bare Event
IF Company Bare Event
IF Company Create
IF Company Enrich
IF Company Recompute
IF Company Skip
IF Contact Needs Judge
IF Contact Research Needed
IF Create
IF Enrich
IF Has Email
IF List Expanded
IF List Input
IF Lusha Company Enabled
IF Lusha Credit Requested
IF Lusha Enabled
IF Name Searchable
IF Needs Judge
IF Object Type Supported
IF Provider Processing Needed
IF Research Needed
IF ZoomInfo Company Enabled
IF ZoomInfo Company Needs Mint
IF ZoomInfo Credit Requested
IF ZoomInfo Enabled
IF ZoomInfo Needs Mint
IF ZoomInfo Usage Needs Mint
Judge Call
Judge Gate
Lusha Company
Lusha Enrich
Lusha Usage
Merge Company
Merge Winners
Normalize + Score
Normalize + Score Company
Parse HubSpot Event
Research Trigger Gate
Respond to Webhook
Route By Object Type
Set Data Quality + Gap Flag
Skip (NoOp)
Sticky Note 1
Sticky Note 2
Sticky Note 3
Sticky Note 4
Sticky Note 5
Sticky Note 6
Sticky Note 7
Unsupported Object Type
Validate Contact Research
Validate Research Output
Webhook Trigger
ZoomInfo Cache Token
ZoomInfo Company
ZoomInfo Company Cache Token
ZoomInfo Company Token Gate
ZoomInfo Enrich
ZoomInfo Mint
ZoomInfo Mint Company
ZoomInfo Token Gate
ZoomInfo Usage
ZoomInfo Usage Cache Token
ZoomInfo Usage Mint
ZoomInfo Usage Token Gate
```

`IF Company Recompute` / `IF Company Skip` (Phase 47.5's recompute lane) are present, as
expected — they were deployed and bounced in Phase 47.5. `IF Research Errored` and
`Build Research Failure Response` (this phase's D-04 gate, built in plan 48-02) are
**absent** — this is the pre-deploy state the post-deploy read in Task 3 must differ from.
Their absence here is what makes their post-bounce presence in a live execution's own node
list (Task 3) meaningful, rather than circular.

Confirmed independently that the committed build artifact already carries both new node
names, staged and waiting to be deployed (`n8n/wf_enrichment_cloud.json`, committed by
plan 48-02, commit `3a1edf1`, unmodified since — `git log --oneline -1 -- n8n/wf_enrichment_cloud.json` still shows that commit as of this write):

```
$ grep -c '"IF Research Errored"' n8n/wf_enrichment_cloud.json
3
$ grep -c '"Build Research Failure Response"' n8n/wf_enrichment_cloud.json
3
```

(3 occurrences each: the node's own name key, the connections source key, and one
`sourceNodeId`/reference inside the connections map — the ordinary shape for a node with
one inbound and one outbound wire, not evidence of duplication.)

### 2. Dry-run deploy diff (default, disarmed — no keys set)

`scripts/deploy_n8n_workflows.py` run in its default mode. Zero writes: `_writes_allowed()`
requires `DRY_RUN=false` **and** `ALLOW_N8N_DEPLOY=true` together; neither was set for this
run.

```
$ .venv/bin/python scripts/deploy_n8n_workflows.py
Workflows to create: []
Workflows to update: ['LV Backend Status (Cloud template)', 'LV Contact Ingest (Cloud template)', 'LV Enrichment (Cloud template)', 'LV Review Decision (Cloud)', 'LV Scheduled Maintenance (Cloud)']
DRY RUN (default) — no writes will be made. Set DRY_RUN=false AND ALLOW_N8N_DEPLOY=true to deploy.
```

Exit code: `0`.

**Known diff noise — do not misread as a real change.** All 5 Cloud-target workflows show
as "to update" because they share the `ENRICH_CO_GATE` shared-workflow node — this is the
same shape 47.5's deploy recorded ("All 5 workflows PUT, 200 each (the shared
`ENRICH_CO_GATE` moves all five...)"). Separately, `compute_workflow_diff`'s own diff
compares nothing meaningful field-by-field: credential ids, `webhookId`, and the
`executeWorkflow` placeholder always differ between the local build (which carries none of
these — they are bound at deploy time) and the live workflow, so a reviewer reading a raw
diff of local-vs-live would see noise on every field, not a signal of what changed
(project memory: `n8n-deploy-diff-noise.md`). "5 to update, 0 to create" is the entire
verdict this dry run can honestly offer; the real change (the two new D-04 nodes) is
confirmed structurally above, from the committed build artifact, not from this diff.

### 3. The two operator commands (Task 2 — ready to paste)

**Command 1 — the deploy, both keys in ONE invocation:**

```
DRY_RUN=false ALLOW_N8N_DEPLOY=true .venv/bin/python scripts/deploy_n8n_workflows.py
```

Setting the two keys in separate shells/invocations silently produces another dry run —
`_writes_allowed()` requires both `DRY_RUN=false` and `ALLOW_N8N_DEPLOY=true` to be true
in the SAME process's environment. Expect the same "Workflows to update" list as the dry
run above, this time followed by `updated workflow <name> (200)` for each of the 5, and
exit code `0`. Activation is deliberately NOT performed by this script (its own docstring:
"a separate operator-runbook step").

**Command 2 — the bounce (deactivate, then reactivate):**

```
.venv/bin/python -c "
import sys; sys.path.insert(0,'operator-claude-plugin/scripts')
import config_gate, n8n_control
cfg = config_gate.load_config()
for want in (False, True):
    r = n8n_control.set_active('950HPb7a1GgSAIyZ', want, cfg)
    print(r.action, '->', r.verdict, '| observed:', r.observed)
"
```

This is the mandatory second step — a bare PUT (Command 1) stores JSON without reloading a
running workflow; n8n keeps executing the OLD in-memory graph until deactivate/activate
forces a reload (Trap 3). `set_active` proves each leg with an INDEPENDENT second GET, not
the mutation's own echo — expect two lines, `turn workflow 950HPb7a1GgSAIyZ off -> verified
| observed: False` then `turn workflow 950HPb7a1GgSAIyZ on -> verified | observed: True`.
If either leg reads anything other than `verified`, STOP and report back rather than
proceeding — do not send Task 3's proof POST against an unconfirmed bounce.

**Blast radius:** both commands touch only `LV Enrichment (Cloud template)`'s stored
definition and (via `ENRICH_CO_GATE`) the four sibling Cloud workflows that share it —
`LV Backend Status`, `LV Contact Ingest`, `LV Review Decision`, `LV Scheduled Maintenance`
(all Cloud templates). No HubSpot record is touched by either command. The bounce is a
few-seconds-long deactivate/reactivate cycle on a webhook- and schedule-triggered
workflow; the daily poller (`SJ-3`, `daysInterval: 1`) has a 24h window, so a bounce
lasting seconds carries no meaningful missed-trigger risk. This is the ONE deploy and ONE
bounce declared in D-06 for this phase — if a second becomes necessary, that is a
disclosure obligation in the run report, not a silent event.

**Claude executed neither command above and will not.** No command run in this task set
`ALLOW_N8N_DEPLOY` or ran the deploy script with `DRY_RUN=false`; the Phase 47.5 waiver
that once delegated arming/deploy to Claude expired with that phase and was not invoked
here.

<!-- Task 3 appends its proof here after the operator confirms the deploy and bounce. -->
