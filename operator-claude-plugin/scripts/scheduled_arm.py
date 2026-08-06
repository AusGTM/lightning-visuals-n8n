"""operator-claude-plugin/scripts/scheduled_arm.py

The SJ-3 scheduled-poller companion (WINDOWS.md #2's "scheduled arm" resolution).

WHY NOT IN-N8N (the investigated, rejected option). `n8n_arming.arm_for_dispatch`'s own
bracket — deactivate -> PUT -> activate (`n8n_control.apply_mutation`) — exists BECAUSE a
bare PUT never reaches a RUNNING workflow: n8n keeps executing an active workflow's
pre-PUT content until it is bounced (proven live 2026-08-03, runs 1122/1123 fired
disarmed inside an "armed PASS" window — see MEMORY.md n8n-stored-vs-running-content).
SJ-3's own dispatch (`SJ-3 Dispatch To Enrichment`, an n8n Execute-Workflow "call another
workflow" node inside `LV Scheduled Maintenance (Cloud)`) runs search -> extract ->
build-dispatch-event -> dispatch entirely inside ONE n8n execution, fired by n8n's own
internal 15-minute clock, with no external hook between those steps — and
`control_actions.start_scheduled_scan` already documents that n8n has no way to fire a
workflow by request at all (405, checked live). An in-n8n arm/disarm pair (Code/HTTP-
Request nodes spliced into that same workflow, bracketing the dispatch node) would have
to replicate `arm_for_dispatch`'s deactivate->PUT->activate bounce against "LV
Enrichment (Cloud template)" from INSIDE a running n8n execution: an `N8N_API_KEY`
credential (full workflow-management power — a strictly bigger blast radius than any
credential this pipeline holds today) pasted into a Code node, self-modifying a sibling
workflow's code mid-flight, reimplementing `arm_for_dispatch`'s fail-closed re-scan and
allowlist guards in JavaScript with none of this module's test coverage. That is not a
smaller mechanism than reusing `n8n_arming` from outside n8n; it is the same mechanism,
done less safely, in a language with none of the existing tests. Rejected — this module
is the external form the design brief asked for instead.

WHAT THIS DOES INSTEAD. Since SJ-3's own internal dispatch cannot be intercepted or fired
on demand, this companion cannot literally straddle SJ-3's Execute-Workflow call. What it
CAN do, reusing exactly the machinery this repo already shipped and tested:

  1. Read (never guess) the batch SJ-3 most recently matched, off n8n's OWN execution
     history (`executions_client.list_executions`/`get_execution`, the same read this
     plugin already holds for `control`/`status` reads — no HubSpot credential needed,
     D-05: the plugin has never held one).
  2. Arm the enrichment workflow for exactly that batch (`n8n_arming.armed_window`,
     UNCHANGED — the same allowlist-scoped, guaranteed-disarm ceremony Phase 28 built).
  3. Dispatch that SAME batch itself, via the SAME external webhook POST the manual
     `enrich-records` skill already uses (`enrichment.build_envelope` /
     `dispatch_enrichment`) — arming a window with nothing sent through it grants
     nothing (`arm_for_dispatch`'s own docstring: the grant closes "the moment the
     dispatch returns").
  4. Disarm, guaranteed, even when the dispatch raises (`armed_window.__exit__`).

This gives the SJ-3 poller's identified backlog standing (but windowed, per-cycle) write
authority. It does not touch SJ-3's own in-n8n dispatch, which keeps running on its own
schedule and will keep reporting `write_blocked` for whatever it processes in the moments
this companion is not also mid-cycle — there is no dependency on SJ-3's own dispatch
succeeding for a write to land. Whichever cycle (SJ-3's internal one, or this companion's
external one) reaches a record first is the one that actually writes it; a record this
companion's read misses (because the maintenance workflow's most recent executions were
all sibling triggers — SJ-1/SJ-2/dedupe/review — rather than an SJ-3 tick) simply waits
for this companion's next cron-scheduled cycle, the same bounded latency model
docs/OPERATOR-VETO-REFRESH.md already documents for the refresh path generally ("up to 15
minutes, not immediate").

Bounded by design, not by convention: an empty batch is a no-op (`arm_for_dispatch`
itself refuses an empty allowlist — reused verbatim, never re-implemented here); the
arm/dispatch/disarm cycle costs at most one dispatch's wall-clock time and is never held
open longer than that. One invocation of `run_scheduled_arm_cycle` is one cycle, exactly
like `sweep_entry.run_sweep` is one sweep — a cron-adjacent wrapper supplies the repeat
(SWEEP-CRON-TEMPLATE.md precedent), not this module.

STILL GATED ON `ALLOW_N8N_ARM` (28-03's own kill switch, unchanged). An operator who has
not set it in the cron's environment gets `arm_refused` every cycle, at zero HTTP cost —
the safe default this whole design exists to preserve. Nothing here ever flips
`WRITE_SAFETY_DEFAULTS`'s build-time default; every write this module makes is scoped to
one batch and closes the moment the dispatch returns, exactly like the manual
`enrich-records` path Phase 28 already shipped.
"""
import requests

import config_gate
import enrichment
import executions_client
import n8n_arming
from report import _node_output_items, _run_data
from sweep_read import MAINTENANCE_WORKFLOW_NAME

ENRICHMENT_WORKFLOW_NAME = "LV Enrichment (Cloud template)"
SJ3_ROWS_NODE = "SJ-3 Extract Rows"

# How many of the maintenance workflow's own most recent executions to look back through
# for one that actually ran an SJ-3 tick. n8n gives each of that workflow's five schedule
# triggers (SJ-1/SJ-2/SJ-3/dedupe/review) its OWN execution containing only ITS OWN
# downstream nodes — a SJ-1/SJ-2/dedupe/review execution never carries "SJ-3 Extract Rows"
# in its runData at all. SJ-3 is that workflow's most frequent trigger (15 min, vs SJ-1's
# hourly and SJ-2's monthly), so five candidates comfortably covers one lookback window
# even when this companion's own cycle lands between ticks.
LOOKBACK_EXECUTIONS = 5

# Outcomes worth a non-zero exit from the CLI entrypoint — see `_cli_main`'s docstring.
# `arm_refused` is deliberately absent: an unarmed cycle (ALLOW_N8N_ARM unset) is this
# design's safe default, not a failure to page anyone about.
_FAILURE_OUTCOMES = frozenset({
    "not_configured", "workflow_not_found", "disarm_failed", "dispatch_failed",
})


def _outcome(kind, **fields):
    return {"outcome": kind, **fields}


def _resolve_workflow_ids(config, transport):
    """Both workflow ids this cycle needs, resolved by NAME (n8n assigns ids
    server-side, so nothing here may hardcode one)."""
    enrichment_id = executions_client.resolve_workflow_id(
        config, transport=transport, workflow_name=ENRICHMENT_WORKFLOW_NAME)
    maintenance_id = executions_client.resolve_workflow_id(
        config, transport=transport, workflow_name=MAINTENANCE_WORKFLOW_NAME)
    return enrichment_id, maintenance_id


def _matched_record_ids(execution):
    """The `hs_object_id`s SJ-3 matched in one execution.

    Returns `None` when this execution never ran SJ-3 at all (a sibling trigger's own
    run — see `LOOKBACK_EXECUTIONS`) — the caller's signal to try the next candidate.
    Returns `[]` (not `None`) when SJ-3 ran and matched nothing: a genuine empty poll,
    identical in meaning to SJ-3's own search returning zero rows.
    """
    run_data = _run_data(execution)
    if run_data is None:
        return None
    runs = run_data.get(SJ3_ROWS_NODE)
    if not isinstance(runs, list):
        return None

    ids = []
    for run in runs:
        for item in _node_output_items(run):
            if not isinstance(item, dict):
                continue
            record_id = (item.get("json") or {}).get("hs_object_id")
            if record_id not in (None, "") and str(record_id) not in ids:
                ids.append(str(record_id))
    return ids


def find_latest_sj3_batch(config, maintenance_workflow_id, transport,
                          lookback=LOOKBACK_EXECUTIONS):
    """The hs_object_ids of SJ-3's most recently completed tick, or `None` when no
    execution within the lookback window ran SJ-3 at all.

    Reads the maintenance workflow's OWN executions only (`executions_client.
    list_executions`, filtered by `workflowId`) — never the cross-workflow page
    `n8n_read.recent_executions` returns, which could just as easily surface a sibling
    workflow's run first. Newest first by `startedAt`, never assumed from list order
    (mirrors `executions_client.find_execution_for_dispatch`'s own defensiveness).
    """
    candidates = executions_client.list_executions(
        config, maintenance_workflow_id, transport=transport, limit=lookback)
    candidates = sorted(
        (c for c in candidates if isinstance(c, dict) and c.get("startedAt")),
        key=lambda c: c["startedAt"], reverse=True,
    )

    for candidate in candidates:
        execution_id = candidate.get("id")
        if execution_id is None:
            continue
        full = executions_client.get_execution(config, execution_id, transport=transport)
        record_ids = _matched_record_ids(full)
        if record_ids is not None:
            return {"execution_id": execution_id, "started_at": candidate.get("startedAt"),
                    "record_ids": record_ids}
    return None


def run_scheduled_arm_cycle(config, get_transport=requests.get, post_transport=None):
    """One bounded arm -> dispatch -> disarm cycle for SJ-3's currently-matched backlog.

    Returns an outcome dict; never raises for a routine no-op (nothing configured wrong,
    just nothing to do this cycle). See the module docstring for why this reads SJ-3's
    batch from n8n's own execution history rather than intercepting SJ-3's own internal
    dispatch — that interception point does not exist from outside n8n.
    """
    config_gate.require_capability(config, "scheduled-arm")
    post_transport = post_transport if post_transport is not None else requests

    enrichment_workflow_id, maintenance_workflow_id = _resolve_workflow_ids(
        config, get_transport)
    if enrichment_workflow_id is None or maintenance_workflow_id is None:
        return _outcome("workflow_not_found",
                        enrichment_workflow_id=enrichment_workflow_id,
                        maintenance_workflow_id=maintenance_workflow_id)

    batch = find_latest_sj3_batch(config, maintenance_workflow_id, get_transport)
    if batch is None:
        return _outcome("no_recent_sj3_tick")
    if not batch["record_ids"]:
        return _outcome("no_records_matched", execution_id=batch["execution_id"])

    record_ids = batch["record_ids"]
    # Built and validated BEFORE arming: a bad envelope must never arm a window it then
    # has nothing to send through (mirrors control_actions.execute_action's own ordering).
    providers = enrichment.resolve_providers(None, config)
    envelope = enrichment.build_envelope(
        {"record_ids": record_ids, "object_type": "companies"}, providers)

    dispatch_result = None
    try:
        with n8n_arming.armed_window(enrichment_workflow_id, record_ids, [], False,
                                     config, transport=post_transport) as window:
            dispatch_result = enrichment.dispatch_enrichment(
                envelope, True, config, transport=post_transport)
    except n8n_arming.ArmingRefused as refusal:
        return _outcome("arm_refused", detail=str(refusal), record_ids=record_ids,
                        execution_id=batch["execution_id"])
    except n8n_arming.DisarmFailed as failure:
        return _outcome("disarm_failed", record_ids=record_ids,
                        execution_id=batch["execution_id"], **failure.outcome)
    except enrichment.DispatchError as failure:
        # The disarm already ran — `armed_window.__exit__` fires before this `except`
        # is ever reached (guaranteed disarm on a dispatch failure, per the design
        # brief). This only stops an unattended cron cycle from crashing silently
        # (sweep_entry.py's own "a raised exception with nobody watching produces
        # nothing" reasoning — D-15 — applies here too).
        return _outcome("dispatch_failed", detail=str(failure), record_ids=record_ids,
                        execution_id=batch["execution_id"])

    return _outcome("dispatched", record_ids=record_ids, execution_id=batch["execution_id"],
                    arm=window.arm_result, disarm=window.disarm_result,
                    dispatch_result=dispatch_result)


def _load_config_no_migration():
    """Read-only config resolution — no sibling-scan-and-migrate, mirrors
    `sweep_entry._load_config_no_migration` for the same reason: this runs unattended,
    so the one irreversible operation `config_gate.load_config`'s default can perform
    (adopt-then-delete a sibling install's config) must never happen with nobody
    watching."""
    return config_gate.load_config(allow_migration=False)


def _cli_main(load_config=_load_config_no_migration, get_transport=requests.get,
              post_transport=None):
    """What `python3 scripts/scheduled_arm.py` prints — one cycle, JSON out, isolated
    from `__main__` so a test can drive it with an injected config loader (no subprocess,
    no touching the real gitignored operator.local.json)."""
    try:
        cfg = load_config()
    except config_gate.ConfigError as refusal:
        return _outcome("not_configured", detail=str(refusal))
    try:
        return run_scheduled_arm_cycle(cfg, get_transport=get_transport,
                                       post_transport=post_transport)
    except config_gate.ConfigError as refusal:
        return _outcome("not_configured", detail=str(refusal))


if __name__ == "__main__":
    import json
    import sys

    _result = _cli_main()
    print(json.dumps(_result))
    # Non-zero on anything a cron log/monitor should page on. `arm_refused` is excluded on
    # purpose — see `_FAILURE_OUTCOMES`'s own comment.
    sys.exit(1 if _result.get("outcome") in _FAILURE_OUTCOMES else 0)
