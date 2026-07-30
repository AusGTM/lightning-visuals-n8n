"""operator-claude-plugin/scripts/n8n_read.py

The read-only half of the credential split (D-01/D-02): everything about workflow and
execution state that the plugin's own n8n API key already entitles it to read, read
directly rather than asked of the backend.

GET only. No activate, deactivate, PUT, PATCH or DELETE path exists in this module at
all, so no mutation is reachable even by a caller mistake (T-27-10).

Auth is `X-N8N-API-KEY` — NOT the `X-Enrichment-Secret` the webhook endpoints take.
Same base URL, two different secrets; crossing them yields a 401 that reads like a
configuration problem rather than an auth one (27-CONTEXT key_links, T-27-13).

Contract, in one line: `None` means "could not tell", `[]` means "read fine, nothing
there", and the two are never conflated. Nothing here raises its way out of a status
question — an operator seeing a traceback learns less than one seeing "unknown" (D-08).

A fetched workflow body is hundreds of kilobytes of backend internals. It enters this
module and does not leave it: the extractor returns the parsed literal and the declaring
node names only, and nothing here logs a body (T-27-11).

Mirrors the calling convention of scripts/deploy_n8n_workflows.py and
scripts/enrichment_cost_ledger.py — reimplemented, never imported (PLUGIN-04's
no-backend-import guard). Sibling `executions_client.py` covers the same API with a
raise-on-failure contract for the report lane; this module's degrade-to-unknown contract
is deliberately the opposite, because a status read must answer even when a read fails.
"""
import re

import requests

DEFAULT_TIMEOUT = 30

# n8n's documented execution statuses: canceled, crashed, error, new, running, success,
# unknown, waiting. Only these two mean "still going".
IN_FLIGHT_STATUSES = frozenset({"running", "new", "waiting"})


def _base_url(config: dict) -> str:
    return str(config.get("n8n_url") or "").rstrip("/")


def _headers(config: dict) -> dict:
    return {"X-N8N-API-KEY": config.get("n8n_api_key") or ""}


def _get_json(config: dict, url: str, params, transport, timeout: int = DEFAULT_TIMEOUT):
    """One GET. Returns the parsed object, or None for every failure mode there is —
    transport error, non-2xx, unparseable body, non-object body. Never raises, and never
    echoes a transport exception's text (it can carry request headers)."""
    try:
        response = transport(url, headers=_headers(config), params=params, timeout=timeout)
    except Exception:
        return None

    status_code = getattr(response, "status_code", None)
    if not isinstance(status_code, int) or not 200 <= status_code < 300:
        return None

    try:
        body = response.json()
    except Exception:
        return None

    return body if isinstance(body, dict) else None


def list_workflows(config: dict, transport=requests.get):
    """Every workflow the API key can see. `[]` is genuinely none; `None` is unreadable."""
    body = _get_json(config, f"{_base_url(config)}/api/v1/workflows", None, transport)
    if body is None:
        return None
    data = body.get("data")
    return data if isinstance(data, list) else None


def get_workflow(config: dict, workflow_id, transport=requests.get):
    """One workflow's full body — for `active` and the write-safety literals. The body
    stays inside the caller's composition step; it is never rendered to the operator."""
    return _get_json(config, f"{_base_url(config)}/api/v1/workflows/{workflow_id}", None, transport)


def _derive_status(execution: dict):
    """Older n8n responses carry no `status` and only a `finished` boolean — mirrored
    from scripts/enrichment_cost_ledger.py rather than trusting `status` unconditionally.
    """
    status = execution.get("status")
    if isinstance(status, str) and status:
        return status
    finished = execution.get("finished")
    if isinstance(finished, bool):
        return "finished" if finished else "running"
    return None


def last_execution(config: dict, workflow_id, transport=requests.get) -> dict:
    """The most recent execution for one workflow.

    Always returns the same shape. `never_run` True with no error means the workflow has
    genuinely never run; an `error` means the read failed and nothing is known — those
    two are the pair a naive implementation conflates into a reassuring blank.
    """
    unknown = {"status": None, "started_at": None, "stopped_at": None,
               "never_run": False, "in_flight": None, "error": None}

    body = _get_json(config, f"{_base_url(config)}/api/v1/executions",
                     {"workflowId": workflow_id, "limit": 1}, transport)
    if body is None:
        return dict(unknown, error="could_not_read_executions")

    data = body.get("data")
    if not isinstance(data, list):
        return dict(unknown, error="unrecognized_response_shape")
    if not data:
        return dict(unknown, never_run=True, in_flight=False)

    execution = data[0] if isinstance(data[0], dict) else {}
    status = _derive_status(execution)
    return {
        "status": status,
        "started_at": execution.get("startedAt"),
        "stopped_at": execution.get("stoppedAt"),
        "never_run": False,
        "in_flight": status in IN_FLIGHT_STATUSES if status else None,
        "error": None,
    }


def read_write_safety(workflow_body, flag_name: str) -> dict:
    """Whether live writes are currently enabled, read out of the deployed workflow —
    never asserted from the plugin's own config (D-03).

    Scans EVERY node's code rather than a fixed node list: the declaring set is not
    stable (`ALLOW_HUBSPOT_CREATE` is currently declared in 9 nodes and
    `ALLOW_HUBSPOT_RECORD_WRITES` in 8, across three workflows, and both sets have
    grown). The pattern is the one `enable_baked_flags()` uses for its own fail-closed
    re-scan, so the read side recognizes exactly what the write side produces.

    One distinct value across declaring nodes is the answer. Zero is unknown. More than
    one is unknown plus the disagreement, naming the disagreeing nodes: a partial deploy
    or a hand edit in the n8n UI can desync them, and reporting a guess would be worse
    than reporting the desync.

    Returns the extracted literal and node names only — never a line of code, never the
    workflow body (T-27-11).
    """
    decl_re = re.compile(rf"const\s+{re.escape(flag_name)}\s*=\s*([^;]+);")
    found = []

    nodes = workflow_body.get("nodes") if isinstance(workflow_body, dict) else None
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict):
            continue
        js_code = (node.get("parameters") or {}).get("jsCode")
        if not isinstance(js_code, str):
            continue
        for match in decl_re.finditer(js_code):
            found.append({"node": node.get("name"),
                          "value": match.group(1).strip().strip('"').strip("'")})

    node_names = sorted({entry["node"] for entry in found if entry["node"]})
    distinct = {entry["value"] for entry in found}

    if len(distinct) == 1:
        return {"value": distinct.pop(), "nodes": node_names, "disagreement": None}
    if not distinct:
        return {"value": None, "nodes": [], "disagreement": None}
    return {"value": None, "nodes": node_names, "disagreement": found}
