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
    assert "hour span" in detail
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
    import n8n_read
    assert n8n_read.EXECUTIONS_PAGE_LIMIT == 100
    assert callable(n8n_read.recent_executions)
