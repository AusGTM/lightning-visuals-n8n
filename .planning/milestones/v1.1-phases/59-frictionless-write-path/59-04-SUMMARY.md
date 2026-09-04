---
phase: 59-frictionless-write-path
plan: 04
subsystem: operator-facing-disclosure
tags: [bash, pytest, claude-code-hooks, operator-plugin]

requires:
  - phase: 59-03
    provides: "the retired pre-emptive two-lane disclosure this note does not duplicate or contradict"
provides:
  - "operator-claude-plugin/hooks/ -- the plugin's first hooks directory"
  - "a SessionStart hook that discloses, once per session and non-blockingly, that a run continues to completion once started"
  - "an automated subprocess contract test proving the note's content without a Claude Code host"
affects: []

actuals:
  tokens: 2266
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Claude Code plugin SessionStart hook: hooks/hooks.json declares the matcher and ${CLAUDE_PLUGIN_ROOT}-relative command; hooks/<name>.sh does the work, zero dependencies, unconditional exit 0"
    - "Hook stdout is written as an instruction for Claude to relay in its own words (the initialize/SKILL.md relay convention), not assumed to be echoed verbatim to the operator"

key-files:
  created:
    - operator-claude-plugin/hooks/hooks.json
    - operator-claude-plugin/hooks/session-start.sh
    - operator-claude-plugin/tests/test_session_start_hook.py
  modified:
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md

key-decisions:
  - "Wrapped the note's prose across output lines for readability; the contract test normalizes stdout whitespace (`\" \".join(stdout.split())`) before substring-matching each fact, so a line wrap inside a pinned phrase (e.g. 'continues until it is\\ndone') does not produce a false test failure."
  - "The note leads with an explicit instruction addressed to Claude ('Relay the following... in your own words... without asking anything'), not to the operator -- per planner assumption 2, since this plugin's own initialize/SKILL.md convention treats hook/command stdout as context for Claude to paraphrase, not guaranteed verbatim display."

requirements-completed: [D-59-06]

coverage:
  - id: D1
    description: "bash operator-claude-plugin/hooks/session-start.sh exits 0 and prints all three D-59-06 facts, with no question mark, under both a normal and a deliberately minimal environment"
    requirement: D-59-06
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_session_start_hook.py::test_script_prints_all_three_d_59_06_facts, ::test_script_works_with_a_deliberately_minimal_environment, ::test_script_output_has_no_question_mark"
        status: pass
    human_judgment: false
  - id: D2
    description: "hooks.json parses as JSON, declares a SessionStart matcher covering startup and resume, references ${CLAUDE_PLUGIN_ROOT}, and points at a script that actually exists on disk"
    requirement: D-59-06
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_session_start_hook.py::test_hooks_json_declares_a_sessionstart_entry_pointing_at_the_real_script"
        status: pass
    human_judgment: false
  - id: D3
    description: "the hook does not reference dispatch_plan, write_grant, or chunking internals -- the dispatch loop stays grant-unaware, and test_a_revocation_midway_does_not_stop_a_running_dispatch is untouched"
    requirement: D-59-06
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_session_start_hook.py::test_script_does_not_reach_into_dispatch_or_grant_internals"
        status: pass
    human_judgment: false
  - id: D4
    description: "plugin released as 0.23.0 with a CHANGELOG entry naming the hook, its three facts, and stating plainly that revocation semantics did not change"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_plugin_manifest.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "the note's DELIVERY by a live Claude Code host is recorded as an unperformed manual check, not claimed as covered"
    verification: []
    human_judgment: true

duration: 20min
completed: 2026-08-28
status: complete
---

# Phase 59 Plan 04: D-59-06 SessionStart disclosure hook Summary

**Shipped the plugin's first `hooks/` directory: a `SessionStart` hook that tells the operator, once per session and non-blockingly, that once enrichment and writing to HubSpot start the run continues to completion -- a revoke refuses the NEXT send, and a dispatch already running finishes its remaining chunks -- proven by a subprocess contract test rather than by starting a Claude session, and released as plugin 0.23.0.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-08-28
- **Completed:** 2026-08-28
- **Tasks:** 2
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments

- `operator-claude-plugin/hooks/hooks.json` -- follows the verified installed-plugin
  precedent exactly: a `SessionStart` entry with `matcher: "startup|resume"` invoking
  `bash "${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh"`. No `plugin.json` key change was
  needed for hook discovery, matching `test_plugin_manifest.py`'s own assertion that
  `hooks/` belongs at the plugin root alongside `skills/`, `commands/`, `agents/`.
- `operator-claude-plugin/hooks/session-start.sh` -- a dependency-free bash script
  (`set -eu`, unconditional exit 0) that prints a note carrying exactly three facts:
  the run continues until done once started, a revoke refuses the next send, and a
  dispatch already running finishes its remaining chunks (a revoke arriving mid-run
  does not stop it). The output leads with an instruction addressed to Claude to relay
  the note in its own words, following the `initialize/SKILL.md` relay convention. A
  comment block at the top names D-59-06, the date, and states the note exists
  *instead of* a grant-aware, chunk-granular dispatch loop -- so a future reader
  wondering why revocation isn't chunk-granular finds the answer at the artifact that
  replaced it. Verified working with `env -i PATH="$PATH"` (the fresh-install case).
- `operator-claude-plugin/tests/test_session_start_hook.py` -- six tests: hooks.json
  structural/content validity (including confirming the referenced script actually
  exists on disk, not just a JSON-shape check), executable-bit presence, the
  behavioural subprocess run asserting all three facts are present, the same run under
  a minimal environment, a no-question-mark property check, and a structural check
  that the script never references `dispatch_plan`, `write_grant`, or `chunking`.
- `plugin.json` bumped 0.22.0 -> 0.23.0; `CHANGELOG.md` gained a 0.23.0 entry naming
  the hook, its three disclosed facts, and stating explicitly that revocation
  semantics are UNCHANGED -- `dispatch_plan` stays grant-unaware and the revocation
  test named above is untouched. Also records that the note's DELIVERY by a live
  Claude Code host is not covered by any automated check here (see below).

## Task Commits

Each task was committed atomically:

1. **Task 1: The SessionStart hook and its contract test** - `1aba55c` (feat)
2. **Task 2: Version bump and CHANGELOG, stating plainly what the note does not do** - `adabc9b` (chore)

## Files Created/Modified

- `operator-claude-plugin/hooks/hooks.json` - new, the SessionStart wiring
- `operator-claude-plugin/hooks/session-start.sh` - new, executable, the note itself
- `operator-claude-plugin/tests/test_session_start_hook.py` - new, subprocess contract test
- `operator-claude-plugin/.claude-plugin/plugin.json` - version 0.22.0 -> 0.23.0
- `operator-claude-plugin/CHANGELOG.md` - new 0.23.0 entry

## Decisions Made

- The note's prose is hand-wrapped for readability across the script's output lines,
  which put a line break inside the pinned phrase "continues until it is done." The
  first draft of the contract test asserted the exact substring against raw stdout and
  failed on that wrap. Fixed by normalizing stdout whitespace (`" ".join(stdout.split())`)
  before each substring assertion, rather than reflowing the script's prose to avoid the
  wrap -- the test should tolerate cosmetic line-wrapping, not dictate it.
- Followed planner assumption 2 exactly: the script's stdout leads with an instruction
  addressed to Claude ("Relay the following to the operator... in your own words..."),
  not text written as if a human will read it verbatim. This matches
  `initialize/SKILL.md` step 1's established convention in this same plugin
  ("Read its output back to the operator in your own words").

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered

`git commit -m "$(cat <<'EOF' ... EOF)"` failed on the Task 2 commit message with a
shell parsing error ("unexpected EOF while looking for matching quote") despite the
same pattern working for Task 1. Root-caused to the interactive shell wrapper in this
environment rather than the message content (no unmatched quote in the text). Worked
around by writing the message to a scratch file and using `git commit -F <file>`,
which succeeded cleanly. No plan or code impact.

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness

- D-59-06 is fully closed: the note's content is shipped and automatically verified;
  its DELIVERY by a live Claude Code host remains the one deliberately unperformed
  manual check named in `59-VALIDATION.md` ("The session-start note actually appears").
  That check requires starting a real Claude Code session with the plugin installed
  and is out of scope for an automated executor.
- `dispatch_plan` and `chunking.py` are untouched by this plan; the revocation test
  `test_a_revocation_midway_does_not_stop_a_running_dispatch` was never opened.
- Plugin ships at 0.23.0; the marketplace clone needs a fetch before the operator's
  installed copy sees the update (per this repo's known plugin-release pattern).
- No blockers for the remaining Phase 59 plans (59-05, 59-06 per `59-VALIDATION.md`'s
  ownership table).

---
*Phase: 59-frictionless-write-path*
*Completed: 2026-08-28*
