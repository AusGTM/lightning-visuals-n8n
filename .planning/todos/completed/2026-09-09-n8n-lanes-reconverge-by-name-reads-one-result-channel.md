---
created: 2026-09-09T06:00:00.000Z
updated: 2026-09-09
title: Structural — n8n lanes reconverge without a merge, readers pull upstream rows by node name, and the client has two result channels; every UAT row-loss finding is this one idiom
area: n8n-backend
severity: major
files:
  - scripts/build_cloud_workflows.py
  - n8n/code/nodeRunRecovery.js
  - operator-claude-plugin/scripts/dispatch.py
  - operator-claude-plugin/scripts/watch.py
  - operator-claude-plugin/scripts/written_records.py
  - tests/n8n/
---

## The class, with every instance found so far

| Finding | Date found | Code age | Shape |
|---|---|---|---|
| research-lane row loss (memory `companies-research-lane-rowloss`) | 2026-07-24 | Jul | HTTP hop replaced `$json`; by-name recovery added |
| F1 ingest review branch | 2026-09-09 | 2026-08-25 | `Set Review` dead end; response built from `Decide Action` by name |
| F5 mixed-lane enrichment | 2026-09-09 | Jul | `$('Enrichment Gate').all()` returns last run; 6 readers patched with run recovery |
| F5b sync response (suspected) | 2026-09-09 | Jul | `Respond to Webhook` fires per lane; only the first reaches the client |
| F10 ingest first-entry body | 2026-09-09 | Aug | webhook `responseData` default `firstEntryJson` |
| F11 update/associate gate | 2026-09-09 | Aug | three gate copies, different field names |
| F12 response cannot see a gate refusal | 2026-09-09 | Aug | response built from decision, not from the write |

None broke this week. All surfaced on the first live batches with 2+ rows, 2 lanes, 2 actions.
Offline green because `tests/n8n/` models one run per node, one response, one entry.

## Root idiom
Lanes fan out (`IF Has Email`, `IF Linkedin Searchable`, `IF Name Searchable`, `IF Update` /
`IF Create` / `Set Review`) and reconverge on a Code node with no Merge. Downstream nodes read
upstream rows with `$('Node').all()` because provider/HubSpot HTTP nodes replace `$json`. Each
new lane or action multiplies runs; each by-name read silently picks one.

## What a structural fix looks like (for discussion, not decided)
1. Harness: model n8n runtime — N runs per converged node, `$('X').all(branch, run)`,
   `$runIndex`, single webhook response, `responseData`. Existing tests then catch the class.
2. Backend: per-item lineage (`pairedItem` / `$('X').item`) or ONE explicit Merge before
   `Build Response` / `Build Ingest Response`; retire bare `.all()` reads.
3. One write-gate helper with one field contract for create/update/associate/review.
4. Client: one result channel — read the settled execution by `run_id` for sync and async
   alike (the async path already does; it was immune to F5b). Response built from the
   WRITE node's output, never from the decision.
5. Skill/UAT: batches with mixed lanes and mixed actions are the default test shape.

## Out of scope
Confidence policy (new contacts held by design, D-61-03); named-account scoring; anything
in the ICP engines.

## Closed 2026-09-11 (resume session) — resolved by Phase 70

This todo was Phase 70's brief (`ROADMAP.md` § Phase 70). 18/18 plans complete,
`70-VERIFICATION.md` `status: passed`, Gates 10/11/12 passed live 2026-09-10. All five
structural items landed: (1) walker models the v1 engine (`tests/n8n/walkWorkflow.mjs`,
fidelity tests pinned to executions 12354-12356); (2) native Merge at every convergence and
HTTP hop, `nodeRunRecovery.js` deleted, by-name reads a generation-time refusal
(`assert_no_by_name_reads`; 0 `$('X').all()` in committed cloud JSON); (3) one write-gate
contract (D-70-15); (4) one client result channel — runData by `run_id`, ack-only responders
(D-70-05/07); (5) mixed-lane mixed-action batches are the acceptance shape (70-07, Gate 12).

Carried forward separately, not reopened here: `Associate Carry Merge` row drop (RED-pinned
in `tests/n8n/writeGateShape.test.mjs`, builder follow-on) and todo
`2026-09-11-merge-input-contract-allows-many-producers-per-input.md`.
