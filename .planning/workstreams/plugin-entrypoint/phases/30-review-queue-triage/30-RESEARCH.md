# Phase 30: Review-Queue Triage - Research

**Researched:** 2026-07-30
**Domain:** n8n-side review-decision endpoint, HubSpot review-flow properties, existing non-clobber/provenance mechanism reuse
**Confidence:** MEDIUM-HIGH — every property name and code path below is read directly from this repo's deployed config/code (not from root `CLAUDE.md`'s aspirational spec). The one open item is architectural (synchronous vs. polled apply), not factual.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Review writeback gate**
- **D-01:** Review writeback uses a **session-scoped arm plus an exact-write display per decision**. The operator arms review writeback once for the session; every individual decision still shows the exact property write before it is applied.
- **D-02:** This gate is **separate from dispatch arming** (REVIEW-03 draws that distinction deliberately). Arming dispatch does not arm review writeback, and vice versa.
- **D-03:** Ungated, the plugin **shows exactly what it would write and writes nothing** (REVIEW-03).
- **D-04:** Rationale worth preserving: triaging ten records must not mean ten arming steps. Friction here pushes the operator back to the HubSpot UI, which defeats the phase. — **Reversibility:** reversible.

**Non-clobber enforcement**
- **D-05:** The **backend enforces** the non-clobber policy. The n8n-side review endpoint applies the existing merge and field policy — a `manual_protected` value is never overwritten by a review decision, and that rule lives in exactly one place.
- **D-06:** The **client reads `config/field_policy.yaml` display-only**, purely to show the operator that a value is protected *before* they attempt a decision on it. Same read-only-lookup pattern as Phase 23 D-07.
- **D-07:** The client does **not** refuse locally. Refusing locally would create a second policy authority that can drift from the backend's.

**Audit stamping**
- **D-08:** Every decision stamps **human source, timestamp, and the operator's stated reason** into the **existing source-metadata fields** (REVIEW-04). No new audit schema is invented — the `<field>_source` / `<field>_verified_at` / `<field>_verified_by_model` / `<field>_validation_status` convention already exists and has a `human` source and a `human_approved` validation status.
- **D-09:** The operator's stated reason is captured as free text and stored. A decision without a reason is still a decision, but the reason is what makes the audit trail useful later.

**Rejection**
- **D-10:** Rejecting a record **records the reason and leaves it in the queue** (REVIEW-05). Review flags are **never silently cleared**, and a record never leaves the queue without a recorded decision.

**Queue presentation**
- **D-11:** The queue lists each record's conflict in plain language — the competing values, which source said what, evidence links, and a link to the HubSpot record — so a non-technical operator can actually adjudicate. The enrichment pipeline already stores all of this in the source-metadata and `enrichment_last_decision` fields; this phase renders it, it does not recompute it.

### Claude's Discretion
- Queue ordering and how many conflicts are shown at once.
- Wording of the conflict presentation and of the exact-write display.
- How the operator's reason is elicited.
- Whether the queue renders in chat or as an Artifact (Phase 23 D-09 permits either).
- Batch resolution of several records sharing one conflict shape.

### Deferred Ideas (OUT OF SCOPE)
- **General CRM editing from the plugin** — explicit exclusion, not deferred.
- **Write-back of corrections beyond review decisions** — REQUIREMENTS.md §"Future Requirements".
- **Automated resolution of conflicts** — out of scope by definition; the queue exists because a human is required.
- **Rubric revision from accumulated review decisions** — a future analysis task, not this phase.

> **CORRECTION REQUIRED BEFORE PLANNING — read §"Corrections to CONTEXT.md's factual premises" below.**
> D-08's claim that "the `<field>_source`/`<field>_verified_at`/`<field>_verified_by_model`/`<field>_validation_status` convention already exists" is **false as literally written** — no such flat per-field properties exist anywhere in this repo's deployed schema. A provenance mechanism *does* exist, but it is shaped completely differently (one JSON blob per object, no `verified_by_model` key at all). D-08's *intent* (stamp human source/timestamp/reason using an existing mechanism, invent nothing new) is still fully achievable — see the corrected contract below — but the planner must target the real shape, not the one named in CONTEXT.md's canonical_refs.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REVIEW-01 | Queue shows each record's conflict in plain language: competing values, which source said what, evidence links, HubSpot record link | §"Where conflict detail actually lives" — real fields identified; one hard limitation found (see Open Question 1) |
| REVIEW-02 | Conversational resolution writes back, honoring field-policy ownership classes; `manual_protected` never overwritten | §"Non-clobber enforcement path" — `reviewApply.js` + `mergeCompanies.js`/`mergeContacts.js` are the exact enforcement point; reuse contract given |
| REVIEW-03 | Review writeback gated by its own session-scoped confirmation, separate from dispatch arming; ungated shows the write and sends nothing | §"The writeback endpoint" — no existing endpoint covers this; new endpoint + new baked flag required, pattern given |
| REVIEW-04 | Every decision stamps human source, timestamp, operator's reason into existing source-metadata fields | §"The source-metadata stamping contract, corrected" — real blob shape given; extension approach given |
| REVIEW-05 | Rejection records reason, leaves record in queue, never silently clears flags | §"Rejection semantics" — direct write path identified, does not touch `reviewApply.js`'s clearing logic at all |
</phase_requirements>

## Summary

Phase 30's foundational premise — "reuse the existing merge/field policy and existing source-metadata convention, render what's already stored" — is **directionally correct but the concrete mechanism named in 30-CONTEXT.md and root `CLAUDE.md` is not what was actually built**. This repo already has a complete, tested, human-review *apply* loop (`n8n/code/reviewApply.js`, wired into `wf_scheduled_maintenance_cloud.json`'s `Review Trigger (15 min)` branch, covered by `tests/n8n/reviewLoop.test.mjs`), and it already does the hard part of D-05/REVIEW-02 correctly: non-clobber-by-construction (a `manual_protected` field never enters the review queue in the first place — `mergeCompanies`/`mergeContacts` resolve it to `stage_only` upstream, so it can never appear in `lv_enrichment_review_candidate_json`'s `needs_review` list at all) plus a compare-and-set staleness guard (refetch live properties, and if ANY held field drifted since the candidate was frozen, apply nothing, mark the record stale, and leave it queued — never a partial apply). This is the exact single-authority enforcement point D-05 asks for, and it needs zero re-implementation.

What is **missing**, and what this phase must build: (1) the existing loop is a 15-minute **poll**, not a **synchronous write** — it can't satisfy Phase 28's confirm-then-verify pattern (D-13/14/15, which 30-CONTEXT.md explicitly imports) because there is no way to "re-read the backend and report verified" on a webhook response when the actual apply might not run for up to 15 more minutes; (2) `reviewApply.js` never stamps a `human` source anywhere — it applies the machine's own original `chosen_value` under the machine's own original provenance entry and just clears the review flags, so REVIEW-04's audit requirement is not met by reusing it verbatim; (3) there is no existing webhook endpoint for this at all — `hubspot/enrichment/event` and `hubspot/contact-upload` are the only two, and neither's envelope fits a review decision; (4) the source-metadata convention 30-CONTEXT.md names (flat `<field>_source`/`<field>_confidence`/`<field>_evidence_url`/`<field>_verified_at`/`<field>_verified_by_model`/`<field>_validation_status` properties) **does not exist** — the real mechanism is a single JSON blob per object (`lv_enrichment_provenance` for companies, `lv_contact_enrichment_provenance` for contacts), one entry per field, shaped `{source, confidence, verified_at, validation_status, value, evidence_url?}` — with **no `verified_by_model` key at all** in either the Python oracle or the deployed JS.

**Primary recommendation:** Build one new n8n webhook (e.g. `hubspot/review/decision`) that runs synchronously: refetch the record, run the SAME compare-and-set core `reviewApply.js` already implements (reuse its logic, don't fork it), and on a clean (non-stale) approve, apply the canonical patch **plus** a new provenance entry per approved field with `source: "human"`, `validation_status: "human_approved"`, `verified_at: now`, `value: chosen_value`, and add `reason` (the operator's stated text) to that same entry — this is additive to the existing blob shape, not a schema replacement, and satisfies D-08's actual intent ("no new audit schema... reuse the human source and existing convention") against the *real* convention rather than the one CONTEXT.md described. Gate this endpoint behind a **new** baked flag (e.g. `ALLOW_HUBSPOT_REVIEW_WRITES`, added to `scripts/deploy_n8n_workflows.py`'s `_OVERLAY_FLAG_SPEC` exactly like `ALLOW_HUBSPOT_RECORD_WRITES` already is) so D-01/D-02's "separate gate from dispatch arming" is real at the backend level, not just a client-side fiction. Rejection needs no `reviewApply.js` involvement at all: it is a direct, always-safe HubSpot property write (`lv_enrichment_review_reason` = operator's text, flags untouched) that cannot violate non-clobber because it writes no candidate field.

## Corrections to CONTEXT.md's factual premises

These three corrections should be read by the planner before writing tasks — they change what REVIEW-01/02/04's task bodies must actually say:

1. **The review-flow properties ARE real, but only under their `lv_`-prefixed names** — `lv_enrichment_needs_review`, `lv_enrichment_review_reason`, `lv_enrichment_review_candidate_json`, `lv_enrichment_review_approved`, `lv_enrichment_reviewed_by`, `lv_enrichment_reviewed_at`, `lv_icp_needs_review` all exist on **both** companies and contacts [VERIFIED: `config/hubspot_properties.yaml`, full read]. CONTEXT.md's canonical_refs cites them without the `lv_` prefix (matching root `CLAUDE.md`'s generic spec, not this repo's build) — the same divergence Phase 27's research already flagged for the status-surface properties. Use the `lv_`-prefixed names exclusively.
2. **There is no flat per-field source-metadata property convention.** `config/hubspot_properties.yaml` has exactly four per-field `_verified_at` properties total (`lv_org_type_verified_at`, `lv_produces_content_verified_at` on companies; `lv_jobtitle_verified_at`, `lv_mobilephone_verified_at` on contacts) — these are stale-refresh **cache keys**, not a general metadata convention, and there is no `_source`/`_confidence`/`_evidence_url`/`_verified_by_model`/`_validation_status` property for ANY field. All per-field provenance lives inside one JSON-text property per object: `lv_enrichment_provenance` (companies) / `lv_contact_enrichment_provenance` (contacts) [VERIFIED: `src/merge_policy.py` lines 34-45, `n8n/code/mergeCompanies.js` lines 9-14, both state this as the Phase 15 provenance model explicitly].
3. **`human_approved` and `human` are real, registered vocabulary — but never yet used in code.** `config/source_registry.yaml` has `human: {type: reviewer, trust_rank: 100, can_promote_directly: true}` [VERIFIED]. Nothing in `src/` or `n8n/code/` currently constructs a provenance entry with `source: "human"` — grep across both trees found zero occurrences. `human_approved` as a literal string does not appear anywhere in code either; it is a naming convention from root `CLAUDE.md`, not an enforced enum (nothing validates `validation_status` against a fixed list), so the plugin is free to use it.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Render queue / conflict detail in plain language | Client (conversation) | — | No credential needed once the n8n-side read supplies the data; pure presentation |
| Read per-record conflict detail (candidate JSON, provenance blob) | n8n-side endpoint (HubSpot credential) | — | Client holds no HubSpot credential (same boundary as Phases 27/28/30's canonical_refs) |
| Field-policy display lookup (`manual_protected` etc.) | Client (reads `config/field_policy.yaml` at build/package time) | — | D-06: read-only, mirrors Phase 23 D-07 |
| Non-clobber enforcement (compare-and-set, `manual_protected` never overwritten) | Backend (`reviewApply.js`-style logic inside the new n8n endpoint) | — | D-05: single authority; already exists, must not be re-implemented or forked into a second copy |
| Human-source provenance stamping | Backend (same n8n endpoint, same HubSpot PATCH as the canonical write) | — | Only the backend holds the HubSpot credential to write `lv_enrichment_provenance` |
| Session-scoped review-writeback arm state | Client (conversation-scoped flag) + Backend (a new baked flag gating the actual write) | — | Mirrors Phase 28 D-01/D-02's split: client tracks "am I willing to write right now," backend flag is the real gate a stray call still can't bypass |
| Rejection write (reason only, flags untouched) | Backend (n8n endpoint, direct property write, no merge logic invoked) | — | Simpler than approve; touches no candidate field so nothing can clobber |

## Standard Stack

No new library or package. This phase reuses this repo's own JS modules (`n8n/code/reviewApply.js`, `mergeCompanies.js`, `mergeContacts.js`) inside a new n8n Code node, and extends `scripts/deploy_n8n_workflows.py`'s existing flag-overlay mechanism with one new entry. The client side (whatever runtime Phase 23 lands on) makes one new outbound HTTP call type and one new inbound read call, both over the same HTTP client already used for `hubspot/enrichment/event` and `hubspot/backend-status`.

| Surface | Method | Auth | Already exercised by |
|---|---|---|---|
| New `hubspot/review/decision` webhook (approve/reject) | POST | headerAuth (same convention as `hubspot/enrichment/event`) | New — mirrors the existing webhook pattern exactly |
| Review-detail read (queue contents, per-record conflict) | via existing/extended `hubspot/backend-status` endpoint, or a small sibling read endpoint | headerAuth | Extends Phase 27's status endpoint pattern — HubSpot Search is already proven live in `wf_scheduled_maintenance_cloud.json`'s `Review Search (approved=true)` node |
| `config/field_policy.yaml` | local file read | none (build-time/packaged) | New for the client; same read-only pattern Phase 23 D-07 established for `column_mapping.yaml` |

**Installation:** none.

## Package Legitimacy Audit

Not applicable — this phase installs no external package on either the client or backend side.

## Architecture Patterns

### System Architecture Diagram

```
Operator: "show me what needs review"
        │
        ▼
Client (no HubSpot credential)
        │
        ├──► GET review detail via n8n-side endpoint (extends hubspot/backend-status,
        │     or a small sibling read) — per flagged record:
        │       lv_enrichment_review_candidate_json  (needs_review decisions: field,
        │         current_value, chosen_value, source_provider, confidence, reason,
        │         validation_status, evidence_url, verified_at)
        │       lv_enrichment_provenance / lv_contact_enrichment_provenance
        │       lv_icp_score_breakdown, lv_anti_icp_reason (ICP-specific narrative)
        │       lv_enrichment_review_reason (why review was needed, machine-written)
        │
        ├──► read config/field_policy.yaml locally (display-only, D-06)
        │
        ▼
Client renders plain-language conflict + HubSpot record link (REVIEW-01)
   operator adjudicates conversationally (approve/reject + free-text reason)
        │
        ▼  (only if review-writeback armed this session — D-01/D-02, separate flag
        │   from dispatch arming)
        │
        ├──► APPROVE: POST hubspot/review/decision
        │       { object_type, record_id, decision: "approve", reason }
        │            │
        │            ▼
        │     n8n workflow (new Code node, reuses reviewApply.js's core):
        │       1. Refetch live HubSpot properties for record_id
        │       2. Compare-and-set against candidate's frozen current_value (per field)
        │          -> ANY drift: apply nothing, mark stale, leave queued, respond "stale"
        │       3. Clean: build canonicalPatch (candidate's chosen_value, unchanged)
        │          PLUS a NEW provenance entry per approved field:
        │            { source: "human", confidence: 100, verified_at: now,
        │              validation_status: "human_approved", value: chosen_value,
        │              reason: <operator's text> }
        │          merged into the existing lv_enrichment_provenance blob (additive key)
        │       4. clearPatch: lv_enrichment_needs_review=false,
        │          lv_enrichment_review_approved=false, lv_enrichment_review_reason="",
        │          lv_enrichment_review_candidate_json="", lv_enrichment_reviewed_at=now,
        │          lv_enrichment_reviewed_by=<operator label>
        │       5. Gated by NEW baked flag ALLOW_HUBSPOT_REVIEW_WRITES (separate from
        │          ALLOW_HUBSPOT_RECORD_WRITES — D-02)
        │       6. HubSpot PATCH, then re-read the record -> respond verified/failed
        │            │
        │            ▼
        │     Client re-reads (Phase 28 D-14 pattern) -> reports verified or failed
        │
        └──► REJECT: POST hubspot/review/decision
                { object_type, record_id, decision: "reject", reason }
                     │
                     ▼
              n8n workflow: direct property write, NO merge/candidate logic touched:
                lv_enrichment_review_reason = <operator's rejection text>
                (lv_enrichment_needs_review, lv_icp_needs_review,
                 lv_enrichment_review_candidate_json all left exactly as-is — D-10)
                     │
                     ▼
              HubSpot PATCH (same ALLOW_HUBSPOT_REVIEW_WRITES gate) -> verified/failed
```

### Recommended Project Structure

No new top-level structure. Backend addition lives in `n8n/` (new webhook path on `wf_enrichment_cloud.json` or a dedicated small workflow, new Code node reusing `reviewApply.js`/`mergeCompanies.js`/`mergeContacts.js` via the same inline-require pattern those files already use) plus one new entry in `scripts/deploy_n8n_workflows.py`'s `_OVERLAY_FLAG_SPEC`. Client logic lives inside whatever `operator-claude-plugin/` layout Phase 23 establishes.

### Pattern 1: Reuse `reviewApply.js`'s compare-and-set core, don't fork it (D-05, REVIEW-02)

**What:** `reviewApply(candidateJson, refetchedProperties)` already does exactly the non-clobber check this phase needs: it re-fetches the live record, compares each held decision's frozen `current_value` against the live value, and — **all or nothing** — refuses to apply ANY field if even one has drifted (reports `stale: true`, leaves the record queued). This is the single-authority enforcement D-05 requires. The new synchronous endpoint should call this exact function (or a factored variant that also accepts a `humanStamp` object to merge into the returned patch), not write a second copy of the comparison logic.

**When to use:** Every approve decision, for both companies and contacts (a `reviewApplyContacts.js`-equivalent does not currently exist as a separate file — check whether `reviewApply.js`'s `allowedFields = Object.keys(DEFAULT_COMPANY_POLICY)` needs a contacts variant using `mergeContacts.js`'s policy object instead, since companies and contacts have different field policies).

**Example:**
```javascript
// Source: n8n/code/reviewApply.js (read directly, full file)
const { reviewApply } = require("./reviewApply");
const result = reviewApply(record.properties.lv_enrichment_review_candidate_json,
                            freshlyRefetchedProperties);
// result: { canonicalPatch, clearPatch, stale, reason }
// if (result.stale) -> respond "stale, re-review required", write nothing
// else -> PATCH canonicalPatch + clearPatch + a NEW human-provenance merge (see Pattern 2)
```
[VERIFIED: `n8n/code/reviewApply.js`, full file read; `tests/n8n/reviewLoop.test.mjs` exercises exactly this contract]

### Pattern 2: Human-source provenance stamp is an ADDITIVE merge into the existing blob, not a new property (D-08, corrected)

**What:** The real provenance blob (`lv_enrichment_provenance` / `lv_contact_enrichment_provenance`) is a flat JSON object keyed by field name. Nothing about its shape prevents adding a `reason` key to an entry, or overwriting a field's entry with a new one whose `source` is `"human"`. This is the mechanism that actually satisfies D-08's "no new audit schema is invented" — reusing the existing blob's *shape* — while accepting that the specific properties CONTEXT.md named do not exist.

**When to use:** On every approved field, immediately after `reviewApply`'s (or the equivalent contacts) compare-and-set passes cleanly.

**Example:**
```javascript
// Extends the existing entry shape (src/merge_policy.py source_metadata() /
// n8n/code/mergeCompanies.js's `entry` object) with one additive key: `reason`.
function humanProvenanceEntry(field, chosenValue, operatorReason) {
  return {
    [field]: {
      source: "human",
      confidence: 100,
      verified_at: new Date().toISOString(),
      validation_status: "human_approved",
      value: chosenValue,
      reason: operatorReason || "",
    },
  };
}
// Merge into the parsed lv_enrichment_provenance object (parse -> Object.assign ->
// re-stringify with the SAME stableStringify() mergeCompanies.js already exports,
// so the blob's key-ordering convention is not broken).
```
[VERIFIED: entry shape from `src/merge_policy.py::source_metadata()` and `n8n/code/mergeCompanies.js`'s inline `entry` object, both read directly; `reason` is confirmed absent from the existing shape and additive]

### Pattern 3: A rejection is a direct write, never a merge call (D-10, REVIEW-05)

**What:** Because a rejection changes no candidate field, it cannot conflict with `manual_protected` or any other policy class — there is nothing to gate through `reviewApply`. It is a plain HubSpot PATCH of exactly one property: `lv_enrichment_review_reason` set to the operator's stated text. `lv_enrichment_needs_review`, `lv_icp_needs_review`, and `lv_enrichment_review_candidate_json` are **not touched**, so the record stays exactly where the queue found it, satisfying D-10 literally.

**When to use:** Every reject decision.

**Anti-pattern to avoid:** Do not route a rejection through `reviewApply.js` "for consistency" — that function's only two outcomes are "apply the candidate" or "mark stale," neither of which is "leave everything alone but record why." Forcing rejection through it would either wrongly apply a value the operator just rejected, or require bolting an unused third branch onto a well-tested function.

### Anti-Patterns to Avoid

- **Polling for the write-back result.** `Review Trigger (15 min)` is the *existing* scheduled loop — it is not this phase's job to piggyback on it for a conversational decision. The conversational path needs its own synchronous endpoint; reusing the 15-minute scheduled workflow directly would silently break Phase 28's confirm-then-verify pattern (D-13/14/15), which 30-CONTEXT.md explicitly imports for this phase.
- **Inventing flat `<field>_source` properties to satisfy CONTEXT.md's literal wording.** Adding new HubSpot properties to match a spec that was never actually built would fork the provenance model into two conventions (the blob everything else uses, plus a new flat set only this phase writes) — exactly the drift D-07 was written to prevent, just at the schema level instead of the policy level.
- **Reusing `ALLOW_HUBSPOT_RECORD_WRITES` for review writeback.** D-02 is explicit that arming dispatch must not arm review writeback. Gating the new endpoint behind the same flag dispatch already uses would make that decision false at the backend, regardless of how carefully the client tracks two "separate" conversation-scoped booleans.
- **Treating `conflicts` (see Open Question 1) as if it were already stored.** `n8n/code/scoreEnrichment.js`'s `Merge Company` node computes a `conflicts` array (multi-provider disagreement, `{field, chosen, chosen_source, candidates}`) for `lv_revenue_band`/`lv_employee_band`, but grep across every Code node in `wf_enrichment_cloud.json` shows it is never referenced again after `Merge Company` — it is computed and then dropped. Do not plan a "read the stored conflict list" task assuming this data survives past that one execution; it does not, today.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Non-clobber compare-and-set on apply | A new staleness-check function | `n8n/code/reviewApply.js`'s existing logic, called synchronously instead of from the 15-min poll | Already correct, already tested (`tests/n8n/reviewLoop.test.mjs`), and is the ONE place D-05 wants this rule to live — a second copy is exactly what D-05 forbids |
| `manual_protected` enforcement | A field-level guard inside the review endpoint | Nothing — it's already enforced upstream: `mergeCompanies`/`mergeContacts` never let a `manual_protected` field resolve to `needs_review`, so it can never appear in the candidate JSON this phase reads | The gate that matters already ran before the record entered the queue; re-checking it here would be the second policy authority D-07 explicitly rejects |
| Stable JSON serialization for the provenance blob | A new stringify helper | `stableStringify()`, already exported from `n8n/code/mergeCompanies.js` (sorted keys, compact separators, `ensure_ascii=False`-equivalent) | Byte-parity with the Python oracle and every other writer of this blob depends on this exact function; a second serializer risks silent key-order drift |
| Detecting whether a field is `manual_protected` for display (D-06) | A parser for the field-policy YAML shape | `config/field_policy.yaml`'s `class` key, read directly (`yaml.safe_load` or a JS YAML parser already used elsewhere in the repo) | The schema is trivial (flat `field: {class, ...}` map) — no need for anything beyond a plain YAML load |

**Key insight:** almost everything the *enforcement* half of this phase needs already exists and is tested — `reviewApply.js` plus `mergeCompanies.js`/`mergeContacts.js` together already form the complete non-clobber engine this phase must not re-implement. The only genuinely new backend work is (1) making that engine callable synchronously from a webhook instead of only from a 15-minute poll, and (2) adding the human-provenance stamp it currently never writes.

## Common Pitfalls

### Pitfall 1: Assuming the 15-minute scheduled loop already satisfies REVIEW-02/REVIEW-03
**What goes wrong:** Planning "the operator sets `lv_enrichment_review_approved=true` and the existing scheduler applies it" as the write path. This technically reuses existing code, but it cannot satisfy D-13/14/15 (consequence stated, explicit confirmation, re-read and report verified/failed) because the apply might not happen for up to 15 more minutes after the operator confirms — there is nothing to read back yet.
**Why it happens:** The existing mechanism looks like a complete review-apply loop, and it is — for the HubSpot-UI-driven flow CLAUDE.md §22 describes, which was never conversational.
**How to avoid:** Build the new synchronous endpoint (§"The writeback endpoint"); the scheduled loop can stay as a backstop for `approved=true` records the plugin didn't apply itself, but is not this phase's primary write path.
**Warning signs:** A plan whose "verify" step is "wait 15 minutes and check again."

### Pitfall 2: Believing the `<field>_source`/`_confidence`/`_evidence_url` convention exists per-field
**What goes wrong:** Planning a task to "stamp `lv_org_type_source = human`" — that property does not exist and creating it forks the provenance model.
**Why it happens:** Root `CLAUDE.md` §6 describes exactly this convention in detail, and 30-CONTEXT.md's canonical_refs cites it as already-existing.
**How to avoid:** Target `lv_enrichment_provenance`/`lv_contact_enrichment_provenance`'s per-field JSON entries instead (§"Corrections" above).
**Warning signs:** A HubSpot property-creation task appearing inside what should be a pure-logic phase.

### Pitfall 3: Losing the machine's "why review was needed" reason on rejection
**What goes wrong:** `lv_enrichment_review_reason` is the ONE textarea property available, and it is currently written by the *pipeline* to explain why a record needed review (e.g. "Best confidence 62 below threshold 80"). If a rejection overwrites it with the operator's rejection text, the original machine reason is gone — which may be fine (the record is about to be re-reviewed anyway) but the planner should decide this deliberately, not by accident.
**Why it happens:** There is only one review-reason property; nothing distinguishes "why the pipeline flagged it" from "why the human just rejected it."
**How to avoid:** Either accept the overwrite (simplest, and arguably correct — the operator's own words now explain the record's state) or, if both are wanted, note this needs `lv_enrichment_review_candidate_json`'s existing per-decision `reason` field (machine reason, per field) as the retained original, and reserve `lv_enrichment_review_reason` for the human's text going forward. Flag this as a Claude's-Discretion item for the plan, not a blocker.
**Warning signs:** A UAT check that expects to see BOTH the original conflict reason and the operator's rejection reason in the same single property.

### Pitfall 4: Expecting true multi-provider "who said what" for every conflict
**What goes wrong:** D-11 asks for "the competing values, which source said what" — but by the time a field reaches `needs_review`, the pipeline has already resolved to ONE candidate value + ONE `source_provider` + a `reason` string (e.g. "Best confidence 62 below threshold 80" or "Refresh candidate requires review in MVP"). True multi-provider disagreement data (`ranked[field]`, every scored candidate with its source) exists transiently inside `scoreEnrichment.js`'s `scoreCandidates()` output and is even assembled into a `conflicts` array inside `Merge Company`'s node — but that array is never referenced by any downstream node and is not persisted anywhere retrievable.
**Why it happens:** The merge model is single-candidate-per-call by design (see `mergeCompanies(existingProps, candidateRow, ..., opts.source)` — one `source` string applies to the whole call, not per provider).
**How to avoid:** Build the plain-language rendering around what IS stored (`source_provider`, `confidence`, `reason`, `evidence_url`, `validation_status`, plus `lv_icp_score_breakdown`/`lv_anti_icp_reason` for ICP-specific narrative) rather than assuming a multi-provider diff table is available. See Open Question 1 for the option of persisting `conflicts` as a small, cheap backend addition if the planner decides true multi-source rendering is load-bearing.
**Warning signs:** A UI mock showing "ZoomInfo: $65M / Apollo: $12M / Lusha: no match" side by side for a field where the stored data only ever names one `source_provider`.

## Code Examples

### The real candidate-JSON shape a review record carries (companies)
```javascript
// Source: n8n/code/mergeCompanies.js:224-235 (decisions[] entry), filtered to
// decision === "needs_review" and stableStringify()'d into
// lv_enrichment_review_candidate_json by the ENRICH_DECIDE_CO_CLOUD producer
// (per n8n/code/reviewApply.js's own consumer-contract comment).
{
  field: "lv_org_type",
  current_value: "broadcaster",
  chosen_value: "governing_body_league",
  source_provider: "claude_web",
  decision: "needs_review",
  confidence: 60,
  reason: "Best confidence 60 below threshold 80.",
  validation_status: "human_review_required",
  evidence_url: "https://example.org/about",
  verified_at: "2026-07-30T05:12:00.000Z",
}
```

### The real provenance-blob entry shape (companies and contacts, current state)
```javascript
// Source: src/merge_policy.py::source_metadata() / n8n/code/mergeCompanies.js's
// inline `entry` object — the ONLY per-field metadata shape that exists today.
// NOTE: no verified_by_model key exists in either language's implementation.
{
  "lv_org_type": {
    "source": "claude_web",
    "confidence": 60,
    "verified_at": "2026-07-30T05:12:00.000Z",
    "validation_status": "human_review_required",
    "value": "governing_body_league",
    "evidence_url": ["https://example.org/about"]
  }
}
```

### Field-policy display lookup (D-06) — the real schema to read
```yaml
# Source: config/field_policy.yaml (full file read)
companies:
  domain:
    class: manual_protected     # <- this is the ONE key the client needs for D-06
    promote_to_canonical: false
    stage_only: true
    min_confidence: 95
```

## State of the Art

| Old Approach (root CLAUDE.md's generalized spec / 30-CONTEXT.md's canonical_refs) | Current Approach (as actually built) | When Changed | Impact |
|---|---|---|---|
| Flat `<field>_source`/`<field>_confidence`/`<field>_evidence_url`/`<field>_verified_at`/`<field>_verified_by_model`/`<field>_validation_status` properties per field | One JSON blob per object (`lv_enrichment_provenance` / `lv_contact_enrichment_provenance`), one entry per field, no `verified_by_model` key | Phase 15 (per `src/merge_policy.py`'s own header comment) | D-08 must target the blob, not invent flat properties |
| Human review applied via HubSpot UI, unspecified mechanism | `reviewApply.js` + `Review Trigger (15 min)` scheduled poll, fully coded and tested | Phase 16-02 | The enforcement engine already exists; this phase's real gap is making it synchronous and adding the human stamp |
| "the CRM records that a person decided" implies human-source provenance already flows | No code path currently ever writes `source: "human"` anywhere | Never implemented | This phase is where that first gets built, not merely surfaced |

**Deprecated/outdated:** none of root `CLAUDE.md`'s §6/§22/§23 wording should be treated as implemented fact for this phase — cross-check every property name against `config/hubspot_properties.yaml` and every mechanism against `n8n/code/*.js` first, exactly as Phase 27's research had to.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A new webhook (`hubspot/review/decision`) and a new baked flag (`ALLOW_HUBSPOT_REVIEW_WRITES`) are legitimate backend work for this phase, mirroring the precedent Phases 25/27 already set for `hubspot/backend-status` | Summary, Architecture Patterns | If the planner instead insists on zero backend changes, D-01/D-02's "separate gate" and D-13/14/15's synchronous verify cannot both be satisfied — this needs an explicit decision, not a silent scope cut |
| A2 | Overwriting `lv_enrichment_review_reason` with the operator's text on rejection (rather than preserving the machine's original review reason elsewhere) is acceptable | Pitfall 3 | If the machine's original reason must be preserved for audit, a second field or a structured append is needed — flagged as discretion, not resolved here |
| A3 | `reviewApply.js`'s all-fields-in-one-record all-or-nothing apply model is acceptable for a conversational per-field "approve this one, not that one" UX, or the plan will present record-level (not field-level) approve/reject | Architecture Patterns, Pitfall 4 | If the operator genuinely needs field-granular approve/reject within one record, `reviewApply.js`'s contract (all held decisions apply together, or none do) does not support that without a real code change beyond adding a human stamp |
| A4 | A contacts-side equivalent to `reviewApply.js`'s `DEFAULT_COMPANY_POLICY`-keyed allowlist (built against `mergeContacts.js`'s own policy object) needs to be written new, since no `reviewApplyContacts.js`-shaped file currently exists | Pattern 1 | If contacts review-apply is planned as "reuse `reviewApply.js` directly," it will silently allow/reject the wrong field set (it currently imports `DEFAULT_COMPANY_POLICY` specifically) |

## Open Questions

1. **Can "which source said what" (D-11) be satisfied literally, or only approximately?**
   - What we know: the merge model resolves to ONE `source_provider` + `reason` string per flagged field by the time a record reaches `needs_review`. True multi-provider disagreement data (`ranked[field]`, `conflicts` array) is computed transiently in `scoreEnrichment.js`/`Merge Company` but never persisted or referenced again [VERIFIED: grep for `.conflicts` across every Code node in `wf_enrichment_cloud.json` returns zero downstream consumers].
   - What's unclear: whether the planner should (a) render D-11 using only what's stored today (single source + reason + confidence + evidence), which is a smaller lift and needs no backend change, or (b) add a small backend change to persist the already-computed `conflicts` array (cheap — it already exists in memory, just needs a serialization + a property or a slot inside `lv_enrichment_review_candidate_json`) so genuine multi-provider disagreement can be shown for the two fields (`lv_revenue_band`, `lv_employee_band`) where it's computed.
   - Recommendation: (a) for the first pass — it satisfies the literal requirement's spirit ("which source said what" = the one source that proposed the value now under review, and why it wasn't auto-promoted) without new backend surface area; flag (b) as a fast-follow if user testing shows operators specifically need to see the provider disagreement CONFLICT_WATCH already detects.

2. **Does the synchronous review-decision endpoint replace the 15-minute scheduled loop, or run alongside it?**
   - What we know: the scheduled loop (`Review Trigger (15 min)` → `Review Search (approved=true)` → `Apply Review` → `Review Apply Update`) already exists, is tested, and applies any record where `lv_enrichment_review_approved=true`. A new synchronous endpoint doing the same apply logic would make that record's flags already-cleared by the time the next scheduled tick looks for it (harmless — the search would just find nothing).
   - What's unclear: whether the scheduled loop should be left as a backstop (catches a record approved through some other path, e.g. a stray manual HubSpot edit) or whether this phase's plan should note it as now-redundant-but-harmless.
   - Recommendation: leave the scheduled loop untouched (it costs nothing to leave running and is a legitimate backstop for non-conversational approval), and have the new synchronous endpoint be the ONLY path this phase's client uses.

3. **Where does the queue's per-record read (REVIEW-01) actually come from — an extension of `hubspot/backend-status`, or a new sibling endpoint?**
   - What we know: Phase 27 already reads a review-backlog *count* through `hubspot/backend-status`; 27-RESEARCH explicitly deferred "review-queue detail and resolution" to this phase.
   - What's unclear: whether the count-only endpoint should grow a detail mode (e.g. `?detail=true` returning the flagged records' candidate JSON/provenance), or whether a dedicated `hubspot/review/queue` GET-equivalent (POST with headerAuth, per this repo's convention — n8n Cloud webhooks are POST-only in this repo's existing pattern) is cleaner.
   - Recommendation: extend the existing status endpoint's HubSpot Search branch to optionally return full row detail for the review-backlog query (it already runs that search for the count; returning the matched properties too costs nothing extra), consistent with the "one endpoint grown twice" pattern the ROADMAP already established for `hubspot/backend-status` between Phases 25 and 27.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `n8n/code/reviewApply.js`, `mergeCompanies.js`, `mergeContacts.js` | REVIEW-02 non-clobber reuse | Yes — present, tested | n/a (repo code) | None needed |
| `tests/n8n/reviewLoop.test.mjs` harness (`node --test`) | Validation of the reused/extended apply logic | Yes | Node's built-in test runner | None needed |
| A deployed `ALLOW_HUBSPOT_REVIEW_WRITES`-style baked flag | D-01/D-02 backend-level separate gate | **Not yet built** — must be added to `scripts/deploy_n8n_workflows.py`'s `_OVERLAY_FLAG_SPEC` | n/a | None — this is required new backend work, not optional |
| `operator-claude-plugin/` runtime | All client-side rendering/dispatch of review decisions | Not yet decided (Phase 23 not yet built, same finding as 27-RESEARCH) | — | Plan client-side logic runtime-agnostically |

**Missing dependencies with no fallback:** the new baked flag and new webhook endpoint are required backend work for this phase — there is no way to satisfy D-01/D-02's "separate gate" or D-13/14/15's synchronous verify without them.

**Missing dependencies with fallback:** none beyond the above.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `node --test` for n8n Code-node logic (mirrors `tests/n8n/reviewLoop.test.mjs`'s existing pattern); `.venv/bin/python -m pytest` for any Python-oracle-side parity test; plugin-side framework undecided pending Phase 23 |
| Config file | none dedicated |
| Quick run command | `node --test tests/n8n/reviewLoop.test.mjs tests/n8n/mergeCompanies.test.mjs` (adjust to whatever new test file this phase adds) |
| Full suite command | `.venv/bin/python -m pytest && node --test tests/n8n/*.test.mjs` (per this repo's documented dual-runner convention) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REVIEW-01 | Queue render pulls real fields (`lv_enrichment_review_candidate_json`, `lv_enrichment_provenance`) and renders plain language, not raw JSON | unit (client-side, mocked backend response) | plugin-runtime-dependent | ❌ Wave 0 |
| REVIEW-02 | New synchronous apply reuses `reviewApply`'s compare-and-set; a `manual_protected` field is never present in a needs_review candidate to begin with (regression guard) | unit | `node --test tests/n8n/reviewDecisionEndpoint.test.mjs -x` (new file) | ❌ Wave 0 |
| REVIEW-03 | Ungated request shows the exact write, sends nothing (no HubSpot PATCH attempted) | unit | same new test file, "ungated" case | ❌ Wave 0 |
| REVIEW-04 | Approve path adds a `source: "human"` / `validation_status: "human_approved"` entry with the operator's reason into the provenance blob, alongside the existing clearPatch | unit | same new test file, "human stamp" case | ❌ Wave 0 |
| REVIEW-05 | Reject path writes only `lv_enrichment_review_reason`; `lv_enrichment_needs_review`/`lv_icp_needs_review`/`lv_enrichment_review_candidate_json` are provably unchanged | unit | same new test file, "reject leaves flags" case | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** the quick run command above.
- **Per wave merge:** full suite command.
- **Phase gate:** full suite green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/n8n/reviewDecisionEndpoint.test.mjs` — new synchronous apply logic: stale-refuses-all, human-stamp-added-on-clean-approve, reject-touches-only-the-reason-field, ungated-writes-nothing.
- [ ] A contacts-side companion to `reviewApply.js`'s allowlist (or a parameterized version accepting either `DEFAULT_COMPANY_POLICY` or `mergeContacts.js`'s policy object) — currently `reviewApply.js` hardcodes the companies policy import (A4 above).
- [ ] Plugin-side test framework itself does not exist yet (Phase 23 not built) — client-side rendering/queue logic needs whatever harness Phase 23 establishes.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | yes | New webhook uses the same headerAuth secret convention as `hubspot/enrichment/event`; no new auth mechanism |
| V3 Session Management | yes | Review-writeback arm state is conversation-scoped client state (mirrors CONTROL-04's pattern), backed by a real backend flag so a stray call after "disarm" still can't write |
| V4 Access Control | yes | The new endpoint must refuse any `object_type`/`record_id` combination outside what the review queue itself surfaced — do not accept an arbitrary record_id and blindly apply a client-supplied patch; only ever apply the record's OWN stored `lv_enrichment_review_candidate_json`, never an operator-typed value, per D-05/D-07 |
| V5 Input Validation | yes | The operator's free-text reason is stored verbatim into a HubSpot textarea property — treat it as untrusted text at rest (no execution context), but do not allow it to be interpreted as anything other than display text anywhere downstream |
| V6 Cryptography | n/a | No new secret material |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Client-supplied field/value bypassing the stored candidate (operator or a compromised client tries to write an arbitrary value, not just approve/reject the stored one) | Tampering | The new endpoint must only ever apply `lv_enrichment_review_candidate_json`'s own stored `chosen_value` per field — it takes no field/value payload from the request at all, only `decision` (approve/reject) and `reason` (free text) |
| A rejection accidentally clearing review flags (silent data loss of the queue's own bookkeeping) | Tampering / Repudiation | D-10's explicit rule; the reject code path must be reviewed to touch exactly one property |
| Reusing the dispatch arm flag for review writes, collapsing two intentionally-separate authorities into one | Elevation of Privilege | D-02's explicit separate-flag requirement; verify at code-review time that the new endpoint's write gate checks a DIFFERENT literal than `ALLOW_HUBSPOT_RECORD_WRITES` |

## Sources

### Primary (HIGH confidence)
- `config/hubspot_properties.yaml` — read directly, full file; confirms every real `lv_`-prefixed review property on both companies and contacts.
- `config/field_policy.yaml`, `config/source_registry.yaml` — read directly, full files.
- `src/merge_policy.py` — read directly, full file; Python oracle's provenance model and its own header comment documenting the Phase 15 blob shape.
- `n8n/code/reviewApply.js`, `n8n/code/mergeCompanies.js`, `n8n/code/scoreEnrichment.js`, `n8n/code/providerSelection.js`, `n8n/code/normalizeProviders.js` — read directly.
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_scheduled_maintenance_cloud.json` — inspected via `python3 -c "json.load(...)"` for node names, jsCode bodies, webhook paths, and cross-references (`.conflicts` grep across all Code nodes).
- `tests/n8n/reviewLoop.test.mjs` — read (head), confirms the producer-consumer contract for `lv_enrichment_review_candidate_json`.
- `scripts/deploy_n8n_workflows.py` — grepped for `_OVERLAY_FLAG_SPEC`/`enable_baked_flags`, confirming the flag-overlay mechanism this phase's new flag must extend.

### Secondary (MEDIUM confidence)
- `.planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-RESEARCH.md` — prior finding that root `CLAUDE.md`'s generic property names diverge from this repo's real `lv_`-prefixed schema; this research extends the same finding to the review-flow properties specifically.
- `.planning/workstreams/plugin-entrypoint/phases/28-control-actions/28-CONTEXT.md` — the confirm-then-verify (D-13/14/15) and arm/disarm (D-01/D-02) machinery this phase's review-writeback gate must satisfy.

### Tertiary (LOW confidence)
- Root `CLAUDE.md` §6, §22, §23 — used only to identify what was aspirational and never built; every property name and mechanism from these sections was cross-checked against `config/hubspot_properties.yaml` and the deployed workflow/code files before being trusted, and in every case where they diverged, the deployed reality is what this document reports.

## Metadata

**Confidence breakdown:**
- Real property names and provenance-blob shape: HIGH — read directly from deployed config and code, cross-confirmed between the Python oracle and the JS implementation.
- Non-clobber enforcement reuse path (`reviewApply.js`): HIGH — existing, tested code; contract read in full.
- New endpoint/flag design (approve/reject synchronous webhook): MEDIUM — sound and consistent with this milestone's established "one endpoint grown twice" precedent, but is a design recommendation, not yet-built code; the planner should treat the endpoint shape as a strong default, not an unchangeable spec.
- Multi-provider "which source said what" (D-11 literal satisfaction): MEDIUM — the limitation is HIGH confidence (verified via grep that `conflicts` has no downstream consumer), but the right resolution (Open Question 1) is a judgment call for the planner/user.

**Research date:** 2026-07-30
**Valid until:** 30 days for the schema/code findings (stable, this repo's own committed state); re-verify sooner if `config/hubspot_properties.yaml` or `n8n/code/mergeCompanies.js`/`mergeContacts.js`/`reviewApply.js` change before this phase is planned.
