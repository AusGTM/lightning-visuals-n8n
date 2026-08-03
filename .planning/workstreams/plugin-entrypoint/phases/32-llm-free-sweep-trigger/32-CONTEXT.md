# Phase 32: LLM-Free Sweep Trigger - Context

**Gathered:** 2026-08-03
**Status:** Ready for planning
**Source:** PRD Express Path (`.planning/todos/pending/2026-08-03-sweep-cron-credentials-block-notice-03.md`, solution section)

<domain>
## Phase Boundary

Replace the sweep's unattended trigger: `claude -p` out, a shipped `sh` wrapper running
`sweep_entry.py` directly in. Rewrite the install template, amend the host decision, pin the
wrapper↔python contract two-sided. Nothing about the sweep's conditions, notices, or read-only
guarantees changes — 29-05's logic is untouched.
</domain>

<decisions>
## Implementation Decisions

### Settled and proven 2026-08-03 — do not relitigate
- **The trigger contains no LLM.** `sweep_entry.py` under `env -i HOME=... PATH=/usr/bin:/bin`
  with zero credentials emits the byte-identical notice JSON, exit 0. The `claude -p` wrapper
  contributed only re-printing that JSON and shelling `osascript`, while being the sole source of
  the observed failure (expired token/empty refresh_token, `node` off cron's PATH) — and it failed
  SILENTLY.
- **The wrapper shape is proven.** A ~30-line `sh` script: run the python, parse the JSON count,
  healthy → one run-stamp log line and nothing else (NOTICE-04 silence), notices → full JSON to the
  log then one `osascript` banner per notice headline, failure → non-zero exit AND a banner saying
  the sweep itself is broken. Fired under REAL cron with no session open at 22:54:21 (2-min test
  cadence); loud-failure path demonstrated by pointing it at a python lacking `requests`.
- **Rejected alternatives, recorded so they stay rejected:** API key in cron's env, launchd GUI
  session for Keychain access, backend-hosted scheduler. All treat the symptom; the LLM simply does
  not belong in a deterministic path.

### Contracts to honor
- The wrapper takes three arguments: plugin root, python path, log path. cron line stays one line.
- Healthy output is EXACTLY one stamped line — no heartbeat, no all-clear (NOTICE-04).
- Banner text ≤ one line (29-HOST-PROBE §A5 budget); headline used verbatim, one banner per notice,
  double quotes escaped before interpolation into osascript.
- The venv: the plugin's own `requirements.txt` (requests, PyYAML, openpyxl) — system python3
  lacks requests, measured. The venv-creation step joins NOTICE-05's two-part admin install docs.
- Not a breach of "Claude is the only interface": that governs operator surfaces; NOTICE-03 is by
  definition when nobody is watching.

### Claude's Discretion
- Wrapper filename and exact argument/env conventions (positional args proven; keep or improve).
- Whether the wrapper also stamps healthy runs into the log (the proven draft does — keep unless a
  reason emerges).
- Test placement/naming; how the shell side is read (as text, per the repo's two-sided idiom).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Evidence and decision trail
- `.planning/todos/pending/2026-08-03-sweep-cron-credentials-block-notice-03.md` — the PRD; its Solution section carries the proof and the implementation checklist
- `.planning/workstreams/plugin-entrypoint/phases/29-notices-unattended-sweep/29-06-FINDINGS.md` — RB-8's failure, verbatim errors
- `.planning/workstreams/plugin-entrypoint/phases/29-notices-unattended-sweep/29-HOST-PROBE.md` — D-01 host decision to amend, §A5 banner budget

### Artifacts being changed
- `operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md` — rewritten around the wrapper
- `operator-claude-plugin/skills/backend-sweep/SKILL.md` — references to the trigger, if any
- `operator-claude-plugin/scripts/sweep_entry.py` — the CLI whose output shape the wrapper consumes (`_cli_main`, added 29-06)
- `operator-claude-plugin/README.md`, `CHANGELOG.md` — NOTICE-05's two-part install gains the venv step; changelog entry

### Patterns
- `operator-claude-plugin/tests/test_control_flag_parity.py` — read-the-other-side-as-text two-sided idiom
- `operator-claude-plugin/tests/test_sweep_read_only.py` — the import-graph guard that must stay green
</canonical_refs>

<specifics>
## Specific Ideas

- The proven wrapper draft lives in the session scratchpad (`lv-sweep-run.sh`) and in the todo's
  Solution section by description; reproduce it as a shipped artifact, don't reinvent.
- Wrapper JSON parse uses the python it was handed (`"$PYTHON" -c 'import json...'`), never a
  second interpreter.
- After this ships: re-run RB-8 against the new trigger (silence check will also need the 1173
  error to have aged out of the 100-row window, or the lookback todo fixed — do not conflate the
  two; RB-8's re-run is the phase's exit gate, executed by the orchestrator, not the executor).
</specifics>

<deferred>
## Deferred Ideas

- The windowless 100-row lookback / unacknowledgeable repeat notices — separate todo
  (`2026-08-03-sweep-lookback-has-no-time-window`), not this phase.
- The id→name workflow mapping in notice text — same separate todo.
- launchd variant of the template (cron proven; launchd text may be updated for parity but needs no
  live proof this phase).
</deferred>

---

*Phase: 32-llm-free-sweep-trigger*
*Context gathered: 2026-08-03 via PRD Express Path*
