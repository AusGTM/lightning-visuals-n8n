"""SPIKE (task #1): can lv_icp_fit_score's calculation_equation be made null-safe?

The defect: the formula is a bare five-term sum, and HubSpot blanks a calculated property
entirely when ANY referenced term is null (PORTAL-FACTS.md:176-180, live-reproduced in
Phase 40). gambling_score is null on ~95% of companies because its mapper flow fires on
lv_is_gambling_operator changing, and research answers null for that field unless a source
directly supports it. Result: no score, WF1 never fires.

This spike asks one question: does the formula syntax support any construct that treats a
null term as 0? If yes, that is a root-cause fix. If no, that is a clean negative and the
mitigation has to live elsewhere.

SAFETY
  - Operates on ONE disposable ZZ-SCORING-TEST-DELETE-ME-* company; never a real record.
  - The live formula is restored in a finally block, so an exception or a Ctrl-C still
    puts it back. The original string is captured from the LIVE property first, not from
    the committed file, so a restore cannot write a stale value.
  - Every candidate is also checked for CORRECTNESS with all five terms present. A formula
    that stops blanking but computes the wrong number is worse than the current one, because
    it fails silently.

Run:  .venv/bin/python .planning/phases/41-validation-data-import-end-to-end-proof/spike_null_safe_formula.py
"""

import json
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from src.hubspot_client import create_record, delete_record, get_record, hs_headers  # noqa: E402

PROP = "lv_icp_fit_score"
PROP_URL = f"https://api.hubapi.com/crm/v3/properties/companies/{PROP}"
COMPONENTS = ["org_type_score", "geography_score", "annual_revenue_score",
              "produces_content_score", "gambling_score"]
SETTLE_SECONDS = 8

# Four terms set, gambling_score deliberately absent -> reproduces the live defect.
FOUR_OF_FIVE = {"org_type_score": "40", "geography_score": "10",
                "annual_revenue_score": "10", "produces_content_score": "20"}
ALL_FIVE = dict(FOUR_OF_FIVE, gambling_score="-20")
EXPECTED_ALL_FIVE = 60   # 40+10+10+20-20
EXPECTED_FOUR_ONLY = 80  # 40+10+10+20+0  (what a null-safe formula SHOULD give)

# Candidate null-safe formula shapes. HubSpot's calculation_equation grammar is not
# publicly enumerated for this portal, so this is deliberately empirical: try each, record
# verbatim what the API says.
CANDIDATES = [
    ("if-guard",
     "org_type_score + geography_score + annual_revenue_score + produces_content_score + "
     "if(gambling_score, gambling_score, 0)"),
    ("coalesce",
     "org_type_score + geography_score + annual_revenue_score + produces_content_score + "
     "coalesce(gambling_score, 0)"),
    ("ifnull",
     "org_type_score + geography_score + annual_revenue_score + produces_content_score + "
     "ifnull(gambling_score, 0)"),
    ("is_known",
     "org_type_score + geography_score + annual_revenue_score + produces_content_score + "
     "if(is_known(gambling_score), gambling_score, 0)"),
    ("zero-add",
     "org_type_score + geography_score + annual_revenue_score + produces_content_score + "
     "(gambling_score + 0)"),
]


def read_formula() -> str:
    r = requests.get(PROP_URL, headers=hs_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("calculationFormula")


def write_formula(f: str):
    r = requests.patch(PROP_URL, headers=hs_headers(),
                       json={"calculationFormula": f}, timeout=30)
    return r.status_code, (r.text or "")[:300]


def score_of(cid: str):
    return get_record("companies", cid, [PROP] + COMPONENTS).get("properties", {}).get(PROP)


def main() -> int:
    original = read_formula()
    print("=== live formula (captured for restore) ===")
    print(f"  {original}\n")
    if not original:
        print("HALT: could not read the current formula; refusing to touch it.")
        return 1

    disposable = None
    results = []
    try:
        print("=== create disposable with 4 of 5 components (gambling_score absent) ===")
        created = create_record("companies", dict(
            FOUR_OF_FIVE, name="ZZ-SCORING-TEST-DELETE-ME-formula-spike"), dry_run=False)
        disposable = created.get("id")
        print(f"  id={disposable}")
        time.sleep(SETTLE_SECONDS)
        baseline = score_of(disposable)
        print(f"  {PROP} under the CURRENT formula: {baseline!r}")
        print(f"  -> defect reproduced: {baseline in (None, '')}\n")

        for name, formula in CANDIDATES:
            print(f"=== candidate: {name} ===")
            code, body = write_formula(formula)
            accepted = code in (200, 201, 204)
            print(f"  PATCH {code} accepted={accepted}")
            if not accepted:
                print(f"  rejected: {body[:180]}")
                results.append({"candidate": name, "accepted": False,
                                "http": code, "error": body[:300]})
                continue

            time.sleep(SETTLE_SECONDS)
            null_case = score_of(disposable)
            # correctness with every term present
            requests.patch(
                f"https://api.hubapi.com/crm/v3/objects/companies/{disposable}",
                headers=hs_headers(), json={"properties": ALL_FIVE}, timeout=30)
            time.sleep(SETTLE_SECONDS)
            full_case = score_of(disposable)
            # put the record back to the 4-of-5 shape for the next candidate
            requests.patch(
                f"https://api.hubapi.com/crm/v3/objects/companies/{disposable}",
                headers=hs_headers(),
                json={"properties": {"gambling_score": ""}}, timeout=30)

            null_ok = str(null_case) == str(EXPECTED_FOUR_ONLY)
            full_ok = str(full_case) == str(EXPECTED_ALL_FIVE)
            print(f"  null term  -> {null_case!r}  (want {EXPECTED_FOUR_ONLY}) {'OK' if null_ok else 'NO'}")
            print(f"  all 5 terms-> {full_case!r}  (want {EXPECTED_ALL_FIVE}) {'OK' if full_ok else 'NO'}")
            results.append({"candidate": name, "accepted": True, "http": code,
                            "null_term_value": null_case, "null_term_ok": null_ok,
                            "all_terms_value": full_case, "all_terms_ok": full_ok,
                            "verdict": "VIABLE" if (null_ok and full_ok) else "accepted-but-wrong"})
            print()

    finally:
        print("=== restore ===")
        code, body = write_formula(original)
        back = read_formula()
        print(f"  PATCH {code}; formula restored correctly: {back == original}")
        if back != original:
            print(f"  !! MISMATCH — expected: {original}\n     got: {back}")
        if disposable:
            delete_record("companies", disposable, dry_run=False)
            print(f"  disposable {disposable} deleted")

    out = Path(__file__).with_name("41-formula-spike-results.json")
    out.write_text(json.dumps(
        {"original_formula": original, "candidates": results}, indent=2, default=str))
    viable = [r for r in results if r.get("verdict") == "VIABLE"]
    print(f"\n=== VERDICT: {len(viable)} viable of {len(CANDIDATES)} candidates ===")
    for r in viable:
        print(f"  VIABLE: {r['candidate']}")
    print(f"Evidence: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
