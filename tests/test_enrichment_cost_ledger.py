# tests/test_enrichment_cost_ledger.py
#
# Phase 22 Plan 01 Task 2 — offline proof for scripts/enrichment_cost_ledger.py's
# token-usage half. Fully hermetic: no network. Mirrors
# tests/test_check_provider_credits.py's convention — a fake response class, an autouse
# fixture that makes any real request raise, and no live call in this suite.
import json
from pathlib import Path

import pytest
import requests

import scripts.enrichment_cost_ledger as ledger


def _raise_http(*args, **kwargs):
    raise AssertionError("a live n8n request leaked past a guard that should have refused")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    monkeypatch.delenv("N8N_URL", raising=False)
    monkeypatch.delenv("N8N_API_KEY", raising=False)
    monkeypatch.setattr(requests, "get", _raise_http)
    monkeypatch.setattr(requests, "post", _raise_http)
    monkeypatch.setattr(requests, "patch", _raise_http)


def _fake_execution(node_specs: dict) -> dict:
    """node_specs: node_name -> None (absent from runData entirely) | "empty" (present,
    empty run list) | "not_a_list" (present, malformed) | dict (present, ran; keys
    "model"/"usage" populate the node's output json)."""
    run_data = {}
    for name, spec in node_specs.items():
        if spec is None:
            continue
        if spec == "empty":
            run_data[name] = []
            continue
        if spec == "not_a_list":
            run_data[name] = "not-a-list"
            continue
        item_json = {}
        if "model" in spec:
            item_json["model"] = spec["model"]
        if "usage" in spec:
            item_json["usage"] = spec["usage"]
        run_data[name] = [{"executionStatus": "success", "data": {"main": [[{"json": item_json}]]}}]
    return {"data": {"resultData": {"runData": run_data}}}


FULL_USAGE = {"input_tokens": 100, "output_tokens": 50,
              "cache_creation_input_tokens": 0, "cache_read_input_tokens": 10}


# --- node names pinned against the real workflow (a rename can't leave this silent) --------

def test_all_four_anthropic_node_names_exist_in_the_committed_cloud_workflow():
    workflow = json.loads(ledger.ENRICHMENT_WORKFLOW_PATH.read_text())
    live_names = {n.get("name") for n in workflow.get("nodes", [])}
    for node_name in ledger.ANTHROPIC_NODE_NAMES:
        assert node_name in live_names, f"{node_name!r} missing from wf_enrichment_cloud.json"


# --- behaviour table -----------------------------------------------------------------------

def test_extraction_over_all_four_nodes_returns_one_row_each_in_node_order():
    execution = _fake_execution({
        name: {"model": "claude-haiku-4-5", "usage": FULL_USAGE}
        for name in ledger.ANTHROPIC_NODE_NAMES
    })
    result = ledger.extract_token_usage(execution)
    assert result["available"] is True
    assert [row["node"] for row in result["rows"]] == list(ledger.ANTHROPIC_NODE_NAMES)
    for row in result["rows"]:
        assert row["status"] == "ran"
        assert row["usage_available"] is True
        assert row["model"] == "claude-haiku-4-5"
        for counter, value in FULL_USAGE.items():
            assert row[counter] == value


def test_extraction_reports_not_run_distinctly_from_zero_tokens():
    execution = _fake_execution({
        "Claude Web Research": {"model": "claude-haiku-4-5", "usage": FULL_USAGE},
        "Judge Call": None,  # never ran — absent from runData entirely
        "Contact Web Research": None,
        "Contact Judge Call": None,
    })
    result = ledger.extract_token_usage(execution)
    by_node = {row["node"]: row for row in result["rows"]}
    assert by_node["Claude Web Research"]["status"] == "ran"
    assert by_node["Claude Web Research"]["usage_available"] is True
    for absent in ("Judge Call", "Contact Web Research", "Contact Judge Call"):
        assert by_node[absent] == {"node": absent, "status": "not_run"}
        assert "input_tokens" not in by_node[absent]  # never reported as zero tokens


def test_extraction_over_node_output_with_no_usage_object_is_usage_unavailable():
    execution = _fake_execution({
        "Claude Web Research": {"model": "claude-haiku-4-5"},  # ran, no usage key at all
    })
    result = ledger.extract_token_usage(execution)
    row = next(r for r in result["rows"] if r["node"] == "Claude Web Research")
    assert row["status"] == "ran"
    assert row["usage_available"] is False
    assert row["model"] == "claude-haiku-4-5"


@pytest.mark.parametrize("execution,expected_reason_substring", [
    ({"data": {}}, "resultData"),
    ({"data": {"resultData": {}}}, "runData"),
    ({"data": {"resultData": {"runData": "not-a-mapping"}}}, "runData"),
])
def test_truncated_or_missing_shape_never_raises_and_reports_unavailable(execution, expected_reason_substring):
    result = ledger.extract_token_usage(execution)
    assert result["available"] is False
    assert result["rows"] == []
    assert expected_reason_substring in result["reason"]


def test_run_items_not_a_list_is_reported_unavailable_not_raised():
    execution = _fake_execution({"Judge Call": "not_a_list"})
    result = ledger.extract_token_usage(execution)
    assert result["available"] is False
    assert "Judge Call" in result["reason"]
    assert result["rows"] == []


# --- redacted fixture capture (T-22-02, allow-list only) -----------------------------------

def test_build_redacted_fixture_never_carries_credential_shaped_strings():
    execution = _fake_execution({
        "Claude Web Research": {"model": "claude-haiku-4-5", "usage": FULL_USAGE},
    })
    # Simulate a real payload's credential-shaped noise sitting alongside the usage data,
    # at every level an allow-list (not a deny-list) must exclude by construction.
    execution["data"]["resultData"]["runData"]["Claude Web Research"][0]["data"]["main"][0][0]["json"].update({
        "request_headers": {"x-api-key": "sk-ant-api03-FAKE-SECRET-VALUE", "authorization": "Bearer fake"},
        "prompt": "system prompt full text with company confidential details",
    })
    fixture = ledger.build_redacted_fixture(execution)
    text = json.dumps(fixture)
    for marker in ("sk-ant-api03-FAKE-SECRET-VALUE", "x-api-key", "authorization", "Bearer",
                   "prompt", "confidential"):
        assert marker not in text, f"redacted fixture leaked {marker!r}"
    # But the allow-listed usage data itself DID survive the round-trip.
    reextracted = ledger.extract_token_usage(fixture)
    row = next(r for r in reextracted["rows"] if r["node"] == "Claude Web Research")
    assert row["usage_available"] is True
    assert row["model"] == "claude-haiku-4-5"


CREDENTIAL_MARKERS = ("sk-ant-", "Authorization:", "X-N8N-API-KEY", "HUBSPOT_PRIVATE_APP_TOKEN")


def test_redacted_committed_fixture_carries_none_of_the_credential_markers():
    if not ledger.FIXTURE_PATH.exists():
        pytest.skip("tests/fixtures/n8n/execution_rundata_usage.json not yet captured")
    text = ledger.FIXTURE_PATH.read_text()
    for marker in CREDENTIAL_MARKERS:
        assert marker not in text, f"committed fixture leaked credential marker {marker!r}"


# --- no-creds skip path: zero requests, exit 0 ----------------------------------------------

def test_no_creds_skips_cleanly_with_zero_requests(capsys):
    rc = ledger.main([])
    assert rc == 0
    assert "skipped (no n8n creds)" in capsys.readouterr().out


def test_extract_without_execution_id_refuses(monkeypatch, capsys):
    monkeypatch.setenv("N8N_URL", "https://fake.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    rc = ledger.main(["extract"])
    assert rc != 0
    assert "REFUSED" in capsys.readouterr().out
