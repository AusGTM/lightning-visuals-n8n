---
phase: 66-rich-enrichment-not-minimum-enrichment
reviewed: 2026-09-05T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - scripts/build_cloud_workflows.py
  - n8n/code/enrichmentGate.js
  - n8n/code/lushaRequest.js
  - n8n/code/normalizeProviders.js
  - operator-claude-plugin/scripts/report_enrichment.py
  - tests/n8n/fieldProducerMatrix.test.mjs
  - tests/n8n/linkedinProducer.test.mjs
  - tests/n8n/outcomeContractFlow.test.mjs
  - operator-claude-plugin/tests/test_report_enrichment.py
findings:
  critical: 1
  warning: 3
  info: 0
  total: 4
status: issues_found
---

# Phase 66: Code Review Report

**Reviewed:** 2026-09-05T00:00:00Z
**Depth:** standard
**Files Reviewed:** 9 (plus generated `n8n/wf_*.json` re-derived from the generator per the
review's scope note, and `n8n/code/mergeCompanies.js`/`mergeContacts.js` read for context)
**Status:** issues_found

## Summary

The three plans' own stated deliverables — the widened contacts/companies chase, the Lusha
landline reveal fix, the Apollo LinkedIn producer, the derived field-producer matrix, and the
report-only contactability marker — are all implemented correctly and are backed by strong,
non-hardcoded tests. `node --test tests/n8n/*.test.mjs` (938 pass/0 fail) and
`.venv/bin/python -m pytest -x -q` (4247 passed/154 skipped) both reproduce clean, and
`scripts/build_cloud_workflows.py` regenerates byte-identical to the committed tree. The
D-66-08 zero-diff claims on `config/field_policy.yaml`, `n8n/code/mergeContacts.js`,
`n8n/code/mergeCompanies.js`, `n8n/code/resolveIdentity.js`, and
`operator-claude-plugin/scripts/preingest.py`/`skills/` all hold against the phase's actual
commit range (`git diff 3493a01..HEAD`, filtered to Phase 66's own commits).

One real bug was found in the new Python report code (CR-01: a `TypeError` that breaks an
explicit "never raises" contract). A second, more structural issue was found by taking the
review's own scope note #1 seriously — "confirm that a widened CHASE cannot become a widened
WRITE anywhere": the shared `ENRICH_GATE`/`ENRICH_CO_GATE` gate code was widened once in this
phase but is embedded in *four* different search-node configurations across the generator
(the CLOUD lane's two CSVs, the LOCAL-LIVE lane's two hand-written expressions, and the SJ-1/
SJ-2 scheduled-maintenance CSVs). Only the CLOUD CSV pair was widened and machine-checked by
this phase's own `fieldProducerMatrix.test.mjs`. Verified directly against the generated JSON:
`n8n/wf_enrichment_local_live.json` has **no HubSpot write node at all** (it terminates at
`Decide Action`/`Decide Company Action`, a computed-patch preview only — confirmed by listing
every `httpRequest` node whose URL contains `hubapi.com`, which returns only the two `search`
calls), so this does **not** reach a live CRM overwrite in that lane today. But the merge
decision it computes is provably wrong for 7 of 12 contacts fields and 6 of 13 companies
fields, and `wf_scheduled_maintenance_cloud.json`'s SJ-2 monthly stale-refresh node has the
identical shape with a real consequence (over-triggering, WR-02). Both are downgraded from a
data-loss claim to Warnings below, since I could not verify a live write path for either.

## Critical Issues

### CR-01: `_contactability_for_row` raises `TypeError` on a non-string/unhashable `contactability` value, breaking the module's own "never raises" contract

**File:** `operator-claude-plugin/scripts/report_enrichment.py:230-236`

**Issue:**
```python
_CONTACTABILITY_STATES = {"complete", "email_only", "none"}

def _contactability_for_row(row):
    value = row.get("contactability")
    return value if value in _CONTACTABILITY_STATES else None
```
`value in _CONTACTABILITY_STATES` performs a set-membership test, which requires `value` to be
hashable. If a row's `contactability` key is a `dict` or `list` (a malformed/corrupted backend
response — exactly the class of input every other read in this module, e.g.
`_match_info_for_row`'s `isinstance(match, dict)` guard, is written to tolerate without
raising), this line raises `TypeError: unhashable type`. That exception is not caught anywhere
up the call chain and propagates out of both `build_sync_report` (which reads an HTTP response
body the client does not control) and `build_enrichment_report`, both of which explicitly
document a "never raises" contract (`build_enrichment_report`'s own docstring: *"Never raises:
a missing/malformed execution yields a report whose `state` is `\"unknown\"`... rather than a
guess"*). Reproduced directly:

```
$ cd operator-claude-plugin && ../.venv/bin/python -c "
import report_enrichment as re
row = {'action': 'enrich', 'object_type': 'contacts', 'contactability': {'nested': True}}
re._build_row_report(row, 1)
"
TypeError: cannot use 'dict' as a set element (unhashable type: 'dict')
```
```
$ cd operator-claude-plugin && ../.venv/bin/python -c "
import report_enrichment as re
body = [{'action': 'enrich', 'object_type': 'contacts', 'contactability': ['a', 'b']}]
re.build_sync_report(body)
"
TypeError: cannot use 'list' as a set element (unhashable type: 'list')
```
The existing test suite (`test_build_enrichment_report_never_raises_over_a_malformed_row_missing_contactability`)
only covers a *missing* `contactability` key, not a malformed *value* for it, so this gap
shipped without a red test.

**Fix:** Guard the type before the membership test, matching the module's existing defensive
style:
```python
def _contactability_for_row(row):
    value = row.get("contactability")
    if not isinstance(value, str):
        return None
    return value if value in _CONTACTABILITY_STATES else None
```
Add a test passing a dict/list for `contactability` (alongside the existing
`"some-future-value"` string case) to `build_sync_report` and `build_enrichment_report`, since
both currently only exercise the missing-key shape.

## Warnings

### WR-01: The widened gate is fed by an un-widened search body in the LOCAL-LIVE workflow — the merge decision it computes is wrong for 7/12 contacts fields and 6/13 companies fields (no confirmed write path today)

**File:** `scripts/build_cloud_workflows.py:2062-2069` (`HS_SEARCH_BODY_EXPR`), `2191-2199`
(`HS_CO_SEARCH_BODY_EXPR`), consumed at `3796-3801` and `3896-3905` inside
`build_enrichment_local_live()` — regenerated into `n8n/wf_enrichment_local_live.json`.

**Issue:** `n8n/code/enrichmentGate.js`'s `decideAction` is pure and doesn't know which search
node fed it `existingRecord`. Both `ENRICH_GATE` (contacts) and `ENRICH_CO_GATE` (companies)
are single Python string constants that this phase widened to 12 and 13 fields respectively,
and both are `inline()`'d into *every* workflow variant that builds an "Enrichment Gate"/
"Company Gate" node — including `build_enrichment_local_live()` (a manual-trigger workflow
that makes real Lusha/Apollo/ZoomInfo/Anthropic HTTP calls). That workflow's `HubSpot Search`/
`HubSpot Company Search` nodes use two different, hand-written constants
(`HS_SEARCH_BODY_EXPR`, `HS_CO_SEARCH_BODY_EXPR`) that neither of the two plans that widened
`REQUIRED` updated:

- Contacts `REQUIRED` (12): `city, country, email, hs_country_region_code, hs_state_code,
  jobtitle, lv_linkedin_url, lv_persona_group, mobilephone, phone, seniority, state`.
  `HS_SEARCH_BODY_EXPR` only requests: `email, firstname, lastname, jobtitle, phone,
  mobilephone, lv_jobtitle_verified_at, lv_mobilephone_verified_at, seniority,
  lv_contact_enrichment_provenance, lusha_contact_id`. **Missing: `city`, `country`,
  `hs_country_region_code`, `hs_state_code`, `lv_linkedin_url`, `lv_persona_group`, `state`
  — 7 of 12.**
- Companies `REQUIRED` (13): `industry, numberofemployees, lv_revenue_band, lv_employee_band,
  lv_country_region_normalized, country, city, lv_org_type, lv_produces_content,
  lv_content_type, lv_sponsorship_reliant, lv_is_hardware_vendor, lv_is_gambling_operator`.
  `HS_CO_SEARCH_BODY_EXPR` only requests: `name, domain, industry, annualrevenue,
  numberofemployees, lv_org_type, lv_produces_content, lv_content_type,
  lv_is_hardware_vendor, lv_is_gambling_operator, lv_icp_tier, lv_icp_fit_score,
  lv_anti_icp_flag, lv_enrichment_provenance, lv_org_type_verified_at,
  lv_produces_content_verified_at, lusha_company_id, num_associated_contacts`. **Missing:
  `lv_revenue_band`, `lv_employee_band`, `lv_country_region_normalized`, `country`, `city`,
  `lv_sponsorship_reliant` — 6 of 13.**

Any of these unfetched fields reads as `undefined` on `existingRecord` in this workflow,
regardless of what the real HubSpot record actually holds. `n8n/code/mergeCompanies.js`'s
`fill_blank_only`/`protect_if_current_present` guard (and `mergeContacts.js`'s equivalent) both
read `existingRecord[field]` to decide "current value blank, safe to promote" — so a
genuinely-populated field is misread as blank and the merge computes a `promote` decision for
it. Reproduced directly against the unmodified (byte-identical per `git diff --exit-code`)
`mergeCompanies.js`:

```
$ node -e "
const { mergeCompanies } = require('./n8n/code/mergeCompanies.js');
// existingRecord shaped exactly as HS_CO_SEARCH_BODY_EXPR would return it — country was
// never requested, so it is undefined even though the real HubSpot record may hold it.
const existingRecord = { name: 'Racing NSW', domain: 'racingnsw.com.au', lv_org_type: 'governing_body_league' };
const candidate = { country: 'United States', lv_country_region_normalized: 'Other' };
const { canonicalPatch, decisions } = mergeCompanies(existingRecord, candidate, undefined, { source: 'waterfall', confidence: 90 });
console.log(JSON.stringify(canonicalPatch));
"
{"country":"United States","lv_country_region_normalized":"Other"}
```
`decisions` confirms `country`'s reason as `"Current value blank and candidate passed
threshold."` — a `fill_blank_only`/`protect_if_current_present` field whose true current value
was simply never fetched, not blank.

**Verified NOT a live-write path today:** `wf_enrichment_local_live.json`'s terminal nodes are
`Decide Action`/`Decide Company Action` — the workflow never calls a HubSpot PATCH/POST/PUT.
Confirmed by listing every `httpRequest` node in the generated JSON whose URL contains
`hubapi.com`: only the two `search` calls exist, no create/update node. So this specific
generated workflow is a computed-patch *preview* (it prints/returns what `Decide Action` would
write), not an active overwrite path — I could not find a script or downstream consumer in this
repo that takes this workflow's execution output and issues a real PATCH from it. That is why
this is a Warning rather than a Critical: the finding is that the preview this workflow computes
is wrong (a `fill_blank_only` field it reports as safe-to-promote may already be genuinely
populated in HubSpot), which matters if an operator trusts the preview, and matters immediately
if a write node is ever added to this workflow without someone independently re-noticing this
gap — but it is not, today, an active data-loss path.

This is a regression introduced by this phase, not a pre-existing gap: before Phase 66,
`REQUIRED` was `["email", "jobtitle", "mobilephone"]` (contacts) / `["lv_org_type",
"lv_produces_content"]` (companies) — every member of both lists was already present in
`HS_SEARCH_BODY_EXPR`/`HS_CO_SEARCH_BODY_EXPR`, so no gap existed. Widening the shared gate
constant without correspondingly widening these two search bodies opened the gap. It is
invisible to the phase's own audit machinery — see WR-03. `66-COVERAGE.md` acknowledges
`HS_SEARCH_BODY_EXPR` as a "known-narrower sibling, deliberately not widened" (Plan 01's own
scope decision) but frames it purely as a scope choice, never as a wrong-preview exposure; the
companies sibling `HS_CO_SEARCH_BODY_EXPR` isn't mentioned in `66-COVERAGE.md` at all.

**Fix:** Widen `HS_SEARCH_BODY_EXPR` and `HS_CO_SEARCH_BODY_EXPR` to include every member of
the (now 12/13-field) `REQUIRED` lists, mirroring what Plan 01 Task 2 / Plan 02 Task 2 already
did for the CLOUD CSVs — see WR-03 for the matching test-coverage fix.

```js
// scripts/build_cloud_workflows.py — widen both constants to match REQUIRED
HS_SEARCH_BODY_EXPR = (
  '={{ JSON.stringify({ filterGroups: [...], properties: '
  '["email","firstname","lastname","jobtitle","phone","mobilephone",'
  '"lv_jobtitle_verified_at","lv_mobilephone_verified_at","seniority",'
  '"lv_contact_enrichment_provenance","lusha_contact_id",'
  '"city","state","country","hs_state_code","hs_country_region_code",'
  '"lv_linkedin_url","lv_persona_group"], limit: 5 }) }}'
)
HS_CO_SEARCH_BODY_EXPR = (
  '={{ JSON.stringify({ filterGroups: [...], properties: '
  '["name","domain","industry","annualrevenue","numberofemployees",'
  '"lv_org_type","lv_produces_content","lv_content_type","lv_is_hardware_vendor",'
  '"lv_is_gambling_operator","lv_icp_tier","lv_icp_fit_score","lv_anti_icp_flag",'
  '"lv_enrichment_provenance","lv_org_type_verified_at","lv_produces_content_verified_at",'
  '"lusha_company_id","num_associated_contacts",'
  '"lv_revenue_band","lv_employee_band","lv_country_region_normalized","country","city",'
  '"lv_sponsorship_reliant"], limit: 5 }) }}'
)
```

### WR-02: SJ-2's monthly stale-refresh "Company Gate" no longer confirms staleness — it now virtually always re-queues

**File:** `scripts/build_cloud_workflows.py:7568-7576` (`sj2_search` `properties_csv`),
`7578` (`ENRICH_CO_GATE` reused as `"SJ-2 Company Gate"`) — regenerated into
`n8n/wf_scheduled_maintenance_cloud.json`.

**Issue:** `SJ-2 Search (stale refresh)` requests only
`hs_object_id,domain,lv_org_type,lv_produces_content,lv_org_type_verified_at,
lv_produces_content_verified_at` — 2 of the now-13 companies `REQUIRED` fields — and feeds
that into the same widened `ENRICH_CO_GATE`. Since `decideAction`'s "missing dominates" rule
means any unfetched required field is always reported as missing, the other 11 required fields
will read as missing for essentially every row this search returns, so `action` will resolve to
`enrich` rather than `skip` regardless of whether those fields are actually populated and
fresh. The node's own comment claims this stage "feeds the reused, UNMODIFIED Company Gate so
decideAction actually confirms staleness (RT-5) before the terminal dispatch — a skip (still
fresh, or re-verified since the scan started) never re-queues" — that confirmation no longer
holds once the shared gate widened underneath it; `SJ-2 IF Skip`'s true branch is now close to
unreachable for any record the search matches. Unlike WR-01, this node's own dispatch
(`SJ-2 Set Requested`) does write a real HubSpot property (`lv_enrichment_requested=true`) once
armed, so the consequence here is real: systematic over-triggering of the requested-enrichment
poller for records that were already fresh, a cost/DoS-shaped regression not present before
this phase (the old 2-field `REQUIRED` matched exactly what SJ-2 fetched).

**Fix:** Either widen `sj2_search`'s `properties_csv` to the full 13-field companies list (same
approach as WR-01), or — since SJ-2's own purpose is narrowly "org_type/produces_content
staleness", not full-record completeness — give SJ-2 its own narrower required-field list
instead of reusing the full `ENRICH_CO_GATE` REQUIRED constant. Add a regression test (mirrors
`tests/n8n/materialConflictNoVetoFlip.test.mjs`'s existing skip-fixture pattern) asserting that
a record fresh on `lv_org_type`/`lv_produces_content` alone still reaches `skip` via
`SJ-2 Company Gate` specifically.

### WR-03: The phase's own fetch-gate audit only covers the CLOUD workflow, giving false confidence that "every REQUIRED member is fetched"

**File:** `tests/n8n/fieldProducerMatrix.test.mjs:166-199, 292-299`

**Issue:** `loadWorkflowNodes()` is hardcoded to `n8n/wf_enrichment_cloud.json`, and
`SEARCH_NODE_NAME`/`GATE_NODE_NAME` never vary by workflow file. The fetch-gate assertion
("every REQUIRED member is requested by the lane's search node") therefore only proves the
guarantee for one of at least four search-node configurations that embed the same shared gate
code (see WR-01/WR-02). `66-COVERAGE.md` and the plan SUMMARYs report the fetch-gate assertion
as closing "the non-clobber hole" generally, when it only closes it for the CLOUD lane. This is
a coverage gap in the test infrastructure this phase itself built to prevent exactly this class
of defect.

**Fix:** Parameterize `laneRequired`/`laneSearchPropertiesText` (or add a second parallel
assertion) over `["wf_enrichment_cloud.json", "wf_enrichment_local_live.json"]`, and separately
decide/document whether the SJ-1/SJ-2 scheduled search CSVs are in scope for the same check or
are intentionally narrower with their own required-field subset (see WR-02's suggested fix).

---

_Reviewed: 2026-09-05T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
