#!/usr/bin/env python3
"""scripts/enrichment_cost_ledger.py

Phase 22 Plan 01 Task 2 — TOKEN-USAGE HALF ONLY. Plan 03 expands this same module with
provider-credit diffing and the estimate comparison; the structure below (a small pure
extraction function, a thin live fetch, a `main()` dispatching on argparse subcommands)
is kept deliberately obvious so that expansion is additive, not a rewrite.

Read-only against the n8n Cloud Public API's executions endpoint. Three subcommands:

  list      GET a small page of the executions collection; print id, workflow name,
            status, start time — so an operator can find the canary's execution id
            without the n8n UI.
  extract   GET one execution with includeData=true; print node name, model, and the
            four Anthropic usage counters for each of the four pinned Anthropic nodes
            (Assumption A1 — the whole point of this task is observing whether these
            counters actually survive on this n8n Cloud instance's execution replay).
  capture   Same GET as extract, but writes an ALLOW-LISTED (never deny-listed) redacted
            subset of the payload to tests/fixtures/n8n/execution_rundata_usage.json —
            node names, model, the usage counters, run status, and nothing else. An
            execution's node data can carry request headers and full prompt bodies; a
            deny-list would leak whatever it failed to anticipate (T-22-02).

Reuses `_has_n8n()`/`_base_url()`/`_n8n_headers()`/`_get_live_workflows()` from
scripts/deploy_n8n_workflows.py rather than re-implementing auth or URL assembly — one
module owns how this repo talks to the n8n API (same idiom as
scripts/verify_live_lusha_urls.py). No PATCH/POST path to n8n exists here. Prints only
counts, node names, models and token counters — never a credential value, a full node
body, or a prompt.

Usage:
    python scripts/enrichment_cost_ledger.py list
    python scripts/enrichment_cost_ledger.py extract --execution-id 12345
    python scripts/enrichment_cost_ledger.py capture --execution-id 12345
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from deploy_n8n_workflows import _has_n8n, _base_url, _n8n_headers, _get_live_workflows  # noqa: E402

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "n8n" / "execution_rundata_usage.json"
ENRICHMENT_WORKFLOW_PATH = ROOT / "n8n" / "wf_enrichment_cloud.json"

# The four httpRequest nodes calling api.anthropic.com/v1/messages directly (company +
# contact lanes, research + judge) — pinned so a node rename can't leave this ledger
# silently reading nothing. tests/test_enrichment_cost_ledger.py asserts every one of
# these names exists in the committed cloud workflow JSON.
ANTHROPIC_NODE_NAMES = ("Claude Web Research", "Judge Call", "Contact Web Research", "Contact Judge Call")

USAGE_COUNTERS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def _get_execution(execution_id: str) -> dict:
    import requests
    r = requests.get(
        f"{_base_url()}/api/v1/executions/{execution_id}",
        params={"includeData": "true"},
        headers=_n8n_headers(), timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _list_executions(limit: int = 20) -> list:
    import requests
    r = requests.get(
        f"{_base_url()}/api/v1/executions",
        params={"limit": limit},
        headers=_n8n_headers(), timeout=30,
    )
    r.raise_for_status()
    return (r.json() or {}).get("data", [])


def _node_output_items(run: dict) -> list:
    """A single NodeRun's output items (`data.main[0]`) — defensive against any shape
    mismatch: never raises, returns [] on anything unexpected."""
    if not isinstance(run, dict):
        return []
    data = run.get("data")
    if not isinstance(data, dict):
        return []
    main = data.get("main")
    if not isinstance(main, list) or not main:
        return []
    branch = main[0]
    return branch if isinstance(branch, list) else []


def _first_node_output_json(run: dict):
    for item in _node_output_items(run):
        candidate = item.get("json") if isinstance(item, dict) else None
        if isinstance(candidate, dict):
            return candidate
    return None


def extract_token_usage(execution: dict) -> dict:
    """Pure over an already-fetched execution dict. Never raises — any shape mismatch
    yields {"available": False, "reason": ..., "rows": []}. A node that ran but carried
    no usage object is reported usage_available=False ("usage-unavailable"); a node that
    never ran is reported status="not_run" — the two are different findings, never
    conflated as "zero tokens" (must_haves behaviour table)."""
    data = execution.get("data")
    if not isinstance(data, dict):
        return {"available": False, "reason": "execution payload has no 'data'", "rows": []}
    result_data = data.get("resultData")
    if not isinstance(result_data, dict):
        return {"available": False, "reason": "no resultData in execution payload", "rows": []}
    run_data = result_data.get("runData")
    if not isinstance(run_data, dict):
        return {"available": False, "reason": "runData is not a mapping", "rows": []}

    # A node key genuinely ABSENT from runData (or present with an empty run list) is a
    # normal, expected shape — that node simply didn't run. A node key PRESENT with a
    # non-list value is a malformed/truncated payload, not a legitimate "didn't run"
    # state — fail the whole extraction closed rather than guess at a partial result.
    for node_name in ANTHROPIC_NODE_NAMES:
        if node_name in run_data and not isinstance(run_data[node_name], list):
            return {
                "available": False,
                "reason": f"runData[{node_name!r}] run items are not a list",
                "rows": [],
            }

    rows = []
    for node_name in ANTHROPIC_NODE_NAMES:
        runs = run_data.get(node_name)
        if not runs:
            rows.append({"node": node_name, "status": "not_run"})
            continue
        if not isinstance(runs[0], dict):
            rows.append({"node": node_name, "status": "ran", "usage_available": False})
            continue
        body = _first_node_output_json(runs[0])
        usage = body.get("usage") if isinstance(body, dict) else None
        if not isinstance(usage, dict):
            rows.append({"node": node_name, "status": "ran", "usage_available": False,
                         "model": body.get("model") if isinstance(body, dict) else None})
            continue
        rows.append({
            "node": node_name,
            "status": "ran",
            "usage_available": True,
            "model": body.get("model"),
            **{counter: usage.get(counter) for counter in USAGE_COUNTERS},
        })
    return {"available": True, "reason": None, "rows": rows}


def build_redacted_fixture(execution: dict) -> dict:
    """Allow-list ONLY (T-22-02, never a deny-list): keeps node name, model, the usage
    counters, and run status for each Anthropic node — nothing else. The result is itself
    execution-shaped (same data.resultData.runData nesting) so it round-trips straight
    back through extract_token_usage()."""
    data = execution.get("data") if isinstance(execution.get("data"), dict) else {}
    result_data = data.get("resultData") if isinstance(data.get("resultData"), dict) else {}
    run_data = result_data.get("runData") if isinstance(result_data.get("runData"), dict) else {}

    redacted_run_data = {}
    for node_name in ANTHROPIC_NODE_NAMES:
        runs = run_data.get(node_name)
        if not isinstance(runs, list) or not runs or not isinstance(runs[0], dict):
            continue
        body = _first_node_output_json(runs[0]) or {}
        redacted_item = {"model": body.get("model")}
        usage = body.get("usage")
        if isinstance(usage, dict):
            redacted_item["usage"] = {k: usage.get(k) for k in USAGE_COUNTERS if k in usage}
        redacted_run_data[node_name] = [{
            "executionStatus": runs[0].get("executionStatus"),
            "data": {"main": [[{"json": redacted_item}]]},
        }]

    return {"data": {"resultData": {"runData": redacted_run_data}}}


def _write_fixture(fixture: dict, path: Path = FIXTURE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    return path


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", default="list", choices=["list", "extract", "capture"])
    parser.add_argument("--execution-id", default=None)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)

    if not _has_n8n():
        print("skipped (no n8n creds): the n8n URL and API key must both be set to run this ledger.")
        return 0

    if args.mode == "list":
        executions = _list_executions(args.limit)
        try:
            workflows_by_id = {w.get("id"): w.get("name") for w in _get_live_workflows()}
        except Exception:
            workflows_by_id = {}
        for ex in executions:
            workflow_id = ex.get("workflowId")
            name = (ex.get("workflowData") or {}).get("name") or workflows_by_id.get(workflow_id, "unknown")
            status = ex.get("status") or ("finished" if ex.get("finished") else "running")
            print(f"id={ex.get('id')} workflow={name!r} status={status} started={ex.get('startedAt')}")
        if args.json:
            print(json.dumps(executions, default=str))
        return 0

    if not args.execution_id:
        print("REFUSED: extract/capture mode requires --execution-id.")
        return 1

    execution = _get_execution(args.execution_id)

    if args.mode == "extract":
        usage = extract_token_usage(execution)
        if not usage["available"]:
            print(f"UNAVAILABLE: {usage['reason']}")
            return 1
        for row in usage["rows"]:
            if row["status"] == "not_run":
                print(f"node={row['node']!r} status=not_run")
            elif not row.get("usage_available"):
                print(f"node={row['node']!r} status=ran usage_available=false model={row.get('model')!r}")
            else:
                counters = " ".join(f"{c}={row.get(c)}" for c in USAGE_COUNTERS)
                print(f"node={row['node']!r} status=ran model={row['model']!r} {counters}")
        if args.json:
            print(json.dumps(usage, default=str))
        return 0

    # capture
    fixture = build_redacted_fixture(execution)
    path = _write_fixture(fixture)
    print(f"wrote {path}")
    if args.json:
        print(json.dumps(fixture, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
