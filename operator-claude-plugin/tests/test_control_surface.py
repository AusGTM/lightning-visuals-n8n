"""28-05 Task 1 — the choke point.

The two properties everything hangs off: planning is the only composer and executing is
the only mutator, and the confirmation is structural (no default, no truthy-by-omission).
Everything outside the allowlist must be refused before a mutating call is reachable.
"""
import inspect
import json
import re
from pathlib import Path

import pytest

import config_gate
import control_actions
import n8n_control

WORKFLOW_ID = "wf-ctl-1"


def _workflow(active=True):
    gate = ('const ALLOW_HUBSPOT_RECORD_WRITES = "false";\n'
            'const ALLOW_HUBSPOT_CREATE = "false";\n'
            'const TEST_RECORD_IDS = "";\n'
            'const TEST_RECORD_DOMAINS = "";\n')
    return {
        "id": WORKFLOW_ID, "name": "LV Scheduled Maintenance (Cloud)", "active": active,
        "settings": {}, "connections": {},
        "nodes": [
            {"name": "Review Trigger (15 min)", "type": "n8n-nodes-base.scheduleTrigger",
             "parameters": {"rule": {"interval": [
                 {"field": "minutes", "minutesInterval": 15}]}}},
            {"name": "Review Apply Update Write Gate", "parameters": {"jsCode": gate}},
        ],
    }


@pytest.fixture
def control_config(fake_config):
    return dict(fake_config)          # carries n8n_url + n8n_api_key -> control-capable


# --- the allowlist boundary -------------------------------------------------------------

def test_a_request_to_edit_a_node_is_refused_with_no_mutating_call(
        control_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow()])

    result = control_actions.plan_action(
        {"kind": "edit_node", "asked_for": "add a Slack node to the workflow"},
        control_config, transport=transport)

    assert result["outcome"] == control_actions.REFUSED
    assert "admin" in result["detail"]
    assert transport.mutating_calls == []


def test_executing_an_out_of_allowlist_proposal_is_refused_even_when_confirmed(
        control_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([])

    result = control_actions.execute_action(
        {"kind": "edit_node", "workflow_id": WORKFLOW_ID}, "yes", control_config,
        transport=transport)

    assert result["outcome"] == control_actions.REFUSED
    assert transport.calls == []


def test_the_scheduled_scan_refusal_names_both_alternatives():
    result = control_actions.start_scheduled_scan()

    assert result["outcome"] == control_actions.REFUSED
    assert "on or off" in result["detail"]
    assert "schedule" in result["detail"]
    assert "405" in result["detail"], "cites the probe, not a search result"


def test_no_code_path_changes_a_schedule_to_make_something_fire():
    """D-05c. The module must not contain the workaround it refuses."""
    source = Path(control_actions.__file__).read_text()
    body = source.split("def start_scheduled_scan", 1)[1].split("\ndef ", 1)[0]
    assert "set_cadence" not in body
    assert "set_schedule_enabled" not in body


# --- the structural confirmation gate ---------------------------------------------------

def test_the_confirmation_parameter_has_no_default():
    parameter = inspect.signature(control_actions.execute_action).parameters["confirmation"]
    assert parameter.default is inspect.Parameter.empty


@pytest.mark.parametrize("non_affirmative", [None, False, True, "", "ok", "y", "YES", 1])
def test_anything_but_an_explicit_yes_refuses(non_affirmative, control_config,
                                              stub_module_transport_factory):
    transport = stub_module_transport_factory([])

    result = control_actions.execute_action(
        {"kind": "workflow_active", "workflow_id": WORKFLOW_ID, "after": False},
        non_affirmative, control_config, transport=transport)

    assert result["outcome"] == control_actions.REFUSED
    assert "nothing was changed" in result["detail"]
    assert transport.calls == []


# --- the capability gate ----------------------------------------------------------------

def test_plan_and_execute_both_refuse_on_a_config_without_the_control_key(
        fake_config, stub_module_transport_factory):
    config = {k: v for k, v in fake_config.items() if k != "n8n_api_key"}
    transport = stub_module_transport_factory([])

    for call in (
        lambda: control_actions.plan_action(
            {"kind": "workflow_active", "workflow_id": WORKFLOW_ID, "active": False},
            config, transport=transport),
        lambda: control_actions.execute_action(
            {"kind": "workflow_active", "workflow_id": WORKFLOW_ID, "after": False},
            "yes", config, transport=transport),
    ):
        with pytest.raises(config_gate.ConfigError) as excinfo:
            call()
        assert "n8n_api_key" in str(excinfo.value)
    assert transport.calls == [], "the gate precedes any transport use"


# --- consequences -----------------------------------------------------------------------

def test_the_arming_consequence_names_what_writes_permit_and_the_record_bound(
        control_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow()])

    proposal = control_actions.plan_action(
        {"kind": "arm_dispatch", "workflow_id": WORKFLOW_ID,
         "record_ids": ["12345", "67890"], "record_domains": []},
        control_config, transport=transport)

    text = proposal["consequence"]
    assert "overwrite HubSpot company and contact fields" in text
    assert "cannot write any record outside that list" in text
    assert "2 record id(s)" in text
    assert transport.mutating_calls == []


def test_the_cadence_consequence_speaks_plainly_in_both_directions(
        control_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow()])

    proposal = control_actions.plan_action(
        {"kind": "cadence", "workflow_id": WORKFLOW_ID,
         "node_name": "Review Trigger (15 min)", "phrase": "hourly"},
        control_config, transport=transport)

    assert proposal["before"] == "every 15 minutes"
    assert proposal["after"] == "once an hour"
    assert "*" not in proposal["consequence"]
    assert not re.search(r"\d+ \d+ \*", proposal["consequence"])
    assert "every 15 minutes" in proposal["inverse"]


def test_an_unparseable_cadence_phrase_becomes_a_refusal_with_examples(
        control_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow()])

    result = control_actions.plan_action(
        {"kind": "cadence", "workflow_id": WORKFLOW_ID,
         "node_name": "Review Trigger (15 min)", "phrase": "whenever it feels right"},
        control_config, transport=transport)

    assert result["outcome"] == control_actions.REFUSED
    assert "Try one of" in result["detail"]
    assert transport.mutating_calls == []


def test_the_job_toggle_consequence_says_the_other_jobs_keep_running(
        control_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow()])

    proposal = control_actions.plan_action(
        {"kind": "job_enabled", "workflow_id": WORKFLOW_ID,
         "node_name": "Review Trigger (15 min)", "enabled": False},
        control_config, transport=transport)

    assert proposal["before"] is True and proposal["after"] is False
    assert "keep running" in proposal["consequence"]


# --- verdicts are carried, never reinterpreted ------------------------------------------

def test_a_failed_verdict_reaches_the_surface_as_failed(control_config,
                                                        stub_module_transport_factory):
    """Read-back still shows the old state -> failed, and the report says it did not
    take effect. No status-code optimism."""
    transport = stub_module_transport_factory([
        _workflow(active=True),               # plan's read
    ])
    proposal = control_actions.plan_action(
        {"kind": "workflow_active", "workflow_id": WORKFLOW_ID, "active": False},
        control_config, transport=transport)

    execute_transport = stub_module_transport_factory([
        _workflow(active=True),               # set_active's pre-read
        {},                                   # the deactivate POST
        _workflow(active=True),               # re-read: STILL active
    ])
    result = control_actions.execute_action(proposal, "yes", control_config,
                                            transport=execute_transport)

    assert result["outcome"] == n8n_control.FAILED
    assert "DID NOT TAKE EFFECT" in result["report"]


def test_disarm_failed_is_its_own_surfaced_state(control_config, monkeypatch):
    """Never folded into a generic failure (D-03)."""
    class _Window:
        def __init__(self, *a, **k):
            self.arm_result = {"outcome": "armed"}
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            raise control_actions.n8n_arming.DisarmFailed(
                {"outcome": "disarm_failed",
                 "detail": "DISARM FAILED on 'LV Contact Ingest'. LIVE WRITES MAY "
                           "STILL BE ENABLED"})
    monkeypatch.setattr(control_actions.n8n_arming, "armed_window", _Window)

    result = control_actions.execute_action(
        {"kind": "arm_dispatch", "workflow_id": WORKFLOW_ID, "record_ids": ["1"],
         "record_domains": []},
        "yes", control_config, transport=object())

    assert result["outcome"] == "disarm_failed"
    assert "LIVE WRITES MAY STILL BE ENABLED" in result["operator_note"]


# --- lane starts ------------------------------------------------------------------------

def test_starting_the_contact_lane_reaches_dispatch_dispatch_and_no_api_path(
        control_config, monkeypatch):
    calls = []
    monkeypatch.setattr("dispatch.dispatch",
                        lambda payload, armed, config, **kw:
                        calls.append((payload, armed)) or {"accepted": 1})

    result = control_actions.start_lane("contacts", control_config, armed=True,
                                        payload="/tmp/contacts.csv")

    assert result["outcome"] == "dispatched"
    assert calls == [("/tmp/contacts.csv", True)]
    source = Path(control_actions.__file__).read_text()
    assert "/api/v1/" not in source, "a lane start must never reach the n8n API"


def test_the_enrichment_lane_is_offered_because_its_dispatcher_landed(control_config,
                                                                      monkeypatch):
    """The plan predicted one dispatcher; Phase 25 landed the second. Discovery, not
    assumption, is what made that staleness free."""
    calls = []
    monkeypatch.setattr("enrichment.dispatch_enrichment",
                        lambda payload, armed, config, **kw:
                        calls.append(payload) or {"status": "accepted"})

    result = control_actions.start_lane("enrichment", control_config, armed=True,
                                        payload={"events": []})

    assert result["outcome"] == "dispatched"
    assert calls == [{"events": []}]


def test_a_lane_with_no_importable_dispatcher_is_refused_by_name_not_rerouted(
        control_config, monkeypatch):
    monkeypatch.setattr("dispatch.dispatch",
                        lambda *a, **k: pytest.fail("fell back to the contact lane"))
    real_import = control_actions.importlib.import_module

    def _no_enrichment(name):
        if name == "enrichment":
            raise ImportError(name)
        return real_import(name)
    monkeypatch.setattr(control_actions.importlib, "import_module", _no_enrichment)

    result = control_actions.start_lane("enrichment", control_config, armed=True,
                                        payload={"events": []})

    assert result["outcome"] == control_actions.REFUSED
    assert "Phase 25" in result["detail"]
    assert "contact upload works now" in result["detail"]


def test_an_unknown_lane_is_refused_listing_the_real_ones(control_config):
    result = control_actions.start_lane("companies", control_config, armed=False,
                                        payload=None)

    assert result["outcome"] == control_actions.REFUSED
    assert "contacts" in result["detail"] and "enrichment" in result["detail"]
