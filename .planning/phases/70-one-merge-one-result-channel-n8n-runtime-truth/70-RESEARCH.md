# Phase 70: One merge, one result channel — n8n runtime truth - Research

**Researched:** 2026-09-09
**Domain:** n8n workflow topology (Merge/executionOrder/Code-node semantics on n8n Cloud Starter), a Python client's result-channel design, and an offline execution-order test harness
**Confidence:** MEDIUM — the two decisions explicitly delegated to this research (D-70-02, D-70-04) rest on official n8n docs plus multiple independent community bug reports, not on a live observation in this repo (D-70-19 is that observation, and it happens after planning). Everything about THIS repo's own code (by-name read inventory, convergence points, gate call sites, client scripts) is `[VERIFIED]` — read directly this session.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-70-01: An explicit Merge node at every convergence point.** Wherever two or more lanes
  feed one node today (`Enrichment Gate`, `Company Gate`, `Build Response`, `Build Ingest
  Response`, the write-gate fan-in), a Merge (append, N inputs) sits in front, so the converged
  node runs ONCE on all rows. `n8n/code/nodeRunRecovery.js` and its seven call sites are
  deleted, not kept as a fallback. Rejected: per-item `pairedItem` lineage (HTTP hops break it;
  `.item` is ambiguous across runs — observation 31305); keeping run recovery as a fenced idiom.
  — **Reversibility:** costly — every converged reader's jsCode changes from by-name to
  `$input`; undoing means reinstating run recovery at every site.

- **D-70-02: `executionOrder` v1 flip is the RESEARCHER's call, after a doc check.** Both live
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

- **D-70-04: The locked rule is a BUILD-TIME ASSERTION; the researcher picks the carry
  mechanism.** `scripts/build_cloud_workflows.py` fails generation if any emitted jsCode or
  expression contains a `$('` read, and a test pins it against the committed JSON. How a row
  survives an HTTP hop without `$('Prev')` (HTTP Request nodes have no pass-through) is
  evaluated by the researcher against n8n Cloud limits — candidates named in discussion: Merge
  combine-by-position per hop (n8n-native, ~15–20 new nodes per workflow, relies on 1:1 item
  order incl. `continueOnFail`), HTTP inside Code via `this.helpers.httpRequest` (fewest
  nodes; credential reachability from Code on Cloud is UNVERIFIED), or another the researcher
  finds. The recommendation must state which candidate and why the others lost.

- **D-70-05: The client result channel is the settled execution's runData, read by the
  client-minted `run_id`, ALWAYS.** Sync and async, every mode including `propose`. This is
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

- **D-70-12: One canonical `write_request` shape, no gate fallbacks.** Every node feeding a
  gated write emits `write_request: {action, hs_object_id, domain, email}`. `_write_gate_js`
  reads ONLY that shape — the `identity_keys.domain || domain || company_domain || email-
  domain` fallback ladder (BUG 27, F11) is deleted. The create-row email-domain derivation
  moves into the EMITTER, once. The builder asserts at generation time that each gated node's
  upstream emits `write_request`. Rejected: extend the tolerant gate; canonical-plus-legacy for
  one phase.
  — **Reversibility:** costly — one shape across three workflows; re-adding tolerance means
  re-growing the ladder.

- **D-70-13: Scope — all three splice sites, one shape; the review lane keeps id-only AS
  DATA.** Enrichment (create/update/company), ingest (create/update/associate) and
  review-decision (`Review Decision Update` etc.). The review lane's emitter sets
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

- **D-70-19: The phase closes on a DISARMED live mixed batch whose runData matches the
  walker.** After the operator deploys and bounces (disarmed, both write flags `"false"`), one
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

### Deferred Ideas (OUT OF SCOPE)

Confidence policy (a new person is held by design, D-61-03 — `ALL_HOLD_CODES` and
`min_confidence` untouched); named-account scoring; anything in the ICP engines
(`src/icp_scoring.py`, `Decide Company Action`'s veto block); the review-queue / review-
decision / backend-status endpoints' response shape (they stay body-responding queries,
D-70-08); the unattended gate (still shut). Binding on all six (SAFE-01..05) applies unchanged;
nothing is armed during the phase. Reviewed and NOT folded into this phase:
`2026-08-04-enrichment-throughput-ceiling.md`, `2026-09-04-company-domain-has-no-candidate-
source.md`, `2026-09-07-merge-enriched-ignores-jobtitles-own-protect-if-current-present.md`,
`2026-09-08-forbidden-name-markers-refuse-secretary-and-armidale.md`,
`2026-09-04-website-less-company-search-fallback.md`,
`2026-09-05-fallback-is-keyed-on-ladder-empty-not-round-empty.md`,
`2026-09-04-walk-provenance-locator-names-last-page-only.md`.

</user_constraints>

<phase_requirements>
## Phase Requirements

No milestone requirement IDs exist for this phase (added after `v1.2-REQUIREMENTS.md` was cut).
Every plan must instead trace to one or more of D-70-01..19 above.

| ID | Description | Research Support |
|----|-------------|------------------|
| D-70-01 | Explicit Merge at every convergence point; delete `nodeRunRecovery.js` | §"Convergence point inventory" gives the exact node/edge-count list per workflow; §"D-70-02" gives the Merge-hang risk that makes this NOT a drop-in replacement without D-70-14's IF-shaping and an upstream "always emit ≥1 item per lane" guarantee. |
| D-70-02 | executionOrder v0→v1 flip, doc-grounded | §"D-70-02 research" below — full answer with citations. |
| D-70-03 | Retire every by-name read (23+ targets) | §"By-name read inventory" — full grouped list with line numbers, including the 6 sites that use `recoverConvergedRun`'s injected `$(name)` (dynamic, NOT literal-matched by a `$('` grep — a gap in the locked assertion's own wording, flagged). |
| D-70-04 | Carry mechanism across HTTP hops | §"D-70-04 research" below — full answer with citations. |
| D-70-05..11 | Client result channel (runData-always) | §"Client-side inventory" — `watch.recover_async_dispatch`, `report.all_node_items`, `report.reconcile` already exist and are the generalisation target. |
| D-70-12..15 | Write-gate contract | §"Write-gate inventory" — `_write_gate_js`/`splice_write_gates` call sites (only 3, not the same 3 CONTEXT.md's stale line numbers point at), plus the enrichment lane's DIFFERENT (undocumented) gate shape that D-70-13's "three splice sites" premise does not currently cover. |
| D-70-16..19 | Harness + UAT shape | §"Offline harness inventory", §"Validation Architecture". |

</phase_requirements>

## Summary

This phase retires one idiom with two faces: (1) an n8n execution-order fact this repo has
never verified against a real convergence point under load, and (2) a client that today reads
two different channels (HTTP sync body, execution runData) depending on a flag nobody
consistently sets. Both delegated questions (D-70-02, D-70-04) resolve to the SAME underlying
constraint, confirmed independently by n8n's own docs and by multiple, dated (2022–2024)
community bug reports that remain open patterns in the product today: **an n8n Merge node in
Append/Combine mode "waits for the execution of all connected inputs" — and when an inbound
branch produces zero items, it never executes at all, so the Merge hangs forever waiting for
input that will never arrive.** This is exactly the shape of every convergence point this
repo's own JSON confirms (`Enrichment Gate` 5 inbound edges from mutually-exclusive identity
lanes; `Build Response` 10 inbound edges; `Company Gate` 2; `Merge Winners`/`Merge Company` 3
each) — a normal batch uses ONE lane, not all of them, so "the branch that lost never even ran"
is the common case, not an edge case. D-70-01's literal instruction ("an explicit Merge node at
every convergence point") is achievable, but only if every upstream terminal node feeding a
Merge input has **"Always Output Data"** enabled (a real, documented per-node setting,
independently of executionOrder) — otherwise the very Merge nodes this phase adds will hang the
whole execution on the first batch that doesn't exercise every lane, which is worse than today's
silent-collapse bug. `executionOrder` v0 vs v1 is orthogonal to this hang risk (it governs the
ORDER same-level nodes fire in, not whether a zero-item branch counts as "executed") and the
flip is not required to fix the hang — but D-70-19's disarmed live run should observe it anyway
because this repo has never run any workflow under v1.

For D-70-04, the fewest-nodes candidate (`this.helpers.httpRequest`/`httpRequestWithAuthentication`
inside a Code node) is documented for n8n's node-*building* API, and a Cloud-specific community
report shows it was broken (`this.getNode is not a function` — wrong `this` binding inside the
Code node's sandbox) as late as v1.36.1, fixed in v1.42.0 — version-dependent and genuinely
unverified on this account's current n8n Cloud build, matching CONTEXT.md's own framing. The
Merge-combine-by-position candidate is the one grounded entirely in documented, stable Merge
semantics and needs no credential-reachability assumption at all — it is the recommended
mechanism, at the acknowledged node-count cost.

**Primary recommendation:** keep `executionOrder` absent/legacy for this phase (the hang risk is
identical under v1 and the flip is a separate, all-workflows-at-once behaviour change with no
offsetting benefit for THIS problem) — DEFER the flip and record it as an explicit open
decision, not a silent no-op; use Merge (Append/Combine, N inputs) at every convergence point
BUT gate that recommendation on enabling "Always Output Data" on every lane-terminal node
feeding it (a builder-level requirement this research adds to D-70-01, since the locked
decision's own wording does not mention it and its absence would ship a regression); and for
the HTTP-hop carry problem, use Merge (Combine by Position, 2 inputs: the HTTP response + a
pass-through of the prior Code node's row) inserted immediately after each HTTP node, never
`this.helpers.httpRequest` inside Code.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Row identity resolution (email/name/linkedin/fetch-by-id lanes) | n8n workflow (Code nodes) | HubSpot API (search) | Lane-splitting and search-result adaptation happen entirely inside the generated n8n graph; HubSpot is the external system queried. |
| Convergence / fan-in of lanes | n8n workflow (native Merge node, post-phase) | — | This is the phase's own subject: today it is a Code-node-with-multiple-inbound-edges anti-pattern; the fix is n8n's own native primitive. |
| Write permission (allowlist gate) | n8n workflow (Code node, `_writeSafetyAllows`) | — | Deliberately kept OUT of HubSpot and out of the client — a build-time-asserted, single JS predicate is the whole safety story (SAFE-01..05). |
| Result delivery to the operator's session | Python client (`operator-claude-plugin/scripts/watch.py`, `report*.py`) | n8n Executions API | The workflow's own synchronous HTTP response becomes a pure ack (D-70-07); every row-level fact is read back from the settled execution's runData via the n8n REST API — an API surface, not the workflow's own output channel. |
| Offline correctness proof | Node.js test harness (`tests/n8n/`) | — | A pure JS execution-order simulator over the COMMITTED JSON — no live n8n access, by design (D-70-16). |
| Live differential proof | n8n Cloud (disarmed) | Python driver scripts | The one place `[documented]` claims about Merge/executionOrder get upgraded to `[observed live]` (D-70-19). |

## D-70-02 research — executionOrder v0 vs v1, and Merge behaviour when an input never fires

### What is actually set today

`[VERIFIED: n8n/wf_enrichment_cloud.json, n8n/wf_contact_ingest_cloud.json, n8n/wf_review_decision_cloud.json, n8n/wf_scheduled_maintenance_cloud.json, n8n/wf_backend_status_cloud.json — top-level "settings" key, read this session]`
All five committed cloud workflows carry `"settings": {}` — `executionOrder` is present as a key
in NONE of them (not `"executionOrder": "v0"`, just absent). Per n8n's own docs (quoted below),
an absent value means the workflow runs under the **legacy** order. This matches CONTEXT.md's
own claim and the debug session's prior finding — independently re-confirmed this session by
reading the JSON directly, not by re-citing the earlier claim.

Also confirmed this session: **zero** `n8n-nodes-base.merge` nodes exist across all five
workflows (`[VERIFIED: same 5 files, "type" field of every node, read this session]`). Every
convergence point today is a Code node (`n8n-nodes-base.code`, typeVersion 2) with more than one
inbound `connections` edge — there is no existing Merge node whose behaviour could be observed
in this repo's own history. D-70-19's disarmed live run will be the FIRST time this repo ever
runs a native Merge node.

### The two orderings, quoted

`[CITED: docs.n8n.io/build/flow-logic/understand-execution-order]`
> **Legacy (pre-1.0):** "n8n executes the first node of each branch, then the second node of
> each branch, and so on."
> **Version 1.0+ (v1):** "executes each branch in turn, completing one branch before starting
> another. n8n orders the branches based on their position on the canvas, from topmost to
> bottommost."
> "You can change the execution order in your workflow settings... your existing workflows will
> use the legacy order, while new workflows will execute using the v1 order."

This describes **breadth-first-by-depth (v0/legacy)** vs **depth-first-per-branch (v1)** —
it governs the RELATIVE ORDER in which independent branches' nodes fire, not whether a branch
that produces zero items still counts as "having executed" for a downstream node waiting on it.
Nothing in this page (nor any other n8n docs page reachable this session) states that v1 changes
whether a zero-item branch is treated as "ran" vs "never ran." **No page found states execution-
order-dependent Merge-wait semantics one way or the other; this is an absence of documentation,
not a documented equivalence between v0 and v1 on this specific question.**

### What actually happens when a Merge input never fires — the load-bearing finding

`[CITED: docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.merge]`
> Append mode: "Keep data from all inputs... The node waits for the execution of all connected
> inputs."

`[CITED: community.n8n.io/t/how-to-converge-two-branches-when-only-one-branch-runs/240128]`
> User's own diagnosis, unchallenged in the thread: "Merge waits for _all_ inputs"; "Since one
> branch never runs, Merge blocks forever." "Append / Combine don't help because the missing
> branch never executes."
> A community moderator's suggested workaround: "You need to use the merge node with combine by
> position" — i.e. a DIFFERENT Merge mode, not a settings flip.

`[CITED: community.n8n.io/t/merge-node-dont-wait-for-all-inputs/135843]`
> Original poster explicitly wanted the Merge node to "only proceed when both inputs are
> available"; notes the "Wait" mode that used to exist for exactly this "is no longer available
> in v1.88.0." A second community member confirms this is a persistent, dated problem, citing
> multiple related bug-report threads back to 2023.

`[CITED: github.com/n8n-io/n8n/issues/3949]` (closed, labeled "Released" — i.e. this specific
report was fixed in some later version, but the CLASS of problem — "does not wait until both
inputs are given; executes when previous nodes were [not yet / never] executed" — recurs across
multiple, later-dated community threads, meaning the fix did not eliminate the class):
> "The Merge Node in Mode 'Wait' does not wait until both inputs are given. It already executes
> when previous Nodes were executed."

**Conclusion, stated plainly for the planner:** an inbound branch to a Merge node that produces
zero items (the exact, NORMAL shape of a batch that only exercises one of the identity lanes, or
a batch where `IF Company Skip`'s true lane fires for every row) is documented behaviour
elsewhere in n8n's own model as "the downstream node never runs" — and multiple independent,
dated community reports (2022–2024, still linked from n8n's own current forum as "related
topics," meaning this remains a live pattern people hit) confirm the practical consequence: a
Merge node in Append/Combine mode configured to "wait for all inputs" **either hangs
indefinitely or (per the earlier bug reports) fires prematurely on partial data** — neither
outcome is what D-70-01 needs (a single, complete run over every row that fired).

This is `[CITED]`, not `[VERIFIED]` — no page or thread found states unambiguously and
authoritatively "this is fixed as of version X and here is the exact current contract." The
absence of an authoritative, current, exhaustive statement is itself informative under the
`<absent-evidence provenance rule>`: it means the safe design assumption is "an all-skip lane
still needs to be represented on every Merge input," not "Merge will figure it out."

### The documented mitigation, and why it is load-bearing for D-70-01

`[CITED: multiple community threads found via WebSearch, "Always Output Data" node setting]`
> "The 'Always Output Data' setting makes the node return an empty item even if the node returns
> no data during execution... found in the node's Settings tab... You should be careful setting
> this on IF nodes, as it could cause an infinite loop."

This is a genuine per-node n8n setting (not this repo's invention). Its effect — a node that
would otherwise produce zero items instead emits exactly one placeholder item — is precisely
what turns "the branch never executed" into "the branch executed with one (marker) item," which
is what makes a Merge node's "waits for the execution of all connected inputs" contract
satisfiable for a lane that legitimately has nothing to contribute in a given batch.

**Recommendation for D-70-01 (an addition, not a contradiction, to the locked decision):**
every terminal node immediately upstream of a Merge input — i.e., the last node in EACH lane
before it reaches a convergence point (`Adapt Search`, `Adapt Name Search`, `IF Name
Searchable`'s false branch, `Adapt Linkedin Search`, `Adapt Fetch By Id`, `IF Company Skip`'s
true branch, and the write-gate's refused-row output under D-70-14) — must have "Always Output
Data" enabled, OR the fan-out IF node feeding it must be restructured so every lane always
produces at least an empty marker row (e.g., an explicit "no rows for this lane" sentinel item
the Merge then filters back out downstream). Without this, D-70-01's Merge nodes will introduce
a NEW failure mode (a hang, on Cloud manifesting as an execution stuck in `running` until some
timeout) strictly worse than today's silent row-collapse, on the exact batch shape (single-lane,
which is the common case) that the mixed-batch acceptance test (D-70-17) is specifically NOT
testing (it only tests the 2-lane × 2-action case).

### Recommendation: do NOT flip to v1 for this phase

- The hang risk above is unaffected by v0 vs v1 (nothing found ties it to execution order —
  it is about whether a zero-item output counts as "the input arrived," which v0/v1 does not
  touch per the docs quoted).
- v1 IS a genuine, all-five-workflows-at-once behaviour change (CONTEXT.md's own framing,
  "one-way in effect") with no offsetting benefit identified for the specific problem this
  phase solves. Flipping it introduces a second live-behaviour variable into the SAME disarmed
  proof run (D-70-19) that is supposed to validate the Merge/write-gate changes — conflating
  two independent risks in one observation.
- **Do it as a separate, later, isolated change** if the operator wants v1's ordering
  guarantees for some other reason. This research recommends AGAINST bundling it into Phase 70.
- D-70-19's disarmed run should still explicitly log `settings.executionOrder` from the live
  workflow body (as the F5 investigation already did) so the `[documented]`→`[observed live]`
  upgrade CONTEXT.md asks for happens on the ACTUAL setting the workflow ran with (absent/legacy),
  not on a hypothetical v1 run this phase never performs.

## D-70-04 research — the HTTP-hop carry mechanism

### The constraint, confirmed in this repo's own code

`[VERIFIED: n8n/code/matchProposal.js:14-15 header comment, read this session; scripts/build_cloud_workflows.py lines 4017-4029, 4121-4125, 6194-6199, read this session]`
Every provider/HubSpot HTTP node in this repo replaces `$json` with the raw HTTP response —
confirmed by the pattern at, e.g., line 4022: `json_body="={{ JSON.stringify($('Build
Requests').item.json.lusha_body) }}"` — the node immediately AFTER an HTTP node still reads the
PRE-http row by name (`Build Requests`), because its own `$json` is the HTTP response, not the
row. This is the literal mechanism D-70-04 must replace.

### Candidate (b): `this.helpers.httpRequest`/`httpRequestWithAuthentication` inside a Code node

`[CITED: docs.n8n.io/connect/create-nodes/build-your-node/reference/http-request-helpers]`
> "For requests without authentication, use `const response = await
> this.helpers.httpRequest(options)`. For requests with authentication, use `const response =
> await this.helpers.httpRequestWithAuthentication.call(this, 'credentialTypeName', options)`."

This page documents the helper for people BUILDING custom n8n community nodes (the
"Connect > Create Nodes" doc tree), not explicitly the end-user-facing Code node — the helper
object happens to be the same one, but the page's own authority is about node development, so
this is `[CITED]`, not `[VERIFIED]`, for "the Code node exposes this."

`[CITED: community.n8n.io/t/what-is-the-equivalent-http-request-with-auth-in-code-node/45387]`
> A user ON N8N CLOUD (version 1.36.1) hit `this.getNode is not a function` calling
> `this.helpers.httpRequestWithAuthentication.call(this, ...)` inside a Code node. A maintainer
> (`netroy`) explained: "The issue here is that `this` in
> `this.helpers.httpRequestWithAuthentication.call(this` is not `IExecuteFunctions`, but the
> global object of the sandbox." The maintainer states the fix "was fixed and released in
> 1.42.0."

**Interpretation:** credential-authenticated HTTP calls from inside a Code node were CONFIRMED
BROKEN on n8n Cloud as recently as v1.36.1, due to the Code node's sandbox rebinding `this`
away from the execute-context object the helper expects. It was fixed in 1.42.0 — a specific,
dated version, not "always worked." This repo has no record of which n8n Cloud build this
account currently runs (no version pin found anywhere in the repo — `[VERIFIED: absence check;
grepped package.json, CLAUDE.md, docs/*.md, .planning/*.md for an n8n version string, found
none]`), so whether the account is past 1.42.0 is **unverified**, matching CONTEXT.md's own
framing exactly ("credential reachability from Code on Cloud is UNVERIFIED"). Even if fixed on
the current build, this candidate:
- Requires every hop's Code node to carry its OWN credential reference (today, credentials are
  attached to native HTTP Request nodes via n8n's credential picker UI/API, not passed as a
  string secret into jsCode — `scripts/deploy_n8n_workflows.py`'s `NODE_CREDENTIAL_MAP` binds
  credentials by NODE NAME after deploy, a mechanism that assumes native HTTP Request nodes
  exist to bind to).
- Trades an "unverified but possibly working" runtime dependency for a strictly SMALLER node
  count, but the downside (a silent regression the day n8n changes sandbox behaviour again,
  with no test able to catch it offline since the harness is pure JS with no real n8n sandbox)
  is asymmetric with the upside.

### Candidate (a): Merge (Combine by Position) immediately after each HTTP node

`[CITED: docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.merge]`
> "The items passed into Input 1 of the Merge node will take precedence. For example, if the
> Merge node receives five items in Input 1 and 10 items in Input 2, it only processes five
> items." (Combine mode's "combine by position" pairs item _i_ of input 1 with item _i_ of
> input 2.)

Mechanism: after each HTTP node, add a Merge (Combine, "Combine by Position", 2 inputs) whose
Input 1 is the HTTP node's own output (the response) and whose Input 2 is a pass-through of the
row that went INTO the HTTP node (wired from the SAME upstream node the HTTP node's own input
came from — i.e., a literal fan-out: one edge into the HTTP node, one edge into the Merge's
second input, both from the same source node). This is exactly what CONTEXT.md's own framing
names ("Merge combine-by-position per hop"). It is:
- **n8n-native and needs no credential/sandbox assumption at all** — the strongest point in its
  favour, and the reason this research recommends it over (b).
- Dependent on **1:1 item order** surviving the hop — CONTEXT.md flags this ("relies on 1:1
  item order incl. `continueOnFail`"). `[VERIFIED: scripts/build_cloud_workflows.py, every
  onError site, grepped this session per the F5 post-fix self-check already on file — all say
  `onError: "continueRegularOutput"`]` — an HTTP failure lands as an ITEM on the regular output
  (never a separate error branch), so item COUNT is preserved on failure; whether item ORDER
  is preserved (HubSpot/provider APIs called per-item, one HTTP execution per row, in the SAME
  order items entered) needs to be verified per node at build time — n8n's own docs do not make
  an explicit ordering guarantee for parallel/batched HTTP calls, so this is a risk to design
  around (e.g., stamp a `row_id`/`_carry_index` field the HTTP node's URL or body echoes back
  as a query param or header where the API allows it, and use Combine-by-Fields on that key
  instead of raw position, wherever the target API supports echoing an opaque token).
- Costs ~15–20 new nodes per workflow (CONTEXT.md's own estimate), which is the SAME node-count
  growth this research's D-70-01 addendum (Always Output Data / marker rows) also needs to
  reason about — the two changes compound, not independently.

### Candidate (c): other documented options considered and rejected

- **`itemMatching` / n8n's automatic paired-item lineage.** `[CITED: this repo's own
  nodeRunRecovery.js header comment, which itself investigated and rejected this — read this
  session]`: "`$('Node').itemMatching(currentNodeInputIndex)` is a second, lineage-based
  primitive that survives HTTP-hop $json replacement without any run-index arithmetic at all...
  it requires every intervening node between the Gate and the reader to preserve n8n's automatic
  paired-item linking (a real but unverified assumption)... whereas the scan-based fix depends
  only on documented, already-confirmed `.all(branch,run)` semantics." D-70-01 itself already
  REJECTS this exact primitive ("per-item `pairedItem` lineage... HTTP hops break it"). Not
  re-litigated here — CONTEXT.md's own rejection stands and this research agrees with its
  reasoning.
- **HTTP Request node "echo the input" option.** No such option exists in the HTTP Request
  node's documented parameter set found this session (Body/Headers/Query/Auth/Options — none
  echo arbitrary prior-node JSON back onto the response). Rejected for lack of a mechanism.
- **`Execute Workflow` per item.** Technically possible (n8n supports `mode: each`, already used
  elsewhere in this repo for `SJ-3 Dispatch To Enrichment` and the scale-up fan-out) but converts
  every provider HTTP call into a full sub-workflow invocation — a much larger structural change
  than a Merge insertion, with its own cost/latency implications (§13.0.3: sub-workflow
  executions are `[documented]` as neither billed nor concurrency-capped, but `[not verified
  against billing]`) and no mechanism advantage over (a) for THIS specific problem. Rejected as
  disproportionate.

### Recommendation

**Use candidate (a) — Merge (Combine by Position, 2 inputs) immediately after every HTTP node**,
grounded entirely in documented Merge semantics and requiring no assumption about Code-node
sandbox/credential behaviour that this repo cannot verify offline. Where an API allows echoing
an opaque row-identifying token (query param, header, or a field the API itself passes through
in its response body), prefer Combine-by-Fields keyed on that token over raw positional Combine,
to remove the item-order dependency entirely — decide per HTTP node at build time, not
universally.

## Package Legitimacy Audit

Not applicable — this phase adds no new npm/pip/cargo package. It uses only n8n's own built-in
node types (`n8n-nodes-base.merge`, already present in every n8n install this repo targets) and
existing Python stdlib (`ast`, already used by `test_report_sufficiency.py`'s poll-loop guard).

## Standard Stack

### Core
| Component | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `n8n-nodes-base.merge` | typeVersion 3 (current n8n; confirm against the account's build before generating) | Explicit convergence for D-70-01 | n8n's own native primitive for combining branches — the only alternative to the by-name-read anti-pattern this phase retires. `[ASSUMED: typeVersion 3 — not independently confirmed against this account's exact n8n Cloud build this session; the builder should read the account's current node-type schema via a disarmed API probe before hard-coding a typeVersion, the same discipline `_normalize_hubspot_auth` already applies to credential shapes]` |
| n8n Executions API | current (already in use) | The client's sole result channel per D-70-05 | `watch.py`/`executions_client.py` already call it; no new integration surface. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Merge (Combine by Position) after HTTP hops | `this.helpers.httpRequest` in Code | Fewer nodes, but Cloud sandbox `this`-binding was confirmed broken through v1.36.1 (fixed 1.42.0) — version-dependent, unverified here, and untestable offline. |
| A native Merge node at every convergence point | Keep `nodeRunRecovery.js`, extend its coverage | Rejected by D-70-01 outright — cheaper short-term, but the locked decision explicitly retires this pattern; not re-argued here. |

**Installation:** none — no new dependency of any kind.

## Architecture Patterns

### System Architecture Diagram

```
HubSpot / operator client                     n8n Cloud (5 workflows, all executionOrder:
        |                                      absent/legacy, zero native Merge nodes today)
        |  POST /hubspot/enrichment/event                                     |
        |  POST /hubspot/contact-upload                                       |
        v                                                                     v
+-------------------+        +------------------------------------------------------------+
| dispatch.py       |------->| Webhook Trigger -> Parse HubSpot Event -> Build Identity    |
| chunking.py       |        |   -> IF Has Email / IF Linkedin / IF Name Searchable /      |
| (mints run_id)    |        |      IF fetch_by_id  (mutually exclusive identity lanes,    |
+-------------------+        |       each may fire with ZERO rows in a given batch)        |
        |                    |        |        |         |            |                    |
        | (ack only,         |        v        v         v            v                    |
        |  D-70-07)          |   [ HTTP: HubSpot Search per lane -- $json replaced ]        |
        |                    |        |  <-- carry mechanism (D-70-04): Merge combine-      |
        |                    |        |      by-position, NOT by-name $('Prev').item        |
        |                    |        v                                                    |
        |                    |  [ CONVERGENCE: Enrichment Gate / Company Gate ]             |
        |                    |    (today: 5-/2-way Code-node fan-in, by-name .all() reads   |
        |                    |     recovered via nodeRunRecovery.js;                        |
        |                    |     after D-70-01: native Merge, N inputs, EVERY lane's      |
        |                    |     terminal node has "Always Output Data" set)               |
        |                    |        |                                                     |
        |                    |        v                                                     |
        |                    |  [ Normalize+Score -> Decide Action -> write_request ]        |
        |                    |        |                                                     |
        |                    |        v                                                     |
        |                    |  [ Write Gate (D-70-12..15): reads ONLY write_request,        |
        |                    |    IF-shaped -- permitted -> HubSpot Create/Update;           |
        |                    |    refused -> action:"write_blocked" row, SAME Merge input ] |
        |                    |        |                        |                            |
        |                    |        v                        v                            |
        |                    |  [ Merge before Build Response (D-70-01) ]                    |
        |                    |        |                                                     |
        |                    |        v                                                     |
        |                    |  [ Build Response (10 inbound edges today) ]                  |
        |                    |        |                                                     |
        |                    |        +--> Respond to Webhook (ACK ONLY, D-70-07)            |
        v                    +------------------------------------------------------------+
+-------------------+
| watch.py           |  GET n8n Executions API, poll bounded by run_id (D-70-05, ALWAYS,
| recover_async_     |  sync and async) -> report.all_node_items(runData, "Build Response")
| dispatch (D-70-05) |  -> report.reconcile against the WRITE node's own output (D-70-06)
+-------------------+
        |
        v
  operator-facing report (run_report.py, persisted, D-70-08a)
```

### Convergence point inventory — `[VERIFIED: read this session via a Python script over the connections map of each committed JSON]`

| Workflow | Node | Inbound edge count |
|---|---|---|
| `wf_enrichment_cloud.json` (123 nodes) | `Build Response` | **10** |
| | `Enrichment Gate` | 5 |
| | `Respond to Webhook` | 4 |
| | `Parse HubSpot Event` | 3 |
| | `Merge Winners` | 3 |
| | `Merge Company` | 3 |
| | `IF Apollo Enabled` | 2 |
| | `IF ZoomInfo Enabled` | 2 |
| | `Normalize + Score` | 2 |
| | `ZoomInfo Enrich` | 2 |
| | `Company Gate` | 2 |
| | `Decide Company Action` | 2 |
| | `IF Apollo Org Enabled` | 2 |
| | `IF ZoomInfo Company Enabled` | 2 |
| | `Normalize + Score Company` | 2 |
| | `ZoomInfo Company` | 2 |
| | `ZoomInfo Usage` | 2 |
| `wf_contact_ingest_cloud.json` (29 nodes) | `Build Ingest Response` | 2 (`HubSpot Associate Company`, `Set Review`) |
| | `Build Association Request` | 2 (`HubSpot Update`, `HubSpot Create`) |
| `wf_review_decision_cloud.json` (26 nodes) | `Build Review Response` | 3 |
| | `Review Extract Record` | 2 |
| | `Review Queue Rows` | 2 |

**17 convergence points in the enrichment workflow alone, 2 in ingest, 3 in review-decision —
22 total candidates for a Merge node under D-70-01**, none of them today a native Merge (all
are `n8n-nodes-base.code`, typeVersion 2, confirmed by node type across all 5 files this
session). `wf_scheduled_maintenance_cloud.json` (39 nodes) and `wf_backend_status_cloud.json`
(17 nodes) have **zero** multi-inbound nodes and zero `$('` reads (confirmed by the by-name
grep below returning no hits in either file's constants) — consistent with §13.0.2's "no
scheduled path carries request-level flags" and confirms these two workflows are OUT of this
phase's real scope despite `splice_write_gates` running against `wf_scheduled_maintenance_cloud`
(see Write-gate inventory below — that call site is maintenance, not "enrichment" as CONTEXT.md's
stale line number implied).

`Build Response`, `Merge Winners`, `Merge Company`, `Enrichment Gate`, `Company Gate` are ALL
`n8n-nodes-base.code` (typeVersion 2) — `[VERIFIED: node "type" field read this session]`. A
Code node has exactly ONE output. This is the concrete reason D-70-14's "IF-shaped" gate cannot
be a Code node emitting to two places: it must become (or be followed immediately by) a native
`n8n-nodes-base.if` node, which is n8n's only two-output primitive at this typeVersion.

### Respond to Webhook fan-in (enrichment lane) — `[VERIFIED: connections map, read this session]`

Four inbound edges today, exactly matching CONTEXT.md's framing:
```
IF List Expanded  -> branch 1 -> Respond to Webhook
Build Async Ack   -> branch 0 -> Respond to Webhook
Build Scale Up Ack -> branch 0 -> Respond to Webhook
Build Response    -> branch 0 -> Respond to Webhook
```
`Respond to Webhook` is `n8n-nodes-base.respondToWebhook`, typeVersion 1.1. Under D-70-07 only
`Build Async Ack` should feed it after this phase — the other three edges are removed, and each
of `IF List Expanded`'s false-branch refusal, `Build Scale Up Ack`'s dispatch confirmation, and
`Build Response`'s per-row outcome must become rows the client reads back from runData instead
(D-70-07's own explicit list: `IF Object Type Supported` false, `recompute_refused`,
`write_blocked`, list-expansion refusals).

`Build Response`'s 10 inbound edges, named (`[VERIFIED: connections map]`): `IF Enrich` (branch
1), `HubSpot Create`, `HubSpot Update`, `Skip (NoOp)`, `IF Company Skip` (branch 0), `Build
Research Failure Response`, `IF Company Enrich` (branch 1), `Adapt Company Create`, `HubSpot
Company Update`, `Unsupported Object Type`. This is the single richest convergence point in the
whole system and the one most exposed to the Merge-hang risk documented under D-70-02 — MOST of
these 10 branches are near-certainly empty on any given real batch (a batch is never
simultaneously a create, an update, a skip, a company-skip, a research failure, a company
create, a company update, AND an unsupported object type).

`Merge Winners` / `Merge Company` are misleadingly named (they are pre-existing Code nodes
performing candidate-merge LOGIC, per CLAUDE.md §15.0's "material-conflict suppression" —
NOT n8n Merge nodes). Fed by `IF Contact Research Needed`/`IF Contact Needs Judge`/`Apply
Contact Judge Verdict` (3 inbound) and the companies equivalent (3 inbound) respectively — both
are convergence points needing an ACTUAL Merge node under D-70-01, separate from and upstream of
their own existing candidate-merge logic, which stays untouched (out of scope — the ICP engines
are explicitly deferred).

### By-name read inventory — `[VERIFIED: scripts/build_cloud_workflows.py, grepped this session]`

`grep -o "\$('[^']*')"` finds **25 distinct literal targets** (close to, not identical to,
CONTEXT.md's "23" — the discrepancy is plausibly a handful of comment-only mentions on either
side of the count; the planner should re-derive the count from the builder at plan time rather
than trust either number):

```
Adapt Company Search · Build Company Identity · Build Company Link · Build Company Requests
Build Identity · Build Requests · Build Research Request · Build Review Decision
Company Gate · Enrichment Gate · HubSpot Company Fetch By Id · HubSpot Company Search
HubSpot Fetch By Id · HubSpot Linkedin Search · HubSpot Name Search(+Fallback) · HubSpot Search
HubSpot Search by Email · Normalize Phone · Parse HubSpot Event · Parse Review Decision
Parse Review Queue Request · Set Config · Status Credit Request · Verify Emails (batch)
ZoomInfo Enrich
```

Grouped by workflow and read shape:

**Ingest lane** (`build_local`/`build_cloud`, ~L148-700): `Normalize Phone` `.all()`,
`Verify Emails (batch)` `.first()`, `HubSpot Search by Email` `.all()`, `Set Config` `.first()`
(shared constant), `Build Company Link` `.all()` (the 2026-08-25 association resolution).

**Contacts identity lanes** (`ENRICH_ADAPT_*`, shared across local/local-live/cloud, ~L1571-1580
and ~L5254-5353): `Build Identity` `.all().filter(lane===...)` (4 call sites, one per lane) +
matching `HubSpot Fetch By Id` / `HubSpot Name Search` (+`Fallback`) / `HubSpot Linkedin Search`
`.all()` per lane. Plus `Build Identity` `.item.json...` reads inside IF-node condition
expressions and Set-node value expressions (~L5662-5753) — these are NOT `.all()`/`.first()`
reads at all; they are `.item` reads embedded directly in n8n node PARAMETERS (not jsCode),
which is a different retirement shape than a Code node's `$input` rewrite — the builder needs a
parameter-expression rewrite path, not just a jsCode one.

**`Enrichment Gate` reads deep in the research/judge request builders** (~L5889-5954): `.item`
reads of `existingRecord`, `identity_keys`, `gate` — these are INSIDE
`ENRICH_BUILD_REQUESTS`/similar, reading `Enrichment Gate` by name for fields the research/judge
HTTP request bodies need. **This is a SEPARATE exposure from the F5-fixed `.all()` collapse** —
it uses `.item` (paired-item lookup, not run-indexed `.all()`) and is NOT wrapped in
`recoverConvergedRun` — flagged as a gap the F5 fix did not cover, worth an explicit check
during D-70-03 implementation (a mixed batch with providers ENABLED, unlike the propose-mode
batch F5 was diagnosed on, may expose a live defect here that this session cannot observe).

**Companies lane**: mirrors contacts (`Build Company Identity`, `HubSpot Company Search`,
`Adapt Company Search`, `HubSpot Company Fetch By Id`, `Build Research Request` inside a
try/catch).

**HTTP node body-building expressions** (~L4017-4029, 4121-4125, 6194-6199): `Build
Requests`/`Build Company Requests` `.item.json...` read directly inside `json_body=` HTTP-node
parameters — THE canonical instance of the D-70-04 problem (the node immediately after reads the
PRE-http row because the HTTP node's own `$json` is the response).

**Request-level flag reads**: `Parse HubSpot Event` `.first()` (×5, `recompute`/config
echoes) and `.item.json.provider_enabled.<name>` (a per-provider expression generated
dynamically at L3985) — D-70-03 explicitly calls these out as in-scope even though they read a
SINGLE-run node (no convergence risk), because the locked decision is "no `$('X')` of any form,"
full stop.

**Review-decision / backend-status lanes**: `Parse Review Queue Request` / `Parse Review
Decision` / `Build Review Decision` / `Status Credit Request`, all `.first()` — single-run reads
in a workflow with genuine convergence points (`Build Review Response` etc., 3 inbound) that
this inventory's convergence table above already lists.

### The `recoverConvergedRun` sites — a SEPARATE class D-70-03's literal wording may miss

`[VERIFIED: n8n/code/nodeRunRecovery.js and its 6 call sites in scripts/build_cloud_workflows.py, read this session]`
`recoverConvergedRun` (the F5 fix) is invoked via `(name, b, r) => $(name).all(b, r)` where
`name` is a **JS variable holding the node name string**, not a literal `$('...')`. A build-time
assertion that greps generated jsCode for the literal substring `$('` will **not** catch this —
`$(name)` has no quote character adjacent to the paren. D-70-01 explicitly deletes
`nodeRunRecovery.js` and its 7 call sites (this session counted 6 distinct call sites: 2 via
`_zoom_preamble`, 2 via `_zoom_split_gate_js`, 2 via `_zoom_split_cache_js`, each reused across
contacts/companies/credit-usage — CONTEXT.md's "seven" and this session's "6 distinct call
sites" both undercount/overcount depending on whether reused-function invocations count once or
per-reuse; re-derive at plan time), so the DELETION resolves this regardless — but if D-70-01's
Merge rollout is staged (some convergence points fixed before others), the assertion must be
written to also flag `$(<any-identifier>)` — not just the literal-quote form — or a
partially-migrated intermediate state could pass the assertion while still calling
`recoverConvergedRun` in code the assertion was supposed to make impossible.

### Write-gate inventory — `[VERIFIED: scripts/build_cloud_workflows.py, read this session]`

`splice_write_gates()` is defined once (L7641) and called from exactly **3** sites — but NOT the
three CONTEXT.md's stale line-number citations name:

| Call site (line, current) | Workflow | Gated nodes |
|---|---|---|
| L1086 | **ingest** (`build_cloud`) | `HubSpot Update`: `"enrich"`, `HubSpot Create`: `"create"`, `HubSpot Associate Company`: `"enrich"` |
| L7989 | **scheduled maintenance** (`build_scheduled_maintenance_cloud`) — NOT enrichment | `SJ-1 Set Requested`, `SJ-2 Set Requested`, `Dedupe Set Needs Review`, `Review Apply Update`, all `"enrich"` |
| L8675 | **review-decision** (`build_review_decision_cloud`) | `Review Decision Update`, `Review Contact Decision Update`, both `"review"` |

**The enrichment lane (`build_enrichment_cloud`) never calls `splice_write_gates` at all.**
Its write permission check is instead embedded DIRECTLY inside `Decide Action`/`Decide Company
Action`'s own jsCode (`WRITE_SAFETY_GATE_JS` is concatenated into `ENRICH_DECIDE_CLOUD` at
L1730 and `ENRICH_DECIDE_CO_CLOUD` at L3635), computing `_writeSafetyAllows(...)` and setting
`action = "write_blocked"` BEFORE the `IF Enrich`/`IF Company Enrich` split — there is no
separate, spliced gate NODE standing in front of `HubSpot Create`/`HubSpot Update`/`HubSpot
Company Update` on this lane at all.

**This is a material correction to D-70-13's premise** ("all three splice sites, one shape").
There are not three splice-gate sites with one shape today needing standardisation — there is
ONE splice-gate mechanism (`splice_write_gates`, used by ingest, maintenance, and review-decision
— note maintenance is a FOURTH consumer CONTEXT.md's decision list does not mention at all,
though its gated writes are all `"enrich"` on record-level flags, not create/update/associate,
so D-70-13's "all three splice sites" may have meant to exclude maintenance deliberately) and a
SEPARATE, structurally different inline-precheck mechanism unique to the enrichment lane that
has no spliced gate node counterpart today. Unifying "all three" onto one `write_request` shape
per D-70-12 therefore requires the enrichment lane to GAIN an actual spliced gate node it does
not have today (not just change the shape of a fallback ladder it already has) — a materially
larger structural change on that lane than on ingest/review-decision, which only need their
EXISTING gate's field-reads narrowed to the one canonical shape.

`HubSpot Associate Company` is gated INDEPENDENTLY of `HubSpot Update` today (both spliced
separately at L1086's ingest call) — `[VERIFIED]` confirms D-70-15's premise exactly ("the
second gate copy on the association path is removed").

`ADAPT_COMPANY_CREATE`'s join-by-value pattern (matching a create HTTP response back to its
planning row via `domain`, since index alignment is lost downstream of the write IFs) is the
SAME idiom `Build Association Request` (ingest) and `Build Ingest Response`'s `nodeAll('HubSpot
Associate Company')` sourcing (the F1 fix) already use — a reusable, already-proven pattern for
"how do I re-attach identity to a write node's own response," directly relevant to D-70-06.

### Offline harness inventory — `[VERIFIED: tests/n8n/, ls'd this session]`

84 `.mjs` test files exist under `tests/n8n/` (not "50" — CONTEXT.md's "the 50 `new Function`
tests" is either a subset count or stale; re-derive at plan time). The seed file named by
D-70-16, `enrichmentGateRunRecoveryFlow.test.mjs`, and its sibling `nodeRunRecovery.test.mjs`,
both exercise the F5 fix directly and are explicitly named for retirement/supersession. Files
explicitly named in CONTEXT.md for retirement or rewrite (`ingestWebhookRespondsAllEntries`,
`ingestUpdateWriteBlockedFlow`, `ingestUpdateGateDomainFallback`, `ingestReviewBranchResponds`,
`asyncAck`, `nodeRunRecovery`, `contactCreateGateFlow`, `companyAssociationFlow`,
`pairPipelineAssociationFlow`) all exist and were all touched by the 2026-09-09 F1-F12 fixes
(confirmed against the debug log's own `files_changed` lists).

`report.py::all_node_items(run_data, node_name)` **already exists** (landed in gap-closure
plan 62-11, `[VERIFIED: operator-claude-plugin/scripts/report.py, function signature read this
session]`) — it concatenates every run of a named node in order, which is EXACTLY the primitive
D-70-16's walker needs for "asserts rows at `Build Response`" and is already proven live against
a real multi-run split (executions 12096/12098). This is a direct reusable asset, not something
the walker needs to invent from scratch on the Python side — though the walker itself is a
**Node.js** artifact (`tests/n8n/`), so this is a design-parity reference, not a shared import.

### Client-side inventory — `[VERIFIED: function signatures read this session]`

`watch.py` already implements exactly the mechanism D-70-05 generalises:
- `find_executions_by_run_id(config, run_id, ...)` — scans recent executions, matches on
  `Parse HubSpot Event`'s own echoed `run_id` (exact match, via `_execution_carries_run_id`).
- `_build_response_rows(execution)` — reads EVERY run of `Build Response` via
  `report.all_node_items` (already fixed for the multi-run case per 62-11).
- `recover_async_dispatch(config, run_id, expected_chunk_count, ...)` — the ONE sanctioned
  bounded-poll site in the whole plugin (enforced by `test_report_sufficiency.py`'s AST-based
  guard: no other `operator-claude-plugin/scripts/*.py` file may import `time`/`sched`, call
  `sleep`, or contain a `while` loop — `watch.py` is the sole, explicit exception).

`report.py::reconcile(ledger, run_data)` already implements D-70-06's exact rule ("only report
the success label when [the write] node actually produced output items... downgrade to
`not_confirmed`") — for the ingest lane's `contact_row_ledger`/`WRITE_NODE_FOR_ACTION` mapping.
The enrichment lane's equivalent (`report_enrichment.py::enrichment_row_ledger`) exists as a
separate, parallel implementation — D-70-06's generalisation should check whether it can share
`reconcile`'s logic or needs its own parity-tested twin (Phase 46 parity discipline).

`report.py::sync_response_is_sufficient(body)` is the EXACT mechanism that currently lets a
caller fall back from "trust the sync body" to "read runData instead" — its docstring already
states the review-queue-marker-only body (`{"queue": "needs_review"}`, F1's bug shape) is
insufficient BY DESIGN. Under D-70-05 ("ALWAYS" runData, sync included), this function's role
inverts: today it's a fallback trigger; after the phase, every caller skips straight to runData
and this function's callers change from "if insufficient, escalate" to unconditional — the
function itself may become dead code, or may be repurposed as a defensive sanity-check.
Removing vs. repurposing it is a Claude's-Discretion-adjacent implementation choice, not
pre-decided by CONTEXT.md.

The 7 named repo scripts POSTing to the webhook were all confirmed to exist this session:
`enrich_coverage_companies.py`, `fix_sfv_region.py`, `probe_company_propose_mode.py`,
`probe_n8n_async_semantics.py`, `prove_scale_up_runtime.py`, `remediate_veto_companies.py`,
`rescore_population.py`. Three (`fix_sfv_region.py`, `probe_company_propose_mode.py`) read
`response.json()` directly and would need migration or deletion under D-70-08; two
(`probe_n8n_async_semantics.py`, `prove_scale_up_runtime.py`) are one-shot semantics probes whose
findings are already captured as historical VERDICT JSON files (§13.0.3's own citations) — good
deletion candidates per D-70-08's explicit allowance ("a script that no longer has a purpose may
be deleted instead of migrated"). `rescore_population.py` shows no direct `response.json()`
pattern in this grep (likely already routes through `chunking.dispatch_plan` or similar) — worth
confirming at plan time rather than assuming either way.

`test_report_sufficiency.py`'s poll-loop guard (`_POLL_LOOP_ALLOWED = {"watch.py"}`) is the
concrete enforcement mechanism the plan must respect: any new runData-recovery logic for
`enrich-records`/`scheduled_arm.py`/the repo scripts must call INTO `watch.py`'s existing
functions, never re-implement a bounded wait loop in its own file, or this test fails by design.

### Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Combining N mutually-exclusive lane outputs into one row set | A new by-name recovery scheme, or a bespoke JS "wait for all my named upstream nodes" helper | `n8n-nodes-base.merge` (Append/Combine) | It is n8n's own primitive for exactly this, and D-70-01 locks it in; the risk is not "should we build vs. use it" but "did we account for its documented all-inputs-must-execute contract" (see D-70-02 research). |
| Re-attaching a row's identity to an HTTP response | Another bespoke `nodeAll('X').find(...)`-by-value join, invented per hop | The already-proven `ADAPT_COMPANY_CREATE`/`Build Association Request` join-by-value idiom, generalised, OR Merge combine-by-position (D-70-04's recommendation) | Two independent, already-working patterns exist in this repo for "reconnect a write response to its planning row" — reuse one rather than inventing a third. |
| Bounded polling for a settled execution | A second `while`/`sleep` loop in any newly-migrated script | `watch.recover_async_dispatch`, called from the new site | `test_report_sufficiency.py` structurally forbids a second poll site; this is enforced, not just conventional. |

**Key insight:** almost every mechanism this phase needs already exists somewhere in this repo
in a partial or single-lane form (`report.all_node_items`, `report.reconcile`,
`recover_async_dispatch`, `ADAPT_COMPANY_CREATE`'s join-by-value). The work is generalising and
standardising these, not inventing new primitives — except for the Merge-node insertion itself
and the write-gate's IF-shaping, which are genuinely new to this codebase (zero native Merge
nodes exist anywhere in the committed JSON today).

## Common Pitfalls

### Pitfall 1: A Merge node that "fixes" F5 by hanging instead of collapsing
**What goes wrong:** D-70-01's Merge nodes are inserted at convergence points fed by mutually
exclusive lanes; a real batch commonly exercises only ONE lane, so N-1 of the Merge's inputs
never receive an execution at all.
**Why it happens:** n8n's own documented Merge (Append/Combine) contract is "waits for the
execution of all connected inputs" — and multiple community reports (2022-2024) confirm a branch
that never executes leaves the Merge either hanging indefinitely or firing on incomplete data,
depending on n8n version/mode.
**How to avoid:** enable "Always Output Data" on every lane-terminal node feeding each Merge
input (a documented per-node setting), or explicitly emit a marker/sentinel item for an empty
lane and filter it downstream of the Merge.
**Warning signs:** any execution that reaches `running` and never settles on n8n Cloud during
disarmed testing; a mixed-batch test that only passes when EVERY lane has ≥1 row (the acceptance
test in D-70-17 tests exactly 2×2 — verify it ALSO covers "only one lane populated," which is the
common real-world case the walker's own unit tests should add per D-70-18).

### Pitfall 2: Treating the `$('` grep as the complete by-name-read surface
**What goes wrong:** a build-time assertion literally matching the substring `$('` misses
`recoverConvergedRun`'s `$(name)` dynamic-variable call form, and misses `.item` reads embedded
in n8n node PARAMETER expressions (IF conditions, Set-node values) rather than jsCode strings.
**Why it happens:** the locked decision's wording (`"$('"` ) names the literal pattern that
happens to be everywhere ELSE in this codebase, but `nodeRunRecovery.js`'s whole design point was
to avoid that literal pattern while still doing a by-name read.
**How to avoid:** write the assertion as "any occurrence of `$(` followed by anything that
resolves to a node-name lookup" (a broader AST/regex check, or — simpler — assert
`nodeRunRecovery.js` is not imported/inlined anywhere AND grep both the literal `$('` and the
bare `$(` call form), and separately walk every node's `parameters` tree (not just `jsCode`
strings) for the same patterns.
**Warning signs:** the assertion passes but `n8n/code/nodeRunRecovery.js` still exists on disk
and is still `inline()`d somewhere.

### Pitfall 3: Assuming the enrichment lane's write-gate is "the same shape, needs new field names"
**What goes wrong:** planning D-70-12/13 as a pure field-rename (swap the fallback ladder for
`write_request`) on all "three" sites, when the enrichment lane has no spliced gate NODE at all
today — its check is inline inside `Decide Action`.
**Why it happens:** CONTEXT.md's own decision text describes "three splice sites" as if
symmetric; the actual code has one spliced mechanism (3-4 call sites, none of them enrichment)
and one separate inline mechanism (enrichment only).
**How to avoid:** budget the enrichment lane's write-gate work as "add a new spliced gate node
this lane has never had," not "rename fields on an existing node."
**Warning signs:** a plan task that says "update ENRICH_DECIDE_CLOUD's gate field names" without
also adding a call to (an extended) `splice_write_gates` for `HubSpot Create`/`HubSpot
Update`/`HubSpot Company Update`.

### Pitfall 4: Losing the `Enrichment Gate` `.item`-based research/judge reads in the F5 fix's shadow
**What goes wrong:** treating "the by-name-read problem" as fully solved by
`recoverConvergedRun` (which only covers the `.all()` collapse), when a SEPARATE set of `.item`
reads (`ENRICH_BUILD_REQUESTS` etc., L5889-5954) reads `Enrichment Gate` by name for
research/judge HTTP bodies, unprotected by any run-recovery mechanism, and untested by the
propose-mode UAT (providers were disabled, so this code path never ran).
**Why it happens:** F5's fix scope was scoped to the symptom observed (a propose-mode batch with
providers off); this `.item` exposure sits downstream, only reachable when providers/judge are
armed.
**How to avoid:** include this site explicitly in D-70-03's retirement scope and D-70-17's
acceptance test design (or at minimum, in the walker's OWN unit-test fixtures per D-70-18, since
no live batch this session or the UAT ever exercised it).
**Warning signs:** a live batch with real provider/judge escalation returning research data for
the wrong row — the exact "identity contamination" class F5 already found once at the ZoomInfo
Token Gate, one hop further down the same chain.

## Code Examples

### The join-by-value idiom for re-attaching identity after a write (already proven in this repo)

```javascript
// Source: scripts/build_cloud_workflows.py, ADAPT_COMPANY_CREATE (read this session)
function nodeAll(name) { try { return $(name).all(); } catch (e) { return []; } }
const decided = nodeAll('Decide Company Action').map((it) => it.json);
return $input.all().map((it) => {
  const res = it.json || {};
  const companyId = res.id != null ? String(res.id) : null;
  const domain = (res.properties && res.properties.domain) || null;
  const row = domain
    ? decided.find((r) => r.properties && r.properties.domain === domain)
    : null;
  const companyDependencyId = domain ||
    (row && row.properties && row.properties.name) || null;
  return { json: { ...res, company_dependency_id: companyDependencyId, company_id: companyId } };
});
```
This STILL reads `Decide Company Action` by name — it is itself an instance of the pattern
D-70-03 retires, and must be rewritten to receive the row via the Merge (combine-by-position)
carry mechanism D-70-04 selects, not preserved as-is.

### The existing generalized runData reader (already correct, promote rather than rewrite)

```python
# Source: operator-claude-plugin/scripts/watch.py::_build_response_rows (read this session)
def _build_response_rows(execution) -> list:
    run_data = report._run_data(execution)
    if run_data is None:
        return []
    items = report.all_node_items(run_data, report_enrichment.BUILD_RESPONSE_NODE)
    return [item["json"] for item in items if isinstance(item, dict) and isinstance(item.get("json"), dict)]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| n8n Merge node "Wait" mode | Removed (deprecated) as of n8n v1.88.0 per community report | community-reported, unverified exact date | The specific mode CONTEXT.md's earlier debug session might have expected no longer exists; Append/Combine's "waits for the execution of all connected inputs" contract is the current model. |
| `.all()` bare by-name read | `.all(branchIndex, runIndex)` documented, but still by-name | n8n's current docs (2026) | Neither form solves the "empty branch never executes" hang; both are retired here in favour of a native Merge. |

**Deprecated/outdated:**
- The "Wait" Merge mode this repo's own earlier debug session considered and implicitly assumed
  might exist (per the community thread quoted above) is gone in current n8n; do not plan
  around it.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `n8n-nodes-base.merge` typeVersion is 3 on this account's current n8n Cloud build | Standard Stack | Builder generates a node with an unsupported typeVersion; deploy fails or n8n silently coerces it. Mitigate: probe the account's node-type schema (disarmed) before hard-coding, or use `_normalize_hubspot_auth`'s own discipline of adapting to what's live. |
| A2 | Merge's Append/Combine "waits for all inputs" contract, when combined with "Always Output Data" on every lane terminal, reliably prevents the hang — this session found no authoritative n8n doc CONFIRMING the combination works, only community reports that "Always Output Data" is the standard workaround for the underlying "branch never fires" problem in general (not specifically tested against Merge) | D-70-02 research | If the combination does not fully close the hang risk, D-70-19's disarmed live run is the first and only place this would be caught before the operator arms anything — treat that run's Merge-node behaviour observation as load-bearing, not a formality. |
| A3 | `this.helpers.httpRequestWithAuthentication`'s Cloud sandbox bug (confirmed through v1.36.1, fixed 1.42.0) does or does not still affect this account's current build | D-70-04 research | Irrelevant to the final recommendation (candidate (a) was chosen specifically to avoid this dependency) but relevant if a future phase reconsiders candidate (b). |
| A4 | The count of distinct by-name read targets (23 per CONTEXT.md vs. 25 counted this session) and of `nodeRunRecovery.js` call sites (7 per CONTEXT.md vs. 6 distinct call sites counted this session) | By-name read inventory, `recoverConvergedRun` sites | Low — either count is a starting inventory for the builder-level assertion to enforce exactly, not a number anything downstream depends on being precise. |

**If this table is empty:** not applicable — see rows above.

## Open Questions

1. **Does "Always Output Data" on a lane-terminal node, combined with a native Merge node, actually prevent the hang in practice on THIS account's n8n Cloud build?**
   - What we know: both are independently documented n8n features; no page or thread found tests them together explicitly.
   - What's unclear: whether n8n Cloud's current build has any residual timing/race behaviour (per the older, closed "Released" bug reports) that resurfaces under this specific combination.
   - Recommendation: D-70-19's disarmed live run is the correct, already-planned place to observe this — the plan should treat "Merge behaves as documented under Always-Output-Data" as an explicit pass/fail criterion of that run, not an assumed given.

2. **What n8n Cloud build/version is this account actually on?**
   - What we know: no version pin exists anywhere in this repo.
   - What's unclear: whether the account is past the 1.42.0 fix for Code-node credential access (moot for this phase's recommendation, but relevant context for whether candidate (b) becomes viable in a future phase).
   - Recommendation: a disarmed read of the n8n Cloud instance's own `/rest/login`-adjacent version endpoint (or the UI's "About" panel) would answer this cheaply; not required to unblock this phase's plan.

3. **Does the enrichment lane's `.item`-based `Enrichment Gate` reads inside research/judge HTTP body builders (L5889-5954) exhibit the SAME cross-run contamination class F5 found at the ZoomInfo Token Gate, one hop earlier in the same chain?**
   - What we know: it is structurally the same "read a multi-run node by name with no run-index arithmetic" shape; unlike the `.all()` sites, it uses `.item`, whose semantics under multiple runs were not independently checked this session.
   - What's unclear: whether n8n's `.item` accessor for a multi-run node has the same "most recent run" default n8n's docs state for `.all()`, or a different (paired-item) resolution rule.
   - Recommendation: cover this explicitly in the walker's own unit tests (D-70-18) with providers/judge enabled, since neither the F5 live trace nor the 2026-09-09 UAT ever exercised it (propose mode had providers off).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| n8n Cloud (Starter plan) | All backend changes | ✓ (existing account) | Unpinned/unknown in-repo — see Open Question 2 | none needed — this phase does not require a plan upgrade |
| n8n Executions API + API key (`n8n_api_key`) | D-70-05's runData-always client channel | ✓ historically used by `watch.py`/`executions_client.py` | — | D-70-10 already specifies the fallback: refuse before start, never a time-proximity guess |
| Node.js (for `tests/n8n/*.mjs`) | D-70-16 walker | ✓ (existing suite, `node --test tests/n8n/*.mjs`, glob form — directory form broken on node 24, per memory `shell-grep-is-rtk-wrapped`-adjacent note in project memory) | current | — |
| Python + `.venv` | Client migrations | ✓ (existing) | — | — |

**Missing dependencies with no fallback:** none identified.
**Missing dependencies with fallback:** none beyond D-70-10's own already-specified refusal-before-start for a missing executions-API key.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Node's built-in `node:test` (JS side, `tests/n8n/`); `pytest` (Python side, `operator-claude-plugin/tests/` and root `tests/`) |
| Config file | none — bare `node --test`; `pytest.ini`/equivalent not located this session, assume defaults per project memory `test-suite-run-commands` |
| Quick run command | `node --test tests/n8n/*.test.mjs` (glob form — directory form broken on node 24, per project memory) |
| Full suite command | `.venv/bin/python -m pytest -q --tb=short` (root, ~4600+ tests per the debug log's own baselines) plus `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` (plugin, ~2850+) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| D-70-01/16 | Graph walker replays the committed JSON's execution order, including Merge semantics | unit (walker's own tests) | `node --test tests/n8n/<new-walker>.test.mjs` | ❌ Wave 0 — new file |
| D-70-17 | One mixed-batch (2 lanes × 2 actions) acceptance test per lane, every row returns exactly once | integration (walker-driven) | `node --test tests/n8n/<enrichmentMixedBatch>.test.mjs` / `<ingestMixedBatch>.test.mjs` | ❌ Wave 0 — new files |
| D-70-18 | Walker's own unit tests prove it detects the F5-style collapse and the double-Respond-fires-once class | unit | same walker test file, additional cases | ❌ Wave 0 |
| D-70-03/04 | Build-time assertion: zero `$('` (and dynamic `$(name)`) reads in generated jsCode/expressions | unit (builder-level) | new `tests/test_no_by_name_reads.py` or equivalent, run against `scripts/build_cloud_workflows.py`'s own generation | ❌ Wave 0 |
| D-70-05..11 | `watch.recover_async_dispatch` generalised to the sole channel, sync included | unit + integration | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_watch.py -q` (extend existing) | ✅ file exists, extend |
| D-70-06 | `report.reconcile`/`report_enrichment` read the write node's own output, not the decision | unit | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_report.py operator-claude-plugin/tests/test_report_enrichment.py -q` | ✅ (assume existing — confirm at plan time) |
| D-70-12..15 | Canonical `write_request` shape asserted at generation time; gate is IF-shaped, emits refusals | unit | `node --test tests/n8n/<writeGateShape>.test.mjs`; `tests/test_write_gate_coverage.py` (extend) | ✅ extend existing |
| D-70-19 | Disarmed live mixed batch, runData shape-equal to the walker's prediction | live (disarmed) | manual/scripted per `scripts/prove_async_recovery.py`'s precedent | ✅ precedent exists, adapt |

### Sampling Rate
- **Per task commit:** `node --test tests/n8n/*.test.mjs` (fast, offline) for any n8n JSON/builder
  change; `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` for any client change.
- **Per wave merge:** full root suite `.venv/bin/python -m pytest -q --tb=short`.
- **Phase gate:** full suite green (both node and python) before `/gsd-verify-work`; D-70-19's
  disarmed live run before the phase can close.

### Wave 0 Gaps
- [ ] `tests/n8n/<walker>.mjs` (or `.js` module + tests) — the D-70-16 graph walker itself; nothing like it exists today (`enrichmentGateRunRecoveryFlow.test.mjs`'s `makeDollar` is the closest seed and is explicitly named for supersession).
- [ ] Build-time assertion in `scripts/build_cloud_workflows.py`'s `main()` (currently has ZERO assertions of any kind — confirmed by reading `main()` this session) for D-70-03/04.
- [ ] Mixed-batch acceptance tests for both lanes (D-70-17) — do not exist today under any name.
- [ ] An explicit "only one lane populated" test case, added to the walker's own unit tests, given the Merge-hang risk this research surfaces (see Pitfall 1) — not named by any locked decision but strongly recommended as a Wave 0 addition given the risk is otherwise invisible until D-70-19's live run.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (unchanged) | Existing native `headerAuth` on both webhooks, untouched by this phase. |
| V3 Session Management | no | N/A — stateless webhook + polled executions API, unchanged. |
| V4 Access Control | **yes** | The write-gate contract (D-70-12..15) IS this system's access-control layer for HubSpot writes. Standard control: the existing `_writeSafetyAllows`/allowlist predicate, now asserted single-shape and never bypassable via a fallback field ladder (D-70-12 explicitly deletes the BUG-27 fallback ladder that was itself found via a live canary). |
| V5 Input Validation | **yes** | The canonical `write_request: {action, hs_object_id, domain, email}` shape (D-70-12) IS an input-validation contract between n8n nodes; the build-time assertion enforcing "every gated node's upstream emits `write_request`" (also D-70-12) is a structural input-validation gate, not runtime-only. |
| V6 Cryptography | no | Unchanged — no new secret handling; Merge/HTTP nodes carry no new credential material beyond what the existing HTTP nodes already hold. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A refused write silently reported as succeeded (F12's exact historical shape) | Repudiation / Tampering-adjacent (false audit record) | D-70-06/14: the row's outcome of record is the WRITE node's actual output; a refusal is emitted as `write_blocked`, never silently coerced to the pre-block intent. |
| A batch losing rows across a multi-run convergence (F5's exact historical shape) | Information Disclosure by omission / Repudiation (a written record nobody can account for) | D-70-01's native Merge + D-70-16's walker proving the class is caught offline before any live batch. |
| A gate's own allowlist field-name drift (F11's exact historical shape, BUG 27's original instance) causing an over- or under-permissive write | Elevation of Privilege (a write that should have been blocked landing) or Denial of Service (a legitimate write blocked) | D-70-12's single canonical shape with no fallback ladder, asserted at build time rather than trusted at runtime. |
| A client believing an ack means "done" when the actual outcome is still pending/unknown | Repudiation (operator acts on a false completion signal) | D-70-05/07: the sync body is explicitly an ack only; the operator-facing report is built exclusively from the settled execution's runData, never from the ack. |

## Sources

### Primary (HIGH confidence — read directly this session)
- `scripts/build_cloud_workflows.py` (8778 lines) — by-name read inventory, write-gate call
  sites, `main()`'s assertion-free generation, all `Decide Action`/`Decide Company Action`
  write-permission logic.
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_contact_ingest_cloud.json`,
  `n8n/wf_review_decision_cloud.json`, `n8n/wf_scheduled_maintenance_cloud.json`,
  `n8n/wf_backend_status_cloud.json` — `connections` maps (convergence-point counts), `settings`
  key (executionOrder absence), node `type`/`typeVersion` fields (zero native Merge nodes
  confirmed).
- `n8n/code/nodeRunRecovery.js` — the F5 fix's own header comment, the best in-repo statement of
  the run-collapse mechanism, and its 6 call sites.
- `operator-claude-plugin/scripts/watch.py`, `report.py`, `report_enrichment.py`, `chunking.py`,
  `written_records.py`, `preingest.py`, `run_report.py`, `run_state.py`, `executions_client.py`,
  `confidence.py`, `scheduled_arm.py` — function signatures and key implementations read this
  session.
- `operator-claude-plugin/tests/test_report_sufficiency.py`, `test_control_flag_parity.py` —
  the poll-loop guard mechanism and declaration-count pinning mechanism.
- `tests/test_write_gate_coverage.py` — the existing structural write-gate coverage test.
- `.planning/debug/resolved/uat-batch-review-row-reads-failed.md` (985 lines, read in full) —
  every F1-F12 finding, root cause, fix, and live proof.
- `.planning/todos/pending/2026-09-09-n8n-lanes-reconverge-by-name-reads-one-result-channel.md`.
- `.planning/phases/70-.../70-CONTEXT.md`, `.planning/STATE.md` (partial), `.planning/config.json`
  (`nyquist_validation`/`security_enforcement` both `true`).

### Secondary (MEDIUM confidence — official n8n docs, fetched this session)
- `docs.n8n.io/build/flow-logic/understand-execution-order` — legacy vs v1 execution order,
  quoted verbatim.
- `docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.merge` — Append mode's "waits for
  the execution of all connected inputs," Combine-by-Position's precedence rule.
- `docs.n8n.io/connect/create-nodes/build-your-node/reference/http-request-helpers` —
  `this.helpers.httpRequest`/`httpRequestWithAuthentication` signatures.

### Tertiary (LOW confidence — community reports, cross-checked across multiple independent threads)
- `community.n8n.io/t/how-to-converge-two-branches-when-only-one-branch-runs/240128` — Merge
  hangs forever when a branch never executes; "combine by position" workaround suggested.
- `community.n8n.io/t/merge-node-dont-wait-for-all-inputs/135843` — "Wait" mode removed by
  v1.88.0; persistent, dated community problem.
- `github.com/n8n-io/n8n/issues/3949` — historical "Wait" mode bug, closed/released.
- `community.n8n.io/t/what-is-the-equivalent-http-request-with-auth-in-code-node/45387` — Cloud-
  specific Code-node `this`-binding bug through v1.36.1, fixed 1.42.0.
- General WebSearch summaries for "Always Output Data" (multiple community threads,
  cross-checked, not individually fetched for verbatim quotes beyond what's cited above).

## Metadata

**Confidence breakdown:**
- D-70-02 (executionOrder/Merge): MEDIUM — official docs plus multiple independent, dated,
  mutually-reinforcing community reports, but no single authoritative "here is the exact current
  contract" source; the recommendation (Always Output Data + defer the v1 flip) is a synthesis,
  not a direct quote.
- D-70-04 (carry mechanism): MEDIUM — the eliminating fact for candidate (b) (Cloud sandbox
  `this`-binding bug) is a single community thread, version-specific and possibly stale; the
  recommended candidate (a) rests on stable, well-documented Merge semantics.
- Repo-code findings (by-name inventory, convergence points, gate call sites, client functions):
  HIGH — read directly this session, file:line cited throughout.
- Validation Architecture / Security Domain: MEDIUM — derived from existing test infrastructure
  patterns (`test_report_sufficiency.py`, `test_write_gate_coverage.py`) that are real and
  read this session, extended by inference to the new artifacts this phase needs.

**Research date:** 2026-09-09
**Valid until:** 30 days for the in-repo findings (stable until the next builder change); the
n8n docs/community citations should be re-checked if the operator's n8n Cloud account has
auto-updated by the time D-70-19's live run happens, since Merge/Code-node sandbox behaviour is
exactly the kind of thing n8n has changed between minor versions historically (per the 1.36.1→
1.42.0 fix cited above).
