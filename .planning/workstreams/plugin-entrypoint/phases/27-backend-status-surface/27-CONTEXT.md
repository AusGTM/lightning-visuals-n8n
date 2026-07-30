# Phase 27: Backend Status Surface - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 27 answers "what is the backend doing?" truthfully, in plain language, without the operator
opening n8n and without the plugin holding a provider or HubSpot credential.

It **generalizes the credit-only status endpoint Phase 25 built** into full health: credential
state, queue and lock counts, review backlog. It is read-only — no mutation lives here (that is
Phase 28) and no unprompted notification (that is Phase 29).

</domain>

<decisions>
## Implementation Decisions

### How the status picture is assembled
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

### Failure-cause translation
- **D-04:** Translation is **table-first with a Claude fallback**: a static table maps known n8n
  error signatures to plain language plus who can fix it; anything unmatched is interpreted
  in-session by Claude.
- **D-05:** **Guardrail on the fallback, required.** The concern raised and accepted: a
  non-deterministic interpretation on a surface whose job is telling someone whether they can act
  is the place a confident wrong answer does most damage. Therefore an unmatched error must (a) be
  labelled plainly as an interpretation rather than a known cause, (b) show the raw error text
  alongside it, and (c) **default the who-can-fix-it attribution to "an admin"** rather than
  telling the operator they can fix something the table does not recognize. A wrong "you can fix
  this" is worse than an honest "I don't recognize this — here's the raw error, an admin can
  help." — **Reversibility:** reversible — the fallback is a single branch behind the table lookup.
- **D-06:** Every signature that the fallback handles more than once is a candidate for promotion
  into the static table. The table is expected to grow.

### Scope of reporting
- **D-07:** **Every workflow the n8n API key can see** is reported — no allowlist. A newly deployed
  or renamed workflow appears without a config edit. Truthful by construction, since a workflow
  going silently unreported is the exact failure this phase exists to prevent.

### Unknown handling
- **D-08:** Inherited and reaffirmed from Phase 25 D-10: a value the backend cannot supply reads as
  **"unknown"**, never as zero and never as healthy. Apollo's key is not a master key and returns
  403 on balance reads — that is a known, expected "unknown", and it must not render as a zero
  balance or as a healthy provider. (STATUS-06.)

### Presentation
- **D-09:** Status is **conversational text by default**; a dashboard Artifact is published on
  request, stamped with its fetch time, and a refresh **re-publishes to the same URL** rather than
  minting a second one. This is the convention Phase 23 D-09 anticipated for previews — one
  rendering convention across the plugin.

### Claude's Discretion
- Layout and grouping of the conversational status output.
- Dashboard Artifact design, provided it carries the same data and the fetch-time stamp.
- Initial contents of the error-signature table beyond the four causes criterion 2 names
  (expired credential, rate limit, exhausted quota, malformed record).
- How "in flight" is determined from the executions API.
- Internal shape of the generalized status endpoint, provided it preserves unknown-vs-zero.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase decisions (locked)
- `.planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-CONTEXT.md` —
  builds the credit-only slice of the endpoint this phase generalizes. D-10 there is the
  unknown-vs-zero rule D-08 here inherits.
- `.planning/workstreams/plugin-entrypoint/phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-CONTEXT.md`
  — D-09 sets the chat-first-with-Artifact convention. D-14a confirms the operator is in the Claude
  Desktop **Code** tab, which is what makes Artifact publishing available at all.

### Milestone scope and requirements
- `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` — STATUS-01..06. §"Endpoints (targets)"
  gives the read endpoints and their auth: `/api/v1/workflows` and `/api/v1/executions` take
  `X-N8N-API-KEY`; `hubspot/backend-status` takes headerAuth. §"Credential boundary" is the
  paragraph D-01 implements.
- `.planning/workstreams/plugin-entrypoint/ROADMAP.md` §"Phase 27" — goal and five success criteria.

### Backend and admin references
- `scripts/check_provider_credits.py` — the admin-side probe the status endpoint mirrors for a
  credential-less client. Known behaviors to preserve: Lusha `credits.remaining` works; ZoomInfo
  GTM requires `Accept: application/vnd.api+json` or returns 406; the Apollo key is not a master
  key and 403s. The 403 is the canonical D-08 "unknown" case.
- `scripts/deploy_n8n_workflows.py` — the existing n8n API client: base URL and `X-N8N-API-KEY`
  convention the client's read calls follow. Reference for the calling pattern, not an import.
- `CLAUDE.md` §§19, 21, 23 — scheduled-job semantics, safety gates, and the audit fields that
  define what a stuck lock is (`enrichment_status = running` past `enrichment_lock_until`) and what
  the review backlog counts.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- The Phase 25 status endpoint — extended here, not rebuilt.
- `scripts/check_provider_credits.py` — measured, live-validated provider probe behavior including
  which providers refuse and how.
- The n8n API client pattern from `scripts/deploy_n8n_workflows.py`.
- HubSpot property semantics for lock and review state already exist in the enrichment data model
  (`enrichment_status`, `enrichment_lock_until`, `enrichment_needs_review`, `lv_icp_needs_review`).

### Established Patterns
- **Credential boundary.** D-01 is the boundary expressed as an architecture split rather than a
  policy note.
- **Unknown is not zero.** Repo-wide discipline, applied here to provider balances and any datum
  the backend cannot supply.
- **Read from the system, not from local belief.** D-03 — the plugin reports what n8n says.

### Integration Points
- Client → n8n API: `/api/v1/workflows`, `/api/v1/executions` (read-only, `X-N8N-API-KEY`).
- Client → `hubspot/backend-status` (headerAuth) for credential-gated facts.
- n8n status endpoint → HubSpot, for lock/queue/review counts.
- No mutation. No notification. Both are later phases.

</code_context>

<specifics>
## Specific Ideas

- "A silently wedged backend is visible without anyone thinking to look" (criterion 4) is the
  phase's real purpose. Counts of stuck locks and review backlog matter more than pretty output.
- The error table growing over time (D-06) is expected, not a design smell — each promotion from
  fallback to table is a real error signature learned from production.

</specifics>

<deferred>
## Deferred Ideas

- **Mutating anything** — Phase 28 / CONTROL-01..07. This phase is strictly read-only.
- **Unprompted notification when something is wrong** — Phase 29 / NOTICE-03. Phase 27 answers when
  asked; it does not speak up on its own.
- **Review-queue detail and resolution** — Phase 30 / REVIEW-01..05. Phase 27 reports the backlog
  count only.
- **Promoting fallback-interpreted errors into the static table** — ongoing maintenance, not a
  phase deliverable.

</deferred>

---

*Phase: 27-backend-status-surface*
*Context gathered: 2026-07-30*
