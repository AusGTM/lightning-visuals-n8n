#!/usr/bin/env python3
"""scripts/freeze_execution_rundata.py

Phase 73 Plan 01, Task 1 (D-73-13). A read-only CLI that GETs one or more n8n
executions (via `includeData=true`) and writes a redacted, committable fixture under
`tests/n8n/fixtures/frozen/` — the frozen proof `test_run_report_enrich_account.py`
drives.

GET only. No PATCH, no POST, no deploy, no arm — this script cannot write to n8n or
HubSpot even by accident; `executions_client` (reused, never reimplemented per that
module's own docstring) exposes no write verb at all.

Credentials: `N8N_URL`/`N8N_API_KEY` from the repo's own `.env`, loaded here via
`python-dotenv` — the same direct `load_dotenv()` pattern
`scripts/apply_fit_score_formula.py`/`scripts/judge_reason_distribution.py`/
`scripts/replay_judge_models.py` already use (not the `-c` wrapper form some other
read-only n8n scripts use; this one needs to run unattended, so it loads its own
environment rather than relying on the caller having sourced it). Never prints,
logs, or writes a credential value anywhere.

Redaction (T-73-01-01, repo memory `n8n-rundata-carries-webhook-secret`): every
Webhook Trigger runData item's `headers` object is REPLACED WHOLESALE with a fixed
placeholder string before anything is written — never a key-by-key scrub, which is
easy to under-cover. The caller's IP and the shared webhook secret both live inside
that one object.

Two output shapes:
  - Default: one full-runData fixture per execution id, `exec_<id>.runData.json`,
    matching the shape `tests/n8n/fixtures/frozen/exec_12354.runData.json` already
    established (execution_id/status/mode/workflow_id/workflow_name/
    workflow_version_id/started_at/stopped_at/settings/graph/runData/redaction).
  - `--nodes NAME [NAME ...]` + `--combine PATH`: an EXCERPT across every named
    execution id, restricted to the named nodes only, merged into one file keyed by
    execution id — for a multi-execution run (a chunked dispatch spans many
    executions under one run_id) where committing every execution's FULL runData
    would be disproportionate to what the fixture needs to prove.

Usage:
    .venv/bin/python scripts/freeze_execution_rundata.py 12434 12449
    .venv/bin/python scripts/freeze_execution_rundata.py 12432 12433 ... 12449 \\
        --nodes "Decide Company Action" "Build Response" \\
        --combine tests/n8n/fixtures/frozen/run_6891d018-decide-and-response.excerpt.json \\
        --run-id 6891d018e84f4d869eb8080292dac6c5
"""
import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "operator-claude-plugin" / "scripts"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import os  # noqa: E402

import executions_client  # noqa: E402

REDACTED_PLACEHOLDER = (
    "<redacted — see tests/n8n/fixtures/frozen/README.md 'Redaction rule'>"
)
REDACTION_NOTE = (
    "the whole `headers` object on every Webhook Trigger runData item was replaced "
    "with a fixed placeholder before this fixture was committed (T-73-01-01, repo "
    "memory n8n-rundata-carries-webhook-secret) — never a key-by-key scrub."
)


def _load_config() -> dict:
    return {
        "n8n_url": os.environ.get("N8N_URL"),
        "n8n_api_key": os.environ.get("N8N_API_KEY"),
    }


def _redact_headers(run_data: dict) -> dict:
    """Deep-copies `run_data` and replaces every item's `json.headers` object
    wholesale. Never mutates the caller's dict."""
    redacted = copy.deepcopy(run_data) if isinstance(run_data, dict) else {}
    for _node_name, runs in redacted.items():
        if not isinstance(runs, list):
            continue
        for run in runs:
            if not isinstance(run, dict):
                continue
            main = (run.get("data") or {}).get("main")
            if not isinstance(main, list):
                continue
            for branch in main:
                if not isinstance(branch, list):
                    continue
                for item in branch:
                    if isinstance(item, dict) and isinstance(item.get("json"), dict):
                        if "headers" in item["json"]:
                            item["json"]["headers"] = REDACTED_PLACEHOLDER
    return redacted


def _run_data_of(execution: dict) -> dict:
    data = execution.get("data") if isinstance(execution.get("data"), dict) else {}
    result_data = data.get("resultData") if isinstance(data.get("resultData"), dict) else {}
    run_data = result_data.get("runData")
    return run_data if isinstance(run_data, dict) else {}


def build_full_fixture(execution: dict) -> dict:
    """The established shape (see `tests/n8n/fixtures/frozen/exec_12354.runData.json`).
    `workflowData` itself is dropped — only its name/settings/node-count survive,
    matching every prior fixture's own convention of never committing the full graph
    a second time."""
    workflow_data = execution.get("workflowData") if isinstance(execution.get("workflowData"), dict) else {}
    return {
        "execution_id": execution.get("id"),
        "status": execution.get("status"),
        "mode": execution.get("mode"),
        "workflow_id": execution.get("workflowId"),
        "workflow_name": workflow_data.get("name"),
        "workflow_version_id": execution.get("workflowVersionId"),
        "started_at": execution.get("startedAt"),
        "stopped_at": execution.get("stoppedAt"),
        "settings": workflow_data.get("settings") or {},
        "graph": {
            "node_count": len(workflow_data.get("nodes") or []),
            "note": (
                "workflowData dropped; the live graph at freeze time carried this "
                "many nodes under this workflow id. This fixture is READ for its "
                "runData, never walked, so no committed graph copy is needed beside "
                "it."
            ),
        },
        "runData": _redact_headers(_run_data_of(execution)),
        "redaction": REDACTION_NOTE,
    }


def build_excerpt(execution: dict, node_names: list) -> dict:
    """Only the named nodes' runData, redacted the same way. Used for the
    `--combine` multi-execution mode — a chunked dispatch's run_id spans many
    executions, and committing every one's FULL runData would dwarf what the fixture
    exists to prove."""
    run_data = _redact_headers(_run_data_of(execution))
    return {
        "execution_id": execution.get("id"),
        "status": execution.get("status"),
        "runData": {name: run_data[name] for name in node_names if name in run_data},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("execution_ids", nargs="+", type=int)
    parser.add_argument(
        "--out-dir", default="tests/n8n/fixtures/frozen",
        help="Directory for the default (one-file-per-execution) output mode.",
    )
    parser.add_argument(
        "--nodes", nargs="+", default=None,
        help="Restrict output to these node names (excerpt mode).",
    )
    parser.add_argument(
        "--combine", default=None,
        help="Write one combined excerpt file (requires --nodes) instead of "
             "one file per execution id.",
    )
    parser.add_argument(
        "--run-id", default=None,
        help="Recorded in the combined excerpt's own header, for the reader's benefit only.",
    )
    args = parser.parse_args()

    config = _load_config()
    if not config["n8n_url"] or not config["n8n_api_key"]:
        print(
            "N8N_URL / N8N_API_KEY are not set in the environment — cannot freeze "
            "live executions. Nothing was fetched.",
            file=sys.stderr,
        )
        return 2

    if args.combine:
        if not args.nodes:
            print("--combine requires --nodes.", file=sys.stderr)
            return 2
        combined = {
            "run_id": args.run_id,
            "redaction": REDACTION_NOTE,
            "nodes": list(args.nodes),
            "executions": {},
        }
        for execution_id in args.execution_ids:
            execution = executions_client.get_execution(config, execution_id)
            combined["executions"][str(execution_id)] = build_excerpt(execution, args.nodes)
        out_path = ROOT / args.combine
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(combined, indent=2, sort_keys=True) + "\n")
        print(f"wrote {out_path}")
        return 0

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for execution_id in args.execution_ids:
        execution = executions_client.get_execution(config, execution_id)
        if args.nodes:
            fixture = build_excerpt(execution, args.nodes)
        else:
            fixture = build_full_fixture(execution)
        out_path = out_dir / f"exec_{execution_id}.runData.json"
        out_path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
        print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
