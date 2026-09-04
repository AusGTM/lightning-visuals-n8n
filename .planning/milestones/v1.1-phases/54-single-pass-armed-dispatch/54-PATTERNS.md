# Phase 54: Single-pass armed dispatch - Pattern Map

**Mapped:** 2026-08-27
**Files analyzed:** 5 (2 primary edits, 3 test/measurement touches)
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `n8n/code/reviewDecision.js` (contacts-approve branch, lines 229-235) | transform (pure decision->patch fn) | request-response | `n8n/code/reviewApply.js` `clearPatch` (lines 93-99) | exact — same module family, same property family |
| `scripts/build_cloud_workflows.py` (rebuild only — no logic change needed) | build/codegen | transform | itself (`build_review_decision_cloud`, lines ~3310-3343) | exact — inlines `reviewDecision.js` verbatim, no node-graph edit required |
| `tests/n8n/reviewDecisionEndpoint.test.mjs` (lines 225-228, 654-668) | test | request-response | itself, `test_write_grant.py`'s discipline of rewriting-not-deleting pinned tests | exact — same file, re-point in place |
| new small script: count n8n executions for one record before/after | utility (measurement, read-only) | request-response (HTTP GET) | `operator-claude-plugin/scripts/scheduled_arm.py::find_latest_sj3_batch` (lines 145-172) | exact — same `executions_client` calls, same sort/filter pattern |
| `operator-claude-plugin/tests/test_write_grant.py` (new case: `envelope()` figure vs measured count) | test | CRUD-adjacent (config compare) | existing `envelope()` tests in same file | exact |

## Pattern Assignments

### `n8n/code/reviewDecision.js` — contacts-approve branch

**Analog:** `n8n/code/reviewApply.js` lines 93-101 (the companies `clearPatch` this module already imports and spreads for companies)

**Current code to replace** (lines 229-235):
```javascript
if (inp.objectType === "contacts") {
  return nothingToApply(
    "this record holds no review candidate to approve — contact records are flagged for "
    + "review (dedupe, ICP) but no contact enrichment candidate is ever staged in this "
    + "deployment, so there is nothing to promote. Reject with a reason, or edit the "
    + "record in HubSpot.");
}
```

**Clear-only patch shape to copy** (`reviewApply.js:93-99`, adapted — no `lv_enrichment_review_approved`
key exists for contacts since no candidate/approval boolean is ever staged there, and NO
`lv_enrichment_review_candidate_json` clear because contacts never set it — confirmed by
research §6):
```javascript
{
  lv_enrichment_needs_review: "false",
  lv_enrichment_review_reason: "",
  lv_enrichment_reviewed_at: new Date().toISOString(),
}
```
String-literal `"false"`, not a JS boolean — copy `reviewApply.js`'s D-07 comment convention
(lines 88-92: HubSpot EQ filters compare strings; PATCH consumers here do no coercion of
their own).

**Outcome/message convention to copy** (from the `applied` return shape at the bottom of
`buildReviewDecision`, lines 297-317): reuse the existing `outcome: "applied"` string (do not
invent a new outcome word — `report_enrichment`/skills already know how to render `applied`),
with a message that says what actually happened for a contact:
```javascript
return {
  properties: { lv_enrichment_needs_review: "false", lv_enrichment_review_reason: "",
                lv_enrichment_reviewed_at: verifiedAt },
  outcome: "applied",
  message: "acknowledged — this contact's value was already applied by the permissive "
    + "contact enrichment lane when it was flagged; clearing the review flag only, "
    + "no field was promoted",
};
```
(`verifiedAt` — reuse the same `inp.nowIso`-or-`new Date().toISOString()` fallback already
computed lower in the function at line 291-292; hoist that computation above this branch or
compute it locally here — do not duplicate two different clocks in one response.)

**Reviewed-by handling to copy** (lines 301-302): same omit-if-blank rule applies —
`if (reviewedBy !== "") properties[P_REVIEWED_BY] = ...`.

**What NOT to copy from `reviewApply`:** its compare-and-set/staleness check
(`applied.stale`), its `canonicalPatch`/policy-class filtering (`DEFAULT_COMPANY_POLICY`),
and its provenance-blob write (`buildHumanProvenance`) — none of these apply because there is
no held candidate to promote for a contact (research §6, "Don't Hand-Roll" row 3: no contacts
apply engine is needed).

---

### `scripts/build_cloud_workflows.py` — no logic change

**Analog:** itself. `build_review_decision_cloud()` inlines `reviewDecision.js`'s full source
into the `Review Contact/Company Decision Update`-adjacent Code node already. Once
`reviewDecision.js` is edited, running `python3 scripts/build_cloud_workflows.py` regenerates
`n8n/wf_review_decision_cloud.json` with the new branch baked in — no node-graph, write-gate,
or verify-fetch change (research §6, "Where the write path already exists, unmodified").
**Never hand-edit `n8n/wf_review_decision_cloud.json`** — this repo's hard constraint, cited
in CLAUDE.md and re-confirmed for this exact file in research §6.

Deploy sequence to copy (research §6, "Cost and classification of this change"):
```text
edit reviewDecision.js -> python3 scripts/build_cloud_workflows.py -> diff
  -> disarmed deploy -> bounce (deactivate/reactivate, D-18 reload requirement)
  -> independent re-read
```

---

### `tests/n8n/reviewDecisionEndpoint.test.mjs` — two pinned tests to re-point

**Test 1** (line ~225):
```javascript
test("approve on a contact writes nothing: no contacts candidate producer exists in this repo", () => {
  const out = approve({ objectType: "contacts" });
  assert.equal(out.outcome, "no_candidate");
  assert.deepEqual(out.properties, {});
});
```
Re-point to assert the NEW behavior (`outcome: "applied"`, `properties` containing the
clear-only patch, `properties.lv_enrichment_review_candidate_json` NOT present). Follow this
repo's established discipline (D-53-01/D-53-05, cited in research §5): rewrite in place, do
not delete, and record the decision + date in a comment directly above the assertion, e.g.
`// 2026-08-27, Phase 54: contacts approve now clears the flag (permissive lane already wrote
the value) — was "no_candidate" before this date, see 54-RESEARCH.md §6.`

**Test 2** (line ~654, `(g4) a contacts APPROVE writes nothing and says why`):
```javascript
const { built } = drive(
  { ...REJECT_BODY, object_type: "contacts", decision: "approve", dry_run: false },
  contactRow, { ALLOW_HUBSPOT_REVIEW_WRITES: "true", TEST_RECORD_IDS: "4242" });
assert.equal(built.outcome, "no_candidate");
assert.deepEqual(built.would_write, {});
assert.equal(built.dry_run, true, "nothing to write must never reach a write gate");
```
Re-point the same way: `built.outcome` becomes `"applied"`, `built.would_write` becomes the
clear-only patch, `built.dry_run` becomes `false` (this now IS a real write, so it must reach
the write gate — mirror the neighboring `(g5)` company-approve test's assertions for the
armed/disarmed pair, same file, right below this block, which already exercises exactly this
shape for companies).

---

### Execution-count measurement script (new, small)

**Analog:** `operator-claude-plugin/scripts/scheduled_arm.py::find_latest_sj3_batch`
(lines 145-172)

**Pattern to copy — list + sort executions for one workflow, read-only:**
```python
candidates = executions_client.list_executions(
    config, maintenance_workflow_id, transport=transport, limit=lookback)
candidates = sorted(
    (c for c in candidates if isinstance(c, dict) and c.get("startedAt")),
    key=lambda c: c["startedAt"], reverse=True,
)
```
For Phase 54's measurement, the same call shape applies to the ENRICHMENT workflow's id
(not the maintenance workflow's), scoped by a `startedAt` time window bracketing one
before-send and one after-send timestamp captured by the operator/script — count executions
in each window rather than resolving a single latest batch.

**Client to reuse, not reimplement:** `operator-claude-plugin/scripts/executions_client.py`
— `list_executions`/`get_execution`, `X-N8N-API-KEY` auth header (`_headers`, lines 43-44),
injectable `transport` parameter for testability (no real socket in tests — mirrors
`conftest.py`'s autouse `no_network` guard, cited in the module's own docstring).

**Security note to copy from research (V7/threat table):** a failed execution-count read
must raise `ExecutionsClientError` (already the module's behavior) or be surfaced as
"unmeasured" — never silently reported as zero. Do not call `armed_window`/`arm_for_dispatch`
anywhere in this measurement script; use only the read-only `list_executions`/`get_execution`
calls.

**Where the PROJECTED figure to compare against lives:**
`operator-claude-plugin/scripts/write_grant.py:210-224` (`envelope()`), specifically:
```python
chunk_count = chunking.plan_chunks(
    {"record_ids": ids + domains, "object_type": object_type}, ceiling).chunk_count
executions = chunk_count + record_count
```
labelled `PROJECTED` via the `executions_basis` variable (line 216). The new test case in
`test_write_grant.py` should assert the measured count from the new script against this
formula's output for the same record, not replace the formula — research recommends keeping
`envelope()`'s figure but relabelling/validating it, not deleting it.

---

## Shared Patterns

### String-literal booleans in HubSpot property patches
**Source:** `n8n/code/reviewApply.js` lines 88-99 (D-07 comment + `clearPatch`)
**Apply to:** the new contacts clear-only patch in `reviewDecision.js` — every boolean-shaped
HubSpot property must be the string `"true"`/`"false"`, never a bare JS boolean, because
consumers of this patch (the shared PATCH node, `report_enrichment`) do no coercion.

### Fail-closed / never-throw contract
**Source:** `n8n/code/reviewDecision.js` header comment, line 34 ("FAIL-CLOSED: never
throws, never does I/O, requires nothing outside n8n/code/")
**Apply to:** the new contacts branch — keep it a pure function returning
`{ properties, outcome, message }`, no new imports, no I/O.

### Rewrite-in-place test discipline (D-53-01/D-53-05)
**Source:** cited directly in `54-RESEARCH.md` §5 and §6 for this exact change
**Apply to:** both `reviewDecisionEndpoint.test.mjs` pins — edit assertions in place with a
dated comment recording why, never delete-and-recreate the test.

### Measured vs. projected labelling
**Source:** `write_grant.py`'s existing `PROJECTED`/`UNCONFIGURED`/(presumably `MEASURED`)
basis constants (lines 210-224), and `cost_guard.py`'s tri-state labelling convention cited
in research §4 Don't-Hand-Roll row 4
**Apply to:** any new measurement output — report executions and provider credits as
measured; the Anthropic dollar figure stays labelled `projected` unless new usage-capture
instrumentation is explicitly scoped as its own task (research §4, Pitfall 3).

## No Analog Found

None — every file this phase touches has a direct, precise analog already in the codebase
(this is a closure phase on infrastructure that already exists, not new-pattern work).

## Metadata

**Analog search scope:** `n8n/code/`, `scripts/build_cloud_workflows.py`,
`operator-claude-plugin/scripts/` (`write_grant.py`, `n8n_arming.py`, `chunking.py`,
`scheduled_arm.py`, `executions_client.py`, `cost_guard.py`), `tests/n8n/`,
`operator-claude-plugin/tests/`
**Files scanned:** 8 read directly this session (2 in prior research session, re-cited here);
0 new files needed beyond the small measurement script
**Pattern extraction date:** 2026-08-27
