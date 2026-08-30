#!/usr/bin/env python3
"""scripts/probe_n8n_async_semantics.py

Phase 61 — a one-time, disarmed diagnostic that turns three `[unknown]` premises in
`.planning/phases/61-autonomous-batch-runs/61-SPIKE-VERDICT.md` into OBSERVED facts.

    p07   Does an n8n Cloud execution keep running after its own triggering webhook's
          response has already been sent?  Builds `ZZ-PROBE-61-p07-<uuid>`
          (Webhook[responseMode=responseNode] -> Respond -> Wait -> Set), POSTs to it,
          times the client-side round trip, then reads
          `GET /api/v1/executions/{id}?includeData=true` and checks that the Set node's
          runData recorded success and that the execution spanned at least the wait.

          SCOPE BOUNDARY, stated because it is easy to conflate: a wait SHORTER THAN 65
          SECONDS is held IN PROCESS by n8n and is never offloaded to the database
          (docs.n8n.io). This probe therefore exercises the IN-PROCESS path and says
          NOTHING WHATSOEVER about whether a parked execution survives a platform
          restart — that is P-08, which is answered from n8n's published docs, not here.

    p10   Does the `chunk_count + record_count` execution-cost formula
          (`write_grant.EXECUTIONS_BASIS`) hold at the configured ceiling of 2 records
          per chunk?  READ-ONLY: it reads the enrichment workflow's own execution history
          looking for a past POST that carried >= 2 records in one chunk, and measures
          that window exactly as `operator-claude-plugin/scripts/measure_dispatch.py` did
          for the 1-record case in 54-MEASUREMENT.md.

          It does NOT send. A live 2-record send to the enrichment workflow runs the full
          provider + Haiku/Sonnet + HubSpot chain before it is `write_blocked` (see
          54-MEASUREMENT.md's BEFORE table, executions 11934/11935/11937), and this probe
          is barred from calling a provider or HubSpot at all. If history holds no
          2-record chunk, P-10 stays PENDING and says so — 54-MEASUREMENT.md's own
          discipline: stop and say so rather than spend a send to manufacture a number.

    p13   Can the parent `Execute Workflow` node's own output be correlated to a detached
          child's execution id when wait-for-completion is off?  Builds
          `ZZ-PROBE-61-p13-child-<uuid>` (Execute Workflow Trigger -> Set) and
          `ZZ-PROBE-61-p13-parent-<uuid>` (Webhook -> Execute Workflow -> Set), and fires
          the parent TWICE — once with `waitForSubWorkflow=false`, once with `true` — so
          the OFF case is read against its own ON control rather than against an
          assumption. For each it records, separately: whether the child appears in
          `GET /api/v1/executions` at all, whether the child's own execution row carries
          any field naming the parent, and whether the parent's `Execute Workflow` node
          runData contains the child's real execution id anywhere.

    cleanup   Deactivates and deletes every live workflow whose name starts with
              `ZZ-PROBE-61-`. Belt-and-braces: it lists the instance rather than trusting
              a state file, so a crashed prior run still gets swept.

WHAT THIS MODULE CANNOT DO. No HubSpot call, no provider call, no Anthropic call, no
write-safety constant is written or even named. The only workflows it creates contain
Webhook / Respond / Wait / Set / Execute Workflow (Trigger) nodes and nothing else. It
never routes through `scripts/build_cloud_workflows.py` and never touches `n8n/wf_*.json`.

TWO GATES, BOTH BEFORE ANY TRANSPORT IS CONSTRUCTED:
1. `ALLOW_N8N_PROBE` must read EXACTLY `true` (D-34: not `1`, not `yes`, not `TRUE`).
2. The wrong-instance guard, copied from `scripts/deploy_n8n_workflows.py::_instance_ok()`
   — `N8N_URL` must equal `N8N_EXPECTED_URL` if that is set, else its host must genuinely
   end with `.n8n.cloud`. It never fails open.

`.env` is Read/Bash permission-blocked this session — the operator invocation is:

    ALLOW_N8N_PROBE=true .venv/bin/python -c "from dotenv import load_dotenv; \
      load_dotenv(); import sys; sys.argv=['probe_n8n_async_semantics.py','all']; \
      import runpy; runpy.run_path('scripts/probe_n8n_async_semantics.py', \
      run_name='__main__')"
"""
import argparse
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
VERDICT_PATH = (ROOT / ".planning" / "phases" / "61-autonomous-batch-runs"
                / "61-PREMISE-PROBE-VERDICT.json")

PROBE_ENV_VAR = "ALLOW_N8N_PROBE"
PROBE_PREFIX = "ZZ-PROBE-61-"

# The workflow P-10 reads history from. Resolved by name at runtime; this id is the
# fallback recorded in CLAUDE.md §13.0 / 54-MEASUREMENT.md.
ENRICHMENT_WORKFLOW_NAME = "LV Enrichment (Cloud template)"
ENRICHMENT_WORKFLOW_ID_FALLBACK = "950HPb7a1GgSAIyZ"

# n8n offloads a time-based wait to the database only at or beyond this boundary
# (docs.n8n.io). Below it the execution is held in process. Recorded in the P-07 verdict
# so nobody reads a 5-second result as evidence about restart survival.
WAIT_DB_OFFLOAD_BOUNDARY_SECONDS = 65

DEFAULT_WAIT_SECONDS = 5
READ_SLACK_SECONDS = 4  # settle time between the wait elapsing and the one read


# --------------------------------------------------------------------------- gates

def _instance_ok() -> bool:
    """Wrong-instance guard. Copied from deploy_n8n_workflows.py::_instance_ok — must
    NOT fail open: an unset or unrecognized URL refuses, it never defaults to ok."""
    url = os.getenv("N8N_URL", "")
    expected = os.getenv("N8N_EXPECTED_URL")
    if expected:
        return url == expected
    host = urlparse(url).netloc
    return bool(host) and host.endswith(".n8n.cloud")


def _require_gates() -> None:
    problems = []
    if os.getenv(PROBE_ENV_VAR) != "true":
        problems.append(
            f"{PROBE_ENV_VAR} must read EXACTLY 'true' (not '1'/'yes'/'TRUE'); "
            f"got {os.getenv(PROBE_ENV_VAR)!r}")
    if not os.getenv("N8N_URL") or not os.getenv("N8N_API_KEY"):
        problems.append("N8N_URL and N8N_API_KEY must both be set")
    elif not _instance_ok():
        problems.append(
            "wrong-instance guard refused: N8N_URL must equal N8N_EXPECTED_URL when that "
            "is set, otherwise its host must end with '.n8n.cloud'")
    if problems:
        print("REFUSED — this probe creates and fires live n8n workflows.", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        raise SystemExit(2)


def _base() -> str:
    return os.getenv("N8N_URL", "").rstrip("/")


def _headers() -> dict:
    return {"X-N8N-API-KEY": os.getenv("N8N_API_KEY", ""), "Content-Type": "application/json"}


# ------------------------------------------------------------------ n8n transport

def _api(method, path, **kw):
    import requests
    r = requests.request(method, f"{_base()}/api/v1{path}", headers=_headers(),
                         timeout=kw.pop("timeout", 60), **kw)
    if r.status_code >= 400:
        # n8n's 4xx body names the actual rejection reason; a bare raise_for_status
        # discards it and leaves a diagnostic that says only "400 Bad Request".
        raise RuntimeError(
            f"n8n {method} {path} -> {r.status_code}: {(r.text or '')[:800]}")
    return r.json() if r.content else {}


def _list_workflows() -> list:
    return _api("GET", "/workflows?limit=250").get("data", [])


def _create_workflow(body: dict) -> str:
    return _api("POST", "/workflows", json=body)["id"]


def _activate(wf_id: str) -> None:
    _api("POST", f"/workflows/{wf_id}/activate")


def _delete_workflow(wf_id: str) -> None:
    try:
        _api("POST", f"/workflows/{wf_id}/deactivate")
    except Exception:
        pass
    _api("DELETE", f"/workflows/{wf_id}")


def _executions(workflow_id: str, limit: int = 20) -> list:
    return _api("GET", f"/executions?workflowId={workflow_id}&limit={limit}").get("data", [])


def _execution(exec_id, include_data=True) -> dict:
    suffix = "?includeData=true" if include_data else ""
    return _api("GET", f"/executions/{exec_id}{suffix}")


def _post_webhook(path: str, body: dict, timeout=120):
    """Fire the production webhook and return (elapsed_seconds, status_code)."""
    import requests
    url = f"{_base()}/webhook/{path}"
    started = time.monotonic()
    r = requests.post(url, json=body, timeout=timeout)
    if r.status_code == 404:
        # Webhook registration lag on a just-activated workflow. One retry, not a loop —
        # cheap insurance against burning a one-time operator run into "inconclusive".
        time.sleep(3)
        started = time.monotonic()
        r = requests.post(url, json=body, timeout=timeout)
    return time.monotonic() - started, r.status_code


# ------------------------------------------------------- standalone workflow JSON
# Defined here as literals ON PURPOSE. `scripts/build_cloud_workflows.py` is the
# generator for the real `n8n/wf_*.json` and must not be touched by a probe.

def _set_node(name, node_id, position, field="probe_marker"):
    return {
        "parameters": {"assignments": {"assignments": [
            {"id": node_id, "name": field, "value": "observed", "type": "string"}]},
            "options": {}},
        "id": node_id, "name": name, "type": "n8n-nodes-base.set",
        "typeVersion": 3.4, "position": position,
    }


def _p07_workflow(path: str, wait_seconds: int) -> dict:
    return {
        "name": f"{PROBE_PREFIX}p07-{path}",
        "nodes": [
            {"parameters": {"httpMethod": "POST", "path": path,
                            "responseMode": "responseNode", "options": {}},
             "id": "p07-webhook", "name": "Probe Webhook",
             "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 0],
             "webhookId": path},
            {"parameters": {"respondWith": "allIncomingItems", "options": {}},
             "id": "p07-respond", "name": "Respond Immediately",
             "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1,
             "position": [220, 0]},
            {"parameters": {"amount": wait_seconds, "unit": "seconds"},
             "id": "p07-wait", "name": "Short Wait",
             "type": "n8n-nodes-base.wait", "typeVersion": 1.1, "position": [440, 0],
             "webhookId": f"{path}-wait"},
            _set_node("After Response", "p07-set", [660, 0]),
        ],
        "connections": {
            "Probe Webhook": {"main": [[{"node": "Respond Immediately", "type": "main", "index": 0}]]},
            "Respond Immediately": {"main": [[{"node": "Short Wait", "type": "main", "index": 0}]]},
            "Short Wait": {"main": [[{"node": "After Response", "type": "main", "index": 0}]]},
        },
        "settings": {"executionOrder": "v1"},
    }


def _p13_child_workflow(tag: str) -> dict:
    return {
        "name": f"{PROBE_PREFIX}p13-child-{tag}",
        "nodes": [
            {"parameters": {"inputSource": "passthrough"}, "id": "p13-trigger",
             "name": "Execute Workflow Trigger",
             "type": "n8n-nodes-base.executeWorkflowTrigger", "typeVersion": 1.1,
             "position": [0, 0]},
            _set_node("Child Marker", "p13-child-set", [220, 0], field="child_ran"),
        ],
        "connections": {"Execute Workflow Trigger": {
            "main": [[{"node": "Child Marker", "type": "main", "index": 0}]]}},
        "settings": {"executionOrder": "v1"},
    }


def _p13_parent_workflow(path: str, child_id: str, wait_for_sub: bool) -> dict:
    suffix = "wait" if wait_for_sub else "detached"
    return {
        "name": f"{PROBE_PREFIX}p13-parent-{suffix}-{path}",
        "nodes": [
            {"parameters": {"httpMethod": "POST", "path": path,
                            "responseMode": "lastNode", "options": {}},
             "id": "p13-webhook", "name": "Parent Webhook",
             "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 0],
             "webhookId": path},
            {"parameters": {
                "source": "database",
                "workflowId": {"__rl": True, "value": child_id, "mode": "list",
                               "cachedResultName": f"{PROBE_PREFIX}p13-child"},
                "mode": "each",
                "options": {"waitForSubWorkflow": wait_for_sub}},
             "id": "p13-exec", "name": "Dispatch Child",
             "type": "n8n-nodes-base.executeWorkflow", "typeVersion": 1.2,
             "position": [220, 0]},
            _set_node("Parent Tail", "p13-parent-set", [440, 0], field="parent_ran"),
        ],
        "connections": {
            "Parent Webhook": {"main": [[{"node": "Dispatch Child", "type": "main", "index": 0}]]},
            "Dispatch Child": {"main": [[{"node": "Parent Tail", "type": "main", "index": 0}]]},
        },
        "settings": {"executionOrder": "v1"},
    }


# ------------------------------------------------------------- pure verdict logic
# Everything below this line is I/O-free and is what tests/test_probe_n8n_async.py
# exercises. Keeping the shaping pure is the point: the parsing is the part that can be
# silently wrong, and it is the part a test can reach without live credentials.

def node_run_status(execution: dict, node_name: str):
    """The `executionStatus` recorded for `node_name` in an execution's runData, or None
    if that node has no runData entry at all (it never ran)."""
    runs = (((execution or {}).get("data") or {}).get("resultData") or {}) \
        .get("runData") or {}
    entries = runs.get(node_name)
    if not entries:
        return None
    last = entries[-1] if isinstance(entries, list) else entries
    return (last or {}).get("executionStatus")


def _span_seconds(execution: dict):
    started, stopped = (execution or {}).get("startedAt"), (execution or {}).get("stoppedAt")
    if not started or not stopped:
        return None
    try:
        a = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(stopped).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (b - a).total_seconds()


def verdict_p07(round_trip_seconds, wait_seconds, execution):
    """P-07 from three observations that need NO cross-clock comparison (client wall
    clock and n8n server clock are never subtracted from each other):

      (a) the client's own HTTP round trip was far shorter than the wait,
      (b) the post-Respond Set node's runData recorded success,
      (c) the execution's own server-side span covered at least the wait.

    All three -> `true`: the execution demonstrably kept running after its response was
    already in the caller's hands. A round trip that instead COVERS the wait is a real
    `false` (the response was held until the end), not a broken probe.
    """
    set_status = node_run_status(execution, "After Response")
    respond_status = node_run_status(execution, "Respond Immediately")
    span = _span_seconds(execution)

    responded_early = (round_trip_seconds is not None
                       and round_trip_seconds < wait_seconds * 0.5)
    continued = set_status == "success"
    spanned = span is not None and span >= wait_seconds * 0.8

    if responded_early and continued and spanned:
        answer, basis = True, "observed"
    elif set_status is None and execution:
        answer, basis = False, "observed"
    elif (round_trip_seconds is not None and round_trip_seconds >= wait_seconds * 0.8
            and continued):
        answer, basis = False, "observed"
    else:
        answer, basis = None, "inconclusive"

    return {
        "premise": "P-07",
        "question": ("does an n8n Cloud execution keep running after its own triggering "
                     "webhook's response has already been sent?"),
        "answer": answer,
        "basis": basis,
        "observed": {
            "client_round_trip_seconds": round_trip_seconds,
            "wait_seconds": wait_seconds,
            "respond_node_status": respond_status,
            "post_response_set_node_status": set_status,
            "execution_span_seconds": span,
            "execution_id": (execution or {}).get("id"),
            "execution_status": (execution or {}).get("status"),
        },
        "scope_boundary": (
            f"the wait was {wait_seconds}s, BELOW the {WAIT_DB_OFFLOAD_BOUNDARY_SECONDS}s "
            "boundary at which n8n offloads a time-based wait to the database, so this "
            "exercised the IN-PROCESS path only. It is evidence about respond-then-"
            "continue semantics and NO evidence at all about whether a parked execution "
            "survives a platform restart (P-08)."
            if wait_seconds < WAIT_DB_OFFLOAD_BOUNDARY_SECONDS else
            f"the wait was {wait_seconds}s, at or beyond the "
            f"{WAIT_DB_OFFLOAD_BOUNDARY_SECONDS}s database-offload boundary; this run "
            "additionally crossed into the database-backed wait path."),
    }


def find_multirecord_chunk(executions_with_data, min_records=2):
    """The first execution in `executions_with_data` whose webhook payload carried at
    least `min_records` records in one POST.

    Counts records the way the enrichment lane's own entry node does: the `Parse HubSpot
    Event` node's runData output items. Falls back to the Webhook node's own body when
    that node has no runData (a shape change would otherwise read as 'no multi-record
    send ever happened', which is a different and much stronger claim).
    """
    for execution in executions_with_data or []:
        runs = (((execution or {}).get("data") or {}).get("resultData") or {}) \
            .get("runData") or {}
        count, source = None, None
        for node_name in ("Parse HubSpot Event", "Webhook Trigger"):
            entries = runs.get(node_name)
            if not entries:
                continue
            try:
                items = entries[-1]["data"]["main"][0]
            except (KeyError, IndexError, TypeError):
                continue
            if node_name == "Webhook Trigger":
                body = ((items[0] or {}).get("json") or {}).get("body") if items else None
                inner = None
                if isinstance(body, dict):
                    # The documented envelope keys (CLAUDE.md §13.0.1), plus the generic
                    # `records` form, so a shape change does not read as "no multi-record
                    # send ever happened".
                    for key in ("companies", "contacts", "records"):
                        if isinstance(body.get(key), list):
                            inner = body[key]
                            break
                count = len(inner) if isinstance(inner, list) else len(items or [])
            else:
                count = len(items or [])
            source = node_name
            break
        if count is not None and count >= min_records:
            return {"execution_id": execution.get("id"),
                    "started_at": execution.get("startedAt"),
                    "record_count": count, "counted_from": source}
    return None


def verdict_p10(candidate, window_execution_ids, child_executions_listed):
    """P-10 — the `chunk_count + record_count` formula at a 2-record chunk.

    `child_executions_listed` is P-13's own observation of whether a sub-workflow
    execution shows up in `GET /api/v1/executions` at all. It is carried here because it
    is exactly what separates the two candidate explanations of the measured-1-vs-
    projected-2 anomaly at chunk_count=1:

      (a) the formula over-counts generally, versus
      (b) sub-workflow executions exist but are excluded from the BILLED quota
          (documented: docs.n8n.io — "only the parent (top-level) execution counts").

    NOTE THE TWO DIFFERENT THINGS: this measurement reads the executions LIST. The
    2,500/month figure is a BILLING concept. They are not the same number and this
    verdict never equates them.
    """
    if candidate is None:
        return {
            "premise": "P-10",
            "question": ("does `chunk_count + record_count` hold at the configured "
                         "ceiling of 2 records per chunk?"),
            "answer": None,
            "basis": "pending",
            "reason": ("no execution carrying >= 2 records in one chunk exists in the "
                       "enrichment workflow's reachable history. This probe is barred "
                       "from manufacturing one: a live 2-record send runs the full "
                       "provider + Anthropic + HubSpot chain before it is write_blocked "
                       "(54-MEASUREMENT.md's BEFORE table), and this probe may not call "
                       "a provider or HubSpot at all."),
            "residual_command": ("after the operator's next genuine 2-record send, run "
                                 "operator-claude-plugin/scripts/measure_dispatch.py "
                                 "against the window bracketing it, exactly as "
                                 "54-MEASUREMENT.md did for the 1-record case."),
            "sub_workflow_executions_listed": child_executions_listed,
        }

    measured = len(window_execution_ids or [])
    projected = 1 + candidate["record_count"]  # chunk_count(1) + record_count
    if child_executions_listed is True:
        discrimination = ("sub-workflow executions ARE listed by the executions API on "
                          "this instance, so a shortfall here is NOT explained by "
                          "children being invisible to the list — explanation (a), the "
                          "formula over-counting, is the one the list supports. Whether "
                          "those listed children are BILLED is a separate question this "
                          "measurement does not observe.")
    elif child_executions_listed is False:
        discrimination = ("sub-workflow executions are NOT listed by the executions API "
                          "on this instance, so a measured count below the projection "
                          "cannot distinguish (a) the formula over-counting from (b) "
                          "real-but-invisible children. This measurement cannot tell "
                          "them apart.")
    else:
        discrimination = ("P-13 did not establish whether sub-workflow executions appear "
                          "in the executions list, so (a) and (b) are not separated here.")

    return {
        "premise": "P-10",
        "question": ("does `chunk_count + record_count` hold at the configured ceiling "
                     "of 2 records per chunk?"),
        "answer": measured == projected,
        "basis": "measured",
        "observed": {
            "source_execution": candidate,
            "window_execution_ids": window_execution_ids,
            "measured_executions_listed": measured,
            "projected_executions": projected,
            "delta": measured - projected,
        },
        "list_vs_billing": ("this counts rows returned by GET /api/v1/executions. The "
                           "2,500/month allowance is a BILLING quota. The two are not "
                           "equated anywhere in this verdict."),
        "explanation_discrimination": discrimination,
        "sub_workflow_executions_listed": child_executions_listed,
    }


def _contains_id_token(haystack, needle):
    """Exact-token containment. A plain substring test would let child id `119` match
    `11960` and report a correlation that does not exist — and a false positive here
    reports an unusable substrate as usable, which is the one failure this probe must
    not produce."""
    if not haystack or needle in (None, ""):
        return False
    return bool(re.search(rf"(?<![0-9A-Za-z]){re.escape(str(needle))}(?![0-9A-Za-z])",
                          str(haystack)))


def correlate_child_id(parent_execution, child_execution_ids):
    """Does the parent's `Dispatch Child` node output contain any of the child's real
    execution ids, as a whole token?  Returns (matched_id_or_None, raw_output)."""
    runs = (((parent_execution or {}).get("data") or {}).get("resultData") or {}) \
        .get("runData") or {}
    entries = runs.get("Dispatch Child")
    if not entries:
        return None, None
    raw = json.dumps(entries[-1] if isinstance(entries, list) else entries, default=str)
    for child_id in child_execution_ids or []:
        if _contains_id_token(raw, child_id):
            return str(child_id), raw
    return None, raw


def verdict_p13(detached, waited):
    """P-13. `detached` and `waited` are each a dict from `_run_p13_case`. The OFF case
    is the premise; the ON case is its control, so 'not correlatable' is reported as a
    property of detachment rather than of Execute Workflow generally."""
    answer = detached.get("matched_child_execution_id") is not None
    return {
        "premise": "P-13",
        "question": ("can the parent Execute Workflow node's own output be correlated to "
                     "a detached child's execution id when wait-for-completion is off?"),
        "answer": answer,
        "basis": "observed",
        "wait_for_completion_off": detached,
        "wait_for_completion_on_control": waited,
        "child_appears_in_executions_list": detached.get("child_execution_ids") not in (None, []),
        "delta_off_vs_on": {
            "child_listed": [bool(detached.get("child_execution_ids")),
                             bool(waited.get("child_execution_ids"))],
            "parent_output_carries_child_id": [
                detached.get("matched_child_execution_id") is not None,
                waited.get("matched_child_execution_id") is not None],
        },
        "note": ("n8n's docs state a sub-workflow execution counts neither against the "
                 "billable quota nor against the Starter plan's 5-concurrent cap. That "
                 "is DOCUMENTED, not observed here — this probe observes only what the "
                 "executions API lists and what the parent's runData contains."),
    }


# ------------------------------------------------------------------- probe runners

def _run_p07(wait_seconds):
    path = f"probe61-p07-{uuid.uuid4().hex[:12]}"
    wf_id = _create_workflow(_p07_workflow(path, wait_seconds))
    try:
        _activate(wf_id)
        time.sleep(2)  # webhook registration settle; not a poll
        round_trip, status = _post_webhook(path, {"probe": "p07"})
        time.sleep(wait_seconds + READ_SLACK_SECONDS)
        executions = _executions(wf_id, limit=5)
        execution = _execution(executions[0]["id"]) if executions else {}
        verdict = verdict_p07(round_trip, wait_seconds, execution)
        verdict["observed"]["http_status"] = status
        verdict["executions_spent"] = len(executions)
        return verdict, len(executions)
    finally:
        _delete_workflow(wf_id)


def _run_p13_case(child_id, wait_for_sub, already_seen_child_ids):
    """`already_seen_child_ids` keeps the second case from re-counting (and re-reporting)
    the first case's child — both cases dispatch the SAME child workflow, so its
    execution list is cumulative."""
    path = f"probe61-p13-{uuid.uuid4().hex[:12]}"
    parent_id = _create_workflow(_p13_parent_workflow(path, child_id, wait_for_sub))
    try:
        _activate(parent_id)
        time.sleep(2)
        round_trip, status = _post_webhook(path, {"probe": "p13"})
        time.sleep(6)
        child_rows = [r for r in _executions(child_id, limit=20)
                      if r.get("id") not in already_seen_child_ids]
        parent_rows = _executions(parent_id, limit=5)
        parent_exec = _execution(parent_rows[0]["id"]) if parent_rows else {}
        parent_exec_id = (parent_exec or {}).get("id")
        child_ids = [r.get("id") for r in child_rows]
        matched, raw = correlate_child_id(parent_exec, child_ids)

        # The reverse direction the parent output may not give us: does the CHILD's own
        # detail record name the parent execution? Free — a management-plane read costs
        # 0 n8n executions (P-04) — and it is the practical fallback correlation if
        # parent -> child turns out to be one-way.
        child_detail_link, child_detail_keys = None, []
        if child_ids:
            try:
                child_detail = _execution(child_ids[0])
                child_detail_keys = sorted(
                    k for k in child_detail if "parent" in k.lower() or "retry" in k.lower())
                if _contains_id_token(json.dumps(child_detail, default=str), parent_exec_id):
                    child_detail_link = str(parent_exec_id)
            except Exception:
                child_detail_keys = ["<child detail read failed>"]

        return {
            "wait_for_completion": wait_for_sub,
            "http_status": status,
            "client_round_trip_seconds": round_trip,
            "parent_execution_id": parent_exec_id,
            "child_execution_ids": child_ids,
            "child_rows_carry_parent_link": sorted(
                {k for r in child_rows for k in (r or {}) if "parent" in k.lower()}) or [],
            "child_detail_parent_like_fields": child_detail_keys,
            "child_detail_carries_parent_execution_id": child_detail_link,
            "matched_child_execution_id": matched,
            "parent_dispatch_node_output": (raw or "")[:4000],
            "_executions_seen": len(child_ids) + len(parent_rows),
        }
    finally:
        _delete_workflow(parent_id)


def _run_p13():
    child_id = _create_workflow(_p13_child_workflow(uuid.uuid4().hex[:12]))
    try:
        # OBSERVED CONSTRAINT (2026-08-30): this n8n Cloud instance refuses to activate a
        # parent whose Execute Workflow node references an unpublished child --
        #   400 "Cannot publish workflow: Node "Dispatch Child" references workflow <id>
        #   which is not published. Please publish all referenced sub-workflows first."
        # So the child must be published before the parent. This is a real operational
        # constraint on substrate 3, not probe scaffolding: any sub-workflow dispatch
        # architecture must publish its children before the parent can go live.
        _activate(child_id)
        detached = _run_p13_case(child_id, False, set())
        waited = _run_p13_case(child_id, True, set(detached["child_execution_ids"]))
        spent = detached.pop("_executions_seen", 0) + waited.pop("_executions_seen", 0)
        return verdict_p13(detached, waited), spent
    finally:
        _delete_workflow(child_id)


def _resolve_enrichment_workflow_id():
    for wf in _list_workflows():
        if wf.get("name") == ENRICHMENT_WORKFLOW_NAME:
            return wf.get("id")
    return ENRICHMENT_WORKFLOW_ID_FALLBACK


def _run_p10(child_executions_listed=None, scan_limit=40):
    """READ-ONLY. Costs 0 n8n executions: /api/v1/executions is a management-plane
    endpoint, not a workflow trigger (P-04)."""
    wf_id = _resolve_enrichment_workflow_id()
    rows = _executions(wf_id, limit=scan_limit)
    detailed = []
    for row in rows:
        try:
            detailed.append(_execution(row["id"]))
        except Exception:
            continue
    candidate = find_multirecord_chunk(detailed)
    window_ids = []
    if candidate:
        started = candidate["started_at"]
        window_ids = [r.get("id") for r in rows if r.get("startedAt") == started] or \
                     [candidate["execution_id"]]
    verdict = verdict_p10(candidate, window_ids, child_executions_listed)
    verdict["scanned"] = {"workflow_id": wf_id, "executions_read": len(detailed),
                          "scan_limit": scan_limit}
    return verdict, 0


def _cleanup():
    removed = []
    for wf in _list_workflows():
        if str(wf.get("name", "")).startswith(PROBE_PREFIX):
            _delete_workflow(wf["id"])
            removed.append({"id": wf["id"], "name": wf["name"]})
    return removed


# ---------------------------------------------------------------------------- cli

def _read_verdict() -> dict:
    """Whatever an earlier invocation already recorded. Missing or corrupt file -> {},
    so a caller degrades to 'no prior observation' rather than crashing."""
    if not VERDICT_PATH.exists():
        return {}
    try:
        loaded = json.loads(VERDICT_PATH.read_text())
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _write_verdict(payload):
    VERDICT_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_verdict()
    existing.update(payload)
    existing["written_at"] = datetime.now(timezone.utc).isoformat()
    VERDICT_PATH.write_text(json.dumps(existing, indent=2, default=str) + "\n")
    print(f"verdict written: {VERDICT_PATH}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[2])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p07 = sub.add_parser("p07", help="respond-then-continue semantics")
    p07.add_argument("--wait-seconds", type=int, default=DEFAULT_WAIT_SECONDS)
    sub.add_parser("p10", help="2-record chunk execution cost (read-only, 0 executions)")
    sub.add_parser("p13", help="detached child execution-id correlation")
    sub.add_parser("cleanup", help=f"delete every live {PROBE_PREFIX}* workflow")
    all_p = sub.add_parser("all", help="p07, p13, then p10, then cleanup")
    all_p.add_argument("--wait-seconds", type=int, default=DEFAULT_WAIT_SECONDS)
    args = parser.parse_args(argv)

    _require_gates()
    spent = 0

    if args.cmd == "cleanup":
        print(json.dumps(_cleanup(), indent=2))
        return 0

    if args.cmd == "p07":
        verdict, n = _run_p07(args.wait_seconds)
        spent += n
        _write_verdict({"P-07": verdict, "executions_spent_p07": n})
    elif args.cmd == "p13":
        verdict, n = _run_p13()
        spent += n
        _write_verdict({"P-13": verdict, "executions_spent_p13": n})
    elif args.cmd == "p10":
        # Fire-and-read-separately is this tool's design, so a standalone p10 must be able
        # to pick up a P-13 observation recorded by an EARLIER invocation. Without this,
        # only `all` could ever separate explanation (a) from (b), which defeats the
        # point of the subcommands. Absent/older verdict -> None, exactly as before.
        prior = _read_verdict().get("P-13") or {}
        verdict, n = _run_p10(
            child_executions_listed=prior.get("child_appears_in_executions_list"))
        _write_verdict({"P-10": verdict, "executions_spent_p10": n})
    elif args.cmd == "all":
        v07, n07 = _run_p07(args.wait_seconds)
        v13, n13 = _run_p13()
        listed = v13.get("child_appears_in_executions_list")
        v10, _ = _run_p10(child_executions_listed=listed)
        spent = n07 + n13
        _write_verdict({
            "probe": "61-premise-probe (P-07, P-10, P-13)",
            "instance": urlparse(_base()).netloc,
            "P-07": v07, "P-10": v10, "P-13": v13,
            "executions_spent": {"p07": n07, "p13": n13, "p10": 0, "total": spent},
            "out_of_scope": ["P-05", "P-08", "P-09 — not probed here by design"],
        })
        print(json.dumps({"P-07": v07["answer"], "P-10": v10["answer"],
                          "P-13": v13["answer"]}, indent=2))

    swept = _cleanup()
    print(f"cleanup: removed {len(swept)} {PROBE_PREFIX}* workflow(s)")
    print(f"n8n executions spent by this run: {spent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
