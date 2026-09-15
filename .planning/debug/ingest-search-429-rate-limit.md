---
status: investigating
trigger: "F-A3/F-A4"
created: 2026-09-15T05:40:00Z
updated: 2026-09-15T05:40:00Z
---

## Current Focus
<!-- OVERWRITE on each update - always reflects NOW -->

hypothesis: The contact ingest lane's three per-row HubSpot search HTTP nodes (built by `_live_http` in `scripts/build_cloud_workflows.py`, typeVersion 4.2, `onError: continueRegularOutput`, no `options.batching`, no retry) fire one request per item in a burst; at 48 items HubSpot's per-second search limit returns 429 on most items, `Adapt Search Results` raises the batch-wide `lookup_failed` flag, `Decide Action` downgrades every create to review, and the row reason prints "valid email, no existing match" instead of naming the lookup failure.
test: Confirm the builder emits no throttling for these nodes; confirm the batch-wide `lookup_failed` scope and the reason string in `ADAPT_SEARCH_RESULTS` / `DECIDE_ACTION` jsCode; then add throttling (n8n httpRequest `options.batching.batch.{batchSize,batchInterval}`) to the per-row HubSpot search nodes via the builder, and make the Decide reason name `lookup_failed` distinctly (F-A4); regenerate JSON; offline walker/regression tests prove the reason string and the option's presence.
expecting: If true — the generated `n8n/wf_contact_ingest_cloud.json` gains `options.batching` on `HubSpot Search by Email`, `HubSpot Company Search by Domain`, `HubSpot Company Search by Name`; a new offline test pins it; the Decide reason for a lookup_failed row reads e.g. "lookup failed (HubSpot search unavailable/rate-limited) — held, not matched" rather than "valid email, no existing match". Live proof (a re-run of the 48-row CSV) is the operator's deploy+bounce step, NOT this session's.
next_action: Read `_live_http` (scripts/build_cloud_workflows.py ~line 4652), the ingest lane's three search node call sites (~lines 1288, 1394, 1404) and the `lookup_failed` handling (~lines 335-398 ADAPT_SEARCH_RESULTS, ~887-889 DECIDE_ACTION); decide the smallest builder change; check tests/n8n for the existing frozen-fixture / structural tests that will need re-baselining.
bug_class: bohrbug
reasoning_checkpoint: null
tdd_checkpoint: null

## Symptoms
<!-- Written during gathering, then immutable -->

expected: A 48-row contact-upload batch (tests/stress-tests/uat-stress-mixed-batch-2026-09-13.csv, `tests/stress-tests/README.md` row map) sent with an armed record-scoped window should create the valid-email rows (25) and update the one existing contact (`1251`, ctelfer@australianturfclub.com.au), holding only the sparse/malformed rows for review.
actual: 0 created, 0 updated, 47 review, 1 skip. Every row carried `lookup_failed: true`. 31 rows reported reason "valid email, no existing match" — including contact `1251`, which exists. Arm/disarm verified clean (flags read back false); the send itself was accepted (ack `accepted: true`).
errors: n8n execution 12429 (and the earlier identical attempt 12426), workflow `LV Contact Ingest (Cloud template)` `AwbBeShdPgV48eiY`: node `HubSpot Search by Email` 33/48 items errored, `HubSpot Company Search by Domain` 38/48, `HubSpot Company Search by Name` 42/48 — every error item is NodeApiError `The service is receiving too many requests from you` / description `You have reached your secondly limit.` (HTTP 429). `Adapt Search Results` output: 48× `lookup_failed: true`. `Decide Action`: 23× ('review','valid email, no existing match', company_match None), 15× ('review','no email, insufficient identity'), 6× ('review','valid email, no existing match','manual'), 2× (...,'name'), 1 skip. Read via the plugin's `executions_client.get_execution` — Webhook Trigger runData was NOT inspected or copied (it embeds the webhook secret).
reproduction: POST the 48-row CSV to `hubspot/contact-upload` (the plugin's contact-upload skill, run `aa059535b5f644e6a9c39f695ff76bfb`). Any ingest batch large enough that per-row HubSpot searches exceed HubSpot's per-second search limit (prior UATs were ≤ 9 rows and passed — 9-row walk 2026-08-05, Phase 72 gates 1–2 rows).
started: First observed 2026-09-15 on the first ≥ 20-row ingest send this repo has ever made. Not a regression of a previously-passing size; a throughput ceiling never reached before.

## Constraints (project rules the fix must honour)

- Never hand-edit `n8n/wf_*.json` — change `scripts/build_cloud_workflows.py` and regenerate (`python3 scripts/build_cloud_workflows.py`; the committed JSON must equal the regenerated output).
- Never deploy, bounce or arm anything. Deploy + bounce disarmed is the operator's step (`scripts/deploy_n8n_workflows.py`, `scripts/bounce_n8n_workflows.py`), recorded in the stress session sheet `tests/stress-tests/SESSION-2026-09-15.md`.
- `retryOnFail` is NOT a fix: the builder's own `_live_http` note records that n8n ignores it when `onError` is a continue mode (RESEARCH Pitfall 3). Throttling (`options.batching`) or a batched search body are the candidate mechanisms; state the trade-off (per-execution wall time vs the ~100 s Cloudflare webhook ceiling — note the ingest lane answers its ack early via `Build Ingest Ack`/`Respond to Webhook`, so post-ack work is not bounded by that ceiling; verify this claim in the builder before relying on it).
- Do not widen scope to the enrichment lane's search nodes unless the same per-row burst pattern provably applies there (it chunks at 2 records per POST; propose mode up to 20 rows — decide on evidence, not assumption).
- Keep `lookup_failed → never create` fail-safe intact (D-72-05 / Phase 36 Finding B). F-A4 is about the REASON STRING only.
- Tests: `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider tests/ operator-claude-plugin/tests/` and `node --test tests/n8n/*.test.mjs` must be green (4948 passed / 154 skipped, 1170 node at HEAD). Frozen fixtures under `tests/fixtures/` and `tests/n8n/fixtures/frozen/` may need a recorded, node-scoped re-baseline — follow the existing re-baseline discipline (see 72-11-SUMMARY.md) and never freeze runData containing a Webhook Trigger `headers` object.
- Shell `grep` is rtk-wrapped in this environment: use `/usr/bin/grep`.
- Commit with the session attribution trailers:
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01X5oeJHf2gNeEHmCTyfzjao`.

## Eliminated
<!-- APPEND only - prevents re-investigating after /clear -->

- hypothesis: Arming never reached the running workflow (stored-vs-running drift), so writes were refused.
  evidence: `n8n_control.apply_mutation` deactivates → PUT → reactivates with an independent second read; arm verified, disarm verified; `Decide Action` chose `review` BEFORE any write gate (IF Update 0/48, IF Create 0/48), so gates were never consulted.
  timestamp: 2026-09-15T05:30:00Z
- hypothesis: Company resolution failed (org not in portal) and downgraded creates to review.
  evidence: Rows with a manual `company_id` (`company_match: manual`, e.g. `9605284724`) were also held with "valid email, no existing match"; the hold is driven by `lookup_failed`, not by company resolution.
  timestamp: 2026-09-15T05:32:00Z

## Evidence
<!-- APPEND only - facts discovered during investigation -->

- timestamp: 2026-09-15T05:28:00Z
  checked: runData of executions 12429 and 12426 (`LV Contact Ingest (Cloud template)`), node item counts and error payloads (Webhook Trigger excluded)
  found: 50 nodes ran, status success. `HubSpot Search by Email` 48 items, 33 errored 429 "You have reached your secondly limit."; `HubSpot Company Search by Domain` 38/48 errored; `HubSpot Company Search by Name` 42/48 errored. The successful search items returned `total: 0` for emails (fictitious) and the expected `total: 1` for a few company domains/names.
  implication: HubSpot per-second search rate limit is the trigger; the burst is one request per input item on three consecutive HTTP nodes.
- timestamp: 2026-09-15T05:29:00Z
  checked: `Adapt Search Results` and `Decide Action` outputs for the same executions
  found: 48/48 rows `lookup_failed: true`; `Decide Action` reasons "valid email, no existing match" (31) and "no email, insufficient identity" (16), 1 skip; `IF Update` and `IF Create` both routed 0 to the true branch.
  implication: the batch-wide `lookup_failed` fail-safe (builder ~line 1282: declared outside the per-row loop) held the whole batch as designed; the reason string does not surface that cause (F-A4).
- timestamp: 2026-09-15T05:34:00Z
  checked: generated `n8n/wf_contact_ingest_cloud.json` node parameters for the three search nodes; builder `_live_http`
  found: `n8n-nodes-base.httpRequest` typeVersion 4.2, `options: {"timeout": 20000}` only, `onError: continueRegularOutput`, no `retryOnFail`, no `options.batching`; `_live_http` docstring explains why retryOnFail is deliberately absent. No node in any generated workflow uses `batching` today.
  implication: the fix is a builder change to the per-row search nodes (throttle or batch the body); it must survive regeneration and be pinned by an offline structural test.

## Resolution
<!-- OVERWRITE as understanding evolves -->

root_cause:
fix:
verification:
oracle_type:
files_changed: []
