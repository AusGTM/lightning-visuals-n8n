#!/usr/bin/env python3
"""scripts/probe_scoring_recalc_latency.py

Phase 39 Plan 03 (DECIDE-01) — the two-key-gated disposable-company probe that measures
whether HubSpot's lead-scoring recalculation fires automatically on an API-written
property change (the D-04 gate), and if so how fast (median-of-3, per D-03).

This measures the per-record, event-driven rescore latency following an API-written
property change on the disposable company itself — explicitly NOT the criteria-edit
full-portal bulk recalculation, which HANDOVER §5/39-RESEARCH.md flag as a separate and
much slower one-time phenomenon. The loop never edits the scoring criteria definition.

Two-key arming: DRY_RUN=false AND ALLOW_HUBSPOT_SCORING_PROBE=true (a phase-scoped flag,
deliberately distinct from the generic property-writes flag a migration script might
leave armed). Touches exactly one disposable `ZZ-SCORING-TEST-DELETE-ME-*` company and
deletes it on teardown, guaranteed even on exception or interrupt.

`.env` is Read/Bash permission-blocked this session — the operator invocation is:
    ALLOW_HUBSPOT_SCORING_PROBE=true DRY_RUN=false .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/probe_scoring_recalc_latency.py', run_name='__main__')"
"""
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*`/`src.*` imports resolve

from src import taxonomy  # noqa: E402
from src.hubspot_client import (  # noqa: E402
    BASE_URL,
    hs_headers,
    create_record,
    patch_record,
    get_record,
    delete_record,
)

EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

EVIDENCE_DIR = ROOT / ".planning" / "phases" / "39-path-decision-fit-score-verification" / "evidence"
EVIDENCE_PATH = EVIDENCE_DIR / "recalc_latency_probe.json"

# The ONE disposable-artifact prefix this script will ever create. Module constant, no
# CLI or environment override — there is no legitimate reason for this script to be
# pointable at any other record (mirrors PROBE_PROPERTY_NAME in probe_org_type_migration.py).
COMPANY_NAME_PREFIX = "ZZ-SCORING-TEST-DELETE-ME-"

# Measurement resolution: every reported latency is an upper bound quantized up to the
# nearest poll.
POLL_INTERVAL_SECONDS = 5.0

# 65 minutes — deliberately one poll-scale beyond band b's 3600 s upper edge, so
# exhausting the timeout is unambiguously band c rather than an inconclusive cutoff.
POLL_TIMEOUT_SECONDS = 3900.0

# Fixed by D-03. Also why median_latency never hits the even-length averaging path.
SAMPLE_COUNT = 3

# The A-BOUNDARY contract (39-01-PLAN.md "Planner assumptions") — named rather than
# inline so the band edges are greppable.
BAND_A_MAX_SECONDS = 600.0
BAND_B_MAX_SECONDS = 3600.0

# The one scoring-input property this probe flips on the disposable company. lv_org_type
# is the property named in 39-04-PLAN.md Task 1's own example criterion ("lv_org_type is
# known"), already taxonomy-controlled in this repo, and a stable choice regardless of
# which trivial rubric line the operator actually built. A module constant, not an
# env/CLI override — same disposable-artifact discipline as COMPANY_NAME_PREFIX.
FLIP_PROPERTY_NAME = "lv_org_type"
FLIP_INITIAL_VALUE = taxonomy.DEFAULT_ORG_TYPE
FLIP_TARGET_VALUE = sorted(k for k in taxonomy.ORG_TYPES if k != taxonomy.DEFAULT_ORG_TYPE)[0]


def median_latency(samples: list) -> float:
    """samples: elapsed seconds from property-write to observed score change.

    Pure function. With SAMPLE_COUNT fixed at 3 the result is always one of the input
    samples verbatim — no averaging, no interpolation, no floating-point tie-break.
    Resists a single noisy sample, which is D-03's entire reason for taking three.
    """
    if not samples:
        raise ValueError("no samples")
    return statistics.median(samples)


def classify_latency_band(median_seconds) -> str:
    """Maps a median latency (or None for no observed change) to D-04's outcome bands.

    - "a": event-driven, minutes-scale (<= BAND_A_MAX_SECONDS) -> proceed, lead-scoring tool.
    - "b": event-driven but slow (<= BAND_B_MAX_SECONDS) -> still proceed, latency recorded
      as evidence.
    - "c": manual-only / does not fire on API writes (median_seconds is None) / hours-plus
      (> BAND_B_MAX_SECONDS) -> pause for operator review.
    """
    if median_seconds is None:
        return "c"
    if median_seconds < 0:
        raise ValueError("median_seconds cannot be negative")
    if median_seconds <= BAND_A_MAX_SECONDS:
        return "a"
    if median_seconds <= BAND_B_MAX_SECONDS:
        return "b"
    return "c"


def find_score_property_name(results: list):
    """Returns the `name` of the first companies property whose fieldType is
    'calculation_score', else None. This is the precondition lookup the orchestration
    hard-fails on before ever starting the flip loop (RESEARCH.md Pitfall 2)."""
    for entry in results:
        if entry.get("fieldType") == "calculation_score":
            return entry.get("name")
    return None


# --- two-key write gate + portal guard (verbatim triad from rollback_canary_proof.py,
# second flag swapped for the phase-scoped ALLOW_HUBSPOT_SCORING_PROBE) ----------------

def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_HUBSPOT_SCORING_PROBE", "false").lower() == "true"
    return (not dry_run) and allow


# --- network orchestration -------------------------------------------------------------

def _list_company_properties() -> list:
    r = requests.get(f"{BASE_URL}/crm/v3/properties/companies", headers=hs_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("results", [])


def _disposable_company_name() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{COMPANY_NAME_PREFIX}{ts}"


def flip_value_for_sample(i: int):
    """Pure function (CR-01 fix): the value each round's write must alternate to, so every
    sample is a genuine property change instead of samples 2+ re-writing the same value as
    a no-op. Even rounds flip to FLIP_TARGET_VALUE, odd rounds flip back to
    FLIP_INITIAL_VALUE — the disposable company starts at FLIP_INITIAL_VALUE (line ~208),
    so round 0 (i=0) is always a real change from that starting value."""
    return FLIP_TARGET_VALUE if i % 2 == 0 else FLIP_INITIAL_VALUE


def _run_one_sample(record_id: str, score_property_name: str, pre_flip_value, flip_value):
    """Flips FLIP_PROPERTY_NAME on the disposable company to `flip_value`, then polls
    the score property every POLL_INTERVAL_SECONDS until its value differs from
    pre_flip_value. Returns elapsed seconds (t1 - t0, both from time.monotonic()), or None
    if POLL_TIMEOUT_SECONDS elapses first (no observed change — the no-fire case).

    Only ever writes the disposable company's own property — never the scoring criteria
    definition (RESEARCH.md Pitfall 3)."""
    t0 = time.monotonic()
    patch_record("companies", record_id, {FLIP_PROPERTY_NAME: flip_value}, dry_run=False)

    while time.monotonic() - t0 < POLL_TIMEOUT_SECONDS:
        time.sleep(POLL_INTERVAL_SECONDS)
        record = get_record("companies", record_id, [score_property_name])
        current = record.get("properties", {}).get(score_property_name)
        if current != pre_flip_value:
            t1 = time.monotonic()
            return t1 - t0
    return None


def main(argv=None) -> int:
    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run "
              "this recalc latency probe.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    if not _writes_allowed():
        print("skipped: DRY_RUN=false AND ALLOW_HUBSPOT_SCORING_PROBE=true are both "
              "required to run the recalc latency probe (two-key gate).")
        return 0

    # Precondition, hard-fail (RESEARCH.md Pitfall 2): never poll a property that does
    # not exist yet — that would misreport a no-fire outcome as band c when the truth is
    # "nobody built a criterion."
    properties = _list_company_properties()
    score_property_name = find_score_property_name(properties)
    if score_property_name is None:
        print("FAIL: no calculation_score-typed property exists yet on the companies "
              "object. Build one trivial criterion in the lead-scoring tool first — "
              "proceeding would poll a property that can never change and would "
              "misreport a false no-fire (band c) outcome.")
        return 2

    print(f"discovered score property: {score_property_name}")

    company_name = _disposable_company_name()
    created = create_record(
        "companies",
        {"name": company_name, FLIP_PROPERTY_NAME: FLIP_INITIAL_VALUE},
        dry_run=False,
    )
    record_id = created["id"]
    print(f"created disposable company: {record_id} ({company_name})")

    deleted_ok = False
    try:
        samples = []
        for i in range(SAMPLE_COUNT):
            record = get_record("companies", record_id, [score_property_name])
            pre_flip_value = record.get("properties", {}).get(score_property_name)
            flip_value = flip_value_for_sample(i)
            elapsed = _run_one_sample(record_id, score_property_name, pre_flip_value, flip_value)
            samples.append(elapsed)
            print(f"sample {i + 1}/{SAMPLE_COUNT}: {elapsed}")
            if elapsed is None:
                # A no-fire sample already determines band c; continuing would burn
                # hours for no additional signal.
                print("no change observed within timeout — aborting remaining samples.")
                break

        median_seconds = None if any(s is None for s in samples) else median_latency(samples)
        band = classify_latency_band(median_seconds)

        evidence = {
            "probed_at_utc": datetime.now(timezone.utc).isoformat(),
            "expected_portal_id": EXPECTED_PORTAL_ID,
            "score_property_name": score_property_name,
            "company_id": record_id,
            "company_name": company_name,
            "flipped_property": FLIP_PROPERTY_NAME,
            "flip_initial_value": FLIP_INITIAL_VALUE,
            "flip_target_value": FLIP_TARGET_VALUE,
            "samples": samples,
            "median_seconds": median_seconds,
            "band": band,
            "constants": {
                "POLL_INTERVAL_SECONDS": POLL_INTERVAL_SECONDS,
                "POLL_TIMEOUT_SECONDS": POLL_TIMEOUT_SECONDS,
                "BAND_A_MAX_SECONDS": BAND_A_MAX_SECONDS,
                "BAND_B_MAX_SECONDS": BAND_B_MAX_SECONDS,
            },
            "measurement_contract": (
                "Latency is measured with a monotonic clock from just before the PATCH "
                "that flips the disposable company's own scoring-input property to just "
                "after the first GET response that shows the score property's value has "
                f"changed. It is therefore an upper bound, quantized up to the nearest "
                f"poll at {POLL_INTERVAL_SECONDS}s resolution — not an exact figure. This "
                "is the per-record event-driven rescore latency, not a criteria-edit "
                "full-portal bulk recalculation (a separate, much slower phenomenon)."
            ),
        }
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        with EVIDENCE_PATH.open("w") as f:
            json.dump(evidence, f, indent=2, default=str)
        print(f"wrote {EVIDENCE_PATH}")
    finally:
        # Guaranteed teardown — runs even if the block above raised or was interrupted.
        # A disposable ZZ-SCORING-TEST-DELETE-ME-* company must never survive a crash.
        response = delete_record("companies", record_id, dry_run=False)
        deleted_ok = getattr(response, "status_code", None) == 204
        print(f"teardown: delete company {record_id} -> "
              f"{'204' if deleted_ok else getattr(response, 'status_code', response)}")

    if not deleted_ok:
        print(f"FAIL: teardown did not return 204 for disposable company {record_id} — "
              "it may still exist live. A failed delete is a FAIL even if the "
              "measurement above succeeded.")
        return 1

    print(f"PASS: band={band}, median_seconds={median_seconds}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
