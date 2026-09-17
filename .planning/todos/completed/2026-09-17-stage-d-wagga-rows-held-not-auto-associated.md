---
created: 2026-09-17T00:00:00.000Z
updated: 2026-09-17
title: Stage D held the Wagga rows (41-42) as new-person creates instead of auto-associating them to the Wagga company created in Stage B
area: operator-plugin
severity: info
kind: accepted
evidence: "Stage D live run (73-UAT.md § Attempt 3): rows 41-42 held with reason 'no match found - not confident enough to act without review', per D-70-11 (a create is never made without an explicit operator reply)"
files:
  - tests/stress-tests/RUNBOOK.md
---

## Found during

Phase 73 plan 07 Task 3 (operator gate), Stage D of stress attempt 3, 2026-09-17/18.

## Why accepted (won't-fix)

This is correct D-70-11 behaviour, not a defect: a new person is never created without an
explicit operator "create N" reply, so holding rows 41-42 for review (rather than
auto-associating them as new creates to the Wagga company from Stage B) is the system working
as designed — no new contact landed incomplete or unreviewed.

The only thing that was actually wrong was `tests/stress-tests/RUNBOOK.md`'s own restart-step-4
expectation ("rows 41-42 now associate to Wagga"), which predates D-70-11 being enforced on this
lane. That RUNBOOK line is corrected as part of this same phase's Task 2 release
(operator-claude-plugin 0.50.0).

No code change needed beyond the RUNBOOK correction already shipped in this phase.
