# Phase 29: Notices & Unattended Sweep - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 29 makes the backend speak up. Two mechanisms, one purpose — the operator learns something
needs them without having to think to ask:

1. **In-session watch** — after a dispatch, keep watching until the run settles and report back
   unprompted with per-record outcomes and the cost actually incurred.
2. **Unattended sweep** — with no session open, notice when something needs a human and push a
   notification.

The sweep is **read-only by construction**: it burns no provider credits, enables no writes, and
dispatches nothing. That is a structural property of what it is allowed to call, not a policy it
promises to follow.

Not in scope: acting on what the sweep finds. Notices point at controls Phase 28 already exposes.

</domain>

<decisions>
## Implementation Decisions

### Sweep host
- **D-01:** The unattended sweep is a **Claude scheduled routine that reuses the plugin's existing
  read paths** — Phase 27's status surface on a cadence, pushing a notification when something
  needs a human.
- **D-02:** This makes **NOTICE-05 structural rather than promised**: the sweep calls only read
  endpoints, so it *cannot* burn credits, enable writes, or dispatch. The plan must keep it that
  way — the sweep must have no code path to a mutation or a dispatch, not merely avoid calling one.
- **D-03:** The notice lands **where the operator already is**, rather than in a separate channel
  they would have to watch. — **Reversibility:** costly — moving to an n8n-side or cron-hosted
  sweep later means rebuilding both the scheduling and the delivery path.
- **D-04:** **Dependency the plan must verify early:** this assumes scheduled Claude agents are
  available on the operator's account. If they are not, the sweep has no host and the phase needs
  a different mechanism — verify before building, do not discover mid-implementation.

### In-session watch bound
- **D-05:** The watch bound is an **admin-config value with a sane default**. The default is tuned
  to observed run times; an admin can raise it for a slow backend.
- **D-06:** The bound must be **empirical, not guessed**. Enrichment runs the full provider + Haiku
  + Sonnet chain per record, and 25-RESEARCH.md established that **no batch-timing data exists in
  this repo yet**. Deriving the default therefore needs a measurement task, shared with Phase 25's
  chunk-size measurement (25-CONTEXT D-11a) rather than duplicated.
- **D-07:** At the bound the run is reported as **still running, with how to re-check** — reusing
  Phase 26's run handle (26-CONTEXT D-06). The watch **never simply goes quiet** (NOTICE-02).

### What the sweep reports
- **D-08:** The sweep is **silent when the backend is healthy** (NOTICE-04). Only these conditions
  produce a notice: a failed scheduled run, a credential or auth failure, an exhausted quota, a
  stuck lock, or a review backlog past its configured threshold.
- **D-09:** Every notice states **whether the operator or an admin can act on it** (NOTICE-04),
  using the same attribution discipline as Phase 27 D-04/D-05 — including its guardrail that an
  unrecognized cause defaults to admin attribution rather than telling the operator they can fix
  something the table does not recognize.
- **D-10:** A **stuck-armed backend** is one of the conditions the sweep watches for. Phase 28 D-03
  names this sweep as the backstop for the crash window between arm and disarm.

### Corrections and confirmations from 29-RESEARCH.md
- **D-01a (D-04's availability risk is CLOSED for this machine):** Scheduled Claude routines are
  real and enabled here — `claude_desktop_config.json` carries `coworkScheduledTasksEnabled: true`
  and `ccdScheduledTasksEnabled: true`, and a working example already runs at
  `~/Documents/Claude/Scheduled/weekday-morning-brief/SKILL.md`, firing on a cadence and driving
  real MCP tool calls. **Still unverified:** whether a scheduled routine can invoke *this plugin's
  own* skill rather than a generic connector. That is the plan's **first task**, not an assumption.
- **D-01b:** Anthropic's lower-level scheduled mechanism (Managed Agents `deployments`, cron +
  webhook delivery) is **not** the right fit — its notification path needs a developer-operated
  webhook receiver, which contradicts the milestone's "operator never runs infrastructure" rule.
  Retained only as D-04's named fallback.
- **D-05a (NOTICE-01 is this phase's highest-risk claim):** Research observed the unprompted
  background-notification behaviour NOTICE-01 describes working in the **CLI** runtime, but could
  **not** confirm it in Claude Desktop — which is the actual target (Phase 23 D-14a). Therefore:
  build **D-07's bounded "still running, here's how to re-check" path as the real NOTICE-01/02
  mechanism**, and treat true unprompted mid-conversation follow-up as a **bonus if verified, never
  a dependency**. A phase that depends on an unconfirmed platform primitive fails silently.
- **D-06a (the watch bound is computable from data already fetched):** `/api/v1/executions` returns
  both `startedAt` and `stoppedAt`. `scripts/enrichment_cost_ledger.py` already reads that list but
  never computes a duration. No new endpoint is needed — just the computation, shared with Phase 25
  D-11a's chunk-sizing measurement.
- **D-08a (the five conditions are unevenly detectable):** stuck-lock, review-backlog, and partially
  failed-scheduled-run reuse Phase 27's read surface unmodified. **Credential-failure and
  exhausted-quota need new threshold/classification logic** over Phase 27's existing credit-probe
  data — new logic, not new reads.
- **D-08b (new instance of a known bug pattern):** `wf_scheduled_maintenance_cloud.json`'s own
  HubSpot-Search nodes are `onError: continueRegularOutput`, so **the maintenance job silently
  swallows the same failure class** Phase 27 found in the enrichment workflow (27-CONTEXT D-04a).
  The sweep must not treat "the maintenance job reported success" as evidence of health.
- **D-02a (NOTICE-05 becomes enforceable rather than promised):** implement the sweep as a
  dedicated module plus an **AST / import-graph test asserting zero reachable mutation calls** —
  mirroring `scripts/enrichment_cost_ledger.py`'s no-write guarantee, but enforced by CI instead of
  a comment. This is the concrete mechanism D-02 asked for.

### Claude's Discretion
- Sweep cadence default and whether it is admin-configurable.
- Notification wording and grouping when several conditions fire at once.
- Review-backlog threshold default.
- Backoff schedule within the in-session watch.
- Whether the watch reports incrementally as chunks settle or only once at the end.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase decisions (locked)
- `.planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-CONTEXT.md` — the
  read surface the sweep runs on. D-08 (unknown is never zero) and D-04/D-05 (error translation and
  its guardrail) both apply directly to notice text.
- `.planning/workstreams/plugin-entrypoint/phases/28-control-actions/28-CONTEXT.md` — D-03 names
  this sweep as the backstop for the arm/disarm crash window. Notices point at the controls Phase
  28 exposes.
- `.planning/workstreams/plugin-entrypoint/phases/26-outcome-reporting-safe-retry/26-CONTEXT.md` —
  D-06's run handle is what "how to re-check" refers to. D-07 there deliberately deferred the poll
  loop to this phase, so the watch is built here **once**.
- `.planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-CONTEXT.md` —
  D-11a's missing batch-timing data is the same gap D-06 here depends on; measure once, use twice.

### Research already completed
- `.planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-RESEARCH.md` —
  the ~100s n8n Cloud webhook response ceiling and the absence of a `Split In Batches` node, which
  together determine how long a run realistically takes and therefore what the watch bound must be.
- `.planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-RESEARCH.md` — the
  stuck-lock / queued / review-backlog filter definitions the sweep re-uses verbatim.

### Milestone scope and requirements
- `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` — NOTICE-01..05. §"Future Requirements"
  is binding here: **unattended *ingestion* is explicitly deferred** — the sweep watches and
  reports but never dispatches a batch on its own. Sending stays operator-initiated by design.
- `.planning/workstreams/plugin-entrypoint/ROADMAP.md` §"Phase 29" — goal and five success criteria.

### Repo conventions
- `CLAUDE.md` §19 — the existing scheduled-job semantics (stuck-lock cleanup, needs-review queue,
  stale refresh). The sweep reports on these; it does not replace them.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 27's entire read surface — the sweep is that surface on a timer plus a notification.
- Phase 26's run handle and outcome renderer — the in-session watch reports through the same
  renderer rather than a second one.
- The repo's existing scheduled jobs (CLAUDE.md §19) already define what a stuck lock and a review
  backlog are; the sweep does not invent new definitions.

### Established Patterns
- **Read-only by construction.** The repo's disarmed-by-default posture generalized: the safest
  component is one with no code path to a write.
- **Honest attribution.** Inherited from Phase 27 D-05 — an unrecognized cause names an admin
  rather than guessing the operator can fix it.
- **Silence means healthy.** Notices are exceptions, not a heartbeat.

### Integration Points
- Reads: Phase 27's status surface and the n8n read API. Nothing else.
- Writes: none. Structurally none (D-02).
- Delivery: a push notification into the operator's Claude surface.

</code_context>

<specifics>
## Specific Ideas

- "It never simply stops talking" is the real requirement in NOTICE-02. A watch that hits its bound
  and says nothing is worse than no watch, because the operator believes it is still watching.
- The sweep's value is proportional to how rarely it speaks. A noisy sweep gets ignored, and an
  ignored sweep is the same as no sweep.

</specifics>

<deferred>
## Deferred Ideas

- **Unattended ingestion** — permanently deferred by REQUIREMENTS.md §"Future Requirements". The
  sweep never dispatches.
- **Acting on findings automatically** — out of scope. Notices point at Phase 28's controls; a
  human decides.
- **Alternative sweep hosts (n8n-side, OS cron)** — considered and rejected (D-01). Revisit only if
  D-04's availability check fails.
- **Per-condition notification channels** — all notices use one delivery path in this phase.

</deferred>

---

*Phase: 29-notices-unattended-sweep*
*Context gathered: 2026-07-30*
