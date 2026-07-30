"""Tests for n8n_read.py — the read-only n8n Public API client (27-03 Task 1).

Every test drives the module through conftest's stub GET transport; the autouse
`no_network` guard makes a forgotten stub a loud failure rather than a live call.

The module's contract in one line: `None` means "could not tell", `[]` means "read
fine, nothing there", and the two are never conflated (D-08).
"""
import json
from pathlib import Path

import pytest
import requests

import n8n_read

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
N8N_DIR = REPO_ROOT / "n8n"

WORKFLOWS_PAYLOAD = {"data": [{"id": "wf-1", "name": "LV Contact Ingest (Cloud template)",
                              "active": True}]}


# --- the guard itself: every read this module adds is a GET -------------------------


def test_requests_get_raises_inside_a_test():
    """conftest's autouse guard covers GET as well as POST — `requests.get` routes
    through the patched `Session.request`. Asserted rather than assumed: 27-03's plan
    recorded the guard as GET-blind, and it is not (HANDOFF §5)."""
    with pytest.raises(RuntimeError, match="test_requests_get_raises_inside_a_test"):
        requests.get("https://example.invalid/api/v1/workflows")


def test_stub_get_transport_can_script_a_non_2xx(stub_get_transport_factory):
    transport = stub_get_transport_factory([(401, {"message": "unauthorized"})])
    response = transport("https://example.invalid/api/v1/workflows")
    assert response.status_code == 401
    assert response.ok is False


# --- list_workflows / get_workflow ---------------------------------------------------


def test_list_workflows_issues_one_get_with_the_api_key_header(fake_config,
                                                               stub_get_transport_factory):
    transport = stub_get_transport_factory([WORKFLOWS_PAYLOAD])
    workflows = n8n_read.list_workflows(fake_config, transport=transport)

    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["url"] == "https://fake-tenant.n8n.cloud/api/v1/workflows"
    assert call["headers"]["X-N8N-API-KEY"] == fake_config["n8n_api_key"]
    assert call["timeout"] is not None
    assert workflows == WORKFLOWS_PAYLOAD["data"]


def test_workflows_read_never_carries_the_webhook_secret_header(fake_config,
                                                                stub_get_transport_factory):
    """Two different secrets on the same base URL; crossing them 401s (T-27-13)."""
    transport = stub_get_transport_factory([WORKFLOWS_PAYLOAD])
    n8n_read.list_workflows(fake_config, transport=transport)

    headers = transport.calls[0]["headers"]
    assert "X-Enrichment-Secret" not in headers
    assert fake_config["webhook_secret"] not in headers.values()


def test_list_workflows_returns_none_on_a_non_2xx(fake_config, stub_get_transport_factory):
    transport = stub_get_transport_factory([(401, {"message": "unauthorized"})])
    assert n8n_read.list_workflows(fake_config, transport=transport) is None


def test_list_workflows_returns_none_on_a_transport_failure(fake_config,
                                                            stub_get_transport_factory):
    transport = stub_get_transport_factory([ConnectionError("dead")])
    assert n8n_read.list_workflows(fake_config, transport=transport) is None


def test_list_workflows_distinguishes_empty_from_unreadable(fake_config,
                                                            stub_get_transport_factory):
    transport = stub_get_transport_factory([{"data": []}])
    assert n8n_read.list_workflows(fake_config, transport=transport) == []


def test_get_workflow_hits_the_single_workflow_path(fake_config, stub_get_transport_factory):
    transport = stub_get_transport_factory([{"id": "wf-1", "nodes": []}])
    body = n8n_read.get_workflow(fake_config, "wf-1", transport=transport)

    assert transport.calls[0]["url"] == "https://fake-tenant.n8n.cloud/api/v1/workflows/wf-1"
    assert body == {"id": "wf-1", "nodes": []}


def test_get_workflow_returns_none_on_an_unparseable_body(fake_config,
                                                          stub_get_transport_factory):
    transport = stub_get_transport_factory([(200, ValueError("not json"))])
    assert n8n_read.get_workflow(fake_config, "wf-1", transport=transport) is None


# --- last_execution ------------------------------------------------------------------


def test_last_execution_filters_to_one_workflow_and_limits_to_one(fake_config,
                                                                  stub_get_transport_factory):
    transport = stub_get_transport_factory([
        {"data": [{"id": "e-9", "status": "success", "startedAt": "2026-07-31T00:00:00.000Z",
                   "stoppedAt": "2026-07-31T00:00:11.000Z"}]}
    ])
    result = n8n_read.last_execution(fake_config, "wf-1", transport=transport)

    call = transport.calls[0]
    assert call["url"] == "https://fake-tenant.n8n.cloud/api/v1/executions"
    assert call["params"] == {"workflowId": "wf-1", "limit": 1}
    assert result["status"] == "success"
    assert result["started_at"] == "2026-07-31T00:00:00.000Z"
    assert result["stopped_at"] == "2026-07-31T00:00:11.000Z"
    assert result["never_run"] is False
    assert result["in_flight"] is False
    assert result["error"] is None


def test_last_execution_reports_never_run_distinctly_from_unreadable(
        fake_config, stub_get_transport_factory):
    never = n8n_read.last_execution(fake_config, "wf-1",
                                    transport=stub_get_transport_factory([{"data": []}]))
    assert never["never_run"] is True
    assert never["error"] is None
    assert never["status"] is None

    unreadable = n8n_read.last_execution(
        fake_config, "wf-1", transport=stub_get_transport_factory([(500, {})]))
    assert unreadable["never_run"] is False
    assert unreadable["error"] is not None
    assert unreadable["status"] is None


def test_last_execution_derives_a_status_from_finished_when_status_is_absent(
        fake_config, stub_get_transport_factory):
    """Older n8n responses carry only `finished` — the cost-ledger's defensive
    derivation, mirrored rather than trusting `status` unconditionally."""
    transport = stub_get_transport_factory([{"data": [{"id": "e-9", "finished": True}]}])
    assert n8n_read.last_execution(fake_config, "wf-1", transport=transport)["status"] == "finished"

    running = stub_get_transport_factory([{"data": [{"id": "e-9", "finished": False}]}])
    result = n8n_read.last_execution(fake_config, "wf-1", transport=running)
    assert result["status"] == "running"
    assert result["in_flight"] is True


def test_last_execution_marks_a_running_execution_in_flight(fake_config,
                                                            stub_get_transport_factory):
    transport = stub_get_transport_factory([
        {"data": [{"id": "e-9", "status": "running", "startedAt": "2026-07-31T00:00:00.000Z",
                   "stoppedAt": None}]}
    ])
    assert n8n_read.last_execution(fake_config, "wf-1", transport=transport)["in_flight"] is True


# --- read_write_safety ---------------------------------------------------------------


def _wf(nodes):
    return {"name": "stub", "nodes": [
        {"name": name, "parameters": {"jsCode": code}} for name, code in nodes
    ]}


def test_read_write_safety_returns_the_value_when_every_node_agrees():
    body = _wf([
        ("Decide Action", 'const ALLOW_HUBSPOT_CREATE = "false";\nreturn [];'),
        ("HubSpot Create Write Gate", 'const ALLOW_HUBSPOT_CREATE = "false";'),
    ])
    result = n8n_read.read_write_safety(body, "ALLOW_HUBSPOT_CREATE")
    assert result["value"] == "false"
    assert result["disagreement"] is None
    assert sorted(result["nodes"]) == ["Decide Action", "HubSpot Create Write Gate"]


def test_read_write_safety_accepts_the_bare_boolean_form_too():
    body = _wf([("Decide Action", "const ALLOW_HUBSPOT_CREATE = true;")])
    assert n8n_read.read_write_safety(body, "ALLOW_HUBSPOT_CREATE")["value"] == "true"


def test_read_write_safety_is_unknown_when_no_node_declares_the_constant():
    result = n8n_read.read_write_safety(_wf([("Some Node", "return [];")]),
                                        "ALLOW_HUBSPOT_CREATE")
    assert result["value"] is None
    assert result["nodes"] == []
    assert result["disagreement"] is None


def test_read_write_safety_reports_disagreement_rather_than_picking_a_value():
    """A partial deploy or a hand edit in the n8n UI can desync the declaring nodes.
    Reporting a guess would be worse than reporting the desync."""
    body = _wf([
        ("Decide Action", 'const ALLOW_HUBSPOT_CREATE = "false";'),
        ("Decide Company Action", 'const ALLOW_HUBSPOT_CREATE = "true";'),
    ])
    result = n8n_read.read_write_safety(body, "ALLOW_HUBSPOT_CREATE")
    assert result["value"] is None
    assert result["disagreement"] is not None
    disagreeing = {entry["node"]: entry["value"] for entry in result["disagreement"]}
    assert disagreeing == {"Decide Action": "false", "Decide Company Action": "true"}


def test_read_write_safety_finds_the_constant_however_many_nodes_declare_it():
    body = _wf([(f"Gate {i}", 'const ALLOW_HUBSPOT_RECORD_WRITES = "false";') for i in range(4)])
    assert len(n8n_read.read_write_safety(body, "ALLOW_HUBSPOT_RECORD_WRITES")["nodes"]) == 4

    single = _wf([("Only Gate", 'const ALLOW_HUBSPOT_RECORD_WRITES = "false";')])
    assert n8n_read.read_write_safety(single, "ALLOW_HUBSPOT_RECORD_WRITES")["value"] == "false"


def test_read_write_safety_tolerates_a_malformed_workflow_body():
    for body in ({}, {"nodes": None}, {"nodes": [{"name": "x"}]}, {"nodes": [None]}):
        assert n8n_read.read_write_safety(body, "ALLOW_HUBSPOT_CREATE")["value"] is None


def test_no_read_returns_or_embeds_the_workflow_body(fake_config, stub_get_transport_factory):
    """T-27-11: the extractor returns the parsed literal and node names only — a
    fetched workflow body is hundreds of kilobytes of backend internals."""
    secret_marker = "SECRET-INTERNALS-MARKER"
    body = {"name": "stub", "nodes": [
        {"name": "Decide Action",
         "parameters": {"jsCode": f'const ALLOW_HUBSPOT_CREATE = "false"; // {secret_marker}'}},
    ]}
    result = n8n_read.read_write_safety(body, "ALLOW_HUBSPOT_CREATE")
    assert secret_marker not in json.dumps(result)


# --- contract: the extractor matches the artifact that actually ships ----------------


@pytest.mark.parametrize("flag", ["ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE"])
def test_committed_cloud_workflows_read_as_a_single_consistent_value(flag):
    """An offline unit fixture proves the parsing; this proves the parsing matches the
    committed artifacts. Also re-asserts the repo invariant that every committed
    workflow ships disarmed."""
    paths = sorted(N8N_DIR.glob("wf_*_cloud.json"))
    if not paths:
        pytest.skip("committed cloud workflow JSON not present")

    declaring = 0
    for path in paths:
        result = n8n_read.read_write_safety(json.loads(path.read_text()), flag)
        assert result["disagreement"] is None, f"{path.name} declares {flag} inconsistently"
        if result["nodes"]:
            declaring += 1
            assert result["value"] == "false", f"{path.name} ships {flag} armed"
    assert declaring > 0, f"no committed cloud workflow declares {flag} — the extractor is vacuous"
