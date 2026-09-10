---
created: 2026-09-09T03:40:00.000Z
updated: 2026-09-11
title: written_records records propose/enrich legs — which write nothing — as "None -> failed" in the end-of-run report
area: operator-plugin
severity: major
files:
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/scripts/chunking.py
  - operator-claude-plugin/scripts/run_report.py
---

## Seen 2026-09-09, run `2bc3617b094b4c939d57f38ff6704e3f` (after fix `392753a`)

End-of-run report, "Per-record outcomes":
`row-2 [contacts:unknown]: None -> failed — this action failed, was refused, or is an outcome
never seen before` and the same for row-4. Neither row was ever sent to the ingest lane
(`SENDABLE=0`); the entries come from the enrichment dispatch legs, whose response items
reached `written_records.append_chunk` without an `action` (the same symptom as run
`377a913c`'s row-1 `failed` entry on 2026-09-08). The async-ack leak fixed in `392753a` is a
different source; this one remains. Suspects: the enrichment response item shape in `enrich`
mode (does `Build Response` carry `action` on every lane — check F5's lane-loss first, a
dropped lane may hand `dispatch_plan` a partial body), and `classify_item` treating a missing
`action` as FAILED rather than NO_ACTION for a propose/enrich leg.

## Fix shape

Either stop recording enrichment legs in `written_records` at all (it exists to record
WRITES; an enrichment leg in propose/enrich mode writes nothing — `chunking.dispatch_plan`
should append only when the leg's mode can write), or classify an action-less enrichment
item as NO_ACTION with reason "enrichment leg, no write". The report must never say
"failed" for a row that was not sent. Test against the captured body of a real propose leg.

## Resolved 2026-09-11

This todo's own `## Fix shape` option (a) was already implemented by Phase 70 Plan 06
Task 2 (D-70-09), as caller discipline at `chunking.dispatch_and_recover`'s append site —
the `if can_write and rows:` guard, with `can_write` read off the built envelope through
`chunking.envelope_can_write` rather than re-derived from the spec. No production change
was needed by this task.

What this task added is the missing end-to-end proof on the recorded shape: two new test
functions in `operator-claude-plugin/tests/test_written_records.py` —
`test_the_recorded_shape_renders_failed_when_it_reaches_the_ledger` and
`test_the_recorded_shape_reaches_the_ledger_only_from_a_write_capable_leg` — driven on the
row shape run `2bc3617b094b4c939d57f38ff6704e3f` recorded, asserted against the RENDERED
report block rather than a ledger-double append count. Phase 70's own regression test for
this gate (`test_a_no_write_leg_never_enters_the_ledger`) used a well-formed row and
asserted only on a ledger double; it never drove the gate with this todo's pathological
shape or checked the rendered report string.

The tested row shape was RECONSTRUCTED from the rendered report line, because no captured
body of that propose leg exists anywhere in the repo — a `grep -rl 2bc3617b` over
`.planning/` and the plugin's fixtures during planning found only prose records
(`.planning/uat/UAT-autonomous-batch-2026-09-09.md` § "Round B", this todo itself, and
`70-06-SUMMARY.md`), never a frozen body. This sentence exists so the next reader does not
hunt for a fixture that was never captured.

Two facts a future reader would otherwise re-investigate: the sibling surface this todo's
suspects list pointed at is NOT affected — `report_enrichment._outcome_for_row` reads
`enrichment_row_ledger`, whose rows come from the `Decide Company Action` / `Decide Action`
nodes, and those stamp `action: "proposed"` on a propose leg
(`scripts/build_cloud_workflows.py`), resolving to `no_action`, never the fallback. And
this todo's third named file, `operator-claude-plugin/scripts/run_report.py`, needed no
change because its per-record section reads the ledger and nothing else, so an empty
ledger is an empty section.
