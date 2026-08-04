---
phase: 33-durable-operator-state
plan: 02
subsystem: infra
tags: [python, pytest, subprocess-testing, plugin-config, durable-storage, atomic-write, security]

requires:
  - phase: 33-01
    provides: "durable_paths.py steps 1-4 (explicit, LV_OPERATOR_CONFIG, durable home, legacy), _run_cli extended with env=/durable_config="
provides:
  - "durable_paths.py step 5: _atomic_write_0600, _VERSION_DIR_RE, _version_key, _newest_sibling_holding, _migrate_once — the sibling-scan migration wired into resolve_config_path/resolve_state_path"
  - "allow_migration flag threaded through resolve_config_path/resolve_state_path, config_gate.config_path/load_config — a caller can resolve read-only, skipping step 5 entirely"
  - "sweep_entry._load_config_no_migration — the sweep's default config loader, always allow_migration=False"
  - "test_sweep_read_only.py filesystem-write guard (FS_WRITE_VERBS, DURABLE_PATHS_WRITE_FUNCTIONS, a behavioral migration-abstention test) — the write-verb guard's HTTP-only blind spot for durable_paths.py's new filesystem writes is closed"
affects: ["33-03 (artifact_store.py wiring resolve_state_path inherits the same allow_migration contract)", "33-04"]

actuals:
  tokens: 10826
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Verify-then-delete for an irreversible filesystem operation: copy, read back and compare byte-for-byte, only then unlink — never delete on an unverified copy"
    - "Two independent guards against the same destructive call: exclusion inside the scan (_newest_sibling_holding) AND a second, load-bearing check immediately before the unlink in _migrate_once"
    - "A read-only resolution mode (allow_migration=False) threaded through a whole resolver chain so one caller (the unattended sweep) can be structurally incapable of an irreversible side effect, rather than merely disciplined not to trigger it"
    - "Filesystem-write AST guard as a sibling to an existing HTTP-write-verb AST guard, narrowed to avoid a common-method false positive (bare .replace() vs os.replace())"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/durable_paths.py
    - operator-claude-plugin/scripts/config_gate.py
    - operator-claude-plugin/scripts/sweep_entry.py
    - operator-claude-plugin/tests/test_durable_paths.py
    - operator-claude-plugin/tests/test_config_gate.py
    - operator-claude-plugin/tests/test_sweep_read_only.py

key-decisions:
  - "Checkpoint resolved by the operator (pre-execution): delete-immediately — verify then delete, in the same resolution. _migrate_once implements exactly this."
  - "Blocking constraint found after planning: the unattended sweep must never perform the irreversible delete, but the plan's own checkpoint decision put that delete inside durable_paths.py, which config_gate imports, which is in sweep_entry's transitive closure. Resolved by threading a new allow_migration flag (default True) through resolve_config_path/resolve_state_path and config_gate.config_path/load_config, and giving sweep_entry a dedicated default loader (_load_config_no_migration) that always resolves with allow_migration=False. An update the sweep meets before an interactive run has migrated now surfaces as the existing sweep_not_configured notice — loud, not a silent widening of what the sweep can do. This is the 'migration fully disabled for the sweep' alternative the blocking constraint itself named as acceptable, chosen over a finer-grained 'copy allowed, delete not' split because that split would need a second flag/behavior mode inside the one function in this plugin that destroys live credentials — more surface for a bug, for a guarantee the simpler flag already gives."
  - "test_sweep_read_only.py's compensating write-verb guard was HTTP-verb-only (post/put/patch/delete) and structurally blind to filesystem writes — its own 33-01 comment claiming durable_paths 'cannot be a write vector' went false the moment this task gave it real filesystem writes. Extended with a parallel filesystem-write AST scan (FS_WRITE_VERBS: replace/unlink/chmod/fdopen), narrowed so bare .replace() (the ordinary str/datetime method) doesn't false-positive against n8n_read.py's started.replace(tzinfo=...) — only os.replace(...) qualifies. A second, function-level check (durable_paths_write_call_confinement) asserts the writes live ONLY inside _atomic_write_0600/_migrate_once, not merely 'somewhere in durable_paths.py'. Because the write-capable code exists in durable_paths.py's source regardless (shared with the interactive resolvers), a purely syntactic scan can only prove WHERE the writes live, not that the sweep's actual run never reaches them — so a behavioral test drives sweep_entry._cli_main() with its real default loader against a fake HOME where a migration is genuinely available, proves it does not happen, then proves (as a control) the identical layout DOES migrate when allow_migration=True, so the abstention is meaningful rather than vacuous."
  - "Task 1's interim wiring used _atomic_write_0600 directly (copy-only, no delete), per the plan's explicit Task 1 acceptance criterion that no file be unlinked until Task 3 — kept as a real intermediate commit rather than folding the whole feature into one commit, so each task's own verify/acceptance gate is checkable against its own diff."

requirements-completed: [PLUGIN-02, PLUGIN-03]

coverage:
  - id: D1
    description: "The newest sibling install that actually holds a config is found and migrated into the durable home on first resolution, with no operator action — proven via a simulated update at the CLI subprocess layer"
    requirement: "PLUGIN-02"
    verification:
      - kind: integration
        ref: "operator-claude-plugin/tests/test_config_gate.py::test_cli_migrates_the_newest_sibling_up_to_the_durable_home"
        status: pass
    human_judgment: false
  - id: D2
    description: "The migrated file is mode 0600, verified byte-for-byte before the sibling's copy is deleted, and the current install's own config is never touched even when a sibling scan is possible"
    requirement: "PLUGIN-03"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_durable_paths.py -k atomic_write"
        status: pass
      - kind: integration
        ref: "operator-claude-plugin/tests/test_config_gate.py::test_cli_never_scans_or_touches_anything_when_the_current_install_already_has_a_config"
        status: pass
    human_judgment: false
  - id: D3
    description: "A second run, and a further version bump, are silent no-ops that resolve via the already-populated durable home — no repeat migration, no mtime change, no migration language in output"
    verification:
      - kind: integration
        ref: "operator-claude-plugin/tests/test_config_gate.py -k 'second_run or version_bump'"
        status: pass
    human_judgment: false
  - id: D4
    description: "An unwritable durable home degrades to the legacy path with exit 0 — never a refusal"
    requirement: "PLUGIN-03"
    verification:
      - kind: integration
        ref: "operator-claude-plugin/tests/test_config_gate.py::test_cli_exits_zero_and_reads_the_local_config_when_the_durable_home_is_unwritable"
        status: pass
    human_judgment: false
  - id: D5
    description: "The unattended sweep never triggers the sibling-scan migration or its delete — resolves read-only by construction (allow_migration=False), not merely by discipline — and a filesystem-write AST guard closes the HTTP-verb guard's blind spot to open()/os.replace/Path.unlink/os.chmod"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_sweep_read_only.py::test_the_only_reachable_filesystem_writes_are_the_named_migration_functions"
        status: pass
      - kind: integration
        ref: "operator-claude-plugin/tests/test_sweep_read_only.py::test_the_sweep_does_not_migrate_even_when_a_sibling_holds_a_config"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-08-04
status: complete
---

# Phase 33 Plan 02: Durable Operator State — Sibling-Scan Migration Summary

**The one-time sibling-scan migration (`_migrate_once`) now moves an operator's config up into the durable home on the update that would otherwise lose it — copy, verify byte-for-byte, delete only then — while a newly-discovered risk (the unattended sweep inheriting a code path to that same irreversible delete) was closed by making the sweep's config resolution structurally read-only, not just disciplined.**

## Performance

- **Duration:** ~55 min
- **Tasks:** 3 (plus the checkpoint, pre-resolved by the operator before this run) and one blocking-constraint resolution found after planning
- **Files modified:** 6 (3 scripts, 3 test files; no new files)

## Accomplishments

- `durable_paths.py` gained `_atomic_write_0600` (tempfile-in-target's-own-dir + chmod 0600 + fsync + `os.replace`, never observable partially written), `_VERSION_DIR_RE`/`_version_key` (regex-filtered before sort, `0.10.0` correctly above `0.9.0`), `_newest_sibling_holding` (newest sibling that actually holds the file, excluding the current install by resolved-path equality), and `_migrate_once` (verify-then-delete, per the operator's checkpoint decision).
- Both resolvers (`resolve_config_path`, `resolve_state_path`) now perform the sibling scan and migration as resolution step 5, behind a new `allow_migration` flag.
- The blocking constraint raised after planning — the sweep's read-only guarantee (NOTICE-05) at risk from this task's own delete — resolved by threading `allow_migration` through `config_gate.config_path`/`load_config` and giving `sweep_entry` a dedicated default loader (`_load_config_no_migration`) that always resolves read-only. An update the sweep meets before an interactive run has migrated now surfaces as the existing `sweep_not_configured` notice.
- `test_sweep_read_only.py` extended with a filesystem-write AST guard (parallel to its existing HTTP-write-verb guard, closing that guard's structural blindness to `open`/`os.replace`/`Path.unlink`/`os.chmod`) plus a behavioral test proving the sweep's actual run never migrates even when a migration is genuinely available.
- 15 new tests added across three files; the plugin suite grew from 923/5 to 938/5, the full python suite from 1804/6 to 1819/6, both with zero regressions. Node suite unaffected (550/550).

## Task Commits

Each task was committed atomically:

1. **Task 1: The scan and the atomic write — migrate up, leave the source alone** - `58461a6` (feat)
2. **Task 2: Unit-pin the scan's four edge cases and the write's mode** - `543a86c` (test)
3. **Task 3: Verify-then-delete, and the migration pinned at the CLI (plus the sweep read-only resolution)** - `3553542` (feat)

_No separate plan-metadata commit was needed beyond this SUMMARY's own commit, per the standard final-commit step below._

**Checkpoint:** The plan's `checkpoint:decision` gate ("confirm the shape of the irreversible credential delete before it is built") was resolved by the operator BEFORE this execution run: **`delete-immediately`** — verify then delete, in the same resolution. `_migrate_once` implements exactly this shape; the checkpoint was not re-opened.

## Files Created/Modified

- `operator-claude-plugin/scripts/durable_paths.py` - `_atomic_write_0600`, `_VERSION_DIR_RE`, `_version_key`, `_newest_sibling_holding`, `_migrate_once`; step 5 wired into both resolvers behind `allow_migration`
- `operator-claude-plugin/scripts/config_gate.py` - `config_path()` and `load_config()` gained `allow_migration: bool = True`, threaded to `durable_paths.resolve_config_path`
- `operator-claude-plugin/scripts/sweep_entry.py` - `_load_config_no_migration()` added as `_cli_main`'s default loader; always resolves with `allow_migration=False`
- `operator-claude-plugin/tests/test_durable_paths.py` - 7 new unit tests for the scan's four edge cases and the write helper's mode/cleanup
- `operator-claude-plugin/tests/test_config_gate.py` - `_run_cli` extended with `versions=`/`current=` for multi-version cache layouts; 5 new entrypoint tests for the migration, idempotence, version-bump, and unwritable-home behaviors
- `operator-claude-plugin/tests/test_sweep_read_only.py` - `FS_WRITE_VERBS`/`DURABLE_PATHS_WRITE_FUNCTIONS`, `fs_write_verb_sites`, `durable_paths_write_call_confinement`, 3 new tests (the static guard, its synthetic proof-it-bites, and the behavioral migration-abstention test)

## Deviations from Plan

### Auto-fixed Issues

**1. [Blocking constraint, surfaced by the orchestrator after planning] Threaded `allow_migration` through the resolution chain and gave the sweep a dedicated read-only loader**
- **Found during:** Pre-execution review (flagged in the execution context before Task 3 began)
- **Issue:** `config_gate` imports `durable_paths` (33-01), which put `durable_paths` in `sweep_entry`'s transitive import closure. Task 3 adds `_migrate_once` — a filesystem write AND an irreversible delete of a file holding `webhook_secret`/`n8n_api_key` — into that same module. `test_sweep_read_only.py`'s existing write-verb guard is HTTP-verb-shaped (`post`/`put`/`patch`/`delete` as HTTP methods) and cannot see `open(...,"w")`/`os.replace`/`Path.unlink`/`os.chmod`; its 33-01 comment asserting durable_paths "cannot be a write vector" was about to become false without anyone re-checking it.
- **Fix:** Added `allow_migration: bool = True` to `resolve_config_path`/`resolve_state_path` and `config_gate.config_path`/`load_config`. `sweep_entry._load_config_no_migration` (the module's default config loader) always calls `load_config(allow_migration=False)`, so the sweep's own run — cron-triggered or on-demand via `/operator-claude-plugin:backend-sweep` — never scans siblings, never writes the durable home, and never deletes anything. When migration is genuinely available but disabled, the existing `sweep_not_configured` notice fires instead — loud, matching this project's established failure-visibility design, not a silent capability widening.
- **Files modified:** `operator-claude-plugin/scripts/config_gate.py`, `operator-claude-plugin/scripts/sweep_entry.py` (both outside this plan's original `files_modified` list — a direct, necessary consequence of Task 3's own migration/delete landing in a module the sweep imports)
- **Verification:** `test_sweep_read_only.py::test_the_sweep_does_not_migrate_even_when_a_sibling_holds_a_config` (behavioral) and `test_the_only_reachable_filesystem_writes_are_the_named_migration_functions` (static) both pass; full plugin suite green at 938/5.
- **Committed in:** `3553542` (Task 3 commit)

**2. [Blocking constraint, same origin] Extended `test_sweep_read_only.py` with a filesystem-write AST guard**
- **Found during:** Same pre-execution review
- **Issue:** The existing compensating assertion (`test_the_only_reachable_write_verb_is_the_named_status_post`) only ever scanned for HTTP write verbs. A guard whose stated rationale ("durable_paths cannot be a write vector") had silently gone false was judged worse than no guard at all.
- **Fix:** Added `FS_WRITE_VERBS = {"replace", "unlink", "chmod", "fdopen"}`, `fs_write_verb_sites()` (mirroring the existing `write_verb_sites()`), and `durable_paths_write_call_confinement()` (a function-level check that the writes live only inside `_atomic_write_0600`/`_migrate_once`). `.replace` is narrowed to `os.replace(...)` specifically — an unqualified attribute-name match would have false-positived on `n8n_read.py`'s `started.replace(tzinfo=...)` (the ordinary `datetime` method), which the first run of the new test caught immediately. Also added a synthetic "proof the guard bites" test and the behavioral migration-abstention test described above.
- **Files modified:** `operator-claude-plugin/tests/test_sweep_read_only.py`
- **Verification:** `test_sweep_read_only.py` full file: 14 passed. Full plugin suite green.
- **Committed in:** `3553542` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3 — blocking issues the plan's own Task 3 action would otherwise have introduced), both from the same source (the blocking constraint identified in the execution context, not discovered independently during coding).
**Impact on plan:** Necessary to keep NOTICE-05's "the sweep has no code path to a mutation" guarantee true after Task 3's own required irreversible delete; no scope creep beyond what closing that gap required, no change to `_migrate_once`'s design or the checkpoint-confirmed delete-immediately shape.

## Issues Encountered

- The first run of the new filesystem-write guard false-positived on `n8n_read.py`'s `started.replace(tzinfo=timezone.utc)` — a plain attribute-name match for `replace` also catches the ordinary `str`/`datetime` method, not just `os.replace`. Narrowed the check to require the qualifier be the bare name `os`. No other false positives found; `unlink`/`chmod`/`fdopen` do not otherwise collide with any name reachable in the sweep's closure.
- No other implementation surprises — every other acceptance criterion in the plan was met on the first pass.

## User Setup Required

None — no external service configuration required. This plan is entirely local filesystem/path-resolution logic and its test coverage.

**Open Question 1 from 33-RESEARCH.md** (whether writing into `~/.claude/plugins/data/<id>/` triggers a Bash-tool "sensitive location" permission prompt on the FIRST interactive migration write) remains unobserved live — this plan's own design (degrade-never-refuse, `allow_migration` gating) already covers the failure mode regardless of the answer, and no live migration write was performed against the real plugin install during this execution.

## Next Phase Readiness

- `resolve_state_path()` now has the identical `allow_migration` contract and step-5 migration as `resolve_config_path()`, fully implemented and unit-tested via the same `_migrate_once`/`_newest_sibling_holding`/`_atomic_write_0600` machinery — but `artifact_store.py` does not import it yet. That wiring is 33-03's task, as originally planned.
- `config_gate.load_config`'s new `allow_migration` parameter defaults to `True`, so every pre-existing caller (contact-upload preflight, status, control, review, enrichment) is unaffected and continues to migrate when appropriate — only `sweep_entry` opts into the read-only mode.
- The filesystem-write AST guard in `test_sweep_read_only.py` will need the SAME review discipline `ALLOWED_MODULES`/`ALLOWED_VERB_SITES` already carry: if 33-03 wires `artifact_store` into the sweep's closure for any reason, its own migration path (via `resolve_state_path`) would need the identical `allow_migration=False` treatment before it could pass `test_the_sweep_import_closure_is_exactly_the_allowlist`.

## Self-Check: PASSED

- FOUND: `operator-claude-plugin/scripts/durable_paths.py`
- FOUND: `operator-claude-plugin/scripts/config_gate.py`
- FOUND: `operator-claude-plugin/scripts/sweep_entry.py`
- FOUND: `operator-claude-plugin/tests/test_durable_paths.py`
- FOUND: `operator-claude-plugin/tests/test_config_gate.py`
- FOUND: `operator-claude-plugin/tests/test_sweep_read_only.py`
- FOUND commit `58461a6`
- FOUND commit `543a86c`
- FOUND commit `3553542`

---
*Phase: 33-durable-operator-state*
*Completed: 2026-08-04*
