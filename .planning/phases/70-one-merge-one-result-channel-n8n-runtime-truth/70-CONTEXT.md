# Phase 70: One merge, one result channel — n8n runtime truth - Context

**Gathered:** 2026-09-09
**Status:** Ready for planning

<domain>
## Phase Boundary

A batch with two identity lanes and two actions returns every row once, from the write that
happened, on one client result channel — and the offline harness would have caught every
finding the 2026-09-09 UAT found.

This phase RETIRES an idiom, it does not patch more sites of it. The idiom: lanes fan out
(`IF Has Email` / `IF Linkedin Searchable` / `IF Name Searchable` / `IF Update` / `IF Create` /
`Set Review`) and reconverge on a Code node with no Merge; downstream nodes read upstream rows
by name (`$('Node').all()`, `.first()`, `.item`) because HTTP nodes replace `$json`; the webhook
answers with whichever lane fires `Respond` first, or with the first entry only; the client has
two result channels (sync body, async runData). Seven instances found so far (July research-lane
row loss, F1, F5, F5b, F10, F11, F12). The per-site fixes of 2026-09-09 (`0c42b18`, `995a689`,
`4d35812`, `fa447cc`, `8344b7a`, `nodeRunRecovery.js`) stay green until this phase replaces
them; several are explicitly removed by decisions below.

**In scope:** the n8n builder (`scripts/build_cloud_workflows.py`) and every workflow it
generates; the client result channel in `operator-claude-plugin` (`dispatch.py`, `watch.py`,
`chunking.py`, `written_records.py`, `preingest.py`, `report*.py`) and the repo scripts that
POST to the enrichment webhook; the write-gate contract across all three splice sites; the
offline harness under `tests/n8n/`; the UAT batch shape; the four folded todos.

**Out of scope:** confidence policy (a new person is held by design, D-61-03 — `ALL_HOLD_CODES`
and `min_confidence` untouched); named-account scoring; anything in the ICP engines
(`src/icp_scoring.py`, `Decide Company Action`'s veto block); the review-queue / review-
decision / backend-status endpoints' response shape (they stay body-responding queries, D-70-08);
the unattended gate (still shut). **Binding on all six (SAFE-01..05) applies unchanged; nothing
is armed during the phase.** Never hand-edit `n8n/wf_*.json`; every change goes through the
builder.

</domain>

<decisions>
## Implementation Decisions

### Convergence mechanism

- **D-70-01: An explicit Merge node at every convergence point.** Wherever two or more lanes
  feed one node today (`Enrichment Gate`, `Company Gate`, `Build Response`, `Build Ingest
  Response`, the write-gate fan-in), a Merge (append, N inputs) sits in front, so the converged
  node runs ONCE on all rows. `n8n/code/nodeRunRecovery.js` and its seven call sites are
  deleted, not kept as a fallback. Rejected: per-item `pairedItem` lineage (HTTP hops break it;
  `.item` is ambiguous across runs — observation 31305); keeping run recovery as a fenced idiom.
  — **Reversibility:** costly — every converged reader's jsCode changes from by-name to
  `$input`; undoing means reinstating run recovery at every site.
  *Load-bearing addendum from research 2026-09-09 (70-RESEARCH.md § D-70-02, Pitfall 1):
  a Merge in append mode "waits for the execution of all connected inputs", and an n8n lane
  that produces zero items NEVER executes — so a Merge with an un-fired input hangs the
  execution (`[documented]` + multiple dated community reports; not yet `[observed live]`).
  Every Merge input must therefore ALWAYS fire: enable "Always Output Data" on each
  lane-terminal node feeding a Merge (or emit an explicit sentinel row the Merge's consumer
  filters back out). The single-lane-only batch — the COMMON shape — is the hang case; it
  is a mandatory walker unit test (D-70-18) and a mandatory send in D-70-19's live run.*

- **D-70-02: `executionOrder` v1 flip is the RESEARCHER's call, after a doc check.**
  *RESOLVED by research 2026-09-09: do NOT flip to v1 in this phase. The Merge-input hang
  is independent of v0/v1; flipping would put a second all-five-workflows behaviour change
  into the same disarmed proof run. D-70-19's run logs `settings.executionOrder` from the
  live workflow body so the `[observed live]` upgrade lands on the setting the workflow
  actually ran with (absent/legacy). A v1 flip, if ever wanted, is its own later change.* Both live
  workflows run legacy v0 (`settings.executionOrder` absent on all five committed cloud
  JSONs). Merge behaviour when one lane never fires differs between v0 and v1. The researcher
  verifies from n8n's docs — under the setting the workflow will actually run with — whether a
  Merge with N inputs runs when some inputs never receive data, and recommends flip-or-design-
  around with the doc citation. This is a `[documented]`-tag fact per CLAUDE.md §13.0.3 until
  a disarmed live run observes it (D-70-19 is that observation). If the flip is recommended,
  the builder sets it on every generated workflow, not per-workflow.
  — **Reversibility:** one-way in effect — flipping v1 changes node ordering on all five live
  flows at once; a later revert is a second all-flows behaviour change.

- **D-70-03: Retire EVERY by-name read.** No `$('X')` of any form (`.all()`, `.first()`,
  `.item`, `.last()`) anywhere in generated jsCode or expressions — including the single-run
  reads of `Parse HubSpot Event` / `Set Config` (request-level flags are carried on the row).
  The builder has 23 distinct by-name read targets today. Rejected: retire only converged
  bare `.all()` and lint the rest; retire only the seven listed instances.
  — **Reversibility:** costly — touches every provider/HubSpot hop in three workflows.

- **D-70-04: Build-time assertion is the locked rule; researcher picks the carry.**
   `scripts/build_cloud_workflows.py` fails generation if any emitted jsCode or
  expression contains a `$('` read, and a test pins it against the committed JSON. How a row
  survives an HTTP hop without `$('Prev')` (HTTP Request nodes have no pass-through) is
  evaluated by the researcher against n8n Cloud limits — candidates named in discussion: Merge
  combine-by-position per hop (n8n-native, ~15–20 new nodes per workflow, relies on 1:1 item
  order incl. `continueOnFail`), HTTP inside Code via `this.helpers.httpRequest` (fewest
  nodes; credential reachability from Code on Cloud is UNVERIFIED), or another the researcher
  finds. The recommendation must state which candidate and why the others lost.
  *RESOLVED by research 2026-09-09 (70-RESEARCH.md § D-70-04): Merge (Combine by Position,
  2 inputs) immediately after every HTTP node — pre-hop row on input 1, HTTP response on
  input 2. Where the API echoes an opaque row token, prefer Combine-by-Fields on that token
  over positional combine; decide per HTTP node at build time. HTTP-inside-Code lost:
  `this.helpers.httpRequestWithAuthentication` was broken on n8n Cloud through 1.36.1, fixed
  in 1.42.0, and this account's build is unpinned — a credential-sandbox dependency the repo
  cannot verify offline. The assertion must catch the literal `$('`, the dynamic `$(name)`
  call form `nodeRunRecovery.js` uses, and node `parameters` expressions (IF conditions, HTTP
  jsonBody/url), and must assert `nodeRunRecovery.js` is inlined nowhere (Pitfall 2). The
  `.item` reads of `Enrichment Gate` inside the research/judge HTTP body builders
  (`build_cloud_workflows.py` ~L5889-5954, Pitfall 4) are in scope.*

### Result channel

- **D-70-05: The client result channel is runData by client-minted `run_id`, ALWAYS.**
   Sync and async, every mode including `propose`. This is
  `watch.recover_async_dispatch`'s existing mechanism (`Build Response` runs off the settled
  execution, correlated on `Parse HubSpot Event`'s echoed `run_id` — exact match) promoted to
  the only path. It REOPENS F5b's debug-scope "no code fix" ruling (`7524ee7`) structurally:
  the reason F5b was safe (`classify_matches` walks input rows) stays true, but the sync body
  is no longer a data channel at all. Rejected: sync body made complete by the Merge (two
  channels survive); split by mode.
  — **Reversibility:** one-way — a published client contract; callers that parsed the sync
  body (see D-70-08) are migrated, not shimmed.

- **D-70-06: The row's outcome of record is the WRITE node's actual output.** `Build Response`
  / `Build Ingest Response` receive, on the row itself, the HubSpot write node's response or the
  gate's refusal item (D-70-14). `action` reflects what HubSpot returned; `write_blocked` when
  the gate refused. F12's Decide-side precheck in `DECIDE_CLOUD` (`8344b7a`) is REMOVED, and the
  folded create-row precheck todo is closed by construction, not implemented. Rejected: keeping
  the precheck as the source; both.

- **D-70-07: The HTTP body is ALWAYS an ack; the `async_ack` flag is retired.** `Respond to
  Webhook` fires once, immediately, with `{run_id, accepted, row_ids}` for every request.
  `Build Async Ack` becomes THE response; no business lane ever feeds `Respond`. Today four
  nodes feed `Respond to Webhook` on the enrichment lane (`IF List Expanded`, `Build Async Ack`,
  `Build Scale Up Ack`, `Build Response`); after this phase the refusal paths that today answer
  a bare 200 with a reason (`IF Object Type Supported` false, `recompute_refused`,
  `write_blocked`, list-expansion refusals) must land their reason as a ROW in runData that the
  client reads, because the body no longer carries it. The flag is removed from `Parse HubSpot
  Event` normalisation and from `chunking.dispatch_plan`; a caller that still passes it is
  ignored, not rejected. §13.0.2's four-flag table becomes three (`recompute`, `scale_up`,
  `source_by_field`).
  — **Reversibility:** one-way — the sync body contract is published to every caller.

- **D-70-08: Ack-only applies to the enrichment and ingest lanes only.**
  `hubspot/enrichment/event` and `hubspot/contact-upload` return an ack. `hubspot/review/queue`,
  `hubspot/review/decision` and `hubspot/backend-status` are queries, not row-outcome lanes,
  and keep responding with a body. EVERY caller of the two lanes migrates to runData: the
  plugin, `scheduled_arm.py`, and the seven repo scripts that POST to the webhook
  (`enrich_coverage_companies.py`, `fix_sfv_region.py`, `probe_company_propose_mode.py`,
  `probe_n8n_async_semantics.py`, `prove_scale_up_runtime.py`, `remediate_veto_companies.py`,
  `rescore_population.py`) — a script that no longer has a purpose may be deleted instead of
  migrated. `SJ-3 Dispatch To Enrichment` is an `Execute Workflow` node (`mode: each`) with no
  HTTP body to read; unaffected. Rejected: a request-level flag returning the merged body to
  scripts; every webhook ack-only.

- **D-70-08a: `enrich-records` migrates too — its recorded exception is overridden.** Memory
  `propose-mode-response-body-is-the-data-channel` records that `enrich-records` deliberately
  did NOT use runData recovery: 3 of its 4 spec forms mint no row ids, nothing writes manifest
  verdicts (so `run_state.read_progress` — verified: it derives `running` from
  `run_manifest` verdicts — would report `running` forever), and step 9's F3 per-record report
  reads the body. Under D-70-05 that exception ends. Correlation is by `run_id` alone
  (client-minted per dispatch, not per row), so id-less spec forms still correlate; settlement
  comes from the EXECUTION's status, never from manifest verdicts; the ack's `row_ids` may be
  empty for those forms; step 9's F3 rule ("never guess beyond what the body says") applies
  verbatim to the runData rows instead. `scale_up` children are separate executions of the
  same workflow carrying the same `run_id`; `find_executions_by_run_id` must return them
  (§13.0.3: the executions API lists child executions), or a fanned-out batch loses its rows
  on the sole channel.

- **D-70-09: `written_records` records WRITES only — no-write legs are never appended.**
  `chunking.dispatch_plan` appends a chunk to `written_records` only when the leg's mode can
  write (write / ingest). Propose / match / enrich-proposal legs never enter the ledger; their
  rows reach the end-of-run report through the enrichment outcome. The report can never say
  `failed` for a row that was not sent (folded F8). Rejected: `NO_ACTION` with reason; backend
  stamping an action on every row.

- **D-70-10: Refuse before start when the executions-API key is absent.** runData-only makes
  `n8n_api_key` a hard dependency of every enrichment/ingest send. A missing key is a Phase-57-
  style refusal-before-start alongside Phase 67's fail-closed conditions. NEVER a fallback to
  `executions_client.find_execution_for_dispatch`'s D-12 time-proximity guess. Rejected:
  dispatch then report `unread`; time-proximity fallback.

- **D-70-11: `confidence.assess` is the ONLY per-row verdict on the client.**
  `preingest.render_enriched_preview` calls `confidence.assess` per row and shows
  `HELD <code> <reason>` or `SEND`; `SEND` only when CONFIDENT. The preview's `send_count`
  equals dispatch `SENDABLE` by construction, pinned by a test (row with tier `none` and a found
  email renders `HELD no_match`, never `SEND`). The SKILL and README state the design fact this
  exposed: under autonomy a NEW person is never created without the operator's end-of-run
  approval, because a no-match row is by definition unconfident (D-61-03, unchanged). Folded
  todo `enriched-preview-says-send`. Rejected: two columns; dropping the column.

### Write-gate contract

- **D-70-12: One canonical `write_request` shape, no gate fallbacks.** Every node feeding a
  gated write emits `write_request: {action, hs_object_id, domain, email}`. `_write_gate_js`
  reads ONLY that shape — the `identity_keys.domain || domain || company_domain || email-
  domain` fallback ladder (BUG 27, F11) is deleted. The create-row email-domain derivation
  moves into the EMITTER, once. The builder asserts at generation time that each gated node's
  upstream emits `write_request`. Rejected: extend the tolerant gate; canonical-plus-legacy for
  one phase.
  — **Reversibility:** costly — one shape across three workflows; re-adding tolerance means
  re-growing the ladder.

- **D-70-13: Every gated write in every lane, one shape; review lane keeps id-only AS DATA.**
   Enrichment (create/update/company), ingest (create/update/associate) and
  review-decision (`Review Decision Update` etc.).
  *Premise corrected by research 2026-09-09 (70-RESEARCH.md § Write-gate inventory): the
  "three splice sites" named at discussion were misattributed. `splice_write_gates` is called
  from `build_cloud` (ingest, :1086), `build_scheduled_maintenance_cloud` (:7989 — SJ-1/SJ-2/
  Dedupe set-requested writes) and `build_review_decision_cloud` (:8675). The ENRICHMENT lane
  has NO spliced gate node: its write check is inline inside `Decide Action` /
  `Decide Company Action` via `_writeSafetyAllows` (:1795, :3804). The decision stands
  unchanged and widens: the enrichment lane GAINS a real gate node emitting the refusal item
  (D-70-14), the scheduled-maintenance writes adopt the same `write_request` shape, and the
  inline `_writeSafetyAllows` calls in the two Decide nodes are removed so the predicate has
  one home per lane. Forced widening: deleting the fallback ladder from `_write_gate_js`
  (D-70-12) breaks `build_scheduled_maintenance_cloud`'s three spliced gates (`SJ-1 Set
  Requested`, `SJ-2 Set Requested`, `Dedupe Set Needs Review`) unless their emitters adopt
  `write_request` too — so they do, and `sj3DispatchGate` / `sjPredicates` /
  `dedupeSweepWiring` tests plus the node-count pin 39 move with them.
  `companyRecomputeLaneFlow.test.mjs` pins the recompute lane's `write_blocked` coming from
  `Decide Company Action` (execution 11858, §13.0); with the inline check gone it is
  rewritten against the new gate, not deleted. D-70-19's disarmed run does NOT exercise the
  scheduled lane; its coverage is offline only.* The review lane's emitter sets
  `domain: null`, so 30-02's "contacts are `TEST_RECORD_IDS`-only on review writebacks" survives
  as the emitted value, not as a gate special-case; `reviewDecisionEndpoint.test.mjs` g3 stays
  green. Rejected: enrichment+ingest only; giving review the domain path.

- **D-70-14: A refused row is EMITTED, never dropped.** The gate becomes IF-shaped: permitted
  rows go to the write node; refused rows carry `action: "write_blocked"` and a reason on a
  second output that reaches the Merge before `Build Response` / `Build Ingest Response`. No
  Code node filters its input to zero on a write path any more, so a 100%-refused batch cannot
  dead-end (F1's shape) and the response always sees the refusal (F12). Rejected: pass-through
  with `allowed` flag; keep drop + precheck in every Decide.

- **D-70-15: One gate verdict covers an update AND its association.** Update and the
  `HubSpot Associate Company` PUT are one `write_request` with ONE allowlist verdict; the
  second gate copy on the association path is removed. If the verdict refuses, neither node
  runs (`write_blocked`). If it permits, the update runs, and the association runs only when a
  `company_id` resolved — otherwise `association: not_attempted`. §13.0.1 is unchanged: an
  update is NEVER held for lack of a company; company resolution does not gate the update,
  only the allowlist does. Both facts are reported from the actual nodes. Rejected:
  independent verdicts.

### Harness depth + UAT shape

- **D-70-16: The offline harness is a GRAPH WALKER over the committed JSON.** One shared helper
  under `tests/n8n/` executes a workflow from its `connections`: fires each node per inbound
  edge as n8n does under the workflow's `executionOrder`, runs Code nodes' `jsCode` via
  `new Function` (the mechanism the 50 existing tests already use), stubs HTTP nodes with
  fixtures, models Merge, a single `Respond`, `responseData`, and `$runIndex`. A test feeds rows
  at the trigger and asserts rows at `Build Response`. `enrichmentGateRunRecoveryFlow.test.mjs`'s
  `makeDollar` run-history model is the seed, then superseded. Rejected: promoting `makeDollar`
  alone; a hybrid.
  — **Reversibility:** reversible — additive test infrastructure.

- **D-70-17: Acceptance is one mixed-batch test per lane.** One enrichment test and one ingest
  test, each 2 identity lanes × 2 actions, asserting every row returns exactly once from the
  write node's output. Rejected: one RED-first test per historical instance (seven); walker
  plus live differential as the offline bar.

- **D-70-18: GREEN on the refactored JSON is enough — no historical RED.** The operator chose
  not to run the two tests against the pre-Phase-70 JSON. The walker's ability to detect the
  class is asserted by the walker's OWN unit tests (a fixture graph where lanes reconverge
  without a Merge must yield the F5-style collapse; one where `Respond` fires twice must yield
  first-run-only). Note for the planner: memory `audit-sweep-anti-patterns` says a guard test
  must be seen RED; here the RED lives in the walker's unit tests, by operator decision.

- **D-70-19: Phase closes on a DISARMED live mixed batch whose runData matches the walker.**
   After the operator deploys and bounces (disarmed, both write flags `"false"`), one
  disarmed 2-lane × 2-action send per lane; the rows recovered from runData must be shape-equal
  to the walker's predicted rows for the same input (precedent:
  `.planning/milestones/v1.1-phases/61-autonomous-batch-runs/61-ASYNC-RECOVERY-VERDICT.json`,
  `shapes_equal: true`). Verdict JSON in the phase dir. Zero writes, zero arming. This is also
  the `[observed live]` upgrade for D-70-02's Merge/executionOrder fact. Rejected: offline GREEN
  closes it; adding one armed row.

### Claude's Discretion

- Merge node typeVersion/mode parameters, input count per convergence point, and node layout.
- The walker's API, fixture format for HTTP stubs, and where it lives under `tests/n8n/`.
- The ack body's exact field names beyond `run_id`, `accepted`, `row_ids`.
- Poll bound and cadence for sync-style callers now reading runData (`watch.py`'s measured
  bounds are the starting point).
- Migration order across the three workflows and which repo scripts are deleted vs migrated.
- Node-count pins that move: CLAUDE.md's 123 (enrichment) / 29 (ingest) / 26 (review) /
  39 (maintenance) / 17 (status); `test_control_flag_parity.py`'s declaration counts; builder
  idempotency test. Budget the pin updates; do not treat a moved pin as a regression.
- How the refusal reasons that today ride the sync body (`recompute_refused`, unsupported
  object type, list-expansion refusals) are shaped as runData rows.

### Folded Todos

- **`2026-09-09-n8n-lanes-reconverge-by-name-reads-one-result-channel.md`** — IS the phase.
  Its five-point "what a structural fix looks like" maps to D-70-16 (harness), D-70-01/03/04
  (backend), D-70-12..15 (gate), D-70-05..08 (client), D-70-17/19 (UAT shape).
- **`2026-09-09-ingest-create-row-has-no-write-blocked-precheck.md`** — closed by D-70-06 +
  D-70-14: the precheck pattern is removed rather than extended to create rows; a refused
  create row is a `write_blocked` item from the gate itself.
- **`2026-09-09-written-records-labels-propose-and-enrich-legs-failed.md`** (F8) — D-70-09.
- **`2026-09-09-enriched-preview-says-send-for-rows-the-confidence-gate-holds.md`** — D-70-11.

</decisions>

<canonical_refs>
### Gap-closure decisions (operator, 2026-09-10, after /gsd-verify-work 70)

Source of truth for the gaps: `70-UAT.md` § Gaps (G-70-1 resolved; G-70-2, G-70-3 blocker;
G-70-4 minor) and `70-RUNTIME-VERDICT.json` (`status: observed`, `shapes_equal: false`,
executions 12203, 12204–12208).

- **D-70-20 — Approach: fix graph + walker, keep the Phase 70 design.** The walker
  (`tests/n8n/lib/walkWorkflow.mjs`) must model what the engine did: a zero-item output IS a
  delivery to a Merge input; the first delivery per input wins; a Merge fires once. The walker
  change lands RED first — it must reproduce executions 12203 (`Associate Carry Merge` 1×0,
  `write_blocked` row dropped) and 12206 (`Enrichment Gate Merge` fired on `Contacts Absent
  Sentinel`'s `[]`; `Build Response Merge` never fired) against the CURRENT committed JSON
  before any graph change. Then regenerate every lane in `scripts/build_cloud_workflows.py` so
  NO Merge input is shared between a sentinel and a real producer: a sentinel always emits
  exactly one marker item on its own dedicated append-mode input, markers are filtered at the
  response builder; a starved carry Merge (combineByPosition) is BYPASSED by the sentinel lane,
  never padded with a marker that could pair with a real row. `Build Response Merge` (15
  inputs) is split so no Merge declares more than 10 inputs. Every offline suite must go RED
  under the corrected walker before it goes GREEN under the regenerated graph.
- **D-70-21 — Roll back the live instance FIRST.** Wave 0: deploy + bounce the pre-Phase-70
  `n8n/wf_*_cloud.json` from git commit `59812be` (node counts 17/29/123/26/39), disarmed,
  read back node counts and both write flags `"false"`. The live enrichment lane's `Build
  Response` is dead on the Phase 70 JSON; the rollback restores it while the gap is fixed.
  Redeploying the fixed JSON is a deferred live gate at the end of gap closure, like Gates 1–3.
- **D-70-22 — The proof driver compares like with like (G-70-4).** On the ingest lane
  `scripts/prove_phase70_runtime.py` compares the RAW recovery rows (`watch.recover_dispatch`
  responses), not the client-reconciled rows, or `row_shape` excludes client-added keys — with a
  test that fails on execution 12207's shape first.
- **D-70-23 — Sentinel mechanism: Option B, gated sentinel (amends D-70-20).** D-70-20's
  stated mechanism — a sentinel on its own dedicated append-mode input, always emitting exactly
  one marker — does not hold: the engine requires a delivery on every declared Merge input, and
  a sentinel on its own input leaves the REAL producer's input unfed whenever that lane is dead,
  so the Merge never fires. This is executions 12204–12206 (`Build Response Merge` had inputs
  with no delivery at all and never fired; the run reported success with zero rows), reproduced
  synthetically by Wave 1's dedicated-input marker case in `tests/n8n/walkWorkflow.test.mjs`.
  Operator ruling 2026-09-10: **Option B — gated sentinel.** The sentinel keeps SHARING the real
  producer's Merge input; a gate node sits between the sentinel's condition node and its
  targets, and the gate emits nothing at all when the lane is live — a node fed zero items never
  runs, so no delivery is made and the real row cannot be pre-empted. This is the same mechanism
  the engine already demonstrated at Gate 1 (execution 12200), where a write node received zero
  items, never ran, and contributed no delivery, and it matches the one shared input in this
  repo that already behaves correctly (the credit collector: a fetched result and a skipped
  result feed one input, and exactly one of them ever runs). Wave 1's gated-sentinel synthetic
  case does not stall, confirming the mechanism offline before any regeneration.
  Every other clause of D-70-20 stands unchanged: the carry Merge is bypassed rather than
  padded, no Merge declares more than ten inputs, and markers are filtered at the response
  builders. Cost, taken on deliberately: every sentinel condition is now load-bearing — a
  wrongly-silent sentinel now starves the input it used to satisfy by accident merely by
  emitting an (empty) delivery — so each sentinel condition must be audited to be the exact
  complement of its real producer's own delivery predicate (plan 70-10's Task 2 audit).
- **Unchanged:** every locked decision D-70-01..19 stands. D-70-19's rule stands verbatim: the
  walker is corrected toward the engine, never toward the plans.

### Gap-closure round 2 decisions (operator, 2026-09-10, after Gate 5)

Source of truth: `70-UAT.md` tests 4–6 and gap G-70-5 (blocker). Gate 5 facts: the ingest lane
PASSED live (`shapes_equal: true`, executions 12293/12309); the enrichment gap-closure body
LOOPED — `Dispatch Self` ran once per execution with a marker item though its only declared
producer emitted 0 items, 135 child executions in six minutes, stopped by deactivate + a PUT of
the pre-70 `59812be` body. The live instance is MIXED: enrichment = `59812be` (123 nodes,
active), the other four = gap-closure JSON.

- **D-70-24 — Remove the scale-up fan-out from the enrichment graph.** `Dispatch Self`,
  `Build Scale Up Fan-Out`, `Build Scale Up Ack`, `IF Scale Up Route` and every sentinel/gate
  that exists only for them are deleted from `scripts/build_cloud_workflows.py`'s enrichment
  build (and from `wf_enrichment_local_live.json` if it carries them). A request with
  `scale_up: true` is REFUSED by `Parse HubSpot Event` (recorded as a refusal row, like the
  existing list-expansion refusal), never fanned. The plugin's `dispatch_plan(scale_up=...)`
  path and `IF Scale Up Route`-dependent tests are retired or converted to refusal tests.
  Reason: after Gate 5 no in-graph guard is trusted on this engine; only the absence of a
  self-referencing `Execute Workflow` node makes recursion impossible. The feature may return
  in a later phase once the engine rule behind G-70-5 is understood. CLAUDE.md §13.0.2's
  `scale_up` row is amended to say RETIRED with the execution ids.
- **D-70-25 — Markers never reach the wire.** `Build Response` (enrichment) and
  `Build Ingest Response` (ingest) drop every marker item (an item with none of the row
  identity keys) BEFORE emitting, so a recovered row set can only contain real rows. Pinned by
  a test that fails on Gate 5's recovered shape (marker-shaped items in `12209`/`12210`).
- **D-70-26 — The walker records, not guesses, the G-70-5 rule.** The walker must NOT be
  taught a mechanism that was not isolated. Instead: (a) any `executeWorkflow` node in a
  committed graph is a generation-time refusal (`assert_no_self_dispatch`, mirroring
  `assert_merge_input_contract`), so the walker never needs to model it; (b) the walker's
  engine-fidelity suite gains a frozen-fixture reproduction of execution `12316` that asserts
  the walker CANNOT reproduce the observed `Dispatch Self` run — recorded as a documented
  divergence (`[observed live]`, cause unknown), not a green test that pretends to model it.
- **D-70-27 — Live gates for this round, all deferred per the standing ruling:** Gate 7 =
  disarmed deploy + bounce of the loop-free enrichment body, then WATCH the executions list
  for `mode: integrated` bursts for two minutes BEFORE any send; Gate 8 = the D-70-19 proof
  re-run (all four sends must be `shapes_equal: true`); Gate 9 = the armed mixed-verdict re-run
  (formerly Gate 6), only after Gate 8. Every deploy in this repo now carries the two-minute
  integrated-burst watch as a runbook step.
- **Unchanged:** D-70-01..23 stand. D-70-19 stands verbatim.

### Gap-closure round 3 decisions (operator, 2026-09-10, after Gates 7 and 8)

Source of truth: `70-UAT.md` tests 7–9 and gap G-70-6 (blocker). Gate 7 PASSED (loop-free
287-node enrichment body deployed disarmed, two-minute burst watch clean, zero
`mode: integrated` executions). Gate 8 FAILED on executions `12349`–`12353`: `HubSpot Update`
executed with no real input item and PATCHed an empty id (405) on both ingest sends;
`IF List Expanded` emitted a refusal on an empty list lane; gated sentinels delivered markers on
inputs whose sentinel emitted 0 items; `Enrichment Gate Merge` fired twice and dropped every real
row; `Apply Contact Judge Verdict` crashed on a marker. Gate 9 blocked. Live rolled back to the
pre-Phase-70 `59812be` bundle (17/29/123/26/39, active, disarmed). `settings.executionOrder` was
ABSENT on every live body throughout.

**Engine rule, now source-cited (`[documented]`, not yet `[observed live]` under v1):** n8n's
legacy execution order (`executionOrder` absent or not `"v1"`) — in
`packages/core/src/execution-engine/workflow-execute.ts`, `addNodeToBeExecuted`, the
`addEmptyItem` branch — pushes every node on an empty branch onto the execution stack with ONE
`{ json: {} }` item so that a waiting multi-input node (a Merge) can finish. That single item is
the shape of every Gate 8 symptom and of G-70-2/3/5: a gate Code node fed one empty item runs
and stamps its marker; an HTTP node fed one empty item sends a request with an empty id; an
`Execute Workflow` node fed one empty item dispatches. Under v1 there is no such push: nodes on
an empty branch do not run, and at end-of-run every node still in `waitingExecution` executes
with the inputs that arrived, gated on `requiredInputs` — which, for the Merge node v3.2 this
repo generates (`versionDescription.ts`), is `[0, 1]` for `chooseBranch` and `1` for every other
mode (`append`, `combine`). The n8n docs page on execution order describes only branch ordering
and says nothing about empty-input execution; the source is the citation.

- **D-70-28 — Flip `settings.executionOrder` to `"v1"` on EVERY generated workflow
  (supersedes D-70-02).** `scripts/build_cloud_workflows.py` emits `"settings":
  {"executionOrder": "v1"}` on all eight `n8n/wf_*.json` bodies (five cloud, three local);
  never per-workflow, never hand-edited. RED first: a test that asserts every committed
  `n8n/wf_*.json` carries `settings.executionOrder === "v1"` fails before regeneration and
  passes after. Node counts do not move (settings only) — 287/69/55/43/30 and 82/10/13 are
  NOT a regression signal for this round. D-70-02's reasoning (a second all-five behaviour
  change in one proof run) is retired by four live observations that the legacy order itself
  is the defect; its reversibility rating (one-way in effect) stands and is discharged by this
  ruling, not by a mid-run checkpoint. Rejected: keep legacy and make every gate/IF/HTTP/write
  node tolerate the forced empty item (fights a source-cited engine rule, touches every node,
  and the walker would have to model "always executes"); flip the ingest lane alone first
  (two behaviour generations live at once).
- **D-70-29 — `executionOrder` survives every PUT, and every read-back asserts it.**
  `scripts/deploy_n8n_workflows.py` already forwards `settings`;
  `operator-claude-plugin/scripts/n8n_control.py::put_body` already forwards `settings` and
  refuses a PUT whose `settings` differ from the live original (so an arming/disarming rewrite
  can never revert a workflow to legacy). Both facts are pinned by tests, and every deploy/bounce
  read-back in this repo (deploy script, bounce script, the proof driver's
  `live_settings_execution_order`) reports the live value. A live body reading anything but
  `"v1"` after this round's deploy is a gate failure.
- **D-70-30 — The walker records the v1 contract; it does not model legacy.** The walker
  (`tests/n8n/lib/walkWorkflow.mjs`) keeps its `order` branch but the legacy branch stops
  claiming to model the engine: a non-v1 body is refused unless the caller passes an explicit
  escape used only by the engine-fidelity suite, whose frozen fixtures (`settings: {}`,
  executions 12203/12206/12316) stay as RECORDED legacy divergences with their execution ids.
  Nothing is added to model the legacy empty-item push — the body it acted on is retired.
  Under v1 the walker's rules are `[documented]` until Gate 11 observes them: (a) a node fed
  zero items does not run; (b) a waiting Merge drains at end-of-run with the inputs that
  arrived (`requiredInputs` 1, or `[0,1]` for chooseBranch); (c) whether a Code node that RAN
  and emitted `[]` counts as a Merge-input delivery under v1 is UNOBSERVED — the 70-09 rule was
  observed under legacy and may have been the empty-item push, not a delivery. The walker's
  own comments say which rule is which and cite this decision. Freezing executions
  `12349`–`12353` needs the operator's API key and is an operator step, not an executor task;
  `70-UAT.md` § Test 8 already records the observations.
- **D-70-31 — Live gates for this round, all deferred per the standing ruling (re-points
  D-70-27; Gates 7/8/9 stay in the record as run/failed/blocked):** Gate 10 = disarmed deploy +
  bounce of the v1 bodies (same node counts, both write flags `"false"`), read back
  `settings.executionOrder === "v1"` on all five, then the two-minute integrated-burst watch
  with nothing sent; Gate 11 = the D-70-19 proof re-run (all four sends `shapes_equal: true`,
  every execution settled, `writes_performed: 0`, every recovered enrichment row carrying a
  non-null `row_id`, the runData-source-vs-declared-connections check clean, AND
  `live_settings_execution_order` reading `"v1"` on every workflow — a `null` reading is a
  failure of this gate, the opposite of Gate 8's expectation); Gate 12 = the armed
  mixed-verdict re-run (formerly Gate 9), only after Gate 11. If Gate 11 shows the legacy
  symptoms persist under v1, STOP and report — do not adjust the walker or the driver to match.
- **Unchanged:** D-70-01, D-70-03..26 stand. D-70-19 stands verbatim. D-70-23's gated
  sentinel mechanism stands — under v1 it is the design that was always intended (a gate fed
  zero items never runs).

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### The brief and the evidence
- `.planning/todos/pending/2026-09-09-n8n-lanes-reconverge-by-name-reads-one-result-channel.md`
  — the idiom, all seven instances, the five-point fix shape.
- `.planning/debug/resolved/uat-batch-review-row-reads-failed.md` — F1/F5/F5b/F10/F11/F12 root
  causes, fixes, and live proof (executions 12163, 12173, 12179, 12181, 12194, 12196). §F5b is
  the ruling D-70-05 reopens. §executionOrder records that the setting is absent live.
- `.planning/uat/UAT-autonomous-batch-2026-09-09.md` — the UAT record.
- `docs/OPERATOR-AUTONOMOUS-BATCH-UAT.md` — the operator's UAT procedure; its batch shape
  changes to mixed lanes + mixed actions by default.
- `.planning/ROADMAP.md` § "Phase 70" and § "Binding on all six" (SAFE-01..05).
- `.planning/milestones/v1.2-REQUIREMENTS.md` — the milestone's requirement vocabulary; Phase
  70's requirements are "TBD at discussion" and are D-70-01..19 above.

### Platform facts (read before recommending Merge / executionOrder / carry mechanism)
- `CLAUDE.md` §13.0.3 — `[documented]` vs `[observed live]` tagging rule; Starter plan limits.
- `CLAUDE.md` §13.0, §13.0.1, §13.0.2 — the request-level flags (`async_ack` retired by
  D-70-07; `recompute`, `scale_up`, `source_by_field` unchanged), the association rule's
  single implementation, and the deployment-parity notes.
- `n8n/code/nodeRunRecovery.js` — header comment is the best in-repo statement of n8n's
  per-inbound-edge run semantics and the `.all(0, $runIndex)` insufficiency. Deleted by D-70-01;
  read first.
- Memory `propose-mode-response-body-is-the-data-channel` (in the auto-memory dir) — why
  `async_ack` alone was dangerous; the runData recovery design; the differential live-proof
  method D-70-19 reuses.
- `.planning/milestones/v1.1-phases/61-autonomous-batch-runs/61-ASYNC-RECOVERY-VERDICT.json`
  and `scripts/prove_async_recovery.py` — shape-equal proof precedent.

### The code this phase changes
- `scripts/build_cloud_workflows.py` — the only source of every `n8n/wf_*.json`. Key
  symbols: `splice_write_gates` (:7641), `_write_gate_js` (:7608), `WRITE_SAFETY_GATE_JS`,
  `BUILD_INGEST_RESPONSE` (:496), `ENRICH_BUILD_RESPONSE` (:5064), `DECIDE_CLOUD` (F12 precheck
  to remove), `ENRICH_DECIDE_CLOUD`, `ENRICH_DECIDE_CO_CLOUD`, `Build Async Ack`, `Parse
  HubSpot Event`, `IF Scale Up Route`. All 23 by-name read targets are in this file.
- `n8n/wf_enrichment_cloud.json` (123 nodes), `n8n/wf_contact_ingest_cloud.json` (29),
  `n8n/wf_review_decision_cloud.json` (26), plus `_local` / `_local_live` variants — generated,
  never hand-edited.
- `operator-claude-plugin/scripts/watch.py` — `recover_async_dispatch`,
  `find_executions_by_run_id`, `_build_response_rows`, `poll_until_settled`: the runData path
  D-70-05 promotes.
- `operator-claude-plugin/scripts/executions_client.py` — the API key header; the
  `find_execution_for_dispatch` time-proximity path D-70-10 forbids as a fallback.
- `operator-claude-plugin/scripts/dispatch.py`, `chunking.py` (`dispatch_plan`),
  `written_records.py` (`append_chunk`, `classify_item`), `preingest.py`
  (`render_enriched_preview`, `classify_matches`, `merge_enriched`), `report.py`,
  `report_enrichment.py`, `run_report.py`, `scheduled_arm.py` — sync-body consumers to migrate.
- `operator-claude-plugin/scripts/confidence.py` — `assess`; read only, not modified (D-70-11
  consumes it).
- `operator-claude-plugin/tests/test_report_sufficiency.py` — permits exactly one poll site
  (`watch.py`); the migration must keep that invariant or change the test deliberately.
- `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` — the F5b paragraph added by
  `7524ee7` becomes wrong under D-70-05 and must be rewritten; step 5's `async_ack=True` goes.
- `operator-claude-plugin/skills/enrich-records/SKILL.md` step 9 (F3 recorded edit) and its
  `dispatch_plan` call (:503) — D-70-08a; the report wording moves from body to runData rows.
- `operator-claude-plugin/scripts/run_state.py::read_progress` and
  `run_manifest.load_scoped` — the manifest-verdict settlement D-70-08a replaces with
  execution status for id-less spec forms.

### The harness
- `tests/n8n/enrichmentGateRunRecoveryFlow.test.mjs` — `makeDollar` run-history model and the
  drop-wave case; seed for the walker.
- `tests/n8n/researchChainRowFlow.test.mjs` — the `new Function` execution note.
- `tests/n8n/ingestWebhookRespondsAllEntries.test.mjs`,
  `ingestUpdateWriteBlockedFlow.test.mjs`, `ingestUpdateGateDomainFallback.test.mjs`,
  `ingestReviewBranchResponds.test.mjs`, `asyncAck.test.mjs`, `nodeRunRecovery.test.mjs` — the
  per-site regression tests whose subjects this phase removes or reshapes; each is retired or
  rewritten against the walker, never left asserting a deleted mechanism.
- Run form: `node --test tests/n8n/*.test.mjs` (directory form broken on node 24);
  `.venv/bin/python -m pytest` for the plugin suite.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `watch.recover_async_dispatch` + `find_executions_by_run_id` already implement the runData
  channel end to end, exact-matched on the client-minted `run_id`; D-70-05 generalises them.
- `splice_write_gates` already inserts one gate per gated write from a `{write_name: action}`
  map; D-70-14 changes the gate node's shape (two outputs) and D-70-12 its jsCode, not the
  splice mechanism.
- `Build Async Ack` already emits `{run_id, accepted, row_id}` and already wins the race to
  `Respond`; it becomes the single responder.
- `makeDollar` (run history keyed by node name and run index) and the `new Function` jsCode
  runner are the walker's building blocks.
- `written_records.classify_item` already maps `write_blocked` → GATED.

### Established Patterns
- Phase 46 parity rule: a shared predicate lands in both engines in one commit — not
  triggered here (no scoring predicate changes), but the veto block's INPUT wiring must not
  change.
- Every builder change: regenerate all variants, count nodes, run the node suite and the
  plugin suite, commit JSON with the builder in one commit. Deployment is the operator's step;
  committed JSON runs ahead of live until then.
- `[documented]` / `[observed live]` tagging for any platform claim (CLAUDE.md §13.0.3).
- Guardrails are refusals in code, not prose (SAFE-05); D-70-10 follows this.

### Integration Points
- `Parse HubSpot Event` — request-flag normalisation (drop `async_ack`); `run_id` echo is what
  the client correlates on.
- `Respond to Webhook` — four inbound edges today on enrichment; one after.
- The three `splice_write_gates` call sites (:1086 ingest, :7989 enrichment, :8675 review).
- `chunking.dispatch_plan` — the one place that decides whether a leg is appended to
  `written_records` (D-70-09) and that passed `async_ack` (D-70-07).
- Phase 67's fail-closed conditions list — D-70-10 adds the executions-API key.

</code_context>

<specifics>
## Specific Ideas

- "Retire every by-name read" was chosen over the recommended narrower option; the operator
  wants the idiom gone, not fenced. The assertion is the deliverable; the carry mechanism is
  research.
- The operator declined historical RED and per-instance tests; two mixed-batch tests plus the
  walker's own unit tests are the offline bar. Do not expand that scope in planning.
- Live proof is disarmed only. No armed row is part of this phase's close.

</specifics>

<deferred>
## Deferred Ideas

### Reviewed Todos (not folded)
- `2026-08-04-enrichment-throughput-ceiling.md` — judge cost; not the idiom.
- `2026-09-04-company-domain-has-no-candidate-source.md` — candidate sourcing; not the idiom.
- `2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md` — merge
  policy under SAFE-01..05; separate.
- `2026-09-08-forbidden-name-markers-refuse-secretary-and-armidale.md` — validation vocabulary.
- `2026-09-04-website-less-company-search-fallback.md`,
  `2026-09-05-fallback-is-keyed-on-ladder-empty-not-round-empty.md`,
  `2026-09-04-walk-provenance-locator-names-last-page-only.md` — suggestion-round ladder.

None raised during discussion — it stayed within phase scope.

</deferred>

---

*Phase: 70-one-merge-one-result-channel-n8n-runtime-truth*
*Context gathered: 2026-09-09*
