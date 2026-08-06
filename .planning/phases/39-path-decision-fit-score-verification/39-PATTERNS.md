# Phase 39: Path Decision & Fit-Score Verification - Pattern Map

**Mapped:** 2026-08-06
**Files analyzed:** 4 (2 new scripts, 1 new client function, 1 new test file); 39-DECISION.md is docs-only, no code analog needed
**Analogs found:** 4 / 4

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `scripts/probe_scoring_tool_availability.py` | script/probe (utility) | request-response (read-only HTTP ladder + evidence JSON) | `scripts/snapshot_hubspot_schema.py` | role-match (read-only probe, dry-run-by-default, evidence-to-disk shape) |
| `scripts/probe_scoring_recalc_latency.py` | script/probe (utility) | CRUD (create→patch×3→poll→delete) + batch (median) | `scripts/rollback_canary_proof.py` | exact (two-key gate, disposable-artifact create/verify/no-clobber shape, portal guard) |
| `src/hubspot_client.py::delete_record()` | service/utility (thin API wrapper) | CRUD | `src/hubspot_client.py::create_record()` (same file, same function family) | exact (same file, same signature convention as `patch_record`/`create_record`) |
| `tests/test_scoring_probe_helpers.py` | test | transform (pure-function unit tests) | none in-repo (no prior pure-function unit test file for a probe script) | no analog — see below |

## Pattern Assignments

### `scripts/probe_scoring_tool_availability.py` (script, request-response)

**Analog:** `scripts/snapshot_hubspot_schema.py`

**Imports pattern** (lines 21-28):
```python
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve
```

**Portal guard constant** (line 32):
```python
EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")
```

**Core pattern — read-only probe, zero writes by default:** `snapshot_hubspot_schema.py`'s
docstring states the contract to copy verbatim: "Zero writes in the default mode: GET
only, verbatim to disk." The new script should follow the same shape — a `probe_*(headers)`
function per HTTP call, each returning a dict with `endpoint`, `status`, `body`, and a
`note` field explaining what the result does/doesn't prove (see RESEARCH.md Pattern 1's
`probe_account_info`/`probe_existing_score_properties` — those are the literal functions to
implement). Results get written to `evidence/*.json` via plain `json.dump`, no pydantic
needed for a one-shot file.

**Doomed-POST evidence, if included:** gate behind the same two-key convention as writes
elsewhere (`DRY_RUN=false` + a phase-scoped `ALLOW_*` flag) even though it's expected to
fail on every tier — label the resulting file "expected-to-fail, non-discriminating" so a
future reader doesn't misread a 400 as a tier-negative signal.

**Error handling:** no `raise_for_status()` on the account-info/properties GETs — capture
`r.json() if r.ok else {"status": r.status_code, "text": r.text}` (RESEARCH.md Pattern 1),
since a non-200 here is itself evidence, not a bug to crash on.

---

### `scripts/probe_scoring_recalc_latency.py` (script, CRUD + batch)

**Analog:** `scripts/rollback_canary_proof.py`

**Imports pattern** (lines 1-30, condensed):
```python
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*`/`src.*` imports resolve

EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")
```

**Two-key write gate (verbatim precedent)** — `scripts/rollback_canary_proof.py` lines 42-53:
```python
def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_HUBSPOT_PROPERTY_WRITES", "false").lower() == "true"
    return (not dry_run) and allow
```
Reuse verbatim, swapping the second flag to a phase-scoped name — `ALLOW_HUBSPOT_SCORING_PROBE`
— so it can't be accidentally armed by a flag left on from an unrelated migration script
(RESEARCH.md Code Examples). No credentials → skip to exit 0. Wrong portal → refuse with
no call.

**Disposable-artifact naming discipline** — from `scripts/probe_org_type_migration.py`'s
docstring/module-constant idiom (line ~35-38): a module-level constant, no CLI override,
"no legitimate reason for this script to be pointable anywhere else." Apply the same
discipline to the company name prefix:
```python
COMPANY_NAME_PREFIX = "ZZ-SCORING-TEST-DELETE-ME-"  # HANDOVER §10 disposable pattern
```

**Precondition check (Pitfall 2 from RESEARCH.md — must hard-fail, not silently proceed):**
before starting the flip loop, assert a `calculation_score`-typed property already exists
on the companies object (built by the operator in-portal). If none exists, exit with a
clear message — do not poll a property that doesn't exist and misreport "manual-only."

**Core pattern — create → flip×3 → poll → median → delete:**
```python
import statistics

def median_latency(samples: list[float]) -> float:
    """samples: elapsed seconds from property-write to observed score change.
    Pure function — the ONE thing in this probe worth a unit test without network."""
    if not samples:
        raise ValueError("no samples")
    return statistics.median(samples)
```
(RESEARCH.md Pattern 2 — extracted deliberately so it's unit-testable without a live run;
inlining it into the polling loop was flagged as an explicit anti-pattern.)

Sequencing rule (Pitfall 3): build/confirm the scoring criterion is stable *before* the
timed loop starts; the loop only ever flips the disposable company's property, never the
criteria definition, so the measured number is unambiguously the per-record event-driven
rescore, not the criteria-edit bulk-recalc window. `39-DECISION.md` must state which
latency was measured.

**Teardown:** call the new `delete_record("companies", id)` and assert `204`
(`r.status_code == 204`) — never leave a disposable artifact live after the probe
completes.

---

### `src/hubspot_client.py::delete_record()` (service, CRUD)

**Analog:** same file — `create_record()` (lines 45-61) and `patch_record()` (lines 24-40)

**Pattern to copy exactly** (dry-run-first shape, no token/secret ever printed):
```python
def delete_record(object_type: str, record_id: str, dry_run=True):
    # Mirrors patch_record/create_record: dry_run short-circuits BEFORE any requests.delete
    # — prints only the URL (never hs_headers/token) and returns the sentinel.
    if dry_run:
        print(json.dumps({
            "dry_run": True,
            "method": "DELETE",
            "url": f"{BASE_URL}/crm/v3/objects/{object_type}/{record_id}"
        }, indent=2, default=str))
        return {"dry_run": True}

    url = f"{BASE_URL}/crm/v3/objects/{object_type}/{record_id}"
    r = requests.delete(url, headers=hs_headers(), timeout=30)
    r.raise_for_status()
    return r  # 204 No Content — caller asserts r.status_code == 204
```
This is the one genuinely missing primitive (RESEARCH.md confirms `get_record`/
`patch_record`/`create_record`/`search_records` exist, no `delete_record`). Add it
alongside the other four in the same file — do not create a wrapper class or a second
module.

---

### `tests/test_scoring_probe_helpers.py` (test, transform)

**No direct analog** — this repo has no prior pure-function unit test file scoped to a
probe script (RESEARCH.md: "dry-run-mode manual inspection is the established bar for
these thin wrappers"; `create_record`/`patch_record` also have no dedicated unit test).
Use plain `pytest` function-per-behavior style consistent with the rest of `tests/`
(run via `.venv/bin/python -m pytest`, per this repo's documented convention — dir-form
is broken on the installed Python version).

Minimum coverage (from RESEARCH.md's Phase Requirements → Test Map):
```python
def test_median_latency():
    from scripts.probe_scoring_recalc_latency import median_latency
    assert median_latency([10, 12, 14]) == 12
    assert median_latency([5, 100, 6]) == 6  # resists the one noisy sample

def test_account_info_has_no_tier_field():
    from scripts.probe_scoring_tool_availability import probe_account_info
    # fixture dict, not a live call — regression-proofs the negative-evidence claim
    ...
```

---

## Shared Patterns

### Two-key write gate + portal guard
**Source:** `scripts/rollback_canary_proof.py` lines 42-53 (verbatim above)
**Apply to:** `probe_scoring_recalc_latency.py` (write-capable: create/patch/delete), and
the optional doomed-POST evidence path in `probe_scoring_tool_availability.py`.

### `.env` load without direct file access
**Source:** `scripts/probe_lusha_v3.py` docstring, lines 45-47 — the `.env` file itself is
permission-blocked to Read/Bash this session.
```bash
ALLOW_HUBSPOT_SCORING_PROBE=true DRY_RUN=false .venv/bin/python -c \
  "from dotenv import load_dotenv; load_dotenv(); import runpy; \
   runpy.run_path('scripts/probe_scoring_recalc_latency.py', run_name='__main__')"
```
**Apply to:** any live/armed invocation of either new script — hand the operator this
exact `!`-prefixed command rather than attempting to read `.env` directly.

### `hs_headers()` — token never echoed
**Source:** `src/hubspot_client.py` lines 7-13
```python
def hs_headers():
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
```
**Apply to:** both new scripts — import and reuse `hs_headers()` from `src/hubspot_client.py`
rather than rebuilding auth headers inline; never construct or print the token elsewhere.

### Disposable-artifact naming discipline (module constant, no CLI override)
**Source:** `scripts/probe_org_type_migration.py` `PROBE_PROPERTY_NAME` idiom
**Apply to:** `probe_scoring_recalc_latency.py`'s `COMPANY_NAME_PREFIX =
"ZZ-SCORING-TEST-DELETE-ME-"` — a module constant, never a CLI-overridable value, mirroring
why `PROBE_PROPERTY_NAME` has "no legitimate reason ... to be pointable anywhere else."

### Evidence-to-disk (JSON, no pydantic)
**Source:** `scripts/snapshot_hubspot_schema.py`'s baseline-write shape (`BASELINE_DIR`,
plain `json.dump`)
**Apply to:** both new scripts — write evidence artifacts to
`.planning/phases/39-path-decision-fit-score-verification/evidence/*.json` via plain
`json.dump`; pydantic is available but explicitly not needed for a one-shot evidence file
(RESEARCH.md Standard Stack).

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `39-DECISION.md` | docs (planning artifact) | n/a | Pure documentation output, no runtime tier — cite `HANDOVER-2026-08-06-icp-scoring.md` §5 by structure/section reference, not code |
| `tests/test_scoring_probe_helpers.py` | test | transform | No prior pure-function unit test file scoped to a probe script exists in this repo; use plain pytest style, no fixture framework needed for 2-3 assertions |

## Metadata

**Analog search scope:** `scripts/` (probe/diagnostic scripts), `src/hubspot_client.py`, `tests/`
**Files scanned:** `scripts/rollback_canary_proof.py`, `scripts/probe_org_type_migration.py`, `scripts/probe_lusha_v3.py`, `scripts/snapshot_hubspot_schema.py`, `src/hubspot_client.py`
**Pattern extraction date:** 2026-08-06
