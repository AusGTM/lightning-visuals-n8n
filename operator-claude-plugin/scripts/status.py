"""operator-claude-plugin/scripts/status.py

Composes the two sides of the credential split into one answer to one question: what is
this workflow doing? Workflow and execution state come from `n8n_read` (the plugin's own
API key); anything needing a credential the plugin does not hold comes from
`backend_status` (the n8n-side endpoint).

`describe_workflow` deliberately takes ONE workflow and returns ONE mapping — widening
it to every workflow (plan 27-04) is then a loop rather than a rewrite.

Nothing here returns or prints a fetched workflow body: only the extracted state
crosses out of this module (T-27-11).
"""
import json

import requests

import backend_status
import config_gate
import n8n_read

# The two write-safety constants the deploy overlay can arm. Read, never written.
WRITE_SAFETY_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE")

UNKNOWN = "unknown"

# The four counts 27-01's `Build Status` node emits. Named here so an absent key renders
# as unknown rather than vanishing from the answer entirely.
COUNT_KEYS = (
    "companies_requested_unresolved",
    "companies_awaiting_review",
    "contacts_requested_unresolved",
    "contacts_awaiting_review",
)


def render(value) -> str:
    """One value, as the operator should read it.

    Null, absent and blank all become the word unknown. A genuine numeric zero stays 0
    and a False stays off — conflating either with unknown is the D-08 failure: "out of
    credit" and "we cannot tell" are opposite findings, and a blank reads as healthy.
    """
    if value is None:
        return UNKNOWN
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, str) and not value.strip():
        return UNKNOWN
    return str(value)


def render_source_health(entry) -> str:
    """One credential-health entry as a sentence fragment. A refused source never reads
    with a healthy-sounding word: Apollo's by-design 403 means "we cannot ask", not
    "nothing to report"."""
    entry = entry if isinstance(entry, dict) else {}
    source = entry.get("source") or UNKNOWN
    state = entry.get("state")
    reason = entry.get("reason")

    if state == "refused":
        detail = f" ({reason})" if reason else ""
        return f"{source} — refused{detail}"
    if state == "ok":
        return f"{source} — answering"
    detail = f" ({reason})" if reason else ""
    return f"{source} — {UNKNOWN}{detail}"


def render_backend_status(result) -> dict:
    """`fetch_backend_status()`'s mapping, with EVERY backend-supplied datum routed
    through `render()` here at the point of composition — so no later renderer can
    bypass it and print a bare blank."""
    result = result if isinstance(result, dict) else {}
    data = result.get("data") if isinstance(result.get("data"), dict) else {}

    if not result.get("available"):
        return {
            "available": False,
            "reason": render(result.get("reason")),
            "counts": {key: UNKNOWN for key in COUNT_KEYS},
            "credential_health": [],
            "balances": [],
            "checked_at": UNKNOWN,
        }

    counts = data.get("counts") if isinstance(data.get("counts"), dict) else {}
    health = data.get("credential_health") if isinstance(data.get("credential_health"), list) else []
    balances = data.get("balances") if isinstance(data.get("balances"), list) else []

    return {
        "available": True,
        "reason": None,
        "counts": {key: render(counts.get(key)) for key in COUNT_KEYS},
        "credential_health": [render_source_health(entry) for entry in health],
        "balances": [
            {
                "provider": render((balance or {}).get("provider")),
                "credits": render((balance or {}).get("credits")),
            }
            for balance in balances
        ],
        "checked_at": render(data.get("checked_at")),
    }


def describe_workflow(config: dict, workflow_id, transport=requests.get,
                      body=None, last_run=None) -> dict:
    """On-or-off, whether live writes are currently enabled, when it last ran and
    whether that run succeeded — every one read from the n8n API rather than asserted
    from the plugin's own config (D-03, STATUS-01).

    An unreadable workflow yields None for `active` and None for every flag, never a
    reassuring default (D-08).

    `body` and `last_run` may be supplied by a caller that has already read them —
    `describe_all` has both from its two collection calls, and re-fetching per workflow
    would turn one page into N calls.
    """
    if body is None:
        body = n8n_read.get_workflow(config, workflow_id, transport=transport)
    if last_run is None:
        last_run = n8n_read.last_execution(config, workflow_id, transport=transport)

    active = body.get("active") if isinstance(body, dict) else None
    write_safety = {
        flag: n8n_read.read_write_safety(body if isinstance(body, dict) else {}, flag)
        for flag in WRITE_SAFETY_FLAGS
    }

    return {
        "workflow_id": workflow_id,
        "name": body.get("name") if isinstance(body, dict) else None,
        "active": active if isinstance(active, bool) else None,
        "write_safety": write_safety,
        "last_run": last_run,
        "in_flight": last_run.get("in_flight"),
    }


def describe_all(config: dict, transport=requests.get, now=None) -> dict:
    """Every workflow the API key can see — no allowlist, no name filter, no config list
    of workflows to watch (D-07). A newly deployed or renamed workflow is in the answer
    the moment n8n returns it, because the collection response IS the list.

    Costs two calls in the common case: the workflow collection, and one bounded page of
    recent executions grouped by workflow. A workflow absent from that page gets its own
    filtered read — a bounded page is not complete history, and reporting never-run from
    an absence in it would be a fabrication.

    `readable` False with an empty list is "could not read the collection"; `readable`
    True with an empty list is "there are genuinely none".
    """
    workflows = n8n_read.list_workflows(config, transport=transport)
    if workflows is None:
        return {"readable": False, "workflows": []}

    page = n8n_read.recent_executions(config, transport=transport)
    latest_by_workflow = {}
    for execution in page if isinstance(page, list) else []:
        if not isinstance(execution, dict):
            continue
        # The page is newest first, so the first entry seen for a workflow is its latest.
        latest_by_workflow.setdefault(str(execution.get("workflowId")), execution)

    described = []
    for workflow in workflows:
        if not isinstance(workflow, dict):
            continue
        workflow_id = workflow.get("id")
        raw = latest_by_workflow.get(str(workflow_id))
        last_run = (n8n_read.summarize_execution(raw, config, now=now) if raw is not None
                    else n8n_read.last_execution(config, workflow_id,
                                                 transport=transport, now=now))
        # n8n's collection returns full workflow objects; a thin entry without nodes
        # would leave write-safety unknown and silently under-report an armed backend
        # (the D-10 failure), so fetch the body instead of guessing.
        body = workflow if isinstance(workflow.get("nodes"), list) else None
        described.append(describe_workflow(config, workflow_id, transport=transport,
                                           body=body, last_run=last_run))

    return {"readable": True, "workflows": described}


def full_report(config: dict, get_transport=requests.get,
                post_transport=requests.post, now=None) -> dict:
    """The whole picture: every workflow, plus the half only the backend can supply."""
    config_gate.require_capability(config, "status")
    return {
        "workflows": describe_all(config, transport=get_transport, now=now),
        "backend": render_backend_status(
            backend_status.fetch_backend_status(config, transport=post_transport)),
    }


def status_report(config: dict, workflow_id, get_transport=requests.get,
                  post_transport=requests.post) -> dict:
    """The whole answer for one workflow: the half the client reads itself, plus the
    half only the backend can supply — rendered.

    Refuses before any transport is constructed when the status capability's own keys
    are missing (PLUGIN-03). A missing webhook secret is NOT such a case: it costs the
    backend-supplied half, which reports unavailable, not the whole answer.
    """
    config_gate.require_capability(config, "status")
    return {
        "workflow": describe_workflow(config, workflow_id, transport=get_transport),
        "backend": render_backend_status(
            backend_status.fetch_backend_status(config, transport=post_transport)),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 2:
        print(json.dumps({"ok": False, "error": "usage: status.py [workflow_id]"}))
        raise SystemExit(1)

    try:
        _cfg = config_gate.load_config()
        # No argument is the skill's own first call: it doubles as the capability check
        # and as the whole-picture read (D-07).
        _report = (status_report(_cfg, sys.argv[1]) if len(sys.argv) == 2
                   else full_report(_cfg))
    except config_gate.ConfigError as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    print(json.dumps({"ok": True, **_report}, indent=2))
