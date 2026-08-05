---
phase: 37-enrich-before-ingest
plan: 05
subsystem: enrichment-preview
tags: [preview, cli-argv, adaptive-sample, non-clobber-merge, tdd]

requires:
  - phase: 37-enrich-before-ingest
    plan: 04
    provides: "preingest.merge_enriched (MergeResult with rows/conflicts), preingest.apply_match_decisions"
provides:
  - "preview_enrichment.records_block's rows branch — states a rows spec is NOT in HubSpot yet, opposite of the ids/list branch's already-exists claim; cost/providers/chunks blocks unchanged"
  - "preview_enrichment.py's __main__ file-path argv form — reads a spec from a file when argv[1] names an existing path, so a 200+-row batch can reach the CLI"
  - "preingest.render_enriched_preview(rows, merge_report=None) — the pre-ingest, post-enrichment render: SEND/HELD verdict from extraction.hold_emailless, every held row named in full, sendable rows adaptively sampled, merge conflicts surfaced, states nothing has reached HubSpot yet"
affects: [37-06, enrich-before-ingest-skill]

actuals:
  tokens: 5630
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "records_block's rows/ids branches make deliberately opposite claims about the same field position, kept as separate branches with byte-identity tests pinning the untouched one"
    - "CLI argv file-path fallback: try Path(argv[1]).exists() first, fall through to JSON-literal parsing otherwise — guarded on existence, not shape"
    - "One-predicate verdict: render_enriched_preview calls extraction.hold_emailless (the same function write_dispatch_csv refuses on) rather than re-deriving SEND/HELD, proven by a monkeypatch test"
    - "Held rows are exempt from preview._adaptive_sample; only SEND rows are sampled — proven by a 25-held test that would collapse to 13 named rows under the regression"

key-files:
  created:
    - operator-claude-plugin/tests/test_preingest_preview.py
  modified:
    - operator-claude-plugin/scripts/preview_enrichment.py
    - operator-claude-plugin/scripts/preingest.py
    - operator-claude-plugin/tests/test_preview_enrichment.py

key-decisions:
  - "render_enriched_preview(rows, merge_report=None) takes the PRE-merge rows plus the MergeResult (not just the merged rows) so it can diff source-supplied values against enrichment-added ones per field. The SEND/HELD verdict runs over the MERGED rows (merge_report.rows when given), not the originals, since enrichment can fill a previously-blank email — running the gate predicate over the wrong row set would misclassify exactly the row this flow exists to rescue."
  - "Per-field enrichment source is reported as the constant \"the enrichment waterfall\" rather than a per-provider name. The merge response merge_enriched consumes carries one flat properties map per row with no per-provider attribution at this layer — naming an individual provider would be a guess this module has no evidence for, so the honest aggregate label is used instead (marked with a ponytail comment naming the ceiling)."
  - "The __main__ file-path branch is guarded on Path(argv[1]).exists() rather than on shape (e.g. \"ends with .json\"). A JSON literal that happens to also name a real path is not a case worth handling, and a mistyped path falls through to the literal parser, which names the actual bad text rather than a new file-not-found failure class."

requirements-completed: [PREVIEW-01, PREVIEW-02]

coverage:
  - id: D1
    description: "records_block gains a rows-spec branch stating the row count, that these rows are not in HubSpot yet, and that nothing is created there by enriching them — the opposite claim of the named-IDs branch's unchanged 'already exist in HubSpot' tail. cost_block/providers_block/chunks_block are untouched; the cost block prices identically for a same-size rows spec and record-id spec."
    requirement: PREVIEW-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preview_enrichment.py (37-05 Task 1 section, 7 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "preview_enrichment.py's __main__ reads its spec from a file when argv[1] names an existing path, falling back to JSON-literal parsing otherwise; a 200-row spec file reaches the CLI as a real subprocess against an isolated plugin root and renders the expected chunk count; a malformed spec file produces a structured error, never a traceback."
    requirement: PREVIEW-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preview_enrichment.py (37-05 Task 2 section, 4 subprocess tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "render_enriched_preview shows, per row, source-supplied values, what enrichment added, an honest source label, and a SEND/HELD verdict computed by extraction.hold_emailless — proven by a monkeypatch test. Every held row is named individually regardless of batch size (proven at 25 held rows, over the adaptive-sample threshold); sendable rows are adaptively sampled. Merge conflicts are surfaced. Both held-batch boundaries state themselves explicitly, and the result always states nothing has reached HubSpot yet."
    requirement: PREVIEW-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preingest_preview.py (13 tests)"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-08-05
status: complete
---

# Phase 37 Plan 05: The Two Previews This Flow Adds Summary

**A rows batch prices and previews as truthfully NOT-yet-in-HubSpot through the existing four blocks, a 200-row spec now reaches the CLI via a file-path argv form, and `render_enriched_preview` names every held person in full while computing its SEND/HELD verdict from the same predicate the ingest gate refuses on.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-08-05T10:08:31Z
- **Tasks:** 3/3
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- `preview_enrichment.records_block` gained a rows-spec branch, placed before the
  existing count-based branch and after the list branch: for a spec carrying `rows`,
  it states the row count, the object type, and plainly that these rows are **not**
  in HubSpot yet and that nothing is created there by enriching them — the
  deliberately opposite claim of the named-IDs branch's unchanged "already exist in
  HubSpot" tail. Both branches are pinned against literal strings so a rendering
  regression in the untouched branch cannot hide behind the new one.
  `cost_block`/`providers_block`/`chunks_block` are untouched — a doc comment in
  the module docstring's block-1 paragraph records why: `cost_guard.estimate_batch`
  already prices a bare integer count and never reads a record id, confirmed by a
  test asserting the cost block is byte-identical for a same-size rows spec and
  record-id spec.
- `preview_enrichment.py`'s `__main__` reads its spec from a file when `argv[1]`
  names an existing path, falling back to JSON-literal parsing otherwise (guarded
  on existence, not shape). The usage string names both forms, and `OSError`/
  `UnicodeDecodeError` join the existing caught-exception tuple so an unreadable
  file produces the same structured error object as every other failure, never a
  traceback. A new subprocess harness (`_run_preview_cli`) copies the whole
  `scripts/` tree into an isolated root with a literal env dict and fake `HOME`,
  proving a 200-row spec file reaches the CLI and renders the expected chunk count.
- `preingest.render_enriched_preview(rows, merge_report=None)` is the post-
  enrichment, pre-ingest render: per row it shows the source-supplied values, what
  enrichment added, an honest aggregate source label, and a SEND/HELD verdict
  computed by calling `extraction.hold_emailless` over the rows as they will
  actually be sent — never re-derived. Every held row is named individually
  regardless of batch size (the adaptive-sample rule applies only to the sendable
  rows, reusing `preview._adaptive_sample`). Merge conflicts from `merge_enriched`
  are surfaced. Both held-batch boundaries (nothing held, everything held) state
  themselves explicitly, and the result always carries the sentence that nothing
  has reached HubSpot yet.

## Task Commits

Each task was committed atomically:

1. **Task 1: records_block learns to describe rows that are not records yet** - `b7366c3` (feat)
2. **Task 2: the preview CLI accepts a spec file, because 200 rows do not fit in argv** - `8a804e2` (feat)
3. **Task 3: render_enriched_preview — the render the second arming answers** - `053f3ae` (feat)

_No separate plan-metadata commit — this SUMMARY and STATE.md updates are committed
together per `final_commit`._

## Files Created/Modified

- `operator-claude-plugin/scripts/preview_enrichment.py` — `records_block`'s rows
  branch; `__main__`'s file-path argv form; module docstring comment
- `operator-claude-plugin/scripts/preingest.py` — `render_enriched_preview`,
  `_held_statement`, `_NOTHING_REACHED_HUBSPOT`
- `operator-claude-plugin/tests/test_preview_enrichment.py` — 11 new tests across
  Task 1 (rows branch) and Task 2 (subprocess CLI)
- `operator-claude-plugin/tests/test_preingest_preview.py` — new file, 13 tests

## Decisions Made

- **`render_enriched_preview` takes the pre-merge `rows` plus the `MergeResult`**,
  not just the merged rows, so it can diff source-supplied values against
  enrichment-added ones per field. The SEND/HELD verdict itself runs over the
  MERGED rows (`merge_report.rows` when given) — enrichment can fill a previously
  blank email, and running the gate predicate over the wrong row set would
  misclassify exactly the row this flow exists to rescue.
- **Per-field enrichment source is reported as the constant "the enrichment
  waterfall"**, not a per-provider name. The merge response `merge_enriched`
  consumes carries one flat `properties` map per row with no per-provider
  attribution reaching this layer — naming an individual provider would be a guess
  this module has no evidence for; the aggregate label is the honest one
  (`ponytail:` comment names this ceiling in the code).
- **The `__main__` file-path branch is guarded on `Path(argv[1]).exists()`**, not
  on shape. A JSON literal that happens to also name a real path is not a case
  worth handling, and a mistyped path falls through to the literal parser, which
  names the actual bad text rather than inventing a new file-not-found failure
  class the operator has never seen from this CLI before.

## Deviations from Plan

None — plan executed exactly as written.

## Red-Check Failure Text (recorded per task's explicit instruction)

**Task 1 — records_block's rows branch:**
Deleting the rows branch made the two new claim-content tests fall through to the
ids branch's wording:
```
AssertionError: assert 'not' in '**Records:** 3 contacts, named by ID. Nothing is
structured or uploaded — these already exist in HubSpot.'
AssertionError: assert 'already exist' not in '**Records:*... in HubSpot.'
```
This is the actual harm the branch prevents: the operator would be shown the
opposite of what is true about the batch in front of them.

**Task 2 — the file-path `__main__` branch:**
Reverting the file-read branch (falling back to `json.loads(sys.argv[1])`
unconditionally) made the 200-row spec-file subprocess test fail:
```
AssertionError: {"ok": false, "error": "Expecting value: line 1 column 1 (char 0)"}
assert 1 == 0
```
On this platform the failure is a JSON parse error over the file path string
itself, not an argument-list-too-long error — but the point is the same one the
plan named: today the call is simply not makeable.

**Task 3 — `render_enriched_preview`:**
1. Re-deriving the SEND/HELD verdict inline (`if row.get("email")` instead of
   calling `extraction.hold_emailless`) made the monkeypatch test fail:
   ```
   assert result["send_count"] == 0
   AssertionError: assert 2 == 0
   ```
   The stub told the function to hold everything; the inline predicate ignored it
   and sent both rows anyway — exactly the "second predicate disagrees with the
   gate" failure T-37-20 exists to prevent.
2. Applying `preview._adaptive_sample` to the held rows (verified against a
   25-row all-held batch via a scratch script before restoring, since the
   committed 12-held acceptance-criteria test sits under the adaptive threshold
   and would not itself trip): named held rows collapsed from 25 to 13
   (10 leading + 3 trailing) — a silent drop of 12 held people from the
   operator's view. The committed suite pins this specific regression class with
   `test_a_held_batch_larger_than_the_adaptive_threshold_still_names_every_row`
   (25 held rows, all 25 asserted present), added beyond the plan's literal
   12-held scenario because that scenario alone sits under
   `preview.ADAPTIVE_THRESHOLD` (20) and would not detect this regression if it
   were ever reintroduced.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `preview_enrichment.records_block`'s rows branch, the `__main__` file-path form,
  and `preingest.render_enriched_preview` are the exact primitives the
  `enrich-before-ingest` skill's turn sequence (37-CONTEXT §5, steps 4 and 6) is
  specified to call — no further preview work is needed before that skill is
  wired.
- Suite counts after this plan: `operator-claude-plugin/tests/ -q` → 1207 passed,
  5 skipped (baseline post-37-06: 1183/5); repo-root `.venv/bin/python -m pytest -q`
  → 2122 passed, 6 skipped (baseline 2098/6); `node --test tests/n8n/*.test.mjs` →
  621 pass, unchanged; arming grep → 0 for every `n8n/*.json` file;
  `operator-claude-plugin/scratch` clean.
- No blockers.

---
*Phase: 37-enrich-before-ingest*
*Completed: 2026-08-05*

## Self-Check: PASSED

All 5 files created/modified by this plan verified present on disk; all 3 commit
hashes (`b7366c3`, `8a804e2`, `053f3ae`) verified present in `git log --oneline --all`.
