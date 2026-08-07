# Phase 40: Scoring Engine, Veto & Parity Remediation - Pattern Map

**Mapped:** 2026-08-06
**Files analyzed:** 8
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `n8n/code/mergeCompanies.js` (D-04: raise `min_confidence: 0` → ~80 on `veto_output` entries) | transform/policy | CRUD (merge decision) | itself (edit in place) | exact |
| `scripts/build_cloud_workflows.py` — `ENRICH_DECIDE_CO_CLOUD` (D-01: add veto-derivation pure function) | transform (Code-node wrapper) | request-response (n8n Code node) | itself (edit in place); shape mirrors `ENRICH_MERGE_CO`'s two-`mergeCompanies()`-call fold pattern just above it | exact |
| `src/hubspot_client.py` — add `batch_update_companies()` | service/client | CRUD (HTTP write) | `patch_record()` / `create_record()` / `delete_record()` in the same file | exact |
| `scripts/fetch_hubspot_flow.py` (new — D-05 GET+strip+archive) | utility/script | file-I/O (GET → repo JSON) | `scripts/snapshot_hubspot_schema.py` | exact |
| `scripts/put_hubspot_flow.py` or inline session commands (D-05/D-08 PUT round-trip) | utility/script | request-response (live API mutation) | `scripts/probe_scoring_recalc_latency.py` (two-key gate, disposable-company validate, guaranteed teardown) | role-match |
| `scripts/backfill_seed_company_scores.py` (new — D-10 batch component seed) | utility/script | batch (batch PATCH) | `scripts/probe_scoring_recalc_latency.py` (dry_run/live gate, disposable-company pattern) + new `batch_update_companies()` | role-match |
| `tests/test_scoring_parity.py` (new — D-11/D-12/D-13, PARITY-01/02) | test | request-response (opt-in live) | `tests/test_icp_scoring.py` (oracle usage, `HubSpotRecord`/`compute_icp_score` shape) + `tests/test_cloud_companies_branch.py` (n8n-branch-shape live/offline split) | exact (oracle) + role-match (live-gating) |
| `scripts/run_scoring_parity.py` (new — D-11 thin sweep wrapper) | utility/script | batch (report) | `scripts/snapshot_hubspot_schema.py` (env-gated read + JSON artifact to disk) | role-match |

## Pattern Assignments

### `n8n/code/mergeCompanies.js` (transform/policy, CRUD)

**Analog:** itself — `DEFAULT_COMPANY_POLICY` block, already read in full.

**Core pattern to copy** (current state, lines ~33-59):
```js
const DEFAULT_COMPANY_POLICY = {
  ...
  lv_anti_icp_flag:        { class: "veto_output",       min_confidence: 0 },
  lv_anti_icp_reason:      { class: "veto_output",       min_confidence: 0 },
};
```
D-04 fix: raise `min_confidence: 0` to a real threshold (~80, discretion) on both entries.
This is dead-policy hardening only (PIPELINE-DEFECTS-VALIDATION.md P2's own recommendation)
— these two entries are never live inputs to `mergeCompanies()` after D-01/Pattern 2 moves
the actual veto write to `ENRICH_DECIDE_CO_CLOUD`. Match the existing comment style (see
`lv_country_region_normalized`'s inline threshold-rationale comment a few lines up) when
explaining why 80, not just changing the number silently.

---

### `scripts/build_cloud_workflows.py` — `ENRICH_DECIDE_CO_CLOUD` (transform, request-response)

**Analog:** itself — the immediately-preceding `ENRICH_MERGE_CO` two-call-fold block (already
read, ~lines 2452-2501) is the closest in-file precedent for "derive a field from other
already-merged fields and splice it into `properties`/`canonicalPatch` without touching
`mergeCompanies()`'s policy machinery."

**Core pattern to copy** (RESEARCH.md Pattern 2, verbatim, insertion point: inside
`ENRICH_DECIDE_CO_CLOUD`, after `properties` is built ~line 2601, before the `needsReview`
branch ~line 2603):
```js
function _regionKey(v) {
  return (v === "AU" || v === "NZ" || v === "ANZ") ? v : "non_anz";
}
function _boolish(v) {
  if (typeof v === "boolean") return v;
  if (v === "true") return true;
  if (v === "false") return false;
  return null;
}
const existing = row.existingRecord || {};
const region = _regionKey(properties.lv_country_region_normalized ?? existing.lv_country_region_normalized);
const producesContent = _boolish(properties.lv_produces_content ?? existing.lv_produces_content);
const isHardwareVendor = _boolish(properties.lv_is_hardware_vendor ?? existing.lv_is_hardware_vendor);

const reasons = [];
if (region === "non_anz") reasons.push("Non-ANZ geography");
if (producesContent === false) reasons.push("No broadcast or streaming content");
if (isHardwareVendor === true) reasons.push("Hardware/AV/LED vendor, not sports-media buyer");

properties.lv_anti_icp_flag = reasons.length > 0 ? "true" : "false";
properties.lv_anti_icp_reason = reasons.length > 0 ? reasons.join("; ") : "";
```
This is a direct JS port of `src/icp_scoring.py:84-97`'s hard-veto block (see below) — keep
the field names and reason strings byte-identical to the oracle, since PARITY-01/02 assert
against it. **Do not** add these two fields to `ENRICH_MERGE_CO`'s candidate lists at
scripts/build_cloud_workflows.py:2445/2473 (Pitfall 4 — wrong insertion point, that policy
class expects a provider-supplied candidate, not a same-row derivation).

**Reference oracle to port from** — `src/icp_scoring.py` lines 84-97 (already read):
```python
anti_icp_flag = False
anti_reasons = []

if region_key == "non_anz":
    anti_icp_flag = True
    anti_reasons.append(cfg["hard_vetoes"]["non_anz"]["reason"])

if produces_content is False:
    anti_icp_flag = True
    anti_reasons.append(cfg["hard_vetoes"]["no_content"]["reason"])

if is_hardware_vendor:
    anti_icp_flag = True
    anti_reasons.append(cfg["hard_vetoes"]["hardware_vendor"]["reason"])
```
Reason strings are pulled from `config/icp_scoring.yaml` `hard_vetoes.*.reason` — confirm
exact text there before hardcoding (RESEARCH.md already quotes them: "Non-ANZ geography",
"No broadcast or streaming content", "Hardware/AV/LED vendor, not sports-media buyer").

**Bool→string coercion pattern (D-04)** — matches the precedent named in CONTEXT.md/RESEARCH.md:
`.planning/workstreams/plugin-entrypoint/phases/36-enrichment-propose-mode/36-07-SUMMARY.md`
(the `lv_enrichment_requested` boolean→string EQ-filter fix). Same shape: assign the string
literal `"true"`/`"false"`, never a bare JS boolean, into a `properties` object that becomes
a HubSpot PATCH payload.

---

### `src/hubspot_client.py` — new `batch_update_companies()` (service, CRUD)

**Analog:** `patch_record()` / `create_record()` / `delete_record()`, same file, already read
in full.

**Imports pattern** (top of file, lines 1-4):
```python
import os
import json
import requests

BASE_URL = "https://api.hubapi.com"
```

**dry_run-first pattern to copy** (from `create_record`, lines 43-61 — the closest shape,
since this is also a POST):
```python
def batch_update_companies(updates: list[dict], dry_run=True):
    # updates: [{"id": "789", "properties": {"org_type_score": 40, ...}}, ...]
    payload = {"inputs": updates}

    if dry_run:
        print(json.dumps({
            "dry_run": True,
            "method": "POST",
            "url": f"{BASE_URL}/crm/v3/objects/companies/batch/update",
            "payload": payload
        }, indent=2, default=str))
        return {"dry_run": True, "payload": payload}

    url = f"{BASE_URL}/crm/v3/objects/companies/batch/update"
    r = requests.post(url, headers=hs_headers(), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()
```
Note the existing file's convention: every write function prints only the payload dict
(never `hs_headers()`/token) and returns a `{"dry_run": True, ...}` sentinel before any
network call — replicate exactly, do not invent a new sentinel shape.

---

### `scripts/fetch_hubspot_flow.py` (new — utility, file-I/O)

**Analog:** `scripts/snapshot_hubspot_schema.py` (already read, lines 1-60 + full-file
structure via `wc -l`/imports).

**Imports + path-setup pattern** (lines 1-26):
```python
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

BASELINE_DIR = ROOT / "config" / "hubspot_migration" / "baseline"
```
For this phase, mirror this exactly but target `config/hubspot_flows/` (RESEARCH.md's
recommended storage location) instead of `config/hubspot_migration/baseline/`.

**Portal-guard pattern** (lines 27-31, and `_portal_ok()` a few lines below):
```python
EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))

def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID
```
Apply the same guard before any `GET /automation/v4/flows/{id}` call — this repo's
established discipline (also present in `probe_scoring_recalc_latency.py`'s
`EXPECTED_PORTAL_ID` constant) is "assert portal before any call, never mid-batch."

**GET-and-archive core pattern** — no exact existing analog for flow-specific GET (schema
snapshot uses the properties API, not automation/v4), but the shape is the same: fetch,
strip volatile fields, write JSON verbatim to a versioned repo path with before/after
naming. Use `requests.get(f"{BASE_URL}/automation/v4/flows/{flow_id}", headers=hs_headers(), timeout=30).json()`
then `for k in ("createdAt", "updatedAt", "dataSources"): flow.pop(k, None)` per
RESEARCH.md Pattern 1 (already cross-checked against the official API guide this session).

---

### PUT round-trip / disable-edit-validate-reenable (D-05/D-07/D-08)

**Analog:** `scripts/probe_scoring_recalc_latency.py` (already read in full structurally;
`wc -l` = 318 lines).

**Two-key arm + disposable-company + guaranteed-teardown pattern** (docstring lines 14-16 +
module constants lines 44-52):
```python
# Two-key arming: DRY_RUN=false AND ALLOW_HUBSPOT_SCORING_PROBE=true (a phase-scoped flag,
# deliberately distinct from the generic property-writes flag a migration script might
# leave armed). Touches exactly one disposable `ZZ-SCORING-TEST-DELETE-ME-*` company and
# deletes it on teardown, guaranteed even on exception or interrupt.

EXPECTED_PORTAL_ID = "22617666"
COMPANY_NAME_PREFIX = "ZZ-SCORING-TEST-DELETE-ME-"
```
D-08 explicitly departs from this convention for the flow PUTs themselves (Claude executes
in-session, no script gate) — but the disposable-company create/validate/delete lifecycle
this script uses (via `src/hubspot_client.py`'s `create_record`/`delete_record`, imported
lines 34-40) is still the correct validation vehicle per D-07, and any backfill/parity
script this phase adds should still follow the two-key + guaranteed-teardown shape for its
own live writes.

---

### `scripts/backfill_seed_company_scores.py` (new — utility, batch)

**Analog:** `scripts/probe_scoring_recalc_latency.py` for the dry_run/live gate + disposable
pattern; `batch_update_companies()` (new, above) for the actual write call.

**Core pattern:**
```python
# ponytail: compute each component score from the record's OWN current inputs (0 where
# missing) — no cross-record logic, no new scoring rubric duplicated here. Mirrors
# PROPERTY_DEFAULT_VALUE's existing 0-stamp behavior (HANDOVER §10.1).
updates = [
    {"id": company_id, "properties": {
        "org_type_score": ...,
        "geography_score": ...,
        "annual_revenue_score": ...,
        "produces_content_score": ...,
    }}
    for company_id in sample
]
batch_update_companies(updates, dry_run=dry_run)
```
Reuse `src/icp_scoring.py`'s `cfg["base_score"]` YAML-loaded point tables (already read,
lines 70-97 region) as the single source of point values — do not hand-roll a second point
table in this script (RESEARCH.md's "Don't Hand-Roll" table calls this out explicitly).

---

### `tests/test_scoring_parity.py` (new — test, request-response)

**Analog:** `tests/test_icp_scoring.py` (already read in full, 180 lines) for oracle usage
shape; `tests/test_cloud_companies_branch.py` (239 lines, role-match for live/offline test
split conventions in this repo — not re-read line-by-line here since RESEARCH.md's Code
Examples section already supplies the exact sketch).

**Oracle-call pattern to copy** (`tests/test_icp_scoring.py` lines 1-27):
```python
from src.schemas import HubSpotRecord
from src.icp_scoring import compute_icp_score


def score(patch):
    record = HubSpotRecord(object_type="companies", id="789", properties={})
    return compute_icp_score(record, patch)
```

**Live-gating pattern (D-11/A3 — env-var skipif, no new pytest marker/config needed since
none exists in this repo)** — from RESEARCH.md Code Examples, cross-checked against this
session's own file reads (no `pytest.ini`/`[tool:pytest]` found):
```python
import os
import pytest
from src.hubspot_client import get_record

live = pytest.mark.skipif(
    os.getenv("RUN_LIVE_PARITY") != "true",
    reason="opt-in: set RUN_LIVE_PARITY=true to hit the live HubSpot portal",
)

FIT_SCORE_PROPS = [
    "lv_org_type", "lv_produces_content", "lv_country_region_normalized",
    "lv_revenue_band", "lv_is_gambling_operator", "lv_is_hardware_vendor",
    "lv_icp_fit_score", "lv_icp_tier", "lv_anti_icp_flag", "lv_anti_icp_reason",
]

def fetch_for_parity(company_id: str) -> dict:
    return get_record("companies", company_id, FIT_SCORE_PROPS)["properties"]

@live
def test_parity_real_record_sample(real_company_ids):
    for cid in real_company_ids:
        props = fetch_for_parity(cid)
        record = HubSpotRecord(object_type="companies", id=cid, properties=props)
        expected = compute_icp_score(record, {})
        assert str(props.get("lv_icp_fit_score")) == str(expected.score)
        assert props.get("lv_icp_tier") == expected.tier
```
Name test functions per RESEARCH.md's Validation Architecture test map so `-k` selectors
work: `f8_sub15`, `veto_set`, `veto_clear`, `tier_on_flag_change`, `revenue_boundary`,
`org_type_sweep`, `f4_or_f7_or_f9_or_f10` (PARITY-02's named regression cases).

---

### `scripts/run_scoring_parity.py` (new — utility, batch)

**Analog:** `scripts/snapshot_hubspot_schema.py` (env-gated read, writes a JSON artifact to
a versioned repo path, safe-without-credentials default mode).

**Core pattern:** thin wrapper — no independent logic beyond invoking the same
`compute_icp_score`/`fetch_for_parity` pair `tests/test_scoring_parity.py` uses, on the
read-only real-record sample (D-12's scheduled cadence), writing a JSON verdict report the
same way `snapshot_hubspot_schema.py` writes its baseline snapshot to disk (`json.dump` to
a `.planning`/`config` path with a datestamp in the filename).

## Shared Patterns

### dry_run-first / two-key write gating
**Source:** `src/hubspot_client.py` (`patch_record`, `create_record`, `delete_record` — all
three follow the identical `if dry_run: print(...); return {"dry_run": True, ...}` shape
before any network call) + `scripts/probe_scoring_recalc_latency.py` (two-key arm:
`DRY_RUN=false` AND a phase-scoped `ALLOW_*` flag).
**Apply to:** `batch_update_companies()`, the backfill seed script, and any live-write
script this phase adds (flow PUTs are the one deliberate exception, D-08).

### Portal guard before any live call
**Source:** `scripts/snapshot_hubspot_schema.py` (`EXPECTED_PORTAL_ID` + `_portal_ok()`) and
`scripts/probe_scoring_recalc_latency.py` (`EXPECTED_PORTAL_ID = "22617666"` module
constant, no env override).
**Apply to:** every new script in this phase that touches the live HubSpot API.

### Boolean → string coercion for HubSpot EQ filters
**Source:** `.planning/workstreams/plugin-entrypoint/phases/36-enrichment-propose-mode/36-07-SUMMARY.md`
(named precedent in CONTEXT.md/RESEARCH.md; the fix pattern is: assign the literal string
`"true"`/`"false"`, never a bare boolean, at the single point where a field enters
`properties`/`canonicalPatch`).
**Apply to:** `ENRICH_DECIDE_CO_CLOUD`'s new veto-derivation block (D-04).

### Disposable-company create/validate/delete lifecycle
**Source:** `scripts/probe_scoring_recalc_latency.py`'s `COMPANY_NAME_PREFIX =
"ZZ-SCORING-TEST-DELETE-ME-"` + `src/hubspot_client.py`'s `create_record`/`delete_record`
(guaranteed teardown, even on exception).
**Apply to:** D-07's flow-edit validation step, D-13's live veto-regression cases, and the
full-fixture tier of the parity harness (D-12).

## No Analog Found

None — every file this phase touches has a same-repo precedent of matching or adjacent role
and data flow (see table above). The two genuinely novel operations (`PUT
/automation/v4/flows/{id}` action-content edits, and `calculationFormula` PATCH on an
existing calculated property) are external-API unknowns, not missing internal patterns —
RESEARCH.md's Pitfalls 2/3 cover the risk; no in-repo code performs either operation today,
so those two specific sub-steps proceed from the official-docs pattern (RESEARCH.md
Architecture Patterns Pattern 1) rather than a codebase analog.

## Metadata

**Analog search scope:** `n8n/code/`, `scripts/`, `src/`, `tests/` (all files named in
CONTEXT.md/RESEARCH.md's Reusable Assets and Integration Points sections).
**Files scanned:** 8 target files against 6 analog files (`mergeCompanies.js`,
`build_cloud_workflows.py`, `hubspot_client.py`, `snapshot_hubspot_schema.py`,
`probe_scoring_recalc_latency.py`, `test_icp_scoring.py`), plus `icp_scoring.py` as the
oracle reference all veto/scoring ports must match verbatim.
**Pattern extraction date:** 2026-08-06
