---
status: awaiting_human_verify
trigger: "F1 and F2 (from .planning/uat/UAT-autonomous-batch-2026-09-09.md) — plus operator answers: Barry's Bigpond email came from direct web research by hand; row 3 was ignored by the round; no end-of-run report was rendered; Apollo unconfirmed is accepted (no master key)"
slug: uat-batch-review-row-reads-failed
created: 2026-09-09
updated: 2026-09-09T05:00:00Z
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

next_action: F1-F4 resolved, fixed, and committed (F1 `0c42b18`, F3/F4 `392753a`, F2
  `734826b`, F4 row-accounting false-positive correction `00668a3`, F4 closed on direct
  driver-script evidence `e14c7b1`). F5 (multi-run convergence row loss at
  `Enrichment Gate`/`Company Gate`) also now fixed and offline-verified — see F5's own
  Resolution section below. Nothing verified live for ANY finding — every check ran
  offline. Awaiting operator confirmation per the CHECKPOINT below before this session
  moves the file to `resolved/` and appends the knowledge base.
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
next_action: F5 fixed, tested RED->GREEN, and full suites green (see Resolution below).
  Nothing deployed — the operator's next step is to deploy `n8n/wf_enrichment_cloud.json`
  and `n8n/wf_backend_status_cloud.json` and re-run Round B. Awaiting operator confirmation
  per the CHECKPOINT below before this session moves the file to `resolved/`.

```yaml
reasoning_checkpoint:
  hypothesis: >
    "Enrichment Gate"/"Company Gate" each have MULTIPLE inbound connections (5 lanes for
    contacts — email/linkedin/name/fetch-by-id/unmatchable; 2 for companies —
    fetch-by-id/domain-search) and n8n runs a node with multiple inbound edges ONCE PER
    FIRING EDGE, not once on a merged item array (confirmed live, execution 12163). Every
    by-name `$('Gate').all()` read downstream of that convergence point (required because
    HTTP provider hops replace $json) collapses to the gate's MOST RECENT run only — n8n's
    own docs confirm `.all()` with no run index "returns the items of the node's most
    recent run" — silently losing every row from every earlier lane.
  confirming_evidence:
    - "n8n docs (docs.n8n.io/code/cookbook/builtin/all, docs.n8n.io/code-examples/methods-variables-examples/run-index): bare .all() = most recent run; .all(0, $runIndex) = same run as the current node — confirms the mechanism, not just the live symptom."
    - "Live trace (execution 12163, already in Evidence below): Enrichment Gate ran twice (run 0 = [row-1,row-4] email lane; run 1 = [row-2,row-3] name lane); BOTH runs of Normalize + Score returned [row-2,row-3] — exactly 'last run wins', matching the docs precisely."
    - "Structural audit of scripts/build_cloud_workflows.py found the SAME by-name-.all()-with-no-run-index idiom at every downstream reader of Enrichment Gate/Company Gate: ENRICH_NORMALIZE_SCORE_CLOUD (:1815+1816-1818 nodeAll), ENRICH_NORMALIZE_SCORE_CO (:2543+2544-2546), ENRICH_ZOOMINFO_CACHED (:1924, local-live), ENRICH_ZOOMINFO_CO_CACHED (:2148, local-live), and — found during this session's audit, NOT named in the original F5 note — _zoom_split_gate_js/_zoom_split_cache_js (the CLOUD split-code-node ZoomInfo subgraph actually deployed for wf_enrichment_cloud.json; ENRICH_ZOOMINFO_CACHED/_CO_CACHED are the local-live-only single-node variant)."
    - "Offline node-chain test against the ACTUAL committed pre-fix jsCode (tests/n8n/enrichmentGateRunRecoveryFlow.test.mjs, git-stash-verified): 0/5 pass pre-fix, reproducing both the row-loss (F5's own symptom) AND a second, related defect the trace didn't show — cross-run IDENTITY CONTAMINATION in the ZoomInfo Token Gate (a run pairs $input row-1/row-4 with gateRows belonging to row-2/row-3, attaching the WRONG identity_keys to a live ZoomInfo call whenever ZoomInfo is enabled — invisible in execution 12163 only because providers were disabled there)."
  falsification_test: >
    If a Normalize+Score run legitimately needed the RAW (not surviving-only) run index
    of its Gate — i.e. if n8n executes converged inbound branches out of the temporal
    order they were wired, or if a dropped (all-skip) wave could somehow still trigger a
    downstream run — the scan-based recoverConvergedRun (matching runs by SURVIVING
    sequence position, not raw index) would misalign instead of fixing. Nothing in this
    session observed or could construct such a case (no live access to prove branch
    execution order deterministically); documented as a residual blind spot below rather
    than silently assumed away.
  fix_rationale: >
    The straightforward documented fix, `$('Gate').all(0, $runIndex)`, is NOT sufficient
    by itself: a wave can be dropped ENTIRELY between "Enrichment Gate"/"Company Gate" and
    the reader (every row in that wave resolves action:"skip" — e.g. the "IF Name
    Searchable" false/unmatchable lane, or "IF Company Skip"'s true lane — and "IF
    Provider Processing Needed"/"IF Company Skip" is the ONE point where such a wave never
    reaches the provider chain at all). A dropped wave still consumes one of the Gate's
    raw run indices without ever producing a run of the reader, so a LATER wave's
    $runIndex would then point at the WRONG (dropped) Gate run — a drift the advisor
    caught before any code was written (see Evidence). recoverConvergedRun
    (n8n/code/nodeRunRecovery.js) scans the Gate's own runs in order, keeping only the
    ones surviving a `keep` predicate, and returns the SURVIVING run at the reader's own
    $runIndex — immune to that drift by construction, proven by a dedicated offline test
    scenario (B) that a bare .all(0,$runIndex) fix would fail. Lusha/Apollo/ZoomInfo Enrich
    sit entirely DOWNSTREAM of the one drop point on a single-file chain (no further
    branching), so their own run counts stay 1:1 with Normalize+Score's — a bare
    `.all(0, $runIndex)` is provably sufficient for them (advisor-confirmed), which is why
    the fix uses the cheaper form there and reserves the scan for reads that cross the
    drop point.
  blind_spots: >
    No live n8n access this session (no .env) — the "last run wins" mechanism and the
    documented .all(0,$runIndex) semantics are confirmed against n8n's own published docs
    plus the ALREADY-CAPTURED live trace (execution 12163), but the drift scenario (an
    all-skip wave landing BEFORE a later actionable wave) and the ZoomInfo Cache Token
    predicate (zoom_needs_mint) were never observed live — only reasoned from the wiring
    and proven against an offline simulation of n8n's documented .all(branch,run)
    contract. The operator's Round B re-run after deploy is the first live proof.
  candidate_causes:
    - "code: by-name .all() reads with no run index, at every downstream consumer of a
      multi-inbound-edge node (Enrichment Gate, Company Gate) — confirmed, fixed at all
      6 call sites (2 shared functions covering 3 call sites each via _zoom_preamble/
      _zoom_split_gate_js/_zoom_split_cache_js reuse)"
    - "process: none — unlike F4, this is a pure code defect with a full mechanism proof;
      no out-of-band call or operator action contributed to F5"
  and_gate: >
    no — one root cause (the by-name .all() collapse), fixed uniformly by one shared
    helper function reused at every exposed call site; the AND-gate does not fire because
    no second, independent contributing condition was found or needed to explain the
    symptom.
```

## F4 — evidence found after the fix (2026-09-09): `drv_enrich.py:11` in the 2026-09-08 session's scratchpad hard-codes `enrich_rows=[row-1, row-2]`; row-3 was excluded by the operator-Claude's driver before `run_state.start_run`. `:39` passes `async_ack=True` (the `392753a` leak's source). The "out-of-band call" hypothesis is confirmed with the exact file; no repo defect.

## F5 — Evidence (audit + fix, 2026-09-09)

- timestamp: 2026-09-09T04:00:00Z
  checked: scripts/build_cloud_workflows.py wiring for every inbound edge into
    "Enrichment Gate" (:6363-6412) and "Company Gate" (:6473-6489)
  found: "Enrichment Gate" has FIVE inbound edges (fetch-by-id, email, linkedin, name,
    and "IF Name Searchable"'s false/unmatchable branch straight to the Gate); "Company
    Gate" has TWO (fetch-by-id, and domain-search -> name-search-fallback). Downstream of
    each Gate there is exactly ONE wave-dropping point before the provider chain: "IF
    Provider Processing Needed" (contacts) / "IF Company Skip" (companies) — a wave whose
    every row resolves `action: "skip"` never reaches "Normalize + Score"/"Normalize +
    Score Company" at all. `IF Company Recompute` does NOT create per-wave variability
    (CLAUDE.md §13.0.2: `recompute` is a REQUEST-level boolean, same value for every row
    in an execution, never a per-row split).
  implication: confirms the advisor's structural claim before any code was written — a
    naive `.all(0, $runIndex)` fix would drift whenever an all-skip wave lands before a
    later actionable wave, because the dropped wave still consumes one of the Gate's raw
    run indices without producing a run of the reader.
- timestamp: 2026-09-09T04:10:00Z
  checked: `_zoom_split_contacts_subgraph`/`_zoom_split_company_subgraph`/
    `_zoom_split_usage_subgraph` (scripts/build_cloud_workflows.py:4249-4508) — the
    ACTUAL ZoomInfo implementation `build_enrichment_cloud()` deploys (not
    `ENRICH_ZOOMINFO_CACHED`/`ENRICH_ZOOMINFO_CO_CACHED`, which are the
    `build_enrichment_local_live()`-only single-node variant)
  found: `_zoom_split_gate_js(gate_source_node)` ("ZoomInfo Token Gate"/"ZoomInfo Company
    Token Gate") reads `$('{gate_source_node}').all()` — same by-name, no-run-index
    collapse, one MORE exposed site the original F5 note (which only named
    ENRICH_ZOOMINFO_CACHED's :1924) did not cover. `_zoom_split_cache_js(token_gate_name)`
    ("ZoomInfo Cache Token"/"ZoomInfo Company Cache Token") reads its OWN upstream Token
    Gate node the SAME way, but that read has ITS OWN drop point: "ZoomInfo Cache Token"
    only runs on waves that needed a token mint (`zoom_needs_mint === true`), a SUBSET of
    the Token Gate's own runs — a second instance of the identical drift class, one level
    deeper in the chain, needing the SAME scan-based fix with a DIFFERENT `keep` predicate.
    `_zoom_split_usage_subgraph` (the credit-check branch, "Credit Request"/"Status Credit
    Request" as `gate_source_node`) reuses the SAME two functions — fixing them once fixed
    it too, safely: its rows carry no `.action` field at all, so the `action !== "skip"`
    predicate degrades to "keep everything" there, matching its own single-run reality.
  implication: the fix touches 6 call sites total via 2 shared helper functions
    (`_zoom_preamble` for the local-live single-node variant's 2 sites;
    `_zoom_split_gate_js`/`_zoom_split_cache_js` for the CLOUD split-subgraph's 4 sites,
    reused 3x each across contacts/companies/credit-usage) — one code change per function,
    not 6 separate hand-edits.
- timestamp: 2026-09-09T04:20:00Z
  checked: web search of n8n's own published docs (docs.n8n.io/code/cookbook/builtin/all,
    docs.n8n.io/code-examples/methods-variables-examples/run-index)
  found: `$('Node').all()` with no run index "returns the items of the node's most recent
    run" (matches the live collapse exactly); `.all(branchIndex, runIndex)` is the
    documented signature; `.all(0, $runIndex)` is n8n's own documented idiom for "same run
    as the current node". `$('Node').itemMatching(currentNodeInputIndex)` is a second,
    lineage-based primitive that survives HTTP-hop $json replacement without any run-index
    arithmetic at all — considered as an alternative design (advisor raised it as worth
    weighing), not used: it requires every intervening node between the Gate and the
    reader to preserve n8n's automatic paired-item linking (a real but unverified
    assumption for the ZoomInfo split-subgraph's Mint/Cache hops, since this repo has no
    live n8n access to confirm linking survives every hop), whereas the scan-based fix
    depends only on documented, already-confirmed `.all(branch,run)` semantics.
  implication: the chosen fix (recoverConvergedRun, a bounded forward scan over
    `.all(0, r)` keeping only surviving runs) is grounded in CONFIRMED semantics only,
    not an additional unverified assumption about paired-item lineage survival.
- timestamp: 2026-09-09T04:40:00Z
  checked: `tests/n8n/enrichmentGateRunRecoveryFlow.test.mjs` + `tests/n8n/
    nodeRunRecovery.test.mjs` executed against the pre-fix committed workflow JSON
    (`git stash` of `scripts/build_cloud_workflows.py` + the 3 regenerated `n8n/wf_*.json`
    files, restoring the exact pre-session state) vs. the post-fix state
  found: RED before fix — 0/5 integration tests pass (all 5 fail: two-run row loss on
    both contacts and companies Normalize+Score, the drift case on both, and the ZoomInfo
    Token Gate cross-run identity-contamination case). GREEN after fix — 5/5 pass, plus
    7/7 on the pure-function `recoverConvergedRun` unit tests (unaffected by the stash
    since that file was untracked, moved aside separately and confirmed present for both
    runs).
  implication: proves the fix is what fixes it (Fix-Acceptance Guardrail signal 5,
    revert-and-reconfirm), not merely correlated with the test passing.
- timestamp: 2026-09-09T04:50:00Z
  checked: full `node --test tests/n8n/*.test.mjs` run immediately after the fix, before
    any collateral repair
  found: 9 pre-existing tests broke — `personaGroupProducer.test.mjs` (2),
    `linkedinProducer.test.mjs` (1), `bareEventChainFlow.test.mjs` (2),
    `enabledResearchLaneFlow.test.mjs` (3), plus 1 duplicate-count line — every failure
    `ReferenceError: $runIndex is not defined`. Each of these files runs "Normalize +
    Score"/"Normalize + Score Company" jsCode via its OWN hand-rolled `new Function(...)`
    harness (pre-dating this fix), none of which declared a `$runIndex` parameter, because
    nothing in the committed jsCode read it before this session.
  implication: NOT a sign the fix is wrong — a genuinely new global the fixed jsCode reads
    that 4 test harnesses (all copies/mirrors of the same single-run pattern, per their own
    comments) never declared. Fixed by adding `"$runIndex"` to each `new Function(...)`
    parameter list and passing `0` at each call site (every one of these harnesses models
    exactly one execution of each node, so $runIndex is always 0 by construction — matches
    the mocked `.all()` in each of these files, which already ignores its arguments).
    Confirms Fix-Acceptance Guardrail signal 4 (adjacent tests) caught a REAL collateral
    break the driving test alone would not have — full node suite green (954/954) only
    after this repair.

## F5 — RESOLVED

root_cause: `scripts/build_cloud_workflows.py`'s downstream readers of "Enrichment
  Gate"/"Company Gate" (required to read them BY NAME, not via `$input`, because HTTP
  provider-hop nodes replace `$json` — memory `companies-research-lane-rowloss`) used a
  bare `$('Gate').all()` with no run index. "Enrichment Gate"/"Company Gate" each have
  more than one inbound connection (contacts: fetch-by-id/email/linkedin/name/unmatchable;
  companies: fetch-by-id/domain-search) and n8n runs a node with multiple inbound edges
  ONCE PER FIRING EDGE (confirmed live, execution 12163), not once on a merged item array.
  n8n's own docs confirm a bare `.all()` "returns the items of the node's most recent
  run" — so every run of a downstream reader collapsed onto the SAME final Gate run,
  silently losing every row from every earlier lane (a mixed 4-row batch returned only
  the 2 no-email rows, twice, and lost both email rows — one of which, Natalie Waters, was
  an EXISTING contact, putting her at risk of duplicate creation). A second, related
  defect was found in the same audit: the ZoomInfo split-subgraph's Token
  Gate/Cache Token nodes pair `$input`'s row i with the Gate's (collapsed, wrong-run)
  row i by POSITION — not just row loss but silent cross-run IDENTITY CONTAMINATION,
  attaching one lane's identity_keys to another lane's ZoomInfo request whenever ZoomInfo
  is enabled (invisible in execution 12163 only because providers were disabled there).
fix: added `n8n/code/nodeRunRecovery.js` (`recoverConvergedRun`) — a pure, Node-testable
  function that scans an upstream node's own runs in temporal order via `.all(0, r)`,
  keeping only the runs surviving a caller-supplied `keep` predicate, and returns the
  SURVIVING run at the reader's own `$runIndex`. This is deliberately NOT the simpler
  documented `.all(0, $runIndex)` idiom alone: a wave can be dropped entirely between the
  Gate and the reader (every row in it resolves `action: "skip"`, e.g. the unmatchable
  contacts lane or "IF Company Skip"'s true lane) — a dropped wave still consumes one of
  the Gate's raw run indices without ever producing a run of the reader, so pairing by raw
  run index would misalign for every wave after the drop (an advisor-caught risk, proven
  by a dedicated offline drift-scenario test). Applied at all 6 exposed call sites via 2
  shared functions: `_zoom_preamble` (adds `nodeRunRecovery.js` to the local-live
  single-node ZoomInfo variant's shared inline() — `ENRICH_ZOOMINFO_CACHED`/
  `ENRICH_ZOOMINFO_CO_CACHED`) and `_zoom_split_gate_js`/`_zoom_split_cache_js` (the CLOUD
  split-subgraph actually deployed — reused 3x each across contacts/companies/
  credit-usage). `ENRICH_NORMALIZE_SCORE_CLOUD`/`ENRICH_NORMALIZE_SCORE_CO` (the shared
  "Normalize + Score"/"Normalize + Score Company" constants, used by BOTH
  `build_enrichment_local_live()` and `build_enrichment_cloud()`) use the scan for their
  Gate read and a plain `.all(0, $runIndex)` for Lusha/Apollo/ZoomInfo Enrich — provably
  sufficient there because those three sit entirely downstream of the ONE drop point on a
  single-file chain with no further branching, so their own run counts stay 1:1 with the
  reader's. Regenerated every affected `n8n/wf_*.json` via `scripts/build_cloud_workflows.py`
  (never hand-edited) — only `wf_enrichment_cloud.json`, `wf_enrichment_local_live.json`,
  and `wf_backend_status_cloud.json` (the credit-usage branch reuses the same two shared
  functions) changed; `wf_enrichment_local.json` (the fully-mocked variant, no by-name
  Gate reads at all), `wf_contact_ingest_*`, `wf_scheduled_maintenance_cloud.json`, and
  `wf_review_decision_cloud.json` are untouched, confirmed via `git status --porcelain`.
verification: RED before fix — `tests/n8n/enrichmentGateRunRecoveryFlow.test.mjs` (5
  tests, run against the pre-fix committed JSON via `git stash`): 0/5 pass, reproducing
  both the row-loss (F5's reported symptom, scenarios A on both contacts/companies) and
  the drift case (scenario B on both) and the ZoomInfo Token Gate cross-run identity
  contamination. GREEN after fix (`git stash pop`): 5/5 pass; `tests/n8n/
  nodeRunRecovery.test.mjs` (7 pure-function tests, including the same drift scenario and
  a `zoom_needs_mint` predicate case for the Cache Token site, and explicit coverage of
  both possible "past the last run" signals — throw or empty array, since n8n's docs do
  not specify which): 7/7 pass.
  Collateral repair (Fix-Acceptance Guardrail signal 4, adjacent tests): 9 pre-existing
  tests across `personaGroupProducer.test.mjs`, `linkedinProducer.test.mjs`,
  `bareEventChainFlow.test.mjs`, `enabledResearchLaneFlow.test.mjs` broke
  (`$runIndex is not defined` — their own hand-rolled single-run `new Function(...)`
  harnesses never declared it); fixed by adding `"$runIndex"` to each harness's parameter
  list and passing `0` (every one of these harnesses models exactly one node execution).
  Full suites green: `node --test tests/n8n/*.test.mjs` 954/954 (940 baseline + 12 new: 5
  + 7 across the two new files; 2 collateral-fixed files' test counts unchanged).
  `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` 2850/2850 (unchanged — no
  Python source touched by F5). `.venv/bin/python -m pytest -q --tb=short` 4608/154
  (unchanged). No Stryker configuration exists in this repo (mutation-check signal
  skipped, logged per the guardrail's degradation table). No-op/deletion detector: the
  diff is purely additive (one new shared helper, its adoption at 6 call sites, and the 4
  collateral test-harness parameter additions) — no branch, assertion, or behavior was
  removed or weakened.
operator_handoff: deploy the regenerated `n8n/wf_enrichment_cloud.json` and
  `n8n/wf_backend_status_cloud.json` to n8n Cloud (needs the operator's `.env`, out of
  scope for this session), bounce, and re-run Round B's mixed email/no-email chunk. This
  is the first live proof of the fix (no live n8n access this session) — specifically
  re-check that Natalie Waters (`351336543679`, an EXISTING contact) is no longer at risk
  of duplicate creation via the `unchecked` fallback the operator's Claude worked around
  off-SKILL during Round B.
files_changed:
  - n8n/code/nodeRunRecovery.js (new)
  - scripts/build_cloud_workflows.py
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_enrichment_local_live.json
  - n8n/wf_backend_status_cloud.json
  - tests/n8n/nodeRunRecovery.test.mjs (new)
  - tests/n8n/enrichmentGateRunRecoveryFlow.test.mjs (new)
  - tests/n8n/personaGroupProducer.test.mjs
  - tests/n8n/linkedinProducer.test.mjs
  - tests/n8n/bareEventChainFlow.test.mjs
  - tests/n8n/enabledResearchLaneFlow.test.mjs

## F5 — post-fix self-checks (2026-09-09, before returning the checkpoint)

- timestamp: 2026-09-09T05:10:00Z
  checked: `/usr/bin/grep -n "onError" scripts/build_cloud_workflows.py` (every `onError`
    site in the file, not just the ones on the Gate->Normalize+Score chain)
  found: every occurrence is `onError: "continueRegularOutput"` (or the helper's own
    documented default of the same value) — a provider/HTTP failure always lands as an
    ITEM on the node's REGULAR output, never routed to a separate error branch. No
    `continueErrorOutput` anywhere in the file.
  implication: confirms there is exactly ONE wave-dropping point between "Enrichment
    Gate"/"Company Gate" and "Normalize + Score"/"Normalize + Score Company" — the
    `action !== "skip"` gate ("IF Provider Processing Needed"/"IF Company Skip") — which
    is what the fix_rationale's "Lusha/Apollo/ZoomInfo sit downstream of the ONE drop
    point" claim depends on. A second, hidden drop point via HTTP error routing would
    have made the plain `.all(0, $runIndex)` simplification for those three wrong; ruled
    out.
- timestamp: 2026-09-09T05:12:00Z
  checked: builder idempotency (`python scripts/build_cloud_workflows.py` re-run, then
    `git status --porcelain -- n8n/`) and node count (`jq '.nodes|length'
    n8n/wf_enrichment_cloud.json`)
  found: re-running the builder against the committed source produces a byte-identical
    `n8n/wf_enrichment_cloud.json` (empty git diff) — confirms the committed JSON is
    exactly what the committed builder emits, not hand-edited. Node count: 123 (unchanged
    from CLAUDE.md §13.0.2's last-recorded count) — this fix edited existing Code nodes'
    `jsCode` strings only, added/removed none.
  implication: satisfies the debug file's own Constraints ("never hand-edit
    `n8n/wf_*.json`... regenerate; Phase 46 parity") and the resume directive's explicit
    node-count-unless-Merge-node-is-smallest condition (a Merge node was NOT used; the
    scan-based fix stayed inside existing Code nodes).
- timestamp: 2026-09-09T05:14:00Z
  checked: `n8n/wf_enrichment_cloud.json`'s top-level `settings` key (workflow-level
    `executionOrder`)
  found: `"settings": {}` — `executionOrder` is ABSENT, not explicitly set to either `v0`
    (legacy) or `v1`. Recorded as context, not asserted as evidence either way: this
    session has no live n8n access to observe what execution order n8n actually applies
    for an unset value on this account/version, or whether it affects the ORDER in which
    independently-firing inbound branches into "Enrichment Gate"/"Company Gate" execute.
  implication: **this is the fix's one remaining unverified assumption, flagged rather
    than silently assumed away** (advisor-raised, 2026-09-09). recoverConvergedRun pairs
    "Normalize + Score" run *k* with "Enrichment Gate"'s *k*-th SURVIVING run — correct
    only if the reader's own runs fire in the SAME temporal order the Gate's runs did
    (chain 0 -> reader run 0, chain 1 -> reader run 1). The live trace (execution 12163)
    proves BOTH Gate runs completed before either Normalize+Score run started (not pure
    depth-first-per-lane), but does NOT prove which chain the Gate processed FIRST, or
    that Normalize+Score's own run order matches it. In propose mode (Round B, as run so
    far) this is INVISIBLE either way — providers are off, so `lusha`/`apollo`/`zoominfo`
    are always `[]` regardless of pairing, and Normalize+Score just re-emits whichever
    Gate row set it paired with, all 4 row_ids present either way. The misalignment would
    only be OBSERVABLE once providers are enabled: `lusha = nodeAll('Lusha Enrich')` would
    correctly be chain-k's own provider data (downstream of the one drop point, in
    lockstep with its own reader), but `rows` would be chain-(1-k)'s Gate data if run
    order were reversed — stapling one lane's provider response to the OTHER lane's row,
    the exact contamination class already found and fixed at "ZoomInfo Token Gate", one
    node later in the chain. **This is why the checkpoint below asks the operator to
    verify per-run row_id identity, not just that all 4 rows came back.**

## executionOrder (2026-09-09, read via the plugin key)
`settings.executionOrder` is absent on both the committed `wf_enrichment_cloud.json`/`wf_contact_ingest_cloud.json` and the live `950HPb7a1GgSAIyZ`/`AwbBeShdPgV48eiY` bodies — n8n therefore runs the legacy `v0` order. Live enrichment `updatedAt` was `2026-09-09T03:04:48Z`, after the 01:33Z bounce and before the F5 deploy; source of that touch unknown (operator-Claude probes ran 02:57–03:00Z).
