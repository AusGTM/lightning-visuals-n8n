---
status: investigating
trigger: "F1 and F2 (from .planning/uat/UAT-autonomous-batch-2026-09-09.md) — plus operator answers: Barry's Bigpond email came from direct web research by hand; row 3 was ignored by the round; no end-of-run report was rendered; Apollo unconfirmed is accepted (no master key)"
slug: uat-batch-review-row-reads-failed
created: 2026-09-09
updated: 2026-09-09T03:20:00Z
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

hypothesis: F1 CONFIRMED and FIXED (see Resolution). F3/F4 CONFIRMED — see reasoning_checkpoint and Resolution below.

```yaml
reasoning_checkpoint:
  hypothesis: >
    F4's row-3 reached the enrichment webhook (execution 12140, real gap_flag/
    contactability output) via an out-of-band call that bypasses this repo's ONLY
    sanctioned dispatch path (chunking.dispatch_plan) — the sole surviving in-repo
    caller of enrichment.dispatch_enrichment that skips ALL bookkeeping is
    scripts/enrichment.py's own __main__ CLI entry point, which no SKILL.md
    references for a real send. F3's report block was computed (run_report.
    build_run_report never raises — it degrades to a REPORT INCOMPLETE block on any
    internal error) but never persisted anywhere durable, so its absence from the
    operator's chat is unrecoverable and unprovable after the fact — a Claude-relay
    omission, not a code crash.
  confirming_evidence:
    - "run_state.start_run records the FULL unmatched_rows row_id list unconditionally,
      before any HTTP call; row-3's absence from total_row_ids proves he was never a
      member of unmatched_rows for this run — not an execution-order artifact."
    - "Every legitimate dispatch path (chunking.dispatch_plan, called from step 5's
      main pass AND from rerequest_unanswered) unconditionally attempts
      written_records.append_chunk, which even on an I/O failure still ATTEMPTS a
      write; a Python mtime scan of the whole durable directory for the local
      09:10-10:00 window (execution 12140's real time) shows literally zero files
      touched other than the six files belonging to run 377a913c itself — ruling out
      an orphaned-run_id write from rerequest_unanswered too."
    - "scripts/enrichment.py's __main__ block calls dispatch_enrichment directly with
      zero bookkeeping — the only such call site in the repository."
  falsification_test: >
    A written_records-<uuid>.json (or any other durable file) with an mtime in the
    09:10-10:00 local window, under a run_id other than 377a913c, would prove a
    dispatch_plan-routed call (the rerequest_unanswered orphaned-run_id defect) was
    the mechanism instead. Ruled out by the mtime scan (see Evidence).
  fix_rationale: >
    F3 — persisting report["block"] to a durable, run_id-keyed file
    (run_report-<run_id>.md) makes "was the report actually rendered" a
    file-existence check instead of a memory of chat scrollback: addresses the ROOT
    gap (the report existed only as a Python return value) not the symptom (operator
    says "I did not get a report"). F4 — two REAL code defects were found in the same
    investigation and are fixed regardless of whether either explains row-3 (neither
    does — see Eliminated) because both independently corrupt this run's own
    written_records artifact under NORMAL operation: (a) dispatch_plan flushes the
    async-ack's bare {run_id, accepted, row_id} body as a bogus action:null/
    outcome:failed entry whenever async_ack=True, even though written_records exists
    specifically to record actual writes and a propose-mode async dispatch writes
    nothing; (b) rerequest_unanswered omits run_id= when calling dispatch_plan,
    breaking the documented "all dispatch legs share one run_id" invariant
    (SKILL.md step 9's own prose) for any future run that actually exercises a
    re-request pass. Row-3's specific disappearance itself has no code defect to
    patch — it is made DETECTABLE in future via a row-count line in the persisted
    report, not silently fixed.
  blind_spots: >
    Cannot fetch n8n execution 12140's raw request body directly (no .env access) to
    see literally what was POSTed and by what tool; "operator's Claude ran
    enrichment.py's CLI directly" is the only surviving code-level explanation after
    eliminating dispatch_plan and rerequest_unanswered, but it is inferred by
    elimination, not directly observed.
  candidate_causes:
    - "code: dispatch_plan flushes an async-ack body into written_records as a bogus
      failure entry (confirmed, fixed)"
    - "code: rerequest_unanswered omits run_id=, orphaning a re-request's bookkeeping
      under a fresh UUID (confirmed invariant violation, fixed, not causal for row-3)"
    - "process: an out-of-band, unsanctioned direct call (enrichment.py's CLI) to the
      enrichment webhook for row-3, bypassing all SKILL.md-prescribed bookkeeping —
      the surviving explanation for row-3's specific disappearance, not a repo code
      defect"
  and_gate: >
    no — F3 and F4 are two independent gaps (report never persisted; a row's
    dispatch bypassed bookkeeping) with two independent minimal fixes; neither
    requires the other to be true, and the two in-repo defects found (async-ack
    flush, missing run_id) each stand alone, not jointly required to explain any one
    symptom.
```

next_action: all four findings resolved, fixed, and committed (F1 `0c42b18`, F3/F4 `392753a`, F2 `734826b`, F4 row-accounting false-positive correction `00668a3`). Nothing verified live — every check ran offline. Awaiting operator confirmation per the CHECKPOINT below before this session moves the file to `resolved/` and appends the knowledge base.
test_gate: F1 — `node --test tests/n8n/ingestReviewBranchResponds.test.mjs` and `.venv/bin/python -m pytest operator-claude-plugin/tests/test_written_records.py -q -k queue`; both green. F3/F4 — `.venv/bin/python -m pytest operator-claude-plugin/tests/test_run_report.py operator-claude-plugin/tests/test_chunking.py operator-claude-plugin/tests/test_preingest_merge.py -q` and `.venv/bin/python -m pytest operator-claude-plugin/tests/test_skill_sequence_coverage.py -q`; all green. F2 — `.venv/bin/python -m pytest operator-claude-plugin/tests/test_run_report.py operator-claude-plugin/tests/test_sweep_read_only.py -q`; green. Final pass after the row-accounting correction: plugin suite 2850/5, full repo 4608/154, node 942/0 — unchanged baselines, no regression.

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
    A second inbound edge into one node is already an established pattern in this exact
    lane (`HubSpot Update` + `HubSpot Create` both -> `Build Association Request`, :989-992
    — fan-IN precedent, not `fan()`, which is a fan-OUT helper for one source -> many
    targets and is not the relevant precedent here) — so adding `Set Review -> Build
    Ingest Response` as a second inbound edge is architecturally consistent.
  implication: safest fix sources `results` by NODE NAME (`nodeAll('HubSpot Associate
    Company')`) instead of `$input.all()` — decouples correctness from what else feeds
    the node's input, preserves byte-identical alignment for the existing write path.
    Advisor correction (2026-09-09): n8n may run a node with multiple inbound branches
    ONCE PER BRANCH THAT FIRES rather than once on a merged item array (an explicit Merge
    node is n8n's documented way to combine branches) — unverified live either way in
    this repo. It does not matter which is true here: EVERY value `Build Ingest Response`
    computes is read by NODE NAME (`nodeAll('Decide Action')`, `nodeAll('Build Association
    Request')`, `nodeAll('HubSpot Associate Company Write Gate')`, `nodeAll('HubSpot
    Associate Company')`) — none of it is derived from this node's OWN `$input`, only
    triggered by it. So whether the node runs once (merged) or twice (once per firing
    branch) in a mixed create+review batch, every run reads the SAME full named-node
    snapshots and produces a BYTE-IDENTICAL output array. `responseMode: "lastNode"`
    taking whichever run happened last is therefore safe by construction, not by luck —
    still worth a first-live-mixed-batch spot-check (Resolution operator handoff note),
    since this is reasoned from source, not observed live.

- timestamp: 2026-09-09T01:00:00Z
  checked: written_records-377a913c….json's 3 entries against chunking.py's
    dispatch_plan/append_chunk, preingest.rerequest_unanswered, enrichment.py's __main__
  found: entry[0] (row_id="row-1", action=null, outcome=failed — no "queue" key) is
    NOT the F1 dead-end shape; it is `written_records.append_chunk`'s classification of
    a BARE dict body — `items = body if isinstance(body, list) else [body]` — and
    `Build Async Ack`'s own documented shape is exactly `{run_id, accepted: true,
    row_id}` (`ENRICH_BUILD_ASYNC_ACK`, scripts/build_cloud_workflows.py:4679-4685),
    which CLAUDE.md §13.0.2 states "wins the race against the full chain,
    deterministically, every time" whenever `async_ack: true`. Step 5's own dispatch
    call passes `async_ack=True`. Entries[1]/[2] (Natalie's create, and a second
    action=null/row_id=null entry) are from step 7's SYNCHRONOUS `dispatch.dispatch`
    ingest send (no async_ack there — confirmed by reading SKILL.md :795-889), so
    entry[2] is plausibly Barry's F1-shaped review hold, flushed correctly by chunk
    but misclassified for the ALREADY-FIXED F1 reason.
  implication: a REAL, distinct, confirmed defect — `chunking.dispatch_plan` flushes
    the meaningless async-ack body into `written_records` whenever `async_ack=True`,
    producing a bogus `action:null/outcome:failed` entry every time. Independent of F4.
- timestamp: 2026-09-09T01:10:00Z
  checked: preingest.rerequest_unanswered's own `chunking.dispatch_plan(...)` call
    (operator-claude-plugin/scripts/preingest.py:840-841)
  found: called WITHOUT `run_id=` — `dispatch_plan`'s default (`run_id=None`) mints a
    fresh `uuid.uuid4().hex` internally, so any re-requested row's `written_records`
    entries land in a DIFFERENT, orphaned file, never `written_records-377a913c….json`.
    Directly contradicts SKILL.md step 9's own documented invariant: "One grant, two
    lanes, several dispatch legs — the match pass, the enrich pass, the re-request
    pass when it ran, and the final ingest send — all under the SAME run_id."
  implication: a REAL, distinct, confirmed invariant violation. Fixed regardless of
    causal relevance to row-3 (ruled out below) because a future run that DOES
    exercise a re-request pass would silently lose that leg's bookkeeping the same way.
- timestamp: 2026-09-09T01:20:00Z
  checked: Python mtime scan of the WHOLE durable directory
    (~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/) for
    the local window 2026-09-09T09:10:00-10:00:00 (covers execution 12140's local time,
    09:22:18)
  found: exactly six files touched in that window, all six belonging to run
    377a913c1c9d49129663c6c8740f436d (run_state, held_queue.json, run_manifest.json,
    run_manifest-377a913c…, written_records-377a913c…, run_audit-377a913c…). No
    OTHER run_id's file (which `rerequest_unanswered`'s orphaned-UUID defect would
    have produced) exists anywhere near this timestamp.
  implication: rules out `rerequest_unanswered` as F4's row-3 mechanism (its defect is
    real but did not fire for this run — no second dispatch_plan-driven leg happened
    at all). The ONLY surviving in-repo caller of `enrichment.dispatch_enrichment` that
    produces ZERO bookkeeping trace by design is `scripts/enrichment.py`'s bare
    `__main__` CLI entry point (verified: it calls `dispatch_enrichment` directly,
    :600, with no `chunking.dispatch_plan`/`run_state`/`written_records` involvement
    anywhere in that code path). No SKILL.md file references invoking it directly for
    a real send (checked enrich-before-ingest, enrich-records, contact-upload).
  implication_2: F4's root cause is therefore an out-of-band call outside every
    SKILL.md-sanctioned path — a process/operator-Claude-execution gap, not a repo
    code defect, per the objective's own framing for this case.
- timestamp: 2026-09-09T01:30:00Z
  checked: run_report.build_run_report's own exception handling
    (operator-claude-plugin/scripts/run_report.py:668-694)
  found: wraps its entire body in `try/except Exception`, degrading to a valid
    `{"block": "**REPORT INCOMPLETE**...", ...}` dict rather than ever raising — "this
    is the report's own never-raise contract" (its own comment). SKILL.md step 9's own
    fence is PURE PROSE at the render step: "Render `report["block"]` to the operator
    verbatim" — no code persists it anywhere; it exists only as a Python return value.
  implication: `build_run_report` could not have crashed silently — if step 9's fence
    executed, `report["block"]` existed as a real string. The only remaining
    explanations are (a) step 9's fence never ran at all, or (b) it ran and the
    resulting string was computed but never relayed to the operator's chat — neither
    is a code defect; both are undetectable after the fact because nothing persists
    the block. Confirms F3's root cause and its fix (persist the block to a durable
    file, making its existence a checkable fact rather than a chat-scrollback memory).

## Eliminated

- hypothesis: F4 — row-3 was dropped at step 2's identity/resolution gate (never
    passed identity, never dispatched at all).
  evidence: row-3's actual response (execution 12140) carries real `gap_flag`/
    `contactability`/candidate-search output — a row that failed identity never
    reaches the enrichment webhook at all, so it must have passed
    firstname+lastname+company identity and been dispatched for real.
  timestamp: 2026-09-09T00:45:00Z
- hypothesis: F4 — row-3 fell out via `preingest.rerequest_unanswered`'s re-request
    pass (a second, legitimate dispatch leg for a row unanswered in the first pass).
  evidence: `rerequest_unanswered` DOES have a real bug (omits `run_id=`, see Evidence)
    but that bug means IF it ran, it would still leave a trace — a
    `written_records-<some-other-uuid>.json` file with an mtime near 09:22 local. The
    directory-wide mtime scan found none. `rerequest_unanswered` therefore did not run
    for this batch at all; it cannot be F4's mechanism.
  timestamp: 2026-09-09T01:25:00Z
- hypothesis: F4 — row-3 was classified `unchecked` at step 2's MATCH stage (a chunk
    failure in the HubSpot search itself) and retried at the match level.
  evidence: an unchecked-row retry re-runs `preingest.match_batch` (the MATCH/search
    lane, hitting the ingest webhook's search-only mode) — it cannot itself produce
    `gap_flag`/`contactability`, which are ENRICHMENT-lane merge-output fields. Whatever
    produced execution 12140's real output was an enrichment dispatch, not a match
    retry.
  timestamp: 2026-09-09T01:28:00Z

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
operator_handoff: deploy `n8n/wf_contact_ingest_cloud.json` to n8n Cloud (needs the
  operator's `.env`, out of scope for this session — see CHECKPOINT below). On the FIRST
  mixed create+review batch after deploy, spot-check that the response body is the full
  decided set exactly once (not duplicated, not truncated to one branch) — reasoned safe
  by construction above (every value `Build Ingest Response` computes is read by node
  name, so any run's output is byte-identical regardless of firing order), but never
  observed live.
files_changed:
  - scripts/build_cloud_workflows.py
  - n8n/wf_contact_ingest_cloud.json
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/tests/test_written_records.py
  - tests/n8n/ingestReviewBranchResponds.test.mjs (new)
  - tests/n8n/companyAssociationFlow.test.mjs
  - tests/n8n/pairPipelineAssociationFlow.test.mjs

### F3 — RESOLVED

root_cause: `run_report.build_run_report` never raises — an internal error degrades to
  a valid `{"block": "**REPORT INCOMPLETE**...", ...}` dict, so `report["block"]`
  ALWAYS existed as a real string once step 9's fence ran. SKILL.md step 9's own fence
  was pure prose at the render step ("Render `report["block"]` to the operator
  verbatim") — nothing persisted it anywhere durable. The block existed only as a
  Python return value; whether step 9's fence ran at all, and whether its result was
  actually relayed into the chat, are BOTH unrecoverable and unprovable after the
  fact — a Claude-execution-fidelity gap, not a code crash.
fix: `run_report.build_run_report` now PERSISTS `report["block"]` verbatim to
  `run_report-<run_id>.md` (new `report_path`/`_persist_report`, mirroring
  `run_audit_path`'s own resolution convention and every sibling store's
  degrade-on-I/O-failure contract — never raises, never withholds the in-memory
  report) before returning, for BOTH the happy path and the internal-error degrade
  path. Closes the gap: "was this report actually rendered" is now a file-existence
  check, never only a memory of chat scrollback. SKILL.md step 9's fence and prose
  updated to say so.
verification: RED before fix — `test_build_run_report_persists_the_block_verbatim_to_a_durable_file`,
  `test_report_path_is_named_by_run_id_in_the_same_durable_directory_as_run_audit`,
  `test_build_run_report_persists_even_the_report_incomplete_block` all failed
  (`AttributeError: module 'run_report' has no attribute 'report_path'`). GREEN after
  fix; `test_persisting_the_report_never_raises_on_an_io_failure` pins the
  never-raise contract survives an injected `_atomic_write_0600` failure.
files_changed:
  - operator-claude-plugin/scripts/run_report.py
  - operator-claude-plugin/tests/test_run_report.py
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md

### F4 — RESOLVED (repo defects fixed; row-3's specific mechanism is process, not code)

root_cause: row-3 (Ross Burridge, Tasmanian Racing Club) reached the enrichment
  webhook for a real dispatch (execution 12140, genuine gap_flag/contactability
  output) via a call outside every SKILL.md-sanctioned bookkeeping path. Proven by
  elimination: (1) `run_state.start_run` unconditionally records the FULL
  `unmatched_rows` row_id list before any HTTP call — row-3's absence from
  `total_row_ids` proves he was never a member of `unmatched_rows` for this run, not
  an execution-order artifact; (2) every legitimate dispatch path
  (`chunking.dispatch_plan`, from step 5's main pass OR `rerequest_unanswered`)
  unconditionally attempts `written_records.append_chunk`, which even on an I/O
  failure still ATTEMPTS a write — a directory-wide mtime scan of the WHOLE durable
  state directory for the local window covering execution 12140 (09:10-10:00) found
  literally zero files touched other than the six files belonging to run 377a913c
  itself, ruling out an orphaned-run_id write too; (3) the ONLY in-repo caller of
  `enrichment.dispatch_enrichment` that produces zero bookkeeping trace by design is
  `scripts/enrichment.py`'s bare `__main__` CLI entry point, which no SKILL.md file
  references invoking directly for a real send. This is a process/operator-Claude
  execution gap, not a repo code defect, per the objective's own framing for this
  case.

  Two REAL, DISTINCT, CONFIRMED code defects were found and fixed in the same
  investigation — both independently corrupt this run's own `written_records`
  artifact under NORMAL operation, though NEITHER explains row-3's specific
  disappearance (see Eliminated):
    (a) `chunking.dispatch_plan`, whenever `async_ack=True`, flushed the
        deterministic ack body (`{run_id, accepted, row_id}` — `Build Async Ack`'s
        own documented race-winning output, CLAUDE.md §13.0.2) into
        `written_records` as a bogus `action: null / outcome: failed` entry,
        misrepresenting a row that may have succeeded. Confirmed live: the entry
        for Natalie Waters' row (who was in fact created successfully moments
        later by a separate, synchronous dispatch leg).
    (b) `preingest.rerequest_unanswered` called `chunking.dispatch_plan` without
        `run_id=`, so `dispatch_plan`'s default (mint a fresh `uuid.uuid4().hex`)
        orphaned any re-requested row's bookkeeping under an id nobody else in the
        batch ever sees — directly contradicting SKILL.md step 9's own documented
        invariant ("all under the SAME run_id").
fix: (a) `chunking.dispatch_plan` now skips the `append_chunk` flush entirely when
  `async_ack=True` (a deliberate no-op, never counted as a bookkeeping FAILURE) —
  `written_records` exists to record what was ACTUALLY WRITTEN, and a propose-mode
  async dispatch writes nothing; the real per-row outcome is recovered separately via
  `watch.recover_async_dispatch` and was never re-flushed into this artifact either
  way. (b) `preingest.rerequest_unanswered` gained a keyword-only `run_id=None`
  parameter, threaded straight through to `chunking.dispatch_plan`; SKILL.md step
  5's prose now instructs every caller to pass `run_id=run_id`. (c) F3's persisted
  report plus a new row-accounting section (`build_run_report(...,
  original_row_count=...)`) states this run's own `run_state.total_row_ids` count
  against the caller-supplied original batch row count and names any mismatch
  explicitly — the detectable-in-future gate for row-3's OWN class of symptom (a
  row that never reached `run_state` at all, whatever the cause): SKILL.md step 9
  now passes `original_row_count=len(rows)` (step 2's own, unreassigned row list).
  No fix was written for row-3's specific mechanism — there is no code defect to
  patch for an out-of-band CLI call; the row-accounting line is what makes a future
  recurrence of this CLASS of symptom visible on the report's own face, per the
  objective's explicit instruction for a process-not-code cause.

  CORRECTION (same day, caught by advisor review before handoff, not by a failing
  test): the first cut passed `original_row_count=len(rows)` — step 2's WHOLE
  extraction, before match/classification narrowed anything down. But
  `run_state.total_row_ids` (step 5) is seeded from `unmatched_rows` only —
  auto-matched and confirmed-proposed rows never call `run_state.start_run` at all,
  they route to `enrich-records` via `confirmed_ids` at step 7, a different run
  entirely. Any ordinary batch containing one matched row would have rendered a
  false MISMATCH on the very gate meant to catch a real silent drop. Fixed by
  switching the call site to `original_row_count=len(unmatched_rows)` — the exact
  set step 5 passes to `run_state.start_run` — so a match now means every row that
  was SUPPOSED to enter this run's tracked scope did, and a mismatch still names a
  row dispatched outside `chunking.dispatch_plan`, just without the false alarm on
  the common case. `run_report.py` itself needed no change (its row-accounting
  tests call `build_run_report` directly with an explicit `original_row_count`);
  this was a SKILL.md caller-side argument fix only. Commit `00668a3`.
verification: RED before fix —
  `test_an_async_ack_body_is_never_flushed_into_written_records` (chunking) failed
  with a real entry present where none was expected;
  `test_rerequest_unanswered_threads_run_id_through_to_dispatch_plan` failed with
  `TypeError: unexpected keyword argument 'run_id'`;
  `test_row_accounting_flags_a_mismatch`/`test_row_accounting_reports_a_match`/
  `test_row_accounting_states_unknown_when_no_original_row_count_is_given` (shared
  with F3) failed before the row-accounting section existed. All GREEN after fix.
  Full suites: `node --test tests/n8n/*.test.mjs` 942/942 (unchanged — no n8n JSON
  touched by F3/F4). `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q`
  2832/2832 (2821 + 11 new), 5 known skips unchanged.
  `.venv/bin/python -m pytest -q --tb=short` 4590/4590 (4579 + 11 new), 154 known
  skips unchanged.
files_changed:
  - operator-claude-plugin/scripts/chunking.py
  - operator-claude-plugin/scripts/preingest.py
  - operator-claude-plugin/scripts/run_report.py
  - operator-claude-plugin/tests/test_chunking.py
  - operator-claude-plugin/tests/test_preingest_merge.py
  - operator-claude-plugin/tests/test_run_report.py
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md

### F2 — RESOLVED

root_cause: nothing in this plugin ever deleted a per-run durable artifact —
  `run_state.new_run_id()` mints one 155-byte `run_state-*.json` file per run
  (including every offline/preview run that never dispatched), and
  `written_records`/`run_audit`/`run_manifest` each add their own per-run file too.
  Only `artifact_store`'s `dashboard_artifact_ttl_days` (30) existed as a TTL
  anywhere, covering exactly one file. Observed live: 393 files / 1.5 MB after one
  week, 362 of them `run_state-*.json`.
fix: `run_report.prune_durable_state(config=None, now=None)` — two TTL families
  measured from each file's own mtime (never a `saved_at` field parsed from
  content, so it works uniformly across every JSON store and F3's new plain-text
  `run_report-*.md`): `run_state-*.json` at a fixed 7-day TTL (a resume attempted
  after that long re-runs everything anyway, Phase 61); `written_records-*.json` /
  `run_audit-*.json` / `run_manifest-*.json` / `run_report-*.md` at
  `artifact_store.TTL_CONFIG_KEY` (`dashboard_artifact_ttl_days`, default 30,
  reused rather than a second key). `held_queue.json`, `suggestion_declines.json`,
  and `operator.local.json` (and any sibling starting with that name) are named
  explicitly and never touched. Never raises — an unreadable/undeletable file is
  skipped, matching every sibling durable-store writer's degrade-not-halt posture
  (D-59-10). Wired into `enrich-before-ingest/SKILL.md` step 1, run once at the
  start of a round, never mid-run (deleting a file a live dispatch is about to
  append to would corrupt the D-59-07 partial-run guarantee).

  DESIGN DEVIATION from the todo's original proposal: the function lives in
  `run_report.py`, not `durable_paths.py` as the todo suggested. Discovered
  mid-implementation: `test_sweep_read_only.py` statically verifies the
  unattended sweep's own module import closure never reaches a function that
  performs a filesystem write, and confines `durable_paths.py`'s own writes to
  exactly `_atomic_write_0600`/`_migrate_once` — `durable_paths.py` IS in that
  closure (the sweep needs it for read-only config-path resolution).
  `prune_durable_state`'s `path.unlink()` call would have put a write-capable
  function back on the sweep's reachable graph. `run_report.py` already imports
  `durable_paths` and is NOT in the sweep's closure, so that is where the pruner
  (and its own TTL constants, duplicated fresh from `artifact_store`'s rather than
  importing it — `artifact_store` is also outside `durable_paths.py`'s safe
  import set, though that constraint stopped applying once the function moved) now
  lives.
verification: RED before fix (17 new unit tests, verified via a temporary
  `git stash` of the implementation): all failed with
  `AttributeError: module 'run_report' has no attribute 'prune_durable_state'` (or
  the equivalent `SHORT_TTL_DAYS` constant lookup). GREEN after fix. The 18th test
  (`test_config_load_composed_with_prune_durable_state_respects_the_operators_configured_ttl`,
  registered in `test_skill_sequence_coverage.py`'s COVERED dict) drives the exact
  documented SKILL.md step 1 sequence — `config_gate.load_config()` ->
  `run_report.prune_durable_state(cfg)` — end to end over a real config file on
  disk. Full suites: `node --test tests/n8n/*.test.mjs` 942/942 (unchanged — no
  n8n JSON touched). `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q`
  2850/2850 (2832 + 18 new), 5 known skips unchanged.
  `.venv/bin/python -m pytest -q --tb=short` 4608/4608 (4590 + 18 new), 154 known
  skips unchanged.
files_changed:
  - operator-claude-plugin/scripts/run_report.py
  - operator-claude-plugin/tests/test_run_report.py
  - operator-claude-plugin/tests/test_skill_sequence_coverage.py
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md

## Session summary

All four findings (F1-F4) resolved, fixed, and committed (`0c42b18`, `392753a`,
`734826b`, plus a same-day correction `00668a3` for a false-positive the F4
row-accounting gate would have raised on the healthy path — caught by advisor
review before handoff, not by a failing test). Every check ran offline; nothing
here has been verified against a live send. Deploying the regenerated
`n8n/wf_contact_ingest_cloud.json` to n8n Cloud remains the operator's own next
action (needs their `.env`) — explicitly out of scope for this session, per the
work order. `prune_durable_state` is wired into `enrich-before-ingest/SKILL.md`
only; adopting the same step-1 call in the other batch-shaped skills
(`enrich-records`, `contact-upload`, `suggest-contacts`) is a natural, small
follow-on, not done here (F2's own scope was one flow, matching the todo's
"minor" severity and this session's own priority ordering). The untracked
`uat-batch-2026-09-09.csv` (real names/emails from the source batch) should be
deleted once the operator no longer needs it for reference.


## F5 — NEW, 2026-09-09 03:00Z, found during Round B (mixed batch) of the UAT — BLOCKS the UAT

DATA_START
**Symptom (operator's Claude, probing with `preingest.match_batch` in propose mode):** a 4-row match
chunk — two rows WITH email (row-1 Natalie Waters, row-4 Barry Milton) and two WITHOUT (row-2
Nardine Beresford, row-3 Greg Purcell) — came back with only 2 response items, both for the
no-email rows; the two email rows were dropped from the response and fell to `unchecked`. Sent
alone, or as an all-email chunk, every row returns. The operator's Claude worked around it by
splitting the match by email presence (off-SKILL); the SKILL itself would have carried Natalie —
an EXISTING contact `351336543679` — as unchecked, at risk of duplicate creation.

**Root cause, traced on execution `12163` (`LV Enrichment (Cloud template)`, 2026-09-09T02:58:51Z),
node by node, read-only via the plugin key:**
- `Parse HubSpot Event` 4 items → `Build Identity` 4 → `IF Has Email` splits **2 | 2**.
- Email lane: `HubSpot Search` 2 → `Adapt Search` 2 (row-1, row-4) → `Enrichment Gate` **run 0** = [row-1, row-4].
- Name lane: `IF Name Searchable` 2 → `HubSpot Name Search` → `Adapt Name Search` 2 (row-2, row-3) → `Enrichment Gate` **run 1** = [row-2, row-3].
- Both lanes then run `IF Provider Processing Needed` / `IF Lusha|Apollo|ZoomInfo Enabled` (all false in propose mode) → `Normalize + Score` runs twice — **and BOTH runs output [row-2, row-3]**. Every node downstream (`Contact Research Trigger Gate`, `Merge Winners`, `Decide Action`, `Build Response`, `Respond to Webhook`) runs twice with [row-2, row-3] each. row-1 and row-4 exist nowhere after `Enrichment Gate` run 0.
- `ENRICH_NORMALIZE_SCORE_CLOUD` (`scripts/build_cloud_workflows.py:1815`): `const rows = $('Enrichment Gate').all().filter((it) => it.json.action !== "skip");` — a by-name read with no run index. n8n's `$('Node').all()` returned the node's LAST run ([row-2, row-3]) to both of this node's runs. The by-name read exists to survive provider HTTP hops replacing `$json` (memory `companies-research-lane-rowloss`); it silently assumed the named node ran once. A mixed chunk makes it run once per lane.
- Same idiom, same exposure, to audit: `:1924` (`gateRows = $('Enrichment Gate').all()` in a try/catch), `:2148` (`$('Company Gate').all()`, companies lane), `:2543` (`$('Company Gate').all().filter(...)`, companies Normalize), and any downstream node reading `Decide Action`/`Build Requests` by name. Contacts lanes that can co-exist in one chunk: email, name, linkedin (`IF Linkedin Searchable`), fetch_by_id — any two present = two runs.
- Executions `12160`–`12167` (8) were the operator's probes; propose mode, providers disabled, zero credits.
DATA_END

hypothesis: `$('Enrichment Gate').all()` without a run index returns the last run; when `IF Has Email` (or the linkedin/fetch_by_id splits) produce more than one upstream run, every converged by-name read collapses to the final lane's rows. Fix candidates, for the debugger to weigh: (a) `$('Enrichment Gate').all(0, $runIndex)` — pair this node's run with the gate's run of the same index (lanes reach the gate and this node in the same order, but prove it); (b) iterate run indexes 0..N collecting all gate rows, then select by `row_id` ∈ the current run's `$input` rows where `$input` still carries `row_id`, falling back to (a) only across an HTTP hop; (c) a Merge node before `Normalize + Score` so it runs once — changes node count and every downstream by-name read. Prefer the smallest change that a node-chain test in `tests/n8n/` can prove with TWO upstream runs (the existing harness models one run; extend it to model `.all(branch, runIndex)` and `$runIndex`).
next_action: reproduce F5 offline — build a two-run simulation of `Enrichment Gate` → `Normalize + Score` from the emitted jsCode (extend the item-flow harness pattern of `tests/n8n/researchChainRowFlow.test.mjs`), confirm RED (email rows lost), fix in `scripts/build_cloud_workflows.py` at every listed site, regenerate the JSON via the builder, GREEN; then the operator deploys + bounces and re-runs Round B.
