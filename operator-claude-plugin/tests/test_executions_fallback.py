"""Tests for executions_client.py and the executions-API-fed half of report.py
(REPORT-01, REPORT-03, D-12).

Every test drives the client through an injected stub transport
(`stub_get_transport_factory` — conftest.py) so no test ever performs a real GET; the
autouse `no_network` guard would fail the suite if one tried.
"""
from datetime import datetime, timezone

import executions_client
import report


# =====================================================================================
# find_execution_for_dispatch — pure, no transport at all.
# =====================================================================================

def test_find_execution_for_dispatch_returns_earliest_execution_at_or_after_dispatch():
    dispatched_at = datetime(2026, 7, 30, 10, 0, 0, tzinfo=timezone.utc)
    candidates = [
        {"id": "too-early", "status": "success", "startedAt": "2026-07-30T09:59:00.000Z"},
        {"id": "later", "status": "success", "startedAt": "2026-07-30T10:00:30.000Z"},
        {"id": "earliest-qualifying", "status": "running", "startedAt": "2026-07-30T10:00:05.000Z"},
    ]

    handle = executions_client.find_execution_for_dispatch(candidates, dispatched_at, tolerance_s=5)

    assert handle["execution_id"] == "earliest-qualifying"


def test_find_execution_for_dispatch_returns_none_when_nothing_qualifies():
    dispatched_at = datetime(2026, 7, 30, 10, 0, 0, tzinfo=timezone.utc)
    candidates = [
        {"id": "long-before", "status": "success", "startedAt": "2026-07-30T09:00:00.000Z"},
        {"id": "just-before-tolerance", "status": "success", "startedAt": "2026-07-30T09:59:50.000Z"},
    ]

    handle = executions_client.find_execution_for_dispatch(candidates, dispatched_at, tolerance_s=5)

    assert handle is None, "must never fall back to the nearest earlier run"


def test_find_execution_for_dispatch_marks_result_best_effort():
    dispatched_at = datetime(2026, 7, 30, 10, 0, 0, tzinfo=timezone.utc)
    candidates = [{"id": "1", "status": "success", "startedAt": "2026-07-30T10:00:01.000Z"}]

    handle = executions_client.find_execution_for_dispatch(candidates, dispatched_at)

    assert handle["best_effort"] is True, (
        "no execution id is ever returned by the webhook (D-12) — the caller must not "
        "treat this handle as an authoritative lookup"
    )


def test_find_execution_for_dispatch_tolerates_malformed_candidates():
    dispatched_at = datetime(2026, 7, 30, 10, 0, 0, tzinfo=timezone.utc)
    candidates = ["not a dict", None, {"id": "no-started-at"}, {"id": "ok", "startedAt": "2026-07-30T10:00:01.000Z"}]

    handle = executions_client.find_execution_for_dispatch(candidates, dispatched_at)

    assert handle["execution_id"] == "ok"


# =====================================================================================
# executions_client's GETs — driven through the injected stub transport.
# =====================================================================================

def test_resolve_workflow_id_matches_by_exact_name_and_uses_the_n8n_api_key_header(
    fake_config, stub_get_transport_factory
):
    executions_client._workflow_id_cache.clear()
    transport = stub_get_transport_factory([
        {"data": [
            {"id": "wf-enrichment", "name": "LV Enrichment (Cloud template)"},
            {"id": "wf-contacts", "name": "LV Contact Ingest (Cloud template)"},
        ]},
    ])

    workflow_id = executions_client.resolve_workflow_id(fake_config, transport=transport)

    assert workflow_id == "wf-contacts"
    call = transport.calls[0]
    assert call["headers"] == {"X-N8N-API-KEY": fake_config["n8n_api_key"]}
    assert "X-Enrichment-Secret" not in call["headers"], (
        "the executions API authenticates with X-N8N-API-KEY, never the webhook secret"
    )


def test_resolve_workflow_id_returns_none_when_no_workflow_matches(fake_config, stub_get_transport_factory):
    executions_client._workflow_id_cache.clear()
    transport = stub_get_transport_factory([{"data": [{"id": "wf-other", "name": "Something Else"}]}])

    assert executions_client.resolve_workflow_id(fake_config, transport=transport) is None


def test_resolve_workflow_id_caches_and_does_not_refetch(fake_config, stub_get_transport_factory):
    executions_client._workflow_id_cache.clear()
    transport = stub_get_transport_factory([
        {"data": [{"id": "wf-contacts", "name": "LV Contact Ingest (Cloud template)"}]},
    ])

    first = executions_client.resolve_workflow_id(fake_config, transport=transport)
    second = executions_client.resolve_workflow_id(fake_config, transport=transport)

    assert first == second == "wf-contacts"
    assert len(transport.calls) == 1, "the second call must be served from the process-lifetime cache"


def test_list_executions_filters_by_workflow_id(fake_config, stub_get_transport_factory):
    transport = stub_get_transport_factory([{"data": [{"id": "exec-1"}]}])

    executions = executions_client.list_executions(fake_config, "wf-contacts", transport=transport)

    assert executions == [{"id": "exec-1"}]
    assert transport.calls[0]["params"] == {"workflowId": "wf-contacts", "limit": 5}


def test_get_execution_requests_include_data_true(fake_config, stub_get_transport_factory):
    transport = stub_get_transport_factory([{"id": "exec-1", "status": "success"}])

    execution = executions_client.get_execution(fake_config, "exec-1", transport=transport)

    assert execution == {"id": "exec-1", "status": "success"}
    assert transport.calls[0]["params"] == {"includeData": "true"}
    assert "exec-1" in transport.calls[0]["url"]


def test_get_execution_raises_client_error_on_transport_failure(fake_config):
    def _boom(*args, **kwargs):
        raise ConnectionError("boom")

    try:
        executions_client.get_execution(fake_config, "exec-1", transport=_boom)
        assert False, "expected ExecutionsClientError"
    except executions_client.ExecutionsClientError as exc:
        assert fake_config["n8n_api_key"] not in str(exc), "the API key must never leak into an error message"


# =====================================================================================
# contact_row_ledger — reads Decide Action, never the terminal nodes (Pattern 1, D-11).
# =====================================================================================

def test_contact_row_ledger_returns_one_entry_per_source_row_in_order(contact_execution):
    ledger, reason = report.contact_row_ledger(contact_execution)

    assert reason is None
    assert [row["outcome"] for row in ledger] == ["match", "net_new", "ambiguous", "rejected"]


def test_contact_row_ledger_missing_decision_node_returns_empty_ledger_and_reason():
    execution = {"data": {"resultData": {"runData": {"Set Review": [{"data": {"main": [[]]}}]}}}}

    ledger, reason = report.contact_row_ledger(execution)

    assert ledger == []
    assert reason is not None and "Decide Action" in reason


def test_contact_row_ledger_never_raises_on_malformed_payload():
    for bad in (None, "garbage", 42, [], {}, {"data": "not-a-dict"}, {"data": {"resultData": None}}):
        ledger, reason = report.contact_row_ledger(bad)
        assert ledger == []
        assert reason is not None


# =====================================================================================
# build_contact_report — counts, in-flight framing, source labelling (REPORT-01/03).
# =====================================================================================

def test_build_contact_report_finished_fixture_counts_sum_to_ledger_length(contact_execution):
    r = report.build_contact_report(contact_execution, handle=None)

    assert r["state"] == "finished"
    assert sum(r["counts"].values()) == len(r["rows"]) == r["total"] == 4


def test_build_contact_report_running_execution_is_never_rendered_finished(contact_execution):
    contact_execution["status"] = "running"

    r = report.build_contact_report(contact_execution, handle=None)

    assert r["state"] == "in_flight"


def test_build_contact_report_unrecognised_status_is_also_in_flight(contact_execution):
    contact_execution["status"] = "some-new-status-this-code-has-never-seen"

    r = report.build_contact_report(contact_execution, handle=None)

    assert r["state"] == "in_flight", "unknown is never rendered as finished"


def test_build_contact_report_records_executions_api_source(contact_execution):
    r = report.build_contact_report(contact_execution, handle={"execution_id": "12345"})

    assert r["source"] == "executions_api"


def test_build_contact_report_never_raises_on_a_non_dict_execution():
    # A None/scalar/list execution means the fetch itself never returned anything
    # usable (a pruned run, a 404) — reported "unknown", not guessed as either state.
    for bad in (None, "garbage", 42, []):
        r = report.build_contact_report(bad, handle=None)
        assert r["state"] == "unknown"
        assert r["handle"] is None


def test_build_contact_report_empty_dict_execution_is_in_flight_not_a_crash():
    # An empty dict IS a fetched execution (unlike None) — it just has no recognised
    # status, which the "unknown status is never finished" rule renders as in_flight
    # rather than raising on the missing keys.
    r = report.build_contact_report({}, handle=None)
    assert r["state"] == "in_flight"
    assert r["counts"] == report._empty_counts()
