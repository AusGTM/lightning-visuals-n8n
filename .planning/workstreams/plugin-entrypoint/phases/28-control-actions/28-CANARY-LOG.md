# 28-CANARY-LOG — RB-7 / plan 28-06, the armed arm→dispatch→disarm cycle

**Status: PRE-FLIGHT SEEDED, CANARY NOT YET RUN.** Everything below the pre-flight section is a
blank waiting on the operator. Nothing in this file may be filled in from expectation — every
verdict is an observation or it is left empty.

---

## Pre-flight — established read-only, 2026-08-03, before any arming

GETs only. No arm, no deploy, no write.

| Item | Value |
|---|---|
| Lane | **enrichment** (step 1's preferred branch; `enrichment.dispatch_enrichment` shipped in Phase 25) |
| Target workflow | `950HPb7a1GgSAIyZ` — `LV Enrichment (Cloud template)`, `active=true` |
| Record allowlist | `9604614548` — one HubSpot **company** id, the test company Probe B4 and the Phase 22 canary used |
| Domain allowlist | *(empty)* |
| `allow_create` | `false` — an update to an existing company, not a create |
| `control` capability | passes against the installed `operator.local.json` |
| Tenant | `https://alexherman.app.n8n.cloud` |

**Flag state BEFORE, read live via `n8n_read.read_write_safety` across every deployed workflow.**
`(Nn)` is the count of declaring nodes.

```
Cj83mOgrIm59oxcX  active=True   'LV Backend Status (Cloud template)'   — no write-safety declarations
AwbBeShdPgV48eiY  active=True   'LV Contact Ingest (Cloud template)'
      ALLOW_HUBSPOT_RECORD_WRITES='false'(2n)  ALLOW_HUBSPOT_CREATE='false'(3n)
      ALLOW_HUBSPOT_REVIEW_WRITES='false'(2n)  TEST_RECORD_IDS=''(2n)  TEST_RECORD_DOMAINS=''(2n)
950HPb7a1GgSAIyZ  active=True   'LV Enrichment (Cloud template)'        <-- TARGET
      ALLOW_HUBSPOT_RECORD_WRITES='false'(2n)  ALLOW_HUBSPOT_CREATE='false'(2n)
      ALLOW_HUBSPOT_REVIEW_WRITES='false'(2n)  TEST_RECORD_IDS=''(2n)  TEST_RECORD_DOMAINS=''(2n)
WBJwoZOo63wzeP69  active=False  'LV Review Decision (Cloud)'
      ALLOW_HUBSPOT_RECORD_WRITES='false'(2n)  ALLOW_HUBSPOT_CREATE='false'(2n)
      ALLOW_HUBSPOT_REVIEW_WRITES='false'(2n)  TEST_RECORD_IDS=''(2n)  TEST_RECORD_DOMAINS=''(2n)
1fXPuIabz3RsAHgn  active=True   'LV Scheduled Maintenance (Cloud)'
      ALLOW_HUBSPOT_RECORD_WRITES='false'(4n)  ALLOW_HUBSPOT_CREATE='false'(4n)
      ALLOW_HUBSPOT_REVIEW_WRITES='false'(4n)  TEST_RECORD_IDS=''(4n)  TEST_RECORD_DOMAINS=''(4n)
```

No disagreement was reported on any flag in any workflow.

### Two things the operator should expect, recorded before the run so they are not mistaken for defects

1. **The reload gap does not bite on this path.** `n8n_control.apply_mutation` brackets its PUT with
   deactivate → PUT → restore-prior-active, and the target is active, so the arm's activate forces
   the running instance to reload the armed content *before* the verify GET. The disarm uses the same
   bracket. The gap found under RB-3 was in `deploy_n8n_workflows.py`, which never activates.
2. **`dispatch_fn` is not wired by the surface.** `plan_action(kind="arm_dispatch")` composes the
   proposal; `execute_action` calls `proposal["dispatch_fn"]`; neither `control_actions.py` nor
   `backend-control/SKILL.md` says who sets it. The plugin session has to. **This is a finding about
   the shipped surface** — record below whether the session wired it unaided, needed the runbook's
   snippet, or got it wrong.

**Step 6, pre-computed from source (still to be confirmed live):** the plugin's
`_render_literal(True)` produces `"true"` and the deploy script's `_OVERLAY_FLAG_SPEC` enabled
literal is `"true"` — identical by construction. Allowlist values: plugin `json.dumps("9604614548")`
vs deploy's comma-separated quoted string — also identical for a single id. A difference here would
be a genuine surprise.

---

## The run — to be filled in by the operator

### Step 0 — installed plugin refreshed
- Plugin updated: ☐ / verdict:
- `skills/backend-control/SKILL.md` opens with the "Where commands run" note: ☐

### Step 2 — flag state BEFORE, re-read fresh — **DONE 2026-08-03T03:27:46Z**

**A. Phase 27 status surface, target workflow** (`python3 scripts/status.py 950HPb7a1GgSAIyZ`):

```
LV Enrichment (Cloud template)   active: true
  ALLOW_HUBSPOT_RECORD_WRITES = "false"  nodes: [Decide Action, Decide Company Action]  disagreement: null
  ALLOW_HUBSPOT_CREATE        = "false"  nodes: [Decide Action, Decide Company Action]  disagreement: null
  last_run: 1116  success  2026-08-03T01:11:53.127Z → 01:11:55.846Z   in_flight: false  stuck: false
```

The same call's `backend` block returned `"available": false, "reason":
"unrecognized_response_shape"` with every count `unknown` — **the known open client-side bug** (the
webhook array-wraps its answer; curl shows real data). Recorded so it is not read as a sick backend.

**B. Full-tenant flag inventory**, all five overlayable flags, every deployed workflow. `(Nn)` =
declaring-node count; no `disagreement` on any flag in any workflow:

```
Cj83mOgrIm59oxcX  active=True   'LV Backend Status (Cloud template)'   — no declarations
AwbBeShdPgV48eiY  active=True   'LV Contact Ingest (Cloud template)'
      RECORD_WRITES='false'(2n)  CREATE='false'(3n)  REVIEW_WRITES='false'(2n)  IDS=''(2n)  DOMAINS=''(2n)
950HPb7a1GgSAIyZ  active=True   'LV Enrichment (Cloud template)'        <-- TARGET
      RECORD_WRITES='false'(2n)  CREATE='false'(2n)  REVIEW_WRITES='false'(2n)  IDS=''(2n)  DOMAINS=''(2n)
WBJwoZOo63wzeP69  active=False  'LV Review Decision (Cloud)'
      RECORD_WRITES='false'(2n)  CREATE='false'(2n)  REVIEW_WRITES='false'(2n)  IDS=''(2n)  DOMAINS=''(2n)
1fXPuIabz3RsAHgn  active=True   'LV Scheduled Maintenance (Cloud)'
      RECORD_WRITES='false'(4n)  CREATE='false'(4n)  REVIEW_WRITES='false'(4n)  IDS=''(4n)  DOMAINS=''(4n)
```

**C. Execution baseline — the line that makes "nothing was sent" checkable.**
Highest execution id at 03:27:48Z is **1147**. Ids 1144–1147 are `Cj83mOgrIm59oxcX` (LV Backend
Status) and are this read's own `status.py` calls, not backend activity. The target workflow
`950HPb7a1GgSAIyZ` has had **no execution since 1116** (01:11:53Z).

> **Therefore: any execution on `950HPb7a1GgSAIyZ` with an id above 1147 belongs to this canary.
> The decline path must produce none.**

### Step 3 — the decline path
- Consequence sentence shown before any confirmation, **verbatim**:
- Did it name what live writes permit? ☐
- Did it name the single record the grant is bounded to? ☐
- Declined. Confirm nothing was sent (execution history shows no new run): ☐
- How the session wired `dispatch_fn` (unaided / from the runbook snippet / incorrectly):

### Step 4 — the accepted run
- Arm read-back verdict (verbatim):
- Dispatch landed — n8n execution id / HTTP status:
- Disarm read-back verdict (verbatim):
- **Armed-window wall-clock duration:** ______ s (context: B4's full waterfall measured 37.44 s; the
  n8n Cloud webhook response ceiling is ~100 s)

### Step 5 — the HubSpot outcome
- Write observed on company `9604614548`, property/properties changed:
- **No other record touched** — how that was checked:

### Step 6 — literal-shape comparison, live
- Declaration text fetched from the armed workflow:
- Matches `_OVERLAY_FLAG_SPEC`'s enabled literal: ☐ / difference:

### Step 7 — flag state AFTER
```
(paste the status-surface read-back — every declaration must read disabled)
```
- Disarming redeploy run: ☐
- `verify_live_write_safety.py --expectation disarmed` verdict:
- Status surface re-read after the redeploy:
- `ALLOW_N8N_ARM` unset again: ☐

### Anything that did not behave as the runbook describes — verbatim
