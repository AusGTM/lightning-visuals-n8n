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

Never writes lv_icp_fit_score, lv_icp_tier_derived, lv_anti_icp_flag or lv_anti_icp_reason -- those
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
import time
from collections import Counter
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

POPULATION_SEARCH_LIMIT = 100


def select_scored_population() -> list:
    """The single live population definition this driver ever uses -- the same
    HAS_PROPERTY(lv_icp_fit_score) search shape as run_scoring_parity.py's
    _select_sample_ids() and simulate_rubric_weights.py's _select_row_ids(), never a
    second definition (49-RESEARCH.md's "Don't Hand-Roll" table).

    A page limit alone does NOT prevent silent truncation -- it only moves where the
    truncation happens. Both reads of the exact-set gate call this function, so a
    truncated page would make them agree on the same wrong set and the gate would pass
    while operating on a subset. Compare the reported total against what we actually got
    and REFUSE on any shortfall, the same refuse-rather-than-truncate contract
    enforce_exact_population() and enforce_sample_cap() hold."""
    result = search_records(
        "companies",
        [{"propertyName": "lv_icp_fit_score", "operator": "HAS_PROPERTY"}],
        ["lv_icp_fit_score"],
        limit=POPULATION_SEARCH_LIMIT,
    )
    ids = sorted(r["id"] for r in result.get("results", []))
    total = result.get("total")
    if total is not None and total > len(ids):
        raise RuntimeError(
            f"REFUSED: the scored population is {total} records but this search returned "
            f"only {len(ids)} (page limit {POPULATION_SEARCH_LIMIT}). Operating on a "
            "truncated set would let the exact-set gate agree with itself on a subset. "
            "Add pagination to select_scored_population() before re-running."
        )
    return ids


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


# --- population re-confirm (D-03: never reuse a cached id list across the arm-time gate
# and the write; re-derive live, immediately before every write leg) -----------------------

def _derive_and_confirm_population():
    """Derives the live scored population, then re-derives it a SECOND time immediately
    before any write path is allowed to proceed, and refuses (returns None, prints a
    refusal) unless the two derivations are exactly equal (enforce_exact_population).
    Guards against a race between "what we planned to write" and "what is live right
    now" within a single invocation -- population selection is a read, so this costs
    one extra search_records call, never a write."""
    ids = select_scored_population()
    if not ids:
        print("REFUSED: live population read returned zero ids -- refusing rather than "
              "acting on an empty population. Check credentials/portal id and retry.")
        return None
    confirm_ids = select_scored_population()
    if not enforce_exact_population(ids, confirm_ids):
        print("REFUSED: the live scored population changed between derivation and "
              "write -- refusing rather than acting on a stale sample. Re-run the driver.")
        return None
    if not enforce_sample_cap(ids):
        print(f"REFUSED: resolved population has {len(ids)} records, exceeding the "
              f"backfill cap ({backfill._resolved_max_records()}). No API call made.")
        return None
    return ids


def _fetch_records(ids: list, props: list) -> list:
    return [{"id": i, "properties": get_record("companies", i, props)["properties"]} for i in ids]


# --- canary selection (D-04) ---------------------------------------------------------------

def select_canary(records: list) -> str:
    """records: [{"id": ..., "properties": {canonical inputs + currently stored
    COMPONENT_PROPS}}], already sorted by id (callers pass ids from select_scored_population,
    which sorts). Rule, never a hard-coded id: the first id whose lv_org_type reads
    individual_club_team (the org type whose weight moved 5 -> 15 under Phase 46, so its
    components are guaranteed to change). Falling back to the first id whose freshly
    computed components differ from what is currently stored, if no individual_club_team
    record exists. Last resort (neither condition matches any record): the first record in
    sorted order, so a canary is always chosen when records is non-empty."""
    for record in records:
        if record["properties"].get("lv_org_type") == "individual_club_team":
            return record["id"]
    for record in records:
        computed = compute_components(record["properties"])
        stored = {k: record["properties"].get(k) for k in COMPONENT_PROPS}
        if any(str(computed[k]) != str(stored.get(k)) for k in COMPONENT_PROPS):
            return record["id"]
    return records[0]["id"]


# --- settle (D-04: poll until two consecutive reads agree, never a fixed sleep;
# mirrors backfill_seed_company_scores.py's own _settle(), but a generous 300s default,
# not the single-record 11s figure measured in Phase 40-07 -- a simultaneous multi-record
# batch firing the calculated-property chain has never been timed at this scale,
# 49-RESEARCH.md assumption A2) -----------------------------------------------------------

def _settle_one(company_id: str, prop: str, timeout: float, interval: float):
    start = time.monotonic()
    previous = None
    first_read = True
    while True:
        record = get_record("companies", company_id, [prop])
        current = record.get("properties", {}).get(prop)
        elapsed = time.monotonic() - start
        if not first_read and current == previous:
            print(f"  {company_id}: {prop}={current!r} (settled after {elapsed:.1f}s)")
            return current
        first_read = False
        previous = current
        if elapsed >= timeout:
            print(f"  {company_id}: {prop}={current!r} (timed out after {elapsed:.1f}s)")
            return current
        time.sleep(interval)


def settle_population(ids: list, prop: str, timeout: float = 300, interval: float = 5) -> dict:
    """Polls prop for each id until it stops changing across two consecutive reads, or
    timeout elapses. Prints a per-record settled/timed-out line; asserts nothing on the
    values itself -- the parity sweep (scripts/run_scoring_parity.py) is what checks
    correctness. Returns {id: final_value}."""
    return {company_id: _settle_one(company_id, prop, timeout=timeout, interval=interval)
            for company_id in ids}


# --- write legs (T-49-01: both arm keys required; disarmed builds+prints, never calls
# batch_update_companies at all) -------------------------------------------------------------

def run_canary() -> int:
    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this driver.")
        return 0
    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    ids = _derive_and_confirm_population()
    if ids is None:
        return 1

    candidates = _fetch_records(ids, CANONICAL_INPUT_PROPS + COMPONENT_PROPS)
    canary_id = select_canary(candidates)
    canary_record = next(r for r in candidates if r["id"] == canary_id)
    components = compute_components(canary_record["properties"])
    update = [{"id": canary_id, "properties": components}]
    assert_payload_scope(update)

    print(json.dumps({"canary_id": canary_id, "components": components}, indent=2))

    armed = _writes_allowed()
    if not armed:
        print("DISARMED -- no write performed. Set DRY_RUN=false and "
              "ALLOW_SCORE_BACKFILL=true to arm.")
        return 0

    batch_update_companies(update, dry_run=False)
    print(f"canary written -- settling {canary_id} (up to 300s)...")
    fit_score = settle_population([canary_id], "lv_icp_fit_score", timeout=300)
    tier = settle_population([canary_id], "lv_icp_tier_derived", timeout=300)
    print(json.dumps({"canary_id": canary_id, "lv_icp_fit_score": fit_score.get(canary_id),
                       "lv_icp_tier_derived": tier.get(canary_id)}, indent=2))
    return 0


def run_execute(already_written: list) -> int:
    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this driver.")
        return 0
    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    ids = _derive_and_confirm_population()
    if ids is None:
        return 1

    already_written_set = set(already_written or [])
    to_write_ids = [i for i in ids if i not in already_written_set]

    if not to_write_ids:
        print("nothing to write -- every derived id is already written.")
        return 0

    records = _fetch_records(to_write_ids, CANONICAL_INPUT_PROPS)
    updates = build_updates(records)

    armed = _writes_allowed()
    for chunk in _chunked(updates, BATCH_CHUNK_SIZE):
        assert_payload_scope(chunk)
        print(json.dumps({"chunk_size": len(chunk), "ids": [u["id"] for u in chunk]}, indent=2))
        if armed:
            batch_update_companies(chunk, dry_run=False)

    if not armed:
        print("DISARMED -- no write performed. Set DRY_RUN=false and "
              "ALLOW_SCORE_BACKFILL=true to arm.")
        return 0

    print(f"armed run complete -- {len(updates)} companies written. Settling (up to 300s each)...")
    written_ids = [u["id"] for u in updates]
    settle_population(written_ids, "lv_icp_fit_score", timeout=300)
    settle_population(written_ids, "lv_icp_tier_derived", timeout=300)
    return 0


# --- --snapshot census mode (RESCORE-03's P2/P3 report points, D-10) -----------------------

# The seven per-record properties a census entry carries (id is the record id itself, not
# a fetched property).
SNAPSHOT_RECORD_PROPS = [
    "name", "lv_icp_tier_derived", "lv_icp_fit_score", "lv_org_type",
    "lv_anti_icp_flag", "lv_anti_icp_reason",
]

# Fixed, deterministic tier-key iteration order so two snapshots of the same data render
# byte-identically (a residual/unexpected tier value sorts after these, alphabetically).
TIER_ORDER = ["A", "B", "C", "D", "Unscored", "Needs Review"]

# A blank/None lv_icp_tier is counted under this literal key rather than dropped -- a
# blank must never silently vanish from the distribution.
BLANK_TIER_KEY = "Unscored-or-blank"


def build_snapshot(ids: list) -> dict:
    records = []
    for company_id in sorted(ids):
        props = get_record("companies", company_id, SNAPSHOT_RECORD_PROPS)["properties"]
        records.append({
            "id": company_id,
            "name": props.get("name"),
            "lv_icp_tier": props.get("lv_icp_tier_derived"),
            "lv_icp_fit_score": props.get("lv_icp_fit_score"),
            "lv_org_type": props.get("lv_org_type"),
            "lv_anti_icp_flag": props.get("lv_anti_icp_flag"),
            "lv_anti_icp_reason": props.get("lv_anti_icp_reason"),
        })

    counts = Counter(
        (r["lv_icp_tier"] if r["lv_icp_tier"] is not None else BLANK_TIER_KEY) for r in records
    )
    tier_distribution = {}
    for tier in TIER_ORDER:
        if tier in counts:
            tier_distribution[tier] = counts.pop(tier)
    for tier in sorted(counts.keys(), key=str):
        tier_distribution[tier] = counts[tier]

    return {
        "derived_at": _now_iso(),
        "population_count": len(records),
        "tier_distribution": tier_distribution,
        "records": records,
    }


def run_snapshot(out_path=None) -> int:
    """Never consults _writes_allowed() and has no write path at all -- a HubSpot read
    costs nothing against the 2,500/month n8n allowance (it makes zero n8n calls), which
    is why D-10 can afford three of these across the phase."""
    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this driver.")
        return 0
    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    ids = select_scored_population()
    if not ids:
        print("REFUSED: live population read returned zero ids -- refusing to emit a "
              "clean empty census (the false-green risk run_scoring_parity.py's "
              "assertions_executed == 0 guard exists to prevent). Check "
              "credentials/portal id and retry.")
        return 1

    snapshot = build_snapshot(ids)
    text = json.dumps(snapshot, indent=2, default=str)
    if out_path:
        Path(out_path).write_text(text + "\n")
        print(f"snapshot written to {out_path} ({snapshot['population_count']} records).")
    else:
        print(text)
    return 0


def run_plan() -> int:
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


# --- CLI ---------------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true",
                       help="Dry plan mode (default): re-derive the live scored population "
                            "and print a budget-bounded plan. No writes of any kind.")
    mode.add_argument("--canary", action="store_true",
                       help="Write exactly one record, chosen by rule, and settle it -- "
                            "confirm before releasing --execute for the remainder. "
                            "Requires DRY_RUN=false and ALLOW_SCORE_BACKFILL=true to "
                            "actually write; disarmed, prints what would be written.")
    mode.add_argument("--execute", action="store_true",
                       help="Write the remainder of the live-derived population (minus "
                            "any --already-written ids) and settle. Requires DRY_RUN=false "
                            "and ALLOW_SCORE_BACKFILL=true to actually write; disarmed, "
                            "prints what would be written.")
    mode.add_argument("--snapshot", action="store_true",
                       help="Dated JSON census of the live scored population (id, name, "
                            "tier, score, org type, veto flag/reason) plus a tier-"
                            "distribution roll-up. Read-only -- never writes, regardless "
                            "of arm state.")
    parser.add_argument("--already-written", action="append", default=[], dest="already_written",
                         help="Company id already written by an earlier --canary step "
                              "(repeatable); excluded from --execute's write set.")
    parser.add_argument("--out", default=None,
                         help="Path to write --snapshot's census JSON to. Defaults to stdout.")
    return parser


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _apply_max_records_default()

    if args.canary:
        return run_canary()
    if args.execute:
        return run_execute(args.already_written)
    if args.snapshot:
        return run_snapshot(args.out)
    return run_plan()  # --plan is the default when no mode flag is given.


if __name__ == "__main__":
    sys.exit(main())
