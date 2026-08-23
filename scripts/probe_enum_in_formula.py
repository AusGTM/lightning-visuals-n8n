#!/usr/bin/env python3
"""scripts/probe_enum_in_formula.py

Quick task 260823-ono (CP1) -- settles RESEARCH.md's headline open question before
`lv_named_account_priority` is created: is `string(<enum property>)` readable inside a
HubSpot `calculation_equation` on this portal? D-20 (50-CONTEXT.md) concluded "no" from a
single bare-identifier variant (`if lv_anti_icp_flag then ...`); HubSpot's own docs require
the `string()`/`bool()` wrapper for non-numeric properties, and both tokens are in this
portal's own 400-body token list (41-FORMULA-SPIKE.md) -- so D-20's negative is probably an
artifact of the wrong syntax, not a portal limitation. This probe re-tests with the
wrapper, on a DISPOSABLE calculated property reading the EXISTING `lv_org_type` enum (both
populated and blank records already exist), so no new production property is spent testing
the premise.

Reuses scripts/check_tier_null_propagation.py's `_create_calculated_property`,
`_get_property_live`, `_archive_and_confirm_gone` (POST/GET/DELETE
crm/v3/properties/companies, disposable naming, teardown confirmed by independent re-read)
rather than re-implementing them -- same idiom, same portal guard.

Three questions (RESEARCH P1/P2/P3), one disposable property per variant tried:
    P1 -- does the `string(...) equals '...'` wrapper PARSE?          (create: 200 vs 400)
    P2 -- does it READ the value? (parse != readable -- D-04's booleancheckbox parsed and
          still read null)                                             (poll ATC -> 'HIT')
    P3 -- does a NULL enum in the condition blank the whole result,
          rather than falling through to else?                        (poll a never-enriched
                                                                         company -> 'MISS',
                                                                         NOT blank)

Every 400 on a variant creates NOTHING (a failed create burns no property) and prints the
response body verbatim -- the 41-spike's token list is positional, so the body at the
failing parse position is the whole value of a failed attempt; the ladder keeps going, it
never stops after one negative (D-20's own mistake). Variants are tried IN ORDER
(VARIANTS below); the loop stops at the first variant whose P1+P2+P3 all pass. The last
variant in the ladder is the `is_present`-guarded condition -- RESEARCH's cheap repair if
an earlier variant parses and reads (P1+P2 pass) but a null condition still blanks the
result (P3 fails); trying it last, unconditionally, means a P3-only failure on any earlier
variant is naturally repaired without a special case.

D-22 is mandatory on every live read: poll to a populated value or a 300s ceiling (>=2
reads >=90s apart), never a single immediate read -- a race here is exactly what produced
Phase 50's wrong D-04 conclusion (a value that had not backfilled yet was misread as
absent).

Two-key write gate (repo idiom, same shape as check_tier_null_propagation.py, its OWN
dedicated key -- never ALLOW_HUBSPOT_PROPERTY_WRITES, which is scoped to
sync_hubspot_properties.py's migration): DRY_RUN=false AND ALLOW_ENUM_PROBE=true, plus the
portal guard. `--plan` (default) prints the variant ladder and makes zero HTTP calls.

`.env` is Read/Bash permission-blocked this session -- the operator invocation is:
    ALLOW_ENUM_PROBE=true DRY_RUN=false .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/probe_enum_in_formula.py', run_name='__main__')"

Usage:
    python scripts/probe_enum_in_formula.py                 # --plan (default), zero calls
    ALLOW_ENUM_PROBE=true DRY_RUN=false \
        python scripts/probe_enum_in_formula.py               # live probe
"""
import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*`/`scripts.*` imports resolve

from scripts.check_tier_null_propagation import (  # noqa: E402
    _archive_and_confirm_gone,
    _create_calculated_property,
    _get_property_live,
)

DEFAULT_OUT = (
    ROOT / ".planning" / "quick" / "260823-ono-metro-peak-body-override-rule-tier-atc-m"
    / "260823-ono-PROBE-VERDICT.json"
)

EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

PROBE_PREFIX = "zz_probe_enum_read_"
TARGET_VALUE = "individual_club_team"

# ATC -- a known individual_club_team company (260823-ono-CONTEXT.md's baseline read,
# re-confirmed live by Task 1 step 1). P2's HIT target.
ATC_ID = "9605284724"

# D-22 poll shape -- a fixed ceiling and a minimum gap between reads, never a single
# immediate read.
POLL_CEILING_SECONDS = 300.0
POLL_INTERVAL_SECONDS = 90.0

# The variant ladder, tried in order (RESEARCH's exact sequence: equals vs =, single vs
# double quotes, contains() as an alternate predicate, is_present()-guarded last as the
# cheap repair for a P3-only failure). Each is a full `if <cond> then 'HIT' else 'MISS'`
# calculation_equation formula string against the EXISTING lv_org_type property.
VARIANTS = [
    ("p1_equals_single_quote",
     f"if string(lv_org_type) equals '{TARGET_VALUE}' then 'HIT' else 'MISS'"),
    ("p1b_eq_sign",
     f"if string(lv_org_type) = '{TARGET_VALUE}' then 'HIT' else 'MISS'"),
    ("p1c_double_quote",
     f"if string(lv_org_type) equals \"{TARGET_VALUE}\" then 'HIT' else 'MISS'"),
    ("p1d_contains",
     f"if contains(string(lv_org_type), '{TARGET_VALUE}') then 'HIT' else 'MISS'"),
    ("p1e_is_present_guarded",
     f"if is_present(string(lv_org_type)) and string(lv_org_type) equals "
     f"'{TARGET_VALUE}' then 'HIT' else 'MISS'"),
]


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_ENUM_PROBE", "false").lower() == "true"
    return (not dry_run) and allow


def _assert_no_secrets(text: str) -> None:
    # Copied verbatim from scripts/check_tier_null_propagation.py / check_schema_drift.py.
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN") or ""
    assert "Authorization" not in text, "serializer leaked the Authorization header"
    if token:
        assert token not in text, "serializer leaked the bearer token value"
    assert "HUBSPOT_PRIVATE_APP_TOKEN" not in text, "serializer leaked the token env var name"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _try_create(name: str, formula: str):
    """POST crm/v3/properties/companies with a type:string calculation_equation formula.
    Returns (status_code, body_text) -- never raises on non-2xx, so the caller can print
    the 400 body's positional token list and move to the next variant without losing the
    response."""
    import requests
    from src.hubspot_client import BASE_URL, hs_headers

    body = {
        "name": name, "label": f"[disposable] {name}", "type": "string",
        "fieldType": "calculation_equation", "groupName": "companyinformation",
        "options": [], "calculationFormula": formula,
    }
    r = requests.post(f"{BASE_URL}/crm/v3/properties/companies", headers=hs_headers(),
                       json=body, timeout=30)
    return r.status_code, r.text


def _get_company_prop(company_id: str, prop_name: str):
    from src.hubspot_client import get_record
    return get_record("companies", company_id, [prop_name])["properties"].get(prop_name)


def find_never_enriched_company():
    """Live-derived (RESEARCH's explicit "live-derived" instruction) -- never a hard-coded
    id, so this stays correct as records get enriched over time. Any company missing
    lv_org_type qualifies as P3's MISS target."""
    from src.hubspot_client import search_records
    result = search_records(
        "companies",
        [{"propertyName": "lv_org_type", "operator": "NOT_HAS_PROPERTY"}],
        ["name"],
        limit=1,
    )
    results = result.get("results", [])
    return results[0]["id"] if results else None


def poll_d22(company_id: str, prop_name: str, ceiling: float = POLL_CEILING_SECONDS,
             interval: float = POLL_INTERVAL_SECONDS):
    """D-22: an immediate first read, then re-reads >=`interval` seconds apart until two
    consecutive reads agree or `ceiling` elapses. Never a single immediate read -- that
    race produced Phase 50's wrong D-04 conclusion. Returns (final_value, elapsed_seconds,
    all_reads)."""
    start = time.monotonic()
    value = _get_company_prop(company_id, prop_name)
    reads = [{"elapsed": 0.0, "value": value}]
    while True:
        elapsed = time.monotonic() - start
        remaining = ceiling - elapsed
        if remaining <= 0:
            return value, elapsed, reads
        time.sleep(min(interval, remaining))
        new_value = _get_company_prop(company_id, prop_name)
        elapsed = time.monotonic() - start
        reads.append({"elapsed": round(elapsed, 1), "value": new_value})
        if new_value == value:
            return new_value, elapsed, reads
        value = new_value


def _teardown_probe_property(name: str) -> bool:
    gone = _archive_and_confirm_gone("companies", name)
    print(f"  archived+confirmed-gone {name}: {gone}")
    if not gone:
        print(f"TEARDOWN LEAKED -- {name} was not confirmed gone.")
    return gone


def probe_one_variant(variant_id: str, formula: str, never_enriched_id):
    """Creates ONE disposable calculated property for this variant, runs P2/P3 if it
    parses, and ALWAYS tears it down (a leaked disposable is a defect regardless of the
    probe's verdict). Returns a result dict; never raises past teardown."""
    name = f"{PROBE_PREFIX}{uuid.uuid4().hex[:8]}"
    print(f"\n--- variant {variant_id} ---\nformula: {formula}\ncreating {name} ...")
    status, body = _try_create(name, formula)

    result = {
        "variant": variant_id, "formula": formula, "property_name": name,
        "create_status": status, "p1_parses": status in (200, 201),
        "p2_reads_value": False, "p3_null_falls_through": False,
        "atc_value": None, "atc_reads": None,
        "never_enriched_id": never_enriched_id, "never_enriched_value": None,
        "never_enriched_reads": None, "teardown_gone": None,
    }

    if status not in (200, 201):
        print(f"  -> HTTP {status} FAILED to parse. Body (verbatim, token list is "
              f"positional -- read it at the failing parse position):\n  {body}")
        return result

    print(f"  -> HTTP {status} CREATED. Polling P2 (ATC {ATC_ID}, expect 'HIT', D-22) ...")
    try:
        atc_value, atc_elapsed, atc_reads = poll_d22(ATC_ID, name)
        print(f"     final read after {atc_elapsed:.0f}s: {atc_value!r}")
        result["atc_value"] = atc_value
        result["atc_reads"] = atc_reads
        result["p2_reads_value"] = (atc_value == "HIT")

        if never_enriched_id:
            print(f"  Polling P3 (never-enriched {never_enriched_id}, expect 'MISS' NOT "
                  "blank, D-22) ...")
            ne_value, ne_elapsed, ne_reads = poll_d22(never_enriched_id, name)
            print(f"     final read after {ne_elapsed:.0f}s: {ne_value!r}")
            result["never_enriched_value"] = ne_value
            result["never_enriched_reads"] = ne_reads
            result["p3_null_falls_through"] = (ne_value == "MISS")
        else:
            print("  NO never-enriched company found live -- P3 cannot be evaluated for "
                  "this variant (recorded as False/untested).")
    finally:
        result["teardown_gone"] = _teardown_probe_property(name)

    return result


def run_probe(out_path: Path) -> int:
    never_enriched_id = find_never_enriched_company()
    if never_enriched_id is None:
        print("WARNING: no never-enriched company found live -- P3 will be untested for "
              "every variant.")

    attempts = []
    winner = None
    for variant_id, formula in VARIANTS:
        result = probe_one_variant(variant_id, formula, never_enriched_id)
        attempts.append(result)
        if result["p1_parses"] and result["p2_reads_value"] and result["p3_null_falls_through"]:
            winner = result
            print(f"\nWINNER: variant {variant_id} passes P1+P2+P3.")
            break

    if winner is not None:
        p1, p2, p3 = True, True, True
        winning_condition = winner["formula"]
        winning_variant = winner["variant"]
    else:
        # No variant achieved a full pass. Report the best-observed p1/p2/p3 across all
        # attempted variants so the verdict is informative, not just "all False" when e.g.
        # every variant parsed and read but none survived a null condition.
        p1 = any(a["p1_parses"] for a in attempts)
        p2 = any(a["p2_reads_value"] for a in attempts)
        p3 = any(a["p3_null_falls_through"] for a in attempts)
        winning_condition = None
        winning_variant = None
        print("\nNO VARIANT achieved a full P1+P2+P3 pass -- halt-b: numeric-mirror "
              "fallback required, per CONTEXT.md's pre-authorized fallback. Surface to "
              "the operator before building it (a separate authorization and re-plan).")

    leaked = [a["property_name"] for a in attempts if a["teardown_gone"] is False]

    result = {
        "p1": p1, "p2": p2, "p3": p3,
        "winning_variant": winning_variant,
        "winning_condition": winning_condition,
        "never_enriched_id": never_enriched_id,
        "attempts": attempts,
        "all_disposables_confirmed_gone": not leaked,
        "leaked_properties": leaked,
        "checked_at": _now_iso(),
    }

    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    _assert_no_secrets(text)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    print(f"\nwrote {out_path}")
    print(json.dumps(result, indent=2))

    return 0 if (winner is not None and not leaked) else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                         help="Path to write the probe verdict JSON to.")
    parser.add_argument("--plan", action="store_true",
                         help="Print the variant ladder and make zero HTTP calls "
                              "(default behavior regardless of this flag -- explicit for "
                              "readability at call sites).")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this "
              "probe.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    if not _writes_allowed():
        print("--plan (default) -- no writes will be made. Set DRY_RUN=false AND "
              "ALLOW_ENUM_PROBE=true to run the live probe.\n")
        print("Variant ladder (tried in order until one passes P1+P2+P3):")
        for variant_id, formula in VARIANTS:
            print(f"  {variant_id}: {formula}")
        return 0

    return run_probe(Path(args.out))


if __name__ == "__main__":
    sys.exit(main())
