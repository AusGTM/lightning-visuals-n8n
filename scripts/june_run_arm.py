#!/usr/bin/env python3
"""scripts/june_run_arm.py

Phase 41 Plan 02 Task 3 (D-06/F3) — two independently invocable commands implementing
D-06's whole-run arming style: arm once for the entire 66-record run, let SJ-3's own
15-minute internal poller tick write across however many cycles it takes, disarm once at
the end. Every other exposed arm path in the plugin binds arm->dispatch->disarm into ONE
bounded cycle via a paired context-manager helper -- this script deliberately calls
`n8n_arming.arm_for_dispatch()` and `n8n_arming.disarm()` directly, unpaired, because that
whole-run style has no existing single-command wrapper anywhere in the repo.

Every safety check stays inside n8n_arming, where it already lives: the ALLOW_N8N_ARM kill
switch, the allowlist charset validation, and the fail-closed re-scan are never duplicated
here. This wrapper adds exactly two refusals the library cannot make on its own -- an
empty allowlist, i.e. --ids AND --domains both empty (an empty allowlist denies every write
and would look like a successful arm) and an unresolvable workflow name (refusing rather
than guessing an id) -- and
translates a raised library exception into the same JSON outcome shape a clean refusal
already has, so a partially-applied state can never read as a plain success on stdout.

Disarm mode is deliberately NOT gated on ALLOW_N8N_ARM -- an operator must always be able
to close the window, per n8n_arming.disarm's own docstring: a kill switch that blocked
disarming would strand an armed backend, which is the exact failure the whole ceremony
exists to prevent.

`ALLOW_N8N_ARM` is operator-only, per-shell, never set by Claude. The operator invocation
for arming:
    ALLOW_N8N_ARM=true .venv/bin/python scripts/june_run_arm.py --ids <comma-separated ids>
or, for a record HubSpot has not created yet (an id allowlist cannot name it):
    ALLOW_N8N_ARM=true .venv/bin/python scripts/june_run_arm.py --domains <comma-separated domains>
and for disarming at the end of the run:
    .venv/bin/python scripts/june_run_arm.py --disarm
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_SCRIPTS = ROOT / "operator-claude-plugin" / "scripts"
sys.path.insert(0, str(PLUGIN_SCRIPTS))  # flat plugin imports, same idiom the plugin's own scripts use

import config_gate  # noqa: E402
import executions_client  # noqa: E402
import n8n_arming  # noqa: E402

DEFAULT_WORKFLOW_NAME = "LV Enrichment (Cloud template)"


def _parse_ids(raw: str) -> list:
    return [v.strip() for v in (raw or "").split(",") if v.strip()]


def arm(ids_csv: str, workflow_name: str = DEFAULT_WORKFLOW_NAME,
        domains_csv: str = "") -> dict:
    """Arm the whole run for exactly the resolved ids and/or domains. Never calls
    n8n_arming.disarm -- the two are separate operator actions by D-06.

    Phase 47.5: `domains_csv` exposes n8n_arming.arm_for_dispatch's `record_domains`
    parameter, which the library has always accepted and this wrapper hid by passing []
    unconditionally. A domain allowlist is the only allowlist that can be armed for a
    company that does not exist yet -- an id allowlist cannot name a record HubSpot has not
    created. Keyword with an empty default, so every existing caller keeps passing ids only
    and lands the same record_domains=[] it always did.
    """
    ids = _parse_ids(ids_csv)
    domains = _parse_ids(domains_csv)
    if not ids and not domains:
        return {
            "outcome": "refused",
            "detail": (
                "refusing to arm: --ids and --domains are both empty. An empty allowlist "
                "denies every write and would look like a successful arm."
            ),
        }

    cfg = config_gate.load_config()
    workflow_id = executions_client.resolve_workflow_id(cfg, workflow_name=workflow_name)
    if workflow_id is None:
        return {
            "outcome": "refused",
            "detail": f"refusing to arm: no workflow named {workflow_name!r} was found.",
        }

    try:
        return n8n_arming.arm_for_dispatch(
            workflow_id, record_ids=ids, record_domains=domains, allow_create=False,
            config=cfg,
        )
    except n8n_arming.ArmingRefused as exc:
        return {"outcome": "refused", "detail": str(exc)}


def disarm(workflow_name: str = DEFAULT_WORKFLOW_NAME) -> dict:
    """Close the window and verify it closed, by an independent re-read. Never calls
    n8n_arming.arm_for_dispatch -- the two are separate operator actions by D-06."""
    cfg = config_gate.load_config()
    workflow_id = executions_client.resolve_workflow_id(cfg, workflow_name=workflow_name)
    if workflow_id is None:
        return {
            "outcome": "refused",
            "detail": f"refusing to disarm: no workflow named {workflow_name!r} was found.",
        }

    try:
        return n8n_arming.disarm(workflow_id, cfg)
    except n8n_arming.DisarmFailed as exc:
        # A partially-applied disarm must never read as a plain success on stdout --
        # the outcome dict carried on the exception already says LIVE WRITES MAY STILL
        # BE ENABLED; that is what gets printed and it is what drives the non-zero exit.
        return exc.outcome


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--ids", default="",
        help="comma-separated resolved HubSpot company ids (arm mode only)",
    )
    parser.add_argument(
        "--domains", default="",
        help=("comma-separated company domains (arm mode only). The only allowlist that "
              "can cover a company that does not exist yet."),
    )
    parser.add_argument(
        "--disarm", action="store_true",
        help="close the arm window instead of opening it",
    )
    parser.add_argument("--workflow-name", default=DEFAULT_WORKFLOW_NAME)
    args = parser.parse_args(argv)

    outcome = disarm(workflow_name=args.workflow_name) if args.disarm \
        else arm(args.ids, workflow_name=args.workflow_name, domains_csv=args.domains)

    print(json.dumps(outcome, indent=2, default=str))

    ok_outcomes = {n8n_arming.ARMED, n8n_arming.DISARMED}
    return 0 if outcome.get("outcome") in ok_outcomes else 1


if __name__ == "__main__":
    sys.exit(main())
