---
phase: 65-round-empty-re-entry-keyed-on-the-cause
reviewed: 2026-09-07T00:51:53Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - operator-claude-plugin/config/field_policy.yaml
  - operator-claude-plugin/scripts/preingest.py
  - operator-claude-plugin/scripts/suggest_contacts.py
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - operator-claude-plugin/skills/suggest-contacts/SKILL.md
  - operator-claude-plugin/tests/test_preingest_merge.py
  - operator-claude-plugin/tests/test_skill_sequence_coverage.py
  - operator-claude-plugin/tests/test_suggest_contacts.py
  - operator-claude-plugin/tests/test_suggest_contacts_composition.py
findings:
  critical: 1
  warning: 0
  info: 0
  total: 1
status: issues_found
---

# Phase 65: Code Review Report

**Reviewed:** 2026-09-07T00:51:53Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Phase 65 adds two things: (1) `suggest_contacts.round_outcome`, a pure, fail-closed
classifier naming why a suggestion round ended with nothing usable and routing at most
one re-entry (search fallback); and (2) `preingest.merge_enriched`'s allowlist widening
from `extraction.canonical_props()` alone to the union with
`preingest.promotable_contact_props()` (the field-policy's twelve promotable contact
keys), plus the new `preingest.strip_enrichment_extras` dispatch-boundary strip.

Both pieces are unusually well tested — `round_outcome` has dedicated unit tests for
every cause, the terminal/routing-call distinction, idempotency, no-mutation, and a
`no while loop` AST guard; the `merge_enriched` widening has parity tests across all
three known callers (the direct step-7 CSV path, the suggest-contacts/`validate()`
path, and `rerequest_unanswered`), a byte-identity pin on the shipped config copy, and
a SAFE-01 pin on every `min_confidence` so the widening cannot quietly lower a
threshold. The full plugin suite (2564 passed, 5 skipped) and the composition-coverage
ratchet (`test_skill_sequence_coverage.py`) both pass clean.

Tracing an initially plausible concern (that `suggest-contacts/SKILL.md`'s dispatch
step was never given the new `strip_enrichment_extras` call enrich-before-ingest got)
to its conclusion showed it is a non-issue: `extraction.validate()` is the boundary
strip on that lane, confirmed by
`test_preingest_merge.py::test_the_suggest_contacts_path_tolerates_a_widened_key_through_validate`
and by the `COVERED` registry entry showing the documented suggest-contacts sequence
sinks at `round_artifact`, never `write_dispatch_csv`.

One real defect surfaced by tracing the documented pipeline end to end for the
round's own worst case — every company in the batch finding nobody — detailed below.
It sits exactly in the scenario `round_outcome` was built to explain, and turns "name
the cause" into an unhandled crash for that scenario instead.

## Critical Issues

### CR-01: An all-companies-empty round crashes before the terminal classify ever runs, and the routing-call outcome it discarded was never kept as a fallback

**File:** `operator-claude-plugin/skills/suggest-contacts/SKILL.md:424, 451-454, 458-459, 478-484`
**File:** `operator-claude-plugin/scripts/suggest_contacts.py:568-588` (`mint_row_ids`)
**File:** `operator-claude-plugin/scripts/preingest.py:195-228` (`build_rows_spec`)

**Issue:**

Trace the documented per-batch pipeline for the round that ends emptiest: every
company's page walk finds nobody (`walk["people"] == []`), and for each one
`search_fallback.eligible_after_ladder(attempts)` is either ineligible or the fallback
itself finds nobody. `selected` therefore stays `[]` for every company, so
`suggest_contacts.synthesise_rows(...)` returns `[]` for each one
(`company_records = []`), and the accumulating `records` list is empty after the whole
per-company loop.

At SKILL.md line 458, `minted = suggest_contacts.mint_row_ids(records)` is called
unconditionally on that empty list. `mint_row_ids` calls
`preingest.build_rows_spec([record["row"] for record in records])`
(`suggest_contacts.py:583`), and `build_rows_spec` raises `preingest.RowSpecError`
on an empty rows list (`preingest.py:210-213`: `if not rows: raise RowSpecError(...)`).
`mint_row_ids`'s own docstring is explicit that this propagates untouched — "never
caught, re-worded or worked around" (`suggest_contacts.py:578-581`). Nothing in the
SKILL.md's documented sequence, and nothing in `mint_row_ids`, catches it.

The crash happens *before* the terminal classify loop that Phase 65 Task 2 added
(SKILL.md lines 478-484: `for entry in rounds: entry["outcome"] = suggest_contacts.round_outcome(...)`).
That loop is the only place any `rounds` entry is ever given an `"outcome"` key —
the earlier, per-company **routing** call at SKILL.md line 424
(`outcome = suggest_contacts.round_outcome(walk)`) is a bare local variable used only
to decide whether to try the search fallback; its result is never written onto the
`rounds.append({...})` dict at lines 451-454, which carries `company`, `walk`,
`fallback`, `start`, `count` — no `outcome`. So even for the company whose cause
(`CAUSE_NO_PEOPLE_FOUND`) was already computed once, that computed cause is thrown
away, and if `mint_row_ids` never returns, no company in the round ever gets a
reported cause at all.

This is precisely the scenario `round_outcome` exists to name (per its own docstring:
"Name the CAUSE of one company's round" for "a round that ends with nothing usable")
and precisely the scenario the report step (SKILL.md line ~522-523) promises never
stops the report: "No cause causes a stop; a report reports (Phase 68's standing
rule)." A one-company round (a very ordinary real invocation — the operator can run
this skill over a single company) that finds nobody on its site and gets no rescue
from the search fallback raises an uncaught `RowSpecError` instead of producing the
report Phase 65 built. This is a regression relative to the phase's own stated goal,
not merely an unhandled edge case: the mechanism this phase added to avoid exactly
this ships with no path to reach it in the case it names first in its own vocabulary
(`CAUSE_NO_PEOPLE_FOUND` is listed first in `ROUND_CAUSES`).

No test in `test_suggest_contacts.py` or `test_suggest_contacts_composition.py`
drives the full documented pipeline with every company yielding zero records —
`test_mint_row_ids_propagates_row_spec_error_for_a_row_that_already_has_one`
(`test_suggest_contacts_composition.py:517-528`) only exercises the *duplicate
row_id* branch of `RowSpecError`, never the *empty batch* branch, and no test calls
`mint_row_ids([])` from within the round pipeline at all.

**Fix:** Two independent, compatible options — take at least one:

1. Persist the routing-call outcome as each entry's initial/fallback `outcome` when
   `rounds.append(...)` is built (SKILL.md ~line 451), so a crash (or any other reason
   the terminal loop is never reached) still leaves every company with a reported
   cause:
   ```python
   rounds.append({
       "company": eligible_company, "walk": walk, "fallback": fallback_selection,
       "start": len(records), "count": len(company_records),
       "outcome": outcome,   # the routing call's own result -- overwritten by the
                              # terminal classify below if that loop is reached
   })
   ```
2. Guard the mint/dispatch block so it is only entered when there is something to
   mint, and skip straight to reporting when the whole batch is empty:
   ```python
   if records:
       minted = suggest_contacts.mint_row_ids(records)
       ...
       for entry in rounds:
           ...
           entry["outcome"] = suggest_contacts.round_outcome(...)
   # else: every rounds[] entry already carries its routing-call `outcome` from
   # option 1 above, and step 9 reports off that.
   ```

Either fix should be covered by a new composition test that drives the documented
sequence with every company's walk yielding `people: []` and asserts the round
completes (no raised `RowSpecError`) and every `rounds[]` entry carries a
`CAUSE_NO_PEOPLE_FOUND` outcome.

---

_Reviewed: 2026-09-07T00:51:53Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
