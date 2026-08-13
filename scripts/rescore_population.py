#!/usr/bin/env python3
"""scripts/rescore_population.py

Phase 49 Plan 01 (RESCORE-01/RESCORE-02) -- the re-score driver for a rubric WEIGHT
change (D-01: this reuses the Phase 40 component-backfill mechanism -- compute_components /
build_updates / batch_update_companies -- never the n8n enrichment pipeline, which is the
veto branch's vehicle and untouched by a weight-only change).

Population: re-derived live, every invocation, via the same HAS_PROPERTY(lv_icp_fit_score)
search shape run_scoring_parity.py and simulate_rubric_weights.py already share
(select_scored_population()). D-03: the sample this driver may write to must equal that
live-derived set EXACTLY -- enforce_exact_population() (scripts/backfill_seed_company_scores.py)
refuses any subset or superset, and enforce_sample_cap() (same module, unchanged) is a second,
independent count check. Neither predicate is ever bypassed; a failed gate is a refusal, never
a truncation.

Window W1 (D-05): a direct HubSpot CRM v3 batch PATCH of the five *_score component
properties -- zero n8n executions, zero Anthropic calls, zero provider credits
(estimate_rescore_cost's weight branch). The arm is a two-key Python-side gate only
(DRY_RUN=false AND ALLOW_SCORE_BACKFILL=true); W1 does NOT arm any n8n execution allowlist
-- do not copy Phase 48's "both arming surfaces must be armed together" rule here, there is
no n8n allowlist anywhere in this window's write path (Pitfall 3, 49-RESEARCH.md).

Never writes lv_icp_fit_score, lv_icp_tier, lv_anti_icp_flag or lv_anti_icp_reason -- those
are derived by HubSpot's calculated property, WF1, and the n8n Decide Company Action node
respectively (project D-07); assert_payload_scope() enforces this on every payload this
driver builds by requiring an exact match against COMPONENT_PROPS.

The veto branch (a rubric change to a hard-veto predicate) is a documented, NOT-exercised-
by-this-driver alternative -- see scripts/remediate_veto_companies.py::post_webhook_event
and docs/OPERATOR-VETO-REFRESH.md. estimate_rescore_cost(branch="veto") documents its cost
shape but this driver's write legs only ever perform the weight branch.

`.env` is Read/Bash permission-blocked this session -- the operator invocation is:
    ALLOW_SCORE_BACKFILL=true DRY_RUN=false .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/rescore_population.py', run_name='__main__')"

Run --plan first (the default) and review the printed plan before arming.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*`/`scripts.*` imports resolve

import scripts.backfill_seed_company_scores as backfill  # noqa: E402
from scripts.backfill_seed_company_scores import (  # noqa: E402
    CANONICAL_INPUT_PROPS,
    COMPONENT_PROPS,
    BATCH_CHUNK_SIZE,
    EXPECTED_PORTAL_ID,
    build_updates,
    compute_components,
    enforce_exact_population,
    enforce_sample_cap,
    _chunked,
)
from src.hubspot_client import batch_update_companies, get_record, search_records  # noqa: E402

# D-08's measured recompute-lane figure (Phase 47.5, executions 11858-11861): 1 n8n
# execution per veto-branch POST, 0 provider/Anthropic calls. Documented for the veto
# branch's estimate_rescore_cost() shape; this driver never posts to that lane itself.
N8N_EXECUTION_BUDGET_MONTH = 2500


# --- gates (mirrors scripts/backfill_seed_company_scores.py's own three, unchanged
# shape) -----------------------------------------------------------------------------

def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _writes_allowed() -> bool:
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    allow = os.getenv("ALLOW_SCORE_BACKFILL", "false").lower() == "true"
    return (not dry_run) and allow


def _apply_max_records_default() -> None:
    """Defaults BACKFILL_MAX_RECORDS to backfill.HARD_CEILING_RECORDS (100) for this
    driver's own invocations when the operator has not set it -- so the 66-record live
    population is not refused by backfill.enforce_sample_cap's own DEFAULT_MAX_RECORDS of
    10, tuned for Phase 40's small proving sample. Uses os.environ.setdefault: if the
    operator has already set BACKFILL_MAX_RECORDS, that value is left untouched."""
    os.environ.setdefault("BACKFILL_MAX_RECORDS", str(backfill.HARD_CEILING_RECORDS))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- population -----------------------------------------------------------------------

def select_scored_population() -> list:
    """The single live population definition this driver ever uses -- the same
    HAS_PROPERTY(lv_icp_fit_score) search shape as run_scoring_parity.py's
    _select_sample_ids() and simulate_rubric_weights.py's _select_row_ids(), never a
    second definition (49-RESEARCH.md's "Don't Hand-Roll" table). limit=100 so the query
    does not silently truncate if the scored population grows past the current 66."""
    result = search_records(
        "companies",
        [{"propertyName": "lv_icp_fit_score", "operator": "HAS_PROPERTY"}],
        ["lv_icp_fit_score"],
        limit=100,
    )
    return sorted(r["id"] for r in result.get("results", []))


# --- cost / plan -------------------------------------------------------------------------

def estimate_rescore_cost(ids: list, branch: str = "weight") -> dict:
    """Every value is an int, derived from module constants -- no float arithmetic
    anywhere in this function (RESCORE-01 precision truth). branch="weight" (this
    driver's only exercised branch, D-01/D-05): n8n_executions/anthropic_calls/
    provider_credits are literal 0 -- compute_components()+batch_update_companies() never
    touch n8n or Anthropic. branch="veto" (documented, not exercised): n8n_executions
    equals the record count (D-08's measured 1-execution-per-recompute-POST figure),
    anthropic_calls/provider_credits stay 0 (the recompute lane carries no provider,
    research, judge, merge or normalize node)."""
    n_records = len(ids)
    hubspot_batch_calls = (n_records + BATCH_CHUNK_SIZE - 1) // BATCH_CHUNK_SIZE

    if branch == "veto":
        n8n_executions = n_records
    else:
        n8n_executions = 0

    return {
        "records": n_records,
        "hubspot_batch_calls": hubspot_batch_calls,
        "n8n_executions": n8n_executions,
        "anthropic_calls": 0,
        "provider_credits": 0,
        "n8n_budget_month": N8N_EXECUTION_BUDGET_MONTH,
        "branch": branch,
    }


def build_plan(ids: list) -> dict:
    """Assembles the --plan payload. The top-level key set is a cross-plan contract --
    plan 49-02's runbook verify parses this document by these literal key names -- so do
    not rename, add, or drop a key without updating that plan too."""
    _apply_max_records_default()
    n_records = len(ids)
    chunks = (n_records + BATCH_CHUNK_SIZE - 1) // BATCH_CHUNK_SIZE
    return {
        "ids": ids,
        "population_count": n_records,
        "derived_at": _now_iso(),
        "chunk_size": BATCH_CHUNK_SIZE,
        "chunks": chunks,
        "max_records": backfill._resolved_max_records(),
        "window": "W1",
        "arm_keys": ["DRY_RUN=false", "ALLOW_SCORE_BACKFILL=true"],
        "arms_n8n_allowlist": False,
        "cost": estimate_rescore_cost(ids, branch="weight"),
    }


# --- payload scope guard (T-49-02) ------------------------------------------------------

def assert_payload_scope(updates: list) -> None:
    """Raises ValueError unless every payload entry's properties key set is EXACTLY
    COMPONENT_PROPS -- stated positively as an equality (not FORBIDDEN_PROPS.isdisjoint,
    the shape remediate_veto_companies.py uses) so this also catches a *missing*
    component: a missing term blanks compute_components()' calculated sum entirely, per
    that function's own contract, which is why all five are always written together."""
    expected = set(COMPONENT_PROPS)
    for entry in updates:
        keys = set(entry.get("properties", {}).keys())
        if keys != expected:
            raise ValueError(
                f"payload entry for id={entry.get('id')!r} has properties key set "
                f"{sorted(keys)}, expected exactly {sorted(expected)}."
            )


# --- CLI ---------------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true",
                       help="Dry plan mode (default): re-derive the live scored population "
                            "and print a budget-bounded plan. No writes of any kind.")
    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    parser.parse_args(argv)  # --plan is the only mode this task wires; also the default.

    _apply_max_records_default()

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this driver.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    ids = select_scored_population()

    if not ids:
        print("REFUSED: live population read returned zero ids -- refusing to print a "
              "plan for an empty population rather than emitting a clean empty report "
              "(the false-green risk run_scoring_parity.py's assertions_executed == 0 "
              "guard exists to prevent). Check credentials/portal id and retry.")
        return 1

    plan = build_plan(ids)
    print(json.dumps(plan, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
