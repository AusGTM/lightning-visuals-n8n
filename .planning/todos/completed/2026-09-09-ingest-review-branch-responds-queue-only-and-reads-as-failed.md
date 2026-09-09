---
created: 2026-09-09T00:30:00.000Z
updated: 2026-09-09
title: The contact-ingest review branch responds {"queue":"needs_review"} only — the client records it as FAILED and the operator never sees Decide Action's reason
area: n8n-backend
severity: major
files:
  - scripts/build_cloud_workflows.py
  - n8n/wf_contact_ingest_cloud.json
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/scripts/run_report.py
---

## Hit live — first supervised batch, 2026-09-08, run `377a913c1c9d49129663c6c8740f436d`

Execution `12147` (`LV Contact Ingest (Cloud template)`): `Decide Action` produced
`{"action": "review", "reason": "no company in HubSpot matched name \"Devonport Racing Club\"
— create or enrich the company first, or name its record id on the row", "email": ...,
"company_id": null}` — exactly §13.0.1's downgrade, correct. But the review branch ends at
`Set Review` (`scripts/build_cloud_workflows.py:943-949`), a Set node whose whole output is
`{"queue": "needs_review"}`, and the webhook responds with the last node. `Build Ingest
Response` (`:970`) is wired only off the two write branches (`:982`). So the body the client
receives for a review row carries no `action`, no `reason`, no `row_id`, no email.

Client side: `written_records.classify_item` → `outcome_for_action(None)` → `FAILED`
(`ACTION_TO_OUTCOME` maps `"review"` → HELD, but the word never arrives). The durable
`written_records-377a913c….json` holds `{"action": null, "outcome": "failed", "reason":
null, "row_id": null}` for Barry Milton, and the end-of-run report renders him as failed —
the exact reading AFTER-03 forbids for a gated/held row. The operator's Claude, with no
reason to go on, explained the hold as an email-verifier refusal of a Bigpond address; the
true cause (company absent from HubSpot) was only visible in the n8n execution.

## Fix (backend, Phase 46 parity: builder + regenerated JSON in one commit, then deploy)

Route `IF Create`'s false branch through `Build Ingest Response` too, or make `Set Review`
pass through `$json.action`, `$json.reason`, `$json.email`, `$json.row_id`, `$json.company`
alongside `queue`. `Build Ingest Response` already promises "one row-identifying item per
decided row" (§13.0.1) — the review branch is the one decided row it never sees.

Client side, defensively: `classify_item` should map a body carrying `queue: "needs_review"`
and no `action` to HELD with reason "backend review — reason not returned", never FAILED.

## Test shape

`tests/n8n/*ingest*.test.mjs`: drive a create that resolves no company through the built
workflow's node chain and assert the RESPONSE item carries `action: "review"` and the
reason. Plugin: `test_written_records.py` — a `{"queue": "needs_review"}` body classifies
HELD, and the report block never prints "failed" for it.

## Resolved 2026-09-09

Fixed in debug session `.planning/debug/uat-batch-review-row-reads-failed.md` (F1):
`Set Review -> Build Ingest Response` wired, `results` sourced by node name instead of
`$input`, `n8n/wf_contact_ingest_cloud.json` regenerated, and `written_records.classify_item`
given the defensive `queue: "needs_review"` -> HELD mapping. Deploying the regenerated
workflow to n8n Cloud is still the operator's own next action (needs `.env`).
