---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
verified: 2026-09-10T06:23:26Z
status: human_needed
score: 28/28 offline-verifiable must-haves verified (gap-closure plans 70-08..70-12); 2 live proof gates remain (Gate 5, Gate 6); Gate 4 recorded but not exercised (operator went forward instead of rolling back — see Human Verification Required)
behavior_unverified: 0
overrides_applied: 0
covered_files:
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-01-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-01-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-02-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-02-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-03-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-03-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-04-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-04-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-05-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-05-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-06-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-06-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-07-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-07-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-08-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-08-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-09-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-09-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-10-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-10-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-11-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-11-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-12-PLAN.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-12-SUMMARY.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-CONTEXT.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-ROLLBACK-DRYRUN.txt
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-ROLLBACK-RUNBOOK.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-RUNTIME-VERDICT.json
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-UAT.md
  - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-WALKER-RED-INVENTORY.md
  - CLAUDE.md
  - n8n/wf_contact_ingest_cloud.json
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_enrichment_local_live.json
  - n8n/wf_review_decision_cloud.json
  - operator-claude-plugin/scripts/dispatch.py
  - scripts/build_cloud_workflows.py
  - scripts/prove_phase70_runtime.py
  - tests/n8n/lib/walkWorkflow.mjs
  - tests/n8n/mergeInputContract.test.mjs
  - tests/n8n/walkerEngineFidelity.test.mjs
covered_digest: "v1:sha256:a59b21e89983e2d18cce237f2257f29d758c8fab0a854ae61acb564ac4ac86fa"
re_verification:
  previous_status: human_needed
  previous_score: "26/26 must-haves verified (offline-verifiable set); 3 items human_needed (deferred live gates) — as actually recorded in the prior 70-VERIFICATION.md (commit e4e95f0); note the commit MESSAGE for that same commit read '37/39 offline truths verified' — the message and the file content disagreed, and this round trusts the file, not the message"
  gaps_closed:
    - "G-70-1 (run_id echo lost to a Content-Type-bearing multipart part) — fixed in-session on 2026-09-10, re-verified here: dispatch.py uses a 2-tuple (None, value) for run_id and source_by_field; test_dispatch_multipart.py pins len(part) == 2"
    - "G-70-2 / G-70-3 (zero-item sentinel delivery pre-empts a real row on a shared Merge input, engine rule the walker never modelled) — fixed offline by 70-09 (walker corrected to the engine, RED-first against frozen fixtures of 12203/12206), 70-10 (D-70-23 gated-sentinel mechanism, ingest lane), 70-11 (enrichment/review/local-live lanes converted, 15-input Build Response Merge split into 3 stage Merges each <=10 inputs, Merge-input contract enforced at generation time with an empty PENDING list)"
    - "G-70-4 (prove_phase70_runtime.py's ingest comparator compared client-reconciled rows against the walker's raw rows) — fixed by 70-12: dispatch.dispatch() now returns a sibling raw_rows key from the same recovery call, and the driver's ingest branch reads it via a new _ingest_recovered_rows() function, proven RED on execution 12207's recorded shape before the fix"
  gaps_remaining:
    - "Gate 5 (disarmed redeploy of the gap-closure JSON + re-run of the D-70-19 proof) — not yet run; the live n8n instance still runs the PRE-gap-closure Phase 70 bodies (218/50/45/43/30), deployed and bounced disarmed on 2026-09-10 for Gates 1 and 3, which still has the G-70-2/G-70-3 defect live and returns 0 rows on an enrichment request"
    - "Gate 6 (first ARMED mixed-verdict batch against the fixed graph) — gated behind Gate 5 passing; not run"
  regressions: []
gaps: []
deferred: []
human_verification:
  - test: "Standing operational decision, live NOW: the deployed n8n instance still runs the PRE-gap-closure Phase 70 JSON (218/50/45/43/30), which has the G-70-2/G-70-3 defect — every enrichment request against it silently returns 0 rows (executions 12204-12206). Gate 4 (roll back to commit 59812be, prepared and pinned by 70-08) and Gate 5 (redeploy the fixed 291/69/55/43/30/82/10/13 JSON, prepared by 70-09..70-12) are the two live options; neither has been exercised."
    expected: "Operator picks one: run Gate 4 to revert the live instance past Phase 70 entirely (accepting the pre-Phase-70 behaviour until Phase 70 is redeployed later), or run Gate 5 to redeploy the fixed JSON and close the defect directly. Leaving the instance as-is means live enrichment requests keep silently returning 0 rows."
    why_human: "This is a live deploy/bounce decision on the operator's own n8n Cloud + HubSpot instance; not something the offline suite can decide or execute, and the standing 2026-09-09 ruling defers exactly this kind of live action to the operator at end-of-phase"
  - test: "Gate 5 — deploy + bounce the committed gap-closure JSON disarmed (node counts 291/69/55/43/30/82/10/13, confirmed matching the working tree at verification time), then run ALLOW_PHASE70_RUNTIME_PROOF=true .venv/bin/python scripts/prove_phase70_runtime.py (same 4 sends as Gate 3: enrichment_2x2, enrichment_single_lane, ingest_2x2, ingest_single_lane)"
    expected: "70-RUNTIME-VERDICT.json shows shapes_equal: true on all four sends, all four executions settled (none stuck running), writes_performed: 0, every write flag reads \"false\", and the three stage Merges that replaced the 15-input Build Response Merge all fire so Build Response actually runs (answering the still-CONFOUNDED question from Gate 3)"
    why_human: "Requires a live deploy + bounce + disarmed send against n8n Cloud and HubSpot; no committed workflow in this repo has run the gated-sentinel/stage-split graph live yet — the offline walker fidelity (execs 12203/12206) proves the walker models the OLD defect correctly, and the offline acceptance suite (enrichmentConvergenceMerge.test.mjs, writeGateShape.test.mjs) proves the NEW committed graph behaves as designed under the walker's model — neither proves the real engine agrees with that model on the regenerated graph, which is exactly the gap Gate 3 found once already"
  - test: "Gate 6 — arm one window naming exactly one of two contacts resolving the same company (Darwin Turf Club precedent pair: 7101 permitted, 2751 refused, or an equivalent pair), send both in one ingest batch, only after Gate 5 has passed"
    expected: "Build Ingest Response returns exactly 2 rows; the permitted row reports action: update, association: associated (not not_confirmed — the exact field Gate 70-05-A found wrong on execution 12203); the refused row reports action: write_blocked with association not associated; execution settled; HubSpot shows exactly one contact updated and one association created, the other contact untouched; disarm afterward and read all three declaring nodes back at their disarmed literals"
    why_human: "This is the armed re-run of the exact live scenario (execution 12203) that produced gap G-70-2; only a real armed write against HubSpot proves the gated-sentinel fix holds where the walker's model previously diverged from the engine"
---

# Phase 70: One merge, one result channel — n8n runtime truth (Gap-Closure Verification)

**Phase Goal:** a batch with two identity lanes and two actions returns every row once, from
the write that happened, on one client result channel — and the offline harness would have
caught every finding the 2026-09-09 UAT found.

**Verified:** 2026-09-10
**Status:** human_needed
**Re-verification:** Yes — after gap closure (plans 70-08..70-12, closing G-70-1..4 found by the
2026-09-09/10 end-of-phase UAT)

## Context

This is the gap-closure verification round. The prior `70-VERIFICATION.md` (now overwritten,
content read from commit `e4e95f0`) covered plans 70-01..70-07 offline at **26/26** must-haves
verified and deferred Gates 1, 70-05-A, and 3 as `human_needed` (note: that commit's own commit
MESSAGE says "37/39" — the message and the file content disagree; this round trusts the file).
Those three gates then RAN live on 2026-09-10 (`70-UAT.md`): Gate 1 passed after an in-session
fix (G-70-1); Gate 70-05-A and Gate 3 both found a real engine defect (G-70-2/G-70-3, a
zero-item Code output IS a Merge-input delivery — the walker never modelled this) plus a
comparator artifact (G-70-4). Plans 70-08..70-12 closed all four gaps **offline** and recorded
two new live gates (Gate 5, Gate 6) that must still run against the fixed graph before the phase
can close as `passed`. Gate 4 (pre-Phase-70 rollback) was prepared but the operator chose to go
forward with the Phase 70 JSON rather than roll back — this leaves the live instance running the
PRE-gap-closure JSON with the defect still live (0 rows on any enrichment request), which is
surfaced below as a standing human-verification item, not folded silently into a "recorded, no
action needed" note.

`ROADMAP.md`'s Phase 70 entry carries only a prose **Goal** (no separate `success_criteria`
array) — the Goal text above is the full roadmap contract and is what this report verifies
against; nothing was skipped by relying on plan `must_haves` alone.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | D-70-21: the five pre-Phase-70 bodies are pinned by commit + node count (17/29/123/26/39) | VERIFIED | `.venv/bin/python -m pytest tests/test_phase70_rollback_bundle.py -q` → 15 passed |
| 2 | D-70-21: a self-contained rollback runbook exists, no other plan needed | VERIFIED | `70-ROLLBACK-RUNBOOK.md` names commit `59812be`, all 5 workflow filenames, `DRY_RUN`/`ALLOW_N8N_DEPLOY`, `bounce_n8n_workflows.py`, node counts, both write-flag names, dirty-tree refusal as step 1 |
| 3 | Rollback prep made zero live writes; working tree byte-identical to HEAD when done | VERIFIED | `70-ROLLBACK-DRYRUN.txt` documents a real live GET + dry-run diff (DRY RUN banner, no write); `git status --porcelain -- n8n/` is empty now |
| 4 | The live deploy/bounce is the operator's step, recorded as Gate 4 | VERIFIED (recorded); standing action NOT taken — see Human Verification Required | `70-DEFERRED-GATES.md` § Gate 4 present; operator went forward instead of rolling back (`70-12-SUMMARY.md`), leaving the live instance on the defective JSON |
| 5 | D-70-20: walker models zero-item-output-as-delivery, first-delivery-wins, fires-once | VERIFIED | `tests/n8n/lib/walkWorkflow.mjs` lines ~345-407 implement exactly this, each rule commented with its observing execution id (12200/12203/12206) |
| 6 | D-70-20 correction lands RED-first against a test on the CURRENT committed graph | VERIFIED | git history: `563940b test(70-09): RED — reproduce execution 12203 against the frozen ingest graph` precedes `062154b feat(70-09): correct the walker's delivery model` |
| 7 | D-70-19: walker corrected toward the engine, not toward plans/green-suite | VERIFIED | `tests/n8n/walkerEngineFidelity.test.mjs` reproduces executions 12203 and 12206 against `tests/n8n/fixtures/frozen/*.2026-09-10.json` (byte-identical, never regenerated) — both pass |
| 8 | Node-fed-zero-items-never-runs modelled distinctly from ran-but-empty-still-delivers | VERIFIED | `walkWorkflow.mjs` line ~456-461: `if (delivery.items.length === 0) continue` gating node execution, vs. the separate arrived/buffers delivery-tracking logic |
| 9 | Literal D-70-20 mechanism (dedicated always-marking sentinel input) shown to starve a real-producer input | VERIFIED | `70-09-SUMMARY.md` key-decisions: "the literal D-70-20 mechanism ... is priced and shown to never rescue a sibling input's starvation" |
| 10 | Which suites go RED under the corrected walker is recorded with a reason per suite | VERIFIED | `70-WALKER-RED-INVENTORY.md` exists (9.6K), traces all 26 new RED failures to one generator function (`splice_carry_merge_after`) |
| 11 | D-70-20's intent holds: sentinel output never pre-empts a real producer's row, on any lane | VERIFIED | `_add_starved_lane_sentinel` (build_cloud_workflows.py:9865) — condition feeds a gate node, gate is fed zero items and does not run when the lane is live; `mergeInputContract.test.mjs` PENDING list empty across all 8 workflows |
| 12 | D-70-20's mechanism decided by operator on a measured comparison, recorded as D-70-23 | VERIFIED | `70-CONTEXT.md` / `70-10-SUMMARY.md`: "D-70-23: Option B, gated sentinel"; `_sentinel_gate_js()` docstring cites the executions (12204-12206, 12200) that motivated it |
| 13 | Sentinel delivers only when genuinely starved; live lane produces no delivery at all | VERIFIED | `_sentinel_gate_js()` body: gate node fed zero items when condition emits `[]`, per the "node fed zero items does not run" rule |
| 14 | Starved association carry Merge bypassed (sentinel targets the consumer, not a positional marker) | VERIFIED | `70-10-SUMMARY.md`: "Associate Lane Sentinel bypasses Associate Carry Merge, targeting Ingest Merge Response directly" |
| 15 | No routing IF has a direct edge to a Merge input | VERIFIED | `mergeInputContract.test.mjs` structural rule (no routing-IF-direct edge) passes on all 8 committed workflows, PENDING list empty; `_retarget_all_if_direct_edges` applied (28 edges enrichment lane, 4 local-live, 3 review-decision per 70-11-SUMMARY) |
| 16 | Ingest lane's armed mixed-verdict batch returns correct per-row outcomes offline | VERIFIED | `tests/n8n/writeGateShape.test.mjs::"ingest, ARMED with a mixed verdict: the permitted row keeps its association and the refused row reports blocked"` — loads and walks the COMMITTED (regenerated) `n8n/wf_contact_ingest_cloud.json`, arms it exactly as `n8n_arming.set_write_safety` would, and asserts `byEmail[MIX_A].association === "associated"` and `byEmail[MIX_B].action === "write_blocked"` — the exact fields execution 12203 got wrong |
| 17 | n8n_arming.set_write_safety still rewrites all 3 declaring nodes on the ingest lane | VERIFIED | Structural: exactly 3 nodes in `n8n/wf_contact_ingest_cloud.json` carry `ALLOW_HUBSPOT_RECORD_WRITES`. Confirmed dynamically by invoking `set_write_safety(wf, {"ALLOW_HUBSPOT_RECORD_WRITES": True, "TEST_RECORD_IDS": "7101"})` in-memory against the loaded regenerated JSON — returns `{'ALLOW_HUBSPOT_RECORD_WRITES': 3, 'TEST_RECORD_IDS': 3}` |
| 18 | G-70-3 closed offline: disarmed enrichment batch reaches the response builder, one row per input row | VERIFIED | `tests/n8n/enrichmentConvergenceMerge.test.mjs::"a mixed batch (one create, one update) reaches Build Response with exactly two rows"` — walks the COMMITTED `n8n/wf_enrichment_cloud.json` with a real 2-row batch, asserts `trace.stalled` empty and `nodeItems(runData, "Build Response").length === 2` with the correct emails, matching per row |
| 19 | No Merge in any committed workflow declares more than 10 inputs | VERIFIED | Direct scan of all `n8n/wf_*.json`: zero Merge nodes with `numberInputs > 10` |
| 20 | Merge-input contract test's PENDING list is empty; every committed workflow replays without a stalled Merge | VERIFIED | `node --test tests/n8n/mergeInputContract.test.mjs` → 18/18 pass, including "PENDING names exactly the workflows that violate the contract, in both directions" |
| 21 | Contract enforced at GENERATION time, not only in a test | VERIFIED | `_assert_generation_contracts()` (build_cloud_workflows.py:11363-11368) composes `assert_merge_input_contract` + `assert_no_by_name_reads`; called at all 8 write sites in `main()` |
| 22 | Whole offline harness green again (node, root Python, plugin Python) | VERIFIED | `node --test tests/n8n/*.test.mjs` → 1064/1064; `.venv/bin/python -m pytest -q` → 4690 passed, 154 skipped; `cd operator-claude-plugin && ../.venv/bin/python -m pytest -q` → 2865 passed, 5 skipped |
| 23 | D-70-22: proof driver compares RAW recovered rows against walker's raw rows on the ingest lane | VERIFIED | `scripts/prove_phase70_runtime.py::_ingest_recovered_rows` reads `dispatch_result.get("raw_rows")`; `dispatch.py` returns `"raw_rows": recovered_rows` as a sibling of the pre-existing reconciled `"rows"` |
| 24 | Comparator change proven by a test that fails on execution 12207's shape before the fix | VERIFIED | `tests/test_prove_phase70_runtime.py::test_ingest_recovered_rows_reads_the_raw_key_not_the_reconciled_one` — asserts against a function that did not exist pre-fix (AttributeError RED); passes now (19/19 in the file) |
| 25 | Every platform fact this UAT observed is recorded in CLAUDE.md tagged observed-live with execution ids | VERIFIED | CLAUDE.md §13.0.3 table rows for zero-item-delivery, first-delivery-wins, fires-once, starvation-silent-success, node-fed-zero-items, multipart-Content-Type — each cites its execution id(s) (12200/12203/12206/12204-12206) |
| 26 | D-70-02's documented-only executionOrder claim upgraded to observed-live (absent) | VERIFIED | CLAUDE.md §13.0.3: "`settings.executionOrder` is ABSENT on all five running cloud workflow bodies ... `[observed live]` (2026-09-10 ... `70-RUNTIME-VERDICT.json`)" |
| 27 | Deployment-parity note corrected: live went forward disarmed on 2026-09-10, gap-closure JSON now ahead again | VERIFIED | CLAUDE.md §13.0.2 "Extended 2026-09-10 (Gate 1 / Gate 3 UAT, then gap-closure plans 70-08..70-12)" section, with the before/after node-count table (218→291 etc.) |
| 28 | Two remaining live proofs (disarmed redeploy+re-proof, armed mixed-verdict re-run) recorded as explicit end-of-phase gates | VERIFIED | `70-DEFERRED-GATES.md` § Gate 5 and § Gate 6, both present with exact steps and pass criteria |

**Score:** 28/28 offline-verifiable truths verified (0 present-behavior-unverified, 0 failed).
Two items (Gate 5, Gate 6) are live-only by construction and are listed under Human
Verification Required, not scored as truths — they did not exist as claims to verify in the
gap-closure plans' must-haves; they are the plans' own explicit output naming what remains.

### Prohibitions Check

Each gap-closure plan's `prohibitions:` block, checked deterministically where possible:

| Plan | Prohibition | Disposition |
|---|---|---|
| 70-08 | Executor never runs armed deploy/bounce; no arming; `n8n/` never hand-edited; working tree clean at end | VERIFIED (judgment-tier, non-authoritative): `70-ROLLBACK-DRYRUN.txt` documents only the default dry-run path; `git status --porcelain -- n8n/` is empty now; no independent record of the executor's own session exists to re-verify beyond the artifacts left behind — flagged, not a gap |
| 70-09 | No change to `build_cloud_workflows.py`, no regeneration of any `n8n/wf_*.json`; walker never adjusted just to pass a test; nothing armed live | VERIFIED (deterministic): `git log --oneline <plan-70-09-range> -- scripts/build_cloud_workflows.py` shows no commits in that plan's range touching the generator; `563940b` (RED) precedes `062154b` (fix), confirming the correction followed the observed defect, not a green target |
| 70-10 | No hand-edit of `n8n/wf_*.json` (only through the generator); walker not touched in this plan; nothing armed live; no scoring predicate change | VERIFIED (deterministic): `git log --oneline 2572c47..HEAD -- tests/n8n/lib/walkWorkflow.mjs` is empty (walker untouched since 70-09 closed); `git diff ce78a3b^..586f203 -- scripts/build_cloud_workflows.py` contains no `veto`/`anti_icp` content; `git log --oneline c3b60d3..HEAD -- src/icp_scoring.py` is empty |
| 70-11 | No hand-edit of `n8n/wf_*.json`; walker not touched; no scoring predicate change; nothing armed; no test deleted to reach green | VERIFIED (deterministic): same walker-untouched and icp_scoring-untouched checks as above cover 70-11's range too (walker log is empty across the whole 2572c47..HEAD span, which includes 70-11); `git show --stat` on every gap-closure commit shows zero `delete mode` lines under `tests/` |
| 70-12 | Executor never deploys/bounces/arms/runs the proof driver live; no second poll loop added; walker not touched; no platform fact upgraded without its execution id | VERIFIED: walker-untouched check covers this plan too; `dispatch.dispatch()`'s recovery call is unchanged (single call, `raw_rows` added as a sibling key, not a second poll — confirmed by reading the diff at line 196); every CLAUDE.md `[observed live]` row cites an execution id (Observable Truth #25) |
| all | `n8n/wf_*.json` never hand-edited — only through `build_cloud_workflows.py` | VERIFIED (deterministic, strongest form): regenerating with `.venv/bin/python scripts/build_cloud_workflows.py` and diffing against the committed tree (`git status --porcelain -- n8n/`) produces an EMPTY diff — the committed JSON is exactly what the generator produces today, which is only possible if no hand-edit ever diverged from it |

The 70-08 rollback-prep prohibitions (no live deploy/bounce by the executor) are judgment-tier —
there is no deterministic trace of what calls the executor did NOT make, only the artifacts it
left behind (a dry-run capture, a clean working tree, no evidence of an armed deploy anywhere in
git history or in `70-ROLLBACK-DRYRUN.txt`'s own narration). Recorded as non-authoritative,
flagged rather than silently passed, per the verifier's judgment-tier prohibition handling.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `tests/test_phase70_rollback_bundle.py` | Pins rollback commit + node counts | VERIFIED | 15/15 tests pass |
| `.planning/phases/.../70-ROLLBACK-RUNBOOK.md` | Self-contained operator procedure | VERIFIED | Present, content-checked (commit, filenames, flags, node counts) |
| `.planning/phases/.../70-ROLLBACK-DRYRUN.txt` | Real zero-write dry-run capture | VERIFIED | Present, shows a real live GET + DRY RUN banner |
| `tests/n8n/lib/walkWorkflow.mjs` | Corrected Merge delivery model | VERIFIED | Zero-item-delivery / first-wins / fires-once / not-run-on-empty rules present, each cites an execution id |
| `tests/n8n/walkerEngineFidelity.test.mjs` | Reproduces 12203, 12206 against frozen fixtures | VERIFIED | 2/2 pass |
| `tests/n8n/fixtures/frozen/*.2026-09-10.json` | Byte-identical frozen copies | VERIFIED | Present, referenced by walkerEngineFidelity.test.mjs, not regenerated by `build_cloud_workflows.py` |
| `.planning/phases/.../70-WALKER-RED-INVENTORY.md` | RED suite inventory with reasons | VERIFIED | Present (9.6K) |
| `scripts/build_cloud_workflows.py` | `_add_starved_lane_sentinel` gated-sentinel mechanism + `assert_merge_input_contract` | VERIFIED | Both present and correctly composed at all 8 write sites |
| `tests/n8n/mergeInputContract.test.mjs` | Structural contract, PENDING empty | VERIFIED | 18/18 pass |
| `n8n/wf_enrichment_cloud.json` (291 nodes) | Regenerated, gated sentinels, stage-split response Merge | VERIFIED | Node count = 291 (matches gap-closure spec); no Merge >10 inputs; idempotent regeneration (`git status --porcelain -- n8n/` empty after `build_cloud_workflows.py`); `enrichmentConvergenceMerge.test.mjs` proves the 2-row mixed batch reaches `Build Response` with 2 rows |
| `n8n/wf_contact_ingest_cloud.json` (69 nodes) | Regenerated, gated sentinels, carry-Merge bypass | VERIFIED | Node count = 69; exactly 3 `ALLOW_HUBSPOT_RECORD_WRITES` nodes (dynamically confirmed via in-memory `set_write_safety` invocation); `writeGateShape.test.mjs`'s armed-mixed test proves the correct per-row report |
| `n8n/wf_review_decision_cloud.json` (55 nodes) | Regenerated with IF-direct-edge retargets | VERIFIED | Node count = 55 |
| `n8n/wf_enrichment_local_live.json` (82 nodes) | Regenerated | VERIFIED | Node count = 82 |
| `scripts/prove_phase70_runtime.py` | `_ingest_recovered_rows` reads raw_rows | VERIFIED | Present, called at line ~478 |
| `operator-claude-plugin/scripts/dispatch.py` | `raw_rows` key, 2-tuple multipart parts | VERIFIED | Both present; `test_dispatch_multipart.py` pins `len(part) == 2` |
| `CLAUDE.md` §13.0.2/§13.0.3 | Updated with observed-live facts, execution ids, CONFOUNDED tag preserved | VERIFIED | Read in full; every `[observed live]` row cites an execution id; the 15-input-Merge question is explicitly tagged `[observed live, confounded]`, never upgraded to settled |
| `.planning/phases/.../70-DEFERRED-GATES.md` | Gates 5, 6 recorded with exact steps | VERIFIED | Both sections present, ordered disarmed-before-armed |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/build_cloud_workflows.py::main()` | 8 `n8n/wf_*.json` write sites | `_assert_generation_contracts` | WIRED | Every `out.write_text(json.dumps(_assert_generation_contracts(...)))` call site confirmed by direct read of `main()` (lines 11379-11428) |
| `_add_starved_lane_sentinel` condition node | gate node | direct edge, `_sentinel_gate_js()` | WIRED | `conns[name] = {"main": [[{"node": gate_name, ...}]]}` — condition's ONLY edge is to its own gate, never to `targets` directly |
| gate node | `targets` (Merge inputs) | direct edges | WIRED | `conns[gate_name] = {"main": [[{"node": t, ...} for (t, i) in targets]]}` |
| `operator-claude-plugin/scripts/dispatch.py::dispatch()` | `scripts/prove_phase70_runtime.py::_ingest_recovered_rows` | `raw_rows` dict key | WIRED | `dispatch.py` line 196 sets `"raw_rows": recovered_rows`; `prove_phase70_runtime.py` line 335 reads `dispatch_result.get("raw_rows")` |
| `tests/n8n/walkerEngineFidelity.test.mjs` | `tests/n8n/fixtures/frozen/*.json` | `FROZEN` path const | WIRED | Line 31: `const FROZEN = path.join(HERE, "fixtures", "frozen")`; confirmed the test reads the frozen copies, not the live-regenerated graph |
| `n8n_arming.set_write_safety` | `wf_contact_ingest_cloud.json`'s 3 declaring nodes | `ALLOW_HUBSPOT_RECORD_WRITES` regex match, generic over all nodes | WIRED | Confirmed both structurally (exactly 3 nodes carry the declaration) AND dynamically (in-memory invocation of `set_write_safety` against the loaded regenerated JSON returned rewrite count 3 for both `ALLOW_HUBSPOT_RECORD_WRITES` and `TEST_RECORD_IDS`) |
| `tests/n8n/writeGateShape.test.mjs` armed-mixed test | committed `n8n/wf_contact_ingest_cloud.json` | `loadWf(...)` + `walkWorkflow(...)` over the file on disk | WIRED | Confirmed by reading the test: it `loadWf(path.join(ROOT, "n8n", "wf_contact_ingest_cloud.json"))`, the same file `build_cloud_workflows.py` writes — not a frozen fixture, not an in-memory literal |
| `tests/n8n/enrichmentConvergenceMerge.test.mjs` | committed `n8n/wf_enrichment_cloud.json` | `loadWorkflow(WF_PATH)` | WIRED | Confirmed by reading the test's top-of-file `const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json")` |

### Requirements Coverage

No requirement IDs map to Phase 70 (`.planning/REQUIREMENTS.md` has zero `Phase 70` references;
`.planning/ROADMAP.md`'s Phase 70 entry notes "added 2026-09-09 from the first live batch UAT"
with `**Requirements:** TBD` and no roadmap `success_criteria` list beyond the prose Goal). The
phase's contract is decisions D-70-01..23 in `70-CONTEXT.md`, tracked instead via each
gap-closure plan's `requirements-completed` frontmatter (`[D-70-20, D-70-19, D-70-18]`,
`[D-70-20, D-70-19, D-70-01, D-70-14, D-70-15]`, `[D-70-20, D-70-19, D-70-01, D-70-14]`,
`[D-70-22, D-70-19, D-70-02, D-70-21]` across 70-09/70-10/70-11/70-12) — no orphaned requirement
IDs to report.

### Anti-Patterns Found

None. Scanned `scripts/build_cloud_workflows.py`, `scripts/prove_phase70_runtime.py`,
`operator-claude-plugin/scripts/dispatch.py`, `tests/n8n/lib/walkWorkflow.mjs`,
`tests/n8n/mergeInputContract.test.mjs`, `tests/n8n/walkerEngineFidelity.test.mjs`, `CLAUDE.md`
for `TBD|FIXME|XXX` — zero matches. `TODO|HACK|PLACEHOLDER` matches in
`build_cloud_workflows.py` are all pre-existing narrative comments describing already-documented
placeholder patterns from earlier phases (e.g. BUG 11, the `domain` producer-less open todo),
none introduced by 70-08..70-12, none touching this round's gap-closure code paths. No test file
was deleted by any 70-08..70-12 commit (`git show --stat` on each shows zero `delete mode` lines
under `tests/`).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full node suite green | `node --test tests/n8n/*.test.mjs` | 1064 pass, 0 fail | PASS |
| Full root Python suite green | `.venv/bin/python -m pytest -q --tb=short` | 4690 passed, 154 skipped | PASS |
| Full plugin Python suite green | `cd operator-claude-plugin && ../.venv/bin/python -m pytest -q` | 2865 passed, 5 skipped | PASS |
| Graph regeneration is idempotent | `.venv/bin/python scripts/build_cloud_workflows.py && git status --porcelain -- n8n/` | empty diff | PASS |
| Node counts match gap-closure spec | direct `require(...).nodes.length` per file | 291/69/55/43/30/82/10/13 | PASS |
| No Merge exceeds 10 inputs | scan all `n8n/wf_*.json` for `numberInputs > 10` | zero matches | PASS |
| Merge-input structural contract | `node --test tests/n8n/mergeInputContract.test.mjs` | 18 pass, PENDING list empty | PASS |
| Walker reproduces 12203/12206 against frozen fixtures | `node --test tests/n8n/walkerEngineFidelity.test.mjs` | 2 pass | PASS |
| G-70-4 comparator fix proven RED-then-GREEN | `.venv/bin/python -m pytest tests/test_prove_phase70_runtime.py -q` | 19 passed | PASS |
| Rollback bundle pinned | `.venv/bin/python -m pytest tests/test_phase70_rollback_bundle.py -q` | 15 passed | PASS |
| RED-first discipline for the walker fix | `git log --oneline` | `563940b test(70-09): RED — reproduce execution 12203` precedes `062154b feat(70-09): correct the walker` | PASS |
| Exactly 3 nodes declare `ALLOW_HUBSPOT_RECORD_WRITES` on the ingest lane | direct JSON read of `n8n/wf_contact_ingest_cloud.json` | `HubSpot Update Write Gate`, `HubSpot Create Write Gate`, `Associate Lane Sentinel` | PASS |
| `set_write_safety` dynamically rewrites all 3 declaring nodes | in-memory invocation against the loaded regenerated JSON | `{'ALLOW_HUBSPOT_RECORD_WRITES': 3, 'TEST_RECORD_IDS': 3}` | PASS |
| Armed-mixed ingest acceptance test asserts the correct per-row fields | `node --test tests/n8n/writeGateShape.test.mjs` | passes, `association: "associated"` / `action: "write_blocked"` asserted against the committed graph | PASS |
| Enrichment lane 2-row batch reaches Build Response with 2 rows | `node --test tests/n8n/enrichmentConvergenceMerge.test.mjs` | 12/12 pass, including the exactly-2-rows assertion against the committed graph | PASS |
| Walker untouched since RED-first fix landed (70-09 through 70-12) | `git log --oneline 2572c47..HEAD -- tests/n8n/lib/walkWorkflow.mjs` | empty | PASS |
| No scoring predicate touched by 70-10/70-11's generator diffs | `git diff ce78a3b^..586f203 -- scripts/build_cloud_workflows.py` grepped for veto/anti_icp; `git log c3b60d3..HEAD -- src/icp_scoring.py` | zero matches; empty log | PASS |

### Probe Execution

Not applicable — Phase 70's live probes are the deferred human-gate steps (Gates 4/5/6) in
`70-DEFERRED-GATES.md`, not `scripts/*/tests/probe-*.sh` shell probes. No such probe files exist
for this phase.

### Human Verification Required

See frontmatter `human_verification:` for the full test/expected/why_human shape. Summary:

1. **Standing operational decision (live now, not a future gate):** the deployed n8n instance
   still runs the pre-gap-closure Phase 70 JSON, which has the G-70-2/G-70-3 defect — every
   enrichment request against it silently returns 0 rows right now. The operator must run
   either Gate 4 (roll back to `59812be`) or Gate 5 (redeploy the fixed JSON) to close this.
2. **Gate 5** — disarmed redeploy of the gap-closure JSON + re-run of the D-70-19 proof driver.
3. **Gate 6** — first armed mixed-verdict batch against the fixed graph, gated behind Gate 5.

Both gates are fully specified with exact steps and pass criteria in `70-DEFERRED-GATES.md`.

### Gaps Summary

No gaps found in this offline gap-closure verification round. All four UAT-discovered gaps
(G-70-1 through G-70-4) have durable, evidence-backed fixes in the committed codebase, each
proven RED-before-fix where the plan called for it, and the full offline harness (node 1064/1064,
root Python 4690 passed, plugin Python 2865 passed, idempotent graph regeneration) is green.
Every gap-closure plan's structural/deterministic prohibitions were independently checked (see
Prohibitions Check above) and hold. The phase cannot be marked `passed` yet because its own
thesis — "the walker is a faithful model of the live engine" — was falsified once already
(G-70-2/G-70-3) and the fix has not yet been observed live against the regenerated graph, and
because the live instance is currently running the defective JSON with no operator action taken
yet. `70-DEFERRED-GATES.md` § Gate 5 and § Gate 6 are the two remaining live proofs; per the
phase's own standing discipline (do not adjust the walker to match and call it passed; a mismatch
is a finding, not a prompt to relax the comparator), those two gates must run and pass before
this phase can honestly close as `passed`.

---

_Verified: 2026-09-10T06:23:26Z_
_Verifier: Claude (gsd-verifier)_
