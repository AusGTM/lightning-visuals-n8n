---
phase: 72-enrichment-extras-land-in-hubspot
plan: 02
subsystem: n8n-ingest
tags: [n8n, ingest, mergeContacts, columnMap, field-policy, non-clobber-merge, parity-test]

requires:
  - phase: 72-enrichment-extras-land-in-hubspot
    plan: 01
    provides: mobilephone split off phone, existingRecord wiring on the ingest lane's
      Merge Contacts, and the D-72-22 confidenceByField mechanism this plan's fixtures reuse
provides:
  - "config/column_mapping.yaml + columnMap.js widened with 7 new canonical alias targets (city, state, country, hs_state_code, hs_country_region_code, seniority, lv_persona_group)"
  - "MERGE_CONTACTS candidate loop mirrors ENRICH_MERGE's already-wide loop — the ingest lane now offers every promotable contact key except the deliberately lane-side-only lv_linkedin_url"
  - "hs_linkedin_url: a second, native write target for LinkedIn (D-72-04), with its own explicit field_policy entry and DEFAULT_CONTACT_POLICY twin"
  - "tests/n8n/widenedKeyParity.test.mjs: a derived three-way parity test binding config/field_policy.yaml, config/column_mapping.yaml and the committed ingest candidate loop"
affects: [72-03, 72-04, 72-08]

actuals:
  tokens: 134287
  tasks: 3
  commits: 3
plan_head_before: d7f714d910f637e8a886f5a36d04ab4158dcec07

tech-stack:
  added: []
  patterns:
    - "config-derived allowlist, never a restated literal — new field_policy.yaml keys reach every consumer (columnMap.js, the ingest candidate loop, review's decision CSV, promotable_contact_props) by widening the YAML, never a second Python/JS list"
    - "a native-property mirror of an already PN-1-renamed field (hs_linkedin_url mirroring lv_linkedin_url) is written from the SAME canonicalized value at the SAME call site in both merge wrappers (MERGE_CONTACTS and ENRICH_MERGE), one commit, Phase 46 parity discipline extended to a same-lane sibling-write case"

key-files:
  created:
    - tests/n8n/widenedKeyParity.test.mjs
  modified:
    - config/column_mapping.yaml
    - operator-claude-plugin/config/column_mapping.yaml
    - n8n/code/columnMap.js
    - config/field_policy.yaml
    - operator-claude-plugin/config/field_policy.yaml
    - n8n/code/mergeContacts.js
    - scripts/build_cloud_workflows.py
    - n8n/wf_contact_ingest_cloud.json
    - n8n/wf_contact_ingest_local.json
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_review_decision_cloud.json
    - tests/n8n/ingestWidenedFieldsFlow.test.mjs
    - tests/n8n/fieldProducerMatrix.test.mjs
    - tests/test_fetch_by_id_topology.py
    - operator-claude-plugin/tests/test_extraction_handoff.py
    - operator-claude-plugin/tests/test_preingest_merge.py
    - operator-claude-plugin/scripts/suggestion_declines.py
    - operator-claude-plugin/skills/contact-upload/extraction.md

key-decisions:
  - "hs_linkedin_url added to the ENRICH lane's contact search fetch lists (HS_SEARCH_BODY_EXPR and ENRICH_CONTACT_SEARCH_PROPERTIES_CSV), not just the ingest lane's — the same WR-01/WR-02 non-clobber defect class the file's own comments warn about would otherwise apply to this brand-new field on the enrichment lane's search-matched path."
  - "fieldProducerMatrix.test.mjs's PN-1 rename detection generalized from a single hardcoded lv_ prefix to a small PN1_PREFIXES list (lv_, hs_) so it correctly recognizes hs_linkedin_url as producer-having (it mirrors Apollo's unprefixed linkedin_url push, same as lv_linkedin_url) instead of reporting a genuinely-produced field as producer-less."
  - "A new, explicit NEVER_CHASE exclusion (distinct from the file's pre-existing KNOWN_GAPS list) documents that hs_linkedin_url deliberately stays out of ENRICH_GATE's REQUIRED despite having a producer — the D-66-01/T-66-04 economics the plan calls for, now enforced by a test rather than only by comment."

requirements-completed: [D-72-01, D-72-02, D-72-04]

coverage:
  - id: D1
    description: "D-72-01: the remaining seven promotable_contact_props() keys (city, state, country, hs_state_code, hs_country_region_code, seniority, lv_persona_group) reach the ingest lane's HubSpot Create body on a net_new row"
    requirement: D-72-01
    verification:
      - kind: integration
        ref: "tests/n8n/ingestWidenedFieldsFlow.test.mjs#D-72-01: the remaining seven widened keys reach HubSpot Create for a net_new row"
        status: pass
    human_judgment: false
  - id: D2
    description: "D-72-01: the five fill_blank_only location keys are withheld from an update whose contact already holds different non-blank values; the two system_owned keys (seniority, lv_persona_group) still promote regardless"
    requirement: D-72-01
    verification:
      - kind: integration
        ref: "tests/n8n/ingestWidenedFieldsFlow.test.mjs#D-72-01: the five location keys are withheld from an update that already holds different values; the two system_owned keys still promote"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-72-04: a linkedin_url header value produces a Create body carrying BOTH lv_linkedin_url (canonical, PN-1) and hs_linkedin_url (native), from one canonicalization at one call site in both MERGE_CONTACTS and ENRICH_MERGE"
    requirement: D-72-04
    verification:
      - kind: integration
        ref: "tests/n8n/ingestWidenedFieldsFlow.test.mjs#D-72-04: a linkedin_url header value produces a Create body carrying BOTH lv_linkedin_url and hs_linkedin_url"
        status: pass
    human_judgment: false
  - id: D4
    description: "D-72-04: hs_linkedin_url is withheld from an update whose contact already holds a different non-blank value (fill_blank_only non-clobber), proven against a real existingRecord fetch"
    requirement: D-72-04
    verification:
      - kind: integration
        ref: "tests/n8n/ingestWidenedFieldsFlow.test.mjs#D-72-04: hs_linkedin_url is withheld from an update whose contact already holds a different non-blank value"
        status: pass
    human_judgment: false
  - id: D5
    description: "D-72-02: config/field_policy.yaml is the single source of which contact keys reach HubSpot — a derived, three-way parity test (policy <-> column map <-> committed candidate loop) now fails if any of the three widens without the others"
    requirement: D-72-02
    verification:
      - kind: unit
        ref: "tests/n8n/widenedKeyParity.test.mjs (all three assertions)"
        status: pass
    human_judgment: false
  - id: D6
    description: "The enrichment gate's REQUIRED array stays at exactly twelve keys after field_policy.yaml grows to thirteen (hs_linkedin_url added) — a write-only target must never widen the chase list and trigger provider spend"
    requirement: D-72-02
    verification:
      - kind: unit
        ref: "Task 2 verify: python regex extraction of const REQUIRED = [...] in scripts/build_cloud_workflows.py, asserted length 12"
        status: pass
      - kind: unit
        ref: "tests/n8n/fieldProducerMatrix.test.mjs's chase-gate assertion, with hs_linkedin_url in the file's own NEVER_CHASE exclusion"
        status: pass
    human_judgment: false
  - id: D7
    description: "config/field_policy.yaml and config/column_mapping.yaml stay byte-identical with their operator-claude-plugin shipped copies after both widenings"
    verification:
      - kind: unit
        ref: "diff -q config/field_policy.yaml operator-claude-plugin/config/field_policy.yaml; diff -q config/column_mapping.yaml operator-claude-plugin/config/column_mapping.yaml"
        status: pass
    human_judgment: false
  - id: D8
    description: "No column_mapping.yaml change for LinkedIn identity: required_identity.any_of keeps its three groups verbatim, and columnMapIdentityParity.test.mjs stays green unmodified"
    verification:
      - kind: unit
        ref: "tests/n8n/columnMapIdentityParity.test.mjs (unmodified, green)"
        status: pass
    human_judgment: false

duration: 65min
completed: 2026-09-12
status: complete
---

# Phase 72 Plan 02: Enrichment Extras Land in HubSpot — Widened Ingest Candidate + Native LinkedIn Summary

**The ingest lane's candidate loop now mirrors the enrichment lane's already-wide one (seven more promotable contact keys reach HubSpot on create/update, non-clobber intact), LinkedIn lands in the native `hs_linkedin_url` property alongside the canonical `lv_linkedin_url`, and a new derived test binds `field_policy.yaml`, `column_mapping.yaml` and the committed ingest workflow so the three can never drift apart silently again.**

## Performance

- **Duration:** ~65 min
- **Tasks:** 3
- **Files modified:** 21 (1 created, 20 modified)

## Accomplishments

- `config/column_mapping.yaml` (+ the byte-identical shipped copy) and `n8n/code/columnMap.js` gained alias groups for `city`, `state`, `country`, `hs_state_code`, `hs_country_region_code`, `seniority`, `lv_persona_group` — `column_mapping_canonical_targets` grew from 9 to 16.
- `MERGE_CONTACTS`'s candidate loop (`scripts/build_cloud_workflows.py`) widened from six keys to thirteen, mirroring `ENRICH_MERGE`'s already-wide loop but reading `row.*` (CSV-sourced) instead of `winners.*` (waterfall-sourced) — unlike `ENRICH_MERGE`, `lv_persona_group` needs no separate rename block here because `columnMap.js` already maps a CSV header straight to the PN-1 canonical key.
- The ingest lane's `HubSpot Search by Email` node now fetches the same widened property set (plus `hs_linkedin_url`), so the merge gates every one of the new candidates against a real existing value instead of always reading blank.
- Added `hs_linkedin_url` as a new `config/field_policy.yaml`/`DEFAULT_CONTACT_POLICY` entry (`fill_blank_only`/85, mirroring `lv_linkedin_url` exactly) and wired both `MERGE_CONTACTS` and `ENRICH_MERGE` to write it alongside `lv_linkedin_url` from the same canonicalized value — deliberately NOT added to `ENRICH_GATE`'s twelve-key `REQUIRED` list, so a blank native mirror never marks a contact incomplete and triggers provider spend.
- Widened the enrichment lane's own contact search fetch lists (`HS_SEARCH_BODY_EXPR`, `ENRICH_CONTACT_SEARCH_PROPERTIES_CSV`) to also fetch `hs_linkedin_url`, closing the same non-clobber gap on that lane before it could ever manifest (see Deviations).
- Rewrote the old count-hardcoded `test_promotable_contact_props_names_the_twelve_promotable_contact_keys` to derive its expected set fresh from the YAML via PyYAML — the function's job is "returns exactly the policy's promotable keys," not "returns twelve of them."
- New `tests/n8n/widenedKeyParity.test.mjs`: a third parity dimension (alongside `columnMapAliasParity`/`columnMapIdentityParity`) binding `field_policy.yaml`'s promotable contacts, `column_mapping.yaml`'s canonical targets, and the COMMITTED `n8n/wf_contact_ingest_cloud.json`'s actual candidate loop — three assertions, all derived from the real config files and the real shipped JSON, none restating a key list.
- Regenerated every `n8n/wf_*.json`; confirmed idempotent (a second consecutive regenerate produced zero further diff), `settings.executionOrder: "v1"` everywhere, and no armed write-safety literal anywhere (`ALLOW_HUBSPOT_RECORD_WRITES = "true"` / `ALLOW_HUBSPOT_CREATE = "true"` both grep to zero hits across every `n8n/wf_*.json`).

## Task Commits

1. **Task 1: the remaining seven widened keys reach the ingest candidate** — `108ae0ba` (feat)
2. **Task 2: LinkedIn lands natively too — `hs_linkedin_url` as a second write target** — `de578a58` (feat)
3. **Task 3: one derived parity test binds policy, column map and lane candidate** — `0fecbb00` (test)

**Plan metadata:** this commit (SUMMARY + STATE + ROADMAP + REQUIREMENTS).

## Files Created/Modified

- `tests/n8n/widenedKeyParity.test.mjs` — new. Three derived assertions binding policy, column map, and the committed ingest candidate loop.
- `config/column_mapping.yaml`, `operator-claude-plugin/config/column_mapping.yaml`, `n8n/code/columnMap.js` — seven new canonical alias targets (byte-identical copies confirmed).
- `config/field_policy.yaml`, `operator-claude-plugin/config/field_policy.yaml`, `n8n/code/mergeContacts.js` — new `hs_linkedin_url` entry (byte-identical copies confirmed).
- `scripts/build_cloud_workflows.py` — `MERGE_CONTACTS` and `ENRICH_MERGE` candidate loops widened; both write `hs_linkedin_url` alongside `lv_linkedin_url`; `HubSpot Search by Email`, `HS_SEARCH_BODY_EXPR`, and `ENRICH_CONTACT_SEARCH_PROPERTIES_CSV` all widened to fetch the new fields; `ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV`'s suffix simplified now that `hs_linkedin_url` lives in the base search CSV.
- `n8n/wf_contact_ingest_cloud.json`, `n8n/wf_contact_ingest_local.json`, `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local.json`, `n8n/wf_enrichment_local_live.json`, `n8n/wf_review_decision_cloud.json` — regenerated.
- `tests/n8n/ingestWidenedFieldsFlow.test.mjs` — extended with 4 new tests (the two widened-keys behaviors from Task 1, the two `hs_linkedin_url` behaviors from Task 2) plus 1 new header-aliasing test — 9 tests total in this file now.
- `tests/n8n/fieldProducerMatrix.test.mjs` — `pn1Renames`'s prefix check generalized from a hardcoded `lv_` to a `PN1_PREFIXES` list (`lv_`, `hs_`); a new `NEVER_CHASE` exclusion documents `contacts.hs_linkedin_url`'s deliberate REQUIRED exemption. `[Rule 1]` fix, see Deviations.
- `tests/test_fetch_by_id_topology.py` — updated for `hs_linkedin_url` moving from the fetch-by-id suffix into the base search CSV. `[Rule 1]` fix, see Deviations.
- `operator-claude-plugin/tests/test_extraction_handoff.py` — `CANONICAL_PROPS` literal widened to the new sorted sixteen (Task 1's designated job).
- `operator-claude-plugin/tests/test_preingest_merge.py` — five pre-existing tests updated: three swapped their demonstrative "still-extra" field from `seniority` (now canonical) to `lv_linkedin_url`; the shared-key-set test's expected set grew from four to eleven; the promotable-keys test rewritten per Task 2's instruction; `expected_min_confidence` gained `hs_linkedin_url: 85`. `[Rule 1]` fixes, see Deviations.
- `operator-claude-plugin/scripts/suggestion_declines.py` — `ROW_FIELD_ALLOWLIST` widened by the same seven keys, restoring its documented invariant (`== extraction.canonical_props()`). `[Rule 1]` fix, see Deviations.
- `operator-claude-plugin/skills/contact-upload/extraction.md` — canonical-vocabulary block widened to the new sixteen; `[Rule 3]` fix, see Deviations.

## Decisions Made

- **hs_linkedin_url fetched on the enrichment lane too, not just ingest** (Rule 2 — missing critical non-clobber correctness): the file's own comments at `ENRICH_CONTACT_SEARCH_PROPERTIES_CSV` document the exact WR-01/WR-02 defect class — a merge-candidate field with no fetch producer always reads blank and silently clobbers a real value on a later run. `hs_linkedin_url` is a brand-new merge candidate as of this plan, so both `HS_SEARCH_BODY_EXPR` (local-live) and `ENRICH_CONTACT_SEARCH_PROPERTIES_CSV` (cloud) were widened to include it, closing the gap before any real traffic could hit it. Not requested verbatim by the plan's action text but directly implied by D-72-04's own `fill_blank_only`/`protect_if_current_present` policy shape.
- **`fieldProducerMatrix.test.mjs`'s PN-1 rename detection generalized** (Rule 1 — pre-existing test broken by this plan's own correct change): the D-66-07 producer gate reported `hs_linkedin_url` as producer-less, because its detection only recognized `lv_` as a PN-1 prefix. Since `hs_linkedin_url` genuinely mirrors `lv_linkedin_url`'s Apollo-sourced producer (same call site, same value), the fix generalizes the prefix list (`lv_`, `hs_`) rather than special-casing this one field, so a future same-shaped addition is caught by the same mechanism.
- **A new `NEVER_CHASE` exclusion, distinct from the pre-existing `KNOWN_GAPS`**, was added to the same test file for the chase-gate assertion: `hs_linkedin_url` now HAS a recognized producer, so the chase gate would otherwise demand it appear in `REQUIRED` — which D-72-04 explicitly forbids. `KNOWN_GAPS` documents absence-of-producer facts; `NEVER_CHASE` documents a deliberate "has a producer, stays unchased" fact — a different claim, so a different, explicitly named mechanism.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] `hs_linkedin_url` was not fetched by the enrichment lane's contact search, only the ingest lane's**
- **Found during:** Task 2, after adding `hs_linkedin_url` as a new merge candidate in both `MERGE_CONTACTS` and `ENRICH_MERGE`.
- **Issue:** The plan's action text for Task 2 only mentioned widening the ingest lane's search node (implicitly, via the general non-clobber testing goal); it did not call out the enrichment lane's OWN contact search fetch lists. Left unfetched there, `existingRecord.hs_linkedin_url` would always read `undefined` on the enrichment lane, silently permitting an overwrite of a real value on a second enrichment pass — the exact defect class the file's own comments (`ENRICH_CONTACT_SEARCH_PROPERTIES_CSV`) document for `lv_linkedin_url`/`lv_persona_group`.
- **Fix:** Added `hs_linkedin_url` to `HS_SEARCH_BODY_EXPR` (local-live) and `ENRICH_CONTACT_SEARCH_PROPERTIES_CSV` (cloud); simplified `ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV`'s suffix now that it lives in the base list.
- **Files modified:** `scripts/build_cloud_workflows.py`, regenerated `n8n/wf_enrichment_cloud.json`/`n8n/wf_enrichment_local_live.json`.
- **Verification:** `node --test tests/n8n/*.test.mjs` full suite green; `tests/n8n/fieldProducerMatrix.test.mjs`'s fetch-gate assertions pass.
- **Committed in:** `de578a58` (Task 2 commit).

**2. [Rule 1 - Bug] `fieldProducerMatrix.test.mjs`'s D-66-07 producer gate reported `hs_linkedin_url` as producer-less**
- **Found during:** Task 2, running the full node suite after adding `hs_linkedin_url` to both merge wrappers.
- **Issue:** `pn1Renames()` only checked for an `lv_` prefix on an unprefixed `winners.X` read, so it could not see that `hs_linkedin_url` is written from the same `winners.linkedin_url` read as the already-recognized `lv_linkedin_url` rename. The test reported `contacts.hs_linkedin_url` as having zero producers, though a real one exists.
- **Fix:** Generalized `pn1Renames()` to check a small `PN1_PREFIXES` list (`lv_`, `hs_`) instead of a hardcoded single prefix; the resulting chase-gate assertion then correctly demanded `hs_linkedin_url` be chased (since it now has a recognized producer), which D-72-04 forbids — added an explicit `NEVER_CHASE` exclusion set (distinct from the pre-existing `KNOWN_GAPS`) documenting why.
- **Files modified:** `tests/n8n/fieldProducerMatrix.test.mjs`.
- **Verification:** `node --test tests/n8n/*.test.mjs` (1113/1113 pass).
- **Committed in:** `de578a58` (Task 2 commit).

**3. [Rule 1 - Bug] Five `operator-claude-plugin` tests hardcoded `seniority` as a "still-extra" (policy-only, non-canonical) demonstrative key**
- **Found during:** Task 1, running the full plugin suite after widening `column_mapping.yaml`.
- **Issue:** `test_strip_enrichment_extras_drops_exactly_the_policy_only_keys`, `test_without_the_new_strip_the_step_7_chain_raises_non_canonical_key_in_row`, `test_the_suggest_contacts_path_tolerates_a_widened_key_through_validate`, `test_merge_allowlist_falls_back_to_canonical_props_when_the_policy_is_unreadable`, and `test_the_allowlist_is_a_union_and_a_shared_key_behaves_as_before` all used `seniority` to demonstrate a key that is promotable but not canonical (i.e. gets stripped/dropped). Widening `column_mapping.yaml` made `seniority` canonical too, so these assertions became false.
- **Fix:** Swapped the demonstrative key to `lv_linkedin_url` (the one remaining key in `promotable_contact_props() - canonical_props()`, per D-72-19) in the four negative-case tests; updated the shared-key-set test's expected set from four keys to the new eleven; updated `expected_min_confidence` and the promotable-keys test per Task 2's own instruction.
- **Files modified:** `operator-claude-plugin/tests/test_preingest_merge.py`.
- **Verification:** `.venv/bin/python -m pytest -q operator-claude-plugin/tests/` (3038 passed, 5 skipped).
- **Committed in:** `108ae0ba` (Task 1 commit).

**4. [Rule 1 - Bug] `test_contact_fetch_by_id_properties_csv_adds_company_and_linkedin_to_the_search_csv` pinned the old fetch-by-id suffix shape**
- **Found during:** Task 2, running the full root pytest suite.
- **Issue:** The test asserted `hs_linkedin_url` appeared in the fetch-by-id SUFFIX (its old, by-id-only location). Moving it into the base `ENRICH_CONTACT_SEARCH_PROPERTIES_CSV` (deviation #1 above) made the suffix just `,company`.
- **Fix:** Updated the test to assert `hs_linkedin_url` (like `lv_linkedin_url`) now lives in the base search CSV and is absent from the suffix, mirroring the existing `lv_linkedin_url` assertions in the same test.
- **Files modified:** `tests/test_fetch_by_id_topology.py`.
- **Verification:** `.venv/bin/python -m pytest -q tests/test_fetch_by_id_topology.py` (20 passed).
- **Committed in:** `de578a58` (Task 2 commit).

**5. [Rule 3 - Blocking] `suggestion_declines.ROW_FIELD_ALLOWLIST` and `extraction.md`'s canonical-vocabulary list did not name the seven new canonical props**
- **Found during:** Task 1, running the full plugin suite.
- **Issue:** `test_row_field_allowlist_matches_canonical_props_and_excludes_row_id` requires `ROW_FIELD_ALLOWLIST == extraction.canonical_props()` exactly; `test_every_canonical_prop_is_named_in_extraction_md` requires every canonical prop be named in the doc's prose. Both broke once `canonical_props()` grew to sixteen.
- **Fix:** Widened `ROW_FIELD_ALLOWLIST` with the same seven keys; widened `extraction.md`'s "Canonical props" block and its "these N are all there is" prose to sixteen.
- **Files modified:** `operator-claude-plugin/scripts/suggestion_declines.py`, `operator-claude-plugin/skills/contact-upload/extraction.md`.
- **Verification:** `.venv/bin/python -m pytest -q operator-claude-plugin/tests/` full suite green.
- **Committed in:** `108ae0ba` (Task 1 commit).

---

**Total deviations:** 1 Rule 2 (missing critical), 3 Rule 1 (bug/pre-existing-test-drift groups), 1 Rule 3 (blocking) — covering 8 files beyond the plan's own `<files>` lists.
**Impact on plan:** the Rule 2 fix closes a real non-clobber gap on the enrichment lane before any live traffic could hit it — directly in the spirit of D-72-04's `fill_blank_only`/`protect_if_current_present` intent, not scope creep. Every Rule 1/3 fix is test/doc fallout mechanically caused by widening `canonical_props()`/`promotable_contact_props()`, the exact and expected consequence of this plan's own charter; no production behavior beyond the two widenings themselves was touched.

## Issues Encountered

- **The plan's own top-level `<verification>` block is stale after Task 2.** It restates Task 1's own acceptance criterion — `set(promotable_contact_props()) - set(canonical_props())` is exactly `{"lv_linkedin_url"}` — but Task 2 deliberately adds `hs_linkedin_url` as a second lane-side-only promotable key (D-72-04), which the top-level block was never updated to reflect. Task 3's own, more specific acceptance criteria and `widenedKeyParity.test.mjs` correctly expect `{lv_linkedin_url, hs_linkedin_url}`, which is what this plan implements and verifies (`sorted(p-c) == ['hs_linkedin_url', 'lv_linkedin_url']`). Not treated as a defect to fix in code — the plan text itself needs a one-line correction, noted here for the record rather than silently reconciled.
- **`tests/test_field_policy_conformance.py`'s scope is narrower than Task 2's read_first/action text implies.** That file's `test_key_sets_are_identical` (and its three siblings) compare ONLY `config/field_policy.yaml`'s `companies:` block against `mergeCompanies.js`'s `DEFAULT_COMPANY_POLICY` — it has no `contacts:` counterpart at all. The plan's Task 2 text states this test "requires the two key sets to be equal and will fail otherwise" for the contacts addition; in fact it is a no-op for contacts (passes trivially either way). The contacts-side key-set parity this plan actually relies on is enforced manually (both files edited in the same commit, verified by `diff -q` and the full pytest/node suites) plus, more narrowly, by `widenedKeyParity.test.mjs`'s own assertions. No code change was needed to satisfy this — the acceptance criteria as literally stated (`tests/test_field_policy_conformance.py` passes with no edit to the test file itself) is met — but a reader should not assume this file guards contacts `hs_linkedin_url`/`DEFAULT_CONTACT_POLICY` parity the way it guards companies.

## Known Stubs

None.

## User Setup Required

None — no external service configuration required. Nothing in this plan deploys, bounces, or arms anything (confirmed by the write-safety-literal grep: `ALLOW_HUBSPOT_RECORD_WRITES = "true"` / `ALLOW_HUBSPOT_CREATE = "true"` both grep to zero across every `n8n/wf_*.json`).

## Next Phase Readiness

- Plan 03 can now populate `source_by_field` truthfully on the enrich-before-ingest path (per plan 01's readiness note), making D-72-22's provider-grade confidence reachable in production for every one of the widened keys, not just `mobilephone`.
- Plan 03 is also where D-72-19's naming fork closes inside `merge_enriched` — this plan deliberately left `required_identity.any_of` and the CSV-side `linkedin_url` vocabulary untouched, exactly as instructed.
- `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md`'s D-72-17 gate spec (a later plan's job) should now also read back `hs_linkedin_url` and the five location keys on the armed create, since this plan proves every one of those paths.
- The two `<verification>`/read_first inaccuracies noted under "Issues Encountered" are informational only — no action needed before the next plan, since the implemented behavior is correct per the plan's own more specific, more recent Task 2/3 text.

## Self-Check: PASSED

- `[ -f tests/n8n/widenedKeyParity.test.mjs ]` → FOUND
- `git log --oneline --all | grep -q 108ae0ba` → FOUND
- `git log --oneline --all | grep -q de578a58` → FOUND
- `git log --oneline --all | grep -q 0fecbb00` → FOUND
- All plan-level `<verification>` commands re-run and passing: `node --test tests/n8n/*.test.mjs` (1113/1113), `.venv/bin/python -m pytest -q operator-claude-plugin/tests/ tests/` (4899 passed, 154 skipped), both `diff -q` checks silent (byte-identical), and `set(promotable_contact_props()) - set(canonical_props())` verified as `{lv_linkedin_url, hs_linkedin_url}` (the plan-text discrepancy noted above under Issues Encountered).

---
*Phase: 72-enrichment-extras-land-in-hubspot*
*Completed: 2026-09-12*
