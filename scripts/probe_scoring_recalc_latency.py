#!/usr/bin/env python3
"""scripts/probe_scoring_recalc_latency.py

Phase 39 Plan 03 (DECIDE-01) — the two-key-gated disposable-company probe that measures
whether HubSpot's lead-scoring recalculation fires automatically on an API-written
property change (the D-04 gate), and if so how fast (median-of-3, per D-03).

This measures the per-record, event-driven rescore latency following an API-written
property change on the disposable company itself — explicitly NOT the criteria-edit
full-portal bulk recalculation, which HANDOVER §5/39-RESEARCH.md flag as a separate and
much slower one-time phenomenon. The loop never edits the scoring criteria definition.

Two-key arming: DRY_RUN=false AND ALLOW_HUBSPOT_SCORING_PROBE=true (phase-scoped flag,
deliberately not the generic ALLOW_HUBSPOT_PROPERTY_WRITES a migration script might leave
armed). Touches exactly one disposable `ZZ-SCORING-TEST-DELETE-ME-*` company and deletes
it on teardown, guaranteed even on exception or interrupt.

`.env` is Read/Bash permission-blocked this session — the operator invocation is:
    ALLOW_HUBSPOT_SCORING_PROBE=true DRY_RUN=false .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/probe_scoring_recalc_latency.py', run_name='__main__')"
"""
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*`/`src.*` imports resolve

EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

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
