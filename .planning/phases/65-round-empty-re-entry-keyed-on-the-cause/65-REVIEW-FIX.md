---
phase: 65-round-empty-re-entry-keyed-on-the-cause
fixed_at: 2026-09-07T00:00:00Z
review_path: .planning/phases/65-round-empty-re-entry-keyed-on-the-cause/65-REVIEW.md
iteration: 1
findings_in_scope: 1
fixed: 1
skipped: 0
status: all_fixed
---

# Phase 65: Code Review Fix Report

**Fixed at:** 2026-09-07T00:00:00Z
**Source review:** .planning/phases/65-round-empty-re-entry-keyed-on-the-cause/65-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 1
- Fixed: 1
- Skipped: 0

## Fixed Issues

### CR-01: An all-companies-empty round crashes before the terminal classify ever runs, and the routing-call outcome it discarded was never kept as a fallback

**Files modified:** `operator-claude-plugin/skills/suggest-contacts/SKILL.md`, `operator-claude-plugin/tests/test_suggest_contacts_composition.py`
**Commit:** 67d3f1a
**Status:** fixed

**Applied fix:** Applied both of the review's compatible options, as instructed:

1. Each `rounds.append({...})` entry now carries `"outcome": outcome` — the routing
   call's own result — from the moment it is built, so a company's cause survives
   even if the terminal classify loop (or anything else downstream) is never reached.
2. The whole mint/dispatch/terminal-classify block (`mint_row_ids` through
   `extraction.validate`) is now guarded on `if records:`, so an all-companies-empty
   batch never calls `mint_row_ids([])` — which raised `preingest.RowSpecError`
   before this fix, by `build_rows_spec`'s own by-design refusal of an empty rows
   list. When `records` is empty, every `rounds[]` entry already carries its
   routing-call outcome from fix (1), and step 9 reports off that.

Verified the `test_skill_sequence_coverage.py` `COVERED` registry entry for
suggest-contacts needed **no update**: its parser walks the block's full AST and
records every `module.function(...)` call regardless of the `if` statement wrapping
it, so the parsed call-sequence tuple is byte-identical before and after wrapping the
block in `if records:`. `test_skill_sequence_coverage.py` passes unmodified (11
passed).

Added `test_the_documented_round_pipeline_never_crashes_when_every_company_finds_nobody`
to `operator-claude-plugin/tests/test_suggest_contacts_composition.py`: drives the
documented sequence for two companies whose ladders both yield `people: []` and whose
`attempts` both carry a `refused` disposition (making `search_fallback.
eligible_after_ladder` ineligible for both, per D-5sd-04), asserts `records` stays
empty, asserts no `RowSpecError` is raised, and asserts every `rounds[]` entry carries
`cause == CAUSE_NO_PEOPLE_FOUND` / `reentry == REENTRY_SEARCH_FALLBACK`. Confirmed the
crash is real by calling `suggest_contacts.mint_row_ids([])` directly outside the
guard and observing the `RowSpecError` the review described, before relying on the
guard to avoid it.

Full plugin suite after the fix: **2565 passed, 5 skipped** (was 2564 passed, 5
skipped before this fix — the count grew by exactly the one new test added).

---

_Fixed: 2026-09-07T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
