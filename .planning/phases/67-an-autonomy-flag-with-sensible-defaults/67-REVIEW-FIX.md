---
phase: 67-an-autonomy-flag-with-sensible-defaults
fixed_at: 2026-09-07T08:49:03Z
review_path: .planning/phases/67-an-autonomy-flag-with-sensible-defaults/67-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 67: Code Review Fix Report

**Fixed at:** 2026-09-07T08:49:03Z
**Source review:** .planning/phases/67-an-autonomy-flag-with-sensible-defaults/67-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (CR-01, WR-01, WR-02)
- Fixed: 3
- Skipped: 0

## Fixed Issues

### CR-01: `autonomy_enabled` reads an explicit `"autonomy": null` as ON for every level, contradicting its own near-miss-fails-OFF design

**Files modified:** `operator-claude-plugin/scripts/config_gate.py`, `operator-claude-plugin/tests/test_autonomy_levels.py`
**Commit:** `469d445`
**Applied fix:** `autonomy_enabled` now checks `AUTONOMY_SETTINGS_KEY not in cfg` before indexing the parent, so an explicit `{"autonomy": null}` falls through to the same `not isinstance(parent, dict)` branch a bare boolean parent (`{"autonomy": true}`) already degrades to `False` on, rather than being caught by the earlier `parent is None: return True` absence branch. RED-first: added `test_explicit_null_parent_reads_every_level_off_not_on`, confirmed it failed against the pre-fix code (`AssertionError: assert True is False`), then applied the fix and confirmed GREEN (17 passed in `test_autonomy_levels.py`; full suite 2750 passed / 5 skipped, up from the 2749/5 baseline by exactly the one new test).

### WR-01: `read_only` autonomy level is documented as live but has zero call sites

**Files modified:** `operator-claude-plugin/config/operator.local.example.json`
**Commit:** `49e4d37`
**Applied fix:** Reworded the `_autonomy_note`'s `read_only` clause from claiming it governs `backend-status`, review-queue reads and `loss-reason-report` to stating it is declared and reserved — those skills never pause to ask today, so there is nothing yet for the switch to gate, and wiring it in is outstanding rather than done. Also named which levels ARE actually wired (`spend_no_write` into `suggest-contacts`; `write` into `contact-upload`, `enrich-before-ingest`, `enrich-records`), matching what a grep of every `SKILL.md` for `autonomy_enabled` call sites actually shows. No skill anywhere claimed the read_only wiring outside this one note, so no other file needed the same correction. `AUTONOMY_LEVELS` keeps all three names (D-67-01); no code path changed. Full suite unchanged at 2750 passed / 5 skipped.

### WR-02: `suggest-contacts/SKILL.md` reuses the identifier `outcome` for two unrelated values across the same walkthrough

**Files modified:** `operator-claude-plugin/skills/suggest-contacts/SKILL.md`
**Commit:** `4d121e3`
**Applied fix:** Renamed the per-company loop's local variable from `outcome` to `company_outcome` (its assignment from `suggest_contacts.round_outcome(walk)`, both `["reentry"]` reads, and the `"outcome": company_outcome` dict-entry write into `rounds[]`). The dict key itself stays `"outcome"` — only the bare local variable that previously collided in name (though not in scope-time, since Stage 2's dispatch block reassigns `outcome` afterward) with the batch-level dispatch outcome consumed by step 9's `outcomes=[outcome]` report call was renamed. `test_mandatory_report_call_sites.py`'s literal `outcomes=[outcome]` shape pin still passes unmodified; ran the three prose/call-site/sequence test files together (94 passed). Full suite unchanged at 2750 passed / 5 skipped.

## Skipped Issues

None — all findings were fixed.

## Verification

Ran in the main checkout (worktree isolation skipped: `workflow.use_worktrees` is `false` in `.planning/config.json`, per the documented opt-out).

- `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` → **2750 passed, 5 skipped** (baseline was 2749 passed / 5 skipped; the +1 is the new CR-01 RED/GREEN test).
- `node --test tests/n8n/*.test.mjs` → **940 pass, 0 fail**.
- `git status --porcelain -- n8n/ scripts/build_cloud_workflows.py` → empty (no drift).

---

_Fixed: 2026-09-07T08:49:03Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
