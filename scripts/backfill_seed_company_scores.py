#!/usr/bin/env python3
"""scripts/backfill_seed_company_scores.py

Phase 40 Plan 07 (D-09/D-10) — the component-seeding backfill mechanism. HubSpot's
`PROPERTY_DEFAULT_VALUE`/`default-value-generation` stamp (0 on every writable component)
only fires on FUTURE company creations (PORTAL-FACTS.md's 40-04 finding, "enrollment
requires a genuine future property-change event"), never retroactively. The 712
pre-existing companies have no components at all, so `lv_icp_fit_score` (a
`calculation_equation` property) reads blank — not 0, blank, because HubSpot's calculated
formula blanks entirely when any one referenced term is null (PORTAL-FACTS.md's Task 1
reversible spike) — and WF1 never fires.

This script computes each record's five component scores from its OWN current canonical
inputs (`lv_org_type`, `lv_produces_content`, `lv_country_region_normalized`,
`lv_revenue_band`, `lv_is_gambling_operator`) via `src/icp_scoring.py`'s loaded
`config/icp_scoring.yaml`, and batch-PATCHes those five component properties only. Writing
all five (never a subset — a missing term blanks the sum) makes the calculated sum
recompute, which is what actually populates `lv_icp_fit_score` and, from it,
`lv_icp_tier_derived` for a pre-existing record. It NEVER computes or writes
`lv_icp_fit_score`, `lv_icp_tier_derived`, `lv_anti_icp_flag` or `lv_anti_icp_reason` —
the calculated properties and the n8n pipeline already own those respectively; a second
producer on a field that already has one is exactly what D-01's veto handover in 40-05
removed.

AS-BUILT CORRECTION (2026-08-19, Phase 50 follow-up): this docstring previously said the
component write makes "WF1 fire", and the settle below polled `lv_icp_tier`. Phase 50
deleted WF1 (`4625147345`) on 2026-08-14 and archived `lv_icp_tier`, so that premise is
now categorically false — no workflow grades the tier at all. The tier is a calculated
property (`lv_icp_tier_derived`) computed server-side from `lv_icp_fit_score` and
`lv_anti_icp_flag_num`, with no event and no workflow in the path. The write path here was
always correct and is unchanged; only the post-write confirmation needed repointing. Note
an archived property does not error or read null — it returns its frozen last value — so
the old poll would have settled instantly on stale data and reported it as proof.

D-09 scopes THIS phase to proving the mechanism on a small sample — a hard cap enforced by
this script itself, never trusted to the caller. The portfolio-wide 712-record run is
Phase 41's job, after enrichment has populated inputs so the seeded scores land meaningful
instead of mass-zero.

Two-key arm: DRY_RUN=false AND ALLOW_SCORE_BACKFILL=true (a phase-scoped flag, deliberately
distinct from the generic property-writes flag a migration script might leave armed).
Portal id asserted before any network call.

`.env` is Read/Bash permission-blocked this session — the operator invocation is:
    ALLOW_SCORE_BACKFILL=true DRY_RUN=false .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/backfill_seed_company_scores.py', run_name='__main__')"

Run dry-run first (the default) and review the printed sample and payload before arming.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*`/`scripts.*` imports resolve

from src.hubspot_client import batch_update_companies, get_record, search_records  # noqa: E402
from src.icp_scoring import compute_icp_score  # noqa: E402
from src.schemas import HubSpotRecord  # noqa: E402

# WR-01-style discipline (matches tests/scoring_fixtures.py / probe_scoring_recalc_latency.py):
# hard-coded, no env override.
EXPECTED_PORTAL_ID = "22617666"

# The five canonical inputs a company must carry for its component scores to mean
# anything (D-10). A record with none of these populated would seed to all-zero and
# prove nothing about the mechanism.
CANONICAL_INPUT_PROPS = [
    "lv_org_type",
    "lv_produces_content",
    "lv_country_region_normalized",
    "lv_revenue_band",
    "lv_is_gambling_operator",
]

# The five writable component properties this script is the ONLY thing in this plan
# allowed to write. lv_icp_fit_score/_tier/_flag/_reason are derived elsewhere and must
# never appear in a payload this script builds.
COMPONENT_PROPS = [
    "org_type_score",
    "geography_score",
    "annual_revenue_score",
    "produces_content_score",
    "gambling_score",
]

# D-09: a small default and a small hard ceiling. Even an operator-supplied
# BACKFILL_MAX_RECORDS above the ceiling is clamped down, not honored -- the
# portfolio-wide 712-record run is Phase 41's job, not something a single env var typo
# should be able to trigger here.
DEFAULT_MAX_RECORDS = 10
# Phase 49 Plan 01 (D-03): raised 25 -> 100 so this module's cap no longer refuses the
# 66-record live scored population that scripts/rescore_population.py re-derives. This is
# a strengthening, not a relaxation: a count cap of 100 still permits ANY <=100-record
# subset (a stale snapshot, a 60-of-66 typo, a race-polluted search result). The new,
# separate enforce_exact_population() predicate below is what actually pins the sample to
# the live-derived scored population -- the two checks are independent and both required.
# See PINNED_COMPANY_ID_ORDER in scripts/remediate_veto_companies.py for the Phase 47
# precedent of pinning an exact set rather than trusting a count.
HARD_CEILING_RECORDS = 100

BATCH_CHUNK_SIZE = 100


# --- pure component computation (D-10: reads points via src/icp_scoring.py's loaded
# config, never a second table) ---------------------------------------------------------

def compute_components(props: dict) -> dict:
    """Computes the five component scores from a record's canonical inputs, via
    src/icp_scoring.compute_icp_score -- never a second, hand-copied point table. Missing
    or unrecognised inputs contribute 0, mirroring the PROPERTY_DEFAULT_VALUE stamp new
    records get. Only the five CANONICAL_INPUT_PROPS are passed through -- other fields
    (e.g. native `country`) are deliberately excluded so this mirrors the flows' own
    lv_*-only trigger properties (40-05's retarget), not the oracle's broader native-field
    fallback."""
    canonical = {k: props.get(k) for k in CANONICAL_INPUT_PROPS if props.get(k) not in (None, "")}
    record = HubSpotRecord(object_type="companies", id="0", properties=canonical)
    result = compute_icp_score(record, {})

    by_signal = {c["signal"]: c["points"] for c in result.breakdown["components"]}
    gambling_points = 0
    for deduction in result.breakdown["graduated_deductions"]:
        if deduction["signal"] == "gambling_operator":
            gambling_points = deduction["points"]

    return {
        "org_type_score": by_signal.get("org_type", 0),
        "geography_score": by_signal.get("geography", 0),
        "annual_revenue_score": by_signal.get("revenue_band", 0),
        "produces_content_score": by_signal.get("produces_content", 0),
        "gambling_score": gambling_points,
    }


def build_updates(records: list) -> list:
    """records: [{"id": ..., "properties": {canonical inputs}}, ...] -> the batch PATCH
    payload entries. Every entry's properties dict is exactly the five COMPONENT_PROPS --
    never lv_icp_fit_score/_tier/_flag/_reason (T-40-22's offline guard, asserted in
    tests/test_backfill_seed_company_scores.py)."""
    return [
        {"id": record["id"], "properties": compute_components(record.get("properties", {}))}
        for record in records
    ]


def _chunked(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


# --- sample cap + gates (D-09; mirrors probe_scoring_recalc_latency.py's two-key triad) -

def _resolved_max_records() -> int:
    raw = os.getenv("BACKFILL_MAX_RECORDS", str(DEFAULT_MAX_RECORDS))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_MAX_RECORDS
    return min(value, HARD_CEILING_RECORDS)


def enforce_sample_cap(sample_ids: list) -> bool:
    """True if the sample is at or under the resolved cap. The script refuses (exits
    non-zero) rather than silently truncating -- D-09's scope boundary is enforced here,
    not trusted to the caller."""
    return len(sample_ids) <= _resolved_max_records()


def enforce_exact_population(sample_ids: list, live_ids: list) -> bool:
    """True only if sample_ids == the live-derived HAS_PROPERTY(lv_icp_fit_score) set,
    exactly -- a second, independent predicate added ALONGSIDE enforce_sample_cap (D-03),
    never in place of it. A count cap of 100 permits any <=100-record subset; this refuses
    everything except the intended population, including a 65-of-66 subset, a 67-id
    superset, or an empty set against a non-empty live set. Refuse (return False), never
    truncate -- same contract as enforce_sample_cap.

    Deliberately add-alongside, not in-place replacement: scripts/remediate_veto_companies.py
    imports compute_components from this module, and this module's own Phase 40 contract is
    proving the mechanism on a *small* sample -- a predicate that demanded set-equality with
    the full scored population would make a 3-record proving run impossible."""
    return set(sample_ids) == set(live_ids)


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_SCORE_BACKFILL", "false").lower() == "true"
    return (not dry_run) and allow


# --- sample selection --------------------------------------------------------------------

def _select_default_sample_ids() -> list:
    """Union (deduped, sorted) of companies with at least one canonical lv_* input
    populated, one HAS_PROPERTY search per input -- records with no inputs would all seed
    to 0 and prove nothing about the mechanism. search_records only ANDs within a single
    filterGroup, so the OR across five properties is done as five separate calls merged
    here, not a single filter expression."""
    ids = set()
    for prop in CANONICAL_INPUT_PROPS:
        result = search_records(
            "companies",
            [{"propertyName": prop, "operator": "HAS_PROPERTY"}],
            [prop],
            limit=100,
        )
        ids.update(r["id"] for r in result.get("results", []))
    return sorted(ids)


def _fetch_sample_records(sample_ids: list) -> list:
    return [
        {"id": company_id, "properties": get_record("companies", company_id, CANONICAL_INPUT_PROPS)["properties"]}
        for company_id in sample_ids
    ]


# --- main -----------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--company-id", action="append", default=[], dest="company_ids",
                         help="Explicit company id to seed (repeatable). If omitted, the "
                              "sample is selected via search_records for companies with "
                              "at least one canonical lv_* input populated.")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run the backfill.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    sample_ids = args.company_ids or _select_default_sample_ids()

    if not enforce_sample_cap(sample_ids):
        print(f"REFUSED: resolved sample has {len(sample_ids)} records, exceeding the "
              f"backfill cap ({_resolved_max_records()}, hard ceiling "
              f"{HARD_CEILING_RECORDS}). D-09 scopes this phase to a small proving sample "
              f"-- the portfolio-wide run is Phase 41. No API call made.")
        return 1

    print(f"resolved sample ({len(sample_ids)} records): {sample_ids}")

    if not sample_ids:
        print("no records to seed -- nothing to do.")
        return 0

    records = _fetch_sample_records(sample_ids)
    updates = build_updates(records)

    dry_run = not _writes_allowed()
    for update in updates:
        print(json.dumps({"id": update["id"], "properties": update["properties"]}, indent=2))

    for chunk in _chunked(updates, BATCH_CHUNK_SIZE):
        batch_update_companies(chunk, dry_run=dry_run)

    if dry_run:
        print("DRY RUN complete -- no write performed. Set DRY_RUN=false and "
              "ALLOW_SCORE_BACKFILL=true to arm.")
        return 0

    print(f"armed run complete -- {len(updates)} companies seeded. Waiting for the "
          "calculated sum and WF1 to settle (up to 120s)...")
    for update in updates:
        _settle(update["id"], "lv_icp_tier_derived")

    return 0


def _settle(company_id: str, prop: str, timeout: float = 120, interval: float = 5) -> None:
    """Polls prop until it stops changing across two consecutive reads, or timeout
    elapses. Prints the final value -- this script has no assertion of its own on the
    result, Task 3's parity sweep is what checks correctness."""
    start = time.monotonic()
    previous = None
    first_read = True
    while True:
        record = get_record("companies", company_id, [prop])
        current = record.get("properties", {}).get(prop)
        elapsed = time.monotonic() - start
        if not first_read and current == previous:
            print(f"  {company_id}: {prop}={current!r} (settled after {elapsed:.1f}s)")
            return
        first_read = False
        previous = current
        if elapsed >= timeout:
            print(f"  {company_id}: {prop}={current!r} (timed out after {elapsed:.1f}s)")
            return
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
