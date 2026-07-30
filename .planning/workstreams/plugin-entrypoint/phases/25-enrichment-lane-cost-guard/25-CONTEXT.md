# Phase 25: Enrichment Lane & Cost Guard - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 25 adds the **second lane** — enrichment triggered on records that already exist in HubSpot,
with no row structuring involved — and a **cost guard that covers both lanes**. No batch on either
lane may launch without the operator first seeing what it will cost and how it will be split.

This phase also builds the **credit-only slice of the n8n-side status endpoint**. That is
deliberate: the plugin holds no provider credentials and therefore cannot read balances the way
`scripts/check_provider_credits.py` does. Phase 27 grows the same endpoint into full health.

Unlike Phases 23 and 24, this phase **legitimately touches `n8n/`** — the enrichment workflow and
the new status endpoint are backend work. PLUGIN-04's "no backend file modified" constrains the
*client's* ability to function without backend edits; it does not forbid this milestone from
extending the backend where a requirement demands it.

</domain>

<decisions>
## Implementation Decisions

### Record naming and resolution
- **D-01:** The plugin **passes the record identifier through verbatim** — record IDs, a list name,
  or a view — and **n8n resolves it** using its existing HubSpot credential. The credential
  boundary holds: exactly one system knows how to talk to HubSpot.
- **D-02:** Consequence the planner must handle: this requires **n8n-side work in the enrichment
  workflow** to expand a list/view identifier into record IDs. It also means the plugin cannot
  show a resolved record count before dispatch for list/view inputs — only for explicit ID lists.
  The preview must say plainly that the count is backend-resolved rather than displaying a
  fabricated number. — **Reversibility:** costly — the alternative (a read-only HubSpot token in
  the client) changes the credential boundary the whole milestone is built around.
- **D-02a (raised by 25-RESEARCH.md — UNRESOLVED, plan must sequence this first):** INGEST-04 names
  "list, view, or record IDs", but research found that **HubSpot saved views have no discoverable
  public API**, and the Lists API path (`GET /crm/v3/lists/object-type-id/{id}/name/{name}` +
  `/memberships`) requires a **`crm.lists.read` scope that is not evidenced anywhere in this repo's
  HubSpot credential setup**. Two early plan tasks follow, both before any list/view
  implementation: (1) one live call to verify whether the existing credential carries
  `crm.lists.read`; (2) a decision on view resolution. If views remain unresolvable, **INGEST-04
  scopes down to lists + record IDs** and that reduction is recorded as a requirement amendment
  rather than silently dropped.

### Provider selection
- **D-03:** Provider selection has an **admin-config default that is overridable per batch**. The
  committed example config ships with the default set to the **full waterfall**.
- **D-04:** The example config file must **explicitly document the credit-burn implications** of
  that default, and must state that the valid settings are: the full waterfall, a selected cohort
  of providers, or none — and that any of them can be overridden per batch.
- **D-05:** **This amends success criterion 2 of Phase 25**, which currently reads "with no
  selection stated, no provider is enabled and no credits burn." With a full-waterfall default,
  saying nothing enables everything. The user was shown this conflict and chose the default-on
  behavior with documented warnings as the mitigation. ROADMAP.md Phase 25 criterion 2 should be
  reworded before this phase is marked complete. This is the second accepted requirement amendment
  in this milestone (see Phase 23 D-05 for the PLUGIN-02 amendment).
  — **Reversibility:** reversible — flipping the shipped default to `none` is a one-line change in
  the example config plus a wording change in the preview.
- **D-06:** Whatever the resolved selection is, the **preview states it explicitly** before
  approval. The operator always sees which providers this batch will use — the default being
  permissive makes this display mandatory, not optional.
- **D-06a (from 25-RESEARCH.md — softens D-05's risk):** The deployed `Parse HubSpot Event` node
  has **no server-side default** for `providers` — an absent or unrecognized value resolves to
  **zero providers**, so the backend cannot burn credits on a malformed request. The envelope is
  `{ "providers": [...], "events": [{objectId, objectType}, ...] }` with `X-Enrichment-Secret`
  header auth. Consequence: the client must **always send an explicit resolved provider list**,
  never rely on omission. The permissive default in D-03 is therefore purely a *client-side*
  convenience sitting on top of a fail-closed backend — which is the mitigation that makes the
  criterion-2 amendment in D-05 tolerable.

### Cost estimation
- **D-07:** Cost rates live in a **versioned rate table inside the plugin, stamped with the date
  the rates were measured**. Seeded from this repo's measured actuals rather than vendor list
  prices: Lusha flat 1 credit/contact and 2 credits/company with 0 credits for stored-id
  re-enrich, and roughly $0.0686 Anthropic spend per record from the Phase 22 canary.
- **D-08:** The date stamp exists so **staleness is visible rather than silent**. A rate table
  measured months ago must read as such in the preview.
- **D-09:** Plugin-local, not read from the repo's cost-ledger docs at runtime. Runtime coupling to
  backend doc paths is what broke earlier today when the planning directories were restructured;
  the client must not repeat it.
- **D-10:** Remaining balances come from the **n8n-side status endpoint, never from the client
  calling a provider directly**. A balance that cannot be read renders as **"unknown"**, and the
  warning says so rather than assuming headroom. Unknown is never displayed as zero or as healthy.

### Chunking and dispatch
- **D-11:** The **client splits** oversized batches. The preview shows the chunk count and rows per
  chunk before approval, and dispatch sends exactly that plan.
- **D-11a (from 25-RESEARCH.md — chunk size is constrained, not arbitrary):** n8n Cloud webhook
  responses are capped at roughly 100 seconds, and the enrichment workflow has **no
  `Split In Batches` node** — every record in a POST runs the full provider + Haiku + Sonnet chain
  before the response fires. Chunk size must therefore be derived from measured per-record
  latency, not chosen as a round number. No batch-timing data exists in this repo yet, so the plan
  needs a measurement task before fixing the default.
- **D-11b:** Because of the timeout ceiling, a **timeout must count as a failed chunk** for D-12's
  skip rule — the same as a non-2xx. Distinguishing "timed out but may have succeeded server-side"
  from "backend rejected it" is Phase 26's problem, not this phase's; here it is simply a failure
  that gets skipped and collected.
- **D-12:** Chunks are sent **sequentially**, and a failing chunk is **skipped rather than
  aborting the run**. Remaining chunks continue.
- **D-13:** Failed chunks are **collected and presented back to the operator as a separate
  batch** — a re-sendable unit, not a list of errors. This is the seam Phase 26's safe retry
  (DISPATCH-04) builds on: the failed set is already a well-formed batch by construction.

### Judgment calls made during planning
- **D-14 (the status endpoint is a NEW workflow file, not a second trigger in
  `wf_enrichment_cloud.json`):** research suggested wiring the dangling `*Usage` probe nodes to a
  response. That is wrong — those nodes **fork off `Parse HubSpot Event` and run early**, so a
  responder on that branch would **beat `Build Response` and return the wrong body for an actual
  enrichment call**. A separate workflow file carries zero regression risk and is the natural home
  for Phase 27's growth. Probes are chained **sequentially**, not fanned out, so all three complete
  before the single response fires.
- **D-15 (an oversize list is REFUSED, never truncated):** D-02 (backend resolves; the client
  cannot count) and D-11a (~100s ceiling, no `Split In Batches`) collide — a 500-member list
  resolved server-side into one execution cannot finish. Refusing, with a redirect to record IDs,
  is honest. **Silently truncating would enrich an arbitrary subset and report success**, which is
  the worst available outcome. This is a real capability bound, recorded in `25-BLOCKERS.md` and
  `CHANGELOG.md` so an admin finds it without opening a plan.
- **D-16 (the tabular lane's cost block is a stated zero WITH its reason, not an omitted block):**
  criterion 3 says *every* preview on *both* lanes. Contact-upload runs no provider and no model
  call, so zero is the true answer — and it renders through the **same shared helper** as the
  enrichment block, so the two cannot drift apart.
- **D-17 (the unknown-vs-zero assertion shape is constrained):** the distinction is tested three
  times independently — n8n response assembly, client comparison, and rendered preview text — and
  each test must assert the two produce **different output**. An assertion of the form "unreadable
  is falsy" **passes against the defect**, so that shape is explicitly banned in `25-VALIDATION.md`.

### Claude's Discretion
- The chunk size threshold's default value and where it is configured.
- Rate-table file format and how the measurement date is represented.
- Preview layout for the cost block (per-provider breakdown vs single total).
- The envelope details of the enrichment POST beyond what `Parse HubSpot Event` requires.
- How the credit-only status endpoint is shaped internally, provided it returns balances and
  distinguishes "unknown" from a real zero.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase decisions (locked, constrain this phase)
- `.planning/workstreams/plugin-entrypoint/phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-CONTEXT.md`
  — the dispatch shell, the arming gate (D-11 there: conversation-only, nothing on disk), the
  preview conventions (D-08/D-09 there), and the config file shape this phase's provider default
  lives in.
- `.planning/workstreams/plugin-entrypoint/phases/24-non-tabular-input-adapters/24-CONTEXT.md`
  — the adapters whose output the cost guard must also cover. Note D-01 there: extraction is free
  of provider and API cost, so the cost guard governs dispatch, not extraction.

### Milestone scope and requirements
- `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` — INGEST-04, DISPATCH-02, PREVIEW-02,
  PREVIEW-03. §"Endpoints (targets)" gives the auth model, and §"Credential boundary" is the
  paragraph D-01 and D-10 are both derived from — it explains why the n8n-side status endpoint has
  to exist at all.
- `.planning/workstreams/plugin-entrypoint/ROADMAP.md` §"Phase 25" — goal and four success
  criteria. **Criterion 2 is amended by D-05.**

### Backend contract
- `n8n/` — the enrichment workflow containing `Parse HubSpot Event`, whose accepted envelope shape
  the enrichment POST must match. This phase extends it for list/view resolution (D-02).
- `scripts/check_provider_credits.py` — the admin-side credit check. The n8n-side status endpoint
  serves the same data to a client that cannot hold provider credentials; this script is the
  reference for which balances are readable and which refuse.
- `config/provider_priority.yaml` — the waterfall order the "full waterfall" default means.

### Measured cost data (seeds D-07)
- The Phase 22 canary cost snapshots and the repo's cost ledger — measured Anthropic spend per
  record and observed Lusha credit behavior under v3. Read at planning time to seed the rate
  table; **not** read at runtime (D-09).
- `docs/LUSHA-V3-CONTRACT.md` — the v3 pricing contract of record.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 23's preview → approve → arm → dispatch path. The cost block is added to the existing
  preview; no second approval gate is built.
- `scripts/check_provider_credits.py` — known-good per-provider balance probing, including which
  providers refuse. Lusha's `credits.remaining` works; ZoomInfo GTM needs a `vnd.api+json` Accept
  header or returns 406; the Apollo key is not a master key and 403s, which must degrade to
  "unknown" rather than zero. This is precisely the D-10 case.
- Measured Lusha v3 pricing and canary Anthropic actuals already exist — the rate table is seeded
  from real data, not estimated.

### Established Patterns
- **Credential boundary.** Provider and HubSpot credentials live in n8n. Anything the client needs
  to know about them arrives through an n8n endpoint.
- **Unknown is not zero.** The repo's enrichment side already distinguishes absent from false.
  D-10 applies the same discipline to credit balances.
- **Disarmed by default.** Phase 23's arming gate still governs every send here; the cost guard is
  an additional gate, not a replacement.

### Integration Points
- New: `hubspot/backend-status` (credit-only slice) — built here, grown in Phase 27.
- New: `hubspot/enrichment/event` dispatch from the client, plus list/view resolution inside the
  enrichment workflow.
- Existing: the Phase 23 preview, extended with a cost block and a chunk plan.

</code_context>

<specifics>
## Specific Ideas

- The failed-chunk set being handed back as a *batch* rather than an error list is the deliberate
  design choice here — it makes Phase 26's retry a re-dispatch of an existing object rather than a
  reconstruction from log lines.
- The rate table's date stamp matters more than its precision. An operator seeing "measured
  2026-07-30" can judge whether to trust it; an unstamped number cannot be judged at all.

</specifics>

<deferred>
## Deferred Ideas

- **ROADMAP Phase 25 criterion 2 rewording** — required by D-05 before this phase seals.
- **Full backend health surface** — Phase 27 / STATUS-01..06. This phase builds only the credit
  slice of that endpoint.
- **Per-record outcome parsing and retry execution** — Phase 26 / REPORT-01, DISPATCH-04. Phase 25
  produces the failed-chunk batch; Phase 26 acts on it.
- **Resolved record count for list/view inputs before dispatch** — blocked by D-01/D-02 (the client
  cannot resolve without a HubSpot credential). Revisit only if the credential boundary changes.
- **Parallel chunk dispatch** — rejected for now; sequential-with-skip gives Phase 26 a clean
  failed set.

</deferred>

---

*Phase: 25-enrichment-lane-cost-guard*
*Context gathered: 2026-07-30*
