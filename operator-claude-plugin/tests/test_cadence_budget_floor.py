"""operator-claude-plugin/tests/test_cadence_budget_floor.py

Phase 45 Plan 02 (FLOOR-01, D-09/D-10) — the runtime cadence budget floor.

The incident this guards against (2026-08-10 USAGE.md fact-check): `n8n_cadence`'s
`cadence` control action reaches a live PUT with neither of Phase 44's tripwires
executing — `parse_cadence` accepts "every 30 seconds" as a legal, confirmable request,
and only a plain-language read-back plus the operator's own "yes" stands between it and
the backend. The 2026-08-09 runaway was this exact budget domain.

Task 1 covers the arithmetic: `interval_month_cost`, `schedule_month_cost`, and
`check_budget_floor`'s refusal shape. Task 2 extends this file with the single-shot
override.
"""
import n8n_cadence

CONFIG = {
    "n8n_monthly_execution_allowance": 2500,
    "n8n_schedule_floor_max_share": 0.25,
}


def _node(name, field, every, *, disabled=False, weekdays=None):
    entry = {"field": field, f"{field}Interval": every}
    if weekdays:
        entry["triggerOnWeekdays"] = list(weekdays)
    node = {
        "name": name,
        "type": "n8n-nodes-base.scheduleTrigger",
        "parameters": {"rule": {"interval": [entry]}},
    }
    if disabled:
        node["disabled"] = True
    return node


def _workflow(workflow_id, *nodes):
    return {"id": workflow_id, "name": f"wf-{workflow_id}", "nodes": list(nodes)}


# --- interval_month_cost -------------------------------------------------------------------

def test_minutes_hours_days_cost():
    assert n8n_cadence.interval_month_cost(
        [{"field": "minutes", "minutesInterval": 15}]) == 2880.0
    assert n8n_cadence.interval_month_cost(
        [{"field": "hours", "hoursInterval": 1}]) == 720.0
    assert n8n_cadence.interval_month_cost(
        [{"field": "days", "daysInterval": 1}]) == 30.0


def test_cron_expression_is_an_unknown_cost():
    assert n8n_cadence.interval_month_cost([{"field": "cronExpression"}]) is None


def test_five_weekdays_multiply_the_bare_weekly_base():
    bare = n8n_cadence.interval_month_cost([{"field": "weeks", "weeksInterval": 1}])
    five_days = n8n_cadence.interval_month_cost(
        [{"field": "weeks", "weeksInterval": 1, "triggerOnWeekdays": [1, 2, 3, 4, 5]}])
    assert five_days == bare * 5


# --- schedule_month_cost -------------------------------------------------------------------

def test_disabled_trigger_contributes_zero():
    with_one_disabled = [_workflow(
        "wf-1", _node("A", "days", 1), _node("B", "days", 1, disabled=True))]
    all_enabled = [_workflow("wf-1", _node("A", "days", 1), _node("B", "days", 1))]

    disabled_total = n8n_cadence.schedule_month_cost(
        with_one_disabled, "wf-1", "A", [{"field": "days", "daysInterval": 1}])
    enabled_total = n8n_cadence.schedule_month_cost(
        all_enabled, "wf-1", "A", [{"field": "days", "daysInterval": 1}])

    assert enabled_total - disabled_total == 30.0


def test_five_daily_triggers_then_target_swapped_to_hourly():
    items = [_workflow(
        "wf-1", _node("A", "days", 1), _node("B", "days", 1), _node("C", "days", 1),
        _node("D", "days", 1), _node("E", "days", 1))]

    baseline = n8n_cadence.schedule_month_cost(
        items, "wf-1", "A", [{"field": "days", "daysInterval": 1}])
    assert baseline == 150.0

    swapped = n8n_cadence.schedule_month_cost(
        items, "wf-1", "A", [{"field": "hours", "hoursInterval": 1}])
    assert swapped == 840.0


# --- check_budget_floor --------------------------------------------------------------------

def _five_hourly():
    return [_workflow(
        "wf-1", _node("A", "hours", 1), _node("B", "hours", 1), _node("C", "hours", 1),
        _node("D", "hours", 1), _node("E", "hours", 1))]


def test_five_hourly_triggers_refused_even_though_no_single_one_exceeds_the_allowance():
    items = _five_hourly()
    try:
        n8n_cadence.check_budget_floor(
            "wf-1", "A", [{"field": "hours", "hoursInterval": 1}], CONFIG, items)
        assert False, "expected a CadenceRefused"
    except n8n_cadence.CadenceRefused as refusal:
        assert "3600" in str(refusal)


def test_15_minute_request_over_the_ceiling_names_all_three_numbers():
    items = [_workflow("wf-1", _node("A", "days", 1))]
    try:
        n8n_cadence.check_budget_floor(
            "wf-1", "A", [{"field": "minutes", "minutesInterval": 15}], CONFIG, items)
        assert False, "expected a CadenceRefused"
    except n8n_cadence.CadenceRefused as refusal:
        text = str(refusal)
        for number in ("2880", "625", "2500"):
            assert number in text, text


def test_five_hourly_refusal_examples_contain_no_over_budget_recommendation():
    items = _five_hourly()
    try:
        n8n_cadence.check_budget_floor(
            "wf-1", "A", [{"field": "hours", "hoursInterval": 1}], CONFIG, items)
        assert False, "expected a CadenceRefused"
    except n8n_cadence.CadenceRefused as refusal:
        assert "every 15 minutes" not in " ".join(refusal.examples)
        assert "hourly" not in " ".join(refusal.examples)


def test_unreadable_workflow_list_refuses_and_override_does_not_help():
    interval = [{"field": "days", "daysInterval": 1}]
    for override in (False, True):
        try:
            n8n_cadence.check_budget_floor(
                "wf-1", "A", interval, CONFIG, None, override=override)
            assert False, "expected a CadenceRefused"
        except n8n_cadence.CadenceRefused:
            pass


def test_missing_allowance_key_names_it_and_never_the_value():
    items = [_workflow("wf-1", _node("A", "days", 1))]
    config = {"n8n_schedule_floor_max_share": 0.25}
    try:
        n8n_cadence.check_budget_floor(
            "wf-1", "A", [{"field": "days", "daysInterval": 1}], config, items)
        assert False, "expected a CadenceRefused"
    except n8n_cadence.CadenceRefused as refusal:
        assert "n8n_monthly_execution_allowance" in str(refusal)


def test_missing_share_key_names_it():
    items = [_workflow("wf-1", _node("A", "days", 1))]
    config = {"n8n_monthly_execution_allowance": 2500}
    try:
        n8n_cadence.check_budget_floor(
            "wf-1", "A", [{"field": "days", "daysInterval": 1}], config, items)
        assert False, "expected a CadenceRefused"
    except n8n_cadence.CadenceRefused as refusal:
        assert "n8n_schedule_floor_max_share" in str(refusal)


def test_daily_request_within_budget_returns_the_arithmetic_and_does_not_raise():
    items = [_workflow("wf-1", _node("A", "days", 1))]
    result = n8n_cadence.check_budget_floor(
        "wf-1", "A", [{"field": "days", "daysInterval": 1}], CONFIG, items)
    assert result["within"] is True
    assert result["overridden"] is False
    assert result["allowance"] == 2500
    assert result["share"] == 0.25
    assert result["ceiling"] == 625.0
