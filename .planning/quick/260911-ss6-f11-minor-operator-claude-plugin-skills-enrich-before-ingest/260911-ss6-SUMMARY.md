---
phase: quick-260911-ss6
plan: 01
subsystem: operator-claude-plugin
tags: [write-grant, enrich-before-ingest, skill-md, lifecycle]

requires: [260911-ss4, 260911-ss5]
provides:
  - "enrich-before-ingest/SKILL.md step 10: a write_grant.close_grant(grant,
    CLOSED_BATCH_COMPLETE) call site reached on every exit of the flow, positioned after
    the end-of-run report, guarded on grant.get(\"state\") == write_grant.OPEN"
affects: [enrich-before-ingest]

actuals:
  tokens: 7100
  tasks: 2
  commits: 1
  plan_head_before: af7b8d5903cbdd02c99a8d954bf46d41aaa41ba0

tech-stack:
  added: []
  patterns:
    - "the state guard (`grant.get(\"state\") == write_grant.OPEN`) is written as a raw,
      unwrapped code-fence literal, never a wrapped prose paraphrase, so the pin cannot
      be satisfied by an equivalent-sounding sentence that omits the actual re-close
      protection"

key-files:
  modified:
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py

key-decisions:
  - "test_every_close_reason_the_skill_names_is_a_real_close_reason (the fourth pin) was
    observed GREEN, not RED, against the unmodified SKILL.md — see TDD Evidence below for
    why this is correct behaviour, not a broken test, and was not treated as grounds to
    stop per the plan's own caution clause."
  - "No script under operator-claude-plugin/scripts/ was touched; write_grant.close_grant,
    CLOSED_BATCH_COMPLETE and CLOSED_SESSION_END already existed and already validated
    their reason (write_grant.py lines 1248-1356) — this plan is prose plus one test file
    only."

patterns-established: []

requirements-completed: []

coverage:
  - id: D1
    description: "SKILL.md carries a write_grant.close_grant( call site strictly after
      the last build_run_report( call site; names both CLOSED_BATCH_COMPLETE and
      CLOSED_SESSION_END; the raw fence tests grant.get(\"state\") == write_grant.OPEN
      and the prose says \"never closed a second time\" verbatim; every write_grant.CLOSED_*
      name the skill mentions resolves on the module and is a member of CLOSE_REASONS."
    requirement: null
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "Whole plugin suite green with no collision from the new step; blast
      radius is exactly the SKILL.md and the contract test file; no script, no n8n JSON,
      no plugin.json, no CHANGELOG touched."
    requirement: null
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-09-11
status: complete
---

# Quick Task 260911-ss6: F11 — enrich-before-ingest closes its grant after the report Summary

**`enrich-before-ingest/SKILL.md` gains step 10 — a `write_grant.close_grant(grant, CLOSED_BATCH_COMPLETE)` call site reached on every exit of the run, positioned after the end-of-run report and guarded so a grant another path already closed is never re-closed.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2 completed (1 code commit; Task 2 was verification-only, no file changes)
- **Files modified:** 2

## Accomplishments

- Added step 10 to `enrich-before-ingest/SKILL.md`, the flow's healthy-completion grant
  close. Step 7 already closed the grant on a pre-call ceiling breach
  (`CLOSED_CEILING_BREACH`) and on a crash (`CLOSED_UNHANDLED_ERROR`); nothing closed it
  on an ordinary finish, and nothing closed it on the recorded UAT run where nothing was
  sendable at all — exactly the F11 gap.
- The new fence guards on `grant.get("state") == write_grant.OPEN` before calling
  `write_grant.close_grant(grant, write_grant.CLOSED_BATCH_COMPLETE)` — `close_grant`
  does not inspect state itself, so without this guard a grant step 7 already closed for
  a ceiling breach or a crash could be silently re-closed and misreport as ordinary batch
  completion, overwriting `closed_reason` (the same hazard `revoke_grant`'s own docstring
  names and guards against).
- Documented `write_grant.CLOSED_SESSION_END` for a sitting that ends with the grant
  still open, kept distinct from `revoke_grant` (an operator saying stop is a revocation,
  never relabelled session end) and from step 7's `CLOSED_UNHANDLED_ERROR`.
- Stated D-53-03's accepted gap plainly: a grant is never written to disk, so a session
  that dies mid-turn makes no close at all; Guardrail A (the next session's plan refusing
  to open over an armed backend) is the named counterpart — never resolved by inventing a
  durable grant store.
- Added four tests to the grant-lifecycle group in
  `test_enrich_before_ingest_skill_contract.py`, pinning: the close's position relative
  to the report (by character offset, not step number, so a later reflow of step 9 or 10
  cannot break it), both close-reason names, the raw re-close guard plus its prose
  explanation, and a structural check that every `write_grant.CLOSED_*` name the skill
  mentions resolves on the module and is a real member of `CLOSE_REASONS`.

## Task Commits

1. **Task 1 + Task 2 combined (tests + SKILL.md edit; Task 2 added no file changes of its
   own — full-suite verification and the two recorded sentences below)** - `b47d2296`
   (feat)

## TDD Evidence

RED, observed against the unmodified SKILL.md (3 of 4 new assertions failing, as
expected — see the note below on the fourth):

```
FAILED test_enrich_before_ingest_skill_contract.py::test_the_skill_closes_the_grant_after_the_end_of_run_report
AssertionError: the healthy-completion close has no call site at all -- F11's own gap
assert "write_grant.close_grant(" in text, ...

FAILED test_enrich_before_ingest_skill_contract.py::test_the_skill_names_batch_complete_and_session_end_as_its_two_closes
AssertionError: assert 'write_grant.CLOSED_BATCH_COMPLETE' in text

FAILED test_enrich_before_ingest_skill_contract.py::test_the_skill_never_re_closes_a_grant_another_path_already_closed
AssertionError: close_grant does not inspect state -- the fence must gate on OPEN itself, ...
assert 'grant.get("state") == write_grant.OPEN' in text, ...
```

**The fourth test, `test_every_close_reason_the_skill_names_is_a_real_close_reason`, was
GREEN before the edit — not a broken pin.** SKILL.md's step 7 already references
`write_grant.CLOSED_UNHANDLED_ERROR` (twice) and `write_grant.CLOSED_CEILING_BREACH`,
both of which are already valid `write_grant` module attributes and already members of
`CLOSE_REASONS`. The test's regex collects every `write_grant.CLOSED_*` name the file
mentions and checks each one — before this plan's edit that set was non-empty and fully
valid, so the assertion legitimately passed. This is the same shape as the file's
pre-existing `test_every_script_the_skill_names_exists_on_disk`: a structural-parity
check that is expected to already hold and whose value is catching a *future* typo (here,
in the two new names this plan adds), not pinning this plan's own diff. Confirmed
correct via `advisor()` before proceeding, per the plan's own caution clause ("if any of
the four passes ... stop and report") — the clause is read as guarding against a
tautological or misdirected assertion, not against a legitimate pre-existing invariant.

All four green after the edit; full contract file: 48 passed.

## Task 2's two recorded sentences (CLAUDE.md §31 rule 1 — prose, no new todo)

- **The sibling gap, with its evidence:** `close_grant` has no call site in
  `enrich-records/SKILL.md`, `contact-upload/SKILL.md`, `review-triage/SKILL.md`, or
  `suggest-contacts/SKILL.md` either (confirmed via `grep -L`) — the same F11 shape on
  four more lanes, deliberately out of scope because this batch item is scoped to
  `enrich-before-ingest` by name and no ruling exists for widening it.
- **What the close is and is not:** it records the reason in the conversation's own
  grant value and nothing else — no file is written, no workflow is called — and F11's
  other half ("`open_grant` writes nothing durable") stays true on purpose under D-53-03.

## Deviations from Plan

None — plan executed exactly as written. The one notable deviation from the plan's
literal expectation ("were observed RED against the unmodified SKILL.md" for all four
new tests) is documented above under TDD Evidence: the fourth test is legitimately
green-by-construction both before and after the edit, verified with `advisor()` rather
than assumed.

## Known Stubs

None.

## Threat Flags

None beyond the plan's own threat model (T-ss6-01 through T-ss6-05, all `mitigate` or
accepted, none escalated) — no new network endpoint, auth path, or schema change at a
trust boundary was introduced.

## Self-Check: PASSED

- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — FOUND, step 10 present
- `operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py` — FOUND, four
  new tests present
- Commit `b47d2296` — FOUND (`git log --oneline --all | grep b47d2296`)
- `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` — 2952 passed, 5 skipped
  (baseline was 2948 passed, 5 skipped; +4 new tests)
- `git diff --name-only` (post-commit, against `af7b8d59`) lists exactly the two expected
  paths
- `git diff --stat operator-claude-plugin/scripts/` and `git diff --stat n8n/` both empty
- `plugin.json`/`CHANGELOG.md` — untouched (260911-ss7 owns the version bump)
- `scripts/todo_triage.py --since af7b8d59` — `counts: {} | debt (defect): 0`, no
  untriaged todo created
