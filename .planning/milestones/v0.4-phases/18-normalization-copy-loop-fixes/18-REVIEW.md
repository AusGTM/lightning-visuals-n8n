---
phase: 18-normalization-copy-loop-fixes
reviewed: 2026-07-29T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - n8n/code/normalizeProviders.js
  - scripts/build_cloud_workflows.py
  - tests/n8n/industryNormalization.test.mjs
  - tests/n8n/personaGroupCopyLoop.test.mjs
  - tests/n8n/sponsorshipReliantCopyLoop.test.mjs
  - tests/n8n/enrichment.test.mjs
  - tests/fixtures/companies_jscode_frozen.json
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_enrichment_local.json
  - n8n/wf_enrichment_local_live.json
findings:
  critical: 1
  warning: 1
  info: 0
  total: 2
status: issues_found
---

# Phase 18: Code Review Report

**Reviewed:** 2026-07-29T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the three Phase 18 source edits (NORM-01 `_industryText` helper, COPY-01
`lv_sponsorship_reliant` researchData wiring, COPY-02 `lv_persona_group` dot-access
copy), their four test files, the re-baselined frozen fixture, and the three
regenerated workflow JSONs.

NORM-01 is sound: `_industryText()` correctly prefers a NAICS entry's own `.name`
text over the bare numeric code, falls back to the provider's free-text industry
field, and returns `null` (fabricating nothing) when neither is available. Verified
against the real recorded ZoomInfo GTM fixture (naicsCodes as `{id,name}` objects)
and confirmed the full test suite (44/44 `node --test` across `tests/n8n/*.test.mjs`,
596/596 `pytest`) passes, and that `python3 scripts/build_cloud_workflows.py`
regenerates all three `n8n/wf_*.json` files byte-identical to what's committed (git
diff clean after rebuild) — the generated JSON is a faithful, consistent
regeneration of the reviewed source.

COPY-02 (`lv_persona_group`) is a correctly-wired but currently-unreachable code
path: no provider mapper or classifier in this codebase ever sets
`scored.winners.persona_group`, so the new copy block is forward-wiring, not a live
fix — this exactly mirrors the pre-existing `linkedin_url`/`lv_linkedin_url` pattern
already in the same function (same comment style, explicitly modeled on it), so it
is not flagged as a defect.

COPY-01 (`lv_sponsorship_reliant`) is where the material problem is: unlike
persona_group, `config/field_policy.yaml` already declares
`lv_sponsorship_reliant.allow_web_research: true`, and the phase's own commit
message/comments frame this as "closing a latent copy-loop gap the field's policy
had covered since Phase 15." But the Claude Web Research request contract built in
`build_cloud_workflows.py` (system prompt text, `required_fields` array, and the
forced JSON-response schema string) was never updated to ask for or accept
`lv_sponsorship_reliant` — only `lv_org_type`, `lv_produces_content`,
`lv_content_type`, `lv_is_hardware_vendor`, `lv_is_gambling_operator`. Confirmed
live in both built workflows (`grep` for `lv_sponsorship_reliant` inside the "Build
Research Request" node's `jsCode` in `wf_enrichment_cloud.json` and
`wf_enrichment_local_live.json` returns nothing). See CR-01.

A secondary, lower-severity gap: the company fetch/search property list that builds
`existingRecord` for the merge never requests `lv_sponsorship_reliant`, so the
merge decision's `current_value` audit field is always `null` for this field even
when HubSpot already holds a value. See WR-01.

## Critical Issues

### CR-01: `lv_sponsorship_reliant` copy-loop fix cannot receive a live value — the Claude web-research prompt/schema was never updated to request it

**File:** `scripts/build_cloud_workflows.py:1823-1860` (research system prompt + `required_fields` + forced JSON schema, shared by `build_enrichment_cloud()` and `build_enrichment_local_live()` via `_enrich_build_research_request_js`)

**Issue:** COPY-01 (`scripts/build_cloud_workflows.py:2322-2331`, the `researchData` loop in `ENRICH_MERGE_CO`) now correctly copies `rc.data.lv_sponsorship_reliant` into the company research fold, and `tests/n8n/sponsorshipReliantCopyLoop.test.mjs` proves that copy step works — but only by hand-constructing a `research_candidate.data` object that already contains `lv_sponsorship_reliant`. In production, that object is built exclusively from the Claude Web Research HTTP call's JSON response, and that response is governed entirely by:

- the system prompt's `required_fields` array (`["lv_org_type", "lv_produces_content", "lv_content_type", "lv_is_hardware_vendor", "lv_is_gambling_operator"]`), and
- the forced-shape JSON schema string in the same prompt (`'{"data":{"lv_org_type":<str>,"lv_produces_content":<bool|null>,"lv_content_type":[<str>],"lv_is_hardware_vendor":<bool|null>,"lv_is_gambling_operator":<bool|null>},...}'`)

Neither mentions `lv_sponsorship_reliant`. Verified this is what actually ships by extracting the "Build Research Request" node's `jsCode` from both `n8n/wf_enrichment_cloud.json` and `n8n/wf_enrichment_local_live.json`:

```
$ python3 -c "... 'lv_sponsorship_reliant' in code ..."
sponsorship in schema string: False   # wf_enrichment_cloud.json
sponsorship in schema string: False   # wf_enrichment_local_live.json
```

Since the model is told exactly what JSON shape to return and is not asked for this field, `rc.data.lv_sponsorship_reliant` will be absent on every real invocation, `researchData.lv_sponsorship_reliant` will therefore never be set (the `v === undefined` guard at line ~2329 skips it), and the field can never actually promote to canonical via this path. The phase's stated goal — "closing a latent copy-loop gap the field's policy had covered since Phase 15 but this fold never actually reached" — is not achieved end-to-end; the gap moves one layer upstream and remains open in production, even though the unit test for the copy step itself is green.

**Fix:** Add `"lv_sponsorship_reliant"` to the `required_fields` array and to the forced JSON schema string in the research system prompt (and to the corresponding `evidence_by_field` guidance, matching the pattern used for the other boolean ICP flags), e.g.:

```js
required_fields: ["lv_org_type", "lv_produces_content", "lv_content_type",
                  "lv_is_hardware_vendor", "lv_is_gambling_operator",
                  "lv_sponsorship_reliant"],
```

and extend the schema string with `"lv_sponsorship_reliant":<bool|null>`. Then rebuild (`python3 scripts/build_cloud_workflows.py`) and add/extend a test asserting the built "Build Research Request" node's prompt actually requests this field — the same kind of compiled-node-body differential `sponsorshipReliantCopyLoop.test.mjs` already uses for the copy step, applied one node earlier.

## Warnings

### WR-01: `lv_sponsorship_reliant` is never fetched into `existingRecord` for companies, so the merge decision's `current_value` is always misreported as `null`

**File:** `scripts/build_cloud_workflows.py:3404-3411` (`ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`, used verbatim by both "HubSpot Company Search" and "HubSpot Company Fetch By Id")

**Issue:** `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` lists `lv_org_type`, `lv_produces_content`, `lv_content_type`, `lv_is_hardware_vendor`, `lv_is_gambling_operator` — every other field the research fold writes — but omits `lv_sponsorship_reliant`. Because this field's policy class is `system_owned` (`n8n/code/mergeCompanies.js:43`), `_gate()` always promotes on confidence pass regardless of `currentValue`, so this does not cause incorrect promote/clobber behavior today. However:

- The decision record pushed at `mergeCompanies.js:217-228` always reports `current_value: null` for `lv_sponsorship_reliant`, even on a company where HubSpot already holds a value — this corrupts the audit trail (`lv_enrichment_provenance` / `enrichment_last_decision`) that RevOps reviewers rely on (CLAUDE.md §22, §23).
- It is silently inconsistent with every sibling research field on the same list, which makes the omission easy to miss on future edits (e.g. if the field's policy class is ever changed to `stale_refreshable` or `fill_blank_only`, the missing fetch would then start causing genuine incorrect-promote behavior, since those classes branch on `currentValue`).

**Fix:** Add `lv_sponsorship_reliant` to `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`:

```python
ENRICH_COMPANY_SEARCH_PROPERTIES_CSV = (
    "name,domain,industry,annualrevenue,"
    "numberofemployees,hs_object_id,lv_org_type,"
    "lv_produces_content,lv_content_type,lv_sponsorship_reliant,"
    "lv_is_hardware_vendor,lv_is_gambling_operator,"
    "lv_enrichment_provenance,lv_org_type_verified_at,"
    "lv_produces_content_verified_at"
)
```

then rebuild and re-run `tests/test_companies_factory_frozen.py` (re-baselining the frozen fixture, since this constant feeds byte-identical companies node bodies).

---

_Reviewed: 2026-07-29T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
