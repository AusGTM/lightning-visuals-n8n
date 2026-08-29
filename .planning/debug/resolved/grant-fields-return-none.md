---
status: resolved
trigger: "P5 items 1 and 2 from .planning/HANDOVER-2026-08-29-backlog.md — the write grant reports expires_at: None, and close_grant returns close_reason: None"
created: 2026-08-29
updated: 2026-08-29
resolution: not-a-defect (both items)
---

# Debug: grant fields read None

## Symptoms

### Expected behavior

1. **Expiry.** The write grant's design language is "bounded, **expiring** and revocable"
   (`.planning/HANDOVER-2026-08-29-backlog.md` § P5). A grant should therefore carry a real
   expiry that an operator or a later call can observe, and that expiry should actually bound
   the grant's lifetime.
2. **Close reason.** `close_grant(grant, reason)` should record and return the reason the grant
   was closed. The reason vocabulary is enforced, so the value is validated on the way in.

### Actual behavior

1. The grant reports `expires_at: None`. Bounded and revocable are both demonstrated by the
   operator walks; **expiring is not demonstrated**. Observed during walk run 2.
2. `close_grant` returns `close_reason: None`. The state transition itself is correct — the
   grant does become `closed`, and an invalid reason is rejected — but the returned field
   reads `None`.

### Error messages

None. Neither item raises. Both are wrong-looking values in returned/reported data, not
failures.

### Timeline

Both observed during the Phase 53 operator walks (2026-08-29), recorded as "small, verified,
unfixed" in the backlog handover. Never chased. No evidence either ever worked.

### Reproduction

Via the walk records rather than a standing repro script:
- `.planning/phases/53-operator-openable-write-grant/53-WALK-RECORD-2.md` — where
  `expires_at: None` was observed.
- `.planning/phases/53-operator-openable-write-grant/53-WALK-RECORD.md` — the first walk.
- `operator-claude-plugin/tests/test_write_grant.py`,
  `test_write_grant_guardrails.py`, `test_write_grant_surface.py` — existing grant tests.

## ORCHESTRATOR PRE-INVESTIGATION FINDING — read before forming a hypothesis

**Neither field name exists anywhere in `operator-claude-plugin/scripts/`.** Verified by the
orchestrator immediately before this session was created:

```
grep -rn "expires_at"   operator-claude-plugin/scripts/   -> no matches
grep -rn "close_reason" operator-claude-plugin/scripts/   -> no matches
grep -rn "def close_grant" operator-claude-plugin/scripts/
  -> operator-claude-plugin/scripts/write_grant.py:576
```

So `close_grant(grant, reason)` is real at `write_grant.py:576`, but no field called
`expires_at` or `close_reason` is defined in the plugin's source. The handover itself hedged
item 2 as "Cosmetic; possibly a differently-named field" — that hedge now appears to apply to
BOTH items.

This means the first question is not "why does the field read None" but **"what are these two
fields actually called, and does the grant have an expiry concept at all?"** Start from the
walk record's verbatim output and from `write_grant.py`'s real return shape. Do not assume the
handover's field names are the code's names.

Two genuinely different outcomes are possible, and they need different fixes:
- **(a) The fields exist under other names and are populated** — then this is a reporting/
  display defect in whatever renders the grant, and the handover's observation was of a
  renderer, not of the grant object.
- **(b) There is no expiry concept in the grant at all** — then "expiring" is an unimplemented
  design claim, not a bug with a None value, and the honest fix is either to implement a
  bounded expiry or to correct the design language. That is a design decision and must be put
  to the operator, not chosen unilaterally.

Distinguish (a) from (b) with evidence before proposing any fix.

## Current Focus

hypothesis: CONFIRMED for both items — see Resolution. Item 2 (`close_reason`) is a pure
  investigation/observation error, not a code defect: the real field is `closed_reason` and it
  works correctly. Item 1 (`expires_at`) is outcome (b): no wall-clock expiry concept exists by
  design (GRANT-03 explicitly scopes the grant to a batch, "not a duration"); "expiring" in the
  design language is GRANT-04's five event-triggered closes, which are implemented and tested.
test: n/a — reconciled via source read + test run, no further hypothesis testing needed.
expecting: n/a
next_action: return CHECKPOINT (decision) to the operator — item 1 is a previously-decided
  question (D-53-03, 2026-08-25 declined the exact alternative) being asked to reopen, not an
  open one; item 2 needs only a human-verify nod before archiving.

## Evidence

- timestamp: 2026-08-29 (orchestrator, pre-session)
  finding: `expires_at` and `close_reason` appear nowhere in
  `operator-claude-plugin/scripts/`; `close_grant(grant, reason)` is defined at
  `write_grant.py:576`.
- timestamp: 2026-08-29
  checked: `operator-claude-plugin/scripts/write_grant.py` in full (`open_grant` lines 530-573,
  `close_grant` lines 576-593, GRANT-04/05 comment block lines 645-689).
  found: `open_grant` sets `grant["closed_reason"] = None` at open (line 571). `close_grant`
  unconditionally sets `closed["closed_reason"] = reason` (line 592) after validating `reason`
  against `CLOSE_REASONS` (raises `ValueError` otherwise — never returns silently with a bad
  reason). No field named `expires_at`, `expiry`, or `close_reason` (without the "d") exists
  anywhere in the file. The only "expiry" concept present is GRANT-04's five named
  event-triggered closes (`CLOSED_BATCH_COMPLETE`, `CLOSED_CEILING_BREACH`, `CLOSED_REVOKED`,
  `CLOSED_SESSION_END`, `CLOSED_UNHANDLED_ERROR`, plus guardrail B's two more) — termination by
  event, not by a timestamp.
  implication: the grant's real, populated field is `closed_reason`, not `close_reason`. There
  is no time-bound expiry field to be found under any name.
- timestamp: 2026-08-29
  checked: `operator-claude-plugin/tests/test_write_grant.py` lines 1206-1247.
  found: `test_grant_04s_expiry_set_is_exactly_the_five_it_names` and
  `test_a_grant_closed_for_each_reason_carries_that_reason_by_name` (parametrized over all 5
  GRANT-04 reasons including `session_end`) both assert `closed["closed_reason"] == reason` and
  are green.
  implication: `closed_reason` is not merely present in source — it is the field a scripted test
  pins and verifies populated correctly for every GRANT-04 reason, including the exact
  `session_end` value the walk record used.
- timestamp: 2026-08-29
  checked: ran `.venv/bin/python -m pytest operator-claude-plugin/tests/test_write_grant.py -k
  "expiry_set_is_exactly or carries_that_reason_by_name or close_grant_refuses" -q`
  found: 7 passed, 0 failed.
  implication: confirms live, current behavior matches the source read — `closed_reason`
  reliably reports the close reason today, not just in the test's intent.
- timestamp: 2026-08-29
  checked: `grep -rn "close_reason\b" --include="*.py" --include="*.md" --include="*.json" .`
  (excluding matches on `closed_reason`) across the whole repo.
  found: `close_reason` (missing the "d") appears ONLY in planning prose — the walk record
  itself, the backlog handover, the ultrareview handoff, and this debug session's own trigger —
  never in any `.py` source file (the one `close_reason` hit in `.venv/`'s vendored `uvicorn`
  package is an unrelated websocket attribute).
  implication: `close_reason` was never a real field anywhere in this codebase's history. It is
  an artifact of how the walk record's author named the field when reporting on it (a plausible
  but incorrect guess at `close_grant`'s return shape, one letter short of the real
  `closed_reason`), not a renderer or display-layer bug reading the right key on a wrongly-named
  or unpopulated field.
- timestamp: 2026-08-29
  checked: `.planning/phases/53-operator-openable-write-grant/53-01-PLAN.md`'s source coverage
  audit (lines 91-98) and `.planning/ROADMAP.md`/`.planning/milestones/v1.1-ROADMAP.md`'s
  "bounded, expiring and revocable" language.
  found: REQ GRANT-03 is stated explicitly as "scoped to a named batch, **not a duration**".
  REQ GRANT-04 is stated as "expiry on completion, ceiling breach, revocation, session end,
  error" — the same five reasons implemented in `write_grant.py`'s `GRANT_04_REASONS`. The
  phase's own audit maps "The authorization is expiring and revocable" to 53-02 T2, which is
  exactly the `close_grant`/`CLOSE_REASONS` machinery already read above.
  implication: the design deliberately rejected a wall-clock/duration-based expiry in favor of
  event-triggered termination. "Expiring" was never intended to mean a timestamp field; it means
  "the grant necessarily ends, for one of five named reasons." Under that reading, GRANT-04 is
  fully implemented and item 1 is not missing anything the design asked for.
- timestamp: 2026-08-29
  checked: `grep -rn "expires_at\|expiry\|expiring" operator-claude-plugin/skills/`
  found: no matches.
  implication: rules out a renderer/display-layer surface (a skill markdown template) that
  claims or references an `expires_at` field anywhere — reinforces that no such field exists at
  any layer of the plugin, not just in `write_grant.py`.
- timestamp: 2026-08-29
  checked: `write_grant.py` lines 682-688 (the GRANT-04 comment block, "SESSION END AND
  UNHANDLED ERROR ARE CALLER-MADE CLOSES...").
  found: a wall-clock, time-based expiry was explicitly considered and rejected already. Verbatim:
  "That is D-53-03's accepted risk, put to the operator on 2026-08-25 and accepted after the
  alternative (an expiry inside the shared write-safety gate) was offered and declined."
  implication: this converts item 1 from an open design question into a PREVIOUSLY DECIDED one.
  A literal `expires_at` timestamp was on the table on 2026-08-25 and the operator chose the
  client-held, event-triggered design instead (accepting D-53-03's risk in exchange). Building
  `expires_at` now would not be a bug fix — it would reopen a decision already made and amend
  GRANT-03's "not a duration" text. This must be surfaced to the operator as such, not silently
  re-decided.

## Eliminated

- hypothesis: (a) The fields exist under other names and are populated, and this is a
  rendering/display defect in whatever surfaces the grant to the operator.
  evidence: For `close_reason`/`closed_reason` this is actually TRUE in the narrow sense that a
  differently-named field exists and is populated — but the "defect" is in the walk record's own
  observation (querying a field name that was never real), not in any plugin code, renderer, or
  skill surface. Grepping `operator-claude-plugin/skills/` for `expires_at`/`expiry`/`expiring`
  and for `close_reason` (non-`closed_`) found zero references anywhere a renderer could have
  gotten either name wrong. There is no rendering code path to fix.
  timestamp: 2026-08-29

## Resolution

root_cause: TWO DIFFERENT ROOT CAUSES, both confirmed, neither a code defect in
  `write_grant.py`:
  (1) `expires_at` — no wall-clock expiry concept exists in the grant BY DESIGN. REQ GRANT-03
  explicitly scopes the grant "to a named batch, not a duration," and REQ GRANT-04's "expiry" is
  event-triggered termination (`GRANT_04_REASONS`: batch_complete, ceiling_breach,
  operator_revocation, session_end, unhandled_error — fully implemented in `close_grant`/
  `covers`). The walk record's `expires_at: None` observation is the natural result of reading a
  key that was never defined; it is not a populated-but-wrong field, and not a display bug.
  Whether the design should ALSO carry a literal time-bound expiry is not an unresolved
  question either — it was raised and declined on 2026-08-25 (D-53-03: "an expiry inside the
  shared write-safety gate" was offered and declined in favor of the client-held, event-closed
  design). Implementing `expires_at` now would reopen that decision, not fix a bug — see
  checkpoint returned to orchestrator.
  (2) `close_reason` — pure investigation/observation error, not a code defect. The real,
  implemented, and test-pinned field is `closed_reason` (`write_grant.py:571,592`;
  `test_write_grant.py::test_a_grant_closed_for_each_reason_carries_that_reason_by_name`, green).
  `close_grant(grant, "session_end")` correctly returns `closed["closed_reason"] == "session_end"`.
  The walk record, the backlog handover, and the ultrareview handoff all queried/reported a field
  literally spelled `close_reason` (one letter short), which has never existed in this codebase.
  No fix is needed or appropriate.
fix: None applied. Item 2 required no fix — confirmed working correctly under its real field
  name (`closed_reason`); manufacturing a fix for a non-existent defect would be the wrong
  action per the debugging brief. Item 1 requires an operator decision before any fix is
  appropriate (implement a real time-bound expiry vs. correct the "expiring" design language to
  match what GRANT-04 actually delivers) — returned as a CHECKPOINT rather than chosen
  unilaterally.
verification: Item 2 verified via direct source read (`write_grant.py:571,592`) and a live test
  run (`operator-claude-plugin/tests/test_write_grant.py -k "expiry_set_is_exactly or
  carries_that_reason_by_name or close_grant_refuses"` — 7 passed). Item 1 verified as a design
  gap (not a code bug) via `53-01-PLAN.md`'s source coverage audit and the ROADMAP's own
  "expiring" language, cross-checked against `write_grant.py`'s actual GRANT-04 implementation.
files_changed:
  - .planning/HANDOVER-2026-08-29-backlog.md (P5 rows for both items struck through and closed
    with the finding; `close_reason` -> `closed_reason` corrected)
  - .planning/milestones/v1.1-ROADMAP.md (Phase 53 goal: added a note defining "expiring" as
    event-triggered per GRANT-04, naming D-53-03's declined timestamp alternative)
  - .planning/ROADMAP.md (Phase 53 line: same clarification, cross-referencing v1.1-ROADMAP.md)
  No source file was changed. No test was changed.

## OPERATOR RULINGS — 2026-08-29 (checkpoint answered)

Both items were returned as a CHECKPOINT and both were answered by the operator:

**Item 1 (`expires_at`) — "Accept as designed, reword the language."** The event-triggered
GRANT-04 definition stands; D-53-03 is NOT reopened and no wall-clock `expires_at` will be
built. The roadmap phrasing "bounded, expiring and revocable" was the thing that made this look
like a defect, so it is now qualified at both sites where a future reader meets it, naming
D-53-03 and the declined alternative explicitly. `.planning/phases/53-.../53-CONTEXT.md:10` and
`53-WALK-RECORD-2.md:304` were deliberately LEFT ALONE — the first is a historical phase
context, the second a record of what was observed at the time.

**Item 2 (`closed_reason`) — "Correct the handover, leave walk records alone."** The backlog
handover's P5 row is corrected so the wrong field name cannot send someone down this path
again. `53-WALK-RECORD-2.md` is untouched: it records what the walk observed, wrong field name
included, and amending an observation record after the fact would falsify it.

**Net outcome: zero code defects found, zero code changed, three planning documents corrected.**
The investigation's value was disproving two backlog entries, not fixing them.
