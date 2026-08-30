---
phase: 61-autonomous-batch-runs
plan: "05"
subsystem: infra
tags: [n8n, async-execution, run-state, hubspot-plugin, resume-idempotency]

# Dependency graph
requires:
  - phase: 61-autonomous-batch-runs
    provides: "61-01's spike verdict + operator substrate decision; 61-04's held_queue/run_manifest sixth verdict word"
provides:
  - "run_state.py: client-side run scope + progress tracking over run_manifest.py's per-row verdicts, substrate-1 async-ack shape"
  - "watch.py: resume-or-fail-loudly bounded polling, the sole entry in _POLL_LOOP_ALLOWED"
  - "chunking.py: per-chunk manifest merge (load-merge-save) bounding replay exposure to one chunk"
  - "build_cloud_workflows.py: Build Async Ack node + async_ack opt-in fan, deployed and live-verified"
affects: [61-06]

actuals:
  tokens: 17550
  tasks: 4
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Substrate 1 (Respond node moved to front of chain, async_ack opt-in boolean) chosen over substrate 3 (self-referencing Execute Workflow) at this plan's scale — deliberate, disclosed departure from 61-01's 'strongest candidate' framing, recorded in run_state.py's module docstring"
    - "run_state.py reports OVER run_manifest.py rather than duplicating its verdict store — a fifth persisted artifact holding scope only, no verdicts"
    - "Per-chunk manifest persistence is load-accumulated-document, merge this chunk's verdicts, save whole document — save() itself stays whole-document-semantics, unchanged"

key-files:
  created:
    - operator-claude-plugin/scripts/run_state.py
    - operator-claude-plugin/tests/test_run_state.py
    - operator-claude-plugin/tests/test_resume_or_fail_loudly.py
    - tests/n8n/asyncAck.test.mjs
  modified:
    - operator-claude-plugin/scripts/watch.py
    - operator-claude-plugin/scripts/chunking.py
    - scripts/build_cloud_workflows.py
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md
    - n8n/wf_enrichment_cloud.json

key-decisions:
  - "Substrate 1 selected over substrate 3 for THIS plan's scale (P-11 already showed both 40- and 300-record batches fit the 2,500/month budget under either cost reading, so substrate 3's unmetered/uncapped advantage is not load-bearing here); substrate 3 stays the disclosed scale-up path for 61-06, now further de-risked by P-14 (self-reference publish-viable, runtime unproven)."
  - "REVIEW-C14 resolution: run_id minted client-side before submit, passed into dispatch_plan's existing caller-suppliable run_id keyword — no new handle invented, no signature change."
  - "REVIEW-C15/REVIEW-08 resolution: two consumers, two rules over one run_manifest.load() — the resume path keeps degrade-whole unchanged (money-versus-contact rationale intact); the report path classifies the file (absent/parseable/anomalous/wrong-run) and discloses which, in words, rather than presenting a rerun as a first run or as complete."
  - "REVIEW-C13 resolution: per-chunk persistence is load-merge-save over the accumulated manifest document, not a chunk-only save — run_manifest.save() itself keeps whole-document semantics; the merge belongs to the caller."
  - "Deploy scope for Task 4 exceeded 61-05 alone: the live n8n instance was four plans behind (61-02, 61-03, 61-04 also undeployed), so the operator was shown the true scope and authorized deploying all five cloud workflows in one pass rather than an artificially narrow 61-05-only deploy."

requirements-completed: [RUN-01, RUN-03, RUN-04]

coverage:
  - id: D1
    description: "Premises re-asserted against 61-SPIKE-VERDICT.md; plan halts on a contradicted dependent premise instead of improvising a substitute substrate"
    requirement: RUN-01
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_state.py -k premises"
        status: pass
    human_judgment: false
  - id: D2
    description: "run_state.py: one run submitted and one progress read end-to-end offline, run_id minted before submit, total = pending+running+done+held+failed invariant asserted, unreadable state reads as unreadable not zero"
    requirement: RUN-04
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_run_state.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "Resume path resumes without redoing completed rows; unreadable/inconsistent state reruns in full with loud disclosure sentence; per-chunk manifest merge bounds replay exposure to one chunk; poll loop confined to watch.py"
    requirement: RUN-03
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_resume_or_fail_loudly.py, test_report_sufficiency.py, test_run_manifest.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "Deploy, bounce, and observe one bounded async run live on the operator-selected substrate — the checkpoint's own bounds (return-only, no creates, empty provider list, one chunk, nothing armed beyond the send) held, and the execution count was compared against 61-01's projection"
    verification: []
    human_judgment: true
    rationale: "Live deploy/bounce/run performed by the orchestrator under explicit operator authorization outside this executor's session; this executor only records the observations. The respond-before-finish property was NOT demonstrated by this run (client round-trip 2.28s exceeded execution span 1.911s) — that gap is a genuine unresolved observation a human should see, not something this plan can auto-close by citing P-07 in its place."

duration: ~35min (Tasks 1-3, prior session) + recording pass (this session)
completed: 2026-08-30
status: complete
---

# Phase 61 Plan 05: Async Run Handle, Mid-Flight Progress, and Resume-or-Disclose Summary

**`run_state.py` (substrate-1 async-ack shape) reports live progress over `run_manifest.py`'s per-row verdicts; `chunking.py`/`watch.py` gained per-chunk manifest merge and a four-sentence resume-or-disclose report; deployed to all five cloud workflows and proven live with one bounded, disarmed, zero-spend run (execution `12040`).**

## Performance

- **Tasks:** 4/4 complete (Tasks 1-3 code + tests, Task 4 human-verify checkpoint)
- **Files modified:** 12 (see key-files)
- **Commits:** 5 (4 task commits + this plan-metadata commit)

## Accomplishments

- **Task 1** — Read `61-SPIKE-VERDICT.md`'s `## Premises` block mechanically off its DEPENDENTS field, selecting only premises naming `61-05`, and wrote a test that fails the suite if any of those premises is later retracted. No premise this plan depends on was found unresolved; the operator's run-state decision (HubSpot object + `run_manifest.py`) was present and named. Nothing was substituted.
- **Task 2** — `run_state.py` shipped as the plugin's fifth persisted artifact — holding run SCOPE only (`total_row_ids`, `dispatched_row_ids`), never verdicts, reporting OVER `run_manifest.load_scoped()`. `run_id` is minted client-side before the submit call and passed into `dispatch_plan`'s existing `run_id` keyword (REVIEW-C14), closing the exact gap that would have reproduced the synchronous wait this plan exists to remove. The five-bucket invariant (`total = pending+running+done+held+failed`) is asserted inside the module itself and again in the test suite. An unreadable state reports every count as `None`, never `0`. The corresponding n8n-side change — an opt-in `async_ack` boolean fanning `Parse HubSpot Event`'s output to an immediate `Build Async Ack` response alongside the unchanged chain — was built into `scripts/build_cloud_workflows.py` only; `n8n/wf_enrichment_cloud.json` was regenerated, never hand-edited.
- **Task 3** — Resolved REVIEW-08/C15's apparent resume-vs-fail-loudly contradiction as two consumers over one `run_manifest.load()`: the resume path keeps its existing degrade-whole behavior (a raise would strand a batch on one corrupt byte), while the report path independently classifies the manifest file (absent / parseable / anomalous / another-run's) and says which, in words — "previous state unreadable — rerunning all N rows, nothing was skipped" — never presenting a rerun as a first run or as complete. Fixed REVIEW-C13's read of "write verdicts per chunk": because `run_manifest.save()` writes its argument as the *complete* document rather than merging, per-chunk persistence is now load-the-accumulated-document → merge this chunk's verdicts → save the whole thing, bounding a crash's replay exposure to exactly one chunk (asserted by a test that crashes between two chunks and reads back the first chunk's verdicts intact). No new poll loop was added outside `watch.py`, so `_POLL_LOOP_ALLOWED` needed no widening. `plugin.json` was bumped and `CHANGELOG.md` updated in this task's own commit.
- **Task 4 (this session, recording only)** — See below. Deployed, bounced, and proven live under explicit operator authorization performed by the orchestrator; this executor recorded the observations and did not re-run anything.

## Task 4: Deploy, Bounce, and Observe One Async Run

Performed by the orchestrator on 2026-08-30 under explicit operator authorization. All facts below are observed, not re-derived or re-run by this executor.

**Deploy scope was larger than 61-05 alone.** The live n8n instance was four plans behind, so the operator was shown the true scope and chose to deploy all five cloud workflows via `scripts/deploy_n8n_workflows.py` (`DRY_RUN=false ALLOW_N8N_DEPLOY=true`, no arming flags, no allowlist):

| Workflow | Change deployed | Origin |
| --- | --- | --- |
| LV Enrichment (Cloud template) | +4 nodes (114 → 118), 42 nodes' parameters changed | 61-02, 61-04, 61-05 |
| LV Contact Ingest (Cloud template) | 1 node changed (`Map Columns`) | 61-03 |
| LV Scheduled Maintenance (Cloud) | 1 node (`Apply Review` taxonomy jsCode) | **pre-existing live drift, NOT phase 61 work** — `git log` shows no phase-61 commit touched that file |
| LV Backend Status (Cloud template) | none — no-op | — |
| LV Review Decision (Cloud) | none — no-op | — |

All five returned HTTP 200. Post-deploy independent re-read confirmed residual parameter diff 0 for four of five; Scheduled Maintenance's residual 1 is the `LVenrichmentCloud01` → `950HPb7a1GgSAIyZ` executeWorkflow placeholder the deploy script deliberately resolves via `cachedResultName` — correct behaviour, not drift.

**Bounce.** `950HPb7a1GgSAIyZ` deactivate (200) then activate (200) — a stored PUT does not reload a running workflow on this instance. Post-bounce read confirmed `active=true`, 118 nodes, and all four new nodes present by name: `Build Async Ack`, `Adapt Linkedin Search`, `HubSpot Linkedin Search`, `IF Linkedin Searchable`.

**One bounded run, disarmed, proven so by which nodes ran.** Request: `POST /webhook/hubspot/enrichment/event`, authenticated with the plugin's own `X-Enrichment-Secret`, envelope `{"providers": [], "mode": "propose", "async_ack": true, "events": [{"object_type": "contacts", "mode": "propose", "row": {"linkedin_url": ".../probe-6105-synthetic/"}}]}` — a synthetic non-real LinkedIn URL. `mode: "propose"` is the structural write guard (`isReturnOnly`); `providers: []` spends zero credit; one row = one chunk; nothing armed.

- HTTP 200, client round-trip **2.28s**.
- Response body `[{"run_id": null, "accepted": true, "row_id": null}]` — the async-ack shape; `Build Async Ack` fired and answered. `run_id` is `null` because the caller passed none; the node echoes the caller's handle rather than minting one.
- Execution `12040`, status `success`, span **1.911s** (07:07:28.526Z → 07:07:30.437Z).
- **Execution count: 1 new execution.** 61-01's `chunk_count + record_count` formula projects **2** for one chunk of one record. Observed **1** — this independently reproduces P-10's already-measured finding that the formula over-states cost, rather than being new evidence beyond P-10.
- **Disarmament proven by runData, not asserted:** 20 nodes ran (`Webhook Trigger`, `IF List Input`, `Parse HubSpot Event`, `IF Object Type Supported`, `Credit Request`, `Build Async Ack`, `Route By Object Type`, three `IF <provider> Credit Requested` gates, `Respond to Webhook`, `Build Identity`, `IF Bare Event`, `IF Has Email`, `IF Linkedin Searchable`, `IF Name Searchable`, `Enrichment Gate`, `IF Provider Processing Needed`, `Skip (NoOp)`, `Build Response`). No create/update/patch/associate node ran. No provider HTTP node ran (the three provider-named nodes that ran are IF gates, not calls). No Anthropic/judge/research node ran. The row terminated at `Skip (NoOp)`.
- `IF Linkedin Searchable` (61-02) ran live — that lane is deployed and exercised, not just built.

**Honest limit, recorded rather than overstated: this run did NOT demonstrate respond-before-finish.** Client round-trip (2.28s) exceeded the execution span (1.911s), so the run was too short to separate the two. Respond-then-continue was already proven independently and live by **P-07** (execution `12035`: 0.47s round-trip against a 5s wait, post-Respond `Set` node recorded `success`). Cite P-07 for that property — run `12040` does not independently demonstrate it, and this summary does not claim it does.

### Substrate-3 note carried forward to 61-06 (updated with P-14)

61-01 named substrate 3 (self-referencing `Execute Workflow`, wait-for-completion off) as unmetered, uncapped, and — per the three live probes recorded in `61-PREMISE-DOCS-FINDINGS.md` — **observable** (P-13: a detached child's execution id is recoverable from the parent's runData with `waitForSubWorkflow` off and on alike). Substrate 1 was chosen for 61-05 because P-11 already showed both a 40- and a 300-record batch fit the 2,500/month budget under either cost reading, so substrate 3's unmetered advantage was not load-bearing at this plan's scale, and substrate 3 realized in full is a materially larger, riskier build (either an unprobed self-referencing node inside `wf_enrichment_cloud.json`, or a brand-new parent workflow that would move the plugin's dispatch target).

**P-14 (added 2026-08-30, operator-requested) narrows that risk for 61-06 without spending on it:** a self-referencing `Execute Workflow` node activated successfully (workflow `h2Sn4WGTNfmr4vLj`, no publish-order error) at zero execution cost. This establishes the self-reference route is **publish-viable but runtime-unproven** — activation only, the webhook was never fired, and the probe's depth guard was never exercised. Runtime behaviour of a self-referencing dispatch (whether it runs correctly, terminates, or how it is metered) remains deliberately unprobed, because an unbounded self-dispatch on a live 2,500/month instance is not a risk worth taking to learn something activation already answered. 61-06, if it needs to scale beyond substrate 1's arithmetic, inherits this as its starting point rather than an open question.

## Task Commits

1. **Task 1: Assert premises against spike verdict, or halt** — `0db7bdd` (test)
2. **Task 2: One run submitted and one progress read (tracer)** — `a3458f4` (feat)
3. **Task 3 RED: failing tests for per-chunk merge and resume-or-disclose** — `bbee82d` (test)
4. **Task 3 GREEN: per-chunk manifest merge and resume-or-fail-loudly** — `22c0258` (feat)

**Plan metadata:** this commit (docs: complete plan)

_Task 4 is a human-verify checkpoint (deploy/bounce/live run) and carries no code commit of its own — the deploy artifact is the regenerated `n8n/wf_enrichment_cloud.json` already committed in Tasks 2-3, plus the live n8n instance state itself, which this plugin does not version._

## Files Created/Modified

- `operator-claude-plugin/scripts/run_state.py` — fifth persisted artifact: run scope (`total_row_ids`/`dispatched_row_ids`) + progress read over `run_manifest.py`'s verdicts; three-way `NOT_STARTED`/`OK`/`UNREADABLE` state
- `operator-claude-plugin/scripts/watch.py` — bounded backoff polling extended for resume-or-disclose; remains the sole `_POLL_LOOP_ALLOWED` entry
- `operator-claude-plugin/scripts/chunking.py` — per-chunk manifest persistence: load-accumulated-document → merge chunk verdicts → save whole document
- `scripts/build_cloud_workflows.py` — `ENRICH_PARSE_EVENT_CLOUD` + `Build Async Ack` node, the `async_ack` opt-in fan
- `n8n/wf_enrichment_cloud.json` — regenerated (never hand-edited), deployed and bounced live
- `operator-claude-plugin/tests/test_run_state.py` — premise-assertion test + run-state unit tests, offline/injected-transport only
- `operator-claude-plugin/tests/test_resume_or_fail_loudly.py` — resume/disclosure/per-chunk-merge coverage, all four report sentences (absent/parseable/anomalous/wrong-run)
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md`, `.claude-plugin/plugin.json`, `CHANGELOG.md` — version bump and skill doc updates
- `tests/n8n/asyncAck.test.mjs` — node-side coverage for the new `Build Async Ack` node

## Decisions Made

See `key-decisions` in frontmatter. Summarized: substrate 1 over substrate 3 at this scale (with substrate 3 de-risked-but-unproven for 61-06 via P-14); `run_id` minted client-side before submit (REVIEW-C14); resume keeps degrade-whole while the report classifies-and-discloses (REVIEW-C15/08); per-chunk persistence is load-merge-save, not a chunk-only overwrite (REVIEW-C13); the Task 4 deploy scope was widened to all five workflows with the operator's informed consent because the live instance was already four plans behind.

## Deviations from Plan

**None in Tasks 1-3** — plan executed as written, all review dispositions incorporated as specified in `<review_dispositions>`.

**Task 4 scope widening (disclosed, not an auto-fix under Rules 1-3):** the deploy touched four undeployed plans' worth of change (61-02, 61-03, 61-04, 61-05) rather than 61-05 alone, because the live instance had drifted behind by that much. This was not silently expanded — the operator was shown the true diff scope before authorizing, and the Scheduled Maintenance workflow's single changed node was independently confirmed to be pre-existing drift unrelated to any phase-61 commit.

## Issues Encountered

None during Tasks 1-3. Task 4's one honest gap: the live checkpoint run did not itself demonstrate respond-before-finish (round-trip exceeded execution span) — resolved by citing P-07's independent live proof rather than overstating what run `12040` showed.

## Verification Against Plan's `<verification>` Block

- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — not run in isolation this session; full-suite run below supersedes it.
- `.venv/bin/python -m pytest -q` — **3518 passed, 154 skipped** (matches/exceeds the plan's stated baseline of 3365/154; the delta reflects tests added since baseline was recorded, including this plan's own).
- `node --test tests/n8n/*.test.mjs` (glob form) — **825/825 passed.**
- Poll-loop guard: passed unchanged; no allowlist widening was needed.
- Zero live n8n/HubSpot/Anthropic/provider calls before the checkpoint: true for this executor's own work (Tasks 1-3 were fully offline/injected-transport). At the checkpoint, exactly the bounded run Task 4 specifies was performed (return-only mode, empty provider list, one chunk, no creates, nothing armed beyond that single send) — all five bounds held, confirmed by the runData trace above.

**Every `<verification>` item that could be honestly ticked from the evidence is ticked above.** Nothing was marked passing without a cited basis.

## Next Phase Readiness

61-06 inherits: substrate 1 live and deployed as the default async shape; a resume-or-disclose report path proven by unit test (not yet exercised by an interrupted live run); and, for its own scale-up decision, P-14's narrowed-but-still-open substrate-3 self-reference finding (publish-viable, runtime-unproven) as the documented starting point rather than an open question. 61-06 stays gated on Phase 57's ceilings per D-61-08 — this plan's Task 4 run was explicitly a plumbing observation, not the first unattended batch run.

---
*Phase: 61-autonomous-batch-runs*
*Completed: 2026-08-30*

## Self-Check: PASSED

- FOUND: `.planning/phases/61-autonomous-batch-runs/61-05-SUMMARY.md`
- FOUND: `0db7bdd` (Task 1)
- FOUND: `a3458f4` (Task 2)
- FOUND: `bbee82d` (Task 3 RED)
- FOUND: `22c0258` (Task 3 GREEN)
