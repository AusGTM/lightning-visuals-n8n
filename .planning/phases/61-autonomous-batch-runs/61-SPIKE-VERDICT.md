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

**Status:** Tasks 1-3 (this document + its completeness test) are complete. Task 4 — the
operator's run-state decision and disposition of every `## Unresolved` entry — is a
`checkpoint:decision` and has not yet run in this session.

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
- Q-01 — whether the REMAINING chain actually keeps executing on this n8n Cloud account once its own triggering webhook's response has already been sent, rather than being torn down with the connection, is not demonstrated anywhere in this repo: the deployed workflow's only live use of `responseNode` mode places the Respond node LAST, so no execution in this repo's history exercises "more nodes run after Respond fires." `[unknown]` — command: an admin builds a disarmed 3-node test workflow (`Webhook Trigger` -> `Respond to Webhook` -> a `Wait` node set to 10s -> a `Set` node) on this n8n Cloud instance, triggers it, and reads `GET /api/v1/executions/{id}?includeData=true` (`executions_client.get_execution`) to confirm the `Set` node's `runData` shows `executionStatus: success` recorded after the HTTP response was already received by the caller.
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
- Q-03 — whether a PARKED execution's resume state (and its `resumeUrl`) survives an n8n Cloud platform restart is the single highest-value unknown this spike can name for this substrate; nothing in this repo establishes it either way. `[unknown]` — command: ask n8n Cloud support directly: "if a workflow is parked on a Wait node's resumeUrl when this account's n8n Cloud instance is restarted or redeployed, does that resumeUrl still work afterward, and does the parked execution still complete?"
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
- Q-02 — whether the parent's own node output still carries the child's `$execution.id` once wait-for-completion is switched off is not established: some fire-and-forget dispatch modes return nothing usable to correlate against, others echo an id. `[unknown]` — command: an admin builds a disarmed 2-workflow test (parent: `Execute Workflow` -> a 2-second-delay child, wait-for-completion off) and reads the parent node's own output in a disarmed run's `runData` (`executions_client.get_execution` with `includeData=true`) for any child execution id.
- Q-03 — the same restart-survival question as substrate 2, asked about a DETACHED CHILD execution rather than a parked Wait-node execution; not established from repo source. `[unknown]` — command: the same admin question as substrate 2's Q-03, worded for "a child execution dispatched with wait-for-completion off" instead of "a Wait node".
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
- Q-05 — the alternative reading of that same measured data point — that a chunk costs 1 execution regardless of how many records it carries, because the whole waterfall for that one record ran inside execution `11960` alone with no second execution spawned — has never been checked against a 2-record chunk (this repo's own configured ceiling). If it held at 2 records per chunk too, a 40-record batch would cost 20 executions and a 300-record batch 150 — roughly a quarter of the formula-projected figures above. `[unknown]` — command: a disarmed 2-record chunk send, followed by an admin reading `GET /api/v1/executions?workflowId=...` (`executions_client.list_executions`) in the narrow time window bracketing that one send, exactly as `operator-claude-plugin/scripts/measure_dispatch.py` already did for the 1-record case in 54-MEASUREMENT.md — this is the multi-chunk residual that file names and leaves open (WINDOWS.md id 26).
- Q-05 — either reading above sits well inside the 2,500/month allowance for both a 40-record and a 300-record batch by itself. `[derived]`
- Q-05 — that comparison is against the plan's CONFIGURED allowance, never against what is actually left of it this month: `write_grant.py`'s own `_ALLOWANCE_GAP` text states plainly that the schedulers have already spent an unknown share of this month's allowance and none of it is subtracted here, because n8n exposes no usage/quota endpoint to an API key. `[documented]` (repo source: `write_grant.py:143-148`, and this project's own v0.8 milestone note that `/api/v1/usage|license|quota` all return 404)
- Q-05 — substrates 1 and 2 add no execution-count multiplier beyond the chunk arithmetic above unless a Wait node's park-then-resume counts as two executions per parked chunk rather than one, which is substrate 2's own Q-04 unknown above. `[derived]`
- Q-05 — substrate 3's own arithmetic, from its Q-04 answer above (1 parent-dispatch execution + 1 execution per detached child): for 40 records this is the same `chunk_count + record_count = 60` figure as the formula reading above; for 300 records, `450`. It carries no arithmetic advantage over the formula-projected baseline — its value is TIME (Q-01), not execution count. `[derived]`

Progress-read cost, per candidate run-state store, for an illustrative 30-minute run (this
repo's own longest documented single-send bound, `watch.py`'s `DEFAULT_BOUND_SECONDS = 600.0`, is
a SINGLE-send figure — a multi-chunk async run is the reason this spike exists, so 30 minutes is
used here as a clearly-labelled illustrative input, not a measured run length):

- n8n workflow `staticData` has no public read endpoint, so every progress read against a staticData-based run-state store is its own webhook round trip: 1 execution per poll. Using `watch.py`'s own documented backoff schedule `(5, 5, 10, 15, 30, 60)` seconds, widening then flat at 60s (`watch.py:19-24`), a 30-minute run polled on that schedule takes roughly 6 polls to reach the 60s-flat tail (summing to 125s) plus about 28 more 60s-spaced polls to cover the remaining ~1,675s — on the order of 34 executions spent on watching the run, separate from whatever the run itself costs. `[derived]` (arithmetic over watch.py's own documented schedule; the 30-minute run length is illustrative, not measured)
- A HubSpot object (a property or custom object on the run) costs 0 n8n executions per poll — the client reads HubSpot's own API directly instead, which is a HubSpot API call, not an n8n execution, and is therefore invisible to the 2,500/month n8n figure entirely. `[derived]` (mechanical consequence of the read not touching n8n at all)
- The n8n public executions API (`executions_client.py`) costs 0 n8n executions per poll: `GET /api/v1/executions` and `GET /api/v1/executions/{id}` are n8n's own management-plane REST endpoints, not a workflow trigger, so reading them does not run a workflow. `[documented]` (repo source: executions_client.py's own module docstring, "Thin, read-only wrapper over n8n's public API")
- Whether n8n Cloud meters calls to that same public executions API against some quota separate from the 2,500/month workflow-execution allowance is not established from repo source or from this account's own plan terms. `[unknown]` — command: an n8n admin reads the account's own n8n Cloud plan/billing terms (Settings -> Usage/Plan in the n8n Cloud dashboard) for any stated API-call quota distinct from workflow executions.
- The client's own `run_manifest.py` costs 0 of everything — 0 n8n executions, 0 HubSpot calls — but is readable only by the process that wrote it, which is the constraint that decides whether it is SUFFICIENT rather than whether it is cheap. `[documented]` (repo source: run_manifest.py's own module docstring, "readable only by the process that wrote it")

- Q-06 — whether n8n Cloud imposes a concurrent-execution cap on this account's plan (as distinct from the monthly TOTAL-execution allowance already tracked) is not established anywhere in this repo: nothing here reads, references, or tests an n8n execution-concurrency limit. A concurrency cap changes whether a fan-out substrate (2 or 3, both of which can leave more than one execution "in flight" for a single run) is viable at all — a run that fans out past the cap would have some chunks silently queued or rejected rather than running in parallel as planned. `[unknown]` — command: an n8n admin checks the account's own n8n Cloud plan page (Settings -> Usage, or the tier's published limits) for a stated concurrent-execution limit, or contacts n8n Cloud support directly with the account's plan name.

## Premises

The load-bearing facts 61-05 will be written against. Each entry: a premise id, one sentence, its
basis token, its source, and the plans/tasks that depend on it (REVIEW-04). A premise nothing
depends on is marked `dependents: none (context only)` rather than deleted, so the record of why
it was considered survives.

1. **P-01** — Chunk-count arithmetic (`ceil(n / max_records_per_chunk)`) is identical across all three async substrates and the baseline, because none of them change how a batch is split into chunks. `[derived]` — Source: `operator-claude-plugin/scripts/chunking.py::plan_chunks`. Dependents: 61-05 T2, T3; 61-06 (execution-count check before any larger batch).
2. **P-02** — The client already mints a `run_id` client-side before any HTTP call is sent, via `chunking.dispatch_plan`'s existing `run_id` keyword argument, so no substrate needs to invent a submit-time handle. `[documented]` — Source: `operator-claude-plugin/scripts/chunking.py:315,336-337`. Dependents: 61-05 T2 (REVIEW-C14: mint before submit, pass it in).
3. **P-03** — n8n workflow `staticData` has no public read endpoint, so a progress read against a staticData-based run-state store costs one n8n execution per poll. `[documented]` — Source: this plan's own Task 2 action text (61-01-PLAN.md) and 61-04-PLAN.md's independent HIGH-9 disposition, which states the same fact for an unrelated reason. Dependents: 61-05 T1 (run-state store selection), T3 (poll-loop location); context: 61-04 (cites the same fact to explain why the held queue does not depend on this decision).
4. **P-04** — Reading n8n's own public executions API (`executions_client.py`) costs zero n8n workflow executions per read, because it is a management-plane REST endpoint rather than a workflow trigger. `[documented]` — Source: `operator-claude-plugin/scripts/executions_client.py`'s own module docstring. Dependents: 61-05 T1, T2.
5. **P-05** — Whether n8n Cloud meters calls to its own public executions API against a quota separate from the 2,500/month workflow-execution allowance is not established from repo source or from this account's own plan terms. `[unknown]` — Source: no repo reference found (searched for "usage/license/quota" and "concurren" across the codebase). Dependents: 61-05 T1 (only if the executions-API store is the one selected).
6. **P-06** — `run_manifest.py` costs zero n8n executions and zero HubSpot calls, but is readable only by the process that wrote it. `[documented]` — Source: `operator-claude-plugin/scripts/run_manifest.py`'s own module docstring. Dependents: 61-05 T1, T3 (resume-or-fail-loudly).
7. **P-07** — Whether an n8n Cloud execution keeps running after its own triggering webhook's response has already been sent (the mechanism substrate 1 depends on entirely) is not established from repo source. `[unknown]` — Source: no execution in this repo's history exercises a Respond-node-first shape. Dependents: 61-05 T1 (halts if substrate 1 is selected while this premise stays unresolved), T2, T4.
8. **P-08** — Whether a parked (Wait-node) or detached-child (sub-workflow, wait-for-completion off) execution survives an n8n Cloud platform restart is not established from repo source. `[unknown]` — Source: neither mechanism is used anywhere in this repo today. Dependents: 61-05 T1, T3 (the "resume or fail loudly" must-have's restart clause), T4.
9. **P-09** — Whether n8n Cloud imposes a concurrent-execution cap on this account's plan, separate from the monthly total-execution allowance, is not established from repo source. `[unknown]` — Source: no repo reference to n8n execution concurrency found. Dependents: 61-05 T1 (only if a fan-out substrate, 2 or 3, is selected), T4; 61-06 (any concurrent dispatch it might add later).
10. **P-10** — The `chunk_count + record_count` execution-cost formula (`write_grant.py`'s `EXECUTIONS_BASIS`) has one measured disagreement at `chunk_count = 1` (projected 2, measured 1) and has never been checked at this repo's own configured ceiling of 2 records per chunk. `[unknown]` — Source: 54-MEASUREMENT.md's own named residual (WINDOWS.md id 26). Dependents: 61-05 T1 (budget check before any batch of more than one chunk), T4.
11. **P-11** — A 40-record and a 300-record batch both fit within the configured 2,500/month execution allowance under either arithmetic reading of P-10 (per-chunk-plus-per-record, or per-chunk-only). `[derived]` — Source: `## Execution arithmetic` above. Dependents: 61-05 T1 (must_haves truth on budget), T4.
12. **P-12** — That budget comparison is against the plan's CONFIGURED monthly allowance, never against what is actually left of it after this month's schedulers have already run, because n8n exposes no usage/quota endpoint to an API key. `[documented]` — Source: `write_grant.py:143-148`; PROJECT.md's v0.8 note that `/api/v1/usage|license|quota` all 404. Dependents: 61-05 T1, T4; none further (context for every budget claim above).
13. **P-13** — Whether the parent `Execute Workflow` node's own output can be correlated to a detached child's execution id when wait-for-completion is off is not established from repo source. `[unknown]` — Source: substrate 3's own Q-02 above; no repo evidence either way. Dependents: 61-05 T2 (only if substrate 3 is selected).

## Unresolved

Every `[unknown]` premise above, by id, with the exact read-only command that would resolve it
and who can run it. None of these can be run by an executor — every one needs operator or n8n
admin access this spike is barred from using.

- **P-05** — Command: an n8n admin reads the account's own n8n Cloud plan/billing terms (Settings -> Usage/Plan in the n8n Cloud dashboard) for any stated API-call quota distinct from workflow executions. Owner: n8n admin.
- **P-07** — Command: an admin builds a disarmed 3-node test workflow (`Webhook Trigger` -> `Respond to Webhook` -> a delayed `Set` node) on this account, triggers it, and reads `GET /api/v1/executions/{id}?includeData=true` to confirm the `Set` node's `runData` recorded success after the response was already received by the caller. Owner: n8n admin (needs a disarmed test-workflow deploy).
- **P-08** — Command: ask n8n Cloud support directly whether a parked (Wait-node) or detached-child (sub-workflow) execution resumes across a platform-side restart or redeploy of this account's instance. Owner: operator, via n8n Cloud support, or an n8n admin with a support relationship.
- **P-09** — Command: an n8n admin checks the account's own n8n Cloud plan page (Settings -> Usage, or the tier's published limits) for a stated concurrent-execution limit, or asks n8n Cloud support directly. Owner: n8n admin.
- **P-10** — Command: a disarmed 2-record chunk send, followed by an admin reading `GET /api/v1/executions?workflowId=...` in the narrow window bracketing that one send, exactly as `measure_dispatch.py` did for the 1-record case in 54-MEASUREMENT.md. Owner: n8n admin (needs a live, disarmed send).
- **P-13** — Command: an admin builds a disarmed 2-workflow test (parent dispatches a child with wait-for-completion off) and reads the parent node's own output in a disarmed run's `runData` for any child execution id. Owner: n8n admin.
