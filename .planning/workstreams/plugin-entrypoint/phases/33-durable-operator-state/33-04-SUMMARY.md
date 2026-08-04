---
phase: 33-durable-operator-state
plan: 04
subsystem: operator-claude-plugin
tags: [docs, changelog, release, plugin-manifest, operator-runbook, durable-storage]

requires:
  - phase: 33-01
    provides: "durable_paths.py resolution steps 1-4"
  - phase: 33-02
    provides: "durable_paths.py step 5 (sibling-scan migration, verify-then-delete, allow_migration contract)"
  - phase: 33-03
    provides: "artifact_store.state_path() and init_check.py wired to the same durable_paths authority"
provides:
  - "README.md and CHANGELOG.md no longer describe the hand-copy of operator.local.json between install directories — the standing PLUGIN-02/PLUGIN-03 doc violation is closed"
  - "test_no_shipped_document_instructs_a_manual_config_copy — the doc-side pin matching 33-02's code-side fix"
  - "plugin.json at 0.7.0, cut in the same commit as the CHANGELOG's [0.7.0] section (release checklist steps 1-2)"
  - "RB-10 in OPERATOR-RUNBOOK.md — the exit gate's exact steps, ready for the operator to walk"
  - "33-FINDINGS.md — the live-migration open question recorded verbatim, pending the operator's observation"
affects: ["Phase 33 close (blocked on RB-10)"]

actuals:
  tokens: 7155
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Doc-side regression test mirroring a code-side fix: a substring assertion over README.md/CHANGELOG.md pins the same guarantee test_the_sweep_import_closure_is_exactly_the_allowlist-style code guards already pin for behavior"

key-files:
  created:
    - .planning/workstreams/plugin-entrypoint/phases/33-durable-operator-state/33-FINDINGS.md
  modified:
    - operator-claude-plugin/README.md
    - operator-claude-plugin/CHANGELOG.md
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/scripts/review_queue.py
    - operator-claude-plugin/skills/enrich-records/SKILL.md
    - operator-claude-plugin/tests/test_plugin_manifest.py
    - .planning/workstreams/plugin-entrypoint/OPERATOR-RUNBOOK.md

key-decisions:
  - "durable_paths.py's own two config/operator.local.json references (lines 13, 86) were left alone — they are accurate internal docstrings describing the literal legacy resolution path (resolution step 4), not operator-facing instructions to hand-copy anything. The plan's read_first list named only review_queue.py:253 and enrich-records/SKILL.md:66 as the 'two more strings'; durable_paths.py wasn't one of them, and fixing it would make the code comment wrong rather than the doc right."
  - "Task 3 (checkpoint:human-verify, gate=blocking) is not walked by this execution. Per this plan's explicit boundary, the executor's job was to write RB-10 into OPERATOR-RUNBOOK.md and record the open question verbatim in 33-FINDINGS.md — not to touch ~/.claude/plugins/ or perform any migration against the operator's real webhook_secret/n8n_api_key. STATE.md, ROADMAP.md and REQUIREMENTS.md are deliberately left untouched, matching the precedent set by 28-02-SUMMARY.md ('STATE.md deliberately not touched — plan incomplete and an operator holds it uncommitted')."

requirements-completed: []

coverage:
  - id: D1
    description: "No shipped document (README.md, CHANGELOG.md, review_queue.py's operator-facing no-link message, enrich-records/SKILL.md) tells the operator to move operator.local.json by hand between install directories"
    requirement: "PLUGIN-02"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_plugin_manifest.py::test_no_shipped_document_instructs_a_manual_config_copy"
        status: pass
    human_judgment: false
  - id: D2
    description: "Plugin 0.7.0 is cut: version bump and CHANGELOG entry landed in one commit (24c2f16), so Claude Desktop's Update-button comparison actually sees a change"
    verification:
      - kind: other
        ref: "git show --stat 24c2f16 — lists both .claude-plugin/plugin.json and CHANGELOG.md"
        status: pass
    human_judgment: false
  - id: D3
    description: "RB-10 exists in OPERATOR-RUNBOOK.md with the exact steps to refresh the clone, update, and observe one real migration, including the absolute prohibition on suppressing a permission prompt"
    verification: []
    human_judgment: true
    rationale: "RB-10 is a document, not code — its correctness (does it actually lead an operator to a conclusive observation?) can only be judged by walking it, which this executor is explicitly barred from doing against real operator state"
  - id: D4
    description: "One real migration has been performed and observed on this host, with whether a 'sensitive location' permission prompt fired written down verbatim"
    requirement: "STATUS-05"
    verification: []
    human_judgment: true
    rationale: "This is the phase's own must_haves.truths #3 — by design it can only be satisfied by the operator walking RB-10 against their real install; 33-FINDINGS.md currently records the open question and is explicitly marked PENDING OBSERVATION, not an answer"

duration: 35min
completed: 2026-08-04
status: awaiting-operator
---

# Phase 33 Plan 04: Doc sweep, release cut, RB-10 written — Summary

**Every shipped document now agrees with the durable-storage code 33-01..33-03 built, plugin `0.7.0` is cut in one commit, and RB-10 is written and ready — the live migration-and-permission-prompt observation itself is the operator's, not this execution's, to perform.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 2 of 3 built and committed by this execution; Task 3 (`checkpoint:human-verify`, `gate="blocking"`) has its doc scaffolding written but the live walk is explicitly out of scope for this executor
- **Files modified:** 8 (6 in `operator-claude-plugin/`, 1 runbook, 1 new findings doc)

## Accomplishments

- **Task 1 — docs agree with the code.** `README.md`'s setup section no longer names `operator-claude-plugin/config/` as the settings file's destination; it points the operator at `/operator-claude-plugin:initialize`, which reports the real resolved path (three possible locations, per `durable_paths.py`). Added `durable_paths.py` to the `scripts/` tree with a one-line comment, and two sentences stating the settings file survives an update and where it lives. Dropped the stale `config/` prefix from three README references, `review_queue.py`'s operator-facing "no link" message, and `enrich-records/SKILL.md`. `CHANGELOG.md`'s closing "Two traps" paragraph — the exact terminal instruction PLUGIN-02/03 forbid — is rewritten to state the current facts: neither trap exists as of `0.7.0`. Added `test_no_shipped_document_instructs_a_manual_config_copy`, asserting the substring `operator.local.json across` appears in neither `README.md` nor `CHANGELOG.md`. Plugin suite: 947/5 → **948/5**.
- **Task 2 — 0.7.0 cut.** `plugin.json`'s `version` bumped `0.6.2` → `0.7.0`. `CHANGELOG.md` gained a `## [0.7.0] - 2026-08-04` section (Changed: the durable-home migration for both settings and the dashboard pointer, and the sweep's `allow_migration=False` posture; Fixed: STATUS-05's same-link guarantee, silently broken since the plugin's first-ever update). `## [Unreleased]` stays empty above it. Both files landed in one commit (`24c2f16`) — `git show --stat` confirms.
- **Task 3 (partial) — RB-10 written, not walked.** `OPERATOR-RUNBOOK.md` gained a full RB-10 section (five steps: before-state backup, clone refresh, update, trigger one resolution, read the outcome, confirm the dashboard pointer), a `§0b` readiness row, a resume-signal row, and a changelog line — shaped to match RB-4's and RB-8's house style. `33-FINDINGS.md` records Research Open Question 1 verbatim (does the Bash-tool "sensitive location" permission prompt fire on this plugin's migration write? — not reproduced during research, MEDIUM confidence, closed as not-planned upstream at anthropics/claude-code#41156), states what is already true regardless of the answer (verify-then-delete, `LV_OPERATOR_CONFIG` as the built escape hatch, the sweep's structural immunity), and restates the absolute constraint the walk must not violate. No file under `~/.claude/plugins/` was read, copied, moved, or deleted by this execution.

## Task Commits

Each task was committed atomically:

1. **Task 1: Every shipped document agrees with the code** - `25e26ec` (docs)
2. **Task 2: Cut 0.7.0 — version bump and CHANGELOG entry in one commit** - `24c2f16` (chore)
3. **Task 3 (doc scaffolding only): RB-10 written, real migration pending operator** - `432a35c` (docs)

_This SUMMARY's own commit is separate, per the awaiting-operator precedent (28-02-SUMMARY.md): STATE.md, ROADMAP.md and REQUIREMENTS.md are deliberately NOT touched — the plan is not complete, and an operator now holds the release gate._

## Files Created/Modified

- `operator-claude-plugin/README.md` - setup section points at `/operator-claude-plugin:initialize` instead of a hardcoded directory; `durable_paths.py` added to the `scripts/` tree; two sentences on update-survival; three `config/` prefixes dropped
- `operator-claude-plugin/CHANGELOG.md` - closing "Two traps" paragraph rewritten; `## [0.7.0]` section added under `Changed`/`Fixed`
- `operator-claude-plugin/.claude-plugin/plugin.json` - `version` `0.6.2` → `0.7.0`
- `operator-claude-plugin/scripts/review_queue.py` - operator-facing no-link message drops the `config/` prefix
- `operator-claude-plugin/skills/enrich-records/SKILL.md` - provider-selection admin-default line drops the `config/` prefix
- `operator-claude-plugin/tests/test_plugin_manifest.py` - `test_no_shipped_document_instructs_a_manual_config_copy` added
- `.planning/workstreams/plugin-entrypoint/OPERATOR-RUNBOOK.md` - RB-10 section, §0b row, resume-signal row, changelog line
- `.planning/workstreams/plugin-entrypoint/phases/33-durable-operator-state/33-FINDINGS.md` - new; the open question verbatim, pending-observation scaffold

## Decisions Made

**1. `durable_paths.py`'s own two `config/operator.local.json` references were left as-is.** Lines 13 and 86 are internal docstrings accurately describing the literal legacy resolution path (step 4 of 5) and an example relative path in a helper's docstring — correct code documentation, not an operator-facing instruction. The plan's `read_first` list named only `review_queue.py:253` and `enrich-records/SKILL.md:66` as the "two more strings" beyond README's three; `durable_paths.py` was never one of them. `grep -rn 'config/operator.local.json' operator-claude-plugin/README.md operator-claude-plugin/scripts/ operator-claude-plugin/skills/` therefore still returns these two lines — a mechanical re-run of the acceptance-criteria grep as literally written would show non-zero, but the criterion's intent (operator-facing docs are fixed) is met; fixing the docstring would make it describe the resolution order incorrectly.

**2. Task 3's boundary is doc-writing only, per this plan's own explicit instruction.** The plan text is unambiguous: "Your job is to WRITE RB-10 into OPERATOR-RUNBOOK.md, not to walk it." No migration was performed, no file under `~/.claude/plugins/` was touched, and no permission setting, `settings.json`, or hook was changed. `33-FINDINGS.md` is explicitly headed "Status: PENDING OBSERVATION" so a future reader — including a future audit pass — cannot mistake the recorded open question for an answered one.

## Deviations from Plan

None — plan executed as written, with the one documented scope boundary above (Decision 2) that the plan itself specifies rather than one this execution introduced.

## Issues Encountered

None.

## User Setup Required

**RB-10 must be walked by the operator.** `.planning/workstreams/plugin-entrypoint/OPERATOR-RUNBOOK.md` §RB-10 has the exact steps: back up the live config, push and refresh the marketplace clone, update the plugin through Claude Desktop, trigger one resolution in a new conversation, and confirm the dashboard pointer survives across a brand-new conversation. **If a permission prompt fires, that is the finding — stop and record it; do not change a permission setting, edit `settings.json`, or add a suppressing hook.** Update `33-FINDINGS.md` with the observed result (a clean run with nothing to report is a complete, valid answer).

## Next Phase Readiness

- Phase 33 cannot be marked complete until RB-10 is walked and `33-FINDINGS.md` records the observation — that is `must_haves.truths` #3, verbatim from `33-04-PLAN.md`.
- Once RB-10 is walked: update `33-FINDINGS.md` with the real result, then this SUMMARY (or a follow-up commit) should update `STATE.md`, `ROADMAP.md`, and mark `PLUGIN-02`, `PLUGIN-03`, `STATUS-05` complete in `REQUIREMENTS.md` if not already reflected there (all three already read `[x]`/`Complete` from earlier phases; this plan's contribution is closing the remaining doc-side and release-side gaps under those same IDs).
- No code changed in this plan beyond the version string — the durable-storage mechanism itself (`durable_paths.py`, `config_gate.py`, `artifact_store.py`, `sweep_entry.py`) is unchanged from 33-03's shipped state.

## Self-Check: PASSED

- FOUND: `operator-claude-plugin/README.md`
- FOUND: `operator-claude-plugin/CHANGELOG.md`
- FOUND: `operator-claude-plugin/.claude-plugin/plugin.json`
- FOUND: `operator-claude-plugin/scripts/review_queue.py`
- FOUND: `operator-claude-plugin/skills/enrich-records/SKILL.md`
- FOUND: `operator-claude-plugin/tests/test_plugin_manifest.py`
- FOUND: `.planning/workstreams/plugin-entrypoint/OPERATOR-RUNBOOK.md`
- FOUND: `.planning/workstreams/plugin-entrypoint/phases/33-durable-operator-state/33-FINDINGS.md`
- FOUND commit `25e26ec`
- FOUND commit `24c2f16`
- FOUND commit `432a35c`

---
*Phase: 33-durable-operator-state*
*Completed (partial — awaiting RB-10): 2026-08-04*
