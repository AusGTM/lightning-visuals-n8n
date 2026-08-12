#!/usr/bin/env python3
"""scripts/enrich_coverage_companies.py

Phase 48 (COVER-01/02) -- resolves lv_org_type for the up-to-5 companies left blank after
Phase 47/47.5: an offline enum-mapping pass over 47-RESEARCH-RESULTS.json for four
already-researched records (D-01), one fresh enum-constrained web-research call for
Racing NSW (a later plan's job -- this plan's decide_org_type raises PendingResearch for
it), and the D-03 "unknown" + lv_enrichment_review_reason marker for the one record whose
identity could not be resolved (Editix).

This script writes ONLY: lv_org_type, lv_org_type_verified_at, and (only for the D-03
un-enrichable marker) lv_enrichment_review_reason. It NEVER writes lv_icp_fit_score,
lv_icp_tier, lv_anti_icp_flag or lv_anti_icp_reason (project D-07) -- those are derived by
the n8n "Decide Company Action" Code node. This script changes inputs and (D-09, a later
plan) POSTs a synthetic property-change event with recompute=True so that Code node
actually runs, then reads the derived values back -- it never patches the derived fields
directly.

Two-key arm: DRY_RUN=false AND ALLOW_ENRICH_COVERAGE=true (operator-only, per-shell, never
set by Claude). Deliberately NOT ALLOW_VETO_REMEDIATION -- a distinct arm key for a
distinct script. This plan builds the gate function only; no armed write leg exists yet.

`.env` is Read/Bash permission-blocked this session -- the operator invocation for any
live read is:
    .venv/bin/python -c "from dotenv import load_dotenv; \
        load_dotenv('/abs/path/to/.env'); import runpy; \
        runpy.run_path('scripts/enrich_coverage_companies.py', run_name='__main__')"
A bare load_dotenv() resolves relative to the calling file, not the cwd -- pass an
absolute path or every HubSpot read 401s.

Run dry-run first (the default) and review the printed payloads before any future plan
arms a write.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*`/`src.*` imports resolve

from scripts.remediate_veto_companies import (  # noqa: E402
    VALID_ORG_TYPES,
    FORBIDDEN_PROPS,
    N8N_EXECUTION_BUDGET_MONTH,
    ANTHROPIC_PER_RECORD_ESTIMATE_USD,
    refuse_if_over_budget,
    post_webhook_event,
    BudgetRefused,
    NotArmedError,
    PinRefused,
)
from src.hubspot_client import search_records  # noqa: E402

RESEARCH_RESULTS_PATH = ROOT / ".planning/phases/47-veto-remediation/47-RESEARCH-RESULTS.json"

# CONTEXT.md's per-record mapping table, in the order the table prints (Racing NSW,
# Editix, Jam TV, Waikato, The Rumble). A literal, order-preserving tuple -- the same
# pattern PINNED_COMPANY_ID_ORDER uses, new membership.
COVERAGE_COMPANY_ID_ORDER = (
    "15008671672",   # Racing NSW
    "17317381378",   # Editix
    "17317850381",   # Jam TV
    "20538284384",   # Waikato Racing Club Inc
    "20943964946",   # The Rumble / Pacific Action Sports
)
COVERAGE_COMPANY_IDS = frozenset(COVERAGE_COMPANY_ID_ORDER)

# D-01/D-05: the literal per-record decision table authored from CONTEXT.md. No
# regex/keyword mapper exists anywhere in this module -- decide_org_type below reads this
# table, it never derives the enum value from research free text. Racing NSW has no entry
# (no captured research) -- decide_org_type raises PendingResearch for it, correct until a
# later plan supplies its researched value.
ORG_TYPE_DECISIONS = {
    "17317850381": {
        "org_type": "broadcaster",
        "basis": (
            "47-RESEARCH-RESULTS.json matched=true confidence=85, 'Media company / Web "
            "television broadcaster'"
        ),
    },
    "20538284384": {
        "org_type": "individual_club_team",
        "basis": (
            "47-RESEARCH-RESULTS.json matched=true confidence=85, 'Racing Club / Sports "
            "Organization'"
        ),
    },
    "20943964946": {
        "org_type": "content_producer",
        "basis": (
            "D-05: research says 'Event organizer / Sports league operator' conf 92, but "
            "the same evidence names Skate Australia as the sport's governing body and "
            "The Rumble as a partner -- it produces and broadcasts content, it does not "
            "govern"
        ),
    },
    "17317381378": {
        "org_type": "unknown",
        "basis": (
            "D-03: matched=false confidence=5, every data field null -- identity "
            "unresolvable, not merely unresearched"
        ),
    },
}

# D-03: the un-enrichable reason, authored data (never generated prose), keyed by company
# id -- the home for every record whose ORG_TYPE_DECISIONS entry is the "unknown" marker.
UNENRICHABLE_REASONS = {
    "17317381378": (
        "Web searches for 'Editix edetrix.com.au', 'Editix broadcast streaming live', and "
        "'edetrix.com.au OR Editix Australia media' returned no results for a company "
        "matching this identity (matched=false, confidence=5, every data field null). "
        "Near-hits were EditiX (an XML editor), Editrix (an AI book-editing tool) and "
        "EditShare (media software) -- none matching the company name+domain. Identity is "
        "unresolvable, not merely unresearched."
    ),
}

# The exact live HubSpot search filter CONTEXT.md re-derived the population with.
POPULATION_FILTERS = [
    {
        "propertyName": "lv_icp_fit_score",
        "operator": "HAS_PROPERTY",
    },
    {
        "propertyName": "lv_org_type",
        "operator": "NOT_HAS_PROPERTY",
    },
]
POPULATION_PROPERTIES = (
    "hs_object_id",
    "name",
    "lv_org_type",
    "lv_icp_fit_score",
    "lv_icp_tier",
    "lv_country_region_normalized",
    "lv_anti_icp_flag",
)


class PendingResearch(Exception):
    """Raised by decide_org_type for a coverage id with no ORG_TYPE_DECISIONS entry yet
    (Racing NSW, until a later plan supplies its researched value)."""


# --- pin resolution (new membership, same pattern as resolve_pinned_ids) ------------------

def resolve_coverage_ids(requested):
    """Raises the imported PinRefused, naming the offending id, if any requested id is
    absent from COVERAGE_COMPANY_IDS -- before any HubSpot or n8n call. Returns the
    accepted ids sorted into COVERAGE_COMPANY_ID_ORDER order."""
    for company_id in requested:
        if company_id not in COVERAGE_COMPANY_IDS:
            raise PinRefused(
                f"{company_id!r} is not one of the 5 coverage company ids. Refusing "
                "before any HubSpot or n8n call."
            )
    requested_set = set(requested)
    return tuple(cid for cid in COVERAGE_COMPANY_ID_ORDER if cid in requested_set)


# --- live population re-derivation ---------------------------------------------------------

def derive_population(searcher=search_records):
    """Re-derives the live population with the exact filter CONTEXT.md used. `searcher` is
    injectable so offline tests need no network call."""
    result = searcher("companies", POPULATION_FILTERS, list(POPULATION_PROPERTIES))
    rows = result.get("results", [])
    return {
        "derived_at": datetime.now(timezone.utc).isoformat(),
        "count": len(rows),
        "ids": [row.get("id") for row in rows],
        "rows": rows,
    }


def reconcile_population(derived, literal=COVERAGE_COMPANY_ID_ORDER):
    """Never mutates either set and never narrows the run -- returns the full expected
    list even when drift is found, so a moved population is an operator decision, not
    something this driver absorbs. CONTEXT.md's snapshot (5 ids, read 2026-08-12) is the
    expectation; a different live count is a finding to disclose, not a reason to edit the
    literal tuple silently."""
    derived_ids = list(derived.get("ids") or [])
    expected = list(literal)
    missing = [cid for cid in expected if cid not in derived_ids]
    unexpected = [cid for cid in derived_ids if cid not in expected]
    return {
        "expected": expected,
        "derived": derived_ids,
        "missing": missing,
        "unexpected": unexpected,
        "drift": bool(missing or unexpected),
    }


# --- the offline mapping pass (D-01/D-05) + the D-03 marker semantics ---------------------

def _load_captured_research(company_id, path=RESEARCH_RESULTS_PATH):
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data.get(company_id)


def decide_org_type(company_id, research):
    """Returns ORG_TYPE_DECISIONS[company_id] after confirming the evidence it cites is
    present on `research` (matched/confidence, and -- for a matched record -- a non-empty
    data.lv_org_type free-text field to ground the basis). It reads `research` ONLY to
    assert that evidence is present; it never derives the enum value from that free text
    -- no regex, no substring scan, no .lower() keyword match anywhere in this function
    (D-01). Raises PendingResearch for a coverage id with no table entry yet."""
    if company_id not in ORG_TYPE_DECISIONS:
        raise PendingResearch(
            f"{company_id!r} has no ORG_TYPE_DECISIONS entry -- research has not been "
            "captured/evidenced yet for this coverage id."
        )
    decision = ORG_TYPE_DECISIONS[company_id]
    if not isinstance(research, dict) or "matched" not in research or "confidence" not in research:
        raise ValueError(
            f"{company_id!r}: research is missing matched/confidence -- cannot ground "
            "the decision table's basis"
        )
    if research["matched"] and not (research.get("data") or {}).get("lv_org_type"):
        raise ValueError(
            f"{company_id!r}: research is matched but carries no lv_org_type free text "
            "to ground the decision table's basis"
        )
    return decision


def coverage_state(record_properties):
    """D-03's three-state semantics, machine-readable: blank lv_org_type is
    never_attempted; "unknown" is attempted_unresolved; any other valid enum value is
    resolved. This is what makes COVER-01's "distinguishable from never attempted" bar an
    assertion rather than a description."""
    org_type = (record_properties or {}).get("lv_org_type")
    if not org_type:
        return "never_attempted"
    if org_type == "unknown":
        return "attempted_unresolved"
    return "resolved"


def build_coverage_patch(company_id, decision, now_iso):
    """Returns exactly lv_org_type, lv_org_type_verified_at, and (only for the D-03
    marker) lv_enrichment_review_reason. Raises ValueError naming the id and value when
    decision['org_type'] is not a VALID_ORG_TYPES member -- the out-of-vocabulary write
    must never reach the wire."""
    org_type = decision["org_type"]
    if org_type not in VALID_ORG_TYPES:
        raise ValueError(
            f"{company_id!r}: {org_type!r} is not a member of VALID_ORG_TYPES -- "
            "refusing to build a patch that would 400 the whole batch"
        )
    props = {
        "lv_org_type": org_type,
        "lv_org_type_verified_at": now_iso,
    }
    if org_type == "unknown":
        reason = UNENRICHABLE_REASONS.get(company_id)
        if not reason:
            raise ValueError(
                f"{company_id!r}: org_type is 'unknown' but UNENRICHABLE_REASONS has no "
                "entry -- D-03 requires a non-empty reason"
            )
        props["lv_enrichment_review_reason"] = reason
    assert FORBIDDEN_PROPS.isdisjoint(props), (
        f"{company_id!r}: build_coverage_patch produced a forbidden derived-field key"
    )
    return {"id": company_id, "properties": props}


# --- cost estimate + budget refusal (COVER-02) ---------------------------------------------

def estimate_phase48_cost(research_ids, written_ids, proof_executions=0) -> dict:
    """Phase-48-shaped estimate: research is a direct Anthropic call costing zero n8n
    executions; the n8n executions are exactly the D-09 recompute POSTs, one per written
    record, plus any disarmed proof-of-deploy execution declared up front."""
    return {
        "web_research_calls": len(research_ids),
        "n8n_executions": len(written_ids) + proof_executions,
        "n8n_budget_month": N8N_EXECUTION_BUDGET_MONTH,
        "lusha_credits": 0,
        "lusha_credits_note": (
            "D-01: offline mapping + at most one direct research call, no provider "
            "waterfall -- zero Lusha credits drawn."
        ),
        "anthropic_estimate_usd": round(len(research_ids) * ANTHROPIC_PER_RECORD_ESTIMATE_USD, 4),
    }


# --- two-key arm gate (own name, deliberately not ALLOW_VETO_REMEDIATION) -----------------

def coverage_writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_ENRICH_COVERAGE", "false").lower() == "true"
    return (not dry_run) and allow


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


# --- main -----------------------------------------------------------------------------

def _parse_ids_csv(raw: str) -> list:
    return [v.strip() for v in (raw or "").split(",") if v.strip()]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ids", default="",
                         help="Comma-separated coverage company ids (default: all 5).")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                         help="Print payloads only, no write (default; this plan has no "
                              "armed write leg regardless of this flag).")
    parser.add_argument("--no-dry-run", dest="dry_run", action="store_false",
                         help="Reserved for a future plan's armed write leg -- this plan "
                              "performs no writes regardless of this flag.")
    parser.add_argument("--population-out", default=None,
                         help="Path to write the live-derived population JSON.")
    return parser


def main(argv=None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    requested = _parse_ids_csv(args.ids) or list(COVERAGE_COMPANY_ID_ORDER)
    try:
        resolved_ids = resolve_coverage_ids(requested)
    except PinRefused as exc:
        print(f"REFUSED: {exc}")
        return 1

    if _has_credentials():
        population = derive_population()
        if args.population_out:
            Path(args.population_out).write_text(json.dumps(population, indent=2, default=str))
        reconciliation = reconcile_population(population)
        print(f"POPULATION: {json.dumps(population, indent=2, default=str)}")
        print(f"RECONCILE: {json.dumps(reconciliation, indent=2)}")
        if reconciliation["drift"]:
            print("DRIFT DETECTED -- live population diverges from the 5-id literal set. "
                  "Disclosed, not silently absorbed. Operator decision required.")
    else:
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set for live "
              "population re-derivation. 48-POPULATION.json was not produced.")

    now_iso = datetime.now(timezone.utc).isoformat()
    research_ids = []
    written_ids = []
    for company_id in resolved_ids:
        try:
            decision = decide_org_type(company_id, _load_captured_research(company_id))
        except PendingResearch as exc:
            print(f"PENDING RESEARCH: {exc}")
            research_ids.append(company_id)
            continue
        patch = build_coverage_patch(company_id, decision, now_iso)
        written_ids.append(company_id)
        print(f"DECISION[{company_id}]: {json.dumps(decision)}")
        print(f"PATCH[{company_id}]: {json.dumps(patch['properties'], indent=2)}")

    estimate = estimate_phase48_cost(research_ids, written_ids)
    print(f"COST ESTIMATE: {json.dumps(estimate, indent=2)}")
    try:
        refuse_if_over_budget(estimate, written_ids)
    except BudgetRefused as exc:
        print(f"REFUSED: {exc}")
        return 1

    print("DRY RUN complete -- no write performed. This plan carries no armed write leg; "
          "a later plan owns coverage_writes_allowed()'s consuming branch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
