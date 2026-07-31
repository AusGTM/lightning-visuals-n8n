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
    for var in ("LUSHA_API_KEY", "APOLLO_API_KEY", "ZOOMINFO_CLIENT_ID", "ZOOMINFO_CLIENT_SECRET"):
        monkeypatch.delenv(var, raising=False)
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


# =============================================================================================
# Plan 03 Task 1 — provider credit capture, settle handling, diff, and the report.
# =============================================================================================

def _snap(providers: dict) -> dict:
    return {"label": "t", "captured_at": "t", "providers": providers}


# --- capture_credit_snapshot: composition over credit_checker's _HAS/_CHECK, never re-derived ---

def test_credit_capture_snapshot_all_three_providers_reporting(monkeypatch):
    monkeypatch.setattr(ledger.credit_checker, "_HAS", {
        "lusha": lambda: True, "apollo": lambda: True, "zoominfo": lambda: True,
    })
    monkeypatch.setattr(ledger.credit_checker, "_CHECK", {
        "lusha": lambda: {"provider": "lusha", "status": 200, "credits": 4118},
        "apollo": lambda: {"provider": "apollo", "status": 403, "credits": None, "error": None},
        "zoominfo": lambda: {"provider": "zoominfo", "status": 200, "credits": 9301},
    })
    snapshot = ledger.capture_credit_snapshot("pre-canary")
    assert snapshot["label"] == "pre-canary"
    assert snapshot["providers"]["lusha"] == {"configured": True, "credits": 4118, "status": 200, "error": None}
    # Apollo's non-master-key 403 -> explicit unknown, status recorded, capture still succeeds.
    assert snapshot["providers"]["apollo"]["credits"] is None
    assert snapshot["providers"]["apollo"]["status"] == 403
    assert snapshot["providers"]["zoominfo"]["credits"] == 9301


def test_credit_capture_snapshot_provider_without_credentials_recorded_not_omitted(monkeypatch):
    monkeypatch.setattr(ledger.credit_checker, "_HAS", {
        "lusha": lambda: True, "apollo": lambda: False, "zoominfo": lambda: False,
    })
    called = []
    monkeypatch.setattr(ledger.credit_checker, "_CHECK", {
        "lusha": lambda: {"provider": "lusha", "status": 200, "credits": 4118},
        "apollo": lambda: called.append("apollo"),
        "zoominfo": lambda: called.append("zoominfo"),
    })
    snapshot = ledger.capture_credit_snapshot("pre-canary")
    assert called == []  # unconfigured providers are never called
    assert snapshot["providers"]["apollo"] == {"configured": False, "credits": None, "status": None}
    assert snapshot["providers"]["zoominfo"] == {"configured": False, "credits": None, "status": None}


def test_no_provider_creds_skips_credits_mode_cleanly_with_zero_requests(capsys):
    rc = ledger.main(["credits", "--label", "test"])
    assert rc == 0
    assert "skipped (no provider creds)" in capsys.readouterr().out


# --- diff_snapshots: pure, unknown propagation, top-up anomaly -------------------------------

def test_credit_diff_all_known_returns_spend_per_provider():
    before = _snap({"lusha": {"credits": 4118}, "zoominfo": {"credits": 9301}})
    after = _snap({"lusha": {"credits": 4100}, "zoominfo": {"credits": 9250}})
    result = ledger.diff_snapshots(before, after)
    assert result["providers"]["lusha"] == {"before": 4118, "after": 4100, "spend": 18, "anomaly": None}
    assert result["providers"]["zoominfo"] == {"before": 9301, "after": 9250, "spend": 51, "anomaly": None}
    assert result["any_unknown"] is False


def test_credit_diff_unknown_in_either_snapshot_yields_unknown_never_zero():
    before = _snap({"apollo": {"credits": None}})
    after = _snap({"apollo": {"credits": None}})
    result = ledger.diff_snapshots(before, after)
    assert result["providers"]["apollo"]["spend"] is None
    assert result["any_unknown"] is True

    before2 = _snap({"lusha": {"credits": 100}})
    after2 = _snap({"lusha": {"credits": None}})
    result2 = ledger.diff_snapshots(before2, after2)
    assert result2["providers"]["lusha"]["spend"] is None
    assert result2["any_unknown"] is True


def test_credit_diff_provider_unknown_in_only_one_snapshot_is_never_a_partial_pair_number():
    before = _snap({"lusha": {"credits": None}})
    after = _snap({"lusha": {"credits": 4100}})
    result = ledger.diff_snapshots(before, after)
    assert result["providers"]["lusha"]["spend"] is None


def test_credit_diff_top_up_reported_as_anomaly_not_negative_spend():
    before = _snap({"lusha": {"credits": 100}})
    after = _snap({"lusha": {"credits": 150}})  # topped up mid-window
    result = ledger.diff_snapshots(before, after)
    assert result["providers"]["lusha"]["spend"] is None
    assert result["providers"]["lusha"]["anomaly"] == "top_up"
    assert result["any_unknown"] is True


def test_credit_diff_malformed_snapshot_never_raises_and_reports_unknown():
    result = ledger.diff_snapshots({"not": "a snapshot"}, {"providers": {}})
    assert result["any_unknown"] is True
    assert result["providers"] == {}


# --- settle handling: sleep patched, scripted balance sequence -------------------------------

def test_settle_waits_before_first_read_then_records_stable_after_matching_reread(monkeypatch):
    sleep_calls = []
    monkeypatch.setattr(ledger.time, "sleep", lambda s: sleep_calls.append(s))
    scripted = iter([
        _snap({"lusha": {"credits": 95}}),
        _snap({"lusha": {"credits": 95}}),
    ])
    result = ledger.capture_settled_snapshot(
        "after", settle_interval=3, max_attempts=4, capture_fn=lambda label: next(scripted))
    assert sleep_calls == [3, 3]  # waited before the first read, then before the stabilising reread
    assert result["settle"] == {"attempts": 2, "stable": True, "interval_seconds": 3}
    assert result["providers"]["lusha"]["credits"] == 95


def test_settle_gives_up_after_max_attempts_when_balance_keeps_changing(monkeypatch):
    monkeypatch.setattr(ledger.time, "sleep", lambda s: None)
    values = iter([100, 95, 90, 85])

    def fake_capture(label):
        return _snap({"lusha": {"credits": next(values)}})

    result = ledger.capture_settled_snapshot("after", max_attempts=4, capture_fn=fake_capture)
    assert result["settle"]["attempts"] == 4
    assert result["settle"]["stable"] is False


# --- report: three blocks, partial propagation, per-record division --------------------------

def test_report_marks_partial_when_a_provider_is_unknown_and_prints_three_blocks(capsys):
    before = _snap({"lusha": {"credits": 100}, "zoominfo": {"credits": 50}, "apollo": {"credits": None}})
    after = _snap({"lusha": {"credits": 99}, "zoominfo": {"credits": 49}, "apollo": {"credits": None}})
    token_usage = ledger.extract_token_usage(_fake_execution({
        "Claude Web Research": {"model": "claude-haiku-4-5", "usage": FULL_USAGE},
    }))
    report = ledger.build_report(before, after, token_usage, record_count=1)
    assert report["partial"] is True  # apollo unknown
    assert report["anthropic"]["available"] is True
    assert report["anthropic"]["total_usd"] > 0

    ledger.print_report(report)
    out = capsys.readouterr().out
    assert "Provider credits" in out
    assert "Anthropic usage" in out
    assert "Totals" in out
    assert "PARTIAL" in out


def test_report_marks_partial_when_token_usage_is_unavailable():
    before = _snap({"lusha": {"credits": 100}})
    after = _snap({"lusha": {"credits": 99}})
    report = ledger.build_report(before, after, {"available": False, "reason": "x", "rows": []}, record_count=1)
    assert report["partial"] is True
    assert report["anthropic"]["available"] is False
    assert report["per_record_usd"] is None


def test_report_record_count_divides_the_per_record_total():
    before = _snap({})
    after = _snap({})
    token_usage = ledger.extract_token_usage(_fake_execution({
        "Claude Web Research": {"model": "claude-haiku-4-5", "usage": FULL_USAGE},
    }))
    report_one = ledger.build_report(before, after, token_usage, record_count=1)
    report_two = ledger.build_report(before, after, token_usage, record_count=2)
    assert report_one["partial"] is False
    assert report_two["per_record_usd"] == pytest.approx(report_one["per_record_usd"] / 2)


def test_report_never_computes_estimate_delta_when_provider_absent_from_estimates_map():
    before = _snap({"unknown_provider": {"credits": 10}})
    after = _snap({"unknown_provider": {"credits": 8}})
    report = ledger.build_report(before, after, {"available": False, "reason": "x", "rows": []})
    row = report["providers"][0]
    assert row["estimate"] is None
    assert row["delta"] is None


# --- estimates baseline: cited, no fabricated figures -----------------------------------------

def test_every_estimate_entry_has_a_non_empty_citation_naming_a_real_repo_document():
    for key, entry in ledger.ESTIMATES.items():
        assert entry.get("citation"), f"{key} has no citation"
        path_part = entry["citation"].split(" — ")[0].strip()
        assert (ledger.ROOT / path_part).exists(), f"{key} cites {path_part!r} which is absent from the repo"


def test_estimates_print_mode_lists_every_entry_with_figure_unit_and_citation(capsys):
    ledger.print_estimates()
    out = capsys.readouterr().out
    for key, entry in ledger.ESTIMATES.items():
        assert key in out
        assert entry["citation"] in out
    assert "unknown" in out  # apollo's entry is explicitly marked, never fabricated


def test_main_estimates_mode_prints_the_table(capsys):
    rc = ledger.main(["estimates"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "lusha_contacts_first_time_enrich" in out
    assert "docs/LUSHA-V3-CONTRACT.md" in out


def test_no_retired_v2_credit_arithmetic_anywhere_in_this_module():
    src = ledger.ROOT.joinpath("scripts", "enrichment_cost_ledger.py").read_text()
    for retired_figure in ("4.65", "2.5 credits"):
        assert retired_figure not in src, f"retired v2 credit arithmetic {retired_figure!r} leaked into the v3 ledger"


# =============================================================================================
# Phase 29 Plan 02 Task 2 — execution duration / record count / the `durations` summary.
#
# Unknown is never zero (the same rule Phase 25 D-10 and Phase 27 D-08 enforce for provider
# balances, applied here to timing). A run still in flight has an UNKNOWN duration; folding it
# in as 0 drags the measured bound down, which is the failure direction that produces a watch
# giving up while a healthy run is still going.
# =============================================================================================

def _timed_execution(execution_id="e-1", started="2026-07-31T10:00:00.000Z",
                     stopped="2026-07-31T10:00:45.000Z", **extra):
    execution = {"id": execution_id, "workflowId": "wf-1", "status": "success",
                 "startedAt": started, "workflowData": {"name": "LV Enrichment (Cloud template)"}}
    if stopped is not None:
        execution["stoppedAt"] = stopped
    execution.update(extra)
    return execution


def _write_node_execution(counts: dict) -> dict:
    """counts: write-node name -> number of output items (or None to omit the node)."""
    run_data = {}
    for name, count in counts.items():
        if count is None:
            continue
        items = [{"json": {"hs_object_id": f"{i}"}} for i in range(count)]
        run_data[name] = [{"executionStatus": "success", "data": {"main": [items]}}]
    return {"data": {"resultData": {"runData": run_data}}}


# --- duration ---------------------------------------------------------------------------------

def test_duration_is_computed_from_a_well_formed_started_stopped_pair():
    assert ledger.execution_duration_seconds(_timed_execution()) == pytest.approx(45.0)


def test_duration_of_an_execution_with_no_stopped_at_is_unknown_and_not_zero():
    duration = ledger.execution_duration_seconds(_timed_execution(stopped=None))
    assert duration is None
    assert duration != 0


def test_duration_of_an_unparseable_timestamp_is_unknown_not_an_exception():
    assert ledger.execution_duration_seconds(_timed_execution(started="not-a-timestamp")) is None
    assert ledger.execution_duration_seconds(_timed_execution(stopped="")) is None
    assert ledger.execution_duration_seconds("not-a-dict") is None


# --- record count -----------------------------------------------------------------------------

def test_record_count_sums_items_across_the_write_nodes():
    execution = _write_node_execution({"HubSpot Update": 3, "HubSpot Create": 2})
    assert ledger.execution_record_count(execution) == 5


def test_record_count_is_unknown_when_no_write_node_appears_in_the_run_data():
    execution = _write_node_execution({"Normalize + Score": 4})
    count = ledger.execution_record_count(execution)
    assert count is None
    assert count != 0


def test_record_count_of_a_write_node_that_ran_and_wrote_nothing_is_a_genuine_zero():
    """Present-and-empty is 0; absent is unknown. Conflating them is the D-08 failure."""
    assert ledger.execution_record_count(_write_node_execution({"HubSpot Update": 0})) == 0


# --- summary ----------------------------------------------------------------------------------

def _row(duration, records):
    return {"execution_id": "e", "workflow": "w", "duration_seconds": duration,
            "record_count": records}


def test_summary_reports_the_number_of_executions_it_was_derived_from():
    summary = ledger.summarize_durations([_row(40.0, 2), _row(60.0, 3)])
    assert summary["sample_size"] == 2
    assert summary["computed"] == 2


def test_summary_counts_unknowns_separately_and_never_averages_them_in_as_zero():
    summary = ledger.summarize_durations([_row(40.0, 2), _row(None, 2), _row(60.0, None)])
    assert summary["sample_size"] == 3
    assert summary["computed"] == 1            # only the first row yields a per-record rate
    assert summary["unknown_duration"] == 1
    assert summary["unknown_record_count"] == 1
    assert summary["max_seconds_per_record"] == pytest.approx(20.0)
    assert summary["max_duration_seconds"] == pytest.approx(60.0)


def test_summary_of_nothing_computable_is_unknown_rather_than_a_zero_bound():
    summary = ledger.summarize_durations([_row(None, None)])
    assert summary["computed"] == 0
    assert summary["max_seconds_per_record"] is None
    assert summary["p95_seconds_per_record"] is None


def test_summary_percentile_is_at_or_below_the_maximum():
    rows = [_row(float(seconds), 1) for seconds in range(1, 21)]
    summary = ledger.summarize_durations(rows)
    assert summary["computed"] == 20
    assert summary["p95_seconds_per_record"] <= summary["max_seconds_per_record"]
    assert summary["max_seconds_per_record"] == pytest.approx(20.0)


def test_print_durations_states_the_sample_size_and_the_unknown_counts(capsys):
    ledger.print_durations([_row(40.0, 2), _row(None, 2)],
                           ledger.summarize_durations([_row(40.0, 2), _row(None, 2)]))
    out = capsys.readouterr().out
    assert "sample size" in out.lower()
    assert "unknown" in out.lower()


def test_durations_mode_skips_without_credentials_rather_than_calling_n8n(capsys):
    """The hermetic fixture strips N8N_URL/N8N_API_KEY and makes any real request raise —
    so this asserts the credential gate fires BEFORE the transport, the same as list mode."""
    assert ledger.main(["durations"]) == 0
    assert "skipped (no n8n creds)" in capsys.readouterr().out


def test_collect_durations_resolves_the_workflow_name_from_the_workflow_collection(monkeypatch):
    """The executions collection on this tenant carries no `workflowData` — every item's
    name is None. A filter reading only that matches nothing and reports an empty history,
    which is indistinguishable from "no executions to measure" and would have produced a
    provisional bound when a measured one was available (found live 2026-07-31)."""
    monkeypatch.setattr(ledger, "_list_executions", lambda limit: [
        {"id": "1", "workflowId": "wf-a", "status": "success",
         "startedAt": "2026-07-31T10:00:00.000Z", "stoppedAt": "2026-07-31T10:00:36.000Z"},
        {"id": "2", "workflowId": "wf-b", "status": "success",
         "startedAt": "2026-07-31T10:00:00.000Z", "stoppedAt": "2026-07-31T10:00:03.000Z"},
    ])
    monkeypatch.setattr(ledger, "_get_live_workflows", lambda: [
        {"id": "wf-a", "name": "LV Enrichment (Cloud template)"},
        {"id": "wf-b", "name": "LV Scheduled Maintenance (Cloud)"},
    ])
    monkeypatch.setattr(ledger, "_get_execution",
                        lambda execution_id: _write_node_execution({"HubSpot Company Update": 1}))

    rows = ledger.collect_durations("LV Enrichment (Cloud template)", 20)
    assert [row["execution_id"] for row in rows] == ["1"]
    assert rows[0]["workflow"] == "LV Enrichment (Cloud template)"
    assert rows[0]["duration_seconds"] == pytest.approx(36.0)
    assert rows[0]["record_count"] == 1
