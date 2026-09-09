---
status: fixing
trigger: "F1 and F2 (from .planning/uat/UAT-autonomous-batch-2026-09-09.md) — plus operator answers: Barry's Bigpond email came from direct web research by hand; row 3 was ignored by the round; no end-of-run report was rendered; Apollo unconfirmed is accepted (no master key)"
slug: uat-batch-review-row-reads-failed
created: 2026-09-09
updated: 2026-09-09T00:10:00Z
run_id: 377a913c1c9d49129663c6c8740f436d
---

## Symptoms

DATA_START
**Expected:** After the first supervised live batch (`enrich-before-ingest`, client 0.42.0, backend level with master as of 2026-09-09), (a) a row the ingest lane downgrades to `review` because its company is absent from HubSpot is recorded and reported as HELD with the backend's reason; (b) the operator's durable state directory does not grow without bound; (c) every row in the spreadsheet is accounted for by name in the round — sent, held, or refused, never silently dropped (README "Refusals are explicit"); (d) step 9's end-of-run report block is rendered verbatim at the end of the round (AFTER-01, D-67-11 — mandatory, "the only account of what happened").

**Actual:**
- F1: execution `12147` (`LV Contact Ingest (Cloud template)`) — `Decide Action` emitted `{"action":"review","reason":"no company in HubSpot matched name \"Devonport Racing Club\" — create or enrich the company first, or name its record id on the row", ...}` but the webhook responded with `Set Review`'s output `{"queue":"needs_review"}` only (lastNodeExecuted `Set Review`; `Build Ingest Response` never ran). Client `written_records-377a913c…json` holds `{"action": null, "outcome": "failed", "reason": null, "row_id": null}` for that row. The operator's Claude explained the hold as an email-verifier refusal of the Bigpond address — the real reason never arrived.
- F2: `~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/` — 393 files, 1.5 MB, 362 `run_state-*.json` (155 B each, one per `run_state.new_run_id()` including previews), 19 `written_records-*`, 6 `run_audit-*`. Nothing prunes; only `artifact_store` has a TTL (`dashboard_artifact_ttl_days`, one file).
- F3: no end-of-run report was rendered to the operator. `run_audit-377a913c….json` exists (ceiling, balances, disarm recorded at 23:44:34Z) so `run_report.record_audit` ran, but `build_run_report`/`report["block"]` was never shown. Operator: "I did not get a report."
- F4: the spreadsheet had a third person (execution `12140`, 23:22:18Z: `row_id: "row-3"`, `gap_flag: true`, `contactability: "none"`, no email, no candidates). `run_state-377a913c….json` lists `total_row_ids: ["row-1","row-2"]`; `held_queue.json` holds only row-1/row-2 (`no_match`); no store names row-3. Operator: "It ignored it." Note the row ORDER: 12140 (row-3 alone) preceded 12141 (row-1, row-2) — row-3 went out first, in its own leg, then vanished from every later store.

**Errors:** none raised anywhere; every execution `success`; every store parseable.

**Timeline:** first live supervised batch, 2026-09-08 23:22–23:47 UTC. F1 is structural in `scripts/build_cloud_workflows.py` since the ingest lane's review branch was built (2026-08-25 association work wired `Build Ingest Response` to the write branches only, `:982`). F2 since `run_state.py` existed. F3/F4 first observed now; never exercised live before.

**Reproduction:** F1 — POST a contact row whose company name/domain match nothing in HubSpot to the ingest webhook; the body is `{"queue":"needs_review"}`. Offline: `tests/n8n/` node-chain harness over `wf_contact_ingest_cloud.json`'s review branch. F2 — `ls` the durable dir. F3/F4 — need the SKILL.md sequence audit: which fence/prose path lets a `hold_emailless`/`gap_flag` row fall out of `run_state`, and which path lets step 9 be skipped.

**Facts already established (read-only, 2026-09-09):** Natalie Waters created `351336543679` associated to company `20686065409` (execution `12145`), correct. Barry's Bigpond email was typed by the operator from web research (not a provider, not a step-3 correction of record). Apollo balance `unknown` accepted. Both write flags `"false"` before and after; disarm recorded. Todos already filed: `.planning/todos/pending/2026-09-09-ingest-review-branch-responds-queue-only-and-reads-as-failed.md`, `.planning/todos/pending/2026-09-09-durable-state-dir-never-prunes.md` (both carry candidate fixes and test shapes — treat as hypotheses, verify).
DATA_END

## Current Focus

hypothesis: F1 CONFIRMED and FIXED (see Resolution). F4 — row-3 was dispatched in its own enrichment leg (12140) and then dropped before `run_state` recorded dispatched rows, most likely at the step-7 `hold_emailless` split (held rows are named in prose but persisted nowhere on this lane) or at step 2's identity/resolution gate. F3 — the SKILL.md's step 9 depends on names (`outcome`, `outcome_ingest`, `disarm`, `balances_at_grant`, `ceiling`) bound in earlier fences; if any was unbound after the review row's null body, the fence raised or the step was skipped.
next_action: F4/F3 next (work order item 2) — read `enrich-before-ingest/SKILL.md` steps 2, 7, 9 in full, `operator-claude-plugin/scripts/run_state.py`, and the four store files for run `377a913c…` (run_state, held_queue.json, written_records, run_audit) to trace exactly where row-3 fell out and whether step 9's fence names were bound.
test_gate: F1 — `node --test tests/n8n/ingestReviewBranchResponds.test.mjs` and `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py -q -k queue`; both green.

## Constraints (project)

- Never hand-edit `n8n/wf_*.json`; change `scripts/build_cloud_workflows.py` and regenerate; Phase 46 parity (builder + JSON in one commit). Deploying to n8n Cloud is the OPERATOR's action (needs `.env`), never this session's.
- No `while` loop / `import time` / `sleep()` in plugin scripts except `watch.py`; plugin scripts pure; SKILL.md bodies contain no "tier"/"icp"; any changed `python` fence sequence registered in `tests/test_skill_sequence_coverage.py` in the same commit.
- Nothing armed, no live HubSpot writes, no provider credits. Tests offline: `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` (baseline 2818/5), `.venv/bin/python -m pytest -q --tb=short` (4576/154), `node --test tests/n8n/*.test.mjs` (940).
- Every commit ends with the two trailers: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01T7sdpKuLJhgJfNHm9WUBQZ` (use `git commit -F`).
- Shell `grep` is rtk-wrapped: use `/usr/bin/grep`.

## Evidence

- timestamp: 2026-09-09T00:00:00Z
  checked: scripts/build_cloud_workflows.py:942-1001 (`build_cloud`, the ingest lane) and
    BUILD_INGEST_RESPONSE (:496-551)
  found: `Set Review` (a `n8n-nodes-base.set` node) has NO outgoing connection at all —
    `conns` only wires `IF Update`/`IF Create`'s true branches and the write chain
    (`Build Association Request` -> `HubSpot Associate Company` -> `Build Ingest
    Response`) into `Build Ingest Response`. A batch where every row resolves to
    `action: "review"` never reaches `Build Ingest Response`; with `responseMode:
    "lastNode"` on `Webhook Trigger`, the webhook answers with `Set Review`'s own output,
    which is exactly `{"queue": "needs_review"}` (its only assignment). `Build Ingest
    Response`'s own JS logic is NOT the bug — it already reconstructs every row
    (including review ones) from `nodeAll('Decide Action')`, independent of $input; it
    simply never gets a chance to run.
  implication: root cause is a WIRING gap, not a logic gap. Fix must (a) make `Build
    Ingest Response` execute even when a batch is 100% review, and (b) not silently
    corrupt the association-status alignment (`results[i]` <-> `gatedRows[i]`) for mixed
    batches (some create/update, some review) once a second inbound connection exists.
- timestamp: 2026-09-09T00:05:00Z
  checked: tests/n8n/pairPipelineAssociationFlow.test.mjs, companyAssociationFlow.test.mjs
  found: `Build Ingest Response`'s `results = $input.all()` line is read ONLY to
    index-align against `gatedRows` (`nodeAll('HubSpot Associate Company Write Gate')`).
    Existing tests already prove n8n's own connection-merge semantics are exercised
    elsewhere in this codebase (`fan()` helper) for multi-source -> one-node wiring — so
    adding `Set Review -> Build Ingest Response` as a second inbound edge is architecturally
    consistent, but risks scrambling `results[i]` alignment in a mixed batch if the merge
    interleaves Set Review's bare items with the association chain's items.
  implication: safest fix sources `results` by NODE NAME (`nodeAll('HubSpot Associate
    Company')`) instead of `$input.all()` — decouples correctness from what else feeds
    the node's input, preserves byte-identical alignment for the existing write path.

## Eliminated

- hypothesis: F1 is a logic bug inside `Build Ingest Response`'s field-building JS
    (e.g. it drops review rows, or mis-maps `action`/`reason`).
  evidence: `pairPipelineAssociationFlow.test.mjs`'s pre-existing "held" row assertions
    (report[1].action === "review", reason matched) already passed BEFORE any fix — the
    JS correctly reports a review row whenever it is given the chance to execute. The new
    RED test (`ingestReviewBranchResponds.test.mjs`, second case) confirms the same thing
    directly against the committed jsCode.
  timestamp: 2026-09-09T00:05:00Z

## Resolution

### F1 — RESOLVED

root_cause: `scripts/build_cloud_workflows.py`'s ingest lane wired `Set Review` (the
  `IF Create` false-branch terminus) as a dead end — no outgoing connection into `Build
  Ingest Response`, the lane's one synchronous-body builder. A batch where every row
  resolves to `action: "review"` therefore never executes `Build Ingest Response`, and
  n8n's `responseMode: "lastNode"` answers the webhook with `Set Review`'s own bare
  `{"queue": "needs_review"}` output — `Decide Action`'s real `action`/`reason`/`row_id`
  never reach the response body. Client-side, `written_records.classify_item` then calls
  `outcome_for_action(None)`, which falls through `ACTION_TO_OUTCOME`'s fallback to
  FAILED — exactly what `written_records-377a913c….json` recorded for the Devonport
  Racing Club row, and exactly why the operator's Claude had nothing but a Bigpond-email
  guess to explain the hold with.
fix: (1) backend — wired `conns["Set Review"] = {"main": [[{"node": "Build Ingest
  Response", ...}]]}` so a review-only batch now always reaches the response builder;
  (2) backend — changed `Build Ingest Response`'s `results` source from `$input.all()`
  to `nodeAll('HubSpot Associate Company')` so the association-status alignment against
  `gatedRows` stays correct regardless of what else now feeds the node (a mixed
  create+review batch would otherwise risk scrambling `results[i]` <-> `gatedRows[i]` on
  an unpredictable connection-merge order); regenerated `n8n/wf_contact_ingest_cloud.json`
  via `scripts/build_cloud_workflows.py` (Phase 46 parity — builder + JSON in one commit,
  never hand-edited); (3) client — `written_records.classify_item` now recognises a body
  carrying `queue: "needs_review"` with no `action` and maps it to HELD (reason falls
  back to "backend review — reason not returned" when the body carries none) instead of
  falling through to FAILED — defense in depth for an un-deployed workflow or a future
  regression re-severing the same edge.
verification: offline only (deploy to n8n Cloud is the operator's own next action, needs
  `.env`, explicitly out of scope for this session).
  - RED before fix: `tests/n8n/ingestReviewBranchResponds.test.mjs`'s first case
    (structural reachability, `Set Review` -> `Build Ingest Response`) failed; two Python
    tests in `test_written_records.py` (`test_a_bare_queue_needs_review_body_with_no_action_is_held_not_failed`,
    `test_a_queue_needs_review_body_that_does_carry_a_reason_keeps_it`) failed with
    `outcome == FAILED`.
  - GREEN after fix: all three now pass. Regenerating the JSON changed exactly one file
    (`n8n/wf_contact_ingest_cloud.json`), a 12-line diff (new `Set Review` connection +
    the `results` source-line rewrite) — confirmed via `git diff --stat`.
  - Full suites green: `node --test tests/n8n/*.test.mjs` 942/942 (940 baseline + 2 new;
    2 pre-existing tests — `companyAssociationFlow.test.mjs`,
    `pairPipelineAssociationFlow.test.mjs` — updated to source their `results` mock via
    `nodeOutputs["HubSpot Associate Company"]` instead of `$input`/`seedItems`, matching
    the new sourcing, still asserting the same `association: "associated"` outcome).
    `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` 2821/2821 (2818 + 3
    new), 5 known skips unchanged. `.venv/bin/python -m pytest -q --tb=short` 4579/4579
    (4576 + 3 new), 154 known skips unchanged.
files_changed:
  - scripts/build_cloud_workflows.py
  - n8n/wf_contact_ingest_cloud.json
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/tests/test_written_records.py
  - tests/n8n/ingestReviewBranchResponds.test.mjs (new)
  - tests/n8n/companyAssociationFlow.test.mjs
  - tests/n8n/pairPipelineAssociationFlow.test.mjs

### F2/F3/F4 — pending, next in this session's work order.
