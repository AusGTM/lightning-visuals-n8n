---
phase: 66-rich-enrichment-not-minimum-enrichment
plan: 01
subsystem: enrichment
tags: [n8n, apollo, lusha, zoominfo, hubspot, contacts-waterfall]

requires: []
provides:
  - "Landline (phone) chased end to end: gate REQUIRED, Lusha reveal map (both copies), and decideAction's CREATE branch that used to chase nothing"
  - "lv_linkedin_url and lv_persona_group now fetched by HubSpot Search/Fetch By Id, closing a non-clobber hole for any downstream producer"
  - "Apollo LinkedIn producer with a host-allowlist guard, proven through scoreCandidates -> ENRICH_MERGE's rename -> mergeContacts"
  - "Contacts gate REQUIRED widened from 3 to all 12 config/field_policy.yaml contacts keys, asserted against the YAML directly"
affects: [66-02, 66-03]

actuals:
  tokens: 12000
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Root-cause fix in the shared decideAction function (CREATE branch) rather than a per-caller workaround"
    - "Frozen allow-list map + its hand-written n8n-expression mirror kept in lockstep by an anti-drift parity test"
    - "Host guard admits by parsed-host equality/suffix, never a bare endsWith on the raw string (lookalike-domain refusal)"

key-files:
  created:
    - tests/n8n/linkedinProducer.test.mjs
  modified:
    - n8n/code/lushaRequest.js
    - n8n/code/enrichmentGate.js
    - n8n/code/normalizeProviders.js
    - scripts/build_cloud_workflows.py
    - tests/n8n/lushaRequest.test.mjs
    - tests/n8n/lushaRequestContract.test.mjs
    - tests/n8n/enrichmentGate.test.mjs
    - tests/n8n/enrichment.test.mjs
    - tests/test_fetch_by_id_topology.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_scheduled_maintenance_cloud.json

key-decisions:
  - "D-66-01/RICH-01: decideAction's CREATE branch now returns missingFields === requiredFields (a copy) instead of []. Without this, an all-blank CREATE row — the exact live scenario the phase brief cites — chased nothing no matter how wide REQUIRED was."
  - "The push key for the new Apollo LinkedIn producer is UNPREFIXED (linkedin_url), matching what ENRICH_MERGE already reads at scoreCandidates.winners.linkedin_url — PATTERNS.md had this direction backwards."
  - "ZoomInfo gets no LinkedIn push in this plan: its output-field list is account-verified and an unprobed field risks 400ing the whole batch. Left as a pending-probe row."
  - "T-66-04 (accept): lv_persona_group and lv_linkedin_url each have exactly one producing branch (Apollo), so an Apollo-unmatched contact stays permanently 'enrich' once REQUIRED widens. Accepted because D-66-01 is locked and nothing is armed."

patterns-established:
  - "A field-class change (fill_blank_only -> stale_refreshable) is the only way to activate a stale_after_days entry; adding one to a fill_blank_only field's POLICY is inert, so it is omitted rather than added dead."

requirements-completed: [RICH-01, RICH-03, RICH-06]

coverage:
  - id: D1
    description: "A blank-landline contact row and an all-blank CREATE row both produce a Lusha request body whose reveal array carries the phone reveal value, deduplicated against mobilephone."
    requirement: "RICH-01"
    verification:
      - kind: unit
        ref: "tests/n8n/lushaRequest.test.mjs#D-66-01: a CREATE-row decideAction's missingFields feeds lushaContactBody a reveal containing the phone value"
        status: pass
      - kind: unit
        ref: "tests/n8n/lushaRequestContract.test.mjs#Lusha Enrich body: landline AND mobile both missing -> ONE-element reveal, not two (T-66-03)"
        status: pass
    human_judgment: false
  - id: D2
    description: "An Apollo LinkedIn URL reaches mergeContacts under the lv_-prefixed key, promotes into a blank record, and is protected (stage_only) against a populated stored value; a non-linkedin.com host produces no candidate."
    requirement: "RICH-03"
    verification:
      - kind: unit
        ref: "tests/n8n/linkedinProducer.test.mjs#(j) mergeContacts promotes the produced value into a BLANK existing record"
        status: pass
      - kind: unit
        ref: "tests/n8n/linkedinProducer.test.mjs#(k) mergeContacts STAGES ONLY against an existing record already holding a different LinkedIn URL (D-66-08 non-clobber)"
        status: pass
      - kind: unit
        ref: "tests/n8n/linkedinProducer.test.mjs#(l) the compiled Normalize + Score then Merge Winners bodies carry a live Apollo LinkedIn URL through to lv_linkedin_url in canonicalPatch"
        status: pass
    human_judgment: false
  - id: D3
    description: "Chasing the landline changes no provider's per-call cost (RICH-06), recorded structurally at the Lusha Enrich node's build site."
    requirement: "RICH-06"
    verification:
      - kind: other
        ref: "scripts/build_cloud_workflows.py RICH-06 comment block at the 'Lusha Enrich' node build site, reviewed manually against ZOOM_OUTPUT_FIELDS and the Apollo body"
        status: pass
    human_judgment: true
    rationale: "This is a structural/documentary claim about provider billing (no live call was made per plan instruction), not something a unit test asserts — confirmed by direct code inspection (ZOOM_OUTPUT_FIELDS already lists phone/mobilePhone; Apollo body has no per-field ask) but the underlying billing behavior itself is asserted from docs/LUSHA-V3-CONTRACT.md, not re-measured live."

duration: 50min
completed: 2026-09-04
status: complete
---

# Phase 66 Plan 01: Contacts waterfall chases what it can already promote Summary

**Widened the contacts enrichment gate from 3 chased fields to all 12 promotable ones, fixed the landline reveal (dead end-to-end since the CREATE branch silently dropped `missingFields`), and gave `lv_linkedin_url` its first producer — closing a fetch-list non-clobber hole along the way.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 3
- **Files modified:** 13 (1 new test file, 12 modified)

## Accomplishments
- The landline (`phone`) is chased end to end: `ENRICH_GATE`'s `REQUIRED`, both copies of Lusha's reveal allow-list (the shared module and its hand-written n8n-expression mirror), and — the actual root cause — `decideAction`'s CREATE branch, which used to return an empty `missingFields` for any brand-new contact regardless of how wide `REQUIRED` was.
- `lv_linkedin_url` and `lv_persona_group` are now fetched onto `existingRecord` by both the `HubSpot Search` and `HubSpot Fetch By Id` nodes, closing a non-clobber hole (a `fill_blank_only` field the search never requested read as permanently blank, silently turning the non-clobber guard into a clobber).
- Apollo's contacts branch produces `lv_linkedin_url`'s first candidate, gated by a host guard that admits only `linkedin.com` and its subdomains (never a bare `endsWith`, which would accept a lookalike-suffix domain) — proven to survive scoring, the PN-1 rename, and the merge policy's non-clobber guard.
- The contacts gate's `REQUIRED` list now equals all twelve `config/field_policy.yaml` `contacts` keys, asserted against the YAML file directly rather than a hardcoded copy.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end "the landline is chased"** - `f9c8271` (feat)
2. **Task 2: Fetch what the merge compares against** - `b60b313` (fix)
3. **Task 3: Give lv_linkedin_url a producer, widen the chase** - `d0296d9` (feat)

**Plan metadata:** committed separately below.

## Files Created/Modified
- `n8n/code/lushaRequest.js` - 3rd reveal-map entry (`phone` -> `phones`), de-duplicated `lushaReveal` output
- `n8n/code/enrichmentGate.js` - CREATE branch returns a copy of `requiredFields` as `missingFields`
- `n8n/code/normalizeProviders.js` - `_linkedinHostOnly` guard, one `_push` call in `apolloCandidates`, ZoomInfo pending-probe comment
- `scripts/build_cloud_workflows.py` - `REQUIRED` widened (4 then 12 members), `REVEAL_MAP` mirror, RICH-06 cost comment, `ENRICH_CONTACT_SEARCH_PROPERTIES_CSV`/by-id suffix changes, `HS_SEARCH_BODY_EXPR` known-narrower-sibling note
- `tests/n8n/linkedinProducer.test.mjs` - new: host guard, producer, key-seam proof, gate widening
- `tests/n8n/lushaRequest.test.mjs`, `tests/n8n/lushaRequestContract.test.mjs`, `tests/n8n/enrichmentGate.test.mjs`, `tests/n8n/enrichment.test.mjs` - extended assertions
- `tests/test_fetch_by_id_topology.py` - updated for the moved `lv_linkedin_url` property (pre-existing Python test pinning the old suffix shape)
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local.json`, `n8n/wf_enrichment_local_live.json`, `n8n/wf_scheduled_maintenance_cloud.json` - regenerated via `scripts/build_cloud_workflows.py`, never hand-edited; node count unchanged at 123

## Decisions Made
- The push key for the new Apollo LinkedIn producer is UNPREFIXED (`linkedin_url`), matching what `ENRICH_MERGE` already reads at `winners.linkedin_url` — this plan's `<upstream_corrections>` block flagged PATTERNS.md's opposite instruction as the silent no-op it warns against, and Task 3's tests prove the correct direction end to end.
- Widening `REQUIRED` was proven to do nothing for Lusha on its own — `lushaReveal()`'s frozen allow-list map was the actual ceiling, corrected in Task 1 alongside `REQUIRED`.
- `decideAction`'s CREATE branch was the true root cause of the brief's cited defect (an all-blank CREATE row chasing nothing): fixed once in the shared module rather than in each of its two call sites.
- No `config/field_policy.yaml`, `n8n/code/mergeContacts.js`, or `n8n/code/resolveIdentity.js` changes — D-66-08 held throughout, confirmed by `git diff --exit-code` on all three at the end of every task.
- ZoomInfo intentionally gets no LinkedIn producer in this plan (unprobed output field, batch-wide 400 risk) — left as a pending-probe row for plan 66-02's coverage matrix.

## Deviations from Plan

None — plan executed exactly as written, including the corrections already called out in the plan's own `<upstream_corrections>` block (which this plan's Task 1/3 actions were written to implement, not deviate from).

One process note, not a deviation from the delivered code: all three tasks' edits were originally authored in one pass before per-task git history was reconstructed (each task's file was reset to the prior commit and its edits reapplied in isolation) so that each of the three commits above contains exactly and only that task's intended diff, verified independently before each commit.

## Issues Encountered
- A pre-existing Python test (`tests/test_fetch_by_id_topology.py`) pinned the old shape of `ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV`'s suffix (asserting `lv_linkedin_url` was added there). Task 2's legitimate move of that property into the search CSV broke it; updated in the same commit per Rule 1 (auto-fix), since it was a direct, in-scope consequence of Task 2's change.

## User Setup Required
None - no external service configuration required. Nothing is armed and nothing is deployed to n8n Cloud (CLAUDE.md §13.0.2's undeployed delta grows further, deliberately).

## Next Phase Readiness
- `HS_SEARCH_BODY_EXPR` (used only by `build_enrichment_local_live()`) remains a known-narrower sibling of the widened search CSV, deliberately out of this plan's scope — flagged in a comment for plan 66-02's coverage matrix.
- The ZoomInfo LinkedIn output field remains unprobed and pending — a candidate row for plan 66-02, with `scripts/probe_zoominfo_location_fields.mjs` named as the precedent.
- T-66-04 (accepted): once armed, `lv_persona_group`/`lv_linkedin_url` will stay permanently blank/missing/`enrich` for any contact Apollo does not match. No mitigation needed now — nothing is armed and D-66-01 already accepted this cost.
- No blockers for 66-02/66-03.

---
*Phase: 66-rich-enrichment-not-minimum-enrichment*
*Completed: 2026-09-04*

## Self-Check: PASSED

All claimed files found on disk; all three task commit hashes (`f9c8271`, `b60b313`, `d0296d9`) found in git log.
