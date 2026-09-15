# Phase 73: GA fix list from stress attempt 2 - Research

**Researched:** 2026-09-15
**Domain:** n8n Cloud workflow builder (`scripts/build_cloud_workflows.py` + `n8n/code/*.js`) and the `operator-claude-plugin` Python client, closing 8 findings from a live stress-test session
**Confidence:** HIGH for 7 of the 8 findings — every claim was checked by reading the actual source this session (file:line cited), not from training memory. **F-A6 is MEDIUM** — its graph-wiring fix has no existing precedent in this codebase to copy (see Pitfall 0 below, added after advisor review found the initial design would silently corrupt company associations on a real batch failure), and its live proof is entangled with F-A5 in a way that needs an explicit plan-time decision. Two other items (n8n's `continueErrorOutput` item shape's exact field names; whether F-B6 is a wiring bug vs. a deploy-parity gap) could not be fully resolved by static reading and are flagged `[ASSUMED]`/Open Questions rather than guessed at.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Ingest create containment (F-A6 + F-A5)**
- D-73-01: Ingest `HubSpot Create` gets `onError: continueErrorOutput` — the failed item leaves on the node's ERROR output and becomes a `create_failed` refusal row carrying HubSpot's message; successful creates continue to `HubSpot Associate Company` and the ingest response. NOT `continueRegularOutput` — the error branch is a distinct output routed to a refusal, never to the association or the success ack. Reversibility: costly (needs its own carry Merge/sentinel).
- D-73-02: No orphan-repair tool. Per-item continue means every successful create associates in-lane. `uat_reset.py` covers UAT leftovers. Not a sweep condition.
- D-73-03: Duplicate CSV rows collapse in the PLUGIN pre-flight (`extraction.py`/`preingest.py`), on the identity rule already used by `extraction.dedupe` (casefolded, trimmed: email; then firstname+lastname+company; then linkedin_url). Preview shows the collapse. Backend `Decide Action` is NOT given a second dedupe.
- D-73-04: First occurrence wins. The losing row gets outcome `duplicate_in_csv` naming the winner's row id. No field merge, no batch refusal.
- D-73-05: Both mechanisms ship: dedupe prevents the known 409, the error output contains any other 409 (race, pre-existing contact the search missed).

**Company match + freemail (F-B7 + F-B3)**
- D-73-06: Companies-branch `HubSpot Company Search` (`HS_CO_SEARCH_BODY_EXPR`) matches `domain` with operator `IN` over `[bare, "www." + bare]` in ONE search. The request domain is stripped of a leading `www.` before the pair is built. Stored portal domains are NOT normalised. Apply the same pair wherever the lane searches companies by domain (ingest `HubSpot Company Search by Domain` included — `uat_reset.py --snapshot` already queries both forms; the two must agree).
- D-73-07: F-B2 stays OUT: name + TLD variants remain a documented known gap; the stress CSV keeps its Perth Racing row on purpose.
- D-73-08: Freemail refuses in BOTH engines: plugin domain clean at preview (`company_domain.py`/`enrichment.py` using the parity-tested `FREEMAIL_DOMAINS`) and `Decide Company Action` refusing a create whose domain is freemail. Single source stays `n8n/code/companyLink.js::FREEMAIL_DOMAINS` (JS authoritative, Python mirrored, existing parity test extended if the set changes).
- D-73-09: A freemail-domain company row becomes `review` with reason "freemail domain — supply the real website". Never skip, never create without domain.

**Review approve (F-E1)**
- D-73-10: `Apply Review` (reviewApply wrapper in `scripts/build_cloud_workflows.py`) applies the same array→semicolon-join choke point the enrichment lane already has (`if (Array.isArray(properties[k])) properties[k] = properties[k].join(";")`) before the PATCH. Mechanical; Claude's discretion on whether to extract one shared helper.

**Plugin report truth (F-B5 + folded todo)**
- D-73-11: `run_report` reads enrich/update outcomes from the settled execution's runData — `Decide Company Action` and `HubSpot Company Update` node outputs (the D-70-05 channel `written_records` already uses for creates) — joined by `row_id`, falling back to `hs_object_id`.
- D-73-12: Research-node rows join by `hs_object_id` when `row_id` is absent; they land in their company's bucket, never `unjoinable`.
- D-73-13: Proof before attempt 3: a frozen, secret-redacted runData fixture from executions `12434`/`12449` asserting 24 updates + 11 creates + 1 skip with zero "unaccounted". Redact the Webhook Trigger headers block (memory: `n8n-rundata-carries-webhook-secret`).
- D-73-14 (folded todo): `run_manifest` is scoped per run — step 5 of `enrich-before-ingest` starts from `run_manifest_path(run_id)` (or `{}`), never the accumulated shared file; the report counts only entries carrying THIS `run_id`.

**Throttle, cost envelope, balances (F-A3r, F-A1/A2/B1/B6)**
- D-73-15: `_INGEST_SEARCH_BATCH_INTERVAL_MS` 250 → **400 ms** (2.5 req/s, 50% headroom under HubSpot's 5 req/s account-wide search cap; 48-row send ≈ 58 s over the three search nodes). No `retryOnFail` added.
- D-73-16: `cost_guard` gets a per-LANE rate + execution model, and `plan_grant` reads the lane: `contact-upload` = 0 provider credits, 1 execution per POST (+ the association hop's own count if any); `companies` = 2 Lusha credits per company (measured); `enrich-before-ingest` keeps the contact rates. The rate table stays dated and deliberately over-stating within a lane.
- D-73-17: F-B6: the backend-status workflow (`wf_backend_status_cloud`) reads Lusha `credits.remaining` and ZoomInfo GTM balance (needs `Accept: application/vnd.api+json`) using the already-provisioned credentials; Apollo stays `null`/unknown (key is not a master key → 403). The plugin spend guard bounds on Lusha/ZoomInfo and reports Apollo as unknown. Memory: `provider-credit-check-endpoints`. Reversibility: reversible — read-only nodes on the status lane.
- D-73-18: One deploy: regenerate every changed cloud JSON once, operator deploys + bounces disarmed, resets, runs attempt 3 A–F. No staged ingest-first deploy.

### Claude's Discretion
- Exact shape of the `create_failed` refusal row and where the error-output carry Merge/sentinel sits (must satisfy the walker: `node --test tests/n8n/*.test.mjs`).
- Whether the semicolon-join becomes one shared helper or a copied choke point.
- Preview wording for `duplicate_in_csv` and the freemail review reason.
- F-B4 (name-only company row → `domain EQ ""` 400): fold ONLY if it is a one-line reason fix inside the same `Decide Company Action`/search body already being edited for D-73-06 and a ruling is taken at plan time (CLAUDE.md §31 rule 3); otherwise stays deferred.

### Deferred Ideas (OUT OF SCOPE)
- F-B2: name + TLD variant company duplicates (Perth Racing) — needs fuzzy name/TLD logic; own phase or ruling.
- F-B4: name-only company rows produce `domain EQ ""` 400 then `skip` — deferred unless folded at plan time under §31 rule 3.
- Orphan-association repair script / sweep condition — rejected for this phase (D-73-02).
- Retry-on-429 for the ingest search nodes — rejected in favour of the wider interval.
- Handoff tasks 8–12 (deploy + bounce + reset + attempt 3 is this phase's gate; clean-machine install test; real-data demo recording; `/gsd-debug continue` archive; plugin 0.50.0 bump + `/gsd-complete-milestone`).
</user_constraints>

<phase_requirements>
## Phase Requirements

This is a standalone GA fix-list phase, not part of the v1.2 "Yield and Friction" milestone's tracked `REQUIREMENTS.md` (which covers Phases 64–69's LADDER/RICH/AUTO/FLOW/HELD requirement families only — none of those IDs apply here, same pattern as Phase 72). No formal `REQ-XX` IDs exist for Phase 73. The phase description itself supplies the tracking unit — the finding id — so the table below is that mapping.

| Finding | Description | Research Support |
|---------|-------------|------------------|
| F-A6 | ingest `HubSpot Create` has no continue-on-error | §"F-A6" below: exact node/wiring, `_hs_http_create_node`, existing carry-merge/sentinel idiom to reuse, walker gap |
| F-A5 | duplicate CSV rows not collapsed pre-create | §"F-A5" below: `extraction.dedupe()` vs D-73-04's semantics conflict; `rows_from_table`/`preview.py` gap |
| F-E1 | review approve sends array candidates raw | §"F-E1" below: the REAL choke point is `reviewApply.js`, not the two lines the phase description points at |
| F-B7 | `domain EQ bare` misses `www.`-stored records | §"F-B7" below: exact node, exact fix (mirrors an existing `linkedin_url_variants` IN-filter precedent) |
| F-B3 | freemail accepted as company domain | §"F-B3" below: zero refusal exists today in `Decide Company Action`; `FREEMAIL_DOMAINS` already correct and reusable |
| F-B5 | plugin run report can't see enrich/update outcomes | §"F-B5" below: `written_records.classify_item` already supports enrich outcomes structurally — gap is elsewhere, use D-73-13's frozen fixture to pinpoint |
| F-A3r | 250ms→400ms throttle | §"F-A3r" below: one-line constant change, zero existing test to extend (new test needed) |
| F-A1/A2/B1/B6 | cost envelope + balances | §"Cost envelope" and §"F-B6" below: `cost_guard.py` already has per-object_type provider rates; the gap is lane-blindness, not a missing rate table; F-B6's graph ALREADY probes all 3 providers — the defect is likely wiring/deploy-parity, not missing nodes |
</phase_requirements>

## Summary

All 8 findings are internal-code fixes inside a single repo whose n8n graphs are generated by one Python builder (`scripts/build_cloud_workflows.py`, 11,966 lines) and whose shared logic lives in `n8n/code/*.js`, inlined into Code nodes. No new external package is needed anywhere in this phase — every fix is a change to existing Python/JS in this repo, confirmed by exhaustive reading of the actual call sites (not the phase description's paraphrase of them, which in two cases points at the wrong code).

**Two corrections to the phase description worth flagging before planning starts.** First, F-E1's fix does **not** live at the two "existing choke point" lines (~2582, ~4610) the phase description names — those are the `Decide Action`/`Decide Company Action` nodes' own property-serialization steps, a different code path from the one that actually failed (`Review Decision Update`, fed by `reviewDecision.js::buildReviewDecision` → `reviewApply.js::reviewApply`). The root-cause fix is one line inside `reviewApply()`'s `canonicalPatch[d.field] = enumCheck.value` assignment, which automatically fixes **both** consumers (the operator-triggered `hubspot/review/decision` endpoint AND the 15-minute scheduled backstop `Apply Review` node) with no duplicated choke point. Second, F-B6's target workflow (`build_backend_status_cloud()`) **already has** working Lusha/Apollo/ZoomInfo usage-probe nodes, already wired end to end — this is not new-node work. The JS that turns those probes into `not_configured` is explicitly designed to never say that for a configured provider (`ENRICH_STATUS_CREDIT_REQUEST` unconditionally requests all three every time). The live `not_configured` result is either a wiring regression in the Phase-70 carry-merge chain between "Status Credit Request" and "Build Status", or — more likely given this repo's own recent history (§13.0.2 of CLAUDE.md) — a plain deploy-parity gap where the live workflow predates a fix already in the committed JSON. The planner's first D-73-17 task should be reading one live disarmed status POST's runData, not writing code.

**Primary recommendation:** Plan each finding as an independent, narrowly-scoped fix following the exact existing idiom its lane already uses (carry-merge + starved-lane sentinel for graph work; module-level pure functions with `node --test` coverage for JS; small Python functions with pytest for the plugin) — this repo has zero tolerance for hand-wiring workarounds. Most of this phase's mechanisms (IN-filter variant sets for F-B7, freemail refusal for F-B3, first-wins-tag dedupe for F-A5, the run_manifest scoping already built for D-73-14, a one-line root-cause fix for F-E1) already have a working precedent elsewhere in this exact file/module to copy. **F-A6 is the one exception, and it is the highest-risk item in this phase**: its naive design (route the HTTP error output through the SAME `wire_gate_refusal_lane`/carry-merge idiom every other new lane in this codebase uses) silently breaks the positional pairing `Build Association Request` depends on to associate a create's response with the right company — see Pitfall 0. Plan F-A6 last, with its own dedicated design step, not as a copy-paste of the other seven findings' pattern.

## Architectural Responsibility Map

This project's real tiers are n8n Cloud (orchestration backend, generated from `scripts/build_cloud_workflows.py`), the Operator Plugin (Python client, pre-flight + reporting), and HubSpot (CRM/store) — not a browser/SSR/API stack. Every capability in this phase maps as follows:

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Create-error containment (F-A6) | n8n Cloud | — | The `HubSpot Create` node and its response ARE the backend; the plugin only shows the ack, it never sees per-row create failure today |
| CSV duplicate collapse (F-A5) | Operator Plugin | — | D-73-03 locks this to the plugin pre-flight, deliberately not a second backend dedupe — the backend stays the single write authority, the plugin is the single input-hygiene authority |
| Review-approve serialization (F-E1) | n8n Cloud | — | `reviewApply.js`/`reviewDecision.js` are inlined Code-node JS; the plugin only calls the endpoint and shows the result |
| Domain-match widening (F-B7) | n8n Cloud | — | The search filter body lives in the builder; HubSpot's stored `www.` form is a CRM-tier fact the backend must reconcile |
| Freemail refusal (F-B3) | n8n Cloud | Operator Plugin | D-73-08 requires BOTH: backend `Decide Company Action` refuses (authoritative), plugin preview warns earlier (advisory, same source of truth) |
| Run-report accuracy (F-B5) | Operator Plugin | n8n Cloud | The plugin's `written_records`/`run_report` reads n8n's own runData as its ONLY source — no new backend field is being added, the plugin's own read/join logic is the suspect |
| Search throttle (F-A3r) | n8n Cloud | — | `options.batching` on an httpRequest node — pure backend graph config |
| Cost envelope + balances (F-A1/A2/B1/B6) | Operator Plugin | n8n Cloud | Estimation math lives in the plugin (`cost_guard.py`/`write_grant.py`); the raw balance numbers it needs come from the backend's `hubspot/backend-status` endpoint |

## Standard Stack

No new package in any ecosystem. This phase edits existing Python (repo root + `operator-claude-plugin/`) and JS (`n8n/code/*.js`, inlined — no npm runtime, no `require` outside the inlined modules' own sibling `require`s already present). `requirements.txt`/`operator-claude-plugin/requirements.txt` are unaffected.

## Package Legitimacy Audit

Not applicable — this phase installs zero external packages.

## Architecture Patterns

### Pitfall 0 (BLOCKING) — `continueErrorOutput` breaks `Create Carry Merge`'s positional pairing

**This must be resolved before F-A6's design is finalized — it is not a footnote.** `HubSpot Create`'s existing (and only) consumer today is `Create Carry Merge`, built by:
```python
# Source: scripts/build_cloud_workflows.py:1668-1671
splice_carry_merge_after(nodes, conns, "HubSpot Create", "HubSpot Create Write Gate IF",
                         merge_name="Create Carry Merge")
```
`splice_carry_merge_after` (docstring, `scripts/build_cloud_workflows.py:9862-9885`) builds a `mode="combine"`, `combineByPosition` Merge: input 0 is `HubSpot Create`'s own output, input 1 is the carried pre-write row (from the write gate's pass-through), and it explicitly documents that item count and order must agree "since they are two edges off the one wave that entered `http_name`." `Build Association Request`'s own comment (`scripts/build_cloud_workflows.py:671-680`) states this even more plainly: "No by-name read... no separate join-by-value search over a fetched list — the pairing already happened at the merge, and item count/order agree **by construction**."

`continueErrorOutput` breaks that construction. If `k` of `N` creates in a batch fail (routed to output index 1), `HubSpot Create`'s SUCCESS output (index 0) shrinks to `N-k` items, while `Create Carry Merge`'s OTHER input still delivers all `N` carried rows. Per n8n's own documented `combineByPosition` semantics — **[CITED: docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.merge]**, corroborated by community reports (Reddit/forum threads on "Merge node combine mode... silent data loss"): *the shorter input determines the output length, and the two lists are paired index-for-index* — if item 3 of 10 fails, the success array's item at position 3 onward is actually the response for row 4, 5, 6... paired against carried rows 3, 4, 5... Every create after the FIRST failure in a batch gets associated to the WRONG company. This is worse than the orphan-contact bug F-A6 is fixing (an unassociated contact is a visible gap; a wrongly-associated contact is a silent data-integrity error).

**This means `wire_gate_refusal_lane` (Pattern 1 below) is NOT a drop-in template for F-A6**, despite being the closest existing precedent. That idiom's refusal lane (a write-gate refusal) removes rows **before** the write node runs at all — the write node's own input/output stay 1:1 by construction. F-A6's refusal happens **after** the write node runs, changing its OWN output's item count relative to its own input. This is a structurally different problem the existing idiom does not solve.

**Correction — email IS in the create request body, which changes the best fix.** An earlier draft of this research claimed `email` is never sent on a create because it is `manual_protected`. That is wrong for the specific create path F-A6 touches: **BUG-19**, fixed independently in BOTH the ingest lane's own `DECIDE_CLOUD` (`scripts/build_cloud_workflows.py:920-923`: `if (row.email) properties.email = row.email;`) and the enrichment lane's `ENRICH_DECIDE_CLOUD` (`scripts/build_cloud_workflows.py:2526-2534`), seeds `properties.email` onto a create SPECIFICALLY so the by-email search can find it on a later run — "canonicalPatch never carries email (manual_protected — an UPDATE rule), so an unseeded create writes a contact the by-email search can never find." Live evidence confirms this reaches HubSpot: Stage D's read-only match found Stage A's ingest-lane creates by email, and the F-A6 409 error text itself ("Contact already exists. Existing ID: ...") is HubSpot's email-uniqueness rejection. The repo's own comment at `scripts/build_cloud_workflows.py:4665-4666` states the general rule directly: "HubSpot's create response echoes the properties it was given back."

**The companies branch has a related-but-not-identical precedent — read it precisely, don't over-claim it as a solved case.** `ADAPT_COMPANY_CREATE` (`scripts/build_cloud_workflows.py:4677-4689`, Phase 61 Plan 06 Task 2, REVIEW-C17) reads `merged.properties.domain` off the create response and re-exposes it as `company_dependency_id` so a DOWNSTREAM consumer (the client/report) can correlate a created company back to its planning row BY VALUE. But `ADAPT_COMPANY_CREATE` itself still reads that value off the SAME positionally-merged item `HubSpot Company Create Carry Merge` already paired — it does not itself perform a value-based join at the Merge boundary, it only prepares a value for one to happen later. It solves "let an external reader correlate by domain," not "guarantee this specific HTTP response item is paired with the RIGHT carried row inside this graph" — which is F-A6's actual problem. Do not cite this node as proof the pairing problem is already solved elsewhere in this codebase; it isn't.

Also worth flagging: CLAUDE.md §13.0.1 states `Build Association Request` "joins each write RESPONSE back to its row BY VALUE (update by `id`, create by `properties.email`)" — but the CURRENT `BUILD_ASSOCIATION_REQUEST` jsCode (read this session, `scripts/build_cloud_workflows.py:671-708`) does no such by-value join at all; it reads `row.id`/`row.email` straight off the single item the positional carry-merge already produced, and its own comment says so explicitly ("the pairing already happened at the merge... by construction"). Either §13.0.1 is stale prose describing a mechanism Phase 70's positional-merge refactor superseded, or there is a by-value join elsewhere this session did not find. **Flag this doc-vs-code discrepancy to the planner explicitly** — do not assume CLAUDE.md's description is current without re-checking it against the code at plan time.

**What the planner must verify/decide before implementation, given email IS confirmed present on both sides:**
1. The most directly evidenced fix: change `Create Carry Merge` from `combineByPosition` to n8n Merge v3.2's "Combine by Matching Fields" mode (`combineByFields`), matching the carried row's `email` (already read as a fallback in `BUILD_ASSOCIATION_REQUEST`'s existing code: `row.email || (row.properties && row.properties.email)`) against the HTTP response's `properties.email` (confirmed present per BUG-19 above). This survives any subset of rows failing, in any position, without relying on index alignment at all — the class of fix CLAUDE.md §13.0.1 describes (possibly stale, possibly the intended target state), not a new invention.
2. Verify n8n v3.2 Merge's field-mapping actually supports matching on two DIFFERENT field paths (`email` on one input, `properties.email` on the other) — if it requires identical field names on both inputs, a small Code-node normalization step before the Merge (flattening `properties.email` to a top-level `email` on the HTTP response side) may be needed first.
3. Do NOT pursue a `$('previous node').item`-style by-name single-item read as a fix — this is exactly the by-name addressing pattern Phase 70 (D-70-03/D-70-04) deliberately retired across this entire lane, and reintroducing it here would be a regression against that whole phase's own rule. Also note: n8n's `pairedItem` metadata is for RESOLVING an item's provenance inside `$()` expressions in a Code node — `combineByPosition` itself does not consume or repair pairing using `pairedItem`; it is not a fix on its own, only a possible ingredient if a Code-node-based join (reading both Merge inputs' full arrays via `$input.all()` on each branch and matching manually) is chosen over option 1's declarative field-match.

This is the single piece of F-A6 most worth a live disarmed proof before trusting the fix (a batch with a deliberate mid-batch failure, checking which company the LATER successful creates land associated to) — independent of, and in addition to, the walker-modeling gap in Pitfall 2 below.

### System Architecture Diagram

```
Operator (CSV / HubSpot record ids)
        │
        ▼
Operator Plugin (Python)
  preview.py / preingest.py ──► [F-A5: dedupe pre-flight] ──► dispatch.py (multipart POST)
  write_grant.py / cost_guard.py ──► [F-A1/A2/B1: lane-aware envelope]
        │
        ▼  webhook POST
n8n Cloud workflows (generated from build_cloud_workflows.py)
  LV Contact Ingest ──► HubSpot Search/Company Search ──► Decide Action
        │                                                     │
        │ [F-A3r: throttled 400ms]      [F-B7: IN domain variants, F-B3: freemail]
        ▼                                                     ▼
   IF Create ──► HubSpot Create ──► (success) Build Association Request
        │              │
        │        [F-A6: onError=continueErrorOutput, new refusal lane]
        │              ▼
        │        create_failed row ──► Ingest Merge Response ──► Build Ingest Response
        ▼
  LV Enrichment (companies branch) ──► Decide Company Action ──► HubSpot Company Update
        │                                                              │
        ▼                                                              ▼
  LV Review Decision ──► reviewDecision.js ──► reviewApply.js ──► [F-E1: array→string]
                                                                        │
                                                                        ▼
                                                              Review Decision Update (PATCH)
        │
        ▼  settled execution runData (read back, never the ack)
Operator Plugin
  written_records.py / run_report.py ──► [F-B5: join enrich/update rows by row_id/hs_object_id]
  wf_backend_status_cloud (already has Lusha/Apollo/ZoomInfo probes) ──► [F-B6: why not_configured?]
```

### Recommended Project Structure

No new files/directories. Fixes land in:
```
scripts/build_cloud_workflows.py   # node/filter/onError changes, regenerates n8n/wf_*.json
n8n/code/companyLink.js            # (read-only reference for FREEMAIL_DOMAINS; ingest-side fix is in the builder's CO_LINK_DOMAIN_SEARCH_BODY)
n8n/code/reviewApply.js            # F-E1 root-cause fix (array join)
operator-claude-plugin/scripts/{extraction,preingest,preview}.py   # F-A5
operator-claude-plugin/scripts/{written_records,run_report}.py     # F-B5 (diagnose via frozen fixture first)
operator-claude-plugin/scripts/{cost_guard,write_grant}.py         # F-A1/A2/B1
tests/n8n/*.test.mjs, tests/*.py, operator-claude-plugin/tests/*.py  # new/extended coverage
```

### Pattern 1: Carry-merge + starved-lane sentinel (F-A6's required idiom)

**What:** Any time a node gains a NEW output edge feeding a shared downstream Merge (e.g. an HTTP node's error output becoming a new "refusal row" lane), the graph needs (a) a `combine`-mode Merge splicing the node's real output with a "carried" copy of its input row (`splice_carry_merge_after`), and (b) a starved-lane sentinel so the shared Merge never hangs on an execution where that lane produced nothing (`_add_starved_lane_sentinel` → its own gate node, never wired directly to the Merge — see the `_sentinel_gate_js` docstring on why a direct wire double-counts under v1's "zero-item output is not a delivery" rule).

**When to use:** Exactly F-A6's shape — a new output/lane on an existing node that must reach `Ingest Merge Response` without starving the existing association/review lanes' own inputs, and without a fast empty marker beating a slow real delivery to the same Merge input (see `wire_gate_refusal_lane`'s own docstring for the exact failure this rule prevents — a refusal must get **its own** Merge input, never share one with a real lane's terminal).

**Example (existing precedent to copy, not hypothetical):**
```python
# Source: scripts/build_cloud_workflows.py:9862-9911 (splice_carry_merge_after)
#         scripts/build_cloud_workflows.py:10011-10102 (wire_gate_refusal_lane)
splice_carry_merge_after(nodes, conns, "HubSpot Update", "HubSpot Update Write Gate IF",
                          merge_name="Update Carry Merge")
# ... later, a refusal lane gets its OWN Merge input, never shares the write path's:
idx = _append_merge_input(nodes, conns, merge_name, f"{write_name} Write Gate IF",
                           source_out_idx=1)
```
F-A6's error output is structurally the SAME shape as a write-gate refusal (a distinct, low-frequency branch off a write node that must reach the same response Merge without racing the success path) — `wire_gate_refusal_lane` is the closest existing template, even though it was built for gate refusals rather than HTTP errors.

### Pattern 2: Precomputed variant-set + IN filter (F-B7's required idiom)

**What:** When a HubSpot search must match a value that can be stored in more than one normalized form, compute the full bounded variant list ONE step upstream (never inside the search filter expression itself) and filter with `operator: "IN", values: "={{ $json.<variants_field> }}"`.

**When to use:** F-B7 exactly — domain can be stored bare or `www.`-prefixed. This is not a new idiom for this codebase: Phase 61 already solved the identical shape for `lv_linkedin_url`/`hs_linkedin_url`.

**Example (existing precedent, verbatim structure to mirror for domain):**
```python
# Source: scripts/build_cloud_workflows.py:2083 (variant computed upstream)
linkedin_url_variants: linkedinUrlVariants(row.linkedin_url),

# Source: scripts/build_cloud_workflows.py:6818-6821 (IN filter over that variant field)
hs_linkedin_search = _hs_http_search_node(
    "HubSpot Linkedin Search", "contact", hs_search_x, lby,
    filter_groups=[
        [{"propertyName": "lv_linkedin_url", "operator": "IN",
          "values": "={{ $json.linkedin_url_variants }}"}],
        [{"propertyName": "hs_linkedin_url", "operator": "IN",
          "values": "={{ $json.linkedin_url_variants }}"}],
    ],
    properties_csv=ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV,
)
```
For F-B7 the equivalent is: in `ENRICH_BUILD_CO_IDENTITY` (`scripts/build_cloud_workflows.py:3042-3058`), which already computes a bare `domain` via `cleanDomain()` (already strips `www.` — **nothing to change there**), add `identity_keys.domain_variants: [domain, domain ? "www." + domain : null].filter(Boolean)`, then change the CLOUD lane's actual search node (`_hs_http_search_node("HubSpot Company Search", "company", ..., filter_groups=[[{"propertyName": "domain", "operator": "EQ", "value": "={{ $json.identity_keys.domain }}"}]], ...)` at `scripts/build_cloud_workflows.py:7126-7131`) to `operator: "IN", values: "={{ $json.identity_keys.domain_variants }}"`. Apply the identical pair to the ingest lane's `CO_LINK_DOMAIN_SEARCH_BODY` (`scripts/build_cloud_workflows.py:621-624`), which currently does raw `EQ` on `$json.company_search_domain` — that value is already bare (via `companyDomainForRow`/`cleanCompanyDomain`, which strips `www.`, `n8n/code/companyLink.js:56-65`).

**IMPORTANT — do NOT touch `HS_CO_SEARCH_BODY_EXPR` (`scripts/build_cloud_workflows.py:3088-3104`).** That constant belongs to `build_enrichment_local_live()` only (its own comment says so, and it is confirmed by grep — it has exactly one call site, inside that function). The CLOUD lane actually exercised by the stress test uses a **different** node built via `_hs_http_search_node(...)` inside `build_enrichment_cloud()` (line 7126) — editing the wrong constant would ship a fix that never runs live.

**This fix walks straight into F-B4 (currently deferred/out-of-scope) unless the planner takes a §31 rule-3 ruling.** A name-only company row has no domain at all, so `ENRICH_BUILD_CO_IDENTITY`'s `domain` is `null`, and `domain_variants: [domain, "www."+domain].filter(Boolean)` (or any equivalent) evaluates to `[]`. HubSpot's `IN` operator 400s on an empty `values` array exactly as its `EQ` operator 400s today on an empty string (F-B4's own live evidence: `domain EQ ""` → 400). **The same edit that fixes F-B7 will reproduce F-B4's failure shape one filter-type over, if the `.invalid`-sentinel guard the ingest lane already uses is not applied here too.** The ingest lane's own `BUILD_COMPANY_LINK` (`scripts/build_cloud_workflows.py:610`) already has the pattern to copy: `company_search_domain: companyDomainForRow(row) || "no-company-domain.invalid"` — an RFC 2606 sentinel that returns a clean 200/zero-hits instead of a rejected filter. The companies-branch `ENRICH_BUILD_CO_IDENTITY` needs the equivalent: when `domain` is null, `domain_variants` should be a one-element sentinel array (e.g. `["no-company-domain.invalid"]`), never `[]`. **Recommend the planner take the CLAUDE.md §31 rule-3 fold explicitly at plan time** (as CONTEXT.md's own "Claude's Discretion" section already anticipates for F-B4): this is a one-line addition to the SAME node already being edited for D-73-06, with a clear evidence trail, and skipping it would ship F-B7 already carrying F-B4's exact failure mode under the new operator.

**Open question for the planner:** `ENRICH_ADAPT_CO_SEARCH` (`scripts/build_cloud_workflows.py`, the `Adapt Company Search` node) takes `merged.results[0]` unconditionally on a hit. An IN-over-two-values search can legitimately return `total: 2` when the bare and `www.` forms happen to be two DIFFERENT company records (a real data condition, not this fix's target case). D-73-06 does not specify behavior for `total > 1`; the research question the phase brief poses ("Adapt Company Search / Adapt Company Link handling of total > 1") is genuinely open — recommend the plan either (a) keep taking `results[0]` (accepting the ambiguity as a pre-existing risk class, same as the ingest lane's exact-name fallback already accepts for name collisions) or (b) treat `total > 1` as an ambiguity that routes to `review` — a plan-time decision, not a research one, since CLAUDE.md gives no existing precedent either way for this specific node.

### Pattern 3: First-wins dedupe vs. this repo's existing merge-dedupe — a real conflict, not a naming detail

**What:** `operator-claude-plugin/scripts/extraction.py::dedupe()` (lines 335–424) already implements identity-group clustering with `_first_satisfied_key`/`_group_presence`, but its cluster resolution (`_merge_cluster`, lines 291–333) **merges fields the cluster agrees on and drops the ones it disagrees on as conflicts** — it does NOT keep "the first row, unmodified" and does NOT tag a loser as `duplicate_in_csv` naming the winner. D-73-04 explicitly wants: **first occurrence wins verbatim, no field merge, loser gets `duplicate_in_csv` naming the winner's row id.** These are two different, incompatible behaviors from the same identity-group input.

**Why this matters for planning:** CONTEXT.md's own "Reusable Assets" section says to extend `dedupe()` "rather than writing a second dedupe" — but reusing `dedupe()` UNMODIFIED for this feature would silently violate D-73-04 (it would field-merge instead of first-wins, and it has no `duplicate_in_csv` outcome word at all). The correct reuse is narrower than the CONTEXT text implies: reuse `_first_satisfied_key`/`_group_presence`/`_casefold_trim` (the clustering primitives, all already module-level, importable) to GROUP rows, then write a small new pass that keeps the first index per cluster and tags the rest — not a call to `dedupe()` itself. Flag this explicitly to the planner rather than letting an executor discover the semantic mismatch mid-task.

**Also relevant:** the plain `contact-upload` skill (the one F-A5 actually failed on) does **not** call `extraction.validate()`/`dedupe()` at all today — it calls `preview.py::build_preview()`, which reads raw header-indexed rows via `tabular.read_table()` with zero identity/dedup logic (confirmed by reading `preview.py` end to end — no import of `extraction`). The wire payload sent to n8n is `tabular.to_csv_bytes(file_path)` of whatever path `dispatch.py` is handed (`operator-claude-plugin/scripts/dispatch.py:104`) — today always the ORIGINAL (or header-corrected, or name-split) file. `preingest.rows_from_table()` (canonical-keyed row builder) is currently only used by the `enrich-before-ingest` skill, never by plain `contact-upload`. **This means implementing D-73-03/04 for plain `contact-upload` needs a new step in that skill's flow producing a `deduped_path`** (a rewritten CSV with the loser rows dropped/flagged) that becomes the path forwarded to `dispatch()` — mirroring the SAME established idiom `name_split.py --apply`/`header_suggest.py --confirm` already use (write a corrected file, return its path, that path becomes "the" path for every step after it). This is a **new code path**, not merely extending an existing call.

### Pattern 4: D-73-14's exact call site — the mechanism already exists, one call site is wrong

`run_manifest.py` (Phase 61 REVIEW-07) already ships BOTH the shared-file API every early caller uses (`manifest_path()`, `load()`, `save(run_id, verdicts)`) AND the run-scoped API D-73-14 wants (`run_manifest_path(run_id)`, `load_scoped(path, expected_run_id)`, `classify_read(run_id, path=None)`). **This is not new infrastructure to build — it is a wrong argument at one existing call site.**

The `enrich-before-ingest` skill's own step (SKILL.md, matching the "step 5" language in D-73-14) already WRITES to the run-scoped file:
```
# operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:844
run_manifest.save(run_id, verdicts, path=run_manifest.run_manifest_path(run_id))
```
but READS from the bare, unscoped, cross-run-accumulating shared file:
```
# operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:801
verdicts = run_manifest.load()
```
`run_manifest.load()` with no `path` argument resolves to `manifest_path()` (the single shared file every run since the plugin's install has been appending held/confidence_held rows to) — this is EXACTLY the "shared `run_manifest.json` lists prior runs' held rows as this run's" defect the folded todo names. The fix is changing line 801 to `run_manifest.load(path=run_manifest.run_manifest_path(run_id))` (or the `load_scoped` variant if the mismatch-detection behavior is also wanted) — a one-line change to an already-correct mechanism, not a new one.

**Do not touch `chunking.py::merge_chunk_verdicts`'s own default** (`target = ... run_manifest.manifest_path()`, `chunking.py:770-777`). Its docstring states this is DELIBERATELY the shared file — "the SAME single shared file SKILL.md's existing resume step already reads across separate runs of this skill, never a per-run file... the two stores make opposite defaults for opposite reasons." That function exists to let a crashed batch RESUME by seeing what earlier attempts already accomplished; scoping it per-run would break resume. D-73-14 is narrowly about the REPORT step's read (line 801), not about `merge_chunk_verdicts`'s resume-time accumulation — the two are correct to disagree.

### Anti-Patterns to Avoid
- **Editing `HS_CO_SEARCH_BODY_EXPR` for F-B7** — it is the local-live sibling only; the cloud fix is a different node (see Pattern 2).
- **Adding a second array→semicolon-join copy for F-E1** instead of fixing `reviewApply()`'s `canonicalPatch` assignment once — the two existing choke points at lines ~2582/~4610 are unrelated to the failing code path.
- **Assuming F-B6 needs new nodes** — `build_backend_status_cloud()` already has "Lusha Usage", "Apollo Usage", and a shared ZoomInfo usage subgraph, all wired. Diagnose the live `not_configured` result (wiring vs. deploy-parity) before writing code.
- **Calling `extraction.dedupe()` unmodified** for D-73-03/04 — its merge behavior contradicts the locked "first wins, no merge" decision.
- **Hand-editing any `n8n/wf_*.json`** — always regenerate via `scripts/build_cloud_workflows.py` (repo-wide standing rule, CLAUDE.md, confirmed still true: `.venv/bin/python scripts/build_cloud_workflows.py` currently produces zero diff against committed JSON).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| New Merge-input wiring for a new lane | A hand-spliced connection dict | `splice_carry_merge_after` / `_append_merge_input` / `wire_gate_refusal_lane` / `_add_starved_lane_sentinel` | These already handle v1 executionOrder's "zero-item output is not a delivery" and "first-delivery-wins" rules correctly (CLAUDE.md §13.0.3); a hand-wired edge reproduces exactly the class of bug Phase 70 spent 12+ plans fixing |
| A second freemail domain list | A copy of the freemail set in Python | `n8n/code/companyLink.js::FREEMAIL_DOMAINS` (JS authoritative) + the existing Python mirror + its existing parity test | D-73-08 requires this explicitly; a second independent list is exactly the drift class this repo's parity tests exist to prevent |
| A CSV row identity/dedupe algorithm | A new similarity-score or fuzzy matcher | `extraction.identity_groups()`/`_first_satisfied_key`/`_casefold_trim` (exact, casefolded, trimmed equality only — no similarity score anywhere in this codebase, deliberately, per 24-RESEARCH.md Pitfall 5) | The codebase has a hard rule against fuzzy identity matching; introducing one for F-A5 would be a scope violation, not a shortcut |

**Key insight:** seven of this phase's eight findings can be solved by finding the right existing precedent in this exact file/module and copying its shape, not designing new graph or dedupe primitives. F-A6 is the exception (see Pitfall 0) — its problem (an HTTP node's error output changing the item count of what a downstream positional Merge expects to receive) has no existing solved case in this codebase to copy; its fix needs new design, not precedent-matching.

## Common Pitfalls

### Pitfall 1: Fixing F-E1 at the wrong choke point
**What goes wrong:** Patching the two `Array.isArray(properties[k]) ... join(";")` blocks named in the phase description (lines ~2582, ~4610) and declaring F-E1 fixed.
**Why it happens:** Those two blocks look like "the" serialization choke point because they're the ones documented with a BUG-27 comment — but they belong to `ENRICH_DECIDE_CLOUD`/`ENRICH_DECIDE_CO_CLOUD` (the enrichment lane's pre-write decision nodes), which never run on the review-approve path.
**How to avoid:** Trace the actual failing node (`Review Decision Update`, execution `12502`) back through its build function (`build_review_decision_cloud`, line 10918) to `Build Review Decision`'s call to `buildReviewDecision()` (`n8n/code/reviewDecision.js`) which calls `reviewApply()` (`n8n/code/reviewApply.js`) for its `canonicalPatch`. Fix there.
**Warning signs:** A regression test on `ENRICH_DECIDE_CO_CLOUD` passes but `reviewLoop.test.mjs`/`reviewDecisionEndpoint.test.mjs` still has no test asserting an array-valued candidate serializes — confirmed absent today (neither test file mentions `Array`/arrays at all).

### Pitfall 2: The offline walker cannot see an HTTP node's error output at all
**What goes wrong:** Assuming `node --test tests/n8n/*.test.mjs` will exercise the new `create_failed` refusal lane the same way it exercises every other lane.
**Why it happens:** `tests/n8n/lib/walkWorkflow.mjs`'s `runNode()` (line 275-301) handles every `HTTP_TYPES` node with `return { outputs: [(raw || []).map(unwrapJson)] }` — **always exactly one output array**. There is no branch for a second (error) output anywhere in the walker. `continueErrorOutput` does not appear as a functional value anywhere in this repo today (confirmed: zero hits for the literal string in `scripts/build_cloud_workflows.py`, any `n8n/wf_*.json`, or any `tests/n8n/*.mjs` file) — this is genuinely new ground for both the builder AND the test harness.
**How to avoid:** The walker itself needs a small extension before the new lane can be driven offline: either (a) teach `runNode`'s HTTP_TYPES branch to return a second `outputs[1]` when the stub is shaped `{success, error}` and the node's `onError === "continueErrorOutput"`, or (b) accept that the error-output branch is untestable via the walker and design the graph so the SUCCESS path (index 0) is what the walker drives, with the error path validated only by the live gate (attempt 3) and hand-inspection of the generated JSON's `connections`. Recommend (a) — it is a small, contained addition (mirrors the existing `if`-node's two-output handling already in the same function) and keeps this fix inside the same offline-first discipline every other Phase 70 lane got.
**Warning signs:** A "passing" `node --test` suite that never actually threw `HubSpot Create`'s stub into an error shape — check the new test explicitly asserts a walked trace reaches `Build Ingest Response` via the NEW lane, not just that the graph parses.

### Pitfall 3: `dedupe()`'s existing behavior silently violates D-73-04 if reused as-is
See Pattern 3 above — this is restated here because it is the single highest-risk misread of the CONTEXT.md "Reusable Assets" hint.

### Pitfall 4: Assuming F-B6 is missing code
See "Architecture Patterns" note above and the dedicated section below — `build_backend_status_cloud()` already probes all three providers. Read one live disarmed status response before writing anything.

### Pitfall 5: `cost_guard.py` already partially handles object_type — the real gap is narrower than "add a rate table"
`operator-claude-plugin/scripts/cost_guard.py`'s `PROVIDER_RATE_KEYS` (lines 51-56) already distinguishes `lusha_contacts_first_time_enrich` from `lusha_companies_match` by `object_type`. F-B1 (Lusha priced at the contact rate for a companies batch) and F-A1/F-A2 (a provider-free `contact-upload` lane priced as if it calls providers, and priced with a chunk-based execution count when it is always exactly 1 POST) both point at `write_grant.plan_grant`/`envelope()` (`operator-claude-plugin/scripts/write_grant.py:962-1130`) unconditionally calling the SAME provider-cost/chunk-execution estimator regardless of which lane is asking. `plan_grant` already receives a `label` string (e.g. `"contact-upload batch"`) but nothing in `envelope()` branches on it. D-73-16's fix is: give `plan_grant`/`envelope()` a real `lane` parameter (not just `object_type`, not just the display-only `label`) that routes `contact-upload` to a zero-provider/one-execution estimate (reusing the SAME zero-cost math `preview_enrichment.zero_cost_estimate`/`TABULAR_COST_REASON` already applies correctly in `preview.py::tabular_cost_block()` for the identical lane — a genuine drift between two call sites pricing the same thing differently) and routes `companies` to the already-correct `lusha_companies_match` rate (which just needs `object_type="companies"` to actually reach `estimate_batch`, confirm it isn't being overridden upstream).

## Code Examples

### The exact node this session's F-A6 fix touches

```python
# Source: scripts/build_cloud_workflows.py:1474 (call site) and :9358-9385 (definition)
def _hs_http_create_node(name, resource, x, y):
    if resource not in ("contacts", "companies"):
        raise ValueError(f"_hs_http_create_node only supports contacts/companies — got resource={resource!r}")
    url = "https://api.hubapi.com/crm/v3/objects/" + resource
    body = "={{ JSON.stringify({ properties: $json.properties }) }}"
    return _http_node(
        name, url, x, y,
        auth="hubspot", json_body=body, method="POST", on_error=None,   # <-- D-73-01 changes this
    )
```
`_http_node`'s own `on_error` parameter (docstring at `scripts/build_cloud_workflows.py:5234-5241`) already emits whatever string is passed straight onto the node as `onError` — **no change needed to `_http_node` itself**, only to what `_hs_http_create_node` passes for the `"HubSpot Create"` call site specifically (line 1474, inside the ingest lane's `build_contact_ingest_cloud`), leaving the companies-branch and every other `_hs_http_create_node("HubSpot Company Create", ...)` call untouched — F-A6 is scoped to the ingest lane's contact create only (`HubSpot Company Create` at line 7360 is a separate call site and out of scope per the finding).

### Current wiring that must change (`HubSpot Create`'s only edge today)

```python
# Source: scripts/build_cloud_workflows.py:1596-1599
for write_node in ("HubSpot Update", "HubSpot Create"):
    conns[write_node] = {"main": [
        [{"node": "Build Association Request", "type": "main", "index": 0}]
    ]}
```
Adding `onError: "continueErrorOutput"` without also wiring `main[1]` leaves the error branch a dead end in the generated JSON (n8n tolerates an unwired output; it simply drops those items) — the refusal row would never reach `Build Ingest Response` at all. The new `main[1]` edge must reach `Ingest Merge Response` via its own carry-merge/sentinel input (Pattern 1 above), not `Build Association Request`.

### D-73-08's authoritative freemail set (unchanged, reuse verbatim)

```javascript
// Source: n8n/code/companyLink.js:25-33
const FREEMAIL_DOMAINS = new Set([
  "gmail.com", "googlemail.com", "outlook.com", "outlook.com.au", "hotmail.com",
  "hotmail.com.au", "live.com", "live.com.au", "msn.com", "yahoo.com", "yahoo.com.au",
  "ymail.com", "icloud.com", "me.com", "mac.com", "aol.com", "protonmail.com", "proton.me",
  "gmx.com", "mail.com", "zoho.com",
  "bigpond.com", "bigpond.net.au", "bigpond.com.au", "optusnet.com.au", "iinet.net.au",
  "tpg.com.au", "internode.on.net", "westnet.com.au", "dodo.com.au", "iprimus.com.au",
  "exemail.com.au", "ozemail.com.au",
]);
```
This set already exists and is exported (`module.exports` line 169). D-73-08's fix is calling `FREEMAIL_DOMAINS.has(domain)` inside `Decide Company Action` (`ENRICH_DECIDE_CO_CLOUD`, `scripts/build_cloud_workflows.py:4425`) — confirmed by grep that this string does not currently appear anywhere in `build_cloud_workflows.py`, i.e. the companies branch checks nothing against this set today. `Decide Company Action` does not currently `inline("companyLink.js")` — the planner must decide whether to inline just the `FREEMAIL_DOMAINS` constant (small, no other companyLink.js function is needed there) or the whole module; the smaller inline avoids pulling in ingest-lane-specific functions (`companyDomainForRow`, `emailDomain`) that make no sense in the companies branch.

## State of the Art

Not applicable in the usual "old library vs new library" sense — this is a single-repo bug-fix phase. The one relevant "old approach vs new approach" pair is internal to this repo's own history:

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Hand-wired Merge connections | `splice_carry_merge_after`/`_add_starved_lane_sentinel`/`wire_gate_refusal_lane` generalized helpers | Phase 70 (2026-09-09/10) | F-A6's new lane must use these helpers, not a one-off wire, or it repeats the exact bug class Phase 70 spent 12+ plans fixing |
| `EQ` domain match | `IN [bare, www.]` variant-set match | This phase (F-B7), mirroring Phase 61's `linkedin_url_variants` precedent | Established idiom, not a new pattern |

**Deprecated/outdated:** none relevant.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | n8n's HTTP Request node error-output item shape under `continueErrorOutput` carries something like `$json.error`/`$json.error.status`, but the EXACT field names were not confirmed against n8n's own schema docs (only community-forum evidence found, not authoritative). **This affects only the refusal row's message text, never the Merge-pairing fix** — Pitfall 0's recommended fix (`combineByFields` on `email`) does not depend on the error item's shape at all; the error item feeds only the `create_failed` refusal-row Code node, which reads it once and independently of how `Create Carry Merge` re-pairs the success path | "Pitfall 2" / F-A6 code examples | The refusal-row Code node's field access (`item.json.error?.message` etc.) may need adjustment after the first live disarmed test send reveals the real shape — write defensive parsing (fallback to `JSON.stringify(item.json)`) rather than a brittle exact-field read. No risk to the pairing fix either way |
| A2 | F-B6's live `not_configured` result is a wiring/deploy-parity issue rather than a code defect, based on reading `ENRICH_STATUS_CREDIT_REQUEST`'s comment ("probes ALL THREE providers unconditionally... no 'not configured' case to represent") — **strengthened** by same-session evidence: the ENRICHMENT lane's own credit branch (a DIFFERENT node graph, `build_enrichment_cloud()`, sharing the identical `provider_registry`/`_credit_http_node` probe code) read Lusha and ZoomInfo balances correctly in the SAME stress session ("provider balances (from enrich runData): Lusha total 4200/used 492/remaining 3708; ZoomInfo remaining 9358; Apollo null" — `tests/stress-tests/SESSION-2026-09-15.md`, Stage D). The same probe mechanism works on one lane and reports `not_configured` on the other, which is strong evidence the CODE is correct and the STATUS lane specifically has a wiring or deploy-parity gap, not that the underlying credential/endpoint approach is broken. | "F-B6" section, Pitfall 4 | If wrong, D-73-17 needs a code fix after all — but the recommended first step (read one live disarmed status POST's runData) resolves this cheaply before any code is written, so the risk is bounded to one extra diagnostic step, not a wrong fix shipped |
| A3 | `run_report`'s F-B5 gap is in the render/bucketing logic (`_render_block`/`_build_records`) rather than in `written_records.classify_item` itself, based on reading that `classify_item`/`outcome_for_action` already structurally support `enrich`/`update` actions | "F-B5" (not fully traced to one line — see Open Questions) | If wrong, the D-73-13 frozen-fixture proof required by CONTEXT.md will surface the real location before any fix is written — this is exactly what that locked decision exists to catch |
| A4 | `HS_CO_SEARCH_BODY_EXPR` (line 3088) is unused by the live cloud lane and belongs to `build_enrichment_local_live()` only | Pattern 2 | Verified directly by grep (exactly one call site, inside that function) — low risk, stated as an assumption only because it contradicts the phase description's file:line pointer, worth a second look before the plan locks it in |

**If this table is empty:** N/A — see rows above.

## Open Questions

1. **Does `Adapt Company Search`/`Adapt Company Link` need explicit `total > 1` handling for F-B7?**
   - What we know: both currently take `results[0]` unconditionally on any hit; an IN-over-two-values search can return 2 genuinely different company records in rare cases.
   - What's unclear: whether this is acceptable (same risk class as the existing exact-name-match ambiguity, which the codebase already tolerates) or needs a `review` route.
   - Recommendation: plan-time decision (no existing precedent either points to). Default to accepting it (matches the ingest lane's existing tolerance for the analogous name-collision case) unless the planner has a reason to diverge.

2. **Exact JSON shape of an httpRequest node's `continueErrorOutput` error item.**
   - What we know: community evidence points to `$json.error` (object) with at least a `.status`; HubSpot's own 409 body includes "Contact already exists. Existing ID: <id>" in its message text (confirmed live, `tests/stress-tests/SESSION-2026-09-15.md`, execution `12454`/`8f31173312fd43528300a55f257c04d8`, and again at execution `12454` in the second attempt with "Existing ID: 353064513008").
   - What's unclear: the precise field path(s) to read the message from — n8n's own httpRequest docs page did not yield a schema for this.
   - Recommendation: write the refusal-row Code node defensively (try `error.message`, `error.description`, fall back to `JSON.stringify(error)`), and confirm the real shape — AND the `pairedItem` question — against the first disarmed live send in the attempt-3 gate. This is a case where `[observed live]` evidence from that gate is the only way to close it, per CLAUDE.md §13.0.3's tagging discipline.

3. **Should `written_records.append_chunk`'s companies/enrich-records dispatch path be audited for the SAME gap `dispatch.py` (ingest lane) had before its 2026-08-29 fix (`written-records-misses-write`)?**
   - What we know: `dispatch.py`'s own module docstring records a prior, now-fixed bug where the ingest lane never flushed to `written_records` at all before that fix. `chunking.py:662` is the enrichment lane's equivalent flush call site, inside `dispatch_plan`'s loop. **D-73-11's join rule is NOT new work to implement** — `_identity_for_entry` (`operator-claude-plugin/scripts/run_report.py:513-521`) already reads `entry.get("row_id")` first, falling back to `entry.get("hs_object_id")`, exactly as D-73-11 describes verbatim. The locked decision is describing EXISTING behavior; it is not asking for a new join to be written.
   - What's unclear: whether the Stage-B companies send (18 executions, `enrich-records` skill) actually goes through `chunking.dispatch_plan`'s loop (and therefore already flushes correctly) or a different, unaudited path — and, given the join already exists, WHERE in the pipeline the 24 enrich entries are actually being lost or mislabeled DESPITE that join (a bucketing/rendering bug in `_render_block`/`_build_records`, a `_lane_for_entry` grouping issue, or the entries genuinely never reaching `written_records` in the first place).
   - Recommendation: the D-73-13 frozen-fixture proof (executions `12434`/`12449`) is the fastest way to settle this — trace whether `written_records-<that run_id>.json` already contains the 24 enrich entries (in which case the F-B5 defect is purely in `run_report`'s rendering/counting) or is missing them (in which case the defect is upstream, in the flush call site). Do not implement a NEW join — locate why the existing one isn't producing a visible, counted result.

4. **Does D-73-03/04's dedupe scope to plain `contact-upload` only, or also to `enrich-before-ingest`'s final ingest step?**
   - What we know: for a PLAIN `contact-upload` send, the ingest lane mints NO `row_id` at all — confirmed by reading the ingest lane's own ack-builder comment: "`row_ids` is always empty for this lane today (no per-row identity exists yet at ack time)" (`scripts/build_cloud_workflows.py:1231-1234`), and `n8n/code/columnMap.js::mapRow` has no `row_id` in its alias table. Outcomes for that lane are joined by `hs_object_id` once written, or left `unjoinable` before that — never by a positional row index. This means a first-wins CSV dedupe applied to plain `contact-upload` does NOT create a row_id-vs-file-position mismatch, because no such mapping exists to begin with for this lane.
   - What's unclear: `enrich-before-ingest`'s flow DOES mint a plugin-side positional `row_id` (`preingest.build_rows_spec`: `row-{i+1}`, refusing a row that already carries one) and DOES track `run_state.total_row_ids` for its own "row accounting" report section (`run_report.py`'s "MISMATCH" check). If the SAME dedupe mechanism this phase builds is later applied (or accidentally shared) with that flow's row-id minting, a collapsed row must still be accounted for somewhere (as `duplicate_in_csv`, counted in `total_row_ids`) or that flow's own report will show a spurious MISMATCH.
   - Recommendation: scope the D-73-03/04 implementation explicitly to the plain `contact-upload` skill's preview/dispatch step (where the finding actually occurred and where no row_id accounting exists to conflict with). If the plan also wants dedupe on `enrich-before-ingest`'s CSV intake, treat that as a second, later integration point requiring its OWN accounting rule — not an assumed side effect of building the first one.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `.venv` (Python 3.14) | pytest suite, builder regen | ✓ | 3.14 | — |
| `node` (test runner) | `node --test tests/n8n/*.test.mjs` | ✓ | confirmed working (1170 tests pass) | — |
| n8n Cloud instance (armed writes / deploy / bounce) | attempt-3 live gate | ✗ from this session | — | No fallback: arming, deploying, and bouncing are explicitly the operator's step (D-73-18) and the standing CLAUDE.md rule "never arm n8n writes" — never Claude's |
| n8n executions API (READ-ONLY GETs) | D-73-13's frozen fixture freeze; F-B6 live diagnosis | ✓ — this is Claude-executable per repo memory (`n8n-deploy-permission-blocked`: disarmed reads/GETs pass the sandbox's classifier; only ARMING writes is blocked) | — | — |

**Missing dependencies with no fallback:**
- Live n8n arm/deploy/bounce/reset — this phase's whole gate (attempt 3) is explicitly operator-only, never Claude's, per D-73-18.

**Missing dependencies with fallback:**
- None needed — D-73-13's fixture freeze (read executions `12434`/`12449` via the executions API, redact, commit) and F-B6's one-live-status-POST diagnosis are BOTH read-only operations this session (or the executing agent) can perform directly; they do not need to wait for the operator.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python, root + `operator-claude-plugin/`) + Node's built-in `node:test` (JS) |
| Config file | none dedicated — `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider tests/ operator-claude-plugin/tests/`; `node --test tests/n8n/*.test.mjs` (glob form — directory form is broken on node 24, per repo memory) |
| Quick run command | `.venv/bin/python -m pytest -q -k <finding-specific test file>` / `node --test tests/n8n/<file>.test.mjs` |
| Full suite command | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider tests/ operator-claude-plugin/tests/` (confirmed green at HEAD: **4952 passed, 154 skipped**, 2026-09-15) and `node --test tests/n8n/*.test.mjs` (confirmed green at HEAD: **1170 passed, 0 failed**) |

### Phase Requirements → Test Map
| Finding | Behavior | Test Type | Automated Command | File Exists? |
|---------|----------|-----------|-------------------|-------------|
| F-A6 | `HubSpot Create` error routes to a refusal row, success path unaffected | offline walker + node test; **live gate CANNOT be assumed to exercise this** — see note below | `node --test tests/n8n/<new file, e.g. ingestCreateErrorLane>.test.mjs` | ❌ new file — extend `_add_starved_lane_sentinel`-style coverage; also requires a walker extension (Pitfall 2) before this can pass meaningfully |
| F-A5 | Duplicate CSV rows collapse first-wins, loser tagged `duplicate_in_csv` | pytest unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_extraction.py -k dedupe` (extend) or new `test_csv_dedupe.py` | ⚠️ `extraction.py`'s existing dedupe tests exist but test the WRONG (merge) semantics for this feature — new tests needed, existing ones must NOT be broken |
| F-E1 | `reviewApply()` serializes array-valued candidates before PATCH | node test | `node --test tests/n8n/reviewLoop.test.mjs` (extend with an array-valued decision fixture) | ✅ file exists, ❌ array coverage absent (confirmed by grep) |
| F-B7 | Domain search matches bare and `www.`-prefixed forms in one query | node test | `node --test tests/n8n/*.test.mjs` (extend an existing companies-search-shape test, or new file) | ⚠️ check `tests/n8n/fieldProducerMatrix.test.mjs`/companies-search tests for the closest home |
| F-B3 | Freemail domain company create is refused/downgraded to review, both engines | pytest + node test | `.venv/bin/python -m pytest -k freemail` (extend parity test) + `node --test` on `Decide Company Action`'s jsCode | ✅ parity test exists for the SET; ❌ no test exercises `Decide Company Action` refusing on it yet |
| F-B5 | Run report accounts for enrich/update outcomes with zero "unaccounted" | pytest + frozen fixture | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_run_report.py` (extend with D-73-13's frozen, redacted `12434`/`12449` fixture) | ⚠️ `run_report.py` has existing tests; the frozen fixture is new and REQUIRED by D-73-13 before the fix, not just after |
| F-A3r | Ingest search nodes throttled at 400ms | node test (generated JSON shape) | new: assert `batchInterval === 400` on all 3 ingest search nodes in `n8n/wf_contact_ingest_cloud.json` | ❌ no test currently mentions `batching`/`batchInterval` at all (grep confirmed zero hits) |
| Cost envelope (F-A1/A2/B1) | `plan_grant` prices by lane, not blanket object_type | pytest | extend `operator-claude-plugin/tests/test_write_grant.py` / `test_cost_guard.py` with a `lane="contacts-upload"` zero-cost case and a `lane="companies"` 2-Lusha-credit case | ⚠️ existing tests price by `object_type` only — check for a contact-upload-specific zero-cost assertion |
| F-B6 | Backend-status reports real Lusha/ZoomInfo balances, Apollo `unknown` | live-only (diagnosis first) | N/A until root cause is known — see Open Question 2/A2 | ❌ cannot be resolved by a new offline test alone; needs one live disarmed read first |

**F-A5 and F-A6 interact in a way that hides F-A6's live proof from attempt 3, unless the plan deliberately arranges otherwise.** D-73-03's casefold+trim dedupe collapses the CSV's duplicate `priya` rows client-side, BEFORE the file ever reaches the backend — so a re-send of the SAME stress CSV in attempt 3 will not reproduce the within-batch-duplicate 409 that originally triggered F-A6 at all. Worse: since Stage A's first send already created most of those contacts (per D-73-02, no orphan-repair — they stay in HubSpot until `uat_reset.py` removes them), a same-CSV re-send after the reset finds NO existing contacts and hits the create path cleanly; a re-send WITHOUT a reset would hit the UPDATE path (search finds them), not create, for the very rows that used to collide. The only remaining trigger for a genuine create-time 409 is the race D-73-05 names ("a pre-existing contact the search missed") — not something the plan can reproduce on demand. **The plan must choose explicitly:** either engineer a deliberate trigger for attempt 3 (e.g. a RUNBOOK.md addition that intentionally bypasses/disables the client-side dedupe for ONE send, which is itself a test-only affordance the plan needs to justify and scope tightly), or accept that F-A6's error-output lane is proven only by the walker + `node --test` (once the walker extension in Pitfall 2 exists) and stays `[documented]`-only rather than `[observed live]` until the first genuine race occurs in real operation. Do not let the phase gate quietly assume attempt 3 "proves" F-A6 when the very fix shipped alongside it (F-A5) removes the trigger.

### Sampling Rate
- **Per task commit:** the finding-specific quick command from the table above.
- **Per wave merge:** full suite (`pytest` + `node --test`) — both must stay at or above the HEAD baseline (4952/154 python, 1170/0 node) with zero unexplained skip-count change.
- **Phase gate:** full suite green, `.venv/bin/python scripts/build_cloud_workflows.py` produces zero diff against what's committed (regen-diff-is-zero check, confirmed this is the current state at HEAD), THEN the operator's own gate: deploy+bounce disarmed, reset, run attempt 3 A–F per RUNBOOK.md.

### Wave 0 Gaps
- [ ] Decide, at plan time, how F-A6's error-output lane gets its `[observed live]` proof given F-A5 removes attempt 3's natural trigger (see the note above the Sampling Rate section) — this is a plan-level decision, not something to discover mid-execution.
- [ ] `tests/n8n/lib/walkWorkflow.mjs` — needs a second-output extension for HTTP_TYPES nodes under `onError: "continueErrorOutput"` before F-A6's new lane can be driven offline at all (Pitfall 2). This is infrastructure work the plan should schedule as its own task, not assume comes free with F-A6's graph change.
- [ ] A frozen, secret-redacted runData fixture from executions `12434`/`12449` (D-73-13) — required BEFORE the F-B5 fix is written, not after, per the locked decision's own wording ("Proof before attempt 3"). This is a read-only executions-API operation, executable this session (see Environment Availability) — not blocked on the operator.
- [ ] New test file(s) for F-A3r (batchInterval=400 assertion) and F-A5 (first-wins CSV dedupe with `duplicate_in_csv` tagging) — neither has any existing coverage to extend.
- [ ] **Checked and found NOT to be a gap** (recorded so the planner doesn't re-spend time on it): `tests/n8n/walkerEngineFidelityV1.test.mjs` walks a byte-frozen COPY of `wf_enrichment_cloud.json` (`fixtures/frozen/wf_enrichment_cloud.v1.2026-09-10.json`), never the live/current committed graph, and `tests/n8n/v1RuntimeRecordings.test.mjs` performs zero graph walks at all ("No graph is walked here" — its own file header) — it only asserts fields inside already-frozen runData JSON. Adding nodes to the CURRENT `wf_contact_ingest_cloud.json` for F-A6 does not require re-baselining either file. It DOES require running the full `node --test tests/n8n/*.test.mjs` suite, since some OTHER shape-asserting test (e.g. a node-count or connection-shape pin on the ingest lane specifically) may still be affected — check for one at plan time rather than assuming none exists.

*(No test framework install is needed — pytest and node:test are both already fully set up and green.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Unchanged by this phase (webhook header-auth, HubSpot private-app token — untouched) |
| V3 Session Management | no | N/A |
| V4 Access Control | yes | Write-safety gates (`_writeSafetyAllows`, allowlist-scoped grants) are UNCHANGED and MUST remain the sole write authority; F-A6's new error-output lane must never itself grant a write — it only reports a refusal that already happened downstream of the gate |
| V5 Input Validation | yes | F-A5 (CSV duplicate collapse) and F-B3 (freemail domain refusal) are both input-validation hardening at the plugin/backend boundary — must fail closed (hold/review), never silently drop or silently create |
| V6 Cryptography | no | N/A — no secret handling changes in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A malformed/adversarial CSV row (duplicate email, malformed address) causing a backend write-path crash or an unassociated/orphaned record | Denial of Service / Tampering | F-A6's `continueErrorOutput` containment (this phase) — the existing pattern this repo already uses everywhere else (write nodes fail their execution on error; refusal rows are reported, never swallowed) |
| A HubSpot API response shape this code has never seen (e.g. an unexpected error-output field) silently misreported as a success | Tampering / Repudiation | Defensive parsing in the new refusal-row Code node (Open Question 2) — never assume a field exists, always fall back to a raw dump rather than crashing or reporting success |
| A freemail domain used to create a junk company record that later pollutes matching for every other contact sharing that domain (this repo's own recorded incident class, see `NOT_A_COMPANY_DOMAIN` in `companyLink.js`) | Tampering | F-B3's refusal (hold for review rather than create) — same defensive pattern this repo already applies to LinkedIn/social-profile-as-domain confusion |

## Sources

### Primary (HIGH confidence — read directly this session)
- `scripts/build_cloud_workflows.py` (11,966 lines) — `_http_node`, `_hs_http_create_node`, `_hs_http_patch_node`, `splice_carry_merge_after`, `_add_starved_lane_sentinel`, `wire_gate_refusal_lane`, `_append_merge_input`, `_merge_input_index`, `HS_CO_SEARCH_BODY_EXPR`, `ENRICH_BUILD_CO_IDENTITY`, `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`, `CO_LINK_DOMAIN_SEARCH_BODY`, `ENRICH_DECIDE_CO_CLOUD`/`ENRICH_DECIDE_LOCAL`'s serialization choke points, `ENRICH_APPLY_REVIEW`, `build_review_decision_cloud`, `build_backend_status_cloud`, `ENRICH_STATUS_CREDIT_REQUEST`, `ENRICH_STATUS_BUILD_RESPONSE`, `_INGEST_SEARCH_BATCH_INTERVAL_MS`
- `n8n/code/companyLink.js` — `FREEMAIL_DOMAINS`, `cleanCompanyDomain`, `NOT_A_COMPANY_DOMAIN`
- `n8n/code/reviewApply.js`, `n8n/code/reviewDecision.js`, `n8n/code/backendStatus.js`
- `tests/n8n/lib/walkWorkflow.mjs` — `runNode()`'s single-output HTTP_TYPES handling (line 275-301)
- `operator-claude-plugin/scripts/extraction.py`, `preingest.py`, `preview.py`, `dispatch.py`, `written_records.py`, `run_report.py`, `write_grant.py`, `cost_guard.py`, `sweep_conditions.py`, `backend_status.py`, `status.py`, `watch.py`
- `tests/stress-tests/SESSION-2026-09-15.md` — the full findings evidence (execution ids, live errors, evidence tables)
- `.planning/debug/ingest-search-429-rate-limit.md` — F-A3's resolved debug session (test-suite baseline: 4948 passed/154 skipped, 1170 node, at that commit)
- `.planning/phases/73-ga-fix-list-from-stress-attempt-2/73-CONTEXT.md`
- `.planning/STATE.md`, `.planning/REQUIREMENTS.md`
- Live command execution this session: `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider tests/ operator-claude-plugin/tests/` (4952 passed/154 skipped), `node --test tests/n8n/*.test.mjs` (1170 passed/0 fail), `.venv/bin/python scripts/build_cloud_workflows.py` (zero diff), node-count read of all 5 committed `n8n/wf_*.json` (287/78/55/43/30, all `executionOrder: "v1"`)

### Secondary (MEDIUM confidence)
- n8n community forum posts on `continueErrorOutput` error-output shape (WebSearch) — indicates `$json.error.status` exists but is not an official schema reference

### Tertiary (LOW confidence)
- None used as load-bearing for any recommendation — every claim above traces to a primary source.

## Metadata

**Confidence breakdown:**
- Standard stack: N/A — no new packages
- Architecture (graph wiring patterns): HIGH for F-B7/F-B3/F-E1/F-B5's join rule/D-73-14 — every one of these has a working precedent read directly from the current codebase. **MEDIUM for F-A6** — no existing precedent in this codebase solves its exact problem (an HTTP error output changing item counts a downstream positional Merge depends on); the recommended fix direction (Merge field-matching on `email`) is evidenced (email confirmed present in both the create request and HubSpot's echoed response) but not yet proven live.
- Pitfalls: HIGH for F-E1/F-A5/F-B6/dedupe-conflict/F-B4-fold-interaction (all confirmed by direct code reading); MEDIUM for F-A6's exact error-item shape and its interaction with F-A5's live-proof path (flagged as Assumption A1/Open Questions 2 and 4, and the Validation Architecture note above Sampling Rate)

**Research date:** 2026-09-15
**Valid until:** This is a fast-moving, actively-developed repo (multiple commits per day per STATE.md) — treat this research as valid only until the next commit touches any of the cited files/line numbers. Re-grep line numbers before the plan locks them in if any time has passed since this research.
