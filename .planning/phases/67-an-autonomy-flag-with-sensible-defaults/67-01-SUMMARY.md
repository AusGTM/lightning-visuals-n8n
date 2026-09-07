---
phase: 67-an-autonomy-flag-with-sensible-defaults
plan: 01
subsystem: config
tags: [autonomy, config_gate, write-grant, headless-boundary, default-setter]

# Dependency graph
requires:
  - phase: 68-state-the-price-and-keep-moving
    provides: implicit-approval posture in conversation, and the D-68-04 forward
      reference this plan's Task 3 rewrites into a completed statement
provides:
  - config_gate.AUTONOMY_SETTINGS_KEY / AUTONOMY_LEVELS / autonomy_enabled — the single
    default-setter reader every batch skill's ask-or-proceed switch will call in 67-02
  - the autonomy object + _autonomy_note in operator.local.example.json
  - a checked (not claimed) fact that no settings key can reach the headless/cron arm path
  - the operator's verbatim, recorded answer to the AUTO-04 reversal question, for 67-04
    to quote into backend-control/SKILL.md
affects: [67-02, 67-03, 67-04]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 4646
  tasks: 2
  commits: 4
  plan_head_before: d5b602839207dad4edce7493131bd9fe58e7a12b

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Default-setter reader (absence -> True) as the deliberate mirror-image of an
      authority gate (absence -> False) — same file, two shapes, commented at both
      read sites so a future edit does not collapse them into one."
    - "`.get(level, True) is True` — a single identity comparison that simultaneously
      handles absent-level-defaults-True and near-miss-values-read-False, without a
      separate 'is this key present' branch."
    - "RED-first via deliberate mis-scoping: point the new assertion at a file KNOWN to
      contain the forbidden symbols, observe the failure, then correct the scope for
      GREEN — proves the assertion itself works before it proves the target is clean."

key-files:
  created:
    - operator-claude-plugin/tests/test_autonomy_levels.py
  modified:
    - operator-claude-plugin/scripts/config_gate.py
    - operator-claude-plugin/config/operator.local.example.json
    - operator-claude-plugin/tests/test_headless_grant_boundary.py

key-decisions:
  - "Task 1 Question A, answered verbatim by the operator (2026-09-07), recorded here for
    67-04 to quote into backend-control/SKILL.md: \"On 2026-09-07 the operator reversed
    the 57-05 Task 4 option-a decision: autonomy is ON by default for read-only,
    spend-no-write and write; an unattended round discloses an unknown ceiling, balance
    or allowance key and proceeds; allow_write_grants and ALLOW_N8N_ARM remain the only
    authorities.\""
  - "Task 1 Question B, rendering (1) key shape: one `autonomy` object holding
    `read_only`, `spend_no_write`, `write` — three independently settable keys under one
    parent; constants AUTONOMY_SETTINGS_KEY / AUTONOMY_LEVELS in config_gate.py, as
    proposed."
  - "Task 1 Question B, rendering (2) absence: an absent `autonomy` object, and an absent
    level inside a present one, both read ON — the explicit code default (documented at
    the read site as distinct from write_grants_enabled's `is True` identity-on-absence
    pattern), not a copy of it. As proposed."
  - "Task 1 Question B, rendering (3) near-miss: b-near-miss-asks. Only the JSON boolean
    `true` (or an absent level) reads ON; every other value — \"true\"/\"false\" strings,
    0, 1, \"yes\", an explicit null — reads OFF and the round asks."
  - "Task 1 Question B, rendering (4) malformed parent: b-malformed-off. `{\"autonomy\":
    true}` (a bare boolean where the object belongs) reads OFF for every level and
    raises nothing — pinned by its own test."
  - "67-PATTERNS.md's earlier sketch used `is not False` for the near-miss rule, which
    would have read a near-miss value as ON. Task 1's answer (b-near-miss-asks)
    supersedes that sketch; the shipped implementation reads near-miss OFF, matching the
    recorded decision, not the pattern map's draft."

patterns-established:
  - "Default-setter vs authority gate: both live in config_gate.py, contrasted by an
    inline comment at each read site so a later maintainer does not 'fix' one into the
    other's shape."

requirements-completed: [AUTO-01, AUTO-04, AUTO-05]

coverage:
  - id: D1
    description: "config_gate.autonomy_enabled(cfg, level) reads every level ON when the
      autonomy object or the level is absent, through a real load_config() round trip
      on a file with no autonomy key at all"
    requirement: AUTO-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_autonomy_levels.py#test_absent_autonomy_object_reads_every_level_on"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_autonomy_levels.py#test_absent_level_inside_a_present_object_reads_on"
        status: pass
      - kind: integration
        ref: "operator-claude-plugin/tests/test_autonomy_levels.py#test_a_config_file_with_no_autonomy_key_reads_every_level_on_through_the_real_loader"
        status: pass
    human_judgment: false
  - id: D2
    description: "Every near-miss level value (\"true\", \"false\", 0, 1, \"yes\", null)
      reads OFF, and a bare-boolean autonomy parent reads OFF for all three levels
      without raising"
    requirement: AUTO-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_autonomy_levels.py#test_every_near_miss_level_value_reads_off_not_on"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_autonomy_levels.py#test_bare_boolean_parent_reads_every_level_off_and_raises_nothing"
        status: pass
    human_judgment: false
  - id: D3
    description: "AUTONOMY_SETTINGS_KEY is not a member of CAPABILITY_KEYS, and neither
      scheduled_arm.py nor n8n_arming.py names any of the four autonomy symbols — the
      headless/cron path stays reachable only through ALLOW_N8N_ARM"
    requirement: AUTO-05
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_autonomy_levels.py#test_the_settings_key_is_not_a_capability_row"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_headless_grant_boundary.py#test_scheduled_arm_source_never_names_an_autonomy_symbol"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_headless_grant_boundary.py#test_n8n_arming_source_never_names_an_autonomy_symbol"
        status: pass
      - kind: other
        ref: "git diff --quiet 238d1ab -- operator-claude-plugin/scripts/scheduled_arm.py operator-claude-plugin/scripts/n8n_arming.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "The AUTO-04 reversal was put to the operator before any autonomy
      default was written to disk, and the answer is recorded verbatim"
    requirement: AUTO-04
    verification: []
    human_judgment: true
    rationale: "Recording a verbatim human answer to a blocking-human checkpoint is not
      something a test asserts about; the record itself (this file's key-decisions
      block, and 67-04's later quote of it into backend-control/SKILL.md) is the
      artifact. No automated test can verify the operator actually said this sentence."

# Metrics
duration: 25min
completed: 2026-09-07
status: complete
---

# Phase 67 Plan 01: An autonomy flag with sensible defaults — Task 1 answered, Task 2/3 Summary

**Named the three autonomy levels as `config_gate` settings keys with an absence-reads-ON
default-setter shape, and pinned by a checked (not claimed) fact that no settings key can
ever reach the headless/cron arming path.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-09-07T06:57:39Z
- **Completed:** 2026-09-07T07:22:41Z
- **Tasks:** 3 (Task 1 answered by the operator before this executor was spawned; Task 2
  and Task 3 executed here)
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- Task 1 (checkpoint:decision, `gate="blocking-human"`): the operator answered both
  questions before any default landed on disk. Verbatim answer to Question A, and the
  four confirmed renderings for Question B, are recorded under Decisions Made below.
- Task 2 (tracer, TDD): `config_gate.AUTONOMY_SETTINGS_KEY`, `AUTONOMY_LEVELS`, and
  `autonomy_enabled(config, level)` — a default-setter, not an authority gate, reading
  every level ON when absent (D-67-03/D-67-10) and OFF on any near-miss value or a
  malformed parent (Task 1's confirmed rendering). Verified through a real
  `config_gate.load_config()` round trip on a file with no `autonomy` key at all, not
  just a hand-built dict. `operator.local.example.json` documents the same, immediately
  after `_allow_write_grants_note` so the absence-reads-ON contrast reads adjacent to
  `allow_write_grants`'s absence-reads-OFF.
- Task 3 (auto, TDD): two new source-scan tests pin that neither `scheduled_arm.py` nor
  `n8n_arming.py` names any of the four autonomy symbols — the headless/cron path stays
  reachable only through `ALLOW_N8N_ARM`. Both scripts remain byte-identical to
  `238d1ab`. The module docstring's stale forward reference to a fail-closed condition
  Phase 67 was going to build is rewritten to state what Phase 67 actually did (D-67-09
  reversed that plan — autonomy discloses an unknown ceiling/balance/allowance key and
  proceeds, unchanged from Phase 68's attended path).

## Task Commits

Task 1 made no code changes (checkpoint, answered before this executor was spawned;
`git status --porcelain -- operator-claude-plugin/` was empty at that point, per its own
`<verify>`). Task 2 and Task 3 each produced a RED then GREEN commit (TDD):

1. **Task 2 RED** — `a1a6fd7` (test) — 16 failing tests, all on the target
   `AttributeError: module 'config_gate' has no attribute 'autonomy_enabled'` (or
   `AUTONOMY_SETTINGS_KEY`), not a collection/import error.
2. **Task 2 GREEN** — `faec19d` (feat) — `autonomy_enabled` + the two constants +
   the example-config note; 41/41 pass (`test_autonomy_levels.py` +
   `test_config_gate.py`).
3. **Task 3 RED** — `1cb4690` (test) — two new tests deliberately mis-scoped at
   `config_gate.py` (which does define the four symbols) to prove the assertion trips
   before it is pointed at the real target; 2 failed / 3 passed (pre-existing tests
   unmodified). Docstring correction included in the same commit.
4. **Task 3 GREEN** — `ed70837` (fix) — rescoped the two tests to `scheduled_arm.py` /
   `n8n_arming.py`; 5/5 pass in `test_headless_grant_boundary.py`.

No REFACTOR commit — both GREEN implementations were already minimal; nothing to clean
up without changing behavior.

## Files Created/Modified
- `operator-claude-plugin/scripts/config_gate.py` — `AUTONOMY_SETTINGS_KEY`,
  `AUTONOMY_LEVELS`, `autonomy_enabled(config, level)`, in their own commented section
  below `WRITE_GRANT_SETTINGS_KEY`
- `operator-claude-plugin/config/operator.local.example.json` — `autonomy` object (all
  three levels `true`) + `_autonomy_note`, adjacent to `_allow_write_grants_note`
- `operator-claude-plugin/tests/test_autonomy_levels.py` (new) — 16 tests covering every
  bullet in Task 2's `<behavior>`, including a real `load_config()` round trip and the
  `CAPABILITY_KEYS` separation test
- `operator-claude-plugin/tests/test_headless_grant_boundary.py` — 2 new tests + a
  corrected module docstring; the 3 pre-existing tests are byte-for-byte unmodified

## Decisions Made

**Task 1, Question A — verbatim, recorded for 67-04 to quote:**
> "On 2026-09-07 the operator reversed the 57-05 Task 4 option-a decision: autonomy is
> ON by default for read-only, spend-no-write and write; an unattended round discloses
> an unknown ceiling, balance or allowance key and proceeds; allow_write_grants and
> ALLOW_N8N_ARM remain the only authorities."

**Task 1, Question B — four renderings, all as proposed:**
1. **Key shape:** one `autonomy` object holding `read_only`, `spend_no_write`, `write` —
   three independently settable keys under one parent, not a flat boolean and not three
   top-level keys.
2. **Absence:** an absent `autonomy` object, and an absent level inside a present one,
   both read ON (D-67-03/D-67-10) — implemented as an explicit code default, not a copy
   of `write_grants_enabled`'s `is True` identity-on-absence pattern. The distinction is
   documented in a comment at the read site in `config_gate.py`.
3. **Near-miss:** `b-near-miss-asks`. Only the JSON boolean `true` (or absence) reads ON;
   `"true"`, `"false"`, `0`, `1`, `"yes"`, `null` all read OFF.
4. **Malformed parent:** `b-malformed-off`. `{"autonomy": true}` reads OFF for every
   level, never raises.

**One deviation from 67-PATTERNS.md's earlier sketch, made necessary by Task 1's
answer:** the pattern map's draft implementation used `(config or {}).get(AUTONOMY_
SETTINGS_KEY, {}).get(level, True) is not False`, which would read a near-miss value
(e.g. the string `"false"`) as ON. Task 1's recorded answer (`b-near-miss-asks`) requires
the opposite — near-miss reads OFF. The shipped implementation instead reads the parent
object, returns `True` immediately if it is absent, `False` immediately if it is present
but not a `dict`, and otherwise `parent.get(level, True) is True` — a single identity
comparison that reads absent-level as ON and every non-`True` present value (including an
explicit `null`) as OFF. This is not a plan deviation in the Rule 1-4 sense — it is
following the plan's own Task 2 `<action>` text and Task 1's recorded checkpoint answer
over the pattern map's earlier, superseded draft, exactly as the pattern map itself
anticipates ("Do NOT reuse `write_grants_enabled`'s identity-on-absence shape... " was
correct; the specific `is not False` expression was the part Task 1's answer overrode).

## Deviations from Plan

None — plan executed exactly as written, including the pattern-map/checkpoint-answer
reconciliation described above (which the plan's own Task 1 → Task 2 sequencing exists to
resolve, not an unplanned deviation).

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. `n8n_url`/`webhook_secret`/etc. are
unaffected by this plan.

## Next Phase Readiness

`config_gate.autonomy_enabled` and the three level names are ready for 67-02 to wire into
the batch skills' ask-or-proceed switch sites. The operator's verbatim Question A answer
above is ready for 67-04 to quote into `backend-control/SKILL.md`. No blockers: full
plugin suite (2664 passed / 5 skipped) and the n8n harness (940 passed) are green, and
`operator-claude-plugin/scripts/` diffs to exactly `config_gate.py` since `238d1ab` — the
zero-`n8n/`-diff and byte-identical-arming-scripts invariants both hold.

---
*Phase: 67-an-autonomy-flag-with-sensible-defaults*
*Completed: 2026-09-07*
