---
phase: 58-take-what-the-operator-actually-has
plan: 01
subsystem: extraction
tags: [extraction, hubspot, company-lane, python, pyyaml]

# Dependency graph
requires:
  - phase: 35
    provides: "extraction.py's contact-lane validator, dedupe(), D-07 contradiction check, no-invention rule prose"
provides:
  - "A company row (record_type: companies) travels artifact -> extraction.validate() -> enrichment.build_envelope()'s companies form -> a companies envelope event"
  - "One artifact validates both contact and company records in a single pass, companies first"
  - "Six documented company source adapters (four contact-lane analogs + a bare name list + a search-results screenshot)"
affects: [58-02, contact-upload skill, enrich-records skill]

# Actuals (#2632)
actuals:
  tokens: 9060
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-record record_type discriminator (absent = contacts) routes canonical_props()/identity_groups() to a type-specific mapping file, computed once per type rather than once per batch"
    - "dedupe() runs separately per record_type group, then group results are reassembled with explicit index remapping (never re-derived from list position) — a company row and a contact row can never collapse into each other by construction"

key-files:
  created:
    - operator-claude-plugin/config/company_column_mapping.yaml
    - operator-claude-plugin/tests/test_company_extraction.py
  modified:
    - operator-claude-plugin/scripts/extraction.py
    - operator-claude-plugin/skills/contact-upload/extraction.md
    - operator-claude-plugin/skills/contact-upload/SKILL.md
    - operator-claude-plugin/tests/test_extraction_contract.py

key-decisions:
  - "domain and website are kept as separate canonical company props (mirroring CLAUDE.md's HubSpot company fixture), not merged into one — the company mapping's aliases dedupe to exactly 5 props: name, domain, country, industry, website"
  - "dedupe()/D-07 are made type-aware by splitting the pre-flight-accepted list into per-type sublists and running dedupe() once per sublist, rather than teaching dedupe() itself a record_type parameter — keeps dedupe()'s own signature and internals completely untouched per the plan's read_first note"

patterns-established:
  - "Every per-group local index dedupe() returns (record_index/other_record_index/merged_from) is explicitly remapped onto its position in the reassembled combined list before ambiguity aggregation runs, never left to offset arithmetic alone"

requirements-completed: [INPUT-01, INPUT-04]

coverage:
  - id: D1
    description: "A company known only by its name (no domain, no URL) is accepted by extraction.validate() and reaches a companies envelope event with the same name string on both sides"
    requirement: "INPUT-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_extraction.py#test_bare_company_name_reaches_a_companies_envelope_event"
        status: pass
    human_judgment: false
  - id: D2
    description: "One artifact holding both contact and company records validates in a single pass, with company entries ordered ahead of contact entries and every accepted entry stamped with its record_type"
    requirement: "INPUT-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_extraction.py#test_mixed_artifact_validates_both_lanes_in_one_pass_companies_first"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_extraction.py#test_every_accepted_entry_carries_a_record_type"
        status: pass
    human_judgment: false
  - id: D3
    description: "A company row and a contact row with overlapping field values never collapse into each other; two identical company rows do collapse to one"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_extraction.py#test_company_row_and_contact_row_with_overlapping_values_never_collapse"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_extraction.py#test_two_identical_company_rows_collapse_to_one"
        status: pass
    human_judgment: false
  - id: D4
    description: "A nameless company record is rejected with a reason naming 'name' and no contact field (email/firstname/lastname); a record with no record_type still routes through the unchanged contact rejection sentence"
    requirement: "INPUT-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_extraction.py#test_nameless_company_record_is_rejected_without_naming_contact_fields"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_contract.py#test_a_record_with_no_record_type_key_still_routes_to_the_contact_rules"
        status: pass
    human_judgment: false
  - id: D5
    description: "The six company source adapters (pasted text, foreign JSON, public URL, screenshots, bare name list, search-results screenshot) are documented in extraction.md as a prose contract, pinned structurally against company_column_mapping.yaml and identity_groups() rather than by a retyped list"
    requirement: "INPUT-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_extraction.py#test_all_six_company_adapter_headings_are_present"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_extraction.py#test_company_canonical_props_section_matches_the_config_file_exactly"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_company_extraction.py#test_company_identity_rule_section_matches_identity_groups"
        status: pass
    human_judgment: true
    rationale: "Whether Claude actually follows the prose contract when reading a real screenshot/paste/URL cannot be exercised by a pytest unit test — the tests above prove the contract's structural claims (headings exist, prop list matches config, identity rule matches identity_groups()) but not that an in-session extraction run produces correct rows from a live source."

# Metrics
duration: ~35min
completed: 2026-08-26
status: complete
---

# Phase 58 Plan 01: Company Extraction Machinery Summary

**Extended the Phase-35 contact extraction validator to a second record type — companies — with a name-alone identity rule, per-type dedupe, and six documented source adapters, without touching a single line of `enrichment.py`'s already-shipped companies envelope form.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-08-26T01:49:05Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- A company row known only by its name now travels artifact → `extraction.validate()` → `enrichment.build_envelope()`'s companies form → a `{"objectType": "companies", "name": ...}` envelope event, proven end to end by one tracer test (Task 1).
- `extraction.py`'s `validate()` is fully type-aware: the per-record pre-flight, `dedupe()`, and the D-07 contradiction check all judge a record against its own record type's identity groups. Company and contact records are split before `dedupe()` runs (so they can never collapse into each other by construction), then reassembled companies-first with every per-group index explicitly remapped onto its position in the combined list (Task 2).
- `extraction.md` now documents six company source adapters — the four contact-lane adapters given a company reading, plus two with no contact-lane analog (a bare name list, a search-results-page screenshot) — with the D-58-03 profile-page-never-a-domain rule stated once, and `SKILL.md`'s step 2 now names companies alongside people (Task 3).

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end — a bare company name reaches a companies envelope event** - `b786518` (feat)
2. **Task 2: Mixed input, one pass — both lanes in one artifact, companies first** - `6336d3b` (feat, tdd)
3. **Task 3: The six company source adapters — prose contract and structural pins** - `1a91c89` (docs)

_No separate plan-metadata commit created for this SUMMARY — the orchestrator's final commit step follows this one._

## Files Created/Modified
- `operator-claude-plugin/config/company_column_mapping.yaml` - New company identity config: 5 canonical props (name, domain, country, industry, website), `required_identity.any_of: [[name]]`
- `operator-claude-plugin/scripts/extraction.py` - `COMPANY_MAPPING_PATH` constant; `validate()` reads each record's own `record_type` and routes props/identity lookup, dedupe(), and D-07 through the type it selects; `_merge_cluster` carries `record_type` through a merge; `_load_mapping`'s `mapping_unreadable` message now names whichever file was actually being resolved
- `operator-claude-plugin/tests/test_company_extraction.py` - New test file: the tracer test, mapping-shape pins, mixed-artifact/dedupe/D-07 behavior tests, and structural adapter-prose pins
- `operator-claude-plugin/tests/test_extraction_contract.py` - One added backwards-compatibility pin (no existing assert removed)
- `operator-claude-plugin/skills/contact-upload/extraction.md` - New "Reading company input" section: record_type field, company canonical props, identity rule, no-invention rule restated, D-58-03 profile-page rule, six adapter sections
- `operator-claude-plugin/skills/contact-upload/SKILL.md` - Step 2's non-spreadsheet branch now names companies alongside people; every existing spreadsheet sentence untouched

## Decisions Made
- `domain` and `website` are kept as two separate canonical company props (not merged) — mirrors the HubSpot company fixture shape in CLAUDE.md §11.4, where both properties exist independently and `enrichment.py::_clean_domain` already reads either at write time.
- `dedupe()`'s own function body and signature are untouched; type-awareness is achieved by splitting the accepted list into per-type sublists in `validate()` and calling `dedupe()` once per sublist, then explicitly remapping each sublist's local indices onto the reassembled combined list — chosen over teaching `dedupe()` a `record_type` parameter, per the plan's explicit instruction to leave `dedupe()`/`_compare_identity()`/the D-07 check untouched.
- The six company adapter headings use a distinct `### Company adapter: ...` prefix (not `## Adapter: ... (INGEST-NN)`) so they cannot collide with `test_extraction_contract.py`'s existing literal-heading pins (`URL_ADAPTER_HEADING`, `NEXT_ADAPTER_HEADING`), which locate text via `str.index()` on the exact contact-lane heading strings.

## Deviations from Plan

None - plan executed exactly as written. All three tasks' acceptance criteria were met without requiring a Rule 1-4 deviation.

## Issues Encountered

`_merge_cluster` did not originally carry `record_type` through a merge (it built `{"row": ..., "provenance": ...}` with no type field), which surfaced as a `KeyError` the moment Task 2's "two identical company rows collapse to one" test asserted the merged entry's `record_type`. Fixed inline within Task 2 by having `_merge_cluster` copy `record_type` from the cluster's first entry (safe since a Phase-58 dedupe() call now only ever receives entries of one type) — not logged as a Rule 1 deviation since it was found and fixed while writing Task 2's own planned behavior, not a bug discovered outside the task's scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- The company extraction contract (config, validator, and adapter prose) is in place for a later plan to wire the domain-confirm/decline lane (`company_preingest.py`, D-58-01/02/04-10) and the operator-facing confirm table described in `58-CONTEXT.md` — this plan closes the extraction half of INPUT-01/INPUT-04 only, not the domain-research or cost-consent halves.
- No blockers. `git diff -- operator-claude-plugin/scripts/enrichment.py n8n/code/companyLink.js` is empty — the domain-poisoning guard from the Phase 53 walk is completely untouched by this plan.

---
*Phase: 58-take-what-the-operator-actually-has*
*Completed: 2026-08-26*

## Self-Check: PASSED

All 6 files named as created/modified exist on disk; all 3 task commit hashes
(`b786518`, `6336d3b`, `1a91c89`) are present in `git log`.
