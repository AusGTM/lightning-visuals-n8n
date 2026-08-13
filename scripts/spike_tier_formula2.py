#!/usr/bin/env python3
"""Grammar spike round 2 -- resolve the Boolean/BigDecimal mismatch on lv_anti_icp_flag.

Round 1 established: string literals, if/then/else, >=, and elseif chains all ACCEPTED;
`endif` is not a token; and a bool property arrives in formula-land as BigDecimal, so it
cannot sit bare in a condition slot. Round 2 finds the working veto guard and validates
the full ladder. Same disposable-property harness, same archive-in-finally.
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
SPIKE = "lv_spike_tier_calc2"
BASE = "https://api.hubapi.com/crm/v3/properties/companies"

LADDER = ('elseif lv_icp_fit_score >= 70 then "A" '
          'elseif lv_icp_fit_score >= 40 then "B" '
          'elseif lv_icp_fit_score >= 15 then "C" '
          'else "Unscored"')

CANDIDATES = [
    ("veto: = 1",                'if lv_anti_icp_flag = 1 then "D" else "not-D"'),
    ("veto: bool() cast",        'if bool(lv_anti_icp_flag) then "D" else "not-D"'),
    ("veto: coalesce(...,0) = 1",'if coalesce(lv_anti_icp_flag, 0) = 1 then "D" else "not-D"'),
    ("veto: is_present guard",   'if is_present(lv_anti_icp_flag) and lv_anti_icp_flag = 1 then "D" else "not-D"'),
    ("FULL LADDER: = 1",              f'if lv_anti_icp_flag = 1 then "D" {LADDER}'),
    ("FULL LADDER: coalesce(...,0)",  f'if coalesce(lv_anti_icp_flag, 0) = 1 then "D" {LADDER}'),
    ("FULL LADDER: score coalesced too",
     f'if coalesce(lv_anti_icp_flag, 0) = 1 then "D" '
     f'elseif coalesce(lv_icp_fit_score, -1) >= 70 then "A" '
     f'elseif coalesce(lv_icp_fit_score, -1) >= 40 then "B" '
     f'elseif coalesce(lv_icp_fit_score, -1) >= 15 then "C" '
     f'else "Unscored"'),
]

SEED = '"seed"'


def body(r):
    try:
        j = r.json()
        return j.get("message") or json.dumps(j)[:1500]
    except Exception:
        return r.text[:1500]


def main() -> int:
    if not os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"):
        print("skipped (no credentials).")
        return 1
    if os.getenv("HUBSPOT_PORTAL_ID") != EXPECTED_PORTAL_ID:
        print(f"REFUSED: portal id != {EXPECTED_PORTAL_ID}.")
        return 1
    if os.getenv("ALLOW_SPIKE_PROPERTY_WRITE") != "true":
        print("DRY RUN (set ALLOW_SPIKE_PROPERTY_WRITE=true).")
        for n, f in CANDIDATES:
            print(f"  [{n}]\n    {f}\n")
        return 0

    print(f"=== creating disposable '{SPIKE}' ===")
    r = requests.post(BASE, headers=hs_headers(), timeout=30, json={
        "name": SPIKE, "label": "SPIKE tier calc 2 (disposable)",
        "groupName": "companyinformation", "type": "string",
        "fieldType": "calculation_equation", "calculationFormula": SEED,
    })
    print(f"POST {r.status_code}")
    if r.status_code not in (200, 201):
        print(body(r))
        return 1

    results = []
    try:
        for name, formula in CANDIDATES:
            r = requests.patch(f"{BASE}/{SPIKE}", headers=hs_headers(), timeout=30,
                               json={"calculationFormula": formula})
            ok = r.status_code in (200, 201, 204)
            print(f"\n=== [{name}] -> {r.status_code} {'ACCEPTED' if ok else 'REJECTED'}")
            print(f"    {formula}")
            msg = "" if ok else body(r)
            if msg:
                print(f"    {msg}")
            results.append({"candidate": name, "formula": formula,
                            "status": r.status_code, "accepted": ok, "body": msg})
    finally:
        d = requests.delete(f"{BASE}/{SPIKE}", headers=hs_headers(), timeout=30)
        gone = requests.get(f"{BASE}/{SPIKE}", headers=hs_headers(), timeout=30)
        print(f"\n=== archived: DELETE {d.status_code}; re-read {gone.status_code} (404 == gone) ===")

    out = Path(__file__).parent / "spike_tier_formula2_results.json"
    out.write_text(json.dumps(results, indent=2) + "\n")
    print(f"results -> {out}")
    print(f"ACCEPTED: {sum(1 for x in results if x['accepted'])}/{len(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
