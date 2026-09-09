---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 03
subsystem: n8n-workflow-generation
tags: [n8n, merge-node, enrichment-lane, review-decision-lane, sentinel-pattern, offline-walker, ack-only-webhook]
status: complete
requires:
  - phase: 70-02
    provides: splice_merge_before / splice_carry_merge_after / merge_node / ack-only ingest webhook / lane-aware recover_dispatch
provides:
  - enrichment-lane-convergence-merges (D-70-01, Task 1)
  - ack-only-enrichment-webhook (D-70-07, Task 2)
  - review-decision-lane-convergence-merges (D-70-01/D-70-08, Task 3)
affects:
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_enrichment_local_live.json
  - n8n/wf_enrichment_local.json
  - n8n/wf_review_decision_cloud.json
  - operator-claude-plugin/scripts/chunking.py
  - operator-claude-plugin/scripts/written_records.py
  - phases 70-04..70-07 (next-wave work on the same lanes)

actuals:
  tokens: 768579
  tasks: 3
  commits: 5
  plan_head_before: 5fa9d4b

tech-stack:
  added: []
  patterns:
    - starved-lane sentinel (landed 70-02/Task 1; extended this plan) — an additional
      fan-out edge from a single-producer upstream node feeding a narrow Code node that
      decides whether real content will ever reach a specific Merge input this
      execution, delivering a `{}` marker DIRECTLY to that input when not — never
      through the business/IF/HTTP/write chain it starves around
    - first-line identity-drop filter on converged Code nodes
      (`Object.keys(it.json || {}).length > 0`) so a sentinel marker is never processed
      as a real row
    - ack-only webhook responder — a single, unconditional producer node
      ("Build Ack") is the SOLE feeder of `Respond to Webhook`; every refusal/status
      reason that used to race it into the response body is normalized by a shared
      "Build Refusal Row" node and routed into the Merge instead, reaching the caller
      as a runData row, never the synchronous body

key-files:
  created:
    - tests/n8n/enrichmentConvergenceMerge.test.mjs
    - tests/n8n/reviewConvergenceMerge.test.mjs
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_review_decision_cloud.json
    - operator-claude-plugin/scripts/chunking.py
    - operator-claude-plugin/scripts/written_records.py
    - tests/n8n/asyncAck.test.mjs
    - tests/n8n/enrichmentBatchRefusal.test.mjs
    - tests/n8n/scaleUpFanOutFlow.test.mjs
    - tests/n8n/reviewDecisionEndpoint.test.mjs
    - tests/n8n/lib/walkWorkflow.mjs
    - tests/test_merge_helpers.py
    - tests/test_enrichment_list_branch.py
    - tests/test_remaining_credits_response.py
    - tests/test_fetch_by_id_topology.py
    - tests/test_cloud_companies_branch.py
    - tests/test_cloud_contacts_branch.py
    - tests/test_enrichment_lane_dedup.py
    - tests/fixtures/companies_jscode_frozen.json
    - operator-claude-plugin/tests/test_chunking.py
    - operator-claude-plugin/tests/test_run_state.py
    - operator-claude-plugin/tests/test_scale_up_runtime.py
    - operator-claude-plugin/tests/test_scheduled_arm.py
    - operator-claude-plugin/tests/test_write_grant.py
    - operator-claude-plugin/tests/test_written_records.py
    - tests/n8n/companyNameFallbackFlow.test.mjs
    - tests/n8n/companyRecomputeLaneFlow.test.mjs
    - tests/n8n/linkedinLaneFlow.test.mjs
    - tests/n8n/researchErrorGateFlow.test.mjs

decisions:
  - "Task 2 — the two refusal shapes that ALREADY reached Build Response as rows before
    this task (`Unsupported Object Type`, `recompute_refused` via IF Company Enrich's
    false lane) are left on their existing Task-1 wiring, untouched. They become
    row-only automatically the instant Build Response stops feeding the responder — no
    routing change needed, only the two genuinely body-only paths (list-expansion
    refusal, scale-up dispatch confirmation) needed the new Build Refusal Row node."
  - "Task 2 — 'Build Refusal Row' feeds Build Response Merge via a NEW eleventh input
    (`_append_merge_input`), never straight into Build Response directly. A direct
    edge would re-create a genuine multi-inbound-edge risk at the exact node Task 1
    converged; routing through the Merge with a dedicated 'Refusal Fired Sentinel'
    (fed FROM Build Refusal Row, feeding all ten OTHER inputs whenever it delivers
    anything) keeps Build Response's own inbound edge count at exactly one."
  - "Task 2 — chunking.dispatch_plan's own written_records.append_chunk flush is
    deleted whole, not merely guarded further: since Build Ack is now the workflow's
    ONLY responder input, this function's own `body` is ALWAYS the ack shape for
    EVERY call, never a real per-row outcome — the same bogus-entry failure mode F4
    already proved live for the (retired) async_ack case is now universal. Recorded as
    a deliberate, deferred gap: run_report.py's end-of-run report still reads
    written_records.load() for entries this function used to write; migrating IT to
    runData is D-70-08's scope, not this plan's."
  - "Task 3 — the plan's own action text ('set alwaysOutputData: true ... inserting a
    NoOp terminal where the terminal is an IF output') was NOT implemented literally.
    Verified via the offline walker that alwaysOutputData is checked on the SOURCE of
    a possibly-empty output, and every one of this lane's IF-fed branches (Review IF
    Contacts, Review Queue IF Contacts, Review IF Dry Run) feeds a real HTTP
    search/fetch/write node directly — setting the flag there would leak a marker
    item into a live HubSpot call (in Review IF Dry Run's case, into the WRITE
    branch's PATCH node with no real properties, exactly the T-70-04 leak class this
    plan's threat register exists to prevent). Used the PROVEN starved-lane-sentinel
    pattern instead, sourced from a single-producer node upstream of each split
    (Parse Review Decision / Parse Review Queue Request / Build Review Decision),
    delivering markers DIRECTLY to the Merge input, bypassing the routing/HTTP/write
    chain entirely — the identical mechanism Task 1/2 already use and this repo's own
    tests already prove safe."
  - "Task 3 — 'Build Review Decision' gained an additive `object_type` field. Its own
    `row` output (the refetched HubSpot record) never carries one — HubSpot records
    have no such property — so the Build-Review-Response sentinels had no
    single-producer source that carried BOTH the computed dry_run routing boolean AND
    the object_type needed to pick between the two verify-fetch inputs. Additive,
    verified not to break any test pinning that node's output shape."
  - "Task 3 — 'Review Extract Record'/'Review Queue Rows'/'Build Review Response' were
    rewritten from `$input.first()` to `$input.all()` with the identity-drop filter.
    A Rule-1 bug was found and fixed by the new reviewConvergenceMerge.test.mjs: the
    OLD `$input.first()` could silently grab a starved-lane marker instead of the real
    verify-fetch envelope depending on merge input index/splice order, permanently
    resolving `verified_properties`/`verified` to null for a write that had actually
    succeeded — confirmed by reverting the fix in isolation and observing exactly that
    regression."

patterns-established:
  - "Merge inputs discovered AFTER a merge was already sized ('_append_merge_input')
    get a NEW input index via a bumped `numberInputs`, wired the same way
    `splice_merge_before`'s own collected edges are, rather than forcing a second
    splice pass or a hand-invented index."
  - "A convergence whose upstream split is a routing IF feeding real HTTP/write nodes
    directly gets its starved-lane coverage from a node UPSTREAM of the split (a
    single always-running producer reading the SAME field the IF tests), never from
    `alwaysOutputData` on the IF itself or on the downstream real node — both of which
    either do nothing (a node that received zero input is never dispatched, so its own
    alwaysOutputData flag is never consulted) or actively leak a marker into a live
    call (the IF case)."

requirements-completed: [D-70-01, D-70-02, D-70-07, D-70-08]

coverage:
  - id: D-70-01
    description: "Every fan_in convergence classify_convergence identifies (over the REAL built graph, not the research inventory) sits behind a real n8n Merge whose inputs are all guaranteed to fire — 6 in the enrichment lane (Task 1) plus 3 more in the review-decision lane (Task 3, this plan's own new convergences: Review Extract Record, Review Queue Rows, Build Review Response). Entry-point convergences (Parse HubSpot Event) and class-(b) mutually-exclusive bypass chains (the 9 provider-gate pairs) correctly get none."
    verification:
      - kind: unit
        ref: "tests/n8n/enrichmentConvergenceMerge.test.mjs (11 tests)"
        status: pass
      - kind: unit
        ref: "tests/n8n/reviewConvergenceMerge.test.mjs (10 tests)"
        status: pass
      - kind: unit
        ref: "tests/test_merge_helpers.py"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs (1005/1005)"
        status: pass
    human_judgment: false
  - id: D-70-02
    description: "settings.executionOrder is not set on any of the five committed workflows — no flip in this phase, verified against the REAL built artifacts, not just left alone by omission."
    verification:
      - kind: unit
        ref: ".venv/bin/python -c \"import json;print([json.load(open(p)).get('settings',{}).get('executionOrder') for p in [...]])\" -> [None, None, None, None, None]"
        status: pass
    human_judgment: false
  - id: D-70-07
    description: "The enrichment webhook's responder (Respond to Webhook) has exactly one inbound edge (Build Ack) and answers unconditionally with {run_id, accepted, row_ids} for every request; the retired async_ack flag is absent from both the built workflow JSON and chunking.py; all four body-borne refusal/status reasons (unsupported object type, recompute_refused, list-expansion refusal, scale-up dispatch confirmation) reach Build Response as rows on the sole channel."
    verification:
      - kind: unit
        ref: "tests/n8n/asyncAck.test.mjs (13 tests, rewritten against the new contract)"
        status: pass
      - kind: unit
        ref: "tests/n8n/enrichmentBatchRefusal.test.mjs (17 tests, 4 new walker-driven refusal cases)"
        status: pass
      - kind: unit
        ref: "tests/n8n/scaleUpFanOutFlow.test.mjs (pins updated for the new wiring)"
        status: pass
      - kind: integration
        ref: ".venv/bin/python -m pytest operator-claude-plugin/tests/ -q (2849 passed, 5 skipped)"
        status: pass
      - kind: other
        ref: "grep -c async_ack in n8n/wf_enrichment_cloud.json and operator-claude-plugin/scripts/chunking.py -> 0 in both"
        status: pass
    human_judgment: false
  - id: D-70-08
    description: "hubspot/review/queue, hubspot/review/decision and hubspot/backend-status remain body-responding queries, unaffected by the ack-only change scoped to the enrichment/ingest lanes; wf_backend_status_cloud.json needed zero changes (confirmed 0 Merge nodes, 0 multi-inbound convergences)."
    verification:
      - kind: unit
        ref: "tests/n8n/reviewConvergenceMerge.test.mjs::\"the review responder's inbound edge count is unchanged...\" and \"...byte-shape-identical to the pre-merge contract\" (both)"
        status: pass
      - kind: unit
        ref: "tests/n8n/reviewDecisionEndpoint.test.mjs (case g3 stays green) and reviewAllowlistRefusal.test.mjs / reviewQueueEndpoint.test.mjs / backendStatusResponse.test.mjs"
        status: pass
    human_judgment: false

duration: "~7h (across two dispatches — see Deviations)"
completed: "2026-09-10"
---

# Phase 70 Plan 03: One Merge, One Result Channel — Full Plan Summary

Added a real n8n Merge in front of every genuine fan-in convergence point in both the
enrichment lane (6 convergences, contacts + companies branches) and the review-decision
lane (3 convergences: extract-record, queue-rows, build-response), each backed by a
starved-lane sentinel network so every Merge input is guaranteed to fire on any request
shape without ever cascading a marker into a paid provider call, an Anthropic
research/judge call, or a HubSpot write attempt; made the enrichment webhook's
`Respond to Webhook` answer with exactly one unconditional ack (`{run_id, accepted,
row_ids}`) fed by a single node, with all four body-borne refusal/status reasons now
landing as rows on the sole channel instead of racing the ack into the response body.

## Performance

- **Duration:** ~7h across two dispatches (Task 1 landed first, budget-exhausted
  checkpoint, continuation dispatch completed Tasks 2+3)
- **Tasks:** 3/3 complete
- **Commits:** 5 (`8171d2a`, `024cb03`, `2da56a5`, `ef8648a`, `a23cd23`)
- **Files touched:** ~40 across two dispatches

## Accomplishments

- **Task 1 (D-70-01):** 6 real convergence points in the enrichment lane now sit behind
  an explicit Merge, backed by a 32-node starved-lane sentinel network (see Task 1's own
  detailed record below); `Parse HubSpot Event` correctly gets none (entry_points); 9
  provider-gate bypass chains correctly stay unmerged (class b).
- **Task 2 (D-70-07):** `Build Ack` (renamed from `Build Async Ack`) is now the sole,
  unconditional producer of the enrichment webhook's response; a new `Build Refusal
  Row` node normalizes list-expansion refusals and scale-up dispatch confirmations into
  a canonical row shape, routed into `Build Response Merge`'s new eleventh input; the
  client's `chunking.dispatch_plan` drops the retired `async_ack` parameter and its own
  (now-always-wrong) `written_records` flush.
- **Task 3 (D-70-08):** the review-decision lane's three convergences get the same
  Merge+sentinel treatment, using single-producer-sourced sentinels rather than the
  plan's literally-described NoOp+alwaysOutputData mechanism (which would leak a marker
  into a live HubSpot call — see Deviations); `wf_backend_status_cloud.json` confirmed to
  need zero changes.
- **Two Rule-1 bugs found and fixed via new walker probes this plan added** (see
  Deviations): a scale_up=true stall in the enrichment lane's recompute sentinels, and
  a permanently-null `verified_properties`/`verified` bug in the review-decision lane's
  `Build Review Response`.

## Task Commits

1. **Task 1: A Merge at every enrichment convergence point, with every input
   guaranteed to fire** — `8171d2a` (feat)
2. **Task 2: The enrichment webhook answers with an ack only; refusals become rows** —
   `ef8648a` (feat)
3. **Task 3: Merges on the review-decision lane, which keeps its body response** —
   `a23cd23` (feat)

**Plan metadata:** `024cb03` (checkpoint after Task 1), `2da56a5` (STATE/ROADMAP update
after the checkpoint), plus this SUMMARY's own closing commit.

## Files Created/Modified

- `scripts/build_cloud_workflows.py` — `merge_node`, `classify_convergence`,
  `splice_merge_before`, `set_always_output_data`, `_merge_input_index`,
  `_add_starved_lane_sentinel` (Task 1/70-02 precedent); `_append_merge_input` (new,
  Task 2) — bumps an already-created merge's `numberInputs` for a producer discovered
  after the initial splice; every enrichment/review-decision convergence's wiring
- `n8n/wf_enrichment_cloud.json` — 123 → 161 (Task 1) → 164 (Task 2: `Build Refusal
  Row`, `Refusal Fired Sentinel`, `Refusal Row Absent Sentinel`)
- `n8n/wf_enrichment_local_live.json` — 46 → 56 (Task 1 only; unaffected by Tasks 2/3)
- `n8n/wf_enrichment_local.json` — 10, unchanged throughout (no branching to converge)
- `n8n/wf_review_decision_cloud.json` — 26 → 36 (Task 3: 3 Merges + 7 sentinels)
- `n8n/wf_backend_status_cloud.json` — 17, unchanged (confirmed 0 convergences)
- `n8n/wf_contact_ingest_cloud.json`, `wf_scheduled_maintenance_cloud.json` — unchanged
  by this plan (their own Merges predate 70-03, landed in 70-02)
- `operator-claude-plugin/scripts/chunking.py` — `dispatch_plan` drops `async_ack`
  (swallowed via `**_ignored_legacy_kwargs`), `run_id` now rides every envelope
  unconditionally, the `written_records.append_chunk` per-chunk flush is deleted whole
- `operator-claude-plugin/scripts/written_records.py` — `ACTION_TO_OUTCOME` gained
  `scale_up_dispatched`/`list_expansion_refused`; `append_chunk`'s docstring updated to
  name its two surviving call sites
- `tests/n8n/enrichmentConvergenceMerge.test.mjs` (new, Task 1) — 11 tests
- `tests/n8n/reviewConvergenceMerge.test.mjs` (new, Task 3) — 10 tests
- `tests/n8n/asyncAck.test.mjs` — rewritten against the ack-only contract (Task 2)
- `tests/n8n/enrichmentBatchRefusal.test.mjs` — 4 new walker-driven refusal cases (Task 2)
- `tests/n8n/reviewDecisionEndpoint.test.mjs` — 3 pin updates for the new Merge wiring
  (Task 3)
- `tests/n8n/scaleUpFanOutFlow.test.mjs`, `tests/n8n/lib/walkWorkflow.mjs`, and ~15 more
  pin-moved test files (Task 1's own list is in its section below; Task 2 additionally
  touched `test_enrichment_list_branch.py`, `test_remaining_credits_response.py`)
- `operator-claude-plugin/tests/test_chunking.py`, `test_run_state.py`,
  `test_scale_up_runtime.py`, `test_scheduled_arm.py`, `test_write_grant.py`,
  `test_written_records.py` — rewritten/removed tests for the retired
  `written_records.append_chunk` call site inside `dispatch_plan` (Task 2)

## Task 1 record (preserved verbatim from the partial SUMMARY)

### The 6 merged convergence points (`wf_enrichment_cloud.json`)

| Merge node | Converges | Real (non-sentinel) sources |
| --- | --- | --- |
| `Build Response Merge` | every terminal branch of both contacts and companies | `HubSpot Create`, `HubSpot Update`, `Skip (NoOp)`, `Adapt Company Create`, `HubSpot Company Update`, `IF Enrich`(1), `IF Company Enrich`(1), `Unsupported Object Type`, `IF Company Skip`, `Build Research Failure Response` (+ `Build Refusal Row`, Task 2's eleventh input) |
| `Enrichment Gate Merge` | the 5 contact identity lanes | `Adapt Search`, `Adapt Fetch By Id`, `Adapt Name Search`, `Adapt Linkedin Search`, `IF Name Searchable` |
| `Company Gate Merge` | the 2 company identity lanes | `Adapt Company Fetch By Id`, `Adapt Company Name Search` |
| `Merge Winners Fan-In` | contact waterfall + research/judge escalation | `Apply Contact Judge Verdict`, `IF Contact Needs Judge`, `IF Contact Research Needed` |
| `Merge Company Fan-In` | company waterfall + research/judge escalation | `Apply Judge Verdict`, `IF Needs Judge`, `IF Research Needed` |
| `Decide Company Action Merge` | companies recompute lane | `Merge Company`, `IF Company Recompute` |

`Parse HubSpot Event` (3 alternate entry-point triggers: `Execute Workflow Trigger`,
`IF List Expanded`, `IF List Input`) correctly classifies `entry_points` and gets no
Merge — exactly one of its three sources ever runs per execution, so a Merge there would
hang forever.

9 provider-gate IF-bypass chains classify `fan_in` but are deliberately left unmerged —
one branch is always a fast-path bypass of the other, never two independent producers.

`Respond to Webhook` (4 sources at Task 1's own commit time) was also `fan_in` and left
unmerged pending Task 2 — resolved this plan (see Task 2 below).

### The sentinel network (Task 1)

32 starved-lane sentinel nodes in `wf_enrichment_cloud.json` as committed by Task 1
(measured: `nodes.filter(n => n.name.includes("Sentinel")).length` — now 34 after Task
2's own 2 additions), organized by what they protect: pre-fork absence, per-identity-lane
absence, recompute present/absent, waterfall-absent, research/judge none-needed, and
create/enrich-split absence. 8 more in `wf_enrichment_local_live.json` for its 2 merges.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `classify_convergence` misclassified `Parse HubSpot Event`** — Task 1.
- **Found during:** Task 1, initial design pass over the real graph.
- **Fix:** changed to return `entry_points` on the first disjoint ancestor pair found,
  `fan_in` otherwise (was requiring ALL pairs disjoint).
- **Commit:** `8171d2a`

**2. [Rule 3 - Blocking issue] Offline walker couldn't execute the real graph** — Task 1.
- **Fix:** threaded `ctx` through `evalExpr`/`resolveValue`/`evaluateIfConditions`, added
  `$()`/`$runIndex` injection to `tests/n8n/lib/walkWorkflow.mjs`.
- **Commit:** `8171d2a`

**3. [Rule 1 - Bug] `Recompute Not/Requested Sentinel` fired even when `scale_up=true`** — Task 2.
- **Found during:** Task 2, a new scale_up=true walker probe added specifically to
  validate the responder change (this plan's own suite never walker-tested a full
  scale-up execution through the merged enrichment graph before this task).
- **Issue:** both sentinels were sourced from "Parse HubSpot Event" directly, which
  STILL RUNS in a scale_up=true execution (it computes `scale_up` itself). They fired
  their marker into "Decide Company Action Merge" while that merge's OTHER input
  ("Merge Company"'s cascade) never ran at all, since "IF Scale Up Route"'s false lane
  never delivered — a partial delivery that hangs the merge forever instead of leaving
  it correctly dormant (matching how "Merge Company"'s own sentinels already behaved).
- **Fix:** re-sourced both onto "IF Scale Up Route"'s false lane (`source_out_idx=1`),
  matching the pre-fork sentinels' own established pattern. Verified via a direct
  walker probe (`trace.stalled` went from `[{"node":"Decide Company Action Merge",...}]`
  to `[]`).
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Commit:** `ef8648a`

**4. [Rule 1 - Bug] `Contacts Absent Sentinel`'s condition was sufficient-but-not-necessary** — Task 2.
- **Found during:** Task 2, writing the new `enrichmentBatchRefusal.test.mjs` walker
  case for an unsupported-object-type-ONLY batch (also never previously walker-tested).
- **Issue:** the condition tested `rows.every(r => r.object_type === "companies")` —
  correct only for an all-companies batch, not for the actual predicate ("contacts
  absent"). A batch of rows that are all `"unknown"` (or a mix of `"unknown"` and
  `"companies"`, with no `"contacts"` row at all) is genuinely contacts-absent but
  fails that specific test, so the sentinel never fired and Build Response Merge's
  contacts-side inputs went unfed forever.
- **Fix:** `rows.every(r => r.object_type !== "contacts")` — the actually-correct
  predicate, matching the (already-correct) sibling `Companies Absent Sentinel`'s
  De Morgan-equivalent form.
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Commit:** `ef8648a`

**5. [Rule 1/2 - Bug/missing functionality] `Decide Company Action` never carried a
recompute_refused row's reason forward** — Task 2.
- **Found during:** Task 2, the new `enrichmentBatchRefusal.test.mjs` recompute_refused
  walker case — `row.reason` came back `null` even though `Company Gate`'s own
  `gate.reason` clearly named the refusal.
- **Issue:** `Decide Company Action`'s explicit return object never included `gate` or
  a derived `reason` field at all — a pre-existing gap predating this phase (CLAUDE.md
  §13.0's own comment claims "the reason string is what makes the outcome readable in
  the response", but this was never actually true through this specific node). Left
  unfixed, D-70-07's own goal ("every body-borne refusal reason is a row on the sole
  channel") would be contradicted for this one lane.
- **Fix:** additive `reason: (row.gate && row.gate.reason) || null` on `Decide Company
  Action`'s own return object, paired with `Build Response`'s pre-existing `reason:
  row.reason ?? (row.gate && row.gate.reason) ?? null` hoist (added the same task).
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Commit:** `ef8648a`

**6. [Rule 1 - Bug] `Build Review Response`'s `$input.first()` could silently grab a
starved-lane marker** — Task 3.
- **Found during:** Task 3, `reviewConvergenceMerge.test.mjs`'s own unit-level test for
  this exact node.
- **Issue:** after splicing a real Merge in front of `Build Review Response` (3 inputs,
  exactly one ever real per request), `$input.first()` grabbed whatever landed at merge
  input index 0 — which, depending on splice/collection order, could be a starved-lane
  marker `{}` instead of the real verify-fetch envelope, permanently resolving
  `verified_properties`/`verified` to `null` for a write that had actually succeeded.
- **Fix:** `$input.all().filter((it) => Object.keys(it.json || {}).length > 0)`, taking
  the first REAL item — the same identity-drop pattern Task 1/2 already use elsewhere.
  Applied identically to `Review Extract Record` and `Review Queue Rows` (both also
  rewritten from `$input.first()` per the plan's own instruction, though neither had a
  live bug: their real upstream nodes always deliver exactly one item, real or a
  genuine zero-hit search, never landing at index 0 by chance the way a THREE-way merge
  can).
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Commit:** `a23cd23`

### Scope/design deviations (not code bugs)

**7. [Deliberate deviation] Task 2's "Build Refusal Row" routes into the Merge, not
straight into "Build Response"** — an initial design considered a direct edge
(bypassing the Merge entirely, on the theory that the Merge would receive zero
deliveries anyway in a list-refusal/scale-up execution). Rejected after advisor review:
a direct second edge into "Build Response" would re-create a genuine multi-inbound-edge
risk at the exact node Task 1 converged, and would violate
`test_remaining_credits_response.py`'s existing pin of that node's inbound edge set.
Implemented instead as an eleventh Merge input (`_append_merge_input`) plus a
"Refusal Fired Sentinel" (fed FROM Build Refusal Row itself, feeding all ten OTHER
inputs whenever it delivers anything) — Build Response's own inbound edge count stays
exactly one throughout.

**8. [Deliberate deviation] Task 3's sentinel mechanism differs from the plan's literal
action text** — see Decisions above and the coverage entry for D-70-08. The plan's
own words ("set `alwaysOutputData: true` ... inserting a NoOp terminal where the
terminal is an IF output") were verified, via the offline walker, to either do nothing
(alwaysOutputData on a node that receives zero input is never consulted, since that
node is never dispatched) or actively leak a marker into a live HubSpot search/write
node (alwaysOutputData on the SOURCE IF itself, whose empty branch feeds a real node
directly). Used the proven starved-lane-sentinel pattern instead — behaviorally
equivalent, verified safe, and consistent with every other convergence in this repo.

**9. [Not a code deviation] The plan ran across two dispatches, split by a
context-budget checkpoint after Task 1.** The first dispatch shipped Task 1 alone and
recorded a `status: partial` SUMMARY plus a STATE/ROADMAP checkpoint commit
(`024cb03`, `2da56a5`). This dispatch resumed from that checkpoint, executed Tasks 2 and
3 in full, and rewrites this SUMMARY to `status: complete`. No prior work was redone;
`8171d2a` (Task 1's commit) is unchanged and is the first entry in Task Commits above.

**10. [Documented, out-of-scope note] `test_control_flag_parity.py` — the plan's own
acceptance criteria named this file for "updated declaration counts" (a 4→3 request-
level flag change). Investigated: this file tests an ENTIRELY DIFFERENT flag system
(the five `ALLOW_HUBSPOT_*`/`TEST_RECORD_*` write-safety overlay flags deploy_n8n_
workflows.py reads), has no relationship to the retired `async_ack` request-level flag,
and required — and received — zero changes. It passes, unmodified, as part of the full
plugin suite (2849 passed). Recorded here as a plan-authoring reference mismatch rather
than silently treated as satisfied without comment.

**11. [Documented, deferred gap] `chunking.dispatch_plan` no longer populates
`written_records`.** See Decisions above. `run_report.py`'s end-of-run report currently
reads `written_records.load()` for entries this function used to write via `dispatch_
plan`'s per-chunk loop; that read path is now starved for any run dispatched after this
change. This is the DIRECT, INTENDED consequence of D-70-07 (the sync body can no
longer carry real per-row outcomes for any call), not an oversight — but `run_report.py`
itself is not migrated to read runData in this plan; that migration is D-70-08's scope.
No test in this repo currently exercises `run_report.py` against a post-70-03
`dispatch_plan` call, so this gap is not test-covered either; a follow-on plan should
add that coverage when it performs the migration.

**12. [Documented, out-of-scope note] `CLAUDE.md` §13.0.2's own "four-flag table becomes
three" documentation was NOT updated in this plan** — `CLAUDE.md` is not in this plan's
`files_modified` and updating a document of this size/density carries real risk of
introducing an unrelated inconsistency. Flagged here so a documentation-focused pass
(or the next plan touching this area) picks it up; the LIVE workflow/client behavior
this plan shipped is unaffected by the doc lagging.

**Total deviations:** 6 auto-fixed bugs (Rules 1/2/3), 2 deliberate scope deviations
from the plan's literal wiring description, 1 cross-dispatch note, 2 documented
out-of-scope/deferred notes. **Impact on plan:** none of the auto-fixes changed the
plan's own required behavior or success criteria; both scope deviations were verified,
via the offline walker and the full test suite, to deliver the IDENTICAL required
behavior more safely than the literal instruction would have.

## Verification performed

- `node --test tests/n8n/*.test.mjs`: 1005/1005 pass (was 987/987 after Task 1; +8 from
  Task 2's rewritten `asyncAck.test.mjs`/`enrichmentBatchRefusal.test.mjs`, +10 from
  Task 3's new `reviewConvergenceMerge.test.mjs`, net of small pin adjustments).
- `.venv/bin/python -m pytest -q --tb=short`: 4628 passed, 154 skipped (root suite).
- `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q`: 2849 passed, 5 skipped.
- Builder idempotency: two consecutive `python3 scripts/build_cloud_workflows.py` runs
  produce byte-identical JSON for every one of the eight committed workflow files,
  confirmed independently after Task 2 and after Task 3.
- `settings.executionOrder` confirmed absent (`None`) from all 5 named cloud workflows.
- Both write flags confirmed `"false"` in the committed enrichment JSON
  (`ALLOW_HUBSPOT_CREATE`, `ALLOW_HUBSPOT_RECORD_WRITES`) after every task.
- Merge node counts confirmed by direct query: `wf_review_decision_cloud.json` → 3,
  `wf_backend_status_cloud.json` → 0.
- Manual walker probes (this session): scale_up=true execution (no stall, ack fires
  once, row_ids echoed); list-expansion-refusal execution (no stall, ack fires once
  with empty row_ids); all 5 review-decision request shapes named in the plan's
  `<behavior>` block (dry-run companies, contacts write, queue single-branch × 2) — all
  settle with zero stalls and exactly one response.
- Reverted each of the two Task-3/Task-2 bug fixes in isolation and re-ran the relevant
  probe to confirm the fix actually bites (not a vacuously-passing test) — see
  Deviations #3/#6 above.

## Issues Encountered

None beyond the auto-fixed deviations above — all resolved within this plan's own scope.

## User Setup Required

None — no external service configuration required. Nothing armed; no deploy, no bounce,
no live n8n/HubSpot call anywhere in this plan's execution.

## Next Phase Readiness

Ready for 70-04 and onward: the enrichment lane's provider-chain by-name reads
(`nodeRunRecovery.js`) and the review-decision lane's remaining single-run by-name reads
(`Parse Review Decision`/`Parse Review Queue Request`/`Build Review Decision`/`Status
Credit Request`, deliberately left untouched by Task 3 per its own action text) are the
next wave's scope. The `_append_merge_input` helper this plan added is available for any
future plan that discovers a NEW producer for an already-spliced Merge.

## Self-Check: PASSED

- `n8n/wf_enrichment_cloud.json`: FOUND, 164 nodes, 6 merge nodes.
- `n8n/wf_review_decision_cloud.json`: FOUND, 36 nodes, 3 merge nodes.
- `n8n/wf_backend_status_cloud.json`: FOUND, 17 nodes, 0 merge nodes.
- `tests/n8n/enrichmentConvergenceMerge.test.mjs`: FOUND.
- `tests/n8n/reviewConvergenceMerge.test.mjs`: FOUND.
- Commits `8171d2a`, `024cb03`, `2da56a5`, `ef8648a`, `a23cd23`: all FOUND in
  `git log --oneline --all`.
- `node --test tests/n8n/*.test.mjs`: re-run, 1005/1005 pass.
- `.venv/bin/python -m pytest -q`: re-run, 4628 passed, 154 skipped.

---
*Phase: 70-one-merge-one-result-channel-n8n-runtime-truth*
*Completed: 2026-09-10*
