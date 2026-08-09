"""Post-apply verification for the null-safe lv_icp_fit_score formula (Phase 41 task #3).

Three things must hold after the PATCH:

  A. The 646 never-enriched companies are still UNSCORED. org_type_score is deliberately
     left unguarded so blank keeps meaning "never scored"; if the count of companies with
     lv_icp_fit_score jumps from 66 toward 712, the sentinel failed and the tier flow is
     about to enroll the whole portfolio.
  B. On a disposable: all five components cleared -> score BLANK (sentinel holds), and
     four of five with gambling_score null -> score 80 (the defect is fixed).
  C. No leaked disposables.

Read-only apart from the single disposable it creates and deletes.

Run:  HUBSPOT_PORTAL_ID=22617666 .venv/bin/python \
        .planning/phases/41-validation-data-import-end-to-end-proof/verify_null_safe_formula.py
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

from src.hubspot_client import (  # noqa: E402
    create_record, delete_record, get_record, hs_headers, search_records,
)

PROP = "lv_icp_fit_score"
OBJ_URL = "https://api.hubapi.com/crm/v3/objects/companies"
COMPONENTS = ["org_type_score", "geography_score", "annual_revenue_score",
              "produces_content_score", "gambling_score"]
FOUR_OF_FIVE = {"org_type_score": "40", "geography_score": "10",
                "annual_revenue_score": "10", "produces_content_score": "20"}
CLEAR_ALL = {k: "" for k in COMPONENTS}
STAMP_WAIT, SETTLE, POLL = 120, 120, 6


def count(filters):
    return search_records("companies", filters, ["name"], limit=1).get("total")


def props_of(cid):
    return get_record("companies", cid, [PROP] + COMPONENTS).get("properties", {})


def num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def read_until(cid, want_components, want_score, timeout=SETTLE):
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        last = props_of(cid)
        comps_ok = all(num(last.get(k)) == num(v) for k, v in want_components.items())
        score = num(last.get(PROP))
        score_ok = (score is None) if want_score is None else (score == want_score)
        if comps_ok and score_ok:
            return last, True
        time.sleep(POLL)
    return last, False


def main() -> int:
    out = {}
    print("=== A. portfolio counts (sentinel must hold) ===")
    total = count([])
    scored = count([{"propertyName": PROP, "operator": "HAS_PROPERTY"}])
    with_components = count([{"propertyName": "org_type_score", "operator": "HAS_PROPERTY"}])
    blank_with_inputs = count([
        {"propertyName": "org_type_score", "operator": "HAS_PROPERTY"},
        {"propertyName": PROP, "operator": "NOT_HAS_PROPERTY"}])
    print(f"  total companies          {total}")
    print(f"  have {PROP}   {scored}")
    print(f"  have org_type_score      {with_components}")
    print(f"  inputs but blank score   {blank_with_inputs}  (detector condition)")
    sentinel_ok = scored == with_components and blank_with_inputs == 0
    print(f"  A PASS: {sentinel_ok}")
    out["counts"] = {"total": total, "scored": scored,
                     "with_components": with_components,
                     "blank_with_inputs": blank_with_inputs, "pass": sentinel_ok}

    print("\n=== B. disposable behaviour ===")
    disposable = None
    b_ok = False
    try:
        disposable = create_record("companies", {
            "name": "ZZ-SCORING-TEST-DELETE-ME-verify-null-safe"}, dry_run=False).get("id")
        print(f"  id={disposable}; waiting for the create-time stamp...")
        deadline = time.time() + STAMP_WAIT
        while time.time() < deadline:
            if props_of(disposable).get("gambling_score") not in (None, ""):
                break
            time.sleep(POLL)

        requests.patch(f"{OBJ_URL}/{disposable}", headers=hs_headers(),
                       json={"properties": CLEAR_ALL}, timeout=30)
        cleared, cleared_ok = read_until(disposable, CLEAR_ALL, None)
        print(f"  all five cleared -> {PROP}={cleared.get(PROP)!r} "
              f"(want blank) {'OK' if cleared_ok else 'NO'}")

        requests.patch(f"{OBJ_URL}/{disposable}", headers=hs_headers(),
                       json={"properties": FOUR_OF_FIVE}, timeout=30)
        four, four_ok = read_until(disposable, FOUR_OF_FIVE, 80)
        print(f"  4 of 5, gambling null -> {PROP}={four.get(PROP)!r} "
              f"(want 80) {'OK' if four_ok else 'NO'}")

        b_ok = cleared_ok and four_ok
        out["disposable"] = {
            "cleared_score": cleared.get(PROP), "cleared_ok": cleared_ok,
            "four_of_five_score": four.get(PROP), "four_of_five_ok": four_ok,
            "pass": b_ok}
    finally:
        if disposable:
            delete_record("companies", disposable, dry_run=False)
            print(f"  disposable {disposable} deleted")

    print("\n=== C. leak check ===")
    leaks = count([{"propertyName": "name", "operator": "CONTAINS_TOKEN",
                    "value": "ZZ-SCORING-TEST-DELETE-ME"}])
    print(f"  leaked disposables: {leaks}")
    out["leaks"] = leaks

    verdict = sentinel_ok and b_ok
    out["verdict"] = "PASS" if verdict else "FAIL"
    path = Path(__file__).with_name("41-null-safe-formula-verification.json")
    path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n=== VERDICT: {out['verdict']} ===\nEvidence: {path}")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
