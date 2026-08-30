#!/usr/bin/env python3
"""scripts/prove_scale_up_runtime.py

Phase 61 Plan 06 Task 5 (T-61-25) — the DISARMED runtime proof of the substrate-3
scale-up fan-out `scripts/build_cloud_workflows.py` adds to the deployed, PERMANENT
"LV Enrichment (Cloud template)" workflow, behind the off-by-default `scale_up` flag.

Unlike `scripts/probe_n8n_async_semantics.py` (which built and deleted throwaway
`ZZ-PROBE-61-*` workflows), this script fires the REAL production workflow — there is no
separate proof workflow to sweep; `sweep()` below lists the instance and asserts nothing
`ZZ-*`-prefixed exists, which should already be true and is asserted rather than assumed.

WHAT THIS SENDS: two disarmed POSTs to the real `hubspot/enrichment/event` webhook, both
carrying `mode: "propose"` (return-only — CLAUDE.md's own isReturnOnly() write guard) and
`providers: []` (zero provider credit spend) over 2 SYNTHETIC company rows:
  1. `scale_up: true`  — exercises the fan-out; the parent should dispatch 2 detached
     children (Dispatch Self, waitForSubWorkflow=false) and return quickly.
  2. `scale_up` omitted — the SAME 2 rows on substrate 1, for the execution-count
     comparison this task's own `<verify>` block asks for.

Zero HubSpot writes, zero provider calls, zero Anthropic calls, nothing armed — `mode:
"propose"` and `providers: []` make both structurally true regardless of what the
workflow's own write-safety gate would otherwise decide.

STOP CONDITIONS (the plan's own words): if the self-reference does not run at all (an
error on "Dispatch Self" itself, e.g. "no executable trigger"), or if achieving the proof
would require arming a write window or touching a real record, this script prints the
finding and exits non-zero WITHOUT writing a verdict claiming success — the caller
(a human, or the executing agent) is expected to treat that as this plan's own
checkpoint, not to retry with escalated permissions.

TWO GATES, BOTH BEFORE ANY TRANSPORT IS CONSTRUCTED (mirrors probe_n8n_async_semantics.py
exactly):
1. `ALLOW_SCALE_UP_PROOF` must read EXACTLY `true`.
2. The wrong-instance guard, copied from `deploy_n8n_workflows.py::_instance_ok()`.

Usage (creds via `.env`, exactly like the deploy/probe scripts already document):
    set -a; source .env; set +a
    ALLOW_SCALE_UP_PROOF=true .venv/bin/python scripts/prove_scale_up_runtime.py
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "operator-claude-plugin" / "scripts"))

# Reuse the pure, already-tested token-exact containment check rather than re-deriving it
# — `correlate_child_id` itself is NOT reused: it is hardcoded to a probe-specific node
# name ("Dispatch Child", scripts/probe_n8n_async_semantics.py's own p13 shape) this
# workflow's node is not named, so it is re-implemented inline below against the correct
# node name ("Dispatch Self"), using this same primitive.
from probe_n8n_async_semantics import _api, _base, _contains_id_token  # noqa: E402
import config_gate  # noqa: E402 — plugin module; see module docstring for why

# Real business-effecting node NAME FRAGMENTS — never a bare provider-name substring
# check, which false-positives on the `IF <Provider> Credit Requested` GATE nodes (their
# names legitimately contain "Lusha"/"Apollo"/"ZoomInfo" but they are IF conditions, not
# HTTP calls — observed live, execution 12045, before this fix). A gate is exempted by
# its own `IF ` prefix, which no write/provider action node in this codebase carries.
_WRITE_OR_PROVIDER_MARKERS = (
    "HubSpot Update", "HubSpot Create", "HubSpot Associate", "Lusha Enrich",
    "Lusha Reveal", "Apollo Enrich", "Apollo Match", "ZoomInfo Enrich", "ZoomInfo Search",
    "Sonnet", "Haiku", "Claude Web",
)


def _is_write_or_provider_node(name: str) -> bool:
    if name.startswith("IF "):
        return False
    return any(marker in name for marker in _WRITE_OR_PROVIDER_MARKERS)

VERDICT_PATH = ROOT / ".planning" / "phases" / "61-autonomous-batch-runs" / "61-SCALE-UP-VERDICT.json"
PROOF_ENV_VAR = "ALLOW_SCALE_UP_PROOF"
ENRICHMENT_WORKFLOW_ID = "950HPb7a1GgSAIyZ"
ENRICHMENT_WORKFLOW_NAME = "LV Enrichment (Cloud template)"
WEBHOOK_PATH = "hubspot/enrichment/event"


# --------------------------------------------------------------------------- gates

def _instance_ok() -> bool:
    url = os.getenv("N8N_URL", "")
    expected = os.getenv("N8N_EXPECTED_URL")
    if expected:
        return url == expected
    host = urlparse(url).netloc
    return bool(host) and host.endswith(".n8n.cloud")


def _require_gates() -> None:
    problems = []
    if os.getenv(PROOF_ENV_VAR) != "true":
        problems.append(f"{PROOF_ENV_VAR} must read EXACTLY 'true'; got {os.getenv(PROOF_ENV_VAR)!r}")
    if not os.getenv("N8N_URL") or not os.getenv("N8N_API_KEY"):
        problems.append("N8N_URL and N8N_API_KEY must both be set")
    elif not _instance_ok():
        problems.append("wrong-instance guard refused")
    if problems:
        print("REFUSED — this fires the real production enrichment webhook.", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(2)


# ---------------------------------------------------------------- webhook transport

def _fire(secret: str, body: dict, timeout=120):
    import requests
    url = f"{_base()}/webhook/{WEBHOOK_PATH}"
    headers = {"X-Enrichment-Secret": secret, "Content-Type": "application/json"}
    started = time.monotonic()
    r = requests.post(url, json=body, headers=headers, timeout=timeout)
    return time.monotonic() - started, r.status_code, r.text


def _synthetic_rows():
    return {
        "providers": [],
        "mode": "propose",
        "events": [
            {"objectId": "prove-scale-up-1", "objectType": "companies",
             "subscriptionType": "company.propertyChange", "occurredAt": _now_iso()},
            {"objectId": "prove-scale-up-2", "objectType": "companies",
             "subscriptionType": "company.propertyChange", "occurredAt": _now_iso()},
        ],
    }


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------- deploy admin

def _bounce_and_verify(expected_node_count=None):
    """Deactivate then activate — a stored PUT does not reload a running workflow
    (memory: n8n-stored-vs-running-content). Verified by an independent re-read."""
    _api("POST", f"/workflows/{ENRICHMENT_WORKFLOW_ID}/deactivate")
    _api("POST", f"/workflows/{ENRICHMENT_WORKFLOW_ID}/activate")
    live = _api("GET", f"/workflows/{ENRICHMENT_WORKFLOW_ID}")
    if live.get("active") is not True:
        raise RuntimeError(f"bounce did not leave the workflow active: {live.get('active')!r}")
    if expected_node_count is not None and len(live.get("nodes", [])) != expected_node_count:
        raise RuntimeError(
            f"live node count {len(live.get('nodes', []))} != built node count "
            f"{expected_node_count} — the deploy may not have landed"
        )
    return live


def _sweep_confirm_clean():
    leftovers = [w for w in _api("GET", "/workflows?limit=250").get("data", [])
                 if str(w.get("name", "")).startswith("ZZ-")]
    return leftovers


# ------------------------------------------------------------------ execution reads

def _latest_webhook_execution(workflow_id, limit=10):
    """The most recent execution whose own `mode` is "webhook" — a REAL HTTP-triggered
    run, i.e. the PARENT. A detached self-dispatched child's `mode` is "integrated"
    (observed live: execution 12043 alongside its webhook-mode parent 12042) and can
    complete before or interleave with the parent in the list ordering — picking `rows[0]`
    unconditionally (this function's own earlier, buggy version) can silently pick up a
    CHILD instead of the parent it meant to inspect."""
    rows = _api("GET", f"/executions?workflowId={workflow_id}&limit={limit}").get("data", [])
    for row in rows:
        if row.get("mode") == "webhook":
            return row
    return None


def _execution(execution_id):
    return _api("GET", f"/executions/{execution_id}?includeData=true")


def _nodes_that_ran(execution):
    run_data = (((execution or {}).get("data") or {}).get("resultData") or {}).get("runData") or {}
    return sorted(run_data.keys())


def _child_ids_from_dispatch(parent_execution):
    """Reads the parent's own "Dispatch Self" runData directly for every
    `metadata.subExecution.executionId` it carries — structured extraction, not a raw-text
    scan against a candidate id list (a substring/token scan risks a false match, e.g. id
    "104" inside "11042"; this reads the exact field n8n itself writes, observed live at
    execution 12042: `data.main[0][<item>].metadata.subExecution.executionId`). "each" mode
    with N qualifying items produces N such entries, one per dispatched child."""
    run_data = (((parent_execution or {}).get("data") or {}).get("resultData") or {}) \
        .get("runData") or {}
    entries = run_data.get("Dispatch Self") or []
    ids = []
    for entry in entries:
        items = (((entry or {}).get("data") or {}).get("main") or [[]])[0] or []
        for item in items:
            sub = ((item or {}).get("metadata") or {}).get("subExecution") or {}
            eid = sub.get("executionId")
            if eid:
                ids.append(str(eid))
    return ids


# -------------------------------------------------------------------------- main

def main():
    _require_gates()

    built = json.loads((ROOT / "n8n" / "wf_enrichment_cloud.json").read_text())
    live = _bounce_and_verify(expected_node_count=len(built.get("nodes", [])))
    print(f"bounced and verified: active={live.get('active')}, "
          f"nodes={len(live.get('nodes', []))}")

    secret = config_gate.load_config()["webhook_secret"]

    before_ids = {row.get("id") for row in
                  _api("GET", f"/executions?workflowId={ENRICHMENT_WORKFLOW_ID}&limit=20").get("data", [])}

    # --- 1. substrate-1 comparison batch (scale_up omitted) -----------------------------
    rtt_s1, status_s1, _ = _fire(secret, _synthetic_rows())
    time.sleep(3)
    parent_s1 = _latest_webhook_execution(ENRICHMENT_WORKFLOW_ID)
    nodes_s1 = _nodes_that_ran(_execution(parent_s1["id"])) if parent_s1 else []

    # --- 2. scale_up:true batch ----------------------------------------------------------
    fan_body = _synthetic_rows()
    fan_body["scale_up"] = True
    rtt_fan, status_fan, text_fan = _fire(secret, fan_body)
    time.sleep(4)
    parent_fan = _latest_webhook_execution(ENRICHMENT_WORKFLOW_ID)
    parent_fan_full = _execution(parent_fan["id"]) if parent_fan else {}
    nodes_fan = _nodes_that_ran(parent_fan_full)

    # STOP CONDITION: the self-reference did not run at all.
    if "Dispatch Self" not in nodes_fan:
        verdict = {
            "premise": "T-61-25-runtime",
            "answer": None,
            "basis": "observed",
            "outcome": "STOP — self-reference did not run",
            "scope_boundary": (
                "the parent execution never reached 'Dispatch Self' — the cheap "
                "self-reference route failed at runtime, exactly the outcome the plan "
                "names as an operator decision, not an executor one. Do not fall back to "
                "a new parent workflow without operator sign-off."
            ),
            "observed": {
                "parent_execution_id": (parent_fan or {}).get("id"),
                "nodes_that_ran": nodes_fan,
                "http_status": status_fan,
                "response_text": text_fan[:2000],
            },
        }
        _write_verdict(verdict)
        print("STOP: self-reference did not run — see verdict for details.", file=sys.stderr)
        return 2

    write_or_provider_nodes = [n for n in nodes_fan if _is_write_or_provider_node(n)]

    child_ids = _child_ids_from_dispatch(parent_fan_full)
    children = []
    grandchildren_found = []
    child_write_or_provider_nodes = {}
    for cid in child_ids:
        child_full = _execution(cid)
        child_nodes = _nodes_that_ran(child_full)
        children.append({
            "execution_id": cid,
            "nodes_that_ran": child_nodes,
            "status": child_full.get("status"),
            "reached_dispatch_self_again": "Dispatch Self" in child_nodes,
        })
        if "Dispatch Self" in child_nodes:
            grandchildren_found.append(cid)
        flagged = [n for n in child_nodes if _is_write_or_provider_node(n)]
        if flagged:
            child_write_or_provider_nodes[cid] = flagged

    # Correlation, re-derived from `Dispatch Self`'s OWN raw output — `correlate_child_id`
    # (imported) is hardcoded to a probe-specific node name ("Dispatch Child",
    # scripts/probe_n8n_async_semantics.py's own p13 shape), which this workflow's node is
    # NOT named; calling it as-is always returns no match here. Re-implemented inline with
    # the SAME token-exact discipline (`_contains_id_token`) rather than parameterizing
    # the imported one for a single call site.
    run_data = (((parent_fan_full or {}).get("data") or {}).get("resultData") or {}).get("runData") or {}
    dispatch_raw = json.dumps(run_data.get("Dispatch Self") or [], default=str)
    correlated_child_ids = [cid for cid in child_ids if _contains_id_token(dispatch_raw, cid)]

    after_ids = {row.get("id") for row in
                 _api("GET", f"/executions?workflowId={ENRICHMENT_WORKFLOW_ID}&limit=40").get("data", [])}
    spent_this_run = len((after_ids - before_ids))

    leftovers = _sweep_confirm_clean()

    verdict = {
        "premise": "T-61-25-runtime",
        "question": (
            "does the self-referencing substrate-3 fan-out RUN, TERMINATE, and remain "
            "correlatable, on the real deployed 'LV Enrichment (Cloud template)' "
            "workflow (not a throwaway probe workflow)?"
        ),
        "answer": (
            bool(child_ids) and not grandchildren_found
            and not write_or_provider_nodes and not child_write_or_provider_nodes
        ),
        "basis": "observed",
        "scope_boundary": (
            "DISARMED: mode='propose' + providers=[] over 2 synthetic rows — zero "
            "HubSpot writes, zero provider calls, zero Anthropic calls, nothing armed. "
            "This is NOT D-61-08's gated live unattended run. This counts what the "
            "executions API LISTED; what was BILLED is a separate, unobservable-from-an-"
            "API-key question (P-10's standing residual) and is not claimed here."
        ),
        "substrate_1_comparison": {
            "round_trip_seconds": rtt_s1, "http_status": status_s1,
            "parent_execution_id": (parent_s1 or {}).get("id"),
            "nodes_that_ran": nodes_s1,
        },
        "scale_up_run": {
            "round_trip_seconds": rtt_fan, "http_status": status_fan,
            "parent_execution_id": parent_fan_full.get("id"),
            "parent_nodes_that_ran": nodes_fan,
            "write_or_provider_nodes_observed": write_or_provider_nodes,
            "child_execution_ids": child_ids,
            "children": children,
            "child_write_or_provider_nodes_observed": child_write_or_provider_nodes,
            "grandchildren_found": grandchildren_found,
            "depth_guard_stopped_recursion": len(grandchildren_found) == 0,
            "parent_output_correlates_to_child_ids": correlated_child_ids,
        },
        "executions_spent_this_run": spent_this_run,
        "leftover_zz_workflows": leftovers,
        "flag_off_byte_identity": (
            "asserted offline in tests/n8n/scaleUpFanOutFlow.test.mjs and "
            "operator-claude-plugin/tests/test_scale_up_runtime.py, not re-asserted here"
        ),
    }
    _write_verdict(verdict)
    print(json.dumps({
        "answer": verdict["answer"],
        "child_execution_ids": child_ids,
        "grandchildren_found": grandchildren_found,
        "write_or_provider_nodes_observed": write_or_provider_nodes,
        "executions_spent_this_run": spent_this_run,
        "leftover_zz_workflows": leftovers,
    }, indent=2))
    return 0 if verdict["answer"] and not write_or_provider_nodes and not leftovers else 1


def _write_verdict(payload):
    VERDICT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload["written_at"] = _now_iso()
    VERDICT_PATH.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(f"verdict written: {VERDICT_PATH}")


if __name__ == "__main__":
    raise SystemExit(main())
