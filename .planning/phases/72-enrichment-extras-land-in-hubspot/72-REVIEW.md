---
phase: 72-enrichment-extras-land-in-hubspot
reviewed: 2026-09-12T22:34:29Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - scripts/build_cloud_workflows.py
  - n8n/code/mergeContacts.js
  - n8n/code/mergeCompanies.js
  - tests/n8n/ingestWidenedFieldsFlow.test.mjs
  - tests/n8n/fieldProducerMatrix.test.mjs
  - tests/n8n/overflowSlots.test.mjs
  - tests/test_merge_policy.py
  - tests/fixtures/companies_jscode_frozen.json
  - CLAUDE.md
  - docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md
findings:
  critical: 0
  warning: 0
  info: 0
  total: 0
status: clean
---

# Phase 72: Code Review Report (gap-closure batch — incremental review since `b06dfbb9`)

**Reviewed:** 2026-09-12T22:34:29Z
**Depth:** standard
**Files Reviewed:** 10 (9 diffed source/test files + 2 docs, `companies_jscode_frozen.json` counted once)
**Status:** clean

## Summary

This is an incremental review of the gap-closure batch (plans 72-09/10/11/12) that closed the
prior review's three findings (CR-01, WR-01, WR-02). I traced each fix independently rather than
trusting the plan/summary prose — reading the actual diffs, re-deriving the field sets the fixes
claim to cover from `config/field_policy.yaml` and `config/column_mapping.yaml`, regenerating
`n8n/wf_*.json` from the committed generator to confirm no hand-edits, and running both the full
`node --test tests/n8n/*.test.mjs` suite (1170/1170 pass) and the relevant Python suites
(`test_merge_policy.py` 38/38, `test_preingest_merge.py` 87/87). All three fixes hold up; no new
defects found in the diff.

## Prior findings — disposition

### CR-01 (local-live fetch lists missing overflow/protect fields) — FIXED, commit `455b0173`

`HS_SEARCH_BODY_EXPR` and `HS_CO_SEARCH_BODY_EXPR` (used only inside
`build_enrichment_local_live()` — confirmed by line-range check, not just by comment claim) are
widened to `lv_phone_2`/`lv_mobilephone_2` (contacts) and `lv_phone_2`/`state`/`hs_state_code`/
`phone` (companies), matching the cloud lane's already-widened
`ENRICH_CONTACT_SEARCH_PROPERTIES_CSV`/`ENRICH_COMPANY_SEARCH_PROPERTIES_CSV`. Verified this is
scoped to the local-live lane only (both constants have exactly one definition site each, and
that site sits inside the local-live builder function's line range) — no accidental change to a
cloud lane. The new regression test `fieldProducerMatrix.test.mjs`'s "non-clobber fetch gate
(CR-01)" assertion structurally checks, across every generated workflow file, that every
`protect_if_current_present` policy field is present in its lane's live HubSpot search node — and
passes against the regenerated JSON (`node --test tests/n8n/fieldProducerMatrix.test.mjs`: 9/9).
This closes the bug by a standing guard, not just a one-off patch.

### WR-01 / F72-1 (LinkedIn PN-1 rename vocabulary mismatch, silently withheld dual-write) — FIXED, commit `0f7c8c08`

`CANDIDATE_ALIASES = { linkedin_url: ["lv_linkedin_url", "hs_linkedin_url"] }` is declared once
inside `MERGE_CONTACTS` and read by both the `confidenceByField`/`sourceByField` derivation loop
and the candidate-builder block, closing the vocabulary mismatch between
`preingest.py`'s `PROVIDER_KEY_ALIASES` (which renames a provider's `lv_linkedin_url` response key
onto the CSV's bare `linkedin_url` before it lands in `source_by_field`) and the write-side keys
the merge candidate actually uses. I independently re-derived `promotable_contact_props() -
canonical_props()` in a live Python shell against the current config files and got exactly
`{hs_linkedin_url, lv_linkedin_url}` — matching the doc comment's claim that this is the *only*
pair of candidate keys with this rename problem, i.e. `CANDIDATE_ALIASES` is not missing any other
entry the review was asked to hunt for. The alias-write guard (`sourceByField[target] == null`)
correctly never clobbers a caller-supplied entry already present under the target key. This fix
also has a live observation: contact `352522004980` / execution `12414` landed both keys with
provenance `waterfall`/confidence 85 (`72-UAT.md` Test 3), matching CLAUDE.md's and
`OPERATOR-AUTONOMOUS-BATCH-UAT.md`'s claims — no overclaim found in either doc against the UAT
evidence.

### WR-02 (overflow-slot dedup case sensitivity) — FIXED, commit `e2ea2653`

Both `mergeContacts.js` and `mergeCompanies.js` now `.toLowerCase()` both sides of the
overflow-dedup comparison. I diffed the two loops byte-for-byte post-fix: identical apart from the
field-specific `_overflowSlot("companies"/"contacts", field)` call already documented as the only
intentional divergence — Phase 46 parity holds. `src/merge_policy.py`'s `route_overflow` was
checked and confirmed already case-insensitive before this change (`key =
str(c.normalized_value).lower()`), so the new pinning test in `test_merge_policy.py` is
legitimately a parity-lock, not silently masking a still-open Python-side gap. The frozen fixture
re-baseline (`companies_jscode_frozen.json`) was diffed at the JSON-value level (not just line
count): only the `Merge Company` entry changed in both the `cloud` and `local_live` top-level
sections, and within that entry only the two dedup lines plus their adjoining comment changed —
no unrelated re-baseline slipped in.

## New findings (this diff)

None. Specifically checked and found clean:

- **Other candidate keys renamed away from their `source_by_field` name that `CANDIDATE_ALIASES`
  does not cover** — none exist. `promotable_contact_props() - canonical_props()` is exactly the
  two keys the map already handles.
- **`_isProviderSource`/`sourceByField` aliasing consistency** — `_isProviderSource` tests the
  *value* of `resolvedSource` (a provider name), which is orthogonal to `CANDIDATE_ALIASES`
  (which maps *field names*); the alias loop sets `confidenceByField` and `sourceByField` for a
  target key in the same iteration, so a target field's `_isProviderSource` check sees the same
  provider name its source field would have. No divergence.
- **Parity drift between the two JS dedup loops** — none; verified byte-identical apart from the
  documented, pre-existing `_overflowSlot(objectType, ...)` argument difference.
- **Frozen fixture re-baseline scope** — confirmed narrow (see WR-02 disposition above).
- **`HS_SEARCH_BODY_EXPR`/`HS_CO_SEARCH_BODY_EXPR` widening leaking into a cloud lane** — confirmed
  it does not; both constants are defined and used exclusively inside
  `build_enrichment_local_live()`.

## Verification performed

- `node --test tests/n8n/*.test.mjs` — 1170 pass, 0 fail.
- `.venv/bin/python -m pytest tests/test_merge_policy.py` — 38 pass.
- `.venv/bin/python -m pytest operator-claude-plugin/tests/test_preingest_merge.py` — 87 pass.
- `.venv/bin/python scripts/build_cloud_workflows.py` (regenerate) followed by `git status`/`git
  diff --stat` — zero diff against the committed `n8n/wf_*.json`, confirming the generated
  workflows are faithfully reproduced from the reviewed generator source, not hand-edited.
- Independent Python re-derivation of `promotable_contact_props()`/`canonical_props()` set
  difference (see WR-01 disposition).

---

_Reviewed: 2026-09-12T22:34:29Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
