---
phase: 72-enrichment-extras-land-in-hubspot
verified: 2026-09-12T14:34:52Z
status: gaps_found
score: 19/22 decisions verified
covered_files: [".planning/WINDOWS.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-01-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-01-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-02-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-02-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-03-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-03-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-04-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-04-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-05-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-05-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-06-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-06-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-07-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-07-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-08-PLAN.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-08-SUMMARY.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-CONTEXT.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-PORTAL-PROBE.json", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-REVIEW.md", ".planning/phases/72-enrichment-extras-land-in-hubspot/72-UAT.md", ".planning/todos/completed/2026-09-12-ingest-lane-drops-paid-for-enrichment-extras-map-them-instead.md", ".planning/todos/pending/2026-09-12-enrichment-lane-and-companies-branch-have-no-property-history-hop.md", "CLAUDE.md", "config/column_mapping.yaml", "config/field_policy.yaml", "config/hubspot_migration/undo-manifest-481a5c99-ec62-4f59-940a-7387f5e2a7ad.json", "config/hubspot_properties.yaml", "docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md", "n8n/code/columnMap.js", "n8n/code/mergeCompanies.js", "n8n/code/mergeContacts.js", "n8n/code/normalizeProviders.js", "n8n/wf_contact_ingest_cloud.json", "n8n/wf_contact_ingest_local.json", "n8n/wf_enrichment_cloud.json", "n8n/wf_enrichment_local.json", "n8n/wf_enrichment_local_live.json", "n8n/wf_review_decision_cloud.json", "n8n/wf_scheduled_maintenance_cloud.json", "operator-claude-plugin/.claude-plugin/plugin.json", "operator-claude-plugin/CHANGELOG.md", "operator-claude-plugin/config/column_mapping.yaml", "operator-claude-plugin/config/field_policy.yaml", "operator-claude-plugin/scripts/held_queue.py", "operator-claude-plugin/scripts/preingest.py", "operator-claude-plugin/scripts/suggestion_declines.py", "operator-claude-plugin/skills/contact-upload/extraction.md", "operator-claude-plugin/skills/enrich-before-ingest/SKILL.md", "operator-claude-plugin/skills/review-triage/SKILL.md", "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py", "operator-claude-plugin/tests/test_extraction_handoff.py", "operator-claude-plugin/tests/test_held_queue.py", "operator-claude-plugin/tests/test_preingest_merge.py", "operator-claude-plugin/tests/test_preview_rendering.py", "operator-claude-plugin/tests/test_skill_sequence_coverage.py", "scripts/build_cloud_workflows.py", "scripts/deploy_n8n_workflows.py", "src/merge_policy.py", "tests/fixtures/companies_jscode_frozen.json", "tests/n8n/contactHistoryFlow.test.mjs", "tests/n8n/enrichment.test.mjs", "tests/n8n/fieldProducerMatrix.test.mjs", "tests/n8n/ingestCarryMerge.test.mjs", "tests/n8n/ingestMixedBatch.test.mjs", "tests/n8n/ingestTracerFlow.test.mjs", "tests/n8n/ingestWidenedFieldsFlow.test.mjs", "tests/n8n/mergeCompanies.test.mjs", "tests/n8n/mergeInputContract.test.mjs", "tests/n8n/mergeRecencyGate.test.mjs", "tests/n8n/normalizeProviders.test.mjs", "tests/n8n/overflowSlots.test.mjs", "tests/n8n/parity.test.mjs", "tests/n8n/widenedKeyParity.test.mjs", "tests/n8n/writeGateShape.test.mjs", "tests/test_fetch_by_id_topology.py", "tests/test_merge_helpers.py", "tests/test_merge_policy.py"]
covered_digest: "v1:sha256:272d73cf90d547ae56ca1a77a1cc34044edb14ea5aa75c885846914c74ee7cc5"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "D-72-04 / D-72-17: a linkedin_url on an ingest CREATE row lands as BOTH lv_linkedin_url (canonical) and native hs_linkedin_url on the created contact."
    status: failed
    reason: >
      Confirmed live at the phase's own D-72-17 gate (72-UAT.md, contact 352455353810,
      execution 12402), independently confirmed by static trace of the code at HEAD
      (unfixed), and independently confirmed a third time by the phase's own code review
      (72-REVIEW.md WR-01, committed b06dfbb9). Root cause: `MERGE_CONTACTS`'s
      `confidenceByField` map (scripts/build_cloud_workflows.py ~L479-483) is built by
      iterating `Object.keys(row.source_by_field)`. `source_by_field` is populated by
      `preingest.provider_sourced_fields()`, which reduces `merge_enriched`'s
      `answered_fields` — and `merge_enriched` runs every incoming provider-response key
      through `PROVIDER_KEY_ALIASES = {"lv_linkedin_url": "linkedin_url"}` BEFORE recording
      it as answered (D-72-19), so a provider-supplied `lv_linkedin_url` value is recorded
      under the name `linkedin_url`, never under `lv_linkedin_url`. `hs_linkedin_url` has no
      alias entry, so when the provider response independently carries a `hs_linkedin_url`
      key (it is its own promotable policy entry per D-72-04, not derived from
      `lv_linkedin_url`), that key passes straight through unaliased and IS recorded in
      `answered_fields`/`source_by_field` under its own real name — which is exactly why the
      live gate shows `hs_linkedin_url` landing correctly on the CREATE row while
      `lv_linkedin_url` does not: they take different paths through the alias, and only one
      of the two candidate keys the merge step later reads (`confidenceByField["lv_linkedin_url"]`
      vs `confidenceByField["hs_linkedin_url"]`) happens to already match a name
      `source_by_field` used. The `lv_linkedin_url` candidate (built two lines later in
      `MERGE_CONTACTS` from `row.linkedin_url`, the post-alias row key) therefore never finds
      a `confidenceByField` entry under `"lv_linkedin_url"` and falls back to the flat
      `{source:"csv", confidence:80}` default — below `lv_linkedin_url`'s
      `fill_blank_only@85` threshold, so it is withheld even into a blank field and the row
      is marked `human_review_required` instead of promoted. This directly falsifies plan
      08's own must-have truth ("the re-read contact shows ... BOTH hs_linkedin_url and
      lv_linkedin_url") and D-72-17's live-gate assertion — both plan-08 truths are therefore
      the SAME single gap, not two. It is also a roadmap-goal miss: LinkedIn is one of the
      five field categories the phase goal names by name, and the canonical LinkedIn
      property does not reach a CREATED contact.
    artifacts:
      - path: "scripts/build_cloud_workflows.py"
        issue: "MERGE_CONTACTS's confidenceByField loop (~L479-483) keys on row.source_by_field's own key names (\"linkedin_url\", post-alias) while the lv_linkedin_url candidate two lines later (~L487-494) is looked up under the pre-alias/renamed key \"lv_linkedin_url\" — the two never share a vocabulary for this one field."
      - path: "n8n/code/mergeContacts.js"
        issue: "Line ~400's confidence = confidenceByField[field] ?? flatConfidence lookup is by candidateRow key; it can never see a confidenceByField entry recorded under a different (pre-rename) name. Consuming half of the same defect, not a second bug."
      - path: "tests/n8n/ingestWidenedFieldsFlow.test.mjs"
        issue: "The regression test asserting this exact truth (line 440) seeds its fixture with source_by_field: { lv_linkedin_url: \"apollo\", hs_linkedin_url: \"apollo\" } — the ALREADY-RENAMED key. Real production source_by_field only ever names this field \"linkedin_url\" for the aliased half. The fixture cannot reproduce the real mismatch, which is why the suite stayed green through the very deploy (Task 1) whose live gate (Task 2) caught the defect the same day."
    missing:
      - "In MERGE_CONTACTS, resolve confidenceByField for lv_linkedin_url/hs_linkedin_url through the same alias the candidate builder already applies — e.g. when f === \"linkedin_url\", also set confidenceByField.lv_linkedin_url = 85 (72-REVIEW.md WR-01 gives a worked fix; note hs_linkedin_url does not itself need the alias, since its own key already survives unaliased when a provider independently answers it — adding it anyway per the review's snippet is a safe no-op, not a second defect)."
      - "Regenerate wf_contact_ingest_cloud.json and wf_contact_ingest_local.json, redeploy + bounce disarmed, and re-run a D-72-17-shape read-back before closing this gap."
      - "Fix tests/n8n/ingestWidenedFieldsFlow.test.mjs's fixture to seed source_by_field with the pre-alias key (\"linkedin_url\") the way real production populates it, so the regression test can actually catch a recurrence."
  - truth: "D-72-01/D-72-06 (SAFE-01 non-clobber): every widened field's existing value is fetched into existingRecord before the merge gate runs, on every lane that shares the merge engine — not only the cloud lane."
    status: failed
    reason: >
      72-REVIEW.md CR-01 (Critical): `build_enrichment_local_live()` (emits the real,
      deployed/credential-bound `wf_enrichment_local_live.json`) fetches existing properties
      through `HS_SEARCH_BODY_EXPR` (contacts) and `HS_CO_SEARCH_BODY_EXPR` (companies).
      Confirmed independently by direct read: the cloud siblings
      (`ENRICH_CONTACT_SEARCH_PROPERTIES_CSV`, `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`) were
      widened in Phase 72 to include `lv_phone_2`/`lv_mobilephone_2` (contacts) and
      `lv_phone_2,state,hs_state_code,phone` (companies) — confirmed present at
      scripts/build_cloud_workflows.py:6119-6122 and :6356-6362. `HS_SEARCH_BODY_EXPR`
      (contacts, local-live, ~L2860-2871) and `HS_CO_SEARCH_BODY_EXPR` (companies,
      local-live, ~L3010-3029) were NOT — confirmed by direct read: the contacts constant's
      property list ends at `"lv_linkedin_url","lv_persona_group","hs_linkedin_url"` (no
      overflow slots) and the companies constant's ends at `"lv_sponsorship_reliant"` (no
      phone/state/hs_state_code/lv_phone_2 at all). Both lanes share the SAME merge engine
      code (`ENRICH_MERGE`/`ENRICH_MERGE_CO`), which now unconditionally offers these fields
      as merge candidates — `fill_blank_only` + `protect_if_current_present: true` fields
      whose `currentValue` reads `undefined` (never blank on purpose) are indistinguishable
      from actually-blank to the gate, so the local-live lane will silently overwrite a real
      existing phone/state/overflow value with a new provider guess. This is the exact
      non-clobber defect class (WR-01/58-05/VETO-01) this codebase's own comments repeatedly
      warn about, reintroduced for one lane by omission.
    artifacts:
      - path: "scripts/build_cloud_workflows.py"
        issue: "HS_SEARCH_BODY_EXPR (~L2866, contacts) and HS_CO_SEARCH_BODY_EXPR (~L3010, companies) were not widened alongside their cloud-lane siblings — the local-live enrichment workflow's non-clobber gate is unprotected for lv_phone_2, lv_mobilephone_2 (contacts) and lv_phone_2, state, hs_state_code, phone (companies)."
    missing:
      - "Widen HS_SEARCH_BODY_EXPR to add \"lv_phone_2\",\"lv_mobilephone_2\"; widen HS_CO_SEARCH_BODY_EXPR to add \"lv_phone_2\",\"state\",\"hs_state_code\",\"phone\" — mirroring the cloud-lane CSV constants exactly (72-REVIEW.md CR-01 gives a worked replacement)."
      - "Regenerate and add these five field names to tests/n8n/fieldProducerMatrix.test.mjs's fetch-gate assertion so a NEVER_CHASE (write-map-only) field is checked for presence in every lane's fetch list, not only the REQUIRED-driven check."
  - truth: "D-72-09 (Phase 46 parity): the overflow-slot dedup predicate is identical across mergeContacts.js, mergeCompanies.js and src/merge_policy.py."
    status: failed
    reason: >
      72-REVIEW.md WR-02, confirmed independently by direct read: the JS dedup key
      (`mergeContacts.js:352` and byte-identical at `mergeCompanies.js:380`) is
      `String(c.normalizedValue ?? c.value)` (case-sensitive); the Python oracle's
      equivalent (`src/merge_policy.py:188`, `route_overflow`) is
      `str(c.normalized_value).lower()` (case-insensitive) — an explicit, deliberate mirror
      of `has_conflict()`'s own case-insensitive convention in both engines. Two candidates
      whose normalized values differ only in case would dedupe (no phantom overflow) in the
      Python oracle but NOT in the two JS engines (a real overflow entry would be
      manufactured). Neither `tests/n8n/overflowSlots.test.mjs` nor
      `tests/test_merge_policy.py`'s agreeing-candidates test exercises a same-value-
      different-case pair, so this divergence is currently invisible to the test suite. Low
      real-world likelihood for phone/mobilephone specifically (normalization already
      reduces to digits) but the dedup helper is generic and the repo's own stated Phase 46
      rule treats the three engines as one contract that must never silently diverge.
    artifacts:
      - path: "n8n/code/mergeContacts.js"
        issue: "Line 352: case-sensitive normalizedValue/value string comparison in the overflow dedup loop."
      - path: "n8n/code/mergeCompanies.js"
        issue: "Line 380: byte-identical case-sensitive comparison (same defect, both JS engines)."
      - path: "src/merge_policy.py"
        issue: "Line 188 (route_overflow): case-insensitive comparison — the parity mismatch is between the JS pair and this file, not within the JS pair."
    missing:
      - "Lower-case both sides of the JS dedup key comparison in both mergeContacts.js and mergeCompanies.js to match the Python oracle and each file's own has_conflict() convention (72-REVIEW.md WR-02 gives the worked fix)."
      - "Add a mixed-case agreeing-candidates test case to tests/n8n/overflowSlots.test.mjs and the Python test alongside the fix so the parity is pinned, not just restored."
deferred: []
human_verification:
  - test: "D-72-10: exercise the hs_additional_emails second-email path with a real waterfall response returning two distinct emails for the same person."
    expected: "A second email is recorded in lv_contact_enrichment_provenance only (never written to hs_additional_emails, which the live portal probe found typed enumeration, not string) — confirming the documented fallback actually engages against real dual-email data, not just against the code's own type guard."
    why_human: "72-UAT.md records this explicitly as NOT OBSERVED — the live gate's two rows (Busteed create, Telfer update) each returned only one email from the waterfall. Code-level trace confirms the enumeration-type guard exists (72-05-SUMMARY.md), but that is a different claim from the fallback actually engaging correctly on real dual-email data."
  - test: "F72-3 item 1: is it acceptable that mobilephone can be filled with the exact same number already present in phone on the same contact (observed live on Telfer 1251 — both fields now read +61 409 390 022)?"
    expected: "An explicit operator ruling: either this duplication is acceptable (fill_blank_only correctly filled a blank field; the duplicate value is a data-quality curiosity, not a merge-policy defect) or a cross-field equality check should suppress the fill when the candidate value already equals a sibling field's value."
    why_human: "72-UAT.md F72-3 flags this as observed live exactly as plan 01 predicted, and states explicitly: \"the operator did not give an explicit ruling this sitting.\" This is an open decision the phase left behind, not a code defect — no plan's must_haves asserts a specific behavior here, so it cannot be scored FAILED, but it should not be silently dropped either."
  - test: "F72-3 item 2: is it acceptable that a matched UPDATE row's CSV-supplied firstname/lastname/company corrections are never applied, now that the ingest lane merges against real existingRecord values (Plan 01's new prerequisite)?"
    expected: "An explicit operator ruling on whether identity-field corrections on an UPDATE row should ever apply, and if so, through what mechanism (the current merge intentionally treats these as CREATE-only per D-72-05's IDENTITY_FIELDS carve-out)."
    why_human: "72-UAT.md F72-3 and 72-01-SUMMARY.md (lines 186, 188, 243) record this as plan 01's own flagged, predicted consequence of introducing real existingRecord matching — observed live on Telfer exactly as predicted, with plan 01's two 'Operator confirm:' items left open and no ruling given this sitting."
---

# Phase 72: Enrichment extras land in HubSpot — Verification Report

**Phase Goal:** every field the waterfall finds and the operator paid for reaches the HubSpot
contact it was found for — mobile, LinkedIn, seniority, persona, city/state/country — instead of
being dropped.

**Verified:** 2026-09-12T14:34:52Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Method

No REQUIREMENTS.md rows are mapped to Phase 72 (confirmed: `grep -n "Phase 72" .planning/REQUIREMENTS.md`
returns nothing, and ROADMAP.md's own phase entry says "Requirements: TBD — no requirement IDs
are mapped. Coverage is by DECISION ID"). Per the task's explicit instruction, D-72-01 through
D-72-23 (23 decisions — the original D-72-01..21 plus two execution-time blocking-human rulings,
D-72-22 and D-72-23) are the traceable must-haves; D-72-18 is superseded in-place by D-72-21 and
scored as N/A rather than double-counted, leaving 22 scorable decisions. Each is checked against
the actual codebase at HEAD, not against SUMMARY.md narration, using: static trace of the
merge/policy/wiring code, the full test suite (both green — 4947 py / 1167 node), a from-scratch
regeneration of every n8n workflow JSON confirming zero diff against committed (proving
deployed-live == committed == generated), the phase's own live UAT gate (`72-UAT.md`, run
2026-09-13, PASS-with-findings), and the phase's own code review (`72-REVIEW.md`, committed
`b06dfbb9`, `issues_found`) — every review finding was independently re-derived by direct code
read in this verification, not taken on the review's word alone.

## Goal Achievement — Decision-by-Decision

| # | Decision | Status | Evidence |
|---|---|---|---|
| D-72-01 | Widen ingest lane; plugin stops stripping enrichment extras | ⚠️ PARTIAL — cloud ingest lane VERIFIED; local-live enrichment lane FAILED (see CR-01 gap) | `config/column_mapping.yaml`/`n8n/code/columnMap.js` carry all 12 promotable keys with parity test; `MERGE_CONTACTS`'s cloud-lane candidate loop reads all widened fields from `row.*`; `preingest.strip_enrichment_extras` proven inert behaviourally (plan 03, `test_preingest_merge.py`); confirmed live on both create and update rows in `72-UAT.md`. But CR-01 (below) shows the SAME merge engine's non-clobber guard is unprotected on `wf_enrichment_local_live.json` because two fetch-list constants were not widened alongside their cloud siblings — a real, deployed lane where "reaches the record" can mean "clobbers the record" instead. |
| D-72-02 | ONE source of truth = `field_policy.yaml`'s `promotable_contact_props()` | ✓ VERIFIED | `tests/test_field_policy_conformance.py::test_key_sets_are_identical` (in full green suite) pins `field_policy.yaml` contacts keys against `DEFAULT_CONTACT_POLICY`; no hardcoded "12" literal found in scan of the lane assembly. |
| D-72-03 | `mobile` aliases to `mobilephone`, not `phone` | ✓ VERIFIED | `config/column_mapping.yaml:45-50` and `n8n/code/columnMap.js:42-47` both map mobile/cell/"mobile phone"/"cell phone"/"mobile number" → `mobilephone`, `phone` kept separate; live-confirmed on Busteed create (`phone` `+61 2 9663 8460` vs `mobilephone` `+61 419 212 580`, landed distinctly); CHANGELOG 0.49.0 documents the behavior change. |
| D-72-04 | LinkedIn lands in BOTH `lv_linkedin_url` and `hs_linkedin_url` | ✗ FAILED (CREATE path only; UPDATE path passes) | See gap #1 above. Live-confirmed failing on CREATE (Busteed, `lv_linkedin_url` null) and passing on UPDATE (Telfer, `lv_linkedin_url` landed) in the same gate session; root cause isolated and confirmed by two independent code reads (this verification and `72-REVIEW.md` WR-01). |
| D-72-05 | CREATE: provider wins over CSV for non-identity fields; identity fields unaffected | ✓ VERIFIED | `preingest.merge_enriched`'s `IDENTITY_FIELDS` tuple and CREATE-time provider-wins branch (plan 03, green `test_preingest_merge.py`); live-observed correctly NOT applying on Telfer's non-CREATE row (`72-UAT.md` F72-3). |
| D-72-06 | UPDATE: recency overwrites a stale `stale_refreshable` value only past TTL; `fill_blank_only`/`manual_protected` unchanged (SAFE-01) | ⚠️ PARTIAL — cloud lane VERIFIED; local-live lane FAILED, same CR-01 gap as D-72-01 | `stale_after_days` present for contacts.jobtitle (180d) and companies.industry (365d); byte-identical branch shape in all three engines, exercised by `tests/n8n/mergeRecencyGate.test.mjs`; live-confirmed SAFE-01 holds on the CLOUD lane — Telfer's non-blank `phone` was NOT overwritten. But CR-01 shows the local-live lane's SAME non-clobber guarantee is structurally broken for the newly-widened fields, since `existingRecord` never carries them there. |
| D-72-07 | Observation times: provider = dispatch clock, existing = `propertiesWithHistory` history timestamp, CSV = no time | ✓ VERIFIED | `mergeContacts.js`'s `_isProviderSource(resolvedSource) ? now : undefined` gating (per-field, from `opts.sourceByField`); ingest lane's history HTTP hop added via `splice_carry_merge_after` (no by-name `$()` read, per D-70-03/04); exercised by `tests/n8n/contactHistoryFlow.test.mjs` (green). |
| D-72-08 | System-correctable clause (§17.2.1) generalizes to `stale_refreshable` fields under the same 4 conjuncts | ✓ VERIFIED | `system_correctable_sources` present at `config/field_policy.yaml:18,30,277` (contacts.jobtitle, companies.industry, plus pre-existing companies.domain); `_isSystemCorrectable` present in `mergeContacts.js` (~L180), `mergeCompanies.js` (~L227), `src/merge_policy.py`. |
| D-72-09 | Recency + system-correctable land in all 3 engines (Phase 46 parity) | ✗ FAILED — recency/system-correctable predicates ARE parity-correct; the newer overflow-dedup predicate is NOT | See gap #3 above (WR-02). The specific predicates this decision names (recency, system-correctable) are confirmed byte-identical in shape across all three files. But Phase 72's own new overflow-slot dedup logic — added under the SAME "one merge-policy predicate, three engines" rule this decision states — diverges in case-sensitivity between the JS pair and the Python oracle, untested by either suite. |
| D-72-10 | Second email → `hs_additional_emails` if string-typed+writable, else provenance-only fallback | ⚠️ Design decision VERIFIED as evidence-based; the live behavior is NOT OBSERVED | Live portal probe (`72-PORTAL-PROBE.json`) found `hs_additional_emails` is `enumeration`-typed — the write path was correctly never built, a deliberate and well-evidenced choice, not a gap. But the live gate's two rows each returned only one email, so the provenance-only fallback itself was never exercised against real dual-email data (`72-UAT.md`: "NOT OBSERVED"). Routed to human verification, not scored as a gap. |
| D-72-11 | Exactly one `_2` overflow slot per kind, created once at setup, no `_3` ever | ✓ VERIFIED | `config/hubspot_properties.yaml:254,494,500` declares exactly `lv_phone_2` (contacts), `lv_phone_2` (companies), `lv_mobilephone_2` (contacts); `72-UAT.md` Task 1 confirms all three exist live; no `_3` property found anywhere; `tests/n8n/overflowSlots.test.mjs` green. |
| D-72-12 | Trust-rank winner takes primary slot, runner-up takes `_2`, no judge call for phone/email disagreement | ✓ VERIFIED | `config/source_registry.yaml` trust_rank reused; `tests/test_judge_spec.py::test_ro2_judge_gate_cannot_see_size_conflicts` stays green (RO-2 unbroken). |
| D-72-13 | Verification stamps = provenance JSON only, no new per-field `_source`/`_verified_at` properties | ✓ VERIFIED | No new `_source`/`_verified_at`/`_evidence_url` property found for any new slot; `lv_contact_enrichment_provenance`/`lv_enrichment_provenance` are the two stamped keys, live-confirmed populated on both Busteed and Telfer. |
| D-72-14 | Companies gain phone + domain slots; company email stays a non-goal | ✓ VERIFIED | `config/field_policy.yaml:197,324` declares companies `lv_phone_2`; `hs_additional_domains` scoped per plan 06's probe-driven decision; no company email property created anywhere. |
| D-72-15 | Geo lands as names and codes only when provider supplies a code — nothing derived by guessing | ✓ VERIFIED | Live-confirmed on Busteed: `hs_country_region_code` landed `AU` (a returned code), `hs_state_code` correctly stayed null (none returned) — exactly the "never guess" behavior; `n8n/code/normalizeProviders.js` company branches only push provider-shaped values (`tests/n8n/normalizeProviders.test.mjs` green). |
| D-72-16 | Contact geo never feeds `lv_country_region_normalized` | ✓ VERIFIED | `MERGE_CONTACTS`'s candidate field list has no `lv_country_region_normalized` entry; every occurrence of that property name in the codebase traces to company-branch code only; plan 06's guard test forced RED via a temporary fake derivation then reverted, confirming the test can catch a violation. |
| D-72-17 | End-of-phase live gate: create one absent person, confirm mapped fields land; one UPDATE row proves non-clobber | ✗ FAILED (same root cause as D-72-04) | `72-UAT.md`: mobilephone, phone, jobtitle, seniority, city, state, country, hs_country_region_code, hs_linkedin_url, lv_persona_group, provenance all landed correctly on the CREATE row; `lv_linkedin_url` did not — this is precisely what the gate's own must-have required to be BOTH properties, and only one landed. UPDATE row's non-blank `phone` correctly unchanged (that half of D-72-17 is met). Contact hand-deleted after. Scored FAILED as one decision, not double-counted with D-72-04 — it is the same defect observed through the gate that names it explicitly. |
| D-72-18 | (superseded by D-72-21) | N/A | Not separately scored. |
| D-72-19 | LinkedIn naming closes inside `merge_enriched` via a one-entry alias table, not a new column | ✓ VERIFIED | `PROVIDER_KEY_ALIASES = {"lv_linkedin_url": "linkedin_url"}` present in `operator-claude-plugin/scripts/preingest.py`; `tests/n8n/columnMapIdentityParity.test.mjs` stays green UNMODIFIED. The alias itself works correctly on the Python side — it is a downstream JS consumer's failure to account for the SAME alias that produces the D-72-04 gap, not a defect in D-72-19's own mechanism. |
| D-72-20 | CSV-conflict loser recorded in `MergeResult.conflicts`/report only, never in the persisted held-entry schema | ✓ VERIFIED | `MergeResult.answered_fields` and `.conflicts` fields present in `preingest.py`; held-entry schema (`hold_code`, `reason`, `observed_signals`, `resume_fingerprint`, `row`, `company_known`) confirmed unchanged — no `source_values` key in `held_queue.py`. |
| D-72-21 | Deploy scope widens to every regenerated workflow whose JSON changed, disarmed, node counts + v1 read back | ✓ VERIFIED | `72-UAT.md` Task 1: all 5 cloud workflows deployed+bounced disarmed, node counts 78/287/55/43/30 match committed exactly — independently reconfirmed in this verification by re-running `scripts/build_cloud_workflows.py` from a clean tree with zero git diff; `settings.executionOrder: "v1"` confirmed on all 5; every `ALLOW_*` write flag `false`. |
| D-72-22 | Provider-sourced ingest fields get 85 confidence, not flat csv/80 | ✓ VERIFIED (mechanism correct; its own key-vocabulary edge case for LinkedIn is D-72-04's gap, not counted twice) | The `confidenceByField[f] = 85` derivation exists exactly as specified and is live-confirmed working for `mobilephone` (Busteed create) and for `lv_linkedin_url` on the UPDATE path (Telfer). |
| D-72-23 | Three overflow-slot properties created live in plan 05, verified-not-recreated in plan 08 | ✓ VERIFIED | `72-UAT.md` Task 1 Step 1: sync tool reports 0 pending creates for all three properties on both dry-run and armed run, confirming they already existed and plan 08 correctly only verified rather than re-created. |

**Score:** 19/22 scorable decisions fully verified. 3 FAILED (D-72-04/D-72-17, one shared root
cause counted once; D-72-01/D-72-06, one shared root cause counted once; D-72-09, a second,
unrelated root cause). 1 not-observed-but-well-evidenced (D-72-10, human verification, not a gap).

### Roadmap Goal Assessment

The goal names five field categories by name: "mobile, LinkedIn, seniority, persona,
city/state/country." Four of five are proven landing on a CREATED contact via the cloud ingest
lane, in the phase's own live gate (mobile, seniority, persona, city/state/country + ISO codes).
**LinkedIn is the one category that does not fully land**: `hs_linkedin_url` (native) lands, but
`lv_linkedin_url` (canonical — the property the rest of the system reads for scoring, dedupe, and
provenance) does not, on the create path specifically. This was one of the four operator rulings
that chartered the entire phase (`71-UAT.md` F71-5, ruling (1): "fix the LinkedIn naming
defect"), and the phase's own end-of-phase gate is what caught it as still broken. Separately, the
phase's own code review surfaced a real non-clobber hole (CR-01) on a second, real deployed lane
(`wf_enrichment_local_live.json`) that the live gate never exercised (the gate only exercised the
cloud ingest + cloud enrichment lanes), and a Phase-46-parity divergence (WR-02) in new code this
phase added. **The phase goal is not fully achieved as shipped at HEAD.** All three gaps are
narrow, isolated, and precisely diagnosed — not structural or design failures — but they are
concrete, reproducible, and none is a matter of interpretation.

### Required Artifacts

All artifacts named across the 8 plans' `must_haves.artifacts` blocks exist at HEAD (verified by
direct file check). No MISSING, no STUB (spot-checked content against plan descriptions;
substantive implementations found).

### Key Link Verification

| From | To | Via | Status |
|---|---|---|---|
| `config/column_mapping.yaml` | `n8n/code/columnMap.js` | Byte-parity test (green node suite) | ✓ WIRED |
| `config/field_policy.yaml` | `n8n/code/mergeContacts.js` `DEFAULT_CONTACT_POLICY` | `test_field_policy_conformance.py::test_key_sets_are_identical` (green) | ✓ WIRED |
| `ADAPT_SEARCH_RESULTS` (cloud) | `MERGE_CONTACTS`'s `existingRecord` | Confirmed `row.existingRecord \|\| {}` at merge call site | ✓ WIRED |
| `HS_SEARCH_BODY_EXPR`/`HS_CO_SEARCH_BODY_EXPR` (local-live) | `ENRICH_MERGE`'s `existingRecord` | Confirmed by direct read: fetch lists NOT widened for lv_phone_2/lv_mobilephone_2/state/hs_state_code/phone | ✗ NOT WIRED — CR-01 |
| `preingest.merge_enriched`'s `PROVIDER_KEY_ALIASES` | ingest lane's `row.linkedin_url` read | Wired on the Python side; breaks at the JS `confidenceByField` consumer | ⚠️ PARTIAL — D-72-04 |
| `config/source_registry.yaml` trust_rank | slot routing (`_2` overflow) in all 3 merge engines | Case-sensitivity diverges between JS pair and Python oracle | ⚠️ PARTIAL — WR-02 |
| `scripts/build_cloud_workflows.py` | all 8 `n8n/wf_*.json` | Re-ran generator from clean tree — zero git diff | ✓ WIRED |

### Behavioral Spot-Checks

Full pytest suite: **4947 passed, 154 skipped, 0 failed.** Full node suite: **1167 passed, 0
failed.** Both match the stated baseline exactly — and both stayed green through every gap found
here, confirming none is caught by the existing regression suite (consistent with `72-REVIEW.md`'s
own statement). `scripts/build_cloud_workflows.py` re-run from a clean checkout produced zero diff
against the 5 committed cloud workflow JSONs. `scripts/todo_triage.py --check` exits 0.

### Probe Execution

No `scripts/*/tests/probe-*.sh` convention used by this phase; the phase's equivalent live-check
mechanism is the D-72-17/D-72-21 UAT gate (`72-UAT.md`), reviewed above as primary live evidence
rather than re-run (re-running would require live HubSpot/n8n writes, prohibited here and by the
phase's own "exactly one record" gate discipline).

### Requirements Coverage

No REQUIREMENTS.md rows map to Phase 72, by design. All 23 D-72-NN decisions (22 scorable,
D-72-18 superseded) are accounted for in the Decision-by-Decision table above.

### Anti-Patterns Found

No unresolved `TBD`/`FIXME`/`XXX` debt markers in any of the 11 core implementation files
scanned (one false-positive hit in `src/merge_policy.py` for the literal string `\uXXXX`
describing a JSON escape format). No stub patterns found in the merge engines or ingest lane
candidate assembly. No `<verify><human-check>` blocks found in any of the 8 plans
(`grep -l "human-check" .planning/phases/72-*/72-0*-PLAN.md` returns nothing) — no planner-deferred
human checks to harvest beyond what F72-3 and D-72-10 already surface from the UAT.

### Human Verification Required

1. **D-72-10 second-email path** — genuinely unexercised against real dual-email data (see
   frontmatter).
2. **F72-3 item 1** — is `mobilephone` duplicating an existing `phone` value acceptable?
3. **F72-3 item 2** — should a matched UPDATE row's CSV identity corrections ever apply?

## Gaps Summary

Three real, precisely-diagnosed gaps, all independently re-derived by direct code read in this
verification (not taken on any prior report's word alone):

1. **D-72-04/D-72-17 (LinkedIn dual-write incomplete on CREATE).** A key-vocabulary mismatch
   between `source_by_field`'s post-alias name and the merge candidate's own key in
   `MERGE_CONTACTS` (`scripts/build_cloud_workflows.py`) silently withholds `lv_linkedin_url` on
   every newly-created contact. Caught by the phase's own live gate, not by the regression suite.
2. **D-72-01/D-72-06 (CR-01 — non-clobber hole on the local-live enrichment lane).** Two fetch-list
   constants (`HS_SEARCH_BODY_EXPR`, `HS_CO_SEARCH_BODY_EXPR`) were not widened alongside their
   cloud-lane siblings, so `wf_enrichment_local_live.json` — a real, deployed workflow — can
   silently overwrite real phone/state/overflow values it never fetched to check. Caught by the
   phase's own code review, not by the live gate (which never exercised this lane) or the
   regression suite.
3. **D-72-09 (WR-02 — overflow-dedup case-sensitivity parity drift).** The two JS merge engines
   dedupe overflow candidates case-sensitively; the Python oracle does so case-insensitively,
   breaking the Phase 46 "one predicate, three engines" contract for this one new predicate. Low
   real-world likelihood for phone fields specifically, untested by either suite either way.

All three are small, localized, and each ships with a worked fix in `72-REVIEW.md` — this is
gap-closure-plan-sized work, not a phase re-plan. Everything else the phase's five named field
categories promise (mobile, seniority, persona, city/state/country, and LinkedIn's native-property
half) is proven landing live on both a CREATE and an UPDATE row via the cloud lane, with SAFE-01
non-clobber also proven live on that lane's UPDATE row. Two additional items are recorded as open
operator decisions (F72-3) rather than gaps, since no plan's must-haves asserts a specific
behavior for either. The phase is close to its goal but did not fully achieve it as shipped.

---

_Verified: 2026-09-12T14:34:52Z_
_Verifier: Claude (gsd-verifier)_
