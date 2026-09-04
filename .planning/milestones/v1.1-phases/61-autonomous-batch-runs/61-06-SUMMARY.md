---
phase: 61-autonomous-batch-runs
plan: "06"
subsystem: autonomy
tags: [n8n, association, write-grant, held-queue, hubspot, checkpoint, substrate-3, scale-up]

requires:
  - phase: 61-autonomous-batch-runs
    provides: "61-04's outcome contract/confidence table/held_queue.py; 61-05's async run handle and deployed substrate-1 backend"
provides:
  - "wf_enrichment_cloud's contacts-create path never lands unassociated — one operational implementation of the 2026-08-25 association rule (the contact-upload ingest lane), not two"
  - "Adapt Company Create (new node): a same-run company create's id is captured and joined to its planned dependency by value (REVIEW-C17)"
  - "preingest.py: assign_same_run_company_ids (no second search), classify_company_resolution_hold (bounded lag, 3 attempts), ingest_response_needs_hold/hold_ingest_no_company (REVIEW-10: n8n cannot write held_queue.py, the client does)"
  - "Verified finding (no code change): write_grant.covers() already authorizes a same-run create via the domain named at grant-open time (REVIEW-11)"
  - "REVIEW-C16: the end-of-run account reads written_records_path(run_id), never the aggregating path-less load()"
  - "Substrate-3 self-referencing fan-out (Task 5, T-61-25): an off-by-default `scale_up` request flag on wf_enrichment_cloud, gated by IF Scale Up Route, dispatching to a detached self-referencing Execute Workflow node (Dispatch Self), depth-bounded two independent ways (forced scale_up:false on the child, and an internally-owned fan_depth counter checked both at the gate and inside the fan-out node itself)"
  - "chunking.dispatch_plan gains a scale_up=False keyword (async_ack's own idiom) with structurally no client-side depth/fan_depth parameter to forge"
  - "scripts/prove_scale_up_runtime.py: the disarmed live-proof driver, gated and instance-guarded, proven live against the real deployed workflow (executions 12044-12047) — the self-reference RUNS, TERMINATES with no depth supplied, and stays correlatable"
  - "61-SCALE-UP-VERDICT.json: the runtime observations, the flag-off byte-identity measurement (envelope + graph diff), and the listed-vs-billed limit stated explicitly"
affects: []

actuals:
  tokens: 18900
  tasks: 5
  commits: 8

tech-stack:
  added: []
  patterns:
    - "A lane with no resolution/association mechanism refuses the write outright (downgrades to review) rather than growing a second, driftable copy of a rule that already lives in one place"
    - "Same-run cross-lane id propagation by value (client captures a create's own response, assigns it onto sibling rows) instead of a second search — eliminates the need for a wait/retry loop in the common case"
    - "A verified-no-defect finding, pinned by a test over the real functions, is a legitimate Task output — not every reviewer-flagged gap needs a code change"
    - "A third request-level opt-in boolean, normalized in Parse HubSpot Event with an envelope+event-fallback idiom, is a REUSED pattern (recompute, async_ack, scale_up), not a new mechanism each time"
    - "A workflow's own name/id is a valid self-reference target for Execute Workflow — deploy-time rebind_subworkflow_refs resolves it via the SAME live name->id map every other cross-workflow reference uses, with zero self-ref special-casing, because the workflow already exists live"
    - "A runOnceForAllItems Code node MUST iterate $input.all() to process every item in a batch — a bare $json only ever sees the first item, a real bug this task's own live runtime proof caught rather than merely asserting the mechanism on paper"

key-files:
  created:
    - tests/n8n/pairPipelineAssociationFlow.test.mjs
    - operator-claude-plugin/tests/test_unattended_pair_composition.py
    - tests/n8n/scaleUpFanOutFlow.test.mjs
    - operator-claude-plugin/tests/test_scale_up_runtime.py
    - scripts/prove_scale_up_runtime.py
    - .planning/phases/61-autonomous-batch-runs/61-SCALE-UP-VERDICT.json
  modified:
    - scripts/build_cloud_workflows.py
    - n8n/wf_enrichment_cloud.json
    - operator-claude-plugin/scripts/preingest.py
    - operator-claude-plugin/scripts/write_grant.py
    - operator-claude-plugin/scripts/chunking.py
    - operator-claude-plugin/tests/test_write_grant.py
    - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
    - operator-claude-plugin/.claude-plugin/plugin.json
    - operator-claude-plugin/CHANGELOG.md
    - tests/test_remaining_credits_response.py
    - tests/n8n/asyncAck.test.mjs
    - tests/test_subworkflow_ref_rebinding.py

key-decisions:
  - "Task 1: rather than duplicate the ingest lane's resolve+associate subgraph inside wf_enrichment_cloud (a second, driftable copy of the 2026-08-25 rule), an armed contacts-create on that lane is downgraded to review with a reason pointing at the contact-upload ingest lane, which already owns the one implementation. Measured first: enrich-before-ingest's own real writes already route through the ingest lane exclusively (step 7's dispatch.dispatch -> hubspot/contact-upload); the enrichment webhook is only ever called in mode:propose (return-only) for this flow's waterfall preview. This closes a real-but-currently-unreachable gap (any other caller of wf_enrichment_cloud with object_type:contacts and a genuine write mode) without adding a second implementation."
  - "Task 2: HIGH-12/REVIEW-12's subtraction taken as specified — a same-run company create's own id is carried forward by value via the new Adapt Company Create node + preingest.assign_same_run_company_ids, eliminating the search/wait for that common case entirely. The residual (a create-evidenced zero-hit search) is bounded to LAG_RETRY_LIMIT=3 attempts via a pure, caller-tracked counter — no sleep, no while loop, watch.py remains the sole poll site."
  - "Task 3: REVIEW-11 verified against the real write_grant.covers() rather than assumed. covers() checks record_ids and record_domains symmetrically (an AND across both, not an OR) -- a send that names a same-run create's own brand-new id still refuses even when its domain is granted. But this skill's own calling convention never passes an id for a record that has none yet (SKILL.md: record_ids=<this send's ids> is empty for such a row); it expresses the send by domain, which was already confirmed at step 2 before the grant opened. No production change to write_grant.py's scope logic was needed -- documented via a comment plus two tests over the real function."
  - "Task 4: the operator accepted the offline pipeline and explicitly authorized Task 5's continuation, including a second disarmed deploy carrying Tasks 1-3 live (approved 2026-08-30, 'approved — holding for Phase 57, continue to Task 5'). What stays held for Phase 57 is unchanged: the armed, credit-spending unattended batch."
  - "Task 5: fan-out is spliced as a re-pointed edge (Parse HubSpot Event -> IF Scale Up Route -> [fan-out lane] / [today's IF Object Type Supported]), not a 4th unconditional fan target mirroring Build Async Ack — an unconditional target would have let a fanned row ALSO run the parent's own business chain, double-processing an armed request. This is the one disclosed re-point; the false lane reaches IF Object Type Supported unchanged."
  - "Task 5: self-reference resolves via the SAME rebind_subworkflow_refs name-based lookup every other cross-workflow Execute Workflow node uses (SJ-3's own precedent) — no special-casing, because the workflow already exists live from 61-05's substrate-1 deploy. Dispatch targets the existing 'Execute Workflow Trigger' entry point (added in fix(40)/WINDOWS.md #3 specifically because a Webhook-only entry point 400s an Execute Workflow caller) rather than inventing a second entry point."
  - "Task 5: termination is two independent stops (T-61-25) — the dispatched child's scale_up is forced false regardless of what the original caller sent, AND an internally-owned fan_depth counter is checked both by the native IF gate and, a second time, inside the fan-out Code node itself. Neither stop depends on the other being correct."
  - "Task 5 (Rule 1, found live): Build Scale Up Fan-Out/Build Scale Up Ack were rewritten from a bare-$json single-item read (Build Async Ack's own shape, never exercised past 1 item live before this) to $input.all().filter().map() — the established multi-item idiom this file already uses elsewhere (ENRICH_SKIP_NOOP_JS, ENRICH_SJ3_BUILD_DISPATCH_EVENT). The bug was caught by this task's OWN disarmed runtime proof (execution 12042: a 2-record batch fanned out only 1 child), fixed, redeployed, and re-proven successfully (executions 12044-12047)."

requirements-completed: [RUN-02, AFTER-02]

coverage:
  - id: D1
    description: "An armed create on wf_enrichment_cloud's contacts branch is held for review with a reason, never landed unassociated; a batch-shaped flow test over the ingest lane's own committed jsCode proves resolved/held/update in one call"
    requirement: RUN-02
    verification:
      - kind: unit
        ref: "tests/n8n/pairPipelineAssociationFlow.test.mjs"
        status: pass
      - kind: unit
        ref: "tests/n8n/companyAssociationFlow.test.mjs"
        status: pass
      - kind: unit
        ref: "tests/n8n/contactCreateGateFlow.test.mjs"
        status: pass
    human_judgment: false
  - id: D2
    description: "Adapt Company Create captures a same-run company create's id by value; preingest.py coalesces several contacts naming the same new company onto that id with no second search; a genuinely absent company holds immediately; a create-evidenced zero-hit is bounded to 3 attempts before holding with a lag-naming reason; an n8n-held row lands in the local held_queue with its reason"
    requirement: RUN-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_unattended_pair_composition.py"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_report_sufficiency.py::test_no_plugin_script_polls_sleeps_or_loops_on_execution_status"
        status: pass
    human_judgment: false
  - id: D3
    description: "One grant authorizes the documented sequence including a same-run create via domain scoping, verified against the real grant functions; a resumed run gets a fresh grant; the end-of-run account is scoped to written_records_path(run_id), never the aggregating load()"
    requirement: AFTER-02
    verification:
      - kind: unit
        ref: "operator-claude-plugin/tests/test_write_grant.py::test_covers_admits_a_same_run_create_via_the_domain_named_at_grant_time"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_unattended_pair_composition.py::test_the_end_of_run_account_after_two_runs_shows_only_the_second_runs_records"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_skill_sequence_coverage.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "Task 4 checkpoint: accept the offline pipeline, hold the first live unattended run for Phase 57 (D-61-08). Resolved 2026-08-30: operator approved and authorized Task 5's continuation."
    verification: []
    human_judgment: true
    rationale: "A blocking human-verify checkpoint by design (gate=\"blocking\") -- the operator read the route decision, confirmed the regenerated diff carried only the named nodes, and explicitly accepted holding for Phase 57 while authorizing Task 5's own disarmed deploy+proof."
  - id: D5
    description: "Substrate-3 self-referencing fan-out integrated behind an off-by-default scale_up flag, proven at RUNTIME (not merely publish-viable) on the real deployed workflow: the self-reference RUNS (two detached children, both success), TERMINATES with no depth supplied (the depth guard stopped recursion; zero grandchildren), and remains correlatable (both child execution ids found as exact tokens in the parent's own Dispatch Self output). Zero HubSpot writes, zero provider calls, zero Anthropic calls in either proof run. Flag-off byte-identity measured precisely (envelope: dict-equality test; graph: exactly 4 added nodes, 0 removed, 1 disclosed re-pointed edge, 87 pre-existing nodes differing only in a cosmetic internal id)."
    requirement: RUN-02
    verification:
      - kind: unit
        ref: "tests/n8n/scaleUpFanOutFlow.test.mjs"
        status: pass
      - kind: unit
        ref: "operator-claude-plugin/tests/test_scale_up_runtime.py"
        status: pass
      - kind: live
        ref: ".planning/phases/61-autonomous-batch-runs/61-SCALE-UP-VERDICT.json (executions 12044-12047, disarmed)"
        status: pass
    human_judgment: false

duration: this session
completed: 2026-08-30
status: complete
---

# Phase 61 Plan 06: Offline Pair Pipeline + Substrate-3 Scale-Up Proof Summary

**All five tasks executed and committed. Tasks 1-3 close the unassociated-create gap, carry a
same-run company create's id forward by value, and verify (rather than assume) that one grant
covers what a batch creates. Task 4's blocking checkpoint was resolved by the operator
2026-08-30 ("approved — holding for Phase 57, continue to Task 5"). Task 5 integrates the
substrate-3 scale-up fan-out behind an off-by-default flag and proves it at RUNTIME against the
real deployed workflow — including finding and fixing a real Rule 1 bug (a multi-record batch
silently fanning out only its first row) via the proof's own first live attempt.**

## Performance

- **Tasks:** 5/5 complete
- **Files modified:** 12 modified, 6 created (see key-files)
- **Commits:** 8 (Task 1 feat; Task 2 test+feat as TDD RED/GREEN; Task 3 docs; Task 4 checkpoint-pause docs; Task 5 feat + fix + feat)

## Accomplishments

### Task 1 — Close the unassociated-create gap (or route through the lane that has it)

`wf_enrichment_cloud`'s own contacts branch (`Decide Action`, the enrichment lane) has
no company-resolution or association mechanism at all — CLAUDE.md §13.0.1's own closing
sentence names this gap. Measured before choosing a route: `enrich-before-ingest`'s real
HubSpot writes for contacts already go through the ingest lane exclusively
(`dispatch.dispatch` → `hubspot/contact-upload`, step 7 of the skill); the enrichment
webhook is only ever called in `mode: propose` (return-only) for this flow's waterfall
preview at step 5. So the "route creates through the ingest lane" instruction is already
this flow's real architecture — what remained was closing the *unreachable-but-real*
path: any other caller that could reach `wf_enrichment_cloud` with `object_type:
contacts` and an armed write. That create now downgrades to `review` with an explicit
reason pointing at the contact-upload ingest lane, rather than growing a second copy of
the association rule. One operational implementation of the rule (the ingest lane)
remains; the enrichment lane simply refuses to complete a create it cannot associate.

`tests/n8n/pairPipelineAssociationFlow.test.mjs` (new) drives a three-row batch — a
resolved create, an unresolved create, and an update — through the ingest lane's own
committed `Decide Action`/`Build Association Request`/`Build Ingest Response` jsCode in
ONE call. The load-bearing assertion is the second row: held, with its reason, never
landed unassociated.

### Task 2 (TDD) — Carry a same-run company create's id forward by value

REVIEW-12/HIGH-12's subtraction, taken as specified: HubSpot's company-create response
already returns the authoritative id, so waiting for the search index to catch up is
strictly worse (slower AND ambiguous — a zero-hit search cannot distinguish lag from
absence, from a failed create, from the wrong lookup key — CLAUDE.md §13.0.1's Harness
Racing NSW case, execution `11922`, is the last of those and is NOT lag).

- **`Adapt Company Create`** (new node, companies branch of `wf_enrichment_cloud`,
  spliced between `HubSpot Company Create` and the shared `Build Response`
  convergence): joins the create RESPONSE back to its planned dependency BY VALUE —
  the domain `Decide Company Action` seeded onto the create's own properties (BUG 19),
  which HubSpot's create response echoes back — emitting
  `{company_dependency_id, company_id}`. This is the ONE named capture point
  (REVIEW-C17); `Build Response`'s existing `...row` spread (61-04 Task 1) carries both
  fields to the client for free, with no second serialization point.
- **`preingest.index_company_dependencies`/`assign_same_run_company_ids`**: the client
  side of the same mechanism. Several contacts naming the identical new company coalesce
  onto the one create's returned id; a row with no matching dependency, or one that
  already carries a `company_id`, is left untouched.
- **`preingest.classify_company_resolution_hold`**: what remains after the subtraction —
  a genuinely absent company (no create evidence at all) holds IMMEDIATELY, whatever
  `attempt` is; only a row this run has durable create evidence for may ever be read as
  lag, and even then for only `LAG_RETRY_LIMIT = 3` attempts (a pure, caller-tracked
  counter — no sleep, no while loop; `watch.py` stays the sole poll site) before it too
  holds, with a reason naming the lag rather than absence.
- **`preingest.ingest_response_needs_hold`/`hold_ingest_no_company`** (REVIEW-10): n8n
  cannot write `held_queue.py`'s file (it runs on someone else's machine), so the ingest
  lane RETURNS the hold on its response (`association: "none"` + `reason`, already the
  contract vocabulary) and the client parses it and writes the queue entry. Reuses
  `confidence.HOLD_NO_MATCH` — this plan does not touch `confidence.py`'s vocabulary.

RED commit (`f3fbe2b`) confirmed 9 failures (`AttributeError`) before any of the five new
`preingest.py` functions existed; GREEN commit (`9355d82`) implements them plus the
builder change, and updates `test_remaining_credits_response.py`'s frozen inbound-edges
guard for `Build Response` (a disclosed, direct consequence of the new node, same shape
as 61-04's own guard-test update).

### Task 3 — One grant across the whole lane, verified not to need widening

REVIEW-11 ("one grant is documentation-only") was PART REJECTED, PART a real find, and
this task resolved both halves:

- **Rejected half, confirmed real code, not prose**: `write_grant.plan_grant(lanes=[...])`
  already opens a grant spanning both lanes in one call; `open_grant`'s `_consequence()`
  branch already states the two-lane consequence; `authorize_send`/
  `authorize_ungranted_send` already route every send through it.
- **The real find, verified rather than assumed**: `covers()` refuses any id/domain
  absent from the grant's OWN `record_ids`/`record_domains` at the moment it opened, and
  a company or contact CREATED during the batch has an id that could not have existed
  then. Verified directly against the real function
  (`test_covers_admits_a_same_run_create_via_the_domain_named_at_grant_time`,
  `test_covers_still_refuses_a_domain_never_named_at_grant_time`): `covers()` checks
  `record_ids` AND `record_domains` — a send that ALSO names the create's own brand-new
  id still refuses even with a covered domain. But this skill's own calling convention
  never does that — SKILL.md's `record_ids=<this send's ids>` is empty for a record with
  no id yet, and the send is expressed by the domain the operator already confirmed at
  step 2, before the grant opened. **No production change to `covers()`'s scope logic
  was needed** — the finding is documented (a comment in `write_grant.py`, prose in
  `SKILL.md`) and pinned by tests over the real function, exactly as the plan's own
  "record the measurement and change nothing" escape hatch anticipates.
- **A resumed run gets a fresh grant, always** — documented in SKILL.md and verified
  structurally: `run_manifest.py`'s and `held_queue.py`'s own on-disk documents can never
  carry a grant-shaped object (GRANT-06), so there is nothing for a resume to read back.
- **REVIEW-C16**: the end-of-run account now reads
  `written_records.load(path=written_records.written_records_path(run_id))`, never the
  path-less `load()` (which aggregates every historical run). Both `written_records.py`
  functions already existed; only the composition test needed writing.
  `test_unattended_pair_composition.py::test_the_end_of_run_account_after_two_runs_shows_only_the_second_runs_records`
  proves scoping directly against two real runs' artifacts.
- `enrich-before-ingest/SKILL.md` gained prose (no new fenced python code block, to
  avoid tripping `test_skill_sequence_coverage.py`'s unregistered-sequence ratchet) citing
  all of the above by name. `plugin.json` bumped 0.32.0 → 0.33.0; `CHANGELOG.md` updated
  in the same commit.

### Task 4 — Checkpoint resolved

Operator resolution, 2026-08-30: "approved — holding for Phase 57, continue to Task 5."
The operator accepted the offline pipeline (Tasks 1-3, undeployed at the time of the
checkpoint) and explicitly authorized what Task 5 required in advance: a second disarmed
deploy carrying Tasks 1-3 live (needed because Task 5's own runtime proof requires the
built workflow to actually be deployed), plus the disarmed runtime proof itself. What
stays held for Phase 57 (D-61-08) is unchanged and was restated in the resolution: the
armed, credit-spending, unattended batch. No such run happened in this plan.

### Task 5 — Substrate-3 scale-up fan-out, integrated and proven at runtime

**Design.** A third request-level opt-in boolean, `scale_up`, normalized in `Parse
HubSpot Event` with the identical envelope+event-fallback idiom `recompute`/`async_ack`
already established — "a pattern, not an invention" (the plan's own words). Unlike
`async_ack` (an unconditional 3rd-to-4th fan target that never changes the main route),
`scale_up` had to be spliced as a **re-pointed edge**: `Parse HubSpot Event` now feeds
`IF Scale Up Route` first (instead of `IF Object Type Supported` directly); that gate's
FALSE lane reaches `IF Object Type Supported` unchanged (today's path, one extra
pass-through hop), and its TRUE lane (is-fanning) diverts to `Build Scale Up Fan-Out` ->
`Dispatch Self` -> `Build Scale Up Ack` -> `Respond to Webhook`, bypassing the main
business chain entirely — an unconditional 4th fan target (mirroring `Build Async Ack`)
would have let a fanned row ALSO run the parent's own writes, double-processing an armed
request. This is the ONE disclosed re-point.

**Self-reference, for free.** `Dispatch Self` (Execute Workflow, mode=`each`,
`waitForSubWorkflow: false` — P-13's proven detached shape) targets the workflow's OWN
name/id (`LVenrichmentCloud01`/`LV Enrichment (Cloud template)`). Deploy-time
`rebind_subworkflow_refs` resolves any Execute Workflow node's `cachedResultName` against
a fresh live name→id map — since this workflow already exists live (61-05's substrate-1
deploy), its own name already resolves to its own live id via the exact same mechanism
SJ-3's cross-workflow dispatch already uses, with **zero self-ref special-casing**. The
dispatch enters via the existing `Execute Workflow Trigger` entry point (added in
fix(40)/WINDOWS.md #3 for the documented reason that a Webhook-only entry point 400s an
Execute Workflow caller with "Missing node to start execution") rather than inventing a
second one.

**Termination, two independent stops (T-61-25).** The dispatched child's `scale_up` is
forced `false` regardless of what the original caller sent, AND an internally-owned
`fan_depth` counter (never accepted from the client — `chunking.dispatch_plan` has no
`fan_depth`/`depth` parameter to forge, asserted structurally) is checked BOTH by the
native `IF Scale Up Route` gate and, independently, a second time inside `Build Scale Up
Fan-Out`'s own code. Neither stop depends on the other being correct. Asserted directly,
offline: a fan-out invoked with genuinely no depth supplied (`fan_depth: undefined`, not
a stand-in) still stops after exactly one hop, even if the resubmitted child's own body
is fed back in and `scale_up` is forged back to `true`.

**Rule 1 bug found and fixed by the proof itself.** The FIRST live disarmed attempt
(executions 12041-12043 — 12040 belongs to 61-05's own prior proof, a different task, not
this one) sent a 2-synthetic-row batch with `scale_up:true` and observed
only ONE child dispatched instead of two — both `Build Scale Up Fan-Out` and `Build Scale
Up Ack` were written as `runOnceForAllItems` Code nodes reading a bare `$json`, which only
ever sees the FIRST of however many input items such a node receives (the exact shape
`Build Async Ack` already carries, never exercised past 1 item live before this). Fixed to
`$input.all().filter().map()`, matching this file's own established multi-item precedent
(`ENRICH_SKIP_NOOP_JS`, `ENRICH_SJ3_BUILD_DISPATCH_EVENT`), redeployed, and re-proven.

**Runtime proof, successful (executions 12044-12047, disarmed: `mode:"propose"` +
`providers:[]` over 2 synthetic company rows, zero HubSpot writes, zero provider calls,
zero Anthropic calls).** Parent execution `12045` reached `Dispatch Self` and dispatched
TWO detached children (`12046`, `12047`), both `status: success`, both reaching only
read-only nodes (`Company Gate`/`HubSpot Company Fetch By Id` — a search, never a write).
Zero grandchildren — the depth guard stopped recursion with no `fan_depth` ever supplied
by the proof's own request. Both child execution ids found as exact tokens in the
parent's own `Dispatch Self` runData (correlatable, P-13's mechanism). Substrate-1
comparison batch (execution `12044`, `scale_up` omitted) ran the ordinary single-execution
path unchanged. Instance confirmed clean afterward: 5 workflows total, 0 `ZZ-`-prefixed
leftovers (this proof fires the real production workflow, not a throwaway probe workflow
— there was nothing to sweep beyond confirming no stray workflow existed).

**Flag-off byte-identity, measured precisely, not assumed.** Envelope:
`test_scale_up_runtime.py::test_omitting_scale_up_sends_the_byte_identical_envelope_every_existing_caller_sends_today`
proves `dispatch_plan`'s output with `scale_up` omitted is byte-identical to today's, and
carries no `scale_up` key at all. Graph: exactly 4 nodes added, 0 removed, 1 disclosed
re-pointed edge, and ONE genuinely-changed existing node (`Parse HubSpot Event`'s own
jsCode, behaviourally a no-op absent opt-in). The remaining 87 "changed" nodes in a naive
diff differ ONLY in their own internal `nid()`-generated id (a cosmetic consequence of the
build's sequential id counter being offset by the 4 new nodes' `nid()` calls) — verified
directly by excluding the `id` field from the comparison and confirming byte-identity of
every other field. Full measurement recorded in `61-SCALE-UP-VERDICT.json`.

**The listed-vs-billed limit is stated, not glossed over.** The verdict counts what
`GET /api/v1/executions` LISTED. What was actually BILLED against the 2,500/month
allowance is a separate question this repo has never been able to observe from an API
key (P-10's standing residual, carried forward explicitly rather than quietly closed).

**Scope discipline.** MAX_EVENTS (the events-per-request ceiling: 2 for write mode, 20
for propose) is UNCHANGED by this task — `scale_up` does not yet unlock larger batches at
the client's own request-shaping layer; it proves the DISPATCH MECHANISM at small scale.
Unlocking larger batches is deliberately left for whenever this path is actually put to
production use, after Phase 57's ceilings land. This is explicitly NOT D-61-08's gated
live unattended run: disarmed, synthetic rows, nothing armed, zero writes.

## Task Commits

1. **Task 1: Close the association gap, or route through the lane that has it** — `6002c61` (feat)
2. **Task 2 RED: failing tests for same-run company id coalescing** — `f3fbe2b` (test)
3. **Task 2 GREEN: carry a same-run company create forward by value** — `9355d82` (feat)
4. **Task 3: one grant covers what the batch creates, verified not widened** — `a58fddd` (docs)
5. **Task 4: pause at checkpoint** — `e144bf1` (docs)
6. **Task 5: integrate substrate-3 scale-up fan-out (offline half)** — `4a52243` (feat)
7. **Task 5: fix Build Scale Up Fan-Out/Ack to iterate $input.all() (Rule 1, found live)** — `7682e97` (fix)
8. **Task 5: disarmed runtime proof, executions 12044-12047** — `c1980f0` (feat)

## Files Created/Modified

- `scripts/build_cloud_workflows.py` — Task 1's contacts-create downgrade in
  `ENRICH_DECIDE_CLOUD`; Task 2's `ADAPT_COMPANY_CREATE` node + wiring; Task 5's
  `scale_up`/`fan_depth` normalization, `IF Scale Up Route`, `Build Scale Up Fan-Out`,
  `Dispatch Self`, `Build Scale Up Ack`, and `_execute_workflow_node`'s new
  `wait_for_sub` kwarg
- `n8n/wf_enrichment_cloud.json` — regenerated (the only one of eight workflow JSONs
  that changed across all five tasks — no other lane's builder output was touched)
- `operator-claude-plugin/scripts/chunking.py` — Task 5's `scale_up=False` kwarg on
  `dispatch_plan`, mirroring `async_ack`, no depth parameter
- `scripts/prove_scale_up_runtime.py` (new) — Task 5's disarmed live-proof driver,
  gated (`ALLOW_SCALE_UP_PROOF`) and instance-guarded like every other live script
- `tests/n8n/pairPipelineAssociationFlow.test.mjs` (new) — Task 1's batch-shaped flow
  test over the ingest lane's committed jsCode
- `tests/n8n/scaleUpFanOutFlow.test.mjs` (new) — Task 5's topology + depth-guard
  termination proof, offline
- `operator-claude-plugin/tests/test_scale_up_runtime.py` (new) — Task 5's client-side
  proof (flag-off byte identity, no depth knob, five-bucket invariant)
- `.planning/phases/61-autonomous-batch-runs/61-SCALE-UP-VERDICT.json` (new) — Task 5's
  runtime observations
- `operator-claude-plugin/scripts/preingest.py` — Task 2's five new functions
  (`index_company_dependencies`, `assign_same_run_company_ids`,
  `classify_company_resolution_hold`, `ingest_response_needs_hold`,
  `hold_ingest_no_company`), `LAG_RETRY_LIMIT = 3`
- `operator-claude-plugin/scripts/write_grant.py` — Task 3's verified-finding comment on
  `covers()`; no behavior change
- `operator-claude-plugin/tests/test_unattended_pair_composition.py` (new) — Task 2 and
  Task 3's composition tests, driving the real functions with only the n8n response
  shape/transport synthesized
- `operator-claude-plugin/tests/test_write_grant.py` — Task 3's two new domain-scoping
  tests over the real `covers()`
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — Task 3's one-grant/
  fresh-resume-grant/scoped-account prose, inserted after step 1's existing grant
  exception paragraph
- `operator-claude-plugin/.claude-plugin/plugin.json`,
  `operator-claude-plugin/CHANGELOG.md` — 0.32.0 → 0.33.0
- `tests/test_remaining_credits_response.py` — `BUILD_RESPONSE_SOURCES` updated for
  the new `Adapt Company Create` node (disclosed deviation, see below)
- `tests/n8n/asyncAck.test.mjs` — Task 5's one disclosed pin update: `Parse HubSpot
  Event`'s first fan target is now `IF Scale Up Route`, not `IF Object Type Supported`
- `tests/test_subworkflow_ref_rebinding.py` — Task 5's re-anchoring (the "no
  executeWorkflow nodes" example workflow moved from `wf_enrichment_cloud.json`, which
  now legitimately carries one, to `wf_contact_ingest_cloud.json`) plus a new test
  pinning the self-reference's own live-name resolution

## Decisions Made

See `key-decisions` in frontmatter. Summarized: Task 1 closes the gap by refusal rather
than duplication, measured against this flow's real dispatch paths first; Task 2 takes
the reviewers' subtraction as specified, with a small, bounded, pure-function residual
for the one case that cannot be eliminated; Task 3 verifies REVIEW-11's premise against
the real code and finds no defect to fix, recording the finding rather than inventing a
change; Task 4's checkpoint was resolved by explicit operator authorization covering
both the deploy and the proof; Task 5 splices the fan-out as a re-pointed edge (not an
unconditional 4th fan target) to avoid double-processing, reuses the existing
cross-workflow self-reference and entry-point mechanisms with zero special-casing, bounds
termination two independent ways, and fixes a real multi-item bug its own live proof
caught.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical] `test_remaining_credits_response.py`'s frozen
`Build Response` inbound-edges guard needed updating for the new `Adapt Company Create`
node**
- **Found during:** Task 2's own full-suite verification run, immediately after
  regenerating the workflow
- **Issue:** `test_build_response_is_reachable_from_every_terminal_branch` pins the
  EXACT set of nodes feeding `Build Response` — `("HubSpot Company Create", 0)` was one
  of them, and Task 2 deliberately re-points that edge through the new adapter.
- **Fix:** Updated the expected set to `("Adapt Company Create", 0)` in place of
  `("HubSpot Company Create", 0)`, with a comment explaining why, mirroring 61-04's own
  precedent for this exact test file's evolution.
- **Files modified:** `tests/test_remaining_credits_response.py`
- **Verification:** `.venv/bin/python -m pytest -q` — full suite green (3527/154 after
  Task 2; the failure was reproduced first, then fixed).
- **Committed in:** `9355d82` (Task 2 GREEN commit)

---

**2. [Rule 1 - Bug] `Build Scale Up Fan-Out`/`Build Scale Up Ack` silently dropped every
item after the first in a multi-record batch**
- **Found during:** Task 5's OWN first disarmed live runtime proof (execution `12042`)
  — a 2-synthetic-row `scale_up:true` request fanned out only 1 child instead of 2.
- **Issue:** both nodes were written as `runOnceForAllItems` Code nodes reading a bare
  `$json`, which n8n only binds to the FIRST of however many input items such a node
  receives — the exact single-item shape `Build Async Ack` already carries in this
  codebase, never exercised past 1 item live before this proof.
- **Fix:** rewrote both to `$input.all().filter().map()`/`.map()`, matching this file's
  own established multi-item idiom (`ENRICH_SKIP_NOOP_JS`, `ENRICH_SJ3_BUILD_DISPATCH_
  EVENT`). Updated `tests/n8n/scaleUpFanOutFlow.test.mjs`'s own test harness for these
  two nodes to the multi-item `$input.all()` shim (`companyAssociationFlow.test.mjs`'s
  own pattern) and added a dedicated multi-item test.
- **Files modified:** `scripts/build_cloud_workflows.py`, `n8n/wf_enrichment_cloud.json`,
  `tests/n8n/scaleUpFanOutFlow.test.mjs`
- **Verification:** offline suites green (3539/154, 844/844); redeployed and re-proven
  live (executions 12044-12047, both children ran, zero grandchildren, both correlate).
- **Committed in:** `7682e97`

**3. [Rule 1 - Bug] the proof driver's own "latest execution" read could silently pick
up a CHILD instead of the PARENT**
- **Found during:** the same first live attempt (execution `12043` — its `mode` was
  `"integrated"`, i.e. a detached child, not the `"webhook"`-mode parent the script
  meant to inspect).
- **Issue:** `scripts/prove_scale_up_runtime.py`'s original `_latest_execution` took
  `rows[0]` from a plain executions list unconditionally; a detached child can complete
  before or interleave with its own parent in list ordering.
- **Fix:** `_latest_webhook_execution` filters explicitly on `mode == "webhook"`; child
  ids are now extracted by structured JSON traversal of `Dispatch Self`'s own runData
  (`metadata.subExecution.executionId`) rather than a raw-text id scan against a
  candidate list.
- **Files modified:** `scripts/prove_scale_up_runtime.py`
- **Verification:** the corrected script's second live run correctly identified parent
  `12045` and children `12046`/`12047`.
- **Committed in:** `c1980f0`

---

**Total deviations:** 3 auto-fixed (1x Rule 2, 2x Rule 1) — the two Task 5 deviations
are direct, disclosed consequences of the task's own disarmed runtime proof doing its
job: catching a real defect rather than merely asserting the mechanism on paper. No
scope creep.

## Issues Encountered

None blocking. One design correction mid-Task-3 (see prior summary): an initial draft of
the REVIEW-11 test assumed `covers()` treats `record_ids` and `record_domains` as
alternatives (an OR) — running it against the real function immediately falsified that.
Task 5's own runtime proof surfaced and fixed two real bugs (see Deviations above) rather
than encountering a blocking issue — this is exactly what a disarmed runtime proof is
for, distinguished from a blocking issue precisely because both were auto-fixable within
the task's own scope per Rule 1.

## Verification Against Plan's `<verification>` Block

- `node --test tests/n8n/*.test.mjs` (glob form) — **844/844 passed** (826 after Tasks
  1-3 + 18 new: 16 in the first `scaleUpFanOutFlow.test.mjs` cut, 2 more added with the
  multi-item Rule 1 fix; `asyncAck.test.mjs`'s one topology pin updated).
- `.venv/bin/python -m pytest -q` — **3539 passed, 154 skipped** (3532 after Tasks 1-3 +
  7 new: 6 in `test_scale_up_runtime.py`, 1 in `test_subworkflow_ref_rebinding.py`). The
  plan's own stated baseline of 3365/154 is stale, as the plan itself warns; the
  freshly-measured pre-Task-5 baseline (3532/154) is what this delta is against.
- `.venv/bin/python -m pytest operator-claude-plugin/tests -q` — subsumed by the
  full-repo run above.
- The poll-loop guard (`test_no_plugin_script_polls_sleeps_or_loops_on_execution_status`)
  passes unchanged — no new sleep/while/`import time` in any plugin script (Task 5's
  live driver lives in root `scripts/`, outside the guard's scanned directory, exactly
  as the guard's own design intends for a live-proof driver that needs settle-time
  sleeps).
- Regenerated workflow JSONs: only `n8n/wf_enrichment_cloud.json` changed across all
  five tasks. The other seven are byte-identical to before this plan started.
- **Task 5 only (the disarmed runtime proof, after Task 4's checkpoint resolved):**
  live n8n executions were expected and observed — executions `12041`-`12043` (first
  attempt, both bugs found; `12040` is 61-05's own prior proof execution, a different
  task, and is not part of this count), `12044`-`12047` (second, successful attempt:
  substrate-1 comparison parent, scale_up parent, 2 detached children). **Total listed
  across both attempts: 7.** Substrate-1-vs-scale_up comparison, same 2-row batch:
  substrate 1 listed **1** execution (`12044`, inline, no fan-out); `scale_up:true`
  listed **3** (`12045` parent + `12046`/`12047` children) — more listed executions for
  the same 2 rows at this small scale, since a fan-out only pays off once billing/
  concurrency exemptions or the per-chunk ceiling actually bind, neither of which this
  proof's 2-row batch reaches (see `61-SCALE-UP-VERDICT.json`'s
  `substrate_1_vs_scale_up_comparison` field). Zero HubSpot writes, zero provider calls,
  zero Anthropic calls, nothing armed, in either attempt. Every proof ran against the
  real production workflow (no throwaway `ZZ-*` workflow to sweep); the instance was
  confirmed clean afterward (5 workflows total, 0 `ZZ-` leftovers). Flag-off
  byte-identity measured precisely (see Task 5's own section above and
  `61-SCALE-UP-VERDICT.json`'s `flag_off_byte_identity` field) rather than assumed. The
  listed-vs-billed limit is stated explicitly in the verdict's own `scope_boundary`.
- Zero live n8n, HubSpot, Anthropic or provider calls anywhere in Tasks 1-3 (unchanged
  from the prior summary). Task 5's offline half (the builder/test changes) is
  similarly zero-live; only Task 5's own dedicated runtime-proof step made live calls,
  and only the two POSTs and their associated read-only GETs described above.
- No assertion weakened, deleted, or reworded without a stronger replacement across the
  whole plan: Task 2's one guard-test line change (documented, a required edge gained,
  not lost); Task 5's `asyncAck.test.mjs` topology pin updated to name the new first fan
  target (`IF Scale Up Route` in place of `IF Object Type Supported`), which is a
  disclosed re-point, not a weakening — the assertion still pins an exact 3-element set.

## User Setup Required

None. Task 5's live half required only the credentials already documented for this
repo's other live scripts (`.env` via `set -a; source .env; set +a`, and
`config_gate.load_config()["webhook_secret"]` for the webhook secret) — no new setup.

## Next Phase Readiness

All five tasks are done, tested, and committed. The offline pair pipeline (association
enforcement, same-run company id propagation, one-grant verification) and the
substrate-3 scale-up path (integrated, off by default, proven at runtime) are both ready
for whenever a batch actually needs to scale past substrate 1's arithmetic. **The first
live unattended run remains gated on Phase 57's ceiling work (D-61-08)** — nothing in
this plan, including Task 5's disarmed proof, constitutes or authorizes that run. Phase
57 (RUN-05/AFTER-01/AFTER-03: per-run ceilings, refusal-before-start, post-run allowlist
proof) is the next phase this milestone needs.

---
*Phase: 61-autonomous-batch-runs*
*Completed: 2026-08-30*

## Self-Check: PASSED
