---
phase: 60-review-lane-authority
plan: 03
subsystem: auth
tags: [python, pytest, hubspot, written-records, review-decision, audit-trail]

requires:
  - phase: 60-review-lane-authority
    plan: 01
    provides: review as a grantable lane, review_decision.submit_decision(grant=...) gated by write_grant.authorize_send(lane="review")
  - phase: 59-frictionless-write-path
    provides: written_records.py (D-59-07/D-59-09/D-59-10) and its append_chunk/classify_item conventions this plan extends to the review lane
provides:
  - "written_records.REVIEW_OUTCOME_TO_OUTCOME — the review endpoint's seven outcome words mapped onto the existing eight-word ALL_OUTCOMES vocabulary"
  - "written_records.classify_review_item(item) — pure, seven-key, reason/row_id/association always None"
  - "written_records.append_chunk(..., classify=classify_item) — new keyword-only parameter letting a caller supply an alternate classifier"
  - "review_decision.submit_decision(..., run_id=None) — new keyword; envelope gains a written_records key when an append was attempted"
affects: [60-04-skill-docs]

actuals:
  tokens: 7600
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "a classify= keyword-only parameter on append_chunk lets a second call site reuse one atomic-write implementation with a different item shape, rather than a second writer function"
    - "an append is attempted iff the caller opted in (run_id given) AND the endpoint actually adjudicated the decision (result['available']) — an unavailable/unreachable response records nothing, mirroring dispatch.py's raise-before-append and chunking.dispatch_plan's DispatchError-continue precedent"
    - "a pure classifier's total fallback branch (available:False -> FAILED, no object_type -> a fixed default) stays tested even when the sole call site can never trigger it, documented as unreachable-by-construction rather than removed"

key-files:
  created: []
  modified:
    - operator-claude-plugin/scripts/written_records.py
    - operator-claude-plugin/scripts/review_decision.py
    - operator-claude-plugin/tests/test_written_records.py
    - operator-claude-plugin/tests/test_review_decision.py

key-decisions:
  - "D-60-08: a review decision now appears in the run's written_records-<run_id>.json artifact, in the artifact's own eight-word vocabulary, via a new classify_review_item rather than feeding review's five-key response shape to classify_item unmodified"
  - "REVIEW_OUTCOME_TO_OUTCOME: applied/rejected -> WRITE_ATTEMPTED (never WRITTEN — an id known before the write, and the response's own verified field is a convenience, never authority); not_allowlisted -> GATED (the deployed write gate refusing, same as write_blocked); stale/no_candidate/not_flagged -> NO_ACTION; refused -> FAILED"
  - "Deviation, resolved via advisor consult: the plan's <action> text reads as an unconditional append once run_id is set, but <behavior> Test 3 requires a raising/unreachable POST to leave no artifact entry. Resolved in favor of the behavior contract — the append is gated on result.get('available'), matching dispatch.py's raise-before-append and chunking.dispatch_plan's DispatchError-continue precedent. classify_review_item's available:False->FAILED branch and its companies object-type fallback both stay as pure-function totality guarantees, documented as unreachable from the only call site (the same LOW-4 pattern the plan itself established)"
  - "The wider try/except Exception (not OSError-only) around the review append mirrors remainder_queue.save's precedent: append_chunk propagates WrittenRecordsError by design, and a locally-built item's bookkeeping refusal must never become a mid-decision stop (D-59-10)"

requirements-completed: [D-60-08]

coverage:
  - id: D1
    description: "a review decision maps into written_records' existing seven-key entry and eight-word outcome vocabulary via classify_review_item, with reason/row_id/association fixed at None so no operator free text reaches disk through this path"
    requirement: D-60-08
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_written_records.py#test_an_applied_approve_with_a_record_id_is_write_attempted"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_written_records.py#test_not_allowlisted_is_gated_stale_family_is_no_action_refused_is_failed"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_written_records.py#test_every_review_outcome_to_outcome_value_is_in_all_outcomes"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_written_records.py#test_classify_review_item_key_set_matches_classify_item_exactly"
        status: pass
    human_judgment: false
  - id: D2
    description: "submit_decision(run_id=...) appends a successful decision to that run's own written_records file, and a second run_id gets its own separate file (D-59-09)"
    requirement: D-60-08
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_review_decision.py#test_a_successful_approve_writes_one_entry_and_the_envelope_gains_written_records_true"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_review_decision.py#test_three_decisions_under_one_run_id_produce_three_entries_in_one_file"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_review_decision.py#test_a_fourth_decision_under_a_different_run_id_produces_a_separate_file"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_review_decision.py#test_with_run_id_none_nothing_is_written_and_no_path_is_resolved"
        status: pass
    human_judgment: false
  - id: D3
    description: "neither an OSError nor a WrittenRecordsError from append_chunk can stop or hide a review write's own outcome — the write's outcome is always returned, and the bookkeeping failure is reported loudly under a written_records key naming the exception type"
    requirement: D-60-08
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_review_decision.py#test_append_chunk_raising_oserror_still_returns_the_writes_own_outcome"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_review_decision.py#test_append_chunk_raising_writtenrecordserror_also_returns_the_writes_own_outcome"
        status: pass
    human_judgment: false
  - id: D4
    description: "submit_decision threads its own object_type argument into the classified entry rather than letting the classifier's fallback decide"
    requirement: D-60-08
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_review_decision.py#test_the_entry_carries_the_object_type_submit_decision_was_given"
        status: pass
    human_judgment: false

duration: ~11min
completed: 2026-09-01
status: complete
---

# Phase 60 Plan 03: A review decision in written_records' own vocabulary Summary

**A review approve/reject now lands in the run's `written_records-<run_id>.json` artifact through a new `classify_review_item`, which maps the review endpoint's seven-word outcome vocabulary onto the artifact's existing eight-word one — and no bookkeeping failure of either shape (`OSError` or `WrittenRecordsError`) can stop or hide the write's own outcome.**

## Performance

- **Duration:** ~11 min
- **Completed:** 2026-09-01T17:23:02+10:00
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `written_records.REVIEW_OUTCOME_TO_OUTCOME` added directly below `ACTION_TO_OUTCOME`: `applied`/`rejected` -> `WRITE_ATTEMPTED` (never `WRITTEN` — the id is known before the write, and the response's own `verified` field is documented as a convenience, never the authority), `not_allowlisted` -> `GATED` (the same event `write_blocked` already maps for dispatch), `stale`/`no_candidate`/`not_flagged` -> `NO_ACTION`, `refused` -> `FAILED`
- `written_records.classify_review_item(item)` added beside `classify_item`: pure, no I/O, raises `WrittenRecordsError` on a non-dict item for the same fail-loud reason. Reads a LOCALLY-BUILT item (`{object_type, record_id, decision, outcome}` — never the raw endpoint response, which carries no `action` key at all) and emits `classify_item`'s exact seven keys, with `reason`/`row_id`/`association` fixed at `None` so no operator free text ever reaches disk through this path. `object_type` falls back to `"companies"` (not `classify_item`'s `"contacts"`) when absent — documented as unreachable from the only call site, per cross-AI review LOW-4's own pattern
- `written_records.append_chunk` gained a keyword-only `classify=classify_item` parameter, so `review_decision.submit_decision` can supply `classify_review_item` without a second atomic-write implementation. Docstring's "two call sites" paragraph widened to three
- `review_decision.submit_decision` gained a keyword-only `run_id=None`. After `_post_decision` returns, when `run_id` is not `None` AND the response was `available`, the decision's outcome is appended to that run's own file via `written_records.append_chunk(..., classify=classify_review_item)`, wrapped in `try/except Exception` (wider than `OSError`, mirroring `remainder_queue.save`'s precedent) so `append_chunk`'s designed `WrittenRecordsError` propagation can never turn into a mid-decision stop. The returned envelope gains a `written_records` key (`True`/`False`/exception-type-name) only when an append was actually attempted
- Deviation resolved via advisor consult (see Decisions Made): the append is gated on `result.get("available")` rather than firing unconditionally, so a raising/unreachable POST produces no artifact entry — matching `dispatch.py`'s raise-before-append and `chunking.dispatch_plan`'s `DispatchError`-continue precedent already established in this codebase for the exact same "we never got a response" case

## Task Commits

Each task was committed atomically:

1. **Task 1: A review decision, in the artifact's own vocabulary** - `ec993d2` (feat)
2. **Task 2: Wire it at the write, and make the bookkeeping unable to stop it** - `dddc373` (feat)

**Plan metadata:** committed with this SUMMARY.

## Files Created/Modified
- `operator-claude-plugin/scripts/written_records.py` — `REVIEW_OUTCOME_TO_OUTCOME`, `classify_review_item`, `append_chunk`'s new `classify=` keyword and widened docstring
- `operator-claude-plugin/scripts/review_decision.py` — `import written_records`; `submit_decision` gained `run_id=None` and the gated append/envelope-key logic
- `operator-claude-plugin/tests/test_written_records.py` — 11 new tests: the mapping/shape cases (Test 1-6, 8 from the plan's `<behavior>`) plus three additional pure-function edge cases (forbidden-marker-elsewhere, non-dict raise, unrecognised decision word)
- `operator-claude-plugin/tests/test_review_decision.py` — 10 new tests: the six D-60-08 wiring cases from `<behavior>` (success, `run_id=None`, ordering/availability, both raise shapes, multi-decision-one-file, cross-run-file-separation, object-type pass-through) plus a source assertion for the `except Exception` count

## Decisions Made
- Followed the plan's Task 1 (`written_records.py`) exactly as written; no deviations there.
- Task 2 deviation, escalated to the advisor tool rather than guessed at: the plan's `<action>` text ("After `_post_decision` returns and only then, when `run_id` is not None...") reads as an unconditional append, but `<behavior>` Test 3 explicitly requires "a transport whose POST raises never reaches the artifact." Resolved in favor of the behavior contract — gate the append on `result.get("available")`, not just `run_id is not None`. This matches an existing precedent already in this codebase: `dispatch.py`'s `dispatch()` raises `DispatchError` before ever reaching its own `append_chunk` call when `transport()` raises, and `chunking.dispatch_plan`'s loop `continue`s past its `append_chunk` call on the same `DispatchError`. Under this design, `classify_review_item`'s `available: False -> FAILED` branch (Task 1's Test 4) becomes a pure-function totality guarantee that is unreachable from `submit_decision`, its only call site — documented in `submit_decision`'s own docstring, the same unreachable-by-construction pattern the plan itself established for `classify_review_item`'s `"companies"` object-type fallback (LOW-4).
- `written_records` key present-iff-attempted, not always-present: rather than always adding a `written_records` key (`None` when not attempted), the key is OMITTED entirely when no append was attempted (`run_id=None`, or an unavailable response) — this keeps a `run_id=None` call's envelope byte-identical to the pre-Phase-60 shape, which the plan's own Test 2 ("the returned envelope is unchanged from the no-run_id case") requires.

## Deviations from Plan

### Auto-fixed Issues

None — the one substantive deviation (the availability gate on the review append) is documented above under Decisions Made, not here, because it was a genuine ambiguity between the plan's own `<action>` and `<behavior>` sections rather than a bug discovered during implementation. It was resolved via an advisor consult before any test was written against the wrong interpretation, so no rework was needed.

---

**Total deviations:** 0 auto-fixed bugs/blockers. 1 design-ambiguity resolution (documented above), escalated for a second opinion before implementation rather than guessed and rewritten.
**Impact on plan:** No scope creep. The resolution is additive precision (a narrower, well-precedented gate condition), not a weakening of any stated must-have.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None - no external service configuration required. No HubSpot request, no n8n arm, no provider call was made — every test drives `stub_module_transport_factory` or a hand-built stub transport, never a real transport, and every `written_records` write in a test is redirected to `tmp_path` via `monkeypatch`, never the operator's real durable directory.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/written_records.py` — FOUND
- `operator-claude-plugin/scripts/review_decision.py` — FOUND
- `operator-claude-plugin/tests/test_written_records.py` — FOUND
- `operator-claude-plugin/tests/test_review_decision.py` — FOUND
- Commit `ec993d2` — FOUND in `git log`
- Commit `dddc373` — FOUND in `git log`
- `operator-claude-plugin/tests -q`: 2179 passed, 5 skipped (baseline 2158/5 at 60-02 close)
- Root `pytest -q`: 3849 passed, 154 skipped (baseline 3828/154 at 60-02 close)
- `node --test tests/n8n/*.test.mjs`: 848 pass, 0 fail (unchanged — this plan touches no JS/workflow JSON)
- `git status --porcelain n8n/` — empty
- Source assertion: `python3 -c "...set(w.REVIEW_OUTCOME_TO_OUTCOME.values()) <= w.ALL_OUTCOMES"` — exits 0
- Source assertion: `grep -c 'except Exception' operator-claude-plugin/scripts/review_decision.py` — `4` (>= 2 required; the pre-existing transport catch plus this plan's new one, plus two docstring/code mentions of the literal string)

## Next Phase Readiness
- Ready for 60-04 (skill docs — wiring `run_id`/`review_armed`/`grant` end-to-end through `review-triage/SKILL.md`, and documenting the `written_records` envelope key for the operator-facing report).
- `written_records.classify_review_item`/`REVIEW_OUTCOME_TO_OUTCOME` and `review_decision.submit_decision(run_id=...)` are available for 60-04 to build a skill-level triage-batch caller on, with no further changes to either module's core logic expected.
- No blockers. Nothing armed.

---
*Phase: 60-review-lane-authority*
*Completed: 2026-09-01*
