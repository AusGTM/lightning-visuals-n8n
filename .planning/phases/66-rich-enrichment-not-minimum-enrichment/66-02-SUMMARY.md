---
phase: 66-rich-enrichment-not-minimum-enrichment
plan: 02
subsystem: enrichment
tags: [n8n, field-policy, hubspot, companies-waterfall, test-derivation]

requires:
  - phase: 66-01
    provides: "Contacts REQUIRED already widened to all 12 policy keys; lv_linkedin_url given an Apollo producer; the fetch-list non-clobber fix generalized in this plan's assertion 2"
provides:
  - "tests/n8n/fieldProducerMatrix.test.mjs — four derived assertions (producer, fetch, chase, PN-1 seam) over both lanes, reading config/field_policy.yaml, normalizeProviders.js and the regenerated n8n/wf_enrichment_cloud.json at test runtime"
  - "66-COVERAGE.md — the human-readable producer/consumer matrix, both lanes, 29 policy-key rows"
  - "Company Gate REQUIRED widened from 2 to 13 fields, derived mechanically from the matrix"
  - "ENRICH_COMPANY_SEARCH_PROPERTIES_CSV widened with lv_revenue_band/lv_employee_band so every newly-required field is fetched"
  - "A byte-level snapshot proving CONFLICT_WATCH/MATERIAL_CONFLICT_GROUPS did not move (T-66-09)"
affects: [66-03]

actuals:
  tokens: 9800
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "A matrix test derives its own inputs from source text/YAML/regenerated JSON at runtime, never a hardcoded field list — the same discipline the SUMMARY's own audit rests on"
    - "A merge-policy flag already gating promotion (allow_web_research) doubles as the mechanical signal for 'the research lane produces this field', avoiding a second source-text parser for a wholesale-spread producer"
    - "Known, out-of-assertion-scope gaps (domain, ZoomInfo-linkedin) pinned by small dedicated regression tests rather than folded into an assertion's allow-list, since neither is actually in either assertion's checked scope"

key-files:
  created:
    - tests/n8n/fieldProducerMatrix.test.mjs
    - .planning/phases/66-rich-enrichment-not-minimum-enrichment/66-COVERAGE.md
  modified:
    - scripts/build_cloud_workflows.py
    - tests/n8n/materialConflictNoVetoFlip.test.mjs
    - tests/n8n/companyRecomputeLaneFlow.test.mjs
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_scheduled_maintenance_cloud.json

key-decisions:
  - "Companies REQUIRED derivation rule (three conjuncts, all required): promote_to_canonical: true, class not in {score_output, veto_output}, and the matrix records at least one producing branch. Domain and annualrevenue fail on promote_to_canonical alone; the two veto fields fail on class alone."
  - "The Claude web-research lane's producer status for the 6 ICP fields no provider branch pushes (lv_org_type, lv_produces_content, lv_content_type, lv_sponsorship_reliant, lv_is_hardware_vendor, lv_is_gambling_operator) is derived from config/field_policy.yaml's allow_web_research: true flag, not a source-text scan of webResearch.js's wholesale `{...raw.data}` spread — the spread has no per-field literal to grep for, but the merge-policy flag that already gates promoting a research candidate for that field is an equally load-bearing, and mechanically derivable, signal."
  - "domain and ZoomInfo-contacts-linkedin are NOT allow-list entries inside the four main assertions — both are structurally out of scope (domain: promote_to_canonical false; ZoomInfo-linkedin: lv_linkedin_url already has an Apollo producer). Documented in 66-COVERAGE.md and pinned by two small dedicated regression tests instead of stretching an assertion's allow-list to cover facts the assertion never checks."
  - "companyRecomputeLaneFlow.test.mjs's completeRecord fixture (not in this plan's <files> list) required widening to include all 13 newly-required fields — without it the fixture no longer genuinely reaches a `skip` verdict under the widened gate, and two of that file's tests assert on a genuine skip. Rule 1 auto-fix: a direct, in-scope consequence of Task 2's own change, same class as 66-01's test_fetch_by_id_topology.py fix."
  - "A new comment in ENRICH_CO_GATE originally spelled out 'lv_icp_fit_score' by name; rephrased to 'the derived ICP fit-score field' because that exact literal, once inlined into SJ-2's Company Gate wrapper, tripped tests/n8n/sjPredicates.test.mjs's blob-scan for a derived-ICP-output reference inside any SJ-* node (Approach C, spec §0.7). Root-caused and fixed inline (Rule 1) rather than skipping the test."

patterns-established:
  - "A wrapper-constant array (REQUIRED, CONFLICT_WATCH, MATERIAL_CONFLICT_GROUPS) can be snapshot-pinned byte-for-byte by extracting its literal from the regenerated node's jsCode with a small regex + `new Function` eval, rather than re-implementing the constant's logic in the test."

requirements-completed: [RICH-02, RICH-05]

coverage:
  - id: D1
    description: "The producer/consumer matrix for both lanes is derived (never hardcoded) from config/field_policy.yaml, normalizeProviders.js's pushed literals, the builder's PN-1 renames, and the regenerated workflow JSON; a producer-less promotable field is reported by name."
    requirement: "RICH-05"
    verification:
      - kind: unit
        ref: "tests/n8n/fieldProducerMatrix.test.mjs#D-66-07 producer gate: every promotable, non-recomputed policy key has a producer"
        status: pass
      - kind: unit
        ref: "tests/n8n/fieldProducerMatrix.test.mjs#D-66-03 PN-1 seam: normalizeProviders.js pushes the UNPREFIXED key, never the renamed one"
        status: pass
    human_judgment: false
  - id: D2
    description: "The companies gate's REQUIRED list is derived from the matrix by a written three-part rule rather than chosen by intuition, and the derivation is machine-enforced (chase-gate assertion)."
    requirement: "RICH-02"
    verification:
      - kind: unit
        ref: "tests/n8n/fieldProducerMatrix.test.mjs#chase gate: every producer-having, promotable, non-recomputed policy key is REQUIRED"
        status: pass
      - kind: other
        ref: ".venv/bin/python -c print of the regenerated Company Gate REQUIRED array, matched against 66-COVERAGE.md's derivation by hand"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every newly-required companies field is fetched onto existingRecord (fetch-gate), or the non-clobber comparison would silently permit an overwrite."
    requirement: "RICH-02"
    verification:
      - kind: unit
        ref: "tests/n8n/fieldProducerMatrix.test.mjs#fetch gate: every REQUIRED member is requested by the lane's search node"
        status: pass
    human_judgment: false
  - id: D4
    description: "Widening the companies gate does not disturb the 58-06 material-conflict suppression (CONFLICT_WATCH / MATERIAL_CONFLICT_GROUPS byte-unchanged) or the 47.5 recompute lane."
    requirement: "RICH-02"
    verification:
      - kind: unit
        ref: "tests/n8n/materialConflictNoVetoFlip.test.mjs#T-66-09: Merge Company's CONFLICT_WATCH is byte-unchanged from the pre-plan snapshot"
        status: pass
      - kind: unit
        ref: "tests/n8n/materialConflictNoVetoFlip.test.mjs#T-66-09: Judge Gate's MATERIAL_CONFLICT_GROUPS is byte-unchanged from the pre-plan snapshot"
        status: pass
      - kind: unit
        ref: "tests/n8n/companyRecomputeLaneFlow.test.mjs (all 6 tests, widened completeRecord fixture)"
        status: pass
      - kind: other
        ref: "git diff --exit-code -- n8n/code/providerConflict.js n8n/code/mergeCompanies.js config/field_policy.yaml"
        status: pass
    human_judgment: false
  - id: D5
    description: "The widened gate still gates a genuinely complete companies record to skip (both cache-key timestamps required), and reports a blanked field in missingFields."
    requirement: "RICH-02"
    verification:
      - kind: unit
        ref: "tests/n8n/materialConflictNoVetoFlip.test.mjs#D-66-01: a company holding every newly-required field AND both cache-key timestamps skips"
        status: pass
      - kind: unit
        ref: "tests/n8n/materialConflictNoVetoFlip.test.mjs#D-66-01: blanking one newly-required field reports it in missingFields, gate enriches"
        status: pass
    human_judgment: false

duration: 45min
completed: 2026-09-05
status: complete
---

# Phase 66 Plan 02: Field Producer/Consumer Matrix + Derived Companies Gate Summary

**Built a self-deriving matrix test over both lanes, then widened the companies enrichment gate from 2 chased fields to 13 by reading its own output — while proving byte-for-byte that the 58-06 conflict-adjudication guard and the 47.5 recompute lane never moved.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 2
- **Files modified:** 8 (2 created, 6 modified)

## Accomplishments
- `tests/n8n/fieldProducerMatrix.test.mjs` derives, at test runtime, every input it checks — the 12 contacts and 17 companies `config/field_policy.yaml` keys, the pushed field literals from each of `normalizeProviders.js`'s three provider functions (split contacts vs companies by their shared `if (objectType === "contacts") { ... } else { ... }` shape), the two PN-1 rename mappings from `scripts/build_cloud_workflows.py`'s `winners.X` read sites, and each lane's `REQUIRED`/search-property list from the regenerated `n8n/wf_enrichment_cloud.json`. Four assertions: producer gate, fetch gate, chase gate, PN-1 seam.
- `66-COVERAGE.md` renders the matrix as a human-readable table for both lanes (29 rows), naming the three-spellings-of-one-field seam that made `lv_linkedin_url` invisible, and documenting the two known producer-less gaps (ZoomInfo contacts LinkedIn, companies `domain`) each with its citation — neither is actually in scope of any of the four assertions, so each is separately pinned by its own small regression test rather than stretched into an assertion's allow-list.
- `ENRICH_CO_GATE`'s `REQUIRED` widens from `["lv_org_type", "lv_produces_content"]` to 13 fields — `industry`, `numberofemployees`, `lv_revenue_band`, `lv_employee_band`, `lv_country_region_normalized`, `country`, `city`, `lv_content_type`, `lv_sponsorship_reliant`, `lv_is_hardware_vendor`, `lv_is_gambling_operator` join the existing two — derived from the matrix's three-part rule, written into the wrapper comment. `domain` and `annualrevenue` stay excluded (`promote_to_canonical: false`); the two `veto_output` fields stay excluded (recomputed, never chased).
- `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` gains `lv_revenue_band`/`lv_employee_band` — the only two newly-required fields not already fetched — closing the fetch-gate hole the same class of defect this constant's own comment block already records twice (WR-01, VETO-01/58-05).
- A byte-level snapshot in `materialConflictNoVetoFlip.test.mjs` proves `CONFLICT_WATCH` (`Merge Company`) and `MATERIAL_CONFLICT_GROUPS` (both `Judge Gate` and `Merge Company`) are unchanged from before this plan, plus `git diff --exit-code` on `providerConflict.js`/`mergeCompanies.js`/`config/field_policy.yaml`.
- A widened-gate skip fixture proves a company holding all 13 required values plus both `lv_org_type_verified_at`/`lv_produces_content_verified_at` cache-key timestamps still gates to `skip` (only those two fields carry a TTL — the other 11 just need to be non-blank), and that blanking one field surfaces it in `missingFields`.

## Task Commits

Each task was committed atomically:

1. **Task 1: The producer/consumer matrix, both lanes** - `a433a1c` (test)
2. **Task 2: Widen the companies gate from the matrix, prove the conflict guard did not move** - `aee8dde` (feat)

**Plan metadata:** committed separately below.

## Files Created/Modified
- `tests/n8n/fieldProducerMatrix.test.mjs` - new: 9 tests (2 known-gap pins + 4 main derived assertions across both lanes + 2 PN-1 seam tests, one assertion loops both lanes so 4 logical assertions run as fewer top-level `test()` calls)
- `.planning/phases/66-rich-enrichment-not-minimum-enrichment/66-COVERAGE.md` - new: the human matrix, both lanes
- `scripts/build_cloud_workflows.py` - `ENRICH_CO_GATE`'s `REQUIRED` widened 2→13 with the derivation rule in-comment; `ENRICH_COMPANY_SEARCH_PROPERTIES_CSV` gains 2 properties
- `tests/n8n/materialConflictNoVetoFlip.test.mjs` - +5 tests: 3 conflict-watch snapshot assertions (T-66-09), 2 widened-gate skip/missing fixtures (D-66-01)
- `tests/n8n/companyRecomputeLaneFlow.test.mjs` - `completeRecord` fixture widened to all 13 required fields (Rule 1 auto-fix — its "complete" premise broke under the widened gate)
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local_live.json`, `n8n/wf_scheduled_maintenance_cloud.json` - regenerated via `scripts/build_cloud_workflows.py`, never hand-edited; the other 5 `n8n/wf_*.json` files regenerate byte-identical (they don't use `ENRICH_CO_GATE`); node count on `wf_enrichment_cloud.json` unchanged at 123

## Decisions Made
- Companies `REQUIRED` derivation rule: `promote_to_canonical: true` AND class not in `{score_output, veto_output}` AND the matrix records a producer. Written into the wrapper's own comment so a future reader can re-derive it without re-reading this SUMMARY.
- The Claude web-research lane's producer status for the 6 ICP fields (`lv_org_type`, `lv_produces_content`, `lv_content_type`, `lv_sponsorship_reliant`, `lv_is_hardware_vendor`, `lv_is_gambling_operator`) is derived from `config/field_policy.yaml`'s `allow_web_research: true` flag rather than parsing `webResearch.js`'s wholesale `{...raw.data}` spread, which has no per-field literal to grep for. The flag is the same one the merge policy already reads to gate promoting a research candidate for that field, so it is an equally load-bearing and mechanically derivable signal.
- `domain` and the ZoomInfo-contacts-LinkedIn gap are documented, not force-fit into any assertion's allow-list — both are structurally outside all four assertions' checked scope (`domain`: `promote_to_canonical: false`; ZoomInfo-LinkedIn: `lv_linkedin_url` already has an Apollo producer from 66-01). Each is pinned by its own small regression test instead.
- `companyRecomputeLaneFlow.test.mjs`'s `completeRecord` fixture needed widening even though it is not in this plan's `<files>` list — a direct, in-scope consequence of Task 2's gate change (its "complete" premise no longer reached a genuine `skip` verdict), same auto-fix class as 66-01's `test_fetch_by_id_topology.py` fix.
- A new wrapper comment originally spelled `lv_icp_fit_score` by name; rephrased after it got inlined into SJ-2's Company Gate node and tripped `sjPredicates.test.mjs`'s existing blob-scan guard (Approach C, spec §0.7: no SJ node may reference a derived ICP output field). Fixed inline rather than weakening either test.

## Deviations from Plan

None architecturally — plan executed as written, including both `<notes_for_the_executor>` items (D-66-10 parity vacuous, no RESEARCH/VALIDATION docs). Two Rule-1 auto-fixes surfaced as direct consequences of Task 2's own edit and are documented above (`companyRecomputeLaneFlow.test.mjs`'s fixture; the `sjPredicates.test.mjs` comment collision) — both are exactly the class of "discovered during the task, fixed inline, tracked as a deviation" the executor protocol expects, not a departure from the plan's intent.

## Issues Encountered
- `sjPredicates.test.mjs`'s existing "no SJ filter block anywhere in the built workflow references a derived ICP output field" guard scans the JSON blob of every `SJ-*`-named node for `lv_icp_tier|lv_icp_fit_score|lv_icp_scored_at`. Since `ENRICH_CO_GATE` is inlined into `wf_scheduled_maintenance_cloud.json`'s `SJ-2 Company Gate` node, a new comment I wrote that happened to spell `lv_icp_fit_score` literally tripped this guard on regeneration. Caught immediately by the full `node --test` run; fixed by rephrasing the comment (Rule 1).
- `companyRecomputeLaneFlow.test.mjs`'s `completeRecord`/`unstampedRecord` fixtures predate this plan and were not in Task 2's `<files>` list, but `completeRecord` genuinely needed widening (2 of its 6 consuming tests assert `r.gate.gate.action === "skip"`, which the widened gate would no longer produce against the old 2-field fixture). `unstampedRecord` needed no change — its consuming test only asserts `action === "enrich"`, true whether the reason is "stale" (pre-plan) or now also "missing".

## User Setup Required
None - no external service configuration required. Nothing is armed and nothing is deployed to n8n Cloud (CLAUDE.md §13.0.2's undeployed delta grows further, deliberately — this plan adds a fourth regenerate-and-commit-without-deploy round on top of the ones already recorded there).

## Next Phase Readiness
- The final companies `REQUIRED` list: `industry`, `numberofemployees`, `lv_revenue_band`, `lv_employee_band`, `lv_country_region_normalized`, `country`, `city`, `lv_org_type`, `lv_produces_content`, `lv_content_type`, `lv_sponsorship_reliant`, `lv_is_hardware_vendor`, `lv_is_gambling_operator` (13 of 17 policy keys). Excluded: `domain` (producer-less + not promotable), `annualrevenue` (not promotable — the execution-runaway-shape exclusion), `lv_anti_icp_flag`/`lv_anti_icp_reason` (recomputed, never chased).
- Producer-less field the matrix surfaced: companies `domain` — cited, not fixed, per 66-CONTEXT.md's `<deferred>` block; open todo `.planning/todos/pending/2026-09-04-company-domain-has-no-candidate-source.md` remains open for a future plan.
- Post-plan `node --test tests/n8n/*.test.mjs`: **931 pass / 0 fail** (baseline 919 + 12 new tests: 7 in `fieldProducerMatrix.test.mjs`, 5 in `materialConflictNoVetoFlip.test.mjs`). `.venv/bin/python -m pytest -x -q`: **4240 passed / 154 skipped**, unchanged from baseline (D-66-10 parity remains vacuous — no Python-side `REQUIRED`-shaped constant exists to move).
- No blockers for 66-03.

---
*Phase: 66-rich-enrichment-not-minimum-enrichment*
*Completed: 2026-09-05*

## Self-Check: PASSED

All claimed files found on disk; both task commit hashes (`a433a1c`, `aee8dde`) found in git log.
