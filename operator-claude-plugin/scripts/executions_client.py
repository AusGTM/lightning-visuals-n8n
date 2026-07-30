"""operator-claude-plugin/scripts/executions_client.py

Thin, read-only wrapper over n8n's public API: workflow lookup, execution list,
execution fetch. Auth is the `X-N8N-API-KEY` header — NOT the `X-Enrichment-Secret`
dispatch.py sends to the webhook; sending the wrong one reads as a 401 with no useful
message (26-CONTEXT.md key_links).

Mirrors the calling convention already established in
scripts/deploy_n8n_workflows.py / scripts/enrichment_cost_ledger.py (same base URL and
header shape) — reimplemented here, never imported, per PLUGIN-04's no-backend-import
guard. The plugin's own config (loaded by config_gate.py) supplies `n8n_url` and
`n8n_api_key`, in place of that script's environment variables.

Every GET carries an explicit finite timeout and an injectable transport, so no test
here ever touches a socket — conftest.py's autouse `no_network` guard covers
`requests.get` via the patched `Session.request` too.

This module performs exactly one fetch per call. It never sleeps, loops, or schedules
a re-check — the bounded watch is deliberately left to Phase 29 (D-07).
"""
from datetime import datetime

import requests

# Both deployed workflows contain a node literally named "Decide Action" (D-11c) — the
# enrichment workflow additionally has "Decide Company Action". Selecting the correct
# workflow BY NAME first (this constant) is what keeps report.py from ever reading the
# wrong lane's output.
CONTACT_INGEST_WORKFLOW_NAME = "LV Contact Ingest (Cloud template)"

DEFAULT_TIMEOUT = 30

# Resolved workflow ids, cached for this process only — never persisted to disk.
_workflow_id_cache: dict = {}


class ExecutionsClientError(Exception):
    """Raised when the n8n executions API cannot be reached or returns something
    unusable. Never echoes a transport exception's raw text (it can carry request
    headers) and never interpolates the API key value (T-26-04)."""


def _base_url(config: dict) -> str:
    return str(config.get("n8n_url") or "").rstrip("/")


def _headers(config: dict) -> dict:
    return {"X-N8N-API-KEY": config.get("n8n_api_key") or ""}


def _get_json(config: dict, url: str, params, transport, timeout: int = DEFAULT_TIMEOUT) -> dict:
    try:
        response = transport(url, headers=_headers(config), params=params, timeout=timeout)
    except Exception:
        raise ExecutionsClientError(
            "Could not reach the n8n executions API. Check the connection and try "
            "again, or ask an admin to check the n8n Cloud instance if this persists."
        ) from None

    try:
        body = response.json()
    except Exception:
        raise ExecutionsClientError(
            "The n8n executions API returned something that was not valid JSON."
        ) from None

    if not isinstance(body, dict):
        raise ExecutionsClientError(
            "The n8n executions API returned an unexpected (non-object) response shape."
        )
    return body


def resolve_workflow_id(config: dict, transport=requests.get,
                         workflow_name: str = CONTACT_INGEST_WORKFLOW_NAME):
    """Resolve and cache (process-lifetime only) the workflow id whose `name` matches
    `workflow_name` exactly. Returns None if no workflow matches — the caller decides
    what that means, this function never guesses."""
    cached = _workflow_id_cache.get(workflow_name)
    if cached is not None:
        return cached

    body = _get_json(config, f"{_base_url(config)}/api/v1/workflows", None, transport)
    workflows = body.get("data") if isinstance(body.get("data"), list) else []
    match = next(
        (w for w in workflows if isinstance(w, dict) and w.get("name") == workflow_name),
        None,
    )
    if match is None:
        return None

    workflow_id = match.get("id")
    _workflow_id_cache[workflow_name] = workflow_id
    return workflow_id


def list_executions(config: dict, workflow_id, transport=requests.get, limit: int = 5) -> list:
    """One GET, filtered by workflowId. Newest-or-oldest ordering is not assumed —
    find_execution_for_dispatch below selects by `startedAt` value, not list position."""
    body = _get_json(
        config, f"{_base_url(config)}/api/v1/executions",
        {"workflowId": workflow_id, "limit": limit}, transport,
    )
    data = body.get("data")
    return data if isinstance(data, list) else []


def get_execution(config: dict, execution_id, transport=requests.get) -> dict:
    """One execution, with `includeData=true` — without it `runData` is absent
    entirely (the same requirement scripts/enrichment_cost_ledger.py documents)."""
    return _get_json(
        config, f"{_base_url(config)}/api/v1/executions/{execution_id}",
        {"includeData": "true"}, transport,
    )


def _parse_started_at(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def find_execution_for_dispatch(candidates: list, dispatched_at: datetime, tolerance_s: int = 5):
    """Pure — takes an already-fetched candidate list, performs no fetch of its own.

    Selects the EARLIEST candidate whose `startedAt` is at or after `dispatched_at`
    (allowing `tolerance_s` of clock skew), or returns None when nothing qualifies —
    it never falls back to the nearest earlier run, which would silently attribute a
    stranger's prior execution to this dispatch.

    The returned handle is explicitly marked `best_effort: True`: neither deployed
    workflow references `$execution.id` (D-12), so the webhook response cannot supply
    a real execution id and this correlation could name a neighbouring run. Callers
    must not treat the handle as an authoritative lookup.
    """
    qualifying = []
    for candidate in candidates or []:
        if not isinstance(candidate, dict):
            continue
        started = _parse_started_at(candidate.get("startedAt"))
        if started is None:
            continue
        if (started - dispatched_at).total_seconds() >= -tolerance_s:
            qualifying.append((started, candidate))

    if not qualifying:
        return None

    _, execution = min(qualifying, key=lambda pair: pair[0])
    return {
        "execution_id": execution.get("id"),
        "status": execution.get("status"),
        "started_at": execution.get("startedAt"),
        "best_effort": True,
    }
