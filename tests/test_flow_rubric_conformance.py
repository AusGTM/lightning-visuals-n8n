# tests/test_flow_rubric_conformance.py
#
# Phase 40 Plan 01 (D-05) — offline conformance guard. Asserts every archived
# config/hubspot_flows/*.after.json flow's branch-value point table equals
# config/icp_scoring.yaml's rubric of record. Glob-driven parametrization: a
# mapper flow with no .after.json yet is simply not collected, so this module
# stays green through waves 2-4 as each later plan (40-04/40-05/40-06) adds its
# own .after.json and its own extractor. Zero network — pure JSON/YAML reads.
import glob
import json
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
RUBRIC_PATH = ROOT / "config" / "icp_scoring.yaml"
FLOWS_DIR = ROOT / "config" / "hubspot_flows"


def load_rubric() -> dict:
    with RUBRIC_PATH.open() as f:
        return yaml.safe_load(f)


def load_flow(path) -> dict:
    with Path(path).open() as f:
        return json.load(f)


def extract_org_type_branch_scores(flow: dict) -> dict:
    """Walks the STATIC_BRANCH action keyed on lv_org_type and returns
    {branch_value: int(points)} by following each branch's nextActionId to the
    SINGLE_CONNECTION action that sets org_type_score. 4626124224
    ("Update Score Based on Org Type") is the only flow this extractor targets;
    40-05/40-06 add their own extractors for geography/revenue/tier rather than
    overloading this one."""
    actions_by_id = {a["actionId"]: a for a in flow["actions"]}
    branch_action = next(
        a for a in flow["actions"]
        if a.get("type") == "STATIC_BRANCH"
        and a.get("inputValue", {}).get("propertyName") == "lv_org_type"
    )
    scores = {}
    for branch in branch_action["staticBranches"]:
        target = actions_by_id[branch["connection"]["nextActionId"]]
        scores[branch["branchValue"]] = int(target["fields"]["value"]["staticValue"])
    return scores


def find_static_branch_action(flow: dict, property_name: str):
    """Returns the STATIC_BRANCH action keyed on property_name, or None if the
    flow has no such branch (40-04's two-terms-only extractors)."""
    return next(
        (a for a in flow["actions"]
         if a.get("type") == "STATIC_BRANCH"
         and a.get("inputValue", {}).get("propertyName") == property_name),
        None,
    )


def extract_true_default_scores(flow: dict, property_name: str) -> dict:
    """Walks a STATIC_BRANCH action keyed on property_name that has exactly one
    named branch ("true") plus a defaultBranch (40-04's produces-content and
    gambling mapper shape — every other value, including "false"/empty/absent,
    falls to the same default action). Returns
    {"true": int(points), "__default__": int(points)}."""
    actions_by_id = {a["actionId"]: a for a in flow["actions"]}
    branch_action = find_static_branch_action(flow, property_name)
    true_branch = next(b for b in branch_action["staticBranches"] if b["branchValue"] == "true")
    true_target = actions_by_id[true_branch["connection"]["nextActionId"]]
    default_target = actions_by_id[branch_action["defaultBranch"]["nextActionId"]]
    return {
        "true": int(true_target["fields"]["value"]["staticValue"]),
        "__default__": int(default_target["fields"]["value"]["staticValue"]),
    }


def written_property_names(flow: dict) -> set:
    """All company property names any SINGLE_CONNECTION action in this flow
    writes to. Used to assert a mapper flow's blast radius — T-40-15's
    mitigation for the gambling flow re-conflating the deduction with the
    veto."""
    return {
        a["fields"]["property_name"]
        for a in flow["actions"]
        if a.get("type") == "SINGLE_CONNECTION"
    }


def _after_json_paths() -> list:
    return sorted(glob.glob(str(FLOWS_DIR / "*.after.json")))


def _is_flow(doc: dict) -> bool:
    """Distinguishes an Automation v4 flow archive from a property-definition
    snapshot (both live in config/hubspot_flows/*.after.json, e.g. 40-04 Task 3's
    lv_icp_fit_score-property.after.json) — flows have an "actions" list, property
    snapshots don't."""
    return "actions" in doc


def test_rubric_loads():
    rubric = load_rubric()
    assert "base_score" in rubric
    assert "org_type" in rubric["base_score"]


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_org_type_flow_matches_rubric(flow_path):
    flow = load_flow(flow_path)
    if not _is_flow(flow):
        pytest.skip(f"{flow_path} is not a flow archive")
    has_org_type_branch = any(
        a.get("type") == "STATIC_BRANCH"
        and a.get("inputValue", {}).get("propertyName") == "lv_org_type"
        for a in flow["actions"]
    )
    if not has_org_type_branch:
        pytest.skip(f"{flow_path} has no lv_org_type STATIC_BRANCH action")

    rubric_org_type = load_rubric()["base_score"]["org_type"]
    flow_scores = extract_org_type_branch_scores(flow)

    assert set(flow_scores.keys()) <= set(rubric_org_type.keys()), (
        f"flow branch keys {sorted(flow_scores.keys())} must be a subset of "
        f"rubric org_type keys {sorted(rubric_org_type.keys())}"
    )
    for branch_value, points in flow_scores.items():
        assert points == rubric_org_type[branch_value], (
            f"{flow_path}: branch '{branch_value}' scores {points}, "
            f"rubric says {rubric_org_type[branch_value]}"
        )


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_produces_content_flow_matches_rubric(flow_path):
    """40-04 (ENGINE-02) — produces_content_score's mapper flow branch table must
    equal config/icp_scoring.yaml's base_score.produces_content: true -> 20,
    everything else (including "false"/empty/absent) -> 0."""
    flow = load_flow(flow_path)
    if not _is_flow(flow):
        pytest.skip(f"{flow_path} is not a flow archive")
    if find_static_branch_action(flow, "lv_produces_content") is None:
        pytest.skip(f"{flow_path} has no lv_produces_content STATIC_BRANCH action")

    rubric = load_rubric()["base_score"]["produces_content"]
    scores = extract_true_default_scores(flow, "lv_produces_content")

    assert scores["true"] == rubric[True], (
        f"{flow_path}: 'true' branch scores {scores['true']}, rubric says {rubric[True]}"
    )
    assert scores["__default__"] == rubric[False] == rubric["unknown"], (
        f"{flow_path}: default branch scores {scores['__default__']}, "
        f"rubric says false={rubric[False]} unknown={rubric['unknown']}"
    )
    assert written_property_names(flow) == {"produces_content_score"}, (
        f"{flow_path}: must write only produces_content_score, "
        f"found {written_property_names(flow)}"
    )


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_gambling_flow_matches_rubric(flow_path):
    """40-04 (ENGINE-05) — gambling_score's mapper flow branch table must equal
    config/icp_scoring.yaml's graduated_deductions.gambling_operator: true -> -20,
    everything else -> 0. The flow must write only gambling_score — never
    lv_anti_icp_flag or lv_org_type — so the deduction stays independent of both
    the veto and the org-type branch (F9's original defect, T-40-15)."""
    flow = load_flow(flow_path)
    if not _is_flow(flow):
        pytest.skip(f"{flow_path} is not a flow archive")
    if find_static_branch_action(flow, "lv_is_gambling_operator") is None:
        pytest.skip(f"{flow_path} has no lv_is_gambling_operator STATIC_BRANCH action")

    rubric_deduction = load_rubric()["graduated_deductions"]["gambling_operator"]
    scores = extract_true_default_scores(flow, "lv_is_gambling_operator")

    assert scores["true"] == rubric_deduction, (
        f"{flow_path}: 'true' branch scores {scores['true']}, "
        f"rubric graduated_deductions.gambling_operator says {rubric_deduction}"
    )
    assert scores["__default__"] == 0, (
        f"{flow_path}: default branch scores {scores['__default__']}, expected 0"
    )
    assert written_property_names(flow) == {"gambling_score"}, (
        f"{flow_path}: must write only gambling_score (T-40-15), "
        f"found {written_property_names(flow)}"
    )


FIT_SCORE_PROPERTY_PATH = FLOWS_DIR / "lv_icp_fit_score-property.after.json"

FIT_SCORE_COMPONENT_NAMES = (
    "org_type_score",
    "geography_score",
    "annual_revenue_score",
    "produces_content_score",
    "gambling_score",
)


def test_fit_score_formula_references_all_five_components():
    """40-04 Task 3 (D-06) — lv_icp_fit_score's archived post-PATCH calculationFormula
    must name all five component properties. Fails loudly if a term is dropped,
    reconstructed, or misspelled rather than extended from the fetched syntax."""
    if not FIT_SCORE_PROPERTY_PATH.exists():
        pytest.skip(f"{FIT_SCORE_PROPERTY_PATH} not archived yet")

    with FIT_SCORE_PROPERTY_PATH.open() as f:
        after = json.load(f)

    formula = after["calculationFormula"]
    for name in FIT_SCORE_COMPONENT_NAMES:
        assert name in formula, f"calculationFormula '{formula}' is missing '{name}'"
