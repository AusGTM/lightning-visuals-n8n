---
phase: 28-control-actions
plan: 04
subsystem: operator-claude-plugin
tags: [cadence, schedule-trigger, plain-language, refusal, allowlist, D-25]
requires:
  - n8n_control.apply_mutation (28-01)
  - 28-FINDINGS.md Q3 (the bracket retimes a RUNNING instance — observed, not inferred)
provides:
  - n8n_cadence.read_cadence / describe_cadence / parse_cadence
  - n8n_cadence.schedule_trigger_nodes
  - n8n_cadence.job_enabled / set_job_enabled
  - n8n_cadence.set_schedule_enabled (network)
  - n8n_cadence.set_cadence (network)
  - n8n_cadence.CadenceRefused
affects:
  - 28-05 (operator surface owns the confirmation loop and the CONTROL-05 wording amendment)
tech-stack:
  added: []
  patterns:
    - parse-or-refuse with worked examples, never a best guess
    - plain language in both directions; expression syntax never crosses the boundary
    - field-level diff narrowing, one field per mutation
key-files:
  created:
    - operator-claude-plugin/scripts/n8n_cadence.py
    - operator-claude-plugin/tests/test_control_cadence.py
---

# 28-04 — cadence in plain terms, and per-job enable/disable

**Status: COMPLETE.** Plugin suite 718 → 747. Repo 1593 → 1622. Node 506 unchanged.

## What was built

Three pure functions plus two network mutations.

`read_cadence` / `describe_cadence` / `parse_cadence` are side-effect free, so the whole
interpretation layer tests without a transport. `describe_cadence` renders all five deployed
shapes as sentences; the no-syntax property is asserted by **iterating the entire mapping
table**, not spot-checking.

**D-09 is enforced in both directions.** The module never emits `cronExpression` at all — a
phrase that would need it is refused with worked examples (D-10), because an opaque
expression the operator never sees explained is worse than an honest no. Input that already
*is* expression syntax is refused rather than passed through. A node hand-edited in the n8n
UI to carry one is described as "check it in n8n directly" — the one place D-09 would
otherwise leak.

`rule.interval` is an array, so "every weekday at 9am and 5pm" parses to **two** weeks-type
entries with `triggerOnWeekdays: [1,2,3,4,5]` at hours 9 and 17.

`set_schedule_enabled` implements **D-25 / amendment #6 as decided** — not re-opened, not
offered as a choice, not gated behind a checkpoint. `LV Scheduled Maintenance (Cloud)`
carries five Schedule Triggers, so workflow-level deactivate would stop all five including
the review poller and the stuck-lock sweep. An absent `disabled` key reads as enabled, since
none of the five committed triggers carries it.

Both mutations go through 28-01's single pipeline with 28-03's field-level narrowing:
reverting the one permitted field must reproduce the original node exactly. **Re-timing never
touches `disabled` and disabling never touches the interval** — pinned by a test, because a
guard covering both fields would stop meaning anything.

`set_cadence` refuses a `CadenceRefused` object passed as an interval. That is the mistake
that would turn D-10's honest refusal into a silent write of whatever the refusal stringified
to.

## Grounded in 28-FINDINGS.md, not in the research's inference

Q3 observed the deactivate → PUT → activate bracket retiming a **running** instance live
(two off-grid single fires at 03:22 and 03:26 while the sibling 15-minute trigger stayed on
the quarter hour). That is why this plan writes an interval and expects it to take effect.

**Carried caveat:** the commanded interval was 2 minutes and observed gaps were 7 and 4, so
the *exact* post-change cadence is not established. Nothing here promises one — no "next run"
time is computed or displayed. **28-05 must keep that property**: describe the schedule that
was requested, never assert when it will next fire.

## For 28-05

- The confirmation loop is deliberately absent here; this plan supplies its two halves (the
  parse, and the description of what the parse means). Show the description, wait, then write.
- Every refusal carries `.reason` and `.examples` (≥3). Surface those rather than composing
  new wording.
- **The CONTROL-05 / REQUIREMENTS.md / ROADMAP wording D-25 implies is 28-05 Task 3's edit**
  and was deliberately not touched here — splitting one amendment across two plans is how
  half of it goes missing.
