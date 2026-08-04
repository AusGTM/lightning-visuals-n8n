---
phase: 33-durable-operator-state
plan: 03
subsystem: infra
tags: [python, pytest, subprocess-testing, plugin-config, durable-storage]

requires:
  - phase: 33-02
    provides: "durable_paths.resolve_state_path() with the sibling-scan migration wired in, identical allow_migration contract to resolve_config_path()"
provides:
  - "artifact_store.state_path() delegating to durable_paths.resolve_state_path() — the dashboard Artifact pointer now shares the single resolution authority the config uses"
  - "init_check.inspect() config_location (env/durable/legacy) and one reassurance line in render()'s already-set-up branch, never mentioning migration"
  - "_run_store subprocess harness in test_artifact_store.py pinning artifact_store.py's __main__ across a simulated version bump"
affects: ["33-04"]

actuals:
  tokens: 5920
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Env-var isolation for in-process resolver tests (CLAUDE_PLUGIN_DATA / HOME via monkeypatch) instead of touching real ~/.claude, for tests that call a resolver bare rather than through a subprocess"
    - "Subprocess entrypoint harness mirroring an existing one (_run_cli -> _run_store), reusing the multi-version cache-layout idea from 33-02 for a second module"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/artifact_store.py
    - operator-claude-plugin/scripts/init_check.py
    - operator-claude-plugin/skills/initialize/SKILL.md
    - operator-claude-plugin/tests/test_artifact_store.py
    - operator-claude-plugin/tests/test_init_check.py

key-decisions:
  - "The three retargeted 'where the file lives' tests, called bare (artifact_store.state_path() with no args, not via subprocess), fail in a repo-checkout dev environment even after the correct code change: with nothing at the durable home and no sibling to migrate, resolve_state_path() falls through to the legacy PLUGIN_ROOT/state/ path by design (33-01/33-02's settled resolution order) — the checkout has no version-named siblings under PLUGIN_ROOT.parent to migrate from. Fixed by pointing CLAUDE_PLUGIN_DATA (durable_dir()'s own env override) at a tmp_path directory holding a durable pointer, which is a lighter isolation than faking the whole HOME tree and still never touches real ~/.claude state — not called for explicitly by the plan text but required to satisfy 'all tests pass' deterministically in any environment, not just one where a real durable pointer happens to already exist."
  - "save() keeps write_text rather than durable_paths._atomic_write_0600 — the pointer holds no secret and _read() already treats a half-written file the same as no file, so the 0600 atomicity window has no observable consequence. Documented in the docstring per plan instruction so it reads as a decision, not an oversight."
  - "The STATUS-05 version-bump proof (save from 0.6.2, load from 0.7.0) works via the SAME sibling-scan migration built in 33-02, not a direct durable write on first save: with nothing to migrate, the very first save() call resolves to LEGACY (inside its own version directory) by design, and it is 0.7.0's own resolution, on load, that discovers and migrates 0.6.2's legacy pointer up — exactly mirroring how the config already behaves. This is not a special case for the pointer; it is the same resolution order 33-CONTEXT.md settled for both files."

patterns-established:
  - "config_location derivation (env > durable-by-parent-match > legacy) lives in init_check.py as a three-line function, not duplicated logic inside inspect() or render()"

requirements-completed: [STATUS-05, PLUGIN-02]

coverage:
  - id: D1
    description: "artifact_store.state_path() resolves through durable_paths.resolve_state_path(), the same authority config_gate.config_path() uses — no second copy of the resolution rule"
    requirement: "STATUS-05"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_artifact_store.py::test_the_resolved_state_path_sits_outside_the_plugin_directory"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_artifact_store.py::test_the_resolved_state_path_is_outside_the_repository_working_tree"
        status: pass
    human_judgment: false
  - id: D2
    description: "A dashboard pointer saved under one plugin version is read back under the next version, proven by driving artifact_store.py's __main__ as a subprocess — the STATUS-05 cross-session/cross-update guarantee is true again"
    requirement: "STATUS-05"
    verification:
      - kind: integration
        ref: "operator-claude-plugin/tests/test_artifact_store.py::test_durable_home_lets_a_newer_version_load_what_an_older_version_saved"
        status: pass
      - kind: integration
        ref: "operator-claude-plugin/tests/test_artifact_store.py::test_durable_save_lands_in_the_durable_directory_not_either_version_directory"
        status: pass
    human_judgment: false
  - id: D3
    description: "A missing pointer (fresh home) and a missing config (collect verb) both degrade to a clean exit 0 rather than an error"
    verification:
      - kind: integration
        ref: "operator-claude-plugin/tests/test_artifact_store.py::test_durable_load_on_a_fresh_home_with_nothing_anywhere_is_null_not_an_error"
        status: pass
      - kind: integration
        ref: "operator-claude-plugin/tests/test_artifact_store.py::test_durable_collect_with_no_config_present_still_runs_and_exits_zero"
        status: pass
    human_judgment: false
  - id: D4
    description: "The three original 'where the file lives' location tests are retargeted, not deleted, and each replacement is equal-or-stronger than what it replaced (dotfile: narrowed to filename, the only form true both before and after the move; inside-plugin: replaced with its negation; gitignored: replaced with outside-the-working-tree, strictly stronger since git check-ignore errors on a path outside the repo)"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_artifact_store.py::test_the_resolved_state_path_is_not_a_dotfile"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_artifact_store.py -k 'where_the_file_lives or sits_outside or outside_the_repository'"
        status: pass
    human_judgment: false
  - id: D5
    description: "/operator-claude-plugin:initialize names the resolved settings path and its location (durable/legacy/env) in the already-set-up branch, phrased as reassurance, and makes no claim anywhere that a migration occurred"
    requirement: "PLUGIN-02"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_init_check.py -k config_location"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_init_check.py::test_rendered_output_for_a_durable_config_never_mentions_migration"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-08-04
status: complete
---

# Phase 33 Plan 03: Durable Operator State — Artifact Pointer + Initialize Report Summary

**The dashboard Artifact pointer now resolves through the same `durable_paths` authority the config uses, closing the silent STATUS-05 regression, and `/operator-claude-plugin:initialize` names where the settings actually live without ever claiming a migration happened.**

## Performance

- **Duration:** ~15 min (commit span `b15c2a7` → `13369b2`)
- **Tasks:** 3
- **Files modified:** 5 (2 scripts, 1 skill doc, 2 test files)

## Accomplishments

- `artifact_store.state_path()` now returns `durable_paths.resolve_state_path()` instead of a hardcoded `PLUGIN_ROOT/state/` constant — the pointer survives a plugin update the same way the config already does.
- The three "where the file lives" tests are retargeted with docstrings recording exactly what each guaranteed before and why the replacement is equal-or-stronger (see Deviations/Decisions below — none were weakened, and none were deleted).
- STATUS-05 — "a brand-new conversation lands on the SAME dashboard URL" — is proven true again across a *simulated version bump*, driven at the CLI subprocess layer (`_run_store` mirroring `test_config_gate.py::_run_cli`), closing the gap 33-CONTEXT.md measured live: no install directory on the operator's machine held a pointer.
- `init_check.inspect()` reports `config_location` (`env` / `durable` / `legacy`); `render()`'s already-set-up branch names what that location means for the operator, in one reassurance line, with a code comment explaining why migration is never mentioned on any branch.
- Plugin suite: 938/5 → **947/5**. Full python: 1819/6 → **1828/6**. Node: unchanged at 550/550. Zero regressions.

## Task Commits

Each task was committed atomically:

1. **Task 1: The pointer moves, and the three location tests are retargeted rather than deleted** - `2afa84e` (feat)
2. **Task 2: STATUS-05 across a simulated version bump, pinned at the entrypoint** - `a66abfc` (test)
3. **Task 3: initialize reports the real path and says nothing it cannot know** - `13369b2` (feat)

_No separate plan-metadata commit was needed beyond this SUMMARY's own commit, per the standard final-commit step below._

## Files Created/Modified

- `operator-claude-plugin/scripts/artifact_store.py` - `state_path()` delegates to `durable_paths.resolve_state_path()`; `DEFAULT_STATE_PATH` removed; `save()`'s `write_text` decision documented in-line
- `operator-claude-plugin/scripts/init_check.py` - `_config_location()` (env/durable/legacy), `config_location` in `inspect()`'s report, one reassurance line per location added to `render()`'s `STATUS_READY` branch
- `operator-claude-plugin/skills/initialize/SKILL.md` - "Already set up" paragraph and Step 2 item 1 both extended to relay the location line / note version-independence
- `operator-claude-plugin/tests/test_artifact_store.py` - three location tests retargeted (dotfile narrowed to filename, inside-plugin replaced with its negation, gitignored replaced with outside-repo), four new `-k durable` subprocess entrypoint tests, `_run_store` harness
- `operator-claude-plugin/tests/test_init_check.py` - five new tests: three `config_location` values, the rendered-path assertion, the no-migration-language guard

## Decisions Made

**1. In-process location tests needed env-var isolation the plan text didn't spell out.** The two retargeted tests (`sits_outside_the_plugin_directory`, `is_outside_the_repository_working_tree`) call `artifact_store.state_path()` bare — no subprocess, no explicit path. In THIS repo checkout, with no `~/.claude/plugins/data/...` on the machine and no version-named siblings under `PLUGIN_ROOT.parent` (the checkout has none — `PLUGIN_ROOT.parent` is the whole repo), `resolve_state_path()` legitimately falls through to the legacy `PLUGIN_ROOT/state/` path by design (33-01/33-02's settled resolution order — nothing to migrate is not an error, it is the correct fresh-install answer). A bare call therefore asserts the opposite of what these two tests exist to prove, on this specific machine, regardless of the code being correct. Fixed by pointing `CLAUDE_PLUGIN_DATA` (`durable_dir()`'s own env override) at a `tmp_path` directory holding a pointer before each assertion — the lightest isolation that makes durable resolution deterministic without faking all of `HOME` and without ever touching real `~/.claude` state.

**2. `save()` keeps `write_text`, not `_atomic_write_0600`** — per the plan's locked decision, documented in the function's docstring: the pointer holds no secret, and `_read()` already treats a half-written file identically to no file at all, so the atomicity window has no observable consequence.

**3. The STATUS-05 version-bump test proves the guarantee through the SAME migration mechanism 33-02 built, not a direct-to-durable first write.** With nothing anywhere to migrate, the very first `save()` call resolves to the legacy path inside its OWN version directory — this is not a gap in the fix, it is the documented, settled resolution order (durable → legacy → migrate-once, checked in that sequence). It is the SECOND version's own resolution, on `load`, that discovers and migrates the first version's legacy pointer up. Mirrors exactly how the config already behaves; not a special case invented for the pointer.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `CLAUDE_PLUGIN_DATA`-based isolation to the two retargeted in-process location tests**
- **Found during:** Task 1 verification (`pytest operator-claude-plugin/tests/test_artifact_store.py -x -q`)
- **Issue:** As written per the plan's literal action text (bare `artifact_store.state_path()` call, no isolation), `test_the_resolved_state_path_sits_outside_the_plugin_directory` failed on this dev machine: `resolve_state_path()` legitimately fell through to the legacy path because nothing existed at the durable home and no version-named sibling existed to migrate from — the ordinary, correct behavior for a bare repo checkout, not a code defect.
- **Fix:** Added a small `_point_at_a_fake_durable_home(monkeypatch, tmp_path)` helper that sets `CLAUDE_PLUGIN_DATA` (the env override `durable_dir()` already reads) to a `tmp_path` directory pre-populated with a pointer file, applied to both retargeted "outside" tests. No production code changed; test-only isolation, consistent with the plan's own critical constraint that every test build isolated state under `tmp_path` rather than touching real `~/.claude`.
- **Files modified:** `operator-claude-plugin/tests/test_artifact_store.py`
- **Verification:** `pytest operator-claude-plugin/tests/test_artifact_store.py -x -q` — 27 passed
- **Committed in:** `2afa84e` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 — blocking test-environment issue; no code-behavior change)
**Impact on plan:** No scope creep. The fix is confined to test isolation and does not alter `artifact_store.py`, `durable_paths.py`, or the resolution order in any way.

## Issues Encountered

- The `_run_store` subprocess helper needed `exist_ok=True` on its `scripts/` directory `mkdir` — the fourth durable test calls it twice against the same `home`/`version` pair (once to establish the durable home via migration, once to prove the subsequent write lands there), which the plan's own description implies ("home lets two calls share one fake home") but the helper's first draft didn't tolerate a repeat call against the same version directory. One-line fix, caught immediately by the test run.
- No other implementation surprises — every other acceptance criterion in the plan was met on the first pass.

## User Setup Required

None — no external service configuration required. This plan is entirely local filesystem/path-resolution logic, test coverage, and operator-facing text.

## Next Phase Readiness

- `artifact_store.py` and `config_gate.py` now share the identical `durable_paths` resolution authority for both pieces of per-operator state (config, dashboard pointer) — the "second-source-of-truth pattern this milestone avoids everywhere else" is fully closed for this phase's two files.
- `init_check.py`'s `config_location` field is available for any future skill that wants to say more about where settings live, without adding a second resolution check anywhere.
- 33-04 (per the plan's `depends_on` chain) can build on a fully durable-aware `artifact_store` and `init_check` with no outstanding TODOs from this plan.

## Self-Check: PASSED

- FOUND: `operator-claude-plugin/scripts/artifact_store.py`
- FOUND: `operator-claude-plugin/scripts/init_check.py`
- FOUND: `operator-claude-plugin/skills/initialize/SKILL.md`
- FOUND: `operator-claude-plugin/tests/test_artifact_store.py`
- FOUND: `operator-claude-plugin/tests/test_init_check.py`
- FOUND commit `2afa84e`
- FOUND commit `a66abfc`
- FOUND commit `13369b2`

---
*Phase: 33-durable-operator-state*
*Completed: 2026-08-04*
