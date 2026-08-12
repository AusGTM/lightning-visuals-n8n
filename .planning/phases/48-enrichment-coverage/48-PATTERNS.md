# Phase 48: Enrichment Coverage - Pattern Map

**Mapped:** 2026-08-12
**Files analyzed:** 7 (1 new driver, 1 new pytest, 1 modified builder, 1 new n8n test, 1 possibly-modified prompt module, 1 read-only JS reference, 2 run-artifact docs)
**Analogs found:** 7 / 7

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `scripts/enrich_coverage_companies.py` (new; name is Claude's Discretion) | service/CLI driver | batch, request-response (HubSpot PATCH + webhook POST) | `scripts/remediate_veto_companies.py` | exact — same author, same phase family, explicitly named as the file to extend rather than replace |
| `tests/test_<new_module>.py` (new; e.g. `tests/test_enrich_coverage_companies.py`) | test | transform/unit | `tests/test_veto_remediation_report.py` | exact — same offline-only, network-refusing test style, same repo, same domain |
| `scripts/build_cloud_workflows.py` (MODIFIED — insert `IF Research Errored` + `Build Research Failure Response`) | config/builder (n8n workflow-as-code) | event-driven (IF-gate routing) | same file, `IF Company Recompute` / `IF Company Skip` (Phase 47.5) | exact — same file, same gate-with-failure-branch idiom, same author intent |
| `tests/n8n/researchErrorGateFlow.test.mjs` (new) | test | event-driven, offline structural | `tests/n8n/companyRecomputeLaneFlow.test.mjs` | exact — explicitly named in RESEARCH.md as the model to copy |
| `src/web_research.py` (possibly MODIFIED, or a narrow one-off prompt added alongside it) | service (LLM prompt/adapter) | request-response (single Anthropic call) | itself — `RESEARCH_SYSTEM` / `claude_web_research()` | exact — editing/extending the same module |
| `n8n/code/webResearch.js` | utility (read-only reference) | transform | itself — `researchCandidateFromHttpItem` | n/a — READ ONLY, not modified this phase; consulted to confirm what D-04's gate adds on top of it |
| `.planning/phases/48-enrichment-coverage/48-COST-ESTIMATE.md`, `48-RUN-REPORT.md` (new docs) | doc artifact | batch (report) | `.planning/phases/47-veto-remediation/47-COST-ESTIMATE.md`, `.planning/phases/47.5-veto-recompute-path/47.5-RUN-REPORT.md` | exact — same phase family, same COVER-02 pattern |

## Pattern Assignments

### `scripts/enrich_coverage_companies.py` (new driver)

**Analog:** `scripts/remediate_veto_companies.py` (1045 lines, read in full this session)

**Module docstring / ownership pattern** (lines 1-20 of the analog):
```python
#!/usr/bin/env python3
"""scripts/remediate_veto_companies.py

Phase 47 (VETO-01/02, COVER-01/02) -- the single script carrying all four write legs this
phase needs for the 17 pinned companies ...

This script writes ONLY: lv_org_type, lv_produces_content, lv_country_region_normalized
(the D-05 widened input set) when research actually establishes them ...

It NEVER writes lv_icp_fit_score, lv_icp_tier, lv_anti_icp_flag or lv_anti_icp_reason
(D-07) -- those are derived by ... the n8n "Decide Company Action" Code node. This script
changes inputs and (D-18) POSTs a synthetic property-change event so that Code node
actually runs, then polls for the derived values to settle ...
```
Phase 48's driver docstring must state the same D-07 boundary and name its own 5-record
population, its own two paid/free split (D-01), and its own arm-key name (new, per
`A2` in RESEARCH.md — do not reuse `ALLOW_VETO_REMEDIATION`).

**Pinned-id-order + refusal idiom** (lines 71-89, 202-221) — copy the PATTERN, not the
membership:
```python
PINNED_COMPANY_ID_ORDER = (
    "9604732797",    # Tweed Valley Jockey Club
    ...
    "20943964946",   # The Rumble / Pacific Action Sports
)
PINNED_COMPANY_IDS = frozenset(PINNED_COMPANY_ID_ORDER)

def resolve_pinned_ids(requested):
    """Raises PinRefused naming the offending id if any requested id is absent from
    PINNED_COMPANY_IDS ... Returns the accepted ids sorted into PINNED_COMPANY_ID_ORDER
    order, so output ordering is deterministic regardless of input order."""
    for company_id in requested:
        if company_id not in PINNED_COMPANY_IDS:
            raise PinRefused(...)
    requested_set = set(requested)
    return tuple(cid for cid in PINNED_COMPANY_ID_ORDER if cid in requested_set)
```
Phase 48's version: a 5-id literal tuple (Racing NSW, Editix, Jam TV, Waikato, The Rumble),
`resolve_coverage_ids()` raising before any HubSpot/n8n call — but see the population note
below: unlike Phase 47's design-time-only 17, D-01/CONTEXT.md requires the driver to ALSO
call `search_records` live and assert the derived population matches (or superset-covers)
this literal set, since "re-derive again at plan time and stamp the date" is repeated
verbatim four times in CONTEXT.md.

**`VALID_ORG_TYPES` allowlist — reuse verbatim, do not re-declare** (lines 138-156):
```python
VALID_ORG_TYPES = (
    "governing_body_league", "content_producer", "individual_club_team", "broadcaster",
    "gambling_operator", "hardware_vendor", "regulator", "other", "unknown",
)
```
Import this constant from `scripts.remediate_veto_companies` rather than copying the
9-tuple a second time — CONTEXT.md's hard-constraints table calls this allowlist
"load-bearing" and a second literal risks drift.

**`post_webhook_event(..., recompute=True)` — the D-09 call, reuse unmodified**
(lines ~596-625):
```python
def post_webhook_event(company_id: str, armed, config: dict, transport=requests,
                       recompute: bool = False, domain: str = None, timeout: float = 300):
    """`armed` has NO default ... raises NotArmedError when falsy before any network call.
    `timeout` defaults to 300 seconds ..."""
    if not armed:
        raise NotArmedError(
            "Live writes are off for this run -- nothing was sent. Arming ... is an "
            "operator-only, per-shell decision, never made by Claude."
        )
    url = f"{str((config or {}).get('n8n_url') or '').rstrip('/')}/{WEBHOOK_PATH}"
    headers = {"X-Enrichment-Secret": config["webhook_secret"]}
    response = transport.post(
        url, headers=headers,
        json=build_webhook_event(company_id, recompute=recompute, domain=domain),
        timeout=timeout,
    )
    response.raise_for_status()
    return response
```
Call directly: `post_webhook_event(company_id, armed=True, config=cfg, recompute=True)` —
do not reimplement.

**Cost-estimate pattern — do NOT reuse `estimate_cost()` unmodified.** Its `n8n_executions`
charge is one-per-id assuming Phase 47's research-via-webhook shape (lines 638-671):
```python
ANTHROPIC_PER_RECORD_ESTIMATE_USD = 0.0686

def estimate_cost(ids) -> dict:
    n_records = len(ids)
    redundant = len(set(ids) & KNOWN_LIKELY_EVIDENCE_GATED_IDS)
    return {
        "web_research_calls": n_records,
        "redundant_research_calls": redundant,
        "n8n_executions": n_records,
        "n8n_budget_month": N8N_EXECUTION_BUDGET_MONTH,
        "lusha_credits": 0,
        "lusha_credits_note": "D-08: web research only, no provider waterfall -- zero Lusha credits drawn.",
        "anthropic_estimate_usd": round(n_records * ANTHROPIC_PER_RECORD_ESTIMATE_USD, 4),
        "anthropic_estimate_note": (...),
    }

def refuse_if_over_budget(estimate: dict, ids):
    """D-03: refuse rather than truncate. Returns `ids` UNMODIFIED when the projected
    n8n_executions stays within n8n_budget_month; raises BudgetRefused otherwise."""
    if estimate["n8n_executions"] > estimate["n8n_budget_month"]:
        raise BudgetRefused(...)
    return ids
```
`refuse_if_over_budget()` IS reusable unmodified — it only reads
`estimate["n8n_executions"]`/`estimate["n8n_budget_month"]`. Write a phase-local
`estimate_phase48_cost(research_ids, written_ids)` returning the same dict shape but
charging `n8n_executions = len(written_ids)` (D-09 recompute POSTs only — Racing NSW's
research is a direct Anthropic call, zero n8n executions) and
`web_research_calls = len(research_ids)` (expected 1). Import
`ANTHROPIC_PER_RECORD_ESTIMATE_USD` and `N8N_EXECUTION_BUDGET_MONTH` from the analog rather
than re-declaring them.

**Two-key arm gate** (lines 249-252 pattern, name only — do not reuse the literal env-var
name `ALLOW_VETO_REMEDIATION`):
```python
def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() != "false"
    return (not dry_run) and os.getenv("ALLOW_VETO_REMEDIATION", "false").lower() == "true"
```
Phase 48 needs its own name, e.g. `ALLOW_ENRICH_COVERAGE`, same two-key shape
(`DRY_RUN=false AND ALLOW_ENRICH_COVERAGE=true`).

**`verify_post_run` settle-and-assert idiom** (lines ~700+) — reuse directly for the D-09
before/after read-back; do not write a parallel poller.

### `tests/test_<new_module>.py` (new pytest)

**Analog:** `tests/test_veto_remediation_report.py` (offline, network-refusing style)

```python
"""tests/test_veto_remediation_report.py

... offline tests for scripts/veto_remediation_report.py. No network calls anywhere in
this module -- every test either monkeypatches requests.post to raise, injects a fake
reader/lister, or exercises pure functions.
"""
import ast
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*` imports resolve

import scripts.veto_remediation_report as m  # noqa: E402
import scripts.remediate_veto_companies as rvc  # noqa: E402

PINNED_ID = "9604732797"  # Tweed Valley Jockey Club -- first in PINNED_COMPANY_ID_ORDER

def _refuse_network(*_a, **_kw):
    raise AssertionError("no network call should be made in this test")

def test_snapshot_is_pure_read_and_completes_with_requests_post_raising(monkeypatch):
    monkeypatch.setattr("requests.post", _refuse_network)

    def _fake_reader(object_type, record_id, properties):
        assert object_type == "companies"
        return {"id": record_id, "properties": {p: f"{record_id}-{p}" for p in properties}}

    rows = m.snapshot([PINNED_ID], reader=_fake_reader)
    ...
```

Phase 48's new test file should mirror this exactly: `monkeypatch.setattr("requests.post",
_refuse_network)` at the top of every test that must never hit the network, a fake
`reader=` injected into any HubSpot-reading function, and named test ids
(`RACING_NSW_ID = "15008671672"`, `EDITIX_ID = "17317381378"`, etc., mirroring
`PINNED_ID = "9604732797"  # <comment naming the company>`). Cover: (1) the 4-record
offline mapping (assert each of the CONTEXT.md table's outputs against a fixture loaded
from `47-RESEARCH-RESULTS.json`), (2) the Editix `unknown`+reason marker distinguishable
from blank, (3) `estimate_phase48_cost()`'s dict shape, (4) `refuse_if_over_budget()`
raising on a synthetic over-budget dict.

### `scripts/build_cloud_workflows.py` (MODIFIED — D-04 gate)

**Analog:** same file, `_if_bool_expr_node` builder (lines 2977-2997) + `_http_node`
(lines 3337-3360) + the `IF Company Recompute`/`IF Company Skip` gate-with-failure-branch
idiom (lines ~4680-4700, 5055-5090, built Phase 47.5).

**Builder to reuse verbatim:**
```python
def _if_bool_expr_node(name, expr, x, y):
    """IF node testing an arbitrary boolean n8n EXPRESSION (not just a bare `$json.<field>`
    lookup) for `true`. ... never bare $json [when upstream includes an HTTP hop that may
    have replaced it]."""
    return {
        "parameters": {"options": {}, "conditions": {
            "options": {"caseSensitive": True, "typeValidation": "strict"},
            "combinator": "and",
            "conditions": [{
                "id": nid("i"),
                "leftValue": "={{ " + expr + " }}",
                "rightValue": True,
                "operator": {"type": "boolean", "operation": "equals"},
            }],
        }},
        "id": nid("if"), "name": name,
        "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [x, y],
    }
```

**Existing `Claude Web Research` node build (unchanged, do not re-emit — insert after it)**
(lines 4770-4775):
```python
nodes.append(_http_node(
    "Claude Web Research", "https://api.anthropic.com/v1/messages", csx, cy - 180,
    auth="header",
    headers=[{"name": "anthropic-version", "value": "2023-06-01"},
             {"name": "content-type", "value": "application/json"}],
    json_body="={{ JSON.stringify($json.research_request_body) }}"))
```
`_http_node`'s default `on_error="continueRegularOutput"` is WHY the gate is needed
(docstring, lines 3337-3356): "A WRITE node deliberately does NOT get
continueRegularOutput ... A failed write must fail the execution instead" — `Claude Web
Research` is a READ/research call, so it correctly keeps the default, meaning the 400
survives as data on `$json.error` for exactly one downstream hop.

**The gate-with-failure-branch idiom to copy** (Phase 47.5, lines ~4680-4700 build +
5055-5090 wiring):
```python
nodes.append(_if_bool_expr_node(
    "IF Company Recompute",
    "$('Parse HubSpot Event').first().json.recompute === true",
    build_company_identity_x, crby,
))
nodes.append(_if_bool_expr_node(
    "IF Company Skip", '$json.action === "skip"', hs_co_search_x, crby,
))
...
conns["Company Gate"] = {"main": [[{"node": "IF Company Recompute", "type": "main", "index": 0}]]}
conns["IF Company Recompute"] = {"main": [
    [{"node": "Decide Company Action", "type": "main", "index": 0}],  # true
    [{"node": "IF Company Skip", "type": "main", "index": 0}],        # false
]}
conns["IF Company Skip"] = {"main": [
    [{"node": "Build Response", "type": "main", "index": 0}],          # true
    [{"node": "Build Company Requests", "type": "main", "index": 0}],  # false
]}
```
D-04's shape (per RESEARCH.md's "Corrected recommendation" — the true-lane cannot wire
directly to `Build Response` the way `IF Company Skip` does, because its input row is the
raw HTTP-node output with no `action`/`hs_object_id`/`gate` fields; a recovery Code node is
required first):
```python
nodes.append(_if_bool_expr_node(
    "IF Research Errored",
    "!!$json.error || !Array.isArray($json.content)",
    csx, cy - 180,
))
nodes.append(code_node("Build Research Failure Response", r"""
const preHttp = (function () {
  try { return $('Build Research Request').all(); } catch (e) { return []; }
})();
return $input.all().map((it, i) => {
  const row = (preHttp[i] && preHttp[i].json) || {};
  const message = (it.json && it.json.error && it.json.error.message) || 'research call failed';
  return { json: { ...row, action: "research_failed", gate: { reason: message } } };
});
""", csx, cy - 260))

conns["Claude Web Research"] = {"main": [[{"node": "IF Research Errored", "type": "main", "index": 0}]]}
conns["IF Research Errored"] = {"main": [
    [{"node": "Build Research Failure Response", "type": "main", "index": 0}],  # true: errored
    [{"node": "Validate Research Output", "type": "main", "index": 0}],         # false: unchanged
]}
conns["Build Research Failure Response"] = {"main": [[{"node": "Build Response", "type": "main", "index": 0}]]}
```
The recovery Code node's `$('Build Research Request').all()` idiom is copied from
`Validate Research Output`'s own pre-HTTP row recovery (`_enrich_validate_research_js`,
lines 2360-2362): `const preHttp = (function () { try { return $('Build Research
Request').all(); } catch (e) { return []; } })();` — same node name, same try/catch, same
purpose (recover identity fields an HTTP hop replaced).

**Trap NOT triggered here (do not add `nodeAll` for this specific gate):** `IF Research
Errored` reads bare `$json.error`/`$json.content`, which is correct per the same reasoning
`IF Company Skip`'s own comment states for its bare `$json.action` read (lines
4686-4688): "correct HERE and only here: its immediate upstream is a Code node, with no
HTTP hop in between that could have replaced the item" — for `IF Research Errored` the
immediate upstream IS the HTTP node, so a bare `$json` read is exactly right, no `nodeAll`
needed. If any OTHER new code in this phase adds a `$()` node-name lookup on a shared code
path, use the repo's `nodeAll` idiom instead:
```javascript
function nodeAll(name) { try { return $(name).all(); } catch (e) { return []; } }
```

### `tests/n8n/researchErrorGateFlow.test.mjs` (new)

**Analog:** `tests/n8n/companyRecomputeLaneFlow.test.mjs` — full pattern to copy.

```javascript
// Phase 47.5 Plan 01 -- regression guard for the REQUEST-LEVEL RECOMPUTE LANE.
// ...
// This test drives the ACTUAL emitted jsCode of the committed workflow across the hop
// sequence with faked `$()` node lookups (the researchChainRowFlow.test.mjs template), AND
// evaluates the two IF nodes' real leftValue expressions against the same context -- an IF
// node carries no jsCode, so without that the test would assume the routing it exists to
// pin.
//
// NOTE: this executes the repo's OWN committed workflow jsCode/expressions via
// `new Function` -- the same thing n8n does at runtime -- over a fixed, in-repo list of
// node names. No external or untrusted input is ever interpolated into the function body.
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const WF_PATH = path.join(ROOT, "n8n", "wf_enrichment_cloud.json");

function loadWorkflow() {
  const wf = JSON.parse(fs.readFileSync(WF_PATH, "utf8"));
  const byName = {};
  for (const n of wf.nodes) byName[n.name] = n;
  return { wf, byName };
}

function makeCtx(current, outputs) {
  const $ = (name) => {
    const rows = () => (outputs[name] || []).map((j) => ({ json: j }));
    return {
      all: rows,
      first: () => rows()[0],
      get item() { return rows()[0]; },
    };
  };
  const $input = { ... };
  ...
}
```
Phase 48's new file: load `wf_enrichment_cloud.json`, find the `IF Research Errored` node
by name, extract its real `leftValue` (`"={{ !!$json.error || !Array.isArray($json.content) }}"`),
strip the `={{ ... }}` wrapper, and evaluate it via `new Function("$json", "return (" +
expr + ")")({error: {...}})` against BOTH a genuine `{error: {...}}` shape (from the folded
todo's quoted live payload) and a healthy `{content: [...]}` shape — asserting true/false
respectively. Also assert `Build Research Failure Response`'s jsCode recovers `preHttp` and
sets `action: "research_failed"` by running its actual `jsCode` string through the same
`makeCtx`/faked-`$()` harness. Do not hand-copy the expression as a string literal in the
test — evaluate the real one, per RESEARCH.md's explicit instruction.

### `src/web_research.py` (possibly MODIFIED)

**Current `RESEARCH_SYSTEM` (lines 27-54)** — the open-string `lv_org_type` schema field
that is the root of Phase 47's whole "free text can't be mapped" problem:
```python
# Phase 13: kept in parity with the production n8n research prompt (Task 3 point 4) ...
RESEARCH_SYSTEM = (
    "You are an ICP research analyst. Use web search to research the company across three "
    "query intents: identity (<name> <domain> about), content (<name> watch live | broadcast "
    "| streaming), and size (<name> annual report revenue -- only when a revenue band is not "
    "already known). Then return ONLY a single JSON object (no prose, no markdown fences) "
    "matching this schema:\n"
    '{"provider":"claude_web","object_type":"companies","matched":<bool>,'
    '"confidence":<int 0-100>,"data":{"lv_org_type":<str>,"lv_produces_content":<bool|null>,'
    ...
    "Prefer \"unknown\"/null over guessing -- an absent search result is NOT evidence of "
    "absence. Cite a supporting URL in evidence_by_field for every field you set in data ..."
)
```
Note this is a DIFFERENT (newer, richer, `entity_resolution`-carrying) shape than the
`ProviderResult`-flat shape in `47-RESEARCH-RESULTS.json`'s captured fixtures — confirm the
Racing NSW call's actual output shape against whichever `claude_web_research()` call path
Phase 48 wires up, not against the older captured JSON's shape.

**`claude_web_research()` contract (unchanged call surface)** — call it as-is for Racing
NSW; per RESEARCH.md's recommendation, prefer option (b): a narrower one-off prompt
(new module-level constant, e.g. `RACING_NSW_ORG_TYPE_SYSTEM`, or an inline system-prompt
override parameter) that enum-constrains `lv_org_type` to the 9 `VALID_ORG_TYPES`, leaving
the shared/production `RESEARCH_SYSTEM` untouched (it's parity-tracked against the n8n
prompt and used by every other caller). If editing `RESEARCH_SYSTEM` directly is chosen
instead, replace the open `"lv_org_type":<str>` fragment with an explicit enum literal and
add an "answer unknown rather than invent a value outside this set" sentence, mirroring the
existing "Prefer unknown/null over guessing" sentence already present.

### `n8n/code/webResearch.js` (READ ONLY — not modified this phase)

**`researchCandidateFromHttpItem` (lines 154-188)** — confirms this already guards
`item.error`:
```javascript
function researchCandidateFromHttpItem(item) {
  try {
    if (!item || item.error || !Array.isArray(item.content)) {
      return _unmatchedCandidate();
    }
    const parsed = extractFinalJson(item.content);
    const candidate = toProviderResult(parsed);
    ...
  } catch (e) {
    return _unmatchedCandidate();
  }
}
```
This function already turns an error-shaped item into `matched:false, confidence:0` rather
than parsing the error as data — so D-04's gate is a DEFENSE-IN-DEPTH addition (stop the
error before it even reaches this function and the merge chain), not a fix to a bug in this
function itself. Do not modify this file this phase; its existing guard is correct and
`IF Research Errored` sits upstream of it.

## Shared Patterns

### "Estimate produced by code, not prose"
**Source:** `scripts/remediate_veto_companies.py:estimate_cost()` + `.planning/phases/47-veto-remediation/47-COST-ESTIMATE.md`
**Apply to:** `48-COST-ESTIMATE.md`
```
This document's projected figures are produced by, and must agree with, `estimate_cost()`
in `scripts/remediate_veto_companies.py` ... The numbers below were read directly from a
live call to that function against the 17 pinned IDs, not hand-derived separately -- the
two can never silently drift apart.

$ .venv/bin/python -c "
import scripts.remediate_veto_companies as m
print(m.estimate_cost(m.PINNED_COMPANY_ID_ORDER))
"
{'web_research_calls': 17, 'redundant_research_calls': 4, 'n8n_executions': 17, ...}
```
`48-COST-ESTIMATE.md` should be generated the same way against `estimate_phase48_cost()`.

### "Refuse outright, never truncate"
**Source:** `scripts/remediate_veto_companies.py:refuse_if_over_budget()`
**Apply to:** the new driver's pre-write gate, exercised by a unit test asserting it raises
on a synthetic over-budget dict (COVER-02's literal requirement that refusal is *possible*).

### Two-key operator arm, per-shell, never defaulted true
**Source:** `scripts/remediate_veto_companies.py` `_writes_allowed()` / `NotArmedError` /
`post_webhook_event`'s `armed` parameter with no default.
**Apply to:** the new driver's own HubSpot-PATCH leg AND separately to
`scripts/june_run_arm.py --ids <5 comma-separated ids>` for the n8n-side allowlist — TWO
independent surfaces, both must be armed for D-09's `HubSpot Company Update` leg to
actually write (RESEARCH.md "Anti-Patterns to Avoid" — do not conflate them).

### Dated amendment blocks for correcting a LOCKED decision file
**Source:** the existing dated correction block at the top of
`.planning/decisions/2026-08-12-org-type-venue-and-normalization.md`
**Apply to:** D-02's amendment recording that the venue option was examined and not spent —
add a new dated block, never edit the original text in place.

### `nodeAll` try/catch, fail closed
**Source:** `scripts/build_cloud_workflows.py`, multiple sites (e.g. lines 1403, 1920)
```javascript
function nodeAll(name) { try { return $(name).all(); } catch (e) { return []; } }
```
**Apply to:** any NEW `$()` node-name lookup this phase adds to a workflow-shared code path
(`ENRICH_CO_GATE` is shared by three built workflows). D-04's own `IF Research Errored`
does not need this (bare `$json` is correct there), but if implementation drifts toward a
node-name lookup anywhere, use this idiom.

## No Analog Found

None — every file this phase touches has a strong, explicitly-named analog already
identified by CONTEXT.md/RESEARCH.md's own research pass.

## Metadata

**Analog search scope:** `scripts/`, `tests/`, `tests/n8n/`, `src/`, `n8n/code/`,
`.planning/phases/47-veto-remediation/`, `.planning/phases/47.5-veto-recompute-path/` —
all read this session or in the upstream RESEARCH.md pass this session also consumed.
**Files scanned:** `scripts/remediate_veto_companies.py` (full, 1045 lines),
`scripts/build_cloud_workflows.py` (targeted: builder functions, gate idiom, HTTP node
build/wiring), `src/web_research.py` (full), `n8n/code/webResearch.js` (targeted, 150-200),
`tests/test_veto_remediation_report.py` (targeted header + first test),
`tests/n8n/companyRecomputeLaneFlow.test.mjs` (targeted header + harness),
`47-COST-ESTIMATE.md`, `47.5-RUN-REPORT.md` (targeted headers/shape).
**Pattern extraction date:** 2026-08-12
