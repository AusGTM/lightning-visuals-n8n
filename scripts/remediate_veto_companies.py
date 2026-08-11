#!/usr/bin/env python3
"""scripts/remediate_veto_companies.py

Phase 47 (VETO-01/02, COVER-01/02) — the single script carrying all four write legs this
phase needs for the 17 pinned companies whose non-ANZ veto is false (blank region misread
as non-ANZ) and whose scoring inputs are blank: web-research enrichment (D-08), the
input + metadata PATCH (D-05/D-09), the component-score PATCH (reusing
scripts.backfill_seed_company_scores.compute_components, D-06), and the D-18 webhook POST
that makes the n8n "Decide Company Action" node actually recompute the veto.

This script writes ONLY: lv_org_type, lv_produces_content, lv_country_region_normalized
(the D-05 widened input set) when research actually establishes them with the evidence
config/field_policy.yaml requires; the seven source-metadata stamps for each of those it
writes; and the five component-score properties (org_type_score, geography_score,
annual_revenue_score, produces_content_score, gambling_score).

It NEVER writes lv_icp_fit_score, lv_icp_tier, lv_anti_icp_flag or lv_anti_icp_reason
(D-07) — those are derived by the HubSpot calculated property, WF1 (4625147345), and the
n8n "Decide Company Action" Code node respectively. This script changes inputs and (D-18)
POSTs a synthetic property-change event so that Code node actually runs, then polls for
the derived values to settle (Task 2's settle_tier/settle_veto) — it never patches the
derived fields directly. FORBIDDEN_PROPS is asserted disjoint from every payload dict this
script builds.

The 17 pinned ids and the 3 structurally-excluded ids (Entain, Gravity Media, Ironman —
verified-correct non-ANZ records) are literals below, enumerated from
46-SIMULATION-REPORT.md (D-12) — never discovered at runtime via search_records. There is
no search-based selection path in this script at all.

Two-key arm: DRY_RUN=false AND ALLOW_VETO_REMEDIATION=true (operator-only, per-shell,
never set by Claude — D-11/D-19). Portal id asserted before any HubSpot call.

`.env` is Read/Bash permission-blocked this session — the operator invocation is:
    ALLOW_VETO_REMEDIATION=true DRY_RUN=false .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/remediate_veto_companies.py', run_name='__main__')"

Run dry-run first (the default) and review the printed payloads before arming.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*`/`scripts.*` imports resolve
PLUGIN_SCRIPTS = ROOT / "operator-claude-plugin" / "scripts"
sys.path.insert(0, str(PLUGIN_SCRIPTS))  # flat plugin imports, same idiom scripts/june_run_arm.py uses

import requests  # noqa: E402

from src.hubspot_client import batch_update_companies, get_record  # noqa: E402
from src.icp_scoring import compute_icp_score, load_yaml  # noqa: E402
from src.schemas import HubSpotRecord  # noqa: E402
from src.web_research import claude_web_research  # noqa: E402
from scripts.backfill_seed_company_scores import compute_components  # noqa: E402

import config_gate  # noqa: E402

# WR-01-style discipline (matches backfill_seed_company_scores.py): hard-coded, no env
# override.
EXPECTED_PORTAL_ID = "22617666"

# The 17 pinned company ids, in the fixed table order 47-01-PLAN.md prints them —
# enumerated from 46-SIMULATION-REPORT.md's rows flagged blank_org_type, false_veto
# (D-12). Dry-run payload output and run-report rows are emitted in THIS order so two
# runs over the same input produce the same row order.
PINNED_COMPANY_ID_ORDER = (
    "9604732797",    # Tweed Valley Jockey Club
    "9604794661",    # Sapphire Coast Turf Club (Bega Valley)
    "9605273630",    # Port Macquarie Race Club
    "9604732795",    # Rockhampton Jockey Club
    "9604738976",    # Bunbury Turf Club
    "9604787229",    # The Alice Springs Turf Club
    "10152138518",   # Thoroughbred Park
    "10215097384",   # Wyong
    "14752488879",   # Coffs Harbour Racing Club
    "17317381378",   # Editix
    "17317850381",   # Jam TV
    "17696004613",   # Pinjarra Park
    "18047161864",   # Simtech LED
    "18796602894",   # The Kalgoorlie-Boulder Racing Club
    "19100977027",   # Newcastle Harness Racing Club
    "20538284384",   # Waikato Racing Club Inc
    "20943964946",   # The Rumble / Pacific Action Sports
)
PINNED_COMPANY_IDS = frozenset(PINNED_COMPANY_ID_ORDER)

# Structurally excluded, never writable by this script — verified correct non-ANZ records
# (2026-08-11). Not a filter: any id absent from PINNED_COMPANY_IDS is refused, and these
# three are simply never members of it. Named here only so resolve_pinned_ids can give a
# clearer refusal message.
EXCLUDED_COMPANY_IDS = frozenset({"10024564084", "15860277364", "17317184159"})
_EXCLUDED_NAMES = {
    "10024564084": "Entain",
    "15860277364": "Gravity Media",
    "17317184159": "Ironman",
}
assert PINNED_COMPANY_IDS.isdisjoint(EXCLUDED_COMPANY_IDS), (
    "a pinned id and an excluded id collided -- this must never happen"
)

# Derived fields owned by the calculated property, WF1, and the n8n Decide node
# respectively (D-07). Every payload-building function below asserts its output is
# disjoint from this set before returning.
FORBIDDEN_PROPS = frozenset({
    "lv_icp_fit_score", "lv_icp_tier", "lv_anti_icp_flag", "lv_anti_icp_reason",
})

# D-05: the widened scoring-input set this phase enriches (not lv_org_type alone).
INPUT_PROPS = ("lv_org_type", "lv_produces_content", "lv_country_region_normalized")

# D-09: the seven source-metadata stamps written for every field this script writes.
METADATA_SUFFIXES = (
    "_source", "_confidence", "_evidence_url", "_evidence_summary",
    "_verified_at", "_verified_by_model", "_validation_status",
)

# config/field_policy.yaml's lv_org_type.require_evidence_url_for -- read-only input,
# never written to disk by this script.
EVIDENCE_REQUIRED_ORG_TYPES = (
    "governing_body_league", "content_producer", "hardware_vendor", "gambling_operator",
)

# The only values compute_icp_score treats as a resolved (non-"unknown") region.
VALID_REGIONS = ("AU", "NZ", "ANZ", "Other")

# D-12: the ceiling equals the pinned-set size, so VETO_MAX_RECORDS can only ever LOWER
# the cap -- never BACKFILL_MAX_RECORDS's default of 10, which would refuse all 17
# (47-RESEARCH.md Pitfall 3).
DEFAULT_MAX_RECORDS = 17
HARD_CEILING_RECORDS = 17

N8N_EXECUTION_BUDGET_MONTH = 2500

# Properties fetched per record: identity fields the research prompt reads (per
# src/web_research.py's user_payload), plus every canonical input compute_components()
# can use (D-04's "enrich first, then one recompute" needs the record's PRE-existing
# canonical inputs merged with what this run researches).
FETCH_PROPS = (
    "name", "domain", "website", "country", "industry",
    "lv_org_type", "lv_produces_content", "lv_country_region_normalized",
    "lv_revenue_band", "lv_is_gambling_operator",
)

BATCH_CHUNK_SIZE = 100

WEBHOOK_PATH = "webhook/hubspot/enrichment/event"


class PinRefused(Exception):
    """Raised when a requested company id is not one of the 17 pinned ids."""


class SettleFailed(Exception):
    """Raised when a settle poll times out, or stabilises on a value other than expected."""


class BudgetRefused(Exception):
    """Raised when a projected run would exceed the n8n monthly execution budget."""


class NotArmedError(Exception):
    """Raised when post_webhook_event is called with armed falsy -- no network call made."""


# --- pin resolution (D-12) ---------------------------------------------------------------

def resolve_pinned_ids(requested):
    """Raises PinRefused naming the offending id if any requested id is absent from
    PINNED_COMPANY_IDS -- this is the membership refusal backfill_seed_company_scores.py
    does not have. Returns the accepted ids sorted into PINNED_COMPANY_ID_ORDER order, so
    output ordering is deterministic regardless of input order."""
    for company_id in requested:
        if company_id not in PINNED_COMPANY_IDS:
            if company_id in EXCLUDED_COMPANY_IDS:
                name = _EXCLUDED_NAMES.get(company_id, "")
                raise PinRefused(
                    f"{company_id!r} ({name}) is structurally excluded -- its non-ANZ "
                    "region is verified correct, not a false veto. Refusing before any "
                    "HubSpot or n8n call."
                )
            raise PinRefused(
                f"{company_id!r} is not one of the 17 pinned company ids. Refusing "
                "before any HubSpot or n8n call."
            )
    requested_set = set(requested)
    return tuple(cid for cid in PINNED_COMPANY_ID_ORDER if cid in requested_set)


# --- sample cap + gates (mirrors backfill_seed_company_scores.py's two-key triad) --------

def _resolved_max_records() -> int:
    raw = os.getenv("VETO_MAX_RECORDS", str(DEFAULT_MAX_RECORDS))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_MAX_RECORDS
    return min(value, HARD_CEILING_RECORDS)


def enforce_sample_cap(sample_ids) -> bool:
    """True if the sample is at or under the resolved cap. The caller refuses (exits
    non-zero) rather than silently truncating."""
    return len(sample_ids) <= _resolved_max_records()


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_VETO_REMEDIATION", "false").lower() == "true"
    return (not dry_run) and allow


# --- research (D-08) ----------------------------------------------------------------------

def research_company(record: HubSpotRecord):
    """Delegates to src.web_research.claude_web_research -- returns the ProviderResult
    unchanged. Does not re-implement the research prompt."""
    return claude_web_research(record)


def _has_field_evidence(result, field: str) -> bool:
    """Strict per-field evidence check for GATING (D-14 / config/field_policy.yaml) --
    evidence_by_field only, no fallback. A field a research call did not explicitly cite
    is not evidenced, even if the response carries unrelated general evidence URLs.
    Matches src/taxonomy.py's own produces_content evidence gate."""
    return bool((result.evidence_by_field or {}).get(field))


def _evidence_url_for_metadata(result, field: str):
    """The evidence URL to STAMP for a field already cleared to write -- prefers the
    per-field citation, falling back to the response's first general evidence URL, so a
    field with no per-field citation (e.g. region, which is never evidence-gated) still
    gets a useful pointer."""
    url = (result.evidence_by_field or {}).get(field)
    if url:
        return url
    urls = result.evidence.evidence_urls if result.evidence else []
    return urls[0] if urls else None


def build_input_patch(company_id: str, result):
    """Carries only those of INPUT_PROPS the research actually established, per D-05/D-14:
    - lv_org_type: non-empty and not "unknown"; if it is one of EVIDENCE_REQUIRED_ORG_TYPES,
      only when evidenced.
    - lv_produces_content: only a real boolean AND evidenced -- false on absent evidence is
      NEVER written (D-14: false is a hard veto, and writing it on a data gap manufactures
      exactly the false-veto class this phase clears). Written as the lowercase strings
      HubSpot booleancheckbox properties store, not JSON booleans.
    - lv_country_region_normalized: only one of AU/NZ/ANZ/Other.
    """
    props = {}
    data = result.data or {}

    org_type = data.get("lv_org_type")
    if org_type and org_type != "unknown":
        if org_type not in EVIDENCE_REQUIRED_ORG_TYPES or _has_field_evidence(result, "lv_org_type"):
            props["lv_org_type"] = org_type

    produces_content = data.get("lv_produces_content")
    if isinstance(produces_content, bool) and _has_field_evidence(result, "lv_produces_content"):
        props["lv_produces_content"] = "true" if produces_content else "false"

    region = data.get("lv_country_region_normalized")
    if region in VALID_REGIONS:
        props["lv_country_region_normalized"] = region

    assert FORBIDDEN_PROPS.isdisjoint(props), "build_input_patch produced a forbidden derived-field key"
    return {"id": company_id, "properties": props}


def unresolved_reasons(company_id: str, result) -> dict:
    """Field-keyed dict of short prose reasons for every INPUT_PROPS the patch omitted --
    so an unresolved record is distinguishable from one never attempted (COVER-01, D-14)."""
    written = build_input_patch(company_id, result)["properties"]
    data = result.data or {}
    reasons = {}

    if "lv_org_type" not in written:
        org_type = data.get("lv_org_type")
        if not org_type or org_type == "unknown":
            reasons["lv_org_type"] = "research did not establish an org type"
        else:
            reasons["lv_org_type"] = (
                f"org type {org_type!r} requires an evidence URL and none was cited"
            )

    if "lv_produces_content" not in written:
        produces_content = data.get("lv_produces_content")
        if not isinstance(produces_content, bool):
            reasons["lv_produces_content"] = "research did not establish content output"
        else:
            reasons["lv_produces_content"] = (
                "produces_content requires an evidence URL and none was cited"
            )

    if "lv_country_region_normalized" not in written:
        reasons["lv_country_region_normalized"] = (
            "research did not establish a region in AU/NZ/ANZ/Other"
        )

    return reasons


def build_metadata_patch(company_id: str, result, written_fields) -> dict:
    """For each field actually written, the seven METADATA_SUFFIXES stamps (D-09)."""
    props = {}
    verified_by_model = os.getenv("ANTHROPIC_RESEARCH_MODEL", "claude-sonnet-5")
    verified_at = datetime.now(timezone.utc).isoformat()

    for field in written_fields:
        props[f"{field}_source"] = result.provider
        props[f"{field}_confidence"] = result.confidence
        props[f"{field}_evidence_url"] = _evidence_url_for_metadata(result, field)
        props[f"{field}_evidence_summary"] = result.evidence.evidence_summary if result.evidence else None
        props[f"{field}_verified_at"] = verified_at
        props[f"{field}_verified_by_model"] = verified_by_model
        props[f"{field}_validation_status"] = "web_researched"

    assert FORBIDDEN_PROPS.isdisjoint(props), "build_metadata_patch produced a forbidden derived-field key"
    return {"id": company_id, "properties": props}


# --- component scoring (reuse, never re-implement the point table) ------------------------

def build_component_patch(company_id: str, props: dict) -> dict:
    """Imports and calls scripts.backfill_seed_company_scores.compute_components -- never
    re-implements the point table. `props` must already carry the NEWLY-researched input
    values merged over the record's existing properties (D-04)."""
    components = compute_components(props)
    assert FORBIDDEN_PROPS.isdisjoint(components), "build_component_patch produced a forbidden derived-field key"
    return {"id": company_id, "properties": components}


def expected_score_and_tier(props: dict):
    """Calls src.icp_scoring.compute_icp_score on the same post-write inputs -- the
    oracle's own score/tier, for the settle assertion to compare against. Uses the
    oracle's own tier boundaries; 70/40/15 are never restated as local literals."""
    record = HubSpotRecord(object_type="companies", id="0", properties=props)
    result = compute_icp_score(record, {})
    return result.score, result.tier


# --- the D-18 webhook POST leg (no analog in the repo -- small and local) -----------------

def build_webhook_event(company_id: str, property_name: str = "lv_country_region_normalized"):
    """The raw HubSpot-shaped property-change event array D-18 specifies. Proven live in
    Phase 40-03 -- the workflow's `IF Company Bare Event` -> `HubSpot Company Fetch By Id`
    path accepts a bare object-id event with no domain match required."""
    return [{
        "objectId": str(company_id),
        "objectType": "company",
        "subscriptionType": "company.propertyChange",
        "propertyName": property_name,
        "occurredAt": int(time.time() * 1000),
    }]


def post_webhook_event(company_id: str, armed, config: dict, transport=requests):
    """`armed` has NO default, mirroring operator-claude-plugin/scripts/dispatch.py --
    raises NotArmedError when falsy before any network call. Target is config_gate-
    resolved n8n_url joined with webhook/hubspot/enrichment/event; header
    X-Enrichment-Secret from config["webhook_secret"]. Never prints the secret or the
    HubSpot token."""
    if not armed:
        raise NotArmedError(
            "Live writes are off for this run -- nothing was sent. Arming "
            "(ALLOW_VETO_REMEDIATION=true) is an operator-only, per-shell decision, "
            "never made by Claude."
        )
    url = f"{str((config or {}).get('n8n_url') or '').rstrip('/')}/{WEBHOOK_PATH}"
    headers = {"X-Enrichment-Secret": config["webhook_secret"]}
    response = transport.post(
        url, headers=headers, json=build_webhook_event(company_id), timeout=30,
    )
    response.raise_for_status()
    return response


# --- main -----------------------------------------------------------------------------

def _parse_ids_csv(raw: str) -> list:
    return [v.strip() for v in (raw or "").split(",") if v.strip()]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--company-id", action="append", default=[], dest="company_ids",
                         help="Explicit pinned company id to remediate (repeatable).")
    parser.add_argument("--ids", default="",
                         help="Comma-separated pinned company ids (alias for repeated --company-id).")
    parser.add_argument("--report", default=None,
                         help="Path to write the JSON run report.")
    return parser


def requested_ids_from_args(args) -> list:
    """The raw requested id list before pin-resolution: explicit --company-id/--ids, or
    (if neither given) the full pinned set. There is no search-based selection path at
    all (D-12) -- the fallback the backfill script has (a search_records sweep) is
    exactly the runtime-discovery D-12 forbids, so it is deliberately absent here."""
    explicit = list(args.company_ids) + _parse_ids_csv(args.ids)
    return explicit or list(PINNED_COMPANY_ID_ORDER)


def _fetch_company(company_id: str) -> HubSpotRecord:
    record = get_record("companies", company_id, list(FETCH_PROPS))
    return HubSpotRecord(object_type="companies", id=company_id, properties=record.get("properties", {}))


def _process_one(company_id: str) -> dict:
    """Runs one pinned company through research + the three payload builders. Returns
    everything main()'s print/report/armed-write step needs. No batching, no writes --
    this is the pure "one path" this task proves."""
    record = _fetch_company(company_id)
    result = research_company(record)

    input_patch = build_input_patch(company_id, result)
    written_fields = list(input_patch["properties"].keys())
    metadata_patch = build_metadata_patch(company_id, result, written_fields)
    merged_props = {**record.properties, **input_patch["properties"]}
    component_patch = build_component_patch(company_id, merged_props)
    expected_score, expected_tier = expected_score_and_tier(merged_props)
    webhook_event = build_webhook_event(company_id)

    return {
        "id": company_id,
        "input_patch": input_patch,
        "metadata_patch": metadata_patch,
        "component_patch": component_patch,
        "expected_score": expected_score,
        "expected_tier": expected_tier,
        "webhook_event": webhook_event,
        "unresolved_reasons": unresolved_reasons(company_id, result),
    }


def main(argv=None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this script.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    requested = requested_ids_from_args(args)
    try:
        resolved_ids = resolve_pinned_ids(requested)
    except PinRefused as exc:
        print(f"REFUSED: {exc}")
        return 1

    if not enforce_sample_cap(resolved_ids):
        print(f"REFUSED: resolved sample has {len(resolved_ids)} records, exceeding the "
              f"cap ({_resolved_max_records()}, hard ceiling {HARD_CEILING_RECORDS}). "
              "No API call made.")
        return 1

    print(f"RESOLVED_IDS: {json.dumps(list(resolved_ids))}")

    records = [_process_one(company_id) for company_id in resolved_ids]

    for rec in records:
        print(json.dumps(rec["input_patch"], indent=2))
        print(json.dumps(rec["metadata_patch"], indent=2))
        print(json.dumps(rec["component_patch"], indent=2))
        print(json.dumps(rec["webhook_event"], indent=2))
        if rec["unresolved_reasons"]:
            print(json.dumps({"id": rec["id"], "unresolved_reasons": rec["unresolved_reasons"]}, indent=2))

    if args.report:
        Path(args.report).write_text(json.dumps({
            "resolved_ids": list(resolved_ids),
            "writes_allowed": _writes_allowed(),
            "records": records,
        }, indent=2, default=str))

    if not _writes_allowed():
        print("DRY RUN complete -- no write performed. Set DRY_RUN=false and "
              "ALLOW_VETO_REMEDIATION=true to arm.")
        return 0

    for rec in records:
        combined_props = {**rec["input_patch"]["properties"], **rec["metadata_patch"]["properties"]}
        if combined_props:
            batch_update_companies([{"id": rec["id"], "properties": combined_props}], dry_run=False)
        batch_update_companies([rec["component_patch"]], dry_run=False)
        cfg = config_gate.load_config()
        post_webhook_event(rec["id"], True, cfg)

    print(f"armed run complete -- {len(records)} companies patched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
