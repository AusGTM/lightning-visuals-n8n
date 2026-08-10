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

# The plugin config keys the burn-rate alarm's allowance and threshold live under
# (D-04). Read here, once, and passed downstream as RAW values — parsing is
# sweep_conditions.check_burn_rate's job, so this module stays a pure fetch layer.
EXECUTION_ALLOWANCE_KEY = "n8n_monthly_execution_allowance"
BURN_RATE_THRESHOLD_KEY = "burn_rate_alarm_threshold"

_NO_RECENT_MAINTENANCE_EXECUTION = {
    "available": False, "reason": "no_recent_maintenance_execution", "findings": []}
_MAINTENANCE_EXECUTION_UNREADABLE = {
    "available": False, "reason": "could_not_read_execution", "findings": []}


def gather(config, get_transport=requests.get, post_transport=None, now=None):
    """One sweep's worth of backend state, fetched here and nowhere else.

    Returns::

        {"executions": {"available": bool, "summaries": [...], "window": {...} | None},
         "backend":    fetch_backend_status's {available, reason, data},
         "workflows":  {"available": bool, "items": [...]},
         "maintenance_errors": execution_errors.harvest_errors's {available, reason,
                                findings} over the maintenance workflow's latest run,
         "execution_budget": {"key", "allowance", "threshold_key", "threshold"} — the
                              burn-rate alarm's RAW config values (Phase 45, D-04);
                              parsing is sweep_conditions.check_burn_rate's job}

    Each summary is n8n_read.summarize_execution's dict (tri-state `stuck` included)
    plus the raw item's workflow name AND id, so a notice can say WHICH run is wedged and
    check_stuck_armed can cross-reference a workflow's in-flight state, without downstream
    code touching raw executions.

    `now=` is injected through to summarize_execution — no sweep module reads the clock,
    so the stuck threshold is testable on both sides (29-03 Task 1).

    Phase 45 D-08: the executions read is now TIME-WINDOWED (n8n_read.executions_in_window)
    rather than a fixed 100-row page — every condition that consumes `summaries` inherits
    the window through this ONE substitution. `executions["window"]` carries the read's own
    `window_hours`/`count_in_window`/`observed_span_hours`/`covers_full_window`/
    `truncated_by_page_cap`, which is what lets check_burn_rate state an honest span.

    LOOK-01's secondary: `list_workflows` is fetched BEFORE the summary loop (though
    still after the executions read itself — it has no dependency on THAT read's
    result, only on running before the loop that consumes it) and backfills
    `summary["workflow_name"]` for any raw item whose own `workflowData.name` is
    absent — removing the unnamed-workflow fallback text wherever a name is actually
    resolvable. An unreadable workflow list (`workflows_raw is None`) means no
    backfill, never a crash and never a guessed name.
    """
    window = n8n_read.executions_in_window(config, transport=get_transport, now=now)

    workflows_raw = n8n_read.list_workflows(config, transport=get_transport)
    workflows = {"available": workflows_raw is not None, "items": workflows_raw or []}
    workflow_id_to_name = {
        wf["id"]: wf["name"]
        for wf in workflows["items"]
        if isinstance(wf, dict) and wf.get("id") is not None and wf.get("name")
    }

    maintenance_execution_id = None
    if window is None:
        executions = {"available": False, "summaries": [], "window": None}
    else:
        summaries = []
        for item in window["items"]:
            summary = n8n_read.summarize_execution(item, config, now=now)
            workflow_data = item.get("workflowData") if isinstance(item, dict) else None
            workflow_id = item.get("workflowId") if isinstance(item, dict) else None
            # The raw item's own name wins when present; the backfill fills it in only
            # where it was genuinely absent — never overriding a name the item carried.
            summary["workflow_name"] = ((workflow_data or {}).get("name")
                                        or workflow_id_to_name.get(workflow_id))
            summary["workflow_id"] = workflow_id
            summaries.append(summary)
            # The window is newest-first, so the first maintenance-workflow item seen is
            # its latest — the only one D-17 permits fetching runData for. The name must
            # already be resolved (backfill included) for this comparison to see it.
            if (maintenance_execution_id is None
                    and summary["workflow_name"] == MAINTENANCE_WORKFLOW_NAME):
                maintenance_execution_id = summary["execution_id"]
        executions = {
            "available": True,
            "summaries": summaries,
            "window": {
                "window_hours": window["window_hours"],
                "count_in_window": window["count_in_window"],
                "observed_span_hours": window["observed_span_hours"],
                "covers_full_window": window["covers_full_window"],
                "truncated_by_page_cap": window["truncated_by_page_cap"],
            },
        }

    if maintenance_execution_id is None:
        maintenance_errors = dict(_NO_RECENT_MAINTENANCE_EXECUTION)
    else:
        full_execution = n8n_read.get_execution(config, maintenance_execution_id,
                                                transport=get_transport)
        if full_execution is None:
            maintenance_errors = dict(_MAINTENANCE_EXECUTION_UNREADABLE)
        else:
            maintenance_errors = execution_errors.harvest_errors(full_execution)

    # post_transport=None lets fetch_backend_status's OWN default supply the verb, so
    # this module never names a non-GET transport (test_sweep_read_only.py holds it to
    # that); tests inject a stub here instead of monkeypatching.
    if post_transport is None:
        backend = backend_status.fetch_backend_status(config)
    else:
        backend = backend_status.fetch_backend_status(config, transport=post_transport)

    execution_budget = {
        "key": EXECUTION_ALLOWANCE_KEY,
        "allowance": (config or {}).get(EXECUTION_ALLOWANCE_KEY),
        "threshold_key": BURN_RATE_THRESHOLD_KEY,
        "threshold": (config or {}).get(BURN_RATE_THRESHOLD_KEY),
    }

    return {"executions": executions, "backend": backend, "workflows": workflows,
           "maintenance_errors": maintenance_errors, "execution_budget": execution_budget}


def nothing_was_readable(gathered) -> bool:
    """True when EVERY read came back unavailable — the one-layer-down half of D-15:
    zero fired conditions is only silence when the reads that would have fired them
    succeeded."""
    executions = (gathered or {}).get("executions") or {}
    backend = (gathered or {}).get("backend") or {}
    return not executions.get("available") and not backend.get("available")
