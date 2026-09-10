#!/usr/bin/env python3
"""scripts/judge_reason_distribution.py

Quick task 260911-anv — a read-only judge-trigger distribution reader over n8n
executions that already happened. It produces no new n8n execution, makes no HubSpot
call, no Anthropic call, and writes nothing anywhere except its own stdout.

Reuses `_list_executions`, `_get_execution` and `_node_output_items` from
scripts/enrichment_cost_ledger.py exactly as scripts/replay_judge_models.py does — same
sys.path bootstrap, same module-level load_dotenv() call (.env is not directly readable,
so credentials must come from that call). Every n8n access this module makes is a GET
through those two readers and nothing else; the enrichment workflow's live id, used to
filter the executions list, is read from scripts/bounce_n8n_workflows.py's existing
committed-file -> live-id map (a local constant, not a third n8n reader).

This reads the "Judge Gate" (companies) and "Contact Judge Gate" (contacts) node output
on purpose, because scripts/replay_judge_models.py reads "Build Judge Request" /
"Build Contact Judge Request" and DROPS every row whose judge_request_body is null —
which is the whole non-escalating population. That script has escalated rows but no
denominator; this one has both, because Judge Gate stamps judge_reasons (even an empty
array) on every row it passes downstream, escalating or not (see the quick task's
PLAN.md Task 1 evidence).

Under n8n's v1 execution order a node can run more than once in a single execution
(CLAUDE.md §13.0.3) — every run of both node names is folded, not just the first.

Usage:
    python scripts/judge_reason_distribution.py --limit 100
    python scripts/judge_reason_distribution.py --execution-ids 12354,12355,12356
    python scripts/judge_reason_distribution.py --limit 100 --json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from enrichment_cost_ledger import _get_execution, _list_executions, _node_output_items  # noqa: E402
from deploy_n8n_workflows import _has_n8n  # noqa: E402
from bounce_n8n_workflows import WORKFLOWS as _BOUNCE_WORKFLOWS  # noqa: E402

COMPANIES_NODE = "Judge Gate"
CONTACTS_NODE = "Contact Judge Gate"

# The live workflow id for n8n/wf_enrichment_cloud.json, reused from the deploy tooling's
# own committed-file -> live-id map rather than a second hardcoded copy or a third n8n
# reader (scripts/bounce_n8n_workflows.py's WORKFLOWS dict has no import-time side
# effect — see its module body).
ENRICHMENT_WORKFLOW_ID = _BOUNCE_WORKFLOWS["n8n/wf_enrichment_cloud.json"]

DEFAULT_LIST_LIMIT = 100

_LANES = (("companies", COMPANIES_NODE), ("contacts", CONTACTS_NODE))
_COUNT_KEYS = ("rows_through_gate", "rows_research_matched", "rows_with_reasons", "rows_capped")


def _empty_counts() -> dict:
    return {
        "rows_through_gate": 0,
        "rows_research_matched": 0,
        "rows_with_reasons": 0,
        "rows_capped": 0,
        "by_reason": {},
        "by_reason_set": {},
    }


def _add_counts(total: dict, part: dict) -> None:
    for key in _COUNT_KEYS:
        total[key] += part[key]
    for reason, count in part["by_reason"].items():
        total["by_reason"][reason] = total["by_reason"].get(reason, 0) + count
    for reason_set, count in part["by_reason_set"].items():
        total["by_reason_set"][reason_set] = total["by_reason_set"].get(reason_set, 0) + count


def summarize(run_data) -> dict:
    """Fold one execution's runData into counts only — no row payload, no identity
    field, no header anywhere in the return value. Never raises: a missing node, a run
    without a usable `data.main` branch, a non-dict item, or an absent `judge_reasons`
    key each contribute zero rather than an exception (`_node_output_items` already
    guards the run-shape cases; this function guards the rest).
    """
    result = {"companies": _empty_counts(), "contacts": _empty_counts()}

    if isinstance(run_data, dict):
        for lane, node_name in _LANES:
            runs = run_data.get(node_name)
            if not isinstance(runs, list):
                continue
            counts = result[lane]
            for run in runs:  # every run folded, not just the first (v1 can fire twice)
                for item in _node_output_items(run):
                    payload = item.get("json") if isinstance(item, dict) else None
                    if not isinstance(payload, dict):
                        continue
                    counts["rows_through_gate"] += 1

                    rc = payload.get("research_candidate")
                    if isinstance(rc, dict) and rc.get("matched") is True:
                        counts["rows_research_matched"] += 1

                    reasons = payload.get("judge_reasons")
                    if isinstance(reasons, list) and len(reasons) > 0:
                        counts["rows_with_reasons"] += 1
                        for reason in reasons:
                            reason = str(reason)
                            counts["by_reason"][reason] = counts["by_reason"].get(reason, 0) + 1
                        reason_set = ",".join(sorted(str(r) for r in reasons))
                        counts["by_reason_set"][reason_set] = counts["by_reason_set"].get(reason_set, 0) + 1

                    if payload.get("judge_capped") is True:
                        counts["rows_capped"] += 1

    total = _empty_counts()
    _add_counts(total, result["companies"])
    _add_counts(total, result["contacts"])
    result["total"] = total
    return result


def collect(execution_ids=None, limit=DEFAULT_LIST_LIMIT) -> dict:
    """Resolve ids (an explicit list, else `_list_executions(limit)` filtered to the
    enrichment workflow's live id) and fold `summarize` over each. An execution whose GET
    raises is skipped rather than sinking the whole walk — exactly as
    scripts/replay_judge_models.py's `extract_corpus` already does."""
    if execution_ids is None:
        listed = _list_executions(limit=limit)
        execution_ids = [
            e.get("id") for e in listed
            if isinstance(e, dict) and e.get("id") is not None
            and e.get("workflowId") == ENRICHMENT_WORKFLOW_ID
        ]

    merged = {"companies": _empty_counts(), "contacts": _empty_counts(), "total": _empty_counts()}
    executions_scanned = 0
    execution_ids_used = []

    for execution_id in execution_ids:
        try:
            execution = _get_execution(execution_id)
        except Exception:  # noqa: BLE001 — one bad execution must not sink the walk
            continue
        executions_scanned += 1

        data = execution.get("data") if isinstance(execution, dict) else None
        result_data = data.get("resultData") if isinstance(data, dict) else None
        run_data = result_data.get("runData") if isinstance(result_data, dict) else None
        if not isinstance(run_data, dict):
            continue

        part = summarize(run_data)
        _add_counts(merged["companies"], part["companies"])
        _add_counts(merged["contacts"], part["contacts"])
        _add_counts(merged["total"], part["total"])
        execution_ids_used.append(execution_id)

    merged["executions_scanned"] = executions_scanned
    merged["execution_ids_used"] = execution_ids_used
    return merged


def _share(numerator, denominator):
    if not denominator:
        return None
    return numerator / denominator


def _print_lane(label, counts) -> None:
    matched = counts["rows_research_matched"]
    print(f"  {label}:")
    print(f"    rows_through_gate: {counts['rows_through_gate']}")
    print(f"    rows_research_matched: {matched}")
    print(f"    rows_with_reasons: {counts['rows_with_reasons']}")
    print(f"    rows_capped: {counts['rows_capped']}")
    overall_share = _share(counts["rows_with_reasons"], matched)
    print(f"    rows_with_reasons / rows_research_matched: "
          f"{'n/a (no matched rows)' if overall_share is None else round(overall_share, 3)}")
    print("    by_reason (share of rows_research_matched):")
    for reason, count in sorted(counts["by_reason"].items()):
        share = _share(count, matched)
        share_str = "n/a" if share is None else round(share, 3)
        print(f"      {reason}: {count}  ({share_str})")
    print("    by_reason_set:")
    for reason_set, count in sorted(counts["by_reason_set"].items()):
        print(f"      [{reason_set}]: {count}")


def print_report(result: dict) -> None:
    print(f"executions scanned: {result.get('executions_scanned', 'n/a')}")
    used = result.get("execution_ids_used")
    if used is not None:
        print(f"execution ids used: {used}")
    for label, key in (("companies", "companies"), ("contacts", "contacts"), ("total", "total")):
        _print_lane(label, result[key])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execution-ids", default=None,
                         help="Comma-separated explicit execution ids (skips the list-and-filter GET).")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIST_LIMIT,
                         help="Max executions to list when --execution-ids is not given.")
    parser.add_argument("--json", action="store_true", default=False)
    args = parser.parse_args(argv)

    if not _has_n8n():
        print("REFUSED: N8N_URL and N8N_API_KEY must both be set. No n8n call made.")
        return 1

    execution_ids = None
    if args.execution_ids:
        execution_ids = [x.strip() for x in args.execution_ids.split(",") if x.strip()]

    result = collect(execution_ids=execution_ids, limit=args.limit)
    print_report(result)
    if args.json:
        print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
