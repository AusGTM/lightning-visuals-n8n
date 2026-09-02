---
phase: 24-non-tabular-input-adapters
plan: 01
subsystem: infra
tags: [claude-plugin, extraction, validation, provenance, identity-rule]

requires:
  - phase: 23-04
    provides: dispatch.py, config_gate.py, tabular.py, plugin.json, SKILL.md shell
  - phase: 23-05
    provides: preview.py (label_headers, build_preview), operator README
provides:
  - "operator-claude-plugin/scripts/extraction.py — canonical_props(), identity_groups(), has_identity(), load_artifact(), validate(), ExtractionResult, ExtractionError, write_dispatch_csv(), plus a JSON-printing __main__ CLI"
  - "operator-claude-plugin/scripts/preview.py — resolve_mapping_path() (the one shared rule for finding config/column_mapping.yaml), _adaptive_sample() (shared sampling rule), build_extracted_preview()"
  - "operator-claude-plugin/tests/conftest.py — extraction_artifact_factory and extraction_artifact fixtures"
  - "operator-claude-plugin/scratch/ — non-dot, gitignored scratch directory for the extraction handoff artifact (D-10)"
affects: [24-02, 24-03]

tech-stack:
  added: []
  patterns:
    - "extraction.py validates a Claude-written JSON artifact rather than parsing chat
      prose (Pitfall 1) — a file boundary, not a chat-parsing boundary"
    - "canonical-key diff BEFORE removal, not after: dropped_keys are recorded before the
      row is cleaned, so 'reported rather than silently dropped' is provable per-record"
    - "write_dispatch_csv() enforces STRUCT-01 structurally: it raises on ANY row key
      outside canonical_props(), so a smuggled provenance key is caught by the same
      allowlist check as any other invented field — no special-casing needed"

key-files:
  created:
    - operator-claude-plugin/scripts/extraction.py
    - operator-claude-plugin/tests/test_extraction_handoff.py
    - operator-claude-plugin/tests/test_identity_preflight.py
    - operator-claude-plugin/tests/test_provenance_strip.py
  modified:
    - operator-claude-plugin/scripts/preview.py
    - operator-claude-plugin/tests/conftest.py
    - operator-claude-plugin/tests/test_no_backend_imports.py
    - .gitignore

key-decisions:
  - "resolve_mapping_path() lifted out of preview.py's build_preview() (was inline) into
    a named, importable function — extraction.py calls it for path resolution only;
    extraction.py owns its own YAML parsing so canonical_props()/identity_groups() can
    raise on an unavailable mapping file while preview.py's own display-label reading
    still degrades gracefully. This avoids a preview<->extraction import cycle: preview.py
    never imports extraction.py (build_extracted_preview() is duck-typed against
    result.accepted/.rejected/.dropped_keys/.ambiguities)."
  - "write_dispatch_csv() takes flat row dicts (canonical prop -> value), not
    {row, provenance} pairs — callers extract record['row'] first. This is what makes the
    STRUCT-01 guard generic: a 'provenance' key surviving into a row dict is caught by
    the same 'any key outside canonical_props()' check as any other invented field,
    rather than a bespoke provenance-stripping step that could be forgotten."
  - "Provenance schema settled as {input, locator} (which source, which span/path/region
    within it) rather than a richer structure — the two facts STRUCT-03 requires, no
    more; plan 24-03's SKILL.md half will emit exactly this shape."

requirements-completed: [INGEST-01, INGEST-03, INGEST-06, STRUCT-02, STRUCT-03, STRUCT-04]

coverage:
  - id: D1
    description: "A prose extraction artifact on disk becomes canonical rows and dispatch-ready CSV bytes with no Anthropic API call and no API key anywhere in the module"
    requirement: "INGEST-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_handoff.py#test_write_dispatch_csv_header_matches_canonical_props_and_round_trips"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_handoff.py#test_canonical_props_returns_exactly_the_seven_alias_targets"
        status: pass
    human_judgment: false
  - id: D2
    description: "A row failing the identity rule (missing email and missing firstname+lastname+company, including whitespace-only fields) is excluded from the payload and reported with a reason naming the rule; the check trims whitespace, diverging deliberately from src/file_loader.py::_has_identity to match the deployed Map Columns node"
    requirement: "STRUCT-02"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_identity_preflight.py#test_whitespace_only_identity_field_is_rejected_diverging_deliberately_from_file_loader_has_identity"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_identity_preflight.py#test_record_missing_identity_is_rejected_with_reason_naming_the_rule_and_not_accepted"
        status: pass
    human_judgment: false
  - id: D3
    description: "A key outside the canonical 7-prop set is stripped from the row and reported (record index + key), while the record is still accepted if the remaining fields satisfy identity — reported, never silently dropped"
    requirement: "INGEST-03"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_identity_preflight.py#test_non_canonical_key_is_stripped_and_reported_and_row_still_accepted"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every accepted row carries non-empty provenance (input + locator); a record with no provenance or a partial provenance is rejected with a reason; one malformed record never crashes the surrounding batch"
    requirement: "STRUCT-03"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_handoff.py#test_validate_two_record_artifact_all_accepted_zero_rejected_with_provenance"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_identity_preflight.py#test_record_provenance_missing_locator_is_rejected"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_identity_preflight.py#test_malformed_record_does_not_prevent_surrounding_records_from_being_accepted"
        status: pass
    human_judgment: false
  - id: D5
    description: "A missing, unparseable, wrong-shaped, or empty extraction artifact raises a distinct named ExtractionError code, never a silent zero-row success; the CLI exits non-zero printing that code as JSON"
    requirement: "INGEST-06"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_identity_preflight.py#test_load_artifact_empty_records_raises_artifact_empty"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_identity_preflight.py#test_cli_exits_nonzero_and_prints_code_on_missing_artifact"
        status: pass
    human_judgment: false
  - id: D6
    description: "The dispatch CSV's header set is a subset of canonical props with zero provenance columns; write_dispatch_csv() raises rather than widening the header when handed a row carrying a non-canonical key (including a smuggled provenance key) — provenance stays a preview-only sidecar (D-04) and STRUCT-01 is structurally enforced, not a runtime filter someone can forget"
    requirement: "STRUCT-04"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_provenance_strip.py#test_dispatch_csv_header_is_subset_of_canonical_props_with_no_provenance_column"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_provenance_strip.py#test_write_dispatch_csv_raises_on_row_with_key_outside_canonical_set"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_provenance_strip.py#test_build_extracted_preview_surfaces_provenance_for_the_same_record_the_csv_omits_it_from"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-07-30
status: complete
---

# Phase 24 Plan 01: Extraction Validator, Provenance, Identity Pre-Flight Summary

**`extraction.py` validates a Claude-written JSON extraction artifact (never extracts anything itself), derives the 7-prop canonical allowlist and identity groups from `config/column_mapping.yaml`, trims before checking identity presence (matching the deployed `Map Columns` node rather than `src/file_loader.py::_has_identity`'s stale, untrimmed mirror), and produces a dispatch CSV that structurally cannot carry a provenance column.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-30T21:14:43Z
- **Completed:** 2026-07-30T21:23:02Z
- **Tasks:** 3
- **Files modified:** 8 (4 created, 4 modified)

## Accomplishments

- `extraction.py` documents and validates the artifact contract every future adapter
  (24-02, 24-03) emits into: `{batch_id, source{kind,detail}, records[{row, provenance}],
  ambiguities}`. `canonical_props()` and `identity_groups()` derive both governing rules
  from `config/column_mapping.yaml`'s `aliases` values and `required_identity.any_of` —
  never retyped, so neither can drift from the backend (D-11).
- `has_identity()` mirrors the deployed n8n `Map Columns` node's `requiredIdentity()`
  exactly: coerce to string, strip, test non-empty, any satisfied group passes. This is a
  deliberate divergence from `src/file_loader.py::_has_identity`, which omits the trim —
  a whitespace-only field that Python's existing mirror would wrongly accept is rejected
  here, matching what the live backend actually does.
- `validate()` runs the per-record isolation pattern `src/file_loader.py::ingest_file`
  already established (try/except per record, structured rejects with a reason) and adds
  the canonical-key diff BEFORE removal — every non-canonical key is recorded with its
  record index before being stripped, so "reported rather than silently dropped"
  (criterion 2) is proven per-record, not just asserted in prose.
- `load_artifact()` raises a distinct `ExtractionError` code for every artifact-shape
  failure — absent path, unparseable JSON, wrong top-level shape, empty records list, or
  an unavailable mapping file — never a best-effort partial parse. An empty `records`
  list is treated as an error (`artifact_empty`), not a zero-row success, per criterion 6.
- `write_dispatch_csv()` is the STRUCT-01 enforcement site: it emits every canonical prop
  as the header in deterministic (sorted) order every time, empty cell where a row has
  no value, and **raises** on any row key outside `canonical_props()` — including a
  `provenance` key smuggled into a flat row dict, since provenance is caught by the same
  generic allowlist check as any other invented field. No special-casing needed; the
  strip is structural.
- `preview.py` gains `resolve_mapping_path()` (the mapping-file lookup, lifted out of
  `build_preview()`'s inline logic so extraction.py reuses the exact same rule) and
  `build_extracted_preview()`, which surfaces every accepted row's provenance, the
  rejected list, dropped-key reports, and ambiguities in one structure — reusing the
  same `_adaptive_sample()` rule `build_preview()` applies, so the tabular and extraction
  preview surfaces never disagree about the same batch.
- The plugin scratch directory (`operator-claude-plugin/scratch/`) is created and
  gitignored per D-10 — non-dot, since dot-directories are permission-blocked to tooling
  in this environment.

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end "prose artifact becomes dispatch-ready CSV bytes" (tracer)** - `8d61b39` (feat)
2. **Task 2: Rejection and reporting — identity pre-flight, non-canonical keys, named artifact errors** - `7a9a553` (test)
3. **Task 3: Provenance visible in preview, structurally absent from the wire** - `f5bcec8` (feat)

_Note: extraction.py's rejection/reporting logic (Task 2's behavior) was implemented as
part of Task 1's initial write, since the tracer task and the rejection-path task share
one file and the module was written holistically. Task 2's commit adds only its own new
test file — the implementation it validates against was already present and already
green from Task 1's commit. Task 3's `build_extracted_preview()` was genuinely deferred
out of `preview.py` until its own commit (temporarily removed after being drafted, then
re-added) so each commit's diff matches its task's actual scope._

## Files Created/Modified

- `operator-claude-plugin/scripts/extraction.py` - canonical_props(), identity_groups(), has_identity(), load_artifact(), validate(), ExtractionResult, ExtractionError, write_dispatch_csv(), CLI
- `operator-claude-plugin/scripts/preview.py` - resolve_mapping_path(), _adaptive_sample(), build_extracted_preview() added; build_preview() refactored to use both (no behavior change)
- `operator-claude-plugin/tests/conftest.py` - extraction_artifact_factory, extraction_artifact fixtures
- `operator-claude-plugin/tests/test_extraction_handoff.py` - happy-path tracer tests
- `operator-claude-plugin/tests/test_identity_preflight.py` - rejection/reporting/error-taxonomy tests
- `operator-claude-plugin/tests/test_provenance_strip.py` - STRUCT-01 structural-guard tests
- `operator-claude-plugin/tests/test_no_backend_imports.py` - LOCAL_MODULES gains preview/extraction
- `.gitignore` - operator-claude-plugin/scratch/ added

## Decisions Made

- **`write_dispatch_csv()` accepts flat row dicts, not `{row, provenance}` pairs.**
  Callers extract `record["row"]` before calling it. This is what makes the STRUCT-01
  guard generic rather than provenance-specific: a `provenance` key surviving into a row
  dict is caught by the same "any key outside `canonical_props()`" check as any other
  invented field, so the strip needs no special case for provenance specifically.
- **`resolve_mapping_path()` lifted into `preview.py`, not duplicated in `extraction.py`.**
  Both modules need the same "explicit path → repo config → unavailable" rule; keeping
  it in one place (per the plan's explicit instruction) means it cannot drift. No import
  cycle results because `preview.py` never imports `extraction.py` —
  `build_extracted_preview()` is duck-typed against `result.accepted`/`.rejected`/
  `.dropped_keys`/`.ambiguities` rather than importing `ExtractionResult`.
- **Provenance schema settled as `{input, locator}`.** The two facts STRUCT-03 requires
  (which input, which span/path/region within it) — no richer structure, since plan
  24-03's SKILL.md prose half must emit exactly this shape and any additional required
  field would need independent justification.

## Deviations from Plan

None — plan executed exactly as written. The `test_no_backend_imports.py` LOCAL_MODULES
update was a direct, in-scope consequence of Task 1 adding `extraction.py` (which imports
`preview.py` per the plan's own instruction to reuse its mapping resolver) — not a
deviation from the plan, but a necessary companion edit to an existing architecture-guard
test that the plan's file list didn't enumerate. Documented here for completeness.

## Issues Encountered

A concurrent sibling agent (plan 25-02, working in `n8n/` and the repo-root `scripts/`
per this plan's own note) left 4 unrelated test failures in the working tree at the time
of the final full-suite run (`tests/test_architecture_guard.py`,
`tests/test_deploy_credential_binding.py` x2, `tests/test_write_gate_coverage.py`, all
tied to `scripts/build_cloud_workflows.py` and `n8n/wf_backend_status_cloud.json`).
Confirmed via `git diff --name-only 8d61b39^..f5bcec8` that none of this plan's three
commits touch any file outside `operator-claude-plugin/` and `.gitignore` — the failures
are the other agent's in-progress WIP, not a regression introduced here.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — 66 passed (41 baseline +
  25 new), no regressions.
- `.venv/bin/python -m pytest -q` (full repo suite, isolated to this plan's own commits)
  — 774 passed at the point this plan's work was complete (749 baseline + 25 new); the 4
  failures observed afterward are the concurrent sibling agent's unrelated WIP (see
  Issues Encountered).
- `git diff --name-only 8d61b39^..f5bcec8` confirms every file this plan touched lives
  under `operator-claude-plugin/` or is `.gitignore` — no backend file modified.
- 24-02 and 24-03 (the foreign-JSON, URL, and screenshot adapters, plus SKILL.md's
  prose-extraction instructions) can now target this plan's artifact contract directly:
  write `{batch_id, source, records[{row, provenance}], ambiguities}` to a scratch file
  under `operator-claude-plugin/scratch/`, then invoke
  `python operator-claude-plugin/scripts/extraction.py <path>` and parse its JSON stdout.
- D-13 (the drift pin — a contract test parsing `extraction.md`'s fenced example
  artifacts through the real validator) is not yet built: `extraction.md` itself is a
  24-03 deliverable, so that pin belongs to whichever plan writes SKILL.md's
  prose-extraction half and can reference a real fenced example.

---
*Phase: 24-non-tabular-input-adapters*
*Completed: 2026-07-30*

## Self-Check: PASSED

All created files and commit hashes verified present on disk / in git log.
