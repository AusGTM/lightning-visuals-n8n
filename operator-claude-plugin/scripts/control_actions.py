"""operator-claude-plugin/scripts/control_actions.py

The one entry point every backend mutation passes through (28-05, CONTROL-05/06/07).

The machinery underneath (n8n_control, n8n_arming, n8n_cadence) is correct but silent.
This layer's job is the operator's side of the contract: state the consequence in plain
language, show the before-and-after, wait for an explicit confirmation, run the mutation,
and report the verdict from the independent re-read — verbatim, never re-labelled.

THE GATE IS STRUCTURAL, NOT A CONVENTION. `plan_action` is the only thing that composes a
proposal, and `execute_action` is the only thing that mutates — and it takes a proposal.
A caller that skips planning has nothing to execute. `execute_action`'s confirmation
parameter has NO default, so a caller that forgets it gets a TypeError, never a send.

Anything outside the allowlist is refused BEFORE any mutating call is reachable: the
plugin operates the backend; an admin changes it from the repository.

Lane starts delegate to the lane's own dispatcher unchanged and make no n8n API call —
the preview, cost guard and arming gate live on the dispatch path, so the dispatch path
is the only way in (D-06). Which lanes exist is DISCOVERED at call time: 28-05's plan
said one dispatcher shipped, and by execution day there were two (Phase 25 landed
`enrichment.dispatch_enrichment`). Discovery is why that staleness cost nothing.
"""
import importlib
import json

import requests

import config_gate
import n8n_arming
import n8n_cadence
import n8n_control
import n8n_read

REFUSED = "refused"

# The allowlisted action kinds — D-25's four-item allowlist, as surfaced actions.
ACTION_KINDS = ("workflow_active", "arm_dispatch", "cadence", "job_enabled")

# lane name -> (module, attribute). Resolved by import AT CALL TIME, never at module
# import: a lane whose dispatcher has not landed is refused by name, and a lane that
# lands later is offered with no edit here.
_LANE_DISPATCHERS = {
    "contacts": ("dispatch", "dispatch"),
    "enrichment": ("enrichment", "dispatch_enrichment"),
}


def _refusal(detail):
    return {"outcome": REFUSED, "detail": detail}


def _out_of_allowlist(asked_for):
    return _refusal(
        f"I can't do that: {asked_for}. This plugin operates the backend — it can turn "
        f"a workflow on or off, switch an individual scheduled job on or off, change a "
        f"job's schedule, and enable live writes for one specific send. It does not "
        f"change workflow structure, nodes, or credentials; an admin does that from the "
        f"repository. Ask your n8n admin if that's what you need."
    )


def start_scheduled_scan(*_args, **_kwargs):
    """Always a refusal, and written as one on purpose: an operator who asks deserves an
    honest answer naming what IS available. There is no path in this module that changes
    a schedule in order to make something fire — D-05c rejected that because a crash
    mid-sequence leaves the backend silently burning credits on the wrong cadence."""
    return _refusal(
        "I can't run a scheduled scan outside its normal schedule — n8n has no way to "
        "fire a workflow by request (checked against this instance: 405). Two things I "
        "can do instead: turn the whole workflow on or off, or change the job's "
        "schedule so it next runs when you want it to."
    )


def start_lane(lane, config, *, armed, transport=None, **kwargs):
    """Start an ingestion lane by delegating to its OWN dispatcher, unchanged.

    No n8n API call is made here, ever: the guards live on the dispatch path.
    `armed` is keyword-only with no default at the dispatcher level — passing it through
    untouched preserves the arming gate exactly as Phases 23/25 built it.
    """
    entry = _LANE_DISPATCHERS.get(lane)
    if entry is None:
        return _refusal(
            f"there is no lane called {lane!r}. The lanes are: "
            f"{', '.join(sorted(_LANE_DISPATCHERS))}.")

    module_name, attr = entry
    try:
        module = importlib.import_module(module_name)
        dispatcher = getattr(module, attr)
    except (ImportError, AttributeError):
        return _refusal(
            f"the {lane} lane's dispatcher is Phase 25 work and has not landed yet; "
            f"contact upload works now.")

    if transport is not None:
        kwargs["transport"] = transport
    result = dispatcher(kwargs.pop("payload"), armed, config, **kwargs)
    return {
        "outcome": "dispatched",
        "lane": lane,
        "result": result,
        "where_the_outcome_arrives": (
            "The backend reports per-record outcomes into this conversation once the "
            "run settles; ask for backend status any time to check on it."),
    }


def _gate(config):
    """The control capability, checked before any transport is constructed. Control is
    its own capability row (28-01): a config that may READ the backend is not thereby
    one that may MUTATE it."""
    config_gate.require_capability(config, "control")


def plan_action(request, config, transport=None):
    """Classify, read current state, and compose the proposal — the consequence sentence,
    the before-and-after, and the inverse. NO mutation happens here; the only network
    call is the read needed to show current state."""
    _gate(config)
    transport = transport if transport is not None else requests

    kind = (request or {}).get("kind")
    if kind not in ACTION_KINDS:
        return _out_of_allowlist(str((request or {}).get("asked_for") or kind))

    workflow_id = request.get("workflow_id")
    workflow = n8n_read.get_workflow(config, workflow_id, transport=transport.get)
    if not isinstance(workflow, dict):
        return _refusal(
            f"I could not read workflow {workflow_id!r} to show you what would change, "
            f"so nothing was planned. Check backend status and try again.")
    name = workflow.get("name") or workflow_id

    if kind == "workflow_active":
        desired = bool(request.get("active"))
        current = bool(workflow.get("active"))
        jobs = n8n_cadence.schedule_trigger_nodes(workflow)
        stops = (f" Everything in it stops running, including "
                 f"{len(jobs)} scheduled job(s)." if jobs and not desired else "")
        return {
            "kind": kind, "workflow_id": workflow_id, "workflow_name": name,
            "before": current, "after": desired,
            "consequence": (
                f"{name!r} is currently {'on' if current else 'off'}; this turns it "
                f"{'on' if desired else 'off'}.{stops}"),
            "inverse": f"turn it back {'off' if desired else 'on'} — one step",
        }

    if kind == "arm_dispatch":
        ids = [str(v) for v in (request.get("record_ids") or []) if str(v).strip()]
        domains = [str(v) for v in (request.get("record_domains") or []) if str(v).strip()]
        return {
            "kind": kind, "workflow_id": workflow_id, "workflow_name": name,
            "record_ids": ids, "record_domains": domains,
            "allow_create": bool(request.get("allow_create")),
            "before": "live writes off", "after": "live writes on for this send only",
            "consequence": (
                f"Live writes will be enabled on {name!r} for THIS send only. While the "
                f"window is open, enrichment can overwrite HubSpot company and contact "
                f"fields — but the grant is bounded to exactly the records in this "
                f"batch ({len(ids)} record id(s), {len(domains)} domain(s)): the backend "
                f"cannot write any record outside that list. Writes turn off again the "
                f"moment the send finishes; if turning them off fails you will be told "
                f"so explicitly, and an admin must check n8n."),
            "inverse": "writes disarm automatically when the send completes; a failed "
                       "disarm is reported loudly, never assumed",
        }

    node_name = request.get("node_name")
    if kind == "cadence":
        try:
            current = n8n_cadence.read_cadence(workflow, node_name)
            proposed = (request["interval"] if "interval" in request
                        else n8n_cadence.parse_cadence(request.get("phrase")))
        except n8n_cadence.CadenceRefused as refusal:
            return _refusal(str(refusal))
        return {
            "kind": kind, "workflow_id": workflow_id, "workflow_name": name,
            "node_name": node_name, "interval": proposed,
            "before": n8n_cadence.describe_cadence(current),
            "after": n8n_cadence.describe_cadence(proposed),
            "consequence": (
                f"The job {node_name!r} currently runs "
                f"{n8n_cadence.describe_cadence(current)}; after this change it will "
                f"run {n8n_cadence.describe_cadence(proposed)}. That changes how often "
                f"the backend does this work — and, for jobs that spend provider "
                f"credits, how often it spends them."),
            "inverse": f"set it back to {n8n_cadence.describe_cadence(current)} — one step",
        }

    # kind == "job_enabled"
    try:
        currently_on = n8n_cadence.job_enabled(workflow, node_name)
    except n8n_cadence.CadenceRefused as refusal:
        return _refusal(str(refusal))
    desired = bool(request.get("enabled"))
    return {
        "kind": kind, "workflow_id": workflow_id, "workflow_name": name,
        "node_name": node_name, "before": currently_on, "after": desired,
        "consequence": (
            f"The scheduled job {node_name!r} is currently "
            f"{'running' if currently_on else 'switched off'}; this switches it "
            f"{'on' if desired else 'off'}. The other scheduled jobs in {name!r} keep "
            f"running exactly as they are."),
        "inverse": f"switch it back {'off' if desired else 'on'} — one step",
    }


def execute_action(proposal, confirmation, config, transport=None):
    """The only mutating path — and it takes a PROPOSAL, so planning cannot be skipped.

    `confirmation` has no default and must be the exact string "yes": anything else
    refuses. The result's verdict is the underlying MutationResult's, verbatim — this
    layer never softens `failed` and never synthesizes a success from a status code.
    """
    _gate(config)

    if confirmation != "yes":
        return _refusal(
            "not confirmed — nothing was changed. To go ahead, confirm with an explicit "
            "yes after reading what will change.")

    if not isinstance(proposal, dict) or proposal.get("kind") not in ACTION_KINDS:
        return _out_of_allowlist(str((proposal or {}).get("kind")))

    kind = proposal["kind"]
    workflow_id = proposal["workflow_id"]
    transport = transport if transport is not None else requests

    if kind == "workflow_active":
        result = n8n_control.set_active(workflow_id, proposal["after"], config,
                                        transport=transport)
        return _mutation_report(result, proposal)

    if kind == "cadence":
        result = n8n_cadence.set_cadence(workflow_id, proposal["node_name"],
                                         proposal["interval"], config,
                                         transport=transport)
        return _mutation_report(result, proposal)

    if kind == "job_enabled":
        result = n8n_cadence.set_schedule_enabled(workflow_id, proposal["node_name"],
                                                  proposal["after"], config,
                                                  transport=transport)
        return _mutation_report(result, proposal)

    # kind == "arm_dispatch" — the one cycle: arm, dispatch, disarm, as ONE action.
    dispatch_fn = proposal.get("dispatch_fn")
    try:
        with n8n_arming.armed_window(
                workflow_id, proposal.get("record_ids"), proposal.get("record_domains"),
                proposal.get("allow_create", False), config,
                transport=transport) as window:
            dispatch_result = dispatch_fn() if callable(dispatch_fn) else None
    except n8n_arming.DisarmFailed as failure:
        # Its own reported state — never folded into a generic failure (D-03).
        return {"outcome": "disarm_failed", **failure.outcome,
                "operator_note": failure.outcome.get("detail")}
    except n8n_arming.ArmingRefused as refusal:
        return _refusal(str(refusal))

    return {
        "outcome": "verified",
        "kind": kind,
        "arm": window.arm_result,
        "disarm": window.disarm_result,
        "dispatch_result": dispatch_result,
        "report": (f"Done — live writes were on only for that send, bounded to the "
                   f"batch's records, and the disarm was verified by re-reading the "
                   f"backend. {proposal.get('inverse', '')}"),
    }


def _mutation_report(result, proposal):
    """Carry the verdict; never reinterpret it."""
    report = {
        "outcome": result.verdict,            # verbatim: "verified" or "failed"
        "kind": proposal["kind"],
        "workflow_name": proposal.get("workflow_name"),
        "before": proposal.get("before"),
        "after": proposal.get("after"),
        "detail": result.detail,
        "reversal": result.reversal,
    }
    if result.verdict == n8n_control.VERIFIED:
        report["report"] = (f"Done and verified by re-reading the backend. "
                            f"To undo: {result.reversal or proposal.get('inverse')}")
    else:
        report["report"] = (f"THIS DID NOT TAKE EFFECT — the re-read after the change "
                            f"did not show it. {result.detail or ''} Nothing further "
                            f"was attempted.")
    return report
