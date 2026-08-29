#!/usr/bin/env python3
"""scripts/probe_number_floor_in_formula.py

Quick task 260823-ono (CP1b) -- the operator-mandated live proof BEFORE the production
FORMULA-F push: "if the floor is null, does it still contribute to scoring?" CP1 proved
(halt-b, 260823-ono-PROBE-VERDICT.json) that an enumeration is unreadable in a
`calculation_equation` on this portal; the retargeted mechanism is a plain operator-
editable NUMBER property, `lv_named_account_score_floor` (CONTEXT.md's "Amendment
2026-08-23"). This probe proves the candidate formula on DISPOSABLE properties, on real
records, before FORMULA-F is ever pushed onto the live `lv_icp_fit_score` property that
governs all ~712 companies.

Five checks (CONTEXT amendment / 260823-ono-PLAN.md Task 1b step 7), every comparison
self-calibrated against the record's own LIVE PRODUCTION lv_icp_fit_score (compared as
floats -- HubSpot returns "55", not 55), never a hard-coded 55/80 that would false-fail
if a base has drifted since Task 1:

    Phase 1, no floor written anywhere:
      (a) ATC (scored, floor unset)              -> == live production base, not blank
      (b) never-enriched control (floor unset,
          NEVER written)                          -> stays blank, production also blank

    Phase 2, floor 60 written on exactly THREE records (ATC, Perth, Tier A control --
    the never-enriched control is NEVER written a floor value; doing so would destroy
    check (b), the operator's headline question):
      (c) Perth (blank inputs, floor 60)          -> 60, production still blank
      (d) Tier A control (base 80, floor 60)      -> == live production base (80), >60
                                                       -- proves no cap
      (e) ATC (base 55, floor 60)                 -> 60, != live production base (55)
                                                       -- proves the floor bit

Reuses scripts/check_tier_null_propagation.py's `_create_numeric_property`,
`_get_property_live`, `_archive_and_confirm_gone` (POST/GET/DELETE
crm/v3/properties/companies, disposable naming, teardown confirmed by independent
re-read). Does NOT reuse or mutate its `_create_calculated_property` -- that one
hardcodes `type: "string"` and check_tier_null_propagation.py's own probe depends on
that shape. This module writes its own `_create_calculated_number_property`, `type:
"number"`, matching the live `lv_icp_fit_score` shape exactly.

Poll shape -- CORRECTED, do NOT copy `poll_d22` from probe_enum_in_formula.py. That
function returns as soon as two consecutive reads agree, which is wrong when polling for
a TRANSITION: HubSpot's calculation backfill is ~70-130s, so reads at 0s and 90s can both
return the stale pre-write value, agree, and stop -- reporting the old value as "stable"
and false-failing (c)/(d)/(e). This module polls until the phase's TRANSITION checks
reach their expected value or a 300s ceiling (never a bare stability stop before 180s
elapsed), reading every id in the phase in ONE batched tick (never serially per id --
serial 90s waits per record is what made CP1 a 20-minute run). No-change checks ((b),
(d)) never exit the phase early on their own account -- they ride the transition checks'
evidence that the portal has recomputed. Check (b) is the one exception that DOES fail
immediately, at any tick, if it is ever non-blank -- that is not something to poll past.

Two-key write gate (repo idiom, its OWN dedicated key -- never ALLOW_HUBSPOT_PROPERTY_WRITES
or ALLOW_FORMULA_WRITE, which are scoped to the production property-create and formula-push
respectively): DRY_RUN=false AND ALLOW_FLOOR_PROBE=true, plus the portal guard. `--plan`
(default) prints FORMULA-F with the disposable substitution and the (a)-(e) check table,
and makes zero HTTP calls.

`.env` is Read/Bash permission-blocked this session -- the operator invocation is:
    ALLOW_FLOOR_PROBE=true DRY_RUN=false .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/probe_number_floor_in_formula.py', run_name='__main__')"

Usage:
    python scripts/probe_number_floor_in_formula.py                 # --plan (default), zero calls
    ALLOW_FLOOR_PROBE=true DRY_RUN=false \
        python scripts/probe_number_floor_in_formula.py               # live probe
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
    _create_numeric_property,
    _get_property_live,
)
from src.guards import assert_keys_equal, assert_no_secrets  # noqa: E402

DEFAULT_OUT = (
    ROOT / ".planning" / "quick" / "260823-ono-metro-peak-body-override-rule-tier-atc-m"
    / "260823-ono-FLOOR-PROBE-VERDICT.json"
)

EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

NUMBER_PROP_PREFIX = "zz_probe_floor_"
CALC_PROP_PREFIX = "zz_probe_fitscore_"

FLOOR_PLACEHOLDER = "lv_named_account_score_floor"  # what gets substituted, both occurrences

# FORMULA-F, verbatim (260823-ono-PLAN.md's "The formula (FORMULA-F)" section). Every
# occurrence of FLOOR_PLACEHOLDER is substituted for the disposable number property's
# name at probe time -- the *_score component references stay real, so the probe
# computes real bases on real records.
COALESCED_BASE = (
    "coalesce(org_type_score, 0) + coalesce(geography_score, 0) + "
    "coalesce(annual_revenue_score, 0) + coalesce(produces_content_score, 0) + "
    "coalesce(gambling_score, 0)"
)
BARE_BASE = (
    "org_type_score + coalesce(geography_score, 0) + coalesce(annual_revenue_score, 0) + "
    "coalesce(produces_content_score, 0) + coalesce(gambling_score, 0)"
)


def formula_f_for(floor_prop: str) -> str:
    return (
        f"if coalesce({floor_prop}, 0) > 0 then "
        f"max({COALESCED_BASE}, coalesce({floor_prop}, 0)) "
        f"else {BARE_BASE}"
    )


def formula_f_nested_fallback_for(floor_prop: str) -> str:
    """The plan's disclosed fallback if `max` misbehaves under CP1b -- statement-form
    nesting, base text repeated verbatim rather than a function-form if(a,b,c), which is
    a confirmed 400 on this portal."""
    coalesced_floor = f"coalesce({floor_prop}, 0)"
    return (
        f"if {coalesced_floor} > 0 then "
        f"(if {COALESCED_BASE} < {coalesced_floor} then {coalesced_floor} "
        f"else {COALESCED_BASE}) "
        f"else {BARE_BASE}"
    )


# Live record ids (260823-ono-CONTEXT.md / 260823-ono-PREDICTIONS.json).
ATC_ID = "9605284724"                # scored, base 55, individual_club_team
PERTH_ID = "9604794662"              # all-blank inputs, unscored
TIER_A_CONTROL_ID = "9605284722"     # Racing and Wagering WA, base 80, Tier A
NEVER_ENRICHED_CONTROL_ID = "9604773165"  # Newcastle Jockey Club, READ-ONLY, never written

POLL_CEILING_SECONDS = 300.0
POLL_INTERVAL_SECONDS = 90.0
POLL_STABILITY_MIN_ELAPSED = 180.0


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_FLOOR_PROBE", "false").lower() == "true"
    return (not dry_run) and allow


def _assert_no_secrets(text: str) -> None:
    # Thin wrapper -- delegates to src.guards.assert_no_secrets, the single
    # implementation this check was previously copy-pasted verbatim across six files
    # (WR-02 discipline: a bare `assert` is stripped entirely under `python -O` /
    # PYTHONOPTIMIZE=1). Kept as a named wrapper so this module's own call sites are
    # unchanged.
    assert_no_secrets(text)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _create_calculated_number_property(name: str, formula: str):
    """Mirrors check_tier_null_propagation.py's `_create_calculated_property`, but
    `type: "number"` -- matching the live lv_icp_fit_score shape exactly (a NUMBER
    calculation_equation, not a string one). Returns (status_code, body_text); never
    raises on non-2xx so the caller can print the 400 body verbatim and fall back."""
    import requests
    from src.hubspot_client import BASE_URL, hs_headers
    body = {
        "name": name, "label": f"[disposable] {name}", "type": "number",
        "fieldType": "calculation_equation", "groupName": "companyinformation",
        "options": [], "calculationFormula": formula,
    }
    r = requests.post(f"{BASE_URL}/crm/v3/properties/companies", headers=hs_headers(),
                       json=body, timeout=30)
    return r.status_code, r.text


def _get_company_prop(company_id: str, prop_name: str):
    from src.hubspot_client import get_record
    return get_record("companies", company_id, [prop_name])["properties"].get(prop_name)


def _to_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_blank(value) -> bool:
    return value is None or value == ""


def poll_phase(ids_and_props: dict, transition_ids, is_expected_transition,
               no_early_change_ids=(), no_early_change_check=None,
               ceiling: float = POLL_CEILING_SECONDS, interval: float = POLL_INTERVAL_SECONDS):
    """One phase's batched, corrected D-22 poll. Reads every id in `ids_and_props` (a
    {id: prop_name} dict) in ONE read cycle per tick -- never serially per id, which is
    what made CP1 a 20-minute run. Keeps ticking until every id in `transition_ids`
    satisfies `is_expected_transition(id, value)`, or `ceiling` elapses (never a bare
    stability stop -- there is no stability-only exit in this function at all; a
    transition either lands or the ceiling is hit). `no_early_change_ids`, if given, are
    re-checked EVERY tick via `no_early_change_check(id, value)`; a False result there
    is an IMMEDIATE FAIL, returned right away rather than polled past -- this is what
    catches check (b)'s blank sentinel going non-blank at any point.

    Returns ({id: final_value}, elapsed_seconds, {id: [reads]}, early_fail_id_or_None).
    """
    from src.hubspot_client import get_record

    start = time.monotonic()
    reads = {cid: [] for cid in ids_and_props}
    value = {}

    def _tick():
        elapsed = time.monotonic() - start
        for cid, prop in ids_and_props.items():
            v = get_record("companies", cid, [prop])["properties"].get(prop)
            value[cid] = v
            reads[cid].append({"elapsed": round(elapsed, 1), "value": v})
        return elapsed

    elapsed = _tick()
    for cid in no_early_change_ids:
        if not no_early_change_check(cid, value[cid]):
            return value, elapsed, reads, cid

    while True:
        if all(is_expected_transition(cid, value[cid]) for cid in transition_ids):
            return value, elapsed, reads, None
        remaining = ceiling - elapsed
        if remaining <= 0:
            return value, elapsed, reads, None
        time.sleep(min(interval, remaining))
        elapsed = _tick()
        for cid in no_early_change_ids:
            if not no_early_change_check(cid, value[cid]):
                return value, elapsed, reads, cid


def _patch_disposable_floor(company_id: str, number_prop: str, value) -> None:
    """PATCH the disposable NUMBER property only -- payload key set is asserted to be
    exactly {number_prop} at every call site. `value` is either 60 (write) or "" (clear
    in teardown). No production property is ever in a PATCH body in this script."""
    from src.hubspot_client import patch_record
    payload = {number_prop: value}
    # A real, unstrippable check, not `assert` (WR-02 discipline, ac64353) -- this
    # guards a live PATCH to a HubSpot portal with no rollback.
    assert_keys_equal(
        payload, {number_prop},
        f"payload-scope assertion failed for {company_id}: {set(payload)} != {{{number_prop!r}}}",
    )
    patch_record("companies", company_id, payload, dry_run=False)


def run_probe(out_path: Path) -> int:
    from src.hubspot_client import get_record

    suffix = uuid.uuid4().hex[:8]
    number_name = f"{NUMBER_PROP_PREFIX}{suffix}"
    calc_name = f"{CALC_PROP_PREFIX}{suffix}"

    result = {
        "portal_id": EXPECTED_PORTAL_ID,
        "quick_id": "260823-ono",
        "disposable_number_property": number_name,
        "disposable_calculated_property": calc_name,
        "formula_shipped": None,
        "which_formula": None,
        "create_attempts": [],
        "checks": {},
        "all_pass": False,
        "written_ids": [],
        "leaked_properties": [],
        "teardown": {},
        "checked_at": None,
    }

    try:
        print(f"creating disposable number property {number_name}")
        _create_numeric_property(number_name)

        formula_f = formula_f_for(number_name)
        print(f"creating disposable calculated property {calc_name} with FORMULA-F:\n  {formula_f}")
        status, body = _create_calculated_number_property(calc_name, formula_f)
        result["create_attempts"].append({"variant": "formula_f", "status": status})
        if status in (200, 201):
            result["formula_shipped"] = formula_f
            result["which_formula"] = "formula_f"
        else:
            print(f"  -> HTTP {status} FAILED to parse. Body (verbatim, token list is "
                  f"positional -- read it at the failing parse position):\n  {body}")
            fallback = formula_f_nested_fallback_for(number_name)
            print(f"falling back to the nested-if form:\n  {fallback}")
            status, body = _create_calculated_number_property(calc_name, fallback)
            result["create_attempts"].append({"variant": "nested_fallback", "status": status})
            if status in (200, 201):
                result["formula_shipped"] = fallback
                result["which_formula"] = "nested_fallback"
            else:
                print(f"  -> HTTP {status} FAILED too. Body:\n  {body}")
                print("BOTH formula variants failed to parse -- probe cannot proceed. "
                      "Tearing down the number property only (calc property was never created).")
                return 1  # finally below still runs teardown

        # --- live production baselines, read BEFORE any write, self-calibration anchor ---
        atc_production = _to_float(_get_company_prop(ATC_ID, "lv_icp_fit_score"))
        tier_a_production = _to_float(_get_company_prop(TIER_A_CONTROL_ID, "lv_icp_fit_score"))
        perth_production = _get_company_prop(PERTH_ID, "lv_icp_fit_score")
        never_enriched_production = _get_company_prop(NEVER_ENRICHED_CONTROL_ID, "lv_icp_fit_score")
        result["production_baselines"] = {
            ATC_ID: atc_production,
            TIER_A_CONTROL_ID: tier_a_production,
            PERTH_ID: perth_production,
            NEVER_ENRICHED_CONTROL_ID: never_enriched_production,
        }

        # --- PHASE 1: no floor written anywhere -----------------------------------
        print("\n--- Phase 1: no floor written anywhere ---")

        def _phase1_transition(cid, v):
            return cid == ATC_ID and not _is_blank(v) and _to_float(v) == atc_production

        def _phase1_no_early_change(cid, v):
            return _is_blank(v)  # (b): must stay blank at every tick, no exceptions

        phase1_values, phase1_elapsed, phase1_reads, phase1_fail_id = poll_phase(
            {ATC_ID: calc_name, NEVER_ENRICHED_CONTROL_ID: calc_name},
            transition_ids={ATC_ID},
            is_expected_transition=_phase1_transition,
            no_early_change_ids={NEVER_ENRICHED_CONTROL_ID},
            no_early_change_check=_phase1_no_early_change,
        )

        atc_phase1_value = phase1_values.get(ATC_ID)
        never_enriched_phase1_value = phase1_values.get(NEVER_ENRICHED_CONTROL_ID)

        check_a_pass = (
            phase1_fail_id != ATC_ID
            and not _is_blank(atc_phase1_value)
            and _to_float(atc_phase1_value) == atc_production
        )
        check_b_pass = (phase1_fail_id != NEVER_ENRICHED_CONTROL_ID) and _is_blank(never_enriched_phase1_value)

        result["checks"]["a_atc_null_floor_equals_live_base"] = {
            "expected": atc_production, "observed": atc_phase1_value, "pass": check_a_pass,
        }
        result["checks"]["b_never_enriched_stays_blank"] = {
            "expected": None, "observed": never_enriched_phase1_value, "pass": check_b_pass,
            "early_fail": phase1_fail_id == NEVER_ENRICHED_CONTROL_ID,
        }
        result["phase1_reads"] = phase1_reads
        result["phase1_elapsed"] = phase1_elapsed

        if phase1_fail_id is not None:
            print(f"PHASE 1 EARLY FAIL on {phase1_fail_id} -- see checks in the verdict.")

        # --- PHASE 2: floor 60 written on ATC, Perth, Tier A control only --------
        print("\n--- Phase 2: floor 60 written on ATC, Perth, Tier A control (NOT the "
              "never-enriched control) ---")
        written_ids = [ATC_ID, PERTH_ID, TIER_A_CONTROL_ID]
        for cid in written_ids:
            print(f"  PATCH {cid}: {{{number_name!r}: 60}}")
            _patch_disposable_floor(cid, number_name, 60)
            result["written_ids"].append(cid)
            back = _get_company_prop(cid, number_name)
            print(f"    independent re-read {number_name}={back!r} on {cid}")

        def _phase2_transition(cid, v):
            return not _is_blank(v) and _to_float(v) == 60.0

        phase2_values, phase2_elapsed, phase2_reads, phase2_fail_id = poll_phase(
            {PERTH_ID: calc_name, TIER_A_CONTROL_ID: calc_name, ATC_ID: calc_name},
            transition_ids={PERTH_ID, ATC_ID},
            is_expected_transition=_phase2_transition,
        )

        perth_phase2_value = phase2_values.get(PERTH_ID)
        tier_a_phase2_value = phase2_values.get(TIER_A_CONTROL_ID)
        atc_phase2_value = phase2_values.get(ATC_ID)

        check_c_pass = not _is_blank(perth_phase2_value) and _to_float(perth_phase2_value) == 60.0
        # (c) also requires production stayed blank -- re-read live now, after the write.
        perth_production_after = _get_company_prop(PERTH_ID, "lv_icp_fit_score")
        check_c_pass = check_c_pass and _is_blank(perth_production_after)

        check_d_pass = (
            not _is_blank(tier_a_phase2_value)
            and _to_float(tier_a_phase2_value) == tier_a_production
            and tier_a_production is not None and tier_a_production > 60.0
        )
        check_e_pass = (
            not _is_blank(atc_phase2_value)
            and _to_float(atc_phase2_value) == 60.0
            and (atc_production is None or _to_float(atc_phase2_value) != atc_production)
        )

        result["checks"]["c_perth_floored_to_60_production_still_blank"] = {
            "expected": {"disposable_calc": 60.0, "production": None},
            "observed": {"disposable_calc": perth_phase2_value, "production": perth_production_after},
            "pass": check_c_pass,
        }
        result["checks"]["d_tier_a_control_not_capped"] = {
            "expected": {"disposable_calc": tier_a_production, "gt": 60.0},
            "observed": {"disposable_calc": tier_a_phase2_value},
            "pass": check_d_pass,
        }
        result["checks"]["e_atc_floored_to_60_ne_production"] = {
            "expected": {"disposable_calc": 60.0, "ne_production": atc_production},
            "observed": {"disposable_calc": atc_phase2_value, "production": atc_production},
            "pass": check_e_pass,
        }
        result["phase2_reads"] = phase2_reads
        result["phase2_elapsed"] = phase2_elapsed

        all_checks_pass = all(
            c["pass"] for c in result["checks"].values()
        )
        result["all_pass"] = all_checks_pass and phase1_fail_id is None and phase2_fail_id is None

    finally:
        print("\ntearing down disposables...")
        # Clear the disposable number's value on the three written ids FIRST (a blank
        # PATCH, still asserted single-key), then archive the CALCULATED property
        # (dependent) before the NUMBER property (referenced) -- HubSpot refuses to
        # archive a property a live calculation still depends on (observed live
        # 2026-08-13, check_tier_null_propagation.py::_teardown).
        for cid in result.get("written_ids", []):
            try:
                _patch_disposable_floor(cid, number_name, "")
                print(f"  cleared {number_name} on {cid}")
            except Exception as exc:  # noqa: BLE001 -- teardown must not raise past this point
                print(f"  clearing {number_name} on {cid} raised {exc!r}")

        calc_gone = True
        if result.get("formula_shipped"):
            calc_gone = _archive_and_confirm_gone("companies", calc_name)
            print(f"  archived+confirmed-gone {calc_name}: {calc_gone}")
        number_gone = _archive_and_confirm_gone("companies", number_name)
        print(f"  archived+confirmed-gone {number_name}: {number_gone}")

        leaked = []
        if not calc_gone:
            leaked.append(calc_name)
        if not number_gone:
            leaked.append(number_name)
        result["teardown"] = {
            "calculated_property": {"name": calc_name, "gone": calc_gone},
            "number_property": {"name": number_name, "gone": number_gone},
        }
        result["leaked_properties"] = leaked
        if leaked:
            print(f"TEARDOWN LEAKED -- not confirmed gone: {leaked}")
            result["all_pass"] = False

        result["checked_at"] = _now_iso()
        text = json.dumps(result, indent=2, sort_keys=True) + "\n"
        _assert_no_secrets(text)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text)
        print(f"\nwrote {out_path}")
        print(json.dumps(result, indent=2))

    return 0 if (result["all_pass"] and not result["leaked_properties"]) else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                         help="Path to write the probe verdict JSON to.")
    parser.add_argument("--plan", action="store_true",
                         help="Print FORMULA-F and the check table, zero HTTP calls "
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
        placeholder = "<disposable_number_name>"
        print("--plan (default) -- no writes will be made. Set DRY_RUN=false AND "
              "ALLOW_FLOOR_PROBE=true to run the live probe.\n")
        print("FORMULA-F (disposable substitution, both occurrences of "
              f"{FLOOR_PLACEHOLDER!r} replaced with the disposable number property's name):")
        print(f"  {formula_f_for(placeholder)}")
        print("\nNested-if fallback (used only if FORMULA-F's create 400s):")
        print(f"  {formula_f_nested_fallback_for(placeholder)}")
        print("\nCheck table:")
        print("  Phase 1 (no floor written anywhere):")
        print(f"    (a) ATC ({ATC_ID}, unset floor)                -> == live production base, not blank")
        print(f"    (b) never-enriched ({NEVER_ENRICHED_CONTROL_ID}, unset, NEVER written) -> stays blank")
        print("  Phase 2 (floor 60 written on ATC, Perth, Tier A control only):")
        print(f"    (c) Perth ({PERTH_ID}, floor 60)               -> 60, production still blank")
        print(f"    (d) Tier A control ({TIER_A_CONTROL_ID}, floor 60) -> == live production base, > 60 (no cap)")
        print(f"    (e) ATC ({ATC_ID}, floor 60)                   -> 60, != live production base (floor bit)")
        return 0

    return run_probe(Path(args.out))


if __name__ == "__main__":
    sys.exit(main())
