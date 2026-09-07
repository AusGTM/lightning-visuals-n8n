---
phase: 67-an-autonomy-flag-with-sensible-defaults
plan: 02
subsystem: operator-plugin-skills
tags: [autonomy, config_gate, write-grant, d-67-09, disclosure, prose-contract]

# Dependency graph
requires:
  - phase: 67-an-autonomy-flag-with-sensible-defaults
    provides: "67-01's config_gate.AUTONOMY_SETTINGS_KEY / AUTONOMY_LEVELS /
      autonomy_enabled(config, level) — the one reader every batch skill's
      ask-or-proceed switch now calls"
provides:
  - "one config_gate.autonomy_enabled(config, '<level>') read at the single
    ask-or-proceed switch site Phase 68 left in each of the four batch skills —
    'write' at enrich-before-ingest, enrich-records, contact-upload; 'spend_no_write'
    at suggest-contacts"
  - "the D-67-09 disclosure sentence and the three-unknowns-by-cause sentence,
    replacing the stale 'Phase 67's to add' forward reference at three skills and
    appended fresh at suggest-contacts' shared unknown-verdict sentence"
  - "the pre-start over-ceiling refusal's missing end-of-run report stated as a
    named limitation (D-67-13, RUN-05) at all four skills"
  - "tests/test_autonomy_switch_prose.py — TARGETS over all four batch skills,
    parametrized behaviour assertions, and three structural assertions"
affects: [67-03, 67-04]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 7144
  tasks: 3
  commits: 4
  plan_head_before: 7011828e82c286bb78d29a3cb557aed218c81d2f

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "The autonomy read lives in its own single-call python fence, immediately
      before write_grant.plan_grant( in the same numbered-step span — a second
      scripts-module call sharing that fence would give
      test_skill_sequence_coverage.py's ratchet a new >=2-call sequence identity to
      register, which this plan must not create."
    - "Template-once, vary-the-noun: three of the four skills' four edits (autonomy
      read, off-path, D-67-09 disclosure, refusal limitation) are byte-identical in
      wording, varying only the level string and the run/send noun already native to
      each file — read side by side, per the plan's own <verification> instruction."
    - "A skill with no pre-existing two-phase-ask literal (suggest-contacts) gets an
      off-path sentence that describes asking directly, rather than pointing at a
      documented fallback that does not exist in that file — the one deliberate
      content divergence among the four."

key-files:
  created:
    - operator-claude-plugin/tests/test_autonomy_switch_prose.py
  modified:
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/skills/enrich-records/SKILL.md
    - operator-claude-plugin/skills/contact-upload/SKILL.md
    - operator-claude-plugin/skills/suggest-contacts/SKILL.md

key-decisions:
  - "Task 1 (checkpoint:decision, gate=\"blocking-human\") — answered by the operator
    before this executor was spawned: option `as-proposed`, ship all four items
    exactly as the plan's <context> describes them. Recorded verbatim under Decisions
    Made below; Task 2 and Task 3 wrote the confirmed wording, not a re-ask."
  - "Deviation (Rule 3 — blocking issue in the plan text itself): Task 3's acceptance
    criteria and the plan's own <action> literally instruct a structural assertion
    that 'Phase 67's to' appears in zero files under operator-claude-plugin/skills/ —
    but backend-control/SKILL.md:116 carries its OWN, unrelated forward reference (a
    different decision, D-68-04, the headless/cron gate, explicitly retired by
    67-04-PLAN.md, not this plan), and this plan's own prohibitions explicitly forbid
    editing backend-control/SKILL.md at all (D-67-12). The two constraints cannot
    both hold literally. Resolved by excluding backend-control/SKILL.md BY NAME from
    the structural check (not by narrowing to TARGETS, which would also silently stop
    checking review-triage and the read-only skills) — verified against 67-04-PLAN.md
    itself, which explicitly claims that exact line for its own later retirement.
    Documented in the test file's module docstring and in this SUMMARY so
    /gsd-verify-work does not re-flag it as an oversight."
  - "suggest-contacts' off-path sentence deliberately does not say 'take the
    two-phase ask this skill already documents' — unlike the other three skills, it
    never had one, even before this phase (68-02-SUMMARY.md: 'suggest-contacts never
    had its own independent ungranted-ask literal ... this skill has no survives
    literal in the test's TARGETS entry'). Its off-path instead asks for an explicit
    go-ahead before open_grant. This is the one wording divergence among the four
    skills' edits; every other sentence mirrors enrich-before-ingest's wording
    exactly."
  - "suggest-contacts' autonomy read is placed AFTER the role-selection ask (which
    stays a genuine, pinned question at every autonomy level, D-68-02) and
    immediately before its own plan_grant call — not at the top of step 3, where it
    would sit 'proceeds without asking' directly above a question that still asks
    unconditionally."

patterns-established:
  - "Single-call autonomy-read fence: config_gate.autonomy_enabled(config, level) is
    the only statement in its own fenced python block, keeping it invisible to the
    >=2-call sequence-coverage ratchet by construction, not by an added exclusion
    entry."

requirements-completed: [AUTO-01, AUTO-02, AUTO-03]

coverage:
  - id: D1
    description: "Each of the four batch skills reads its own autonomy level once,
      at the single ask-or-proceed switch site Phase 68 left, before
      write_grant.plan_grant(, in its own single-call fence"
    requirement: AUTO-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_autonomy_switch_prose.py#test_autonomy_read_calls_config_gate_once_with_the_skills_own_level"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_autonomy_switch_prose.py#test_autonomy_read_sits_in_its_own_single_call_fence"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_autonomy_switch_prose.py#test_autonomy_read_precedes_plan_grant"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_skill_sequence_coverage.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "No refusal exists on CEILING_UNKNOWN, an unread provider balance,
      or a missing n8n_monthly_execution_allowance key — all three are disclosed by
      cause and the round proceeds (D-67-09, reversing D-67-05)"
    requirement: AUTO-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_autonomy_switch_prose.py#test_all_three_unknown_causes_are_named"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_autonomy_switch_prose.py#test_the_unsampled_ceiling_verdict_is_still_named_and_disclosed"
        status: pass
      - kind: other
        ref: "git diff --quiet 238d1ab -- operator-claude-plugin/scripts/write_grant.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "The off-path (autonomy off) still takes the pre-existing two-phase
      ask at three skills, and an explicit-ask fallback at suggest-contacts; every
      genuine decision point (role selection, held-row vocabulary, undecided
      company-domain row, per-header confirmation) still stops and asks at every
      level; review-triage and backend-control are untouched"
    requirement: AUTO-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_disclosure_audit.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_interrupt_semantics.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_implicit_approval_contract.py"
        status: pass
      - kind: other
        ref: "git diff --quiet 238d1ab -- operator-claude-plugin/skills/review-triage/SKILL.md operator-claude-plugin/skills/backend-control/SKILL.md"
        status: pass
    human_judgment: false
  - id: D4
    description: "The pre-start over-ceiling refusal's missing end-of-run report is
      stated as a named limitation (D-67-13, RUN-05), not left silent, at all four
      skills"
    requirement: AUTO-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_autonomy_switch_prose.py#test_the_pre_start_refusal_limitation_is_stated"
        status: pass
    human_judgment: false
  - id: D5
    description: "No plugin script edited; write_grant.py/scheduled_arm.py/
      n8n_arming.py byte-identical to 238d1ab; zero n8n/ diff; the substring 'tier'
      introduced nowhere"
    verification:
      - kind: other
        ref: "git diff --quiet 238d1ab -- operator-claude-plugin/scripts/scheduled_arm.py operator-claude-plugin/scripts/n8n_arming.py operator-claude-plugin/scripts/write_grant.py"
        status: pass
      - kind: other
        ref: "git status --porcelain -- n8n/ scripts/build_cloud_workflows.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_report_enrichment.py"
        status: pass
    human_judgment: false

# Metrics
duration: ~25min
completed: 2026-09-07
status: complete
---

# Phase 67 Plan 02: An autonomy flag with sensible defaults — the four batch skills read it, D-67-09 disclosed Summary

**All four batch skills (enrich-before-ingest, enrich-records, contact-upload,
suggest-contacts) now read `config_gate.autonomy_enabled(config, level)` at their one
switch site, disclose all three unknown-bound causes without refusing (D-67-09
reversing D-67-05), and retire the stale "Phase 67's to add" promise everywhere this
plan is permitted to touch.**

## Performance

- **Duration:** ~25 min
- **Started:** ~2026-09-07T07:35:00Z (Task 1 answered by the operator before this
  executor was spawned; timestamp approximate — first RED commit `17a7bba` landed at
  2026-09-07T17:54:04+10:00 / 2026-09-07T07:54:04Z after the reading/setup pass)
- **Completed:** 2026-09-07T07:59:13Z
- **Tasks:** 3 (Task 1 checkpoint answered pre-spawn; Task 2 and Task 3 executed here,
  each RED then GREEN)
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments
- Task 1 (checkpoint:decision, `gate="blocking-human"`): operator confirmed
  `as-proposed` — all four D-67-09 rendering items ship exactly as the plan's
  `<context>` describes. Recorded verbatim below.
- Task 2 (tracer, TDD): `enrich-before-ingest/SKILL.md` step 5 gets the autonomy read,
  off-path sentence, D-67-09 disclosure + three-unknowns sentence, and the pre-start
  refusal limitation. Tracer feedback gate: auto-mode active
  (`workflow._auto_chain_active: true`), tracer `<verify>` re-run and passed —
  "⚡ Tracer verified end-to-end — expanding" — proceeded straight to Task 3 with no
  checkpoint.
- Task 3 (auto, TDD): the same four edits mirrored at `enrich-records`,
  `contact-upload` (level `"write"`) and `suggest-contacts` (level
  `"spend_no_write"`, one wording divergence — see Decisions Made).
  `test_autonomy_switch_prose.py`'s `TARGETS` widened to all four skills; three
  structural assertions added (exact `TARGETS` size, every path exists, "Phase 67's
  to" retired everywhere except the explicitly-excluded `backend-control/SKILL.md`).

## Task Commits

Task 1 made no code changes (checkpoint, answered before this executor was spawned).
Task 2 and Task 3 each produced a RED then GREEN commit (TDD):

1. **Task 2 RED** — `17a7bba` (test) — 8 failing tests in
   `test_autonomy_switch_prose.py` against the unedited `enrich-before-ingest/SKILL.md`.
   Full suite: 8 failed / 2667 passed / 5 skipped, all failures isolated to the new
   file — no collection error.
2. **Task 2 GREEN** — `2647f67` (feat) — the four edits land at
   `enrich-before-ingest/SKILL.md`; 80/80 across the task's three-file verify; full
   suite 2675 passed / 5 skipped; `node --test tests/n8n/*.test.mjs` 940/940
   untouched.
3. **Task 3 RED** — `8ebf5d6` (test) — `TARGETS` widened to four entries plus three
   structural assertions, deliberately still pointed at the three unedited skills. 24
   failed / 2688 passed / 5 skipped, all 24 failures isolated to the new file's
   assertions against the three still-unedited skills.
4. **Task 3 GREEN** — `dab9704` (feat) — the four edits mirrored at `enrich-records`,
   `contact-upload`, `suggest-contacts`; 48/48 in the prose-contract file, full plugin
   suite 2712 passed / 5 skipped, `node --test tests/n8n/*.test.mjs` 940/940.

No REFACTOR commit at either task — both GREEN implementations were the plan's own
specified minimal edits; nothing to clean up without changing wording the plan pins.

## Files Created/Modified
- `operator-claude-plugin/tests/test_autonomy_switch_prose.py` (new) — `TARGETS` over
  all four batch skills (path, level string, open-step tuple); `_normalized` /
  `_numbered_step_spans` / `_step` copied from `test_implicit_approval_contract.py`'s
  own idiom; a `_fence_containing` helper proving the autonomy read's single-call
  fence; 11 parametrized behaviour assertions + 3 structural assertions
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — step 5: autonomy
  read + off-path sentence before the pre-existing "does not ask — it states"
  paragraph; D-67-09 disclosure + three-unknowns sentence replacing "Phase 67's to
  add"; pre-start refusal limitation appended
- `operator-claude-plugin/skills/enrich-records/SKILL.md` — same four edits at step 5
  (level `"write"`)
- `operator-claude-plugin/skills/contact-upload/SKILL.md` — same four edits at step 4
  (level `"write"`)
- `operator-claude-plugin/skills/suggest-contacts/SKILL.md` — autonomy read at step 3
  (level `"spend_no_write"`, placed after the role/cap ask, before `plan_grant`),
  D-67-09 disclosure + three-unknowns sentence appended after step 4's existing
  `"unknown"` sentence, refusal limitation appended to step 3's own `plan_grant`
  refusal paragraph

## Decisions Made

**Task 1 — verbatim, `as-proposed`, all four items (operator, 2026-09-07):**
1. **The sentence:** Phase 67 adds no fence here either — an autonomous round
   discloses an unknown state and proceeds, exactly as the attended path already does
   (D-57-02, D-68-10); the bounds that remain are an `"over"` ceiling verdict and
   `CapRefused`.
2. **The three unknowns, named by cause:** an unsampled or unreadable monthly
   ceiling; a provider balance the backend could not read (which
   `write_grant._headroom` already renders `unconfirmed` and never reads as
   headroom); an unconfigured `n8n_monthly_execution_allowance` key, one of the
   causes of the first rather than a separate fourth check.
3. **The pre-start `"over"` refusal:** stated as reportless — `plan_grant` writes
   nothing durable on that refusal, so the relayed `proposal["detail"]` plus the STOP
   is the whole account; the affordable-subset trimming that would fix this is named
   as unbuilt (RUN-05 / D-67-13).
4. **The off-path line:** names `autonomy.<level>` and `operator.local.json`, and
   doubles as AUTO-02's first-round notice at the round itself.

**Deviation (Rule 3 — blocking issue found IN the plan text itself, not the codebase):**
Task 3's `<action>` and one acceptance-criteria bullet literally instruct a
structural pytest assertion that `"Phase 67's to"` appears in **zero** files under
`operator-claude-plugin/skills/`. But `backend-control/SKILL.md:116` carries its OWN,
unrelated forward reference ("the unattended gate itself ... is Phase 67's to open
(D-68-04)") — a different decision (D-68-04, the headless/cron gate) from D-67-09 (the
four batch skills' pre-spend disclosure, which this plan retires). This plan's own
`<prohibitions>` explicitly forbid editing `backend-control/SKILL.md` at all
(D-67-12: it is in no autonomy level), and `67-04-PLAN.md` explicitly claims that
exact line for its own later retirement — confirmed by reading `67-04-PLAN.md`
directly (`is Phase 67's to open` named at its own line 104, 133, 138, 146). The two
instructions cannot both be satisfied literally. **Resolved by excluding
`backend-control/SKILL.md` BY NAME** from the structural absence check (not by
narrowing the check to `TARGETS`, which would also silently stop checking the two
read-only skills and `review-triage` — strictly weaker than the by-name exclusion).
Documented in the test file's own module docstring so a future reader — including
`/gsd-verify-work` — does not read the narrower scope as an oversight. No file outside
this plan's declared `files_modified` was touched to resolve this.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking, plan-text conflict] `backend-control/SKILL.md` excluded by
name from the "Phase 67's to" structural absence check**
- **Found during:** Task 3, writing the RED structural assertions
- **Issue:** the plan's own acceptance criteria demanded a check that would fail
  while the plan's own prohibitions demanded the file that would trip it stay
  untouched
- **Fix:** see Decisions Made above — the by-name exclusion, cross-checked against
  `67-04-PLAN.md`'s own explicit claim on that exact line
- **Files modified:** `operator-claude-plugin/tests/test_autonomy_switch_prose.py`
  (the exclusion and its documentation)
- **Verification:** `test_phase_67s_to_appears_in_no_skill_except_the_excluded_backend_control`
  passes; `git diff --quiet 238d1ab -- operator-claude-plugin/skills/backend-control/SKILL.md`
  exits 0 (confirmed untouched)
- **Committed in:** `8ebf5d6` (RED, the exclusion is present from the first
  structural-assertion commit) / `dab9704` (GREEN, confirms the assertion passes)

---

**Total deviations:** 1 auto-fixed (1 blocking, plan-text self-conflict).
**Impact on plan:** No scope creep — the fix is entirely inside the one test file
this plan already owns; no additional file was touched, and the excluded file stays
byte-identical to `238d1ab` as every other acceptance criterion in this plan already
required.

## Known Stubs

None.

## Threat Flags

None beyond what the plan's own `<threat_model>` already names — no new surface
introduced outside the four skill bodies and the one test file.

## Issues Encountered

One shell-level false negative, noted for the record and not a defect: the acceptance
criterion `grep -c 'not bounded by the monthly ceiling this run'` on
`enrich-before-ingest/SKILL.md` returns `0` via plain single-line `grep`, because the
pre-existing sentence (unchanged by this plan, confirmed present at commit `7011828`
before any edit) wraps across a markdown line break. The authoritative check is the
`_normalized()`-based pytest assertion
(`test_the_unsampled_ceiling_verdict_is_still_named_and_disclosed`), which collapses
whitespace exactly as `test_implicit_approval_contract.py`'s own passing check for the
same literal already does, and it passes for all four skills.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

67-03 (the MID-RUN ceiling stop, per Task 1's context note) and 67-04 (the
`backend-control/SKILL.md` D-68-04 reversal record, which explicitly claims the
"Phase 67's to open" line this plan deliberately left alone) are unblocked. Full
plugin suite green (2712 passed / 5 skipped) and the n8n harness green (940 passed);
`operator-claude-plugin/scripts/` diffs to exactly `config_gate.py` since `238d1ab`
(67-01's change) — zero-`n8n/`-diff and byte-identical-arming-scripts invariants both
hold.

---
*Phase: 67-an-autonomy-flag-with-sensible-defaults*
*Completed: 2026-09-07*

## Self-Check: PASSED

All key-files (created + modified) confirmed present on disk via `[ -f ]`; all four
task commit hashes (`17a7bba`, `2647f67`, `8ebf5d6`, `dab9704`) confirmed present via
`git log --oneline --all`.
