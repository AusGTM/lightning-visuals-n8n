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

Redaction (T-73-01-01, repo memory `n8n-rundata-carries-webhook-secret`;
CR-04/D-74-07/D-74-08/D-74-09, Phase 74 Plan 01): `_scrub` walks every dict and
list at ANY depth of a whole node-run entry (not only its `data.main` subtree —
that widening is what reaches a node-run-level `run["error"]` sibling of
`run["data"]`) and replaces the value of any key named in `_SENSITIVE_KEYS`
WHOLESALE with a fixed placeholder — never a key-by-key allowlist at one fixed
path, which is easy to under-cover, and never a partial/serialized copy of the
sensitive value. `_SENSITIVE_KEYS` is `headers`/`error`/`request`/`options`/
`config` (D-74-07's specified five) PLUS `zoom_token`/`access_token`, added as a
Phase 74 Task 1 deviation: the five specified keys alone do not reach either
committed live leak in `exec_12434.runData.json`/`exec_12449.runData.json` — both
carry a ZoomInfo OAuth JWT directly under `zoom_token`/`access_token`, siblings of
`json`, never nested under any of the five. Replaces on first match and does not
recurse into the replaced subtree — an item carrying a bearer value at
`json.error.request.headers.Authorization` loses the whole `error` value at the
first match, nothing below it is walked separately. Error fixtures therefore lose
their message text by design.

`--rescrub PATH [PATH ...]`: re-applies the CURRENT `_scrub` to already-committed
fixture file(s) in place, without any n8n API call and without `N8N_URL`/
`N8N_API_KEY` — the mode used to re-redact a fixture whose raw bytes were already
fetched and committed under an earlier, narrower scrub (D-74-08). Handles both
established fixture shapes: the single-execution `runData` top-level key (default
and `--nodes` excerpt modes) and the `--combine` multi-execution shape
(`executions: {id: {runData: {...}}}`). Never a hand edit of the committed JSON.

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
# D-74-07's five specified keys, widened by `zoom_token`/`access_token` — a Task 1
# deviation (Rule 1/2): the five alone never reach the live ZoomInfo OAuth JWT
# committed in exec_12434.runData.json / exec_12449.runData.json, which sits
# directly under `zoom_token` (35/17 occurrences) or `access_token` (2/2), a
# sibling of `json`, not nested under headers/error/request/options/config. See
# tests/test_freeze_execution_rundata.py::test_zoom_token_and_access_token_values_are_replaced.
_SENSITIVE_KEYS = (
    "headers",
    "error",
    "request",
    "options",
    "config",
    "zoom_token",
    "access_token",
)

REDACTION_NOTE = (
    "any `headers`/`error`/`request`/`options`/`config`/`zoom_token`/`access_token` "
    "key, at any depth of a whole node-run entry, was replaced wholesale with a "
    "fixed placeholder before this fixture was committed (T-73-01-01, repo memory "
    "n8n-rundata-carries-webhook-secret; CR-04/D-74-07/D-74-08) — never a key-by-key "
    "scrub at one fixed path."
)


def _load_config() -> dict:
    return {
        "n8n_url": os.environ.get("N8N_URL"),
        "n8n_api_key": os.environ.get("N8N_API_KEY"),
    }


def _scrub(value):
    """Recursively walks `value` — a whole node-run entry, or any nested
    structure inside one — and replaces the value of any dict key named in
    `_SENSITIVE_KEYS` with `REDACTED_PLACEHOLDER`, at any depth, in any dict or
    list. Non-enumerating: unlike the retired `_redact_headers` (which only ever
    reached `run["data"]["main"][branch][item]["json"]["headers"]`), this walks
    the ENTIRE structure passed to it — including a node-run-level `run["error"]`
    sibling of `run["data"]`, which the old function never saw.

    Replaces on FIRST match and does not recurse into the replaced subtree — an
    item carrying a bearer value at `json.error.request.headers.Authorization`
    loses the whole `error` value at the first match; `request`/`headers` below
    it are never inspected separately.

    A non-dict, non-list value (str, int, bool, None) is returned unchanged. Every
    dict/list level walked builds a brand-new container rather than mutating in
    place, so the caller's input is never mutated even though this function
    performs no explicit `copy.deepcopy` — every nested dict/list in the return
    value is a fresh object, never a reference into the input.
    """
    if isinstance(value, dict):
        return {
            key: (REDACTED_PLACEHOLDER if key in _SENSITIVE_KEYS else _scrub(v))
            for key, v in value.items()
        }
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _rescrub_fixture(fixture: dict) -> dict:
    """Re-applies the CURRENT `_scrub` to whichever runData object(s) `fixture`
    carries, leaving every other field untouched. Handles both established
    fixture shapes: the single-execution `runData` top-level key (default and
    `--nodes` excerpt modes) and the `--combine` multi-execution shape
    (`executions: {id: {runData: {...}}}`). Mutates and returns `fixture` in
    place — the caller already owns a freshly-parsed dict, not a value shared
    with anything else."""
    if isinstance(fixture.get("runData"), dict):
        fixture["runData"] = _scrub(fixture["runData"])
    executions = fixture.get("executions")
    if isinstance(executions, dict):
        for exec_fixture in executions.values():
            if isinstance(exec_fixture, dict) and isinstance(exec_fixture.get("runData"), dict):
                exec_fixture["runData"] = _scrub(exec_fixture["runData"])
    if "redaction" in fixture:
        fixture["redaction"] = REDACTION_NOTE
    return fixture


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
        "runData": _scrub(_run_data_of(execution)),
        "redaction": REDACTION_NOTE,
    }


def build_excerpt(execution: dict, node_names: list) -> dict:
    """Only the named nodes' runData, redacted the same way. Used for the
    `--combine` multi-execution mode — a chunked dispatch's run_id spans many
    executions, and committing every one's FULL runData would dwarf what the fixture
    exists to prove."""
    run_data = _scrub(_run_data_of(execution))
    return {
        "execution_id": execution.get("id"),
        "status": execution.get("status"),
        "runData": {name: run_data[name] for name in node_names if name in run_data},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("execution_ids", nargs="*", type=int)
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
    parser.add_argument(
        "--rescrub", nargs="+", default=None, metavar="PATH",
        help="Re-apply the CURRENT _scrub to already-committed fixture file(s) in "
             "place. No n8n API call, no N8N_URL/N8N_API_KEY needed — operates "
             "entirely on the bytes already on disk (D-74-08).",
    )
    args = parser.parse_args()

    if args.rescrub:
        for rel_path in args.rescrub:
            path = ROOT / rel_path
            fixture = json.loads(path.read_text())
            fixture = _rescrub_fixture(fixture)
            path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
            print(f"rescrubbed {path}")
        return 0

    if not args.execution_ids:
        print(
            "No execution ids given and --rescrub not used — nothing to do.",
            file=sys.stderr,
        )
        return 2

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
