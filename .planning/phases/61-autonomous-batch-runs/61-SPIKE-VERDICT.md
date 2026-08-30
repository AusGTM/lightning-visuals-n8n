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
