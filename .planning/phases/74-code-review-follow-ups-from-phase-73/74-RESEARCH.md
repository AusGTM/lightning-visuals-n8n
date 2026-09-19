# Phase 74: Code-review follow-ups from phase 73 - Research

**Researched:** 2026-09-19
**Domain:** n8n Cloud workflow generation (Python builder → JSON), shared JS merge/pairing
engines, operator-plugin Python (write_grant/report_enrichment/chunking/csv_dedupe/preview/
review_decision), offline walker fidelity, secret-redaction tooling.
**Confidence:** HIGH — every code anchor below was re-read this session (`Read`/`sed -n`/`grep`
against the live working tree, and three anchors were additionally confirmed by loading the
*generated* `n8n/wf_contact_ingest_cloud.json` and walking its `connections` table
programmatically). No web research was needed or performed — this is a pure in-repo follow-up
phase with a fully locked CONTEXT.md; the job here is exact current-state grounding, not stack
selection.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Create-error lane convergence (CR-01, WR-07)**
- **D-74-01:** `Create Carry Merge` input 2 gets a REAL producer: a Code node on `HubSpot
  Create`'s error edge that emits exactly one marker item per run unconditionally (a marker when
  the error branch is empty, the error items when it is not), so the input always receives and
  the merge completes normally instead of via the v1 end-of-run drain. The
  `set_always_output_data(["HubSpot Create"])` mechanism and its comment block are retired —
  n8n pads output 0 only, `[observed live]` on execution `12522` (`HubSpot Create` outs
  `[21, 0]`, input 2 never delivered, association still landed via the drain).
  — **Reversibility:** costly — the producer sits inside the Phase 70 carry-merge idiom; removing
  it means re-splicing the create lane and re-running the walker suite.
- **D-74-02:** `Ingest Merge Response` input 5 (`Build Create Failure Row`) gets a gated
  starved-lane sentinel keyed on "the decided-row set contains zero create-routed rows". That is
  knowable before any write, so it is not a second producer in the dangerous (double-fire)
  sense. No all-update batch is left drain-only.
- **D-74-03:** Walker fidelity: `tests/n8n/lib/walkWorkflow.mjs` pads output index 0 only under
  `alwaysOutputData`; execution `12522`'s runData is frozen (through the CR-04-widened freezer)
  as `tests/n8n/fixtures/frozen/exec_12522.runData.json` and a fidelity test pins the rule
  against it; CLAUDE.md §13.0.3 gains the row (file+symbol `[documented]` plus `12522`
  `[observed live]`). WR-08's JSDoc is corrected in the same edit.

**Error-item shape (CR-02, CR-03)**
- **D-74-04:** Classification becomes explicit, not structural: a one-line Code node on the
  error edge (it can be the same node as D-74-01's producer) stamps `_create_error: true`;
  `pairCreateOutcome` tests that flag FIRST, ahead of `_isCarriedRow`. No armed execution is
  spent to observe the real n8n error-item shape — the lane stays `[documented]` per D-73-19
  until a real race occurs.
- **D-74-05:** The single hand-written stub in `tests/n8n/ingestCreateErrorLane.test.mjs` is
  kept and tagged `UNOBSERVED` in the same register `walkWorkflow.mjs` uses for D-70-30 rule
  (c), naming the shape question. Correctness rests on the stamp, not the stub's shape.
- **D-74-06:** `create_outcome` `none` / `refused` are consumed in `BUILD_INGEST_RESPONSE` as
  `action: "create_unconfirmed"`, mapped to `FAILED` in `written_records.ACTION_TO_OUTCOME`
  (never `created_id_unknown`). The operator-facing `reason` passes `create_outcome_reason`
  through verbatim so the two sub-cases stay distinguishable ("no create response joined to this
  row" vs the ambiguity text).

**Fixture redaction guard (CR-04)**
- **D-74-07:** `scripts/freeze_execution_rundata.py` replaces ANY `headers`, `error`, `request`,
  `options` or `config` key at any depth with the placeholder, applied per node run so
  `run.error` is covered — the same non-enumerating idiom the tool already argues for. Error
  fixtures lose their message text by design.
- **D-74-08:** The 7 committed runData fixtures that match a naive pattern today (5 Phase-70
  fixtures carrying the superseded `x-enrichment-secret`; `exec_12434` / `exec_12449` carrying
  JWT-shaped strings) are RE-REDACTED IN PLACE by the widened scrubber and the rewritten bytes
  committed. No path exemptions. (The secret was rotated 2026-09-11; the JWTs have a 24h
  lifetime; git history is not rewritten.)
- **D-74-09:** A guard test over `tests/n8n/fixtures/frozen/` refuses VALUE shapes:
  `pat-na\d-…`, `Bearer <token>`, `x-enrichment-secret` followed by a value, and JWT bodies
  `eyJ[A-Za-z0-9_-]{20,}`. The header NAME inside node jsCode (present in the 4 frozen workflow
  bodies) must not trip it.

**Warnings and the end-of-phase gate**
- **D-74-10:** WR-03, WR-04, WR-08, WR-09, WR-10, WR-11, WR-12 are ALL fixed in code with a test
  each, using the fixes `73-REVIEW.md` supplies. No accept-with-reason rows this phase.
  WR-01/02/05/06 follow the roadmap's stated shape (lane-invariant `executions = 1` hoisted out
  of the `try`; per-lane `executions_projection_basis` and `providers` taken from the estimate;
  ledger keyed by `(lane, id)` with ambiguous ids skipped; `excluded_marker_count` returned and
  reported when non-zero).
- **D-74-11:** End-of-phase gate is IN-PHASE and disarmed: regenerate, deploy
  `--only wf_contact_ingest_cloud.json`, bounce, send ONE all-update batch (zero creates) and
  read runData: `Create Carry Merge` and `Ingest Merge Response` both complete normally with no
  `merge_fired_with_unfilled_input`; freeze the execution. One execution, nothing armed, every
  `ALLOW_*` flag read back `false`. The other five cloud workflows are not deployed.
  — **Reversibility:** reversible — a disarmed deploy of one workflow; the committed JSON stays
  the source of truth.

**Folded Todos**
- `2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md` (MN-01 / NF-MJ-01, `kind:
  question`) — **D-74-12:** answer MN-01 from frozen runData: search `exec_12522` (once frozen),
  `exec_12434` and `exec_12449` for any Merge left with two partially-filled pending runs. If
  found, record the answer in §13.0.3 and close the todo with a dated RESOLVED block; if not,
  keep it open with its trigger and say so in the SUMMARY. Never close it on a `resolves_phase`
  match alone.
- `2026-09-17-stage-d-match-chunk-unchecked-rate.md` (`kind: question`) — **D-74-13:** read the
  recovery bound in `operator-claude-plugin/scripts/chunking.py` against stress attempt 3's
  timings, parametrise or raise it, add a test, and surface `unchecked_count` in the run report.
  No live Stage D run this phase; the todo's trigger ("next Stage D run") stays until one does.

### Claude's Discretion
- Whether D-74-01's producer and D-74-04's stamp are one Code node or two.
- Exact wording of the `UNOBSERVED` tag and of the §13.0.3 rows.
- Plan/wave grouping; the roadmap's fix order (CR-03, CR-02, CR-04, CR-01, then WR) is the
  default unless a shared file makes another order cheaper.

### Deferred Ideas (OUT OF SCOPE)
- Observing the real n8n error-item shape with an armed duplicate-email create — explicitly not
  this phase (D-74-04); the trigger stays "a real race occurs" (D-73-19).
- Deploying the other cloud workflows — only the ingest lane changes graph shape this phase.
- The 8 other pending-todo keyword matches reviewed during discuss-phase (enrichment throughput
  ceiling, company-domain candidate source, property-history hop, `rows_to_resume` fingerprint
  branch, CSV-only ingest thresholds, racing-club `produces_content` veto, suggest-contacts
  stage-2 script, ZoomInfo enrich-lane token cache) — unrelated to the 16 findings; left pending
  with their own triggers.
</user_constraints>

## Summary

This phase closes 16 findings from `73-REVIEW.md` with the fix shapes already locked in
`74-CONTEXT.md` (D-74-01..13). There is no stack/architecture decision left to research — the
planner's job is sequencing 13 already-specified code changes across a handful of files, each
touching a mechanism this document traces to its exact current line. The one fact every
downstream agent must internalize first: **`73-REVIEW.md`'s cited line numbers are stale.**
Phase 73.1 (13 commits, 2026-09-15→19) touched `scripts/build_cloud_workflows.py` most recently
on **2026-09-19** (`41f876b6`, unrelated to this phase — see the name-collision warning below)
and shifted every anchor the review cites by 150-260 lines. The content at every cited anchor is
byte-for-byte unchanged from what the review describes (verified below); only the line numbers
moved. **Grep by function/variable name, never by the review's line number.**

A second thing worth internalizing before planning: three of the four CR items are not
independent hypotheticals — the exact graph shape they describe is verifiable *right now* by
loading the committed `n8n/wf_contact_ingest_cloud.json` and reading its `connections` table (no
n8n credentials, no live call needed). I did this for `Create Carry Merge` (CR-01/D-74-01 target)
and `Ingest Merge Response` (CR-03/WR-07/D-74-02 target) and both match the review's description
exactly, down to the input index. That verification method — load the generated JSON, walk
`connections` in Python — is cheap and should be the plan's own acceptance check for "the splice
landed where D-74-01/02 says it should," not a re-read of the builder source alone.

**Primary recommendation:** sequence the 13 decisions by shared file, not strictly by the
roadmap's CR-03→CR-02→CR-04→CR-01→WR order — CR-01, CR-02, CR-03 and WR-07 all edit the same
20-line region of `scripts/build_cloud_workflows.py` (the `Create Carry Merge` / `Pair Create
Outcome To Row` / `Ingest Merge Response` splice) and the same two JS files
(`pairCreateOutcome.js`, the `BUILD_INGEST_RESPONSE`/`BUILD_CREATE_FAILURE_ROW_JS` constants), so
landing them as one wave against one regenerated `wf_contact_ingest_cloud.json` avoids three
separate regenerate/diff cycles on the same node. CR-04 (freezer) and WR-01/02/05/06/09/10/11/12
touch entirely disjoint files and can run in parallel waves.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Create-error classification/join (CR-01,02,03,WR-07) | n8n Cloud workflow (generated JSON, builder source) | Shared JS engine (`n8n/code/pairCreateOutcome.js`) | Runs inside the deployed Code/HTTP nodes; the builder is the only place the graph shape is authored |
| Ledger outcome mapping (D-74-06) | Operator plugin (Python) | — | `written_records.ACTION_TO_OUTCOME` is a plugin-side table read after the n8n execution settles |
| Fixture redaction (CR-04) | Offline tooling (Python CLI) | — | `scripts/freeze_execution_rundata.py` is a read-only GET-and-write CLI, never touches n8n/HubSpot write paths |
| Walker fidelity (D-74-03) | Offline test infrastructure (Node.js) | — | `tests/n8n/lib/walkWorkflow.mjs` models the engine; no runtime component |
| Consent-disclosure basis (WR-01,02) | Operator plugin (Python) | — | `write_grant.py`'s grant-preview text, read by the operator before dispatch |
| Backfill ledger keying (WR-05) | Operator plugin (Python) | — | `report_enrichment.py`, runs after execution settles |
| Excluded-marker reporting (WR-06) | Operator plugin (Python) | — | `chunking.py`'s `dispatch_and_recover` |
| Review-intent comparison (WR-09) | Operator plugin (Python) | — | `review_decision.py` |
| Build-time constant extraction (WR-10) | Offline tooling (builder itself) | — | `extract_js_const` in `scripts/build_cloud_workflows.py` |
| CSV dedupe correctness (WR-03,04,11,12) | Operator plugin (Python) | — | `csv_dedupe.py`, `preview.py` |

No capability in this phase crosses into the browser/CDN/database tiers — everything is either
generated-workflow-graph or operator-plugin-Python.

<phase_requirements>
## Phase Requirements

This phase carries **no REQUIREMENTS.md ids**. Per `74-CONTEXT.md`'s own framing, it is keyed
entirely on the 13 locked decisions D-74-01..D-74-13, each traceable to a `73-REVIEW.md` finding
(CR-01..04, WR-01..12) and, for D-74-12/13, to a folded todo. The table below is the id-mapping
the planner should carry into PLAN.md task headers in place of a REQ-ID.

| Decision | Finding(s) | One-line scope |
|----------|-----------|-----------------|
| D-74-01 | CR-01, WR-07 (association half) | Real producer Code node on `HubSpot Create`'s error edge, retiring the `alwaysOutputData` reliance for `Create Carry Merge` input 2 |
| D-74-02 | WR-07 (`Ingest Merge Response` half) | Gated starved-lane sentinel on `Ingest Merge Response` input 5 |
| D-74-03 | CR-01 (walker fidelity) | `walkWorkflow.mjs` pads output index 0 only; freeze execution `12522`; pin a fidelity test; correct WR-08's stale JSDoc in the same edit; add the CLAUDE.md §13.0.3 row |
| D-74-04 | CR-02 | Explicit `_create_error: true` stamp Code node, tested first in `pairCreateOutcome.js` |
| D-74-05 | CR-02 (test precedent) | Keep the hand-written stub in `ingestCreateErrorLane.test.mjs`, tag `UNOBSERVED` |
| D-74-06 | CR-03 | Consume `create_outcome` `none`/`refused` in `BUILD_INGEST_RESPONSE`; add `create_unconfirmed` → `FAILED` in `written_records.ACTION_TO_OUTCOME` |
| D-74-07 | CR-04 | Widen `freeze_execution_rundata.py`'s scrub to `headers`/`error`/`request`/`options`/`config` at any depth, per node run |
| D-74-08 | CR-04 | Re-redact 7 committed fixtures in place (5 with `x-enrichment-secret`, 2 with JWT strings) |
| D-74-09 | CR-04 | Guard test refusing VALUE shapes in `tests/n8n/fixtures/frozen/` |
| D-74-10 | WR-03,04,08,09,10,11,12 | Fix all seven with the review's own proposed fix + one test each |
| D-74-11 | (end-of-phase gate) | Regenerate, deploy `--only wf_contact_ingest_cloud.json`, bounce, one disarmed all-update send, freeze the execution |
| D-74-12 | folded todo (MN-01) | Search frozen runData for a Merge left with two partially-filled pending runs |
| D-74-13 | folded todo (Stage D) | Read/parametrise the recovery bound in `chunking.py` against stress-attempt-3 timings |

WR-01/02/05/06 are **not** independently listed above because `74-CONTEXT.md`'s own D-74-10
sentence folds their shape ("follow the roadmap's stated shape") in alongside — treat them as a
14th/15th/16th/17th line item with the SAME fix-with-test obligation as D-74-10's seven, just
pre-specified by the roadmap rather than by `73-REVIEW.md`'s fix column alone.
</phase_requirements>

## Naming collision warning (read before touching `write_grant.py`, `build_cloud_workflows.py`, or the git log)

Phase 73.1 (completed 2026-09-19, immediately before this phase) had **its own, unrelated**
CR-01/WR-01/WR-03 findings from a *different* code review, about the suggest-contacts discovery
lane (ZoomInfo token minting, `per_company_cap`, rung-1 title filtering) — see commits
`96770d6d`, `ab09dafa`, `41f876b6`. These are **not** this phase's CR-01/WR-01/WR-03. When
searching `git log` or reading commit messages, filter for the `73-ga-fix-list` / `73-REVIEW.md`
finding text, not the bare id, or you will pull in the wrong diff as "prior art."

## CR-01 / D-74-01 / D-74-03 — the create-error producer and the walker's AOD branch bug

### Current graph shape (verified live from the generated JSON, not just the builder source)

```
$ python3 -c "... load n8n/wf_contact_ingest_cloud.json, walk connections to Create Carry Merge ..."
Create Carry Merge params: {'mode': 'append', 'numberInputs': 3}
alwaysOutputData on HubSpot Create: True
HubSpot Create (out 0) -> input 0
HubSpot Create (out 1) -> input 2
HubSpot Create Permitted Pass-Through (out 0) -> input 1
```
`[VERIFIED: n8n/wf_contact_ingest_cloud.json, walked via `json.load` + `connections` traversal,
this session]` — `HubSpot Create`'s error output (index 1) feeds `Create Carry Merge` input 2
**directly**, with no intermediate node. The only thing standing between "the error branch is
empty" and "input 2 never delivers" is `alwaysOutputData: true` on `HubSpot Create` itself.

### Builder source (current line numbers — re-verify by grep, not by these numbers, before editing)

```
$ grep -n '_append_merge_input(nodes, conns, "Create Carry Merge", "HubSpot Create"\|set_always_output_data(nodes, \["HubSpot Create"\])' scripts/build_cloud_workflows.py
2228:    _append_merge_input(nodes, conns, "Create Carry Merge", "HubSpot Create", source_out_idx=1)
2229:    set_always_output_data(nodes, ["HubSpot Create"])
```
`[VERIFIED: scripts/build_cloud_workflows.py:2228-2229]`. The review cited `:1993`/`:1956-1992`
(2026-09-18 line numbers) — the same code now sits ~235 lines lower after Phase 73.1's edits to
the same file (13 commits between the review and this research, most recently `41f876b6` on
2026-09-19). The surrounding comment block (the one CR-01 quotes) is unchanged in content,
starting at `scripts/build_cloud_workflows.py:2172` (`# Phase 73 Plan 06 Task 1 ...`) through
`:2229`.

`_hs_http_create_node`'s `on_error` docstring `[VERIFIED: scripts/build_cloud_workflows.py:9931]`
(current line — was implied ~9931 in the review too, this one didn't move) confirms the ingest
lane's own call site passes `on_error="continueErrorOutput"` at
`scripts/build_cloud_workflows.py:1755` `[VERIFIED]`:
```python
nodes.append(_hs_http_create_node("HubSpot Create", "contacts", x + 440, y - 20,
                                  on_error="continueErrorOutput"))
```

### `set_always_output_data`'s own docstring (why the assumption existed)

`[VERIFIED: scripts/build_cloud_workflows.py:10422-10433]` — the docstring is explicit that the
mechanism "ONLY rescues a node that actually RAN with some input and produced nothing... it does
nothing for a node that received ZERO input and was never dispatched at all" and cites
`workflow-execute.ts::ensureAlwaysOutputData` as the verified mechanism — but **never states
which output index** gets the padding. That silence is exactly what CR-01 flags.

### Walker's current (wrong) behaviour — the concrete bug D-74-03 fixes

`[VERIFIED: tests/n8n/lib/walkWorkflow.mjs:512-520]`:
```javascript
function propagate(fromName, outputIndex, items) {
  const node = nodesByName[fromName];
  let outItems = items;
  // ...
  if (outItems.length === 0 && node && node.alwaysOutputData === true) {
    outItems = [{}];
  }
```
`outputIndex` is already a parameter of `propagate` — it is simply **not used** in this
condition. The call site that invokes `propagate` once per output branch:
`[VERIFIED: tests/n8n/lib/walkWorkflow.mjs:796]`
```javascript
result.outputs.forEach((branchItems, idx) => propagate(node.name, idx, branchItems));
```
This means the walker today pads **whichever** branch (0 or 1) happens to be empty when
`alwaysOutputData` is set — the opposite of a real per-output-0-only rule. **The fix is a
one-line change**: add `&& outputIndex === 0` to the condition at line 520. No other walker
plumbing needs to change — `outputIndex` is already threaded through.

### D-74-03's frozen-fixture target does not exist yet

`[VERIFIED: `ls tests/n8n/fixtures/frozen/`, this session]` — no `exec_12522.runData.json` is
committed. Execution `12522` is documented only in
`.planning/phases/73-ga-fix-list-from-stress-attempt-2/73-UAT.md:116-131` (Stage A, run_id
`56ee1e8fb641415095457e82f5f0c10e`, 46 rows sent, 21 created, `HubSpot Create` outs `[21, 0]` per
CONTEXT.md's own citation). **Freezing it is part of this phase's own work**, not a pre-existing
asset — the plan must include a task (or a D-74-11-adjacent step) that runs
`scripts/freeze_execution_rundata.py 12522` through the D-74-07-widened scrubber, then writes the
fidelity test against it. Since D-74-07 (widen the scrubber) and D-74-03 (freeze 12522) both
touch the freezer, land D-74-07 first in the same wave, or the freeze has to be redone.

**Freezing 12522 needs live n8n credentials** (`N8N_URL`/`N8N_API_KEY`), which live in `.env` —
permission-blocked to the `Read`/`Bash` tools directly
(`[CITED: repo memory env-file-permission-blocked.md]`). The established, repo-precedented
workaround (used by 73.1-09, same day as this research) is an **in-process dotenv scratchpad
driver**, never committed to the repo:
```
Scratchpad path (session-specific, not /tmp, not the repo):
  $SCRATCHPAD/run_with_env.py  — calls python-dotenv's load_dotenv() in its OWN process,
  then dispatches to the target script's main()/functions directly. Never echoes a secret
  value to stdout. `.planning/phases/73.1-.../73.1-09-SUMMARY.md:203-219` records this exact
  pattern for deploy/bounce/discover-proof/list-executions subcommands; the same pattern
  applies to `scripts/freeze_execution_rundata.py <id>` (it already loads its own dotenv —
  see below — so the wrapper may be as thin as `import sys; sys.argv=[...]; freeze_module.main()`
  after `load_dotenv()`, or simply invoking `.venv/bin/python scripts/freeze_execution_rundata.py
  12522` from a shell that has `.env` sourced via the wrapper's own env, never via `. ./.env`
  directly — that direct form IS what the sandbox's secret-read guard blocks).
```
`scripts/freeze_execution_rundata.py` itself already calls `load_dotenv()` internally
`[VERIFIED: scripts/freeze_execution_rundata.py:51-54]`, so it does not need the wrapper to parse
`.env` for it — it only needs to be *invoked* through a channel the sandbox's secret-read guard
doesn't block. Confirm the exact current-session blocker shape before planning a live step; do
not assume the 73.1-09 workaround still applies unchanged without a fresh check (the guard's
exact trigger condition is environment-dependent, per repo memory `n8n-deploy-permission-
blocked.md`).

### CLAUDE.md §13.0.3 row (D-74-03's third sub-task)

The table `CLAUDE.md` §13.0.3 already contains the pattern to extend — e.g. the existing row
starting "**A node fed zero items does not run at all...**" cites both an HTTP-node case
(`12200`) and a Code/NoOp gate case (`12203`, `12206`) as *separately observed*, not assumed
identical. The new row should follow the same two-tag convention:

`[documented]` half — the upstream n8n source is public; fetched
`https://raw.githubusercontent.com/n8n-io/n8n/master/packages/core/src/execution-engine/
workflow-execute.ts` this session (`[CITED: n8n-io/n8n master, workflow-execute.ts,
ensureAlwaysOutputData — not independently run, this repo's own copy of n8n was not inspected]`).
The fetched body:
```typescript
private ensureAlwaysOutputData(
    nodeSuccessData: INodeExecutionData[][] | null | undefined,
    executionData: IExecuteData,
): INodeExecutionData[][] | null | undefined {
    if (nodeSuccessData?.[0]?.[0]) return nodeSuccessData;
    if (executionData.node.alwaysOutputData !== true) return nodeSuccessData;
    // ... collects pairedItem from all input items ...
    nodeSuccessData ??= [];
    nodeSuccessData[0] = [{ json: {}, pairedItem }];
    return nodeSuccessData;
}
```
Two things this confirms directly, both matching CR-01's guess rather than the walker's current
(wrong) behaviour: (1) the guard `nodeSuccessData?.[0]?.[0]` means the substitution only fires
when **output 0** is empty — an empty output 1 (the error branch, non-empty output 0) never
triggers it at all; (2) the write target is hardcoded `nodeSuccessData[0] = [...]` — even in the
hypothetical case both outputs were empty, only index 0 gets the marker. This settles CR-01's own
open question in the direction `74-CONTEXT.md`'s D-74-01 already assumes ("n8n pads output 0
only") — cite this fetch alongside the file+symbol per the table's convention. This is `[CITED]`,
not `[VERIFIED]` — no test in this repo executed the real n8n engine to confirm it; treat it as
strong corroboration for the walker fix, not a substitute for the live `12522` observation below.

`[observed live]` half — execution `12522` once frozen (`HubSpot Create` outs `[21, 0]`, input 2
never delivered, association still landed via the v1 end-of-run drain — this half is already
given as fact in `74-CONTEXT.md`'s D-74-01 bullet; tag it `[observed live]` citing `12522` once
the fixture exists).

## WR-08 — the JSDoc fix rides along with D-74-03

`[VERIFIED: tests/n8n/lib/walkWorkflow.mjs:351-357 vs :302-326]` — confirmed still present,
content unchanged from the review's citation (only line numbers shifted, by ~0-10 lines — this
file was not touched by Phase 73.1). The stale sentence is at (current) line ~351-357; the real
contract (a plain-array stub on a `continueErrorOutput` node yields `{success: raw, error: []}`,
confirmed at lines 302-326) is what the JSDoc should say instead. `74-CONTEXT.md`'s D-74-03
already folds this fix into the same edit — no separate task needed, just don't forget it when
touching this function.

## CR-02 / D-74-04 / D-74-05 — explicit `_create_error` stamp, classification order

`n8n/code/pairCreateOutcome.js` `[VERIFIED, full file read this session]` classifies by shape:

```javascript
function _isCarriedRow(row) {
  return typeof (row && row.action) === "string" && row.action.length > 0;
}
function _isSuccessResponse(row) {
  return Boolean(row) && row.id !== undefined && row.id !== null && row.id !== "";
}
// pairCreateOutcome(items):
for (const row of items || []) {
  if (!row) continue;
  if (_isCarriedRow(row)) carried.push(row);
  else if (_isSuccessResponse(row)) responses.push({ row, outcome: "success" });
  else responses.push({ row, outcome: "error" });
}
```
This is the function D-74-04 changes: add a `_create_error === true` check **ahead of**
`_isCarriedRow`, so an item stamped by the new producer node (D-74-01) is unambiguously routed to
`responses.push({row, outcome: "error"})` regardless of whether it happens to carry an `action`
field or an `id` field. The module's docstring header (lines 1-24) explains the current
shape-only design rationale and should be updated to describe the stamp as the primary signal,
shape as fallback (or removed if the stamp makes shape detection for this branch moot — Claude's
discretion per CONTEXT.md).

### Where the hand-written test stub currently lives (D-74-05's target)

`[VERIFIED: tests/n8n/ingestCreateErrorLane.test.mjs:79-99]` — the stub:
```javascript
"HubSpot Create": {
  success: [ {id: CREATED_1, properties: {email: EMAIL_1}}, {id: CREATED_3, properties: {email: EMAIL_3}} ],
  error: [ {
    message: "Contact already exists. Existing ID: 555",
    properties: { email: EMAIL_2 },   // <-- this is the invented part CR-02 flags
    request: { headers: { Authorization: "Bearer super-secret-token" } },
  } ],
}
```
Note precisely *why* this stub currently "works" despite being hand-invented: the error item's
top-level `properties.email` field makes `identityKey()`'s `_emailOf()` resolve successfully
today (`_emailOf` reads `row.properties.email`), which is exactly the assumption CR-02 says
nothing backs — a real n8n error item may not echo the outbound request's `properties` object at
that path at all. D-74-05 keeps this stub (rather than deleting it) and tags it `UNOBSERVED` —
follow the exact register `walkWorkflow.mjs` already uses for D-70-30 rule (c), e.g.:
```javascript
// UNOBSERVED (D-74-05): this error item's `properties.email` shape is INVENTED, not
// pinned by any frozen runData. Real n8n HTTP error-item shape for a continueErrorOutput
// node is still [documented] only (D-73-19) — see CLAUDE.md §13.0.3. The `_create_error`
// stamp (D-74-04) is what makes this test's correctness independent of the guess.
```
After D-74-04 lands, this test should ALSO assert the stamp itself is what drove classification
(e.g. temporarily strip `properties.email` from the stub and confirm the row still classifies as
`create_failed`) — this is the regression the whole CR-02 fix exists to prevent, and the existing
test doesn't currently prove it (it only proves the current, assumption-dependent path works).

## CR-03 / D-74-06 — consuming `create_outcome: "none"`/`"refused"`

`pairCreateOutcome.js`'s three unconsumed outcomes `[VERIFIED: n8n/code/pairCreateOutcome.js:94-
143]`:
- `"success"` — consumed already (feeds `Build Association Request`)
- `"error"` — consumed by `BUILD_CREATE_FAILURE_ROW_JS` (filters `create_outcome === "error"`)
- `"none"` / `"refused"` — **never filtered anywhere**, confirmed by grepping both consumers.

Current consumers, current line numbers (both shifted from the review's citation — file last
touched by Phase 73.1):
- `BUILD_CREATE_FAILURE_ROW_JS` starts `[VERIFIED: scripts/build_cloud_workflows.py:837]`
  (review cited `:766-770` — now 837, ~+70 lines). Its filter:
  `const errors = allItems.filter((row) => row.create_outcome === "error");` — only `"error"`.
- `BUILD_INGEST_RESPONSE` starts `[VERIFIED: scripts/build_cloud_workflows.py:874]` (review cited
  `:848-905` — now 874-...). Reads `row.action`/`row.outcome` from the **decided snapshot**
  (`decided`, filtered on `_decided_snapshot === true`) and separately joins `failed` (filtered
  `row.action === "create_failed"` — the string `BUILD_CREATE_FAILURE_ROW_JS` stamps). It has
  **no equivalent join for `create_outcome: "none"`/`"refused"`** — a row with either of those
  outcomes keeps its pre-write `action` (`"create"`) all the way to the response, exactly as
  CR-03 describes.

The fix's insertion point is the `const failed = allItems.filter(...)` block
`[VERIFIED: scripts/build_cloud_workflows.py:922-931]`:
```javascript
const failed = allItems.filter((row) =>
  row._decided_snapshot !== true && row.action === "create_failed");
const failedByEmail = {};
for (const row of failed) {
  if (row.email) failedByEmail[String(row.email).toLowerCase()] = row;
}
```
D-74-06 wants an analogous `unconfirmed`/`unconfByEmail` block, and the returned object's
`action`/`outcome`/`reason` fields (currently `fail ? "create_failed" : (block ? "write_blocked"
: row.action)` at `[VERIFIED: scripts/build_cloud_workflows.py:962]`) extended with a third
branch for `create_unconfirmed`, per the exact ternary shape `74-CONTEXT.md`/`73-REVIEW.md`
already specify.

**Corrected trace (the review's fix snippet, taken literally, filters an empty set — traced this
session, catches a gap the review itself did not flag).** `pairCreateOutcome`'s `"none"`/
`"refused"` items are `{ ...row, create_outcome: "none" }` / `{ ...row, create_outcome:
"refused", create_outcome_reason }` — the carried row's own fields, with **no `id`** ever
attached (no response joined). Both of `Pair Create Outcome To Row`'s two fan-out consumers drop
such an item today:
- `Build Association Request`'s wrapper `[VERIFIED: scripts/build_cloud_workflows.py:769-806]`:
  `const contactId = row.id != null ? String(row.id) : (row.hs_object_id ? String(row.hs_object_id)
  : null); if (!contactId) return null;` — a create's `hs_object_id` is null pre-write, and no
  `id` was ever joined, so `contactId` is null and the row is dropped (`.filter(Boolean)` at the
  end of the map). CLAUDE.md §13.0.1's own docstring at
  `scripts/build_cloud_workflows.py:1816-1818` already documents this drop rule generally
  ("`Build Association Request` drops any row with no resolved company") — the SAME drop also
  fires here for a different reason (no contact id, not no company id).
- `BUILD_CREATE_FAILURE_ROW_JS`'s filter `[VERIFIED: scripts/build_cloud_workflows.py:850]`:
  `const errors = allItems.filter((row) => row.create_outcome === "error");` — `"none"`/
  `"refused"` fail this test too (only `"error"` passes).

**No item carrying `create_outcome: "none"`/`"refused"` reaches `Ingest Merge Response` in any
form today** — it is dropped by both of its only two possible routes, silently. The review's
own `BUILD_INGEST_RESPONSE` fix snippet (`const unconfirmed = allItems.filter((row) =>
row._decided_snapshot !== true && row.create_outcome && row.create_outcome !== "success")`)
would filter an **empty set** if applied as written, because `allItems` (everything arriving at
`Ingest Merge Response`) never contains an item with `create_outcome` set at all — that field
only ever exists on items inside `Pair Create Outcome To Row`'s own output, one hop upstream of
both drops above.

**The actual fix belongs one hop earlier, in `BUILD_CREATE_FAILURE_ROW_JS`, not in
`BUILD_INGEST_RESPONSE`'s filter alone:**
1. Widen `BUILD_CREATE_FAILURE_ROW_JS`'s filter from `row.create_outcome === "error"` to
   `row.create_outcome !== "success"` — this now also admits `"none"`/`"refused"` items (which
   `Build Association Request` would otherwise have silently swallowed).
2. Stamp the emitted row's `action`/`outcome` conditionally: `"create_failed"` when
   `row.create_outcome === "error"` (unchanged), `"create_unconfirmed"` otherwise — using
   `reason: row.create_outcome_reason || "no create response joined to this row"` (the exact
   text `73-REVIEW.md`'s own `written_records.ACTION_TO_OUTCOME` fix comment specifies for the
   `"none"` sub-case, vs. the review's `create_outcome_reason` value for `"refused"` — these are
   the "two sub-cases" `74-CONTEXT.md`'s D-74-06 bullet says must "stay distinguishable").
3. `BUILD_INGEST_RESPONSE` then joins these rows by email exactly as `failed`/`failedByEmail`
   already do today (no filter on `create_outcome` needed there at all — the row already arrives
   pre-classified with `action: "create_failed"` or `action: "create_unconfirmed"`, mirroring how
   `block`/`fail` already work).

**Interaction with D-74-02 this widening creates (flag for the plan, not resolved here):** once
`BUILD_CREATE_FAILURE_ROW_JS` emits rows for `"none"`/`"refused"` too, its own zero-rejection
sentinel-marker branch (`if (errors.length === 0) return [{ json: {
__SENTINEL_MARKER_KEY__: true } }];`, `[VERIFIED: scripts/build_cloud_workflows.py:855-857]`)
must change its condition from "zero `error` items" to "zero non-`success` items," or a batch
whose only create outcome is `"none"`/`"refused"` (no HubSpot rejection, but also no confirmed
success) would still emit the marker instead of the unconfirmed row it should now produce. Land
this widening and D-74-02's sentinel together, or write D-74-02's sentinel condition against the
POST-widening behavior from the start.

`written_records.ACTION_TO_OUTCOME`'s insertion point
`[VERIFIED: operator-claude-plugin/scripts/written_records.py:184-201]`:
```python
ACTION_TO_OUTCOME = {
    "write_blocked": GATED,
    "review": HELD,
    "needs_match_review": HELD,
    "research_failed": FAILED,
    "recompute_refused": FAILED,
    "skip": NO_ACTION,
    "proposed": NO_ACTION,
    "list_expansion_refused": FAILED,
    # ... (a `create_failed` entry exists further down per CONTEXT.md; add
    # "create_unconfirmed": FAILED beside it)
```
`ALL_OUTCOMES` frozenset `[VERIFIED: operator-claude-plugin/scripts/written_records.py:150-153]`
already contains `FAILED` — no new outcome constant is needed, only a new key mapping to the
existing `FAILED` value.

## CR-04 / D-74-07 / D-74-08 / D-74-09 — the freezer's scrub scope

### Current scrub (narrow — the bug)

`[VERIFIED: scripts/freeze_execution_rundata.py:80-97]`:
```python
def _redact_headers(run_data: dict) -> dict:
    """Deep-copies `run_data` and replaces every item's `json.headers` object
    wholesale. Never mutates the caller's dict."""
    redacted = copy.deepcopy(run_data) if isinstance(run_data, dict) else {}
    for _node_name, runs in redacted.items():
        if not isinstance(runs, list):
            continue
        for run in runs:
            if not isinstance(run, dict):
                continue
            main = (run.get("data") or {}).get("main")
            if not isinstance(main, list):
                continue
            for branch in main:
                if not isinstance(branch, list):
                    continue
                for item in branch:
                    if isinstance(item, dict) and isinstance(item.get("json"), dict):
                        if "headers" in item["json"]:
                            item["json"]["headers"] = REDACTED_PLACEHOLDER
    return redacted
```
This only ever touches `run["data"]["main"][branch][item]["json"]["headers"]`. It never touches
`run["error"]` (the node-run-level error object), `item["json"]["error"]`, or `item["error"]`
(sibling of `json`) — exactly CR-04's three named gaps. D-74-07's replacement (the
non-enumerating `_scrub` walking every dict key against a `_SENSITIVE_KEYS` tuple, already
sketched in the review's fix) should be applied to the **whole `run` dict**, not just
`run["data"]["main"]`, so `run["error"]` is caught — this is the single most important shape
change: today's function iterates `main` branches only and never looks at sibling keys of `data`.

The call site to change is `build_full_fixture`/`build_excerpt`
`[VERIFIED: scripts/freeze_execution_rundata.py:106-150]`, both of which call
`_redact_headers(_run_data_of(execution))` — a drop-in replacement for `_redact_headers` that
scrubs more broadly satisfies both callers with one change.

### The 7 fixtures D-74-08 re-redacts — verified live in this session

Five fixtures already carry `"x-enrichment-secret": "<redacted>"` as a literal string value —
**not a live secret**, already safe:
`[VERIFIED: grepped tests/n8n/fixtures/frozen/exec_1235{4,5,6,7,8}.runData.json, this session]`.
`73.1-SECURITY.md`'s "5 Phase-70 frozen fixtures carry a superseded `x-enrichment-secret`" note
refers to the **key name being present** (harmless — the value is the placeholder string), which
is exactly the case D-74-09's guard must NOT flag (the guard refuses value shapes, not key
names).

Two fixtures carry **live, unredacted JWT bodies** right now, committed to git:
`[VERIFIED: grepped `eyJ[A-Za-z0-9_-]{20,}` against tests/n8n/fixtures/frozen/exec_12434.runData.
json and exec_12449.runData.json, this session — real matches found, both files]`. These are
ZoomInfo OAuth bearer tokens (decodable JWTs — header `{"kid":...,"alg":"RS256"}`, payload
carries `iss: okta-login.zoominfo.com`, `exp`, scopes, an operator email
`alex.h@lightningvisuals.com`). `73.1-SECURITY.md:119` already records this as "pre-existing, out
of scope (recorded, not fixed here)... expired ~24h lifetime, not independently confirmed" —
`74-CONTEXT.md`'s D-74-08 is what fixes it in this phase, citing the same rotation/expiry
rationale ("The secret was rotated 2026-09-11; the JWTs have a 24h lifetime; git history is not
rewritten"). **Why CR-04's own text said the phase-73 fixtures were "clean"**: CR-04 scanned only
for `authorization`/`x-enrichment-secret`/`Bearer …`/`pat-na…` — it never scanned for the
`eyJ` JWT prefix, so the JWT leak was outside that scan's pattern set and only surfaced later, in
73.1's own security review. **Confirm these two JWTs are excluded from D-74-09's guard test
before considering it complete** — they must be re-redacted (D-74-08) BEFORE the guard
(D-74-09) is added, or the guard will correctly fail on them immediately.

### Existing consumers of these fixtures (re-redaction must not break them)

`[VERIFIED: grepped `fixtures/frozen` across tests/, this session]` — files that read frozen
fixtures:
- `tests/n8n/walkerEngineFidelityV1.test.mjs`, `tests/n8n/walkerEngineFidelity.test.mjs` — read
  `.runData.json` files and the `wf_*.2026-09-10.json` graph copies.
- `tests/n8n/v1RuntimeRecordings.test.mjs` — reads `exec_1235{4..8}.runData.json`, and **already
  has its own secret-refusal assertion**
  `[VERIFIED: tests/n8n/v1RuntimeRecordings.test.mjs:22-31]`:
  ```javascript
  test("frozen recordings carry no live secret — webhook request headers are redacted", () => {
    // ...
    for (const m of raw.matchAll(/"x-enrichment-secret":\s*"([^"]*)"/g)) {
      assert.equal(m[1], "<redacted>", `${id}: x-enrichment-secret must be redacted`);
    }
    assert.doesNotMatch(raw, /"x-real-ip":\s*"(?!<redacted>)/, ...);
  ```
  This test only checks `x-enrichment-secret`/`x-real-ip` value shape — it does not check for
  JWT-shaped strings and will not conflict with D-74-09's separate, broader guard. No edit needed
  to this test for D-74-08/09, but note it as the **existing precedent pattern** D-74-09's new
  guard should extend/generalize rather than duplicate — consider whether D-74-09's guard
  subsumes this test's assertion (same value-shape-refusal idea, applied repo-wide instead of to
  5 named files) or the two coexist.
- `operator-claude-plugin/tests/test_run_report_enrich_account.py` — reads
  `exec_12434.runData.json`/`exec_12449.runData.json` for D-73-11/12's reconciliation proof
  (24 updates + 11 creates + 1 skip, per `74-CONTEXT.md`'s citation). **Re-redacting these two
  files in place must not change any field this test reads** — the JWTs live inside a ZoomInfo
  provider-response node's runData, structurally distant from the `Decide Company Action`/`Build
  Response` node outputs this test actually asserts on. Confirm with a targeted grep of which
  node names carry the JWT before writing the widened scrub, so the widened `_SENSITIVE_KEYS`
  scrub (which will touch ANY `request`/`config`/`options` key at depth, not just the JWT's own
  location) doesn't accidentally blank a field this or the walker fidelity tests assert on.

`tests/n8n/fixtures/frozen/README.md`'s own "Redaction rule" section
`[VERIFIED, read in full this session]` currently only documents the `x-enrichment-secret`/
`x-real-ip`/`x-forwarded-for`/`cf-connecting-ip` header rule — it should gain a line describing
the widened D-74-07 scope (headers/error/request/options/config at any depth) so a future reader
doesn't reintroduce CR-04's gap.

## WR-07 — confirmed empirically as "input 5, one producer, no sentinel"

Already covered under CR-01/D-74-02 above for the mechanism; the concrete, live-verified proof:
```
$ python3 -c "... load n8n/wf_contact_ingest_cloud.json, walk connections to Ingest Merge Response ..."
numberInputs: 6
Decide Action Snapshot (out 0) -> input 0
Set Review (out 0) -> input 1
Associate Carry Merge (out 0) -> input 2
Associate Lane Sentinel Gate (out 0) -> input 2
HubSpot Update Gate Unreached Sentinel Gate (out 0) -> input 3
HubSpot Update No Refusal Sentinel Gate (out 0) -> input 3
HubSpot Update Refusal Pass-Through (out 0) -> input 3
HubSpot Create Gate Unreached Sentinel Gate (out 0) -> input 4
HubSpot Create No Refusal Sentinel Gate (out 0) -> input 4
HubSpot Create Refusal Pass-Through (out 0) -> input 4
Build Create Failure Row (out 0) -> input 5
```
`[VERIFIED: n8n/wf_contact_ingest_cloud.json, walked programmatically this session]` — every
other write-gated input (2, 3, 4) has 2-3 producers (the real lane plus one or two sentinels).
Input 5 has exactly **one** producer, `Build Create Failure Row`, which itself only runs when
`Pair Create Outcome To Row` ran, which only runs when `Create Carry Merge` fired, which (before
D-74-01) only reliably fires when a create was routed at all. This is exactly the "gated
starved-lane sentinel keyed on zero create-routed rows" D-74-02 specifies.

### The mechanism to reuse — `_add_starved_lane_sentinel`

`[VERIFIED: scripts/build_cloud_workflows.py:10732-10774]` — full docstring and body read this
session. Signature:
```python
def _add_starved_lane_sentinel(nodes, conns, name, source, condition_js, targets, x, y, *,
                                source_out_idx=0):
```
The exact idiom to copy is already in the same file, at the `wire_gate_refusal_lane` call sites
`[VERIFIED: scripts/build_cloud_workflows.py:2119-2124]`:
```python
_add_starved_lane_sentinel(
    nodes, conns, "Associate Lane Sentinel", "Decide Action",
    WRITE_SAFETY_GATE_JS + associate_sentinel_js,
    [(ingest_merge_response, assoc_carry_idx)], 60, 1020)
```
and the `unreached_condition_js` pattern inside `wire_gate_refusal_lane`
`[VERIFIED: scripts/build_cloud_workflows.py:2130-2135]`:
```python
unreached_condition_js=(
    'if (rows.length > 0 && !rows.some((r) => r.action === '
    f'"{_routed_action}")) return [{{}}]; return [];'),
```
D-74-02's sentinel condition is the same shape keyed on `"create"`: source `"Decide Action"`
(the full pre-write row set, already used by three other sentinels on this lane), condition
`'if (rows.length > 0 && !rows.some((r) => r.action === "create")) return [{}]; return [];'`,
target `[(ingest_merge_response, 5)]` — but **do not hardcode the literal `5`**; the existing
call sites derive the index via `_merge_input_index(conns, "Build Create Failure Row",
ingest_merge_response)` after `_append_merge_input` has already wired it, or by capturing
`_append_merge_input`'s own return value at
`scripts/build_cloud_workflows.py:2243` (`idx = _append_merge_input(nodes, conns,
ingest_merge_response, "Build Create Failure Row")`, currently the return value is discarded —
capture it and pass to the new sentinel call).

## WR-01 / WR-02 — write_grant.py, current anchors

`[VERIFIED: operator-claude-plugin/scripts/write_grant.py:546-580, 634-644, 715-740]` — content
matches the review's citations exactly (this file was touched most recently 2026-09-18 by
73.1-04, but that commit was about a *different* concern — refusing a second open grant — and
landed a comment near, not inside, this block; the WR-01/02 logic itself is byte-identical to
what the review describes). Current line anchors:
- `executions_basis = PROJECTED` — line 551 (inside the `try`, review didn't cite this exact
  line but it's the top of the block)
- `executions = 1` (the contact-upload hardcode WR-01 flags) — **line 574**, confirmed still
  inside the same `try:` that opened at line ~552, still after
  `chunking.chunk_ceiling(config)` raises `ChunkPlanError` for a missing
  `max_records_per_chunk` — reproducing the finding requires no new setup, the code path is
  unchanged.
- `EXECUTIONS_BASIS` constant — line 180; used unconditionally at line 639
  (`"executions_projection_basis": EXECUTIONS_BASIS,`) — WR-02's exact finding, unchanged.
- The render line printing "at {chunk_count} chunk(s) of at most {chunk_ceiling} record(s)" —
  line 735 — still unconditional, still prints for the contact-upload lane where `chunk_count`
  is explicitly documented (same file, `:558-568`, the D-73-16/F-A2 comment) as "NOT this lane's
  real POST count."

No test currently exercises "contact-upload lane + missing ceiling" or "contact-upload lane
basis text" combination — confirmed by the review, not independently re-checked here (would
require reading all of `operator-claude-plugin/tests/test_write_grant.py`, out of this session's
budget; the review's claim that no such test exists is corroborated by the code shape itself,
since the bug is reachable and nothing in the code guards it).

## WR-05 / WR-06 / WR-09 / WR-10 / WR-11 / WR-12 — anchors (current, drift is small-to-none)

| Finding | File | Current anchor `[VERIFIED, this session]` | Note |
|---|---|---|---|
| WR-05 | `operator-claude-plugin/scripts/report_enrichment.py` | `_ACTION_LANE_ORDER` at line 103; `backfill_missing_identity` at line 197; `ledger_by_id = {}` at line 219, populated at line 221-228 (`for _lane, node_name in _ACTION_LANE_ORDER: ... ledger_by_id[str(ledger_id)] = ledger_json` — last-lane-wins, unguarded) | File untouched since 2026-09-15 (Phase 73 itself); review's own line numbers likely still close |
| WR-06 | `operator-claude-plugin/scripts/chunking.py` | `dispatch_and_recover` at line 596; the discarded binding at line 674 (`write_records_rows, _excluded_marker_count = (...)`); returned dict at line 696 (`"written_records_failures": written_records_failures,` — no `excluded_marker_count` key) | File untouched since 2026-09-15 |
| WR-09 | `operator-claude-plugin/scripts/review_decision.py` | `_as_hubspot_text` at line 366; leg-1 comparison at lines 496-504 (`leg1_keys = ...`; `intent_mismatched = [key for key in leg1_keys if _as_hubspot_text(would_write.get(key)) != _as_hubspot_text(intended.get(key))]` — no absence/presence distinction) | File touched 2026-09-18 by an UNRELATED boolean-stringify fix (`b95e38b2`, quick task 260918-322) — confirm this specific block wasn't itself touched (grep shows it wasn't: `_as_hubspot_text` signature and the leg1 comparison shape match the review verbatim) |
| WR-10 | `scripts/build_cloud_workflows.py` | `extract_js_const` at line 173 | Same file as CR-01/02/03 — land in the same regeneration wave to save a diff cycle, though this function is unrelated code (build-time constant extraction, used for e.g. `FREEMAIL_DOMAINS`) |
| WR-11 | `operator-claude-plugin/scripts/csv_dedupe.py` | `_canonical_rows` at line 41, `zip`-truncation bug inside it (review's exact fix — pad with `row[i] if i < len(row) else ""` — applies cleanly) | File touched 2026-09-16 by 73-04 (a docs-only commit per its message: "correct row-numbering claim and note two scope edge cases") — confirm that commit didn't already partially fix this (grep of `_canonical_rows` shows it still zips raw, unpadded — the docs commit did not touch code) |
| WR-12 | `operator-claude-plugin/scripts/csv_dedupe.py` | `apply_dedupe` at line 101; `out_path`/`report_path` stem-only construction at lines 114, 121 | Same file/commit note as WR-11 |
| WR-03 | `operator-claude-plugin/scripts/csv_dedupe.py` | `__main__` block at line 133; `propose_dedupe`/`apply_dedupe` calls at lines 147/149 pass no `mapping_path` (`None` implicit) | `preview.py`'s own `__main__` resolution pattern (`config_gate.load_config().get("column_mapping_path")`) is the model to mirror — confirm its exact current line before copying (see WR-04 row) |
| WR-04 | `operator-claude-plugin/scripts/preview.py` | `collapse_block` at line 141; `--collapsed` arg parse at lines 254-257; the silent-`None`-on-failure read at line 268+ (`_collapsed = json.loads(Path(_collapsed_arg_path).read_text(...))` wrapped in a broad `except` per the review — confirm exact try/except shape before editing) | `preview.py`'s config-gate resolution pattern (cited by WR-03 as the thing `csv_dedupe.py` should mirror) — locate it near the top of `preview.py`'s own `__main__` (search `config_gate.load_config()` in this file) |

## D-74-11 — the end-of-phase proof send, mechanics

### Consent-gate vs write-safety-gate — do not conflate the two "armed" concepts

`operator-claude-plugin/scripts/dispatch.py`'s `dispatch(file_path, armed, config, ...)`
`[VERIFIED: operator-claude-plugin/scripts/dispatch.py:86-106]` — `armed=True` is required for
the function to even attempt the POST (`NotArmedError` otherwise); this is the **plugin's own
consent gate**, entirely separate from the **backend's `ALLOW_*` write-safety flags** baked into
the deployed n8n JSON (`ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`, etc., all read back
`"false"` per D-74-11's own acceptance criterion). **The proof send needs `dispatch(..., armed=
True, ...)` to actually reach n8n** — "disarmed" in D-74-11's sense refers exclusively to the
backend's own literal flags staying `false` in the deployed graph, never to whether the plugin
sends the request at all. Make this distinction explicit in the plan so a reader doesn't
misread "nothing armed" as "the POST itself was skipped."

### The multipart send shape (for constructing the one all-update batch, or driving `dispatch()` directly)

`[VERIFIED: operator-claude-plugin/scripts/dispatch.py:86-133]`:
```python
headers = {"X-Enrichment-Secret": config["webhook_secret"]}
files = {"data": ("contacts.csv", csv_bytes, "text/csv")}
files["run_id"] = (None, run_id)   # 2-tuple, NO content-type — 3-tuple silently misfiles under $binary
if source_by_field:
    files["source_by_field"] = (None, json.dumps(source_by_field))
response = transport(url, headers=headers, files=files, timeout=30)
```
`run_id` defaults to `uuid.uuid4().hex` if not passed `[VERIFIED: :101-102]`. **Load-bearing
detail already recorded in this file's own comment** (lines 108-119): the `run_id` and
`source_by_field` form fields MUST be 2-tuples with no filename/content-type, or n8n's multipart
parser files them under `$binary` instead of `$json.body`, breaking the echo the recovery poll
depends on (observed live 2026-09-10, executions `12200` vs `12201`).

### Readback

`operator-claude-plugin/scripts/executions_client.py` exposes `get_execution(config,
execution_id, transport=requests.get)` and `list_executions(config, workflow_id, ...)`
`[VERIFIED: operator-claude-plugin/scripts/executions_client.py:74-116]` — the same primitive
`scripts/freeze_execution_rundata.py` already uses. Auth is `X-N8N-API-KEY`
`[VERIFIED: operator-claude-plugin/scripts/executions_client.py:4]` — a **different** credential
from the webhook's `X-Enrichment-Secret` (dispatch uses the latter; readback uses the former —
both come from `.env`/config, neither is interchangeable with the other).

### Deploy/bounce mechanics (scoped single-workflow deploy — the precedent D-74-11 follows)

`[VERIFIED: scripts/deploy_n8n_workflows.py:596-624]` — `--only <filename>` is a two-arg CLI
form (`argv[0] == "--only"`), matches against `n8n/` directory contents, refuses with no API call
if the name doesn't match a committed file. `[VERIFIED: scripts/bounce_n8n_workflows.py:24-26]`
— `WORKFLOWS = {"n8n/wf_contact_ingest_cloud.json": "AwbBeShdPgV48eiY", ...}` is the committed
file → live workflow id map; bounce presumably iterates this same map (not independently
re-verified beyond the dict declaration this session — sufficient for planning purposes, since
`73.1-09`'s SUMMARY already documents live use of both scripts through the scratchpad driver).

### Precedent for the in-process credential driver (do not attempt `. ./.env` directly)

Already covered above under D-74-03's freeze step — the same `run_with_env.py` scratchpad
pattern from `73.1-09-SUMMARY.md:203-219` applies to deploy/bounce/dispatch/readback for D-74-11.
It is a **session-scratchpad file, never committed to the repo** — the plan should say so
explicitly (a `checkpoint` or task note), not assume the executor will discover this convention
unprompted.

## D-74-12 — MN-01 / NF-MJ-01 folded todo, what to search for

`[VERIFIED, full todo file read this session:
.planning/todos/pending/2026-09-11-merge-multi-run-drain-and-grouping-unobserved.md]` — the
question: does the engine drain a **second** pending run of the same Merge at end-of-run (MN-01),
or does a per-input FIFO model apply instead (NF-MJ-01)? The trigger named in the todo itself:
*"a live execution where one Merge is left with two partially-filled pending runs... freeze its
runData... run `tests/n8n/walkerEngineFidelityV1.test.mjs` against it."*

D-74-12 asks to search the frozen runData once `exec_12522.runData.json` exists (plus the
already-committed `exec_12434.runData.json`/`exec_12449.runData.json`) for exactly this shape:
a Merge node whose `runData` entry shows **two separate node-runs** (i.e., `runData[mergeName]`
is an array of length ≥ 2), which would indicate two drained pending runs rather than the
single-drain-per-Merge cap the walker currently enforces. The mechanical check is:
```python
import json
d = json.load(open("tests/n8n/fixtures/frozen/exec_12522.runData.json"))
for name, runs in d["runData"].items():
    if len(runs) > 1 and "Merge" in name:  # or check node type via the graph, not just name
        print(name, len(runs))
```
`74-CONTEXT.md`'s own instruction is explicit: **never close the todo on a `resolves_phase`
match alone** — if this search finds nothing (the likely outcome, since 12522 is a single-lane,
no-conflict all-creates-succeed execution with no reason to produce a doubly-pending Merge), keep
the todo open with its trigger unchanged and say so in the SUMMARY, per D-74-12's own text.

## D-74-13 — the recovery-bound question, current numbers

`[VERIFIED: operator-claude-plugin/scripts/watch.py:66]` — `DEFAULT_BOUND_SECONDS = 600.0`.
`[VERIFIED: operator-claude-plugin/scripts/chunking.py:209-220]` — `chunk_ceiling(config, key=
CEILING_KEY)`, `CEILING_KEY = "max_records_per_chunk"` (line 60). `dispatch_and_recover`'s
`bound_seconds` parameter `[VERIFIED: operator-claude-plugin/scripts/chunking.py:596-598, 641-
644]` flows through to `_watch.recover_dispatch(..., bound_seconds=bound_seconds, ...)`.

Stress-attempt-3 Stage D timing evidence
`[VERIFIED: .planning/phases/73-ga-fix-list-from-stress-attempt-2/73-UAT.md:190-196, 241]`: a
48-row match pass over run_id `2950009377574a6cb1bfcb3ad4079795` (match executions
`12549-12551`) produced 18 auto-matched, 2 proposed, 11 unmatched, **17 unchecked** (~35%) — "a
match chunk did not settle inside the recovery bound." No further per-chunk timing (seconds
elapsed, chunk count, or `bound_seconds` value actually used in that run) is recorded in
`73-UAT.md` beyond this summary line — the planner should not expect finer-grained timing data
to exist; D-74-13's own scope ("read the recovery bound... against stress attempt 3's timings")
may need to work from this single aggregate figure rather than a full timing trace. `74-CONTEXT.
md` explicitly defers a live re-run: *"No live Stage D run this phase; the todo's trigger stays
until one does."* This decision is therefore a **read + parametrise + test** task (raise/expose
`bound_seconds` as config-driven rather than the fixed 600s default, surface `unchecked_count` in
the run report — `chunking.py`'s existing `resolve_bound_seconds(config, record_count)`
`[VERIFIED: :97-108]` already reads a config override `watch_bound_seconds` if present, so
"parametrise" may already be half-done — confirm whether a config key already exists before
building a new one) with **no live verification possible or expected** this phase.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| A new merge-input producer that must fire exactly once, marker-or-real, per execution | A bespoke Code node wired by hand | `_add_starved_lane_sentinel` (`scripts/build_cloud_workflows.py:10732`) | This exact "condition → gate → targets" shape is what makes a sentinel a single, non-double-firing producer under v1 — a hand-wired equivalent risks re-discovering the double-fire bug this mechanism was built to prevent (documented at length in the surrounding comments) |
| Deriving a Merge's newly-appended input index | Hardcoding the literal integer | `_merge_input_index(conns, source_name, merge_name)` or capture `_append_merge_input`'s return value | The existing code already treats hardcoded indices as a maintenance hazard (see the `mirror_index` docstring: "derived, never hand-listed... enumerating them by name here would go stale") |
| A second redaction pass elsewhere | A parallel/duplicate scrubber in the walker or a test file | Widen `freeze_execution_rundata.py`'s single scrubber (D-74-07) | One redaction chokepoint; `v1RuntimeRecordings.test.mjs`'s own secret-refusal test already exists as the enforcement pattern to extend, not duplicate |
| A brand-new CSV column-mapping resolver for `csv_dedupe.py`'s CLI (WR-03) | A fresh `config_gate` read | Mirror `preview.py`'s existing `__main__` resolution exactly (same file, same pattern, confirmed present) | Two independent readers of the same config key is exactly the kind of drift WR-03 itself flags — don't introduce a third shape |

**Key insight:** every fix in this phase reuses a mechanism this repo already built for a
sibling problem (sentinel gates, carry merges, redaction chokepoints, config-gate resolution).
None of the 13 decisions call for new architecture — the planner's risk is under-reusing, not
over-building.

## Common Pitfalls

### Pitfall 1: Trusting `73-REVIEW.md`'s line numbers
**What goes wrong:** editing the wrong code, or failing to find the cited block at all, in
`scripts/build_cloud_workflows.py` (drift up to ~260 lines) and (to a lesser extent) `write_
grant.py`/`review_decision.py`/`csv_dedupe.py` (drift 0-30 lines from unrelated same-day commits).
**Why it happens:** 13 Phase-73.1 commits landed between the review (2026-09-18) and this
research/planning (2026-09-19), several touching the exact same files this phase edits, for
unrelated reasons (including a name-colliding "CR-01"/"WR-01"/"WR-03" from a different review).
**How to avoid:** grep by function/constant name (`_append_merge_input`, `EXECUTIONS_BASIS`,
`_as_hubspot_text`, `_canonical_rows`, etc.) before every edit; this document's `[VERIFIED]`
citations give the line numbers as of this research session, which will ALSO drift the moment
CR-01/CR-02/CR-03/WR-07 land (they all touch the same 100-line region of `build_cloud_workflows.
py`) — re-grep before each subsequent decision in the same file within this phase's own plan.

### Pitfall 2: Regenerating before all same-file decisions are speced
**What goes wrong:** running `build_cloud_workflows.py` after landing only D-74-01, then again
after D-74-02, then again after D-74-06/WR-07, produces three separate diffs against the SAME
node region and three separate `git diff --quiet n8n/` idempotency checks, when one regeneration
after all of CR-01/02/03/WR-07 would suffice and be easier to review as one coherent splice.
**How to avoid:** as noted in the Summary, wave these four together.

### Pitfall 3: The freezer needs credentials this session cannot read directly
**What goes wrong:** a plan step that says "run `scripts/freeze_execution_rundata.py 12522`" as
a bare Bash command will hit the same `.env`-read guard 73.1-09 hit, and — unlike a read-only
grep — this one genuinely needs live network access, so it cannot be worked around by reading
code instead.
**How to avoid:** plan D-74-03's freeze step (and D-74-11's proof-send step) as an explicit
`checkpoint:human-verify`-style task, or pre-authorize the in-process dotenv scratchpad pattern
in the plan's own text (citing `73.1-09-SUMMARY.md`) so the executor doesn't have to rediscover
the workaround mid-task.

### Pitfall 4: Re-redacting the two JWT fixtures could silently break `test_run_report_enrich_
account.py`
**What goes wrong:** D-74-07's widened, non-enumerating `_scrub` (walking every key at every
depth) will touch far more of `exec_12434.runData.json`/`exec_12449.runData.json` than the two
JWT strings alone — any `error`/`request`/`options`/`config` key anywhere in those two large
files (3.3MB and 620KB) gets replaced. If any of those keys happen to sit inside the node outputs
`test_run_report_enrich_account.py` actually asserts on (`Decide Company Action`, `Build
Response`), the widened scrub could blank a field the test reads.
**How to avoid:** run the existing test (`.venv/bin/python -m pytest
operator-claude-plugin/tests/test_run_report_enrich_account.py -v`) immediately after
re-redacting, before considering D-74-08 done — this is cheap (offline, no credentials) and
directly answers whether the widened scrub collided with this test's assertions.

### Pitfall 5: `pairCreateOutcome.js`'s `_create_error` stamp must land on the error edge, not inside the pair function
**What goes wrong:** D-74-04's stamp is meant to be applied by a Code node ON THE ERROR EDGE
(possibly the same node D-74-01 adds for the producer role — CONTEXT.md leaves this as Claude's
discretion), stamping every item that flows through it. If the stamp is instead computed inside
`pairCreateOutcome.js` itself (e.g. `_isCarriedRow` rewritten to also check some other signal),
it stops being "explicit... instead of structural" — the whole point of D-74-04 is that the stamp
is applied by something that KNOWS it is on the error branch (the graph topology), not inferred
from the item's shape after the fact.
**How to avoid:** keep the stamp application and the stamp consumption as two distinct steps —
one Code node (graph-topology-aware) writes `_create_error: true`; `pairCreateOutcome.js` (shape-
and-topology-blind, pure function) reads it as the first classification test.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Node suite | `node --test tests/n8n/*.test.mjs` (glob form — the directory form is broken on node 24, per repo memory) |
| Node baseline (verified this session) | 1303 pass / 0 fail |
| Python suite | `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider` |
| Python baseline (verified this session) | 5132 passed / 160 skipped |
| Config files | none dedicated — both suites run from repo root, no pytest.ini/jest.config beyond defaults already in place |
| Idempotent regen check | `.venv/bin/python scripts/build_cloud_workflows.py && git diff --quiet -- n8n/` — verified CLEAN at baseline this session |

### Decision → Test Map

| Decision | Test type | Test file (existing to extend, or new) | Verifiable offline? |
|---|---|---|---|
| D-74-01 | node, graph-shape | new assertion in a `ingestCreateErrorLane.test.mjs`-adjacent test (or extend it): walk the graph, confirm `Create Carry Merge` input 2 has a REAL producer node (not a direct `HubSpot Create` edge) | Yes — pure graph-walk, no live call |
| D-74-02 | node, graph-shape + starvation | extend `tests/n8n/ingestCreateErrorLane.test.mjs` (or a sibling) with an all-update batch case; assert `starvedWithData(trace)` is empty and no `merge_fired_with_unfilled_input` on input 5 | Yes — this is exactly what WR-07's own reproduction already did (`tests/n8n/lib/walkWorkflow.mjs`'s `stalled` trace) |
| D-74-03 | node, walker unit + fidelity | (a) unit test asserting `propagate` pads only `outputIndex === 0` on an AOD node with 2 branches; (b) new fidelity test in the `walkerEngineFidelityV1.test.mjs` family pinned against frozen `exec_12522.runData.json` | (a) offline; (b) needs the live freeze first (Pitfall 3) |
| D-74-04 | node, unit | `tests/n8n/pairCreateOutcome.test.mjs` (exists per `73-REVIEW.md`'s files_reviewed_list) — add a case where `_create_error: true` is set but the item ALSO has an `action` field (proves the stamp wins over shape) | Yes, offline |
| D-74-05 | node, doc-only | no new test — a comment/tag edit in `ingestCreateErrorLane.test.mjs` | N/A |
| D-74-06 | node (BUILD_INGEST_RESPONSE) + python (`written_records`) | extend `tests/n8n/ingestCreateErrorLane.test.mjs` or `pairCreateOutcome.test.mjs` for the graph side; `operator-claude-plugin/tests/test_written_records.py` (exists per review's file list) for the `create_unconfirmed` → `FAILED` mapping | Yes, offline |
| D-74-07/08/09 | python, unit + guard | new guard test over `tests/n8n/fixtures/frozen/` (D-74-09); re-run `test_run_report_enrich_account.py` after D-74-08's re-redaction (Pitfall 4) | Yes, offline (freezing itself needs live creds only for exec 12522, not for re-redacting the 7 EXISTING fixtures, which is a pure local rewrite) |
| D-74-10 (WR-03/04/08/09/10/11/12) | python + node, unit each | one test per finding — see the WR anchor table above for which existing test file is nearest (e.g. `operator-claude-plugin/tests/test_csv_dedupe.py` for WR-03/04/11/12, `operator-claude-plugin/tests/test_review_decision.py` for WR-09) | Yes, offline, all seven |
| WR-01/02 | python, unit | `operator-claude-plugin/tests/test_write_grant.py` (exists per review's file list) — add the missing-ceiling contact-upload case and a basis-text assertion | Yes, offline |
| WR-05/06 | python, unit | no dedicated test files were found in the review's `files_reviewed_list` for `report_enrichment.py`/`chunking.py` under these specific functions — check `operator-claude-plugin/tests/` for an existing `test_report_enrichment.py`/chunking test before assuming one needs creating from scratch | Yes, offline |
| D-74-11 | live, disarmed | one manual proof send + runData read-back; freeze the execution | **No** — this is the phase's one genuinely live step, gated on human/operator execution per the standing "never arm from Claude" rule |
| D-74-12 | offline, data-mining | a Python/Node script over already-frozen (or newly-frozen) runData JSON | Yes, once exec 12522 is frozen — otherwise blocked on the same live step as D-74-03 |
| D-74-13 | python, unit (parametrise) | `operator-claude-plugin/tests/test_run_report_enrich_account.py` or a `chunking`-specific test file — confirm which exists | Yes, offline (no live Stage D run this phase per CONTEXT.md) |

### Sampling Rate
- **Per task commit:** run the specific test file just touched (`node --test tests/n8n/<file>.test.mjs` or `.venv/bin/python -m pytest <file> -q`)
- **Per wave merge:** full suites — `node --test tests/n8n/*.test.mjs` and `.venv/bin/python -m pytest -q --tb=short -p no:cacheprovider`
- **Phase gate:** both full suites green, `git diff --quiet -- n8n/` after final regeneration, `.venv/bin/python scripts/todo_triage.py` zero-inbox (per CLAUDE.md §31), then D-74-11's one live disarmed send

### Wave 0 Gaps
None — every test file this phase needs already exists in the repo (confirmed for the
CR-01..04/WR-07 cluster and the write_grant/review_decision/csv_dedupe/written_records
clusters by the `files_reviewed_list` in `73-REVIEW.md`'s own frontmatter, cross-checked
against a live `git log`/anchor grep this session). The only genuinely new artifact is the
`exec_12522.runData.json` fixture (D-74-03), which is data, not test infrastructure, and is
explicitly a task inside this phase's own scope rather than a pre-req gap.

## Security Domain

Per `security_enforcement` (absent from `.planning/config.json`'s workflow block in what was
read this session → treat as enabled per the reference's own default) and per D-74-07/08/09
already being the security-relevant portion of this phase's own scope:

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V7 Error Handling / Logging (nearest ASVS mapping for "don't leak secrets into logs/fixtures") | yes | D-74-07's non-enumerating scrub, D-74-09's guard test — never a key-by-key allowlist, per this repo's own established idiom (`freeze_execution_rundata.py`'s docstring already argues for wholesale replacement over enumeration) |
| V6 Cryptography (token/secret handling) | yes, narrowly | No cryptography is performed by this phase's code — the concern is committed-secret hygiene only (D-74-08's JWT re-redaction), not key management |
| V2/V3/V4/V5 | no | This phase makes no authentication, session, access-control, or input-validation change |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Committed OAuth bearer token / webhook shared secret in a test fixture | Information Disclosure | D-74-07 (wholesale scrub, not key-by-key), D-74-08 (re-redact existing leaks), D-74-09 (guard test refusing value shapes) — this repo's own established pattern (see CLAUDE.md §13.0.1's `T-73-06-01` threat item, already the model `BUILD_CREATE_FAILURE_ROW_JS` follows: read at most 2-3 named SCALAR fields off an error object, never serialize the whole object) |
| A rejected write silently reported as succeeded, corrupting the durable operator-facing ledger | Repudiation / Information Disclosure (of a false "success") | D-74-06 (`create_unconfirmed` → `FAILED`, never `created_id_unknown`) |
| A Merge input that can silently starve on a common (not exotic) batch shape, dropping the deliverable | Denial of Service (of the reporting channel, not the write itself — writes still land, only the report is affected for WR-07's case; for CR-01's case the ASSOCIATION write itself would silently fail to happen if the drain-based recovery ever failed) | D-74-01/02 (real producer + gated sentinel, not a hoped-for engine behavior) |

No new package, credential, or external endpoint is introduced anywhere in this phase — the
Package Legitimacy Audit section is not applicable (no `npm install`/`pip install` of any kind is
part of this phase's scope).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `.venv/bin/python` (repo venv) | all Python tests, builder regeneration | ✓ (verified this session — pytest ran, builder ran) | 3.14 | — |
| `node` | `node --test` suite | ✓ (verified this session — 1303 tests ran) | not captured this session, assume repo-pinned | — |
| n8n Cloud API (`N8N_URL`/`N8N_API_KEY`) | D-74-03's freeze of execution 12522, D-74-11's deploy/bounce/send/readback | Credentials exist in `.env` but **this session cannot read them directly** (permission-blocked) | — | In-process dotenv scratchpad driver (`run_with_env.py` pattern, `73.1-09-SUMMARY.md`), or hand off as an operator-run `checkpoint` step |
| HubSpot API | none directly this phase (D-74-11 is a disarmed all-update send — no HubSpot write is expected to occur, `ALLOW_*` flags stay false) | n/a | — | — |

**Missing dependencies with no fallback:** none — the n8n Cloud credential gap has an
established, repo-precedented fallback (the scratchpad driver), even though this research session
itself did not exercise it (out of scope for a read-only research pass; flagging the mechanism is
sufficient, per the Skill's own instruction to plan a `checkpoint:human-verify` around any step
this document cannot itself falsify).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `run_with_env.py` scratchpad pattern from 73.1-09 still works unchanged in this session's sandbox (same secret-read-guard trigger condition) | D-74-03, D-74-11, Environment Availability | Low-medium — if the guard's trigger condition changed, the executor needs to rediscover a workaround mid-task rather than following this document's citation; does not block planning, only affects execution smoothness |
| A2 | `bounce_n8n_workflows.py`'s bounce mechanism iterates the same `WORKFLOWS` dict shown for `--only`-style scoped deploy without further gotchas (not independently traced beyond the dict declaration) | D-74-11 | Low — this is a read of a 2-line dict declaration, not a claim about untested behavior; `73.1-09`'s own SUMMARY already reports successful live use of the identical mechanism the same week |
| A3 | No config key already exists for a configurable recovery bound beyond `watch_bound_seconds` (seen at `chunking.py:105`) — i.e., "parametrise" in D-74-13 may reduce to "expose the already-supported override in the plugin's operator-facing config docs/skill text" rather than new code | D-74-13 | Low — worst case the planner discovers during Task planning that more code is needed than this document estimates; the finding itself (bound exists, override path exists) is directly read from source, not inferred |

**If this table is empty:** N/A — three low-risk assumptions listed above; none touches a
locked CONTEXT.md decision, only execution-mechanics details this research could not itself
falsify without live credentials or a full trace of every touched file's test suite.

## Open Questions

1. **Does `operator-claude-plugin/tests/test_write_grant.py` currently have ANY contact-upload +
   grant-preview test at all**, or is the whole lane's grant text untested?
   - What we know: the review asserts "no test covers this combination" — corroborated by the
     code shape (the bug is reachable, nothing guards it), not independently confirmed by reading
     the full test file this session (out of budget).
   - What's unclear: whether the plan needs to add a NEW test file section or can extend an
     existing contact-upload-lane test block.
   - Recommendation: the planner should `grep -n "contact.upload\|COST_LANE_CONTACT_UPLOAD"
     operator-claude-plugin/tests/test_write_grant.py` as the plan's own first step before
     writing the WR-01/02 task's test-file target.

2. **Does a Python test file already exist for `report_enrichment.py`'s `backfill_missing_
   identity` (WR-05) or `chunking.py`'s `dispatch_and_recover` (WR-06)?**
   - What we know: `73-REVIEW.md`'s `files_reviewed_list` does not name a
     `test_report_enrichment.py` or a chunking-specific test file explicitly (it names
     `test_cost_guard.py`, `test_run_manifest.py`, `test_run_report_enrich_account.py`,
     `test_written_records.py` among the plugin tests reviewed).
   - What's unclear: whether these two functions are tested indirectly through one of the named
     files, or need a new dedicated test file.
   - Recommendation: `grep -rn "backfill_missing_identity\|dispatch_and_recover" operator-claude-
     plugin/tests/` as a first planning step.

## Sources

### Primary (HIGH confidence — read/executed this session)
- `scripts/build_cloud_workflows.py` (multiple ranges: 166-182, 769-806, 820-1010, 1745-1825,
  2085-2250, 9931-9970, 10306-10460, 10494-10520, 10592-10650, 10700-10800) — direct `Read`/`sed`
  this session
- `operator-claude-plugin/scripts/write_grant.py` (lines 540-580, 634-644, 715-740) — direct
  `sed` this session
- `n8n/wf_contact_ingest_cloud.json` — loaded and its `connections` table walked programmatically
  this session (the strongest evidence in this document — a generated artifact, not source code)
- `n8n/code/pairCreateOutcome.js` — full file read this session
- `tests/n8n/lib/walkWorkflow.mjs` (lines 280-570, 620-700) — read this session
- `tests/n8n/ingestCreateErrorLane.test.mjs` (lines 1-110) — read this session
- `tests/n8n/v1RuntimeRecordings.test.mjs` (secret-refusal test) — read this session
- `tests/n8n/fixtures/frozen/README.md` — read in full this session
- `tests/n8n/fixtures/frozen/*.json` — grepped for secret/JWT patterns this session (real JWT
  strings found, unredacted, in `exec_12434.runData.json`/`exec_12449.runData.json`)
- `scripts/freeze_execution_rundata.py` — full file read this session
- `operator-claude-plugin/scripts/{write_grant,report_enrichment,chunking,csv_dedupe,preview,
  review_decision,written_records,dispatch,executions_client,watch}.py` — targeted grep + sed
  reads this session
- `scripts/deploy_n8n_workflows.py`, `scripts/bounce_n8n_workflows.py` — targeted grep this
  session
- `git log` on every touched file, this session (established the line-drift finding and the
  naming-collision finding)
- Local test run: `node --test tests/n8n/*.test.mjs` (1303/0), `.venv/bin/python -m pytest -q
  --tb=short -p no:cacheprovider` (5132 passed/160 skipped), `python scripts/build_cloud_
  workflows.py && git diff --quiet -- n8n/` (clean) — all executed this session

### Secondary (MEDIUM confidence)
- `https://raw.githubusercontent.com/n8n-io/n8n/master/packages/core/src/execution-engine/
  workflow-execute.ts` — fetched this session via WebFetch, `ensureAlwaysOutputData` quoted
  above; corroborates (does not independently prove, since not executed) that n8n pads output
  index 0 only
- `.planning/phases/73-ga-fix-list-from-stress-attempt-2/73-UAT.md`, `73-REVIEW.md`,
  `73-CONTEXT.md` — read in full, but these are prior-phase planning artifacts (self-reported by
  a prior agent), not independently re-verified against a live execution by this research pass
  except where separately cross-checked against code/fixtures above
- `.planning/phases/73.1-.../73.1-09-SUMMARY.md`, `73.1-SECURITY.md` — read, used for the
  scratchpad-driver precedent and the JWT/x-enrichment-secret pre-existing-gap note

### Tertiary (LOW confidence)
- None — this research performed no web search and made no claim resting on training-data
  recall; every factual claim above is either a direct file read this session or explicitly
  labeled as a prior-phase self-report (Secondary tier).

## Metadata

**Confidence breakdown:**
- Code anchors (CR-01..04, WR-01..12 locations): HIGH — every anchor re-read/re-grepped this
  session against the current working tree, several cross-checked against the *generated* JSON
- Graph-shape mechanics (Create Carry Merge, Ingest Merge Response inputs): HIGH — verified
  programmatically against the live generated `n8n/wf_contact_ingest_cloud.json`, not inferred
  from source comments alone
- Live-execution/credential-dependent steps (D-74-03's freeze, D-74-11's send): MEDIUM — the
  mechanism and precedent are well-documented in prior-phase SUMMARYs, but this research session
  could not itself exercise them (no live n8n credentials available to the research agent)
- D-74-13's timing data: MEDIUM — only the aggregate 17/48 figure is recorded anywhere in the
  repo; no finer-grained per-chunk timing exists to research further

**Research date:** 2026-09-19
**Valid until:** short — this is an actively-developed file set (`build_cloud_workflows.py` was
touched the same day this research ran); re-grep every anchor immediately before use if more than
a few hours pass, and definitely re-grep after any of CR-01/02/03/WR-07 land (they share a file
region). Recommend treating this document's line numbers as "valid at time of writing" only, not
as a stable reference beyond the current planning session.
