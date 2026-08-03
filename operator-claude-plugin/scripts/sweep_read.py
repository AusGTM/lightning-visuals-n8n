"""operator-claude-plugin/scripts/sweep_read.py

The ONLY module in the sweep graph that performs I/O (29-03, NOTICE-05 / D-02).

Everything downstream — conditions, notices, the entrypoint — receives already-fetched
data, never a client. That split is what makes test_sweep_read_only.py's import-graph
assertion meaningful rather than decorative: one module to audit, one place a new read
can appear.

Reads are n8n_read's GETs plus EXACTLY ONE non-GET call: backend_status.
fetch_backend_status's bodyless POST to webhook/hubspot/backend-status (D-13). That POST
is a read wearing a POST's clothes — n8n webhooks answer on POST, the request carries no
records (json={}), and the endpoint's chain has no write node (a tested fact:
test_backend_status_wiring.py). This module never names a write verb itself: the POST
happens inside fetch_backend_status, whose own default supplies the transport.

Contract, inherited from n8n_read: `available: False` means "could not tell", never
"nothing there". The distinction is load-bearing one layer up — silence is only healthy
when the reads that would have fired a condition actually succeeded (D-15).

29-05 Task 2 widens this gather two ways:

- `workflows`: one `list_workflows` GET, so sweep_conditions.check_stuck_armed can read
  write-safety off the embedded node bodies (n8n's collection response already carries
  full workflow objects in this tenant, the same shortcut status.describe_all takes — no
  per-workflow GET is added).
- `maintenance_errors`: ONE extra GET, gated per D-17/T-27-18 — `n8n_read.get_execution`
  (includeData=true) for the maintenance workflow's single most recent execution only,
  never for every execution in the page, walked by `execution_errors.harvest_errors`. This
  is what makes D-08b's swallowed-failure blind spot detectable at all: the collection
  item `recent_executions()` returns carries no `runData`, so a check written against it
  could never fire.
"""
import requests

import backend_status
import execution_errors
import n8n_read

# The maintenance workflow's own declared name (scripts/build_cloud_workflows.py:5506),
# mirrored from scripts/verify_live_no_native_search.py's MAINTENANCE_WORKFLOW_NAME —
# copied, not imported, since that script lives on the backend side of PLUGIN-04's
# boundary.
MAINTENANCE_WORKFLOW_NAME = "LV Scheduled Maintenance (Cloud)"

_NO_RECENT_MAINTENANCE_EXECUTION = {
    "available": False, "reason": "no_recent_maintenance_execution", "findings": []}
_MAINTENANCE_EXECUTION_UNREADABLE = {
    "available": False, "reason": "could_not_read_execution", "findings": []}


def gather(config, get_transport=requests.get, post_transport=None, now=None):
    """One sweep's worth of backend state, fetched here and nowhere else.

    Returns::

        {"executions": {"available": bool, "summaries": [...]},
         "backend":    fetch_backend_status's {available, reason, data},
         "workflows":  {"available": bool, "items": [...]},
         "maintenance_errors": execution_errors.harvest_errors's {available, reason,
                                findings} over the maintenance workflow's latest run}

    Each summary is n8n_read.summarize_execution's dict (tri-state `stuck` included)
    plus the raw item's workflow name AND id, so a notice can say WHICH run is wedged and
    check_stuck_armed can cross-reference a workflow's in-flight state, without downstream
    code touching raw executions.

    `now=` is injected through to summarize_execution — no sweep module reads the clock,
    so the stuck threshold is testable on both sides (29-03 Task 1).
    """
    raw = n8n_read.recent_executions(config, transport=get_transport)

    maintenance_execution_id = None
    if raw is None:
        executions = {"available": False, "summaries": []}
    else:
        summaries = []
        for item in raw:
            summary = n8n_read.summarize_execution(item, config, now=now)
            workflow_data = item.get("workflowData") if isinstance(item, dict) else None
            summary["workflow_name"] = (workflow_data or {}).get("name")
            summary["workflow_id"] = item.get("workflowId") if isinstance(item, dict) else None
            summaries.append(summary)
            # The page is newest-first, so the first maintenance-workflow item seen is
            # its latest — the only one D-17 permits fetching runData for.
            if (maintenance_execution_id is None
                    and summary["workflow_name"] == MAINTENANCE_WORKFLOW_NAME):
                maintenance_execution_id = summary["execution_id"]
        executions = {"available": True, "summaries": summaries}

    if maintenance_execution_id is None:
        maintenance_errors = dict(_NO_RECENT_MAINTENANCE_EXECUTION)
    else:
        full_execution = n8n_read.get_execution(config, maintenance_execution_id,
                                                transport=get_transport)
        if full_execution is None:
            maintenance_errors = dict(_MAINTENANCE_EXECUTION_UNREADABLE)
        else:
            maintenance_errors = execution_errors.harvest_errors(full_execution)

    workflows_raw = n8n_read.list_workflows(config, transport=get_transport)
    workflows = {"available": workflows_raw is not None, "items": workflows_raw or []}

    # post_transport=None lets fetch_backend_status's OWN default supply the verb, so
    # this module never names a non-GET transport (test_sweep_read_only.py holds it to
    # that); tests inject a stub here instead of monkeypatching.
    if post_transport is None:
        backend = backend_status.fetch_backend_status(config)
    else:
        backend = backend_status.fetch_backend_status(config, transport=post_transport)

    return {"executions": executions, "backend": backend, "workflows": workflows,
           "maintenance_errors": maintenance_errors}


def nothing_was_readable(gathered) -> bool:
    """True when EVERY read came back unavailable — the one-layer-down half of D-15:
    zero fired conditions is only silence when the reads that would have fired them
    succeeded."""
    executions = (gathered or {}).get("executions") or {}
    backend = (gathered or {}).get("backend") or {}
    return not executions.get("available") and not backend.get("available")
