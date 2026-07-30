# Phase 26: Outcome Reporting & Safe Retry - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 26 turns a dispatch result into something an operator can act on: a **per-record outcome**
instead of a bare HTTP status, and a **failed subset that is safe to re-send**.

It consumes what Phase 25 produces — specifically the failed-chunk batch (Phase 25 D-13), which
arrives already shaped as a re-sendable unit rather than as a list of errors.

Not in scope: the unprompted in-session watch that reports back when a run settles (Phase 29 /
NOTICE-01) and the scheduled sweep (NOTICE-03). Phase 26's re-check is operator-initiated.

</domain>

<decisions>
## Implementation Decisions

### Outcome source
- **D-01:** Outcomes are read **from the synchronous webhook response first**, falling back to
  `GET /api/v1/executions` with the n8n API key the plugin already holds when the POST times out or
  returns partial. Both paths feed one report renderer.
- **D-02:** The fallback is what makes success criterion 3 achievable. Without it, a batch that
  outruns the webhook timeout has no route to its own outcome and fails opaquely — which is
  precisely the in-flight case the criterion names.
- **D-03:** A report built from the fallback path must state that it came from the executions API
  and that the run may still be progressing. It never presents an incomplete run as finished.

### Retry safety
- **D-04:** Duplicate-safety on retry is **guaranteed by the backend's existing identity
  resolution**, not by client-side bookkeeping. n8n runs identity resolution and update-vs-create
  routing on every row, so a re-sent row that the earlier attempt already accepted is **updated in
  place rather than duplicated**. The client simply re-sends the failed batch.
  — **Reversibility:** reversible — client-side exclusion could be layered on later if the backend
  guarantee ever proves insufficient, but adding it now would create a second dedupe authority
  that can drift from n8n's.
- **D-05:** This is the same scope-anchor discipline the whole milestone follows: the client does
  not reimplement identity, mapping, normalization, or dedupe. Retry safety is a backend property
  the client relies on and states plainly to the operator.

### Re-check
- **D-06:** The report prints a **run handle** (an execution reference) and the operator asks to
  re-check it conversationally. Re-check is **manual in this phase**.
- **D-07:** The unprompted bounded watch is deliberately left to Phase 29 (NOTICE-01/NOTICE-02) so
  it is built once. Phase 26 must not grow a poll loop.

### Report presentation
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

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase decisions (locked)
- `.planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-CONTEXT.md` —
  D-11/D-12/D-13 define the failed-chunk batch this phase consumes. Also D-10: unknown is never
  displayed as zero.
- `.planning/workstreams/plugin-entrypoint/phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-CONTEXT.md`
  — D-08/D-09 set the adaptive-display and chat-first-with-Artifact conventions D-08/D-09 here
  inherit.

### Research already completed (read before planning)
- `.planning/workstreams/plugin-entrypoint/phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-RESEARCH.md`
  — pins the backend contract: the shared `X-Enrichment-Secret` auth header, the `data` multipart
  field name, and the client-side XLSX→CSV conversion requirement. The response shape this phase
  parses comes from the same workflow.
- `.planning/workstreams/plugin-entrypoint/phases/24-non-tabular-input-adapters/24-RESEARCH.md`
  — the canonical 7-prop set and the `Map Columns` `requiredIdentity()` trim-then-presence rule.

### Milestone scope and requirements
- `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` — REPORT-01/02/03 and DISPATCH-04.
  §"Endpoints (targets)" confirms the plugin holds an n8n API key, which is what makes D-01's
  executions-API fallback possible without a new credential.
- `.planning/workstreams/plugin-entrypoint/ROADMAP.md` §"Phase 26" — goal and four success criteria.

### Backend contract
- `n8n/wf_contact_ingest_cloud.json` — nodes `Decide Action`, `IF Update` / `HubSpot Update`,
  `IF Create` / `HubSpot Create`, `queue`, `Set Review`. These produce the per-record outcomes this
  phase renders, and `Resolve Identity` / `Merge Contacts` are the update-vs-create routing that
  D-04 relies on for retry safety.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- The n8n API client pattern in `scripts/deploy_n8n_workflows.py` — same base URL and
  `X-N8N-API-KEY` auth the executions-API fallback needs. Reference for the calling convention, not
  an import (the plugin must not import from the repo).
- Phase 25's failed-chunk batch — already a well-formed batch object, so retry is a re-dispatch
  rather than a reconstruction.

### Established Patterns
- **The backend owns identity.** D-04 is this pattern applied to retry.
- **Unknown is not zero.** Inherited from Phase 25 D-10 and applied here to in-flight and partial
  results: a run whose outcome is not yet known reads as not-yet-known, never as success.
- **Adaptive display.** Summary-first with actionable detail surfaced, from Phase 23 D-08.

### Integration Points
- Reads: the synchronous webhook response, and `GET /api/v1/executions` as fallback.
- Writes: re-dispatch of the failed batch through Phase 23's existing armed dispatch path — the
  arming gate still applies to a retry.
- No new endpoint is built in this phase.

</code_context>

<specifics>
## Specific Ideas

- The failing rows are the point of the report. Counts orient the operator; the failures are what
  they actually do something about, which is why D-08 shows those in full while summarizing the
  rest.
- Retry inherits the arming gate. A re-send is a send.

</specifics>

<deferred>
## Deferred Ideas

- **Unprompted in-session watch until a run settles** — Phase 29 / NOTICE-01, NOTICE-02. D-07
  explicitly keeps the poll loop out of this phase.
- **Client-side accepted-row tracking** — rejected as a second dedupe authority (D-04). Revisit
  only if the backend guarantee proves insufficient in practice.
- **Scheduled sweep reporting** — Phase 29 / NOTICE-03.
- **Full backend health context in reports** — Phase 27 / STATUS-01..06.

</deferred>

---

*Phase: 26-outcome-reporting-safe-retry*
*Context gathered: 2026-07-30*
