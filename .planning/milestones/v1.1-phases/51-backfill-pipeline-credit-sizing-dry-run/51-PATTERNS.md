# Phase 51: Backfill Pipeline, Credit Sizing & Dry Run - Pattern Map

**Mapped:** 2026-08-19
**Files analyzed:** 4 new (2 scripts, 2 tests)
**Analogs found:** 4 / 4

This phase is almost entirely composition over existing code (per 51-RESEARCH.md's own
"Standard Stack" table). This map exists to pin the exact idioms (arg parsing, gates,
dry-run print discipline, offline test style) new files must copy, not to discover new
analogs — RESEARCH.md already named the file-level analogs; this file extracts the
concrete excerpts.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `scripts/zoominfo_company_client.py` | service (provider HTTP client) | request-response | `scripts/check_provider_credits.py` (`_mint_zoominfo_token`/`_check_zoominfo`) + `scripts/build_cloud_workflows.py` `ENRICH_ZOOMINFO_CO_CACHED` JS block (contract source, not Python) | role-match (auth/gate idiom exact; JS analog is the wire-contract source of truth) |
| `scripts/backfill_dry_run.py` | service (read-only CLI driver) | batch / request-response | `scripts/backfill_seed_company_scores.py` (whole-script shape) + `scripts/rescore_population.py` (population/cost-estimate idiom) | exact (same role: capped-sample HubSpot read → compute → print, zero writes) |
| `tests/test_zoominfo_company_client.py` | test (unit, offline/mocked) | transform | `tests/test_icp_scoring.py` (plain-pytest, plain-assert style) + `tests/n8n/enrichment.test.mjs:448` (the THOUSANDS pin this test must mirror in Python) | role-match |
| `tests/test_backfill_dry_run.py` | test (unit, offline/mocked) | transform | `tests/test_icp_scoring.py` + `tests/scoring_fixtures.py` (fixture/helper reuse, not a new conftest) | role-match |

No `src/` file is modified — `src/icp_scoring.py`, `src/normalizer.py`, `src/hubspot_client.py`
are imported unchanged.

## Pattern Assignments

### `scripts/zoominfo_company_client.py` (service, request-response)

**Analogs:** `scripts/check_provider_credits.py` (auth/token idiom, Python) + the JS contract in
`scripts/build_cloud_workflows.py:1682-1742` (wire shape — port values, not JS code) +
`n8n/code/normalizeProviders.js:37-72,380-415` (revenue/country conversion — the bug this file
must not reintroduce).

**Auth pattern to copy verbatim** (`scripts/check_provider_credits.py:141-158`):
```python
def _mint_zoominfo_token():
    """Inline Basic-auth POST — the ONLY place client_id/client_secret are read, via
    `requests`' own `auth=` tuple (never a manually-built header string). Returns the
    bearer token string, or None on ANY failure — never raises, never prints the secret
    values (grant_type=client_credentials ONLY, no `scope` — a `scope` 400s)."""
    import requests
    cid = os.getenv("ZOOMINFO_CLIENT_ID", "")
    csec = os.getenv("ZOOMINFO_CLIENT_SECRET", "")
    try:
        r = requests.post(
            "https://api.zoominfo.com/gtm/oauth/v1/token",
            auth=(cid, csec), data={"grant_type": "client_credentials"}, timeout=15)
        if not r.ok:
            return None
        token = r.json().get("access_token")
        return token if isinstance(token, str) and token else None
    except Exception:
        return None
```

**companies/enrich wire contract to port** (`scripts/build_cloud_workflows.py:1682-1699`,
JS, port values not code — confirmed live 200 2026-07-20):
```
POST https://api.zoominfo.com/gtm/data/v1/companies/enrich
Headers: Authorization: Bearer <token>, Content-Type: application/vnd.api+json,
         Accept: application/vnd.api+json
Body: {"data": {"type": "CompanyEnrich",
                 "attributes": {"matchCompanyInput": [{"companyWebsite": domain}],
                                "outputFields": ZOOM_CO_OUTPUT_FIELDS}}}
ZOOM_CO_OUTPUT_FIELDS = ["id", "name", "website", "revenue", "revenueRange",
                         "employeeCount", "employeeRange", "country", "primaryIndustry",
                         "naicsCodes", "descriptionList", "foundedYear"]
# "companyType" is NOT valid/entitled (400 PFAPI0009) — do not add it.
Response: {"data": [{"id":..., "type": "Company"|"NoMatch", "attributes": {...},
                      "meta": {"matchStatus": ...}}]}
```
1-25 companies / 25 outputFields per request limit (RESEARCH.md).

**Error handling pattern to copy** (`scripts/check_provider_credits.py:169-181`,
`_check_zoominfo`): mint fails → return `{"credits": None, "error": "mint_failed"}` with
**no** usage GET issued; any HTTP/JSON exception on the data call → caught, never raised,
degrades to a null/skip result. Apply the same discipline to `companies/enrich`: a
malformed response is a skip-logged record (FILL-04), never a crash.

**Revenue THOUSANDS→dollars fix to port** (`n8n/code/normalizeProviders.js:404-411`,
verbatim comment — the bug this phase's FILL-03 pins):
```javascript
// UNITS: GTM `revenue` is in THOUSANDS, not dollars — confirmed live against three
// records (Racing NSW 268163 + revenueRange "$250 mil. - $500 mil."; ...). Prefer the
// unambiguous `revenueRange` string; fall back to revenue*1000.
const ziRev = raw.revenueRange != null && raw.revenueRange !== ""
  ? raw.revenueRange
  : (typeof raw.revenue === "number" ? raw.revenue * 1000 : null);
```
Minimal Python port (per RESEARCH.md's own Code Examples section — `revenueRange`-string
parsing is a nice-to-have, not required by FILL-03):
```python
def zoominfo_revenue_to_dollars(raw_revenue_thousands):
    if not isinstance(raw_revenue_thousands, (int, float)):
        return None
    return raw_revenue_thousands * 1000
# Feed the dollar figure into the EXISTING src/normalizer.py::normalize_revenue_band()
# (expects dollars, matches config/icp_scoring.yaml's band cut points) — do not re-band by hand.
```

**Country mapping — the landmine to avoid** (do NOT reuse `src/normalizer.py::normalize_country_region`
as-is; DO reuse `n8n/code/normalizeProviders.js:96-102`'s contract):
```python
# src/normalizer.py:80-88 — UNSAFE to feed compute_icp_score directly:
def normalize_country_region(value):
    if not value:
        return "Unknown"   # <-- a non-empty string, not in ["AU","NZ","ANZ"] ->
                            #     compute_icp_score treats it as region_key="non_anz"
                            #     -> FALSE hard veto. This is the exact bug already
                            #     fixed for a *missing* key in src/icp_scoring.py:62-70,
                            #     but not for this string.
    ...
```
```javascript
// n8n/code/normalizeProviders.js:96-98 — the SAFE contract to mirror in the new
// Python ZoomInfo-country mapper:
function normalizeCountryRegion(value) {
  if (!value) return null;   // blank -> null, never a truthy sentinel string
  ...
}
```
New Python function must return `None` (or omit the key) for blank/no-match ZoomInfo
country — never the string `"Unknown"`.

---

### `scripts/backfill_dry_run.py` (service, batch read-only driver)

**Analog:** `scripts/backfill_seed_company_scores.py` (whole-script shape: docstring
arm-discipline header, portal guard, sample cap, `main()`/`argparse` shape) +
`scripts/rescore_population.py` (population/cost-plan dict shape) +
`scripts/check_tier_derived_parity.py::_count_never_scored_companies` (count-only search).

**Imports pattern** (`scripts/backfill_seed_company_scores.py:53-60`):
```python
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*`/`scripts.*` imports resolve

from src.hubspot_client import batch_update_companies, get_record, search_records  # noqa: E402
from src.icp_scoring import compute_icp_score, anti_icp_flag_properties  # noqa: E402
from src.schemas import HubSpotRecord  # noqa: E402
from scripts.backfill_seed_company_scores import compute_components  # noqa: E402 -- import, never re-derive
```

**Portal + credential gate pattern** (`scripts/backfill_seed_company_scores.py:63-64,
183-192`):
```python
EXPECTED_PORTAL_ID = "22617666"

def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))

def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID

# in main():
if not _has_credentials():
    print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run.")
    return 0
if not _portal_ok():
    print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
          f"({EXPECTED_PORTAL_ID}). No API call made.")
    return 1
```

**Count-only population read (no pagination needed)** — copy verbatim shape from
`scripts/check_tier_derived_parity.py:596-604`:
```python
def _count_never_scored_companies() -> int:
    from src.hubspot_client import search_records
    result = search_records(
        "companies",
        [{"propertyName": "lv_icp_fit_score", "operator": "NOT_HAS_PROPERTY"}],
        ["name"],
        limit=1,
    )
    return result.get("total", 0)
```

**Refuse-rather-than-truncate population pattern** (`scripts/rescore_population.py:108-129`) —
apply to the bounded sample read too, even though it's `<=100`:
```python
result = search_records(
    "companies",
    [{"propertyName": "lv_icp_fit_score", "operator": "NOT_HAS_PROPERTY"}],
    ["name"],
    limit=SAMPLE_SEARCH_LIMIT,
)
ids = sorted(r["id"] for r in result.get("results", []))
total = result.get("total")
if total is not None and total > len(ids):
    raise RuntimeError(
        f"REFUSED: population is {total} but this search returned only {len(ids)} "
        f"(page limit {SAMPLE_SEARCH_LIMIT}). Add pagination before re-running."
    )
```

**Oracle composition — import, never reimplement** (RESEARCH.md's Code Examples section,
composed from `src/icp_scoring.py:47-172` + `scripts/backfill_seed_company_scores.py:112-136`):
```python
candidate_patch = {
    "lv_org_type": "governing_body_league",
    "lv_produces_content": True,
    "lv_country_region_normalized": "AU",       # never "Unknown" for blank -- see zoominfo client section
    "lv_revenue_band": "5-50M",
    "lv_is_gambling_operator": False,
    "lv_is_hardware_vendor": False,
}
record = HubSpotRecord(object_type="companies", id=company_id, properties={})
result = compute_icp_score(record, candidate_patch)          # the ONE oracle call
six_numbers = {
    **compute_components(candidate_patch),                    # 5 named component scores
    **anti_icp_flag_properties(result.anti_icp_flag),         # lv_anti_icp_flag + _num
}
# Predicted tier -- replicate the LIVE 4-branch calculation_equation directly from
# score+veto. Do NOT use result.tier verbatim ("Needs Review" never appears live).
predicted_tier = (
    "D" if result.anti_icp_flag else
    "A" if result.score >= 70 else
    "B" if result.score >= 40 else
    "C" if result.score >= 15 else
    "Unscored"
)
```

**Dry-run print discipline — reuse `patch_record`'s existing branch, never build a new
one** (`src/hubspot_client.py:24-34`):
```python
if dry_run:
    print(json.dumps({
        "dry_run": True,
        "method": "PATCH",
        "url": f"{BASE_URL}/crm/v3/objects/{object_type}/{record_id}",
        "payload": payload
    }, indent=2, default=str))
    return {"dry_run": True, "payload": payload}
```
This phase's driver calls `patch_record`/`batch_update_companies` with `dry_run=True`
**hard-coded**, not env-driven (RESEARCH.md Pattern 2) — never a `DRY_RUN` env check for
writes in this script.

**Skip-log entry pattern for unmatched records (FILL-04)** — no existing precedent emits
a skip log per se; mirror the "never crash, always continue" discipline of
`_check_zoominfo`'s null-safe extractors: on no ZoomInfo match, append
`{"id": company_id, "skipped": "no zoominfo company match", "reason": ...}` to a skip
list and do NOT append to the PATCH-payload list — same shape as the JS reference's own
`{ json: { skipped: "no zoominfo company match key" } }` push
(`scripts/build_cloud_workflows.py:1717`).

---

### `tests/test_zoominfo_company_client.py` (test, offline/mocked)

**Analog:** `tests/test_icp_scoring.py` (plain pytest, plain `assert`, no fixtures/classes)
+ `tests/n8n/enrichment.test.mjs:448` (the exact THOUSANDS pin to mirror in Python — grep
before writing to get the live wording).

**Style to copy** (`tests/test_icp_scoring.py:17-35`):
```python
from src.schemas import HubSpotRecord
from src.icp_scoring import compute_icp_score

def score(patch):
    record = HubSpotRecord(object_type="companies", id="789", properties={})
    return compute_icp_score(record, patch)

def test_case_1_au_governing_body_tier_a():
    r = score({"lv_org_type": "governing_body_league", "lv_produces_content": True,
               "lv_country_region_normalized": "AU", "lv_revenue_band": "5-50M"})
    assert r.tier == "A"
    assert r.anti_icp_flag is False
    assert r.score == 80
```
Apply the same shape to the new file: no classes, no fixtures beyond a plain helper
function, one `test_*` function per case, descriptive test names encoding the scenario.

**Required test cases** (from RESEARCH.md's Phase Requirements → Test Map, FILL-03):
- `test_revenue_thousands_to_dollars` — pins `zoominfo_revenue_to_dollars(268163) == 268163000`
  style assertion, mirroring the JS pin's own numbers (Racing NSW 268163→$268.163M,
  FanDuel 14050000→$14.05B) so the two pins can be cross-checked by inspection.
- A blank-country test asserting the new country mapper returns `None` (not `"Unknown"`),
  guarding Pitfall 2 directly — this is the test that would have caught the false-veto bug.

---

### `tests/test_backfill_dry_run.py` (test, offline/mocked)

**Analog:** `tests/test_icp_scoring.py` (style) + `tests/scoring_fixtures.py` (reuse
`EXPECTED_PORTAL_ID` constant and helper conventions, do not redefine a second portal
constant).

**Required test cases** (RESEARCH.md's Test Map, exact names to use):
```python
def test_cap_derivation():
    ...  # FILL-01: credit balance -> floor(balance / credits_per_match) cap, mocked HTTP

def test_unmatched_skip_log():
    ...  # FILL-04: unmatched record -> skip-log entry, NO payload emitted

def test_predicted_tier_excludes_needs_review():
    ...  # SAFE-01: assert predicted_tier is derived from (score, anti_icp_flag), never
         # from compute_icp_score(...).tier when tier == "Needs Review" -- construct a
         # candidate_patch that would produce "Needs Review" (unknown org_type or
         # produces_content is None) and assert predicted_tier is "Unscored"/"C"/etc,
         # never the literal string "Needs Review"

def test_imports_oracle_functions():
    ...  # SAFE-01 regression guard: static/import-based -- e.g. assert
         # backfill_dry_run.compute_components is scripts.backfill_seed_company_scores.compute_components
         # (identity check) and backfill_dry_run.compute_icp_score is src.icp_scoring.compute_icp_score,
         # proving no local reimplementation shadows the import
```

## Shared Patterns

### Portal guard
**Source:** `scripts/backfill_seed_company_scores.py:63-64, 187-190` (also
`tests/scoring_fixtures.py:22-24`)
**Apply to:** Both new scripts (`zoominfo_company_client.py`'s live-call entry point and
`backfill_dry_run.py`'s `main()`).
```python
EXPECTED_PORTAL_ID = "22617666"  # hard-coded, no env override
```

### Credential-less clean skip (never crash)
**Source:** `scripts/check_provider_credits.py:186-190`
**Apply to:** Both new scripts.
```python
if not configured:
    print("skipped (no provider creds): ...")
    return 0
```

### dry_run hard-coded True for all writes in this phase
**Source:** `src/hubspot_client.py:24-42` (the `dry_run` branch itself) + RESEARCH.md
Pattern 2 (SAFE-01/criterion 7: zero writes this phase)
**Apply to:** `backfill_dry_run.py` — every `patch_record`/`batch_update_companies` call
site passes `dry_run=True` as a literal, never reads `DRY_RUN` from the environment for
this phase's driver.

### Refuse rather than truncate
**Source:** `scripts/rescore_population.py:108-129`, `scripts/backfill_seed_company_scores.py:169-176`
**Apply to:** Every `search_records` call in `backfill_dry_run.py`, including count-only ones.

### Never re-derive the six numeric scores or the veto
**Source:** `scripts/backfill_seed_company_scores.py::compute_components` (`:112-136`),
`src/icp_scoring.py::anti_icp_flag_properties` (`:36-44`)
**Apply to:** `backfill_dry_run.py` exclusively — import both, never hand-copy the point
table or the `"1"/"0"` veto serialization.

## No Analog Found

None — every file in scope has a clear existing analog per RESEARCH.md's own "Standard
Stack" and "Don't Hand-Roll" tables; this phase is composition, not new-pattern design.

## Metadata

**Analog search scope:** `scripts/`, `src/`, `tests/`, `n8n/code/` (guided by
51-RESEARCH.md's own file citations; no fresh Glob/Grep sweep was needed since the
research doc already pinned exact file:line locations for every reusable piece).
**Files scanned:** `scripts/backfill_seed_company_scores.py` (full), `scripts/rescore_population.py`
(partial, ~90-260), `scripts/check_provider_credits.py` (full), `scripts/build_cloud_workflows.py`
(~1670-1760), `n8n/code/normalizeProviders.js` (~1-110, 380-439), `src/icp_scoring.py` (full),
`src/normalizer.py` (~1-95), `src/hubspot_client.py` (full), `scripts/check_tier_derived_parity.py`
(~585-610), `tests/test_icp_scoring.py` (~1-50), `tests/scoring_fixtures.py` (~1-60).
**Pattern extraction date:** 2026-08-19
