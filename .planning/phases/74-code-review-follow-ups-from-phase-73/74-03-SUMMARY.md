---
phase: 74-code-review-follow-ups-from-phase-73
plan: 03
subsystem: offline-tooling
tags: [operator-plugin, python, csv, preview, review-decision, tdd]

# Dependency graph
requires:
  - phase: 74-02
    provides: "unrelated surface (write_grant/report_enrichment/chunking) -- no code dependency, but this plan's commits landed on top of 74-02's HEAD"
provides:
  - "csv_dedupe._canonical_rows's index-walk row canonicalisation (WR-11) -- a row shorter than the header keeps every header column, keyed to an empty string, instead of losing trailing columns to a zip that stops at the shorter sequence"
  - "csv_dedupe.apply_dedupe's full-resolved-path output location (WR-12) -- deduped CSV and report land beside the input by default, so two sources sharing a bare stem in different directories never overwrite each other"
  - "csv_dedupe.py's CLI resolves column_mapping_path through the SAME config_gate.load_config() reader preview.py's own __main__ already calls (WR-03) -- never a second, drifting resolver for the same config key"
  - "preview.read_collapsed_block/CollapsedBlockError (WR-04) -- an explicitly-requested --collapsed sidecar that cannot be read (missing, unreadable, malformed JSON) raises naming the path, instead of silently rendering a reconciliation count that reads like 'no duplicates'"
  - "review_decision.verify_decision's leg-1 presence-before-value comparison (WR-09) -- a key present on one side of the backend's own would_write/intended comparison and absent from the other is always a mismatch, even when both normalise to the same empty string; the failure message names which case fired (absence vs. differing value)"
affects: [74-06-PLAN.md]

# Actuals (#2632)
actuals:
  tokens: 6999   # chars/4 over the diff (27994 chars / 4) across the six files this plan touched
  tasks: 3
  commits: 6
  plan_head_before: d3efb9613204dd6db4a359acd942aae20a671ea7

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Index-walk over the canonical/target sequence, never zip() against a raw, possibly-ragged source sequence -- zip silently truncates to the shorter of the two, which for a CSV row shorter than its header drops trailing columns instead of keying them to an explicit empty value"
    - "A derived output path built from the input's OWN full resolved path (not its bare stem alone) as the collision-safety mechanism -- two same-stem sources in different directories never collide because each writes beside itself by default"
    - "One canonical config-gate reader, never a second resolver for the same config key -- csv_dedupe.py's CLI now mirrors preview.py's exact config_gate.load_config().get(key) call rather than inventing its own"
    - "Presence tested BEFORE value equality in a comparator that treats None and '' as the same rendered text -- a text-normalising comparator (_as_hubspot_text) is only safe once both sides are confirmed present; applying it across a presence gap hides a key one side silently dropped"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/csv_dedupe.py
    - operator-claude-plugin/scripts/preview.py
    - operator-claude-plugin/scripts/review_decision.py
    - operator-claude-plugin/tests/test_csv_dedupe.py
    - operator-claude-plugin/tests/test_preview_rendering.py
    - operator-claude-plugin/tests/test_review_decision.py

key-decisions:
  - "WR-12's fix diverges from 73-REVIEW.md's own suggested code (a sha256-hash-tagged filename staying inside the fixed plugin-relative scratch dir) in favour of the PLAN's own <action>/<acceptance_criteria> wording, which is more specific and literal: apply_dedupe's default scratch_dir is now the input's own resolved parent directory (path.resolve().parent), so both outputs land beside the input. The explicit scratch_dir override is completely unchanged -- all 7 pre-existing tests that pass scratch_dir=tmp_path/\"scratch\" continue to pass byte-for-byte. The now-unused module-level SCRATCH_DIR constant is removed."
  - "WR-04's 'a collapsed-block file that is simply absent still yields the absent-block path, unchanged' behaviour bullet is read as 'the --collapsed flag was never passed at all', not 'the flag was passed but the file at that path does not exist on disk'. This resolves an ambiguity the plan's own wording leaves open, in favour of 73-REVIEW.md's exact fix snippet (which raises for ANY read failure -- including a missing file -- once --collapsed was explicitly given), per D-74-10's binding directive to use 'the fixes 73-REVIEW.md supplies'. In the real contact-upload flow (SKILL.md step 3), --collapsed is always passed once step 2c's dedupe ran, so a missing file at that point is a genuine failure worth surfacing loudly, not a silent degrade."
  - "review_decision.py's leg-1 mismatch reason is threaded into both the operator-facing message text AND is available per-key internally, but result['mismatched'] itself stays a flat, sorted list of key names -- every pre-existing assertion on that field (list equality, 'in' membership) is unaffected by the fix."
  - "Protected-branch commit check: gsd_run query git.base-branch --is-protected master returns true for this repo, but the executor was explicitly dispatched to commit directly to master (workflow.use_worktrees=false, no worktree isolation, sequential single-executor run) -- consistent with 74-01 and 74-02 landing linearly on the same branch immediately before this plan. Proceeded per the orchestrator's explicit sequential_execution instruction rather than halting on the generic drift-detection default, which exists to catch an agent accidentally landing on master from a worktree, not a repo that deliberately has none."
  - "Task 1's own RED capture (running the new tests against the UNMODIFIED module) wrote two real files into the plugin's actual operator-claude-plugin/scratch/ directory, because the old code's untouched default (scratch_dir=SCRATCH_DIR, a fixed plugin-relative path) was still live at that point -- an accidental side effect of proving RED, not intended output. Both files (deduped-contacts.csv, dedupe-report-contacts.json; gitignored, never staged) were deleted before the final full-suite run; test_header_suggest.py's own real-scratch-directory guard test caught the leftover and re-passed once cleaned up."

patterns-established:
  - "When a plan's own <action>/<acceptance_criteria> gives a more specific, testable shape than the code-review finding's suggested snippet, follow the plan literally and record the divergence as a key decision -- the plan is the authoritative instruction for THIS execution, the review is context for why the finding exists."

requirements-completed: [WR-03, WR-04, WR-09, WR-11, WR-12]

coverage:
  - id: D1
    description: "WR-11: csv_dedupe._canonical_rows walks canonical_headers by index instead of zip()-pairing against the raw row -- a row shorter than the header keeps every header column, keyed to an empty string for each missing trailing value; a row longer than the header is handled without raising, with overflow simply never read"
    requirement: WR-11
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_csv_dedupe.py#test_canonical_rows_pads_a_row_shorter_than_the_header_with_empty_trailing_columns"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_csv_dedupe.py#test_canonical_rows_ignores_overflow_fields_beyond_the_header_without_raising"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_csv_dedupe.py#test_a_short_row_still_clusters_and_survives_dedupe_end_to_end"
        status: pass
    human_judgment: false
  - id: D2
    description: "WR-12: apply_dedupe's default output/report paths derive from the input's own resolved parent directory rather than a fixed plugin-relative scratch dir keyed on the bare stem -- both files land beside the input by default, and two different-directory sources sharing a stem never collide"
    requirement: WR-12
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_csv_dedupe.py#test_apply_dedupe_writes_beside_the_input_by_default"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_csv_dedupe.py#test_apply_dedupe_default_output_does_not_collide_across_directories_sharing_a_stem"
        status: pass
    human_judgment: false
  - id: D3
    description: "WR-03: csv_dedupe.py's __main__ resolves column_mapping_path through _resolve_configured_mapping_path() -- the same config_gate.load_config().get(\"column_mapping_path\") call preview.py's own __main__ makes -- and passes it into both the --propose and --apply calls"
    requirement: WR-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_csv_dedupe.py#test_cli_resolves_the_configured_column_mapping_same_as_preview"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_csv_dedupe.py#test_cli_with_no_mapping_configured_behaves_exactly_as_today"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_csv_dedupe.py#test_cli_with_config_unavailable_degrades_to_none_not_a_crash"
        status: pass
    human_judgment: false
  - id: D4
    description: "WR-04: preview.read_collapsed_block raises CollapsedBlockError naming the offending path when --collapsed was explicitly requested and could not be read (missing, unreadable, or malformed JSON); returns the silent absent-block None only when no path was requested at all"
    requirement: WR-04
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preview_rendering.py#test_read_collapsed_block_returns_none_when_no_path_was_requested"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preview_rendering.py#test_read_collapsed_block_raises_naming_the_path_for_a_missing_file"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preview_rendering.py#test_read_collapsed_block_raises_naming_the_path_on_invalid_json"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_preview_rendering.py#test_read_collapsed_block_returns_the_parsed_list_for_a_valid_file"
        status: pass
    human_judgment: false
  - id: D5
    description: "WR-09: verify_decision's leg 1 tests key presence before value equality -- a key present on one side and absent from the other is always a mismatch, and the failure message names whether the reason was absence or a differing value; both-present-and-equal and absent-from-both stay unreported, exactly as before"
    requirement: WR-09
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_review_decision.py#test_leg1_flags_a_key_absent_from_the_backends_patch_even_when_both_sides_normalise_empty"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_review_decision.py#test_leg1_does_not_flag_a_key_present_in_both_with_equal_normalised_values"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_review_decision.py#test_leg1_still_flags_a_key_present_in_both_with_a_genuinely_different_value"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_review_decision.py#test_leg1_never_reports_a_key_absent_from_both_sides"
        status: pass
    human_judgment: false

duration: 19min
completed: 2026-09-19
status: complete
---

# Phase 74 Plan 03: csv_dedupe/preview/review_decision code-review follow-ups Summary

**Fixed five silent-wrong-answer operator-plugin bugs across three files: a CSV row shorter than its header lost trailing identity columns to a zip-truncation instead of keying them to empty strings, two different-directory sources sharing a file stem overwrote each other's deduped output, the dedupe CLI ignored the operator's configured column-mapping path while the preview CLI honoured it, a malformed --collapsed sidecar silently rendered as "no duplicates", and a review-decision comparison let an approved-but-dropped patch key read as agreement because both sides normalised to the same empty string.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-09-19T08:12:00Z (base commit `d3efb961`)
- **Completed:** 2026-09-19T08:31:26Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- **WR-11 (`csv_dedupe.py`):** `_canonical_rows` walks `canonical_headers` by index instead of `zip()`-pairing against the raw row. A row shorter than the header (an exporter that omits trailing empty cells) keeps every header column, with each missing trailing value keyed to an empty string. A row longer than the header is handled by the same walk without raising — anything past the header's own length is simply never read, never folded into the last column.
- **WR-12 (`csv_dedupe.py`):** `apply_dedupe`'s default output location changed from a fixed plugin-relative `scratch/` directory keyed on the input's bare stem to the input's own resolved parent directory (`path.resolve().parent`). Both the deduped CSV and its report now land beside the input by default, so a same-stem source living in a different directory is never overwritten. The `scratch_dir` parameter, when given explicitly, is completely unchanged. The now-unused module-level `SCRATCH_DIR` constant is removed.
- **WR-03 (`csv_dedupe.py`):** the CLI's `__main__` now resolves `column_mapping_path` through a new `_resolve_configured_mapping_path()` — the SAME `config_gate.load_config().get("column_mapping_path")` call `preview.py`'s own `__main__` makes — and passes it into both the `--propose` and `--apply` calls. Degrades to `None` exactly as an unconfigured mapping does today when the config file is missing or unreadable.
- **WR-04 (`preview.py`):** new `read_collapsed_block(path)` + `CollapsedBlockError`. Returns `None` (the silent absent-block path) only when `--collapsed` was never passed at all. A path that WAS requested but cannot be read — missing, unreadable, malformed JSON — now raises `CollapsedBlockError` naming the offending path, matching `73-REVIEW.md`'s own fix rather than a narrower "missing file stays silent" reading. `__main__` wires this into the same `{"ok": false, "error": ...}` / exit-1 shape every other failure in this CLI already uses.
- **WR-09 (`review_decision.py`):** `verify_decision`'s leg 1 (intent stability, G-60-1) now tests key presence in `would_write` vs. `intended` BEFORE calling `_as_hubspot_text` — a key present on one side and absent from the other is always a mismatch, even when both would render as the same empty string. `_as_hubspot_text`'s own docstring is corrected to state its "None/blank compares equal" consequence is scoped to leg 2 (the refetch) only, never leg 1. The per-key reason ("absent from the backend's submitted patch" / "absent from the approved patch" / "value differs from the approved patch") is threaded into the failure message; `result["mismatched"]` itself stays a flat sorted list of key names, so every pre-existing assertion on that field is unaffected.

## Task Commits

1. **Task 1: A short CSV row survives dedupe end to end (WR-11, WR-12)** — RED `fc6bdfab` (test), GREEN `98be4386` (feat)
2. **Task 2: One canonical column-mapping reader; a parse failure is an error (WR-03, WR-04)** — RED `9b3d3295` (test), GREEN `04d96443` (feat)
3. **Task 3: Absence is not a value in the review-intent comparison (WR-09)** — RED `17e3b0bf` (test), GREEN `4528b587` (feat)

**Plan metadata:** committed alongside this SUMMARY.

_Note: Task 1 carried `type="tracer" tdd="true"` — the tracer feedback gate re-ran Task 1's own `<verify>` (pytest against `test_csv_dedupe.py`) after its GREEN commit; it passed (23/23), logged `⚡ Tracer verified end-to-end — expanding`, and Task 2 began with no checkpoint (auto mode active, `HUMAN_VERIFY_MODE` not consulted per the precedence chain's row 2)._

## Files Created/Modified

- `operator-claude-plugin/scripts/csv_dedupe.py` — WR-11/WR-12/WR-03: index-walk canonicalisation, full-resolved-path output default, one canonical config-gate reader in `__main__`
- `operator-claude-plugin/scripts/preview.py` — WR-04: `CollapsedBlockError` + `read_collapsed_block`, wired into `__main__`
- `operator-claude-plugin/scripts/review_decision.py` — WR-09: leg-1 presence-before-value comparison, per-key reason, corrected `_as_hubspot_text` docstring scope
- `operator-claude-plugin/tests/test_csv_dedupe.py` — 8 new cases: 2 padding/overflow, 1 end-to-end survival, 2 default-output-location, 3 CLI config-gate resolution
- `operator-claude-plugin/tests/test_preview_rendering.py` — 4 new cases pinning `read_collapsed_block`'s four behaviours
- `operator-claude-plugin/tests/test_review_decision.py` — 4 new cases pinning leg 1's presence-vs-value distinction

## Decisions Made

See `key-decisions` in frontmatter. In short: WR-12 follows the plan's own literal wording (write beside the input) rather than the review's hash-tag variant; WR-04's "simply absent" reading resolves to "flag never passed", matching the review's exact fix snippet per D-74-10's binding directive; the protected-branch commit assertion was consciously overridden per the orchestrator's explicit sequential-master instruction, consistent with 74-01/74-02's precedent on this exact branch; and two files accidentally written into the real plugin `scratch/` directory during Task 1's RED capture (before the WR-12 fix landed) were deleted before the final suite run.

## Deviations from Plan

### Auto-fixed Issues

None — no Rule 1/2/3 auto-fixes were needed beyond the two interpretive decisions recorded above (WR-12's output-location mechanism, WR-04's "absent" reading), both of which stayed within the plan's own stated behavior/acceptance criteria and were resolved via advisor consultation rather than guessed.

---

**Total deviations:** 0 auto-fixed.
**Impact on plan:** None — every change is within the plan's declared scope and files. The two interpretive decisions above are documented rather than silently assumed.

## TDD Gate Compliance

All three `tdd="true"` tasks (Task 1 tracer, Task 2, Task 3) landed a separate `test(74-03):` RED commit before each `feat(74-03):` GREEN commit — full RED-GREEN discipline, one pair per task, six commits total.

- **`gsd_run check tdd-red-evidence` was not run.** This tool parses TAP output only (`node --test`'s `# tests N` / `not ok N - <name>` lines); this plan's tests run under pytest's default reporter — the same disclosed limitation `68-01`, `69-01/02/03`, `70-05/06`, `72-03`, and `74-02`'s own SUMMARYs already recorded for this install.
- **RED was observed directly from pytest's own failure output** for each task's target tests, before any implementation edit:
  - Task 1: `test_canonical_rows_pads_a_row_shorter_than_the_header_with_empty_trailing_columns` — `KeyError: 'linkedin_url'` (the trailing column was dropped entirely, not empty). `test_apply_dedupe_writes_beside_the_input_by_default` — `AssertionError` comparing the fixed plugin `scratch/` dir against the expected input-adjacent directory. `test_apply_dedupe_default_output_does_not_collide_across_directories_sharing_a_stem` — `AssertionError` on two different sources' deduped content comparing equal (both landed in the same shared scratch file).
  - Task 2: `test_cli_resolves_the_configured_column_mapping_same_as_preview`, `test_cli_with_no_mapping_configured_behaves_exactly_as_today`, `test_cli_with_config_unavailable_degrades_to_none_not_a_crash` — all `AttributeError: module 'csv_dedupe' has no attribute '_resolve_configured_mapping_path'`. `test_preview_rendering.py` failed to COLLECT at all: `ImportError: cannot import name 'CollapsedBlockError' from 'preview'`.
  - Task 3: `test_leg1_flags_a_key_absent_from_the_backends_patch_even_when_both_sides_normalise_empty` — `AssertionError: assert 'verified' == 'failed'` (the exact WR-09 bug: an approved blank clear silently agreed with a key the backend never sent). `test_leg1_still_flags_a_key_present_in_both_with_a_genuinely_different_value` — `AssertionError` on the new per-key reason text (`"differs"` not yet present in the old message format).
- **Which new tests were genuine RED reproductions vs. regression pins** (green both before and after, pinning behavior the plan states must stay unchanged, not a bug fix):
  - Genuine RED: Task 1's padding case + both default-output-location cases (3 of 5); Task 2's all three config-gate-resolution cases + `test_preview_rendering.py`'s collection failure (blocking all 4 of its new cases from an isolated pre-fix run, though only the `read_collapsed_block`-calling ones were the actual target); Task 3's absence-mismatch case and the per-key-reason-text case (2 of 4).
  - Regression pins (never RED, by design): Task 1's overflow-handling case and short-row-survival-through-identity-matching case (the existing zip-based code already handled both correctly for the specific scenarios chosen — see `74-RESEARCH.md`'s own analysis that `_present()` treats a missing key and an empty-string key identically for `_first_satisfied_key`'s group-satisfaction check, so WR-11's bug is a structural/defensive correctness fix rather than one that changes today's clustering outcome). Task 3's equal-normalised-values case and absent-from-both case.

## Issues Encountered

**Real-scratch-directory contamination during RED capture (self-resolved).** Task 1's first RED test run executed against the UNMODIFIED `csv_dedupe.py`, whose old default (`scratch_dir=SCRATCH_DIR`, a fixed path under `operator-claude-plugin/scratch/`) was still live. The new `test_apply_dedupe_writes_beside_the_input_by_default` test (which deliberately omits `scratch_dir` to exercise the default) therefore wrote `deduped-contacts.csv` and `dedupe-report-contacts.json` into the real, gitignored plugin scratch directory as a side effect of proving RED — not intended output, never staged or committed. Found and cleaned up (`rm`) before the final full-suite run; `test_header_suggest.py::test_git_status_short_shows_no_writes_to_the_real_plugin_scratch_directory` (an existing repo-wide guard, unrelated to this plan's files) caught the leftover on the first full-suite pass and re-passed once removed.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `WR-03`, `WR-04`, `WR-09`, `WR-11`, `WR-12` marked complete (not shared with any sibling plan in this phase). `D-74-10` is shared with 74-02 (already landed), 74-04, and 74-05 — reported `blocked` by `requirements.ready-ids`, per the #2388 shared-ID gate; no action needed here, it will mark complete once every declaring plan finishes.
- `.planning/REQUIREMENTS.md` carries no entries for this phase's `WR-*`/`D-74-*` ids — `requirements.mark-complete` returned `not_found` for all five ready ids and wrote nothing, exactly as `74-02-SUMMARY.md` already recorded for the same phase: this phase is keyed entirely on `73-REVIEW.md` findings and `74-CONTEXT.md` decisions.
- Full suites green at close: `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider` → 5164 passed / 160 skipped (baseline at dispatch: 5148/160; +16 new tests). `node --test tests/n8n/*.test.mjs` → 1305 pass / 0 fail (unchanged — this plan touches no `n8n/` graph). `git diff --quiet -- n8n/` since base `d3efb961` is clean.
- Ready for 74-04 (next plan in this phase's wave 1, per `.planning/phases/74-code-review-follow-ups-from-phase-73/74-04-PLAN.md`).

## Self-Check: PASSED

- `[ -f operator-claude-plugin/scripts/csv_dedupe.py ]` → FOUND
- `[ -f operator-claude-plugin/scripts/preview.py ]` → FOUND
- `[ -f operator-claude-plugin/scripts/review_decision.py ]` → FOUND
- `git log --oneline --all | grep -q fc6bdfab` → FOUND
- `git log --oneline --all | grep -q 98be4386` → FOUND
- `git log --oneline --all | grep -q 9b3d3295` → FOUND
- `git log --oneline --all | grep -q 04d96443` → FOUND
- `git log --oneline --all | grep -q 17e3b0bf` → FOUND
- `git log --oneline --all | grep -q 4528b587` → FOUND
- `git rev-list --count d3efb961..HEAD` → 6 (matches `actuals.commits`)
- `git diff --quiet -- n8n/` → clean (no n8n graph touched)

---
*Phase: 74-code-review-follow-ups-from-phase-73*
*Completed: 2026-09-19*
