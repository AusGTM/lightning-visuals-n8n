# tests/scoring_fixtures.py
#
# Phase 40 Plan 02 (D-11) — shared disposable-company lifecycle + oracle-comparison
# helpers for the parity harness. Plain importable module, deliberately NOT a conftest:
# scripts/run_scoring_parity.py imports this exact code path so the two D-11 layers
# (pytest module + script wrapper) share one implementation instead of drifting apart.
import os
import time
import uuid
from contextlib import contextmanager

from src.hubspot_client import (
    create_record,
    delete_record,
    get_record,
    search_records,
)
from src.icp_scoring import compute_icp_score
from src.schemas import HubSpotRecord

# WR-01-style discipline (matches probe_scoring_recalc_latency.py / snapshot_hubspot_schema.py):
# hard-coded, no env override — there is no legitimate reason for this fixture to be
# pointable at any other portal.
EXPECTED_PORTAL_ID = "22617666"

# The one disposable-artifact prefix this module will ever create.
COMPANY_NAME_PREFIX = "ZZ-SCORING-TEST-DELETE-ME-"

# The read list every parity comparison needs: canonical inputs, the five component
# scores (org_type/geography/annual_revenue/produces_content/gambling), and the three
# derived outputs. produces_content_score and gambling_score don't exist yet as of
# 40-01 (PORTAL-FACTS.md) — 40-04 creates them; requesting an unknown property name in a
# HubSpot properties GET list is a documented no-op (the property is simply absent from
# the response), not an error, so this list is safe to use before and after 40-04 lands.
FIT_SCORE_PROPS = [
    "lv_org_type",
    "lv_produces_content",
    "lv_country_region_normalized",
    "lv_revenue_band",
    "lv_is_gambling_operator",
    "lv_is_hardware_vendor",
    "org_type_score",
    "geography_score",
    "annual_revenue_score",
    "produces_content_score",
    "gambling_score",
    "lv_icp_fit_score",
    "lv_icp_tier",
    "lv_anti_icp_flag",
    "lv_anti_icp_reason",
    # Phase 41 Plan 02 Task 2 (DATA-01's "provenance stamped" bar) -- appended, not
    # inserted, so the first fifteen entries above stay byte-identical. The live schema
    # carries provenance as ONE lv_enrichment_provenance JSON blob plus two verified_at
    # cache keys (n8n/code/mergeCompanies.js's header comment; config/hubspot_properties
    # .yaml:192-209) -- not the per-field *_source/*_confidence properties CLAUDE.md's
    # superseded local-MVP design describes. Requesting an unknown property name in a
    # HubSpot properties GET list is a documented no-op, so this addition is safe against
    # a portal where any of them is missing, same reasoning as the component-score
    # properties above.
    "lv_enrichment_provenance",
    "lv_org_type_verified_at",
    "lv_produces_content_verified_at",
    "lv_enrichment_needs_review",
    "lv_enrichment_review_reason",
    # Phase 43 Plan 04 (live execution) — Rule 1 bug fix: fetch_for_parity() is the read
    # path test_write_breakdown_live_round_trips_through_hubspot (43-02) uses to read the
    # property --write-breakdown writes; the live round trip KeyErrors on every run
    # without this, regardless of timing, because the property was never in this list.
    "lv_icp_score_breakdown",
]


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def fetch_for_parity(company_id: str) -> dict:
    """Live company properties, the FIT_SCORE_PROPS slice only."""
    return get_record("companies", company_id, FIT_SCORE_PROPS)["properties"]


def expected_for(props: dict):
    """The oracle's opinion of a property dict. One function, used by both
    tests/test_scoring_parity.py and scripts/run_scoring_parity.py (D-11) — the id is
    irrelevant to compute_icp_score's scoring logic, so a placeholder is fine."""
    record = HubSpotRecord(object_type="companies", id="0", properties=props)
    return compute_icp_score(record, {})


@contextmanager
def disposable_company(**initial_props):
    """Creates a ZZ-SCORING-TEST-DELETE-ME-* company, yields its id, and deletes it in a
    `finally` block — guaranteed teardown on exception and on KeyboardInterrupt. Asserts
    the expected portal before ever creating anything (T-40-01)."""
    assert _portal_ok(), (
        f"HUBSPOT_PORTAL_ID does not match the expected portal ({EXPECTED_PORTAL_ID}); "
        "refusing to create a disposable company."
    )
    name = f"{COMPANY_NAME_PREFIX}{uuid.uuid4().hex[:12]}"
    created = create_record("companies", {"name": name, **initial_props}, dry_run=False)
    company_id = created["id"]
    try:
        yield company_id
    finally:
        response = delete_record("companies", company_id, dry_run=False)
        assert getattr(response, "status_code", None) == 204, (
            f"teardown delete of disposable company {company_id} did not return 204"
        )


def settle(company_id: str, prop: str, timeout: float = 120, interval: float = 5):
    """Polls `prop` on `company_id` until it stops changing across two consecutive reads,
    or `timeout` elapses. Returns (final_value, elapsed_seconds). HANDOVER §10.1 records
    mapper latency at 4-25s and tier at ~3s, so the 120s/5s defaults are generous
    headroom, not a guess."""
    start = time.monotonic()
    previous = None
    first_read = True
    while True:
        record = get_record("companies", company_id, [prop])
        current = record.get("properties", {}).get(prop)
        elapsed = time.monotonic() - start
        if not first_read and current == previous:
            return current, elapsed
        first_read = False
        previous = current
        if elapsed >= timeout:
            return current, elapsed
        time.sleep(interval)


def assert_no_disposables_survive():
    """Asserts no company named with the disposable prefix survives in the portal."""
    result = search_records(
        "companies",
        [{"propertyName": "name", "operator": "CONTAINS_TOKEN", "value": COMPANY_NAME_PREFIX}],
        ["name"],
    )
    survivors = result.get("results", [])
    assert not survivors, (
        "disposable companies survived: "
        f"{[r.get('properties', {}).get('name') for r in survivors]}"
    )
