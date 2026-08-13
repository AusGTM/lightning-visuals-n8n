#!/usr/bin/env python3
"""scripts/check_tier_null_propagation.py

Phase 50 Plan 01 (D-05) -- the fresh, two-key-gated live probe that answers RESEARCH Q4:
does HubSpot blank a `calculation_equation` result when a referenced term is null even
inside an UNTAKEN conditional branch? Phase 41 proved blanking for a bare arithmetic sum
(PORTAL-FACTS.md); whether that extends into a conditional's untaken branch decides which
formula variant `lv_icp_tier_derived` ships with (D-03's uncoalesced ladder if a value
comes back, D-04's forced `coalesce(lv_icp_fit_score, -1)` fallback if it reads blank).

Deliberately superseding the spike's posture (`.planning/TIER-DERIVATION-SPIKE-2026-08-13.md`):
`spike_tier_formula*.py` were gated on `ALLOW_SPIKE_PROPERTY_WRITE` alone and were NOT kept
in `scripts/` (Phase 49 code review CR-01). This script uses the repo's paired two-key gate
instead -- a write is refused unless BOTH `DRY_RUN=false` AND its OWN dedicated allow-key
`ALLOW_TIER_NULL_PROBE=true` are set (never `ALLOW_HUBSPOT_PROPERTY_WRITES`, which is scoped
to scripts/sync_hubspot_properties.py's migration).

D-16 disclosure: the probe creates one disposable numeric company property, one disposable
calculated string company property, and one disposable company -- all created by this run
and archived/deleted by this run's own `finally` block, verified gone by re-read. This is
NOT a company-record write against the live population; no company id from the live
population is ever read or written by this script.

`.env` is Read/Bash permission-blocked this session -- the operator invocation is:
    ALLOW_TIER_NULL_PROBE=true DRY_RUN=false .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/check_tier_null_propagation.py', run_name='__main__')"

Usage:
    python scripts/check_tier_null_propagation.py             # dry run (default, zero writes)
    ALLOW_TIER_NULL_PROBE=true DRY_RUN=false \
        python scripts/check_tier_null_propagation.py          # live probe
"""
import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

DEFAULT_OUT = ROOT / ".planning" / "phases" / "50-derived-tier-property" / "50-NULL-PROBE.json"

EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

NUMERIC_PROP_PREFIX = "lv_tier_probe_score_"
CALC_PROP_PREFIX = "lv_tier_probe_calc_"

# D-03's ladder, mirroring WF1 exactly (spike Round 2, 7/7 accepted). `{score}` is
# substituted with either the disposable stand-in property (the probe's own formula) or
# the real `lv_icp_fit_score` / `coalesce(lv_icp_fit_score, -1)` (the shipped formula).
LADDER_TEMPLATE = (
    'if coalesce(lv_anti_icp_flag, 0) = 1 then "D" '
    'elseif {score} >= 70 then "A" '
    'elseif {score} >= 40 then "B" '
    'elseif {score} >= 15 then "C" '
    'else "Unscored"'
)


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    # Same idiom as scripts/sync_hubspot_properties.py::_writes_allowed(), a dedicated
    # allow-key per D-05 rather than the migration's ALLOW_HUBSPOT_PROPERTY_WRITES.
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_TIER_NULL_PROBE", "false").lower() == "true"
    return (not dry_run) and allow


def _assert_no_secrets(text: str) -> None:
    # Copied verbatim from scripts/check_schema_drift.py / scripts/snapshot_hubspot_schema.py.
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN") or ""
    assert "Authorization" not in text, "serializer leaked the Authorization header"
    if token:
        assert token not in text, "serializer leaked the bearer token value"
    assert "HUBSPOT_PRIVATE_APP_TOKEN" not in text, "serializer leaked the token env var name"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- pure functions pinned by tests/test_tier_derived_tools.py -------------------------

def derived_tier(score, anti_icp_flag):
    """Offline model of the ladder, pinned against config/icp_scoring.yaml's tier_rules
    and the spike's accepted formula. Veto precedes score (a company with the flag set is
    always "D" regardless of score). score=None returns None -- the blank branch under
    D-03's preferred uncoalesced variant; exported for Plan 03's formula-pin test to reuse
    once the settled variant is known."""
    if anti_icp_flag:
        return "D"
    if score is None:
        return None
    if score >= 70:
        return "A"
    if score >= 40:
        return "B"
    if score >= 15:
        return "C"
    return "Unscored"


def classify_probe_result(read_back_value) -> str:
    """"uncoalesced_ok" when the disposable calculated property returned a value for the
    null-score company; "null_propagates" when it read back blank/None -- the signal that
    forces D-04's coalesce fallback."""
    if read_back_value is None or read_back_value == "":
        return "null_propagates"
    return "uncoalesced_ok"


def settled_variant_for(probe_verdict: str) -> str:
    return "uncoalesced" if probe_verdict == "uncoalesced_ok" else "coalesced_minus_one"


def probe_formula_for(stand_in_property: str) -> str:
    """The disposable calculated property's formula -- the accepted ladder with the
    stand-in property substituted for lv_icp_fit_score, always uncoalesced (this IS the
    RESEARCH Q4 minimal test: whether a bare, never-set stand-in blanks the result)."""
    return LADDER_TEMPLATE.format(score=stand_in_property)


def real_formula_for(settled_variant: str) -> str:
    """The formula that ships on lv_icp_tier_derived, keyed by the probe's verdict."""
    if settled_variant == "uncoalesced":
        return LADDER_TEMPLATE.format(score="lv_icp_fit_score")
    if settled_variant == "coalesced_minus_one":
        return LADDER_TEMPLATE.format(score="coalesce(lv_icp_fit_score, -1)")
    raise ValueError(f"unknown settled_variant: {settled_variant!r}")


# --- live calls (composite of sync_hubspot_properties.py / rollback_property_migration.py) --

def _create_numeric_property(name: str) -> None:
    import requests
    from src.hubspot_client import BASE_URL, hs_headers
    body = {
        "name": name, "label": f"[disposable] {name}", "type": "number",
        "fieldType": "number", "groupName": "companyinformation", "options": [],
    }
    r = requests.post(f"{BASE_URL}/crm/v3/properties/companies", headers=hs_headers(),
                       json=body, timeout=30)
    r.raise_for_status()


def _create_calculated_property(name: str, formula: str) -> None:
    import requests
    from src.hubspot_client import BASE_URL, hs_headers
    body = {
        "name": name, "label": f"[disposable] {name}", "type": "string",
        "fieldType": "calculation_equation", "groupName": "companyinformation",
        "options": [], "calculationFormula": formula,
    }
    r = requests.post(f"{BASE_URL}/crm/v3/properties/companies", headers=hs_headers(),
                       json=body, timeout=30)
    r.raise_for_status()


def _get_property_live(object_type: str, name: str):
    # Copied from scripts/rollback_property_migration.py:_get_property_live.
    import requests
    from src.hubspot_client import BASE_URL, hs_headers
    r = requests.get(f"{BASE_URL}/crm/v3/properties/{object_type}/{name}",
                      headers=hs_headers(), timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def _archive_property_live(object_type: str, name: str) -> int:
    # Copied from scripts/rollback_property_migration.py:_archive_property_live.
    import requests
    from src.hubspot_client import BASE_URL, hs_headers
    r = requests.delete(f"{BASE_URL}/crm/v3/properties/{object_type}/{name}",
                         headers=hs_headers(), timeout=30)
    return r.status_code


def _archive_and_confirm_gone(object_type: str, name: str) -> bool:
    status = _archive_property_live(object_type, name)
    print(f"  archived {object_type}/{name} -> HTTP {status}")
    return _get_property_live(object_type, name) is None


def _company_gone(company_id: str) -> bool:
    import requests
    from src.hubspot_client import BASE_URL, hs_headers
    r = requests.get(f"{BASE_URL}/crm/v3/objects/companies/{company_id}",
                      headers=hs_headers(), timeout=30)
    return r.status_code == 404


def _teardown(numeric_name: str, calc_name: str, company_id) -> dict:
    """Runs unconditionally from run_probe's `finally` block. Confirms every disposable is
    gone by an independent re-read, never trusts the DELETE call's own status code alone."""
    from src.hubspot_client import delete_record

    numeric_gone = _archive_and_confirm_gone("companies", numeric_name)
    calc_gone = _archive_and_confirm_gone("companies", calc_name)

    company_gone = True
    if company_id:
        try:
            delete_record("companies", company_id, dry_run=False)
        except Exception as exc:  # noqa: BLE001 -- teardown must not raise past this point
            print(f"  delete company {company_id} raised {exc!r}")
        company_gone = _company_gone(company_id)
        print(f"  deleted company {company_id} -> gone={company_gone}")

    all_gone = numeric_gone and calc_gone and company_gone
    return {
        "numeric_property": {"name": numeric_name, "gone": numeric_gone},
        "calculated_property": {"name": calc_name, "gone": calc_gone},
        "company": {"id": company_id, "gone": company_gone},
        "all_gone": all_gone,
    }


def _check_archived_listing(numeric_name: str, calc_name: str) -> dict:
    """RESEARCH Q6: does the archived disposable reappear under
    GET /crm/v3/properties/companies?archived=true -- confirming DELETE is a soft archive,
    not a hard delete, before D-06's irreversible archive of lv_icp_tier is ever run."""
    import requests
    from src.hubspot_client import BASE_URL, hs_headers
    r = requests.get(f"{BASE_URL}/crm/v3/properties/companies", headers=hs_headers(),
                      params={"archived": "true"}, timeout=30)
    r.raise_for_status()
    names = {p["name"] for p in r.json().get("results", [])}
    return {
        "numeric_property_reappears": numeric_name in names,
        "calculated_property_reappears": calc_name in names,
        "note": (
            "True means the API DELETE performed a soft archive -- the disposable still "
            "appears under ?archived=true after being deleted. False means it does not "
            "reappear there."
        ),
    }


def run_probe(out_path: Path) -> int:
    from src.hubspot_client import create_record, get_record

    suffix = uuid.uuid4().hex[:8]
    numeric_name = f"{NUMERIC_PROP_PREFIX}{suffix}"
    calc_name = f"{CALC_PROP_PREFIX}{suffix}"
    company_id = None
    verdict = None
    variant = None
    read_back = None

    try:
        print(f"creating disposable numeric property {numeric_name}")
        _create_numeric_property(numeric_name)

        formula = probe_formula_for(numeric_name)
        print(f"creating disposable calculated property {calc_name}: {formula}")
        _create_calculated_property(calc_name, formula)

        company = create_record("companies", {"name": f"TIER-50 NULL PROBE {suffix}"},
                                 dry_run=False)
        company_id = company["id"]
        print(f"created disposable company {company_id} (stand-in property left null, "
              "never set)")

        read_back = get_record("companies", company_id, [calc_name])["properties"].get(calc_name)
        verdict = classify_probe_result(read_back)
        variant = settled_variant_for(verdict)
        print(f"read back {calc_name}={read_back!r} on company {company_id} -> {verdict} "
              f"-> settled variant {variant}")
    finally:
        print("tearing down disposables...")
        teardown = _teardown(numeric_name, calc_name, company_id)

    if verdict is None:
        print("probe did not complete -- see error above. No result written.")
        return 1

    archived_listing_finding = _check_archived_listing(numeric_name, calc_name)

    result = {
        "settled_variant": variant,
        "calculation_formula": real_formula_for(variant),
        "read_back_value": read_back,
        "probe_verdict": verdict,
        "teardown": teardown,
        "archived_listing_finding": archived_listing_finding,
        "checked_at": _now_iso(),
    }

    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    _assert_no_secrets(text)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    print(f"wrote {out_path}")
    print(json.dumps(result, indent=2))
    return 0 if teardown["all_gone"] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                         help="Path to write the probe evidence JSON to.")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this probe.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    if not _writes_allowed():
        print("DRY RUN (default) -- no writes will be made. Set DRY_RUN=false AND "
              "ALLOW_TIER_NULL_PROBE=true to run the live probe.")
        return 0

    return run_probe(Path(args.out))


if __name__ == "__main__":
    sys.exit(main())
