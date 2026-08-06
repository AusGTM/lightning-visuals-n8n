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


def _after_json_paths() -> list:
    return sorted(glob.glob(str(FLOWS_DIR / "*.after.json")))


def test_rubric_loads():
    rubric = load_rubric()
    assert "base_score" in rubric
    assert "org_type" in rubric["base_score"]


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_org_type_flow_matches_rubric(flow_path):
    flow = load_flow(flow_path)
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
