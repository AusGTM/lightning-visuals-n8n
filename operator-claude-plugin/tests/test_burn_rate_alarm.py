"""operator-claude-plugin/tests/test_burn_rate_alarm.py

Phase 45 — the burn-rate alarm (ALARM-01..04) and the time-windowed execution lookback
that backs it (D-08, LOOK-01).

Task 1: the tracer — a synthetic runaway execution history (the 2026-08-09 shape, ~253
executions/hour, flat) through the real `sweep_entry.run_sweep`, end to end, to one
correctly-attributed notice; and the quiet-history silence counterpart.

Task 2 extends this file with the degraded branches (not-configured, unreadable, an
honest span) and the precision/threshold edge cases. Task 3 extends it with LOOK-01's
proof that the same windowed read reaches the pre-existing stuck/failed-run conditions,
and the workflow-name backfill.
"""
from datetime import datetime, timedelta, timezone

import error_table
import n8n_read
import sweep_conditions
import sweep_entry
import sweep_read

SWEEP_CONFIG = {
    "n8n_url": "https://fake-tenant.n8n.cloud",
    "n8n_api_key": "fake-key-for-tests",
    "webhook_secret": "fake-secret-for-tests",
    "n8n_monthly_execution_allowance": 2500,
}

# The reference "now" every fixture here is anchored to — the incident date itself.
NOW = datetime(2026, 8, 9, 12, 0, 0, tzinfo=timezone.utc)

# D-03: every execution counts, all modes, all workflows. Mixed on purpose so a filter
# accidentally introduced later (mode or workflow) fails a test here rather than shipping
# silently.
_MODES = ("manual", "webhook", "trigger", "internal")
_WORKFLOW_IDS = ("wf-a", "wf-b", "wf-c")


def _iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _synthetic_history(count, span_hours, now=NOW, status="success"):
    """`count` executions spread evenly over the last `span_hours`, newest first,
    mixing execution modes and workflow ids (D-03)."""
    history = []
    for i in range(count):
        offset_hours = (span_hours * i / (count - 1)) if count > 1 else 0.0
        started = now - timedelta(hours=offset_hours)
        workflow_id = _WORKFLOW_IDS[i % len(_WORKFLOW_IDS)]
        history.append({
            "id": f"e-{i}",
            "workflowId": workflow_id,
            "mode": _MODES[i % len(_MODES)],
            "status": status,
            "startedAt": _iso(started),
            "stoppedAt": _iso(started + timedelta(seconds=5)),
            "finished": True,
            "workflowData": {"name": f"Workflow {workflow_id}"},
        })
    return history


def _post_ok(url, headers=None, json=None, timeout=None):
    class _R:
        status_code = 200

        @staticmethod
        def json():
            return {"queues": {}, "providers": {}}
    return _R()


# --- Task 1: the tracer ------------------------------------------------------------------


def test_a_runaway_history_produces_exactly_one_burn_rate_notice(stub_get_transport_factory):
    """The 2026-08-09 shape: 1,012 executions over ~4 hours (~253/hour), against a
    2,500/month allowance."""
    history = _synthetic_history(1012, span_hours=4.0)
    get = stub_get_transport_factory([{"data": history}])

    notices = sweep_entry.run_sweep(SWEEP_CONFIG, get_transport=get,
                                    post_transport=_post_ok, now=NOW)

    assert len(notices) == 1
    notice = notices[0]
    assert notice["condition"] == sweep_conditions.BURN_RATE
    detail = notice["detail"]
    assert "per hour" in detail
    assert "hours" in detail
    assert "2500" in detail
    assert "not a total for this month" in detail


def test_the_runaway_history_mixes_every_mode_and_workflow_and_all_of_it_counts(
        stub_get_transport_factory):
    """D-03: no mode and no workflow is filtered out of the rate."""
    history = _synthetic_history(1012, span_hours=4.0)
    modes_present = {item["mode"] for item in history}
    workflow_ids_present = {item["workflowId"] for item in history}
    assert len(modes_present) > 1, "fixture must mix modes for this test to mean anything"
    assert len(workflow_ids_present) > 1, "fixture must mix workflows too"

    get = stub_get_transport_factory([{"data": history}])
    gathered = sweep_read.gather(SWEEP_CONFIG, get_transport=get, post_transport=_post_ok,
                                 now=NOW)
    assert gathered["executions"]["window"]["count_in_window"] == len(history)


def test_a_quiet_history_produces_no_notice_at_all(stub_get_transport_factory):
    """3 executions in 24 hours — well under the idle floor — must be silent."""
    history = _synthetic_history(3, span_hours=24.0)
    get = stub_get_transport_factory([{"data": history}])

    notices = sweep_entry.run_sweep(SWEEP_CONFIG, get_transport=get,
                                    post_transport=_post_ok, now=NOW)
    assert notices == []


def test_error_table_translates_the_burn_reason():
    fired = sweep_conditions.check_burn_rate(
        {"available": True, "summaries": [], "window": {
            "count_in_window": 2000, "observed_span_hours": 4.0,
            "covers_full_window": False, "truncated_by_page_cap": False}},
        {"key": "n8n_monthly_execution_allowance", "allowance": 2500,
         "threshold_key": "burn_rate_alarm_threshold", "threshold": None},
    )
    assert fired
    result = error_table.translate(fired[0]["reason"])
    assert result["matched"] is True
    assert result["is_interpretation"] is False
    assert result["cause"] == "burn_rate"


def test_error_table_still_matches_the_burn_reason_when_its_numbers_include_400():
    """The prepended row must precede the bare-status-code rows (T-45-05)."""
    fired = sweep_conditions.check_burn_rate(
        {"available": True, "summaries": [], "window": {
            "count_in_window": 1000, "observed_span_hours": 1.0,
            "covers_full_window": False, "truncated_by_page_cap": False}},
        {"key": "n8n_monthly_execution_allowance", "allowance": 400,
         "threshold_key": "burn_rate_alarm_threshold", "threshold": 1.0},
    )
    reason = fired[0]["reason"]
    assert "400" in reason, "fixture must actually embed the literal 400 for this test to mean anything"
    assert error_table.translate(reason)["cause"] == "burn_rate"


def test_recent_executions_and_its_page_limit_are_untouched():
    """status.py:159 still calls recent_executions with EXECUTIONS_PAGE_LIMIT — this
    plan adds a windowed read alongside it, never removes the interactive one."""
    assert n8n_read.EXECUTIONS_PAGE_LIMIT == 100
    assert callable(n8n_read.recent_executions)


# --- direct unit coverage of executions_in_window's own boundary contract -----------------


def test_an_execution_exactly_at_the_cutoff_counts_one_a_second_older_does_not(
        stub_get_transport_factory):
    at_cutoff = _iso(NOW - timedelta(hours=24))
    one_second_older = (NOW - timedelta(hours=24) - timedelta(seconds=1)).strftime(
        "%Y-%m-%dT%H:%M:%S.000Z")

    items = [
        {"id": "e-at-cutoff", "workflowId": "wf-a", "status": "success",
         "startedAt": at_cutoff, "stoppedAt": at_cutoff, "finished": True},
        {"id": "e-older", "workflowId": "wf-a", "status": "success",
         "startedAt": one_second_older, "stoppedAt": one_second_older, "finished": True},
    ]
    get = stub_get_transport_factory([{"data": items}])
    window = n8n_read.executions_in_window(SWEEP_CONFIG, transport=get, now=NOW)

    assert window["count_in_window"] == 1, "only the at-cutoff item should count"


def test_observed_span_hours_is_floored_never_zero_or_negative(stub_get_transport_factory):
    """A single execution a few seconds old must not make the rate division raise or
    produce infinity — floored at MIN_OBSERVED_SPAN_HOURS."""
    just_now = (NOW - timedelta(seconds=5)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    items = [{"id": "e-fresh", "workflowId": "wf-a", "status": "success",
             "startedAt": just_now, "stoppedAt": just_now, "finished": True}]
    get = stub_get_transport_factory([{"data": items}])
    window = n8n_read.executions_in_window(SWEEP_CONFIG, transport=get, now=NOW)

    assert window["observed_span_hours"] >= n8n_read.MIN_OBSERVED_SPAN_HOURS
    assert window["observed_span_hours"] > 0


# --- Task 2: the branches that must never be silent ---------------------------------------

_RUNAWAY_WINDOW = {
    "window_hours": 24.0, "count_in_window": 6000, "observed_span_hours": 4.0,
    "covers_full_window": False, "truncated_by_page_cap": False,
}
_HEALTHY_WINDOW = {
    "window_hours": 24.0, "count_in_window": 2, "observed_span_hours": 24.0,
    "covers_full_window": True, "truncated_by_page_cap": False,
}
_BUDGET = {"key": "n8n_monthly_execution_allowance", "allowance": 2500,
          "threshold_key": "burn_rate_alarm_threshold", "threshold": None}


def test_missing_allowance_fires_not_configured_naming_the_key_and_stops_there():
    fired = sweep_conditions.check_burn_rate(
        {"available": True, "summaries": [], "window": _RUNAWAY_WINDOW},
        {"key": "n8n_monthly_execution_allowance", "allowance": None,
         "threshold_key": "burn_rate_alarm_threshold", "threshold": None})
    assert len(fired) == 1
    assert fired[0]["condition"] == sweep_conditions.BURN_RATE_NOT_CONFIGURED
    assert "n8n_monthly_execution_allowance" in fired[0]["reason"]


def test_missing_allowance_alongside_a_stuck_run_fires_both_via_evaluate(
        stub_get_transport_factory):
    """D-05: the rest of the sweep still runs."""
    stuck = _synthetic_history(1, span_hours=0.01)
    stuck[0]["status"] = "running"
    stuck[0].pop("stoppedAt", None)
    stuck[0]["startedAt"] = _iso(NOW - timedelta(minutes=45))
    config = {k: v for k, v in SWEEP_CONFIG.items() if k != "n8n_monthly_execution_allowance"}

    get = stub_get_transport_factory([{"data": stuck}])
    gathered = sweep_read.gather(config, get_transport=get, post_transport=_post_ok, now=NOW)
    fired = sweep_conditions.evaluate(gathered)
    conditions = {c["condition"] for c in fired}
    assert sweep_conditions.BURN_RATE_NOT_CONFIGURED in conditions
    assert sweep_conditions.STUCK in conditions


def test_allowance_present_but_executions_unreadable_fires_unreadable():
    fired = sweep_conditions.check_burn_rate(
        {"available": False, "summaries": [], "window": None}, _BUDGET)
    assert len(fired) == 1
    assert fired[0]["condition"] == sweep_conditions.BURN_RATE_UNREADABLE


def test_projection_exactly_at_ceiling_does_not_fire_one_execution_more_does():
    # allowance=2500, threshold=1.0 -> ceiling 2500/month = 2500/720 per hour.
    # observed_span_hours=1.0 makes count_in_window == rate_per_hour numerically, so
    # rate*720 == ceiling exactly when count_in_window == ceiling/720.
    exact_count = 2500 / 720.0
    at_ceiling = dict(_RUNAWAY_WINDOW, count_in_window=exact_count, observed_span_hours=1.0)
    assert sweep_conditions.check_burn_rate(
        {"available": True, "summaries": [], "window": at_ceiling}, _BUDGET) == []

    over = dict(at_ceiling, count_in_window=exact_count + 0.4 / 720.0)
    fired = sweep_conditions.check_burn_rate(
        {"available": True, "summaries": [], "window": over}, _BUDGET)
    assert len(fired) == 1
    assert fired[0]["condition"] == sweep_conditions.BURN_RATE


def test_threshold_of_2_raises_the_fire_point():
    # allowance=2500 -> ceiling(1x)=2500/month, ceiling(2x)=5000/month. count=5 over a
    # 1-hour span projects to 5*720=3600/month: over the 1x ceiling, under the 2x one.
    window = dict(_RUNAWAY_WINDOW, count_in_window=5, observed_span_hours=1.0)
    budget_1x = dict(_BUDGET, threshold=1.0)
    budget_2x = dict(_BUDGET, threshold=2.0)
    fired_1x = sweep_conditions.check_burn_rate(
        {"available": True, "summaries": [], "window": window}, budget_1x)
    fired_2x = sweep_conditions.check_burn_rate(
        {"available": True, "summaries": [], "window": window}, budget_2x)
    assert fired_1x and fired_1x[0]["condition"] == sweep_conditions.BURN_RATE
    assert fired_2x == [], "doubling the threshold must raise the fire point"


def test_a_blank_zero_negative_or_non_numeric_threshold_falls_back_to_default():
    window = dict(_RUNAWAY_WINDOW, count_in_window=3000, observed_span_hours=1.0)
    baseline = sweep_conditions.check_burn_rate(
        {"available": True, "summaries": [], "window": window},
        dict(_BUDGET, threshold=None))
    for bad in ("", 0, -1, "abc"):
        result = sweep_conditions.check_burn_rate(
            {"available": True, "summaries": [], "window": window},
            dict(_BUDGET, threshold=bad))
        assert bool(result) == bool(baseline), f"threshold={bad!r} must not raise or diverge"


def test_a_shrunken_window_from_pruning_reads_differently_than_a_read_bound_truncation():
    pruned = dict(_RUNAWAY_WINDOW, covers_full_window=False, truncated_by_page_cap=False,
                  observed_span_hours=3.1)
    capped = dict(_RUNAWAY_WINDOW, covers_full_window=False, truncated_by_page_cap=True,
                  observed_span_hours=3.1)

    pruned_reason = sweep_conditions.check_burn_rate(
        {"available": True, "summaries": [], "window": pruned}, _BUDGET)[0]["reason"]
    capped_reason = sweep_conditions.check_burn_rate(
        {"available": True, "summaries": [], "window": capped}, _BUDGET)[0]["reason"]

    assert "3.1 hours" in pruned_reason and "3.1 hours" in capped_reason
    assert "pruned" in pruned_reason
    assert "own execution read bound" in capped_reason
    assert "pruned" not in capped_reason
    assert pruned_reason != capped_reason


def test_error_table_translates_the_not_configured_and_unreadable_reasons():
    not_configured = sweep_conditions.check_burn_rate(
        {"available": True, "summaries": [], "window": _RUNAWAY_WINDOW},
        {"key": "n8n_monthly_execution_allowance", "allowance": "", "threshold_key": "x",
         "threshold": None})[0]["reason"]
    unreadable = sweep_conditions.check_burn_rate(
        {"available": False, "summaries": [], "window": None}, _BUDGET)[0]["reason"]

    for reason, expected_cause in (
        (not_configured, "burn_rate_not_configured"),
        (unreadable, "burn_rate_unreadable"),
    ):
        result = error_table.translate(reason)
        assert result["matched"] is True
        assert result["cause"] == expected_cause
        assert result["who_can_fix"] == "admin"
        assert result["is_interpretation"] is False


def test_driving_run_sweep_twice_over_identical_inputs_produces_identical_notices(
        stub_get_transport_factory):
    """Concurrency backstop: two sweeps share no mutable state. Two FRESH transports —
    a `_StubGetTransport` pops its scripted payloads, so reusing one across two calls
    would prove nothing about shared state and everything about running out of script."""
    history = _synthetic_history(1012, span_hours=4.0)

    get_a = stub_get_transport_factory([{"data": history}])
    get_b = stub_get_transport_factory([{"data": history}])

    notices_a = sweep_entry.run_sweep(SWEEP_CONFIG, get_transport=get_a,
                                      post_transport=_post_ok, now=NOW)
    notices_b = sweep_entry.run_sweep(SWEEP_CONFIG, get_transport=get_b,
                                      post_transport=_post_ok, now=NOW)
    assert notices_a == notices_b


# --- Task 3: LOOK-01 — the window reaches the pre-existing conditions, and workflows
# get named --------------------------------------------------------------------------

_LOOK01_WORKFLOW_ID = "wf-look01"
_LOOK01_WORKFLOW_NAME = "LV Enrichment (Cloud template)"


def _execution_item(execution_id, *, status, started_ago_hours, stopped_ago_minutes=None,
                    workflow_id=_LOOK01_WORKFLOW_ID, workflow_name=_LOOK01_WORKFLOW_NAME):
    """One raw executions-collection item, `started_ago_hours` before NOW. Mirrors
    conftest's own `_execution` helper but parameterised in hours (LOOK-01's fixtures
    need a 30-hour-old start, well past conftest's minutes-scale fixtures)."""
    started = NOW - timedelta(hours=started_ago_hours)
    item = {
        "id": execution_id,
        "workflowId": workflow_id,
        "status": status,
        "startedAt": _iso(started),
        "finished": status not in ("running", "new", "waiting"),
    }
    if workflow_name is not None:
        item["workflowData"] = {"name": workflow_name}
    if stopped_ago_minutes is not None:
        item["stoppedAt"] = _iso(NOW - timedelta(minutes=stopped_ago_minutes))
    return item


def test_a_terminal_failure_that_ended_outside_the_window_ages_out(stub_get_transport_factory):
    """RB-8: a failure whose cause was fixed hours ago must stop being reported."""
    stale = _execution_item("e-stale", status="error", started_ago_hours=30.1,
                            stopped_ago_minutes=30 * 60)
    get = stub_get_transport_factory([{"data": [stale]}, {"data": []}])
    gathered = sweep_read.gather(SWEEP_CONFIG, get_transport=get, post_transport=_post_ok,
                                 now=NOW)
    assert sweep_conditions.check_failed_run(gathered["executions"]["summaries"]) == []


def test_the_same_failure_with_a_recent_stop_time_still_fires(stub_get_transport_factory):
    """Same 30-hour-old start, but it ENDED 20 minutes ago — still fires."""
    recent_stop = _execution_item("e-recent-stop", status="error", started_ago_hours=30.0,
                                  stopped_ago_minutes=20)
    get = stub_get_transport_factory([{"data": [recent_stop]}, {"data": []}])
    gathered = sweep_read.gather(SWEEP_CONFIG, get_transport=get, post_transport=_post_ok,
                                 now=NOW)
    fired = sweep_conditions.check_failed_run(gathered["executions"]["summaries"])
    assert len(fired) == 1
    assert fired[0]["execution_id"] == "e-recent-stop"


def test_an_in_flight_run_started_outside_the_window_is_retained_and_fires_stuck(
        stub_get_transport_factory):
    """The window must not blind the sweep to its own headline case: an in-flight run
    is current state, never age-filtered out of `items`."""
    old_running = _execution_item("e-old-running", status="running", started_ago_hours=30.0)
    get = stub_get_transport_factory([{"data": [old_running]}, {"data": []}])
    gathered = sweep_read.gather(SWEEP_CONFIG, get_transport=get, post_transport=_post_ok,
                                 now=NOW)
    summaries = gathered["executions"]["summaries"]
    assert any(s["execution_id"] == "e-old-running" for s in summaries)
    fired = sweep_conditions.check_stuck(summaries)
    assert any(c["execution_id"] == "e-old-running" and c["condition"] == sweep_conditions.STUCK
              for c in fired)


def test_a_workflow_name_absent_from_the_raw_item_is_backfilled_from_list_workflows(
        stub_get_transport_factory):
    no_name = _execution_item("e-unnamed", status="error", started_ago_hours=0.5,
                              stopped_ago_minutes=10, workflow_name=None,
                              workflow_id="wf-backfill")
    workflows_payload = [{"id": "wf-backfill", "name": "Backfilled Workflow Name", "nodes": []}]
    get = stub_get_transport_factory([{"data": [no_name]}, {"data": workflows_payload}])
    gathered = sweep_read.gather(SWEEP_CONFIG, get_transport=get, post_transport=_post_ok,
                                 now=NOW)
    fired = sweep_conditions.check_failed_run(gathered["executions"]["summaries"])
    assert len(fired) == 1
    assert "Backfilled Workflow Name" in fired[0]["reason"]


def test_list_workflows_returning_none_backfills_nothing_but_does_not_crash(
        stub_get_transport_factory):
    no_name = _execution_item("e-unnamed-2", status="error", started_ago_hours=0.5,
                              stopped_ago_minutes=10, workflow_name=None,
                              workflow_id="wf-unreadable")
    # Only ONE payload: the executions call. The workflows GET falls through to the
    # stub's default ({}), which n8n_read.list_workflows reads as unreadable (None).
    get = stub_get_transport_factory([{"data": [no_name]}])
    gathered = sweep_read.gather(SWEEP_CONFIG, get_transport=get, post_transport=_post_ok,
                                 now=NOW)
    assert gathered["workflows"]["available"] is False
    fired = sweep_conditions.check_failed_run(gathered["executions"]["summaries"])
    assert len(fired) == 1
    assert "an unnamed workflow" in fired[0]["reason"]


def test_maintenance_execution_still_resolves_after_the_backfill(stub_get_transport_factory):
    maintenance = _execution_item("e-maint", status="success", started_ago_hours=0.2,
                                  stopped_ago_minutes=5, workflow_id="wf-maintenance",
                                  workflow_name=sweep_read.MAINTENANCE_WORKFLOW_NAME)
    maintenance["data"] = {"resultData": {"runData": {}}}
    get = stub_get_transport_factory([
        {"data": [maintenance]},
        {"data": []},
        maintenance,  # the gated get_execution response for the maintenance run
    ])
    gathered = sweep_read.gather(SWEEP_CONFIG, get_transport=get, post_transport=_post_ok,
                                 now=NOW)
    assert gathered["maintenance_errors"]["available"] is True
