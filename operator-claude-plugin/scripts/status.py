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
import n8n_read

# The two write-safety constants the deploy overlay can arm. Read, never written.
WRITE_SAFETY_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE")


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


if __name__ == "__main__":
    import sys

    import config_gate

    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "error": "usage: status.py <workflow_id>"}))
        raise SystemExit(1)

    try:
        _cfg = config_gate.load_config()
    except config_gate.ConfigError as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    print(json.dumps({
        "ok": True,
        "workflow": describe_workflow(_cfg, sys.argv[1]),
        "backend": backend_status.fetch_backend_status(_cfg),
    }, indent=2))
