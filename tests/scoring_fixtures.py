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


def settle_until(company_id: str, prop: str, predicate, timeout: float = 180,
                 interval: float = 5):
    """Polls `prop` until `predicate(value)` holds, or `timeout` elapses. Returns
    (last_observed_value, elapsed_seconds) either way — it NEVER raises and never
    asserts, so the calling test's own assert statements stay the verdict.

    Phase 47.5 Plan 03 (RECOMP-01). `settle()` above is the wrong tool for a freshly
    triggered pipeline: it returns as soon as two consecutive reads AGREE, which on a
    disposable whose property has never been written means it returns a perfectly stable
    absence in ~5 seconds while n8n is still mid-execution. A predicate wait is the
    difference between "the value stopped moving" and "the value arrived"."""
    start = time.monotonic()
    while True:
        current = get_record("companies", company_id, [prop]).get("properties", {}).get(prop)
        elapsed = time.monotonic() - start
        if predicate(current) or elapsed >= timeout:
            return current, elapsed
        time.sleep(interval)


def wait_until_searchable(domain: str, timeout: float = 90, interval: float = 5):
    """Returns how many companies HubSpot's search API matches on `domain` EQ, waiting
    for a non-zero count up to `timeout`.

    A newly created record is not immediately visible to the search API (WINDOWS.md id 6
    records ~20s of new-record index lag), and the enrichment workflow resolves a
    domain-carrying event through `HubSpot Company Search`. Posting before the index
    catches up makes `Company Gate` see no existing record, which under the recompute
    intent is `recompute_refused` — a silent, correct refusal that looks like a broken
    pipeline. Returns the count rather than asserting: the caller decides."""
    start = time.monotonic()
    while True:
        result = search_records(
            "companies",
            [{"propertyName": "domain", "operator": "EQ", "value": domain}],
            ["name"],
        )
        count = len(result.get("results", []))
        elapsed = time.monotonic() - start
        if count or elapsed >= timeout:
            return count
        time.sleep(interval)


def trigger_recompute(company_id: str, domain: str):
    """POST the D-18 recompute event that wakes the pipeline for exactly one company.

    Phase 47.5 Plan 03. Without this the live veto tests have no trigger at all — Phase
    40-07 recorded that setting veto-input properties alone never dispatches n8n under
    this portal's configured webhook subscriptions, and the documented fallback
    (`lv_enrichment_requested` + SJ-3) is a DAILY poller (CLAUDE.md §19.0 as-built).

    `domain` is not decoration: it routes the event through `HubSpot Company Search`
    instead of the bare fetch-by-id lane, which is what populates `identity_keys.domain`
    so the deployed `_writeSafetyAllows()` can match a `TEST_RECORD_DOMAINS` allowlist —
    the only allowlist that can be armed for a record HubSpot has not created yet.

    The `armed=True` argument is the remediation SCRIPT's client-side ceremony flag, not
    the live write gate. The live gate is n8n's `_writeSafetyAllows`, which is disarmed
    by default; a POST from an unarmed window reaches `Decide Company Action` and comes
    back `write_blocked`, writing nothing. Imports are local so the offline suite never
    pays for them at collection time."""
    import sys
    from pathlib import Path

    root = str(Path(__file__).resolve().parent.parent)
    plugin_scripts = str(Path(root) / "operator-claude-plugin" / "scripts")
    for entry in (root, plugin_scripts):
        if entry not in sys.path:
            sys.path.insert(0, entry)

    import config_gate

    from scripts.remediate_veto_companies import post_webhook_event

    return post_webhook_event(
        company_id, True, config_gate.load_config(), recompute=True, domain=domain,
    )


def now_iso_ms() -> str:
    """`new Date().toISOString()`'s exact shape — the format `mergeCompanies.js` stamps
    into `lv_*_verified_at` (a HubSpot `datetime` property). Mirrored rather than
    reinvented: a format HubSpot rejects 400s only live, and a silently unstamped record
    is still stale, which voids the gate-skip the caller is trying to produce."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y-%m-%dT%H:%M:%S')}.{now.microsecond // 1000:03d}Z"


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
