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

### Stuck locks — definition corrected by research
- **D-07a (27-RESEARCH.md, verified against `config/hubspot_properties.yaml` and the deployed
  workflow JSON):** STATUS-04's documented stuck-lock definition is **unbuildable as written**.
  `enrichment_lock_until` **does not exist** as a property anywhere, and `lv_enrichment_status` is
  only ever written as `needs_review` or `complete` — **nothing ever sets it to `running`**. That
  definition came from the generic root `CLAUDE.md` and was never implemented in this deployment.
- **D-07b:** **"Stuck" is redefined as an execution still in `status = running` past a threshold**,
  read from the executions API the client already reads for STATUS-01. No schema change, no
  enrichment-pipeline work inside a read-only phase. This detects a wedged *run* rather than a
  wedged *record* — the more useful signal for the operator either way.
- **D-07b(i) — refinement made at execution time (27-04), do not flatten it.** `stuck` is
  **tri-state**, not boolean: `True` is over the threshold, `False` is under it or not in flight,
  and **`None` is in flight with an age we could not read** (a missing or unparseable `startedAt`).
  Collapsing `None` to `False` would make an unreadable run render as "running normally" — the same
  unknown-as-healthy failure D-08 exists to prevent, just wearing a different key. The renderer says
  the age is unknown and names the threshold it could *not* be judged against.
- **D-07b(ii):** because A2's threshold is a carried convention rather than a measured value, the
  verdict **always travels with both numbers** — the run's age and the threshold — and the rendered
  sentence says in words that the threshold is a convention. A future plan that renders a bare
  "stuck" verdict has removed the operator's ability to judge the call.
- **D-07c:** "Queued" and "review backlog" **are** answerable today using the real `lv_`-prefixed
  properties (`lv_enrichment_requested`, `lv_enrichment_status`, `lv_enrichment_needs_review`,
  `lv_icp_needs_review`). Note that "queued" can only be a bare count — no request timestamp is
  stored, so it can never be age-based.
- **D-07d:** REQUIREMENTS.md STATUS-04 and this phase's criterion 4 should be reworded to the
  execution-age definition before the phase seals. Third accepted requirement amendment in the
  milestone.

### Error coverage — corrected by research
- **D-04a (27-RESEARCH.md):** STATUS-02's four named causes are **not equally observable**. Every
  provider-facing node (Lusha / Apollo / ZoomInfo / Anthropic) is configured
  `onError: continueRegularOutput`, so a 401, 429, or exhausted quota **does not fail the n8n
  execution** — those runs are reported as `success`. Only `HubSpot Create` / `HubSpot Update`
  genuinely fail a run, covering "malformed record" only.
- **D-04b:** Therefore the status surface **reads the execution's per-node output data, not just
  the run status** — detecting provider errors inside runs n8n calls successful. This makes
  STATUS-02 true for all four causes **with no backend change**. The pattern already exists
  in-repo: `scripts/enrichment_cost_ledger.py` reads execution data the same way.
- **D-04c:** The operator is given a **very succinct prose explanation** of the error — a sentence,
  not a dump. The raw text remains available (D-05) but is not what leads.
  — **Reversibility:** reversible — falling back to status-only reading is a narrowing, not a
  rewrite.

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
- **D-09a:** "Same URL" extends **across sessions, not just within one**. The artifact identifier
  is **persisted by the plugin** so the operator can bookmark one durable dashboard link.
  Research confirmed same-conversation stability is automatic; cross-session requires this stored
  identifier.
- **D-09b:** The stored identifier carries an **operator-configurable TTL in the operator config
  file, defaulting to 30 days**. Expired identifiers are **garbage-collected on the next plugin
  open**. This is the first plugin-managed state in the design — everything else has been
  admin-provisioned config or session-scoped. The plan must keep it to exactly this: an identifier
  and a timestamp, not a general-purpose store.
  — **Reversibility:** reversible — dropping to same-conversation-only means deleting the store
  and the GC step.

### Findings from planning — one confirmed, one refuted
- **D-10 (CONFIRMED, and it invalidates every prior estimate):** the write-safety literal is **not**
  in 2 nodes (research) or 3 (the planning brief). The committed cloud workflows carry it in **9
  nodes across 3 workflows** — contact ingest 3, enrichment 2, scheduled maintenance 4 — and the
  two flags are declared in **different subsets** of those nodes. The reader must therefore **scan
  every node and report disagreement**, never trust a fixed node list. A hardcoded list would have
  been wrong the day it was written, and would silently under-report an armed backend.
  — **Consequence found at execution time (27-04).** Widening to every workflow (D-07) means the
  reader now works from `GET /api/v1/workflows`'s **collection** entries rather than a per-workflow
  body fetch. That endpoint is documented to return full workflow objects, but nothing in this repo
  proves it always carries `nodes`, and a thin entry would make write-safety read `unknown` for
  every workflow at once — D-10's failure mode wearing an honest-looking word. `describe_all()`
  therefore uses the collection entry only when it actually carries a `nodes` list, and falls back
  to fetching that workflow's body otherwise. **Do not "simplify" that fallback away** in 27-05 or
  Phase 28; it is what keeps an armed backend from reading unknown instead of on.
- **D-11 (REFUTED — verified empirically, do NOT act on the original claim):** planning reported
  that `operator-claude-plugin/tests/conftest.py`'s autouse `no_network` fixture fails to block
  `requests.get`, leaving GET-based reads able to reach the live n8n instance. **This is false.** A
  direct probe run under the fixture raised
  `RuntimeError: Network access blocked in test ...` on a `requests.get` call. The reason: `requests.get`
  delegates to `requests.api.request`, which opens a `Session` and calls `Session.request` — and
  `Session.request` **is** patched. The guard is sound for the `requests` library as used here, and
  **no already-committed test is compromised**. Adding an explicit `requests.get` patch is optional
  belt-and-braces clarity, not a bug fix; do not describe it as closing a hole.
  — **Re-verified and made durable at execution time (27-03).** `27-03-PLAN.md`'s `key_links`
  asserted the opposite ("patches post/request/Session.request but NOT `requests.get` ... the guard
  must be widened in the same commit") — a restatement of the refuted claim that survived into the
  plan. It was **not** acted on. Instead the executor added
  `operator-claude-plugin/tests/test_n8n_read.py::test_requests_get_raises_inside_a_test`, which
  fails loudly if the coverage ever regresses, and left the guard itself untouched. The plan text
  has been corrected. **Any future plan asserting the guard is GET-blind is wrong; read this
  bullet, not the plan.**
- **D-12 (amendment applied, not deferred):** ROADMAP Phase 27 criterion 4 and REQUIREMENTS.md
  STATUS-04 were **reworded to the execution-age definition during planning** rather than left for
  later reconciliation. Correct call — `/gsd-verify-work` would otherwise have failed the phase
  against a criterion nothing in the deployed system could satisfy. D-07d sanctions the change.

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
