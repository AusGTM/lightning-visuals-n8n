"""Offline coverage for `scripts/bounce_n8n_workflows.py`'s `_row_ok` predicate (D-70-29,
Phase 70 Plan 17 Task 2).

`_row_ok` is the whole row verdict the bounce script prints and exits on, extracted to a
module-level pure function so it can be exercised without a network call. Every case here
is a plain dict — no HTTP, no fixtures.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import bounce_n8n_workflows as bounce  # noqa: E402


def _body(active=True, node_count=3, execution_order="v1", write_flags="false"):
    nodes = [{"name": f"n{i}", "type": "n8n-nodes-base.code",
              "parameters": {"jsCode": f'const ALLOW_HUBSPOT_RECORD_WRITES = "{write_flags}";'
                                        if i == 0 else "const X = 1;"}}
             for i in range(node_count)]
    return {"active": active, "nodes": nodes, "settings": {"executionOrder": execution_order}}


# --------------------------------------------------------------------------- _row_ok


def test_row_ok_true_for_a_fully_good_body():
    assert bounce._row_ok(_body(), expected_nodes=3) is True


def test_row_ok_false_when_execution_order_is_absent():
    body = _body()
    body["settings"] = {}
    assert bounce._row_ok(body, expected_nodes=3) is False


def test_row_ok_false_when_execution_order_is_a_non_v1_value():
    assert bounce._row_ok(_body(execution_order="v0"), expected_nodes=3) is False


def test_row_ok_false_when_settings_key_is_absent_entirely():
    body = _body()
    del body["settings"]
    assert bounce._row_ok(body, expected_nodes=3) is False


def test_row_ok_false_when_inactive():
    assert bounce._row_ok(_body(active=False), expected_nodes=3) is False


def test_row_ok_false_on_node_count_mismatch():
    assert bounce._row_ok(_body(node_count=2), expected_nodes=3) is False


def test_row_ok_false_when_a_write_flag_is_armed():
    assert bounce._row_ok(_body(write_flags="true"), expected_nodes=3) is False


# --------------------------------------------------------------------------- _flag_values


def test_flag_values_collects_both_literals_when_a_flag_appears_twice_with_different_values():
    """The shape an arming rewrite can leave behind: two `const FLAG = ...;` declarations
    for the same flag, disagreeing — this must surface as a mismatch, not silently pick
    one."""
    body = {"nodes": [
        {"parameters": {"jsCode": 'const ALLOW_HUBSPOT_RECORD_WRITES = "false";'}},
        {"parameters": {"jsCode": 'const ALLOW_HUBSPOT_RECORD_WRITES = "true";'}},
    ]}
    values = bounce._flag_values(body)
    assert values["ALLOW_HUBSPOT_RECORD_WRITES"] == ["false", "true"]


def test_flag_values_empty_when_flag_never_declared():
    body = {"nodes": [{"parameters": {"jsCode": "const X = 1;"}}]}
    values = bounce._flag_values(body)
    assert values["ALLOW_HUBSPOT_RECORD_WRITES"] == []
    assert values["ALLOW_HUBSPOT_CREATE"] == []
