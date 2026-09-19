---
phase: 74-code-review-follow-ups-from-phase-73
fixed_at: 2026-09-20T09:24:34+10:00
review_path: .planning/phases/74-code-review-follow-ups-from-phase-73/74-REVIEW.md
iteration: 1
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 74: Code Review Fix Report

**Fixed at:** 2026-09-20T09:24:34+10:00
**Source review:** `.planning/phases/74-code-review-follow-ups-from-phase-73/74-REVIEW.md`
**Iteration:** 1
**Fix scope:** `critical_warning` (WR-13 only; IN-01/IN-02 are Info-level and out of scope
— see "Out of scope" below).

**Summary:**
- Findings in scope: 1
- Fixed: 1
- Skipped: 0

## Fixed Issues

### WR-13: `csv_dedupe.py`'s WR-12 fix relocates generated artifacts into the operator's own file-system tree with no corresponding cleanup step

**Files modified:**
- `operator-claude-plugin/skills/contact-upload/SKILL.md`
- `operator-claude-plugin/tests/test_csv_dedupe.py`
- `operator-claude-plugin/.claude-plugin/plugin.json`
- `operator-claude-plugin/CHANGELOG.md`

**Commits:** `7c5d174a669bb14e2860fb963c450afd8a7fdfd1` (the fix), plus a follow-up
correction `86df95ac5717015a1c9ef015dd647d727c934407` (the first commit's own cleanup-step
wording claimed the dedupe artifacts land "not in the scratch directory", which is false
on the branch where step 2b already wrote a scratch copy and step 2c's output lands
beside it, i.e. still in scratch — caught by a post-completion advisor review before this
report was finalized; reworded to state both cases instead of asserting one unconditionally.
The delete instruction itself was correct throughout; only the reason clause was wrong. No
test changes were needed for the correction).

**Chosen fix (of the review's two offered options):** option (a) — added a cleanup step
to `contact-upload/SKILL.md`, rather than option (b) (returning `apply_dedupe`'s default
write location to the gitignored `scratch/` directory). Consulted the advisor before
committing to a direction: reopening WR-12's chosen default (write beside the input,
landed in `74-03`) would ripple into two already-passing location tests
(`test_apply_dedupe_writes_beside_the_input_by_default`,
`test_apply_dedupe_default_output_does_not_collide_across_directories_sharing_a_stem`)
and change `apply_dedupe`'s return shape that step 3/step 10 of the skill already consume
— a materially larger diff for the same collision-safety property WR-12 already achieves.
The doc-only fix touches nothing `74-03` pinned and closes the gap the finding actually
names (nothing in the repo deletes the two new artifacts).

**Applied fix:**
- `csv_dedupe.py` and its WR-12 output-location behavior are **unchanged**.
- `contact-upload/SKILL.md` step 10 ("Clean up") gained one new paragraph: for a
  file-path batch (i.e. one that ran step 2c), delete `deduped_path` and
  `collapsed_path` — step 2c's own outputs, which land beside whatever file step 2b
  handed it, not in the scratch directory, so they were not covered by the pre-existing
  "same scratch directory" sentence. Same end-of-batch rule as step 2b's own artifacts
  (dispatched or declined alike).
- Added one pinning test,
  `test_skill_cleanup_step_names_the_dedupe_artifacts_for_deletion`, to
  `operator-claude-plugin/tests/test_csv_dedupe.py`. It reads
  `skills/contact-upload/SKILL.md`, slices from the `10. **Clean up.**` heading to EOF,
  and asserts both `deduped_path` and `collapsed_path` appear in that slice.
  **RED before the fix:** `AssertionError: cleanup step must name deduped_path (step 2c's
  output) for deletion` (confirmed live against the unmodified `SKILL.md` before editing
  it). **GREEN after:** `1 passed` alongside the other 37 tests in
  `test_csv_dedupe.py` + `test_skill_sequence_coverage.py` (38 passed total, 0 failed).
- Verified no other test pins step 10's exact prose in a way this addition could break
  (`test_header_correction_e2e.py::test_skill_md_names_the_script_the_confirm_flag_and_the_corrected_artifact`
  only asserts `"2b"` appears in the cleanup slice, which it still does).
- Version bump: `operator-claude-plugin/.claude-plugin/plugin.json` `0.52.0` → `0.52.1`
  (a SKILL.md behavior change is a plugin release, per this repo's release checklist),
  with a matching one-entry `CHANGELOG.md` addition naming WR-13 under `## [0.52.1]`.
- `n8n/` untouched: `git diff --quiet -- n8n/` returns clean (exit 0).

**Verification (run from the main checkout — `workflow.use_worktrees=false`, no worktree
was created for this run, so these counts are reproducible directly from this tree):**
- `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider operator-claude-plugin/tests/test_csv_dedupe.py operator-claude-plugin/tests/test_skill_sequence_coverage.py` → **38 passed**
- Full suite: `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider` → **5171 passed, 160 skipped** (matches the expected 5170+/160 given in the task instructions)

## Out of scope (Info-level, not fixed this pass)

Per `fix_scope: critical_warning`, only WR-13 was in scope. The review's two Info findings
were left untouched, as instructed:

- **IN-01** (`operator-claude-plugin/tests/test_control_flag_parity.py:115-161`) — a
  lower-confidence observation about a pattern (per-sentinel hardcoded rewrite counts)
  that could silently drift again for a *third* future sentinel; not a proven defect
  against this phase's own diff.
- **IN-02** (`tests/n8n/frozenFixtureSecrets.test.mjs:38`) — a currently-inert regex
  lookahead (`(?!<redacted>)`) that doesn't match the real `REDACTED_PLACEHOLDER` text;
  harmless today because the widened `_scrub` (CR-04) redacts the whole `headers` object
  wholesale, so the per-key shape this lookahead was meant to exclude never appears in any
  committed fixture.

---

_Fixed: 2026-09-20T09:24:34+10:00_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
