---
phase: 63-the-unattended-lane-actually-runs-unattended
plan: 01
subsystem: infra
tags: [sweep, cron, launchd, shell, python, operator-claude-plugin, staleness-check]

requires: []
provides:
  - "operator-claude-plugin/scripts/sweep_shim.py — resolves the newest installed plugin
    version and installs a durable /bin/sh launcher that never moves"
  - "a staleness self-check inside lv-sweep-run.sh that logs and banners when the running
    root is not the newest installed one, without ever refusing the sweep"
  - "SWEEP-CRON-TEMPLATE.md pinning the shim path plus a documented one-time re-point"
affects: [operator-claude-plugin scheduled sweep, any future phase touching durable_paths.py]

actuals:
  tokens: 4981
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "sweep_shim.py: version ordering delegated to durable_paths._VERSION_DIR_RE /
      _version_key via module-attribute access (not a from-import copy), so the
      resolution logic can never silently diverge into a second implementation"
    - "loud-but-non-refusing third wrapper state (stale), alongside the existing
      healthy / found-notices states — same stamp()/banner() helpers, no new exit path"

key-files:
  created:
    - operator-claude-plugin/scripts/sweep_shim.py
    - operator-claude-plugin/tests/test_sweep_shim.py
  modified:
    - operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh
    - operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md
    - operator-claude-plugin/tests/test_sweep_trigger_contract.py

key-decisions:
  - "sweep_shim.py's newest_install_root skips any candidate whose resolved path escapes
    the resolved cache root (T-63-01 symlink-escape mitigation) and requires the
    skills/backend-sweep/lv-sweep-run.sh marker file before treating a directory as a
    usable candidate."
  - "sweep_shim is deliberately NOT added to test_sweep_read_only.py's ALLOWED_MODULES:
    that set doubles as the exact reachable set of sweep_entry's python import closure
    (equality-checked), and sweep_shim is invoked as an independent subprocess, never
    imported. Widened test_sweep_trigger_contract.py's wrapper-capability check instead,
    and added a dedicated test asserting the wrapper only ever calls --newest, never the
    write-capable --install verb."

requirements-completed:
  - 2026-08-04-sweep-crontab-pins-a-versioned-plugin-path

coverage:
  - id: D1
    description: "A schedule naming only the durable shim path resolves the newest
      installed plugin version at run time and execs that version's lv-sweep-run.sh,
      with no schedule edit between plugin updates (D-63-01)."
    requirement: 2026-08-04-sweep-crontab-pins-a-versioned-plugin-path
    verification:
      - kind: integration
        ref: "operator-claude-plugin/tests/test_sweep_shim.py#test_shim_execs_the_newest_installed_wrapper_end_to_end"
        status: pass
    human_judgment: false
  - id: D2
    description: "A wrapper invoked with a non-newest root stamps one line naming both
      roots, posts a banner, and still completes the sweep with the sweep's own exit
      status (D-63-02); a wrapper that cannot resolve staleness stays quiet and still
      completes."
    verification:
      - kind: integration
        ref: "operator-claude-plugin/tests/test_sweep_shim.py#test_wrapper_running_an_older_root_logs_both_versions_and_still_completes"
        status: pass
      - kind: integration
        ref: "operator-claude-plugin/tests/test_sweep_shim.py#test_wrapper_with_no_resolvable_siblings_logs_could_not_check_and_still_completes"
        status: pass
      - kind: integration
        ref: "operator-claude-plugin/tests/test_sweep_shim.py#test_stale_and_healthy_exit_codes_match_for_identical_sweep_output"
        status: pass
    human_judgment: false
  - id: D3
    description: "Version ordering exists in exactly one implementation (durable_paths.py),
      never restated in the shim (D-63-04)."
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_sweep_shim.py#test_version_ordering_is_not_reimplemented"
        status: pass
    human_judgment: false
  - id: D4
    description: "SWEEP-CRON-TEMPLATE.md pins the shim in both cron and launchd, adds a
      one-time re-point step for an admin with an already-installed schedule, and the
      preserved /bin/sh rationale, cadence, and uninstall sections all survive the edit."
    verification:
      - kind: other
        ref: "grep -n lv-sweep-launcher.sh operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md (4 hits: Step 2 prose, cron line, launchd array, uninstall note)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-09-02
status: complete
---

# Phase 63 Plan 01: The unattended lane actually runs unattended — sweep launcher Summary

**Durable-home `/bin/sh` shim resolves the newest installed plugin version at every scheduled fire (D-63-01), a loud-but-non-refusing staleness self-check lands inside `lv-sweep-run.sh` (D-63-02), both reusing `durable_paths.py`'s existing version ordering (D-63-04), and `SWEEP-CRON-TEMPLATE.md` now pins the shim with a documented one-time re-point.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-09-02T05:51:35+10:00
- **Tasks:** 3 (1 tracer, 2 auto)
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- `operator-claude-plugin/scripts/sweep_shim.py` — `newest_install_root`, `shim_text`,
  `shim_path`, `install_shim`, `main` (`--newest`, `--install`). Version ordering is
  `durable_paths._VERSION_DIR_RE`/`_version_key`, called via module-attribute access so a
  future change to that logic reaches the shim automatically (proven by
  `test_version_ordering_is_not_reimplemented`, which propagates a monkeypatched failure
  rather than swallowing it).
- A schedule that names only the shim's fixed durable path now resolves the newest
  installed version at every fire — proven end to end with a real `/bin/sh` subprocess: the
  tracer test installs the shim once, invokes it, then adds a THIRD version directory and
  re-invokes the SAME shim, watching the resolved root move with zero edits to the shim
  file (byte-identical before/after).
- A third wrapper state — **ran, but stale** — lands inside `lv-sweep-run.sh`, above the
  existing `OUT=$(cd "$1" ...)` sweep invocation. It reuses the existing `stamp()`/`banner()`
  helpers, names both the running and newest root in one log line, and contains no `exit`
  statement anywhere: the sweep always completes and returns its own exit status.
- `SWEEP-CRON-TEMPLATE.md` gained a new Step 2 (`sweep_shim.py --install`) between the venv
  step and the schedule step, both cron and launchd examples now pin the printed shim path
  first (three trailing arguments unchanged), a subsection for an admin re-pointing an
  already-installed schedule once, and the "cannot run" / "confirming it fired" / "uninstalling"
  sections extended for the third state — all without touching the preserved `/bin/sh`
  rationale or cadence prose.

## Task Commits

1. **Task 1: durable-home launcher shim (tracer)** - `40053d1` (feat)
2. **Task 2: staleness self-check in lv-sweep-run.sh** - `4564ef8` (feat)
3. **Task 3: pin the shim in SWEEP-CRON-TEMPLATE.md + re-point step** - `777cfeb` (docs, includes the deviation fix below)

_Task 1 is a `type="tracer"` task: its own commit already includes the end-to-end proof
(schedule-shaped invocation → version resolution → exec → the real stubbed wrapper). The
tracer feedback gate ran immediately after (interactive, `end-of-phase` mode, `<verify>`
carries only `<automated>` blocks) — both `<verify>` commands re-ran green, so execution
continued straight to Task 2 with no checkpoint._

## Files Created/Modified

- `operator-claude-plugin/scripts/sweep_shim.py` - resolution + installer + CLI (new)
- `operator-claude-plugin/tests/test_sweep_shim.py` - 12 tests (Task 1) + 5 more (Task 2) = 17 tests (new)
- `operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh` - staleness self-check block
- `operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md` - new Step 2, shim-pinned examples, re-point subsection, extended loud/confirming/uninstalling sections
- `operator-claude-plugin/tests/test_sweep_trigger_contract.py` - widened wrapper capability assertion, added a dedicated `--install`-never-invoked test

## Decisions Made

- **T-63-01 mitigation implemented, not just documented:** `newest_install_root` skips any
  candidate directory whose resolved path escapes the resolved cache root — a symlink inside
  the user-writable cache root cannot redirect the shim's `exec` target outside the plugin
  tree. Covered by `test_symlink_escaping_cache_root_is_skipped`.
- **`sweep_shim` was deliberately kept out of `test_sweep_read_only.py`'s `ALLOWED_MODULES`.**
  That set doubles as the exact-reachable-set of `sweep_entry`'s Python import closure
  (`test_the_sweep_import_closure_is_exactly_the_allowlist` asserts equality, not just a
  subset) — `sweep_shim` is invoked as an independent subprocess by the wrapper, never
  imported by `sweep_entry.py`, so adding it there would have broken that equality check for
  an unrelated reason. Instead, `test_sweep_trigger_contract.py`'s wrapper-capability test
  was widened to `{"sweep_entry", "sweep_shim"}` with an explanatory docstring, and a new
  test (`test_wrapper_never_invokes_the_shims_write_capable_install_verb`) asserts the
  wrapper's text never contains `--install` — the actual security property NOTICE-05 exists
  to protect (the unattended sweep has no code path to a mutation), proven for the new
  script the same way `durable_paths.py`'s own write functions are proven confined for the
  existing ones.
- **No env var override for the shim's cache root**, per the plan's explicit instruction —
  the shim runs unattended from a scheduler with no human present to notice an injected
  value, so the cache root is always an explicit CLI argument or a value baked in at
  install time.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Task 2's wrapper change broke an existing read-only capability guard**
- **Found during:** Task 3 (running the full plugin suite before final verification)
- **Issue:** `test_sweep_trigger_contract.py::test_wrapper_names_only_the_sweep_entrypoint`
  asserted the wrapper names exactly `{"sweep_entry"}` as its capability surface. Task 2's
  staleness block legitimately added a second reference (`scripts/sweep_shim.py`), so the
  assertion started failing — a real signal from a security-relevant guard, not a false
  positive.
- **Fix:** Widened the assertion to `{"sweep_entry", "sweep_shim"}`, documented why
  `sweep_shim` is not added to the shared `ALLOWED_MODULES` (see Decisions above), and added
  a new test proving the wrapper's text never contains the shim's write-capable `--install`
  verb — closing the actual gap the widened assertion alone would have left unproven.
- **Files modified:** `operator-claude-plugin/tests/test_sweep_trigger_contract.py`
- **Verification:** Full `operator-claude-plugin/tests` suite green (2272 passed / 5 skipped)
- **Committed in:** `777cfeb` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix, Rule 1)
**Impact on plan:** Necessary to keep the pre-existing NOTICE-05 mutation guard honest after
a legitimate, plan-required change. No scope creep — the fix is scoped to the one guard test
Task 2's change touched, plus a new test that closes the actual gap rather than merely
widening the allowlist.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None — no external service configuration required. (`SWEEP-CRON-TEMPLATE.md`'s new Step 2
and the re-point subsection are admin-facing documentation Task 3 shipped, not something
this execution ran live: no crontab was read or written, no install directory removed, no
shim installed onto this machine's real durable home outside of test tmp_paths and a
throwaway `/tmp` verification directory cleaned up after use.)

## Next Phase Readiness

- 63-A (the sweep launcher half of Phase 63) is code-complete and tested. The admin-facing
  one-time re-point (Task 3's new subsection) is the only path that reaches this machine's
  CURRENT twelve stale install directories — that re-point has not been performed as part of
  this plan (correctly: it is an admin action outside plan scope, and D-63-03 forbids this
  plan from touching install directories or crontabs).
- 63-B (the judge model routing / offline replay) is untouched by this plan and remains open
  work for a subsequent plan in this phase.
- Full suites at close: `operator-claude-plugin` 2272 passed / 5 skipped;
  `node --test tests/n8n/*.test.mjs` 862 pass / 0 fail (unaffected by this plan, run as a
  sanity check per the plan-level `<verification>` block).

## Self-Check: PASSED

- `operator-claude-plugin/scripts/sweep_shim.py` — FOUND
- `operator-claude-plugin/tests/test_sweep_shim.py` — FOUND
- `operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh` — FOUND (modified)
- `operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md` — FOUND (modified)
- `operator-claude-plugin/tests/test_sweep_trigger_contract.py` — FOUND (modified)
- Commits `40053d1`, `4564ef8`, `777cfeb` — all present in `git log --oneline`
- `operator-claude-plugin/tests` suite: 2272 passed / 5 skipped
- `node --test tests/n8n/*.test.mjs`: 862 pass / 0 fail
- `/bin/sh -n` accepts both `lv-sweep-run.sh` and a freshly installed shim

---
*Phase: 63-the-unattended-lane-actually-runs-unattended*
*Completed: 2026-09-02*
