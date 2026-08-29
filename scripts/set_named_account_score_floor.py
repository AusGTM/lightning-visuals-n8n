#!/usr/bin/env python3
"""scripts/set_named_account_score_floor.py

Quick task 260823-ono, write surface 3 -- PATCH `lv_named_account_score_floor=60`
onto exactly the five named metro peak-body companies (ATC, MRC, SSR, BRC, Perth Racing),
and the operator's standing tool for "add a 6th named account" going forward (edit
NAMED_ACCOUNTS, run --plan, arm --execute, poll --verify).

Retargeted post-CP1 (halt-b: enums are unreadable in a `calculation_equation` on this
portal -- CONTEXT.md's "Amendment 2026-08-23", operator Option 1). Formerly
scripts/set_named_account_priority.py, PATCHing `lv_named_account_priority=core_racing`
(an enumeration); renamed via `git mv` in the same commit that retargets the mechanism.
The write surface it gates is unchanged -- a PATCH on the same 5 company ids -- only the
filename and the payload's key changed, so ALLOW_NAMED_ACCOUNT_WRITE is kept rather than
minted fresh.

Three modes, one script:
    --plan (default, zero writes) -- prints the 5 single-key PATCH payloads. Also
        re-reads the 5 target ids AND the two control records (never-enriched, Tier A)
        live and refuses (exit 1, never truncates the print) if EITHER set has drifted
        from 260823-ono-PREDICTIONS.json since Task 1 -- a moved control means the CP2
        formula push already damaged the population and arming the PATCH is the wrong
        next move.
    --execute (armed) -- PATCHes each of the 5 with a payload whose key set is asserted
        to be exactly {"lv_named_account_score_floor"} (never a wider write), then
        verifies each write by an INDEPENDENT per-record re-read (never the PATCH
        response body).
    --verify -- polls lv_icp_fit_score + lv_icp_tier_derived on the 5 ids under the
        corrected D-22 poll shape (poll until the record reaches its expected
        score/tier or a 300s ceiling; a stability stop -- two consecutive reads
        agreeing -- is accepted only once >=180s have elapsed, never on an early
        two-reads-agree that could both be the stale pre-write value during the
        ~70-130s calculation backfill window) and diffs the final reads against the
        predictions JSON, exiting non-zero on ANY mismatch.

Two-key write gate for --execute (repo idiom, its OWN dedicated key -- never
ALLOW_HUBSPOT_PROPERTY_WRITES or ALLOW_FORMULA_WRITE, which are scoped to property-create
and formula-push respectively): DRY_RUN=false AND ALLOW_NAMED_ACCOUNT_WRITE=true, plus the
portal guard. No n8n arming anywhere in this script's path -- it is a plain HubSpot
company-record PATCH, the same class of call scripts/rescore_population.py already makes,
never a webhook POST.

`.env` is Read/Bash permission-blocked this session -- the operator invocations are:
    # preflight (unarmed, always run first)
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/set_named_account_score_floor.py', run_name='__main__')"

    # armed
    DRY_RUN=false ALLOW_NAMED_ACCOUNT_WRITE=true .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy, sys; \
         sys.argv = ['set_named_account_score_floor.py', '--execute']; \
         runpy.run_path('scripts/set_named_account_score_floor.py', run_name='__main__')"

    # verify
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy, sys; \
         sys.argv = ['set_named_account_score_floor.py', '--verify']; \
         runpy.run_path('scripts/set_named_account_score_floor.py', run_name='__main__')"
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

from src.guards import assert_keys_equal  # noqa: E402

EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")
PREDICTIONS_PATH = (
    ROOT / ".planning" / "quick" / "260823-ono-metro-peak-body-override-rule-tier-atc-m"
    / "260823-ono-PREDICTIONS.json"
)

FLOOR_VALUE = 60
FLOOR_PROP = "lv_named_account_score_floor"

# The exactly-five metro peak bodies this quick task exists for. To add a 6th named
# account later, add an entry here and re-run --plan / --execute / --verify -- this dict
# IS the operator-facing "add a named account" surface (docs/OPERATOR-RESCORE.md).
NAMED_ACCOUNTS = {
    "9605284724": "Australian Turf Club (ATC)",
    "9604614548": "Melbourne Racing Club (MRC)",
    "18756544344": "Southside Racing (SSR)",
    "9605284723": "Brisbane Racing Club (BRC)",
    "9604794662": "Perth Racing",
}

# D-22 poll shape for --verify -- matches probe_number_floor_in_formula.py's own
# constants and its corrected stop condition (Task 1b step 7).
POLL_CEILING_SECONDS = 300.0
POLL_INTERVAL_SECONDS = 90.0
POLL_STABILITY_MIN_ELAPSED = 180.0


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_NAMED_ACCOUNT_WRITE", "false").lower() == "true"
    return (not dry_run) and allow


def build_payloads() -> dict:
    """{company_id: {property: value}} -- the exact, single-key PATCH bodies. A payload
    key set that is ever anything other than exactly {FLOOR_PROP} is a bug, asserted at
    every call site below, never trusted from this function's return alone."""
    payloads = {cid: {FLOOR_PROP: FLOOR_VALUE} for cid in NAMED_ACCOUNTS}
    for cid, payload in payloads.items():
        # A real, unstrippable check, not `assert` -- `assert` is removed entirely
        # under `python -O` / PYTHONOPTIMIZE=1 (WR-02 discipline, ac64353), and this
        # guards a live PATCH to a HubSpot portal with no rollback.
        assert_keys_equal(
            payload, {FLOOR_PROP},
            f"payload-scope assertion failed for {cid}: {set(payload)} != {{{FLOOR_PROP!r}}}",
        )
    return payloads


def load_predictions() -> dict:
    return json.loads(PREDICTIONS_PATH.read_text())


def _target_prediction(predictions: dict, company_id: str) -> dict:
    for t in predictions["targets"]:
        if t["id"] == company_id:
            return t
    raise KeyError(f"{company_id} not present in {PREDICTIONS_PATH}")


def _control_prediction(predictions: dict, company_id: str) -> dict:
    for c in predictions["controls"]:
        if c["id"] == company_id:
            return c
    raise KeyError(f"{company_id} not present in {PREDICTIONS_PATH}'s controls")


def check_drift(predictions: dict) -> list:
    """Live re-read of the 5 target ids AND the 2 control ids; returns a list of
    human-readable drift descriptions (empty list == no drift). Compares
    lv_icp_fit_score/lv_icp_tier_derived/lv_named_account_score_floor against the
    baseline recorded in predictions -- NOT the predicted post-write values, since this
    check runs BEFORE any write in --plan/--execute's preflight."""
    from src.hubspot_client import get_record

    props = [FLOOR_PROP, "lv_icp_fit_score", "lv_icp_tier_derived"]
    drift = []

    for cid in NAMED_ACCOUNTS:
        pred = _target_prediction(predictions, cid)
        live = get_record("companies", cid, props)["properties"]
        baseline = pred["baseline"]
        live_score = live.get("lv_icp_fit_score") or None
        baseline_score = baseline.get("lv_icp_fit_score_raw") or None
        if live_score != baseline_score:
            drift.append(
                f"TARGET {cid} ({pred['name']}): lv_icp_fit_score drifted "
                f"{baseline_score!r} -> {live_score!r} since Task 1's baseline read"
            )
        if (live.get(FLOOR_PROP) or None) != baseline.get(FLOOR_PROP):
            drift.append(
                f"TARGET {cid} ({pred['name']}): {FLOOR_PROP} already "
                f"{live.get(FLOOR_PROP)!r} (expected still unset)"
            )

    for control in predictions["controls"]:
        cid = control["id"]
        live = get_record("companies", cid, props)["properties"]
        baseline = control["baseline"]
        live_score = live.get("lv_icp_fit_score") or None
        baseline_score = baseline.get("lv_icp_fit_score") or None
        live_tier = live.get("lv_icp_tier_derived") or None
        baseline_tier = baseline.get("lv_icp_tier_derived") or None
        if control["role"] == "never_enriched":
            if live_score not in (None, ""):
                drift.append(
                    f"CONTROL {cid} ({control['name']}, never-enriched): "
                    f"lv_icp_fit_score is now {live_score!r} -- it must stay blank. The "
                    "formula push has damaged the population; do NOT arm the PATCH."
                )
        else:
            if live_score != baseline_score or live_tier != baseline_tier:
                drift.append(
                    f"CONTROL {cid} ({control['name']}, Tier A control): score/tier moved "
                    f"from {baseline_score!r}/{baseline_tier!r} to "
                    f"{live_score!r}/{live_tier!r}. The formula push has damaged the "
                    "population; do NOT arm the PATCH."
                )

    return drift


def _patch_and_verify(company_id: str, payload: dict) -> bool:
    """PATCH one record, then verify by an INDEPENDENT re-read (never the PATCH response
    body). Returns True iff the re-read matches the payload exactly."""
    from src.hubspot_client import get_record, patch_record

    resp = patch_record("companies", company_id, payload, dry_run=False)
    status_ok = "properties" in resp  # patch_record raises on non-2xx via r.raise_for_status()
    back = get_record("companies", company_id, list(payload))["properties"]
    verified = all(str(back.get(k)) == str(v) for k, v in payload.items())
    print(f"  {company_id}: PATCH ok={status_ok}, verified by independent re-read: "
          f"{verified} (live now: {back})")
    return verified


def poll_until(company_id: str, props: list, is_expected, ceiling: float = POLL_CEILING_SECONDS,
               interval: float = POLL_INTERVAL_SECONDS,
               stability_min: float = POLL_STABILITY_MIN_ELAPSED):
    """Corrected D-22 poll shape (Task 1b step 7 -- do NOT copy the old two-consecutive-
    agree stop, which false-passes a still-stale pre-write value). Polls until
    `is_expected(value)` is True or `ceiling` elapses. A stability stop (two consecutive
    reads agreeing on every prop) is accepted only once elapsed >= `stability_min` --
    HubSpot's calculation backfill is ~70-130s, so two early reads can both be the stale
    pre-write value, agree, and stop, falsely reporting the old value as "stable".
    Returns (final_properties_dict, elapsed_seconds, all_reads)."""
    from src.hubspot_client import get_record

    start = time.monotonic()
    value = get_record("companies", company_id, props)["properties"]
    reads = [{"elapsed": 0.0, **{p: value.get(p) for p in props}}]
    if is_expected(value):
        return value, 0.0, reads

    while True:
        elapsed = time.monotonic() - start
        remaining = ceiling - elapsed
        if remaining <= 0:
            return value, elapsed, reads
        time.sleep(min(interval, remaining))
        new_value = get_record("companies", company_id, props)["properties"]
        elapsed = time.monotonic() - start
        reads.append({"elapsed": round(elapsed, 1), **{p: new_value.get(p) for p in props}})
        if is_expected(new_value):
            return new_value, elapsed, reads
        stable = all(new_value.get(p) == value.get(p) for p in props)
        if stable and elapsed >= stability_min:
            return new_value, elapsed, reads
        value = new_value


def run_plan() -> int:
    payloads = build_payloads()
    print("PATCH payloads (single-key, --execute would send these unchanged):")
    for cid, payload in payloads.items():
        print(f"  {cid} ({NAMED_ACCOUNTS[cid]}): {json.dumps(payload)}")

    if not PREDICTIONS_PATH.exists():
        print(f"\nREFUSED: {PREDICTIONS_PATH} does not exist -- Task 1 must run and write "
              "predictions before this tool can preflight-check drift.")
        return 1

    predictions = load_predictions()
    if not _has_credentials():
        print("\nskipped drift check (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be "
              "set to compare live state against predictions.")
        return 0
    if not _portal_ok():
        print(f"\nREFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    print("\nDrift check against 260823-ono-PREDICTIONS.json (5 targets + 2 controls):")
    drift = check_drift(predictions)
    if drift:
        print("REFUSED -- drift detected, arming the PATCH would be the wrong next move:")
        for line in drift:
            print(f"  - {line}")
        return 1

    print("  no drift -- 5 targets and 2 controls all match Task 1's baseline.")
    return 0


def run_execute() -> int:
    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set.")
        return 0
    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1
    if not _writes_allowed():
        print("REFUSED: --execute requires DRY_RUN=false AND "
              "ALLOW_NAMED_ACCOUNT_WRITE=true. No API call made.")
        return 1

    payloads = build_payloads()
    print(f"ARMED: PATCHing {len(payloads)} records with {FLOOR_PROP}={FLOOR_VALUE!r}")
    all_ok = True
    for cid, payload in payloads.items():
        print(f"\n{cid} ({NAMED_ACCOUNTS[cid]}):")
        ok = _patch_and_verify(cid, payload)
        all_ok = all_ok and ok

    return 0 if all_ok else 1


def run_verify() -> int:
    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set.")
        return 0
    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1
    if not PREDICTIONS_PATH.exists():
        print(f"REFUSED: {PREDICTIONS_PATH} does not exist.")
        return 1

    predictions = load_predictions()
    props = ["lv_icp_fit_score", "lv_icp_tier_derived"]
    mismatches = []

    for cid in NAMED_ACCOUNTS:
        pred = _target_prediction(predictions, cid)
        wanted_score = pred["predicted"]["lv_icp_fit_score"]
        wanted_tier = pred["predicted"]["lv_icp_tier_derived"]
        print(f"\npolling {cid} ({NAMED_ACCOUNTS[cid]}) -- expect score>={wanted_score}, "
              f"tier={wanted_tier} (corrected D-22 poll) ...")

        def _is_expected(value, wanted_score=wanted_score, wanted_tier=wanted_tier):
            raw = value.get("lv_icp_fit_score")
            try:
                s = int(raw) if raw not in (None, "") else None
            except (TypeError, ValueError):
                s = None
            return s is not None and s >= wanted_score and value.get("lv_icp_tier_derived") == wanted_tier

        final, elapsed, reads = poll_until(cid, props, _is_expected)
        score_raw = final.get("lv_icp_fit_score")
        tier = final.get("lv_icp_tier_derived")
        score = int(score_raw) if score_raw not in (None, "") else None
        print(f"  final after {elapsed:.0f}s: score={score!r} tier={tier!r} ({reads})")
        if score is None or score < wanted_score or tier != wanted_tier:
            mismatches.append(
                f"{cid} ({NAMED_ACCOUNTS[cid]}): expected score>={wanted_score}/{wanted_tier}, "
                f"got score={score!r}/{tier!r} -- DEFECT, not narrated away"
            )

    if mismatches:
        print("\nMISMATCHES (defects, recorded not narrated):")
        for m in mismatches:
            print(f"  - {m}")
        return 1

    print("\nAll 5 verified: score>=60 and tier='B', matching predictions.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true", help="Armed PATCH of the 5 ids.")
    mode.add_argument("--verify", action="store_true",
                       help="Poll and diff the 5 ids against predictions (corrected D-22).")
    args = parser.parse_args(argv)

    if args.execute:
        return run_execute()
    if args.verify:
        return run_verify()
    return run_plan()


if __name__ == "__main__":
    sys.exit(main())
