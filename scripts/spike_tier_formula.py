#!/usr/bin/env python3
"""Grammar spike: can lv_icp_tier be a calculated (derived) property?

Creates ONE disposable company property, PATCHes candidate formulas at it, records
every status + response body, then archives the disposable. A 400 mutates nothing and
its body enumerates the valid tokens at the failing parse position -- that body is the
authoritative grammar for this portal (Phase 41 precedent).

Never touches lv_icp_tier itself.

Write gate (repo idiom, exact-'true'): ALLOW_SPIKE_PROPERTY_WRITE=true
Without it, prints the candidates and exits 0 -- no network write.

    .venv/bin/python spike_tier_formula.py            # dry run
    ALLOW_SPIKE_PROPERTY_WRITE=true .venv/bin/python spike_tier_formula.py
"""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path("/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc")
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.hubspot_client import hs_headers  # noqa: E402

EXPECTED_PORTAL_ID = "22617666"
SPIKE = "lv_spike_tier_calc"
BASE = "https://api.hubapi.com/crm/v3/properties/companies"

# Probe order matters: cheapest primitive first, so a failure localises the cause.
CANDIDATES = [
    ("string literal alone",          '"D"'),
    ("if/then/else + literal",        'if is_present(lv_icp_fit_score) then "A" else "Unscored"'),
    ("numeric comparison >=",         'if lv_icp_fit_score >= 70 then "A" else "Unscored"'),
    ("elseif chain",                  'if lv_icp_fit_score >= 70 then "A" elseif lv_icp_fit_score >= 40 then "B" else "C"'),
    ("elseif + endif",                'if lv_icp_fit_score >= 70 then "A" elseif lv_icp_fit_score >= 40 then "B" else "C" endif'),
    ("boolean prop in condition",     'if lv_anti_icp_flag then "D" else "not-D"'),
    ("coalesce over boolean",         'if coalesce(lv_anti_icp_flag, false) then "D" else "not-D"'),
    ("FULL LADDER (coalesced veto)",
     'if coalesce(lv_anti_icp_flag, false) then "D" '
     'elseif lv_icp_fit_score >= 70 then "A" '
     'elseif lv_icp_fit_score >= 40 then "B" '
     'elseif lv_icp_fit_score >= 15 then "C" '
     'else "Unscored"'),
    ("FULL LADDER (unguarded veto)",
     'if lv_anti_icp_flag then "D" '
     'elseif lv_icp_fit_score >= 70 then "A" '
     'elseif lv_icp_fit_score >= 40 then "B" '
     'elseif lv_icp_fit_score >= 15 then "C" '
     'else "Unscored"'),
]

SEED = 'if is_present(lv_icp_fit_score) then string(lv_icp_fit_score) else ""'


def preflight() -> int:
    if not os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"):
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set.")
        return 1
    if os.getenv("HUBSPOT_PORTAL_ID") != EXPECTED_PORTAL_ID:
        print(f"REFUSED: HUBSPOT_PORTAL_ID != {EXPECTED_PORTAL_ID}. No API call made.")
        return 1
    return 0


def body(r):
    try:
        j = r.json()
        return j.get("message") or json.dumps(j)[:1200]
    except Exception:
        return r.text[:1200]


def main() -> int:
    if (rc := preflight()) != 0:
        return rc

    if os.getenv("ALLOW_SPIKE_PROPERTY_WRITE") != "true":
        print("DRY RUN (set ALLOW_SPIKE_PROPERTY_WRITE=true to run the spike).")
        print(f"Would create disposable property '{SPIKE}' then PATCH {len(CANDIDATES)} candidates:\n")
        for name, f in CANDIDATES:
            print(f"  [{name}]\n    {f}\n")
        return 0

    # 1. Create the disposable with a deliberately minimal seed formula.
    print(f"=== creating disposable '{SPIKE}' ===")
    r = requests.post(BASE, headers=hs_headers(), timeout=30, json={
        "name": SPIKE, "label": "SPIKE tier calc (disposable)",
        "groupName": "companyinformation", "type": "string",
        "fieldType": "calculation_equation", "calculationFormula": SEED,
    })
    print(f"POST {r.status_code}")
    if r.status_code not in (200, 201):
        print("--- create failed; the body below IS the grammar reference ---")
        print(body(r))
        return 1
    print("created.\n")

    results = []
    try:
        for name, formula in CANDIDATES:
            r = requests.patch(f"{BASE}/{SPIKE}", headers=hs_headers(), timeout=30,
                               json={"calculationFormula": formula})
            ok = r.status_code in (200, 201, 204)
            print(f"=== [{name}] -> {r.status_code} {'ACCEPTED' if ok else 'REJECTED'}")
            print(f"    {formula}")
            msg = "" if ok else body(r)
            if msg:
                print(f"    {msg}\n")
            else:
                print()
            results.append({"candidate": name, "formula": formula,
                            "status": r.status_code, "accepted": ok, "body": msg})
    finally:
        # 2. Always archive the disposable, even if a candidate blew up mid-loop.
        d = requests.delete(f"{BASE}/{SPIKE}", headers=hs_headers(), timeout=30)
        print(f"=== archived disposable: DELETE {d.status_code} ===")
        gone = requests.get(f"{BASE}/{SPIKE}", headers=hs_headers(), timeout=30)
        print(f"=== verified by re-read: {gone.status_code} (404 == gone) ===")

    out = Path(__file__).parent / "spike_tier_formula_results.json"
    out.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nresults -> {out}")
    print(f"\nACCEPTED: {sum(1 for x in results if x['accepted'])}/{len(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
