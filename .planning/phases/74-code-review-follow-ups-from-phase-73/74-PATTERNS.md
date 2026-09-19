# Phase 74: Code-review follow-ups from phase 73 - Pattern Map

**Mapped:** 2026-09-19
**Files analyzed:** 17 (all modifications to existing files; no new source files this phase)
**Analogs found:** 17 / 17 — this phase is entirely edits-in-place, so for every file the
closest analog is a sibling mechanism already living in the SAME file (an existing sentinel
call site, an existing config-gate reader, an existing redaction test). No cross-file "find a
different file to copy from" search was needed — the research (`74-RESEARCH.md`) already
pinned every insertion point with line numbers and verbatim code. This document repackages
those into per-file pattern assignments for the planner.

**Read this before using the line numbers below:** `74-RESEARCH.md`'s own pitfall #1 warns line
numbers drift fast in `scripts/build_cloud_workflows.py` (13 same-day commits already shifted
anchors ~150-260 lines). Every excerpt below is tagged `[VERIFIED <date>]` from the research
session on 2026-09-19 — re-grep by function/constant name before editing, never trust the
number alone.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog (same-file sibling pattern) | Match Quality |
|---|---|---|---|---|
| `scripts/build_cloud_workflows.py` (Create Carry Merge splice) | config/build (n8n graph generator) | event-driven (graph-shape authoring) | `wire_gate_refusal_lane` / `_add_starved_lane_sentinel` call sites (same file, lines ~2119-2135) | exact |
| `n8n/code/pairCreateOutcome.js` | utility (pure classification function) | transform | its own existing `_isCarriedRow`/`_isSuccessResponse` shape-test ladder | exact |
| `tests/n8n/ingestCreateErrorLane.test.mjs` | test | event-driven (graph fidelity) | its own existing stub block (lines 79-99) | exact |
| `tests/n8n/lib/walkWorkflow.mjs` (`propagate`) | utility (offline engine model) | transform | its own `alwaysOutputData` branch (line ~520) | exact |
| `tests/n8n/walkerEngineFidelityV1.test.mjs` (new case) | test | event-driven (fidelity pinning) | `v1RuntimeRecordings.test.mjs`'s existing pinned-execution pattern | exact |
| `scripts/freeze_execution_rundata.py` | utility (CLI, read-only GET+redact+write) | file-I/O / transform | its own `_redact_headers` function (lines 80-97) | exact |
| `tests/n8n/fixtures/frozen/*.json` (7 files, re-redact) | config (data fixture) | batch | `tests/n8n/v1RuntimeRecordings.test.mjs`'s existing secret-refusal assertion (lines 22-31) | exact |
| new guard test over `tests/n8n/fixtures/frozen/` | test | batch | `v1RuntimeRecordings.test.mjs`'s secret-refusal test — generalize, don't duplicate | exact |
| `CLAUDE.md` §13.0.3 (new row) | config (living doc) | — | the existing "A node fed zero items does not run at all" row's two-tag convention | exact |
| `operator-claude-plugin/scripts/written_records.py` | model (outcome-mapping table) | transform | `ACTION_TO_OUTCOME`'s existing `create_failed` entry (line ~184) | exact |
| `operator-claude-plugin/scripts/write_grant.py` | service (grant-preview builder) | transform | its own `executions_basis`/`EXECUTIONS_BASIS` block (lines 546-740) | exact |
| `operator-claude-plugin/scripts/report_enrichment.py` | service | batch | its own `_ACTION_LANE_ORDER`/`ledger_by_id` loop (lines 103-228) | exact |
| `operator-claude-plugin/scripts/chunking.py` | service (dispatch/recovery orchestration) | batch | its own `dispatch_and_recover` discarded-binding site (line 674) + `resolve_bound_seconds` (line 97-108) | exact |
| `operator-claude-plugin/scripts/review_decision.py` | service | transform | its own `_as_hubspot_text`/leg1 comparison (lines 366, 496-504) | exact |
| `operator-claude-plugin/scripts/csv_dedupe.py` | utility (CRUD-like row transform) | transform / file-I/O | its own `_canonical_rows` zip bug (line 41) + `preview.py`'s config-gate `__main__` pattern (cross-file) | role-match (config-gate part) |
| `operator-claude-plugin/scripts/preview.py` | service | file-I/O | its own `collapse_block`/`--collapsed` arg handling (lines 141, 254-268) | exact |
| Python test files (`test_write_grant.py`, `test_written_records.py`, `test_csv_dedupe.py`, `test_review_decision.py`, `pairCreateOutcome.test.mjs`) | test | — | each file's own existing test-case shape for the function under fix | exact |

## Pattern Assignments

### `scripts/build_cloud_workflows.py` — D-74-01, D-74-02, D-74-06, WR-10 (builder, config/build role, event-driven graph authoring)

**Analog:** the file's own `wire_gate_refusal_lane` call sites and `_add_starved_lane_sentinel`
definition — this file is both source and analog; every new splice must reuse these exact
helpers, never hand-wire a Code node.

**Current create-lane splice** (verified `[VERIFIED 2026-09-19]`, re-grep before editing —
anchors shift):
```python
# scripts/build_cloud_workflows.py:2228-2229 (as of 2026-09-19)
_append_merge_input(nodes, conns, "Create Carry Merge", "HubSpot Create", source_out_idx=1)
set_always_output_data(nodes, ["HubSpot Create"])
```
D-74-01 replaces the direct `HubSpot Create` (out 1) → `Create Carry Merge` input 2 edge with a
new Code node in between that stamps unconditionally (marker-or-error-items), retiring the
`set_always_output_data(nodes, ["HubSpot Create"])` call for this edge.

**Sentinel pattern to copy** (`_add_starved_lane_sentinel` — D-74-02's template):
```python
# scripts/build_cloud_workflows.py:10732-10774 — signature
def _add_starved_lane_sentinel(nodes, conns, name, source, condition_js, targets, x, y, *,
                                source_out_idx=0):
    ...

# scripts/build_cloud_workflows.py:2119-2124 — call-site idiom to copy verbatim
_add_starved_lane_sentinel(
    nodes, conns, "Associate Lane Sentinel", "Decide Action",
    WRITE_SAFETY_GATE_JS + associate_sentinel_js,
    [(ingest_merge_response, assoc_carry_idx)], 60, 1020)

# scripts/build_cloud_workflows.py:2130-2135 — condition-js idiom
unreached_condition_js=(
    'if (rows.length > 0 && !rows.some((r) => r.action === '
    f'"{_routed_action}")) return [{{}}]; return [];'),
```
D-74-02's new sentinel: source `"Decide Action"`, condition
`'if (rows.length > 0 && !rows.some((r) => r.action === "create")) return [{}]; return [];'`,
target `Ingest Merge Response` input derived from `_append_merge_input`'s return value
(`scripts/build_cloud_workflows.py:2243` currently discards it — capture instead of
hardcoding `5`).

**`BUILD_INGEST_RESPONSE` join pattern (D-74-06)** — mirror the existing `failed`/`failedByEmail`
email-keyed join, not a fresh lookup on the decided snapshot:
```python
# scripts/build_cloud_workflows.py:922-931
const failed = allItems.filter((row) =>
  row._decided_snapshot !== true && row.action === "create_failed");
const failedByEmail = {};
for (const row of failed) {
  if (row.email) failedByEmail[String(row.email).toLowerCase()] = row;
}
```
Add an analogous `unconfirmed`/`unconfByEmail` block filtering `create_outcome === "none" ||
create_outcome === "refused"`, then extend the ternary at
`scripts/build_cloud_workflows.py:962` (`fail ? "create_failed" : (block ? "write_blocked" :
row.action)`) with a third `create_unconfirmed` branch, passing `create_outcome_reason`
through verbatim (D-74-06's operator-facing requirement).

**WR-10** — `extract_js_const` at `scripts/build_cloud_workflows.py:173`; unrelated
build-time-constant-extraction fix, land in the same regeneration wave purely to save a diff
cycle on this heavily-edited file.

**Index-derivation rule (Don't Hand-Roll):**
```
# Never hardcode a merge input index. Either:
idx = _append_merge_input(nodes, conns, ingest_merge_response, "Build Create Failure Row")
# and pass idx to the sentinel target, or use:
_merge_input_index(conns, "Build Create Failure Row", ingest_merge_response)
```

---

### `n8n/code/pairCreateOutcome.js` — D-74-04 (utility, transform role)

**Analog:** the file's own existing shape-test functions, which the new stamp check is
inserted AHEAD of, not merged into:
```javascript
// n8n/code/pairCreateOutcome.js — current classification ladder [VERIFIED 2026-09-19]
function _isCarriedRow(row) {
  return typeof (row && row.action) === "string" && row.action.length > 0;
}
function _isSuccessResponse(row) {
  return Boolean(row) && row.id !== undefined && row.id !== null && row.id !== "";
}
for (const row of items || []) {
  if (!row) continue;
  if (_isCarriedRow(row)) carried.push(row);
  else if (_isSuccessResponse(row)) responses.push({ row, outcome: "success" });
  else responses.push({ row, outcome: "error" });
}
```
D-74-04 inserts `if (row._create_error === true) { responses.push({row, outcome: "error"});
continue; }` as the FIRST test in this loop, ahead of `_isCarriedRow`. Per Pitfall 5: the stamp
must be written by a graph-topology-aware Code node on the error edge (D-74-01's producer, or a
sibling node), never inferred inside this pure function from item shape.

---

### `tests/n8n/ingestCreateErrorLane.test.mjs` — D-74-05 (test)

**Analog:** its own existing stub (lines 79-99), kept and annotated, not replaced:
```javascript
// tests/n8n/ingestCreateErrorLane.test.mjs:79-99 [VERIFIED 2026-09-19]
"HubSpot Create": {
  success: [ {id: CREATED_1, properties: {email: EMAIL_1}}, {id: CREATED_3, properties: {email: EMAIL_3}} ],
  error: [ {
    message: "Contact already exists. Existing ID: 555",
    properties: { email: EMAIL_2 },
    request: { headers: { Authorization: "Bearer super-secret-token" } },
  } ],
}
```
D-74-05 tags this with the `UNOBSERVED` comment register `walkWorkflow.mjs` already uses for
D-70-30 rule (c):
```javascript
// UNOBSERVED (D-74-05): this error item's `properties.email` shape is INVENTED, not
// pinned by any frozen runData. Real n8n HTTP error-item shape for a continueErrorOutput
// node is still [documented] only (D-73-19) — see CLAUDE.md §13.0.3. The `_create_error`
// stamp (D-74-04) is what makes this test's correctness independent of the guess.
```
Add a case stripping `properties.email` from the stub and asserting the row still classifies
as `create_failed` via the stamp alone — the regression D-74-04 exists to prevent.

---

### `tests/n8n/lib/walkWorkflow.mjs` — D-74-03 (utility, offline engine model)

**Analog:** the function's own `outputIndex` parameter, already threaded but unused in the
guard condition:
```javascript
// tests/n8n/lib/walkWorkflow.mjs:512-520 [VERIFIED 2026-09-19]
function propagate(fromName, outputIndex, items) {
  const node = nodesByName[fromName];
  let outItems = items;
  if (outItems.length === 0 && node && node.alwaysOutputData === true) {
    outItems = [{}];
  }
```
One-line fix: `&& outputIndex === 0` appended to the condition. Call site already passes
`idx`:
```javascript
// tests/n8n/lib/walkWorkflow.mjs:796
result.outputs.forEach((branchItems, idx) => propagate(node.name, idx, branchItems));
```
**WR-08 rides along in the same edit** — the stale JSDoc at lines ~351-357 (vs the real
contract demonstrated at lines 302-326: a plain-array stub on a `continueErrorOutput` node
yields `{success: raw, error: []}`) gets corrected in the same commit.

---

### `tests/n8n/walkerEngineFidelityV1.test.mjs` family — D-74-03(b), D-74-12 (test)

**Analog:** `tests/n8n/v1RuntimeRecordings.test.mjs`'s existing pinned-execution pattern
(reads `exec_1235{4..8}.runData.json`, asserts specific node-run shapes). Add a sibling case
reading `tests/n8n/fixtures/frozen/exec_12522.runData.json` once frozen, asserting the
`propagate` fix pads output 0 only. D-74-12's search is a standalone script, not a test:
```python
# mechanical check, per 74-RESEARCH.md
import json
d = json.load(open("tests/n8n/fixtures/frozen/exec_12522.runData.json"))
for name, runs in d["runData"].items():
    if len(runs) > 1 and "Merge" in name:
        print(name, len(runs))
```
Never close the folded todo on a `resolves_phase` match alone — if the search finds nothing,
keep it open with its trigger and say so in the SUMMARY (per D-74-12 and CLAUDE.md §31 rule 2).

---

### `scripts/freeze_execution_rundata.py` — D-74-07 (utility, file-I/O CLI)

**Analog:** its own narrow `_redact_headers` function, being widened in place:
```python
# scripts/freeze_execution_rundata.py:80-97 [VERIFIED 2026-09-19] — current narrow scrub
def _redact_headers(run_data: dict) -> dict:
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
D-74-07 replaces this with a non-enumerating `_scrub(run)` walking every dict key at every
depth of the WHOLE `run` dict (not just `run["data"]["main"]`) against a `_SENSITIVE_KEYS =
("headers", "error", "request", "options", "config")` tuple — catching `run["error"]`, the gap
CR-04 names. Call sites to redirect: `build_full_fixture`/`build_excerpt` at lines 106-150,
both currently call `_redact_headers(_run_data_of(execution))` — drop-in replacement.

---

### `tests/n8n/fixtures/frozen/*.json` (7 files) — D-74-08 (config/data fixture, batch)

**Analog:** `v1RuntimeRecordings.test.mjs`'s existing secret-refusal test, the precedent
pattern D-74-09's new guard generalizes:
```javascript
// tests/n8n/v1RuntimeRecordings.test.mjs:22-31 [VERIFIED 2026-09-19]
test("frozen recordings carry no live secret — webhook request headers are redacted", () => {
  for (const m of raw.matchAll(/"x-enrichment-secret":\s*"([^"]*)"/g)) {
    assert.equal(m[1], "<redacted>", `${id}: x-enrichment-secret must be redacted`);
  }
  assert.doesNotMatch(raw, /"x-real-ip":\s*"(?!<redacted>)/, ...);
});
```
Five fixtures (`exec_1235{4,5,6,7,8}.runData.json`) already carry the SAFE placeholder string
for `x-enrichment-secret` — no data change needed, only confirm D-74-09's guard doesn't
false-positive on the key name. Two fixtures (`exec_12434.runData.json`,
`exec_12449.runData.json`) carry LIVE unredacted JWTs — re-run through the D-74-07-widened
scrubber and commit the rewritten bytes. **Order matters: D-74-07 before D-74-08 before
D-74-09**, or the new guard fails immediately on the still-unredacted JWTs.

**Regression guard (Pitfall 4):** re-run
`.venv/bin/python -m pytest operator-claude-plugin/tests/test_run_report_enrich_account.py -v`
immediately after re-redacting — this test reads both JWT-carrying fixtures for its own
reconciliation assertions on unrelated node outputs (`Decide Company Action`, `Build
Response`).

---

### New guard test over `tests/n8n/fixtures/frozen/` — D-74-09 (test)

**Analog:** same `v1RuntimeRecordings.test.mjs` pattern above, generalized repo-wide instead
of 5 named files. Refuses VALUE shapes only, never key names:
```
patterns to refuse (value shapes, not key names):
  /pat-na\d-.../               (HubSpot private-app token)
  /Bearer\s+\S+/               (bearer auth header VALUE)
  /"x-enrichment-secret":\s*"(?!<redacted>)/   (value present, not the placeholder)
  /eyJ[A-Za-z0-9_-]{20,}/       (JWT body)
```
Must NOT trip on the header NAME string appearing inside node jsCode bodies (present in the 4
frozen workflow-body fixtures) — test against fixture files carrying runData, distinguish from
workflow-definition fixtures if both live under the same directory.

---

### `CLAUDE.md` §13.0.3 — D-74-03 third sub-task (living doc)

**Analog:** the existing "A node fed zero items does not run at all" row's two-tag format —
copy its exact shape:
```
| **A node fed zero items does not run at all, and so contributes no delivery to anything it
feeds.** First demonstrated with an HTTP node at Gate 1 (`12200`); the SAME rule, in Code/NoOp
gate form, was only first observed at Gate 3/70-05-A (`12203`, `12206`) — recorded separately
rather than assumed identical in every node type until each was actually seen. | `[documented]`
(HTTP form: `12200`...) + `[observed live]` (Code/NoOp gate form: `12203`, `12206`) |
```
New row: `[documented]` citing `packages/core/src/execution-engine/workflow-execute.ts`'s
`ensureAlwaysOutputData` symbol (file+symbol only — this repo can't read that file) PLUS
`[observed live]` citing execution `12522` once frozen (`HubSpot Create` outs `[21, 0]`, input
2 never delivered directly, association landed via the v1 end-of-run drain instead).

---

### `operator-claude-plugin/scripts/written_records.py` — D-74-06 (model, transform)

**Analog:** the existing `ACTION_TO_OUTCOME` table's `create_failed` entry — same file, same
dict, add one key:
```python
# operator-claude-plugin/scripts/written_records.py:184-201 [VERIFIED 2026-09-19]
ACTION_TO_OUTCOME = {
    "write_blocked": GATED,
    "review": HELD,
    "needs_match_review": HELD,
    "research_failed": FAILED,
    "recompute_refused": FAILED,
    "skip": NO_ACTION,
    "proposed": NO_ACTION,
    "list_expansion_refused": FAILED,
    # ... "create_failed": FAILED exists further down; add "create_unconfirmed": FAILED beside it
```
`ALL_OUTCOMES` frozenset (line 150-153) already contains `FAILED` — no new outcome constant
needed.

---

### `operator-claude-plugin/scripts/write_grant.py` — WR-01, WR-02

**Analog:** the file's own `executions_basis`/`EXECUTIONS_BASIS` block:
```python
# operator-claude-plugin/scripts/write_grant.py — anchors [VERIFIED 2026-09-19]
# :574  executions = 1  (contact-upload hardcode, inside the try that opened ~:552)
# :180  EXECUTIONS_BASIS constant; used unconditionally at :639
#       "executions_projection_basis": EXECUTIONS_BASIS,
# :735  unconditional chunk_count/chunk_ceiling render line
```
Fix: hoist the lane-invariant `executions = 1` out of the `try` (WR-01); make
`executions_projection_basis` and `providers` per-lane, taken from the estimate (WR-02), per
the roadmap's stated shape (D-74-10 / CONTEXT §Warnings). First check
`grep -n "contact.upload\|COST_LANE_CONTACT_UPLOAD" operator-claude-plugin/tests/test_write_grant.py`
to see whether the missing-ceiling case is already scaffolded (Open Question 1 in RESEARCH).

---

### `operator-claude-plugin/scripts/report_enrichment.py` — WR-05

**Analog:** own `_ACTION_LANE_ORDER`/`ledger_by_id` loop:
```python
# operator-claude-plugin/scripts/report_enrichment.py — anchors [VERIFIED 2026-09-19]
# :103  _ACTION_LANE_ORDER
# :197  backfill_missing_identity
# :219  ledger_by_id = {}
# :221-228  for _lane, node_name in _ACTION_LANE_ORDER: ... ledger_by_id[str(ledger_id)] = ledger_json
#           (last-lane-wins, unguarded — the bug)
```
Fix: key the ledger by `(lane, id)` instead of `id` alone, so ambiguous ids across lanes don't
silently overwrite — skip (don't merge) on ambiguity, per CONTEXT's stated shape.

---

### `operator-claude-plugin/scripts/chunking.py` — WR-06, D-74-13

**Analog:** own `dispatch_and_recover` discarded binding, and own `resolve_bound_seconds`:
```python
# operator-claude-plugin/scripts/chunking.py — anchors [VERIFIED 2026-09-19]
# :596  dispatch_and_recover
# :674  write_records_rows, _excluded_marker_count = (...)   <- discarded, the bug
# :696  "written_records_failures": written_records_failures,   <- no excluded_marker_count key
# :97-108  resolve_bound_seconds(config, record_count) — already reads config override
#          `watch_bound_seconds` if present
# :60  CEILING_KEY = "max_records_per_chunk"
# :209-220  chunk_ceiling(config, key=CEILING_KEY)
```
WR-06 fix: stop discarding `_excluded_marker_count`, return it in the dict, surface/report when
non-zero (D-74-10's stated shape). D-74-13 fix: confirm `watch_bound_seconds` is exposed as a
real operator-facing config knob (may already be half-done per Assumption A3); add a test
against stress-attempt-3's aggregate 17/48-unchecked figure; no live re-run this phase.

---

### `operator-claude-plugin/scripts/review_decision.py` — WR-09

**Analog:** own `_as_hubspot_text`/leg1-comparison block:
```python
# operator-claude-plugin/scripts/review_decision.py:366, 496-504 [VERIFIED 2026-09-19]
leg1_keys = ...
intent_mismatched = [key for key in leg1_keys if
    _as_hubspot_text(would_write.get(key)) != _as_hubspot_text(intended.get(key))]
```
Fix: distinguish absence from presence-with-different-value in the comparison (the review's
own proposed fix — WR-09's exact shape). File was touched 2026-09-18 by an unrelated boolean
fix (`b95e38b2`) — confirmed this block untouched.

---

### `operator-claude-plugin/scripts/csv_dedupe.py` — WR-03, WR-11, WR-12

**Analog:** own `_canonical_rows` (zip-truncation bug) and `apply_dedupe`; cross-file analog
`preview.py`'s config-gate `__main__` resolution for WR-03:
```python
# operator-claude-plugin/scripts/csv_dedupe.py — anchors [VERIFIED 2026-09-19]
# :41   _canonical_rows — zips raw, unpadded (WR-11's bug)
# :101  apply_dedupe
# :114, :121  out_path/report_path — stem-only construction (WR-12's bug)
# :133  __main__ block
# :147, :149  propose_dedupe/apply_dedupe calls — no mapping_path passed (WR-03's bug)
```
WR-11 fix: pad short rows (`row[i] if i < len(row) else ""`) instead of `zip`-truncating.
WR-12 fix: construct `out_path`/`report_path` from the full path, not stem-only. WR-03 fix:
mirror `preview.py`'s own `config_gate.load_config().get("column_mapping_path")` resolution —
**do not build a third independent resolver**; this is the exact drift WR-03 itself flags.

---

### `operator-claude-plugin/scripts/preview.py` — WR-04

**Analog:** own `collapse_block`/`--collapsed` handling, and own config-gate `__main__`
pattern (the thing `csv_dedupe.py` above should mirror for WR-03):
```python
# operator-claude-plugin/scripts/preview.py — anchors [VERIFIED 2026-09-19]
# :141       collapse_block
# :254-257   --collapsed arg parse
# :268+      _collapsed = json.loads(Path(_collapsed_arg_path).read_text(...))  # wrapped in a
#            broad except per the review — confirm exact try/except shape before editing
```
WR-04 fix: narrow the broad `except` to the specific failure modes the review names, so a
genuine parse error isn't silently swallowed into `None`.

## Shared Patterns

### Never hardcode a Merge input index
**Source:** `scripts/build_cloud_workflows.py`'s `_merge_input_index` / `_append_merge_input`
return value, and the `mirror_index` docstring's own rationale ("derived, never hand-listed").
**Apply to:** D-74-02's new sentinel target index.

### Sentinel-gated starved-lane producer, never a bare structural hope
**Source:** `_add_starved_lane_sentinel` (`scripts/build_cloud_workflows.py:10732`).
**Apply to:** D-74-01 (real producer node) and D-74-02 (gated sentinel) — both must use this
existing mechanism, never a hand-wired Code node or a reliance on `alwaysOutputData` alone.

### Non-enumerating, wholesale redaction over key-by-key allowlists
**Source:** `scripts/freeze_execution_rundata.py`'s own docstring rationale;
`BUILD_CREATE_FAILURE_ROW_JS`'s "read at most 2-3 named scalar fields, never serialize the
whole object" idiom (CLAUDE.md §13.0.1's `T-73-06-01` threat item).
**Apply to:** D-74-07 (scrubber widening), D-74-09 (guard test), and D-74-04's stamp reading
(read only the boolean stamp, never re-serialize the raw error object into a fixture or log).

### Config-gate resolution, one canonical reader
**Source:** `preview.py`'s `config_gate.load_config().get("column_mapping_path")` pattern.
**Apply to:** WR-03's fix in `csv_dedupe.py` — mirror, don't reinvent.

### `UNOBSERVED` / `[documented]` vs `[observed live]` tagging discipline
**Source:** `walkWorkflow.mjs`'s D-70-30 rule (c) register; CLAUDE.md §13.0.3's own two-tag
convention.
**Apply to:** D-74-03 (CLAUDE.md row, fidelity test), D-74-05 (test stub comment).

## No Analog Found

None — every file in this phase's scope is an edit-in-place with a same-file or clearly-cited
cross-file sibling pattern already identified in `74-RESEARCH.md`.

## Metadata

**Analog search scope:** `scripts/build_cloud_workflows.py`, `n8n/code/pairCreateOutcome.js`,
`tests/n8n/lib/walkWorkflow.mjs`, `tests/n8n/*.test.mjs`, `scripts/freeze_execution_rundata.py`,
`tests/n8n/fixtures/frozen/`, `operator-claude-plugin/scripts/*.py`, `CLAUDE.md` — all searched
via `74-RESEARCH.md`'s own direct-read session (this pass performed no additional Read/Grep
beyond confirming the research's file list, since every insertion point was already verified
with line numbers and verbatim excerpts this same day).
**Files scanned:** 17 target files + their cited analog siblings (all within the same files).
**Pattern extraction date:** 2026-09-19
