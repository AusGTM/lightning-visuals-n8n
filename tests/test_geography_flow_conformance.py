# tests/test_geography_flow_conformance.py
#
# Phase 75 Plan 04 (D-75-09/D-75-11a) -- pins that
# config/hubspot_flows/4626722240-geography-score.after.json's geography branch `values`
# array is GENERATED from config/icp_scoring.yaml's regions.home by
# scripts/gen_geography_flow.py, never hand-edited. Regenerate with:
#   .venv/bin/python scripts/gen_geography_flow.py
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
# scripts/ is not a package -- same idiom as tests/test_check_schema_drift.py.
sys.path.insert(0, str(ROOT / "scripts"))

from src.icp_scoring import regions_home  # noqa: E402

FLOW_PATH = ROOT / "config" / "hubspot_flows" / "4626722240-geography-score.after.json"


def _geography_branch_values(body: dict) -> list:
    return (
        body["actions"][0]["listBranches"][0]["filterBranch"]["filterBranches"][0]
        ["filters"][0]["operation"]["values"]
    )


def test_committed_flow_branch_values_equal_regions_home_exactly():
    """RED until scripts/gen_geography_flow.py has been run once: the committed
    after.json still carries the pre-Phase-75 3-code list (["AU", "NZ", "ANZ"]), not the
    widened regions.home whitelist -- byte-equality including order."""
    body = json.loads(FLOW_PATH.read_text())
    assert _geography_branch_values(body) == list(regions_home()), (
        "config/hubspot_flows/4626722240-geography-score.after.json's geography branch "
        "is stale -- regenerate with: .venv/bin/python scripts/gen_geography_flow.py"
    )


def test_render_is_idempotent():
    from gen_geography_flow import render

    body = json.loads(FLOW_PATH.read_text())
    once = render(copy.deepcopy(body))
    twice = render(copy.deepcopy(once))
    assert json.dumps(once, sort_keys=True) == json.dumps(twice, sort_keys=True)


def test_render_raises_when_zero_matching_filters():
    from gen_geography_flow import render

    body = json.loads(FLOW_PATH.read_text())
    target = (
        body["actions"][0]["listBranches"][0]["filterBranch"]["filterBranches"][0]
        ["filters"][0]
    )
    target["property"] = "some_other_property"
    with pytest.raises(AssertionError):
        render(body)


def test_render_raises_when_two_matching_filters():
    from gen_geography_flow import render

    body = json.loads(FLOW_PATH.read_text())
    existing_filter = (
        body["actions"][0]["listBranches"][0]["filterBranch"]["filterBranches"][0]
        ["filters"][0]
    )
    body["actions"][0]["listBranches"][0]["filterBranch"]["filterBranches"][0]["filters"].append(
        copy.deepcopy(existing_filter)
    )
    with pytest.raises(AssertionError):
        render(body)
