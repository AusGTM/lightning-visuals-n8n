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
import n8n_control
import control_actions

CONFIG = {
    "n8n_monthly_execution_allowance": 2500,
    "n8n_schedule_floor_max_share": 0.25,
}

STRICT_CONFIG = {
    "n8n_url": "https://fake-tenant.n8n.cloud",
    "n8n_api_key": "fake-n8n-api-key-for-tests-only",
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


def test_a_bool_allowance_value_refuses_as_missing_not_as_a_real_1_0():
    """WR-03: bool is an int subclass, so float(True) == 1.0 -- a misconfigured
    `"n8n_monthly_execution_allowance": true` must refuse the same way a missing key
    does, never silently authorize against an allowance of 1.0."""
    items = [_workflow("wf-1", _node("A", "days", 1))]
    config = {"n8n_monthly_execution_allowance": True, "n8n_schedule_floor_max_share": 0.25}
    try:
        n8n_cadence.check_budget_floor(
            "wf-1", "A", [{"field": "days", "daysInterval": 1}], config, items)
        assert False, "expected a CadenceRefused"
    except n8n_cadence.CadenceRefused as refusal:
        assert "n8n_monthly_execution_allowance" in str(refusal)


def test_daily_request_within_budget_returns_the_arithmetic_and_does_not_raise():
    items = [_workflow("wf-1", _node("A", "days", 1))]
    result = n8n_cadence.check_budget_floor(
        "wf-1", "A", [{"field": "days", "daysInterval": 1}], CONFIG, items)
    assert result["within"] is True
    assert result["overridden"] is False
    assert result["allowance"] == 2500
    assert result["share"] == 0.25
    assert result["ceiling"] == 625.0


# =============================================================================================
# Task 2 — the single-shot override
# =============================================================================================

def test_budget_floor_override_taken_matches_the_exact_normalised_phrase_only():
    assert n8n_cadence.budget_floor_override_taken("Override The Budget Floor") is True
    assert n8n_cadence.budget_floor_override_taken(
        "  override   the budget floor ") is True

    assert n8n_cadence.budget_floor_override_taken(
        "please override the budget floor now") is False
    assert n8n_cadence.budget_floor_override_taken("") is False
    assert n8n_cadence.budget_floor_override_taken(None) is False
    assert n8n_cadence.budget_floor_override_taken(123) is False


BUDGET_WORKFLOW_ID = "wf-budget-1"
BUDGET_NODE_NAME = "Nightly Sweep"


def _budget_workflow(*, active=False):
    return {
        "id": BUDGET_WORKFLOW_ID, "name": "Budget Test Workflow", "active": active,
        "settings": {}, "connections": {},
        "nodes": [
            {"name": BUDGET_NODE_NAME, "type": "n8n-nodes-base.scheduleTrigger",
             "parameters": {"rule": {"interval": [
                 {"field": "days", "daysInterval": 1}]}}},
        ],
    }


def _budget_workflow_items_response():
    return {"data": [_budget_workflow()]}


def _retimed_budget_workflow():
    workflow = _budget_workflow()
    for node in workflow["nodes"]:
        if node["name"] == BUDGET_NODE_NAME:
            node["parameters"]["rule"]["interval"] = [
                {"field": "minutes", "minutesInterval": 15}]
    return workflow


def _over_budget_request(**extra):
    return {"kind": "cadence", "workflow_id": BUDGET_WORKFLOW_ID,
           "node_name": BUDGET_NODE_NAME, "phrase": "every 15 minutes", **extra}


def test_plan_action_refuses_over_budget_and_names_the_override_phrase(
        stub_module_transport_factory):
    transport = stub_module_transport_factory(
        [_budget_workflow(), _budget_workflow_items_response()])

    result = control_actions.plan_action(_over_budget_request(), STRICT_CONFIG,
                                         transport=transport)

    assert result["outcome"] == control_actions.REFUSED
    text = result["detail"]
    for number in ("2880", "625", "2500"):
        assert number in text, text
    assert n8n_cadence.BUDGET_FLOOR_OVERRIDE_PHRASE in text


def test_the_single_shot_override_end_to_end_then_refuses_again(
        stub_module_transport_factory):
    plan_transport = stub_module_transport_factory(
        [_budget_workflow(), _budget_workflow_items_response()])

    proposal = control_actions.plan_action(
        _over_budget_request(
            budget_floor_override_phrase=n8n_cadence.BUDGET_FLOOR_OVERRIDE_PHRASE),
        STRICT_CONFIG, transport=plan_transport)

    assert "outcome" not in proposal, proposal
    assert proposal["budget_floor"]["overridden"] is True
    consequence = proposal["consequence"]
    for number in ("2880", "625", "2500"):
        assert number in consequence, consequence
    assert "dispatch cap" in consequence

    execute_transport = stub_module_transport_factory([
        _budget_workflow_items_response(),   # set_cadence's own floor re-check
        _budget_workflow(),                  # apply_mutation's fetch
        {},                                  # the PUT
        _retimed_budget_workflow(),          # read-back
    ])
    result = control_actions.execute_action(proposal, "yes", STRICT_CONFIG,
                                            transport=execute_transport)
    assert result["outcome"] == n8n_control.VERIFIED

    # Single-shot: the override did NOT persist. A fresh over-budget request with no
    # phrase refuses again, with the same arithmetic.
    second_transport = stub_module_transport_factory(
        [_budget_workflow(), _budget_workflow_items_response()])
    second = control_actions.plan_action(_over_budget_request(), STRICT_CONFIG,
                                         transport=second_transport)
    assert second["outcome"] == control_actions.REFUSED
    for number in ("2880", "625", "2500"):
        assert number in second["detail"], second["detail"]


def test_set_cadence_direct_call_refuses_even_after_a_prior_overridden_call(
        stub_module_transport_factory):
    """A direct caller that forgets `budget_floor_override` gets the gate, not a bypass —
    the override never persists across calls in the same process."""
    transport = stub_module_transport_factory([_budget_workflow_items_response()])
    try:
        n8n_cadence.set_cadence(
            BUDGET_WORKFLOW_ID, BUDGET_NODE_NAME,
            [{"field": "minutes", "minutesInterval": 15}], STRICT_CONFIG,
            transport=transport, budget_floor_override=False)
        assert False, "expected a CadenceRefused"
    except n8n_cadence.CadenceRefused:
        pass


def test_override_phrase_does_not_help_when_the_workflow_list_is_unreadable(
        stub_module_transport_factory):
    transport = stub_module_transport_factory([_budget_workflow(), {}])

    result = control_actions.plan_action(
        _over_budget_request(
            budget_floor_override_phrase=n8n_cadence.BUDGET_FLOOR_OVERRIDE_PHRASE),
        STRICT_CONFIG, transport=transport)

    assert result["outcome"] == control_actions.REFUSED
