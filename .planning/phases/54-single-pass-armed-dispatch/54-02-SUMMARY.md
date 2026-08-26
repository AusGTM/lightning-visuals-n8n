---
phase: 54-single-pass-armed-dispatch
plan: 02
subsystem: operator-plugin
tags: [reporting, hubspot, enrichment, docs]

requires: []
provides:
  - "report_enrichment._ACTION_TO_OUTCOME/_OUTCOME_REASON — two new named outcomes (held, previewed) for the two legitimate two-pass shapes, replacing an `unknown` render"
  - "enrich-records/SKILL.md §2 — the identity-hold paragraph now states the second-pass cost, pinned by a contract test"
  - "v1.1-REQUIREMENTS.md G-3 amendment — dated, pointing at 54-MEASUREMENT.md, naming the shipped fix and the two legitimate two-pass shapes"
  - "v1.1-ROADMAP.md Phase 54 entry amendment — the stale write_blocked-then-arm bullet replaced; the projection bullet now points at the measured figures"
affects: [54-03, 54-04, 54-05]

actuals:
  tokens: 3368
  tasks: 3
  commits: 4

tech-stack:
  added: []
  patterns:
    - "an exact-dict-equality counts pin re-pointed in place with a dated comment, rather than deleted, when a new outcome word is added to a fixed enum (mirrors the D-53-01/D-53-05 discipline)"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/report_enrichment.py
    - operator-claude-plugin/tests/test_report_enrichment.py
    - operator-claude-plugin/tests/test_watch_settle_reporting.py
    - operator-claude-plugin/skills/enrich-records/SKILL.md
    - operator-claude-plugin/tests/test_enrich_skill_contract.py
    - .planning/milestones/v1.1-REQUIREMENTS.md
    - .planning/milestones/v1.1-ROADMAP.md

key-decisions:
  - "Outcome words chosen: needs_match_review -> \"held\", proposed -> \"previewed\" (past-tense, matching created/enriched/blocked/skipped's register). Neither joins SUCCESS_OUTCOMES."
  - "Checked, not assumed: no operator-facing skill offers the companies propose=True form today. Grepped all three lane skills (enrich-records, enrich-before-ingest, contact-upload) for any surface that sets spec['propose'] or exposes a look-only rehearsal for companies — none exists. The 'rows' form's own unconditional mode:propose (used by preingest.py's fetch_matches for pre-ingest identity matching) is a DIFFERENT, already-free (providers=[]) lookup and is out of this task's scope — it costs nothing to repeat, so it needs no second-pass-cost disclosure. Per the plan's own instruction, no wording was invented for a surface that does not exist; Task 1's report outcome (`previewed`) is the disclosure that stands ready for whenever a surface is added."
  - "Both milestone-document edits used Edit only, never Write, to protect sibling phase entries (T-54-07). Phase-entry count in v1.1-ROADMAP.md unchanged (7 before and after); diff size 14 lines, well under the plan's 30-line ceiling."
  - "G-3's original 2026-08-25 defect text is preserved verbatim as recorded history; the correction is a dated amendment appended after it, not an overwrite -- the milestone document is this project's audit trail."
  - "The roadmap's projection bullet (2 provider passes -> 1, ~$0.07 -> ~$0.035, 2 executions -> 1) is left as the projection it always was; a Measured pointer to 54-MEASUREMENT.md was added beside it, not substituted for it (OP-54-05: a projection is never silently promoted to a measurement)."

requirements-completed: []

coverage:
  - id: D1
    description: "A row whose action is needs_match_review renders as a named outcome (held), not unknown, with a reason stating the second-pass cost; a row whose action is proposed renders as previewed, same discipline. Neither joins SUCCESS_OUTCOMES."
    requirement: G-3
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_report_enrichment.py::test_needs_match_review_row_renders_as_held_never_unknown_or_a_success, ::test_proposed_row_renders_as_previewed_never_unknown_or_a_success"
        status: pass
    human_judgment: false
  - id: D2
    description: "enrich-records/SKILL.md's identity-hold paragraph states that confirming a held match and sending it again re-runs the whole lookup and costs the same as the first run did"
    requirement: G-3
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_skill_contract.py::test_the_skill_states_the_second_pass_cost_of_confirming_a_held_identity_match — verified live to fail when the sentence is deleted, then restored"
        status: pass
    human_judgment: false
  - id: D3
    description: "G-3's REQUIREMENTS.md paragraph and the Phase 54 ROADMAP.md entry both amended in place (Edit only) to name the shipped fix, the measurement artifact, and the two legitimate remaining two-pass shapes"
    requirement: G-3
    verification:
      - kind: other
        ref: "grep-based acceptance checks in 54-02-PLAN.md (authorize_ungranted_send, 54-MEASUREMENT.md, OP-54-02 all present; phase-entry count unchanged at 7; roadmap diff-stat 14 lines)"
        status: pass
    human_judgment: false

duration: ~25min
completed: 2026-08-27
status: complete
---

# Phase 54 Plan 02: Name the two legitimate two-pass shapes and correct stale G-3 text Summary

**Two shapes that still cost a second full pass — an identity hold and a look-only rehearsal — now say so where the operator reads them, and the milestone's own G-3 text no longer describes a defect that shipped a day earlier.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 3 completed (plus one downstream test fix)
- **Files modified:** 7

## Accomplishments

- `report_enrichment._ACTION_TO_OUTCOME` gained two entries: `needs_match_review` -> `held`, `proposed` -> `previewed`. Neither joins `SUCCESS_OUTCOMES`. Both `_OUTCOME_REASON` strings state, in operator register, that proceeding costs a second full pass — no node names, no "waterfall", no "write-safety gate" in the text an operator reads.
- `enrich-records/SKILL.md` §2's identity paragraph — which already said a same-surname match is held rather than written over — now adds one sentence: confirming it and sending it again re-runs the whole lookup and costs the same as the first run did. Pinned by a new contract test, verified live to fail when the sentence is removed.
- Confirmed by grep across all three lane skills that no operator-facing surface offers the companies `propose=True` look-only form today (it is reachable only through `enrichment.build_envelope`, used by the Phase 58 spike). No wording was invented for a surface that does not exist, per the plan's own instruction.
- G-3's paragraph in `v1.1-REQUIREMENTS.md` gained a dated amendment (2026-08-27) naming the shipped fix (`write_grant.authorize_ungranted_send`, plugin 0.18.0, live-verified 2026-08-26), pointing at `54-MEASUREMENT.md`'s measured saving, naming the two legitimate two-pass shapes, and citing the SJ-3 residual (OP-54-02, WINDOWS.md entry 27). The original defect text is preserved verbatim above it.
- The Phase 54 entry in `v1.1-ROADMAP.md` had its stale "write_blocked-then-arm path stays reachable" bullet replaced with the two shapes that ARE reachable, and gained a Measured pointer beside its existing projection numbers — the projection itself is untouched.

## Task Commits

1. **Task 1: Name the two outcomes the report currently renders as unknown** - `466f026` (feat)
2. **Task 2: Put the second-pass cost beside the identity hold** - `1bf8f40` (feat)
3. **Task 3: Correct the G-3 and Phase 54 text that still describes a fixed defect** - `98edcb8` (docs)
4. **[Deviation, Rule 1] Re-point `test_watch_settle_reporting`'s own counts pin** - `29c4fe1` (fix)

## Files Created/Modified

- `operator-claude-plugin/scripts/report_enrichment.py` - two new `_ACTION_TO_OUTCOME`/`_OUTCOME_REASON` entries, `_empty_counts()` grown to match
- `operator-claude-plugin/tests/test_report_enrichment.py` - two new outcome tests; the exact-dict-equality counts pin re-pointed in place with a dated comment
- `operator-claude-plugin/tests/test_watch_settle_reporting.py` - its own copy of the same counts pin, re-pointed the same way (Rule 1)
- `operator-claude-plugin/skills/enrich-records/SKILL.md` - one sentence added to §2's identity paragraph
- `operator-claude-plugin/tests/test_enrich_skill_contract.py` - new contract test pinning the added sentence
- `.planning/milestones/v1.1-REQUIREMENTS.md` - dated amendment appended to G-3's paragraph
- `.planning/milestones/v1.1-ROADMAP.md` - Phase 54 entry's stale bullet replaced; Measured pointer added to the projection bullet

## Decisions Made

- **Outcome words:** `needs_match_review` -> `held`, `proposed` -> `previewed` — past-tense, matching the existing `created`/`enriched`/`blocked`/`skipped` register.
- **Checked, not assumed, that no operator-facing look-only surface exists for companies.** Grepped `enrich-records`, `enrich-before-ingest`, and `contact-upload` SKILL.md files for any path that sets `spec["propose"]`; none exists. The `rows` form's own unconditional `mode: propose` (used by `preingest.py`'s `fetch_matches` for pre-ingest identity matching, sending `providers=[]`) is a separate, already-free lookup and out of this task's scope — no cost, no disclosure needed.
- **Milestone documents edited with `Edit` only**, never `Write`, per the plan's explicit prohibition (T-54-07). Phase-entry count in the roadmap is unchanged (7); the roadmap diff is 14 lines, under the 30-line ceiling.
- **G-3's original defect text is preserved as recorded history**, with the correction appended as a dated amendment — the milestone document is this project's audit trail, not a place for silent overwrites.
- **The roadmap's projection numbers stay a projection**; a Measured pointer to `54-MEASUREMENT.md` was added beside them, not substituted for them (OP-54-05).

## Deviations from Plan

**[Rule 1 - Bug] `test_watch_settle_reporting.py` carried its own copy of the same exact-dict-equality counts pin, broken by Task 1's change.**
- **Found during:** running the full plugin suite after Task 1's verify command passed (the plan's own `<automated>` verify was scoped to `test_report_enrichment.py`/`test_report_sufficiency.py`, which did not catch this).
- **Issue:** `test_settled_report_renders_the_same_counts_as_report_enrichment_directly` asserts the same fixture's `counts` dict against a literal without `held`/`previewed`, and started failing once `_empty_counts()` grew.
- **Fix:** re-pointed in place with a dated comment, same discipline as the pin Task 1 moved.
- **Files modified:** `operator-claude-plugin/tests/test_watch_settle_reporting.py`
- **Commit:** `29c4fe1`

## Issues Encountered

None beyond the deviation above. `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` is fully green (1619 passed, 5 skipped) — the plan's own verification note about "4 known `test_merge_policy.py` failures, outside this path" did not surface; that file is not under `operator-claude-plugin/tests/`.

## Known Gap (not fixed, out of scope)

`recompute_refused` (the on-demand veto-recompute lane's own refusal action, `Company Gate` node — see CLAUDE.md §13.0) is a THIRD non-writing outcome, but it terminates by routing directly to `Build Response` without ever passing through `Decide Company Action`. `enrichment_row_ledger()` reads only the two decision nodes (`Decide Company Action`/`Decide Action`), so a `recompute_refused` row is silently ABSENT from the ledger this report builds — not rendered `unknown`, simply never counted. This is a distinct, pre-existing gap this plan did not introduce and was not scoped to fix (the recompute lane is admin/script-driven, not reachable through any of the three lane skills this plan touches). Recorded here as a finding for whoever next touches `report_enrichment.py`'s ledger-reading scope.

## User Setup Required

None — every change in this plan is offline text editing and pure-Python rendering. Execution budget spent: 0 n8n executions, 0 provider credits, 0 Anthropic calls (verified: no live call, no arming, no network in any test — `no_network` autouse fixture guards the whole suite).

## Next Phase Readiness

Plans 54-03 through 54-05 are unblocked by this plan and do not depend on anything it changed beyond the report/skill/milestone-doc text.

---
*Phase: 54-single-pass-armed-dispatch*
*Completed: 2026-08-27*

## Self-Check: PASSED

`54-02-SUMMARY.md` found on disk; all 4 commit hashes (`466f026`, `1bf8f40`, `98edcb8`,
`29c4fe1`) found in `git log --oneline --all`.
