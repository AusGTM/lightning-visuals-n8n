"""SPIKE v2 (task #1 re-run): can lv_icp_fit_score's calculation_equation be made null-safe?

v1 (spike_null_safe_formula.py) was CONFOUNDED — see 41-FORMULA-SPIKE.md. It never created a
null term (a stamping flow sets gambling_score=0 on new companies), so every candidate was
measured against a fully populated record, and it read only the score while ignoring the
components it had already fetched, so stale reads looked like results.

v2 fixes exactly that:
  1. Create BARE, wait for the create-time stamp to land, THEN clear all five components.
  2. Gate on the defect reproducing under the ORIGINAL formula (4 of 5 set -> score blank).
     If it does not reproduce, HALT. That gate is the whole point of the re-run.
  3. Every read returns all six properties and is re-read until the score RECONCILES with the
     components seen in the same GET. No fixed sleeps as proof.
  4. Each candidate is judged on BOTH cases: null term (want 80) and all five (want 60).
     A formula that stops blanking but computes wrong is worse than the status quo.
  5. Candidates are identity-preserving with all terms present, so the live portfolio (all 66
     records have populated components) sees zero drift while the spike runs.
  6. finally: restore + INDEPENDENT re-read, delete disposable, search for leaked disposables.

Run:  .venv/bin/python .planning/phases/41-validation-data-import-end-to-end-proof/spike_null_safe_formula_v2.py
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
PROP_URL = f"https://api.hubapi.com/crm/v3/properties/companies/{PROP}"
OBJ_URL = "https://api.hubapi.com/crm/v3/objects/companies"
COMPONENTS = ["org_type_score", "geography_score", "annual_revenue_score",
              "produces_content_score", "gambling_score"]
DISPOSABLE_NAME = "ZZ-SCORING-TEST-DELETE-ME-formula-spike-v2"

FOUR_OF_FIVE = {"org_type_score": "40", "geography_score": "10",
                "annual_revenue_score": "10", "produces_content_score": "20"}
ALL_FIVE = dict(FOUR_OF_FIVE, gambling_score="-20")
CLEAR_ALL = {k: "" for k in COMPONENTS}
EXPECT_FULL = 60   # 40+10+10+20-20
EXPECT_NULL = 80   # 40+10+10+20+0   (what a null-safe formula SHOULD give)

STAMP_WAIT = 120       # how long to wait for the create-time stamping flow
STABLE_TIMEOUT = 150    # per-read reconcile budget after a formula change
POLL = 6
PATCH_SPACING = 5       # seconds between formula PATCHes (v1's rapid cycle drew a 401)

# ponytail: identity-preserving shapes only. max(x,0) is deliberately excluded — gambling_score
# is a NEGATIVE deduction, so max() would silently change scores on populated records.
BASE = "org_type_score + geography_score + annual_revenue_score + produces_content_score + "
CANDIDATES = [
    ("is_present-stmt-then",
     BASE + "if is_present(gambling_score) then gambling_score else 0"),
    ("is_present-stmt-brace",
     BASE + "if (is_present(gambling_score)) { gambling_score } else { 0 }"),
    ("is_present-mul",
     BASE + "is_present(gambling_score) * gambling_score"),
    ("coalesce",
     BASE + "coalesce(gambling_score, 0)"),
    ("zero-add",
     BASE + "(gambling_score + 0)"),
]


def req(method: str, url: str, **kw):
    """One retry with backoff on 401/429 — v1 died on a transient 401 mid-run."""
    for attempt in (1, 2):
        r = requests.request(method, url, headers=hs_headers(), timeout=30, **kw)
        if r.status_code in (401, 429) and attempt == 1:
            print(f"  [retry] {method} {r.status_code}; backing off 10s")
            time.sleep(10)
            continue
        return r
    return r


def read_formula():
    r = req("GET", PROP_URL)
    r.raise_for_status()
    return r.json().get("calculationFormula")


def write_formula(f: str):
    r = req("PATCH", PROP_URL, json={"calculationFormula": f})
    return r.status_code, (r.text or "")


def props_of(cid: str) -> dict:
    return get_record("companies", cid, [PROP] + COMPONENTS).get("properties", {})


def num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def read_until_reconciled(cid: str, want_components: dict, want_score,
                          timeout=STABLE_TIMEOUT) -> tuple[dict, bool]:
    """Re-read until BOTH the components and the score match what we expect in the SAME GET.

    want_score is a number, or None meaning 'must read blank'. Returns (last_props, ok).
    Reconciling against components read in the same response is what makes a stale read
    fail loudly instead of masquerading as a result.
    """
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


def show(label: str, p: dict):
    comps = " ".join(f"{k.split('_score')[0]}={p.get(k)!r}" for k in COMPONENTS)
    print(f"  {label}: {PROP}={p.get(PROP)!r} | {comps}")


def main() -> int:
    original = read_formula()
    print("=== live formula (captured for restore) ===")
    print(f"  {original}\n")
    if not original:
        print("HALT: could not read the current formula; refusing to touch it.")
        return 1

    disposable = None
    results = []
    reproduced = False
    try:
        # --- 1. create BARE, let the create-time stamping flow land -------------------
        print("=== create disposable (bare — no components set) ===")
        disposable = create_record(
            "companies", {"name": DISPOSABLE_NAME}, dry_run=False).get("id")
        print(f"  id={disposable}")
        print(f"  waiting up to {STAMP_WAIT}s for the create-time 0-stamp to land...")
        deadline = time.time() + STAMP_WAIT
        while time.time() < deadline:
            p = props_of(disposable)
            if p.get("gambling_score") not in (None, ""):
                show("stamped", p)
                break
            time.sleep(POLL)
        else:
            show("no stamp observed (fine — clearing anyway)", props_of(disposable))

        # --- 2. clear all five, prove the score goes blank ----------------------------
        print("\n=== clear all five components ===")
        req("PATCH", f"{OBJ_URL}/{disposable}", json={"properties": CLEAR_ALL})
        p, ok = read_until_reconciled(disposable, CLEAR_ALL, None)
        show("cleared", p)
        if not ok:
            print("  HALT: components would not clear / score did not go blank.")
            return 1

        # --- 3. GATE: defect must reproduce under the ORIGINAL formula ----------------
        print("\n=== gate: 4 of 5 set, gambling_score null, ORIGINAL formula ===")
        req("PATCH", f"{OBJ_URL}/{disposable}", json={"properties": FOUR_OF_FIVE})
        p, ok = read_until_reconciled(disposable, FOUR_OF_FIVE, None)
        show("4-of-5", p)
        reproduced = ok and num(p.get("gambling_score")) is None
        print(f"  defect reproduced (score blank with a genuine null term): {reproduced}")
        if not reproduced:
            print("  HALT: without a real null term this run measures nothing. "
                  "That was v1's exact failure.")
            return 1

        # --- 4. candidates ------------------------------------------------------------
        for name, formula in CANDIDATES:
            print(f"\n=== candidate: {name} ===")
            print(f"  {formula}")
            time.sleep(PATCH_SPACING)
            code, body = write_formula(formula)
            accepted = code in (200, 201, 204)
            print(f"  PATCH {code} accepted={accepted}")
            if not accepted:
                print(f"  rejected: {body[:400]}")
                results.append({"candidate": name, "formula": formula, "accepted": False,
                                "http": code, "error_full": body})  # full body = grammar map
                continue

            null_p, null_ok = read_until_reconciled(disposable, FOUR_OF_FIVE, EXPECT_NULL)
            show(f"null term (want {EXPECT_NULL})", null_p)

            req("PATCH", f"{OBJ_URL}/{disposable}", json={"properties": ALL_FIVE})
            full_p, full_ok = read_until_reconciled(disposable, ALL_FIVE, EXPECT_FULL)
            show(f"all five (want {EXPECT_FULL})", full_p)

            # back to the 4-of-5 shape for the next candidate
            req("PATCH", f"{OBJ_URL}/{disposable}",
                json={"properties": {"gambling_score": ""}})

            verdict = "VIABLE" if (null_ok and full_ok) else "accepted-but-wrong"
            print(f"  null_ok={null_ok} full_ok={full_ok} -> {verdict}")
            results.append({"candidate": name, "formula": formula, "accepted": True,
                            "http": code,
                            "null_case": {k: null_p.get(k) for k in [PROP] + COMPONENTS},
                            "null_ok": null_ok,
                            "full_case": {k: full_p.get(k) for k in [PROP] + COMPONENTS},
                            "full_ok": full_ok, "verdict": verdict})

    finally:
        print("\n=== restore ===")
        code, _ = write_formula(original)
        time.sleep(3)
        back = read_formula()          # independent re-read, not the PATCH's own response
        print(f"  PATCH {code}; formula restored correctly: {back == original}")
        if back != original:
            print(f"  !! MISMATCH — expected: {original}\n     got: {back}")
        if disposable:
            delete_record("companies", disposable, dry_run=False)
            print(f"  disposable {disposable} deleted")
        leaks = search_records(
            "companies",
            [{"propertyName": "name", "operator": "CONTAINS_TOKEN",
              "value": "ZZ-SCORING-TEST-DELETE-ME"}], ["name"], limit=100)
        print(f"  leaked disposables still live: {leaks.get('total')}")

    out = Path(__file__).with_name("41-formula-spike-v2-results.json")
    out.write_text(json.dumps({"original_formula": original,
                               "defect_reproduced": reproduced,
                               "candidates": results}, indent=2, default=str))
    viable = [r for r in results if r.get("verdict") == "VIABLE"]
    print(f"\n=== VERDICT: {len(viable)} viable of {len(CANDIDATES)} ===")
    for r in viable:
        print(f"  VIABLE: {r['candidate']}  ->  {r['formula']}")
    print(f"Evidence: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
