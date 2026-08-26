#!/usr/bin/env python3
"""scripts/probe_company_propose_mode.py

Phase 58 Plan 02 -- the propose-mode observation spike (INPUT-02/INPUT-03). Converts the
phase's one traced-but-unobserved architectural claim into observed evidence: does an
unrecognized `mode` key on a companies webhook event ride `Parse HubSpot Event`'s `...event`
spread onto the row and get read by `Decide Company Action`'s `isReturnOnly(row.mode)`,
forcing `action: "proposed"` before the write-safety allowlist check even runs? (CLAUDE.md
Section 13.0; n8n/code/matchProposal.js's `isReturnOnly`; scripts/build_cloud_workflows.py
lines 1566, 3130, 3234-3242.) That trace has never been observed on a live execution's own
runData -- per project memory (n8n-stored-vs-running-content.md), a stored read-back proves
nothing.

Rides the Phase 47.5 on-demand recompute lane (`recompute: true`) alongside `mode:
"propose"`. That lane reaches `Decide Company Action` with no provider, research, judge or
merge node on the path (CLAUDE.md Section 13.0), so this probe costs 0 provider credits and
0 Anthropic calls while still exercising the one predicate under test. It targets ONE
company already known to have complete enrichment inputs (TARGET_COMPANY_ID below) -- the
recompute lane needs a complete record to reach Decide without Company Gate re-enriching it
first, and it is the same company Phase 47.5-03 and Phase 50's armed recompute proof already
used, so re-touching it here adds no new record to this project's blast radius.

Writes NOTHING. `mode: "propose"` forces `Decide Company Action`'s `action` to "proposed"
(a non-writing action) BEFORE `_writeSafetyAllows` even runs -- an empty write-safety
allowlist is the expected, safe configuration for this probe, not a precondition it needs
armed (the Phase 47.5-03 precedent: execution 11858, `action: "write_blocked"` on an empty
allowlist, no record touched).

Two modes, both offline-safe by default:
    python3 scripts/probe_company_propose_mode.py --plan
        Prints the exact event body and target URL. Makes no network call.
    ALLOW_VETO_REMEDIATION=true python3 scripts/probe_company_propose_mode.py --execute
        Sends the event for real via scripts.remediate_veto_companies.post_webhook_event,
        whose `armed` argument has no default and raises NotArmedError before any network
        call unless ALLOW_VETO_REMEDIATION=true is set in the caller's shell. That arming
        decision is operator-only, per-shell, and this script never sets it itself
        (D-11/D-19 precedent) -- see --help.

After a live send, this script reads back the execution the same way
scripts/enrich_coverage_companies.py does: an n8n executions-API GET with includeData=true,
correlated to this dispatch by start time (executions_client.find_execution_for_dispatch) --
never a stored HubSpot property read-back. It reports, from that execution's own runData:
  - whether "Decide Company Action" ran at all
  - what `action` value it produced
  - whether `mode` is visible on the row "Parse HubSpot Event" itself produced
  - the full response body the caller got back

Prints cost actuals (n8n executions used, provider credits, Anthropic calls) against this
plan's cap of 3 / 0 / 0.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*`/`src.*` imports resolve
PLUGIN_SCRIPTS = ROOT / "operator-claude-plugin" / "scripts"
sys.path.insert(0, str(PLUGIN_SCRIPTS))  # flat plugin imports, same idiom scripts/june_run_arm.py uses

from scripts.remediate_veto_companies import (  # noqa: E402
    WEBHOOK_PATH,
    NotArmedError,
    build_webhook_event,
    post_webhook_event,
)

import config_gate  # noqa: E402
import executions_client  # noqa: E402

# Mirrors operator-claude-plugin/scripts/scheduled_arm.py's own ENRICHMENT_WORKFLOW_NAME.
# Kept as a local literal rather than imported -- importing scheduled_arm would pull its
# arming machinery into a read-only probe for no benefit.
ENRICHMENT_WORKFLOW_NAME = "LV Enrichment (Cloud template)"

# The ONE company this probe will ever target -- a module constant with no CLI override,
# same discipline as PROBE_PROPERTY_NAME (probe_org_type_migration.py) / COMPANY_NAME_PREFIX
# (probe_scoring_recalc_latency.py). Melbourne Racing Club: the same "frozen-COMPLETE"
# company Phase 47.5-03's acceptance test and Phase 50's armed recompute proof already used
# for exactly this purpose -- its inputs are complete, it carries no veto, and it already has
# a live recompute history, so re-touching it here adds no new record to the blast radius.
TARGET_COMPANY_ID = "9604614548"  # Melbourne Racing Club

# The plan's own cap (58-02-PLAN.md must_haves) -- printed against actuals, never enforced
# as a hard stop here (a live run past 1 execution is itself the finding to report).
N8N_EXECUTION_CAP = 3
PROVIDER_CREDIT_CAP = 0
ANTHROPIC_CALL_CAP = 0

FIND_EXECUTION_TIMEOUT_S = 60
FIND_EXECUTION_POLL_S = 3


def build_probe_event(company_id: str = TARGET_COMPANY_ID) -> list:
    """The exact event body this probe sends. Delegates entirely to build_webhook_event --
    no second event-body builder exists in this script."""
    return build_webhook_event(company_id, recompute=True, mode="propose")


def _node_output_json(execution: dict, node_name: str):
    """One named node's first output item's `json` payload from
    data.resultData.runData. This exact tiny walk is reimplemented at this call site
    rather than imported from enrich_coverage_companies.py's own (underscore-prefixed,
    private) `_node_output_json` -- that function's own comment states this repo's
    convention is to reimplement it at each call site rather than share it."""
    run_data = ((execution.get("data") or {}).get("resultData") or {}).get("runData")
    if not isinstance(run_data, dict):
        return None
    runs = run_data.get(node_name)
    if not isinstance(runs, list) or not runs:
        return None
    first = runs[0]
    if not isinstance(first, dict):
        return None
    main = (first.get("data") or {}).get("main")
    if not isinstance(main, list) or not main:
        return None
    branch = main[0] if isinstance(main[0], list) else []
    for item in branch:
        if isinstance(item, dict) and isinstance(item.get("json"), dict):
            return item["json"]
    return None


def observe_execution(
    config: dict,
    dispatched_at: datetime,
    resolver=executions_client.resolve_workflow_id,
    lister=executions_client.list_executions,
    getter=executions_client.get_execution,
    finder=executions_client.find_execution_for_dispatch,
    sleeper=time.sleep,
    timeout_s=FIND_EXECUTION_TIMEOUT_S,
    poll_s=FIND_EXECUTION_POLL_S,
):
    """Polls the n8n executions API for the run this probe just dispatched, then extracts
    the observed answers from THAT execution's own runData -- never from a stored HubSpot
    property read-back (project memory: n8n-stored-vs-running-content.md proves that reads
    nothing about what actually ran)."""
    workflow_id = resolver(config, workflow_name=ENRICHMENT_WORKFLOW_NAME)
    if workflow_id is None:
        return {"error": f"no live workflow named {ENRICHMENT_WORKFLOW_NAME!r} was found"}

    deadline = time.monotonic() + timeout_s
    handle = None
    while True:
        candidates = lister(config, workflow_id)
        handle = finder(candidates, dispatched_at)
        if handle is not None or time.monotonic() >= deadline:
            break
        sleeper(poll_s)
    if handle is None:
        return {"error": "no matching execution appeared within the poll window"}

    execution = getter(config, handle["execution_id"])
    run_data = ((execution.get("data") or {}).get("resultData") or {}).get("runData")
    nodes_run = sorted(run_data.keys()) if isinstance(run_data, dict) else []
    decide_output = _node_output_json(execution, "Decide Company Action")
    parse_output = _node_output_json(execution, "Parse HubSpot Event")

    return {
        "execution_handle": handle,
        "nodes_run": nodes_run,
        "decide_company_action_ran": "Decide Company Action" in nodes_run,
        "decide_company_action_output": decide_output,
        "action_value": (decide_output or {}).get("action") if decide_output else None,
        "mode_visible_on_parsed_row": (parse_output or {}).get("mode") if parse_output else None,
    }


def _describe_target(config: dict) -> str:
    """The exact URL scripts.remediate_veto_companies.post_webhook_event will POST to --
    deliberately NOT config_gate.describe_target(), whose WEBHOOK_PATH constant is the
    contact-upload lane's path, not the enrichment lane's."""
    return f"{str((config or {}).get('n8n_url') or '').rstrip('/')}/{WEBHOOK_PATH}"


def _print_plan(event: list, config: dict, config_error) -> None:
    print("=== PLAN (dry run -- no network call is made) ===")
    if config_error:
        print(f"note: config could not be loaded ({config_error}); target URL is unresolvable.")
        target = "(unresolvable)"
    else:
        try:
            target = _describe_target(config)
        except Exception as exc:  # noqa: BLE001 -- a bad config shape IS the observation here
            target = f"(unresolvable: {exc})"
    print(f"target url: {target}")
    print(f"target company id: {TARGET_COMPANY_ID}")
    print(f"event body: {json.dumps(event, indent=2)}")
    print(
        f"cost cap for this spike: {N8N_EXECUTION_CAP} n8n execution(s), "
        f"{PROVIDER_CREDIT_CAP} provider credit(s), {ANTHROPIC_CALL_CAP} Anthropic call(s)"
    )
    print(
        "\nLive send needs the operator-only shell variable ALLOW_VETO_REMEDIATION=true --\n"
        "Claude never sets this. Run:\n"
        "  ALLOW_VETO_REMEDIATION=true python3 scripts/probe_company_propose_mode.py --execute"
    )


def _print_execute(event: list, response_body, observed: dict) -> None:
    print("=== EXECUTED ===")
    print(f"event body sent: {json.dumps(event, indent=2)}")
    print(f"response body received by the caller: {json.dumps(response_body, indent=2, default=str)}")
    print("\n=== OBSERVED (from the execution's own runData, not a stored read-back) ===")
    print(json.dumps(observed, indent=2, default=str))
    n8n_executions_used = 1 if observed.get("execution_handle") else 0
    print(
        f"\ncost actuals vs cap: {n8n_executions_used} n8n execution(s) used "
        f"(cap {N8N_EXECUTION_CAP}), 0 provider credits (cap {PROVIDER_CREDIT_CAP}), "
        f"0 Anthropic calls (cap {ANTHROPIC_CALL_CAP})"
    )


def main(
    argv=None,
    config_loader=config_gate.load_config,
    poster=post_webhook_event,
    observer=observe_execution,
    transport=None,
    env=os.environ,
) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--plan", action="store_true",
        help="Print the event body and target URL. Makes no network call.",
    )
    group.add_argument(
        "--execute", action="store_true",
        help=(
            "Send the event for real. Needs ALLOW_VETO_REMEDIATION=true set in the "
            "OPERATOR's own shell -- this script never sets that variable itself."
        ),
    )
    args = parser.parse_args(argv)

    event = build_probe_event()

    config = {}
    config_error = None
    try:
        config = config_loader()
    except Exception as exc:  # noqa: BLE001 -- an unloadable config IS reportable here
        config_error = str(exc)

    if args.plan:
        _print_plan(event, config, config_error)
        return 0

    # --execute
    if config_error:
        print(f"REFUSED: config could not be loaded ({config_error}). No network call made.")
        return 1

    armed = str(env.get("ALLOW_VETO_REMEDIATION", "false")).lower() == "true"
    dispatched_at = datetime.now(timezone.utc)
    poster_kwargs = {"recompute": True, "mode": "propose"}
    if transport is not None:
        poster_kwargs["transport"] = transport
    try:
        response = poster(TARGET_COMPANY_ID, armed, config, **poster_kwargs)
    except NotArmedError as exc:
        print(f"REFUSED: {exc}")
        return 1

    try:
        response_body = response.json()
    except Exception:  # noqa: BLE001 -- a non-JSON response body IS the observation here
        response_body = getattr(response, "text", None)

    observed = observer(config, dispatched_at)
    _print_execute(event, response_body, observed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
