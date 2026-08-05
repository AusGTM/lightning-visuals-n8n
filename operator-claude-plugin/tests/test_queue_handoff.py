"""Tests for report.queue_handoff_ids (37-CONTEXT §13b, STRUCT-02) — the post-ingest
handoff that hands the scheduled poller the ids of every row that actually landed.

Drives the shared `contact_execution` fixture (one row per outcome: match/net_new/
ambiguous/rejected) for the small-batch shape, and builds a dedicated large-batch
execution locally to prove the function does not depend on
`build_contact_report(...)["rows"]`, which is `None` above `report.SMALL_BATCH_
THRESHOLD` by design (D-08/D-09).
"""
import copy

import report


def _decide_action_row(action, outcome, contact_id=None, hs_object_id=None, reason=None, email_status="verified"):
    return {
        "action": action,
        "outcome": outcome,
        "contact_id": contact_id,
        "hs_object_id": hs_object_id,
        "reason": reason,
        "email_status": email_status,
        "properties": {},
    }


def _write_node_run(ids):
    """A terminal write node's own run, shaped like `HubSpot Create`/`HubSpot
    Update`'s `data.main[0]` — one item per confirmed id."""
    return [{
        "executionStatus": "success",
        "data": {"main": [[{"json": {"id": i, "properties": {}}} for i in ids]]},
    }]


def _build_execution(rows, create_ids=None, update_ids=None, status="success"):
    """A minimal execution payload: `rows` become `Decide Action`'s own output;
    `create_ids`/`update_ids` become `HubSpot Create`/`HubSpot Update`'s own
    confirmed output. A write node is entirely absent when its id list is empty —
    same shape as a gate that filtered every row before the node ever ran."""
    run_data = {
        "Decide Action": [{
            "executionStatus": "success",
            "data": {"main": [[{"json": r} for r in rows]]},
        }],
    }
    if create_ids:
        run_data["HubSpot Create"] = _write_node_run(create_ids)
    if update_ids:
        run_data["HubSpot Update"] = _write_node_run(update_ids)
    return {"status": status, "data": {"resultData": {"runData": run_data}}}


# =====================================================================================
# The shared fixture — one row per outcome.
# =====================================================================================

def test_fixture_returns_the_created_and_updated_matched_ids(contact_execution):
    result = report.queue_handoff_ids(contact_execution)

    # `_row_identity` prefers `contact_id` over `hs_object_id` when both are present
    # (the update row in the fixture carries both, matching the deployed shape).
    assert result["created"] == ["2002"]
    assert result["updated_matched"] == ["contact-redacted-001"]


def test_fixture_ambiguous_and_rejected_ids_appear_in_neither_partition(contact_execution):
    result = report.queue_handoff_ids(contact_execution)

    all_ids = set(result["created"]) | set(result["updated_matched"])
    assert all_ids == {"2002", "contact-redacted-001"}
    excluded_labels = {row["reported_label"] for row in result["excluded"]}
    assert excluded_labels == {"needs_review", "rejected"}


def test_a_not_confirmed_row_appears_in_neither_partition(contact_execution):
    # Force HubSpot Update's run to produce zero output items, so reconcile()
    # downgrades the update row to not_confirmed — the write was gated/filtered
    # before it reached HubSpot.
    execution = copy.deepcopy(contact_execution)
    execution["data"]["resultData"]["runData"]["HubSpot Update"][0]["data"]["main"] = [[]]

    result = report.queue_handoff_ids(execution)

    assert result["updated_matched"] == []
    assert result["created"] == ["2002"]
    excluded_labels = {row["reported_label"] for row in result["excluded"]}
    assert "not_confirmed" in excluded_labels


# =====================================================================================
# The large-batch property: build_contact_report(...)["rows"] is None, this isn't.
# =====================================================================================

def test_large_batch_returns_every_landed_id_even_though_report_rows_is_none():
    rows = [
        _decide_action_row("update", "match", contact_id=None, hs_object_id=str(1000 + i))
        for i in range(25)
    ]
    update_ids = [str(1000 + i) for i in range(25)]
    execution = _build_execution(rows, update_ids=update_ids)

    report_result = report.build_contact_report(execution, handle={"execution_id": "big"})
    handoff_result = report.queue_handoff_ids(execution)

    assert report_result["rows"] is None
    assert report_result["total"] == 25
    assert sorted(handoff_result["updated_matched"], key=int) == sorted(update_ids, key=int)
    assert len(handoff_result["updated_matched"]) == 25


# =====================================================================================
# The row-N placeholder must never be queued.
# =====================================================================================

def test_a_row_whose_identity_falls_back_to_the_placeholder_is_excluded_not_queued():
    rows = [_decide_action_row("update", "match", contact_id=None, hs_object_id=None)]
    execution = _build_execution(rows, update_ids=["9999"])

    result = report.queue_handoff_ids(execution)

    assert result["updated_matched"] == []
    assert not any(str(rid).startswith("row ") for rid in result["created"] + result["updated_matched"])
    assert result["excluded"][0]["reported_label"] == "updated_matched"
    assert "placeholder" in result["excluded"][0]["reason"]


# =====================================================================================
# Unreadable / in-flight executions.
# =====================================================================================

def test_a_non_mapping_execution_yields_empty_partitions_without_raising():
    for execution in ({}, None, "accepted", 42, []):
        result = report.queue_handoff_ids(execution)
        assert result == {"created": [], "updated_matched": [], "excluded": []}


def test_an_in_flight_execution_yields_empty_partitions():
    rows = [_decide_action_row("create", "net_new")]
    execution = _build_execution(rows, create_ids=["5001"], status="running")

    result = report.queue_handoff_ids(execution)

    assert result == {"created": [], "updated_matched": [], "excluded": []}


# =====================================================================================
# The deployed, prefixed property name (T-37-31).
# =====================================================================================

def test_report_module_records_the_prefixed_property_name_only():
    import pathlib
    source = pathlib.Path(report.__file__).read_text()

    assert "lv_enrichment_requested" in source
    assert "'enrichment_requested'" not in source
    assert '"enrichment_requested"' not in source
