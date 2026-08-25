---
phase: 53-operator-openable-write-grant
plan: 01
subsystem: operator-plugin
tags: [write-grant, arming, authority, hubspot-writes, operator-surface, python]

# Dependency graph
requires:
  - phase: 28-backend-control
    provides: n8n_arming.arm_for_dispatch, armed_window, disarm, n8n_control.apply_mutation
  - phase: 28-backend-control
    provides: control_actions.plan_action/execute_action -- the proposal + explicit-yes shape
  - phase: 27-status
    provides: config_gate.CAPABILITY_KEYS, require_capability's refusal wording convention
  - phase: 40-scoring-engine-remediation
    provides: scheduled_arm.ENRICHMENT_WORKFLOW_NAME, executions_client.resolve_workflow_id
provides:
  - "config_gate.WRITE_GRANT_SETTINGS_KEY / write_grants_enabled(config): the ONE definition of the admin-set write-grant authority, compared by identity against the JSON boolean true"
  - "write_grant.py: plan_grant -> open_grant -> covers -> close_grant, shipped in FINAL signature shape so 53-02..04 fill rather than reshape"
  - "write_grant.LANES: the grantable lanes (enrichment + contacts, D-53-05); review deliberately excluded"
  - "n8n_arming._arm_gate(config, grant=None): AUTHORITY, three-way split -- grant branch on the settings key, no-grant branch unchanged on ALLOW_N8N_ARM"
  - "arm_for_dispatch(..., grant=None): SCOPE (GRANT-03) enforced in-function, before transport construction"
  - "armed_window(..., grant=None): pass-through only; per-send windows and the guaranteed disarm are untouched"
affects: [53-02-envelope-revocation-guardrails, 53-03-operator-surface, 53-04-skills-docs-release]

actuals:
  tokens: 13867
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Authority and scope as two separate decisions: _arm_gate answers 'may this session arm at all', arm_for_dispatch's grant branch answers 'is THIS send inside the grant'. Both must pass before any transport is constructed."
    - "Scope enforced in the function a caller can actually reach, not only in a helper a lane skill is supposed to call -- a bypassable scope check is not a scope check."
    - "Behavioural parity over source-text pins: one shared parameter list driven through BOTH confirmation gates, rather than asserting a literal appears in two files (token presence != semantic agreement)."
    - "Single-definition authority: config_gate.write_grants_enabled is imported by both consumers, so there is no second copy to hold in agreement and no text pin is needed."
    - "Grant as a plain JSON-shaped dict, not a dataclass -- it has to survive being carried across a conversation turn and handed back into a later Python invocation."

key-files:
  created:
    - operator-claude-plugin/scripts/write_grant.py
    - operator-claude-plugin/tests/test_write_grant.py
  modified:
    - operator-claude-plugin/scripts/config_gate.py
    - operator-claude-plugin/scripts/n8n_arming.py
    - operator-claude-plugin/tests/test_control_arming.py

key-decisions:
  - "covers() takes lane as OPTIONAL. arm_for_dispatch knows a workflow id, not a lane name, so with lane=None the workflow id is checked against every id the grant resolved. This keeps ONE implementation and ONE refusal wording for the scope question rather than a second copy at the arm site."
  - "write_grant imports scheduled_arm (for ENRICHMENT_WORKFLOW_NAME) at module level, and n8n_arming imports write_grant INSIDE arm_for_dispatch's grant branch. scheduled_arm imports n8n_arming at top level, so a top-level import in n8n_arming would be a cycle. Function-level import is already this module's house style (import os in _arm_gate, import requests in arm_for_dispatch)."
  - "The empty-allowlist refusal is kept independent of, and after, the scope check. covers() is a subset test and the empty set is trivially a subset, so a grant must not become a route past the refusal that exists because _writeSafetyAllows denies everything on an empty allowlist."
  - "plan_grant accepts a module-shaped transport (consistent with n8n_arming) and passes transport.get down to executions_client.resolve_workflow_id, which takes a GET callable."
  - "Task 3's added assertion reads config_gate.py's source, not n8n_arming's. The identity comparison lives only in config_gate.write_grants_enabled -- that is the whole point of the no-duplication rule, so the pin has to sit where the comparison actually is."

patterns-established:
  - "Final-shape-in-wave-1: plan_grant/open_grant ship with their permanent signatures (a proposal, then a confirmation with no default that must read exactly yes) plus a named preflight seam, so waves 2-4 fill dict keys and add callers rather than reshaping a function wave-1 tests already bind to."

requirements-completed: [GRANT-03]
requirements-partial:
  - "GRANT-01: the grant's SHAPE ships (object type, record set, lanes, creates, behind a proposal + explicit yes). Ceilings are 53-02 T1; the one-exchange operator surface is 53-03 T2."
  - "GRANT-06: holds for everything 53-01 built (no file, no env var, no default -- pinned). Stays open until 53-02..04 ship their own surfaces under the same prohibition."

coverage:
  - id: D1
    description: "A dispatch arms under an admin-set settings key and an operator-opened grant with NO shell environment variable set anywhere -- G-2's blocker removed on the interactive path, proven end to end through arm -> window -> verified disarm"
    requirement: "GRANT-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_a_send_arms_under_an_opened_grant_with_no_environment_variable_set"
        status: pass
    human_judgment: false
  - id: D2
    description: "GRANT-03 binds INSIDE arm_for_dispatch: a record id, a domain, or a workflow id outside the grant is refused with an EMPTY transport call log -- refused before transport construction, not merely without mutating"
    requirement: "GRANT-03"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_a_record_outside_the_grant_is_refused_before_any_transport_call"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_a_domain_outside_the_grant_is_refused_before_any_transport_call"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_a_grant_on_one_lane_cannot_arm_another_lanes_workflow"
        status: pass
    human_judgment: false
  - id: D3
    description: "The settings key is the authority and is re-read from config at arm time: a hand-built dict shaped like an open grant, presented against a config without the key, is refused (T-53-01)"
    requirement: "GRANT-06"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_a_grant_presented_against_a_config_without_the_key_refuses"
        status: pass
    human_judgment: false
  - id: D4
    description: "Sixteen near-miss rows ('true'/'True'/'TRUE'/'1'/'yes'/1/1.0/''/false/null/absent, over both the plan and the arm) all refuse; only the JSON boolean true authorizes (T-53-02). Mutation-verified: replacing `is True` with `bool()` reddens 16 tests"
    requirement: "GRANT-06"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_every_near_miss_settings_value_refuses_the_arm"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_every_near_miss_settings_value_refuses_the_plan"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_only_the_json_boolean_true_authorizes"
        status: pass
    human_judgment: false
  - id: D5
    description: "The headless path is untouched: with no grant and no environment variable the arm refuses at zero HTTP cost, ALLOW_N8N_ARM still compares against the exact string 'true', scheduled_arm.py is unedited and test_scheduled_arm.py passes unchanged (T-53-03)"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_with_no_grant_and_no_environment_variable_the_arm_refuses_at_zero_http_cost"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_control_arming.py::test_with_the_gate_unset_the_arm_refuses_and_makes_no_call_at_all"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_scheduled_arm.py (whole file, unedited)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Disarm gains no authority check of any kind and its test is byte-identical (T-53-04). git diff -U0 of test_control_arming.py removes exactly two lines: the old test name and its old docstring"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_control_arming.py::test_the_disarm_is_NOT_gated_on_the_kill_switch"
        status: pass
      - kind: command
        ref: "git diff -U0 operator-claude-plugin/tests/test_control_arming.py | grep '^-' -- two lines, neither a test function"
        status: pass
    human_judgment: false
  - id: D7
    description: "The empty-allowlist refusal is not relaxed for a grant-authorized arm -- covers() is a subset check and the empty set trivially passes it, so the refusal is kept independent"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_the_empty_allowlist_refusal_still_fires_under_a_grant"
        status: pass
    human_judgment: false
  - id: D8
    description: "GRANT-06: nothing about a grant reaches disk or the environment -- no file written under a redirected config path, os.environ unchanged, and write_grant.py's source contains no open(), write_text, os.environ[, setenv or json.dump("
    requirement: "GRANT-06"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_nothing_about_a_grant_is_written_to_disk_or_to_the_environment"
        status: pass
    human_judgment: false
  - id: D9
    description: "One shared confirmation list drives BOTH control_actions.execute_action and write_grant.open_grant behaviourally: both refuse all eleven rows, both proceed on the exact string yes, both raise TypeError when the argument is omitted. No source-text pin introduced"
    requirement: "GRANT-01"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_neither_confirmation_gate_accepts_anything_but_the_exact_string_yes"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_both_confirmation_gates_proceed_on_the_exact_string_yes"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_both_confirmation_gates_raise_type_error_when_the_argument_is_omitted"
        status: pass
    human_judgment: false
  - id: D10
    description: "The settings key is NOT a capability row (D-53-01): absent from CAPABILITY_KEYS, from _CAPABILITY_DESCRIPTIONS, and from every capability's required-key tuple, so a later edit that folds it in fails loudly"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_the_settings_key_is_not_a_capability_row"
        status: pass
    human_judgment: false
  - id: D11
    description: "No configured value reaches any refusal string across plan_grant, open_grant and the grant-branch arm refusal (T-53-06 / T-27-12 convention)"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_no_configured_value_reaches_any_refusal_string"
        status: pass
    human_judgment: false
  - id: D12
    description: "No new write-safety constant is declared in any n8n workflow; the declaring set does not move and test_control_flag_parity.py passes unchanged"
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_control_flag_parity.py (whole file, unedited)"
        status: pass
      - kind: command
        ref: "git diff 3defa36 HEAD --stat -- five files only; nothing under n8n/, scripts/build_cloud_workflows.py or scheduled_arm.py"
        status: pass
    human_judgment: false

duration: ~4min
completed: 2026-08-25
status: complete
---

# Phase 53 Plan 01: Operator-Openable Write Grant Summary

**An admin sets one key in `operator.local.json`, the operator opens a grant in conversation, and a dispatch arms live HubSpot writes with no shell environment variable anywhere — bounded to the named batch by a scope check inside `arm_for_dispatch` itself.**

## Performance

- **Duration:** ~4min (first commit 16:02:10 +1000, last 16:04:27 +1000)
- **Completed:** 2026-08-25
- **Tasks:** 3
- **Files modified:** 5 (2 new, 3 edited)

## Accomplishments

- **G-2's blocker is removed on the interactive path.** `_arm_gate()` required
  `ALLOW_N8N_ARM=true` in the session's *shell*, which an operator in Claude Desktop cannot
  set — so the documented operator path ended in a refusal only an admin with terminal
  access could clear. The interactive arm's authority is now
  `config_gate.WRITE_GRANT_SETTINGS_KEY` (`allow_write_grants`) in `operator.local.json`,
  compared by **identity** against the JSON boolean `true`. The tracer test walks the whole
  path — key, plan, explicit yes, arm, window, verified disarm — and asserts the
  environment variable was never set at any step.
- **Authority and scope are two separate decisions, and both bind.** `_arm_gate(config,
  grant)` answers *may this session arm at all*; `arm_for_dispatch`'s own grant branch
  answers *is THIS send inside the grant* (GRANT-03), immediately after the authority check
  and **before any transport is constructed**. The scope check lives in the function a
  caller can actually reach, not only in a helper a lane skill is supposed to call. Three
  scope refusals (record id, domain, workflow id) each assert `transport.calls == []` —
  that empty list is what distinguishes "refused before transport" from "did not mutate".
- **The headless path is byte-identical in behaviour.** `grant` is a keyword defaulting to
  `None`, so `scheduled_arm.py` and every pre-53 caller stay on the environment branch,
  still comparing against the exact string `"true"`, still at zero HTTP cost.
  `scheduled_arm.py` took zero edits and `test_scheduled_arm.py` passes unchanged.
- **Disarm gained nothing.** `disarm`, `set_write_safety` and `disarmed_targets` are
  untouched; `armed_window` took only a `grant=None` pass-through, so per-send windows and
  the guaranteed disarm the milestone's must-not-lose list names are unchanged.
  `test_the_disarm_is_NOT_gated_on_the_kill_switch` is byte-identical.
- **The settings-key comparison exists exactly once**, in `config_gate.write_grants_enabled`,
  imported by both `write_grant` and `n8n_arming`. No duplication, therefore no text pin
  holding two copies in agreement.
- **The parity pin moved once, deliberately, with the reason in the test file.** Its old
  assertion still passed after Task 1 — but its name and docstring claimed a coupling that
  no longer holds, and a test whose assertion passes while its claim is false reads as
  evidence for something nobody checked. Renamed to name the *headless branch*, docstring
  replaced with D-53-01, the date and the three-way split, one assertion added pinning the
  interactive branch's identity comparison in `config_gate.py`. Nothing deleted, nothing
  else in the file touched.

## Task Commits

Each task was committed atomically:

1. **Task 1 (tracer): End-to-end — an admin-set key, an opened grant, one send armed under it** — `7607825` (feat)
2. **Task 2: The authority's edges — near misses, absent key, forged grant, headless untouched** — `6d08a03` (test, tdd)
3. **Task 3: Re-point the arm/probe parity pin — one edit, reason recorded in the test** — `c9aaee6` (test)

## Files Created/Modified

- `operator-claude-plugin/scripts/write_grant.py` *(new, 274 lines)* — the grant: `LANES`,
  `plan_grant` (refusal order: authority, unknown lane, empty record set, unresolvable
  lane; `preflight` seam for 53-02's guardrail A), `open_grant` (proposal + no-default
  confirmation that must read exactly `yes`), `close_grant` (copy, no network call, no
  disarm — and the docstring says why that is not a forgotten step), `covers` (the one
  implementation of the scope question).
- `operator-claude-plugin/tests/test_write_grant.py` *(new, 598 lines, 61 tests)* — the
  tracer, the three scope refusals, the authority edges, the confirmation-parity pair, and
  the nothing-reaches-disk pin.
- `operator-claude-plugin/scripts/config_gate.py` — `WRITE_GRANT_SETTINGS_KEY` and
  `write_grants_enabled`, with the `bool`-is-an-`int` comment and a comment saying why the
  key is deliberately not in `CAPABILITY_KEYS`.
- `operator-claude-plugin/scripts/n8n_arming.py` — `_arm_gate(config, grant=None)`,
  `arm_for_dispatch`'s grant branch and signature, `armed_window`'s pass-through. Diff
  confined to those three; `disarm`, `set_write_safety` and `disarmed_targets` untouched.
- `operator-claude-plugin/tests/test_control_arming.py` — one test renamed and
  re-documented; `git diff -U0` removes exactly two lines.

## Decisions Made

- **`covers(grant, *, lane=None, workflow_id, ...)` — lane is optional.**
  `arm_for_dispatch` knows a workflow id, not a lane name. Rather than write a second scope
  check at the arm site, `lane=None` checks the workflow id against every id the grant
  resolved. One implementation, one refusal wording, as the plan's key_links require.
- **`write_grant` is imported inside `arm_for_dispatch`'s grant branch, not at module top.**
  `write_grant` imports `scheduled_arm` (for `ENRICHMENT_WORKFLOW_NAME`, per the plan's
  "read it rather than respell it"), and `scheduled_arm` imports `n8n_arming` at top level —
  so a top-level import in `n8n_arming` would be a cycle at import time. Function-level
  import is already this module's house style (`import os` in `_arm_gate`, `import requests
  as _requests` in `arm_for_dispatch`).
- **The empty-allowlist refusal stays independent of, and after, the scope check.**
  `covers` is a subset test and the empty set is trivially a subset of anything, so without
  this ordering a grant would have become a route past the refusal that exists because the
  deployed `_writeSafetyAllows` denies everything on an empty allowlist. Pinned by its own
  test.
- **`plan_grant` takes a module-shaped transport and passes `transport.get` down.**
  `executions_client.resolve_workflow_id` takes a GET *callable* (`transport=requests.get`),
  while `n8n_arming` threads the `requests` module — this bridges the two the same way
  `arm_for_dispatch` already does (`transport=transport.get`).
- **Task 3's added assertion reads `config_gate.py`'s source, not `n8n_arming`'s.** The
  identity comparison lives only in `write_grants_enabled` — that is the point of Task 1's
  no-duplication rule, so the pin has to sit where the comparison actually is.
- **`contacts` resolves through `executions_client.CONTACT_INGEST_WORKFLOW_NAME`**, the same
  way `enrichment` resolves through `scheduled_arm.ENRICHMENT_WORKFLOW_NAME` — no workflow
  name is respelled in this module.

## Deviations from Plan

**One correction to the plan's own bookkeeping.** 53-01-PLAN.md's frontmatter lists
`requirements: [GRANT-01, GRANT-03, GRANT-06]`, but the plan's OWN source-coverage audit
maps GRANT-01 across 53-01 + 53-02 + 53-03 and GRANT-06 across 53-01 "+ prohibitions in
every plan". Only **GRANT-03** is genuinely closed here, so only GRANT-03 is ticked in
`.planning/milestones/v1.1-REQUIREMENTS.md`; GRANT-01 and GRANT-06 carry a dated *Partial
(53-01)* note naming what shipped and which plan closes the rest. Ticking all three would
have been a false completion claim.

**None that change scope.** Two implementation details resolved inside the plan's own
action text, both recorded above and both pinned by tests: the optional `lane` on `covers`
(the plan specified `covers(grant, *, lane, ...)` but `arm_for_dispatch` has no lane name to
pass), and the function-level import of `write_grant` in `n8n_arming` (a top-level import
would have been an import-time cycle through `scheduled_arm`).

**One test-fixture correction during Task 1.** The two-lane test initially scripted one
`/api/v1/workflows` response for two distinct workflow names;
`executions_client._workflow_id_cache` keys by name, so the second lane needed its own
scripted read. Fixed in the fixture, not in the source.

## TDD Gate Compliance

Task 2 carried `tdd="true"` and its tests were **green on arrival**, which is the plan's own
design rather than a skipped RED gate: Task 1 is a `type="tracer"` that deliberately ships
`plan_grant`/`open_grant` in their final shape so waves 2–4 have a stable signature to bind
to, and Task 2's job is edge coverage over that shape. The RED property was checked by
mutation instead of by omission: replacing `write_grants_enabled`'s `is True` with `bool()`
reddens **16 tests**, and the change was reverted before commit. Recorded here rather than
manufacturing a failure by breaking working code.

## Known Stubs

Two grant keys are initialised and never written in this plan. Both are **deliberate seams
named in 53-01-PLAN.md**, initialised here precisely so 53-02 lands as a fill rather than a
reshape of a dict wave-1 tests already bind to:

| Key | File | Reason | Resolved by |
|---|---|---|---|
| `envelope` (always `None`) | `operator-claude-plugin/scripts/write_grant.py:~155` | GRANT-02's arithmetic is 53-02's task; D-53-02 records that a ceiling derived from the batch discloses rather than constrains | 53-02 T1 |
| `consecutive_disarm_failures` (always `0`) | `operator-claude-plugin/scripts/write_grant.py:~200` | D-53-04's guardrail B (bound the disarm unknown) is 53-02's task | 53-02 T2/T3 |

The `preflight=None` parameter on `plan_grant` is the third such seam; unlike the two above
it is *exercised* by a test
(`test_the_preflight_seam_can_refuse_before_a_proposal_exists`), so it is a working
extension point rather than a stub.

Neither prevents this plan's goal — a dispatch arms under an operator-opened grant with no
shell — from being achieved.

## Issues Encountered

No auth gates, no architectural decisions, no package installs. One tooling defect, worth
recording because the next executor will hit it:

**`gsd-tools query state.advance-plan` corrupted `.planning/STATE.md` and was repaired by
hand.** Run at closeout, the verb set `current_phase: 53 -> 51`, reported
`{reason: "last_plan", current_plan: 3, total_plans: 3}` (phase 51's shape, not phase 53's
four plans), and flattened both `stopped_at` and `last_activity_desc`, discarding the
carried Phase-52-deferral context the previous session had left there. The follow-on
`state.update-progress` then recomputed the body's legacy `Progress:` line against the same
stale v0.9 scan (100% -> 57%).

Repaired by hand in the same session: `current_phase` back to 53, `status: executing`,
`stopped_at` restored *with* the Phase 52 deferral note plus the 53-01 completion,
`progress` set to honest v1.1 values (5 phases, 4 plans in phase 53, 1 complete), and the
legacy `Progress:` line restored. The metric row and session timestamp the verbs added are
correct and were kept. Same family as the already-recorded
`phase-complete-workstream-guard-misfires` note: **read `git diff .planning/STATE.md` after
running these verbs — do not assume they wrote what they reported.**

**`gsd-tools query requirements.mark-complete` was a no-op** (`not_found` for all three
GRANT ids): it reads `.planning/REQUIREMENTS.md`, while v1.1's requirements live at
`.planning/milestones/v1.1-REQUIREMENTS.md`. That file was edited directly instead — see
Deviations for why only GRANT-03 was ticked.

**`gsd-tools query roadmap.update-plan-progress 53` was also a no-op** (reported
`status: "In Progress"` but modified no file): phase 53 has no plans-progress row in
`.planning/ROADMAP.md`; its plan list is a checkbox block in
`.planning/milestones/v1.1-ROADMAP.md`. `53-01-PLAN.md`'s checkbox was ticked there
directly.

## User Setup Required

**An n8n admin must add one key to `operator.local.json` before any operator can open a
grant:**

```json
{ "allow_write_grants": true }
```

It must be the JSON boolean `true` — the string `"true"`, `1`, `1.0` and `"yes"` all read
as *not authorized*, by design (`bool` is an `int` subclass in Python, so a truthiness test
would have made this gate silently weaker than the exact-string environment variable it
replaces on the interactive path). Absent or `false`, the plugin refuses to plan or open a
grant and names the key and the file. The operator-facing surface that walks an admin
through this is 53-03/53-04; nothing in this plan is reachable from a skill yet.

`ALLOW_N8N_ARM` is unchanged and still required for the headless/cron path
(`scheduled_arm.py`). Do not remove it.

## Next Phase Readiness

- `plan_grant`, `open_grant`, `close_grant` and `covers` ship in their **final signatures**.
  53-02 fills `envelope` and `consecutive_disarm_failures`, adds revocation/expiry and the
  two guardrails; 53-03 builds the operator-facing config and confirmation surface; 53-04
  does the skills, docs and release. None of them needs to reshape a function this plan's
  tests bind to.
- 53-02's guardrail A has a named seam waiting: `plan_grant(preflight=...)` is invoked with
  `(config, workflow_ids, transport)` before the proposal is built and returns its refusal
  unchanged, and that behaviour is already tested.
- **53-04 still owes the one deliberate contract-test edit for D-53-05.**
  `test_enrich_before_ingest_skill_contract.py` still forbids a combined arming phrase and
  pins the enriched-preview heading as strictly preceding the ingest-arm heading. This plan
  made a two-lane grant *expressible* (`LANES` covers both, with the traded protection
  recorded in its own comment) but did not touch that contract test — per the source
  coverage audit, that edit is 53-04 T1.
- Zero n8n executions, zero HubSpot writes and zero provider credits were spent by this
  plan. Nothing was deployed; `n8n/` and `scripts/build_cloud_workflows.py` are unmodified.

## Verification Output (as run, 2026-08-25)

```
$ .venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py \
    operator-claude-plugin/tests/test_control_arming.py \
    operator-claude-plugin/tests/test_scheduled_arm.py \
    operator-claude-plugin/tests/test_control_flag_parity.py -q
87 passed in 0.13s                                          # Task 1 verify

$ .venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py \
    operator-claude-plugin/tests/test_config_gate.py \
    operator-claude-plugin/tests/test_control_surface.py -q
110 passed in 0.79s                                         # Task 2 verify

$ .venv/bin/python -m pytest operator-claude-plugin/tests/test_control_arming.py -q
22 passed in 0.04s                                          # Task 3 verify

$ .venv/bin/python -m pytest operator-claude-plugin/tests/ -q
1399 passed, 5 skipped in 4.65s

$ .venv/bin/python -m pytest -q
2962 passed, 154 skipped, 1 warning in 9.22s

$ node --test tests/n8n/*.test.mjs
tests 711 | pass 711 | fail 0

$ git status --porcelain
(clean)

$ git diff --stat 3defa36 HEAD
 operator-claude-plugin/scripts/config_gate.py    |  33 ++
 operator-claude-plugin/scripts/n8n_arming.py     |  91 +++-
 operator-claude-plugin/scripts/write_grant.py    | 274 +++++++++
 .../tests/test_control_arming.py                 |  40 +-
 operator-claude-plugin/tests/test_write_grant.py | 598 ++++++++++++++++++
 5 files changed, 1019 insertions(+), 17 deletions(-)

$ git diff -U0 operator-claude-plugin/tests/test_control_arming.py | grep '^-' | grep -v '^---'
-def test_the_probe_and_the_arm_gate_use_the_same_comparison():
-    """Pinned by reading both sources: both compare against the exact string 'true'."""
```

Exactly two test files changed. Nothing under `n8n/`, `scripts/build_cloud_workflows.py` or
`operator-claude-plugin/scripts/scheduled_arm.py`. The `test_control_arming.py` diff removes
exactly two lines — the old test name and its old docstring — and deletes no test function.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/write_grant.py` — FOUND (274 lines)
- `operator-claude-plugin/tests/test_write_grant.py` — FOUND (598 lines, 61 tests, all passing)
- `.planning/phases/53-operator-openable-write-grant/53-01-SUMMARY.md` — FOUND
- Commits `7607825`, `6d08a03`, `c9aaee6` — all FOUND in `git log`
