# Phase 22: Armed E2E Enrichment Canary - Research

**Researched:** 2026-07-30
**Domain:** Operator-gated live HubSpot write canary (n8n Cloud) + cost-ledger tooling (Python)
**Confidence:** HIGH (mechanism/precedent) / MEDIUM (cost baselines, n8n execution-data API) / LOW (whether the current allowlisted record's fields will actually trigger the research+judge gates)

## Summary

Phase 22 has two deliverables that are structurally different in *who* executes them.
The armed canary itself (REQ-armed-e2e-canary) is **operator-only** — every prior armed
HubSpot write in this repo (16.9/19-OPERATOR-RUNBOOK, the contacts canary in Phase 16.4/16.5)
was executed by a human following a written runbook, because the environment's permission
classifier structurally blocks agents from arming `ENABLE_BAKED_FLAGS` writes (confirmed twice:
directly in `n8n-deploy-permission-blocked` memory, and again by the orchestrator's own blocked
attempt in Phase 20 Plan 04 Task 3). **What an agent builds this phase is the runbook, the
pre/post read-back tooling, and the cost-ledger script** — not the armed write itself.

The mechanism to reuse is already fully proven: `scripts/deploy_n8n_workflows.py`'s
`ENABLE_BAKED_FLAGS` overlay rewrites the committed-disabled write-safety literals
in-flight at deploy time (never touching git), gated by a code-enforced rule that
`ALLOW_HUBSPOT_RECORD_WRITES`/`ALLOW_HUBSPOT_CREATE` cannot be armed without a non-empty
`TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS` in the *same* invocation. Research and judge
(`ALLOW_WEB_RESEARCH`, `ALLOW_JUDGE_ESCALATION`) are **no longer overlayable** — both flip
to `true` at build time as of the 2026-07-30 quick tasks (260730-din, 260730-fij) — so the
canary's "complete chain" is already live on every enrichment run; only the HubSpot
*write* half needs arming. This is a narrower canary than it sounds: the research/judge
lanes fire on ordinary disarmed runs today (proven live for contacts in Phase 16.5); what
has never been proven live is a *promoted write* landing after that full chain runs, on
the currently-migrated (v3 + hygiene) schema.

**Sequencing risk (the most important finding):** ROADMAP's Phase 22 success criterion 2
requires "`lv_org_type` accepted by the enumeration" — but `REQUIREMENTS.md` currently
shows `REQ-orgtype-enumeration` as **Pending**, and Phase 21's plans 21-03/21-04 (the
disposable-property probe ladder, rollback runbook, and the actual one-way-door migration)
have no SUMMARY yet. Phase 22 cannot validate criterion 2 until Phase 21 actually finishes
the enum migration live. Separately, `REQ-lusha-id-staging`'s live properties
(`lusha_contact_id`/`lusha_company_id`) are also a **pending operator action** from Phase
20 Plan 04 — not required for the core waterfall+research+judge chain to run, but relevant
if the ledger wants to demonstrate the free-reuse cost benefit live.

**Primary recommendation:** Build (1) an `22-OPERATOR-RUNBOOK.md` that is a direct extension
of `19-OPERATOR-RUNBOOK.md`'s arm/fire/read-back/disarm ceremony, scoped to company
`9604614548` (Melbourne Racing Club — the only company-lane record with a track record of
exercising the research+judge gates), (2) a pre-canary live-read-only check confirming
`lv_org_type`/`lv_produces_content`/`lv_country_region_normalized` are still blank/stale
enough on that record to actually fire the research gate (otherwise the canary mechanically
passes without exercising the "complete chain" it claims to), and (3) a new
`scripts/enrichment_cost_ledger.py` that diffs Lusha/ZoomInfo/Apollo credit balances
before/after (reusing `check_provider_credits.py`'s registry) and reads the n8n Cloud
execution's `runData` via `GET /api/v1/executions/{id}?includeData=true` to extract each
Anthropic `httpRequest` node's raw `usage.input_tokens`/`output_tokens` — no code change to
the already-verified enrichment workflow is needed to capture tokens, because the raw
Anthropic response (including `usage`) is present in that node's own execution output even
though the downstream Code node discards it before merge.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-armed-e2e-canary | One armed end-to-end enrichment on allowlisted record(s): provider waterfall + Haiku web research + Sonnet judge → staged fields, source metadata, and promoted canonical writes land in HubSpot; neighbor records byte-untouched; disarm + read-back closes the run | Pattern 1/2 (overlay + read-back), Runtime State Inventory (Phase 20/21 pending live-state gates), Pitfall 1/3 (gate-firing risk, schema-migration sequencing), Code Examples (exact arm/disarm/fire commands), Environment Availability (all dependencies confirmed live) |
| REQ-canary-cost-ledger | The canary records actual spend — provider credits (before/after) and Anthropic tokens per call — against the 2026-07-30 estimates, producing a calibrated per-record cost figure | Pattern 3 (n8n execution `runData` token scrape — new), Standard Stack (reuse `check_provider_credits.py`/`provider_registry.py`), Pitfall 2 (Lusha eventual-consistency lag), Assumption A3 (baseline estimate sources), Validation Architecture (`test_enrichment_cost_ledger.py`) |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Arm/fire/disarm the write-safety overlay | Operator (CLI, `.env`-loaded) | n8n Cloud (deploy target) | Classifier-blocked for agents; `deploy_n8n_workflows.py` is the only writer of the overlay |
| Fire one canary event | Operator (webhook POST) or n8n Schedule (SJ jobs) | n8n Cloud (`LV Enrichment` webhook) | Precedent (16.4/16.9) always fired a direct webhook POST shaped like a HubSpot event, not the real HubSpot UI |
| Provider waterfall + research + judge | n8n Cloud (Code + httpRequest nodes) | Anthropic API / Lusha / ZoomInfo / Apollo | Already live and disarmed-verified; nothing new to build here |
| Neighbor byte-untouched verification | Operator (read-only HubSpot API reads) | New/extended Python script | Read-only reads are agent-allowed; script can be built and dry-run by an agent, only the armed fire is operator-only |
| Cost ledger (credits + tokens) | New Python script (`scripts/`) | n8n Cloud Executions API + provider usage APIs | All read-only HTTP; fully agent-buildable and testable offline (mocked) |
| Rollback / disarm | Operator (same `deploy_n8n_workflows.py` overlay, empty) | n8n Cloud | Distinct read-back step per established pattern (Phase 19/20/21) |

## Package Legitimacy Audit

No new external packages are required. The cost-ledger script and any read-back tooling
reuse `requests` (already a pinned dependency, `requirements.txt`) for both the n8n
Executions REST API and the provider credit endpoints — the same library
`check_provider_credits.py` and `deploy_n8n_workflows.py` already use. No npm packages
needed either (no new n8n node types, no new JS tooling). `Disposition: N/A — no packages
to audit.`

## Standard Stack

No new stack. This phase is 100% reuse of already-verified infrastructure:

| Component | Version/Identity | Purpose | Precedent |
|---|---|---|---|
| `scripts/deploy_n8n_workflows.py` `ENABLE_BAKED_FLAGS` overlay | current (Phase 20 Plan 05 verified live) | Arms/disarms `ALLOW_HUBSPOT_RECORD_WRITES` + `TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS` without a rebuild | `19-OPERATOR-RUNBOOK.md`, `16.5-01-SUMMARY.md` |
| n8n public REST API `GET /api/v1/executions/{id}?includeData=true` | n8n Cloud current version | Read back a completed execution's per-node `runData`, including each Anthropic `httpRequest` node's raw JSON body (`usage.input_tokens`/`output_tokens`) [CITED: docs.n8n.io/connect/n8n-api/execution] | New for this phase — no existing script calls the executions endpoint |
| `check_provider_credits.py` / `PROVIDER_REGISTRY` (`scripts/provider_registry.py`) | current | Read-only Lusha/ZoomInfo/Apollo balance snapshot, before + after | Live-validated endpoints in `provider-credit-check-endpoints` memory |
| `python-dotenv` in-process wrapper idiom | current | The only way `.env` credentials load without an agent touching `.env` directly | `19-OPERATOR-RUNBOOK.md` §"Command form" |
| HubSpot CRM v3 object GET/search (read-only) | current | Pre/post snapshot of the allowlisted record + at least one neighbor (`lastmodifieddate`) | 19-OPERATOR-RUNBOOK Step 2 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Scraping n8n execution `runData` for token usage | Adding a `usage` passthrough field to the "Validate…" Code nodes | Would require a code change + rebuild + redeploy to the already-verified, disarmed-live enrichment workflow, for a canary that is supposed to validate the *existing* pipeline, not modify it further. Read-only API scrape needs zero pipeline changes. |
| Manual operator eyeballing of before/after JSON | A small diffing script (`enrichment_cost_ledger.py` / an extended read-back script) | Manual review is what Phase 19 did and is fine for a single record, but REQ-canary-cost-ledger explicitly wants a *calibrated per-record cost figure*, which needs arithmetic over multiple numeric fields — worth a ~100-line script over hand math. |

## Architecture Patterns

### System Architecture Diagram

```
Operator shell (armed commands only — classifier-blocked for agents)
  |
  |  DRY_RUN=false ALLOW_N8N_DEPLOY=true
  |  ENABLE_BAKED_FLAGS="ALLOW_HUBSPOT_RECORD_WRITES,TEST_RECORD_IDS=9604614548"
  v
scripts/deploy_n8n_workflows.py  --(rewrites 2 baked literals in-flight)-->  n8n Cloud API (PUT workflow)
  |
  |  operator fires ONE webhook event (company:update shape, object 9604614548)
  v
LV Enrichment (Cloud) webhook  -->  provider waterfall (Lusha v3 + ZoomInfo + Apollo)
  |                                        |
  |                                        v
  |                                 Normalize + Score Company
  |                                        |
  |                          Research Trigger Gate (fires if org_type/content blank)
  |                                        |
  |                            Claude Web Research (claude-haiku-4-5, httpRequest)
  |                                        |
  |                       Validate Research Output --(usage discarded here)--> Judge Gate
  |                                        |
  |                          Build Judge Request --> Judge Call (claude-sonnet-5, httpRequest)
  |                                        |
  |                                 Merge Company --> Decide Action
  |                                        |
  |                      write-safety gate: allowlist check + ALLOW_HUBSPOT_RECORD_WRITES
  |                                        |
  |                                 HubSpot Update (armed only for 9604614548)
  v
Operator read-back (read-only, agent-buildable)
  - HubSpot GET company 9604614548: confirm staged + canonical fields landed
  - HubSpot GET neighbor (e.g. contact 201, or another company): lastmodifieddate unchanged
  - n8n GET /api/v1/executions/{id}?includeData=true: per-node runData
       -> pull Anthropic httpRequest node outputs -> usage.input_tokens/output_tokens
  - Provider credit endpoints (Lusha/ZoomInfo/Apollo usage): balance after - balance before
  v
scripts/enrichment_cost_ledger.py (new) --> cost-ledger record (credits + tokens vs 2026-07-30 estimates)
  |
  v
Operator disarms: same overlay command with ENABLE_BAKED_FLAGS unset entirely
  -> read the deployment back again -> confirm all write flags "false", allowlist cleared
```

### Recommended Project Structure

No new top-level structure — this phase adds files into existing directories:

```
.planning/phases/22-armed-e2e-enrichment-canary/
├── 22-RESEARCH.md              (this file)
├── 22-OPERATOR-RUNBOOK.md      (new — extends 19-OPERATOR-RUNBOOK.md's ceremony)
└── 22-LEDGER.md                (new — records the observed cost figures, mirrors 19-LEDGER.md's evidentiary bar)

scripts/
└── enrichment_cost_ledger.py   (new — read-only: provider credit diff + n8n execution token scrape)

tests/
└── test_enrichment_cost_ledger.py   (new — offline, mocked HTTP, proves the extraction logic before any live run)
```

### Pattern 1: Deploy-time overlay for one-shot armed writes
**What:** `ENABLE_BAKED_FLAGS` rewrites the committed-disabled JS literal in the built
workflow JSON between "read from git" and "POST to n8n," never touching the repo.
**When to use:** Exactly this phase — arming exactly one write-enabling flag plus its
mandatory allowlist, for exactly one operator-run window, then reverting.
**Example:**
```bash
# Source: 19-OPERATOR-RUNBOOK.md Step 1 (verified live 2026-07-29)
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  ENABLE_BAKED_FLAGS="ALLOW_HUBSPOT_RECORD_WRITES,TEST_RECORD_IDS=9604614548" \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```
Multiple ids use `|` in the `ENABLE_BAKED_FLAGS` value (`,` already delimits entries); the
overlay itself translates `|` back to a comma-separated runtime string
(`_requested_overlay_flags()`, `scripts/deploy_n8n_workflows.py`).

### Pattern 2: Read-back-as-a-distinct-step
**What:** A redeploy's HTTP 200 / exit 0 proves the *request* succeeded, never that the
live artifact is current. Every phase since 20 has independently re-read the deployment
after arming AND after disarming.
**When to use:** After every arm and every disarm in the canary runbook — never trust the
deploy script's own exit code as proof of the live state.
**Example:** `scripts/verify_live_lusha_urls.py` / `scripts/verify_live_no_native_search.py`
are the two existing precedents; a Phase 22 equivalent should read the live `LV Enrichment`
workflow's write-safety constants back after arm (expect `"true"` x2 + allowlist populated)
and after disarm (expect `"false"` x2 + allowlist empty) — do not build a third one-off if
the fetch-and-grep-node-bodies helper in `deploy_n8n_workflows.py`/`verify_live_lusha_urls.py`
can be imported and reused.

### Pattern 3: n8n execution `runData` scrape for token usage (new for this phase)
**What:** `GET /api/v1/executions/{id}?includeData=true` returns `data.resultData.runData`
keyed by node name; each entry is an array of `NodeRun` objects whose `data.main[0][0].json`
is that node's actual output item(s). For an `httpRequest` node calling
`https://api.anthropic.com/v1/messages` directly (as `Claude Web Research`/`Contact Web
Research`/`Judge Call`/`Contact Judge Call` all do — confirmed in `n8n/wf_enrichment_cloud.json`),
that JSON **is the raw Anthropic Messages API response**, including
`usage.input_tokens`/`usage.output_tokens`/`usage.cache_creation_input_tokens`/
`usage.cache_read_input_tokens`. The downstream `Validate …`/`Apply … Verdict` Code nodes
discard `usage` when they extract just the structured fields — but that happens in a
*separate* node, so the raw response with `usage` is still captured in the httpRequest
node's own `runData` entry.
**When to use:** For the cost ledger's Anthropic token capture. No modification to the
live, disarmed-verified enrichment workflow is needed.
**Example:**
```python
# New for this phase — no direct precedent script exists yet.
import requests

def get_execution_token_usage(n8n_url: str, api_key: str, execution_id: str) -> list[dict]:
    r = requests.get(
        f"{n8n_url.rstrip('/')}/api/v1/executions/{execution_id}",
        params={"includeData": "true"},
        headers={"X-N8N-API-KEY": api_key},
        timeout=30,
    )
    r.raise_for_status()
    run_data = r.json().get("data", {}).get("resultData", {}).get("runData", {})
    usages = []
    for node_name, runs in run_data.items():
        if "Research" not in node_name and "Judge" not in node_name:
            continue  # only the Anthropic httpRequest nodes carry `usage`
        for run in runs:
            items = (run.get("data", {}) or {}).get("main", [[]])[0]
            for item in items or []:
                body = item.get("json", {})
                if isinstance(body, dict) and "usage" in body:
                    usages.append({"node": node_name, "model": body.get("model"), **body["usage"]})
    return usages
```

### Anti-Patterns to Avoid
- **Adding a passthrough `usage` field to the live pipeline's Code nodes just for this
  canary:** the whole point of Phase 22 is to validate the *already-shipped* pipeline. A
  code change introduces a new variable into a canary that's supposed to prove the existing
  thing works, and it would require a rebuild + redeploy cycle (with its own read-back
  ceremony) before the canary could even start.
- **Treating a mechanically-passing canary as proof the "complete chain" ran:** if the
  allowlisted company's `lv_org_type`/`lv_produces_content` are already non-blank from a
  prior canary run, `Research Trigger Gate` will NOT fire (RT-3 fires on
  `orgUnresolved || contentBlank`), and the run will silently skip straight to a
  provider-only merge — passing every mechanical check while never exercising the
  Haiku-research-then-Sonnet-judge half of the criteria. Read the record's current field
  state BEFORE arming.
- **Arming `ALLOW_HUBSPOT_CREATE` "just in case":** the runbook precedent (19-OPERATOR-RUNBOOK
  Scope) explicitly declines to re-arm `create` when only `update` needs re-proving — re-arming
  an unneeded write-enabling flag widens risk for zero verification value. Phase 22's criteria
  only require `company:update`-shaped writes on an existing test record; do not request
  `ALLOW_HUBSPOT_CREATE` unless a specific criterion needs it.
- **Trusting `check_provider_credits.py`'s single before/after diff without accounting for
  Lusha's documented eventual-consistency lag:** `docs/LUSHA-V3-CONTRACT.md` §1 measured a
  balance re-read taken immediately after a call under-reporting the true debit for several
  seconds. The cost ledger should re-read the "after" balance a few seconds after the last
  billable call, not immediately after the canary fires, or it will misreport the spend.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Arming/disarming write-safety flags | A new overlay mechanism, a `.env`-based toggle, or a manual JSON edit before deploy | The existing `ENABLE_BAKED_FLAGS` overlay in `scripts/deploy_n8n_workflows.py` | Already carries the fail-closed allowlist-required invariant, the charset-restricted value parser, and is the ONLY mechanism this repo's tests (`test_deploy_write_safety_overlay.py`) pin against |
| Reading provider credit balances | New per-provider HTTP clients | `scripts/provider_registry.py` + `scripts/check_provider_credits.py`'s null-safe extractors | Already live-validated (Lusha 200, ZoomInfo needs `Accept: vnd.api+json`, Apollo 403-degrades-to-null) — reinventing risks re-discovering the same auth quirks |
| Verifying a redeploy actually landed | Trusting the deploy script's HTTP 200 | The read-back pattern (`verify_live_lusha_urls.py`/`verify_live_no_native_search.py`) | BUG 26 (Phase 19) and the Phase 20/21 redeploys all independently found the live deployment behind git despite a clean prior deploy exit code |
| Extracting Anthropic token usage | Modifying the live Code nodes to pass `usage` through | Scraping the httpRequest node's own raw response via the n8n Executions API | Zero pipeline changes; the data is already present in `runData`, just discarded one node downstream |

**Key insight:** every piece of machinery this phase needs — the overlay, the allowlist gate,
the read-back pattern, the credit-check registry — already exists and is live-verified.
The only genuinely new code is the cost-ledger's execution-data scrape.

## Runtime State Inventory

Not applicable in the rename/refactor/migration sense (Phase 22 is a canary + tooling phase,
not a rename). However, since this phase's success criteria hinge on *other* phases' pending
live-state changes, the equivalent inventory here is: **what live HubSpot/n8n state must exist
before the canary can validate its own criteria.**

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| HubSpot schema (org_type enum) | `lv_org_type` is still a free-text property live — the Phase 21 one-way-door migration (plans 21-03/21-04) has not executed yet (`REQUIREMENTS.md`: `REQ-orgtype-enumeration` Pending; no `21-03-SUMMARY.md`/`21-04-SUMMARY.md` exist) | Operator must complete Phase 21's probe ladder + rollback runbook + armed migration BEFORE Phase 22's canary can validate success criterion 2 ("writes succeed against the migrated schema") |
| HubSpot schema (Lusha id staging) | `lusha_contact_id`/`lusha_company_id` do not exist live yet — Phase 20 Plan 04 Task 3 is a documented pending operator action (dry run confirms exactly 2 creates, 0 updates) | Operator can create these independently of Phase 22 (not blocking the core canary criteria, but needed if the ledger wants to demonstrate id-reuse's free-recheck cost benefit live) |
| n8n Cloud deployment currency | Confirmed CURRENT as of the 20-05 and 21-01/21-02 disarmed redeploys (both read back live, 0 residual v2 Lusha URLs, 0 native search nodes) | None — verified current; a Step-0 disarmed redeploy immediately before the canary is still recommended per the BUG-26-shaped-drift precedent (every phase so far has found the live deployment behind git at least once) |
| Test-record field state | Company `9604614548`'s current `lv_org_type`/`lv_produces_content`/`lv_country_region_normalized` values are not known as of this research (no fresh live read performed this session) | A read-only pre-canary check must confirm these fields are still blank/stale enough to fire `Research Trigger Gate`'s `orgUnresolved \|\| contentBlank` condition — otherwise the canary mechanically passes without exercising the research+judge lanes |
| ROADMAP/STATE progress tables | `ROADMAP.md`'s Milestone 5 progress table shows "21. Transport & Schema Hygiene | 0/? | Not started," which contradicts the existing `21-01-SUMMARY.md`/`21-02-SUMMARY.md` and `REQUIREMENTS.md`'s Complete marks for `REQ-dedupe-transport-swap`/`REQ-country-region-policy` | Stale tracking table, not a runtime state issue — flag for the planner/operator to reconcile, does not block Phase 22 itself |

**Canonical question for the planner:** after Phase 21 finishes (org_type enum live) and
Phase 22's tooling is built, what is the FIRST live state the operator must independently
confirm before arming writes? Answer: (1) org_type enum migration complete and read-back
confirmed, (2) company `9604614548`'s ICP fields still blank/stale enough to fire research,
(3) `LV Enrichment` deployment current with git (disarmed Step-0 redeploy + read-back).

## Common Pitfalls

### Pitfall 1: Canary "passes" without ever exercising research or judge
**What goes wrong:** The armed run writes SOME field to HubSpot and the runbook is
marked passed, but `Research Trigger Gate` never fired because the target record's
`lv_org_type`/`lv_produces_content` were already populated from an earlier canary/scheduled
run, so `Merge Company`'s "complete chain" claim (waterfall + Haiku research + Sonnet judge)
is unverified.
**Why it happens:** Multiple canaries and scheduled research-lane runs have already touched
company `9604614548` and contact `201` (per `STATE.md`'s canary history) — their field state
is not "fresh," and the research gate is conditional, not unconditional.
**How to avoid:** Live-read the target record's ICP fields immediately before arming; if
already populated, either pick a different allowlisted record known to be blank, or force a
`full_refresh`-shaped event if the workflow supports staleness-based re-trigger (check
`enrichment_mode`/staleness TTL logic in `Enrichment Gate`/`Research Trigger Gate` before
assuming a repeat run will re-fire research).
**Warning signs:** The post-run read-back shows a write landed, but the n8n execution's
`runData` shows `Research Trigger Gate`/`IF Research Needed` evaluated false, or
`Claude Web Research`/`Judge Call` nodes never ran at all (0 entries in `runData` for those
node names).

### Pitfall 2: Lusha credit-balance eventual consistency corrupts the cost ledger
**What goes wrong:** Reading the "after" Lusha balance immediately following the canary's
last billable call under-reports the true spend by several credits.
**Why it happens:** `docs/LUSHA-V3-CONTRACT.md` §1 measured this directly: `credits.remaining`
lagged a real debit by ~4 seconds on at least one call in the same probe session.
**How to avoid:** Sleep a few seconds (or poll until the number changes/stabilizes) between
the canary's last Lusha-billing call and the ledger's "after" balance read.
**Warning signs:** The ledger reports a delta of 0 or fewer credits than the number of
Lusha-billing HTTP calls that clearly ran (per the execution's `runData`).

### Pitfall 3: Phase-21-incomplete schema breaks criterion 2 silently
**What goes wrong:** The armed canary runs, the waterfall+research+judge chain completes,
and a write lands — but `lv_org_type` is still free-text (not yet migrated), so the "writes
succeed against the migrated schema" half of criterion 2 is not actually being tested; the
write would have succeeded on the OLD schema too, so a pass here proves nothing new about
the migration.
**Why it happens:** Phase 22 depends on Phase 21 completing per ROADMAP, but Phase 21's
org_type work (21-03/21-04) has no SUMMARY yet — the dependency is declared but not
verified closed.
**How to avoid:** Before writing the Phase 22 plan, confirm (via `REQUIREMENTS.md` and a
fresh `21-04-SUMMARY.md`/rollback-runbook read) that the enum migration is live and
read-back-confirmed. If it is not, Phase 22's plan must either wait, or explicitly scope
criterion 2 down to "v3 selective reveal only" and defer the enum half to a follow-up
canary.
**Warning signs:** `snapshot_hubspot_schema.py`'s live property type for `lv_org_type` still
reads `string`/`text`, not `enumeration`.

### Pitfall 4: Treating the deploy script's exit code as the live state
**What goes wrong:** Assuming the arm (or disarm) succeeded because the deploy script
returned 0, without independently reading the live workflow back.
**Why it happens:** BUG 26 (Phase 19) is exactly this failure mode — a clean prior deploy
exit code, but the live deployment predated the committed code by multiple phases.
**How to avoid:** Always follow the pattern from `19-OPERATOR-RUNBOOK.md` Steps 2/4 — arm,
then independently GET the live workflow's node bodies and confirm the literal changed;
disarm, then independently GET again and confirm it changed back.
**Warning signs:** No independent read-back step appears in the runbook draft — this is a
process smell, not a runtime one, but it has caused a real incident every time it was
skipped in this repo's history.

## Code Examples

### Reading provider credit balance (before/after pattern)
```python
# Source: scripts/check_provider_credits.py (existing, reused as-is)
from provider_registry import PROVIDER_REGISTRY
import requests

def lusha_balance() -> int | None:
    credit = PROVIDER_REGISTRY["lusha"]["credit"]
    r = requests.get(credit["url"], headers={credit["header"]: LUSHA_API_KEY}, timeout=15)
    if not r.ok:
        return None
    remaining = (r.json().get("credits") or {}).get("remaining")
    return remaining if isinstance(remaining, (int, float)) else None
```

### Firing exactly one canary event (webhook POST, HubSpot-event-shaped)
```bash
# Source: 19-OPERATOR-RUNBOOK.md Step 2 precedent (n8n webhook, not the real HubSpot UI)
curl -sS -X POST "$N8N_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-Enrichment-Secret: $N8N_HUBSPOT_WEBHOOK_SECRET" \
  -d '[{"objectId": 9604614548, "objectType": "company", "subscriptionType": "company.propertyChange", "propertyName": "enrichment_requested", "propertyValue": "true", "occurredAt": 1783316400000}]'
```

### Arm / disarm overlay (exact operator command form)
```bash
# Arm — Source: 19-OPERATOR-RUNBOOK.md Step 1
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  ENABLE_BAKED_FLAGS="ALLOW_HUBSPOT_RECORD_WRITES,TEST_RECORD_IDS=9604614548" \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"

# Disarm — Source: 19-OPERATOR-RUNBOOK.md Step 3 (no ENABLE_BAKED_FLAGS at all)
DRY_RUN=false ALLOW_N8N_DEPLOY=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `ALLOW_WEB_RESEARCH`/`ALLOW_JUDGE_ESCALATION` armed per-canary via overlay | Both default `true` at build time; removed from `_OVERLAY_FLAG_SPEC` entirely | 2026-07-30 (quick tasks 260730-din, 260730-fij) | Phase 22's canary no longer needs to arm research/judge — only the HubSpot write half needs the overlay now |
| Lusha v2 `GET /v2/*` with ~4.65-credit/reveal phone bundling | Lusha v3 `POST /v3/*/search-and-enrich`, flat 1 cr/contact + 2 cr/company, id-reuse free (contacts) | Phase 20 (2026-07-30) | The `measured-provider-match-rates` memory's Lusha figure is now STALE for cost-ledger purposes — use the v3 figures from `docs/LUSHA-V3-CONTRACT.md` instead |
| `ANTHROPIC_RESEARCH_MODEL = claude-sonnet-5` | `ANTHROPIC_RESEARCH_MODEL = claude-haiku-4-5` (judge stays `claude-sonnet-5`) | 260730-fij | This canary is the FIRST live validation of the Haiku research-model swap per ROADMAP criterion 1 |

**Deprecated/outdated:**
- Lusha v2 endpoints: dead entirely from the live deployment as of Phase 20 Plan 05's
  read-back (0 v2 URLs). Do not reference v2 credit math for this phase's cost ledger.
- The `measured-provider-match-rates` memory's "~2.5 credits/attempt" Lusha figure: correct
  for v2, refuted for v3 (see `docs/LUSHA-V3-CONTRACT.md` §6 — selective reveal buys
  nothing, the only lever is search vs. reuse-by-id).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `GET /api/v1/executions/{id}?includeData=true` on n8n Cloud (this instance's version) returns `runData` with each node's raw output including the Anthropic response's `usage` field, exactly as the self-hosted n8n docs describe | Pattern 3 / Standard Stack | If n8n Cloud's API differs (e.g. truncates large node outputs, or this instance has execution-data retention/pruning that discards `runData` before the ledger script runs), token capture from execution replay fails and the ledger falls back to no per-call token breakdown — a live read-only probe against one recent execution ID should confirm this before the cost-ledger script is built as designed |
| A2 | Company `9604614548`'s `lv_org_type`/`lv_produces_content`/`lv_country_region_normalized` are still blank/stale enough to fire `Research Trigger Gate` | Pitfall 1, Runtime State Inventory | If already populated from an earlier canary/scheduled run, the armed canary would mechanically pass while never exercising the Haiku-research-then-Sonnet-judge half of the "complete chain" — a live read-only GET on this record should be the very first step of the plan |
| A3 | The "2026-07-30 estimates" REQ-canary-cost-ledger compares against are: Lusha ~1 cr/contact + 2 cr/company (v3, `REQUIREMENTS.md`/`docs/LUSHA-V3-CONTRACT.md`), ZoomInfo ~1.08 cr/match (v2 measurement, unchanged by this milestone), and Haiku research ~$0.07/company-call incl. search fees (`260730-fij-SUMMARY.md`) | Summary, State of the Art | No single consolidated "2026-07-30 estimates" document exists in the repo (the `dryrun-sample-2026-07-30.csv` referenced in memory lives only in a prior session's scratchpad, not committed) — if the planner intends a different baseline document, it should be named explicitly before the ledger script is built against these three sources |
| A4 | Phase 21's org_type enum migration will complete (with a live read-back) before Phase 22's plan is executed | Pitfall 3, Runtime State Inventory | If Phase 22 is planned/executed before Phase 21 finishes, success criterion 2's schema-migration half cannot be validated and the plan should explicitly scope around it rather than silently skip it |

## Open Questions

1. **Does firing the canary via a direct webhook POST (bypassing real HubSpot) still count as "live" for the cost ledger's provider-credit measurement?**
   - What we know: every prior canary (16.4, 16.9, 16.5) fired a synthetic webhook body shaped like a HubSpot event, not a real HubSpot UI action — and this still drove real Lusha/ZoomInfo/Apollo/Anthropic/HubSpot API calls (real credit and token spend).
   - What's unclear: whether REQ-armed-e2e-canary intends a "genuine" HubSpot-triggered event (e.g. an operator flipping `enrichment_requested` in the HubSpot UI) as extra evidence that the webhook subscription itself still works end-to-end, on top of the synthetic-payload precedent.
   - Recommendation: follow precedent (synthetic webhook POST) for the mechanism proof; if the operator wants the HubSpot-side trigger also exercised, that is a cheap addition (flip the property in the UI) that costs nothing extra to add to the runbook.

2. **What should happen if company `9604614548`'s ICP fields are already populated (Pitfall 1/A2 materializes)?**
   - What we know: several prior canaries and now-live scheduled research runs may have already written to this record.
   - What's unclear: whether a `full_refresh`/staleness-forced re-trigger path exists that would re-fire research on an already-populated record, or whether a different, still-blank allowlisted company should be chosen for this specific canary.
   - Recommendation: the plan's first task should be a read-only live check of this record's current field values; branch the runbook based on the result rather than assuming either state.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| n8n Cloud API (`N8N_URL`/`N8N_API_KEY`) | Deploy overlay, execution read-back, executions API scrape | Confirmed working (Phase 20/21 disarmed redeploys) | current n8n Cloud | — |
| HubSpot private-app token | Record read-back, neighbor-untouched check | Confirmed working (Phase 16-21 live reads/writes) | current | — |
| Anthropic API key | Research/judge calls (already live in the deployed workflow) | Confirmed working (Phase 16.5 live) | `claude-haiku-4-5` (research), `claude-sonnet-5` (judge) | — |
| Lusha API key | Provider waterfall + cost ledger | Confirmed working, v3 endpoints live-verified 2026-07-30 | v3 | — |
| ZoomInfo GTM credentials | Provider waterfall + cost ledger | Confirmed working; usage endpoint needs `Accept: application/vnd.api+json` (406 otherwise) | current | — |
| Apollo API key | Provider waterfall | Confirmed working for enrichment calls; usage endpoint 403s (non-master key) | current | Cost ledger reports Apollo credits as `null` — documented, graceful degrade, not a blocker |
| Operator shell access (classifier-unblocked) | Arming/disarming writes | Not available to this agent — confirmed structurally blocked | n/a | Runbook + tooling built by agent; armed steps executed by a human operator |

**Missing dependencies with no fallback:** None — every dependency this phase's *buildable*
work needs (read-only APIs, credit-check registry, deploy overlay code) is already available
and proven. The one non-negotiable gap (operator-only arming) has a documented fallback: an
operator-run runbook, which is precisely what this phase produces.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + node:test (node 24) |
| Config file | existing — no Wave 0 install |
| Quick run command | `.venv/bin/python -m pytest tests/ -q -x` |
| Full suite command | `.venv/bin/python -m pytest -q && node --test tests/n8n/*.test.mjs` |
| Estimated runtime | ~60-90 seconds (621 pytest / 354 node at time of this research) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-armed-e2e-canary | Cost-ledger/read-back script logic (credit diff math, `runData` token extraction) is correct against mocked HTTP responses | unit | `.venv/bin/python -m pytest tests/test_enrichment_cost_ledger.py -q` | ❌ new file |
| REQ-armed-e2e-canary | The armed write, neighbor-untouched confirmation, and disarm/read-back itself | manual (operator-run, blocking checkpoint) | procedure in `22-OPERATOR-RUNBOOK.md` — no automated command, matches 19-OPERATOR-RUNBOOK's own bar | n/a |
| REQ-canary-cost-ledger | Credit-balance-before/after diff arithmetic, per-provider null-safe degrade | unit | `.venv/bin/python -m pytest tests/test_enrichment_cost_ledger.py -q -k credit` | ❌ new file |
| REQ-canary-cost-ledger | Anthropic token extraction from a mocked `runData` payload shape | unit | `.venv/bin/python -m pytest tests/test_enrichment_cost_ledger.py -q -k token` | ❌ new file |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/ -q -x`
- **Per wave merge:** Full suite (pytest + node --test)
- **Phase gate:** Full suite green before `/gsd-verify-work`; the armed-canary steps themselves
  are verified by the operator-run runbook's own pass/fail condition (mirrors 19-OPERATOR-RUNBOOK),
  not by pytest.

### Wave 0 Gaps
- [ ] `tests/test_enrichment_cost_ledger.py` — covers REQ-canary-cost-ledger's credit-diff and
      token-extraction logic against mocked HTTP (no live calls in the offline suite, same
      convention as `test_check_provider_credits.py`)
- [ ] A live, read-only probe of one recent n8n execution's `GET .../executions/{id}?includeData=true`
      response — to confirm assumption A1 (that `usage` actually survives in `runData` on this
      n8n Cloud instance) before the ledger script's design is finalized

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No new auth surface — reuses existing n8n API key / HubSpot private-app token / provider keys, all already credential-bound |
| V3 Session Management | No | N/A |
| V4 Access Control | Yes | The write-safety allowlist gate itself (`TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS` required alongside any write-enabling flag) IS the access-control mechanism under test this phase — reuse it, do not weaken it |
| V5 Input Validation | Yes | `_ALLOWLIST_VALUE_RE` already restricts overlay values to a narrow id/domain charset; the new cost-ledger script should apply the same "never trust external API response shape" defensive parsing already established in `check_provider_credits.py`'s null-safe extractors |
| V6 Cryptography | No | No new secrets handling — credentials continue to flow only through `.env` (agent-blocked) + the in-process `load_dotenv()` wrapper pattern |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Accidental "allow all" via a misconfigured/empty allowlist | Elevation of Privilege | Already enforced in code (`_requested_overlay_flags()` raises if a write-enabling flag is requested with no allowlist) — do not build a second, weaker allowlist check in the cost-ledger tooling |
| Leaking a credential value into a log/ledger artifact | Information Disclosure | Follow `check_provider_credits.py`'s convention: never print a secret value, only status codes and numeric balances/token counts; the new cost-ledger script's output must be reviewed for this before it is run against real keys |
| Cost-ledger script accidentally making a BILLABLE call (e.g. hitting a provider's enrich endpoint instead of its usage endpoint) while "just checking credits" | Repudiation / cost blowup | Reuse `PROVIDER_REGISTRY`'s `credit` URLs exclusively (read-only usage endpoints), never the `match`/`enrich` endpoints, mirroring `check_provider_credits.py`'s existing scope discipline |

## Sources

### Primary (HIGH confidence)
- `.planning/milestones/v0.4-phases/19-verification-debt-closure/19-OPERATOR-RUNBOOK.md` — the arm/fire/read-back/disarm ceremony this phase's runbook extends
- `scripts/deploy_n8n_workflows.py` (`_OVERLAY_FLAG_SPEC`, `_requested_overlay_flags`) — read directly, current code
- `scripts/check_provider_credits.py`, `scripts/provider_registry.py` — read directly, current code
- `docs/LUSHA-V3-CONTRACT.md` §§1, 6, 7, 8, 8.1 — live-probed 2026-07-30, contract of record (explicitly supersedes RESEARCH.md's WebSearch-derived v3 hypothesis)
- `n8n/wf_enrichment_cloud.json` — read directly (webhook trigger, httpRequest nodes hitting `api.anthropic.com/v1/messages` directly, node names/topology)
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` — current requirement/phase status
- `.planning/phases/20-lusha-v3-migration/20-04-SUMMARY.md` — pending operator action for Lusha id-staging properties
- `.planning/phases/21-transport-schema-hygiene/21-VALIDATION.md`, `21-01-SUMMARY.md` — current Phase 21 completion state

### Secondary (MEDIUM confidence)
- [docs.n8n.io/connect/n8n-api/execution](https://docs.n8n.io/connect/n8n-api/execution) — `includeData`/`runData` shape, confirmed via WebSearch summary of official docs, not directly fetched byte-exact this session
- `.planning/quick/260730-fij-enable-web-research-haiku/260730-fij-SUMMARY.md` — the ~$0.07/company-call Haiku cost estimate

### Tertiary (LOW confidence)
- `.planning/STATE.md` prose entries describing "≈960/day ceiling at 15-min cadence" — narrative estimate, not independently re-derived this session

## Metadata

**Confidence breakdown:**
- Standard stack (overlay/deploy/read-back mechanism): HIGH — read directly from current code, matches multiple prior live-verified precedents
- Cost-ledger token-scrape design: MEDIUM — the n8n Executions API shape is WebSearch-sourced, not directly probed against this specific n8n Cloud instance yet
- Whether the canary will actually exercise research+judge on the current record state: LOW — depends on live field values not read this session (A2)
- Cost baseline figures: MEDIUM — sourced from committed docs/memory, but no single consolidated "2026-07-30 estimates" artifact exists

**Research date:** 2026-07-30
**Valid until:** ~7 days (fast-moving: Phase 21's org_type migration status and the exact live field state of the canary target record can change before this phase executes)
