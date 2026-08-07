"""fix-40 ad-hoc — the SJ-3 scheduled-poller arm/disarm companion (WINDOWS.md #2).

The property under test throughout, mirroring test_control_arming.py's own framing: a
missing/refused arm must never dispatch, and a failed disarm must never look finished —
plus this module's own addition, that the record allowlist is read from n8n's execution
history and is exactly SJ-3's own matched batch, never guessed and never widened.
"""
import json

import pytest

import config_gate
import enrichment
import executions_client
import n8n_arming
import scheduled_arm
from conftest import (ENRICHMENT_WORKFLOW_ID, ENRICHMENT_WORKFLOW_NAME,
                      MAINTENANCE_WORKFLOW_ID, MAINTENANCE_WORKFLOW_NAME)

WORKFLOWS_PAGE = {"data": [
    {"id": ENRICHMENT_WORKFLOW_ID, "name": ENRICHMENT_WORKFLOW_NAME},
    {"id": MAINTENANCE_WORKFLOW_ID, "name": MAINTENANCE_WORKFLOW_NAME},
]}


@pytest.fixture(autouse=True)
def _clear_workflow_id_cache():
    executions_client._workflow_id_cache.clear()
    yield
    executions_client._workflow_id_cache.clear()


@pytest.fixture
def armed_env(monkeypatch):
    monkeypatch.setenv(n8n_arming.ARM_ENV_VAR, "true")


@pytest.fixture(autouse=True)
def _clean_arm_env(monkeypatch):
    monkeypatch.delenv(n8n_arming.ARM_ENV_VAR, raising=False)


def _sj3_row(hs_object_id):
    return {"json": {"hs_object_id": hs_object_id, "lv_enrichment_requested": "true"}}


def _execution_list_item(execution_id, started_at):
    return {"id": execution_id, "startedAt": started_at,
            "workflowId": MAINTENANCE_WORKFLOW_ID}


def _execution_with_sj3_rows(execution_id, *hs_object_ids):
    """A full execution payload (includeData=true shape) whose SJ-3 lane ran and
    matched the given ids — the shape `report._run_data`/`_node_output_items` walk."""
    return {
        "id": execution_id,
        "data": {"resultData": {"runData": {
            scheduled_arm.SJ3_ROWS_NODE: [
                {"data": {"main": [[_sj3_row(oid) for oid in hs_object_ids]]}},
            ],
        }}},
    }


def _execution_without_sj3(execution_id):
    """A sibling-trigger execution (SJ-1/SJ-2/dedupe/review) — no SJ-3 node at all."""
    return {
        "id": execution_id,
        "data": {"resultData": {"runData": {
            "SJ-1 Search (input-gap scan)": [{"data": {"main": [[{"json": {"total": 0}}]]}}],
        }}},
    }


# =====================================================================================
# find_latest_sj3_batch — pure over already-fetched (stubbed) execution payloads.
# =====================================================================================

def test_finds_the_batch_from_the_newest_execution_that_actually_ran_sj3(
        fake_config, stub_get_transport_factory):
    """Newest-first, and a sibling-trigger execution never satisfies the search — it
    must be skipped, not mistaken for an empty SJ-3 poll."""
    transport = stub_get_transport_factory([
        {"data": [
            _execution_list_item("newest-sibling", "2026-08-06T10:30:00.000Z"),
            _execution_list_item("sj3-tick", "2026-08-06T10:15:00.000Z"),
            _execution_list_item("older-sj3-tick", "2026-08-06T10:00:00.000Z"),
        ]},
        _execution_without_sj3("newest-sibling"),
        _execution_with_sj3_rows("sj3-tick", "111", "222"),
    ])

    batch = scheduled_arm.find_latest_sj3_batch(
        fake_config, MAINTENANCE_WORKFLOW_ID, transport)

    assert batch["execution_id"] == "sj3-tick"
    assert batch["record_ids"] == ["111", "222"]


def test_an_sj3_tick_that_matched_nothing_is_a_genuine_empty_batch_not_none(
        fake_config, stub_get_transport_factory):
    transport = stub_get_transport_factory([
        {"data": [_execution_list_item("empty-tick", "2026-08-06T10:15:00.000Z")]},
        _execution_with_sj3_rows("empty-tick"),
    ])

    batch = scheduled_arm.find_latest_sj3_batch(
        fake_config, MAINTENANCE_WORKFLOW_ID, transport)

    assert batch["record_ids"] == []


def test_returns_none_when_nothing_in_the_lookback_window_ran_sj3(
        fake_config, stub_get_transport_factory):
    transport = stub_get_transport_factory([
        {"data": [_execution_list_item("sibling-1", "2026-08-06T10:00:00.000Z")]},
        _execution_without_sj3("sibling-1"),
    ])

    batch = scheduled_arm.find_latest_sj3_batch(
        fake_config, MAINTENANCE_WORKFLOW_ID, transport)

    assert batch is None


def test_duplicate_hs_object_ids_across_rows_are_deduped_in_order(
        fake_config, stub_get_transport_factory):
    transport = stub_get_transport_factory([
        {"data": [_execution_list_item("t", "2026-08-06T10:15:00.000Z")]},
        _execution_with_sj3_rows("t", "111", "222", "111"),
    ])

    batch = scheduled_arm.find_latest_sj3_batch(fake_config, MAINTENANCE_WORKFLOW_ID, transport)

    assert batch["record_ids"] == ["111", "222"]


# =====================================================================================
# run_scheduled_arm_cycle — the whole read -> arm -> dispatch -> disarm cycle.
# =====================================================================================

def _base_enrichment_workflow(record_writes='"false"', ids='""'):
    gate = (f'const ALLOW_HUBSPOT_RECORD_WRITES = {record_writes};\n'
            f'const ALLOW_HUBSPOT_CREATE = "false";\n'
            f'const TEST_RECORD_IDS = {ids};\n'
            'const TEST_RECORD_DOMAINS = "";\n'
            'function _writeSafetyAllows() { return false; }\n')
    return {
        "id": ENRICHMENT_WORKFLOW_ID, "name": ENRICHMENT_WORKFLOW_NAME, "active": True,
        "settings": {}, "connections": {},
        "nodes": [
            {"name": "Company Gate", "parameters": {"jsCode": gate}},
            {"name": "Webhook Trigger", "parameters": {}},
        ],
    }


def test_no_workflow_found_short_circuits_with_no_mutating_calls(
        fake_config, stub_get_transport_factory, stub_module_transport_factory):
    get_transport = stub_get_transport_factory([{"data": []}])
    post_transport = stub_module_transport_factory()

    result = scheduled_arm.run_scheduled_arm_cycle(
        fake_config, get_transport=get_transport, post_transport=post_transport)

    assert result["outcome"] == "workflow_not_found"
    assert post_transport.calls == []


def test_no_recent_sj3_tick_is_a_clean_noop(
        fake_config, stub_get_transport_factory, stub_module_transport_factory):
    get_transport = stub_get_transport_factory([
        WORKFLOWS_PAGE, WORKFLOWS_PAGE,
        {"data": [_execution_list_item("sibling", "2026-08-06T10:00:00.000Z")]},
        _execution_without_sj3("sibling"),
    ])
    post_transport = stub_module_transport_factory()

    result = scheduled_arm.run_scheduled_arm_cycle(
        fake_config, get_transport=get_transport, post_transport=post_transport)

    assert result["outcome"] == "no_recent_sj3_tick"
    assert post_transport.calls == []


def test_an_empty_sj3_batch_never_arms(
        fake_config, stub_get_transport_factory, stub_module_transport_factory):
    get_transport = stub_get_transport_factory([
        WORKFLOWS_PAGE, WORKFLOWS_PAGE,
        {"data": [_execution_list_item("empty-tick", "2026-08-06T10:15:00.000Z")]},
        _execution_with_sj3_rows("empty-tick"),
    ])
    post_transport = stub_module_transport_factory()

    result = scheduled_arm.run_scheduled_arm_cycle(
        fake_config, get_transport=get_transport, post_transport=post_transport)

    assert result["outcome"] == "no_records_matched"
    assert post_transport.calls == []


def test_without_ALLOW_N8N_ARM_the_cycle_refuses_and_never_dispatches(
        fake_config, stub_get_transport_factory, stub_module_transport_factory):
    """The kill switch precedes the transport construction inside arm_for_dispatch —
    zero mutating calls, and the dispatch body (inside the `with`) never runs at all."""
    fake_config = {**fake_config, "max_records_per_chunk": 2}
    get_transport = stub_get_transport_factory([
        WORKFLOWS_PAGE, WORKFLOWS_PAGE,
        {"data": [_execution_list_item("t", "2026-08-06T10:15:00.000Z")]},
        _execution_with_sj3_rows("t", "111"),
    ])
    post_transport = stub_module_transport_factory()

    result = scheduled_arm.run_scheduled_arm_cycle(
        fake_config, get_transport=get_transport, post_transport=post_transport)

    assert result["outcome"] == "arm_refused"
    assert n8n_arming.ARM_ENV_VAR in result["detail"]
    assert post_transport.mutating_calls == []


def test_a_successful_cycle_arms_dispatches_and_disarms_bounded_to_the_batch(
        armed_env, fake_config, stub_get_transport_factory, stub_module_transport_factory):
    fake_config = {**fake_config, "max_records_per_chunk": 2}
    get_transport = stub_get_transport_factory([
        WORKFLOWS_PAGE, WORKFLOWS_PAGE,
        {"data": [_execution_list_item("t", "2026-08-06T10:15:00.000Z")]},
        _execution_with_sj3_rows("t", "111", "222"),
    ])
    post_transport = stub_module_transport_factory([
        _base_enrichment_workflow(),                                  # arm's own read
        _base_enrichment_workflow(),                                  # apply_mutation's re-read
        {}, {}, {},                                                   # deactivate, put, activate
        _base_enrichment_workflow(record_writes='"true"', ids='"111,222"'),  # arm verify
        {"status": "accepted"},                                       # dispatch POST
        _base_enrichment_workflow(record_writes='"true"', ids='"111,222"'),  # disarm's own read
        _base_enrichment_workflow(record_writes='"true"', ids='"111,222"'),  # apply_mutation's re-read
        {}, {}, {},                                                   # deactivate, put, activate
        _base_enrichment_workflow(),                                  # disarm verify
    ])

    result = scheduled_arm.run_scheduled_arm_cycle(
        fake_config, get_transport=get_transport, post_transport=post_transport)

    assert result["outcome"] == "dispatched"
    assert result["record_ids"] == ["111", "222"]
    assert result["arm"]["outcome"] == n8n_arming.ARMED
    assert result["arm"]["record_ids"] == ["111", "222"]
    assert result["disarm"]["outcome"] == n8n_arming.DISARMED

    dispatch_calls = [c for c in post_transport.calls
                      if c["verb"] == "post" and "enrichment/event" in c["url"]]
    assert len(dispatch_calls) == 1
    sent_events = dispatch_calls[0]["json"]["events"]
    assert {e["objectId"] for e in sent_events} == {"111", "222"}
    assert all(e["objectType"] == "companies" for e in sent_events)


def test_a_dispatch_failure_still_guarantees_the_disarm(
        armed_env, fake_config, stub_get_transport_factory, stub_module_transport_factory):
    """The dispatched enrichment run failing must not leave the write window open."""
    fake_config = {**fake_config, "max_records_per_chunk": 2}
    get_transport = stub_get_transport_factory([
        WORKFLOWS_PAGE, WORKFLOWS_PAGE,
        {"data": [_execution_list_item("t", "2026-08-06T10:15:00.000Z")]},
        _execution_with_sj3_rows("t", "111"),
    ])
    post_transport = stub_module_transport_factory([
        _base_enrichment_workflow(),
        _base_enrichment_workflow(),
        {}, {}, {},
        _base_enrichment_workflow(record_writes='"true"', ids='"111"'),
        RuntimeError("dispatch webhook unreachable"),                 # the dispatch POST fails
        _base_enrichment_workflow(record_writes='"true"', ids='"111"'),  # disarm's own read
        _base_enrichment_workflow(record_writes='"true"', ids='"111"'),  # apply_mutation's re-read
        {}, {}, {},
        _base_enrichment_workflow(),                                  # disarm verify
    ])

    result = scheduled_arm.run_scheduled_arm_cycle(
        fake_config, get_transport=get_transport, post_transport=post_transport)

    assert result["outcome"] == "dispatch_failed"
    assert result["record_ids"] == ["111"]
    mutating_puts = [c for c in post_transport.calls if c["verb"] == "put"]
    assert len(mutating_puts) == 2, "one PUT to arm, one PUT to disarm — both must have run"


def test_missing_chunk_ceiling_config_key_refuses_before_any_arm(
        armed_env, fake_config, stub_get_transport_factory, stub_module_transport_factory):
    """`max_records_per_chunk` absent (D-20: never defaulted) must refuse before the
    window is ever armed — the same "validate before arm" ordering the module docstring
    already guarantees for a malformed record spec."""
    get_transport = stub_get_transport_factory([
        WORKFLOWS_PAGE, WORKFLOWS_PAGE,
        {"data": [_execution_list_item("t", "2026-08-06T10:15:00.000Z")]},
        _execution_with_sj3_rows("t", "111"),
    ])
    post_transport = stub_module_transport_factory()

    result = scheduled_arm.run_scheduled_arm_cycle(
        fake_config, get_transport=get_transport, post_transport=post_transport)

    assert result["outcome"] == "plan_failed"
    assert post_transport.calls == []


def test_a_batch_larger_than_the_ceiling_dispatches_in_multiple_chunks_in_one_arm_window(
        armed_env, fake_config, stub_get_transport_factory, stub_module_transport_factory):
    """The bug this fix closes: the whole matched batch used to go out as ONE POST
    regardless of size, which the deployed webhook refuses outright once it exceeds
    `ENRICH_MAX_LIST_RECORDS` (mirrored client-side by `max_records_per_chunk`). Three
    records against a ceiling of two must become two chunked POSTs — 2 then 1 — inside
    a SINGLE arm/disarm bracket, never a second arm."""
    fake_config = {**fake_config, "max_records_per_chunk": 2}
    get_transport = stub_get_transport_factory([
        WORKFLOWS_PAGE, WORKFLOWS_PAGE,
        {"data": [_execution_list_item("t", "2026-08-06T10:15:00.000Z")]},
        _execution_with_sj3_rows("t", "111", "222", "333"),
    ])
    post_transport = stub_module_transport_factory([
        _base_enrichment_workflow(),                                              # arm read
        _base_enrichment_workflow(),                                              # apply_mutation re-read
        {}, {}, {},                                                               # deactivate, put, activate
        _base_enrichment_workflow(record_writes='"true"', ids='"111,222,333"'),   # arm verify
        {"status": "accepted"},                                                   # dispatch POST chunk 1 (111,222)
        {"status": "accepted"},                                                   # dispatch POST chunk 2 (333)
        _base_enrichment_workflow(record_writes='"true"', ids='"111,222,333"'),   # disarm read
        _base_enrichment_workflow(record_writes='"true"', ids='"111,222,333"'),   # apply_mutation re-read
        {}, {}, {},                                                               # deactivate, put, activate
        _base_enrichment_workflow(),                                              # disarm verify
    ])

    result = scheduled_arm.run_scheduled_arm_cycle(
        fake_config, get_transport=get_transport, post_transport=post_transport)

    assert result["outcome"] == "dispatched"
    assert result["record_ids"] == ["111", "222", "333"]
    assert result["chunk_count"] == 2
    assert result["arm"]["record_ids"] == ["111", "222", "333"]
    assert result["disarm"]["outcome"] == n8n_arming.DISARMED

    dispatch_calls = [c for c in post_transport.calls
                      if c["verb"] == "post" and "enrichment/event" in c["url"]]
    assert len(dispatch_calls) == 2
    assert {e["objectId"] for e in dispatch_calls[0]["json"]["events"]} == {"111", "222"}
    assert {e["objectId"] for e in dispatch_calls[1]["json"]["events"]} == {"333"}


def test_a_partial_chunk_failure_is_visible_not_silently_swallowed(
        armed_env, fake_config, stub_get_transport_factory, stub_module_transport_factory):
    """One chunk failing must still surface loudly — in `results`/`failed_batch` — even
    though the cycle as a whole still reports `dispatched` because SOME records landed
    (D-12: a failing chunk is recorded, the run continues). Never folded away silently."""
    fake_config = {**fake_config, "max_records_per_chunk": 2}
    get_transport = stub_get_transport_factory([
        WORKFLOWS_PAGE, WORKFLOWS_PAGE,
        {"data": [_execution_list_item("t", "2026-08-06T10:15:00.000Z")]},
        _execution_with_sj3_rows("t", "111", "222", "333"),
    ])
    post_transport = stub_module_transport_factory([
        _base_enrichment_workflow(),
        _base_enrichment_workflow(),
        {}, {}, {},
        _base_enrichment_workflow(record_writes='"true"', ids='"111,222,333"'),   # arm verify
        {"status": "accepted"},                                                   # chunk 1 (111,222) succeeds
        RuntimeError("dispatch webhook unreachable"),                             # chunk 2 (333) fails
        _base_enrichment_workflow(record_writes='"true"', ids='"111,222,333"'),   # disarm read
        _base_enrichment_workflow(record_writes='"true"', ids='"111,222,333"'),   # apply_mutation re-read
        {}, {}, {},
        _base_enrichment_workflow(),                                              # disarm verify
    ])

    result = scheduled_arm.run_scheduled_arm_cycle(
        fake_config, get_transport=get_transport, post_transport=post_transport)

    assert result["outcome"] == "dispatched"
    assert result["results"][0]["ok"] is True
    assert result["results"][1]["ok"] is False
    assert result["failed_batch"] == {"record_ids": ["333"], "object_type": "companies"}
    mutating_puts = [c for c in post_transport.calls if c["verb"] == "put"]
    assert len(mutating_puts) == 2, "arm PUT + disarm PUT both ran despite the partial failure"


def test_a_failed_disarm_surfaces_as_its_own_outcome_never_folded_into_dispatched(
        armed_env, fake_config, stub_get_transport_factory, stub_module_transport_factory):
    fake_config = {**fake_config, "max_records_per_chunk": 2}
    still_armed = _base_enrichment_workflow(record_writes='"true"', ids='"111"')
    post_transport = stub_module_transport_factory([
        _base_enrichment_workflow(),
        _base_enrichment_workflow(),
        {}, {}, {},
        still_armed,                                                  # arm verify (succeeds)
        {"status": "accepted"},                                       # dispatch POST
        still_armed,                                                  # disarm's own read
        still_armed,                                                  # apply_mutation's re-read
        {}, {}, {},
        still_armed,                                                  # disarm verify STILL ARMED
    ])
    get_transport = stub_get_transport_factory([
        WORKFLOWS_PAGE, WORKFLOWS_PAGE,
        {"data": [_execution_list_item("t", "2026-08-06T10:15:00.000Z")]},
        _execution_with_sj3_rows("t", "111"),
    ])

    result = scheduled_arm.run_scheduled_arm_cycle(
        fake_config, get_transport=get_transport, post_transport=post_transport)

    assert result["outcome"] == "disarm_failed"
    assert "LIVE WRITES MAY STILL BE ENABLED" in result["detail"]


# =====================================================================================
# The CLI entrypoint and its exit-code mapping.
# =====================================================================================

def test_cli_main_reports_not_configured_without_raising():
    def _refusing_loader():
        raise config_gate.ConfigError("no config file")

    result = scheduled_arm._cli_main(load_config=_refusing_loader)

    assert result["outcome"] == "not_configured"


@pytest.mark.parametrize("outcome,expect_failure", [
    ("dispatched", False),
    ("no_recent_sj3_tick", False),
    ("no_records_matched", False),
    ("arm_refused", False),
    ("not_configured", True),
    ("workflow_not_found", True),
    ("disarm_failed", True),
    ("dispatch_failed", True),
    ("plan_failed", True),
])
def test_failure_outcome_classification_matches_the_documented_intent(outcome, expect_failure):
    assert (outcome in scheduled_arm._FAILURE_OUTCOMES) == expect_failure


def test_capability_gate_names_all_three_keys_scheduled_arm_needs():
    assert config_gate.CAPABILITY_KEYS["scheduled-arm"] == (
        "n8n_url", "n8n_api_key", "webhook_secret")


def test_a_config_missing_the_n8n_api_key_refuses_before_any_call(
        fake_config, stub_get_transport_factory, stub_module_transport_factory):
    cfg = {k: v for k, v in fake_config.items() if k != "n8n_api_key"}
    get_transport = stub_get_transport_factory([])
    post_transport = stub_module_transport_factory()

    with pytest.raises(config_gate.ConfigError):
        scheduled_arm.run_scheduled_arm_cycle(
            cfg, get_transport=get_transport, post_transport=post_transport)

    assert get_transport.calls == []
    assert post_transport.calls == []
