# tests/test_probe_n8n_async_semantics.py
#
# Phase 61 — the offline check for scripts/probe_n8n_async_semantics.py's PURE half:
# runData parsing and verdict shaping. No credentials, no network, no n8n. The live half
# of that script is a one-time operator-run diagnostic and is deliberately not tested
# here; what IS testable is the part that can be silently wrong — reading a verdict out
# of an execution's runData.
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "probe_n8n_async_semantics", ROOT / "scripts" / "probe_n8n_async_semantics.py")
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)


def _execution(run_data, started="2026-08-30T00:00:00.000Z",
               stopped="2026-08-30T00:00:06.000Z", exec_id="900"):
    return {"id": exec_id, "status": "success", "startedAt": started,
            "stoppedAt": stopped,
            "data": {"resultData": {"runData": run_data}}}


def _ok(node_names):
    return {n: [{"executionStatus": "success", "data": {"main": [[{"json": {}}]]}}]
            for n in node_names}


# ------------------------------------------------------------------------- P-07

def test_p07_true_when_response_beat_the_wait_and_the_set_node_still_ran():
    execution = _execution(_ok(["Probe Webhook", "Respond Immediately", "After Response"]))
    v = probe.verdict_p07(round_trip_seconds=0.4, wait_seconds=5, execution=execution)
    assert v["answer"] is True and v["basis"] == "observed"
    assert v["observed"]["post_response_set_node_status"] == "success"


def test_p07_false_when_the_response_was_held_until_the_end():
    # The failure shape that must NOT read as a broken probe: round trip covers the wait.
    execution = _execution(_ok(["Probe Webhook", "Respond Immediately", "After Response"]))
    v = probe.verdict_p07(round_trip_seconds=5.4, wait_seconds=5, execution=execution)
    assert v["answer"] is False and v["basis"] == "observed"


def test_p07_false_when_the_post_response_node_never_ran():
    execution = _execution(_ok(["Probe Webhook", "Respond Immediately"]))
    v = probe.verdict_p07(round_trip_seconds=0.3, wait_seconds=5, execution=execution)
    assert v["answer"] is False


def test_p07_records_the_in_process_scope_boundary_for_a_short_wait():
    execution = _execution(_ok(["Probe Webhook", "Respond Immediately", "After Response"]))
    short = probe.verdict_p07(0.4, 5, execution)["scope_boundary"]
    assert "IN-PROCESS" in short and "P-08" in short
    long = probe.verdict_p07(0.4, 90, execution)["scope_boundary"]
    assert "database-backed" in long


# ------------------------------------------------------------------------- P-10

def _enrichment_execution(n_records, exec_id="11960"):
    items = [{"json": {"object_id": str(i)}} for i in range(n_records)]
    return {"id": exec_id, "startedAt": "2026-08-25T21:01:12.008Z",
            "data": {"resultData": {"runData": {
                "Parse HubSpot Event": [{"data": {"main": [items]}}]}}}}


def test_find_multirecord_chunk_ignores_single_record_sends():
    assert probe.find_multirecord_chunk([_enrichment_execution(1)]) is None


def test_find_multirecord_chunk_reads_the_documented_envelope_keys_via_the_webhook():
    for key in ("companies", "contacts", "records"):
        execution = {"id": "9", "startedAt": "t", "data": {"resultData": {"runData": {
            "Webhook Trigger": [{"data": {"main": [[{"json": {"body": {
                key: [{"domain": "a.example"}, {"domain": "b.example"}]}}}]]}}]}}}}
        hit = probe.find_multirecord_chunk([execution])
        assert hit is not None and hit["record_count"] == 2, key


def test_find_multirecord_chunk_finds_a_two_record_chunk():
    hit = probe.find_multirecord_chunk(
        [_enrichment_execution(1, "1"), _enrichment_execution(2, "2")])
    assert hit == {"execution_id": "2", "started_at": "2026-08-25T21:01:12.008Z",
                   "record_count": 2, "counted_from": "Parse HubSpot Event"}


def test_p10_is_pending_not_false_when_history_holds_no_two_record_chunk():
    v = probe.verdict_p10(None, [], child_executions_listed=None)
    assert v["answer"] is None and v["basis"] == "pending"
    assert "may not call a provider" in v["reason"]
    assert "measure_dispatch.py" in v["residual_command"]


def test_p10_measured_verdict_never_equates_the_list_with_the_billed_quota():
    candidate = {"execution_id": "2", "started_at": "x", "record_count": 2,
                 "counted_from": "Parse HubSpot Event"}
    v = probe.verdict_p10(candidate, ["2"], child_executions_listed=True)
    assert v["observed"]["projected_executions"] == 3      # chunk_count 1 + 2 records
    assert v["observed"]["measured_executions_listed"] == 1
    assert v["answer"] is False and v["observed"]["delta"] == -2
    assert "BILLING" in v["list_vs_billing"]


def test_p10_says_plainly_when_it_cannot_separate_the_two_explanations():
    candidate = {"execution_id": "2", "started_at": "x", "record_count": 2,
                 "counted_from": "Parse HubSpot Event"}
    unlisted = probe.verdict_p10(candidate, ["2"], child_executions_listed=False)
    assert "cannot tell them apart" in unlisted["explanation_discrimination"]
    listed = probe.verdict_p10(candidate, ["2"], child_executions_listed=True)
    assert "explanation (a)" in listed["explanation_discrimination"]


# ------------------------------------------------------------------------- P-13

def test_correlate_child_id_matches_a_literal_child_execution_id():
    parent = {"data": {"resultData": {"runData": {"Dispatch Child": [
        {"data": {"main": [[{"json": {"executionId": "12345"}}]]}}]}}}}
    matched, raw = probe.correlate_child_id(parent, ["12345"])
    assert matched == "12345" and "12345" in raw


def test_correlate_child_id_reports_no_match_and_still_hands_back_the_raw_output():
    parent = {"data": {"resultData": {"runData": {"Dispatch Child": [
        {"data": {"main": [[{"json": {"probe_marker": "observed"}}]]}}]}}}}
    matched, raw = probe.correlate_child_id(parent, ["12345"])
    assert matched is None and "probe_marker" in raw


def test_correlate_child_id_never_matches_on_a_substring():
    # The failure that would report an uncorrelatable substrate as correlatable:
    # child id "123" must NOT match a dump containing the unrelated id 12345.
    parent = {"data": {"resultData": {"runData": {"Dispatch Child": [
        {"data": {"main": [[{"json": {"executionId": "12345"}}]]}}]}}}}
    assert probe.correlate_child_id(parent, ["123"])[0] is None
    assert probe.correlate_child_id(parent, ["12345"])[0] == "12345"


def test_contains_id_token_is_boundary_aware():
    assert probe._contains_id_token('{"id": 11960}', "11960") is True
    assert probe._contains_id_token('{"id": 11960}', "119") is False
    assert probe._contains_id_token('{"id": "a11960b"}', "11960") is False
    assert probe._contains_id_token('{"id": 11960}', None) is False


def test_p13_verdict_reports_the_off_case_against_its_on_control():
    off = {"wait_for_completion": False, "child_execution_ids": ["7"],
           "matched_child_execution_id": None,
           "child_detail_carries_parent_execution_id": None}
    on = {"wait_for_completion": True, "child_execution_ids": ["8"],
          "matched_child_execution_id": "8",
          "child_detail_carries_parent_execution_id": "50"}
    v = probe.verdict_p13(off, on)
    assert v["answer"] is False
    assert v["child_appears_in_executions_list"] is True
    assert v["delta_off_vs_on"]["parent_output_carries_child_id"] == [False, True]
    # The reverse-direction observation the coordinator asked for is carried verbatim.
    assert v["wait_for_completion_off"]["child_detail_carries_parent_execution_id"] is None


# -------------------------------------------------------------------- the gates

def test_instance_guard_never_fails_open(monkeypatch):
    monkeypatch.delenv("N8N_EXPECTED_URL", raising=False)
    monkeypatch.setenv("N8N_URL", "")
    assert probe._instance_ok() is False
    monkeypatch.setenv("N8N_URL", "https://evil.example.com")
    assert probe._instance_ok() is False
    monkeypatch.setenv("N8N_URL", "https://lv.app.n8n.cloud")
    assert probe._instance_ok() is True
    monkeypatch.setenv("N8N_EXPECTED_URL", "https://other.app.n8n.cloud")
    assert probe._instance_ok() is False


def test_probe_gate_demands_exactly_true(monkeypatch):
    monkeypatch.setenv("N8N_URL", "https://lv.app.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "k")
    for bad in ("1", "yes", "TRUE", "True"):
        monkeypatch.setenv(probe.PROBE_ENV_VAR, bad)
        try:
            probe._require_gates()
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError(f"gate accepted {bad!r}")
    monkeypatch.setenv(probe.PROBE_ENV_VAR, "true")
    probe._require_gates()


def test_probe_workflows_contain_only_the_permitted_node_types():
    allowed = {"n8n-nodes-base.webhook", "n8n-nodes-base.respondToWebhook",
               "n8n-nodes-base.wait", "n8n-nodes-base.set",
               "n8n-nodes-base.executeWorkflow", "n8n-nodes-base.executeWorkflowTrigger"}
    for wf in (probe._p07_workflow("p", 5), probe._p13_child_workflow("t"),
               probe._p13_parent_workflow("p", "child", False)):
        assert wf["name"].startswith(probe.PROBE_PREFIX)
        assert {n["type"] for n in wf["nodes"]} <= allowed
