---
phase: 12-taxonomy-single-source
verified: 2026-07-20T00:00:00Z
status: passed
score: 7/7 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 12: Taxonomy Single-Source Verification Report

**Phase Goal:** Adding an `lv_org_type` or `lv_content_type` value is a one-file edit to `config/taxonomy.yaml` that cannot silently drift.
**Verified:** 2026-07-20
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `config/taxonomy.yaml` is the only hand-edited vocabulary; all derived artifacts trace to it | ✓ VERIFIED | `src/taxonomy.py` reads `config/taxonomy.yaml` at import; `scripts/gen_taxonomy_js.py` imports from `src.taxonomy` and renders `n8n/code/taxonomy.generated.js`; `mergeCompanies.js` `require`s `EVIDENCE_GATED_ORG_TYPES` from the generated module (line 18); `scripts/build_cloud_workflows.py:29-31` regenerates the taxonomy module before any `inline()` call runs |
| 2 | Forgetting to rebuild after a taxonomy edit fails a test (never silent 0-score) | ✓ VERIFIED | Live-ran the drift: appended a bogus `esports_organiser` entry to `config/taxonomy.yaml`, ran `pytest -k currency` → genuine `AssertionError` naming the diff (not a collection no-op), reverted cleanly (`git diff --exit-code config/taxonomy.yaml` = 0) |
| 3 | `normalize_org_type`/`normalize_content_types` satisfy NM-1..NM-5 (never off-vocabulary; tri-state preserved) | ✓ VERIFIED | `tests/test_web_research_spec.py` NM-1/3/4/5 tests pass unmarked (no `@unbuilt`); full suite run confirms `132 passed, 7 xfailed, 0 failed, 0 xpassed` |
| 4 | Builder generates JS literal into workflow JSON; TX-4 green, zero hand-maintained org_type lists in `mergeCompanies.js` | ✓ VERIFIED | `grep -c 'governing_body_league' n8n/code/mergeCompanies.js` = 0; `test_tx4_mergecompanies_has_no_handmaintained_enum` passes; `EVIDENCE_GATED_ORG_TYPES` from the generated module = `["content_producer","gambling_operator","governing_body_league","hardware_vendor"]`, matching plan's expected sorted set |
| 5 | NM-6 parity: Python and JS normalizers agree on every case in the shared fixture | ✓ VERIFIED | `node --test tests/n8n/*.test.mjs` → `taxonomy: NM-6 GENUINE parity vs Python src.taxonomy across the shared fixture` passes; live-broke the JS regex (`[^a-z0-9]+` → `\W+`), reran → genuine failure (`node --test` exit 1, 1 of 12 parity.test.mjs tests failed), restored, byte-identical to committed version |
| 6 | Drift guard test actually compares regenerated output to committed file, not a trivial existence check | ✓ VERIFIED | Read `test_taxonomy_generated_js_currency` source: it calls `gen_taxonomy_js.render()` and asserts string equality against the checked-in file's full text — confirmed by the live drift-fire test above (assertion failed with a real diff, not "file missing") |
| 7 | Full suites green; rebuild is a byte-for-byte no-op; no regressions in mergeCompanies/evidence-gate/conflict-withholding semantics | ✓ VERIFIED | See Behavioral Spot-Checks and Probe Execution tables below |

**Score:** 7/7 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `config/taxonomy.yaml` | normative vocabulary, single hand-edit point | ✓ VERIFIED | Contains `org_types`/`content_types` with `score`, `requires_evidence`, `synonyms`, exactly one `is_default` per vocab |
| `src/taxonomy.py` | loader + NM-1..NM-5 normalizers | ✓ VERIFIED | `normalize_key`, `normalize_org_type`, `normalize_org_type_result`, `normalize_content_types`, exported constants; self-check `__main__` block present |
| `scripts/gen_taxonomy_js.py` | generator emitting JS data module | ✓ VERIFIED | `render()` uses `json.dumps` throughout (no hand-escaping); imports `normalize_key` from `src.taxonomy` (no re-implementation) |
| `n8n/code/taxonomy.generated.js` | generated vocabulary data, DO-NOT-EDIT | ✓ VERIFIED | Header states GENERATED FROM/DO NOT EDIT; `node --check` passes; regenerating twice is a no-op (confirmed via full rebuild + `git diff --exit-code n8n/`) |
| `n8n/code/taxonomy.js` | hand-written JS normalizer logic | ✓ VERIFIED | `require("./taxonomy.generated")`; `normalizeKey` uses `[^a-z0-9]+` (not `\W+`) matching Python; `node --check` passes; parity-proven (see truth 5) |
| `tests/fixtures/taxonomy_parity_cases.json` | shared Python/JS case table | ✓ VERIFIED | Valid JSON with `org_type_cases` and `content_type_list_cases` keys; consumed by both `tests/test_web_research_spec.py`-adjacent Python and `tests/n8n/parity.test.mjs` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `config/taxonomy.yaml` | `gen_taxonomy_js.py` | `src.taxonomy` import (`ORG_TYPES`, `CONTENT_TYPES`, etc.) | ✓ WIRED | Confirmed by reading `scripts/gen_taxonomy_js.py:25-33` import block |
| `gen_taxonomy_js.py` | `n8n/code/taxonomy.generated.js` | `render()` written by `__main__` and by `build_cloud_workflows.py` | ✓ WIRED | `scripts/build_cloud_workflows.py:29-31` calls `gen_taxonomy_js.render()` and writes the file before any `inline()` |
| `n8n/code/taxonomy.generated.js` | `mergeCompanies.js` | `require("./taxonomy.generated")` → `EVIDENCE_GATED_ORG_TYPES` | ✓ WIRED | `mergeCompanies.js:18,33` |
| `mergeCompanies.js` | Merge Company node `jsCode` | `inline("taxonomy.generated.js", "mergeCompanies.js")` | ✓ WIRED | `scripts/build_cloud_workflows.py:1293`; confirmed via node-level diff (only `Merge Company` changed across all 5 workflows since before Phase 12) |
| `config/taxonomy.yaml` | `src/taxonomy.py` | `load_yaml("config/taxonomy.yaml")` at module import | ✓ WIRED | `src/taxonomy.py:20` |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full Python suite green at expected counts | `.venv/bin/python -m pytest -q` | `132 passed, 7 xfailed, 1 warning` (0 failed, 0 xpassed) | ✓ PASS |
| Full JS suite green at expected count | `node --test tests/n8n/*.test.mjs` | `tests 46 / pass 46 / fail 0` | ✓ PASS |
| Rebuild is a no-op | `.venv/bin/python scripts/build_cloud_workflows.py && git diff --exit-code n8n/` | exit 0, empty diff | ✓ PASS |
| All Code-node JS files parse | `for f in n8n/code/*.js; do node --check "$f"; done` | no errors | ✓ PASS |
| No hand-typed org_type literal remains | `grep -c 'governing_body_league' n8n/code/mergeCompanies.js` | `0` | ✓ PASS |
| Currency guard fires on real drift | appended bogus org_type to `taxonomy.yaml`, ran `pytest -k currency` | `1 failed` (genuine `AssertionError` with diff), then reverted clean | ✓ PASS |
| NM-6 parity guard fires on real divergence | broke JS regex to `\W+`, ran `node --test tests/n8n/parity.test.mjs` | `pass 11 / fail 1`, exit code 1; restored, `diff` against backup empty | ✓ PASS |
| Node-level diff shows only `Merge Company` changed | Python script diffing `jsCode` per node, HEAD~5 vs working tree, across 5 workflow JSONs | `n8n/wf_enrichment_local_live.json :: Merge Company` only | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| REQ-taxonomy-single-source | 12-01-PLAN.md | `config/taxonomy.yaml` single hand-edit vocabulary, TX-1..TX-9 | ✓ SATISFIED | REQUIREMENTS.md marked complete; TX-1/2/3/4/5 conformance tests pass; currency guard verified live |
| REQ-enum-normalization | 12-01-PLAN.md | Normalizers never emit off-vocabulary, NM-1..NM-6 | ✓ SATISFIED | NM-1..5 unmarked tests pass; NM-6 parity test passes and was proven to fire on divergence |

### Anti-Patterns Found

None. Scanned all created/modified files (`src/taxonomy.py`, `scripts/gen_taxonomy_js.py`, `n8n/code/taxonomy.js`, `n8n/code/taxonomy.generated.js`, `n8n/code/mergeCompanies.js`, `scripts/build_cloud_workflows.py`, `tests/test_taxonomy_conformance.py`, fixture JSON, `tests/n8n/parity.test.mjs`) for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER|placeholder|coming soon|not yet implemented` — zero hits.

### Human Verification Required

None. All must-haves are code/test-verifiable and were directly executed against the codebase.

### Gaps Summary

None. All 7 derived truths, all 5 required artifacts, all 5 key links, both requirements, and the full test suites (Python: 132 passed/7 xfailed/0 failed/0 xpassed; JS: 46/46 pass) verified directly — not from SUMMARY.md claims. Both "guard fires" claims (currency drift, NM-6 parity divergence) were independently reproduced by this verifier, not merely re-read from the SUMMARY narrative. Rebuild is byte-for-byte no-op. Node-level diff proof confirms only the `Merge Company` node changed across all 5 workflow JSONs — the contacts branch and every other node are untouched, matching the Task 3 non-regression constraint.

The ROADMAP's own deferral note (research prompt deriving from taxonomy is Phase 13 scope, not this phase) is accepted as-is — it is documented in both PLAN.md and ROADMAP.md success criterion 1, and matches the "Out of scope" section explicitly excluding `validate_research_output`/`to_provider_result`/HubSpot property sync.

---

_Verified: 2026-07-20_
_Verifier: Claude (gsd-verifier)_
