---
phase: 12-taxonomy-single-source
plan: 01
subsystem: enrichment
tags: [taxonomy, codegen, n8n, jsdata, normalization, parity, icp-scoring]

requires:
  - phase: 11-company-enrichment-branch
    provides: mergeCompanies.js companies branch + DEFAULT_COMPANY_POLICY, ENRICH_MERGE_CO builder wiring
provides:
  - "src/taxonomy.py — single Python-side org_type/content_type normalizer, reads config/taxonomy.yaml at import"
  - "scripts/gen_taxonomy_js.py — generator emitting n8n/code/taxonomy.generated.js from config/taxonomy.yaml"
  - "n8n/code/taxonomy.generated.js — generated vocabulary data module (DO-NOT-EDIT), consumed by mergeCompanies.js"
  - "n8n/code/taxonomy.js — hand-written JS normalizer logic (Task 4), parity-proven against src/taxonomy.py"
  - "tests/test_taxonomy_conformance.py::test_taxonomy_generated_js_currency — drift guard on the generated artifact"
  - "tests/n8n/parity.test.mjs NM-6 test + tests/fixtures/taxonomy_parity_cases.json — shared Python/JS case table"
  - "mergeCompanies.js require_evidence_url_for derived from config/taxonomy.yaml, TX-4 retired"
affects: [13-web-research-retrieval, 15-hubspot-property-sync]

tech-stack:
  added: []
  patterns:
    - "Codegen-only-where-runtime-can't-read (AR-4): n8n Code nodes get a generated JS
      data literal; Python reads the YAML directly at runtime. Same taxonomy, two
      consumption paths, one source file."
    - "Data generated / logic hand-written (D2): taxonomy.generated.js carries only
      vocabulary; taxonomy.js carries the normalizer functions and requires the data."
    - "Currency guard as the safety net for artifacts that can't self-verify: a test
      asserts the checked-in generated file equals render() right now."

key-files:
  created:
    - src/taxonomy.py
    - scripts/gen_taxonomy_js.py
    - n8n/code/taxonomy.generated.js
    - n8n/code/taxonomy.js
    - tests/fixtures/taxonomy_parity_cases.json
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/code/mergeCompanies.js
    - n8n/wf_enrichment_local_live.json
    - tests/test_taxonomy_conformance.py
    - tests/test_web_research_spec.py
    - tests/n8n/parity.test.mjs

key-decisions:
  - "D1/D2/D3/D4 taken as written in PLAN.md (generate JS data only, not builder
    machinery; icp_scoring.yaml/field_policy.yaml stay hand-written + drift-guarded)."
  - "Renamed the currency-guard test from the plan's literal name
    (test_taxonomy_generated_js_is_current) to test_taxonomy_generated_js_currency so
    the plan's own `pytest -k currency` verification step actually selects it — the
    original name and the -k filter did not share a substring, which would have made
    the guard-fires proof a false positive (0 tests collected, non-zero exit read as
    'failed as expected')."
  - "Adapted the Task 4 deliberate-break verification to run against
    tests/n8n/parity.test.mjs (the file Task 4's own Action section and PLAN
    frontmatter's files_modified target), not the plan verify block's
    tests/n8n/taxonomyParity.test.mjs, which does not exist anywhere in the plan or
    codebase."

requirements-completed: [REQ-taxonomy-single-source, REQ-enum-normalization]

coverage:
  - id: D1
    description: "src/taxonomy.py loader + NM-1..NM-5 normalizers, no off-vocabulary output"
    requirement: "REQ-enum-normalization"
    verification:
      - kind: unit
        ref: "tests/test_web_research_spec.py#test_nm1_nm3_org_type_normalization"
        status: pass
      - kind: unit
        ref: "tests/test_web_research_spec.py#test_nm1_never_returns_off_vocabulary"
        status: pass
      - kind: unit
        ref: "tests/test_web_research_spec.py#test_nm4_default_sets_needs_review"
        status: pass
      - kind: unit
        ref: "tests/test_web_research_spec.py#test_nm5_content_types_drop_unknown_and_dedupe"
        status: pass
    human_judgment: false
  - id: D2
    description: "Generator emits n8n/code/taxonomy.generated.js from config/taxonomy.yaml; currency guard fails on drift"
    requirement: "REQ-taxonomy-single-source"
    verification:
      - kind: unit
        ref: "tests/test_taxonomy_conformance.py#test_taxonomy_generated_js_currency"
        status: pass
      - kind: other
        ref: "manual taxonomy.yaml edit + rerun -k currency proved the guard fails on drift, then reverted"
        status: pass
    human_judgment: false
  - id: D3
    description: "mergeCompanies.js consumes the generated evidence-gated list; TX-4 (no hand-maintained enum) goes green"
    requirement: "REQ-taxonomy-single-source"
    verification:
      - kind: unit
        ref: "tests/test_taxonomy_conformance.py#test_tx4_mergecompanies_has_no_handmaintained_enum"
        status: pass
      - kind: unit
        ref: "tests/n8n/parity.test.mjs#mergeCompanies: unevidenced ICP claims -> needs_review, never canonical"
        status: pass
      - kind: other
        ref: "per-node jsCode diff across all 5 workflow JSONs vs HEAD: only Merge Company changed"
        status: pass
    human_judgment: false
  - id: D4
    description: "n8n/code/taxonomy.js JS normalizer; NM-6 Python/JS parity across the shared fixture table"
    requirement: "REQ-enum-normalization"
    verification:
      - kind: unit
        ref: "tests/n8n/parity.test.mjs#taxonomy: NM-6 GENUINE parity vs Python src.taxonomy across the shared fixture"
        status: pass
      - kind: other
        ref: "deliberately broke the JS regex ([^a-z0-9]+ -> \\W+), guard failed naming the Racing_Club case, restored"
        status: pass
    human_judgment: false

duration: ~30min
completed: 2026-07-20
status: complete
---

# Phase 12 Plan 01: Taxonomy Single-Source Summary

**`config/taxonomy.yaml` is now the only hand-edited org_type/content_type vocabulary; a generator inlines it into the n8n Merge Company Code node, a currency test catches a forgotten rebuild, and NM-6 parity is proven Python-vs-JS on a shared fixture table.**

## Performance

- **Duration:** ~30 min
- **Completed:** 2026-07-20
- **Tasks:** 4
- **Files modified:** 12 (5 created, 7 modified)

## Accomplishments

- `src/taxonomy.py`: `normalize_key`, `normalize_org_type`, `normalize_org_type_result`,
  `normalize_content_types` over `config/taxonomy.yaml`, satisfying NM-1 through NM-5.
  Never returns anything outside `ORG_TYPES`; falls back to `unknown` with
  `needs_review: True` for anything unmapped.
- `scripts/gen_taxonomy_js.py`: renders `n8n/code/taxonomy.generated.js` — a pure data
  module (`ORG_TYPES`, `ORG_TYPE_SYNONYMS`, `EVIDENCE_GATED_ORG_TYPES`, `DEFAULT_ORG_TYPE`,
  `CONTENT_TYPES`, `CONTENT_TYPE_SYNONYMS`, `CONTENT_TYPE_IMPLIES`, `DEFAULT_CONTENT_TYPE`)
  via `json.dumps`, no hand-escaping. Deterministic — regenerating twice is a byte-for-byte
  no-op.
- `scripts/build_cloud_workflows.py` regenerates the taxonomy module before any `inline()`
  call runs, so the builder physically cannot emit a workflow with a stale vocabulary.
- `tests/test_taxonomy_conformance.py::test_taxonomy_generated_js_currency`: fails if the
  checked-in generated file doesn't match `render()` right now — proven to actually fire
  by temporarily appending a bogus org_type to `config/taxonomy.yaml` and confirming the
  test failed, then reverting.
- `n8n/code/mergeCompanies.js` now `require()`s `EVIDENCE_GATED_ORG_TYPES` from the
  generated module instead of hand-typing the array — TX-4 (the intentional red carried
  from Phase 11) is now green. `grep -c 'governing_body_league' mergeCompanies.js` is 0.
- `n8n/code/taxonomy.js`: hand-written JS normalizer logic (`normalizeKey`,
  `normalizeOrgType`, `normalizeOrgTypeResult`, `normalizeContentTypes`) consuming the
  generated data — no node wires it up yet (Phase 13's web-research node will).
- `tests/fixtures/taxonomy_parity_cases.json` + a new NM-6 test in
  `tests/n8n/parity.test.mjs`: one Python subprocess call normalizes the whole shared
  table, JS normalizes the same table in-process, `deepStrictEqual` on all three
  normalizer outputs. Deliberately broke the JS regex to prove the guard fires (named the
  divergent `"Racing_Club"` case), then restored.

## Task Commits

1. **Task 1: `src/taxonomy.py` loader + NM-1..NM-5 normalizers** - `fd9888b` (feat)
2. **Task 2: generator + generated JS data module + currency guard** - `e62ff43` (feat)
3. **Task 3: `mergeCompanies.js` consumes the generated list; TX-4 green** - `7b1e5ec` (feat)
4. **Task 4: JS normalizer + NM-6 Python/JS parity test** - `f91239e` (feat)

## Files Created/Modified

- `src/taxonomy.py` - NM-1..NM-5 loader/normalizers over `config/taxonomy.yaml`
- `scripts/gen_taxonomy_js.py` - generator; `render()` used by both the builder and the currency test
- `n8n/code/taxonomy.generated.js` - generated vocabulary data (DO-NOT-EDIT)
- `n8n/code/taxonomy.js` - hand-written JS normalizer logic, parity-proven vs Python
- `tests/fixtures/taxonomy_parity_cases.json` - shared NM-6 case table
- `scripts/build_cloud_workflows.py` - regenerates taxonomy module before inlining; `ENRICH_MERGE_CO` now inlines `taxonomy.generated.js` before `mergeCompanies.js`
- `n8n/code/mergeCompanies.js` - `require`s `EVIDENCE_GATED_ORG_TYPES`, no hand-typed array
- `n8n/wf_enrichment_local_live.json` - regenerated; only the `Merge Company` node's `jsCode` changed
- `tests/test_taxonomy_conformance.py` - `test_taxonomy_generated_js_currency` (TX-4 companion drift guard)
- `tests/test_web_research_spec.py` - 4 `@unbuilt` xfail markers removed (NM-1/2/3/4/5 now implemented)
- `tests/n8n/parity.test.mjs` - NM-6 parity test + `pyTaxonomy` oracle helper

## Decisions Made

- Followed PLAN.md's D1-D4 design decisions exactly: generate a JS *data* module only
  (no new builder machinery beyond the existing `inline()`); keep the ~30 lines of
  normalizer logic hand-written in `taxonomy.js`; leave `icp_scoring.yaml` and
  `field_policy.yaml` hand-written and drift-guarded by the pre-existing TX-1/2/3 tests
  rather than generating them; delete only the 4 NM-* xfail markers this phase satisfies,
  leaving the other 7 (`OC-*`, `TS-1/2/3`, `AT-2`, `ER-1`) exactly as-is for Phase 13.
- `ORG_TYPE_SYNONYMS`/`CONTENT_TYPE_SYNONYMS` in the generated module carry only literal
  YAML synonyms (not canonical-key self-entries); `taxonomy.js`'s hand-written
  `_lookup()` builds the merged canonical+synonym table at require-time, mirroring how
  `src/taxonomy.py`'s `_build_synonym_map` does it in Python. Keeps the generated file
  pure vocabulary data per D2, with the "fold canonical keys in" step living in logic on
  both sides identically.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Currency-guard test name didn't match its own verification's `-k currency` filter**
- **Found during:** Task 2 verify step (currency-guard-fires proof)
- **Issue:** PLAN.md names the new test `test_taxonomy_generated_js_is_current` but its
  own Verify block runs `pytest ... -k currency`. `"is_current"` does not contain the
  substring `"currency"`, so `-k currency` would select zero tests — the guard-fires
  proof's `if pytest ...; then FAIL; fi` would report "guard fires as expected" for the
  wrong reason (0 tests collected -> pytest exit 5 -> non-zero -> `if` branch not taken),
  never actually exercising the assertion.
- **Fix:** Named the test `test_taxonomy_generated_js_currency` instead, so `-k currency`
  actually selects it. Re-ran the guard-fires proof against the corrected name and
  confirmed a genuine `AssertionError` (not a collection no-op) when `config/taxonomy.yaml`
  carries an unregenerated addition.
- **Files modified:** tests/test_taxonomy_conformance.py
- **Verification:** `pytest -k currency` selects exactly 1 test in the passing case; the
  deliberate-drift case shows an `AssertionError` with the "is stale" message, not
  "no tests collected".
- **Committed in:** e62ff43 (Task 2 commit)

**2. [Rule 3 - Blocking] Task 4's deliberate-break verify command targets a file that doesn't exist**
- **Found during:** Task 4 verify step
- **Issue:** PLAN.md's Task 4 Action section and the plan frontmatter's
  `files_modified` both name `tests/n8n/parity.test.mjs` as where the NM-6 test lives.
  The Task 4 Verify block's deliberate-break proof instead runs
  `node --test tests/n8n/taxonomyParity.test.mjs` — a file that is never created anywhere
  in the plan or the codebase. Run verbatim, that command would fail with
  `ENOENT`/module-not-found, which the `if ...; then FAIL; fi` guard would also
  misinterpret as "guard fired as expected" without ever running the real test.
- **Fix:** Ran the deliberate-break proof against the actual file,
  `tests/n8n/parity.test.mjs`, which does contain the new NM-6 test. Confirmed a genuine
  test failure (naming the divergent `"Racing_Club"` case) rather than a file-not-found
  error, then restored the JS file from the file-copy backup per the plan's own
  git-checkout-free convention.
- **Files modified:** none (verification-only; no source change beyond the temporary,
  reverted regex break)
- **Verification:** `node --test tests/n8n/parity.test.mjs` shows 1 failing test with an
  `AssertionError` diff naming `Racing_Club`; after restore, all 46 tests in
  `tests/n8n/*.test.mjs` pass and `git diff --exit-code n8n/code/taxonomy.js` is clean.
- **Committed in:** n/a (no commit needed; nothing was left in a broken state)

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking verification-script issues in
the plan itself, not in the implementation).
**Impact on plan:** Zero scope creep. Both fixes were needed only to make the plan's own
guard-fires proofs actually prove anything; the underlying implementation matched
PLAN.md's Action sections exactly.

## Issues Encountered

- `node --test tests/n8n/` (directory form, no glob) fails with `MODULE_NOT_FOUND` in
  this environment's Node v24.10.0 — pre-existing environment quirk, unrelated to this
  phase's code. Worked around throughout by using `node --test tests/n8n/*.test.mjs` or a
  specific file path, both of which run identically to what the phase's stated baseline
  (45 JS tests green) expects. Not a code change; noted here so a future executor isn't
  surprised by the same symptom.

## Next Phase Readiness

- `src/taxonomy.py` exports `ORG_TYPES`/`ALLOWED_ORG_TYPES`-equivalent constants and the
  normalizer functions Phase 13's web-research prompt and `validate_research_output` /
  `to_provider_result` will consume (`OC-1..4`, `TS-1..3`, `AT-2`, `ER-1` xfails are
  untouched, as directed by PLAN.md's "Out of scope" section).
- `n8n/code/taxonomy.js` exists and is parity-proven but not yet required by any Code
  node — Phase 13 wires it into the web-research node.
- `CONTENT_TYPE_IMPLIES` is generated but not yet consumed anywhere; available for
  Phase 13's produces_content inference.
- No blockers. `.planning/STATE.md`'s "TX-4 red (intentional)" pending todo is now
  resolved and should be cleared/marked retired in the next STATE.md update.

## Self-Check: PASSED

All 5 created files and all 4 task commit hashes verified present on disk / in `git log`.

---
*Phase: 12-taxonomy-single-source*
*Completed: 2026-07-20*
