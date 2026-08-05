---
phase: 37-enrich-before-ingest
plan: 02
subsystem: extraction
tags: [extraction, ingest-gate, hubspot, tdd]

requires:
  - phase: 34-plugin-extraction
    provides: "extraction.py's canonical-key validation, has_identity, write_dispatch_csv guard-before-open idiom"
provides:
  - "extraction.hold_emailless(rows) -> (sendable, held) — the STRUCT-02 separator every enrich-before-ingest caller uses to report held rows before ingest"
  - "write_dispatch_csv's emailless-row raise (code emailless_row_cannot_ingest) — the STRUCT-02 choke-point enforcement every caller routes through"
affects: [37-03, 37-05]

actuals:
  tokens: 3574
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Guard-before-open idiom extended: a second pre-open check added to write_dispatch_csv's existing loop, same shape as the non-canonical-key guard"
    - "Partition-and-name idiom for held rows (index, row, reason), modeled on dedupe's report entries"

key-files:
  created:
    - operator-claude-plugin/tests/test_extraction_email_gate.py
  modified:
    - operator-claude-plugin/scripts/extraction.py
    - operator-claude-plugin/tests/test_extraction_handoff.py

key-decisions:
  - "hold_emailless and write_dispatch_csv's raise both check presence through the same _present() helper has_identity already uses — the separator and the gate can never disagree about what an empty email cell is."
  - "No force flag, override parameter, or stub-record path was added — the only way to send a held row is to give it an email (37-CONTEXT.md must_haves.prohibitions)."

requirements-completed: [STRUCT-01, STRUCT-02]

coverage:
  - id: D1
    description: "extraction.hold_emailless(rows) partitions every row into (sendable, held) exactly once, in input order, and names each held row's index, content, and reason."
    requirement: STRUCT-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_email_gate.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "write_dispatch_csv raises ExtractionError for a row with no usable email, before out_path is opened, so a refused call — including one caused by a row late in the list — leaves no file on disk."
    requirement: STRUCT-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_email_gate.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_extraction_handoff.py::test_write_dispatch_csv_refuses_the_emailless_row_and_leaves_no_file"
        status: pass
    human_judgment: false

duration: 3min
completed: 2026-08-05
status: complete
---

# Phase 37 Plan 02: The Email Gate Summary

**`extraction.hold_emailless` names every held row by index and reason; `write_dispatch_csv` now raises `ExtractionError` on an emailless row before opening any file, closing the choke point that let nine Gold Coast Turf Club directors evaporate in HubSpot.**

## Performance

- **Duration:** ~3 min
- **Completed:** 2026-08-05T08:48:33Z
- **Tasks:** 2/2
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments

- `extraction.hold_emailless(rows)` partitions rows into `(sendable, held)`, reusing `_present()` — the same trimming predicate `has_identity` already uses — so the separator and the extraction identity rule can never disagree about what an empty email cell is. Each held entry names the row's original index, the row itself, and a reason in the operator's language.
- `write_dispatch_csv` gained a second pre-open guard, in the same loop as the existing non-canonical-key check: a row with no usable email now raises `ExtractionError` (code `emailless_row_cannot_ingest`) naming the row index and pointing the caller at `hold_emailless`, instead of writing the row with an empty email cell. Both guards complete before `out_path.open()`, so a refusal — even one caused by a row at the end of the list — leaves `out_path.exists()` `False`.
- The deliberate §10 flip: `test_extraction_handoff.py`'s round-trip case used to assert Ben's emailless row was written with an empty email cell — the exact live bug. It now asserts the refusal, with an inline comment recording that the assertion was inverted on purpose and why. A companion test (`test_write_dispatch_csv_header_matches_canonical_props_and_round_trips_for_email_bearing_rows`) keeps the header/round-trip coverage the flip replaced, filtered to the email-bearing row only.
- `has_identity` and `required_identity.any_of` are untouched — a firstname+lastname+company row is still a valid extraction row.

## Task Commits

1. **Task 1: hold_emailless — separate and name, never a bare count** - `8d0f94c` (feat)
2. **Task 2: write_dispatch_csv raises, before any file is opened** - `adddc8c` (feat)

## Files Created/Modified

- `operator-claude-plugin/scripts/extraction.py` - `hold_emailless(rows)` new function; `write_dispatch_csv` gains the emailless-row pre-open raise
- `operator-claude-plugin/tests/test_extraction_email_gate.py` - new test file: `hold_emailless` partition/naming/no-mutation cases, and `write_dispatch_csv`'s raise/no-file/late-row/extra-key cases
- `operator-claude-plugin/tests/test_extraction_handoff.py` - the §10 flip (refusal assertion, commented) plus its header/round-trip companion test

## Decisions Made

- Both `hold_emailless` and `write_dispatch_csv`'s new guard check presence through the same `_present()` helper — a single presence predicate for the whole email-gate surface, never a second emptiness rule that could drift.
- No force flag, override parameter, environment variable, or stub-record path was added. The only way to send a held row through `write_dispatch_csv` is to give it an email.

## Deviations from Plan

None - plan executed exactly as written.

## Red-Check Results (per task's explicit instruction)

**Task 1** — `hold_emailless`:
- Before implementing: renamed `def hold_emailless` to `def _hold_emailless_disabled` and ran `test_extraction_email_gate.py` — all 8 tests failed with `AttributeError: module 'extraction' has no attribute 'hold_emailless'`.
- After passing: swapped `_present(row.get("email"))` for the bare truthiness check `row.get("email")` — `test_hold_emailless_holds_whitespace_only_email` and `test_hold_emailless_every_row_appears_in_exactly_one_output_in_order` both failed (`"   "` was wrongly treated as present and routed to `sendable`), confirming the whitespace-only case specifically goes red. Reverted to `_present()`.

**Task 2** — `write_dispatch_csv`'s raise:
- Moved the email guard to run inside `out_path.open(...)`'s `with` block (after the file was created) instead of the pre-open loop: `test_write_dispatch_csv_raises_extraction_error_on_emailless_row` still passed (the raise still fires), but `test_write_dispatch_csv_leaves_no_file_after_an_emailless_refusal` failed — `AssertionError: assert True is False` on `out_path.exists()` — proving the two assertions test different things. Restored the guard to the pre-open loop.
- Removed the emailless-row guard entirely: `test_write_dispatch_csv_refuses_the_emailless_row_and_leaves_no_file` (the flipped round-trip case) failed with `Failed: DID NOT RAISE ExtractionError`. Restored the guard.

## Issues Encountered

While staging Task 1 for its own atomic commit, an in-flight `git checkout --` used during the second red-check reverted `extraction.py` to its pre-plan committed state (both the `hold_emailless` addition and the not-yet-committed Task 2 raise were wiped, since neither had been committed yet). `hold_emailless` was re-added from the same source, re-verified green, and both red-checks were re-run and passed as documented above before committing. No test was silenced or weakened as a result; the SUMMARY documents the actual, final red-check runs.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `extraction.hold_emailless` and `write_dispatch_csv`'s raise are the exact primitives 37-05's `preingest.render_enriched_preview` is specified to read from for its SEND/HELD verdict (37-02-PLAN.md `key_links`) — no further extraction-side work is needed before that plan starts.
- Suite counts after this plan: `operator-claude-plugin/tests/ -q` → 1085 passed, 5 skipped (baseline 1070/5); repo-root `.venv/bin/python -m pytest -q` → 2000 passed, 6 skipped (baseline 1985/6); `node --test tests/n8n/*.test.mjs` → 621 pass, unchanged; arming grep → 0 for every file; `operator-claude-plugin/scratch` clean.
- No blockers for 37-03 through 37-06.

---
*Phase: 37-enrich-before-ingest*
*Completed: 2026-08-05*

## Self-Check: PASSED

All 3 files created/modified by this plan verified present on disk; both commit hashes
(`8d0f94c`, `adddc8c`) verified present in `git log --oneline --all`.
