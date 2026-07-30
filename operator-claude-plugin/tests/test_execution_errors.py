"""Reading the failure out of an execution's node output, not out of its status
(27-04 Task 2).

D-04a, verified node-by-node against the deployed JSON: every provider-facing node is
`onError: continueRegularOutput`. A Lusha 401, an Apollo 403 or an exhausted ZoomInfo
quota therefore does NOT fail the n8n execution — that run is reported `success`. Three
of STATUS-02's four named causes live inside runs n8n calls healthy.

D-04b is the consequence: read per-node output. The headline test here is an execution
whose top-level status reads successful and whose node output nonetheless carries a
provider rejection — that finding must still reach the operator.
"""
import error_table
import execution_errors
import n8n_read


def _execution(run_data=None, status_value="success", top_level_error=None):
    result_data = {"runData": run_data if run_data is not None else {}}
    if top_level_error is not None:
        result_data["error"] = top_level_error
    return {"id": "e-1", "status": status_value, "finished": True,
            "data": {"resultData": result_data}}


def _node_run(items=None, error=None):
    run = {"executionStatus": "success"}
    if error is not None:
        run["error"] = error
    run["data"] = {"main": [[{"json": item} for item in (items or [])]]}
    return run


def _causes(result):
    return [finding["cause"] for finding in result["findings"]]


# --- defensive walk: nothing raises, nothing is invented ------------------------------


def test_an_execution_with_no_data_section_yields_no_findings_without_raising():
    result = execution_errors.harvest_errors({"id": "e-1", "status": "success"})
    assert result["findings"] == []
    assert result["available"] is False
    assert result["reason"]


def test_none_and_junk_inputs_do_not_raise():
    for junk in (None, [], "", 7, {"data": "not a mapping"}):
        result = execution_errors.harvest_errors(junk)
        assert result["findings"] == []


def test_a_malformed_run_data_value_is_an_explicit_unreadable_result():
    """Not an empty success. `runData` present but the wrong type is a truncated or
    unexpected payload — reporting "no errors found" over it would be the T-27-17
    failure of a wedged backend reading healthy."""
    result = execution_errors.harvest_errors(
        {"data": {"resultData": {"runData": "not a mapping"}}})

    assert result["available"] is False
    assert "runData" in result["reason"]
    assert result["findings"] == []


def test_a_node_whose_runs_are_not_a_list_is_unreadable_rather_than_clean():
    result = execution_errors.harvest_errors(_execution({"Lusha Enrich": "broken"}))
    assert result["available"] is False
    assert result["findings"] == []


def test_a_node_absent_from_the_run_data_produces_no_finding():
    """A node that never ran is not a node that failed."""
    result = execution_errors.harvest_errors(_execution({"Decide Action": _node_run()}))
    assert result["available"] is True
    assert result["findings"] == []


def test_a_node_that_ran_and_produced_nothing_is_not_an_error():
    result = execution_errors.harvest_errors(_execution({"Lusha Enrich": [_node_run([])]}))
    assert result["findings"] == []


# --- the three places a failure can hide ----------------------------------------------


def test_an_execution_level_error_is_collected():
    result = execution_errors.harvest_errors(_execution(
        status_value="error",
        top_level_error={"message": "HubSpot 400 Bad Request: property values were not valid"}))

    assert _causes(result) == ["malformed_record"]
    assert result["findings"][0]["level"] == "execution"


def test_a_node_level_error_is_collected_and_names_its_node():
    result = execution_errors.harvest_errors(_execution({
        "HubSpot Create": [_node_run(error={"message": "400 Bad Request"})],
    }))

    assert _causes(result) == ["malformed_record"]
    assert result["findings"][0]["node"] == "HubSpot Create"
    assert result["findings"][0]["level"] == "node"


def test_an_error_inside_a_node_output_item_is_collected():
    """Where a continue-on-error node puts a provider failure."""
    result = execution_errors.harvest_errors(_execution({
        "Lusha Enrich": [_node_run([{"error": {"message": "429 Too Many Requests"}}])],
    }))

    assert _causes(result) == ["rate_limit"]
    assert result["findings"][0]["node"] == "Lusha Enrich"
    assert result["findings"][0]["level"] == "item"


def test_an_item_level_error_that_is_a_bare_string_is_collected():
    result = execution_errors.harvest_errors(_execution({
        "Apollo Enrich": [_node_run([{"error": "403 Forbidden — invalid api key"}])],
    }))
    assert _causes(result) == ["expired_credential"]


# --- the headline: a failure inside a run n8n calls successful ------------------------


def test_a_provider_rejection_surfaces_even_when_the_run_status_reads_successful():
    """D-04a/D-04b. `Lusha Enrich` is onError: continueRegularOutput, so this whole
    execution is reported `success` by the executions API. Reading run status alone would
    report the backend healthy while every enrichment silently returned nothing."""
    execution = _execution(
        {"Lusha Enrich": [_node_run([{"error": {"message": "401 Unauthorized"}}])]},
        status_value="success")
    result = execution_errors.harvest_errors(execution)

    assert execution["status"] == "success"
    assert _causes(result) == ["expired_credential"]
    assert result["findings"][0]["who_can_fix"] == error_table.ADMIN


def test_all_four_status_02_causes_are_reachable_from_node_output():
    payloads = {
        "expired_credential": "401 Unauthorized",
        "rate_limit": "429 Too Many Requests",
        "exhausted_quota": "402 Payment Required: insufficient credits",
        "malformed_record": "400 Bad Request: property values were not valid",
    }
    for expected, message in payloads.items():
        result = execution_errors.harvest_errors(_execution({
            "Some Node": [_node_run([{"error": {"message": message}}])]}))
        assert _causes(result) == [expected], message


# --- collapse, translation, guardrail -------------------------------------------------


def test_identical_findings_collapse_to_one_entry_with_a_count():
    """A hundred rejected rows are one problem, not a hundred."""
    items = [{"error": {"message": f"400 Bad Request: row {i} invalid"}} for i in range(100)]
    result = execution_errors.harvest_errors(_execution({
        "HubSpot Create": [_node_run(items)]}))

    assert len(result["findings"]) == 1
    assert result["findings"][0]["count"] == 100


def test_findings_from_different_nodes_do_not_collapse_together():
    result = execution_errors.harvest_errors(_execution({
        "Lusha Enrich": [_node_run([{"error": "401 Unauthorized"}])],
        "Apollo Enrich": [_node_run([{"error": "401 Unauthorized"}])],
    }))
    assert sorted(f["node"] for f in result["findings"]) == ["Apollo Enrich", "Lusha Enrich"]


def test_every_finding_carries_the_translation_tables_full_result():
    result = execution_errors.harvest_errors(_execution({
        "Lusha Enrich": [_node_run([{"error": "429 rate limit"}])]}))
    finding = result["findings"][0]

    for key in ("matched", "cause", "sentence", "who_can_fix", "is_interpretation", "raw"):
        assert key in finding


def test_an_unrecognised_signature_keeps_the_guarded_interpretation():
    result = execution_errors.harvest_errors(_execution({
        "Mystery Node": [_node_run([{"error": "flurble exploded sideways"}])]}))
    finding = result["findings"][0]

    assert finding["matched"] is False
    assert finding["is_interpretation"] is True
    assert finding["who_can_fix"] == error_table.ADMIN


def test_raw_text_arrives_already_redacted_and_bounded():
    """27-02 owns redaction on every path; this module must not re-implement it, and
    must not bypass it by carrying its own copy of the message."""
    secret = "Bearer sk-ant-supersecretvalue0123456789"
    result = execution_errors.harvest_errors(_execution({
        "Lusha Enrich": [_node_run([{"error": f"401 Unauthorized ({secret})"}])]}))

    import json
    assert "supersecretvalue" not in json.dumps(result)


def test_this_module_holds_no_second_translation_path():
    from pathlib import Path
    source = (Path(__file__).resolve().parent.parent
              / "scripts" / "execution_errors.py").read_text()
    assert "error_table" in source
    assert "who_can_fix=" not in source, (
        "the attribution must come from error_table.translate() alone — a caller-supplied "
        "override is exactly what D-05's guardrail forbids")


# --- the detail read is gated at the call site ----------------------------------------


def test_get_execution_requests_one_execution_with_its_data(fake_config,
                                                            stub_get_transport_factory):
    transport = stub_get_transport_factory([{"id": "e-9", "data": {}}])
    body = n8n_read.get_execution(fake_config, "e-9", transport=transport)

    assert body == {"id": "e-9", "data": {}}
    assert transport.calls[0]["url"].endswith("/api/v1/executions/e-9")
    assert transport.calls[0]["params"] == {"includeData": "true"}
    assert transport.calls[0]["timeout"] is not None


def test_get_execution_degrades_to_none_rather_than_raising(fake_config,
                                                            stub_get_transport_factory):
    for scripted in (ConnectionError("dead"), (404, {}), (200, ValueError("not json"))):
        assert n8n_read.get_execution(
            fake_config, "e-9", transport=stub_get_transport_factory([scripted])) is None


def test_nothing_fetches_a_detail_payload_for_every_run_in_the_page(fake_config,
                                                                    stub_get_transport_factory):
    """T-27-18: the detail payload is large. `describe_all` must not pull one per run —
    the gate is at the call site, for a run already known to have failed or one the
    operator names."""
    import status
    collection = {"data": [{"id": "wf-1", "name": "A", "active": True, "nodes": []}]}
    page = {"data": [{"id": "e-1", "workflowId": "wf-1", "status": "error",
                      "startedAt": "2026-07-31T00:00:00.000Z"}]}
    transport = stub_get_transport_factory([collection, page])
    status.describe_all(fake_config, transport=transport)

    assert not [c for c in transport.calls if (c["params"] or {}).get("includeData")]
