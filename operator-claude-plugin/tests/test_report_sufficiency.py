"""Tests for report.py's sufficiency check, write reconciliation, and adaptive
shaping (REPORT-01, D-01, D-08, D-09, D-11) — plus the AST-based no-poll-loop guard
(D-07) that turns "this phase never grows a watch" into a property the suite
enforces rather than a promise the next plan can quietly break.
"""
import ast
from pathlib import Path

import report

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"


# =====================================================================================
# sync_response_is_sufficient — D-01's first leg.
# =====================================================================================

def test_review_queue_marker_only_body_is_insufficient():
    body = [{"queue": "needs_review"}, {"queue": "needs_review"}]

    assert report.sync_response_is_sufficient(body) is False


def test_body_with_contact_id_is_sufficient():
    assert report.sync_response_is_sufficient([{"contact_id": "c1"}]) is True


def test_body_with_hs_object_id_is_sufficient():
    assert report.sync_response_is_sufficient([{"hs_object_id": "1001"}]) is True


def test_body_that_is_a_full_hubspot_object_is_sufficient():
    assert report.sync_response_is_sufficient([{"id": "1001", "properties": {"email": "a@b.com"}}]) is True


def test_empty_body_is_insufficient():
    assert report.sync_response_is_sufficient([]) is False
    assert report.sync_response_is_sufficient(None) is False


def test_non_list_scalar_body_is_insufficient():
    assert report.sync_response_is_sufficient("accepted") is False
    assert report.sync_response_is_sufficient(42) is False


def test_body_of_non_mapping_items_is_insufficient():
    assert report.sync_response_is_sufficient(["not a dict", 1, None]) is False


def test_mixed_sufficient_and_insufficient_items_is_insufficient():
    # One item lacking any identity is enough to make the whole body unusable — a
    # partial ledger is not a safe substitute for the full one.
    body = [{"contact_id": "c1"}, {"queue": "needs_review"}]
    assert report.sync_response_is_sufficient(body) is False


# =====================================================================================
# reconcile — never claim a write the terminal node did not confirm (Pitfall 3, T-26-01).
# =====================================================================================

def test_create_row_is_not_confirmed_when_hubspot_create_produced_zero_items(contact_execution):
    run_data = contact_execution["data"]["resultData"]["runData"]
    run_data["HubSpot Create"][0]["data"]["main"] = [[]]  # write gate filtered it out
    ledger, _ = report.contact_row_ledger(contact_execution)

    reconciled = report.reconcile(ledger, run_data)

    create_row = next(row for row in reconciled if row["action"] == "create")
    assert create_row["reported_outcome"] == "not_confirmed"
    assert create_row["reported_outcome"] != "create"


def test_update_row_is_not_confirmed_when_hubspot_update_produced_zero_items(contact_execution):
    run_data = contact_execution["data"]["resultData"]["runData"]
    run_data["HubSpot Update"][0]["data"]["main"] = [[]]
    ledger, _ = report.contact_row_ledger(contact_execution)

    reconciled = report.reconcile(ledger, run_data)

    update_row = next(row for row in reconciled if row["action"] == "update")
    assert update_row["reported_outcome"] == "not_confirmed"


def test_update_row_is_confirmed_when_the_write_node_did_produce_items(contact_execution):
    run_data = contact_execution["data"]["resultData"]["runData"]
    ledger, _ = report.contact_row_ledger(contact_execution)

    reconciled = report.reconcile(ledger, run_data)

    update_row = next(row for row in reconciled if row["action"] == "update")
    assert update_row["reported_outcome"] == "update"


def test_reconcile_downgrades_when_the_write_node_is_absent_entirely(contact_execution):
    run_data = contact_execution["data"]["resultData"]["runData"]
    del run_data["HubSpot Create"]
    ledger, _ = report.contact_row_ledger(contact_execution)

    reconciled = report.reconcile(ledger, run_data)

    create_row = next(row for row in reconciled if row["action"] == "create")
    assert create_row["reported_outcome"] == "not_confirmed"


def test_build_contact_report_never_labels_the_write_blocked_row_created(contact_execution):
    run_data = contact_execution["data"]["resultData"]["runData"]
    run_data["HubSpot Create"][0]["data"]["main"] = [[]]

    r = report.build_contact_report(contact_execution, handle=None)

    assert r["counts"]["created"] == 0
    assert r["counts"]["not_confirmed"] == 1
    labels = {row["_identity"]: row["reported_label"] for row in r["rows"]}
    assert "created" not in labels.values() or all(
        row["reported_label"] != "created" for row in r["rows"] if row.get("action") == "create"
    )


# =====================================================================================
# Adaptive shaping — small batch renders every row; large batch shows counts + the
# full failing subset + a stated total (D-08/D-09).
# =====================================================================================

def _execution_with_n_rows(n, n_rejected):
    """Builds a minimal execution-shaped payload with `n` Decide Action rows, the
    last `n_rejected` of which are rejected ('skip') and the rest matched updates
    (all confirmed — HubSpot Update produced one item per accepted row)."""
    rows = []
    for i in range(n - n_rejected):
        rows.append({
            "action": "update", "outcome": "match", "contact_id": f"contact-{i}",
            "hs_object_id": f"{1000 + i}", "reason": None, "email_status": "verified",
            "properties": {},
        })
    for i in range(n_rejected):
        rows.append({
            "action": "skip", "outcome": "rejected", "contact_id": None, "hs_object_id": None,
            "reason": "missing required identity fields", "email_status": "NO_EMAIL",
            "properties": {},
        })
    return {
        "status": "success",
        "data": {"resultData": {"runData": {
            "Decide Action": [{"data": {"main": [[{"json": row} for row in rows]]}}],
            "HubSpot Update": [{"data": {"main": [[{"json": {"id": "1"}}]]}}],
        }}},
    }


def test_small_batch_renders_every_row():
    execution = _execution_with_n_rows(n=10, n_rejected=2)

    r = report.build_contact_report(execution, handle=None)

    assert r["adaptive"] is False
    assert len(r["rows"]) == 10


def test_large_batch_omits_full_rows_but_keeps_the_full_failing_subset_and_a_total():
    execution = _execution_with_n_rows(n=25, n_rejected=3)

    r = report.build_contact_report(execution, handle=None)

    assert r["adaptive"] is True
    assert r["rows"] is None, "the successful rows must be summarised, not printed in full"
    assert r["total"] == 25
    assert len(r["failing_rows"]) == 3, "the failing subset is always returned in full"
    assert r["counts"]["rejected"] == 3
    assert r["counts"]["updated_matched"] == 22


def test_failing_rows_carry_reason_and_identity_or_ordinal_position(contact_execution):
    r = report.build_contact_report(contact_execution, handle=None)

    for row in r["failing_rows"]:
        assert row.get("reason"), f"failing row missing a reason: {row}"
        assert row.get("_identity"), f"failing row missing an identity/ordinal marker: {row}"


# =====================================================================================
# No poll loop grew here (D-07) — enforced by the suite, not just promised in prose.
# =====================================================================================

def _plugin_source_files():
    return sorted(p for p in SCRIPTS_DIR.glob("*.py"))


def _imports_forbidden_module(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == name or alias.name.startswith(name + ".") for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module == name or (node.module or "").startswith(name + "."):
                return True
    return False


def _calls_sleep(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name == "sleep":
                return True
    return False


def _has_while_loop(tree):
    return any(isinstance(node, ast.While) for node in ast.walk(tree))


def test_no_plugin_script_polls_sleeps_or_loops_on_execution_status():
    files = _plugin_source_files()
    assert files, "the guard must scan at least one plugin source file to mean anything"

    offenders = []
    for path in files:
        tree = ast.parse(path.read_text(), filename=str(path))
        if _imports_forbidden_module(tree, "time") or _imports_forbidden_module(tree, "sched"):
            offenders.append(f"{path.name}: imports time/sched")
        if _calls_sleep(tree):
            offenders.append(f"{path.name}: calls a sleep()")
        if _has_while_loop(tree):
            offenders.append(f"{path.name}: contains a while loop")

    assert not offenders, (
        "D-07: the bounded watch is Phase 29's job, built once there — no plugin "
        f"script may poll/sleep/loop over an execution's status. Offenders: {offenders}"
    )
