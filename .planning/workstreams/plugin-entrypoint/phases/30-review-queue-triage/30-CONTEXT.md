# Phase 30: Review-Queue Triage - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 30 closes the loop on records the backend flagged for human judgment. The operator sees each
conflict in plain language, adjudicates it conversationally, and the decision is written back to
HubSpot **stamped as a human decision** — so the audit trail distinguishes a person's call from a
model's.

This is the milestone's **second distinct write path**, separate from dispatch. It reuses Phase
28's confirm-then-verify machinery but has its **own** session-scoped gate.

Not in scope: re-implementing the non-clobber merge policy, changing field-policy ownership
classes, or replacing the HubSpot UI as a record-editing surface.

</domain>

<decisions>
## Implementation Decisions

### Review writeback gate
- **D-01:** Review writeback uses a **session-scoped arm plus an exact-write display per decision**.
  The operator arms review writeback once for the session; every individual decision still shows
  the exact property write before it is applied.
- **D-02:** This gate is **separate from dispatch arming** (REVIEW-03 draws that distinction
  deliberately). Arming dispatch does not arm review writeback, and vice versa.
- **D-03:** Ungated, the plugin **shows exactly what it would write and writes nothing** (REVIEW-03).
- **D-04:** Rationale worth preserving: triaging ten records must not mean ten arming steps.
  Friction here pushes the operator back to the HubSpot UI, which defeats the phase.
  — **Reversibility:** reversible — tightening to per-decision arming is a change at one gate check.

### Non-clobber enforcement
- **D-05:** The **backend enforces** the non-clobber policy. The n8n-side review endpoint applies
  the existing merge and field policy — a `manual_protected` value is never overwritten by a review
  decision, and that rule lives in exactly one place.
- **D-06:** The **client reads `config/field_policy.yaml` display-only**, purely to show the
  operator that a value is protected *before* they attempt a decision on it. This is the same
  read-only-lookup pattern as Phase 23 D-07's mapping preview: read the config to explain, never to
  decide.
- **D-07:** The client does **not** refuse locally. Refusing locally would create a second policy
  authority that can drift from the backend's — the thing this milestone has declined everywhere
  else.

### Audit stamping
- **D-08:** Every decision stamps **human source, timestamp, and the operator's stated reason**
  into the existing audit mechanism (REVIEW-04). No new audit schema is invented.
- **D-08a (CORRECTS D-08's premise — 30-RESEARCH.md, verified against deployed schema and code):**
  The flat `<field>_source` / `<field>_verified_at` / `<field>_verified_by_model` /
  `<field>_validation_status` convention described in the root `CLAUDE.md` **does not exist in this
  repo's deployed schema**. The real mechanism is **one JSON blob per object** —
  `lv_enrichment_provenance` (companies) / `lv_contact_enrichment_provenance` (contacts) — with
  entries shaped `{source, confidence, verified_at, validation_status, value, evidence_url?}` and
  **no `verified_by_model` key at all** (`src/merge_policy.py`, `n8n/code/mergeCompanies.js`).
- **D-08b:** D-08's intent is still satisfiable: a human decision **additively merges an entry**
  into that same blob with `source: "human"`, `validation_status: "human_approved"`, and
  `reason: <operator text>`. Additive merge, never replacement — the prior machine entries stay.
- **D-08c:** The review properties this phase drives **are real, but only under the `lv_` prefix**:
  `lv_enrichment_needs_review`, `lv_enrichment_review_reason`, `lv_enrichment_review_candidate_json`,
  `lv_enrichment_review_approved`, `lv_enrichment_reviewed_by`, `lv_enrichment_reviewed_at`,
  `lv_icp_needs_review` — on both companies and contacts. The generic unprefixed names used in root
  `CLAUDE.md` are wrong for this deployment.

### Enforcement path and endpoint — corrected by research
- **D-08d:** The non-clobber engine D-05 defers to **already exists and is tested**:
  `n8n/code/reviewApply.js`, wired into `wf_scheduled_maintenance_cloud.json`'s 15-minute
  `Review Trigger`. It performs compare-and-set staleness checking and never lets a
  `manual_protected` field reach the queue at all. `tests/n8n/reviewLoop.test.mjs` covers the
  contract. **Reuse it; do not re-implement.**
- **D-08e:** A **new synchronous endpoint and a new baked flag are required.** No existing webhook
  carries a review decision, and the existing apply path is a 15-minute poll — incompatible with
  the confirm-then-verify pattern D-01 imports from Phase 28. The plan adds
  `hubspot/review/decision` plus `ALLOW_HUBSPOT_REVIEW_WRITES` in
  `scripts/deploy_n8n_workflows.py`'s `_OVERLAY_FLAG_SPEC`, mirroring how Phases 25/27 grow
  `hubspot/backend-status`. The existing 15-minute loop **stays as a backstop** rather than being
  retired.
- **D-08f:** **D-11's "which source said what" cannot be fully literal.** By the time a field
  reaches `needs_review` the pipeline has resolved to a single `source_provider` + `reason` string;
  true multi-provider disagreement is computed transiently in `scoreEnrichment.js` (`ranked` /
  `conflicts`) and **never persisted**. The queue renders what is stored, and says plainly that it
  is showing the resolved source rather than the full disagreement. Persisting `conflicts` is a
  cheap fast-follow, recorded as deferred rather than assumed.
- **D-09:** The operator's stated reason is captured as free text and stored. A decision without a
  reason is still a decision, but the reason is what makes the audit trail useful later.

### Rejection
- **D-10:** Rejecting a record **records the reason and leaves it in the queue** (REVIEW-05).
  Review flags are **never silently cleared**, and a record never leaves the queue without a
  recorded decision.

### Queue presentation
- **D-11:** The queue lists each record's conflict in plain language — the competing values, which
  source said what, evidence links, and a link to the HubSpot record — so a non-technical operator
  can actually adjudicate. The enrichment pipeline already stores all of this in the source-metadata
  and `enrichment_last_decision` fields; this phase renders it, it does not recompute it.

### Claude's Discretion
- Queue ordering and how many conflicts are shown at once.
- Wording of the conflict presentation and of the exact-write display.
- How the operator's reason is elicited.
- Whether the queue renders in chat or as an Artifact (Phase 23 D-09 permits either).
- Batch resolution of several records sharing one conflict shape.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Prior phase decisions (locked)
- `.planning/workstreams/plugin-entrypoint/phases/28-control-actions/28-CONTEXT.md` — the
  confirm-then-verify machinery this phase reuses. D-13/D-14/D-15 (consequence stated, read-back
  verified, out-of-allowlist refused) apply to review writes too.
- `.planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-CONTEXT.md` — the
  queue is surfaced there as a count before it is worked here.
- `.planning/workstreams/plugin-entrypoint/phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-CONTEXT.md`
  — D-07's read-only-config-lookup pattern, which D-06 here follows for `field_policy.yaml`.

### Milestone scope and requirements
- `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` — REVIEW-01..05. §"Out of Scope"
  forbids replacing the HubSpot UI as a record-editing surface; this phase adjudicates flagged
  conflicts, it is not a general CRM editor.
- `.planning/workstreams/plugin-entrypoint/ROADMAP.md` §"Phase 30" — goal and five success criteria.

### Backend policy (the single source of truth D-05 defers to)
- `config/field_policy.yaml` — ownership classes including `manual_protected`. Read display-only by
  the client (D-06); enforced by the backend.
- `src/merge_policy.py` — the non-clobber merge engine. **Read to understand, never to re-implement.**
- `CLAUDE.md` §6 (source-of-enrichment tracking), §9 (field governance), §22 (human review
  workflow), §23 (audit strategy) — these define the source-metadata fields D-08 stamps into, the
  `human` source and `human_approved` validation status, and the existing review-flow properties
  (`enrichment_review_approved`, `enrichment_reviewed_by`, `enrichment_reviewed_at`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- The source-metadata field convention already supports a human decision: `human` is a registered
  source with `trust_rank: 100` and `can_promote_directly: true`, and `human_approved` is an
  existing validation status. D-08 stamps into fields that already exist.
- The existing review-flow properties (`enrichment_needs_review`, `enrichment_review_reason`,
  `enrichment_review_approved`, `enrichment_reviewed_by`, `enrichment_reviewed_at`,
  `lv_icp_needs_review`) — this phase drives them conversationally instead of through a HubSpot view.
- `enrichment_last_decision` and `lv_icp_score_breakdown` already carry the competing values and
  reasoning D-11 renders.
- Phase 28's confirm-then-verify gate machinery.

### Established Patterns
- **The backend owns policy.** D-05/D-07 — the client explains, the backend decides.
- **Nothing leaves a queue silently.** D-10 mirrors the repo's existing refusal to clear review
  flags without a recorded decision.
- **Audit distinguishes who decided.** The whole source-registry design exists so a human decision
  is traceable as such.

### Integration Points
- Reads: Phase 27's review-backlog surface, plus per-record conflict detail through an n8n endpoint
  (the client holds no HubSpot credential).
- Writes: review decisions through an n8n-side review endpoint that applies the existing merge and
  field policy.
- No direct HubSpot access from the client, in either direction.

</code_context>

<specifics>
## Specific Ideas

- The phase succeeds only if a non-technical operator can actually adjudicate. That makes the
  plain-language conflict rendering (D-11) the load-bearing part, not the writeback plumbing.
- Showing that a field is `manual_protected` *before* the operator decides (D-06) is the difference
  between a considered decision and a silently discarded one.

</specifics>

<deferred>
## Deferred Ideas

- **General CRM editing from the plugin** — explicit exclusion, not deferred.
- **Write-back of corrections beyond review decisions** — REQUIREMENTS.md §"Future Requirements".
- **Automated resolution of conflicts** — out of scope by definition; the queue exists because a
  human is required.
- **Rubric revision from accumulated review decisions** — a future analysis task, not this phase.

</deferred>

---

*Phase: 30-review-queue-triage*
*Context gathered: 2026-07-30*
