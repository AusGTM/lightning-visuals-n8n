"""Every workflow the key can see, what is in flight, and what has been running too long
(27-04 Task 1).

D-07: no allowlist. A workflow going silently unreported is the exact failure this phase
exists to prevent, so the collection response IS the list — adding a workflow to n8n must
put it in the answer with no code and no config change.

D-07b: "stuck" is an execution-age verdict read from the executions API, not a claim about
`enrichment_lock_until` — a property that does not exist in this portal's schema and that
nothing in the pipeline ever wrote (D-07a). The threshold is a carried convention rather
than a measured value (27-RESEARCH.md A2), so the verdict has to carry its own evidence.
"""
from datetime import datetime, timedelta, timezone

import n8n_read
import status

NOW = datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc)


def _iso(minutes_ago):
    return (NOW - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _workflow(wf_id, name, active=True, flag_value="false"):
    """A collection entry carrying nodes, which is what n8n's /workflows returns."""
    return {
        "id": wf_id,
        "name": name,
        "active": active,
        "nodes": [{"name": "Decide Action",
                   "parameters": {
                       "jsCode": f'const ALLOW_HUBSPOT_CREATE = "{flag_value}";'}}],
    }


def _execution(wf_id, status_value="success", minutes_ago=1, exec_id="e-1"):
    return {
        "id": exec_id,
        "workflowId": wf_id,
        "status": status_value,
        "startedAt": _iso(minutes_ago),
        "stoppedAt": None if status_value == "running" else _iso(minutes_ago - 1),
    }


def _collection(workflows):
    return {"data": workflows}


# --- D-07: every workflow, no allowlist ----------------------------------------------


def test_every_workflow_in_the_collection_is_reported(fake_config,
                                                      stub_get_transport_factory):
    transport = stub_get_transport_factory([
        _collection([_workflow("wf-1", "Contact Ingest"), _workflow("wf-2", "Enrichment")]),
        _collection([_execution("wf-1"), _execution("wf-2")]),
    ])
    result = status.describe_all(fake_config, transport=transport, now=NOW)

    assert result["readable"] is True
    assert [entry["name"] for entry in result["workflows"]] == ["Contact Ingest", "Enrichment"]


def test_a_newly_added_workflow_appears_with_no_other_change(fake_config,
                                                             stub_get_transport_factory):
    """The acceptance case for D-07: one extra entry in the collection, nothing else
    edited, and it is in the answer."""
    transport = stub_get_transport_factory([
        _collection([_workflow("wf-1", "Contact Ingest"),
                     _workflow("wf-2", "Enrichment"),
                     _workflow("wf-9", "Brand New Workflow")]),
        _collection([_execution("wf-1"), _execution("wf-2"), _execution("wf-9")]),
    ])
    names = [e["name"] for e in status.describe_all(
        fake_config, transport=transport, now=NOW)["workflows"]]
    assert "Brand New Workflow" in names


def test_no_workflow_allowlist_exists_in_any_plugin_source():
    from pathlib import Path
    scripts = Path(__file__).resolve().parent.parent / "scripts"
    offenders = [p.name for p in scripts.glob("*.py")
                 if "workflow_allowlist" in p.read_text().lower()]
    assert offenders == []


def test_an_unreadable_collection_is_unknown_and_not_an_empty_list(
        fake_config, stub_get_transport_factory):
    transport = stub_get_transport_factory([(401, {"message": "nope"})])
    result = status.describe_all(fake_config, transport=transport, now=NOW)

    assert result["readable"] is False
    assert result["workflows"] == []


def test_a_genuinely_empty_collection_is_readable_with_no_workflows(
        fake_config, stub_get_transport_factory):
    """`[]` is "read fine, nothing there" — never conflated with "could not read"."""
    transport = stub_get_transport_factory([_collection([]), _collection([])])
    result = status.describe_all(fake_config, transport=transport, now=NOW)

    assert result["readable"] is True
    assert result["workflows"] == []


# --- one page, grouped, plus a top-up read for anything absent from it ----------------


def test_the_executions_page_is_fetched_once_not_once_per_workflow(
        fake_config, stub_get_transport_factory):
    transport = stub_get_transport_factory([
        _collection([_workflow("wf-1", "A"), _workflow("wf-2", "B"), _workflow("wf-3", "C")]),
        _collection([_execution("wf-1"), _execution("wf-2"), _execution("wf-3")]),
    ])
    status.describe_all(fake_config, transport=transport, now=NOW)

    assert len(transport.calls) == 2, (
        "one workflows call plus one executions page — a per-workflow executions read "
        "would be three more")


def test_a_workflow_absent_from_the_page_gets_its_own_filtered_read(
        fake_config, stub_get_transport_factory):
    """A bounded page is not complete history. Claiming never-run from an absence in it
    would be a fabrication, so the absence triggers its own read."""
    transport = stub_get_transport_factory([
        _collection([_workflow("wf-1", "A"), _workflow("wf-2", "B")]),
        _collection([_execution("wf-1")]),
        _collection([_execution("wf-2", minutes_ago=900, exec_id="e-old")]),
    ])
    result = status.describe_all(fake_config, transport=transport, now=NOW)

    by_name = {e["name"]: e for e in result["workflows"]}
    assert by_name["B"]["last_run"]["never_run"] is False
    assert by_name["B"]["last_run"]["execution_id"] == "e-old"
    assert transport.calls[-1]["params"] == {"workflowId": "wf-2", "limit": 1}


def test_an_empty_top_up_read_is_never_run(fake_config, stub_get_transport_factory):
    transport = stub_get_transport_factory([
        _collection([_workflow("wf-1", "A")]),
        _collection([]),
        _collection([]),
    ])
    entry = status.describe_all(fake_config, transport=transport, now=NOW)["workflows"][0]

    assert entry["last_run"]["never_run"] is True
    assert entry["last_run"]["error"] is None


def test_a_failed_top_up_read_is_unknown_and_specifically_not_never_run(
        fake_config, stub_get_transport_factory):
    """T-27-17: the reassuring answer is the dangerous one. A read that failed must not
    read as "this workflow has simply never run"."""
    transport = stub_get_transport_factory([
        _collection([_workflow("wf-1", "A")]),
        _collection([]),
        (500, {"message": "boom"}),
    ])
    entry = status.describe_all(fake_config, transport=transport, now=NOW)["workflows"][0]

    assert entry["last_run"]["never_run"] is False
    assert entry["last_run"]["error"] == "could_not_read_executions"
    assert entry["last_run"]["status"] is None


def test_an_unreadable_executions_page_still_reports_every_workflow(
        fake_config, stub_get_transport_factory):
    """The page failing is not a reason to drop workflows out of the answer — each one
    falls back to its own read."""
    transport = stub_get_transport_factory([
        _collection([_workflow("wf-1", "A"), _workflow("wf-2", "B")]),
        (503, {}),
        _collection([_execution("wf-1")]),
        _collection([_execution("wf-2")]),
    ])
    result = status.describe_all(fake_config, transport=transport, now=NOW)
    assert len(result["workflows"]) == 2


# --- in flight versus stuck -----------------------------------------------------------


def test_a_running_execution_is_reported_in_flight(fake_config, stub_get_transport_factory):
    transport = stub_get_transport_factory([
        _collection([_workflow("wf-1", "A")]),
        _collection([_execution("wf-1", status_value="running", minutes_ago=2)]),
    ])
    entry = status.describe_all(fake_config, transport=transport, now=NOW)["workflows"][0]

    assert entry["in_flight"] is True
    assert entry["last_run"]["stuck"] is False


def test_a_run_past_the_threshold_is_stuck_and_carries_its_age_and_the_threshold(
        fake_config, stub_get_transport_factory):
    """A2: the threshold is a carried convention, not a measured value — the operator has
    to be able to judge the call, so both numbers travel with the verdict."""
    transport = stub_get_transport_factory([
        _collection([_workflow("wf-1", "A")]),
        _collection([_execution("wf-1", status_value="running", minutes_ago=40)]),
    ])
    last_run = status.describe_all(
        fake_config, transport=transport, now=NOW)["workflows"][0]["last_run"]

    assert last_run["stuck"] is True
    assert round(last_run["running_for_minutes"]) == 40
    assert last_run["stuck_threshold_minutes"] == 15


def test_a_run_under_the_threshold_is_in_flight_and_not_stuck(fake_config,
                                                              stub_get_transport_factory):
    transport = stub_get_transport_factory([
        _collection([_workflow("wf-1", "A")]),
        _collection([_execution("wf-1", status_value="running", minutes_ago=14)]),
    ])
    last_run = status.describe_all(
        fake_config, transport=transport, now=NOW)["workflows"][0]["last_run"]

    assert last_run["stuck"] is False
    assert last_run["running_for_minutes"] < 15


def test_the_threshold_comes_from_configuration(fake_config, stub_get_transport_factory):
    transport = stub_get_transport_factory([
        _collection([_workflow("wf-1", "A")]),
        _collection([_execution("wf-1", status_value="running", minutes_ago=20)]),
    ])
    config = dict(fake_config, stuck_execution_minutes=60)
    last_run = status.describe_all(
        config, transport=transport, now=NOW)["workflows"][0]["last_run"]

    assert last_run["stuck"] is False
    assert last_run["stuck_threshold_minutes"] == 60


def test_the_threshold_falls_back_to_the_documented_default_when_absent():
    assert n8n_read.stuck_threshold_minutes({}) == n8n_read.DEFAULT_STUCK_MINUTES
    assert n8n_read.stuck_threshold_minutes({"stuck_execution_minutes": None}) == 15
    assert n8n_read.stuck_threshold_minutes({"stuck_execution_minutes": "nonsense"}) == 15
    assert n8n_read.stuck_threshold_minutes({"stuck_execution_minutes": 0}) == 15


def test_an_unparseable_start_time_is_unknown_age_and_is_not_classified_stuck(
        fake_config, stub_get_transport_factory):
    for bad in (None, "", "not-a-timestamp"):
        running = _execution("wf-1", status_value="running")
        running["startedAt"] = bad
        transport = stub_get_transport_factory([
            _collection([_workflow("wf-1", "A")]),
            _collection([running]),
        ])
        last_run = status.describe_all(
            fake_config, transport=transport, now=NOW)["workflows"][0]["last_run"]

        assert last_run["running_for_minutes"] is None
        assert last_run["stuck"] is not True


def test_a_trailing_zulu_marker_parses_and_is_compared_in_utc():
    assert round(n8n_read.elapsed_minutes("2026-07-31T11:30:00.000Z", now=NOW)) == 30
    assert round(n8n_read.elapsed_minutes("2026-07-31T11:30:00Z", now=NOW)) == 30
    assert round(n8n_read.elapsed_minutes("2026-07-31T11:30:00+00:00", now=NOW)) == 30


def test_a_finished_run_has_no_running_duration_and_is_not_stuck(
        fake_config, stub_get_transport_factory):
    transport = stub_get_transport_factory([
        _collection([_workflow("wf-1", "A")]),
        _collection([_execution("wf-1", status_value="success", minutes_ago=600)]),
    ])
    last_run = status.describe_all(
        fake_config, transport=transport, now=NOW)["workflows"][0]["last_run"]

    assert last_run["stuck"] is False
    assert last_run["running_for_minutes"] is None


# --- the rest of the per-workflow answer survives the widening ------------------------


def test_each_entry_still_carries_on_off_and_write_safety(fake_config,
                                                          stub_get_transport_factory):
    transport = stub_get_transport_factory([
        _collection([_workflow("wf-1", "A", active=False, flag_value="true")]),
        _collection([_execution("wf-1")]),
    ])
    entry = status.describe_all(fake_config, transport=transport, now=NOW)["workflows"][0]

    assert entry["active"] is False
    assert entry["write_safety"]["ALLOW_HUBSPOT_CREATE"]["value"] == "true"


def test_a_collection_entry_without_nodes_triggers_its_own_body_read(
        fake_config, stub_get_transport_factory):
    """Write-safety unknown because the collection was thin would silently under-report an
    armed backend — the exact D-10 failure. Fetch the body instead."""
    thin = {"id": "wf-1", "name": "A", "active": True}
    transport = stub_get_transport_factory([
        _collection([thin]),
        _collection([_execution("wf-1")]),
        _workflow("wf-1", "A", flag_value="true"),
    ])
    entry = status.describe_all(fake_config, transport=transport, now=NOW)["workflows"][0]

    assert entry["write_safety"]["ALLOW_HUBSPOT_CREATE"]["value"] == "true"


def test_no_fetched_workflow_body_leaks_into_the_answer(fake_config,
                                                        stub_get_transport_factory):
    """T-27-11 held across the widening."""
    import json
    marker = "SECRET-INTERNALS-MARKER"
    wf = _workflow("wf-1", "A")
    wf["nodes"][0]["parameters"]["jsCode"] += f" // {marker}"
    transport = stub_get_transport_factory([
        _collection([wf]),
        _collection([_execution("wf-1")]),
    ])
    result = status.describe_all(fake_config, transport=transport, now=NOW)

    rendered = json.dumps(result)
    assert marker not in rendered
    # `write_safety.nodes` is 27-03's deliberate list of DECLARING NODE NAMES, which is
    # not a body leak. The body itself is `jsCode` under `parameters` — that is what must
    # never cross out of the module.
    assert "jsCode" not in rendered and "parameters" not in rendered


def test_describe_all_refuses_before_any_transport_when_the_key_is_missing(fake_config):
    import config_gate
    import pytest

    exploded = {"n8n_url": fake_config["n8n_url"]}

    def _never(*args, **kwargs):
        raise AssertionError("a transport was constructed despite the missing key")

    with pytest.raises(config_gate.ConfigError):
        status.full_report(exploded, get_transport=_never, post_transport=_never)
