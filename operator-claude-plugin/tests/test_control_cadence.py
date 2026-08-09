"""28-04 — cadence as meaning, never as syntax.

The binding constraint under test: schedule-expression syntax never reaches the operator,
in either direction. Everything else here serves that, plus D-10's "refuse rather than
guess" and the field-level narrowing that keeps re-timing a job separate from switching it
off.
"""
import copy
import json
import re
from pathlib import Path

import pytest

import n8n_cadence
import n8n_control

REPO_ROOT = Path(__file__).resolve().parents[2]
MAINTENANCE = REPO_ROOT / "n8n" / "wf_scheduled_maintenance_cloud.json"
WORKFLOW_ID = "wf-maint-1"

# A whitespace-separated field expression: digits, asterisks, slashes, commas, hyphens.
# Nothing the description layer emits may match this.
FIELD_EXPRESSION = re.compile(r"^[\d*/,\-]+(\s+[\d*/,\-]+)+$")


def _maintenance():
    """The committed artifact, marked active — which is how it is deployed (confirmed live
    2026-07-31, workflow 1fXPuIabz3RsAHgn, `active: true`). The committed JSON carries no
    `active` key, and without it `apply_mutation` correctly SKIPS the deactivate/activate
    bracket, so a fixture left inactive would silently exercise a different call sequence
    than production."""
    workflow = json.loads(MAINTENANCE.read_text())
    workflow["active"] = True
    return workflow


def _trigger_names():
    return n8n_cadence.schedule_trigger_nodes(_maintenance())


# --- read + describe --------------------------------------------------------------------

def test_every_deployed_schedule_trigger_describes_as_a_sentence():
    workflow = _maintenance()
    names = n8n_cadence.schedule_trigger_nodes(workflow)
    assert len(names) == 5, f"expected the five deployed triggers, found {names}"

    for name in names:
        sentence = n8n_cadence.describe_cadence(n8n_cadence.read_cadence(workflow, name))
        assert sentence and sentence != "no schedule is set", name
        assert not FIELD_EXPRESSION.match(sentence), f"{name} described with syntax"


def test_reading_an_unknown_node_lists_the_actual_trigger_names():
    """A typo is the most likely operator-facing failure; a bare KeyError teaches nothing."""
    with pytest.raises(n8n_cadence.CadenceRefused) as excinfo:
        n8n_cadence.read_cadence(_maintenance(), "Reviw Trigger")
    message = str(excinfo.value)
    for name in _trigger_names():
        assert name in message


@pytest.mark.parametrize("interval,expected", [
    ([{"field": "minutes", "minutesInterval": 15}], "every 15 minutes"),
    ([{"field": "hours", "hoursInterval": 1}], "once an hour"),
    ([{"field": "months", "monthsInterval": 1}], "once a month"),
    ([{"field": "weeks", "weeksInterval": 1}], "once a week"),
    ([{"field": "days", "daysInterval": 1}], "once a day"),
])
def test_the_deployed_shapes_render_in_plain_language(interval, expected):
    assert n8n_cadence.describe_cadence(interval) == expected


def test_a_multi_entry_interval_renders_every_entry():
    rendered = n8n_cadence.describe_cadence([
        {"field": "weeks", "weeksInterval": 1, "triggerOnWeekdays": [1, 2, 3, 4, 5],
         "triggerAtHour": 9},
        {"field": "weeks", "weeksInterval": 1, "triggerOnWeekdays": [1, 2, 3, 4, 5],
         "triggerAtHour": 17},
    ])
    assert "9:00am" in rendered and "5:00pm" in rendered
    assert "weekday" in rendered


def test_no_description_the_mapping_table_can_produce_contains_expression_syntax():
    """Iterated over the whole table, not spot-checked."""
    for field, companion in n8n_cadence.SUPPORTED_FIELDS.items():
        for every in (1, 2, 15):
            entry = {"field": field, companion: every}
            if field == "weeks":
                entry["triggerOnWeekdays"] = [1, 2, 3, 4, 5]
            if field in ("days", "weeks", "months"):
                entry["triggerAtHour"] = 9
                entry["triggerAtMinute"] = 30
            if field == "months":
                entry["triggerAtDayOfMonth"] = 3
            rendered = n8n_cadence.describe_cadence([entry])
            assert not FIELD_EXPRESSION.match(rendered), f"{field}: {rendered}"
            assert "*" not in rendered, f"{field}: {rendered}"


def test_a_hand_edited_cron_node_is_described_without_showing_the_syntax():
    """The module never emits one, but a node edited in the n8n UI can carry one — and
    showing it raw would break D-09 exactly where it matters most."""
    rendered = n8n_cadence.describe_cadence(
        [{"field": "cronExpression", "expression": "0 9 * * 1-5"}])
    assert "0 9" not in rendered and "*" not in rendered
    assert "n8n directly" in rendered


# --- parse or refuse ----------------------------------------------------------------------

def test_hourly():
    assert n8n_cadence.parse_cadence("hourly") == [{"field": "hours", "hoursInterval": 1}]


def test_every_15_minutes():
    assert n8n_cadence.parse_cadence("every 15 minutes") == \
        [{"field": "minutes", "minutesInterval": 15}]


def test_every_weekday_at_two_times_yields_two_weeks_entries():
    """D-08's own example. rule.interval is an ARRAY — two entries, not one expression."""
    parsed = n8n_cadence.parse_cadence("every weekday at 9am and 5pm")

    assert len(parsed) == 2
    assert all(entry["field"] == "weeks" for entry in parsed)
    assert [entry["triggerAtHour"] for entry in parsed] == [9, 17]
    assert all(entry["triggerOnWeekdays"] == [1, 2, 3, 4, 5] for entry in parsed)


def test_a_phrase_needing_the_expression_field_is_refused_not_expressed():
    with pytest.raises(n8n_cadence.CadenceRefused) as excinfo:
        n8n_cadence.parse_cadence("the third Tuesday of every month")
    assert "raw schedule syntax" in excinfo.value.reason
    assert len(excinfo.value.examples) >= 3


def test_input_that_is_already_expression_syntax_is_refused():
    with pytest.raises(n8n_cadence.CadenceRefused) as excinfo:
        n8n_cadence.parse_cadence("0 9 * * 1-5")
    assert "your own words" in excinfo.value.reason


def test_an_ambiguous_phrase_is_refused_with_at_least_three_examples():
    with pytest.raises(n8n_cadence.CadenceRefused) as excinfo:
        n8n_cadence.parse_cadence("sometimes, when it seems useful")
    assert len(excinfo.value.examples) >= 3
    assert excinfo.value.reason


def test_no_refusal_is_a_bare_none():
    for phrase in ("", None, "gibberish nonsense", "0 9 * * 1-5"):
        with pytest.raises(n8n_cadence.CadenceRefused) as excinfo:
            n8n_cadence.parse_cadence(phrase)
        assert excinfo.value.reason
        assert excinfo.value.examples


def test_a_parsed_phrase_round_trips_back_into_plain_language():
    """The two halves confirmation needs: the parse, and what the parse MEANS."""
    described = n8n_cadence.describe_cadence(n8n_cadence.parse_cadence("every 15 minutes"))
    assert described == "every 15 minutes"


# --- per-job enable/disable (D-25) ---------------------------------------------------------

def test_a_node_with_no_disabled_key_reads_as_enabled_and_disabling_adds_it():
    """None of the five committed triggers carries the key, so a toggle assuming its
    presence would raise on every real node."""
    workflow = _maintenance()
    name = "Review Trigger"
    assert "disabled" not in json.dumps(
        [n for n in workflow["nodes"] if n["name"] == name][0])
    assert n8n_cadence.job_enabled(workflow, name) is True

    n8n_cadence.set_job_enabled(workflow, name, False)
    node = [n for n in workflow["nodes"] if n["name"] == name][0]
    assert node["disabled"] is True
    assert n8n_cadence.job_enabled(workflow, name) is False


def test_disabling_one_job_sends_a_body_differing_only_in_that_nodes_disabled_field(
        fake_config, stub_module_transport_factory):
    fetched = _maintenance()
    after = copy.deepcopy(fetched)
    for node in after["nodes"]:
        if node["name"] == "Review Trigger":
            node["disabled"] = True

    transport = stub_module_transport_factory([fetched, {}, {}, {}, after])

    result = n8n_cadence.set_schedule_enabled(
        WORKFLOW_ID, "Review Trigger", False, fake_config, transport=transport)

    assert result.verdict == n8n_control.VERIFIED
    put = [call for call in transport.calls if call["verb"] == "put"][0]
    sent = put["kwargs"]["json"] if "json" in put.get("kwargs", {}) else put.get("json")
    sent_nodes = {node["name"]: node for node in sent["nodes"]}
    for node in fetched["nodes"]:
        expected = copy.deepcopy(node)
        if node["name"] == "Review Trigger":
            expected["disabled"] = True
        assert sent_nodes[node["name"]] == expected


def test_the_reversal_sentence_quotes_the_prior_state(fake_config,
                                                      stub_module_transport_factory):
    fetched = _maintenance()
    after = copy.deepcopy(fetched)
    for node in after["nodes"]:
        if node["name"] == "Review Trigger":
            node["disabled"] = True
    transport = stub_module_transport_factory([fetched, {}, {}, {}, after])

    result = n8n_cadence.set_schedule_enabled(
        WORKFLOW_ID, "Review Trigger", False, fake_config, transport=transport)

    assert "was running" in result.reversal
    assert "switch it back on" in result.reversal


def test_naming_a_non_schedule_trigger_node_refuses_and_lists_the_real_ones():
    workflow = _maintenance()
    with pytest.raises(n8n_cadence.CadenceRefused) as excinfo:
        n8n_cadence.set_job_enabled(workflow, "SJ-3 Extract Rows", False)
    assert "not a scheduled job" in str(excinfo.value)


def test_a_readback_still_showing_the_prior_state_is_failed(fake_config,
                                                            stub_module_transport_factory):
    fetched = _maintenance()
    transport = stub_module_transport_factory([fetched, {}, {}, {}, _maintenance()])

    result = n8n_cadence.set_schedule_enabled(
        WORKFLOW_ID, "Review Trigger", False, fake_config, transport=transport)

    assert result.verdict == n8n_control.FAILED


# --- the cadence mutation -------------------------------------------------------------------

def _retimed(interval):
    after = _maintenance()
    for node in after["nodes"]:
        if node["name"] == "Review Trigger":
            node["parameters"]["rule"]["interval"] = interval
    return after


def test_set_cadence_sends_a_body_whose_only_differing_node_is_the_named_trigger(
        fake_config, stub_module_transport_factory):
    target = [{"field": "hours", "hoursInterval": 1}]
    fetched = _maintenance()
    transport = stub_module_transport_factory([fetched, {}, {}, {}, _retimed(target)])

    result = n8n_cadence.set_cadence(WORKFLOW_ID, "Review Trigger", target,
                                     fake_config, transport=transport)

    assert result.verdict == n8n_control.VERIFIED
    put = [call for call in transport.calls if call["verb"] == "put"][0]
    sent = put["kwargs"]["json"] if "json" in put.get("kwargs", {}) else put.get("json")
    differing = [node["name"] for node, original in
                 zip(sent["nodes"], fetched["nodes"]) if node != original]
    assert differing == ["Review Trigger"]


def test_the_reversal_names_the_prior_cadence_in_plain_language(
        fake_config, stub_module_transport_factory):
    target = [{"field": "hours", "hoursInterval": 1}]
    transport = stub_module_transport_factory(
        [_maintenance(), {}, {}, {}, _retimed(target)])

    result = n8n_cadence.set_cadence(WORKFLOW_ID, "Review Trigger", target,
                                     fake_config, transport=transport)

    # The shipped Review Trigger is daily (2026-08-10: three sub-daily triggers alone
    # exceeded the 2,500/month n8n plan while doing no work), so the prior cadence this
    # reversal names is "once a day".
    assert "once a day" in result.reversal
    assert not FIELD_EXPRESSION.match(result.reversal)
    assert "*" not in result.reversal


def test_a_refusal_object_is_never_accepted_as_an_interval(fake_config,
                                                           stub_module_transport_factory):
    """The mistake that turns D-10's honest refusal into a silent write of whatever the
    refusal happened to stringify to."""
    transport = stub_module_transport_factory([_maintenance()])
    try:
        n8n_cadence.parse_cadence("something unparseable")
    except n8n_cadence.CadenceRefused as refusal:
        with pytest.raises(n8n_cadence.CadenceRefused):
            n8n_cadence.set_cadence(WORKFLOW_ID, "Review Trigger", refusal,
                                    fake_config, transport=transport)
    assert transport.mutating_calls == []


def test_an_unchanged_readback_is_failed(fake_config, stub_module_transport_factory):
    target = [{"field": "hours", "hoursInterval": 1}]
    transport = stub_module_transport_factory(
        [_maintenance(), {}, {}, {}, _maintenance()])      # read-back returns the OLD interval

    result = n8n_cadence.set_cadence(WORKFLOW_ID, "Review Trigger", target,
                                     fake_config, transport=transport)

    assert result.verdict == n8n_control.FAILED


def test_retiming_and_disabling_stay_independent():
    """Neither mutation may widen to cover the other's field, or the field-level guard
    stops meaning anything."""
    workflow = _maintenance()
    name = "Review Trigger"

    n8n_cadence._set_interval_in_place(workflow, name,
                                       [{"field": "hours", "hoursInterval": 1}])
    assert n8n_cadence.job_enabled(workflow, name) is True     # untouched by re-timing

    n8n_cadence.set_job_enabled(workflow, name, False)
    assert n8n_cadence.read_cadence(workflow, name) == \
        [{"field": "hours", "hoursInterval": 1}]               # untouched by disabling


def test_the_field_guard_refuses_a_change_outside_the_permitted_field():
    original = [n for n in _maintenance()["nodes"]
                if n["name"] == "Review Trigger"][0]
    modified = copy.deepcopy(original)
    modified["disabled"] = True
    modified["parameters"]["rule"]["interval"] = [{"field": "hours", "hoursInterval": 1}]

    with pytest.raises(n8n_cadence.CadenceRefused, match="differs outside"):
        n8n_cadence._assert_only_field_changed(original, modified, ("disabled",))
