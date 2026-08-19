#!/usr/bin/env python3
"""scripts/backfill_dry_run.py

Phase 51 Plan 01 (D-01..D-05) -- the zero-write backfill dry-run driver. Carries one
never-scored company from a credit-capped population through ZoomInfo enrichment to a
printed HubSpot PATCH payload and a pre-registered tier prediction, WITHOUT making any
HubSpot write and WITHOUT triggering any n8n execution.

Every `patch_record` call site in this driver passes `dry_run=True` as a HARD-CODED
literal, never read from an environment variable, so there is no live-write code path to
misconfigure (SAFE-01, T-51-02).

Imports -- never reimplements -- `compute_icp_score`/`anti_icp_flag_properties` from
src.icp_scoring and `compute_components`/`COMPONENT_PROPS` from
scripts.backfill_seed_company_scores (Phase 46 parity rule: those two modules are the sole
oracle for the six numeric properties).

`.env` is Read/Bash permission-blocked this session -- operator invocation:
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/backfill_dry_run.py', run_name='__main__')"

Run from the repo root (config/icp_scoring.yaml is loaded via a CWD-relative path inside
src/icp_scoring.py). Full `after`-cursor pagination for the never-scored population
(~646 records) is a Phase 52 prerequisite -- deliberately NOT built here. This driver only
ever needs a total count (the `limit=1`/`total` trick) and a single bounded page (a sample
`<=SAMPLE_SEARCH_LIMIT` records).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*`/`scripts.*` imports resolve

from src.hubspot_client import patch_record, search_records  # noqa: E402
from src.icp_scoring import anti_icp_flag_properties, compute_icp_score  # noqa: E402
from src.schemas import HubSpotRecord  # noqa: E402
from scripts.backfill_seed_company_scores import COMPONENT_PROPS, compute_components  # noqa: E402 -- import, never re-derive
from scripts.check_provider_credits import _mint_zoominfo_token  # noqa: E402
from scripts.zoominfo_company_client import (  # noqa: E402
    enrich_company,
    zoominfo_country_region,
    zoominfo_credentials_present,
    zoominfo_credit_balance,
    zoominfo_revenue_band,
)

# WR-01-style discipline (matches every precedent script in this repo): hard-coded, no
# env override.
EXPECTED_PORTAL_ID = "22617666"

# Pre-v3 documented figure (scripts/enrichment_cost_ledger.py), carried as a conservative
# floor -- Task 3's --measure-cost flag replaces it with a live-measured figure for the
# rest of the milestone (retires research Assumption A1).
CREDITS_PER_MATCH_HUNDREDTHS_FALLBACK = 108

DEFAULT_SAMPLE_SIZE = 12
SAMPLE_SEARCH_LIMIT = 100

# The six lv_* scoring-input properties this driver's candidate patch may populate.
# lv_org_type / lv_produces_content / lv_is_hardware_vendor / lv_is_gambling_operator are
# deliberately left absent by THIS plan -- ZoomInfo does not answer them; plan 02 adds the
# D-02 gap-fill research lane for those four.
PAYLOAD_INPUT_PROPS = [
    "lv_org_type",
    "lv_produces_content",
    "lv_country_region_normalized",
    "lv_revenue_band",
    "lv_is_hardware_vendor",
    "lv_is_gambling_operator",
]

# The twelve names a dry-run payload may EVER contain: the six lv_* inputs (a matched
# row's candidate patch is always a subset of these), the five component scores, and the
# single veto-number serialization. lv_icp_fit_score / lv_icp_tier_derived /
# lv_anti_icp_flag / lv_anti_icp_reason are owned by other producers (HubSpot's own
# calculation engine and this repo's n8n pipeline respectively) and must never appear
# here.
PERMITTED_PAYLOAD_KEYS = frozenset(PAYLOAD_INPUT_PROPS + COMPONENT_PROPS + ["lv_anti_icp_flag_num"])


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def derive_credit_cap(balance_credits, credits_per_match_hundredths: int) -> int:
    """Integer-only: (balance_credits * 100) // credits_per_match_hundredths. Per-match
    cost is carried in hundredths of a credit so no float division can round a cap upward
    past what the balance actually supports. A zero, negative or unknown (None) balance
    guards to a cap of 0."""
    if balance_credits is None or balance_credits <= 0:
        return 0
    return (int(balance_credits) * 100) // credits_per_match_hundredths


def count_never_scored_companies() -> int:
    """D-01's population count: NOT_HAS_PROPERTY(lv_icp_fit_score), limit=1, read `total`
    -- no pagination needed for a count-only read."""
    result = search_records(
        "companies",
        [{"propertyName": "lv_icp_fit_score", "operator": "NOT_HAS_PROPERTY"}],
        ["name"],
        limit=1,
    )
    return result.get("total", 0)


def select_never_scored_sample(size: int) -> list:
    """A deliberately BOUNDED sample, not the population -- see module docstring. Refuses
    (raises RuntimeError) rather than silently truncating: when `size` exceeds
    SAMPLE_SEARCH_LIMIT, or when the single page returns fewer rows than requested while
    the reported population total exceeds what was returned (a genuine anomaly, since a
    never-scored population is expected to be far larger than one page)."""
    if size > SAMPLE_SEARCH_LIMIT:
        raise RuntimeError(
            f"REFUSED: requested sample size {size} exceeds the single-page search limit "
            f"({SAMPLE_SEARCH_LIMIT}). Add pagination before requesting a larger sample."
        )
    result = search_records(
        "companies",
        [{"propertyName": "lv_icp_fit_score", "operator": "NOT_HAS_PROPERTY"}],
        ["name", "domain"],
        limit=SAMPLE_SEARCH_LIMIT,
    )
    rows = sorted(result.get("results", []), key=lambda r: r["id"])
    total = result.get("total")
    if total is not None and len(rows) < size and total > len(rows):
        raise RuntimeError(
            f"REFUSED: this search returned only {len(rows)} rows (page limit "
            f"{SAMPLE_SEARCH_LIMIT}) but the reported population is {total}. Add "
            "pagination to select_never_scored_sample() before requesting a sample this "
            "size."
        )
    return [
        {
            "id": row["id"],
            "name": row.get("properties", {}).get("name"),
            "domain": row.get("properties", {}).get("domain"),
        }
        for row in rows[:size]
    ]


def build_candidate_patch(zi_attributes: dict) -> dict:
    """Builds the scoring inputs ZoomInfo can actually answer. Any key whose value is
    None is OMITTED from the returned dict entirely -- HubSpot must not receive nulls, and
    an absent lv_country_region_normalized is exactly the input compute_icp_score's
    blank-region guard reads as "not yet enriched" rather than as a non-ANZ
    determination."""
    patch = {}
    band = zoominfo_revenue_band(zi_attributes)
    if band is not None:
        patch["lv_revenue_band"] = band
    region = zoominfo_country_region(zi_attributes.get("country") if isinstance(zi_attributes, dict) else None)
    if region is not None:
        patch["lv_country_region_normalized"] = region
    return patch


def predict_tier(score: int, anti_icp_flag: bool) -> str:
    """Replicates the LIVE four-branch lv_icp_tier_derived calculation_equation directly
    from (score, anti_icp_flag) -- never reads compute_icp_score's own .tier attribute,
    which carries a fifth, Python-only "Needs Review" label the live calculation has no
    branch for."""
    if anti_icp_flag:
        return "D"
    if score >= 70:
        return "A"
    if score >= 40:
        return "B"
    if score >= 15:
        return "C"
    return "Unscored"


def build_dry_run_row(company_id: str, candidate_patch: dict) -> dict:
    """The ONE oracle call this function makes. Composes the payload as the candidate
    patch's present keys, plus compute_components(candidate_patch), plus ONLY the
    lv_anti_icp_flag_num entry from anti_icp_flag_properties(result.anti_icp_flag) -- the
    other key that function returns (lv_anti_icp_flag) and the two calculated properties
    are owned by other producers and must never appear here."""
    record = HubSpotRecord(object_type="companies", id=company_id, properties={})
    result = compute_icp_score(record, candidate_patch)

    payload = dict(candidate_patch)
    payload.update(compute_components(candidate_patch))
    payload["lv_anti_icp_flag_num"] = anti_icp_flag_properties(result.anti_icp_flag)["lv_anti_icp_flag_num"]

    assert set(payload.keys()) <= PERMITTED_PAYLOAD_KEYS, (
        f"payload key set {sorted(payload.keys())} is not a subset of "
        f"PERMITTED_PAYLOAD_KEYS {sorted(PERMITTED_PAYLOAD_KEYS)}"
    )

    return {
        "id": company_id,
        "payload": payload,
        "predicted_tier": predict_tier(result.score, result.anti_icp_flag),
        "score": result.score,
        "anti_icp_flag": result.anti_icp_flag,
        "anti_icp_reason": result.anti_icp_reason,
    }


# Only the attributes build_candidate_patch actually consumes -- trimmed before the row
# is recorded, so a committed artifact never drags in ZoomInfo marketing text
# (descriptionList etc) that this driver never reads.
_MATCHED_ATTRIBUTES_USED = ("revenue", "revenueRange", "country")


def run_dry_run(sample_size: int = DEFAULT_SAMPLE_SIZE,
                 credits_per_match_hundredths: int = CREDITS_PER_MATCH_HUNDREDTHS_FALLBACK,
                 measure_cost: bool = False) -> dict:
    """Orchestrates the single path: balance read -> cap -> population count -> bounded
    sample -> per record, skip-log and continue when `domain` is blank or when
    `enrich_company` reports unmatched, otherwise build the row. Refuses (raises
    RuntimeError) when `sample_size` exceeds the derived cap, BEFORE issuing any enrich
    request -- the credit balance read gates the sample size, never the reverse. The
    pre-spend gate always uses `credits_per_match_hundredths` (the documented fallback,
    or a caller-supplied floor) -- no measurement exists yet at gate time.

    measure_cost=True brackets the sample's enrich calls with a second balance read and
    replaces `credits_per_match_hundredths_used`/`credit_cap` in the returned result with
    figures derived from the LARGER of the measured per-match cost and the fallback, so a
    zero or free-cached measurement can never produce a division by zero or an unbounded
    cap, and a measurement above the fallback tightens the cap rather than being
    ignored (research Assumption A1)."""
    balance_before = zoominfo_credit_balance()
    gate_cap = derive_credit_cap(balance_before, credits_per_match_hundredths)

    if sample_size > gate_cap:
        raise RuntimeError(
            f"REFUSED: requested sample size {sample_size} exceeds the derived credit "
            f"cap ({gate_cap}, balance {balance_before!r}). No ZoomInfo companies/enrich "
            "call was issued."
        )

    population_total = count_never_scored_companies()
    sample = select_never_scored_sample(sample_size)

    token = _mint_zoominfo_token() if sample else None

    rows = []
    skipped = []
    enrich_calls_issued = 0
    for company in sample:
        domain = company.get("domain")
        if not domain:
            skipped.append({"id": company["id"], "reason": "no domain on record"})
            continue
        match = enrich_company(domain, token)
        enrich_calls_issued += 1
        if not match.get("matched"):
            skipped.append({
                "id": company["id"],
                "reason": match.get("reason") or "no zoominfo company match",
            })
            continue
        candidate_patch = build_candidate_patch(match["attributes"])
        row = build_dry_run_row(company["id"], candidate_patch)
        row["matched_attributes"] = {
            k: match["attributes"][k] for k in _MATCHED_ATTRIBUTES_USED if k in match["attributes"]
        }
        rows.append(row)

    result = {
        "population_total": population_total,
        "credit_balance_before": balance_before,
        "credits_per_match_hundredths_used": credits_per_match_hundredths,
        "credit_cap": gate_cap,
        "sample_size": sample_size,
        "rows": rows,
        "skipped": skipped,
    }

    if measure_cost:
        balance_after = zoominfo_credit_balance()
        result["credit_balance_after"] = balance_after
        measured = 0
        if enrich_calls_issued > 0 and balance_before is not None and balance_after is not None:
            spent = balance_before - balance_after
            measured = max((spent * 100) // enrich_calls_issued, 0)
        result["measured_credits_per_match_hundredths"] = measured
        used = max(measured, credits_per_match_hundredths)
        result["credits_per_match_hundredths_used"] = used
        result["credit_cap"] = derive_credit_cap(balance_before, used)

    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample", type=int, default=DEFAULT_SAMPLE_SIZE,
                         help="Sample size to draw from the never-scored population "
                              f"(default {DEFAULT_SAMPLE_SIZE}).")
    parser.add_argument("--out", default=None,
                         help="Optional path to write the collected dry-run result as JSON.")
    parser.add_argument("--measure-cost", action="store_true",
                         help="Bracket the sample's enrich calls with a second ZoomInfo "
                              "credit-balance read and measure the real per-match cost "
                              "(retires research Assumption A1).")
    args = parser.parse_args(argv)

    if not _has_credentials() or not zoominfo_credentials_present():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN and "
              "ZOOMINFO_CLIENT_ID/ZOOMINFO_CLIENT_SECRET must all be set to run.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    result = run_dry_run(sample_size=args.sample, measure_cost=args.measure_cost)
    result["run_at"] = datetime.now(timezone.utc).isoformat()
    result["portal_id_verified"] = EXPECTED_PORTAL_ID
    result["population_filter"] = "NOT_HAS_PROPERTY(lv_icp_fit_score)"
    result["predicted_tier_values_allowed"] = ["A", "B", "C", "D", "Unscored"]

    for row in result["rows"]:
        # dry_run is a hard-coded literal True -- this driver has no live-write code path.
        patch_record("companies", row["id"], row["payload"], dry_run=True)

    print(json.dumps(result, indent=2, default=str))

    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
