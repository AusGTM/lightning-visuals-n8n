---
phase: 63-the-unattended-lane-actually-runs-unattended
fixed_at: 2026-09-02T00:00:00Z
review_path: .planning/phases/63-the-unattended-lane-actually-runs-unattended/63-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 63: Code Review Fix Report

**Fixed at:** 2026-09-02
**Source review:** .planning/phases/63-the-unattended-lane-actually-runs-unattended/63-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (WR-01 through WR-04; `fix_scope: critical_warning`, no Critical findings existed)
- Fixed: 4
- Skipped: 0

Edited and committed directly on `master` (no worktree) per `workflow.use_worktrees: false` in
`.planning/config.json` — the documented opt-out.

## Fixed Issues

### WR-01: Shim-level failures banner but never write a log line

**Files modified:** `operator-claude-plugin/scripts/sweep_shim.py`, `operator-claude-plugin/tests/test_sweep_shim.py`
**Commit:** `fce7948`
**Applied fix:** Both failure branches inside `_SHIM_TEMPLATE` (no bootstrap found; `--newest`
resolves nothing usable) now append a stamped line to `$3` (the log path — already validated
present by that point) before calling `banner()`, mirroring `lv-sweep-run.sh`'s own `stamp()`
convention. Banner text is unchanged; only a log write was added ahead of it. Added
`test_shim_failure_paths_write_a_log_line_not_just_a_banner`, which drives the real `/bin/sh`
shim as a subprocess through both failure branches and asserts the log file gets a line.
Verified the rendered shim text with `sh -n` (syntax clean) before committing.

### WR-02: Headline-printing program has no exception guard, unlike the count program

**Files modified:** `operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh`, `operator-claude-plugin/tests/test_sweep_trigger_contract.py`
**Commit:** `92e1ba2`
**Applied fix:** Wrapped the embedded `HEADLINES` python program in the same `try/except
Exception: pass` pattern the `COUNT` program already uses, and gated the `.get("headline")`
call on `isinstance(n, dict)` so a non-dict element degrades to an empty headline instead of
raising `AttributeError` mid-loop. Also replaced the final `stamp "posted $COUNT
notification(s)"` (which reported the *total* notice count) with `POSTED_COUNT`, computed from
what the program actually printed (`grep -c .` over `$HEADLINES`), so the log can no longer
claim full delivery on a run that silently dropped headlines after a malformed element. Added
two tests in `test_sweep_trigger_contract.py`
(`test_behavior_headline_program_survives_a_non_dict_element`,
`test_behavior_headline_program_prints_nothing_on_top_level_malformed_input`) using that file's
existing in-process extraction/exec pattern — a full shell-level end-to-end run through
`osascript` is explicitly out of scope for this test file per its own docstring, so I followed
the file's established methodology rather than adding a new one.

### WR-03: Symlink-escape guard covers the version directory, not the wrapper path one level inside it

**Files modified:** `operator-claude-plugin/scripts/sweep_shim.py`, `operator-claude-plugin/tests/test_sweep_shim.py`
**Commit:** `7f761b8`
**Applied fix:** Chose the **code fix**, not the docstring-narrowing alternative the review also
offered — the docstring's existing claim ("must not redirect the shim's `exec` target outside
the plugin tree") is the invariant the phase actually wants (T-63-01), the gap was cheap to
close, and closing it fully delivers what was already documented rather than watering the
documentation down to match a partial implementation. Extended `newest_install_root` to resolve
`(entry / "skills" / "backend-sweep" / "lv-sweep-run.sh")` and verify it too stays within
`resolved_cache_root`, rejecting the candidate otherwise — this catches a real (non-symlink)
version directory whose wrapper file is itself a symlink pointing outside the cache root, which
the prior top-level-only check missed. Widened the docstring to state the guarantee now covers
both levels. Added `test_symlink_wrapper_escaping_cache_root_is_skipped`, mirroring the existing
`test_symlink_escaping_cache_root_is_skipped` test shape, which fails against the pre-fix code
and passes against the fix.

### WR-04: The harness's own failure-path remediation instructions name a file the harness then deletes

**Files modified:** `scripts/verify_sweep_shim_scheduler.sh`
**Commit:** `f9ab76c`
**Applied fix:** In `cleanup()`, the unconditional `rm -rf "$WORK"` now only runs when
`TEARDOWN_OK -eq 1`. When teardown could not be confirmed, the work directory (which contains
`$PLIST_PATH`, the exact file named in the printed remediation instructions) is left in place
and a `log_err` line explains why, so an operator following the printed `launchctl unload
'$PLIST_PATH'` instruction finds a real file rather than one the harness just deleted. No
automated test suite references this file (confirmed by grep across `.py`/`.sh`/`.md`) — it is a
real-launchd proof harness meant to be run manually against a live scheduler, consistent with
its own docstring. Verified with `sh -n` (syntax clean) and a full re-read of the modified
`cleanup()` function (Tier 1 + Tier 2 fallback per the verification strategy).

## Skipped Issues

None — all four in-scope findings were fixed.

---

_Fixed: 2026-09-02_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
