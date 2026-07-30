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


def describe_workflow(config: dict, workflow_id, transport=requests.get) -> dict:
    """On-or-off, whether live writes are currently enabled, when it last ran and
    whether that run succeeded — every one read from the n8n API rather than asserted
    from the plugin's own config (D-03, STATUS-01).

    An unreadable workflow yields None for `active` and None for every flag, never a
    reassuring default (D-08).
    """
    body = n8n_read.get_workflow(config, workflow_id, transport=transport)
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

    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "error": "usage: status.py <workflow_id>"}))
        raise SystemExit(1)

    try:
        _cfg = config_gate.load_config()
        _report = status_report(_cfg, sys.argv[1])
    except config_gate.ConfigError as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    print(json.dumps({"ok": True, **_report}, indent=2))
