---
created: 2026-09-17T00:00:00.000Z
updated: 2026-09-18
title: The phantom research_failed marker row — "IF Research Errored"'s alwaysOutputData {} item is stamped with a real `action` and reaches the caller as a fabricated failed outcome
area: n8n-enrichment
severity: medium
kind: defect
evidence: "Executions 12526-12542 (run ca0537929b26401384f361902039ce7e) re-read 2026-09-18: 18/18 web-research responses parsed by `Validate Research Output` (17 matched:true, 1 false for daktronics.com, a hardware vendor — correct), AND 12 `research_failed` rows, exactly one per research-running execution, each `domain: None, hs_object_id: None`. Plus the two new tests in tests/n8n/researchErrorGateFlow.test.mjs."
files:
  - scripts/build_cloud_workflows.py
  - tests/n8n/researchErrorGateFlow.test.mjs
---

## Found during

Phase 73 plan 07 Task 3 (operator gate), Stage B of stress attempt 3, 2026-09-17/18.
Re-diagnosed 2026-09-18 in quick task 260918-32u.

## The original premise was checked live and found FALSE

This todo was opened as "the deployed JS validator does not strip a ```json fence, so fenced
research output is discarded as research_failed". **That is not what happened.** There is no
parser defect and no Phase 46 parity gap:

- `n8n/code/webResearch.js::extractFinalJson` already strips a ` ```json ` fence with the
  regex `/^```(?:json)?\s*|\s*```$/gm` — byte-identical in effect to
  `src/web_research.py::_extract_json`. The parity pair was never broken.
- Live re-read of the executions the todo cites: `Claude Web Research` produced 18 responses
  and `Validate Research Output` parsed **18/18**. NYRA (12540), the response attempt 3 quoted
  as "fenced and rejected", came out `lv_org_type: individual_club_team` at confidence 85.
- `src/web_research.py` was never implicated and has been dropped from `files:`.

## What was actually wrong

The 12 `research_failed` rows are **phantoms** — exactly one per execution that ran research,
each with no id, no domain and no object. The chain:

1. `IF Research Errored` carries `alwaysOutputData: true` — the one place in the graph where
   that (rather than a starved-lane sentinel) is correct. It keeps `Build Response Merge
   Stage 2` input 1 fed on the "research happened, no error" case.
2. On that case the gate's TRUE branch is empty, so n8n's `ensureAlwaysOutputData` pushes one
   literal `{ json: {} }` item down it.
3. `Build Research Failure Response` spread that `{}` and unconditionally stamped
   `action: "research_failed"` and `gate: { reason: "research call failed" }` onto it.
4. `Filter Build Response Rows` drops a bare `{}` and drops the reserved sentinel key — but
   the item was no longer bare and carried neither.
5. `Build Response`'s `hasRowIdentity` test accepted it, because `action` IS an identity key.
6. `operator-claude-plugin/scripts/written_records.py` (`ACTION_TO_OUTCOME`) buckets
   `research_failed` as FAILED — so attempt 3's audit counted 12 fabricated failures and
   attributed them to a fence.

## Fix (landed, quick task 260918-32u)

`Build Research Failure Response`'s jsCode (`scripts/build_cloud_workflows.py` ~:7583) now
returns the reserved `_gsd_sentinel_marker` for a zero-key input instead of stamping an
`action`. A zero-key item can only be `ensureAlwaysOutputData`'s push — every real item on
that branch arrives through `Research Carry Merge` carrying the row.

- `alwaysOutputData` on `IF Research Errored` is deliberately **retained**: the delivery to
  `Build Response Merge Stage 2` input 1 is what it exists for, and removing it starves the
  stage Merge under v1. Only the marker's shape changed.
- No new sentinel node, and no edit at `Filter Build Response Rows` or `Build Response` —
  `code_node`'s existing rewrite (`_OLD_MARKER_FILTER_JS` → `_NEW_MARKER_FILTER_JS`) already
  makes every emitted Code node's filter drop the reserved key.
- Pinned by two tests in `tests/n8n/researchErrorGateFlow.test.mjs` (the marker's shape, and
  end-to-end through the filter with a genuine error row asserted to survive).

## Residual, tracked separately

Several racing clubs researched `lv_produces_content: false` WITH evidence at high confidence
(GRNSW execution 12536, confidence 92, survived TS-2; also Perth Racing, Pakenham, Murray
Bridge), firing a `no_content` veto on bodies that plausibly do produce content. That is the
research model's own evidenced answer — a research-prompt quality question, not a parse loss.
Opened as `.planning/todos/pending/2026-09-18-racing-clubs-researched-produces-content-false.md`.
No code in 260918-32u touched the research prompt.
