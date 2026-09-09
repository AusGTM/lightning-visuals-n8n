---
phase: 70-one-merge-one-result-channel-n8n-runtime-truth
plan: 05
subsystem: n8n-workflow-generation
tags: [n8n, workflow-automation, code-generation, write-safety, hubspot, merge-convergence]

requires:
  - phase: 70-04
    provides: carry Merges at every hop, zero by-name reads across all 8 built cloud workflows, assert_no_by_name_reads wired into main()
provides:
  - "D-70-12: one canonical `write_request` ({action, hs_object_id, domain, email}) emitted by every gated write's upstream Code node on all four lanes, via one shared `_buildWriteRequest` helper; the gate reads ONLY that shape; the four-way identity fallback ladder is deleted; `assert_write_request_emitters` raises at generation time when an emitter is missing"
  - "D-70-13: the enrichment lane has real spliced gates for the first time (four of them: HubSpot Create/Update, HubSpot Company Create/Update); neither Decide node computes write permission or bakes an arming constant any more"
  - "D-70-14: every gate is IF-shaped — a Code node stamps a `write_allowed` verdict onto EVERY item and a paired IF routes it; a refused row is emitted with `action: \"write_blocked\"` and a reason, reaching the lane's response builder through its OWN merge input"
  - "D-70-06: the ingest lane's pre-write refusal precheck is deleted; the row's outcome of record is the gate's own emitted verdict, overlaid onto the decided snapshot by Build Ingest Response"
  - "D-70-15: an update and its association share ONE write_request and ONE allowlist verdict; the association's second gate is removed; an update is never held for lack of a company"
  - "`wire_gate_refusal_lane(...)`: the one helper that gives a gate's refusal its own merge input plus the three sentinels that keep both that input and the write path's own fed"
affects: [70-06, 70-07]

actuals:
  tokens: 690000
  tasks: 3
  commits: 15
  plan_head_before: 0350531

tech-stack:
  added: []
  patterns:
    - "Shared emitter helper composed at module top (WRITE_REQUEST_JS / _write_request_js()), unlike WRITE_SAFETY_GATE_JS's build-site composition — the emitter has no dependency on constants defined later in the module, so `+ WRITE_REQUEST_JS +` works at every call site regardless of definition order."
    - "Generation-time emitter assertion via a walk-to-nearest-Code-node BFS (_write_request_source_names) plus a string-literal marker check (`_buildWriteRequest(` in jsCode) — same string-marker-at-generation-time approach as _run_recovery_marker/assert_no_by_name_reads, extended to a graph walk because the emitter is not always the write node's DIRECT predecessor."
    - "A merge input may have many MARKER producers but exactly ONE real producer. Markers carry no data and are filtered downstream, so a double marker delivery is harmless; two real producers on one input race, and the Merge fires and locks on whichever satisfies it first."
    - "`mirror_index`: derive a new merge input's starvation sentinels from the ones already feeding a sibling input, instead of hand-listing ~30 sentinel names that would go stale the first time one is added."

key-files:
  created: []
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_contact_ingest_cloud.json
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_review_decision_cloud.json
    - n8n/wf_scheduled_maintenance_cloud.json
    - tests/n8n/writeGateShape.test.mjs
    - tests/n8n/companyRecomputeLaneFlow.test.mjs
    - tests/n8n/ingestUpdateWriteBlockedFlow.test.mjs
    - tests/n8n/ingestUpdateGateDomainFallback.test.mjs
    - tests/n8n/companyAssociationFlow.test.mjs
    - tests/n8n/contactCreateGateFlow.test.mjs
    - tests/n8n/enrichmentLaneContactCreateRefusal.test.mjs
    - tests/n8n/bareEventChainFlow.test.mjs
    - tests/n8n/createIdentitySeed.test.mjs
    - tests/n8n/enabledResearchLaneFlow.test.mjs
    - tests/n8n/writePatchBodyFlow.test.mjs
    - tests/n8n/ingestCarryMerge.test.mjs
    - tests/n8n/ingestTracerFlow.test.mjs
    - tests/n8n/reviewAllowlistRefusal.test.mjs
    - tests/n8n/reviewDecisionEndpoint.test.mjs
    - tests/n8n/reviewWriteFlagSeparation.test.mjs
    - tests/n8n/dedupeSweepWiring.test.mjs
    - tests/n8n/sjPredicates.test.mjs
    - tests/test_write_gate_coverage.py
    - tests/test_cloud_write_path.py
    - tests/test_merge_helpers.py
    - tests/test_remaining_credits_response.py
    - operator-claude-plugin/tests/test_control_flag_parity.py
    - .planning/todos/completed/2026-09-09-ingest-create-row-has-no-write-blocked-precheck.md
    - .planning/phases/70-one-merge-one-result-channel-n8n-runtime-truth/70-DEFERRED-GATES.md

key-decisions:
  - "A gate's refusal lane gets its OWN merge input, never a share of the write path's. The first design shared it — reasoning that reusing an existing index left the ~30-entry starved-lane sentinel network untouched, which it does. It is still wrong: every OTHER multi-producer input on these merges is mutually exclusive by construction (a marker OR the real terminal, never both), and this one was not. On an ARMED batch with a MIXED verdict the zero-hop refusal beats the permitted row's multi-hop delivery, the Merge fires and locks, and the real arrival is dropped. Measured with the walker over the committed graph: the permitted row reported `association: \"not_confirmed\"` when HubSpot had associated it. Every disarmed suite was green through the bug, because disarmed every row is refused and the two producers ARE exclusive."
  - "The refusal lane costs three sentinels per gate, not one: `No Refusal Sentinel` (gate-sourced, feeds the refusal input when the gate refused nothing), `Gate Unreached Sentinel` or a derived `mirror_index` (feeds it when the gate never ran), and `All Refused Sentinel` (gate-sourced, feeds the WRITE path's own input when the gate allowed nothing). The third is newly required precisely because refused rows now keep their real action past the routing IFs: the routing-keyed sentinels correctly stay silent when rows ARE heading for the write, yet the gate can refuse every one of them."
  - "Ingest's `Associate Lane Sentinel` gains the gate predicate itself (`_writeSafetyAllows` duplicated into its jsCode) — the review lane's accepted BUG-30 pattern, for the identical reason: it is graph plumbing deciding whether a Merge-feeding marker is needed, never a second authorization. It is required because that marker SHARES the association lane's input with a real delivery, so the two must be mutually exclusive. Consequence: it becomes a third `ALLOW_HUBSPOT_RECORD_WRITES` declaring node on the ingest lane, and any arming run that misses it reproduces the dropped-association bug on a real batch."
  - "D-70-13's null-domain rule (Task 1) was implemented literally and LANE-WIDE, not contacts-only: `Build Review Decision` feeds BOTH the companies and contacts review PATCHes through routing IFs, so forcing `write_request.domain` to null there applies to companies too. Companies lose their domain-allowlist path on review writebacks. FLAGGED FOR THE OPERATOR rather than silently accepted — the plan's own wording (\"contacts stay id-allowlist-only\") reads contacts-specific even though the single emitter node cannot distinguish."
  - "`association: \"none\"` is KEPT over the plan's `not_attempted` wording. The behaviour D-70-15 asks for is implemented exactly (a permitted update with no resolved company runs, is never held, and reports that it associated nothing); only the vocabulary differs, and it is a live client-visible value — `operator-claude-plugin/scripts/preingest.py:1186` keys on `== \"none\"`, and `run_report.py` already maps BOTH `not_confirmed` and `not_attempted` for display. Renaming it would break a reader for no behavioural gain."
  - "Scheduled-maintenance gates FOUR writes, not the plan's three: `SJ-1 Set Requested`, `SJ-2 Set Requested`, `Dedupe Set Needs Review`, `Review Apply Update`. Task 1 + 2a already put all four on the canonical shape and the IF shape. That lane has NO response builder and no webhook response, so its gates' false branches have nowhere useful to go — leaving them unwired is correct and final for that lane, not a placeholder."
  - "The enrichment lane gates FOUR writes too, not the plan's three: `HubSpot Company Create` is the identical off-by-one already caught for scheduled-maintenance. `assert_write_request_emitters` runs INSIDE `splice_write_gates`, so the two Decide nodes had to stamp `write_request` BEFORE the splice call was added, not after."
  - "An enrichment-lane contact create now reports `review` rather than `write_blocked` on a disarmed run. The Phase 61 Plan 06 association hold (`if (action === \"create\") action = \"review\"`) was always unconditional and always sat immediately AFTER the inline write-safety check; the check merely masked it disarmed. The hold is the stronger refusal — it is upstream of the gate, so an armed gate cannot land the create either."

patterns-established:
  - "`wire_gate_refusal_lane(nodes, conns, write_name, merge_name, x, y, *, mirror_index=None, unreached_source=None, unreached_condition_js=None)` — the one place any future gated write's refusal lane should be wired, rather than hand-appending a merge input and three sentinels at a new call site."
  - "_write_request_js()/WRITE_REQUEST_JS + _buildWriteRequest(action, hsObjectId, domain, email): the one place any future gated write's emitter should call, rather than hand-deriving identity fields."

requirements-completed: [D-70-12, D-70-13, D-70-14, D-70-15, D-70-06]

coverage:
  - id: D-70-12
    description: "Every node feeding a gated write emits the canonical write_request; the gate reads only that shape; the fallback ladder is deleted; generation raises when an upstream emitter is missing"
    verification:
      - kind: unit
        ref: "tests/n8n/writeGateShape.test.mjs (28 tests — every gate's jsCode references no identity key outside write_request; empty-allowlist denial on all four lanes)"
        status: pass
      - kind: unit
        ref: "tests/test_write_gate_coverage.py::test_assert_write_request_emitters_raises_on_a_missing_emitter, ::test_assert_write_request_emitters_passes_when_the_emitter_is_correct, ::test_assert_write_request_emitters_walks_through_a_native_if_node"
        status: pass
      - kind: unit
        ref: "tests/n8n/ingestUpdateGateDomainFallback.test.mjs (rewritten against the canonical shape — its subject, the gate-side fallback, is gone)"
        status: pass
      - kind: unit
        ref: "node --test tests/n8n/*.test.mjs (1032/1032)"
        status: pass
    human_judgment: false
  - id: D-70-13
    description: "The enrichment lane gains four real spliced gates; the write-permission predicate has exactly one home per lane; the scheduled-maintenance writes adopt the same shape"
    verification:
      - kind: unit
        ref: "tests/test_write_gate_coverage.py::test_every_enrichment_write_sits_behind_its_own_spliced_gate (4 params), ::test_the_enrichment_decide_nodes_no_longer_compute_write_permission (2 params)"
        status: pass
      - kind: unit
        ref: "tests/test_cloud_write_path.py::test_write_gates_bake_write_safety_constants_and_gate_the_action (4 params), ::test_decide_nodes_no_longer_decide_write_permission (2 params), ::test_proposed_action_assignment_cannot_be_overridden_by_any_flag{,_companies}"
        status: pass
      - kind: unit
        ref: "tests/n8n/writeGateShape.test.mjs::\"the enrichment lane has a spliced two-node gate in front of each of its four HubSpot writes\", ::\"enrichment lane: the empty-allowlist denial now comes from the spliced gate, not Decide Action\""
        status: pass
      - kind: unit
        ref: "tests/n8n/companyRecomputeLaneFlow.test.mjs::\"execution 11858's refusal survives, now emitted by the spliced gate rather than by Decide Company Action\""
        status: pass
    human_judgment: false
  - id: D-70-14
    description: "A refused row is EMITTED, never dropped; a fully refused batch cannot dead-end; the refusal reaches the response builder on a channel that cannot starve or race"
    verification:
      - kind: unit
        ref: "tests/n8n/writeGateShape.test.mjs::\"every spliced write gate's Code node preserves item count on a mixed permit/refuse batch\""
        status: pass
      - kind: integration
        ref: "tests/n8n/writeGateShape.test.mjs::\"enrichment lane: a fully refused two-row batch produces exactly two rows at the response builder, with no stalled merge\" (walker over the committed wf_enrichment_cloud.json)"
        status: pass
      - kind: integration
        ref: "tests/n8n/writeGateShape.test.mjs::\"ingest: a batch of nothing but REFUSED updates still reaches Build Ingest Response, one row, reported blocked\", ::\"ingest: a batch of updates that resolve NO company does not stall\""
        status: pass
      - kind: integration
        ref: "tests/n8n/enrichmentConvergenceMerge.test.mjs::\"a mixed batch (one create, one update) reaches Build Response with exactly two rows\", ::\"a companies-only batch does not stall any contacts-side merge input\", ::\"a contacts-only batch does not stall any companies-side merge input\""
        status: pass
      - kind: unit
        ref: "tests/n8n/writeGateShape.test.mjs::\"the enrichment lane's gate IF false branch has its OWN Build Response Merge input\", ::\"ingest: each gate's refusal lane has its OWN Ingest Merge Response input, with both its sentinels\""
        status: pass
    human_judgment: false
  - id: D-70-06
    description: "The ingest pre-write refusal precheck is removed rather than extended to create rows; the row's outcome of record is the write node's actual output"
    verification:
      - kind: unit
        ref: "tests/n8n/writeGateShape.test.mjs::\"ingest: the pre-write refusal precheck is gone from Decide Action (D-70-06)\", ::\"ingest: Build Ingest Response reports the GATE's verdict, not the pre-write intention\""
        status: pass
      - kind: unit
        ref: "tests/n8n/ingestUpdateWriteBlockedFlow.test.mjs (5 tests, rewritten: the F11/execution-12181 regression pin now runs Decide Action -> gate -> Build Ingest Response)"
        status: pass
    human_judgment: false
  - id: D-70-15
    description: "An update and its association share one write_request and one verdict; both run or neither; an update is never held for lack of a company"
    verification:
      - kind: unit
        ref: "tests/n8n/writeGateShape.test.mjs::\"ingest: ONE gate covers both the update and its association (D-70-15)\""
        status: pass
      - kind: integration
        ref: "tests/n8n/writeGateShape.test.mjs::\"ingest: a batch of nothing but REFUSED updates...\" (asserts NEITHER HubSpot Update NOR HubSpot Associate Company ran), ::\"ingest: a batch of updates that resolve NO company does not stall\" (association \"none\", not held)"
        status: pass
      - kind: unit
        ref: "tests/n8n/companyAssociationFlow.test.mjs (rewritten: the association's only remaining condition is a resolved company id, applied in Build Association Request), tests/n8n/pairPipelineAssociationFlow.test.mjs (unmodified, still green)"
        status: pass
    human_judgment: false
  - id: live-armed-mixed-verdict
    description: "The armed, MIXED-verdict batch observed on the real n8n engine rather than on the offline walker"
    verification: []
    human_judgment: true
    rationale: "Deferred per the operator's standing ruling that `gate=\"blocking-human\"` LIVE probes go to end-of-phase UAT; nothing is armed and no unattended credit-spending batch has run. Recorded as Gate 70-05-A in `70-DEFERRED-GATES.md` with its six required observations. The fix IS proven offline (walker over the committed graph, RED before the fix and GREEN after), but `tests/n8n/lib/walkWorkflow.mjs`'s own comment states its fire-once Merge model is a spec, \"not n8n's real multi-wave behaviour\" — and this phase's thesis is n8n runtime truth, so the model's agreement is not the engine's."

duration: ~6h (four dispatches)
completed: 2026-09-10
status: complete
---

# Phase 70 Plan 05: One write request, one gate per lane, and a refusal that is a row Summary

**Every gated write on all four lanes now sits behind a two-node IF-shaped gate that reads one canonical `write_request`, stamps a verdict on every row instead of filtering any away, and routes refusals onto their own merge input so a fully refused batch reports rather than dead-ends. The enrichment lane got real gates for the first time (four of them); the ingest lane lost both its pre-write refusal precheck and the association's duplicate second verdict; and the identity fallback ladder that grew from two live incidents is deleted, with a generation-time assertion that every gated node's upstream emits the shape the gate reads.**

## Performance

- **Duration:** ~6h across four dispatches · **Started:** 2026-09-09 · **Completed:** 2026-09-10 · **Tasks:** 3 (Task 2 executed as sub-steps 2a/2b/2c) · **Commits:** 15 · **Files modified:** 28

## Accomplishments

**Task 1 — one canonical write request, emitted once (commits `12866c8`, `e0a35aa`)**

- `_write_request_js()` / `WRITE_REQUEST_JS` define the single shared `_buildWriteRequest(action, hsObjectId, domain, email)` helper, embedded verbatim into every emitting Code node.
- `_write_gate_js(action)` reads exclusively from `it.json.write_request`. The four-way fallback ladder (`existingRecord.hs_object_id`, `identity_keys.domain`, `properties.email`, bare `.email`) that grew from F11 and BUG 27 is deleted outright.
- `assert_write_request_emitters` (+ `_write_request_source_names`, a backwards BFS stopping at the nearest Code node on each path) is wired unconditionally into `splice_write_gates`, so every present and future call site is covered for free — including Task 2's enrichment call.
- Every emitter on the ingest, scheduled-maintenance and review-decision lanes stamps `write_request`; the review lane forces `domain: null` per D-70-13.
- A same-dispatch Rule 1 fix (`e0a35aa`) kept `Build Review Decision`'s own BUG-30 precheck in agreement with the gate it precedes — Task 1 had widened the null-domain rule to the whole lane, making a company review approval under a domain-only armed window reach the gate with a verdict the precheck disagreed with, and starve `Build Review Response Merge`.

**Task 2a — the gate becomes IF-shaped (commit `d87eef1`)**

- `_write_gate_js` rewritten from `.filter()` to `.map()`: it stamps `write_allowed`, and on refusal `action: "write_blocked"` plus a reason, onto EVERY item. Its item count in equals its item count out on every call — that invariant is what makes a refused row a row.
- `splice_write_gates` emits a paired `<write> Write Gate IF` node and rewires the write node behind its true output.

**Task 2b — the enrichment lane's first-ever gates (commit `2c75e90`, RED `2a8370e`)**

- Four gates spliced: `HubSpot Create`, `HubSpot Update`, `HubSpot Company Create`, `HubSpot Company Update`.
- `ENRICH_DECIDE_CLOUD` and `ENRICH_DECIDE_CO_CLOUD` stop calling `_writeSafetyAllows` and stop baking any write-safety constant; they emit `write_request` instead. `Decide Action` (ingest) later shed `WRITE_SAFETY_GATE_JS` too, keeping only the one `ALLOW_HUBSPOT_CREATE` const it genuinely reads for create-vs-review routing.
- Carry-merge count-mismatch fix (Rule 1, pre-existing at ingest since 2a): a carry merge's `carry_source` must be the gate IF's TRUE output — never the gate CODE node, whose output includes the refused rows, and never the routing IF upstream of it. Applied to the enrichment company-create carry and all three ingest carries.

**Task 2c + Task 3 — the precheck deleted, one verdict per row (commit `d90fdba`, RED `71ec850`)**

- The ingest `Decide Action` pre-write refusal precheck is deleted. It PREDICTED the gate's verdict instead of reporting it; its own comment conceded create rows were left uncovered because reproducing the create gate's email-domain derivation risked a false `write_blocked`. `Build Ingest Response` now overlays the gate's emitted verdict (and its reason) onto the decided snapshot, which still carries the pre-write action — closing F11 / execution 12181 for creates and updates alike, with no per-action derivation to get wrong. The todo the precheck filed is closed by construction and moved to `.planning/todos/completed/`.
- The association's own second allowlist gate is removed (D-70-15). It ran downstream of a write that had already passed a gate, so a second verdict could only ever disagree with the first. Its only remaining condition is a resolved company id, which `Build Association Request` already applies by dropping rows without one — an update is never held, and reports `association: "none"`.
- `Associate Lane Sentinel`'s condition gains the `company_id` conjunct (and, in the follow-up fix, the gate predicate), so it asks the question the lane actually answers.

**The Rule 1 fix that mattered most (commit `45cbd50`)**

2b and 2c both wired each gate IF's false output onto the SAME merge input the write path's own terminal already feeds, on the reasoning that reusing an existing index leaves the entire starved-lane sentinel network untouched. It does. It is still wrong, and every disarmed suite was green through it.

An advisor-prompted walker run over the committed graph with ONE row on the allowlist and one not — the primary armed use case of an allowlist — showed the failure: the refusal travels zero hops from the gate to the merge while the permitted row travels the real multi-hop chain (`HubSpot Update` → `Update Carry Merge` → `Build Association Request` → `HubSpot Associate Company` → `Associate Carry Merge`). The Merge fires on whichever set of deliveries satisfies it first and locks; the permitted row's real association arrival was dropped and it reported `association: "not_confirmed"` when HubSpot had associated it. Disarmed, every row is refused, so the two producers ARE mutually exclusive — which is exactly why nothing caught it.

Fixed via one new helper, `wire_gate_refusal_lane`, called once per gate:

- each gate's refusal gets its OWN merge input (`_append_merge_input`);
- `<write> No Refusal Sentinel` (gate-sourced) feeds it when the gate refused nothing;
- `<write> Gate Unreached Sentinel` (routing-predicate-sourced) feeds it when the gate never ran — on the enrichment lane that second question is DERIVED instead, via `mirror_index`, by copying it off whichever sentinels already feed that write's own terminal, so a hand-listed set of ~30 names cannot go stale;
- `<write> All Refused Sentinel` is the mirror image, newly required now that refused rows keep their real action past the routing IFs: the routing sentinels correctly stay silent when rows ARE heading for the write, yet the gate can refuse every one and starve the terminal's input;
- ingest's `Associate Lane Sentinel` gains the gate predicate itself, because its marker shares the association lane's input with a real delivery and the two must be exclusive.

Pinned permanently by an armed-mixed walker case asserting the permitted row keeps `association: "associated"`, the refused row reports `write_blocked`, and `Ingest Merge Response` fires exactly once (a second run would double every reported row).

## Task Commits

1. **Task 1: One canonical write request, emitted once, fallback ladder deleted** — `12866c8` (feat) + `e0a35aa` (fix)
2. **Task 2: The gate becomes IF-shaped, and the enrichment lane finally has one** — `d87eef1` (2a) + `2a8370e`/`2c75e90` (2b RED/GREEN) + `71ec850`/`d90fdba` (2c RED/GREEN) + `45cbd50` (Rule 1: refusal lanes get their own merge inputs)
3. **Task 3: One verdict covers an update and its association** — `d90fdba` (landed with 2c; the two changes are one graph edit) + `43b0d70` (plugin arming-surface counts) + `841c1ec`/`3c7b16e` (acceptance-criteria and recompute-lane pins)

**Plan metadata:** `9bbe7d7`, `393b398`, `72a6a3f`, `6427f46` (partial checkpoints across dispatches 1-3), plus this dispatch's completion commit.

## Files Created/Modified

- `scripts/build_cloud_workflows.py` — `_write_request_js()`/`WRITE_REQUEST_JS`; rewritten `_write_gate_js` (map, never filter); `assert_write_request_emitters`/`_write_request_source_names`; two-node `splice_write_gates`; new `wire_gate_refusal_lane`; `write_request` emission in `DECIDE_CLOUD`, `ENRICH_DECIDE_CLOUD`, `ENRICH_DECIDE_CO_CLOUD`, `BUILD_ASSOCIATION_REQUEST`, `REVIEW_BUILD_DECISION`, `ENRICH_EXTRACT_SEARCH_ROWS`, `SJ2_CO_GATE`, `ENRICH_DEDUPE_SWEEP`, `ENRICH_APPLY_REVIEW`; the ingest precheck deleted; `BUILD_INGEST_RESPONSE`'s verdict overlay; `Associate Lane Sentinel` rewritten
- `n8n/wf_enrichment_cloud.json` — 202 → **218** nodes (4 gates + 4 gate IFs + 10 refusal sentinels); `Build Response Merge` 11 → 15 inputs
- `n8n/wf_contact_ingest_cloud.json` — 45 → **50** nodes (2 gates + 2 gate IFs + 4 refusal sentinels, minus the association's removed gate pair); `Ingest Merge Response` 3 → 5 inputs
- `n8n/wf_review_decision_cloud.json` — 43 → **45** nodes (2 gate IFs)
- `n8n/wf_scheduled_maintenance_cloud.json` — 39 → **43** nodes (4 gate IFs), the moved pin Task 3 asks to record against 39
- `tests/n8n/writeGateShape.test.mjs` — 28 tests: canonical shape and empty-allowlist denial on all four lanes; the enrichment lane's four gates and their own refusal inputs; the ingest precheck's absence and the single update+association verdict; and four walker-driven cases (fully-refused enrichment batch, fully-refused ingest batch, no-company ingest batch, armed-mixed ingest batch)
- `tests/test_write_gate_coverage.py`, `tests/test_cloud_write_path.py`, `tests/test_merge_helpers.py`, `tests/test_remaining_credits_response.py` — the gate/merge inventories and the moved predicate, retargeted from the Decide nodes to the gates
- `operator-claude-plugin/tests/test_control_flag_parity.py` — the ingest lane's arming-surface counts: `ALLOW_HUBSPOT_RECORD_WRITES` 4 → 3, `ALLOW_HUBSPOT_CREATE` 4 → 4
- 18 further `tests/n8n/*.test.mjs` files — rewritten where they asserted a gate DROPPED a row, or that `Decide Action` stamped `write_blocked`, or that the association had its own gate
- `.planning/phases/70-.../70-DEFERRED-GATES.md` — Gate 70-05-A, the first armed mixed-verdict batch

## Decisions Made

See `key-decisions` in the frontmatter. The four an operator or a later phase must actually act on:

1. **The refusal lane must never share the write path's merge input** — with the measured evidence, so no future change re-derives the "reuse the index, touch no sentinel" shortcut.
2. **D-70-13's null-domain rule is lane-wide** — companies lose their domain-allowlist path on review writebacks. Flagged, not silently accepted.
3. **`Associate Lane Sentinel` is now an arming surface.** Any arming run (or hand-rolled test helper) that rewrites the gates but not the sentinel reproduces the dropped-association bug on a real batch. `n8n_arming.set_write_safety` does rewrite all declaring nodes, so the tool is correct; the risk is a manual arm.
4. **`association: "none"` kept over the plan's `not_attempted`** — behaviour matches D-70-15 exactly; the rename would break `preingest.py`'s live reader for no gain.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Review precheck disagreed with the gate it precedes, reachable hang on a company**
- **Found during:** post-Task-1 advisor review
- **Issue:** `Build Review Decision`'s BUG-30 precheck passed the record's real domain while the gate downstream now sees `write_request.domain === null` unconditionally. Under an armed domain-only window a company submit would report `applied`, be refused at the gate, never reach `Review Verify Fetch`, and starve `Build Review Response Merge`.
- **Fix:** the precheck passes `null` too, matching the gate.
- **Files:** `scripts/build_cloud_workflows.py`, `n8n/wf_review_decision_cloud.json`
- **Verification:** full node + pytest suites; confirmed no existing test arms a company review approval via `TEST_RECORD_DOMAINS`
- **Commit:** `e0a35aa`

**2. [Rule 1 - Bug] Carry merges paired with the wrong source once a gate could refuse a subset**
- **Found during:** Task 2b
- **Issue:** `splice_carry_merge_after`'s `carry_source` was the gate CODE node (ingest, latent since 2a) and `IF Company Create` (enrichment). Both deliver a different item count than the write node on any partially-refused batch, so `combineByPosition` would pair row i of the HTTP response with row i of the wrong wave.
- **Fix:** `carry_source` is the gate IF's TRUE output on all four affected carries.
- **Files:** `scripts/build_cloud_workflows.py`, both regenerated workflows
- **Verification:** `tests/n8n/writeGateShape.test.mjs::"the enrichment lane's carry merges pair with the gate IF's TRUE output"`
- **Commit:** `2c75e90`

**3. [Rule 1 - Bug] A gate's refusal sharing the write path's merge input drops the permitted row's real arrival on an armed mixed batch**
- **Found during:** advisor review after 2b and 2c were both committed
- **Issue:** the full mechanism is in Accomplishments above. Not hypothetical: measured with the walker over the committed graph.
- **Fix:** `wire_gate_refusal_lane` — one merge input per refusal lane plus three sentinels per gate; `Associate Lane Sentinel` gains the gate predicate.
- **Files:** `scripts/build_cloud_workflows.py`, all four cloud workflows, `tests/n8n/writeGateShape.test.mjs`, `tests/n8n/ingestCarryMerge.test.mjs`, `tests/n8n/ingestTracerFlow.test.mjs`, `tests/test_merge_helpers.py`, `operator-claude-plugin/tests/test_control_flag_parity.py`
- **Verification:** the permanent armed-mixed walker case, RED before the fix (`association: "not_confirmed"`) and GREEN after (`"associated"`), plus `Ingest Merge Response` asserted to fire exactly once
- **Commit:** `45cbd50`

### Plan-text corrections (off-by-one and file-name)

- **"three scheduled-maintenance gates" is FOUR:** `SJ-1 Set Requested`, `SJ-2 Set Requested`, `Dedupe Set Needs Review`, `Review Apply Update`.
- **"a gate in front of `HubSpot Create`, `HubSpot Update` and `HubSpot Company Update`" is FOUR:** `HubSpot Company Create` is the same class of omission.
- **Emitter-assert ordering:** `assert_write_request_emitters` runs INSIDE `splice_write_gates`, so the two enrichment Decide nodes had to stamp `write_request` BEFORE the splice call was added.
- **Task 2's `<action>` says to make the false branch "always fire on a fully permitted batch, at the `alwaysOutputData` placement 70-02's disarmed probe established".** Not done, and moot: the builder's own comment above `Associate Lane Sentinel` records that per-routing-IF `alwaysOutputData` was tried and REJECTED in 70-02 for precisely the race this plan then hit anyway. The obligation is met by the sentinel mechanism instead — `<write> No Refusal Sentinel` is exactly "the false branch's input is fed on a fully permitted batch".
- **Task 2's acceptance criterion names `tests/test_write_gate_coverage.py` for the "Decide nodes no longer compute write permission" case.** Asserted in BOTH that file and `tests/test_cloud_write_path.py` (where the superseded assertion lived).

### Behavioural changes worth naming

- **An enrichment-lane contact create now reports `review` rather than `write_blocked` disarmed.** The association hold was always unconditional and upstream of the gate; the inline check masked it. Stronger, not weaker: an armed gate cannot land the create either, because the row never reaches `IF Create`'s true branch.
- **Ingest arming surfaces fall from four declaring nodes to three** for `ALLOW_HUBSPOT_RECORD_WRITES` (two gates + `Associate Lane Sentinel`), and stay at four for `ALLOW_HUBSPOT_CREATE` (those three + `Decide Action`'s standalone create-vs-review const).

### Process deviations

- **TDD RED/GREEN was collapsed into one commit for Task 1 and 2a** (dispatches 1-2, under context-budget pressure; no `gsd-tools check tdd-red-evidence` run). 2b and 2c were done properly: a RED commit with the failing count recorded in its message, then the GREEN implementation.
- **`d90fdba` was committed with the plugin suite red** — the ingest arming-surface counts were stale. Found by running the plugin suite immediately after, fixed in `43b0d70`. Disclosed rather than folded into an amend.
- **Task 2 was split into 2a/2b/2c**, none of which is a boundary the plan draws, to keep each dispatch's committed work green. No acceptance criterion or `must_have` changed.

**Total deviations:** 3 auto-fixed Rule 1 bugs + 5 plan-text corrections + 2 named behavioural changes + 3 process deviations.
**Impact on plan:** the three Rule 1 fixes each close a real, previously-shippable failure — two hangs and one silent data loss on the primary armed path. No scope creep: every fix stayed inside this plan's `files_modified`.

## Issues Encountered

`Build Response Merge` now declares **15** inputs and `Ingest Merge Response` **5**. n8n's own `numberInputs` property is documented as 2-10. The repo already shipped 11 before this plan (D-70-07's `Build Refusal Row`), so this crosses no new line, but it widens an existing exposure: a `numberInputs` above the documented ceiling has never been observed rendering or validating on the live instance. Worth a look during the first deploy of this build — noted here rather than filed, since it is a property of the pre-existing design this plan extended, not a defect this plan introduced.

## User Setup Required

None — no external service configuration required. Nothing deployed, nothing bounced, nothing armed. Every `ALLOW_HUBSPOT_*` flag reads `"false"` in every committed workflow (verified by direct grep: zero `"true"` occurrences across all `n8n/wf_*.json`).

## Next Phase Readiness

Ready for **70-06** (client side, file-disjoint from this plan).

Carried forward:

- **Gate 70-05-A** in `70-DEFERRED-GATES.md` — the first armed, mixed-verdict batch must be observed on the real engine. The walker proved the fix; the walker's own comment says its Merge model is a spec, not n8n's multi-wave behaviour, and this phase's thesis is runtime truth.
- **The committed JSON is ahead of the live instance again.** Per CLAUDE.md §13.0.2's running record: the instance was level as of the 2026-09-09 disarmed deploy; this plan's four regenerated workflows are committed and NOT deployed.
- **D-70-13 lane-wide** — companies lose their domain-allowlist path on review writebacks. An operator decision, flagged not resolved.
- **`Associate Lane Sentinel` is an arming surface.** Any manual arm must rewrite it with the gates.

## Self-Check: PASSED

- Every file in `key-files.modified` exists on disk (`[ -f ]` over all 30 paths).
- `git log --oneline --all --grep="70-05"` returns 15 commits from `0350531..HEAD`; `commits: 15` is measured via `git rev-list --count 0350531..HEAD`, not narrated.
- Acceptance criteria re-run at close: `node --test tests/n8n/*.test.mjs` → 1032 pass / 0 fail; `.venv/bin/python -m pytest tests/ -q` → 1795 passed, 149 skipped; `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` → 2849 passed, 5 skipped; generation is idempotent (regenerate → byte-identical JSON); zero `ALLOW_HUBSPOT_* = "true"` across every committed workflow.

---
*Phase: 70-one-merge-one-result-channel-n8n-runtime-truth*
*Completed: 2026-09-10*
