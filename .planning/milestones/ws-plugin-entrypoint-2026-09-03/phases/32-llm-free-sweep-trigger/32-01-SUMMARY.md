---
phase: 32-llm-free-sweep-trigger
plan: 01
subsystem: operator-claude-plugin
tags: [sweep-trigger, cron, launchd, llm-free, notice-03, shell-wrapper, two-sided-test]

requires:
  - phase: 29
    plan: 06
    provides: "RB-8's live finding that the claude -p cron trigger fails silently (expired credential, node off cron's PATH) and that sweep_entry.py under env -i with zero credentials produces byte-identical notice JSON, exit 0"
provides:
  - "operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh — the LLM-free trigger: POSIX sh, three positional args (plugin root, python, log path), runs sweep_entry.py directly, no LLM/credential anywhere in the path"
  - "operator-claude-plugin/tests/test_sweep_trigger_contract.py — the two-sided pin between the wrapper's embedded -c programs and sweep_entry.py's real printed output"
  - "operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md — rewritten around the wrapper: venv step, /bin/sh invocation, loud-failure guarantee"
  - "29-HOST-PROBE.md's dated D-01 amendment — the host is now cron/launchd -> the plugin's own Python, with the reason the original probe misled"
affects:
  - "32-02 — the live RB-8 re-run against this trigger is the phase's exit gate; this plan does not seal NOTICE-03"

tech-stack:
  added: []
  patterns:
    - "two-sided contract pin (test_control_flag_parity.py's idiom): the wrapper is read as TEXT, its own embedded -c python programs are extracted by regex and exec()'d in-process against a real sweep_entry._cli_main() return value, never shelled out and never touching osascript"
    - "loud-failure-by-construction: every non-healthy exit path (bad arity, python failure, unreadable output) posts a banner AND returns non-zero; the healthy path is the only one with neither"
    - "allowlist reuse over allowlist duplication: the new contract test imports ALLOWED_MODULES and _skill_capabilities from test_sweep_read_only rather than re-declaring either"

key-files:
  created:
    - operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh
    - operator-claude-plugin/tests/test_sweep_trigger_contract.py
  modified:
    - operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md
    - operator-claude-plugin/tests/test_sweep_read_only.py
    - operator-claude-plugin/README.md
    - operator-claude-plugin/CHANGELOG.md
    - .planning/workstreams/plugin-entrypoint/phases/29-notices-unattended-sweep/29-HOST-PROBE.md
    - .planning/workstreams/plugin-entrypoint/STATE.md

key-decisions:
  - "Guard the wrapper's arity BEFORE any assignment referencing $1/$2/$3: under `set -u` an unbound positional parameter exits with no banner at all — exactly the silent death this phase removes."
  - "The log path is captured into a named variable (LOG=\"$3\") before stamp() is defined, because a POSIX sh function call replaces $1/$2/$3 with its OWN arguments for the duration of the call — referencing the script's $3 from inside a function called as `stamp \"message\"` would silently read empty instead of the log path."
  - "Removed the `grep -c` line originally drafted for a separate posted-notification counter: `-c '...'` is also the shell's own syntax for invoking the count/headline python programs, and a third occurrence would have broken the contract test's assumption that lv-sweep-run.sh contains exactly two extractable -c programs. The final stamp reuses $COUNT instead, since every notice sweep_entry.py produces always carries a non-empty headline."
  - "The wrapper's own prose (SWEEP-CRON-TEMPLATE.md, the wrapper's header comment) avoids the literal substring `claude -p` even when describing what was removed, since test_sweep_trigger_contract.py and test_sweep_read_only.py's rewritten assertion both check for its total ABSENCE from the shipped artifacts, not just its absence as an invocation."

metrics:
  duration: ~45min
  completed: 2026-08-03
status: complete

actuals:
  tokens: 8592
  tasks: 3
  commits: 3
---

# Phase 32 Plan 01: LLM-Free Sweep Trigger Summary

Replaces the sweep's unattended cron/launchd trigger with a deterministic `sh` wrapper that
runs `sweep_entry.py` directly — no LLM, no Anthropic credential, nothing in the path that
can expire — and makes the trigger's own inability to run loud for the first time. Rewrites
the install template around it, amends `29-HOST-PROBE.md`'s D-01 host decision in place, and
pins the wrapper's contract with `sweep_entry.py`'s real printed output from both ends.

## What was built

**Task 1 (tracer) — the wrapper, end to end, pinned against `sweep_entry.py`'s real output**
(`e3847db`)

- `operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh`: POSIX `sh`, `set -u`, three
  positional arguments (plugin root, python interpreter, log path). Arity is checked before
  any assignment touches `$1`/`$2`/`$3` — under `set -u` an unbound positional parameter
  would otherwise exit silently, which is exactly the failure mode this phase removes.
  `banner()` is the file's single `osascript` call site; `stamp()` appends one timestamped
  line per call. Body: run `sweep_entry.py` via `cd "$1" && "$2" scripts/sweep_entry.py
  2>&1`, capture `RC`; on non-zero, stamp and banner the failure and exit `$RC`; otherwise
  count notices with `"$2" -c '<program>'` (never a second interpreter) — `-1` is the
  unreadable sentinel, distinct from `0` (healthy); count `0` writes exactly one stamped
  line and exits 0, no banner, no `$OUT` (NOTICE-04's silence preserved); otherwise stamps
  the count and the full JSON, extracts each notice's `headline` with a second `"$2" -c`
  program, and posts one banner per non-empty headline, escaping backslash before double
  quote and truncating to 200 chars (T-32-01) before interpolating into the `osascript`
  string.
- `operator-claude-plugin/tests/test_sweep_trigger_contract.py`: extracts the wrapper's two
  embedded `-c` programs as text (a non-greedy regex up to the shell's own closing quote —
  neither program contains a literal single quote) and `exec()`s them in-process with a
  stubbed `sys.argv`, never shelling out and never touching `osascript`. Drives the five
  `<behavior>` cases (one notice → count 1 and verbatim headline, `[]` → 0, a traceback
  fragment → -1, `"{}"` → -1), the one-notice/headline cases from a real
  `sweep_entry._cli_main(load_config=<raises ConfigError>)` call rather than a hand-written
  fixture. Structural pins: shebang/`set -u`, the wrapper's only named script is
  `scripts/sweep_entry.py` (subset of `ALLOWED_MODULES`, imported from
  `test_sweep_read_only` rather than re-declared), total absence of `claude -p`,
  `--allowedTools`, `ANTHROPIC_API_KEY`, `anthropic`, exactly one `osascript` occurrence,
  both count/headline programs invoked through `"$2" -c`, the escape ordering
  (backslash before quote), and that the healthy/failure/unreadable branches each contain
  exactly what criterion 2 requires (banner + non-zero exit, or neither).

**Task 2 — rewrite `SWEEP-CRON-TEMPLATE.md` around the wrapper, and its two template
assertions** (`9a4cbb7`)

- `SWEEP-CRON-TEMPLATE.md`: Step 1 is now creating a dedicated venv and installing this
  plugin's `requirements.txt` into it (the system `python3` lacks `requests`, measured, not
  assumed) instead of saving a prompt file. Step 2 installs `cron`/`launchd` pointed at
  `lv-sweep-run.sh` through `/bin/sh` with its three positional arguments — deliberate,
  since it doesn't depend on the executable bit surviving a marketplace clone or an
  `rsync`. The "known, accepted gap" paragraph is replaced with the loud-failure guarantee:
  a trigger that runs and cannot complete now banners and exits non-zero; a trigger never
  installed is still silent, which is exactly why the second install step exists. The
  cadence section (probes all three provider balance endpoints unconditionally; cadence is
  the only dial bounding the cost, D-19) is kept verbatim.
- `test_sweep_read_only.py`: renamed and rewrote
  `test_sweep_cron_template_reproduces_the_a1_invocation_and_a5_delivery` to
  `..._reproduces_the_wrapper_invocation_and_a5_delivery` — the old assertions required
  `claude -p` and the exact `--allowedTools` flag, precisely what RB-8 proved fails
  silently under real cron. The rewritten test asserts the new invocation's presence
  (`lv-sweep-run.sh`, `/bin/sh`, the wrapper's argument placeholders, a `.log` path,
  `osascript`, the notice-list-gated banner) AND the old LLM invocation's total absence,
  with a dated docstring citing RB-8.
  `test_sweep_cron_template_states_the_cadence_mediated_no_credit_property` passes
  unchanged, confirming the D-19 reasoning survived the rewrite intact.

**Task 3 — amend D-01, the two-part install, the changelog, and state** (`25a084f`)

- `29-HOST-PROBE.md`: the original §A1 verdict block, its verbatim probe output, and the
  "Hosts that do NOT work" table are all preserved exactly as recorded on 2026-08-03. A
  dated `⚠ SUPERSEDED` amendment (matching the file's existing amendment idiom, seen
  elsewhere in `OPERATOR-RUNBOOK.md`) is added at the head of §A1, mirrored in the
  "Consequence for D-01" paragraph, and in item 1 of "What 29-03…06 may rely on" — each
  states the new host (cron/launchd → the plugin's own Python via `lv-sweep-run.sh`), why
  the original probe misled (run from an interactive shell, which inherits a live session's
  credentials and PATH — it proved headless, not unattended-under-cron), and names it the
  same class of error as the stored-vs-running reload gap: verification one layer away from
  the thing it claimed to verify.
- `README.md`: rewrote step 2 of "Installing the sweep is two steps, not one" to describe
  the wrapper and its venv creation as one admin task, and to distinguish
  installed-but-broken (now loud: banner + non-zero exit) from never-installed (still
  silent, and still the first thing to check). Added `skills/backend-sweep/` with its three
  files to the Layout block, which previously listed only `contact-upload` and
  `enrich-records`.
- `CHANGELOG.md`: one `[Unreleased]` → `### Changed` entry stating the trigger no longer
  runs through an LLM, the measured fact behind that (byte-identical notice JSON under
  `env -i` with zero credentials), and the install cost (a python with this plugin's
  `requirements.txt`).
- `STATE.md`: two surgical hand-edits (no `state.update-progress` run — this repo's ROADMAP
  concatenates three milestones and the tool miscounts against it) recording phase 32's
  build as complete and gated on 32-02, one in `## Current Position`, one in the Session
  Continuity autonomous-front bullet list. `current_phase` (23) and `REQUIREMENTS.md`'s
  NOTICE-03 traceability row (BLOCKED) are both left untouched, per the plan's explicit
  instruction — flipping either here would itself be the "verification one layer away from
  the claim" this phase exists to correct.

## Deviations from Plan

None — the plan executed as written. Three small implementation choices were made within
"Claude's Discretion" per `32-CONTEXT.md` (wrapper filename and argument conventions were
already pinned as proven; the internal `LOG` variable and the reused `$COUNT` for the final
posted-count stamp are the only genuinely new choices, both recorded above under
key-decisions).

## Verification

| Check | Result |
|---|---|
| `.venv/bin/python -m pytest operator-claude-plugin/tests/test_sweep_trigger_contract.py -q` | 14 passed |
| `.venv/bin/python -m pytest operator-claude-plugin/tests/test_sweep_read_only.py -q` | 11 passed (baseline count, unchanged) |
| `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` | **903 passed, 5 skipped** (889 baseline + 14 new) |
| `node --test tests/n8n/*.test.mjs` (file form) | 550 passed, 0 fail — untouched, run for collateral-damage check |
| `sh -n lv-sweep-run.sh` | syntax OK (parse only — the phase's hard invariant forbids executing the wrapper, which would reach the real `osascript` call) |
| `grep -c "lv-sweep-run.sh"` across README/CHANGELOG/29-HOST-PROBE.md | 2 / 1 / 3 — all present |
| No `crontab` edited, no notification posted, no network call made | confirmed — the only executions performed were `sh -n` (parse-only) and pytest/node test runs |

## Known Stubs

None. The wrapper is the real, shipped trigger — not a placeholder pending 32-02's live
proof. 32-02's live RB-8 re-run is the phase's exit gate, not a stub in this plan's own
scope; `REQUIREMENTS.md`'s NOTICE-03 row is deliberately left BLOCKED until that gate runs.

## Threat Flags

None beyond the plan's own threat register (T-32-01 through T-32-05, T-32-SC), all of which
are addressed as designed: T-32-01 (banner injection) mitigated by the backslash-then-quote
escape + truncation, pinned by `test_escape_program_escapes_backslash_before_double_quote`;
T-32-02 (silent trigger death) mitigated by the loud-failure branches, pinned by the
failure/unreadable branch structural tests; T-32-03 (capability-surface widening via shell)
mitigated by reusing `ALLOWED_MODULES` for the wrapper's named-script check.

## Self-Check: PASSED

- `operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh` — FOUND, executable
- `operator-claude-plugin/tests/test_sweep_trigger_contract.py` — FOUND
- `operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md` — FOUND, rewritten
- `operator-claude-plugin/tests/test_sweep_read_only.py` — FOUND, rewritten test present
- `operator-claude-plugin/README.md` — FOUND, Layout block lists `skills/backend-sweep/`
- `operator-claude-plugin/CHANGELOG.md` — FOUND, `[Unreleased]` entry present
- `.planning/workstreams/plugin-entrypoint/phases/29-notices-unattended-sweep/29-HOST-PROBE.md` — FOUND, three amendment blocks present
- `.planning/workstreams/plugin-entrypoint/STATE.md` — FOUND, two surgical edits present
- commits `e3847db`, `9a4cbb7`, `25a084f` — all FOUND in `git log`
- no file deletions in any commit (`git diff --diff-filter=D` empty on all three)
