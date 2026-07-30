# Phase 28: Control Actions - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 28 is **the only phase in this milestone that mutates the backend**. The operator can start a
run, turn a workflow on or off, re-time a scheduled job, and enable live writes — all from the
conversation, each mutation confirmed before it happens and verified by read-back after.

The mutation set is **allowlisted**: write-safety flag overlay, Schedule Trigger cadence, workflow
active state. Any other workflow-JSON change is **refused rather than attempted**. Arbitrary
workflow deployment from the plugin is a permanent exclusion — editing nodes, credentials, or
workflow structure stays an admin task run from this repo.

Nothing may be flipped that Phase 27 cannot first read: every confirmation and every read-back
verification is built on that read surface.

</domain>

<decisions>
## Implementation Decisions

### Live-write arming — resolving the conversation-scope contradiction
- **D-01:** CONTROL-04 requires live-write permission to be conversation-scoped, but n8n's
  write-safety flag is **persistent backend state that outlives any conversation**. Resolution:
  the plugin **arms immediately before dispatch, dispatches, then disarms**, with **read-back
  verification in both directions**.
- **D-02:** This scopes the permission **tighter than the conversation** — to the span of a single
  operation. "Never inherited by a later session" therefore holds by construction rather than by
  promise, which is strictly stronger than CONTROL-04 asks for.
  — **Reversibility:** costly — the alternative (arm-for-the-session with a TTL sweep) makes the
  lapse depend on Phase 29's sweep actually running, and unwinding to it later means rebuilding the
  arming lifecycle and its verification points.
- **D-03:** **Known failure mode, must be handled explicitly:** a crash or interruption between
  dispatch and disarm leaves the backend armed. Mitigations required in the plan: (a) Phase 27's
  status readout reports the true flag state read from n8n, so a stuck-armed backend is visible;
  (b) Phase 29's sweep is the backstop that catches it unattended. The plugin must not pretend
  disarm always succeeds — a failed disarm is reported loudly, not swallowed.
- **D-04:** Every status readout states plainly whether live writes are currently on, read from the
  backend (Phase 27 D-03), never asserted from local config.

### Starting a run
- **D-05:** Runs are started by **the mechanism each already has**: an ingestion lane is started by
  its **existing webhook POST** — the same dispatch path with its preview, cost guard, and arming
  gate intact. A **scheduled scan** has no payload and no webhook, so it is started through the
  **n8n API**.
- **D-06:** Rationale worth preserving: starting an ingestion lane via the n8n API would bypass the
  preview, cost guard, and arming gate that Phases 23 and 25 built. The guards live on the dispatch
  path, so the dispatch path is the only way in for a lane.
- **D-07:** No new manual-trigger webhooks are added to workflows. Each would be another entry
  point to secure for no gain.

### Cadence
- **D-08:** Cadence accepts **free-form natural language**, parsed to a schedule — but the parse is
  **interpreted back to the operator in plain language for confirmation before any conversion to
  cron**. The operator confirms "so: every weekday at 9am and 5pm" before anything is written.
- **D-09:** The confirmation step is what makes free-form safe. A misparse silently changing how
  often the backend burns provider credits is the failure this guards against, and the operator
  sees the interpretation, not the cron string. **Cron syntax never appears to the operator** in
  either direction (CONTROL-03).
- **D-10:** A parse the plugin cannot confidently interpret is **refused with examples**, not
  guessed at.

### Reversibility statement
- **D-11:** Before mutating, the plugin **captures the prior state and quotes it back** when the
  change lands: "it was hourly; to undo, I'll set it back to hourly." Exact even when the prior
  value was unusual.
- **D-12:** This costs nothing extra — the pre-read is already required for CONTROL-06's read-back
  verification, so the prior value is in hand either way.

### Confirmation and verification (from requirements, restated as binding)
- **D-13:** Every mutation states its consequence in plain language before it happens, shows what
  will change, and waits for **explicit confirmation** (CONTROL-05).
- **D-14:** After every mutation the plugin **re-reads the backend and reports verified or failed**.
  A `200` from n8n is **never** reported as success on its own (CONTROL-06).
- **D-15:** Any requested change outside the allowlist is **refused, not attempted** (CONTROL-05).

### Claude's Discretion
- Wording of consequence statements per action type.
- Confirmation phrasing and how the diff of "what will change" is displayed.
- How the natural-language cadence parse is performed and how its interpretation is rendered.
- Retry posture when a read-back verification is inconclusive.
- Whether arm/disarm and the dispatch are presented to the operator as one action or three.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase decisions (locked)
- `.planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-CONTEXT.md` — the
  read surface every confirmation and verification here depends on. D-03 there (read state from
  n8n, never assert from config) is what D-04 here relies on.
- `.planning/workstreams/plugin-entrypoint/phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-CONTEXT.md`
  — D-11 there is the interim client-side arming this phase supersedes with the real n8n-side
  mechanism.
- `.planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-CONTEXT.md` —
  the cost guard and chunked dispatch that D-05/D-06 must not bypass.

### Research already completed (read before planning)
- `.planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-RESEARCH.md` —
  the enrichment envelope and the n8n Cloud webhook response ceiling (~100s), which bounds how long
  an arm→dispatch→disarm cycle can hold the flag open.
- `.planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-RESEARCH.md` — where
  the write-safety flag actually lives in the deployed workflow JSON and how a client reads it.
  **This phase writes the same flag it reads, so the two must agree exactly.**

### Milestone scope and requirements
- `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` — CONTROL-01..07. §"Endpoints (targets)"
  gives the mutation surface: `POST /api/v1/workflows/{id}/activate` and `/deactivate` need no JSON
  write; `PUT /api/v1/workflows/{id}` is **allowlisted mutations only**. §"Out of Scope" forbids
  arbitrary workflow deployment from the plugin.
- `.planning/workstreams/plugin-entrypoint/ROADMAP.md` §"Phase 28" — goal and five success criteria.
  Also §"Safety posture, inherited and non-negotiable" in the Overview, which names this phase's
  widening of plugin authority and states that the allowlist plus confirm-and-verify is what keeps
  it bounded.

### Repo conventions
- `scripts/deploy_n8n_workflows.py` and the build scripts — how the write-safety flag overlay is
  applied today by an admin. The plugin's arming must produce the **same** flag state, not a
  parallel convention.
- `CLAUDE.md` §21 — safety gates and the high-risk write list.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 27's read surface — workflow state, execution state, and the write-safety flag read. Every
  mutation here is bracketed by two of those reads.
- The admin-side write-safety flag overlay in the deploy scripts — the canonical definition of what
  armed means in this repo.
- Phase 23's dispatch path, which D-05 reuses verbatim for lane starts.

### Established Patterns
- **Two-key write gate.** Phases 19–22 all follow it. This phase automates the operator's key while
  keeping the gate itself.
- **Confirm, then verify.** The repo's armed operations already read back rather than trusting a
  success status. D-14 is that discipline applied to control actions.
- **Allowlist over generality.** Consistent with the milestone's refusal to become a deploy
  pipeline.

### Integration Points
- `POST /api/v1/workflows/{id}/activate` / `/deactivate` — no JSON write, lowest-risk mutation.
- `PUT /api/v1/workflows/{id}` — allowlisted only: write-safety flag overlay and Schedule Trigger
  cadence. Everything else refused.
- Existing webhooks — lane starts (D-05).
- Phase 27's status endpoint and n8n read API — pre-read and read-back for every mutation.

</code_context>

<specifics>
## Specific Ideas

- The arm→dispatch→disarm cycle is the heart of this phase. It converts a persistent backend flag
  into an operation-scoped grant, which is the only honest way to satisfy "conversation-scoped"
  against state that has no concept of a conversation.
- Confirming the *interpretation* of a cadence rather than the cron string is the same principle as
  showing a preview before dispatch: the operator confirms meaning, never syntax.

</specifics>

<deferred>
## Deferred Ideas

- **Unattended detection of a stuck-armed backend** — Phase 29 / NOTICE-03. D-03 names this as the
  backstop for the arm/disarm crash window.
- **Arbitrary workflow deployment or node editing from the plugin** — permanent exclusion, not
  deferred.
- **Review-queue writeback gating** — Phase 30 / REVIEW-03, which has its own session-scoped
  confirmation separate from dispatch arming.
- **Widening the mutation allowlist** — out of scope; any addition is a new requirement, not a
  planning decision.

</deferred>

---

*Phase: 28-control-actions*
*Context gathered: 2026-07-30*
