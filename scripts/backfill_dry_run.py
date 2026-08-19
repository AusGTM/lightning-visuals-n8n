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
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*`/`scripts.*` imports resolve

from src.hubspot_client import patch_record, search_records  # noqa: E402
from src.icp_scoring import anti_icp_flag_properties, compute_icp_score  # noqa: E402
from src.schemas import HubSpotRecord, ProviderEvidence, ProviderResult  # noqa: E402
from src.taxonomy import normalize_org_type  # noqa: E402
from src.web_research import claude_web_research  # noqa: E402
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

# D-02 gap-fill lane (plan 02): the four scoring inputs ZoomInfo's firmographic response
# cannot answer. lv_revenue_band and lv_country_region_normalized are NOT gap-fill fields
# -- ZoomInfo answers both (build_candidate_patch above) and research must never overwrite
# them.
GAP_FILL_FIELDS = [
    "lv_org_type",
    "lv_produces_content",
    "lv_is_hardware_vendor",
    "lv_is_gambling_operator",
]

# MAX_WEB_RESEARCH_PER_RUN when set (live .env carries 10) -- refuses a --research run
# whose sample could exceed it, before any research or enrich request is issued.
MAX_RESEARCH_CALLS_DEFAULT = int(os.getenv("MAX_WEB_RESEARCH_PER_RUN", "12"))

# Phase 20 canary figure ($0.0686/record, scripts/remediate_veto_companies.py:655) --
# measured under the n8n Haiku-plus-Sonnet pipeline, NOT this driver's bare
# claude_web_research() call. Carried as an integer number of hundredths of a US cent so
# build_sizing_plan()/write_sizing_markdown() stay free of float arithmetic (matches
# scripts/rescore_population.py::estimate_rescore_cost's own precision rule). Labelled a
# prior-pipeline estimate, never presented as precise, in write_sizing_markdown().
ANTHROPIC_PER_RECORD_ESTIMATE_USD = 0.0686
ANTHROPIC_PER_RECORD_ESTIMATE_HUNDREDTHS_CENT = round(ANTHROPIC_PER_RECORD_ESTIMATE_USD * 10000)

# The Phase 51 Plan 01 tracer's own committed artifact -- build_sizing_plan() reuses its
# measured_credits_per_match_hundredths rather than re-deriving it.
TRACER_ARTIFACT_PATH = (
    ROOT / ".planning" / "phases" / "51-backfill-pipeline-credit-sizing-dry-run" / "51-TRACER-DRYRUN.json"
)

# The six lv_* scoring-input properties this driver's candidate patch may populate.
# lv_org_type / lv_produces_content / lv_is_hardware_vendor / lv_is_gambling_operator are
# answered by the D-02 gap-fill research lane (research_gap_fields/apply_research_to_patch
# below) when ZoomInfo's own attributes don't already answer them.
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

# Operator ruling, checkpoint round 2 (2026-08-19): apply_research_to_patch() was
# promoting any well-typed research answer regardless of confidence or evidence -- the
# SAME field_policy.yaml this repo's live merge engine (src/merge_policy.py) already
# enforces elsewhere declares min_confidence/require_evidence_url(_for) gates for every
# GAP_FILL_FIELDS name. This driver's own promotion path was the one place that skipped
# them. Loaded fresh per call (not cached), matching src/icp_scoring.py's own
# load_yaml("config/icp_scoring.yaml") convention -- an edited policy takes effect
# immediately and no import-time file read is required for an offline test to import
# this module.
FIELD_POLICY_PATH = ROOT / "config" / "field_policy.yaml"


def _load_field_policy() -> dict:
    return (yaml.safe_load(FIELD_POLICY_PATH.read_text()) or {}).get("companies", {})


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
    never-scored population is expected to be far larger than one page).

    Sorted by NUMERIC id (int(r["id"])), never lexicographic string order -- this portal
    mixes 10- and 11-digit HubSpot ids (e.g. "9604614548" vs "10021111653"), and a plain
    string sort would both misorder the predictions artifact's rows AND silently select a
    different slice of the population than a numeric sort would (SAFE-01 ordering probe)."""
    if size > SAMPLE_SEARCH_LIMIT:
        raise RuntimeError(
            f"REFUSED: requested sample size {size} exceeds the single-page search limit "
            f"({SAMPLE_SEARCH_LIMIT}). Add pagination before requesting a larger sample."
        )
    result = search_records(
        "companies",
        [{"propertyName": "lv_icp_fit_score", "operator": "NOT_HAS_PROPERTY"}],
        ["name", "domain", "website", "country", "industry"],
        limit=SAMPLE_SEARCH_LIMIT,
    )
    rows = sorted(result.get("results", []), key=lambda r: int(r["id"]))
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
            "website": row.get("properties", {}).get("website"),
            "country": row.get("properties", {}).get("country"),
            "industry": row.get("properties", {}).get("industry"),
        }
        for row in rows[:size]
    ]


# Diversification rule (operator ruling, 2026-08-19, the Gold Coast Turf Club checkpoint):
# the plain ascending-id sample landed entirely on one org-type cluster -- 8/8 racing/turf
# clubs, HubSpot native `industry` GAMBLING_CASINOS for every one (live-confirmed against
# three of the eight ids). This allowlist names the native `industry` values plausibly
# associated with governing bodies, leagues, broadcasters and content producers -- the org
# types that could score Tier A/B -- deliberately EXCLUDING GAMBLING_CASINOS (the cluster
# already sampled) and the population's single largest bucket, "Amusement Parks, Arcades &
# Attractions" (venues, not a plausible governing-body/broadcaster signal). Live-observed
# industry distribution over the population's first page recorded in 51-SIZING.md.
DIVERSIFICATION_INDUSTRIES = frozenset({
    "BROADCAST_MEDIA", "Broadcasting", "Media & Internet", "SPORTS",
    "ENTERTAINMENT", "Entertainment Providers", "Social Networks",
})


def select_diversified_never_scored_sample(size: int, media_slots: int) -> list:
    """Deterministic stratified sample over the SAME single bounded page
    select_never_scored_sample() draws from -- same refuse-rather-than-truncate contract,
    same numeric-id ordering, same row shape. Up to `media_slots` records whose native
    HubSpot `industry` is in DIVERSIFICATION_INDUSTRIES (ascending numeric id within that
    subset), then the remaining `size - len(media_selected)` slots filled by ascending
    numeric id from the rest of the page (excluding the media slots already taken) -- the
    same rule select_never_scored_sample() uses, applied to the residual pool, so the
    "some of the small clubs" half of the sample stays exactly as reproducible as before."""
    if size > SAMPLE_SEARCH_LIMIT:
        raise RuntimeError(
            f"REFUSED: requested sample size {size} exceeds the single-page search limit "
            f"({SAMPLE_SEARCH_LIMIT}). Add pagination before requesting a larger sample."
        )
    result = search_records(
        "companies",
        [{"propertyName": "lv_icp_fit_score", "operator": "NOT_HAS_PROPERTY"}],
        ["name", "domain", "website", "country", "industry"],
        limit=SAMPLE_SEARCH_LIMIT,
    )
    rows = sorted(result.get("results", []), key=lambda r: int(r["id"]))
    total = result.get("total")
    if total is not None and len(rows) < size and total > len(rows):
        raise RuntimeError(
            f"REFUSED: this search returned only {len(rows)} rows (page limit "
            f"{SAMPLE_SEARCH_LIMIT}) but the reported population is {total}. Add "
            "pagination to select_diversified_never_scored_sample() before requesting a "
            "sample this size."
        )

    def _as_dict(row):
        props = row.get("properties", {})
        return {
            "id": row["id"],
            "name": props.get("name"),
            "domain": props.get("domain"),
            "website": props.get("website"),
            "country": props.get("country"),
            "industry": props.get("industry"),
        }

    media_rows = [r for r in rows if r.get("properties", {}).get("industry") in DIVERSIFICATION_INDUSTRIES]
    media_selected = media_rows[:media_slots]
    media_ids = {r["id"] for r in media_selected}
    fill_rows = [r for r in rows if r["id"] not in media_ids]
    fill_selected = fill_rows[: max(size - len(media_selected), 0)]

    return [_as_dict(r) for r in media_selected] + [_as_dict(r) for r in fill_selected]


def build_candidate_patch(zi_attributes: dict, hubspot_country=None):
    """Builds the scoring inputs ZoomInfo can actually answer. Any key whose value is
    None is OMITTED from the returned dict entirely -- HubSpot must not receive nulls, and
    an absent lv_country_region_normalized is exactly the input compute_icp_score's
    blank-region guard reads as "not yet enriched" rather than as a non-ANZ
    determination.

    Country guard (operator ruling, 2026-08-19, the Gold Coast Turf Club finding):
    ZoomInfo's own `country` attribute drives the region by default, same as before. But
    when the record's OWN HubSpot `country` and ZoomInfo's `country` normalize to
    DIFFERENT non-blank regions, HubSpot's value wins -- CLAUDE.md Section 6.3 ranks
    `hubspot` trust_rank 90 above `zoominfo`'s 85, and a provider disagreeing with the
    record's own CRM data is not grounds to silently override it. Returns
    (patch, country_conflict): country_conflict is None when there was nothing to
    disagree about (including the out-of-scope case where hubspot_country is blank --
    ZoomInfo is then the only value, not a contradiction), otherwise a dict naming both
    countries/regions and which one won, so the caller can surface it in the artifact
    rather than resolve it invisibly."""
    patch = {}
    band = zoominfo_revenue_band(zi_attributes)
    if band is not None:
        patch["lv_revenue_band"] = band

    zi_country = zi_attributes.get("country") if isinstance(zi_attributes, dict) else None
    zi_region = zoominfo_country_region(zi_country)
    hs_region = zoominfo_country_region(hubspot_country)

    country_conflict = None
    region = zi_region
    if hs_region is not None and zi_region is not None and hs_region != zi_region:
        region = hs_region  # HubSpot's own record wins (trust_rank 90 > zoominfo's 85)
        country_conflict = {
            "hubspot_country": hubspot_country,
            "hubspot_region": hs_region,
            "zoominfo_country": zi_country,
            "zoominfo_region": zi_region,
            "resolved_region": region,
        }

    if region is not None:
        patch["lv_country_region_normalized"] = region

    return patch, country_conflict


# Operator ruling, checkpoint round 2 (2026-08-19), work item 2 second lever: measured
# claude_web_research() flip rate (51-RESEARCH-REPRODUCIBILITY.json, "before" label) showed
# lv_produces_content/lv_is_hardware_vendor/lv_is_gambling_operator flipping across
# repeated live calls at confidence/evidence levels that ALREADY clear the field_policy
# gate above -- so the gate alone (lever one) cannot fix it. The claude-api skill's
# migration notes confirm claude-sonnet-5 (this project's ANTHROPIC_RESEARCH_MODEL
# default, src/web_research.py) rejects any explicit `temperature` with a 400 -- so
# deterministic decoding (temperature=0) is not an available lever on this model.
# Majority-of-3 vote across repeated live calls is the remaining lever the operator
# explicitly sanctioned ("deterministic decoding, repeated-call majority, requiring
# corroborating evidence"). Odd number so a boolean vote never ties by construction;
# lv_org_type (string) CAN still tie (three distinct answers) -- ties resolve to no
# majority (None), never a guessed value.
RESEARCH_VOTE_REPETITIONS = 3


def _majority_bool(values):
    """None entries are non-votes (abstentions), never counted as a False vote -- a tied
    or all-abstain vote resolves to None (absent), never a defaulted False, for the same
    reason apply_research_to_patch never defaults a missing boolean to False."""
    votes = [v for v in values if isinstance(v, bool)]
    if not votes:
        return None
    true_count = sum(votes)
    false_count = len(votes) - true_count
    if true_count > false_count:
        return True
    if false_count > true_count:
        return False
    return None


def _majority_str(values):
    """Most-common non-empty string value; ties resolve to None (no majority), never an
    arbitrary tie-break guess."""
    votes = [v for v in values if isinstance(v, str) and v]
    if not votes:
        return None
    counts = Counter(votes)
    top_count = max(counts.values())
    tied = [v for v in counts if counts[v] == top_count]
    return tied[0] if len(tied) == 1 else None


def research_with_majority_vote(record: HubSpotRecord, repetitions: int = RESEARCH_VOTE_REPETITIONS):
    """Calls claude_web_research `repetitions` times and folds the results into a single
    ProviderResult carrying the MAJORITY answer per GAP_FILL_FIELDS name (see
    RESEARCH_VOTE_REPETITIONS' comment for why: temperature=0 is unavailable on
    claude-sonnet-5, so voting across repeated calls is the reproducibility lever used
    instead). A single failed repetition is dropped, never raised (mirrors
    research_gap_fields' own never-crash discipline); if every repetition fails, returns
    None exactly as a single failed call would.

    `confidence` on the returned result is the mean confidence of the calls that agree
    with the majority on every field that HAS a majority (the calls whose answer the
    majority patch actually reflects) -- not a mean over all calls including outvoted
    ones, which would understate how confident the winning answer actually was. Falls
    back to the mean of all calls only if no single call agreed with the majority on
    every field (can happen when different fields' majorities come from different
    subsets of calls).

    Top-level `evidence` (the evidence_urls list surfaced in the dry-run row) is taken
    from the first call whose lv_produces_content answer matches that field's majority --
    the single highest-leverage GAP_FILL_FIELDS name (CLAUDE.md SS10.1: 20 base-score
    points AND the sole no-content hard-veto trigger) -- falling back to the first call
    when lv_produces_content had no majority, so the evidence shown always supports an
    answer this function actually promoted, never an outvoted one."""
    results = []
    for _ in range(repetitions):
        try:
            result = claude_web_research(record)
        except Exception:
            continue
        if result is not None:
            results.append(result)
    if not results:
        return None

    majority_data = {}
    majority_evidence_by_field = {}
    for field in GAP_FILL_FIELDS:
        raw_values = [(getattr(r, "data", None) or {}).get(field) for r in results]
        majority = _majority_str(raw_values) if field == "lv_org_type" else _majority_bool(raw_values)
        if majority is None:
            continue
        majority_data[field] = majority
        for r in results:
            if (getattr(r, "data", None) or {}).get(field) == majority:
                evidence_by_field = getattr(r, "evidence_by_field", None) or {}
                if field in evidence_by_field:
                    majority_evidence_by_field[field] = evidence_by_field[field]
                break

    def _agrees_with_majority(r) -> bool:
        data = getattr(r, "data", None) or {}
        return all(data.get(field) == value for field, value in majority_data.items())

    agreeing = [r for r in results if _agrees_with_majority(r)]
    confidence_pool = agreeing if agreeing else results
    confidences = [
        c for c in (getattr(r, "confidence", None) for r in confidence_pool)
        if isinstance(c, (int, float)) and not isinstance(c, bool)
    ]
    avg_confidence = int(sum(confidences) / len(confidences)) if confidences else 0

    content_majority = majority_data.get("lv_produces_content")
    evidence_source = results[0]
    if content_majority is not None:
        for r in results:
            if (getattr(r, "data", None) or {}).get("lv_produces_content") == content_majority:
                evidence_source = r
                break
    evidence = getattr(evidence_source, "evidence", None) or ProviderEvidence()

    return ProviderResult(
        provider="claude_web",
        object_type=record.object_type,
        matched=True,
        confidence=avg_confidence,
        data=majority_data,
        evidence=evidence,
        evidence_by_field=majority_evidence_by_field,
    )


def research_gap_fields(company: dict, zi_attributes: dict, candidate_patch: dict):
    """D-02 gap-fill lane. Returns None -- issuing NO call at all -- when every name in
    GAP_FILL_FIELDS is already present in `candidate_patch` (ZoomInfo already answered
    everything research could add). Otherwise builds a HubSpotRecord carrying the
    record's name/domain/website/country/industry and calls
    research_with_majority_vote(record) -- RESEARCH_VOTE_REPETITIONS live calls folded
    into one majority-voted answer (operator ruling, checkpoint round 2: see that
    function's docstring for why a single call was not reproducible enough). NOTE: the
    underlying claude_web_research() call returns the mock fixture unless
    USE_MOCK_WEB_RESEARCH is explicitly set to a false value in the process environment --
    a live invocation that forgets to set it produces fixture data silently, REPETITIONS
    times. Any exception is caught and degraded to None here -- never raised -- so a
    malformed/failed research call becomes a skip-logged reason at the call site, never a
    crash (mirrors scripts/check_provider_credits.py's never-crash discipline)."""
    if all(field in candidate_patch for field in GAP_FILL_FIELDS):
        return None
    record = HubSpotRecord(
        object_type="companies",
        id=company["id"],
        properties={
            "name": company.get("name"),
            "domain": company.get("domain"),
            "website": company.get("website"),
            "country": company.get("country"),
            "industry": company.get("industry"),
        },
    )
    try:
        return research_with_majority_vote(record)
    except Exception:
        return None


def apply_research_to_patch(candidate_patch: dict, research_result) -> dict:
    """Merges ONLY the GAP_FILL_FIELDS names still absent from `candidate_patch`, and only
    when the research result's value for that name is present, well-formed, AND clears
    config/field_policy.yaml's own gate for that field (operator ruling, checkpoint round
    2, 2026-08-19 -- see FIELD_POLICY_PATH's comment). NEVER overwrites a value ZoomInfo
    already supplied (T-51-07). lv_org_type passes through src.taxonomy.normalize_org_type
    so only live enum values reach the oracle -- but only when the raw value is not None;
    normalize_org_type(None) returns the "unknown" default, which IS a guess and must not
    be written. Boolean fields accept only real booleans (isinstance check, no string
    coercion): a null/non-bool answer leaves the key absent rather than defaulting to
    False, because a defaulted False on lv_produces_content would fire the no-content hard
    veto on a record nobody actually researched -- an absent key is exactly what
    compute_icp_score's blank-input guards read as "not yet enriched".

    Field-policy gate: a research answer below its field's `min_confidence`, or missing a
    URL required by `require_evidence_url` (lv_produces_content) / `require_evidence_url_for`
    (lv_org_type, only for the listed org types), is treated exactly like an absent
    answer -- the key stays out of the patch rather than being promoted on a low-confidence
    or uncorroborated guess. lv_is_hardware_vendor/lv_is_gambling_operator carry a
    min_confidence gate in the same policy but no evidence-url requirement."""
    patch = dict(candidate_patch)
    if research_result is None:
        return patch
    data = getattr(research_result, "data", None)
    if not isinstance(data, dict):
        return patch

    confidence = getattr(research_result, "confidence", None)
    evidence_by_field = getattr(research_result, "evidence_by_field", None) or {}
    policy = _load_field_policy()

    for field in GAP_FILL_FIELDS:
        if field in patch:
            continue  # never overwrite a ZoomInfo-supplied value
        if field not in data:
            continue
        value = data[field]

        field_policy = policy.get(field, {})
        min_confidence = field_policy.get("min_confidence", 0)
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or confidence < min_confidence:
            continue  # below the declared confidence gate -- treat as absent, never guess

        if field == "lv_org_type":
            if value is None:
                continue
            normalized = normalize_org_type(value)
            evidence_required_for = field_policy.get("require_evidence_url_for", [])
            if normalized in evidence_required_for and field not in evidence_by_field:
                continue  # gated org type with no cited evidence -- stays absent
            patch[field] = normalized
        else:
            if not isinstance(value, bool):
                continue
            if field_policy.get("require_evidence_url") and field not in evidence_by_field:
                continue  # e.g. lv_produces_content requires a cited evidence URL
            patch[field] = value
    return patch


def build_skip_entry(company: dict, reason: str) -> dict:
    """D-04 skip contract: {"id", "name", "domain", "reason"} and NOTHING else -- no
    payload key, no partial patch, no predicted tier. `reason` must be a non-empty
    string. Every skip site in run_dry_run routes through this one function so the
    contract cannot silently drift between the no-domain and no-zoominfo-match sites."""
    return {
        "id": company["id"],
        "name": company.get("name"),
        "domain": company.get("domain"),
        "reason": reason,
    }


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


def _tracer_measured_credits_per_match_hundredths(tracer_path=TRACER_ARTIFACT_PATH) -> int:
    """Reads 51-TRACER-DRYRUN.json's live-measured per-match cost. NEVER raises -- any
    read/parse failure, missing file, or non-numeric field degrades to
    CREDITS_PER_MATCH_HUNDREDTHS_FALLBACK, the same floor build_sizing_plan() applies on
    top of whatever this returns."""
    try:
        data = json.loads(Path(tracer_path).read_text())
        value = data.get("measured_credits_per_match_hundredths")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return int(value)
    except Exception:
        pass
    return CREDITS_PER_MATCH_HUNDREDTHS_FALLBACK


def build_sizing_plan(sample_size: int, credits_per_match_hundredths: int = None,
                       tracer_path=TRACER_ARTIFACT_PATH) -> dict:
    """D-03 sizing gate (FILL-01). Read-only: one ZoomInfo usage GET
    (zoominfo_credit_balance) and one HubSpot count search (count_never_scored_companies)
    -- no enrich call, no HubSpot write, no n8n execution. When `credits_per_match_hundredths`
    is not supplied, reuses the LARGER of the measured figure from 51-TRACER-DRYRUN.json
    and CREDITS_PER_MATCH_HUNDREDTHS_FALLBACK (retiring research Assumption A1, same rule
    plan 01's own --measure-cost path already applies). Raises RuntimeError naming both
    `sample_size` and the derived `credit_cap` when the sample would exceed the cap -- run
    at the top of run_dry_run(), before any enrich request is issued anywhere in this
    driver (D-03: size against the balance the account actually has, never discover
    exhaustion partway)."""
    if credits_per_match_hundredths is None:
        credits_per_match_hundredths = max(
            _tracer_measured_credits_per_match_hundredths(tracer_path),
            CREDITS_PER_MATCH_HUNDREDTHS_FALLBACK,
        )
    population_total = count_never_scored_companies()
    credit_balance = zoominfo_credit_balance()
    credit_cap = derive_credit_cap(credit_balance, credits_per_match_hundredths)

    if sample_size > credit_cap:
        raise RuntimeError(
            f"REFUSED: requested sample size {sample_size} exceeds the derived credit "
            f"cap ({credit_cap}, balance {credit_balance!r}, "
            f"{credits_per_match_hundredths} hundredths/match). No ZoomInfo "
            "companies/enrich call was issued."
        )

    research_calls_projected = min(sample_size, MAX_RESEARCH_CALLS_DEFAULT)
    # ceil(sample_size * credits_per_match_hundredths / 100) -- integer-only, matches
    # scripts/rescore_population.py::estimate_rescore_cost's own precision rule.
    credits_projected_for_sample = -(-(sample_size * credits_per_match_hundredths) // 100)

    return {
        "population_total": population_total,
        "credit_balance": credit_balance,
        "credits_per_match_hundredths": credits_per_match_hundredths,
        "credit_cap": credit_cap,
        "sample_size": sample_size,
        "credits_projected_for_sample": credits_projected_for_sample,
        "research_calls_projected": research_calls_projected,
        "anthropic_estimate_usd_hundredths": research_calls_projected * ANTHROPIC_PER_RECORD_ESTIMATE_HUNDREDTHS_CENT,
    }


def write_sizing_markdown(plan: dict, path) -> None:
    """Emits 51-SIZING.md from a build_sizing_plan() dict: run timestamp, verified portal
    id, a table of every figure, the explicit credit arithmetic with actual numbers
    substituted, a statement of how many credits the tracer already spent plus how many
    the sample will spend and that the sum sits inside the cap, and a labelled-assumptions
    section carrying A1 (retired) and A2 (still open, not measured for this call pattern)
    verbatim in substance. No credential material is ever written here."""
    tracer_credits_spent = 1  # 51-01's live tracer run spent exactly 1 ZoomInfo credit
    total_credits_this_phase = tracer_credits_spent + plan["credits_projected_for_sample"]

    lines = [
        "# Phase 51 Sizing -- Credit Balance, Population and Sample Cap",
        "",
        f"**Run at (UTC):** {datetime.now(timezone.utc).isoformat()}",
        f"**Verified portal id:** {EXPECTED_PORTAL_ID}",
        "",
        "## Figures",
        "",
        "| Figure | Value |",
        "|---|---|",
        f"| Population total (`NOT_HAS_PROPERTY(lv_icp_fit_score)` company search, live) | {plan['population_total']} |",
        f"| ZoomInfo credit balance (live, `users/usage`) | {plan['credit_balance']} |",
        f"| Credits per match, hundredths (measured, floored at fallback) | {plan['credits_per_match_hundredths']} |",
        f"| Credit cap | {plan['credit_cap']} |",
        f"| Sample size (chosen) | {plan['sample_size']} |",
        f"| Credits projected for sample | {plan['credits_projected_for_sample']} |",
        f"| Research calls projected (bounded by MAX_WEB_RESEARCH_PER_RUN) | {plan['research_calls_projected']} |",
        f"| Anthropic research-cost estimate (hundredths of a US cent) | {plan['anthropic_estimate_usd_hundredths']} |",
        "",
        "## Credit arithmetic",
        "",
        "`credit_cap = (credit_balance * 100) // credits_per_match_hundredths = "
        f"({plan['credit_balance']} * 100) // {plan['credits_per_match_hundredths']} = {plan['credit_cap']}`",
        "",
        f"The Phase 51 Plan 01 tracer already spent **{tracer_credits_spent}** ZoomInfo credit on "
        "one live `companies/enrich` call. This sample is projected to spend "
        f"**{plan['credits_projected_for_sample']}** more, for a phase total of "
        f"**{total_credits_this_phase}** credits -- inside the {plan['credit_cap']}-credit cap.",
        "",
        "## Assumptions (labelled)",
        "",
        "- **A1 (retired):** the ZoomInfo per-match cost is now measured live by the "
        "Phase 51 Plan 01 tracer (100 hundredths-of-a-credit/match), not the previously "
        f"inferred pre-v3 1.08 credits/match figure. This sizing uses the LARGER of that "
        f"measured figure and the documented CREDITS_PER_MATCH_HUNDREDTHS_FALLBACK="
        f"{CREDITS_PER_MATCH_HUNDREDTHS_FALLBACK}, so a zero or free-cached measurement can "
        "never produce an unbounded cap.",
        f"- **A2 (still open):** the Anthropic research-cost estimate "
        f"(${ANTHROPIC_PER_RECORD_ESTIMATE_USD}/record, ~{plan['anthropic_estimate_usd_hundredths']} "
        "hundredths-of-a-US-cent per projected research call) is a **prior-pipeline "
        "estimate, NOT measured for this call pattern** -- it was measured under a "
        "combined n8n Haiku-research plus Sonnet-judge pipeline, which this milestone's "
        "design does not use (no judge/validator step at all). Treat it as a rough "
        "estimate, not a precise per-record cost.",
        "",
    ]
    Path(path).write_text("\n".join(lines))


def run_dry_run(sample_size: int = DEFAULT_SAMPLE_SIZE,
                 credits_per_match_hundredths: int = CREDITS_PER_MATCH_HUNDREDTHS_FALLBACK,
                 measure_cost: bool = False,
                 research: bool = False,
                 max_research_calls: int = None,
                 diversified: bool = False,
                 media_slots: int = None) -> dict:
    """Orchestrates the single path: build_sizing_plan() (balance read -> cap ->
    population count, refusing before any enrich request if sample_size exceeds the cap)
    -> bounded sample -> per record, skip-log-and-continue (via build_skip_entry) when
    `domain` is blank or when `enrich_company` reports unmatched, otherwise build the row.
    The skip-and-continue sites sit BEFORE the research call site in the loop body, so a
    record ZoomInfo did not match structurally can never reach research_gap_fields (D-04:
    no whole-record research rescue) -- a property of control flow, not a conditional a
    later edit could invert.

    diversified=True (operator ruling, 2026-08-19) swaps select_never_scored_sample() for
    select_diversified_never_scored_sample() -- same page, same refuse contract, but
    stratified by native `industry` (DIVERSIFICATION_INDUSTRIES) instead of pure ascending
    id, so the sample is not entirely one org-type cluster. media_slots defaults to half of
    sample_size, rounded up (ceil), when not given. The chosen rule and slot count are
    recorded on the returned result (`sample_selection_rule`, `media_slots`) so the
    artifact states which rule produced it, exactly as the plain rule already did
    implicitly by being the only rule that existed.

    research=True gates the D-02 gap-fill lane; max_research_calls (default
    MAX_RESEARCH_CALLS_DEFAULT, itself read from MAX_WEB_RESEARCH_PER_RUN) refuses the run
    -- BEFORE issuing any research or enrich request -- if `sample_size` could exceed it.

    measure_cost=True brackets the sample's enrich calls with a second balance read and
    replaces `credits_per_match_hundredths_used`/`credit_cap` in the returned result with
    figures derived from the LARGER of the measured per-match cost and the fallback
    (research Assumption A1).

    Before returning, asserts the predictions/skip partition is exact: the rows' ids and
    the skipped entries' ids are disjoint and their union equals the sample's id set,
    raising RuntimeError naming the offending ids otherwise -- the specific failure D-04
    exists to make structurally impossible (a silently dropped company)."""
    plan = build_sizing_plan(sample_size, credits_per_match_hundredths=credits_per_match_hundredths)
    balance_before = plan["credit_balance"]
    gate_cap = plan["credit_cap"]
    population_total = plan["population_total"]

    if research:
        effective_max_research = (
            max_research_calls if max_research_calls is not None else MAX_RESEARCH_CALLS_DEFAULT
        )
        # research_gap_fields now issues RESEARCH_VOTE_REPETITIONS raw calls per company
        # (majority vote, operator ruling checkpoint round 2) -- the cap check must budget
        # for that multiplier, not just one call per company, or a run could silently
        # exceed MAX_WEB_RESEARCH_PER_RUN.
        projected_calls = sample_size * RESEARCH_VOTE_REPETITIONS
        if projected_calls > effective_max_research:
            raise RuntimeError(
                f"REFUSED: requested sample size {sample_size} at "
                f"{RESEARCH_VOTE_REPETITIONS} majority-vote calls/company "
                f"({projected_calls} total) exceeds the research call cap "
                f"({effective_max_research}, from MAX_WEB_RESEARCH_PER_RUN). No ZoomInfo "
                "companies/enrich call and no research call was issued."
            )

    if diversified:
        slots = media_slots if media_slots is not None else -(-sample_size // 2)  # ceil half
        sample = select_diversified_never_scored_sample(sample_size, slots)
    else:
        slots = None
        sample = select_never_scored_sample(sample_size)

    token = _mint_zoominfo_token() if sample else None

    rows = []
    skipped = []
    enrich_calls_issued = 0
    research_calls_made = 0
    for company in sample:
        domain = company.get("domain")
        if not domain:
            skipped.append(build_skip_entry(company, "no domain on record"))
            continue
        match = enrich_company(domain, token)
        enrich_calls_issued += 1
        if not match.get("matched"):
            skipped.append(build_skip_entry(company, match.get("reason") or "no zoominfo company match"))
            continue

        zi_attributes = match.get("attributes") if isinstance(match.get("attributes"), dict) else {}
        candidate_patch, country_conflict = build_candidate_patch(zi_attributes, hubspot_country=company.get("country"))
        sources = {field: "zoominfo" for field in candidate_patch}
        if country_conflict is not None:
            sources["lv_country_region_normalized"] = "hubspot"  # guard overrode ZoomInfo's disagreeing value
        research_filled = []
        evidence_urls = []

        if research:
            research_result = research_gap_fields(company, zi_attributes, candidate_patch)
            if research_result is not None:
                # Ceiling projection, RESEARCH_VOTE_REPETITIONS raw calls per company --
                # matches this function's existing credits_spent ceiling-projection
                # convention (comment above, "not a live re-measurement") rather than
                # metering exactly how many of the REPETITIONS calls actually succeeded.
                research_calls_made += RESEARCH_VOTE_REPETITIONS
                before_keys = set(candidate_patch)
                candidate_patch = apply_research_to_patch(candidate_patch, research_result)
                research_filled = sorted(set(candidate_patch) - before_keys)
                for field in research_filled:
                    sources[field] = "claude_web"
                evidence = getattr(research_result, "evidence", None)
                if evidence is not None:
                    evidence_urls = list(evidence.evidence_urls)

        row = build_dry_run_row(company["id"], candidate_patch)
        row["name"] = company.get("name")
        row["domain"] = domain
        row["sources"] = sources
        row["research_filled"] = research_filled
        row["evidence_urls"] = evidence_urls
        row["country_conflict"] = country_conflict  # None unless HubSpot/ZoomInfo regions disagreed
        row["industry"] = company.get("industry")  # native HubSpot value; shows which diversification bucket a row came from
        row["matched_attributes"] = {
            k: zi_attributes[k] for k in _MATCHED_ATTRIBUTES_USED if k in zi_attributes
        }
        rows.append(row)

    sample_ids = {company["id"] for company in sample}
    row_ids = {row["id"] for row in rows}
    skip_ids = {entry["id"] for entry in skipped}
    overlap = row_ids & skip_ids
    if overlap:
        raise RuntimeError(
            f"PARTITION VIOLATION: ids present in both predictions and skip log: {sorted(overlap)}"
        )
    union = row_ids | skip_ids
    if union != sample_ids:
        raise RuntimeError(
            "PARTITION VIOLATION: predictions+skip log do not equal the sample id set -- "
            f"missing={sorted(sample_ids - union)} extra={sorted(union - sample_ids)}"
        )

    result = {
        "population_total": population_total,
        "credit_balance_before": balance_before,
        "credits_per_match_hundredths_used": credits_per_match_hundredths,
        "credit_cap": gate_cap,
        "sample_size": sample_size,
        "rows": rows,
        "skipped": skipped,
        "research_calls_made": research_calls_made,
        "research_vote_repetitions": RESEARCH_VOTE_REPETITIONS if research else None,
        "sample_selection_rule": "diversified_industry_stratified" if diversified else "ascending_id",
        "media_slots": slots,
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

    # Integer-only projection (ceil): enrich_calls_issued * the per-match rate actually in
    # play for this run (post measure_cost update when present).
    result["credits_spent"] = -(-(enrich_calls_issued * result["credits_per_match_hundredths_used"]) // 100)

    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample", type=int, default=DEFAULT_SAMPLE_SIZE,
                         help="Sample size to draw from the never-scored population "
                              f"(default {DEFAULT_SAMPLE_SIZE}).")
    parser.add_argument("--out", default=None,
                         help="Optional path to write the predictions result as JSON.")
    parser.add_argument("--skip-out", default=None,
                         help="Optional path to write the run's skip log as JSON.")
    parser.add_argument("--sizing-out", default=None,
                         help="Sizing-only mode: write build_sizing_plan()'s markdown via "
                              "write_sizing_markdown() and exit -- no enrich call, no "
                              "HubSpot write, no n8n execution issued in this mode.")
    parser.add_argument("--research", action="store_true",
                         help="Enable the D-02 gap-fill research lane (default off).")
    parser.add_argument("--measure-cost", action="store_true",
                         help="Bracket the sample's enrich calls with a second ZoomInfo "
                              "credit-balance read and measure the real per-match cost "
                              "(retires research Assumption A1).")
    parser.add_argument("--diversified", action="store_true",
                         help="Stratify the sample by native HubSpot `industry` "
                              "(DIVERSIFICATION_INDUSTRIES) instead of pure ascending id, "
                              "so it is not one homogeneous org-type cluster (operator "
                              "ruling 2026-08-19).")
    parser.add_argument("--media-slots", type=int, default=None,
                         help="Max records drawn from DIVERSIFICATION_INDUSTRIES when "
                              "--diversified is set (default: half of --sample, rounded up).")
    args = parser.parse_args(argv)

    if not _has_credentials() or not zoominfo_credentials_present():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN and "
              "ZOOMINFO_CLIENT_ID/ZOOMINFO_CLIENT_SECRET must all be set to run.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    if args.sizing_out:
        plan = build_sizing_plan(args.sample)
        write_sizing_markdown(plan, args.sizing_out)
        print(json.dumps(plan, indent=2, default=str))
        return 0

    result = run_dry_run(sample_size=args.sample, measure_cost=args.measure_cost, research=args.research,
                          diversified=args.diversified, media_slots=args.media_slots)
    run_at = datetime.now(timezone.utc).isoformat()

    for row in result["rows"]:
        # dry_run is a hard-coded literal True -- this driver has no live-write code path.
        patch_record("companies", row["id"], row["payload"], dry_run=True)

    predictions = {
        "run_at": run_at,
        "portal_id_verified": EXPECTED_PORTAL_ID,
        "population_filter": "NOT_HAS_PROPERTY(lv_icp_fit_score)",
        "population_total": result["population_total"],
        "credit_balance": result["credit_balance_before"],
        "credit_cap": result["credit_cap"],
        "sample_size": result["sample_size"],
        "credits_spent": result["credits_spent"],
        "research_calls_made": result["research_calls_made"],
        "predicted_tier_values_allowed": ["A", "B", "C", "D", "Unscored"],
        "sample_selection_rule": result["sample_selection_rule"],
        "media_slots": result["media_slots"],
        "rows": result["rows"],
    }
    skip_log = {
        "run_at": run_at,
        "portal_id_verified": EXPECTED_PORTAL_ID,
        "entries": result["skipped"],
        "counts": {
            "rows": len(result["rows"]),
            "skipped": len(result["skipped"]),
            "sample_size": result["sample_size"],
        },
    }

    print(json.dumps(predictions, indent=2, default=str))

    if args.out:
        Path(args.out).write_text(json.dumps(predictions, indent=2, default=str))
    if args.skip_out:
        Path(args.skip_out).write_text(json.dumps(skip_log, indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
