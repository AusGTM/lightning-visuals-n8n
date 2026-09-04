# Phase 61 Plan 01: Async Run Substrate Spike — Verdict

**Purpose:** decide what n8n Cloud's execution model actually permits for submit/poll/resume,
before 61-05 plans a single task against it (D-61-08). No live calls were made to produce this
document — every claim below is `[measured]` (read out of live execution history already
committed to this repo), `[derived]` (arithmetic over a measured or documented input, inputs
named), `[documented]` (an n8n behaviour stated in this repo's own code comments/config, or a
planning document already in this repo), or `[unknown]` (would need a live call; the exact
read-only command follows).

**Client-side run id is already solved (D-61-08).** `chunking.dispatch_plan(..., run_id=None)`
already mints a `run_id` client-side, before any HTTP call, whenever the caller omits one
(`operator-claude-plugin/scripts/chunking.py:336-337`), and every chunk it sends flushes into
`written_records.written_records_path(run_id)` under that same id. "Submit returns a run id"
therefore needs no new mechanism on any substrate below — the caller can mint the id BEFORE the
submit call and pass it in. What each substrate actually answers is narrower: can PROGRESS be
read back against that id WHILE the run is still going.

**Status:** Complete. Tasks 1-3 produced this document and its completeness test. Task 4 — the
operator's run-state decision and disposition of every `## Unresolved` entry — ran on 2026-08-30;
see `## Operator Decision (Task 4)` at the end of this document. All six premises that closed
`## Unresolved` on the first pass (P-05, P-07, P-08, P-09, P-10, P-13) are now answered — three
from n8n's own published documentation, three from a live disarmed probe the operator authorised
— and are recorded below with their basis tokens updated in place.

## Substrates

### 1. Respond-immediately — `responseMode: responseNode`, Respond node moved to the front of the chain

The deployed enrichment workflow already uses `responseMode: responseNode`
(`scripts/build_cloud_workflows.py:4752-4757`), but its "Respond to Webhook" node sits at the END
of the chain today, fed by the "Build Response" convergence after every terminal branch — the
response only fires once the whole batch's work is already done, which is why the ~100s ceiling
binds the batch size today. This candidate moves the Respond node to fire immediately after
`Parse HubSpot Event`, before the provider/Haiku/Sonnet chain runs, and lets the rest of the
chain continue after the response has already gone out.

- Q-01 — a request whose Respond node fires immediately closes the client's own HTTP connection before the ~100s Cloudflare ceiling starts counting against it, because that ceiling bounds the client's round trip, not server-side work after the response (`operator-claude-plugin/scripts/chunking.py`'s own module docstring names "a ~100 s Cloudflare ceiling" on "every record in a POST"). `[derived]`
- Q-01 — the REMAINING chain DOES keep executing on this n8n Cloud account once its own triggering webhook's response has already been sent: a disarmed live probe on 2026-08-30 (execution `12035`) sent a 5s `Wait` between a Respond node and a `Set` node, the client's round trip closed in 0.47s, and the `Set` node's `runData` recorded `success` at an execution span of 5.06s — the chain ran to completion after the caller had already moved on. `[measured]` — Source: `61-PREMISE-PROBE-VERDICT.json` (P-07).
- Q-02 — a durable handle is available to return the moment Respond fires, with no extra work: the caller's own minted `run_id` (see the intro above) can be echoed straight back in the response body, since it exists before the request is even sent. `[documented]` (repo source: `chunking.py:336-337`)
- Q-02 — n8n's own execution id (`$execution.id`) is a separate handle this workflow could also return, since it is assigned at the start of execution and would be readable at a Respond node placed this early — but neither deployed workflow references `$execution.id` today (`operator-claude-plugin/scripts/executions_client.py`'s own D-12 note), so wiring it in is new work, not a re-discovery. `[documented]` (repo source: executions_client.py's D-12 note)
- Q-03 — whether an execution that is actively running (not parked in any n8n "waiting" state) survives an n8n Cloud platform restart mid-run is not established anywhere in this repo; nothing here exercises this case today. `[unknown]` — command: ask n8n Cloud support directly whether an in-progress (non-waiting) execution resumes, errors visibly, or silently vanishes across a platform-side restart or redeploy of this account's instance; this cannot be answered from the client side without n8n operations access.
- Q-04 — this substrate does not fork the pipeline into more executions than today's shape: one webhook call still runs one execution end to end (the code after Respond is the same chain, just re-ordered), so its per-record/per-chunk execution cost is the same arithmetic as the baseline (substrate 4, below). `[derived]` — see `## Execution arithmetic`.

### 2. Wait node + `$execution.resumeUrl`

The Wait node's webhook-resume mode parks an execution and hands back a URL
(`$execution.resumeUrl`) that a later external call can hit to continue it — the mechanism this
task names by name. Nothing in this repo uses a Wait node anywhere (a repo-wide search for
`n8n-nodes-base.wait` outside the vendored `.venv` returns zero hits), so every claim below is
either the feature's bare existence or explicitly unknown.

- Q-01 — a Wait node's whole purpose is to detach an execution from any request/response cycle while it is parked, so a run parked this way is not bound by the ~100s ceiling while it waits — that ceiling only ever applied to a synchronous HTTP round trip, and a parked execution is holding no such connection open. `[derived]` (from the ceiling's own documented scope, chunking.py's module docstring, plus the Wait node's documented parking behaviour)
- Q-02 — `$execution.resumeUrl` is itself a durable handle, but a DIFFERENT one from the client-minted `run_id`: it is not minted until the execution actually reaches the Wait node, so it cannot be returned at submit time the way substrate 1's echoed `run_id` can — a caller would need a first response (e.g. a quick Respond node before the Wait) to learn it, or would treat the client-minted `run_id` as the correlating key and `resumeUrl` as an internal-only continuation detail. `[derived]`
- Q-03 — a PARKED execution's resume state survives an n8n Cloud platform restart, for waits offloaded to the database: n8n's own published architecture deliberately offloads a Wait-node execution to the database and reloads it when the resume condition occurs, so it does not depend on the original process staying alive. This carries a hard boundary, load-bearing for design: a wait `>= 65s` is offloaded (restart-safe); a wait `< 65s` stays in-process (NOT restart-safe) — a design that parks work must never use a sub-65s timed wait and call it durable. `[documented]` — Source: `61-PREMISE-DOCS-FINDINGS.md` (P-08, n8n's own published documentation, verified independently by the operator before recording).
- Q-04 — whether a parked-then-resumed execution counts as one execution total, or as two (one up to the park, one from the resume), against the monthly allowance is not established from repo source. `[unknown]` — command: an admin's disarmed test (same shape as substrate 1's Q-01 command, with a Wait node inserted between the two `Set` nodes) reads `GET /api/v1/executions?workflowId=...` (`executions_client.list_executions`) before and after resuming, to see whether one execution id or two appear for the one logical run.

### 3. Sub-workflow dispatch — `Execute Workflow` with wait-for-completion off

`Execute Workflow` (n8n's call-another-workflow node) already appears in this repo's deployed
shape: SJ-3's own dispatcher uses it in "each" mode to fan a chunk out to the enrichment workflow
(`scripts/build_cloud_workflows.py`'s SJ-3 dispatch comment, "an executeWorkflow node in 'each'
mode"). That existing use WAITS for the sub-workflow's own completion before SJ-3's own
execution continues — it is the deployed shape's own per-record dispatch, which is why SJ-3 is
still bound by the same synchronous chain per record it dispatches. This candidate is the SAME
node type with its wait-for-completion setting turned off, so the parent returns immediately
without blocking on the child's result.

- Q-01 — with wait-for-completion off, the calling (parent) execution does not block on the sub-workflow's result, so the parent's own response can return before the sub-workflow's work finishes — the same "response fires before the work" property substrate 1 has, achieved by detaching a child execution instead of re-ordering nodes in one chain. `[derived]` (from the node's documented on/off toggle behaviour and this repo's own existing, waiting use of the same node type)
- Q-02 — the parent's own node output DOES still carry the child's `$execution.id` once wait-for-completion is switched off: a disarmed live probe on 2026-08-30 dispatched a child with `waitForSubWorkflow` off (parent `12036` -> child `12037`) and, as a control, on (parent `12038` -> child `12039`); in both cases the parent dispatch node's own `runData` carried `metadata.subExecution.executionId` naming the child, and the child also appeared in the executions list. Detachment costs no correlation — the off case behaved identically to the on case. `[measured]` — Source: `61-PREMISE-PROBE-VERDICT.json` (P-13).
- Q-03 — a detached child, once dispatched, is not a "parked" execution at all — per Q-01 above it is an actively-running execution to completion, the same class of behaviour P-07 already confirmed live for substrate 1 (an execution keeps running once its own response has left). n8n's published documentation on Wait-node database offload (substrate 2's Q-03) is scoped to genuinely parked/waiting executions, and that citation's own text is explicit that persistence "does not imply recovery from an arbitrary process crash at any arbitrary node — it is a guarantee about parked executions, not about executions generally." The operator's ruling closes this premise as answered under that same documented architecture rather than deferring it; the residual scope caveat above is recorded, not reopened. `[documented]` — Source: `61-PREMISE-DOCS-FINDINGS.md` (P-08) plus the operator's 2026-08-30 ruling closing all six premises.
- Q-04 — this shape costs at minimum 1 execution for the parent's own dispatch call plus 1 execution per detached child, mirroring today's "1 webhook execution per chunk + 1 sub-execution per record" formula that `write_grant.py`'s own `EXECUTIONS_BASIS` already documents as unconfirmed for a multi-chunk grant — so it does not obviously save executions over the baseline; what it changes is TIME (Q-01), not execution count. `[derived]` (repo source: `operator-claude-plugin/scripts/write_grant.py:132-141`) — see `## Execution arithmetic`.

### 4. Today's synchronous client-driven chunk loop, ceiling raised — BASELINE — not eligible

This is the shape this phase exists to replace (D-61-08: "a run bounded by the synchronous
window is not an async run"). It is assessed only so the other three have something to be
measured against; selecting it is not an available outcome of this spike.

- Q-01 — no: every record in one POST runs the full provider + Haiku + Sonnet chain before the response fires, against the ~100s Cloudflare ceiling — that IS the window this shape is bound by, and raising `max_records_per_chunk` only changes how many records fit inside one hit of that same wall, not whether the wall applies. `[documented]` (repo source: `operator-claude-plugin/scripts/chunking.py`'s module docstring, and `operator-claude-plugin/config/operator.local.example.json`'s own `_max_records_per_chunk_note`)
- Q-02 — not needed: the client already holds the full synchronous HTTP response, so there is no separate "handle" to invent — the response IS the answer, which is precisely why this shape is not async at all. `[documented]` (repo source: `chunking.dispatch_plan`'s own return-after-loop-completes shape, `chunking.py:315-417`)
- Q-03 — nothing on the n8n side needs to survive a restart mid-chunk, because every chunk is a discrete client-driven request/response round trip and a timeout is already treated as an ordinary chunk failure the client resumes past: `chunking.dispatch_plan` catches `DispatchError` (a timeout included) per chunk and continues, and each chunk's outcome is flushed inline into `written_records.append_chunk` before the next chunk starts. `[documented]` (repo source: `chunking.py:350-357` and its own D-59-07 inline-flush comment)
- Q-04 — 1 execution for a single-record, single-chunk send, read directly out of live execution history (execution `11960`, `.planning/phases/54-single-pass-armed-dispatch/54-MEASUREMENT.md`). The multi-chunk case has never been counted end to end — the same file's own named residual (WINDOWS.md id 26). `[measured]` (single-chunk figure only) — see `## Execution arithmetic` for the unmeasured multi-chunk case.

## Execution arithmetic

Inputs, all named: `max_records_per_chunk = 2` (`operator-claude-plugin/config/operator.local.example.json:24`,
confirmed by live probe B4 per that file's own provenance note), `n8n_monthly_execution_allowance = 2500`
(same file, line 6), and the one measured execution-count data point this repo owns: 1 execution
for a single-record, single-chunk send (execution `11960`, 54-MEASUREMENT.md).

- Q-05 — chunk count is arithmetic, not measurement, and is identical across all three async substrates and the baseline, because none of them change how a batch is split into chunks of at most `max_records_per_chunk`: a 40-record batch is `ceil(40 / 2) = 20` chunks; a 300-record batch is `ceil(300 / 2) = 150` chunks. `[derived]`
- Q-05 — `write_grant.py`'s own `envelope()` projects `chunk_count + record_count` executions per send (`EXECUTIONS_BASIS`, `write_grant.py:132-141`): for a 40-record batch that is `20 + 40 = 60`; for a 300-record batch, `150 + 300 = 450`. This is arithmetic over a formula, never a live count — 54-MEASUREMENT.md's own single-record test already disagreed with exactly this formula once (projected 2, actually observed 1, `compare_to_projection` verdict `differs`, reproduced verbatim in that file). `[derived]`
- Q-05 — the alternative reading of that same measured data point IS what a real 2-record chunk shows: a live read against this repo's own configured ceiling, execution `11950` (a real historical 2-record chunk, counted from `Parse HubSpot Event`), found the `chunk_count + record_count` formula projected 3 executions while `GET /api/v1/executions?workflowId=...` listed only 1 — a delta of -2, the formula over-states cost. The listed-vs-billed distinction still applies (the executions API and the billing quota are different systems; this measures the list, not the invoice), and the scan was scoped to the enrichment workflow's own id so a child running under a different workflow id would be out of scope either way — but nothing found suggests the cost model UNDER-projects, which is the direction that would matter for a budget guard. Under this reading, a 40-record batch costs on the order of 20 executions and a 300-record batch on the order of 150 — roughly a quarter of the formula-projected figures above. `[measured]` — Source: `61-PREMISE-PROBE-VERDICT.json` and `61-PREMISE-DOCS-FINDINGS.md` (P-10).
- Q-05 — either reading above sits well inside the 2,500/month allowance for both a 40-record and a 300-record batch by itself. `[derived]`
- Q-05 — that comparison is against the plan's CONFIGURED allowance, never against what is actually left of it this month: `write_grant.py`'s own `_ALLOWANCE_GAP` text states plainly that the schedulers have already spent an unknown share of this month's allowance and none of it is subtracted here, because n8n exposes no usage/quota endpoint to an API key. `[documented]` (repo source: `write_grant.py:143-148`, and this project's own v0.8 milestone note that `/api/v1/usage|license|quota` all return 404)
- Q-05 — substrates 1 and 2 add no execution-count multiplier beyond the chunk arithmetic above unless a Wait node's park-then-resume counts as two executions per parked chunk rather than one, which is substrate 2's own Q-04 unknown above. `[derived]`
- Q-05 — substrate 3's arithmetic is superseded by a documented finding this spike did not have when Q-04 was first answered: n8n's own docs state, verbatim, "Sub-workflow executions: When a workflow calls another workflow with the Execute Sub-workflow node, only the parent (top-level) execution counts" — so a parent fanning out to N children costs ONE billable execution, not `1 + N`, and the same doc page states concurrency control "doesn't apply to any other kinds, such as ... sub-workflow executions" — the 5-concurrent Starter cap (Q-06) does not bind the children either. For 40 records this reads as roughly 20 billable executions (one per chunk's parent dispatch, the same chunk arithmetic as every other substrate) rather than 60; for 300 records, roughly 150 rather than 450 — and it is also a confirmed candidate explanation for the P-10 anomaly above (a child execution that was never counted would produce exactly that -2 shortfall). This makes substrate 3 the only candidate that escapes both the execution-count ceiling and the concurrency cap at once. `[documented]` — Source: `61-PREMISE-DOCS-FINDINGS.md` ("The finding that changes the architecture: sub-workflows are doubly exempt").

Progress-read cost, per candidate run-state store, for an illustrative 30-minute run (this
repo's own longest documented single-send bound, `watch.py`'s `DEFAULT_BOUND_SECONDS = 600.0`, is
a SINGLE-send figure — a multi-chunk async run is the reason this spike exists, so 30 minutes is
used here as a clearly-labelled illustrative input, not a measured run length):

- n8n workflow `staticData` has no public read endpoint, so every progress read against a staticData-based run-state store is its own webhook round trip: 1 execution per poll. Using `watch.py`'s own documented backoff schedule `(5, 5, 10, 15, 30, 60)` seconds, widening then flat at 60s (`watch.py:19-24`), a 30-minute run polled on that schedule takes roughly 6 polls to reach the 60s-flat tail (summing to 125s) plus about 28 more 60s-spaced polls to cover the remaining ~1,675s — on the order of 34 executions spent on watching the run, separate from whatever the run itself costs. `[derived]` (arithmetic over watch.py's own documented schedule; the 30-minute run length is illustrative, not measured)
- A HubSpot object (a property or custom object on the run) costs 0 n8n executions per poll — the client reads HubSpot's own API directly instead, which is a HubSpot API call, not an n8n execution, and is therefore invisible to the 2,500/month n8n figure entirely. `[derived]` (mechanical consequence of the read not touching n8n at all)
- The n8n public executions API (`executions_client.py`) costs 0 n8n executions per poll: `GET /api/v1/executions` and `GET /api/v1/executions/{id}` are n8n's own management-plane REST endpoints, not a workflow trigger, so reading them does not run a workflow. `[documented]` (repo source: executions_client.py's own module docstring, "Thin, read-only wrapper over n8n's public API")
- n8n's own published documentation defines billable usage as production workflow executions, not management-API requests, so calling `GET /api/v1/executions` does not itself consume the 2,500/month allowance — no separate billable API-call quota is documented. This does not rule out an undocumented protective rate limit; billing metering and operational rate limiting are different questions, and only the first is answered. `[documented]` — Source: `61-PREMISE-DOCS-FINDINGS.md` (P-05).
- The client's own `run_manifest.py` costs 0 of everything — 0 n8n executions, 0 HubSpot calls — but is readable only by the process that wrote it, which is the constraint that decides whether it is SUFFICIENT rather than whether it is cheap. `[documented]` (repo source: run_manifest.py's own module docstring, "readable only by the process that wrote it")

- Q-06 — yes: n8n Cloud imposes a per-plan concurrent-execution cap, and this account is on Starter — 5 concurrent executions (alongside the 2.5K-executions/month allowance this repo already tracks in `write_grant.py`'s `EXECUTIONS_BASIS`, which matches). Executions beyond the cap queue FIFO and are processed as capacity frees, so exceeding concurrency is a THROUGHPUT bound, not an error condition — a fan-out of 50 does not fail, it drains 5 at a time. The empirical burst test this spike would otherwise have needed is now unnecessary: it could only ever establish an observed floor, and the published figure supersedes it. `[documented]` — Source: `61-PREMISE-DOCS-FINDINGS.md` (P-09).

## Premises

The load-bearing facts 61-05 will be written against. Each entry: a premise id, one sentence, its
basis token, its source, and the plans/tasks that depend on it (REVIEW-04). A premise nothing
depends on is marked `dependents: none (context only)` rather than deleted, so the record of why
it was considered survives.

1. **P-01** — Chunk-count arithmetic (`ceil(n / max_records_per_chunk)`) is identical across all three async substrates and the baseline, because none of them change how a batch is split into chunks. `[derived]` — Source: `operator-claude-plugin/scripts/chunking.py::plan_chunks`. Dependents: 61-05 T2, T3; 61-06 (execution-count check before any larger batch).
2. **P-02** — The client already mints a `run_id` client-side before any HTTP call is sent, via `chunking.dispatch_plan`'s existing `run_id` keyword argument, so no substrate needs to invent a submit-time handle. `[documented]` — Source: `operator-claude-plugin/scripts/chunking.py:315,336-337`. Dependents: 61-05 T2 (REVIEW-C14: mint before submit, pass it in).
3. **P-03** — n8n workflow `staticData` has no public read endpoint, so a progress read against a staticData-based run-state store costs one n8n execution per poll. `[documented]` — Source: this plan's own Task 2 action text (61-01-PLAN.md) and 61-04-PLAN.md's independent HIGH-9 disposition, which states the same fact for an unrelated reason. Dependents: 61-05 T1 (run-state store selection), T3 (poll-loop location); context: 61-04 (cites the same fact to explain why the held queue does not depend on this decision).
4. **P-04** — Reading n8n's own public executions API (`executions_client.py`) costs zero n8n workflow executions per read, because it is a management-plane REST endpoint rather than a workflow trigger. `[documented]` — Source: `operator-claude-plugin/scripts/executions_client.py`'s own module docstring. Dependents: 61-05 T1, T2.
5. **P-05** — n8n's own published documentation defines billable usage as production workflow executions, not management-API requests, so calling `GET /api/v1/executions` does not consume the 2,500/month allowance; no separate billable API-call quota is documented (an undocumented protective rate limit is not ruled out — billing metering and operational rate limiting are different questions). `[documented]` — Source: `61-PREMISE-DOCS-FINDINGS.md` (n8n's own published documentation, verified independently by the operator, 2026-08-30). Dependents: none (context only — Task 4's 2026-08-30 decision selected hubspot-object + client-manifest, not the executions-API store).
6. **P-06** — `run_manifest.py` costs zero n8n executions and zero HubSpot calls, but is readable only by the process that wrote it. `[documented]` — Source: `operator-claude-plugin/scripts/run_manifest.py`'s own module docstring. Dependents: 61-05 T1, T3 (resume-or-fail-loudly).
7. **P-07** — An n8n Cloud execution DOES keep running after its own triggering webhook's response has already been sent (the mechanism substrate 1 depends on entirely): a disarmed live probe (execution `12035`, 2026-08-30) closed the client round trip in 0.47s against a 5s `Wait` node, and the post-Respond `Set` node recorded `success` at a 5.06s execution span. `[measured]` — Source: `61-PREMISE-PROBE-VERDICT.json` (P-07), operator-authorised probe, 2026-08-30. Dependents: 61-05 T1 (substrate 1 is now viable on this premise), T2.
8. **P-08** — A parked (Wait-node) execution survives an n8n Cloud platform restart when its wait is `>= 65s` — n8n's published architecture offloads such waits to the database and reloads them on the resume condition; a wait `< 65s` stays in-process and is NOT restart-safe (hard boundary, load-bearing for design). A detached child (sub-workflow, wait-for-completion off) is not a "parked" state at all — per P-07 it is an actively-running execution to completion — and the operator's 2026-08-30 ruling closes both cases as answered under this documented architecture rather than deferring either; the citation's own residual caveat ("not about executions generally") is recorded, not reopened. `[documented]` — Source: `61-PREMISE-DOCS-FINDINGS.md` (P-08, n8n's own published documentation, verified independently by the operator). Dependents: 61-05 T1, T3 (the "resume or fail loudly" must-have's restart clause).
9. **P-09** — n8n Cloud DOES impose a concurrent-execution cap, per plan: this account is on Starter, 5 concurrent executions, alongside the 2.5K-executions/month allowance already tracked in `write_grant.py`'s `EXECUTIONS_BASIS`. Executions beyond the cap queue FIFO and are processed as capacity frees — exceeding concurrency is a throughput bound, not an error. `[documented]` — Source: `61-PREMISE-DOCS-FINDINGS.md` (n8n's own published plan-tier documentation, verified independently by the operator). Dependents: 61-05 T1 (a fan-out substrate, 2 or 3, now has a known ceiling rather than an unknown one); 61-06 (any concurrent dispatch it might add later).
10. **P-10** — The `chunk_count + record_count` execution-cost formula (`write_grant.py`'s `EXECUTIONS_BASIS`) over-states cost: a real historical 2-record chunk (execution `11950`, this repo's own configured ceiling) projected 3 executions and the executions list showed only 1, a delta of -2. Sub-workflow executions ARE listed by the executions API on this instance (P-13), so the shortfall is not explained by invisible children — the formula's own over-counting is the reading the evidence supports. The listed-vs-billed distinction still applies: this measures what the API lists, not what was billed. `[measured]` — Source: `61-PREMISE-PROBE-VERDICT.json` (P-10), operator-authorised probe, 2026-08-30. Dependents: 61-05 T1 (budget check before any batch of more than one chunk).
11. **P-11** — A 40-record and a 300-record batch both fit within the configured 2,500/month execution allowance under either arithmetic reading of P-10 (per-chunk-plus-per-record, or per-chunk-only). `[derived]` — Source: `## Execution arithmetic` above. Dependents: 61-05 T1 (must_haves truth on budget), T4.
12. **P-12** — That budget comparison is against the plan's CONFIGURED monthly allowance, never against what is actually left of it after this month's schedulers have already run, because n8n exposes no usage/quota endpoint to an API key. `[documented]` — Source: `write_grant.py:143-148`; PROJECT.md's v0.8 note that `/api/v1/usage|license|quota` all 404. Dependents: 61-05 T1, T4; none further (context for every budget claim above).
13. **P-13** — The parent `Execute Workflow` node's own output CAN be correlated to a detached child's execution id when wait-for-completion is off: a disarmed live probe (parent `12036` -> child `12037`, wait-for-completion off; parent `12038` -> child `12039` as an on-control, 2026-08-30) found the parent dispatch node's `runData` carrying `metadata.subExecution.executionId` naming the child in both cases, and the child listed in the executions API both times — detachment costs no correlation. Combined with n8n's documented "sub-workflow executions don't count toward the billable quota or the 5-concurrent Starter cap" (the two-page finding cited at P-05/P-09's sources), this makes substrate 3 the most attractive dispatch mechanism on this plan: unmetered, uncapped, AND observable. `[measured]` — Source: `61-PREMISE-PROBE-VERDICT.json` (P-13), operator-authorised probe, 2026-08-30. Dependents: 61-05 T1, T2 (substrate 3 is now the strongest dispatch candidate); note the deployment-ordering constraint the same probe discovered — n8n refuses to activate a parent whose `Execute Workflow` node references an unpublished child, so any sub-workflow architecture must publish children before the parent.

## Unresolved

**All six premises listed here on the first pass are now resolved.** None was deferred. This
section is retained (rather than deleted) so the record of what was once unknown, who resolved
it, and how, survives — an empty section reads as "nobody checked," and that is not what
happened here.

Three were answered from n8n's own published documentation (verified independently by the
operator against the cited pages before being recorded); three were answered by a live disarmed
probe the operator authorised on 2026-08-30, at a total cost of 5 n8n executions, with every
`ZZ-PROBE-61-*` test workflow swept afterward (instance verified clean). Each entry below records
the original command, whether it was actually run or superseded by documentation, and where the
resolution now lives.

- **P-05** — Original command: an n8n admin reads the account's own n8n Cloud plan/billing terms for any stated API-call quota distinct from workflow executions. Resolution: answered from n8n's own published documentation instead — no separate billable API-call quota is documented; command not run. See `## Premises` P-05.
- **P-07** — Original command: an admin builds a disarmed 3-node test workflow (`Webhook Trigger` -> `Respond to Webhook` -> a delayed `Set` node), triggers it, and reads `GET /api/v1/executions/{id}?includeData=true` to confirm the post-Respond node ran. Resolution: command run live, 2026-08-30 (execution `12035`) — confirmed true. See `## Premises` P-07 and `61-PREMISE-PROBE-VERDICT.json`.
- **P-08** — Original command: ask n8n Cloud support directly whether a parked (Wait-node) or detached-child (sub-workflow) execution resumes across a platform restart. Resolution: answered from n8n's own published documentation instead — database-backed for waits `>= 65s`, in-process (not restart-safe) below that; command not run. See `## Premises` P-08.
- **P-09** — Original command: an n8n admin checks the account's own n8n Cloud plan page for a stated concurrent-execution limit. Resolution: answered from n8n's own published documentation instead — Starter plan, 5 concurrent, FIFO queue beyond that; command not run. See `## Premises` P-09.
- **P-10** — Original command: a disarmed 2-record chunk send, followed by an admin reading `GET /api/v1/executions?workflowId=...` in the narrow window bracketing that one send. Resolution: superseded by reading a REAL historical 2-record chunk already in this account's execution history (`11950`) instead of sending a new one, 2026-08-30 — formula projected 3, list showed 1. See `## Premises` P-10 and `61-PREMISE-PROBE-VERDICT.json`.
- **P-13** — Original command: an admin builds a disarmed 2-workflow test (parent dispatches a child with wait-for-completion off) and reads the parent node's own output for a child execution id. Resolution: command run live, 2026-08-30 (parent `12036` -> child `12037` off; parent `12038` -> child `12039` on-control) — confirmed true both ways. See `## Premises` P-13 and `61-PREMISE-PROBE-VERDICT.json`.

## Operator Decision (Task 4)

**Decided 2026-08-30.** Run state for an async batch run lives in **a HubSpot object plus the
existing client manifest** — a combination of two of the four options this checkpoint offered,
not a single one:

- **Run handle and progress** — a new HubSpot object property (to be created in 61-05), read
  directly against the CRM the operator already uses.
- **Per-row verdicts** — `operator-claude-plugin/scripts/run_manifest.py`, already built; no new
  mechanism needed for this half.

**Operator's stated basis:** this combination depends on NONE of n8n's remaining unknowns, costs
zero n8n executions and zero concurrency slots per progress read, and survives both an n8n
restart and the end of the session that started the run. The executions-API option
(`executions_client.py`) was actively weakened by the sub-workflow findings above, because it
depends on correlating executions — and while P-13 answered that correlation is possible for a
parent-to-child link, the executions-API store itself was not the option chosen.

**Disposition of every `## Unresolved` entry:** all six returned a probe result or a documented
answer (see `## Unresolved` above for the resolution of each) — none was left to "proceed under
[P-NN]" and none was deferred. 61-05 does not halt on P-05, P-07, P-08, P-09, P-10, or P-13.

**Two findings that change the architecture, carried forward for 61-05 (this is the DISPATCH
axis, separate from the run-state STORE decided above):**

1. **Sub-workflows are doubly exempt.** n8n's own documentation states a parent's fan-out to N
   children costs one billable execution, not `1 + N` (only the parent counts toward the
   2,500/month allowance), and that sub-workflow executions do not count against the Starter
   plan's 5-concurrent cap either. Combined with P-13 confirming a detached child's execution id
   is correlatable from the parent's own `runData`, substrate 3 (sub-workflow dispatch,
   wait-for-completion off) is the strongest dispatch candidate on this plan — unmetered,
   uncapped, and observable. This is a dispatch-mechanism finding, not a run-state-store finding;
   61-05 decides dispatch separately from where progress is read.
2. **A deployment-ordering constraint, discovered by a probe failure.** n8n refuses to activate a
   parent whose `Execute Workflow` node references an unpublished child workflow — any
   sub-workflow architecture built in 61-05 must publish children before the parent.

Full evidentiary write-up: `61-PREMISE-DOCS-FINDINGS.md` (documentation-sourced answers) and
`61-PREMISE-PROBE-VERDICT.json` (machine-readable probe results). Both were produced outside this
plan's own tasks and are committed alongside this document as the evidence for the decision
recorded here.
