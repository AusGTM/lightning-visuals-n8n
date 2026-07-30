# Phase 27: Backend Status Surface - Research

**Researched:** 2026-07-30
**Domain:** n8n Public API (workflows/executions), HubSpot Search API, provider credit probing, Claude Artifact publish/republish
**Confidence:** MEDIUM — the n8n/HubSpot mechanics are HIGH (verified against this repo's live-tested code); two of six requirements (STATUS-02, STATUS-04) have a real data-model gap that must be resolved by the planner before tasks can be written (see Open Questions).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**How the status picture is assembled**
- **D-01:** The picture is **split along the credential boundary**. The **client** reads
  `/api/v1/workflows` and `/api/v1/executions` directly with the n8n API key it already holds —
  workflow on/off state, last run and whether it succeeded, what is in flight. The **n8n-side
  status endpoint** supplies only what requires credentials the client does not have: provider
  balances, stuck-lock and review-backlog counts from HubSpot, and credential health.
- **D-02:** Each side reads exactly what it is entitled to. This avoids duplicating workflow and
  execution data in the backend endpoint, and means most status changes need no backend edit.
- **D-03:** Criterion 1 requires this state be **read from the n8n API, not asserted from local
  config**. The plugin never reports "live writes are on" from its own config file — it reports
  what the backend says.

**Failure-cause translation**
- **D-04:** Translation is **table-first with a Claude fallback**: a static table maps known n8n
  error signatures to plain language plus who can fix it; anything unmatched is interpreted
  in-session by Claude.
- **D-05:** **Guardrail on the fallback, required.** An unmatched error must (a) be labelled
  plainly as an interpretation rather than a known cause, (b) show the raw error text alongside
  it, and (c) **default the who-can-fix-it attribution to "an admin"** rather than telling the
  operator they can fix something the table does not recognize. — Reversibility: reversible.
- **D-06:** Every signature the fallback handles more than once is a candidate for promotion into
  the static table. The table is expected to grow.

**Scope of reporting**
- **D-07:** **Every workflow the n8n API key can see** is reported — no allowlist.

**Unknown handling**
- **D-08:** Inherited from Phase 25 D-10: a value the backend cannot supply reads as **"unknown"**,
  never zero and never healthy. Apollo's key is not a master key and returns 403 on balance reads —
  a known, expected "unknown."

**Presentation**
- **D-09:** Status is **conversational text by default**; a dashboard Artifact is published on
  request, stamped with its fetch time, and a refresh **re-publishes to the same URL** rather than
  minting a second one.

### Claude's Discretion
- Layout and grouping of the conversational status output.
- Dashboard Artifact design, provided it carries the same data and the fetch-time stamp.
- Initial contents of the error-signature table beyond the four causes criterion 2 names
  (expired credential, rate limit, exhausted quota, malformed record).
- How "in flight" is determined from the executions API.
- Internal shape of the generalized status endpoint, provided it preserves unknown-vs-zero.

### Deferred Ideas (OUT OF SCOPE)
- **Mutating anything** — Phase 28 / CONTROL-01..07. This phase is strictly read-only.
- **Unprompted notification when something is wrong** — Phase 29 / NOTICE-03.
- **Review-queue detail and resolution** — Phase 30 / REVIEW-01..05. Phase 27 reports the backlog
  count only.
- **Promoting fallback-interpreted errors into the static table** — ongoing maintenance, not a
  phase deliverable.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| STATUS-01 | Per-workflow: on/off, live-writes-on/off (read from backend), last run + success, in-flight | §"n8n API read surface", §"Write-safety flag" — both fully answered with exact node names/regex |
| STATUS-02 | Failed run translated to plain language (4 causes) + who can fix | §"Error signatures" — partially answered; a real gap exists (see Open Questions #3) between what the execution API can show and what causes 3 of 4 categories actually produce |
| STATUS-03 | Provider balances via n8n-side endpoint, never client-direct | §"Provider balance probing" — fully answered, ports Phase 25's already-designed endpoint |
| STATUS-04 | Stuck locks, queued-never-processed, review backlog, with counts | §"Stuck locks and queues" — **the literal spec (`enrichment_lock_until`) does not exist in this repo's schema**; a working alternative is recommended (see Open Questions #1/#2) |
| STATUS-05 | Conversational by default; Artifact on request, same URL on refresh | §"Artifact stable URL" — fully answered via the platform's redeploy/update mechanism, with one session-scope caveat |
| STATUS-06 | Unknown never renders as zero/healthy | §"Provider balance probing" — fully answered, this repo's code already implements the exact null-propagation this requires |
</phase_requirements>

## Summary

This phase has no new library or package to add — it is wiring plus read logic against three
existing surfaces (n8n Public API, HubSpot Search API, and the Claude Artifact publish
mechanism), all already exercised elsewhere in this repo. Four of six requirements
(STATUS-01, STATUS-03, STATUS-05, STATUS-06) are well-supported by code that already exists and
has been live-validated: `scripts/deploy_n8n_workflows.py`'s `X-N8N-API-KEY` client pattern,
`scripts/enrichment_cost_ledger.py`'s `/api/v1/executions` list/extract calls,
`scripts/check_provider_credits.py`'s three-provider probe with its already-correct
null-vs-zero contract, and `enable_baked_flags()`'s exact-literal scan/rewrite convention for the
write-safety flag (which this phase only needs to *read*, not rewrite).

The other two requirements (STATUS-02, STATUS-04) hit a real gap between the aspirational
architecture in this repo's root `CLAUDE.md` (which describes `enrichment_lock_until`, a
`running` runtime state, and per-run locking) and what was **actually built**. Direct inspection
of `config/hubspot_properties.yaml` and the deployed `n8n/wf_enrichment_cloud.json` /
`wf_scheduled_maintenance_cloud.json` shows: (1) there is no `enrichment_lock_until` property
anywhere in the schema, (2) `lv_enrichment_status` is only ever written as `"needs_review"` or
`"complete"` — nothing in the pipeline ever writes `"running"`, `"queued"`, `"failed"`, or
`"skipped"` even though those enum values exist on the property, and (3) there is no
`requested_at`-style timestamp, so "how long has this been queued" cannot be computed from
HubSpot at all. Separately, nearly every provider-facing HTTP node in the enrichment workflow
(`Lusha Enrich`, `Apollo Match`, `ZoomInfo Mint`, `Claude Web Research`, `Judge Call`, …) is
configured `onError: continueRegularOutput`, meaning a provider 401/429/403 does **not** fail the
n8n execution — the execution reports `status: "success"` regardless. Only the two real HubSpot
write nodes (`HubSpot Update`, `HubSpot Create`, no `onError` override) will actually fail an
execution on a bad write. This means the naive plan ("read `execution.status`, translate it")
only reliably covers "malformed record" (HubSpot write rejects a bad payload) — the other three
causes named in criterion 2 (expired credential, rate limit, exhausted quota) mostly happen
**inside a "successful" execution** and are not visible from execution status alone.

**Primary recommendation:** For STATUS-04, drop the HubSpot-lock-property framing entirely and
define "stuck" purely from the executions API the client already reads under D-01: an execution
with `status: "running"` whose `startedAt` is older than a configured threshold. This needs no
schema change, fits the credential boundary exactly as designed (client already holds this data),
and is honest about what the pipeline can actually detect. "Queued but never processed" and
"review backlog" ARE answerable from HubSpot today, using the real property names
(`lv_enrichment_requested`, `lv_enrichment_status`, `lv_enrichment_needs_review`,
`lv_icp_needs_review`) — but "queued" can only mean "requested and not yet resolved," never
"requested more than N minutes ago," because no request timestamp exists to measure against.
For STATUS-02, seed the static table with the one cause the execution API genuinely surfaces
(malformed record → HubSpot 4xx on write) and route the other three through the Claude fallback
by design until a future phase (out of scope here) adds `fullResponse`/status-code capture to the
provider nodes — this is not a planning failure, it is the honest state of the instrumentation
today, and D-04/D-05's table-first-with-guarded-fallback design already anticipates exactly this.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Workflow on/off, last-run success, in-flight | Client (direct n8n API) | — | D-01: client already holds `X-N8N-API-KEY`; no credential gap |
| Write-safety flag state (armed/disarmed) | Client (direct n8n API, read `GET /workflows/{id}`) | — | Same credential; D-03 requires reading the backend, not local belief |
| Provider credit balances | n8n-side status endpoint (`hubspot/backend-status`) | — | Client holds no provider credential (STATUS-03) |
| Stuck-lock detection | Client (executions API, `status=running` + age) | — | No HubSpot lock property exists; the only real signal is execution age, which the client already reads |
| Queued-never-processed / review backlog counts | n8n-side status endpoint (HubSpot Search) | — | Client holds no HubSpot credential |
| Failure-cause translation (table lookup) | Client (static table + raw error text) | Claude (fallback interpretation) | D-04: deterministic first, then a guarded model fallback — no backend role |
| Dashboard Artifact publish/republish | Client / conversation | — | Platform-level Artifact mechanism, not a backend concern |

## Standard Stack

No new library or package is required. This phase is wiring against three protocols already in
active use in this repo:

| Surface | Method | Auth | Already exercised by |
|---|---|---|---|
| `GET /api/v1/workflows` | n8n Public API | `X-N8N-API-KEY` | `scripts/deploy_n8n_workflows.py::_get_live_workflows()` |
| `GET /api/v1/executions`, `GET /api/v1/executions/{id}` | n8n Public API | `X-N8N-API-KEY` | `scripts/enrichment_cost_ledger.py::_list_executions()` / `_get_execution()` |
| `POST /crm/v3/objects/{companies\|contacts}/search` | HubSpot Search API | HubSpot app token (n8n-side only) | `n8n/wf_scheduled_maintenance_cloud.json` (`SJ-3 Search`, `Review Search`, etc.) |
| Provider usage endpoints (Lusha/Apollo/ZoomInfo) | provider-specific | provider key (n8n-side only) | `scripts/check_provider_credits.py`, dangling `*Usage` nodes in `wf_enrichment_cloud.json` |
| Artifact publish/update | Claude platform tool call | conversation-scoped | New to this phase; see §"Artifact stable URL" |

**Installation:** none. No `npm install` / `pip install` — this phase adds read-only HTTP calls and
one regex-based literal extractor, using whatever HTTP client the plugin's chosen runtime already
uses (not yet fixed — Phase 23 has not landed; see Environment Availability).

## Package Legitimacy Audit

Not applicable — this phase installs no external package. Skipped per the "Required whenever this
phase installs external packages" condition in the output contract.

## Architecture Patterns

### System Architecture Diagram

```
Operator: "what's the backend doing?"
        │
        ▼
Client (Claude plugin, holds n8n API key + webhook secret — no provider/HubSpot creds)
        │
        ├──► GET /api/v1/workflows            (X-N8N-API-KEY)
        │      → per workflow: {id, name, active, nodes[...]}
        │      → regex-scan "Decide Action"/"Decide Company Action" jsCode for
        │        ALLOW_HUBSPOT_RECORD_WRITES / ALLOW_HUBSPOT_CREATE literal
        │
        ├──► GET /api/v1/executions?workflowId=&limit=&cursor=   (X-N8N-API-KEY)
        │      → per workflow: latest execution → status, startedAt, stoppedAt
        │      → in-flight: status="running" AND stoppedAt=null
        │      → stuck: status="running" AND (now - startedAt) > threshold
        │
        └──► POST hubspot/backend-status        (header secret, n8n-side)
                     │
                     ▼
             n8n workflow (holds HubSpot + provider creds)
                     │
                     ├──► Lusha/Apollo/ZoomInfo usage endpoints → {credits|unknown}
                     ├──► HubSpot Search: lv_enrichment_requested=true
                     │      AND lv_enrichment_status NOT IN (complete, needs_review)
                     │      → queued-never-resolved COUNT
                     └──► HubSpot Search: lv_enrichment_needs_review=true
                            OR lv_icp_needs_review=true
                            → review-backlog COUNT
                     │
                     ▼
             {credits: {...}, queued_count, review_backlog_count, credential_health}
        │
        ▼
Client merges both reads → table-lookup failure cause (fallback to Claude if unmatched,
   D-05 guardrail applied) → conversational text, or Artifact on request (same URL on refresh)
```

### Recommended Project Structure

No new top-level structure — this phase's logic lives inside whatever `operator-claude-plugin/`
layout Phase 23 establishes (not yet built; see Environment Availability), plus a small backend
addition to `n8n/wf_enrichment_cloud.json` (the `hubspot/backend-status` webhook path Phase 25
already scaffolds by leaving the three `*Usage` nodes dangling, ready to be wired to a response).

### Pattern 1: Read-only literal extraction for the write-safety flag (D-03)

**What:** `enable_baked_flags()` in `scripts/deploy_n8n_workflows.py` already defines the exact
literal shape the flag takes (`const ALLOW_HUBSPOT_RECORD_WRITES = "false";` / `"true";`) inside
the `jsCode` of two named Code nodes: `Decide Action` (contacts) and `Decide Company Action`
(companies). A read-only client does the mirror-image operation: GET the workflow, find those two
node names, regex out the current literal, and report it — never write it.

**When to use:** STATUS-01's "whether live writes are currently enabled" and STATUS-03's
implicit companion (nothing here needs a provider credential).

**Example:**
```python
# Source: scripts/deploy_n8n_workflows.py — the disabled/enabled literal pair this
# extractor must recognize (mirrors _OVERLAY_FLAG_SPEC's own literals exactly)
import re
FLAG_RE = re.compile(r'const\s+ALLOW_HUBSPOT_RECORD_WRITES\s*=\s*"(true|false)";')

def read_write_safety(workflow_json: dict) -> str | None:
    """Returns 'true'/'false' if found consistently in both known nodes, else None
    (report as unknown — never guess)."""
    found = set()
    for node in workflow_json.get("nodes", []):
        if node.get("name") not in ("Decide Action", "Decide Company Action"):
            continue
        js = node.get("parameters", {}).get("jsCode", "")
        m = FLAG_RE.search(js)
        if m:
            found.add(m.group(1))
    if len(found) == 1:
        return found.pop()
    return None  # 0 or >1 distinct values found — report unknown, flag the inconsistency
```
[VERIFIED: scripts/deploy_n8n_workflows.py — `_OVERLAY_FLAG_SPEC["ALLOW_HUBSPOT_RECORD_WRITES"]`
and the literal `const ALLOW_HUBSPOT_RECORD_WRITES = "false";` confirmed present verbatim in both
`Decide Action` and `Decide Company Action` nodes of the committed `n8n/wf_enrichment_cloud.json`]

### Pattern 2: Unknown-vs-zero propagation (D-08/STATUS-06)

**What:** `scripts/check_provider_credits.py`'s extractors already return `None` (never `0`) on
any shape mismatch or non-2xx response, and `scripts/enrichment_cost_ledger.py`'s
`capture_credit_snapshot()` already distinguishes `configured: false` (no credential at all) from
`configured: true, credits: None` (probed, refused). This is the exact three-state contract
STATUS-06 asks for — port it verbatim into the status endpoint's response, and have the client
render `None`/absent as the literal word "unknown," never `0` and never a healthy-looking blank.

**When to use:** Every field in the status response that a credential or API can refuse to supply.

**Example:**
```json
// Source: .planning/workstreams/milestone/phases/22-armed-e2e-enrichment-canary/snapshots/
//         credits-pre-arming-2026-07-30-20260730T085813Z.json (live-captured, real account)
{
  "lusha":    {"configured": true, "credits": 3940, "error": null, "status": 200},
  "zoominfo": {"configured": true, "credits": 9301, "error": null, "status": 200},
  "apollo":   {"configured": true, "credits": null, "error": null, "status": 403}
}
```

### Pattern 3: n8n execution list/status read (STATUS-01's "in flight")

**What:** `GET /api/v1/executions` returns `.data[]` items shaped `{id, workflowId, status,
finished, startedAt, stoppedAt, mode, ...}`. Official docs [CITED:
https://docs.n8n.io/connect/n8n-api/execution] enumerate `status` as one of: `canceled`,
`crashed`, `error`, `new`, `running`, `success`, `unknown`, `waiting`. "In flight" = `status ==
"running"` (equivalently, `stoppedAt == null`); "last run succeeded" = most recent execution for
that `workflowId` has `status == "success"`.

**When to use:** STATUS-01 criterion 1 (last run + whether it succeeded, what's in flight).

**Example:**
```python
# Source: scripts/enrichment_cost_ledger.py::main() 'list' branch — this repo's own
# defensive read, kept here because older n8n API responses may lack `status` entirely
# and only carry `finished` (boolean). Mirror this fallback rather than trusting `status`
# unconditionally.
status = ex.get("status") or ("finished" if ex.get("finished") else "running")
```
Pagination [CITED: https://docs.n8n.io/connect/n8n-api/pagination]: default page size 100, max
250, response carries `nextCursor`; pass it back unchanged as `cursor` on the next call; `null`
means no more pages. Rate limits [CITED: same doc family]: n8n Cloud enforces per-plan execution
limits rather than a documented flat requests/second cap; this repo's existing scripts issue at
most a handful of calls per invocation and have never hit a 429 in testing — budget for one
retry-with-backoff on 429 defensively, but do not build elaborate rate-limit handling for a status
read that runs on operator demand, not a tight poll loop.

### Anti-Patterns to Avoid

- **Trusting `execution.status` as a complete failure catalog.** Nearly every provider-facing
  node in `wf_enrichment_cloud.json` is `onError: continueRegularOutput` — a 401/403/429 from
  Lusha/Apollo/ZoomInfo/Anthropic does **not** flip the execution to `error`/`crashed`. Only
  `HubSpot Create`/`HubSpot Update` (no `onError` override) will fail the execution outright.
  [VERIFIED: `n8n/wf_enrichment_cloud.json` node-by-node `onError` field, enumerated directly]
- **Asserting write-safety from the plugin's own config.** D-03 exists precisely because this is
  the failure mode to avoid — always read the live workflow JSON, never a locally cached belief.
- **Treating the two write-safety nodes as one.** `Decide Action` and `Decide Company Action` are
  separate Code nodes with separately-baked literals. `enable_baked_flags()` rewrites both
  atomically at deploy time, but a *read-only* client cannot assume they still agree (a partial
  deploy, or manual n8n-UI edit, could desync them) — read both, and if they disagree, report the
  disagreement rather than picking one.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Provider credit probing (3 providers, 3 different failure shapes) | A new HTTP client per provider | Port `scripts/check_provider_credits.py`'s `_extract_lusha`/`_extract_apollo`/`_extract_zoominfo` + `scripts/provider_registry.py`'s endpoint/auth table into the n8n-side endpoint | Already live-validated against real accounts (Lusha 200, ZoomInfo 200 w/ Accept header, Apollo 403) — re-deriving risks silently regressing the Accept-header/406 and non-master-key/403 findings |
| Write-safety flag extraction | A bespoke JSON-walking parser | The exact regex `enable_baked_flags()` already uses for its own fail-closed re-scan | Guarantees the read side recognizes precisely the literal the write side produces — divergent regexes would silently desync |
| Execution pagination | Custom retry/backoff scaffolding | n8n's documented `cursor`/`nextCursor` convention, already used correctly (single-page) in `scripts/enrichment_cost_ledger.py::_list_executions` | No custom pagination code exists yet in this repo to copy verbatim; the cursor contract itself is simple enough that hand-rolling a wrapper is fine, but do not invent a different pagination shape |
| Stuck-lock / review-backlog HubSpot filters | A generic "any needs_review-like field" scanner | The exact real property names already used by `wf_scheduled_maintenance_cloud.json`'s `SJ-3 Search`/`Review Search` nodes | These are the only filters this repo has ever live-tested against the real HubSpot schema; the generic names in root `CLAUDE.md` (`enrichment_status`, `enrichment_lock_until`) do not exist and will 400 or silently match nothing |

**Key insight:** almost everything this phase needs already exists somewhere in this repo in a
live-validated form (three separate places, in one case) — the job is porting a read pattern, not
inventing one. The one place nothing exists to copy is the stuck-lock/queued-timestamp problem,
because the underlying HubSpot property was never built (see Open Questions).

## Common Pitfalls

### Pitfall 1: Reporting "healthy" when a provider-side failure never touched execution status
**What goes wrong:** A pipeline run where Lusha returns 401 (expired key) still shows
`execution.status: "success"` in the executions API, because `Lusha Enrich`'s `onError:
continueRegularOutput` swallows the failure into the item payload rather than failing the node.
**Why it happens:** The workflow was built to degrade gracefully (a dead provider should not stop
a company being scored on the providers that DO work) — a deliberate design choice, not a bug, but
one this phase's status surface must not misread as "nothing is wrong."
**How to avoid:** Do not derive "is Lusha working" from execution status. Derive it from the
credit-balance probe (STATUS-03's endpoint) — a probe that itself 401s/403s IS the credential-health
signal, independent of whether any enrichment execution happened to run recently.
**Warning signs:** A "why does the operator say Lusha never worked when every execution shows
success" ticket.

### Pitfall 2: STATUS-04's literal spec references a property that does not exist
**What goes wrong:** Planning a HubSpot Search filter on `enrichment_lock_until` (as both root
`CLAUDE.md` §4.1 and the phase's own REQUIREMENTS.md/CONTEXT.md wording describe) will fail,
because `config/hubspot_properties.yaml` has no such property, and nothing in
`n8n/wf_enrichment_cloud.json` ever sets `lv_enrichment_status` to `"running"` in the first place.
**Why it happens:** Root `CLAUDE.md` is a generalized architecture spec written before the actual
MVP; the real build (Phase 15/16 era, confirmed by the `Decide Company Action` node's code)
implemented a narrower two-state status (`complete`/`needs_review`) and never added the
lock/timestamp fields the generalized spec describes.
**How to avoid:** See Open Questions #1 — redefine "stuck" against the executions API (age of a
`running` execution) instead of a HubSpot property that was never built.
**Warning signs:** A HubSpot Search request with `propertyName: "enrichment_lock_until"` returning
a 400 ("property does not exist") the first time this phase is actually implemented.

### Pitfall 3: ZoomInfo's usage endpoint 406s without the JSON:API Accept header
**What goes wrong:** `GET https://api.zoominfo.com/gtm/data/v1/users/usage` returns 406 unless the
request sets `Accept: application/vnd.api+json` — a header that is easy to omit when porting the
call to a new endpoint.
**Why it happens:** ZoomInfo's GTM data API is JSON:API throughout, contract-verified in this repo
(`docs/LUSHA-V3-CONTRACT.md` reference and `scripts/check_provider_credits.py::_check_zoominfo`).
**How to avoid:** Copy the header verbatim from `PROVIDER_REGISTRY["zoominfo"]["credit"]["accept"]`
rather than re-typing it.
**Warning signs:** ZoomInfo balance always reads "unknown" even though the account has credits and
the token mint succeeded.

### Pitfall 4: Apollo's 403 must never render as "0 credits" or "healthy"
**What goes wrong:** A shallow "if request failed, treat balance as 0" fallback would tell the
operator Apollo has no credit headroom, which is false — this account's key is simply non-master
and cannot read the usage endpoint at all.
**Why it happens:** `403` and `credits: 0` look superficially similar ("can't spend") but mean
opposite things operationally (one is "you're out," the other is "we can't tell you").
**How to avoid:** D-08's unknown-vs-zero rule; `_extract_apollo` already returns `None` on this
403, never `0` — preserve that exact behavior end to end into the client's rendering.
**Warning signs:** An operator asks "why did we stop using Apollo" when in fact nothing changed —
the read was always unreadable, and a bad status surface just started calling it "zero."

## Code Examples

### Determining "last run + succeeded" per workflow (STATUS-01)

```python
# Source: mirrors scripts/enrichment_cost_ledger.py::_list_executions / main() 'list' branch
import requests

def last_execution(base_url, headers, workflow_id):
    r = requests.get(f"{base_url}/api/v1/executions",
                      params={"workflowId": workflow_id, "limit": 1},
                      headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json().get("data", [])
    if not data:
        return {"status": "never_run"}
    ex = data[0]
    status = ex.get("status") or ("finished" if ex.get("finished") else "running")
    return {
        "status": status,
        "in_flight": status == "running",
        "started_at": ex.get("startedAt"),
        "stopped_at": ex.get("stoppedAt"),
    }
```

### HubSpot Search filters for queued-never-resolved and review backlog (n8n-side, STATUS-04)

```javascript
// Source: real property names confirmed live in n8n/wf_scheduled_maintenance_cloud.json's
// "SJ-3 Search (requested poller)" and "Review Search (approved=true)" nodes — NOT the
// generic `enrichment_status`/`enrichment_lock_until` names from root CLAUDE.md, which do
// not exist on this portal's schema.

// Queued but never resolved (companies) — note: cannot filter by "how long," no
// requested_at-style timestamp exists on this object.
const queuedFilter = {
  filterGroups: [{ filters: [
    { propertyName: "lv_enrichment_requested", operator: "EQ", value: "true" },
    { propertyName: "lv_enrichment_status", operator: "NEQ", value: "complete" },
    { propertyName: "lv_enrichment_status", operator: "NEQ", value: "needs_review" },
  ]}],
  limit: 1,          // only .total is needed for a count
};

// Review backlog (companies) — two OR'd reasons a record needs a human.
const reviewBacklogFilter = {
  filterGroups: [
    { filters: [{ propertyName: "lv_enrichment_needs_review", operator: "EQ", value: "true" }] },
    { filters: [{ propertyName: "lv_icp_needs_review", operator: "EQ", value: "true" }] },
  ],
  limit: 1,
};
```
Both reuse the search-count-only trick (`limit: 1`, read `.total` from the response) to avoid
pulling full row payloads for a badge count.

### Stuck-lock detection, recommended replacement definition (client-side, STATUS-04)

```python
# No backend call needed beyond what STATUS-01 already reads — this reframes "stuck" as
# an execution-age question, answerable entirely from data the client already holds under D-01.
from datetime import datetime, timezone

STUCK_THRESHOLD_MINUTES = 15  # matches this repo's existing LOCK_TTL_MINUTES convention
                               # from the .env.example template in root CLAUDE.md §11.2

def is_stuck(execution: dict, now=None) -> bool:
    if execution.get("status") != "running":
        return False
    started = execution.get("startedAt")
    if not started:
        return False  # can't judge age -> not "stuck", report unknown separately
    now = now or datetime.now(timezone.utc)
    started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
    return (now - started_dt).total_seconds() > STUCK_THRESHOLD_MINUTES * 60
```

## State of the Art

| Old Approach (root CLAUDE.md's generalized spec) | Current Approach (as actually built) | When Changed | Impact |
|---|---|---|---|
| Per-record lock via `enrichment_lock_until` + `enrichment_status=running` | No lock property exists; `lv_enrichment_status` only ever resolves to `complete`/`needs_review` | Never implemented — the generalized architecture doc predates the narrower MVP build (Phase 15/16) | STATUS-04 cannot use the property the spec names; must be redefined against the executions API |
| Flat `enrichment_*` property names | `lv_`-prefixed real properties (`lv_enrichment_status`, `lv_enrichment_requested`, `lv_enrichment_needs_review`) | Same divergence | Any HubSpot filter built against the generic names will 400 or silently match nothing |
| Direct-to-provider client reads (`scripts/check_provider_credits.py` framing) | Client holds no provider credential at all; reads come through `hubspot/backend-status` | Established explicitly for this milestone (REQUIREMENTS.md "Credential boundary") | STATUS-03's whole reason to exist — do not let `check_provider_credits.py`'s pattern leak into client code, only into the *backend* endpoint |

**Deprecated/outdated:** the `enrichment_lock_until`/lock-acquire-release architecture described
in root `CLAUDE.md` §4.1 and §17.1 — never built, and this phase should not resurrect it just to
satisfy the letter of the stuck-lock wording; see Open Questions #1 for the recommended
replacement.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | n8n Cloud has no documented flat requests/second rate limit for the Public API, only per-plan execution limits | Pattern 3 / Standard Stack | If wrong, a status read hammering `/executions` per-workflow in a loop could 429 unexpectedly; mitigate with a single retry-with-backoff regardless |
| A2 | 15 minutes is a reasonable "stuck" threshold for a running execution | Code Examples / stuck-lock | Too short → false positives on a legitimately slow research+judge run; too long → a genuinely wedged record sits unnoticed longer. This number is carried from the `.env.example` `LOCK_TTL_MINUTES` convention in root CLAUDE.md §11.2, which describes a mechanism this repo never actually built — treat the number itself as a starting point, not a measured value |
| A3 | The Artifact "redeploy to same identifier" mechanism works within a single conversation without extra plumbing, but a NEW conversation has no way to recover a prior artifact's identifier unless the plugin persists it somewhere | §"Artifact stable URL" | If cross-session refresh is actually required by the acceptance criteria, "same URL" may only be achievable within one sitting, not across a new chat — needs an explicit decision, not silent under-delivery |
| A4 | n8n's execution-level `resultData.error` / per-node `runData[node][0].error` shapes documented publicly (`{message, stack?, context?}` / `{message, description?, context?}`) match what this instance actually returns | §"Error signatures" | Unverified against a real failed execution in THIS n8n Cloud instance (no live failed execution was available to inspect during this research session) — the static table's field-name assumptions should be spot-checked against one real failure before the table ships |

**If this table is empty:** N/A — populated above.

## Open Questions

1. **STATUS-04's "stuck lock" cannot be computed as literally specified — needs a locked
   redefinition before planning.**
   - What we know: `config/hubspot_properties.yaml` has no `enrichment_lock_until` property on
     either companies or contacts [VERIFIED: full-file grep, zero matches for "lock"]. Nothing in
     `n8n/wf_enrichment_cloud.json` ever writes `lv_enrichment_status = "running"` — only
     `"needs_review"` and `"complete"` appear as assignments [VERIFIED: read `Decide Company
     Action`'s full jsCode body directly].
   - What's unclear: whether the planner should (a) redefine "stuck" entirely against the
     executions API (recommended, no schema change, fits D-01/D-02 exactly), or (b) treat adding
     `lv_enrichment_requested_at` + actually setting `lv_enrichment_status="running"` at the start
     of a run as in-scope backend work for this phase (the ROADMAP already treats the
     `hubspot/backend-status` endpoint itself as legitimate backend work for this milestone, so a
     property addition is not obviously out of bounds — but it is a bigger lift than option (a) and
     touches the enrichment workflow's write path, which a read-only phase should be reluctant to
     do).
   - Recommendation: (a). It costs nothing, needs no HubSpot schema migration, and produces a
     real, honest signal ("this execution has been running for 40 minutes") instead of reviving an
     architecture that was designed but never implemented.

2. **"Queued but never processed" can only mean "requested and unresolved," never
   "requested more than N minutes ago" — confirm this is an acceptable definition.**
   - What we know: `lv_enrichment_requested` (bool) + `lv_enrichment_status` (enum) exist and are
     real, live-searchable properties [VERIFIED: `SJ-3 Search (requested poller)`'s actual filter
     body]. No timestamp records *when* a record was requested.
   - What's unclear: whether the operator needs "has been queued too long" (which needs a new
     timestamp property) or a bare count is sufficient for criterion 4 ("silently wedged backend
     is visible... counts matter more than pretty output").
   - Recommendation: ship the bare count for this phase (matches the criterion's literal wording,
     "surfaced with counts"); flag age-of-queue as a future enhancement requiring a schema
     addition, not a blocker for this phase.

3. **STATUS-02's four named causes are not equally observable from the executions API today —
   confirm the fallback-heavy outcome is acceptable, or scope a companion instrumentation fix.**
   - What we know: `HubSpot Create`/`HubSpot Update` have no `onError` override and will genuinely
     fail an execution (→ "malformed record" is directly observable via `resultData.error` /
     `lastNodeExecuted`). Every provider-facing node (`Lusha Enrich`, `Apollo Match`, `ZoomInfo
     Mint`, `Claude Web Research`, `Judge Call`, and their siblings) is `onError:
     continueRegularOutput` and none of them declare `options.response.fullResponse` — meaning a
     401 (expired credential), 429 (rate limit), or a quota-exhaustion condition from a provider
     will NOT fail the execution and may not even preserve the numeric HTTP status in the item the
     downstream Code node sees. [VERIFIED: enumerated `onError` and `options` on every
     credential-bearing node in `n8n/wf_enrichment_cloud.json`]
   - What's unclear: whether this phase should accept a mostly-Claude-fallback experience for 3 of
     4 causes (consistent with D-04/D-05's explicit design for exactly this situation), or whether
     a companion task should add `fullResponse: true` to the provider HTTP nodes so their real
     status code survives into `runData` — which is a workflow-JSON edit, arguably still "reading
     more precisely" rather than "mutating behavior," but touches the same files Phase 28 is meant
     to own.
   - Recommendation: accept the fallback-heavy outcome for causes 2-4 in this phase (it is what
     D-04/D-05 were written for), and record `fullResponse` instrumentation as a candidate
     follow-up — not a blocker, since the guardrail already makes an honest "I don't recognize
     this" a safe default.

4. **Does "refresh re-publishes to the same URL" (D-09) need to survive a new conversation, or
   only a refresh within the same one?**
   - What we know: the Artifact platform's redeploy/update mechanism naturally keeps the same
     identifier (and therefore the same URL) across repeated tool calls **within one
     conversation** — omitting `capabilities` on a redeploy already "carries the stored
     declaration forward," confirming update-in-place is the platform's normal behavior for a
     repeated publish targeting the same artifact.
   - What's unclear: whether "the operator asks again in a brand-new chat" must also land on the
     same URL. That requires the plugin to have persisted the artifact's identifier somewhere
     outside the conversation that produced it — and the plugin currently has no such store (its
     only config is admin-provisioned, read-only, and PLUGIN-02 forbids the operator handling
     anything that looks like a credential/identifier by hand).
   - Recommendation: scope D-09 to same-conversation refresh only (consistent with this
     milestone's existing pattern of conversation-scoped state, e.g. CONTROL-04's live-write
     permission); if cross-session stability turns out to matter, that needs its own decision about
     where a plugin-owned identifier could live, which is out of scope for a read-only status
     phase to invent unilaterally.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| n8n Cloud instance + `X-N8N-API-KEY` | STATUS-01 (client-side reads) | Assumed available in production (admin-provisioned) — not independently verified this session (no live credential probed) | n8n Cloud, Public API v1 | None — a missing/rejected key must produce PLUGIN-03's "refuse and name who can fix it," not a silent status gap |
| HubSpot Search API access (n8n-side only) | STATUS-04 | Already used successfully by the deployed `wf_scheduled_maintenance_cloud.json` scheduled searches | CRM v3 | None needed — same credential already proven live |
| Lusha / Apollo / ZoomInfo usage endpoints | STATUS-03 | Live-validated 2026-07-30 (Lusha 200, ZoomInfo 200, Apollo 403-by-design) [VERIFIED: Phase 22 canary snapshot] | n/a | Apollo's 403 IS the expected/handled case, not a gap |
| `operator-claude-plugin/` runtime (language/framework) | All client-side work in this phase | **Not yet decided** — Phases 23-26 (its prerequisites) have CONTEXT/RESEARCH docs but no implementation; the directory holds only README + CHANGELOG | — | Phase 27 planning should not assume a specific language; keep the flag-extraction regex and executions-read logic phrased so they port cleanly whichever runtime Phase 23 lands on |

**Missing dependencies with no fallback:** none identified beyond the standing "n8n
URL/API-key must be configured" requirement already covered by PLUGIN-03 in an earlier phase.

**Missing dependencies with fallback:** none beyond what's noted above.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (backend/Python conventions) — `.venv/bin/python -m pytest`; the plugin-side test framework is undecided pending Phase 23 |
| Config file | none dedicated; repo-root `pytest.ini`/`.pytest_cache` present, no special config needed |
| Quick run command | `.venv/bin/python -m pytest tests/test_check_provider_credits.py tests/test_deploy_flag_overlay.py -q` |
| Full suite command | `.venv/bin/python -m pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STATUS-01 | Write-safety literal extractor returns correct value / None-on-mismatch | unit | `pytest tests/test_status_flag_read.py -x` | ❌ Wave 0 |
| STATUS-01 | In-flight/last-run status derivation from a mocked executions response | unit | `pytest tests/test_status_executions_read.py -x` | ❌ Wave 0 |
| STATUS-02 | Static table lookup for the "malformed record" HubSpot-4xx case; fallback path labels unmatched errors + defaults attribution to "an admin" (D-05) | unit | `pytest tests/test_status_error_translation.py -x` | ❌ Wave 0 |
| STATUS-03 | Backend endpoint response preserves unknown-vs-zero across all three providers | unit (mocked HTTP, mirrors `tests/test_check_provider_credits.py`'s existing pattern) | `pytest tests/test_backend_status_endpoint.py -x` | ❌ Wave 0 |
| STATUS-04 | HubSpot search filter bodies match the real property names; stuck-execution age calculation | unit | `pytest tests/test_status_hubspot_filters.py -x` | ❌ Wave 0 |
| STATUS-05 | Artifact publish/update call carries the same identifier on a same-conversation refresh (manual/exploratory — no automated harness exists for Artifact publish behavior) | manual-only | n/a — justified: the Artifact publish mechanism is a platform tool call, not something this repo's pytest suite can invoke | — |
| STATUS-06 | `None`/absent renders as the literal string "unknown," never `0` | unit | `pytest tests/test_status_unknown_rendering.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the quick run command above.
- **Per wave merge:** full suite command.
- **Phase gate:** full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_status_flag_read.py` — write-safety literal extractor, including the
  "both nodes must agree" defensive check.
- [ ] `tests/test_status_executions_read.py` — in-flight/last-run/stuck-execution derivation,
  mocked `requests` responses shaped per the official `status` enum.
- [ ] `tests/test_status_error_translation.py` — static table + D-05 guardrail (unmatched →
  labeled interpretation, raw text shown, attribution defaults to admin).
- [ ] `tests/test_backend_status_endpoint.py` — mirrors `tests/test_check_provider_credits.py`'s
  mocked-HTTP idiom, extended to also assert the HubSpot-count filters.
- [ ] `tests/test_status_hubspot_filters.py` — filter-body construction against the real
  `lv_`-prefixed property names (guards against silently regressing to the generic
  `enrichment_status`/`enrichment_lock_until` names from root CLAUDE.md).
- [ ] `tests/test_status_unknown_rendering.py` — `None`/absent → "unknown" string, never `0`.
- [ ] Plugin-side test framework itself does not exist yet (Phase 23 not built) — this phase's
  client-side logic needs whatever harness Phase 23 establishes; the above pytest files cover the
  **backend-side** (`n8n/wf_enrichment_cloud.json` extension) half only.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | yes | `X-N8N-API-KEY` and the `hubspot/backend-status` header-auth secret are both admin-provisioned, never operator-visible (PLUGIN-02); this phase adds no new auth mechanism |
| V3 Session Management | yes | The Artifact identifier and the "am I currently armed" answer are both conversation-scoped facts, not persisted server-side by this phase — consistent with CONTROL-04's existing conversation-scope pattern |
| V4 Access Control | yes | Read-only surface by construction (this phase's entire point); no write path exists here to gate |
| V5 Input Validation | yes | HubSpot Search filter bodies are built server-side (n8n) from a fixed, code-reviewed template — no operator-supplied string is ever interpolated into a filter value in this phase |
| V6 Cryptography | n/a | No new secret material or crypto operation introduced |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Leaking a provider/HubSpot credential value into conversational status text | Information Disclosure | Never render a credential value — only counts/booleans/derived health (already this repo's convention: `check_provider_credits.py`'s "NEVER prints a secret value" docstring) |
| A confident-but-wrong fallback interpretation telling an operator they can fix an admin-only problem | Repudiation / operator harm (not a classic STRIDE category, but the explicit concern behind D-05) | The guardrail already locked in D-05: unmatched errors default attribution to "an admin," show raw text, and are labeled as interpretation, not fact |
| Regex-based literal extraction over `jsCode` being fooled by a cosmetically similar but different literal (e.g. whitespace variant) | Tampering (self-inflicted, not adversarial) | Mirror `enable_baked_flags()`'s own fail-closed re-scan regex exactly rather than writing a second, looser one |

## Sources

### Primary (HIGH confidence)
- `scripts/deploy_n8n_workflows.py` — read directly; `_n8n_headers()`, `_get_live_workflows()`,
  `enable_baked_flags()`, `_OVERLAY_FLAG_SPEC` (this repo, live-tested).
- `scripts/enrichment_cost_ledger.py` — read directly; `_list_executions()`, `_get_execution()`,
  `extract_token_usage()`, the `ESTIMATES` table.
- `scripts/check_provider_credits.py` — read directly; per-provider extractors and their
  documented failure modes.
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_scheduled_maintenance_cloud.json` — read directly (node
  types, `onError` settings, jsCode bodies, HubSpot Search filter bodies) via `python3 -c
  "json.load(...)"` inspection in this session.
- `config/hubspot_properties.yaml` — read directly; confirms the real `lv_`-prefixed property
  names and the absence of any lock/timestamp property.
- `.planning/workstreams/milestone/phases/22-armed-e2e-enrichment-canary/snapshots/credits-pre-arming-2026-07-30-*.json`
  — live-captured provider-credit snapshot from this repo's own canary.

### Secondary (MEDIUM confidence)
- [n8n Execution API docs](https://docs.n8n.io/connect/n8n-api/execution) — status enum, response
  fields, `stoppedAt`/`running` semantics [CITED].
- [n8n Pagination docs](https://docs.n8n.io/connect/n8n-api/pagination) — page size, `cursor`/
  `nextCursor` convention, limit range [CITED].
- n8n community/docs discussion of `resultData.error` / per-node `runData[node][0].error` shape
  [CITED, not independently confirmed against a live failed execution in this instance — see
  Assumption A4].
- `.planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-RESEARCH.md`
  — the already-designed `hubspot/backend-status` credit-only endpoint this phase generalizes;
  read directly for continuity.

### Tertiary (LOW confidence)
- Root `CLAUDE.md` §§4.1, 17.1, 19, 21, 23 (the generalized architecture spec) — used only to
  identify what was *aspirational and never built*; do not treat any property name or mechanism
  from these sections as implemented without cross-checking `config/hubspot_properties.yaml` and
  the deployed workflow JSON first, as this research had to do repeatedly in this session.

## Metadata

**Confidence breakdown:**
- n8n API read surface (STATUS-01): HIGH — verified against this repo's own live-tested code plus
  official n8n docs.
- Provider balance probing (STATUS-03/STATUS-06): HIGH — live-validated snapshot exists from this
  repo's own canary run.
- Stuck-lock/queue/review (STATUS-04): MEDIUM — the recommended redefinition is sound and
  code-grounded, but requires an explicit planner/user decision to diverge from the phase's own
  written spec wording.
- Error-signature translation (STATUS-02): MEDIUM — the mechanism (D-04/D-05) is well specified,
  but this session could not observe a real failed execution in this n8n instance, so the exact
  field shapes are cited from public docs rather than verified live.
- Artifact stable URL (STATUS-05): MEDIUM — the platform mechanism is confirmed via the
  `artifact-capabilities` skill reference, but cross-session scope is an open question.

**Research date:** 2026-07-30
**Valid until:** 30 days for the n8n/HubSpot mechanics (stable APIs); re-verify the provider
credit shapes sooner (7-14 days) if any provider contract changes, per this repo's existing
`docs/LUSHA-V3-CONTRACT.md` precedent of provider APIs shifting without notice.
