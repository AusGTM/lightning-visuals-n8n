# Phase 26: Outcome Reporting & Safe Retry - Research

**Researched:** 2026-07-30
**Domain:** Parsing an n8n webhook/execution response into a per-record ledger; safe re-dispatch
**Confidence:** MEDIUM-HIGH on what the backend *actually does* today (read directly from the
deployed workflow JSON — no guessing); LOWER on exact n8n Cloud runtime behavior that can only be
confirmed by a live execution (node-execution ordering under `responseMode: lastNode`, exact HTTP
Request node output-merge behavior). Every such gap is called out explicitly with a cheap
live-verification recommendation rather than papered over.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Outcomes are read **from the synchronous webhook response first**, falling back to
  `GET /api/v1/executions` with the n8n API key the plugin already holds when the POST times out or
  returns partial. Both paths feed one report renderer.
- **D-02:** The fallback is what makes success criterion 3 achievable. Without it, a batch that
  outruns the webhook timeout has no route to its own outcome and fails opaquely — which is
  precisely the in-flight case the criterion names.
- **D-03:** A report built from the fallback path must state that it came from the executions API
  and that the run may still be progressing. It never presents an incomplete run as finished.
- **D-04:** Duplicate-safety on retry is **guaranteed by the backend's existing identity
  resolution**, not by client-side bookkeeping. n8n runs identity resolution and update-vs-create
  routing on every row, so a re-sent row that the earlier attempt already accepted is **updated in
  place rather than duplicated**. The client simply re-sends the failed batch.
  — Reversibility: reversible — client-side exclusion could be layered on later if the backend
  guarantee ever proves insufficient, but adding it now would create a second dedupe authority
  that can drift from n8n's.
- **D-05:** This is the same scope-anchor discipline the whole milestone follows: the client does
  not reimplement identity, mapping, normalization, or dedupe. Retry safety is a backend property
  the client relies on and states plainly to the operator.
- **D-06:** The report prints a **run handle** (an execution reference) and the operator asks to
  re-check it conversationally. Re-check is **manual in this phase**.
- **D-07:** The unprompted bounded watch is deliberately left to Phase 29 (NOTICE-01/NOTICE-02) so
  it is built once. Phase 26 must not grow a poll loop.
- **D-08:** Reports lead with **summary counts** — created / updated-matched / needs_review /
  rejected — then show **the failing rows in full**, since those are the actionable ones. Complete
  per-record detail is available on request.
- **D-09:** This mirrors the adaptive convention set by Phase 23 D-08 for previews: small results
  shown whole, large results summarized with the actionable part surfaced. One convention across
  preview and report.
- **D-10:** For enrichment dispatches the report shows, per record, at minimum **ICP tier and the
  needs-review flag**, alongside remaining provider credits taken from the enrichment response's
  own `remaining_credits` or the n8n-side status endpoint. The client never queries a provider
  itself.

### Claude's Discretion

- Exact wording of outcome labels shown to the operator, provided they map cleanly to
  created / updated-matched / needs_review / rejected.
- Format of the run handle and how re-check is phrased.
- Timeout threshold that triggers the executions-API fallback.
- Whether the drill-down renders in chat or as an Artifact (Phase 23 D-09 permits either).
- How rejected-row reasons are grouped when many rows share one cause.

### Deferred Ideas (OUT OF SCOPE)

- **Unprompted in-session watch until a run settles** — Phase 29 / NOTICE-01, NOTICE-02. D-07
  explicitly keeps the poll loop out of this phase.
- **Client-side accepted-row tracking** — rejected as a second dedupe authority (D-04). Revisit
  only if the backend guarantee proves insufficient in practice.
- **Scheduled sweep reporting** — Phase 29 / NOTICE-03.
- **Full backend health context in reports** — Phase 27 / STATUS-01..06.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REPORT-01 | Per-record outcome (created/updated/needs_review/rejected) instead of bare HTTP status | §The `hubspot/contact-upload` outcome pipeline (exact) — including the two confirmed gaps that block a naive read of the terminal nodes |
| REPORT-02 | Enrichment results (ICP tier, needs-review flag, remaining credits) without leaving session | §The `hubspot/enrichment/event` response contract — confirms `remaining_credits` is real and present, and that **ICP tier is not computed anywhere in this pipeline today** (a genuine gap, not a parsing problem) |
| REPORT-03 | Graceful degradation when the run is still in flight | §Timeout behavior, §Executions-API fallback and run-handle correlation |
| DISPATCH-04 | Failed/partial dispatch reported with failing rows named; retry-safe | §Retry duplicate-safety verification — confirms the email path is safe, and identifies the one identity path (no-email, name+company) that can never auto-resolve on retry (lands in review both times, which is safe but not silent) |
</phase_requirements>

## Summary

This phase's research question was never really "how do I parse JSON" — it was "what does the
backend actually hand back, and can the plan's promises (a 4-way outcome vocabulary, safe retry,
ICP tier in the enrichment report) actually be kept with zero backend changes." Reading the two
deployed workflow JSONs end-to-end (not the Python MVP, not `CLAUDE.md`'s aspirational description
of it — the literal Cloud JSON that is live today) surfaced four load-bearing, verifiable facts
that change how this phase must be planned, each cited to an exact node:

1. **The contact-upload webhook's `needs_review` terminal node throws away every identifying
   field.** `Set Review` is an Edit-Fields (Set) node with a single assignment
   (`queue = "needs_review"`) and no `includeOtherFields` override — n8n's default behavior for
   that node type is to **output only the fields you explicitly set**, dropping everything else.
   Every row that lands there — genuine `ambiguous` matches needing human judgment, *and*
   `rejected` rows that failed the identity rule server-side — arrives in the wire response (and
   in the executions-API's per-node output for that node) as an indistinguishable
   `{"queue": "needs_review"}`, with no email, no row identity, no reason. This is the single
   concrete "no distinguishable marker" gap the phase brief asked this research to find. It does
   **not** block the phase — `Decide Action` (upstream of `Set Review`) computes and carries
   `action`, `outcome`, `contact_id`, `reason`, and `email` per row, and that data is fully
   recoverable via `GET /api/v1/executions/{id}?includeData=true` reading `Decide Action`'s own
   node output — but a plan that trusts `Set Review`'s own output (or the sync response when
   `Set Review` happens to be the `lastNode`) will silently produce an unusable report.
2. **`hubspot/contact-upload` cannot currently produce a `created` outcome at all.** The `Set
   Config` node hardcodes `allow_create: false` unconditionally on every request — it is not one
   of the four deploy-time-overlayable flags (`ALLOW_HUBSPOT_RECORD_WRITES`,
   `ALLOW_HUBSPOT_CREATE`, `TEST_RECORD_IDS`, `TEST_RECORD_DOMAINS`); it is a separate, earlier,
   non-overlayable literal. Every `net_new` row is forced to `action = "review"` regardless of the
   write-safety gate downstream. This is worth surfacing to the user directly (see Open Questions)
   rather than quietly building a report that promises a `created` bucket the backend cannot
   currently produce.
3. **Retry safety genuinely holds for the email identity path, and genuinely does not (in a
   specific, narrow, already-safe way) for the no-email path.** `resolveIdentity` in
   `Resolve Identity` has a hard rule: a row with no valid email is **never** `net_new` — it is
   always `ambiguous` (→ `needs_review`), because the deployed workflow's `HubSpot Search by
   Email` node is the *only* search performed (the `phone_lastname`/`name_company` weak-key
   branches exist in the pure function but are **always empty** in this deployment, since nothing
   populates those search-result keys). Consequence for D-04: a `firstname+lastname+company`-only
   row can never accidentally duplicate-create on retry (good — D-04's promise holds), but it also
   can never resolve to `update` even if the same person already exists in HubSpot — it sits in
   `needs_review` on every attempt, indefinitely, until a human resolves it (Phase 30 territory).
   This is exactly the case CONTEXT.md's own D-04 hedge anticipated ("a row that landed in
   queue/Set Review... the plan needs to surface it to the operator") — the research confirms it
   is real and names the exact mechanism.
4. **`remaining_credits` is real and present per-item in the enrichment response; ICP tier is
   not, anywhere in this pipeline.** `Build Response` (enrichment workflow) does append a real
   `remaining_credits: [{provider, credits}]` array to every outgoing item — D-10's premise is
   correct. But `lv_icp_fit_score`/`lv_icp_tier`/`lv_anti_icp_flag` are **never written by this
   system** — `src/merge_policy.py`'s own comment ("Approach C... HubSpot owns the derived ICP
   outputs... only the canonical WRITE is removed") confirms this is a deliberate, existing design
   choice carried into the n8n port, not an oversight. No node in the deployed enrichment workflow
   reads a record's ICP tier back from HubSpot after writing to it. REPORT-02's "operator sees ICP
   tier" cannot be satisfied by parsing the enrichment response better — the data simply is not
   there, and the plugin holds no HubSpot credential to fetch it directly. This is a real,
   pre-existing gap the plan must either route around (extend the n8n-side status endpoint to read
   it back, since n8n does hold the HubSpot credential) or flag to the user as a known limitation
   for this phase.

**Primary recommendation:** Build the report renderer against **`GET /api/v1/executions/{id}
?includeData=true`, reading `Decide Action` (contacts) / `Decide Company Action` (companies) node
output by item index**, not the terminal write nodes, as the *authoritative* per-row ledger for
`hubspot/contact-upload`. Treat the synchronous webhook response as a fast-path optimization that
works only when the batch is small, uniform-outcome, and doesn't hit the `Set Review` gap above —
which in practice will be the exception, not the rule, given today's deployed configuration (see
finding 2). This is consistent with D-01 as written (response first, fallback second) — it just
means the fallback is the workhorse, and the plan should budget for that rather than treat the
executions-API path as a rare degraded case. For the enrichment response, read `remaining_credits`
directly off the response body (confirmed present); for ICP tier, either coordinate a small,
additive backend read-back (new to this milestone's backend-touch allowance — see Open Questions)
or explicitly report "not available in this phase" rather than fabricate a value.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-row outcome computation (match/net_new/ambiguous/create/update/review) | n8n (`Decide Action`/`Resolve Identity`) | — | Already computed server-side; the client only reads and renders it |
| Per-row outcome **retrieval** when the sync response is insufficient | Plugin Python script (`report.py`) calling `GET /api/v1/executions/{id}?includeData=true` | n8n API (read-only) | Deterministic HTTP+JSON parsing; no model judgment needed to extract fields |
| Execution-ID correlation (which execution belongs to this POST) | Plugin Python script | n8n API (`GET /api/v1/executions?workflowId=`) | The webhook response carries no execution id (verified — no node references `$execution.id`); correlation is a client-side best-effort by time proximity, not a lookup by key |
| Report rendering (summary counts, failing-rows-in-full, run handle) | Claude skill (SKILL.md, prompt-level) | Plugin Python script (computes the counts/groupings) | Presentation/wording is conversational; the underlying counts must be deterministic |
| Retry dispatch (re-POST the failed-chunk batch) | Plugin Python script (`dispatch.py`, reused from Phase 23) | — | No new dispatch mechanism — retry is exactly another call to the same armed `dispatch()` function with a different payload |
| Retry **safety** (no duplicate create) | n8n (`Resolve Identity`, `HubSpot Search by Email`) | — | D-04's whole premise; confirmed real for the email path, confirmed a stable-non-duplicating-but-stuck case for the no-email path |
| ICP tier availability | **Nobody, currently** | n8n-side status endpoint (if extended) | Confirmed gap: no component in this system computes or reads back `lv_icp_tier` today |

## Standard Stack

No new external packages are introduced by this phase. Everything needed is already decided in
Phase 23's research and already in `operator-claude-plugin/requirements.txt`:

| Library | Version | Purpose in this phase | Why Standard |
|---------|---------|------------------------|--------------|
| `requests` | `>=2.32.0` | `GET /api/v1/executions` / `/api/v1/executions/{id}`, and the retry POST (reuses Phase 23's `dispatch()`) | Already the established HTTP client for this plugin (Phase 23 D-pattern) |
| stdlib `json`, `datetime` | n/a | Parsing execution payloads; comparing `startedAt` for correlation | No dataframe/parsing library is warranted for this — row-by-row dict work, same size class as Phase 23's file reading |

**Installation:** none — no `requirements.txt` change needed for this phase.

**Version verification:** not applicable; no new dependency decision was made.

## Package Legitimacy Audit

**Not applicable this phase.** No new external packages are installed. The n8n API client pattern
this phase's `report.py` follows is read directly from `scripts/deploy_n8n_workflows.py` /
`scripts/enrichment_cost_ledger.py` (same repo, same auth header, same base URL convention) —
reference for the calling convention only, per ROADMAP's standing note that the plugin must not
import from the repo.

## Architecture Patterns

### System Architecture Diagram

```text
Operator: "did that batch land?" / re-send after a failed chunk
  │
  ▼
Skill (SKILL.md) — conversation owner
  │
  ├─ 1. dispatch.py already returned from the original send: either
  │     (a) a parsed JSON body (sync response reached lastNode), or
  │     (b) a timeout/5xx/connection error (D-02's trigger condition)
  │
  ├─ 2. report.py: build the report
  │     │
  │     ├─ (a) sync body present?
  │     │     ├─ came from "Set Review" only, or is otherwise thin/ambiguous
  │     │     │   (per-item shape lacks contact_id/email/reason)? → treat as
  │     │     │   INSUFFICIENT, fall through to (b) rather than render it as-is
  │     │     └─ came from a real write node (HubSpot Update/Create) with full
  │     │         per-item HubSpot object data? → render directly, still offer
  │     │         re-check since lastNode only reflects ONE branch of a mixed batch
  │     │
  │     └─ (b) executions-API fallback (D-01/D-02):
  │           1. resolve workflowId once (GET /api/v1/workflows, match by name,
  │              cache — "LV Contact Ingest (Cloud template)" /
  │              "LV Enrichment (Cloud template)")
  │           2. GET /api/v1/executions?workflowId=<id>&limit=5
  │           3. pick the execution whose startedAt is the closest match
  │              at/after dispatch-sent-time (best-effort correlation —
  │              NO execution id is returned by the webhook itself, verified)
  │           4. GET /api/v1/executions/{id}?includeData=true
  │           5. read data.resultData.runData["Decide Action"] (contacts) or
  │              ["Decide Company Action"] (enrichment) — NOT the terminal
  │              write/review nodes — for the authoritative per-row ledger
  │           6. status "running"/"waiting"/"new" → REPORT-03: state clearly
  │              that the run is still in flight, print the run handle,
  │              explain manual re-check (D-06/D-07 — no poll loop)
  │
  ├─ 3. Render (D-08/D-09, same adaptive convention as Phase 23's preview):
  │     summary counts first (created/updated-matched/needs_review/rejected),
  │     then the failing/needs_review rows in full, complete detail on request
  │
  └─ 4. Operator asks to retry the failed CHUNK (Phase 25 D-13's object) →
        dispatch.py(armed=<operator just armed this turn>, batch=failed_chunk)
        — same function, same arming gate, no new code path (D-04/D-05/Specifics
        "a re-send is a send")
```

### Recommended Project Structure

Additive to Phase 23's tree — no restructuring:

```text
operator-claude-plugin/
  skills/
    contact-upload/
      scripts/
        dispatch.py          # existing (Phase 23) — reused verbatim for retry
        report.py            # NEW — sync-body sufficiency check, executions-API
                              #   fallback, run-handle correlation, outcome parsing
        executions_client.py # NEW — thin GET wrapper: list/get workflows+executions,
                              #   mirrors scripts/deploy_n8n_workflows.py's auth
                              #   convention (X-N8N-API-KEY), not imported from it
  tests/
    test_report_sufficiency.py   # is-the-sync-body-usable? decision logic
    test_executions_fallback.py  # correlation + Decide Action parsing (fixtures)
    test_retry_reuses_dispatch.py  # retry calls dispatch() with armed explicit
```

### Pattern 1: Read the decision node, not the write node

**What:** For `hubspot/contact-upload`, build the per-row ledger from
`data.resultData.runData["Decide Action"]`'s output items, not from `HubSpot Update` /
`HubSpot Create` / `Set Review`.
**When to use:** Any time the plan needs a *complete* row ledger, including reasons for
`needs_review`/`rejected` rows. `Decide Action` runs once for the whole batch
(`mode: "runOnceForAllItems"`) and every row survives in its output — it is the one point in the
pipeline where every row's outcome, contact_id, reason, and email are all still present in one
place, before any node conditionally drops or overwrites them.
**Example:**
```python
# report.py — sketch, reads an already-fetched execution payload
def contact_row_ledger(execution: dict) -> list[dict]:
    """Authoritative per-row outcome for hubspot/contact-upload, read from
    Decide Action — NOT the terminal write/review nodes, which (a) may not have
    run for a filtered-out row and (b) Set Review strips every field except
    `queue` (verified: n8n Edit-Fields default output-only-what-you-set)."""
    run_data = execution.get("data", {}).get("resultData", {}).get("runData", {})
    runs = run_data.get("Decide Action") or []
    if not runs or not isinstance(runs[0], dict):
        return []
    branch = runs[0].get("data", {}).get("main", [[]])[0]
    return [item["json"] for item in branch if isinstance(item, dict) and "json" in item]
    # each row: {action, outcome, contact_id, hs_object_id, reason, email, ...}
```

### Pattern 2: Reconcile whether a decided row actually wrote

**What:** `Decide Action`'s `action` field is the *intent* (update/create/review/skip), decided
before the write-safety gate. Whether the write actually happened requires cross-referencing the
corresponding terminal node's run — a row can be `action: "update"` in `Decide Action` and still
never reach `HubSpot Update` if the (currently baked-closed) write gate filtered it out.
**When to use:** Rendering "created"/"updated-matched" as a *confirmed* outcome, not just an
intended one — otherwise the report over-promises writes that were actually silently gated off
(exactly finding #2 above: `allow_create` is hardcoded `false` today, so no row can ever actually
reach `created`, and the report must not claim it did).
**Example:**
```python
def reconcile(decide_action_rows: list[dict], write_node_runs: dict) -> list[dict]:
    """write_node_runs: {"HubSpot Update": [...], "HubSpot Create": [...]} — each a
    runData entry (possibly empty/absent if the write gate filtered everything)."""
    update_ok = len(_node_output_items(write_node_runs.get("HubSpot Update", [{}])[0] or {})) if write_node_runs.get("HubSpot Update") else 0
    create_ok = len(_node_output_items(write_node_runs.get("HubSpot Create", [{}])[0] or {})) if write_node_runs.get("HubSpot Create") else 0
    out = []
    for row in decide_action_rows:
        outcome = row["action"]
        if outcome == "update" and update_ok == 0:
            outcome = "needs_review"  # decided but write-gated off — do not claim "updated"
        if outcome == "create" and create_ok == 0:
            outcome = "needs_review"
        out.append({**row, "reported_outcome": outcome})
    return out
```
This is intentionally conservative: when in doubt about whether a write actually landed, the report
must say "not confirmed written" rather than assert success — the same "unknown is never displayed
as zero/success" discipline the milestone already applies everywhere else (Phase 25 D-10).

### Pattern 3: Retry is the same `dispatch()` call, not a new function

**What:** `dispatch.py`'s existing signature (`dispatch(file_path/batch, armed: bool, config: dict)`
from Phase 23) is reused unmodified. Retry passes Phase 25's failed-chunk batch object as the
payload and requires the operator to arm *this* turn, exactly as an original send does.
**When to use:** Always, for this phase — do not build a `retry_dispatch()` variant.
**Why:** D-04/D-05's "the client does not reimplement" principle, applied to the dispatch path
itself, not just to identity/mapping logic. The Specifics section states it directly: "a re-send is
a send." The code seam is Phase 23's own `armed: bool` parameter, which already has no default —
it is a required, explicit argument on every call, retry included.

### Anti-Patterns to Avoid

- **Trusting `Set Review`'s own node output (or a sync response whose `lastNode` happens to be
  `Set Review`) as if it carried row identity.** Verified: it outputs only `{"queue":
  "needs_review"}`. A report built from this literally cannot tell two different rejected rows
  apart.
- **Reporting `created` as ever having happened via `hubspot/contact-upload` in its current
  deployed form**, since `allow_create` is unconditionally `false` in `Set Config`. If a live
  smoke test is run against the deployed workflow as-is, do not be surprised when every net-new
  row comes back `needs_review` — that is correct, current behavior, not a bug in the plugin.
- **Building client-side name+company deduplication "to fix" the no-email retry-stuck case.**
  D-04/Deferred Ideas explicitly reject a second dedupe authority. The correct response to finding
  #3 is to *report* that these rows are stuck in review, not to route around the backend's
  identity rule.
- **Polling `GET /api/v1/executions` in a loop from within this phase's code.** D-07 is explicit —
  the bounded watch is Phase 29. Phase 26's re-check is one-shot, operator-triggered.
- **Treating a chunk-level retry (Phase 25 D-13's object) as if it should also "retry" individual
  rejected/needs_review rows.** Those rows failed for a *business* reason (identity rule,
  ambiguous match) that a bare re-POST does not fix — re-sending them unchanged reproduces the same
  outcome. Chunk retry exists for **transport-level** failures (a chunk that never got a response
  at all, or 5xx'd) — see the Common Pitfalls section below for why conflating these two matters.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-row identity resolution / dedupe on retry | A client-side "already sent" ledger, or a second matching heuristic | n8n's existing `Resolve Identity` + `HubSpot Search by Email`, exercised again by simply re-POSTing | D-04/D-05 — this is the entire point of the locked decision; confirmed real for the email path by reading the actual code |
| Execution status/outcome semantics | A custom polling/retry loop against `/executions` | One-shot `GET`, rendered, with the run handle given back for a manual re-check | D-07 — the bounded watch is Phase 29's job, built once there |
| ICP scoring readback | Re-implementing `compute_icp_score` client-side from raw enriched fields the response *does* carry (org_type, produces_content, revenue_band, etc.) | Flag as unavailable this phase / route through an n8n-side status-endpoint extension | Recomputing the score client-side would fork the scoring engine a third time (Python MVP, n8n JS port, and now the plugin) — exactly the kind of duplicated source-of-truth this milestone's scope anchor forbids everywhere else |

**Key insight:** every "don't hand-roll" here is the same shape as Phase 23/25's: the temptation is
to patch around a backend gap with client-side logic (a dedupe ledger, a local scoring
recomputation) rather than either (a) reading what the backend *actually* already computes more
carefully (the `Decide Action` fix), or (b) naming the gap plainly when the backend genuinely
doesn't have the data (the ICP tier gap).

## Common Pitfalls

### Pitfall 1: Assuming `Set Review`'s wire output carries row identity
**What goes wrong:** A report built from `Set Review`'s own output (or a sync response that landed
there) shows N identical `{"queue": "needs_review"}` rows with no way to tell them apart, and no
reason to show the operator.
**Why it happens:** `Set Review` reads, at a glance, like it should carry the row through (it's
positioned as if it's just "tagging" the row for review). n8n's Set/Edit-Fields node's default
behavior — keep only the fields you explicitly assign, drop everything else — is a well-documented
but easy-to-miss default.
**How to avoid:** Build the ledger from `Decide Action`'s own output (Pattern 1 above), which runs
upstream of `Set Review` and still has every field.
**Warning signs:** A rendered report where every `needs_review` row looks byte-identical.

### Pitfall 2: Reporting "created" when `Set Config` has already ruled it out
**What goes wrong:** The plan (or a live smoke test) assumes a net-new row can come back `created`
via `hubspot/contact-upload`. It cannot, in the currently deployed workflow — `Set Config`
hardcodes `allow_create: false`, so `action` is forced to `"review"` for every `net_new` outcome,
independent of the write-safety gate.
**Why it happens:** `CLAUDE.md`'s own architecture doc (§9-§10) and the Phase 26 requirements both
describe a `created` outcome as a normal, expected bucket — nothing in the requirements docs flags
that the deployed Cloud workflow currently forecloses it entirely.
**How to avoid:** Verify directly (`grep allow_create n8n/wf_contact_ingest_cloud.json`, already
done here) before designing around an assumption. Surface this to the user as an explicit,
named limitation (see Open Questions) rather than silently building a report bucket the backend
cannot fill.
**Warning signs:** A smoke test where every net-new test row comes back `needs_review` regardless
of arming state.

### Pitfall 3: Conflating "decided" with "written"
**What goes wrong:** Reporting a row as `updated`/`created` because `Decide Action`/`Decide Company
Action` computed that intent, without checking whether the downstream write-safety gate actually
let it through (it may have filtered the row to zero items, silently).
**Why it happens:** `action: "update"` reads as a completed fact rather than a routing decision.
**How to avoid:** Pattern 2 above — cross-reference the terminal write node's own run in the
executions payload; if it has zero output items for what should have been a written row, downgrade
the reported outcome rather than asserting success.
**Warning signs:** Reported "success" counts that don't match what actually changed in HubSpot when
spot-checked.

### Pitfall 4: Retrying rejected/needs_review rows expecting a different outcome
**What goes wrong:** Building "retry" as "re-POST every row the operator sees as not-yet-landed,"
including rows that came back `rejected` (failed the identity rule) or `needs_review` (ambiguous
match, or the no-email-forever case from finding #3). Re-sending these unchanged reproduces the
identical outcome — it is not what Phase 25's D-13 failed-chunk object represents.
**Why it happens:** DISPATCH-04's wording ("names the specific rows that did not land... safe to
retry") can read as "any row not fully accepted," when Phase 25's actual failed-chunk object is
scoped to **transport-level** chunk failures (timeout, 5xx, connection error on the whole chunk),
not business-outcome rows within a chunk that *did* get a response.
**How to avoid:** Keep the two concepts separate in the plan: chunk-level retry (DISPATCH-04,
Phase 25's object, transport failures) vs. row-level reporting (REPORT-01, informational, may
require the operator to correct data and build a *new* batch — out of this phase's scope to
automate).
**Warning signs:** A "retry" button offered on rows whose `reason` is a business-logic message
("no email, insufficient identity") rather than an HTTP failure.

### Pitfall 5: Assuming the webhook response carries an execution id
**What goes wrong:** Designing D-06's "run handle" around a field the response doesn't have.
**Why it happens:** It's a very natural assumption — n8n *can* expose `$execution.id` to a node,
so it's easy to assume a workflow surfaces it in its own response.
**How to avoid:** Confirmed by direct inspection: neither cloud workflow JSON references
`$execution.id`/`executionId` anywhere. The run handle must be built by the client from
time-proximity correlation against `GET /api/v1/executions?workflowId=<id>` (see Architecture
Patterns diagram), not read out of the dispatch response.
**Warning signs:** Code that tries to read `response.json()["execution_id"]` or similar — that key
does not exist in either workflow's response shape today.

## Code Examples

### Deciding whether the sync response is even usable (D-01's "first" leg)
```python
# Source: derived from the verified node shapes above — not a literal n8n API contract,
# a heuristic this plugin applies to whatever body dispatch.py already received.
def sync_response_is_sufficient(body) -> bool:
    """A usable per-row body has row-identifying fields (contact_id/hs_object_id/email)
    on at least one item, OR is unambiguously a full HubSpot object response (has 'id'
    and 'properties' at the top level, per-item). A response whose items are all
    `{"queue": "needs_review"}` and nothing else is NOT sufficient — fall through to the
    executions-API path."""
    items = body if isinstance(body, list) else [body]
    if not items:
        return False
    for item in items:
        if not isinstance(item, dict):
            return False
        has_identity = any(k in item for k in ("contact_id", "hs_object_id", "email"))
        has_hubspot_object = "id" in item and "properties" in item
        if not (has_identity or has_hubspot_object):
            return False
    return True
```

### Correlating a POST to its execution (no execution id is ever returned — verified)
```python
# Source: pattern already proven in scripts/deploy_n8n_workflows.py (_n8n_headers,
# _base_url) and scripts/enrichment_cost_ledger.py (_list_executions/_get_execution) —
# not imported, reimplemented per the plugin's own-dependency rule.
import requests
from datetime import datetime, timezone

def find_execution_for_dispatch(n8n_url: str, api_key: str, workflow_name: str,
                                  dispatched_at: datetime) -> dict | None:
    headers = {"X-N8N-API-KEY": api_key}
    workflows = requests.get(f"{n8n_url}/api/v1/workflows", headers=headers, timeout=30).json()["data"]
    wf = next((w for w in workflows if w["name"] == workflow_name), None)
    if not wf:
        return None
    execs = requests.get(
        f"{n8n_url}/api/v1/executions",
        params={"workflowId": wf["id"], "limit": 5},
        headers=headers, timeout=30,
    ).json()["data"]
    # Best-effort: nearest startedAt at/after dispatch time, small clock-skew tolerance.
    candidates = [e for e in execs if _started_after(e, dispatched_at, tolerance_s=5)]
    return min(candidates, key=lambda e: e["startedAt"]) if candidates else None

def _started_after(execution: dict, dispatched_at: datetime, tolerance_s: int) -> bool:
    started = datetime.fromisoformat(execution["startedAt"].replace("Z", "+00:00"))
    return (started - dispatched_at).total_seconds() >= -tolerance_s
```

### Reading the enrichment response's `remaining_credits` (confirmed real, D-10)
```python
# Source: n8n/wf_enrichment_cloud.json "Build Response" node — verified: every item
# gets `remaining_credits: [{"provider": "lusha", "credits": <int|null>}, ...]` appended.
def remaining_credits_from_response(item: dict) -> list[dict]:
    return item.get("remaining_credits", [])  # [] if the field truly is absent (older run)

def icp_tier_from_response(item: dict) -> str:
    # VERIFIED GAP: this pipeline never computes/writes lv_icp_tier. Do not fabricate one.
    return "not available — this system does not compute ICP tier (see Phase 26 RESEARCH.md)"
```

### Reconciling `needs_review` across the "wrote" vs "blocked" cases (enrichment)
```python
# Source: derived from Decide Company Action's output shape + HubSpot's v3 PATCH/POST
# response echoing back the properties it was sent (ASSUMED — HubSpot's documented
# behavior, not re-verified live in this session; flag for a Wave 0 smoke check).
def needs_review_flag(item: dict) -> bool | None:
    if "needs_review" in item:               # write_blocked/skip path — field survives
        return item["needs_review"]
    props = item.get("properties")           # written path — item.json is now the raw
    if isinstance(props, dict) and "lv_enrichment_needs_review" in props:
        return str(props["lv_enrichment_needs_review"]).lower() == "true"
    return None  # genuinely unknown — never render as False
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Treat the sync webhook response as a complete per-row ledger (Phase 23's stated limitation) | Treat `GET /api/v1/executions/{id}?includeData=true` reading `Decide Action`'s node output as the authoritative ledger | This research, 2026-07-30 | The plan should budget for the fallback path as the normal case, not a rare degraded one — confirmed by reading the actual deployed `Set Review` and `Set Config` behavior |

**Deprecated/outdated:** none — this phase's "state of the art" question is really "what does the
already-deployed backend do," not an external library/tooling shift.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | HubSpot's v3 PATCH/POST response echoes back the `properties` included in the request body (used to recover `lv_enrichment_needs_review` after an `httpRequest` node overwrites `item.json` with the raw API response) | Code Examples, Pattern 2 | If wrong, the needs_review flag is unrecoverable for rows that actually wrote, and the report must fall back to "unknown" for those rows rather than guessing false |
| A2 | n8n's HTTP Request node (`HubSpot Update`/`HubSpot Create`/`HubSpot Company Update`/`HubSpot Company Create`), with the options shown in the deployed JSON (no "Full Response"/merge option set), replaces `item.json` with the raw response body rather than merging it with the input — this is standard, well-documented n8n behavior but was not re-verified with a live execution in this session | Architecture Patterns, Pattern 2; Code Examples | If wrong (i.e., the node actually preserves input fields), Pattern 2's reconciliation logic is unnecessary and the simpler direct read would work — low risk either way since Pattern 2 degrades gracefully (falls back to "unknown" rather than crashing) |
| A3 | `GET /api/v1/executions` (list, no `includeData`) returns executions newest-first by default, and its `startedAt` field is reliable for time-proximity correlation | Code Examples, execution correlation | If ordering/field assumptions are wrong, the client-side `min()`-by-`startedAt` approach still works (it doesn't depend on list order), but should be smoke-tested once live rather than trusted from docs alone |
| A4 | The current n8n Cloud plan for this project retains execution data long enough (days, not hours) for the executions-API fallback to be useful for a same-session re-check | Priority Question 2 / Timeout behavior | If the plan is a low tier with very short retention, D-03's fallback could itself go stale within the same working session — worth a one-line confirmation with the admin, not a blocking assumption |
| A5 | Phase 25's failed-chunk batch object (D-13) is scoped to **transport-level** chunk failures, not business-outcome rows within an accepted chunk — inferred from D-12's "a failing chunk is skipped" framing, since Phase 25 has not yet been planned/built (no code exists to confirm the exact object shape) | Common Pitfalls #4, Architecture Patterns Pattern 3 | If Phase 25 ends up defining the failed-chunk object more broadly (e.g., including rejected rows), Phase 26's retry logic needs to special-case those rows rather than blindly re-POSTing them — worth confirming at Phase 25's actual completion, before or during Phase 26 planning |

## Open Questions

1. **`hubspot/contact-upload` cannot produce a `created` outcome in its currently deployed form —
   should this milestone treat that as pre-existing/out of scope, or as a defect worth a backend
   fix?**
   - What we know: `Set Config`'s `allow_create: false` is hardcoded, not one of the four
     deploy-time-overlayable flags. This is verified by direct inspection, not inferred.
   - What's unclear: whether this was a deliberate MVP safety choice (matching the milestone's
     "disarmed by default" posture generally) that the user already knows about, or an oversight
     nobody has revisited since it was written.
   - Recommendation: name this to the user explicitly during planning. If it's deliberate, the
     Phase 26 plan should say plainly in the report design that `created` is not currently
     reachable and describe what an operator sees instead (a `needs_review` row for what would
     have been a new contact). If it's not deliberate, fixing it is a `Set Config` edit — a
     backend file — which is outside this phase's stated scope (client-only, `n8n/` off-limits
     except the status endpoint) and would need to be an explicitly accepted amendment, the same
     way Phase 23 D-05 and Phase 25 D-05 each amended a locked requirement with the user's
     awareness.

2. **`lv_icp_tier`/`lv_icp_fit_score` are never computed anywhere in this system — REPORT-02 as
   literally worded expects them in the enrichment report. How should this phase close that gap?**
   - What we know: `src/merge_policy.py`'s own comment says HubSpot owns the derived ICP outputs
     by design ("Approach C"); no node in the deployed enrichment workflow reads them back after a
     write; the plugin holds no HubSpot credential to read them directly (credential boundary).
   - What's unclear: whether "HubSpot owns it" means an existing HubSpot-native workflow/calculated
     property already computes `lv_icp_tier` today (in which case a *read-back* step is all that's
     missing — cheap, additive, and n8n already holds the needed HubSpot credential), or whether
     nothing computes it yet at all (in which case this phase genuinely cannot satisfy REPORT-02's
     ICP-tier clause without a larger backend addition, likely coordinated with Phase 27's status
     endpoint).
   - Recommendation: confirm with the user/admin whether HubSpot-side ICP-tier automation already
     exists before planning. If yes: plan a small, additive read-back node in the enrichment
     workflow (a `HubSpot Fetch By Id` reading `lv_icp_tier`/`lv_icp_fit_score`/
     `lv_icp_needs_review` right before `Build Response`) — this is a genuine, narrow backend touch
     that should be named and agreed the same way Phase 25's status-endpoint touch was. If no:
     report the gap plainly to the operator ("ICP tier not yet available — see admin") rather than
     silently omitting it or fabricating a value, consistent with the milestone's "unknown is never
     displayed as zero/healthy" discipline (Phase 25 D-10, carried forward).

3. **What is the actual node-execution order for a mixed-outcome batch under `responseMode:
   lastNode` (contact-upload)?**
   - What we know: three disjoint terminal branches exist (`HubSpot Update`, `HubSpot Create`,
     `Set Review`), with no merge node. `lastNode` picks whichever node's output happens to run
     last in that specific execution.
   - What's unclear: the exact tie-break order n8n's engine uses when multiple branches have
     items in the same run — this determines which single branch "wins" the sync response for a
     batch that has, say, both matched and ambiguous rows.
   - Recommendation: don't invest in reverse-engineering n8n's scheduler from docs. The primary
     recommendation already routes around this (always fall through to the executions API for
     anything but a trivially uniform batch) — this question only matters if someone later wants
     the sync-response fast path to be more ambitious than "small and uniform." A single live test
     with a batch containing one of each outcome would resolve it cheaply if ever needed.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| n8n Cloud reachability, `X-N8N-API-KEY` | `GET /api/v1/executions`, `/api/v1/workflows` | ✓ — the plugin already holds this per REQUIREMENTS.md's endpoint table and Phase 25's cost-guard design | n/a | None needed — this is the one live capability the whole phase depends on |
| n8n Cloud execution-data retention | Executions-API fallback usefulness within a session | Unconfirmed — varies by n8n Cloud plan tier (Starter: 7 days/2,500 executions; Pro/Power: 30 days/25,000; Enterprise: unlimited) [CITED, community-sourced, not confirmed against this project's actual plan] | n/a | If retention is very short, the fallback is still usable for same-session re-checks (which is all D-06/D-07 ask for); only matters for a next-day re-check, which is arguably Phase 29 territory anyway |
| Backend read-back for ICP tier | REPORT-02 | ✗ — confirmed absent, see Open Question 2 | n/a | Report the field as unavailable; do not fabricate |
| `created` outcome reachability (contact-upload) | REPORT-01 | ✗ in the currently deployed workflow — see Open Question 1 | n/a | Report accordingly; do not claim a row was created when the backend cannot currently produce that outcome |

**Missing dependencies with no fallback:** none block starting implementation. Both Open Questions
1 and 2 are backend-behavior gaps this research surfaced, not missing tools — they need a
conversation with the user before planning locks in report wording, not a code workaround.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest, same as Phase 23 (`.venv/bin/python -m pytest`) |
| Config file | none (repo default discovery, unchanged from Phase 23's finding) |
| Quick run command | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` |
| Full suite command | `.venv/bin/python -m pytest operator-claude-plugin/tests/ tests/test_architecture_guard.py -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REPORT-01 | `Decide Action` row ledger correctly built from a fixture execution payload; `Set Review`-only rows correctly flagged insufficient | unit (fixture-driven, offline) | `pytest operator-claude-plugin/tests/test_report_sufficiency.py -x` | ❌ Wave 0 |
| REPORT-01 | Reconciliation downgrades `update`/`create` to `needs_review` when the corresponding write node has zero output items | unit | `pytest operator-claude-plugin/tests/test_executions_fallback.py::test_reconcile_write_blocked -x` | ❌ Wave 0 |
| REPORT-02 | `remaining_credits` parsed correctly; ICP tier explicitly reported as unavailable, never fabricated | unit | `pytest operator-claude-plugin/tests/test_report_sufficiency.py::test_enrichment_credits -x` | ❌ Wave 0 |
| REPORT-03 | Execution `status: running/waiting/new` renders as in-flight with a run handle, never as finished | unit | `pytest operator-claude-plugin/tests/test_executions_fallback.py::test_in_flight_never_finished -x` | ❌ Wave 0 |
| DISPATCH-04 | Retry calls `dispatch()` with the failed-chunk batch and an explicit `armed` argument — no default, no new function | unit | `pytest operator-claude-plugin/tests/test_retry_reuses_dispatch.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q`
- **Per wave merge:** full suite command above
- **Phase gate:** full suite green, plus one live smoke test against a real (or disposable test-id)
  batch to confirm (a) the executions-API correlation actually finds the right execution and (b)
  Assumption A1/A2 (HubSpot response echo, httpRequest overwrite behavior) hold as expected —
  before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `operator-claude-plugin/tests/test_report_sufficiency.py` — covers REPORT-01, REPORT-02
- [ ] `operator-claude-plugin/tests/test_executions_fallback.py` — covers REPORT-01, REPORT-03
- [ ] `operator-claude-plugin/tests/test_retry_reuses_dispatch.py` — covers DISPATCH-04
- [ ] Fixture: a redacted sample execution payload shaped like `data.resultData.runData` with
  `Decide Action`, `HubSpot Update`, `HubSpot Create`, `Set Review` entries (mirrors the pattern
  `scripts/enrichment_cost_ledger.py`'s `build_redacted_fixture` already uses for the same kind of
  payload) — needed before the fallback-parsing tests can run offline
- [ ] Framework install: none — pytest already a root dependency

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Reuses the existing `X-N8N-API-KEY` (already held per REQUIREMENTS.md's endpoint table) and `X-Enrichment-Secret` — no new credential introduced |
| V5 Input Validation | yes | Execution payloads from the n8n API are external input to the plugin's parser; `report.py`'s functions above are written defensively (never raise on shape mismatch, mirroring `enrichment_cost_ledger.py`'s own `_node_output_items`/`extract_token_usage` pattern) |
| V6 Cryptography | n/a | No cryptographic operations in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Over-reporting success (claiming `created`/`updated` when the write was actually gated off) | Repudiation / false assurance | Pattern 2's reconciliation step — never assert a write outcome without confirming the corresponding write node actually produced output |
| Leaking full execution payloads (which may contain contact PII: email, phone, name) into chat/Artifact without the operator's adaptive-display gating | Information Disclosure | Reuse Phase 23 D-08/D-09's adaptive convention — summary counts by default, full per-row detail only shown for the actionable (failing) subset or on explicit request, same as the preview |
| Treating an in-flight run (`status: running`) as finished because *some* rows already show outcomes | Tampering with operator trust | REPORT-03/D-03 — explicit "still in flight" framing whenever execution status is not `success`/`error`/`crashed`/`canceled` |

## Sources

### Primary (HIGH confidence)
- `n8n/wf_contact_ingest_cloud.json` — read directly; every node listed in this document (`Webhook
  Trigger`, `Set Config`, `Map Columns`, `Resolve Identity`, `Decide Action`, `IF Update`,
  `IF Create`, `HubSpot Update Write Gate`, `HubSpot Create Write Gate`, `HubSpot Update`,
  `HubSpot Create`, `Set Review`) — parameters, connections, and jsCode inspected verbatim
- `n8n/wf_enrichment_cloud.json` — read directly; `Webhook Trigger` (`responseNode` mode),
  `Decide Action`/`Decide Company Action` (write-safety gating via `action = "write_blocked"`),
  `Build Response`/`Respond to Webhook`, `Credit Request`/`Lusha Usage`/`Apollo Usage`/`ZoomInfo
  Usage` credit nodes, and the full connection graph into `Build Response`
- `scripts/deploy_n8n_workflows.py` — read directly; `_OVERLAY_FLAG_SPEC`, `_requested_overlay_flags`
  confirm `allow_create`/`Set Config`'s hardcoded literal is NOT one of the overlayable flags
- `scripts/enrichment_cost_ledger.py` — read directly; confirmed the `includeData=true` requirement,
  the `data.resultData.runData` nesting, and the defensive-parsing pattern this phase's code
  reuses
- `src/merge_policy.py` (lines ~330-365) — read directly; the "Approach C" comment confirming
  ICP-tier writes were deliberately removed from the canonical write path
- `CLAUDE.md`, `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md`, `ROADMAP.md`,
  `26-CONTEXT.md`, `25-CONTEXT.md`, `23-RESEARCH.md` — read directly, per the task's required
  reading list

### Secondary (MEDIUM confidence)
- `docs.n8n.io/connect/n8n-api/execution/` (WebFetch) — exact query-parameter list for
  `GET /executions` and `GET /executions/{id}` (`includeData`, `status` enum values, `workflowId`,
  `limit`, `cursor`)
- WebSearch, "n8n webhook node response timeout n8n Cloud" — n8n Cloud's webhook response is capped
  at 100 seconds by a Cloudflare-enforced timeout (524 on breach); this is the concrete trigger
  threshold to design the client's own (shorter) timeout around
- WebSearch, "n8n execution data pruning retention" — n8n Cloud retention varies by plan tier
  (Starter 7 days/2,500 executions; Pro/Power 30 days/25,000; Enterprise unlimited) — not confirmed
  against this project's actual subscription tier (flagged as Assumption A4)

### Tertiary (LOW confidence)
- n8n's HTTP Request node default output-merge behavior (Assumption A2) — based on general,
  well-documented n8n behavior from training knowledge, not re-verified with a live execution in
  this session
- HubSpot v3 PATCH/POST response echoing back requested `properties` (Assumption A1) — standard,
  documented HubSpot API behavior from training knowledge, not re-curled in this session

## Metadata

**Confidence breakdown:**
- What the backend currently does (node shapes, gating logic, response contracts): HIGH — every
  claim traced to an exact node's `parameters`/`jsCode` in the deployed JSON, not inferred from
  `CLAUDE.md`'s description of the intended design
- n8n Cloud runtime specifics not observable from static JSON (execution ordering under
  `lastNode`, HTTP Request node's exact merge behavior, execution-data retention on this project's
  actual plan): MEDIUM/LOW — each flagged with a cheap live-verification recommendation rather
  than presented as settled
- Retry safety conclusion (D-04): HIGH for the email path (traced through
  `resolveIdentity`/`HubSpot Search by Email` line by line), HIGH for the no-email-stuck-in-review
  finding (same code, same trace) — this is a confirmed backend behavior, not a guess

**Research date:** 2026-07-30
**Valid until:** ~30 days for the backend-contract findings (stable unless either cloud workflow is
redeployed with different node logic — a redeploy of `Set Config`, `Set Review`, or the write-safety
gates would invalidate the specific findings here); the n8n Cloud platform facts (timeout, execution
retention) should be treated as ~90-day-stable per typical platform-doc cadence, but the retention
tier is genuinely project-specific and worth a one-line confirmation rather than a research
re-run.
