---
phase: 73-ga-fix-list-from-stress-attempt-2
reviewed: 2026-09-18T00:00:00Z
depth: standard
files_reviewed: 47
files_reviewed_list:
  - n8n/code/pairCreateOutcome.js
  - n8n/code/reviewApply.js
  - operator-claude-plugin/.claude-plugin/plugin.json
  - operator-claude-plugin/CHANGELOG.md
  - operator-claude-plugin/scripts/chunking.py
  - operator-claude-plugin/scripts/company_domain.py
  - operator-claude-plugin/scripts/csv_dedupe.py
  - operator-claude-plugin/scripts/preview.py
  - operator-claude-plugin/scripts/report_enrichment.py
  - operator-claude-plugin/scripts/review_decision.py
  - operator-claude-plugin/scripts/write_grant.py
  - operator-claude-plugin/scripts/written_records.py
  - operator-claude-plugin/skills/contact-upload/SKILL.md
  - operator-claude-plugin/skills/enrich-before-ingest/SKILL.md
  - operator-claude-plugin/skills/enrich-records/SKILL.md
  - operator-claude-plugin/tests/conftest.py
  - operator-claude-plugin/tests/test_company_extraction.py
  - operator-claude-plugin/tests/test_cost_guard.py
  - operator-claude-plugin/tests/test_csv_dedupe.py
  - operator-claude-plugin/tests/test_enrich_before_ingest_skill_contract.py
  - operator-claude-plugin/tests/test_review_decision.py
  - operator-claude-plugin/tests/test_run_manifest.py
  - operator-claude-plugin/tests/test_run_report_enrich_account.py
  - operator-claude-plugin/tests/test_skill_sequence_coverage.py
  - operator-claude-plugin/tests/test_write_grant.py
  - operator-claude-plugin/tests/test_written_records.py
  - scripts/build_cloud_workflows.py
  - scripts/freeze_execution_rundata.py
  - tests/n8n/backendStatusCredits.test.mjs
  - tests/n8n/companyDomainVariants.test.mjs
  - tests/n8n/companyFreemailRefusal.test.mjs
  - tests/n8n/companyNameOnlyOutcome.test.mjs
  - tests/n8n/ingestCarryMerge.test.mjs
  - tests/n8n/ingestCreateErrorLane.test.mjs
  - tests/n8n/ingestSearchThrottle.test.mjs
  - tests/n8n/lib/walkWorkflow.mjs
  - tests/n8n/pairCreateOutcome.test.mjs
  - tests/n8n/researchErrorGateFlow.test.mjs
  - tests/n8n/reviewDecisionEndpoint.test.mjs
  - tests/n8n/reviewLoop.test.mjs
  - tests/n8n/walkerHttpErrorOutput.test.mjs
  - tests/test_backend_status_workflow.py
  - tests/test_bug10_company_search_transport.py
  - tests/test_cloud_write_path.py
  - tests/test_merge_helpers.py
findings:
  critical: 4
  warning: 12
  info: 0
  total: 16
status: issues_found
---

# Phase 73: Code Review Report

**Reviewed:** 2026-09-18
**Depth:** standard
**Files Reviewed:** 47
**Status:** issues_found

## Summary

Reviewed the Phase 73 GA fix list plus the two 2026-09-18 quick tasks (260918-322 review-verify
normaliser + `reviewApply.js` boolean stringify; 260918-32u `Build Research Failure Response`
sentinel). Generated `n8n/wf_*.json` and frozen runData fixtures were out of scope; the
`scripts/build_cloud_workflows.py` review was scoped to the hunks in
`git diff a662ec7^..HEAD`.

Both suites are green (`node --test tests/n8n/*.test.mjs` 1218/1218;
`pytest operator-claude-plugin/tests` 3109 passed, 5 skipped). That is not evidence of
correctness here, because the highest-severity findings below are cases where the offline
test suite encodes the *same* unverified assumption as the code it exercises.

The concentration of risk is the new **create-error lane** (Plan 06, D-73-01, F-A6). It is
built on two engine behaviours that no execution in this repo has ever observed, and CLAUDE.md
§13.0.1 itself records the lane as `[documented]` only. Both assumptions are load-bearing, both
are contradicted by the nearest in-repo evidence, and if either is wrong the failure is silent:
one loses the company association on *every ordinary batch*, the other records a contact HubSpot
rejected as `created_id_unknown` in the durable ledger.

Secondary clusters: a redaction tool that misses the exact credential path the same phase's own
threat model names; and the new `cost_lane="contact-upload"` pricing path, whose operator-facing
consent disclosure now states a basis that contradicts its own number (reproduced empirically).

Not defects (checked and cleared): `plugin.json` 0.50.1 matches the CHANGELOG's top entry; there
is no `src/` Python oracle for `reviewApply.js`, so the Phase 46 parity rule does not bind the
boolean-stringify change; `_hs_http_create_node` correctly refuses to accept
`continueRegularOutput` (BUG 11 intact); `FREEMAIL_DOMAINS` has no name collision with any
module inlined into `ENRICH_DECIDE_CO_CLOUD`; the freemail create refusal (`action: "review"`)
falls through both companies routing IFs to the response and never reaches a write node with a
null id; an email-less row can never reach `action: "create"` on the ingest lane
(`resolveIdentity.js:59` — "a valid email is the ONLY route to net_new").

## Critical Issues

### CR-01: `alwaysOutputData` is assumed to pad an HTTP node's ERROR output; nothing in this repo has ever observed that, and the same diff's sibling use pads output 0

**File:** `scripts/build_cloud_workflows.py:1993` (and its justifying comment at `:1956-1992`); model at `tests/n8n/lib/walkWorkflow.mjs:520-522`
**Severity:** BLOCKER

**Issue:**
`set_always_output_data(nodes, ["HubSpot Create"])` is the fix the comment block relies on to
keep `Create Carry Merge` *normally-completing* rather than drain-only on the common
zero-rejection batch. The comment states it "makes `HubSpot Create`'s OWN sole error-output edge
deliver an empty marker whenever the branch would otherwise be silent."

That requires n8n to pad output index **1**. Every other `alwaysOutputData` use in this
repository pads index **0**:

- `:1933` — `Set Review`, `HubSpot Associate Company`: single-output nodes.
- `:8693` — `IF Research Errored`, whose own quick-task comment (added in *this same diff*,
  `:7587-7594`) says: *"n8n's ensureAlwaysOutputData then pushes one literal `{}` down this TRUE
  branch"* — TRUE is output 0, and that is the branch that is empty in the case it describes.

On a zero-rejection batch `HubSpot Create`'s output 0 is **non-empty** (the successes) and output
1 is empty. If n8n's `ensureAlwaysOutputData` pads `nodeSuccessData[0]` only — which the
builder's own docstring at `:10150` cites as the mechanism, without naming an index — then no
marker is emitted, `Create Carry Merge` never receives on input 2, and it becomes drain-only.
The commit's own comment (`:1960-1973`) already documents exactly what happens next: `Build
Association Request Merge` drains early on its always-immediate Update-lane sentinel, the later
real Create-side delivery opens a second undrainable pending run, and **the association is
silently lost** — on every ordinary ingest batch, not an exotic one.

The offline suite cannot detect this. `walkWorkflow.mjs`'s `propagate()` applies the AOD
substitution **per outgoing branch** (`if (outItems.length === 0 && node.alwaysOutputData === true)`),
so it pads output 1 by construction. The walker's own evidence note for that rule cites execution
`12200`, which is a *negative* observation (a node that never ran contributed nothing) and says
nothing about which output index gets padded.

**Fix:** Do not ship this on the strength of the walker. Either:
1. Read `packages/core/src/execution-engine/workflow-execute.ts`'s `ensureAlwaysOutputData` and
   confirm whether the empty-item push is written against `nodeSuccessData[0]` or against every
   output branch; record the answer in CLAUDE.md §13.0.3 as `[documented]` with the file+symbol,
   as that table's own convention requires. **Then** confirm it live with one disarmed
   zero-rejection ingest send and freeze the runData, upgrading to `[observed live]`; or
2. Replace the mechanism with one that does not depend on the answer. The shape-independent
   option is to stop requiring the error branch to deliver at all: give `Create Carry Merge` two
   declared inputs again and route the error branch through a Code node that emits a sentinel
   marker unconditionally per run — i.e. a real producer on that input, rather than an engine
   flag believed to synthesise one.

Until one of those lands, `walkWorkflow.mjs:520` should carry an explicit `UNOBSERVED` tag naming
the index question, in the same register the file already uses for D-70-30 rule (c).

---

### CR-02: `pairCreateOutcome`'s shape classification depends on an invented n8n error-item shape; both realistic shapes defeat it, and the durable ledger then records a rejected contact as created

**File:** `n8n/code/pairCreateOutcome.js:69-75, 94-143`; test that encodes the assumed shape at `tests/n8n/ingestCreateErrorLane.test.mjs:88-99`
**Severity:** BLOCKER

**Issue:**
Classification is by shape (module header, lines 15-23): an item with a non-empty string `action`
is a carried row; an item with an `id` is a success; **everything else is an error item**. The
join then needs `identityKey(errorItem)` to resolve, or the error is dropped
(`:112-117` — `if (key === null) continue;`).

The only place the real error-item shape is pinned is the test stub, which was written by hand:

```js
"HubSpot Create": { error: [{ message: "...", properties: { email: EMAIL_2 }, request: {...} }] }
```

No frozen runData, no live execution, and no citation to n8n source backs that shape. The two
realistic alternatives both defeat the design:

- **(a) the error item is `{ error: ... }` only.** `identityKey` returns `null`, the error never
  enters `responsesByKey`, and the carried row falls to `matches.length === 0` →
  `create_outcome: "none"` (`:130-132`). `Build Create Failure Row` filters on
  `create_outcome === "error"`, finds none, and emits its sentinel. **No `create_failed` row is
  ever produced.**
- **(b) n8n passes the input item through on the error output (its documented
  continue-on-fail behaviour) with `error` attached.** The item feeding `HubSpot Create` is
  `{...row, write_allowed: true}` from `HubSpot Create Write Gate`, and that row carries
  `action: "create"` (verified against the committed `wf_contact_ingest_cloud.json`:
  `HubSpot Create Write Gate IF` is a pass-through IF). `_isCarriedRow()` therefore returns
  **true** — the error item is classified as a *second carried row* with the same identity key,
  and `:125-128` refuses **both** with `create_outcome: "refused"`. Again no `create_failed` row.

In either case the rejected contact reaches `Build Ingest Response` with its original
`action: "create"` and a null id, and `written_records.classify_item` resolves it to
`created_id_unknown` (verified:
`classify_item({"action": "create", "hs_object_id": None})` → `outcome: 'created_id_unknown'`).
The durable end-of-run ledger therefore reports a contact HubSpot **refused** as "created, id
unknown" — a worse outcome than the 409 that aborted the batch before this change, because it is
silent.

**Fix:**
1. Establish the real shape before relying on it: run one disarmed create against a known-duplicate
   email, freeze the execution with `scripts/freeze_execution_rundata.py`, and rebuild the test
   stub from that fixture rather than from a hand-written literal. Record the shape in
   CLAUDE.md §13.0.3.
2. Independently of the answer, make classification explicit instead of structural. The error
   branch is the *only* producer on `Create Carry Merge` input 2 — stamp it there:
   ```python
   # a one-line Code node on the error edge, before the merge
   return $input.all().map((it) => ({ json: { ...it.json, _create_error: true } }));
   ```
   and have `pairCreateOutcome` test `_create_error === true` first, ahead of `_isCarriedRow`.
   That removes the dependency on whether the error item happens to carry `action`.
3. Apply CR-03's guard so that, whatever the shape turns out to be, an unjoined create can never
   be reported as a successful one.

---

### CR-03: `create_outcome: "none"` / `"refused"` is computed and then never read — an unjoined create is reported as a successful create

**File:** `n8n/code/pairCreateOutcome.js:130-136`; consumer at `scripts/build_cloud_workflows.py:848-905` (`BUILD_INGEST_RESPONSE`)
**Severity:** BLOCKER

**Issue:**
`pairCreateOutcome` carefully distinguishes four outcomes and documents `"none"` ("no response of
either kind ever arrived for this row's identity key") and `"refused"` ("never guessed —
`create_outcome_reason` names which"). Nothing downstream consumes either.

`BUILD_CREATE_FAILURE_ROW_JS` filters `create_outcome === "error"` only. `Build Ingest Response`'s
new join reads `row.action === "create_failed"` only. A row stamped `"none"` or `"refused"` keeps
`action: "create"` and `contact_id: null`, so it is reported to the operator as a create and
persisted as `created_id_unknown`.

This is the mechanism by which *both* of CR-02's branches degrade silently, and it is a defect in
its own right: `"none"` is reachable without any error at all (a create whose success response
carries no email — HubSpot's create echo carries `properties` only for the properties requested —
would produce a success item whose `identityKey` is `null`, which `:114` discards, leaving the
carried row at `"none"`).

**Fix:** Consume the field. In `BUILD_INGEST_RESPONSE`, treat a non-`success` `create_outcome` as
its own reported outcome rather than letting the row's pre-write `action` stand:

```js
const unconfirmed = allItems.filter((row) =>
  row._decided_snapshot !== true &&
  row.create_outcome && row.create_outcome !== "success");
// ...per row, alongside `fail`:
action: fail ? "create_failed"
      : (unconf ? "create_unconfirmed" : (block ? "write_blocked" : row.action)),
reason: (unconf && (unconf.create_outcome_reason || "no create response joined to this row"))
      || ...
```

and add `"create_unconfirmed"` to `written_records.ACTION_TO_OUTCOME` mapped to `FAILED` (not
`created_id_unknown`), beside the `create_failed` entry added at
`operator-claude-plugin/scripts/written_records.py:184`.

---

### CR-04: the runData freezer redacts only `json.headers` — it misses the error-object path its own phase's threat model (T-73-06-01) names as carrying `Authorization`

**File:** `scripts/freeze_execution_rundata.py:80-100`
**Severity:** BLOCKER

**Issue:**
`_redact_headers` replaces `item["json"]["headers"]` and nothing else. The module docstring
(`:22-27`) justifies the wholesale replacement as being safer than "a key-by-key scrub, which is
easy to under-cover" — but the scope of *which objects* get replaced is itself under-covered.

The same phase's own threat item, quoted verbatim in `BUILD_CREATE_FAILURE_ROW_JS`
(`scripts/build_cloud_workflows.py:766-770`), states: *"an n8n HTTP error item can carry the
OUTBOUND request configuration, including its Authorization header."* None of the places that
object lives are touched by this redactor:

- `run["error"]` — the node-run-level error object on a failed node run;
- `item["json"]["error"]` / `item["json"]["error"]["request"]["headers"]` — the shape
  `_createFailureReason` itself reads around;
- `item["error"]` — the sibling of `json` on an error-output item.

A HubSpot private-app token (`pat-na1-…`) or the `x-enrichment-secret` webhook shared secret
committed into git history is not revocable by deleting the file. The three fixtures this commit
adds are clean today (scanned for `authorization` / `x-enrichment-secret` / `Bearer …` /
`pat-na…` — zero hits), so nothing has leaked; the gap is in the tool that will freeze the next
one. Note that the very next fixture this tooling is likely to be pointed at is CR-01/CR-02's —
an execution whose whole point is that an HTTP node **failed**.

**Fix:** Widen the wholesale replacement to every object that can carry a request config, in the
same non-enumerating idiom:

```python
_SENSITIVE_KEYS = ("headers", "error", "request", "options", "config")

def _scrub(obj):
    if isinstance(obj, dict):
        return {k: (REDACTED_PLACEHOLDER if k in _SENSITIVE_KEYS else _scrub(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj
```

applied to each `run` (so `run["error"]` is covered) rather than only to `item["json"]`. If
`error` must be kept readable for a fixture, keep a whitelist of scalar fields
(`message`/`description`/`httpCode`) exactly as `_createFailureReason` already does, and drop the
rest — never the whole object. Add a guard test that asserts no committed fixture under
`tests/n8n/fixtures/frozen/` matches `Authorization|x-enrichment-secret|pat-na\d-`.

## Warnings

### WR-01: the contact-upload lane's hardcoded `executions = 1` sits inside the chunk-ceiling `try`, so a config key it does not use suppresses it — and the operator is told a falsehood

**File:** `operator-claude-plugin/scripts/write_grant.py:546-575`
**Severity:** WARNING

**Issue:** The comment at `:551-555` is explicit that this lane "sends the WHOLE csv as a single
multipart POST regardless of row count (no chunking loop exists for this lane at all)". The
assignment is nonetheless placed after `chunking.chunk_ceiling(config)` inside the same `try`, so
a missing `max_records_per_chunk` raises `ChunkPlanError` and the projection degrades to
`None`/`unconfigured`. Reproduced:

```
projected_executions: None basis: unconfigured
block: "n8n executions: **not projected** — `max_records_per_chunk` is not set in the operator
        config, so the chunk count is unknown. ... a dispatch will refuse for the same missing
        key and say so."
```

The final clause is false for this lane: `dispatch.dispatch()` never reads that key. `ceiling_verdict`
degrades to `unknown` rather than refusing, so the grant still opens — but the operator is
handed a wrong explanation of why a number is missing, for a number that was known all along.
No test covers this combination (`tests/test_write_grant.py` has neither a contact-upload +
missing-ceiling case nor an assertion on the rendered basis text for this lane).

**Fix:** Hoist the lane-invariant value out of the `try`:

```python
    executions = 1 if cost_lane == COST_LANE_CONTACT_UPLOAD else None
    executions_basis = PROJECTED
    try:
        chunk_record_ceiling = chunking.chunk_ceiling(config)
        chunk_count = chunking.plan_chunks(...).chunk_count
        if executions is None:
            executions = chunk_count + record_count
    except chunking.ChunkPlanError:
        if executions is None:
            executions_basis = UNCONFIGURED
```

and add the missing-ceiling contact-upload test.

---

### WR-02: the contact-upload grant disclosure states a basis that contradicts its own number

**File:** `operator-claude-plugin/scripts/write_grant.py:634` (`executions_projection_basis`), rendered at `:727-732`
**Severity:** WARNING

**Issue:** `figures["executions_projection_basis"]` is unconditionally `EXECUTIONS_BASIS`, whose
text is `"1 webhook execution per chunk + 1 sub-execution per record (the enrichment workflow has
no batching node, so it fans out per record)"`. For `cost_lane="contact-upload"` the number is a
hardcoded 1. Reproduced with 5 records and `max_records_per_chunk = 2`:

```
n8n executions: **1 (projected, not measured)** — 1 webhook execution per chunk + 1 sub-execution
per record (the enrichment workflow has no batching node, so it fans out per record), at 3
chunk(s) of at most 2 record(s).
```

3 chunks × per-record fan-out cannot be 1. This is a GRANT-02 consent surface; an operator cannot
reconcile it, and the `chunk_count: 3` figure the sentence prints is explicitly documented at
`:558-562` as "NOT this lane's real POST count". The same run also leaves
`figures["providers"] == ['lusha']` while the block prints "this grant runs no provider" —
`zero_cost_estimate` returns `providers: []` but the figure is taken from the caller's argument.

**Fix:** Make the basis a per-lane value, not a module constant:

```python
CONTACT_UPLOAD_EXECUTIONS_BASIS = (
    "1 webhook execution for the whole CSV — this lane sends one multipart POST "
    "regardless of row count and does not chunk")
...
"executions_projection_basis": (CONTACT_UPLOAD_EXECUTIONS_BASIS
                               if cost_lane == COST_LANE_CONTACT_UPLOAD else EXECUTIONS_BASIS),
```

and suppress the `at N chunk(s) of at most M record(s)` clause for this lane (or drop
`chunk_count` from `figures` when it is not the POST count). Take `figures["providers"]` from
`estimate.get("providers")` so the two agree.

---

### WR-03: `csv_dedupe.py`'s CLI ignores the operator config's `column_mapping_path`, unlike every sibling CLI

**File:** `operator-claude-plugin/scripts/csv_dedupe.py:127-147`
**Severity:** WARNING

**Issue:** `preview.py`'s `__main__` (`:259-263`) resolves `column_mapping_path` from
`config_gate.load_config()` before building the preview. `csv_dedupe.py`'s `__main__` calls
`propose_dedupe(_path)` / `apply_dedupe(_path)` with `mapping_path=None`, so it falls back to
`resolve_mapping_path(None)`. `contact-upload/SKILL.md` step 2c invokes it through the CLI
(`python3 scripts/csv_dedupe.py <path> --apply`), so on any install that configures a custom
mapping path, the dedupe clusters against a *different* alias table than the preview the operator
then approves and than the `Map Columns` node that eventually reads the file — silently, because
an unmapped header simply contributes no key (`_canonical_rows`'s `if c is not None`).

**Fix:** Mirror `preview.py`'s resolution in `csv_dedupe.py`'s `__main__`:

```python
    _mapping_path = None
    try:
        import config_gate
        _mapping_path = config_gate.load_config().get("column_mapping_path")
    except Exception:
        _mapping_path = None
    ...
    propose_dedupe(_path, _mapping_path)  # / apply_dedupe(_path, _mapping_path)
```

---

### WR-04: `preview.py --collapsed` swallows every read failure, silently making `pre_collapse_row_count` wrong exactly when it matters

**File:** `operator-claude-plugin/scripts/preview.py:264-272`; `collapse_block` at `:141-152`
**Severity:** WARNING

**Issue:** An unreadable, missing or malformed sidecar sets `_collapsed = None`, which makes
`pre_collapse_row_count == row_count` and `collapsed_rows.count == 0`. `contact-upload/SKILL.md`'s
step 3 instructs the assistant to state `pre_collapse_row_count` alongside `row_count` "so the
operator can reconcile the count they expected in their own file against the count actually being
sent". A dropped sidecar therefore produces a confidently wrong reconciliation number that reads
exactly like a batch with no duplicates — the one case the operator most needs to be able to
distinguish. `collapse_block` also accepts any sized object: pass the whole `apply_dedupe` result
dict by mistake and you get `count: 5, rows: ["deduped_path", ...]` with no complaint.

**Fix:** Fail loudly on an explicitly-requested sidecar, and type-check the payload:

```python
    if _collapsed_arg_path:
        try:
            _collapsed = json.loads(Path(_collapsed_arg_path).read_text(encoding="utf-8"))
        except Exception as _e:
            print(json.dumps({"ok": False, "error":
                f"--collapsed {_collapsed_arg_path} could not be read ({_e}); refusing to "
                f"render a reconciliation count that would read as 'no duplicates'."}))
            raise SystemExit(1)
```

and in `collapse_block`, `collapsed = collapsed if isinstance(collapsed, list) else []`.

---

### WR-05: `backfill_missing_identity`'s ledger map is keyed by id alone across both object types, contacts silently overwriting companies

**File:** `operator-claude-plugin/scripts/report_enrichment.py` — the `ledger_by_id` build in `backfill_missing_identity` (`_ACTION_LANE_ORDER` at `:103`)
**Severity:** WARNING

**Issue:** `_ACTION_LANE_ORDER` is `(("companies", DECIDE_COMPANY_ACTION_NODE), ("contacts", DECIDE_CONTACT_ACTION_NODE))`
and the map is built with `ledger_by_id[str(ledger_id)] = ledger_json` — last lane wins. HubSpot
draws contact and company ids from independent sequences, so numeric collisions are possible
(CLAUDE.md itself names contact `1251` and company `9604614548` in the same document). A recovered
id that collides copies the *wrong* lane's `action`, `object_type` and `row_id` onto the row, and
the whole point of the function is that `written_records.classify_item` then trusts `object_type`.
The function's own docstring promises "A miss leaves `action` alone — this never guesses"; a
cross-object collision is a guess it cannot see.

**Fix:** Key by `(lane, id)` and refuse an ambiguous id rather than taking the last writer:

```python
    ledger_by_id = {}
    ambiguous = set()
    for lane, node_name in _ACTION_LANE_ORDER:
        for item in all_node_items(run_data, node_name):
            ...
            key = str(ledger_id)
            if key in ledger_by_id and ledger_by_id[key][0] != lane:
                ambiguous.add(key)
            ledger_by_id[key] = (lane, ledger_json)
    # later: skip the backfill entirely for an id in `ambiguous`
```

---

### WR-06: `dispatch_and_recover` discards `_excluded_marker_count`, so rows dropped from the durable ledger leave no trace anywhere

**File:** `operator-claude-plugin/scripts/chunking.py:669-671`
**Severity:** WARNING

**Issue:** `write_records_rows, _excluded_marker_count = _report_enrichment.backfill_missing_identity(rows, run_data)`
— the count is bound and never used. `backfill_missing_identity`'s docstring is explicit that
whole-request markers are **removed** from the persisted list. `dispatch_and_recover`'s return
dict carries `written_records_failures` for the bookkeeping failures it *does* report, but nothing
for rows it deliberately dropped. An operator reconciling "N rows sent, M rows in the ledger"
has no way to account for the difference, and there is no signal at all if the exclusion ever
fires on a shape it should not have.

**Fix:** Return it alongside the existing bookkeeping channel:

```python
    return {
        ...
        "written_records_failures": written_records_failures,
        "excluded_marker_count": excluded_marker_count,
    }
```

and have the end-of-run report state it when non-zero.

---

### WR-07: `Ingest Merge Response`'s new sixth input has no producer on a zero-create batch, making the lane's final convergence drain-only on every all-update batch

**File:** `scripts/build_cloud_workflows.py:1995-2007`
**Severity:** WARNING

**Issue:** `Build Create Failure Row` is fed by a fan-out off `Pair Create Outcome To Row`, which
only runs when the create lane runs. On an all-update or all-review batch it never executes, so
input 5 never receives. Verified by walking the committed `wf_contact_ingest_cloud.json` with a
two-row all-update batch:

```
stalled: [{ "node": "Ingest Merge Response", "reason": "merge_fired_with_unfilled_input",
            "run": 0, "missingInputs": [5] }]
```

Rows do survive (`starvedWithData(trace)` is `[]`, both rows reach `Build Ingest Response`),
because the v1 end-of-run drain fires the merge on the inputs that arrived — so this is not
starvation. But it is the exact drain-only hazard class the same commit's own comment
(`:1960-1973`) identifies as dangerous and spends `alwaysOutputData` to avoid for `Create Carry
Merge`, and CLAUDE.md §13.0.3's stated design rule is that "each way a producer can legitimately
be silent needs a node that says so". The asymmetry is undocumented: the comment at `:1995-2007`
argues only against a *separate* starved-lane sentinel (a second producer), and never addresses
the zero-create case where the single producer itself does not run.

**Fix:** Either document the zero-create drain explicitly at `:1995` (naming that
`Ingest Merge Response` is the lane's terminal convergence, so an end-of-run drain cannot lose a
later delivery), or give input 5 a gated sentinel the same way the lane's other silent producers
get one — a `_add_starved_lane_sentinel` keyed on the decided-row set containing zero
create-routed rows, which is knowable pre-write and therefore not a second producer in the
dangerous sense.

---

### WR-08: `walkWorkflow.mjs`'s JSDoc contradicts the implementation it documents, in the same diff

**File:** `tests/n8n/lib/walkWorkflow.mjs:351-357` vs `:316-326`
**Severity:** WARNING

**Issue:** The JSDoc added by this change states: *"A stub in the plain array form still yields
exactly one output even on such a node (no existing stub's meaning changes)."* The implementation
does the opposite — a plain-array stub on a `continueErrorOutput` node is reshaped to
`{ success: raw, error: [] }` and **two** outputs are returned. The inline comment at `:302-315`
records that the one-output version was the original and was deliberately replaced; the JSDoc was
simply not updated with it. Anyone reading the documented contract (the natural entry point for a
test author) will reason about walker behaviour incorrectly, which matters more than usual here
because CR-01 turns on exactly how this function models output branches.

**Fix:** Replace the stale sentence with the real contract:

```
 *     A stub in the plain array form on such a node is treated as
 *     `{ success: <that array>, error: [] }` — the second output exists but is empty. Under v1
 *     an empty branch makes no delivery, so no pre-existing stub's observable meaning changes.
```

---

### WR-09: `_as_hubspot_text(None) -> ""` also weakens leg 1, where the docstring only reasons about leg 2

**File:** `operator-claude-plugin/scripts/review_decision.py:366-390`, applied at `:500-503`
**Severity:** WARNING

**Issue:** The docstring's "ONE narrow consequence, accepted deliberately" paragraph reasons
entirely about the refetch (leg 2: "HubSpot omits a blank property from a read, so there is
nothing for that comparison to catch"). The same helper is applied to **leg 1**, the intent-stability
check between `intended` and the backend's own `would_write`, where that justification does not
hold: `would_write` is a patch the backend *composed*, not a HubSpot read, and a key the backend
silently dropped from it is a real divergence from the approved patch. After this change, a key
whose approved value is blank (`lv_enrichment_review_reason: ""`,
`lv_enrichment_review_candidate_json: ""` — both minted by `reviewApply`'s `clearPatch`) compares
equal when the backend omits it entirely. Those two are precisely the de-queue clears, and leg 1
is the only check that would notice them going missing from the submitted patch.

**Fix:** Keep `_as_hubspot_text` for leg 2, and make leg 1 distinguish absence from blankness:

```python
_MISSING = object()
intent_mismatched = [
    key for key in leg1_keys
    if (would_write.get(key, _MISSING) is _MISSING) != (intended.get(key, _MISSING) is _MISSING)
    or _as_hubspot_text(would_write.get(key)) != _as_hubspot_text(intended.get(key))
]
```

At minimum, extend the docstring so the accepted consequence is stated for both legs rather than
one.

---

### WR-10: `extract_js_const` can silently truncate the constant it extracts, and the build never validates the result

**File:** `scripts/build_cloud_workflows.py:166-182`
**Severity:** WARNING

**Issue:** The pattern `^const\s+NAME\s*=.*?;\s*$` is non-greedy under `DOTALL | MULTILINE`, so it
stops at the first `;` that ends a line. It works today only because `companyLink.js`'s
`FREEMAIL_DOMAINS` literal happens to contain no `;` at any line end — including inside its two
`//` comment lines. Add a comment ending in a semicolon, or a future constant whose literal
contains one, and the extraction silently yields a syntactically-broken prefix that is spliced
verbatim into the generated Code node. The docstring's stated guard ("Raises if the constant is
not found, so a rename in the source module fails the build") covers rename but not truncation:
the regex still matches, so nothing raises. The generated workflow JSON is not syntax-checked at
build time; the truncation is caught only if the walker suite happens to execute that particular
node's body.

**Fix:** Validate what was extracted before returning it — balanced brackets are enough and need
no parser:

```python
    text = m.group(0)
    if text.count("[") != text.count("]") or text.count("{") != text.count("}") \
            or text.count("(") != text.count(")"):
        raise ValueError(
            f"extract_js_const: `const {const_name}` in {module_name} did not extract as a "
            f"balanced statement — the terminating `;` heuristic truncated it.")
    return text
```

---

### WR-11: `_canonical_rows` zips headers against raw rows, so a short row silently loses its identity fields and never dedupes

**File:** `operator-claude-plugin/scripts/csv_dedupe.py:39-50`
**Severity:** WARNING

**Issue:** `read_table` returns CSV rows exactly as `csv.reader` produced them, which for a file
whose exporter omits trailing empty cells means rows shorter than the header. `zip(canonical_headers, row)`
truncates to the shorter of the two, so a trailing `linkedin_url` (or `company`) column is absent
from the canonical dict, `_first_satisfied_key` finds no fully-satisfied group for that row, and
the duplicate is silently kept — reported as "0 collapsed" with no indication that a row could not
be keyed at all. Symmetrically, two headers that map to the same canonical prop (e.g. `Email` and
`Email Address`) let the last column win with no report.

**Fix:** Pad, and surface unkeyable rows:

```python
    return [
        {c: (row[i] if i < len(row) else "")
         for i, c in enumerate(canonical_headers) if c is not None}
        for row in rows
    ]
```

and have `propose_dedupe`/`apply_dedupe` report `unkeyable_count` (rows where
`_first_satisfied_key` returned `None`) so "nothing collapsed" is distinguishable from "nothing
could be compared".

---

### WR-12: `apply_dedupe`'s output paths collide on file stem, so two sources with the same name overwrite each other's deduped copy and report

**File:** `operator-claude-plugin/scripts/csv_dedupe.py:96-116`
**Severity:** WARNING

**Issue:** `out_path = scratch_dir / f"deduped-{path.stem}.csv"` and
`report_path = scratch_dir / f"dedupe-report-{path.stem}.json"` are derived from the stem alone.
Two files named `contacts.csv` from different folders in one session — or the same file re-run
after an edit — silently overwrite both artifacts. `contact-upload/SKILL.md` step 2c makes
`deduped_path` *the* path sent to HubSpot and `collapsed_path` the thing shown to the operator, so
a stale collision means the preview the operator approves and the bytes actually sent can come
from different files.

**Fix:** Disambiguate, in the same register `written_records`/`run_manifest` already use for
run-scoped artifacts — e.g. include a short hash of the resolved source path, or write into a
per-run subdirectory:

```python
    tag = hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:8]
    out_path = scratch_dir / f"deduped-{path.stem}-{tag}.csv"
    report_path = scratch_dir / f"dedupe-report-{path.stem}-{tag}.json"
```

---

_Reviewed: 2026-09-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
