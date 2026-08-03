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
"""
import requests

import backend_status
import n8n_read


def gather(config, get_transport=requests.get, post_transport=None, now=None):
    """One sweep's worth of backend state, fetched here and nowhere else.

    Returns::

        {"executions": {"available": bool, "summaries": [...]},
         "backend":    fetch_backend_status's {available, reason, data}}

    Each summary is n8n_read.summarize_execution's dict (tri-state `stuck` included)
    plus the raw item's workflow name, so a notice can say WHICH run is wedged without
    downstream code touching raw executions.

    `now=` is injected through to summarize_execution — no sweep module reads the clock,
    so the stuck threshold is testable on both sides (29-03 Task 1).
    """
    raw = n8n_read.recent_executions(config, transport=get_transport)

    if raw is None:
        executions = {"available": False, "summaries": []}
    else:
        summaries = []
        for item in raw:
            summary = n8n_read.summarize_execution(item, config, now=now)
            workflow_data = item.get("workflowData") if isinstance(item, dict) else None
            summary["workflow_name"] = (workflow_data or {}).get("name")
            summaries.append(summary)
        executions = {"available": True, "summaries": summaries}

    # post_transport=None lets fetch_backend_status's OWN default supply the verb, so
    # this module never names a non-GET transport (test_sweep_read_only.py holds it to
    # that); tests inject a stub here instead of monkeypatching.
    if post_transport is None:
        backend = backend_status.fetch_backend_status(config)
    else:
        backend = backend_status.fetch_backend_status(config, transport=post_transport)

    return {"executions": executions, "backend": backend}


def nothing_was_readable(gathered) -> bool:
    """True when EVERY read came back unavailable — the one-layer-down half of D-15:
    zero fired conditions is only silence when the reads that would have fired them
    succeeded."""
    executions = (gathered or {}).get("executions") or {}
    backend = (gathered or {}).get("backend") or {}
    return not executions.get("available") and not backend.get("available")
