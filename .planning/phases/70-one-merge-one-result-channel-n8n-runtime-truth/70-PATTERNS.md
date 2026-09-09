# Phase 70: One merge, one result channel — n8n runtime truth - Pattern Map

**Mapped:** 2026-09-09
**Files analyzed:** 9 (grouped; the builder change touches ~25 by-name-read sites and 22
convergence points inside ONE file, counted as one file-level change)
**Analogs found:** 9 / 9 (all in-repo; no external pattern needed)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `tests/n8n/<walker>.mjs` (new graph-walker helper) | test / utility | transform (offline execution-order simulation) | `tests/n8n/enrichmentGateRunRecoveryFlow.test.mjs` (`makeDollar`/`runOneNodeRun`) + `tests/n8n/researchChainRowFlow.test.mjs` (`new Function` runner) | exact — same mechanism, generalized |
| `tests/n8n/<enrichmentMixedBatch>.test.mjs`, `tests/n8n/<ingestMixedBatch>.test.mjs` (new) | test | integration (2 lanes × 2 actions through the walker) | `tests/n8n/ingestWebhookRespondsAllEntries.test.mjs` (its assertion shape: every row returns exactly once) | role-match |
| `scripts/build_cloud_workflows.py` — new build-time assertion in `main()` | build script / config | validation (fail generation on bad jsCode) | `scripts/build_cloud_workflows.py::_normalize_hubspot_auth` (a whole-workflow post-pass invoked from `main()` before write) | exact — same insertion point and pattern (mutate/validate the built dict before `json.dumps`) |
| `scripts/build_cloud_workflows.py` — Merge node emission (new node-builder helper) | builder / node factory | event-driven (n8n node construction) | `code_node()` (:706) for the dict shape; `_hs_http_search_node()` (:7436) for a specialized-node-builder docstring/contract convention | exact for dict shape; role-match for builder convention |
| `scripts/build_cloud_workflows.py` — IF-shaped write gate (rewrite of `splice_write_gates`/`_write_gate_js`) | middleware (gate) | request-response (permit/refuse a write) | `splice_write_gates()` (:7641) + `_write_gate_js()` (:7608) — existing, being reshaped from single-output-drop to two-output IF | exact — same mechanism, output count changes |
| `operator-claude-plugin/scripts/watch.py` (generalize `recover_async_dispatch`) | client / poller | request-response (bounded poll → settled report) | itself — `recover_async_dispatch` (:464), `find_executions_by_run_id` (:440), `_build_response_rows` (:421) are the ALREADY-correct mechanism being promoted, not replaced | exact |
| `operator-claude-plugin/scripts/chunking.py` (`dispatch_plan` — drop `async_ack`) | service | batch / event-driven | itself (:352) — remove the `async_ack` branch (:493-495, :557) | exact |
| `operator-claude-plugin/scripts/written_records.py` (`append_chunk` — write-only ledger) | model / ledger | CRUD (append-only) | itself (:474) + `classify_item` (:273) — restrict call sites, not the function body | exact |
| `operator-claude-plugin/scripts/preingest.py` (`render_enriched_preview`) | service / formatter | transform | itself (:981) + `confidence.assess` (read-only dependency) | exact |
| `operator-claude-plugin/scripts/dispatch.py` (drop `async_ack` passthrough) | service | request-response | itself (:58) | exact |

## Pattern Assignments

### `tests/n8n/<walker>.mjs` (new — graph walker)

**Analog 1:** `tests/n8n/enrichmentGateRunRecoveryFlow.test.mjs`

**`new Function` jsCode runner** (lines 55-68 of that file):
```javascript
function runOneNodeRun(jsCode, inputItems, runData, runIndex) {
  const $ = makeDollar(runData);
  const $input = { all: () => inputItems.map((j) => ({ json: j })) };
  const $runIndex = runIndex;
  const $getWorkflowStaticData = () => ({});
  const fn = new Function(
    "$", "$input", "$runIndex", "$getWorkflowStaticData", `"use strict";\n${jsCode}`
  );
  const out = fn($, $input, $runIndex, $getWorkflowStaticData) || [];
  return out.map((it) => (it && it.json !== undefined ? it.json : it));
}
```
**Run-history model to generalize** (lines 39-49): `makeDollar(runData)` — `runData` is
`{ nodeName: [run0Items, run1Items, ...] }`, mirroring n8n's own per-node run history. The
walker's job is to DRIVE this model from a workflow's own `connections` map (fire each node
per inbound edge, in `executionOrder` order) rather than have the test author the run
history by hand — this file hand-builds `runData`; the walker must compute it.

**Node/workflow loading convention** (lines 26-34):
```javascript
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");
const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
const node = (name) => {
  const n = wf.nodes.find((x) => x.name === name);
  assert.ok(n, `node present: ${name}`);
  return n;
};
const jsCodeOf = (name) => node(name).parameters.jsCode;
```

**Analog 2:** `tests/n8n/researchChainRowFlow.test.mjs`, line 99 — the fuller `new Function`
call signature the walker should support for nodes needing more globals:
```javascript
const fn = new Function("$", "$input", "$json", "$node", "$now", "$today", ...);
```
Its header comment (line 16) states the load-bearing fact: "this executes the repo's OWN
committed workflow jsCode via `new Function` — the same mechanism n8n's Code node uses at
runtime." The walker inherits this justification verbatim.

**What must change, not just be copied:** neither analog models a native Merge node, IF
branching from `connections`, or `Respond`/`responseData` — these are genuinely new (per
RESEARCH.md, zero native Merge nodes exist in any committed JSON today). Build the walker
as a small interpreter over `wf.connections` that:
- tracks, per node, an array of "runs" (each an item array) — literally `makeDollar`'s
  `runData` shape, but computed instead of hand-fed;
- for a Code node, calls `runOneNodeRun`'s exact mechanism per firing edge;
- for a Merge node, waits for (or requires-present, per D-70-02's "Always Output Data"
  finding) all configured inputs before firing once;
- for an IF node, evaluates its condition per item and routes to the correct edge;
- for `Respond to Webhook`, records the first (and only, after D-70-07) firing.

---

### New build-time assertion in `scripts/build_cloud_workflows.py::main()`

**Analog:** `scripts/build_cloud_workflows.py::_normalize_hubspot_auth` (definition ~line
8768; call sites throughout `main()`, e.g. `wf_contact_ingest_cloud.json` write).

**Pattern — a whole-workflow post-pass invoked right before `json.dumps`, once per variant:**
```python
def _normalize_hubspot_auth(wf: dict) -> dict:
    """Normalize every HubSpot node in a built workflow. ..."""
    for node in wf.get("nodes", []):
        if node.get("type") != HUBSPOT_NODE_TYPE:
            continue
        params = node.setdefault("parameters", {})
        params["authentication"] = HUBSPOT_AUTH_MODE
        ...
    return wf

def main():
    out_cloud = ROOT / "n8n" / "wf_contact_ingest_cloud.json"
    out_cloud.write_text(json.dumps(_normalize_hubspot_auth(build_cloud()), indent=2) + "\n")
```
The new by-name-read assertion follows this SAME shape but **raises instead of mutating**:
walk every node's `parameters` (jsCode strings AND parameter-expression trees — RESEARCH.md
Pitfall 2 warns a jsCode-only grep misses `.item` reads embedded in IF/Set parameter
expressions), searching for the literal `$('` pattern AND the dynamic `$(name)` call form
`recoverConvergedRun` uses (RESEARCH.md: `(name, b, r) => $(name).all(b, r)` has no adjacent
quote character, so a literal-substring assertion alone is insufficient). `main()` currently
has **zero assertions of any kind** (confirmed in RESEARCH.md) — this is a wholly new
insertion, but the insertion POINT and the "mutate-or-validate the dict, once, right before
write" convention is directly borrowed from `_normalize_hubspot_auth`.

---

### Merge-node emission in the builder (new node-builder helper)

**Analog 1 (dict shape convention):** `code_node()` (:706):
```python
def code_node(name, js, x, y):
    return {
        "parameters": {"mode": "runOnceForAllItems", "jsCode": js},
        "id": nid("c"), "name": name,
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [x, y],
    }
```
A `merge_node(name, x, y, num_inputs, mode="append")` helper should mirror this exactly:
same `id`/`name`/`type`/`typeVersion`/`position` keys, `type: "n8n-nodes-base.merge"`,
`parameters: {"mode": mode, "numberInputs": num_inputs}` (per RESEARCH.md's Assumption A1,
confirm `typeVersion` against the account's live node-type schema before hard-coding — do
not blindly copy `code_node`'s `typeVersion: 2`, which is Code-node-specific).

**Analog 2 (specialized-node-builder docstring/contract convention):**
`_hs_http_search_node()` (:7436) — its docstring pattern (state the BUG number, the live
symptom, the workaround mechanism, and which call sites migrate) is the convention every
non-trivial node-builder in this file follows. The Merge-node helper's docstring should name
D-70-01/D-70-02 and the "Always Output Data" requirement RESEARCH.md adds as a builder-level
obligation, not an afterthought — every lane-terminal node feeding a new Merge input needs
`"alwaysOutputData": true` set somewhere in its own `parameters`.

**Analog 3 (splicing into existing connections):** `splice_write_gates()` (:7641) — its
"re-point every inbound connection from X to a newly-inserted node, then wire the new node
to X" mutation pattern is exactly what inserting a Merge node in front of `Build Response`
(10 inbound edges) or `Enrichment Gate` (5 inbound edges) requires: collect every `conn`
across `conns` whose target is the convergence node, redirect each to a distinct Merge input
index instead of a single gate, then wire `Merge -> convergence_node`.

---

### IF-shaped write gate (rewrite of `splice_write_gates` / `_write_gate_js`)

**Analog:** itself — `_write_gate_js()` (:7608) and `splice_write_gates()` (:7641), already
live and working for ingest/maintenance/review-decision (RESEARCH.md's corrected inventory:
3 call sites at L1086/L7989/L8675 — NOT enrichment, which has no spliced gate today).

**Current shape (Code node, single output, drops refused rows):**
```python
def _write_gate_js(action: str) -> str:
    return WRITE_SAFETY_GATE_JS + (
        "\nreturn $input.all().filter((it) => _writeSafetyAllows(\n"
        f"  {action!r},\n"
        "  it.json.hs_object_id || ... || null,\n"
        "  ... domain fallback ladder (BUG 27) ...\n"
        "));\n"
    )

def splice_write_gates(nodes, conns, gated):
    by_name = {n["name"]: n for n in nodes}
    for write_name, action in gated.items():
        target = by_name.get(write_name)
        gate_name = f"{write_name} Write Gate"
        nodes.append(code_node(gate_name, _write_gate_js(action), gx, gy))
        # re-point every inbound edge targeting write_name to gate_name instead
        conns[gate_name] = {"main": [[{"node": write_name, "type": "main", "index": 0}]]}
    return nodes, conns
```
**What changes under D-70-12/14:** `_write_gate_js` must read ONLY the canonical
`write_request: {action, hs_object_id, domain, email}` shape (delete the fallback ladder —
the multi-line `||` chain visible above is precisely BUG 27's fix, being retired per D-70-12,
not extended). The gate node itself must become (or be immediately followed by) an
`n8n-nodes-base.if` node — RESEARCH.md states plainly: "A Code node has exactly ONE
output... this is the concrete reason D-70-14's IF-shaped gate cannot be a Code node." So
this is: keep the Code-node computation of `_writeSafetyAllows(...)` (unchanged predicate,
SAFE-01..05), but instead of `.filter()`-dropping, stamp a boolean/verdict field onto every
item and route through a new `n8n-nodes-base.if` node whose condition reads that field — true
lane to the write node, false lane emits `{action: "write_blocked", reason: ...}` (D-70-14)
into the SAME Merge input the write node's own response feeds (D-70-06).

**Enrichment lane has no analog to reshape — it needs a NEW gate.** RESEARCH.md's Pitfall 3:
the enrichment lane's check is inline inside `Decide Action`/`Decide Company Action`
(`WRITE_SAFETY_GATE_JS + DECIDE_CLOUD` concatenation at :957/:1730/:3635) with no spliced
node at all. Budget this as "extend `splice_write_gates`'s `gated` map to cover `HubSpot
Create`/`HubSpot Update`/`HubSpot Company Update`" — i.e., call the (reshaped)
`splice_write_gates` a 4th time from `build_enrichment_cloud`, removing the inline
`_writeSafetyAllows` call from `ENRICH_DECIDE_CLOUD`/`ENRICH_DECIDE_CO_CLOUD` so the
predicate has exactly one call site per D-70-13's "one home per lane."

**Analog for D-70-15 (one verdict covers update + its association):** the SAME
`splice_write_gates` mechanism, called with `HubSpot Update` and `HubSpot Associate Company`
sharing one gate node rather than two independent ones (RESEARCH.md confirms these are gated
independently today at L1086 — this is the one line to change: drop the second `gated` entry
for the association write, and instead route the association node off the SAME gate's
permitted-lane output, conditioned additionally on `company_id` having resolved).

---

### `operator-claude-plugin/scripts/watch.py` — generalize `recover_async_dispatch`

**Analog:** itself. This is a promote-don't-rewrite case.

```python
# Source: operator-claude-plugin/scripts/watch.py (read this session)
def find_executions_by_run_id(config, run_id, *, workflow_id=None, transport=requests.get, ...):
    # scans recent executions, matches on Parse HubSpot Event's own echoed run_id (exact match)
    ...

def _build_response_rows(execution) -> list:
    run_data = report._run_data(execution)
    if run_data is None:
        return []
    items = report.all_node_items(run_data, report_enrichment.BUILD_RESPONSE_NODE)
    return [item["json"] for item in items
            if isinstance(item, dict) and isinstance(item.get("json"), dict)]

def recover_async_dispatch(config, run_id, expected_chunk_count, *, workflow_id=None, ...):
    ...  # the ONE sanctioned bounded-poll site in the whole plugin
```
Under D-70-05, every sync-style caller that previously trusted the HTTP response body must
instead call THIS existing function (never build a second poll loop —
`test_report_sufficiency.py`'s AST guard, `_POLL_LOOP_ALLOWED = {"watch.py"}`, structurally
forbids it, see below). The generalization is: broaden `expected_chunk_count`/lane handling
so `enrich-records`' id-less spec forms (D-70-08a) and `scale_up` children (same `run_id`,
separate executions — `find_executions_by_run_id` must return all of them per §13.0.3) are
covered by the SAME function, not a sibling.

**Companion analog for D-70-06 (row outcome = write node's own output):**
`report.py::reconcile(ledger, run_data)` already implements this exact rule for the ingest
lane ("only report the success label when the write node actually produced output items...
downgrade to `not_confirmed`"). `report_enrichment.py::enrichment_row_ledger` is the parallel,
not-yet-shared twin for the enrichment lane — check whether `reconcile` can be reused (Phase
46 parity discipline) before writing a second copy.

---

### `operator-claude-plugin/scripts/chunking.py::dispatch_plan` — drop `async_ack`

**Analog:** itself, lines ~352-557. Removal pattern:
```python
def dispatch_plan(plan, providers, armed, config, transport=requests, *, run_id=None,
                   async_ack=False, scale_up=False, execution_ceiling=None):
    ...
    if async_ack:
        envelope["async_ack"] = True
    ...
    if not async_ack:
        ...  # old sync-body-trusting branch
```
Delete the `async_ack` parameter and both branches; every caller passing it is simply
stopped from passing it (D-70-07: "a caller that still passes it is ignored, not
rejected" — so consider accepting-and-ignoring the kwarg for one release rather than a hard
`TypeError`, matching that decision's tone, at Claude's discretion).

---

### `operator-claude-plugin/scripts/written_records.py::append_chunk` — writes only

**Analog:** itself, `append_chunk` (:474) + `classify_item` (:273) + the already-existing
`outcome_for_action` (:244, which maps `write_blocked` → GATED per RESEARCH.md). D-70-09
requires the CALL SITE in `chunking.dispatch_plan` to gate the `append_chunk` call on
`mode in ("write", "ingest")` — the function body itself needs no change; this is a
caller-discipline pattern, analog is "don't touch the ledger function, touch who calls it."

---

### `operator-claude-plugin/scripts/preingest.py::render_enriched_preview` — D-70-11

**Analog:** itself (:981) + `confidence.py::assess` (read-only per D-70-11: "the ONLY
per-row verdict"). Pattern: for each row, call `confidence.assess(row)` and render
`HELD <code> <reason>` or `SEND` (SEND only when CONFIDENT) — mirrors the existing
`_held_statement`/`_unanswered_statement` helper pair (:954, :967) already in this file for
summarizing counts; extend that pair's convention rather than inventing new prose helpers.

## Shared Patterns

### Bounded polling is a single sanctioned site
**Source:** `operator-claude-plugin/tests/test_report_sufficiency.py` (AST-based guard):
```python
"""...the AST-based no-poll-loop guard (D-07) that turns "this phase never grows a watch"
into a property the suite enforces rather than a promise the next plan can quietly break.
D-07 named exactly where the loop belongs once it was built: Phase 29's watch.py (29-04).
That module is the one deliberate exception to this guard..."""
import ast
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
```
**Apply to:** every migrated client site (`scheduled_arm.py`, `enrich-records`'
`dispatch_plan` call, the 5 repo scripts kept under D-70-08). None may add a `while`/`sleep`
loop of their own; all must call into `watch.py`'s existing functions. If a new file needs
to poll, it must be added to `watch.py` itself or the guard's exception set updated
deliberately (never silently).

### Whole-workflow post-pass before write
**Source:** `scripts/build_cloud_workflows.py::_normalize_hubspot_auth`, invoked from
`main()` immediately before each `json.dumps(...)`.
**Apply to:** the new by-name-read assertion AND the (optional, at Claude's discretion)
Merge-node "Always Output Data" stamping pass — both are whole-workflow mutations/checks
that belong in this exact insertion point, run once per variant (`_local`, `_cloud`,
`_local_live`), never duplicated per builder function.

### Splice-into-existing-connections mutation
**Source:** `scripts/build_cloud_workflows.py::splice_write_gates`.
**Apply to:** Merge-node insertion at every convergence point (D-70-01) — the exact same
"collect every inbound `conn` targeting node X, redirect it, wire the new node to X"
mutation, generalized from 1 upstream (today's gate) to N upstream (a Merge's inputs).

### Docstring convention for a builder-level structural fix
**Source:** `_hs_http_search_node`'s docstring (BUG number, live symptom, workaround
mechanism, migrating call sites) and `_normalize_hubspot_auth`'s (two numbered corrections,
each with its own live-failure citation).
**Apply to:** every new/reshaped builder function this phase adds — cite the relevant D-70-NN
decision and, where applicable, the F-number/execution-id evidence from
`.planning/debug/resolved/uat-batch-review-row-reads-failed.md`, matching this file's own
established citation discipline throughout.

## No Analog Found

None. Every file this phase touches has a direct, already-working in-repo analog — per
RESEARCH.md's own "Don't Hand-Roll" table: "almost every mechanism this phase needs already
exists somewhere in this repo in a partial or single-lane form... except for the Merge-node
insertion itself and the write-gate's IF-shaping, which are genuinely new to this codebase."
Those two ARE covered above via the closest available analogs (`code_node`, `splice_write_
gates`) with explicit notes on what must change rather than be copied verbatim.

## Metadata

**Analog search scope:** `scripts/build_cloud_workflows.py` (8778 lines, read via targeted
grep + sed ranges); `n8n/wf_enrichment_cloud.json` connections map (read via CONTEXT/RESEARCH
citations, not re-read here); `tests/n8n/*.test.mjs` (2 files read in full/near-full);
`operator-claude-plugin/scripts/{watch,chunking,written_records,preingest,dispatch}.py`
(function signatures + key snippets read); `operator-claude-plugin/tests/
test_report_sufficiency.py` (head read).
**Files scanned:** ~12 files directly; remainder characterized via 70-RESEARCH.md's own
`[VERIFIED: ... read this session]` citations (trusted as primary source per that document's
Sources section — HIGH confidence, read directly by the researcher this session).
**Pattern extraction date:** 2026-09-09
