---
phase: 37-enrich-before-ingest
plan: 06
subsystem: preingest
tags: [durable-state, idempotent-resume, atomic-write, ast-guard, tdd]

requires:
  - phase: 37-enrich-before-ingest
    plan: 03
    provides: "preingest.build_rows_spec (stable row_id minting), preingest.match_batch/classify_matches (MatchOutcome, four-tier classification)"
  - phase: 37-enrich-before-ingest
    plan: 04
    provides: "preingest.apply_match_decisions, merge_enriched — the decisions/merge lane a manifest verdict is ultimately derived from"
provides:
  - "run_manifest.save(run_id, verdicts, path=None) / load(path=None) — a row_id -> verdict artifact beside the dashboard pointer, its own schema, its own refusal, never inside artifact_store.py"
  - "run_manifest.rows_to_resume(rows, manifest) — pure resume decision: skip matched/enriched, re-request unchecked, re-include held only once emailed"
  - "run_manifest.ManifestError / ALLOWED_VERDICTS (matched/enriched/held/unchecked) — the four-word verdict vocabulary 37-05/37-CONTEXT §13a can build on"
affects: [37-05]

actuals:
  tokens: 7725
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Second persisted artifact beside artifact_store.py's dashboard pointer, sharing durable_paths.resolve_state_path()'s directory but never its schema — a separate file with its own field refusal rather than a widening of an existing store"
    - "Same-package private-helper reuse: durable_paths._atomic_write_0600 called directly rather than reimplemented, documented as a deliberate choice in the module docstring"
    - "Whole-manifest-degrades-on-any-anomaly load(): one bad verdict entry returns {} for the entire file, never a partially-trusted map — mirrors artifact_store.py's every-failure-returns-nothing rule at a stricter (whole-document) granularity"
    - "Payload-plus-report dataclass return (ResumeResult: rows/skipped/still_held), mirroring MatchOutcome/MergeResult from 37-03/37-04"

key-files:
  created:
    - operator-claude-plugin/scripts/run_manifest.py
    - operator-claude-plugin/tests/test_run_manifest.py
  modified: []

key-decisions:
  - "Writes go through durable_paths._atomic_write_0600 directly (a same-package use of that module's private helper) rather than a second atomic-write implementation. It already carries the exact guarantee needed (temp file in the target's own directory, chmod 0600, fsync, os.replace) and duplicating it would be a second copy of the one pattern durable_paths.py already centralizes."
  - "load() degrades the WHOLE manifest to {} on any single bad entry (a verdict outside the four words, a non-string row_id), never a partially-trusted map that silently drops just the bad row. Degrading to a full run costs money; degrading to a partial skip costs a contact — only one of those is recoverable."
  - "The forbidden-name refusal checks BOTH the verdict-map key and value against a substring list (arm, secret, api_key, apikey, token, credential, password, grant, permission, webhook), not just the value. The four-word verdict check alone catches a value like \"armed\" (it simply isn't an allowed word), but a KEY named e.g. \"webhook_secret\" or \"armed_batch\" needs its own check — proven by the Task 1(a) red-check, which showed the four-word check alone lets an arming-shaped KEY through."
  - "run_manifest never imports, and is never imported by, anything in sweep_entry's transitive closure. Verified by running test_sweep_read_only.py unchanged (still green) and by a new local test (test_run_manifest_is_absent_from_the_sweeps_import_closure) that calls that file's own transitive_closure() directly. No widening of ALLOWED_MODULES was needed or made."
  - "Only genuinely terminal outcomes get a manifest verdict: a high-tier auto-match becomes 'matched'; an unchecked chunk becomes 'unchecked'. An unmatched (no-hit) or proposed (medium-tier, awaiting operator decision) row is left OUT of the manifest entirely — it is neither done nor blocked, so it has no verdict yet and is naturally re-requested on resume via the 'absent from manifest' branch, no special-casing needed."

requirements-completed: [STRUCT-02, PREVIEW-02]

coverage:
  - id: D1
    description: "run_manifest.py persists a row_id -> verdict map as its own artifact beside the dashboard pointer under durable_paths.resolve_state_path()'s directory, at 0600, via durable_paths._atomic_write_0600. artifact_store.py is untouched (git diff --stat confirms). A verdict outside the four allowed words, or a verdict-map key/value naming an arming grant, live-write permission, secret, or API key raises ManifestError naming the offending key, and nothing is written."
    requirement: STRUCT-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_manifest.py (Task 1 section, 18 tests)"
        status: pass
    human_judgment: false
  - id: D2
    description: "load() degrades every failure mode (missing, malformed JSON, wrong schema, a truncated/half-written file, a single invalid verdict entry) to the same empty {} result rather than raising, and never returns a partially-trusted map."
    requirement: STRUCT-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_manifest.py (Task 1c section, 6 tests)"
        status: pass
    human_judgment: false
  - id: D3
    description: "rows_to_resume(rows, manifest) is pure and returns the subset of rows still needing work in original order, plus a skipped/still_held report: matched/enriched excluded, unchecked always re-requested, held re-included only once the row carries an email (else reported still_held), absent-from-manifest or empty/absent manifest means every row is included."
    requirement: PREVIEW-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_manifest.py (Task 2 section, 11 tests)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The no-re-spend property is proven against a real match_batch/fetch_matches pass through a stub transport: the SET of row_ids in a resumed pass's recorded request bodies is exactly the still-open rows and none of the already-matched ones. A truncated manifest re-requests every row. The unattended sweep's import closure stays free of run_manifest, verified by the existing and a new local test."
    requirement: PREVIEW-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_manifest.py (Task 3 section, 3 tests)"
        status: pass
    human_judgment: false

duration: ~35min
completed: 2026-08-05
status: complete
---

# Phase 37 Plan 06: run_manifest.py — Resumable Batches, Never a Second Store Summary

**A row_id -> verdict manifest that survives a crash at 0600 beside the dashboard pointer, refuses to ever hold an arming grant, and lets a resume ask about only the rows a recording transport shows were never actually finished — proven by the set of ids, not a call count.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-08-05
- **Tasks:** 3/3
- **Files modified:** 2 (both created)

## Accomplishments

- `run_manifest.save(run_id, verdicts, path=None)` / `load(path=None)` persist a
  `row_id -> verdict` map as the plugin's SECOND persisted artifact, sharing
  `durable_paths.resolve_state_path()`'s directory with the dashboard pointer but never
  its filename or schema. Every entry is validated BEFORE anything is written: a verdict
  outside the four allowed words (`matched`, `enriched`, `held`, `unchecked`), or a
  verdict-map key or value whose name suggests an arming grant, a live-write permission, a
  secret, or an API key, raises `ManifestError` naming the offending key and writes
  nothing. Writes go through `durable_paths._atomic_write_0600` directly (documented in
  the module docstring as a deliberate same-package reuse, not a second atomic-write
  implementation) — 0600, temp-file-in-target-dir, fsync, `os.replace`.
- `load()` degrades every failure mode to the same empty `{}` — missing file, malformed
  JSON, wrong top-level shape, a missing `verdicts` field, a single bad verdict entry
  buried in an otherwise-valid map, or a truncated/half-written file. A manifest carrying
  even ONE bad entry degrades the WHOLE map, never a partially-trusted subset — proven by
  a dedicated test that plants one good and one bad verdict in the same file.
- `run_manifest.rows_to_resume(rows, manifest)` is pure (no file read; takes an
  already-loaded manifest) and implements the four-way resume rule from 37-CONTEXT §13a:
  `matched`/`enriched` rows are excluded; `unchecked` rows are always re-requested
  ("we could not look" is a reason to look again, never an answer about the row); `held`
  rows are excluded unless the row now carries an email, in which case they're
  re-included, and stay reported in `still_held` otherwise; a row absent from the
  manifest, or an empty/absent manifest entirely, is included. Returns a `ResumeResult`
  dataclass (`rows`/`skipped`/`still_held`), mirroring `MatchOutcome`/`MergeResult`'s
  payload-plus-report shape from 37-03/37-04. Order is preserved.
- The no-re-spend property is proven end-to-end, not just at the `rows_to_resume` unit
  level: a real `match_batch`/`fetch_matches` pass runs against a scripted stub, verdicts
  are derived from the response (only the two high-tier auto-matches become `matched`;
  the no-hit and medium-tier rows are left out of the manifest entirely, since they're
  still-open decisions, not terminal outcomes), the manifest is saved and reloaded, and a
  SECOND `match_batch` pass through a fresh stub is asserted to carry exactly the
  still-open row ids in its request bodies — asserted as a **set**, never a bare call
  count, since a count could coincide while the wrong rows were sent. A resume against a
  deliberately truncated manifest re-requests every row (degrading to a full run, never a
  partial skip). `run_manifest` is confirmed absent from `sweep_entry`'s transitive import
  closure both by the existing `test_sweep_read_only.py` (unchanged, still green) and by
  a new local test calling that file's own `transitive_closure()` directly — no widening
  of the sweep's read-only allowlist was needed or made.

## Task Commits

1. **Task 1: the manifest file — its own artifact, its own refusal** - `27eb375` (feat)
2. **Task 2: resume — skip what completed, re-request what did not** - `98d4a9b` (feat)
3. **Task 3: prove the resume does not re-spend, and that the sweep still cannot write** - `48a55d8` (test)

_No separate plan-metadata commit — this SUMMARY and STATE.md updates are committed
together per `final_commit`._

## Files Created/Modified

- `operator-claude-plugin/scripts/run_manifest.py` — new module: `manifest_path`, `save`,
  `load`, `rows_to_resume`, `ManifestError`, `ResumeResult`, `ALLOWED_VERDICTS`
  (`matched`/`enriched`/`held`/`unchecked`)
- `operator-claude-plugin/tests/test_run_manifest.py` — new test file, 32 tests across all
  three tasks

## Decisions Made

- **Writes reuse `durable_paths._atomic_write_0600` directly** rather than a second
  atomic-write implementation — a same-package use of that module's private helper,
  documented as a deliberate choice (not an oversight) in the module docstring, since it
  already carries the exact guarantee this file needs.
- **`load()` degrades the WHOLE manifest to `{}` on any single bad entry**, never a
  partially-trusted map that silently drops just the bad row — degrading to a full run
  costs money, degrading to a partial skip costs a contact, and only one of those is
  recoverable.
- **The forbidden-name check inspects both the verdict-map KEY and its VALUE** — the
  four-word verdict check alone already blocks a value like `"armed"` (it just isn't one
  of the four allowed words), but a KEY named `"webhook_secret"` or `"armed_batch"` needs
  its own guard. Confirmed via the Task 1(a) red-check: removing the forbidden-name check
  left the value-shaped test passing (caught incidentally by the four-word check) while
  the two key-shaped tests failed with `DID NOT RAISE`.
- **Only genuinely terminal outcomes get a manifest verdict.** A high-tier auto-match
  becomes `"matched"`; a failed chunk becomes `"unchecked"`. A no-hit (`unmatched`) or
  medium-tier (`proposed`, awaiting an operator decision) row is left OUT of the manifest
  entirely — it has no verdict yet, so it is naturally re-requested by `rows_to_resume`'s
  "absent from manifest" branch with no special-casing required.

## Deviations from Plan

None — plan executed exactly as written.

## Red-Check Failure Text (recorded per task's explicit instruction)

**Task 1:**
- (a) Removing the forbidden-name validation (`_looks_forbidden` calls) from `save()`:
  `test_save_refuses_an_arming_shaped_key_naming_the_offending_key`,
  `test_save_refuses_a_secret_shaped_key`, and `test_save_refuses_an_api_key_shaped_key`
  all failed with `Failed: DID NOT RAISE ManifestError`.
  `test_save_refuses_an_arming_shaped_verdict_and_writes_nothing` continued to pass
  (caught incidentally by the four-word `ALLOWED_VERDICTS` check, since `"armed"` isn't
  one of the four words) — this is exactly why the key-naming check needs its own
  assertion, not just a value check.
- (b) Replacing `durable_paths._atomic_write_0600(...)` with a plain
  `target.write_text(...)`: `test_save_writes_at_mode_0600` failed —
  `assert 420 == 384` (mode `0o644` instead of `0o600`) — and
  `test_a_save_that_fails_partway_leaves_the_previous_manifest_readable` failed with
  `Failed: DID NOT RAISE OSError` (the monkeypatched `os.replace` failure point was never
  reached, since `write_text` doesn't call it).
- (c) Removing the `try/except (OSError, ValueError)` around `json.loads(...)` in `load()`:
  `test_load_on_a_missing_file_returns_empty_without_raising` failed with an unhandled
  `FileNotFoundError`, and `test_load_on_malformed_json_returns_empty_without_raising`
  failed with an unhandled `json.decoder.JSONDecodeError: Expecting value: line 1 column
  1 (char 0)`.

**Task 2:**
- (a) Adding `UNCHECKED` to the excluded-verdicts tuple in `rows_to_resume`:
  `test_a_row_verdicted_unchecked_is_included_we_could_not_look_is_a_reason_to_look_again`
  failed — `assert () == ({'row_id': 'row-1', ...},)` — the unchecked row was silently
  dropped from the resume set.
- (b) Making the `held` branch skip unconditionally (removing the `_present(row.get
  ("email"))` check): `test_a_held_row_that_now_carries_an_email_is_included` failed the
  same way — `assert () == ({'row_id': 'row-1', ..., 'email': 'now@example.com'},)` — a
  row that had since gained an email stayed excluded.
- (c) Changing `preingest.build_rows_spec` to mint `f"row-{uuid.uuid4()}"` instead of the
  deterministic sequence: both the pre-existing
  `test_build_rows_spec_assigns_distinct_deterministic_ids` (37-03) and this plan's own
  `test_build_rows_spec_ids_are_stable_so_a_manifest_from_the_first_call_still_filters_the_second`
  failed with an id mismatch between two calls over identical input — confirming id
  stability is load-bearing for the whole resume feature, not just documented intent.

**Task 3:**
- Pointing `rows_to_resume` at an empty manifest (`{}`) inside
  `test_a_resume_re_requests_only_rows_that_still_needed_work` instead of the loaded one:
  the id-set assertion failed — `assert {'row-1', 'row-2', 'row-3', 'row-4', 'row-5'} ==
  {'row-3', 'row-4', 'row-5'}` (`Extra items in the left set: 'row-2', 'row-1'`) —
  demonstrating the already-matched rows getting re-sent, exactly the re-spend this
  feature exists to prevent.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `run_manifest.save`/`load`/`rows_to_resume` and the four-word `ALLOWED_VERDICTS`
  vocabulary are the exact primitives a future integration into the
  `enrich-before-ingest` turn sequence (37-05, and the skill itself) would call after each
  terminal outcome (a confirmed/auto match -> `matched`, a successful `merge_enriched` ->
  `enriched`, an emailless row at the ingest gate -> `held`, a failed match chunk ->
  `unchecked`). This plan does not wire that call site — it ships the manifest module and
  proves its contract in isolation, per the plan's own scope (`files_modified` names only
  `run_manifest.py` and its tests).
- Suite counts after this plan: `operator-claude-plugin/tests/ -q` → 1183 passed, 5
  skipped (baseline post-37-04: 1151/5); repo-root `.venv/bin/python -m pytest -q` → 2098
  passed, 6 skipped (baseline 2066/6); `node --test tests/n8n/*.test.mjs` → 621 pass,
  unchanged; arming grep → 0 for every file; `git diff --stat
  operator-claude-plugin/scripts/artifact_store.py` → empty (untouched);
  `operator-claude-plugin/scratch` clean.
- No blockers.

---
*Phase: 37-enrich-before-ingest*
*Completed: 2026-08-05*

## Self-Check: PASSED

Both files created by this plan verified present on disk; all 3 commit hashes
(`27eb375`, `98d4a9b`, `48a55d8`) verified present in `git log --oneline --all`.
