# Phase 49 Plan 04: Deploy Proof (org-type definitions, RESCORE-01)

Written after the deploy and bounce ran, under waiver `D-49-01` (`49-CONTEXT.md` D-06 —
a NEW, Phase-49-only delegation of the deploy, the bounce and both arming surfaces to
Claude; does **not** revive the expired `D-48-01` / `D-47.5-01`). The operator authorised
spending Phase 49's single declared deploy and bounce at Task 49-04-01's checkpoint on
**2026-08-13**, selecting `deploy-now`. Every command below that could write was run
under that authorisation; every read below is a plain GET or the deploy script's default
disarmed dry run.

## 1. Pre-deploy baseline (read-only GET)

GET issued **2026-08-13T04:45:32.890807Z** against `LV Enrichment (Cloud template)`
(`950HPb7a1GgSAIyZ`) via `operator-claude-plugin/scripts/n8n_read.get_workflow` (read-only
module — no activate/deactivate/PUT/PATCH/DELETE path exists in it), authenticated
through `config_gate.load_config()` — never `.env` directly, per the project's `.env`
Read/Bash permission block.

| Field | Value |
|---|---|
| `active` | `true` |
| `updatedAt` | `2026-08-12T22:35:53.692Z` (Phase 48's deploy — last touch before this one) |
| Node count | **111** (Phase 48's post-deploy baseline; unaffected by this plan's change) |
| `IF Research Errored` present | YES (Phase 48, unrelated to this deploy) |
| `Build Research Failure Response` present | YES (Phase 48, unrelated to this deploy) |
| `Build Research Request` node found | YES (1) |
| `Build Research Request` `jsCode` length | **6928** chars |
| `jsCode` contains `ORG_TYPE_DEFINITIONS` | **NO** — confirms the live lane was still definition-free pre-deploy, matching the folded todo |

This is the state the post-deploy read below must differ from.

## 2. Dry-run deploy diff (default, disarmed — no keys set)

```
$ .venv/bin/python scripts/deploy_n8n_workflows.py
Workflows to create: []
Workflows to update: ['LV Backend Status (Cloud template)', 'LV Contact Ingest (Cloud template)', 'LV Enrichment (Cloud template)', 'LV Review Decision (Cloud)', 'LV Scheduled Maintenance (Cloud)']
DRY RUN (default) — no writes will be made. Set DRY_RUN=false AND ALLOW_N8N_DEPLOY=true to deploy.
```

Exit code: `0`. All 5 Cloud-target workflows show "to update" because they share the
`ENRICH_CO_GATE` shared-workflow node — the same known diff-noise shape Phase 47.5 and
Phase 48 both recorded (project memory: `n8n-deploy-diff-noise.md`). The real change (the
research-prompt definitions) is confirmed structurally in §1 above and §4/§5 below, not
from this diff.

## 3. Deploy — one invocation, both keys together (2026-08-13)

No credential-skip attempt occurred this time (`N8N_URL`/`N8N_API_KEY` were resolved on
the first invocation, via the absolute-path dotenv wrapper — `.env` is Read/Bash
permission-blocked; see `CLAUDE.md`'s constraints and project memory
`env-file-permission-blocked.md`). Exactly one armed invocation was made:

```
$ DRY_RUN=false ALLOW_N8N_DEPLOY=true .venv/bin/python scripts/deploy_n8n_workflows.py
Workflows to create: []
Workflows to update: ['LV Backend Status (Cloud template)', 'LV Contact Ingest (Cloud template)', 'LV Enrichment (Cloud template)', 'LV Review Decision (Cloud)', 'LV Scheduled Maintenance (Cloud)']
updated workflow LV Backend Status (Cloud template) (200)
updated workflow LV Contact Ingest (Cloud template) (200)
updated workflow LV Enrichment (Cloud template) (200)
updated workflow LV Review Decision (Cloud) (200)
updated workflow LV Scheduled Maintenance (Cloud) (200)
EXIT_CODE= 0
```

**This is the declared one PUT-issuing deploy invocation.** `DRY_RUN` and
`ALLOW_N8N_DEPLOY` were set together in one per-shell invocation only, never in `.env`,
never in a shell that outlived this step.

## 4. Bounce — deactivate then reactivate, both legs independently re-read

A bare PUT stores JSON without reloading a running workflow; n8n keeps executing the OLD
in-memory graph until deactivate/activate forces a reload. This is the mandatory second
step:

```
$ .venv/bin/python -c "
import sys; sys.path.insert(0,'operator-claude-plugin/scripts')
import config_gate, n8n_control
cfg = config_gate.load_config()
for want in (False, True):
    r = n8n_control.set_active('950HPb7a1GgSAIyZ', want, cfg)
    print(r.action, '->', r.verdict, '| observed:', r.observed)
"
turn workflow 950HPb7a1GgSAIyZ off -> verified | observed: False
turn workflow 950HPb7a1GgSAIyZ on -> verified | observed: True
```

Both legs verified with an INDEPENDENT second GET, not the mutation's own echo. **This is
the declared one bounce.**

**Blast radius:** identical to Phase 48's — the deploy PUT touches `LV Enrichment (Cloud
template)`'s stored definition and (via the shared `ENRICH_CO_GATE` node) the four sibling
Cloud workflows. No HubSpot record is touched by either the deploy or the bounce.

## 5. Proof — one disarmed recompute execution against the RUNNING instance

**Proof POST.** `scripts.remediate_veto_companies.post_webhook_event('17317850381', True,
cfg, recompute=True)` — `armed=True` is this script's own client-side ceremony flag, not
n8n's write arming; no HubSpot-write arming surface was touched for this proof (no
`ALLOW_HUBSPOT_RECORD_WRITES`, no `TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS` set — disarmed
on the n8n side by construction). Sent **2026-08-13T04:46:31.727757Z**, HTTP 200, client
elapsed 3.38s. Exactly one POST was made; no retry occurred.

Response body, verbatim:

```json
[{"action":"write_blocked","object_type":"companies","hs_object_id":"17317850381","gap_flag":false,"needs_review":false,"row_id":null,"mode":null,"match":{"tier":"unknown","auto":false,"reason":"no searchable identity — the row has no email, object id, or name+company pair","candidates":[]},"properties":{"lv_anti_icp_flag":"true","lv_anti_icp_reason":"Non-ANZ geography"},"remaining_credits":[]}]
```

**Execution located and read back.** `executions_client.find_execution_for_dispatch`
against `LV Enrichment (Cloud template)`'s 5 most recent executions selected execution
**`11871`** (`startedAt 2026-08-13T04:46:32.503Z`, ~0.8s after dispatch, well inside
tolerance). Read via `GET /api/v1/executions/11871?includeData=true`.

| Field | Value |
|---|---|
| `status` | `success` (not treated as proof by itself — judged by `runData` below) |
| `finished` | `true` |
| `resultData.error` | `None` (absent) |
| `lastNodeExecuted` | `Respond to Webhook` |
| `startedAt` → `stoppedAt` | `2026-08-13T04:46:32.503Z` → `2026-08-13T04:46:34.962Z` |
| duration | 2.459s |
| `mode` | `webhook` |

This matches the healthy recompute-lane shape (Phase 47.5's `11852`, Phase 48's `11865`):
`Decide Company Action` ran and produced a real decision, ending at `Respond to Webhook` —
not the died-early shape (chain stopping at `Normalize + Score Company` with 0 items out).

**Node-level check (not top-level status).** `resultData.runData` carries **20 nodes**, in
order:

```
Webhook Trigger, IF List Input, Parse HubSpot Event, IF Object Type Supported,
Credit Request, Route By Object Type, IF Lusha Credit Requested,
IF Apollo Credit Requested, IF ZoomInfo Credit Requested, Build Company Identity,
IF Company Bare Event, HubSpot Company Fetch By Id, Adapt Company Fetch By Id,
Company Gate, IF Company Recompute, Decide Company Action, IF Company Create,
IF Company Enrich, Build Response, Respond to Webhook
```

None carries a node-level `error` field (checked every entry in `runData`, not just the
top-level `status`). `Decide Company Action` output, verbatim:

```json
{
  "action": "write_blocked",
  "object_type": "companies",
  "hs_object_id": "17317850381",
  "gap_flag": false,
  "needs_review": false,
  "row_id": null,
  "mode": null,
  "match": {"tier": "unknown", "auto": false, "reason": "no searchable identity — the row has no email, object id, or name+company pair", "candidates": []},
  "properties": {"lv_anti_icp_flag": "true", "lv_anti_icp_reason": "Non-ANZ geography"}
}
```

Zero provider, research, judge, or merge node appears in `runData` — the recompute lane
routes straight from `Company Gate` to `Decide Company Action` (D-09/CLAUDE.md §13.0).
This proof therefore cost **0 provider credits and 0 Anthropic calls**, plus 1 n8n
execution, 0 HubSpot writes.

### 5a. The load-bearing check — the execution's OWN embedded `workflowData.nodes`

The full graph snapshot n8n stored for this execution at run time, independent of which
branch actually fired — this is what proves the RUNNING instance's graph, never a
`GET /workflows/{id}` read of the stored definition (Trap 3, explicitly refused as proof).

| Check | Result |
|---|---|
| `workflowData.nodes` count | **111** — unchanged from the §1 baseline (this plan changes a node's `jsCode` content, not the graph topology; no new node is expected or found) |
| `IF Research Errored` present | YES (unaffected, Phase 48) |
| `Build Research Failure Response` present | YES (unaffected, Phase 48) |
| `Build Research Request` node found | YES (1) |
| `Build Research Request` `jsCode` length | **9392** chars — up from the §1 baseline's 6928 (the +2464 chars is the added `ORG_TYPE_DEFINITIONS` const plus the `researchSystemPrompt()` rendering line) |
| `jsCode` contains `const ORG_TYPE_DEFINITIONS` | **YES** |
| `jsCode` contains all nine org-type keys | **YES** — `governing_body_league`, `content_producer`, `broadcaster`, `individual_club_team`, `regulator`, `gambling_operator`, `hardware_vendor`, `other`, `unknown` |

**The stricter check — running the node's OWN emitted code and reading its actual return
value**, not just grepping the jsCode text (per `49-03-SUMMARY.md`'s own caution: the
module carrying `ORG_TYPE_DEFINITIONS` is inlined into this node's jsCode regardless of
whether `researchSystemPrompt()` actually consumes it, since the module is already
inlined there for `ORG_TYPES`/`CONTENT_TYPES`). Executed the jsCode extracted from
execution `11871`'s own `workflowData.nodes` — the running instance's code, not the local
repo file — via `new Function`, the exact harness `tests/n8n/orgTypeDefinitionsPrompt.test.mjs`
uses:

```
$ node -e '
const { ORG_TYPES, ORG_TYPE_DEFINITIONS } = require("./n8n/code/taxonomy.generated.js");
const jsCode = <extracted from execution 11871 workflowData.nodes>;
const $input = { all: () => [{ json: {
  research_needed: true,
  identity_keys: { domain: "exampleco.example" },
  existingRecord: { domain: "exampleco.example" },
} }] };
const fn = new Function("$input","$vars","$env","$node","$now","$today", `"use strict";\n${jsCode}`);
const out = fn($input, undefined, {}, {}, new Date(), new Date()) || [];
const prompt = out[0].json.research_request_body.system;
...
'
rows emitted: 1
system is string: true
prompt length: 3868
every org type key+definition present: true
includes QRIC: true
includes Racing NSW: true
includes enum JSON.stringify(ORG_TYPES): true
```

The `research_request_body.system` string the RUNNING node actually returns, the relevant
excerpt quoted verbatim (all nine definitions present, not paraphrased):

```
lv_org_type option definitions: - governing_body_league: Holds commercial control of a
sport or competition: sets the calendar or race programme, distributes prizemoney, and
holds media rights and sponsorship, whether or not it ALSO carries statutory regulatory
powers. Anchor example: Racing NSW, a statutory body that nonetheless programmes racing,
distributes prizemoney, collects Race Fields fees and runs its own streaming. -
content_producer: Produces and distributes broadcast or streaming content but does not
govern the sport it covers -- a media/production entity, not the competition's
controlling body. - broadcaster: A media company or network that airs or streams sport
content, typically without governing the competition itself. - individual_club_team: A
single club, team, or venue-level sporting organisation -- not a governing body, league,
or peak body for the wider sport. - regulator: Integrity, licensing and stewarding ONLY,
where a DIFFERENT body holds the commercial functions (calendar, prizemoney, media
rights, sponsorship). Anchor example: QRIC, where Racing Queensland holds the commercial
functions. Statutory origin is NOT the test -- both a pure regulator and a governing body
can be created by an Act. - gambling_operator: A bookmaker, betting exchange, or
wagering/gaming operator -- takes bets or offers gambling products, rather than producing
or governing sport. - hardware_vendor: An AV/LED/display or systems-integration vendor
supplying broadcast hardware -- not a sports-media buyer; a hard-veto trigger. - other: A
company that does not fit any other org_type option -- identity is known but the
category is genuinely outside this list. - unknown: Identity or category could not be
established from the evidence available -- the default; never guessed into.
```

This is stronger evidence than a jsCode substring match: it proves the RUNNING node's
`researchSystemPrompt()` function, when actually invoked, emits the org-type-defining
prompt string to the model — not merely that the definitions text happens to sit inert in
an unused inlined module.

## 6. What is proven and what is not

**Proven:** the RUNNING instance's `Build Research Request` node — structurally (its own
embedded jsCode, extracted from a live execution, never a stored-definition GET) and
behaviourally (its own emitted code, executed, returns a prompt string carrying all nine
org-type keys and definitions, including the QRIC/Racing NSW anchor examples, with the
strict enum constraint unweakened) — now carries the fix. The recompute lane continues to
function correctly end to end post-deploy, disarmed, writing nothing.

**Not proven this phase (same limitation Phase 48 recorded for its own gate):** the
research branch's live FIRING with a real Anthropic call and a genuine misclassification
avoided in production. No execution in this plan traverses the research branch — the
recompute lane bypasses providers/research/judge by design (D-09/§13.0), and there is no
supported way to force a live research call on demand without spending Anthropic/provider
budget this plan declares zero of. Structural presence plus the executed-node behavioural
proof above is the proof bar this phase meets, matching the standard `tests/n8n/orgTypeDefinitionsPrompt.test.mjs`
already sets offline.

## 7. Budget note

**1 n8n execution** (`11871`) against the 2,500/month allowance (~0.04%). **0 provider
credits, 0 Anthropic calls, 0 HubSpot writes.** Exactly 1 deploy invocation issuing PUTs
(§3), exactly 1 bounce (§4), no credential-skip attempts this run.

## 8. Post-deploy section — disarmed verification and independent allowlist re-read

This section runs regardless of the deploy leg's outcome (it did succeed here, but the
verification below is unconditional per the plan's own rule — closing the window always
wins).

### 8a. `scripts/verify_live_write_safety.py` disarmed pass

```
$ .venv/bin/python scripts/verify_live_write_safety.py
expectation: disarmed
coverage: 5 workflow(s) fetched, 14 declaring node(s) found
drain authority: ALLOW_SJ3_DRAIN_WRITES expected "true", declared by 13 node(s) — PASS
workflow 'LV Scheduled Maintenance (Cloud)':
  node 'SJ-3 Dispatch Gate': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
  node 'SJ-3 Drain Gate': ALLOW_SJ3_DRAIN_WRITES='true'
  node 'SJ-1 Set Requested Write Gate': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
  node 'SJ-2 Set Requested Write Gate': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
  node 'Dedupe Set Needs Review Write Gate': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
  node 'Review Apply Update Write Gate': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
workflow 'LV Enrichment (Cloud template)':
  node 'Decide Action': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
  node 'Decide Company Action': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
workflow 'LV Contact Ingest (Cloud template)':
  node 'Decide Action': ALLOW_HUBSPOT_CREATE='false'
  node 'HubSpot Update Write Gate': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
  node 'HubSpot Create Write Gate': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
workflow 'LV Review Decision (Cloud)':
  node 'Build Review Decision': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
  node 'Review Decision Update Write Gate': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
  node 'Review Contact Decision Update Write Gate': ALLOW_HUBSPOT_RECORD_WRITES='false' ALLOW_HUBSPOT_CREATE='false' ALLOW_HUBSPOT_REVIEW_WRITES='false' TEST_RECORD_IDS='' TEST_RECORD_DOMAINS='' ALLOW_SJ3_DRAIN_WRITES='true'
VERDICT: disarmed PASS
```

Exit code `0`. `coverage: 5 workflow(s) fetched, 14 declaring node(s) found` — a
non-zero-discovery scan, per the script's own rule (a zero-discovery scan would be a
failure, never a disarmed pass by omission).

**This IS the independent allowlist re-read.** Every `TEST_RECORD_IDS='' TEST_RECORD_DOMAINS=''`
above is a fresh GET against the live workflow definitions issued by this script's own
`_get_live_workflows()` call — not a re-read of the deploy's PUT response body, and not
the same GET object used in §1's baseline read (a new HTTP round-trip, run after the
deploy and bounce completed). Both facts hold across every declaring node found: the
record-write allowlist (`TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS`) is **empty everywhere**,
and every write-enabling boolean (`ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`,
`ALLOW_HUBSPOT_REVIEW_WRITES`) reads `'false'` everywhere it is declared.
`ALLOW_SJ3_DRAIN_WRITES` correctly reads `'true'` everywhere (Phase 44's rest-state
default, checked with the opposite polarity by design — the SJ-3 drain must run at rest).

### 8b. Fresh-shell demonstration — no arming variable survived the window

```
$ env | grep -E "^DRY_RUN=|^ALLOW_N8N_DEPLOY=" || echo "no arming vars in current shell env"
no arming vars in current shell env

$ bash -c "
cd <repo root>
.venv/bin/python -c \"
from dotenv import load_dotenv
load_dotenv('<abs path>/.env')
import os
print('DRY_RUN in fresh shell env:', os.getenv('DRY_RUN'))
print('ALLOW_N8N_DEPLOY in fresh shell env:', os.getenv('ALLOW_N8N_DEPLOY'))
import runpy, sys
sys.argv = ['deploy_n8n_workflows.py']
try:
    runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')
except SystemExit as e:
    print('EXIT_CODE=', e.code)
\"
"
DRY_RUN in fresh shell env: true
ALLOW_N8N_DEPLOY in fresh shell env: false
Workflows to create: []
Workflows to update: ['LV Backend Status (Cloud template)', 'LV Contact Ingest (Cloud template)', 'LV Enrichment (Cloud template)', 'LV Review Decision (Cloud)', 'LV Scheduled Maintenance (Cloud)']
DRY RUN (default) — no writes will be made. Set DRY_RUN=false AND ALLOW_N8N_DEPLOY=true to deploy.
EXIT_CODE= 0
```

`.env` itself declares these two variables at their disarmed values (`DRY_RUN=true`,
`ALLOW_N8N_DEPLOY=false`) — a brand-new shell invocation, sourcing nothing carried over
from the arming step in §3, reads the disarmed values and the deploy script defaults to
its dry-run path, exit `0`, zero writes. No environment variable that armed §3's write
survived past that single invocation into this fresh process.

**Verdict: nothing is armed at the end of this plan.** Both checks above ran after the
deploy and bounce succeeded — the plan's rule that this section runs regardless of the
deploy leg's outcome did not need to be exercised on a failure path this time, but the
verification itself is unconditional and would have run identically had §3 or §4 failed.

## 9. Post-plan regression check

```
$ node --test tests/n8n/*.test.mjs
ℹ tests 676
ℹ pass 676
ℹ fail 0
```

Green, both the general suite and (within it)
`tests/n8n/orgTypeDefinitionsPrompt.test.mjs`'s own offline assertions against the
committed `n8n/wf_enrichment_cloud.json` / `wf_enrichment_local_live.json` — unaffected by
this deploy, since deploying never rewrites the committed build artifact.

**`git log --oneline -1 -- n8n/wf_enrichment_cloud.json`** shows Plan 49-03's commit as
the last touch to that file — this plan did not modify it (deploy reads the committed
artifact and PUTs it; it never hand-edits it).
