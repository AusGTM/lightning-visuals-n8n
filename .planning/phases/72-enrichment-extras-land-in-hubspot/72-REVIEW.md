---
phase: 72-enrichment-extras-land-in-hubspot
reviewed: 2026-09-13T00:00:00Z
depth: standard
files_reviewed: 33
files_reviewed_list:
  - CLAUDE.md
  - config/column_mapping.yaml
  - config/field_policy.yaml
  - config/hubspot_properties.yaml
  - docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md
  - n8n/code/columnMap.js
  - n8n/code/mergeCompanies.js
  - n8n/code/mergeContacts.js
  - n8n/code/normalizeProviders.js
  - operator-claude-plugin/.claude-plugin/plugin.json
  - operator-claude-plugin/CHANGELOG.md
  - operator-claude-plugin/config/column_mapping.yaml
  - operator-claude-plugin/config/field_policy.yaml
  - operator-claude-plugin/scripts/held_queue.py
  - operator-claude-plugin/scripts/preingest.py
  - operator-claude-plugin/scripts/suggestion_declines.py
  - operator-claude-plugin/skills/contact-upload/extraction.md
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - operator-claude-plugin/skills/review-triage/SKILL.md
  - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
  - operator-claude-plugin/tests/test_extraction_handoff.py
  - operator-claude-plugin/tests/test_held_queue.py
  - operator-claude-plugin/tests/test_preingest_merge.py
  - operator-claude-plugin/tests/test_preview_rendering.py
  - operator-claude-plugin/tests/test_skill_sequence_coverage.py
  - scripts/build_cloud_workflows.py
  - scripts/deploy_n8n_workflows.py
  - src/merge_policy.py
  - tests/n8n/*.test.mjs (the Phase 72 additions/changes listed in the task)
  - tests/test_fetch_by_id_topology.py
  - tests/test_hubspot_properties_config.py
  - tests/test_merge_helpers.py
  - tests/test_merge_policy.py
findings:
  critical: 1
  warning: 2
  info: 0
  total: 3
status: issues_found
---

# Phase 72: Code Review Report

**Reviewed:** 2026-09-13
**Depth:** standard
**Files Reviewed:** 33 (per `required_reading`; diffs taken against `90252e8873d121bf41ae7fd677cfadc83b87ab88^`)
**Status:** issues_found

## Summary

Phase 72 widens the contact-ingest lane and the two enrichment merge lanes (contacts,
companies) to carry several new fields (mobilephone, geo, seniority, persona,
hs_linkedin_url, and overflow-slot phone/mobilephone runner-ups), and adds a
recency/TTL gate plus a system-correctable-arm to all three merge engines
(`n8n/code/mergeContacts.js`, `n8n/code/mergeCompanies.js`, `src/merge_policy.py`).
The three-engine parity (the "Phase 46 rule") is respected almost everywhere I traced
it — the recency gate, the `_isSystemCorrectable` four-conjunct test, and the
`_overflowSlot` closed map are byte-identical in shape across all three files.

Two real gaps survived to this diff, both in the class of defect this very codebase's
own comments repeatedly warn about ("an existingRecord that never fetches a field
reads it as blank, and the non-clobber guard silently becomes a permit to
overwrite"): the CLOUD lane's two existing-record fetch lists were widened correctly
for every new Phase 72 field, but the LOCAL-LIVE lane's two sibling fetch constants
were not — see CR-01. A second, already-known defect (F72-1, confirmed independently
here) leaves the LinkedIn fields' provider-grade confidence override silently inert on
CREATE in the contact-upload lane — see WR-01. A third finding (WR-02) is a genuine,
currently-untested Phase-46-parity divergence in the brand-new overflow-slot dedup
logic. All 1167 `node --test tests/n8n/*.test.mjs` and 4947 `pytest` tests pass; none
of the three findings below is caught by the existing suite.

## Critical Issues

### CR-01: Phase 72's new merge candidates are un-fetched (and therefore un-protected) on the local-live enrichment workflow

**File:** `scripts/build_cloud_workflows.py:2866-2871` (`HS_SEARCH_BODY_EXPR`, contacts) and `scripts/build_cloud_workflows.py:3010-3029` (`HS_CO_SEARCH_BODY_EXPR`, companies)

**Issue:** `build_enrichment_local_live()` (which emits `wf_enrichment_local_live.json`,
a real, deployed/credential-bound workflow — see `deploy_n8n_workflows.py`'s
`NODE_CREDENTIAL_MAP` and the CLAUDE.md §13.0.2 deployment tables that track its node
count through every phase) fetches the matched record's existing properties for its
non-clobber gate through two hand-maintained constants, `HS_SEARCH_BODY_EXPR`
(contacts) and `HS_CO_SEARCH_BODY_EXPR` (companies). Both constants have a sibling
used by the real cloud lane — `ENRICH_CONTACT_SEARCH_PROPERTIES_CSV` and
`ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` respectively — and Phase 72 widened *only* the
cloud siblings:

- `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` (companies, cloud) gained `lv_phone_2` (Plan
  05) and `state,hs_state_code,phone` (Plan 06), each with an explicit comment citing
  the exact non-clobber defect class being avoided. `HS_CO_SEARCH_BODY_EXPR`
  (companies, local-live) gained neither — its property list still ends at
  `"lv_sponsorship_reliant"` (confirmed by inspecting the generated
  `n8n/wf_enrichment_local_live.json`'s "HubSpot Company Search" node, which lists
  23 properties and none of `phone`/`state`/`hs_state_code`/`lv_phone_2`).
- `ENRICH_CONTACT_SEARCH_PROPERTIES_CSV` (contacts, cloud) gained `lv_phone_2` and
  `lv_mobilephone_2` (Plan 05). `HS_SEARCH_BODY_EXPR` (contacts, local-live) gained
  only `hs_linkedin_url` (Plan 02) — it still omits both overflow slots.

Both lanes' merge call site (`ENRICH_MERGE` for contacts, `ENRICH_MERGE_CO` for
companies) is a *single shared constant* used by both `build_enrichment_local_live()`
and `build_cloud()` (confirmed: `code_node("Merge Winners", ENRICH_MERGE, ...)` at
lines 4829 and 6969; `code_node("Merge Company", ENRICH_MERGE_CO, ...)` at lines 4929
and 7250), and that shared code now unconditionally offers `state`/`hs_state_code`/
`phone` (companies) and `lv_phone_2`/`lv_mobilephone_2` (both objects) as merge
candidates. Every one of these fields is `fill_blank_only` with
`protect_if_current_present: true` in `config/field_policy.yaml`. Because
`mergeCompanies.js`/`mergeContacts.js` read `currentValue = existingProps[field]`, and
the local-live lane's `existingProps` never carries these keys, `currentValue` is
always `undefined` — `_isBlank(undefined)` is `true` — so the gate always treats the
field as blank and promotes the provider candidate, even when the HubSpot record
already holds a real, human-entered phone number, state, or overflow value. This is
the exact "WR-01/58-05/VETO-01" defect class the surrounding comments in this same
file were written to prevent, reintroduced for the local-live lane by omission in this
phase.

**Fix:** Widen `HS_SEARCH_BODY_EXPR` to add `"lv_phone_2","lv_mobilephone_2"`, and
widen `HS_CO_SEARCH_BODY_EXPR` to add `"lv_phone_2","state","hs_state_code","phone"`
— mirroring exactly what Plans 05/06 already did to
`ENRICH_CONTACT_SEARCH_PROPERTIES_CSV`/`ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`. Example
for the companies constant:

```python
HS_CO_SEARCH_BODY_EXPR = (
    '={{ JSON.stringify({ filterGroups: [ { filters: '
    '[ { propertyName: "domain", operator: "EQ", value: $json.identity_keys.domain } ] } ], '
    'properties: ["name","domain","industry","annualrevenue","numberofemployees",'
    '"lv_org_type","lv_produces_content","lv_content_type","lv_is_hardware_vendor",'
    '"lv_is_gambling_operator","lv_icp_tier","lv_icp_fit_score","lv_anti_icp_flag",'
    '"lv_enrichment_provenance",'
    '"lv_org_type_verified_at","lv_produces_content_verified_at","lusha_company_id",'
    '"num_associated_contacts",'
    '"lv_revenue_band","lv_employee_band","lv_country_region_normalized","country","city",'
    '"lv_sponsorship_reliant","lv_phone_2","state","hs_state_code","phone"], '
    'limit: 5 }) }}'
)
```

After the fix, regenerate the workflows (`scripts/build_cloud_workflows.py`) and add
these five field names to `tests/n8n/fieldProducerMatrix.test.mjs`'s fetch-gate
assertion (or a new assertion) so a `NEVER_CHASE` (write-map-only, non-REQUIRED) field
is still checked for presence in *every* lane's existing-record fetch, not only the
REQUIRED-driven WR-03 check — this is precisely the kind of drift WR-03 does not catch
today, since these fields are deliberately excluded from `REQUIRED`.

## Warnings

### WR-01: LinkedIn candidates never receive their provider-grade confidence on the contact-upload CREATE path (known defect F72-1)

**File:** `scripts/build_cloud_workflows.py:479-494` (`MERGE_CONTACTS`)

**Issue:** The `confidenceByField` map is built by iterating the keys of
`row.source_by_field`:

```js
const sourceByField = row.source_by_field || {};
const confidenceByField = {};
for (const f of Object.keys(sourceByField)) {
  if (sourceByField[f] && sourceByField[f] !== "csv") confidenceByField[f] = 85;
}
```

`row.source_by_field` is populated upstream by
`operator-claude-plugin/skills/enrich-before-ingest/SKILL.md`'s
`source_by_field = {field_name: "waterfall" for field_name in
preingest.provider_sourced_fields(merge_report)}`. `provider_sourced_fields()` reduces
`MergeResult.answered_fields`, whose keys pass through
`preingest.py`'s `PROVIDER_KEY_ALIASES = {"lv_linkedin_url": "linkedin_url"}` — i.e.
the map is deliberately keyed on the CSV's canonical name `"linkedin_url"`, never on
`"lv_linkedin_url"`.

But a few lines later, `MERGE_CONTACTS` builds the actual merge candidate under the
*renamed* keys:

```js
if (row.linkedin_url != null && String(row.linkedin_url).trim() !== "") {
  candidate.lv_linkedin_url = row.linkedin_url;
  candidate.hs_linkedin_url = row.linkedin_url;
}
```

`mergeContacts()`'s per-field loop iterates `Object.keys(candidateRow)` and looks up
`confidenceByField[field]` by that same (renamed) key. `confidenceByField["linkedin_url"]`
was set to `85`, but `confidenceByField["lv_linkedin_url"]` and
`confidenceByField["hs_linkedin_url"]` are both `undefined`, so the merge falls back to
the flat `flatConfidence` of `80`. Both `lv_linkedin_url` and `hs_linkedin_url` are
`fill_blank_only @ min_confidence: 85` — an 80-confidence candidate can never clear
that bar, even into a completely blank field. Net effect: a LinkedIn URL the waterfall
found for a brand-new contact never lands in HubSpot via this lane, silently and
without any error, review flag, or log line — it is simply never promoted.

**Fix:** Build `confidenceByField` from the *post-alias* candidate keys, not from
`source_by_field`'s raw keys — e.g. apply the same `linkedin_url -> lv_linkedin_url`/
`hs_linkedin_url` mapping used two lines below when constructing `candidate`, before
assigning into `confidenceByField`:

```js
const sourceByField = row.source_by_field || {};
const confidenceByField = {};
for (const f of Object.keys(sourceByField)) {
  if (!sourceByField[f] || sourceByField[f] === "csv") continue;
  confidenceByField[f] = 85;
  if (f === "linkedin_url") {
    confidenceByField.lv_linkedin_url = 85;
    confidenceByField.hs_linkedin_url = 85;
  }
}
```

### WR-02: Overflow-slot candidate dedup diverges between the JS engines and the Python oracle (untested Phase-46-parity gap)

**File:** `n8n/code/mergeContacts.js:352` / `n8n/code/mergeCompanies.js:380` vs `src/merge_policy.py:188`

**Issue:** The new (Phase 72 Plan 05) overflow-slot routing dedupes candidates with the
same normalized value before assigning a primary/overflow/tail split, so two providers
agreeing never manufactures a phantom overflow. The three engines use different
case-sensitivity for that comparison:

```js
// mergeContacts.js:352 and mergeCompanies.js:380 (byte-identical in both files)
const key = String(c.normalizedValue != null ? c.normalizedValue : c.value);
if (!deduped.some((d) => String(d.normalizedValue != null ? d.normalizedValue : d.value) === key)) {
  deduped.push(c);
}
```

```python
# src/merge_policy.py:188 (route_overflow)
key = str(c.normalized_value).lower()
if not any(str(d.normalized_value).lower() == key for d in deduped):
    deduped.append(c)
```

The JS comparison is case-sensitive; the Python comparison lower-cases both sides
(explicitly mirroring `has_conflict()`'s own case-insensitive comparison, per its own
comment). For two candidates whose normalized values differ only in case (e.g. two
providers returning the same email/URL/text value with different capitalization — for
phone/mobilephone specifically this is unlikely to bite in practice, since phone
normalization already reduces to digits, but the dedup helper itself is generic and
the codebase explicitly treats "the Python oracle" and "the two JS engines" as one
contract that must never silently diverge — this is the repo's own stated Phase 46
rule, restated for this feature by both files' comments ("mergeContacts.js's/
mergeCompanies.js's identical routing")), the JS engines would treat them as two
distinct candidates (creating a real overflow entry) while the Python oracle would
treat them as one agreeing candidate (no overflow). Neither `tests/n8n/overflowSlots.test.mjs`
nor `tests/test_merge_policy.py`'s `test_route_overflow_agreeing_candidates_do_not_manufacture_an_overflow`
exercises a same-value-different-case pair, so this divergence is currently invisible
to the test suite.

**Fix:** Make the JS dedup key case-insensitive to match the Python oracle (and
`has_conflict()`'s own convention in both engines):

```js
const key = String(c.normalizedValue != null ? c.normalizedValue : c.value).toLowerCase();
if (!deduped.some((d) => String(d.normalizedValue != null ? d.normalizedValue : d.value).toLowerCase() === key)) {
  deduped.push(c);
}
```

Add a mixed-case "agreeing candidates" case to `tests/n8n/overflowSlots.test.mjs` and
the Python test alongside the fix so the parity is pinned, not just restored.

---

_Reviewed: 2026-09-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
