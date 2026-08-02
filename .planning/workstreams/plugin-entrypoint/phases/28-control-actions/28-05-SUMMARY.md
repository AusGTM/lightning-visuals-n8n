---
phase: 28-control-actions
plan: 05
subsystem: operator-claude-plugin
tags: [control-surface, confirmation-gate, allowlist, skill, amendments]
requires:
  - n8n_control.set_active / apply_mutation (28-01)
  - n8n_arming.armed_window / DisarmFailed (28-03)
  - n8n_cadence.set_cadence / set_schedule_enabled / parse_cadence / describe_cadence (28-04)
  - config_gate.require_capability("control") (28-01)
  - dispatch.dispatch (23-04) and enrichment.dispatch_enrichment (25-04)
provides:
  - control_actions.plan_action / execute_action
  - control_actions.start_lane / start_scheduled_scan
  - skills/backend-control/SKILL.md
  - test_plugin_manifest.py widened to every skill
affects:
  - 28-06 (armed canary drives this surface)
tech-stack:
  added: []
  patterns:
    - plan/execute split so the confirmation gate is structural, not a convention
    - lane dispatchers resolved by import at call time, never assumed
    - verdicts carried verbatim from the independent re-read
key-files:
  created:
    - operator-claude-plugin/scripts/control_actions.py
    - operator-claude-plugin/skills/backend-control/SKILL.md
    - operator-claude-plugin/tests/test_control_surface.py
  modified:
    - operator-claude-plugin/tests/test_plugin_manifest.py
    - .planning/workstreams/plugin-entrypoint/REQUIREMENTS.md (CONTROL-01, CONTROL-05)
    - .planning/workstreams/plugin-entrypoint/ROADMAP.md (Phase 28 criteria 1 and 4)
---

# 28-05 — the operator-facing control surface

**Status: COMPLETE.** Repo 1635 → 1670 pytest. Node 506 unchanged. Serialization behind
the operator's `test_plugin_manifest.py` commit resolved 2026-08-03 (`348a36e`) before
execution began.

## Task 1 — the choke point

`plan_action` composes; `execute_action` mutates; nothing else does either. The gate is
structural: executing takes a proposal, so skipping planning leaves nothing to execute,
and the confirmation parameter has **no default** (pinned via `inspect.signature`) and
accepts only the literal `"yes"` — `True`, `"YES"`, `"y"` and friends all refuse.

Out-of-allowlist requests refuse before any mutating call is reachable, naming the
boundary (plugin operates; admin changes; from the repository). `start_scheduled_scan`
is a written refusal citing the live 405 from 28-FINDINGS Q2, and a source test asserts
its body contains no cadence-changing call — the D-05c workaround is structurally absent.

Verdicts are carried verbatim: a `failed` re-read reaches the operator as "THIS DID NOT
TAKE EFFECT", and `disarm_failed` surfaces as its own state with the LIVE-WRITES-MAY-
STILL-BE-ENABLED sentence intact, never folded into a generic failure.

**Plan staleness, absorbed by design:** the plan said "exactly one dispatcher ships
today". Phase 25 landed `enrichment.dispatch_enrichment` in the meantime. Because
`start_lane` resolves dispatchers by import at call time, the enrichment lane is simply
offered — zero edits needed — and the refusal branch ("Phase 25 work has not landed yet;
contact upload works now") is still tested by simulating the import failure. Lane starts
make no n8n API call, asserted against the module source: the guards live on the
dispatch path, so the dispatch path is the only way in.

## Task 2 — the skill

`skills/backend-control/SKILL.md`: plan → show consequence verbatim → explicit yes →
execute → report the re-read's verdict. Arm/dispatch/disarm is presented as **one**
action with one confirmation — three confirmations for one decision trains click-through.
Schedule syntax never crosses the boundary in either direction; refusals read as
boundaries with a named owner, not malfunctions.

`test_plugin_manifest.py` widened from its hardcoded contact-upload path to a glob over
`skills/*/SKILL.md`, non-empty-asserted first. The plan expected the widening to surface
a third skill; it surfaced **six** (contact-upload, backend-status, enrich-records,
initialize, review-triage, backend-control) — five of which the hardcoded form had never
covered. All pass, including a new pin that frontmatter `name` matches the directory.

## Task 3 — the amendments, closed in the source artifacts

28-FINDINGS Q2 recorded **405**, so the CONTROL-01 amendment applies (a 2xx would have
halted this task per the plan).

- REQUIREMENTS.md CONTROL-01: scan clause removed, greppable phrase
  `no endpoint to execute a workflow by id` present, 405 cited with its source.
  Amendment #5. The "either ingestion lane that is built" qualifier notes both are.
- REQUIREMENTS.md CONTROL-05 **and** ROADMAP criterion 4: allowlist is now the four-item
  D-25 form including the Schedule Trigger `disabled` boolean. Amendment #6 recorded in
  both places in the same commit, so the artifacts cannot contradict each other.
- ROADMAP criterion 1: same narrowing as CONTROL-01. Diff confined to exactly two lines.

## For 28-06

- The canary drives THIS surface: `plan_action` → operator "yes" → `execute_action` with
  a real `dispatch_fn`, under `ALLOW_N8N_ARM=true`.
- Its closing gate remains `test_control_disarmed_artifacts.py`.
- CONTROL-02/03/05/06/07 checkboxes flip on the canary's evidence, not on this build.
