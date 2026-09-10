---
created: 2026-09-09T03:40:00.000Z
updated: 2026-09-09
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
