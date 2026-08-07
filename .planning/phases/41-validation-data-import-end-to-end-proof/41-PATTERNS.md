# Phase 41: Validation Data Import & End-to-End Proof - Pattern Map

**Mapped:** 2026-08-07
**Files analyzed:** 6 net-new artifacts (per RESEARCH.md Wave 0 gaps + locked decisions)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `scripts/build_june_candidates.py` (candidate-table builder) | transform/utility | batch, file-I/O | `config/taxonomy.yaml` (vocabulary) + `src/normalizer.py` (normalize→candidate shape, local-MVP lane, historical) | role-match (no direct script analog; taxonomy is the vocabulary source, normalizer.py the closest transform shape) |
| Pre-flight HubSpot ID resolver (new script) | utility, request-response | batch | `src/hubspot_client.py` (`get_record`, `search_records`) | role-match, no batch-ID-resolution helper exists (RESEARCH.md Pitfall 5) |
| June pseudo-provider adapter/injection | service/adapter | event-driven (merge candidate) | `n8n/code/mergeCompanies.js`'s waterfall→claude_web second-call fold (`scripts/build_cloud_workflows.py:2452-2500`) — cloud lane, NOT `src/providers.py` | role-match; `src/providers.py`/`ProviderResult` is the **superseded local-MVP** shape (RESEARCH.md State of the Art) — do not pattern-match against it for the write path itself, only for naming/registry conventions |
| Run-report writer | utility, file-I/O | batch | `scripts/run_scoring_parity.py` (JSON verdict writer) + `docs/reports/*.md` dated convention | exact (verdict-JSON shape) + exact (dated markdown convention) |
| Provenance assertion in parity path | test/assertion | request-response | `tests/scoring_fixtures.py::expected_for` + `scripts/run_scoring_parity.py`'s per-record check loop | exact |
| Arm/disarm sequence for whole run | orchestration script (operator-facing) | event-driven, batch | `operator-claude-plugin/scripts/n8n_arming.py` (`arm_for_dispatch`/`disarm`) + `scheduled_arm.py` (docstring precedent, NOT the code path) | role-match; scheduled_arm.py binds arm→dispatch→disarm, this phase needs the two calls **unpaired** |

## Pattern Assignments

### 1. `scripts/build_june_candidates.py` (June-dataset → candidate-table builder)

**Analog:** `config/taxonomy.yaml` (vocabulary source of truth) — no existing script reads an external sibling-repo JSON and emits a normalized row set, so the closest *code shape* analog is the local-MVP `src/normalizer.py`'s `normalize_field`/`provider_to_candidates` pattern (historical design, RESEARCH.md flags as superseded for the write path, but the **shape** — map raw provider value → per-field normalized candidate dict — is still the right shape for a standalone script that just builds a table, independent of which lane consumes it).

**Vocabulary to map into** (`config/taxonomy.yaml:1-40`, NORMATIVE — never hand-invent enum values):
```yaml
# Source: config/taxonomy.yaml:22-40
# TO ADD A VALUE: edit this file -> rebuild workflows -> run the HubSpot property sync ->
# run the conformance suite. Never edit a node.
org_types:
  governing_body_league:
    score: 40
    requires_evidence: true
    synonyms:
      - league
      - governing body
      - peak body
      - racing authority
      - sporting authority
  regulator:
    score: 5
    requires_evidence: false
    synonyms:
      - regulatory body
      - regulator authority
      - commission
      - integrity body
```
`tests/test_taxonomy_conformance.py` enforces every derived representation agrees with this file — the builder script must emit exactly these `lv_org_type` string values, nothing invented.

**Transform shape to copy** (local-MVP normalizer — historical but structurally right for a standalone mapping script):
```python
# Source: src/normalizer.py (normalize_field / provider_to_candidates pattern)
def normalize_field(field: str, value):
    # field-specific branches: bool coercion, revenue/employee band bucketing,
    # country-region normalization, else plain text normalize
    ...

def provider_to_candidates(result):
    # iterate result.data.items(), skip None/"", emit one normalized row per field
    ...
```
The June builder should follow the same shape — read `enriched_companies.json` once, iterate 66 records, apply D-02's deterministic enum table (Perplexity `org_type` → `lv_org_type`) plus the hand-curated exception list, apply D-03's confidence mapping (high/medium/low → 85/65/40), and emit one row per company with `lv_org_type`, `lv_produces_content`, `lv_sponsorship_reliant`, `lv_country_region_normalized`, and (per RESEARCH.md Pitfall 2) a best-effort `lv_employee_band` from `employee_estimate` with an explicit documented rounding rule — no `lv_revenue_band` (source has no revenue field at all).

**Exception-list precedent** (QRIC, verbatim reusable signal):
```yaml
# Source: config/taxonomy.yaml:75-80 — "commission"/"integrity body" synonyms already
# match "Queensland Racing Integrity Commission"'s name text directly, corroborated by
# n8n/code/judge.js:15's own QRIC reference comment.
```

---

### 2. Pre-flight HubSpot ID resolver

**Analog:** `src/hubspot_client.py` (`get_record`, `search_records`) — no batch-by-ID helper exists (RESEARCH.md Pitfall 5); this is a new small script built directly on these two primitives.

**Imports/primitives pattern** (`src/hubspot_client.py:1-9, 15-21, 119-`):
```python
import os
import json
import requests

BASE_URL = "https://api.hubapi.com"

def hs_headers():
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def get_record(object_type: str, record_id: str, properties: list[str]):
    url = f"{BASE_URL}/crm/v3/objects/{object_type}/{record_id}"
    params = {"properties": ",".join(properties)}
    r = requests.get(url, headers=hs_headers(), params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def search_records(object_type: str, filters: list[dict], properties: list[str], limit=100):
    url = f"{BASE_URL}/crm/v3/objects/{object_type}/search"
    # payload = {"filterGroups": [{"filters": filters}], "properties": properties, "limit": limit}
```

**Resolution strategy:** try `get_record("companies", id, [...])` per June ID first (404 → dead); for dead IDs, fall back to `search_records("companies", filters=[{"propertyName": "domain", "operator": "EQ", "value": ...}], ...)` or a name-based filter, per D-09. RESEARCH.md's Assumption A1 flags that a single `IN`-operator batch search is unverified against this wrapper's filter-building code — plan for sequential `get_record` calls as the safe default, batch search as an optimization if verified.

**Error-handling convention to match:** every `hubspot_client.py` function calls `r.raise_for_status()` un-wrapped — the resolver script should catch `requests.HTTPError` at the call site (per-ID) rather than adding new exception classes, consistent with the rest of the file's bare-`raise_for_status` style.

---

### 3. June pseudo-provider adapter / injection mechanics

**Analog (the ACTUAL write path — cloud lane):** `n8n/code/mergeCompanies.js`'s existing two-call fold pattern (`scripts/build_cloud_workflows.py:2452-2500`) — this is the concrete precedent for "inject a second candidate source" and directly answers RESEARCH.md's Open Question 1 / Pitfall 3: **yes**, the company lane already calls `mergeCompanies()` twice per record (once for the provider waterfall, once for claude_web research) and shallow-merges the two patches. A June pseudo-provider is a **third** `mergeCompanies()` call following the same shape, not new architecture.

**Core pattern to copy** (verbatim, the exact two-call fold this phase's third call should mirror):
```javascript
// Source: scripts/build_cloud_workflows.py:2452-2500
const merged = mergeCompanies(row.existingRecord || {}, candidate, undefined,
                              { source: "waterfall", confidence: 85 });

let finalMerge = merged;
const rc = row.research_candidate;
if (rc && rc.matched) {
  const researchData = {};
  for (const f of ["lv_org_type", "lv_produces_content", "lv_content_type",
                   "lv_is_hardware_vendor", "lv_is_gambling_operator",
                   "lv_sponsorship_reliant", "lv_country_region_normalized"]) {
    const v = rc.data && rc.data[f];
    if (v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0)) continue;
    researchData[f] = v;
  }
  if (Object.keys(researchData).length > 0) {
    const researchMerged = mergeCompanies(row.existingRecord || {}, researchData, undefined,
      { source: "claude_web", confidence: rc.confidence || 80, evidence: rc.evidence_by_field || {},
        confidenceByField: row.judge_confidence_by_field || {} });
    // shallow merge of both patches + concatenated decisions; last-spread-wins on the
    // one overlapping field (lv_country_region_normalized)
  }
}
```
```javascript
// Source: scripts/build_cloud_workflows.py:2430-2441 — the CONFLICT_WATCH diff pattern
// D-04's "route to needs_review on disagreement" should extend/mirror, not reinvent:
const conflicts = [];
for (const f of CONFLICT_WATCH) {
  const b = best[f];
  if (!b) continue;
  const others = (b.agreedBy || []).length;
  const sources = row.scored.sourcesByField && row.scored.sourcesByField[f];
  if (sources && sources.length > 1 && others === 0) {
    conflicts.push({ field: f, chosen: b.normalizedValue, chosen_source: b.source, candidates: sources });
  }
}
```
**Important — unresolved wiring gap the planner must decide (RESEARCH.md Pitfall 3/Open Question 1):** the existing `ponytail`-flagged comment at this call site explicitly says *"no cross-source conflict check here (that's CONFLICT_WATCH's job above, scoped to revenue/employee bands only)"* — CONFLICT_WATCH today does NOT cover `lv_org_type`/`lv_produces_content`, the two fields D-04 needs conflict routing on. The plan must either (a) extend `CONFLICT_WATCH`'s field list to include org_type/produces_content and add a third `mergeCompanies()` call for June alongside the two shown above, comparing June's normalized value against claude_web's before the merge, or (b) run June and fresh-research through `mergeCompanies` independently and diff the two `canonicalPatch` outputs as a separate step. Either is buildable on today's primitives; neither exists today — call this the wiring gap explicitly rather than assuming "the existing machinery adjudicates naturally."

**Naming/registry convention** (`config/source_registry.yaml:1-40` — for the June pseudo-provider's registry entry, if the plan wants one):
```yaml
# Source: config/source_registry.yaml — claude_web entry shape to mirror for "june_2026" or similar
claude_web:
  type: research
  trust_rank: 78
  can_promote_directly: false
  supported_signals:
    - org_type
    - content_output
    - sports_media_fit
    - sponsorship_reliance
    - gambling_operator
    - hardware_vendor
    - evidence_url
```
Note: `config/source_registry.yaml` is part of the **local-MVP** design (RESEARCH.md State of the Art table) — it is not read by the cloud pipeline's JS. If the plan keeps a registry entry for documentation/audit purposes, it's decorative for this phase, not load-bearing; the load-bearing convention is the `mergeCompanies({source: "...", confidence: N})` call-site shape above.

---

### 4. Run-report writer

**Analog (JSON verdict shape):** `scripts/run_scoring_parity.py`'s verdict-writing pattern — read-only, writes to `PARITY_REPORT_DIR`, has an explicit "zero assertions executed is a failure, not a pass" guard.
```python
# Source: scripts/run_scoring_parity.py:1-30 (docstring, verbatim contract)
# Env vars:
#     PARITY_SAMPLE_IDS  Comma-separated real company ids to check. If unset, ids are
#                         selected via a HAS_PROPERTY search on lv_icp_fit_score.
#     PARITY_REPORT_DIR  Directory the JSON verdict report is written to.
#
# The false-green guard is the point of this script, not a nicety (T-40-05). If
# `assertions_executed` is 0 ... the script exits non-zero with an explicit
# "zero assertions executed" verdict in the written report.
```
The run-report writer for D-12 (resolved/skipped IDs, mapped values, conflicts routed to review, per-record landing status) should follow the same shape: one JSON object per run, written to the phase directory, with an explicit non-zero-exit / "nothing processed" guard mirroring the false-green discipline above — not a silent empty report.

**Analog (dated-markdown convention):** `docs/reports/2026-07-17-dryrun-batch.md`, `docs/reports/2026-07-15-dry-run-gillon-mclachlan.md` — existing convention is `docs/reports/YYYY-MM-DD-<slug>.md`. If the run report gets a human-readable companion (not just the JSON verdict), follow this naming pattern and directory.

---

### 5. Provenance assertion in the parity path

**Analog:** `tests/scoring_fixtures.py::expected_for` + `scripts/run_scoring_parity.py`'s existing per-record check loop.
```python
# Source: tests/scoring_fixtures.py:63-68
def expected_for(props: dict):
    """The oracle's opinion of a property dict. One function, used by both
    tests/test_scoring_parity.py and scripts/run_scoring_parity.py (D-11)."""
    record = HubSpotRecord(object_type="companies", id="0", properties=props)
    return compute_icp_score(record, {})
```
```python
# Source: tests/scoring_fixtures.py:37-59 — FIT_SCORE_PROPS is the read-list the parity
# harness fetches; a provenance check needs lv_enrichment_provenance added to this list
# (it is NOT currently read):
FIT_SCORE_PROPS = [
    "lv_org_type", "lv_produces_content", "lv_country_region_normalized",
    "lv_revenue_band", "lv_is_gambling_operator", "lv_is_hardware_vendor",
    "org_type_score", "geography_score", "annual_revenue_score",
    "produces_content_score", "gambling_score",
    "lv_icp_fit_score", "lv_icp_tier", "lv_anti_icp_flag", "lv_anti_icp_reason",
]
```
The addition is small and additive, matching house style: (1) add `lv_enrichment_provenance` (and the two `*_verified_at` cache keys per RESEARCH.md's provenance-shape finding, `config/hubspot_properties.yaml:192-204`) to `FIT_SCORE_PROPS`; (2) in `run_scoring_parity.py`'s per-record loop, add a presence/shape assertion (non-empty, valid JSON) alongside the existing `expected_for(...)` score/tier/veto comparison — same loop, same report structure, one more field checked. Do not build a second harness.

---

### 6. Arm/disarm sequence for a whole run

**Analog:** `operator-claude-plugin/scripts/n8n_arming.py` — `arm_for_dispatch()` and `disarm()` are already independently callable (not only via the `armed_window` context manager that pairs them). `scheduled_arm.py`'s docstring is the precedent for *why* an unpaired call sequence is safe/necessary here, but its code path itself should NOT be reused (it binds arm→dispatch→disarm into one bounded cycle, which is the opposite of D-06).

**Arm call site to copy** (verbatim signature and safety framing):
```python
# Source: operator-claude-plugin/scripts/n8n_arming.py:264-267 (signature),
# 297-312 (allowlist targets), 388-397 (success payload)
def arm_for_dispatch(workflow_id, record_ids, record_domains, allow_create, config,
                     transport=None):
    """Grant live writes for ONE dispatch, bounded to exactly the records in it.
    ... record-scoped as well as operation-scoped ...
    """
    ...
    targets = {
        "ALLOW_HUBSPOT_RECORD_WRITES": True,
        "TEST_RECORD_IDS": ",".join(ids),
        "TEST_RECORD_DOMAINS": ",".join(domains),
    }
    ...
    return {
        "outcome": ARMED,
        "workflow_id": workflow_id,
        "prior": dict(prior),
        "record_ids": ids,
        "record_domains": domains,
        "consequence": (
            f"Live writes are enabled on {workflow_id} for exactly "
            f"{len(ids)} record id(s) ... The backend cannot write a record outside that "
            f"list even while this window is open. It closes as soon as the dispatch returns."),
    }
```
**Disarm call site** (`n8n_arming.py:366-415`, verbatim safety property):
```python
def disarm(workflow_id, config, transport=None):
    """Take live writes away again and PROVE it by an independent re-read.
    Deliberately NOT gated on ALLOW_N8N_ARM. A kill switch that blocked disarming would
    strand an armed backend, which is the exact failure the whole ceremony exists to
    prevent.
    """
```
**Why unpaired calls are safe for D-06** (`scheduled_arm.py` docstring, the load-bearing justification, not the code to reuse):
```text
# Source: operator-claude-plugin/scripts/scheduled_arm.py:1-20
# SJ-3's own dispatch ... runs search -> extract -> build-dispatch-event -> dispatch
# entirely inside ONE n8n execution, fired by n8n's own internal 15-minute clock, with
# no external hook between those steps. If the workflow is left armed continuously,
# SJ-3's own tick succeeds on its own; no re-dispatch companion is needed.
```
The arm/disarm script for this phase is: call `arm_for_dispatch(workflow_id, record_ids=<66 resolved ids>, record_domains=[], allow_create=False, config)` once directly (not via `armed_window`), queue via `batch_update_companies`, wait across poller cycles (D-10 canary-then-rest), then call `disarm(workflow_id, config)` once — both handed to the operator as literal `!` commands requiring `ALLOW_N8N_ARM=true` in their shell (never set by Claude).

---

## Shared Patterns

### `.env` permission boundary (applies to every live-touching script in this phase)
**Source:** RESEARCH.md Pitfall 6 + `scripts/run_scoring_parity.py:24-26` invocation contract.
**Apply to:** the ID resolver, the arm/disarm calls, the batch queue write, the parity/provenance check — anything needing `HUBSPOT_PRIVATE_APP_TOKEN`, `ANTHROPIC_API_KEY`, or `ALLOW_N8N_ARM`.
```bash
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; \
runpy.run_path('scripts/run_scoring_parity.py', run_name='__main__')"
```
Every plan task touching these must end with "hand the operator this exact command," never "run this command."

### Dry-run-first discipline
**Source:** `src/hubspot_client.py`'s `patch_record`/`create_record`/`delete_record`/`batch_update_companies` — every write primitive short-circuits on `dry_run=True` BEFORE any network call, printing only the payload (never headers/token).
**Apply to:** the pre-flight ID resolver and any script that stages a write payload before D-06's arm — default to printing the planned batch, not sending it, until the operator's arm command has run.

### Boolean-string coercion landmine
**Source:** `config/hubspot_properties.yaml:185-189` (booleancheckbox options), confirmed live pattern throughout `n8n/code/*.js`.
**Apply to:** the June candidate builder (`lv_produces_content`, `lv_sponsorship_reliant`, `lv_is_hardware_vendor`, `lv_is_gambling_operator` must serialize as literal `"true"`/`"false"` strings, not Python bools/JSON bools) and the batch queue write (`lv_enrichment_requested="true"`).

## No Analog Found

None — every artifact has at least a role-match analog; the pseudo-provider's cross-source conflict wiring (item 3) has no existing analog for the specific "adjudicate June vs fresh research on org_type/produces_content" behavior and is flagged above as a real design decision for the planner, not a missing-analog gap to fill with more searching.

## Metadata

**Analog search scope:** `src/`, `scripts/`, `n8n/code/`, `config/`, `tests/`, `operator-claude-plugin/scripts/`, `docs/reports/`
**Files read this session:** `src/providers.py`, `src/schemas.py`, `src/hubspot_client.py`, `src/normalizer.py` (referenced), `config/taxonomy.yaml`, `config/source_registry.yaml`, `scripts/run_scoring_parity.py`, `tests/scoring_fixtures.py`, `operator-claude-plugin/scripts/n8n_arming.py`, `operator-claude-plugin/scripts/scheduled_arm.py`, `scripts/build_cloud_workflows.py` (mergeCompanies call site + CONFLICT_WATCH), `docs/reports/` listing
**Pattern extraction date:** 2026-08-07
