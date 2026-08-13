# tests/test_sweep_tier_dependents.py
#
# Phase 50 Plan 02 (D-13). Offline only: no network, no HubSpot credentials, no environment
# variable. Pins scripts/sweep_tier_dependents.py's two pure functions -- find_references()
# and render_sweep_markdown() -- against fixture blobs, plus a source-level AST assertion
# that the module contains no write-verb `requests` call site (T-50-08).
import ast
import inspect
from pathlib import Path

import scripts.sweep_tier_dependents as sweep_tier_dependents
from scripts.sweep_tier_dependents import find_references, render_sweep_markdown

MODULE_PATH = Path(inspect.getfile(sweep_tier_dependents))


# --- find_references() ---------------------------------------------------------------------

def test_exact_match_returns_one_path():
    blob = {"filters": [{"property": "lv_icp_tier"}]}
    paths = find_references(blob, "lv_icp_tier")
    assert paths == ["$.filters[0].property"]


def test_prefix_name_is_not_a_match():
    # The load-bearing case: a blob naming only the NEW property must never be reported
    # as a dependent of the OLD one.
    blob = {"filters": [{"property": "lv_icp_tier_derived"}]}
    assert find_references(blob, "lv_icp_tier") == []


def test_unrelated_blob_returns_empty():
    blob = {"filters": [{"property": "annualrevenue"}], "name": "Unrelated List"}
    assert find_references(blob, "lv_icp_tier") == []


def test_nested_list_and_dict_walked():
    blob = {
        "enrollmentCriteria": {
            "eventFilterBranches": [
                {"filters": [{"property": "hs_name", "value": "lv_icp_tier"}]},
                {"filters": [{"property": "hs_name", "value": "lv_anti_icp_flag"}]},
            ]
        }
    }
    paths = find_references(blob, "lv_icp_tier")
    assert paths == [
        "$.enrollmentCriteria.eventFilterBranches[0].filters[0].value"
    ]


def test_multiple_matches_return_multiple_paths():
    blob = {"a": {"property": "lv_icp_tier"}, "b": {"property": "lv_icp_tier"}}
    assert len(find_references(blob, "lv_icp_tier")) == 2


# --- render_sweep_markdown() ----------------------------------------------------------------

def test_zero_findings_states_both_scanned_counts():
    text = render_sweep_markdown([], [], {"lists": 12, "flows": 9}, "2026-08-13")
    assert "12" in text
    assert "9" in text
    assert "NONE" in text


def test_consecutive_renders_are_byte_identical():
    list_findings = [{"id": "1", "name": "List One", "path": "$.filters[0].property"}]
    flow_findings = [{"id": "42", "name": "Flow Forty Two", "path": "$.actions[0].value"}]
    first = render_sweep_markdown(list_findings, flow_findings, {"lists": 1, "flows": 1}, "2026-08-13")
    second = render_sweep_markdown(list_findings, flow_findings, {"lists": 1, "flows": 1}, "2026-08-13")
    assert first == second


def test_manual_check_section_present_when_findings_are_non_empty():
    list_findings = [{"id": "1", "name": "List One", "path": "$.filters[0].property"}]
    flow_findings = [{"id": "42", "name": "Flow Forty Two", "path": "$.actions[0].value"}]
    text = render_sweep_markdown(list_findings, flow_findings, {"lists": 1, "flows": 1}, "2026-08-13")
    assert "Manual UI Check" in text
    assert "UNCHECKED" in text


def test_manual_check_section_present_when_findings_are_empty():
    text = render_sweep_markdown([], [], {"lists": 0, "flows": 0}, "2026-08-13")
    assert "Manual UI Check" in text
    assert "UNCHECKED" in text


def test_findings_sorted_by_object_type_then_id():
    list_findings = [
        {"id": "20", "name": "List Twenty", "path": "$.a"},
        {"id": "5", "name": "List Five", "path": "$.b"},
    ]
    flow_findings = [{"id": "1", "name": "Flow One", "path": "$.c"}]
    text = render_sweep_markdown(list_findings, flow_findings, {"lists": 2, "flows": 1}, "2026-08-13")
    flow_row = text.index("| flow | 1 |")
    list5_row = text.index("| list | 5 |")
    list20_row = text.index("| list | 20 |")
    assert flow_row < list5_row < list20_row


# --- Read-only-by-construction: no write-verb requests call anywhere in the module ---------

def test_module_contains_no_write_verb_requests_call():
    tree = ast.parse(MODULE_PATH.read_text())
    forbidden = {"post", "patch", "delete"}
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in forbidden and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id == "requests":
                offenders.append(f"requests.{node.func.attr}")
    assert offenders == [], f"found write-verb requests call(s): {offenders}"


# --- No-credentials skip-to-exit-0 ------------------------------------------------------

def test_main_skips_cleanly_with_no_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)
    out_path = tmp_path / "sweep.md"
    exit_code = sweep_tier_dependents.main(["--out", str(out_path)])
    assert exit_code == 0
    assert not out_path.exists()
