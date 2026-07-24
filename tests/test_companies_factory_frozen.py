# tests/test_companies_factory_frozen.py
#
# Phase 16.2 Plan 01 Task 1 — the load-bearing byte-identity guard. The entire 16.2
# reuse strategy rests on one mechanical fact (RESEARCH SS1.1): inline() concatenates
# the FULL text of a shared JS module into a Code node's jsCode, so the only safe way
# to reuse the six companies research/judge/validate/apply-verdict factories for
# contacts is to parameterize the PYTHON factories by a `target` config that DEFAULTS
# to companies and reproduces today's exact string.
#
# This test is INTEGRITY-STRONG by construction (gpt #4): it CALLS
# build_enrichment_cloud() and build_enrichment_local_live() itself and compares each
# companies Code node's FRESHLY-BUILT jsCode against a frozen fixture captured from the
# CURRENT (post-bd682a2) HEAD. A shared-module edit that changes companies jsCode
# without ever regenerating wf_enrichment_*.json still fails here — a fixture-vs-
# committed-JSON compare would not catch that.
#
# The fixture (tests/fixtures/companies_jscode_frozen.json) is re-baselined ONLY by an
# explicit, reviewed act — never as a routine "make the test pass" step.
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_cloud_workflows as m  # noqa: E402

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "companies_jscode_frozen.json"
WF_CLOUD_PATH = ROOT / "n8n" / "wf_enrichment_cloud.json"
WF_LOCAL_LIVE_PATH = ROOT / "n8n" / "wf_enrichment_local_live.json"

FROZEN_NODE_NAMES = [
    "Research Trigger Gate",
    "Build Research Request",
    "Validate Research Output",
    "Judge Gate",
    "Build Judge Request",
    "Apply Judge Verdict",
    "Merge Company",
]


def _extract_code_nodes(doc: dict) -> dict:
    by_name = {}
    for n in doc["nodes"]:
        if n["name"] in FROZEN_NODE_NAMES and n.get("type") == "n8n-nodes-base.code":
            by_name[n["name"]] = n["parameters"]["jsCode"]
    return by_name


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def test_companies_cloud_jscode_is_byte_identical_to_frozen_fixture():
    """CALLS build_enrichment_cloud() in-test (not a committed-JSON compare) so a
    shared-module edit with no rebuild still fails this test."""
    fixture = _load_fixture()["cloud"]
    built = _extract_code_nodes(m.build_enrichment_cloud())
    missing = [n for n in FROZEN_NODE_NAMES if n not in built]
    assert not missing, f"companies cloud node(s) not built: {missing}"
    for name in FROZEN_NODE_NAMES:
        assert built[name] == fixture[name], (
            f"companies CLOUD {name!r} jsCode changed vs the frozen snapshot — "
            "byte-identity break (RESEARCH SS1.1)."
        )


def test_companies_local_live_jscode_is_byte_identical_to_frozen_fixture():
    """CALLS build_enrichment_local_live() in-test — same integrity property as the
    cloud test above, for the LOCAL-LIVE variant (differs from cloud only in
    flag-const baking, per _flag_const)."""
    fixture = _load_fixture()["local_live"]
    built = _extract_code_nodes(m.build_enrichment_local_live())
    missing = [n for n in FROZEN_NODE_NAMES if n not in built]
    assert not missing, f"companies local-live node(s) not built: {missing}"
    for name in FROZEN_NODE_NAMES:
        assert built[name] == fixture[name], (
            f"companies LOCAL-LIVE {name!r} jsCode changed vs the frozen snapshot — "
            "byte-identity break (RESEARCH SS1.1)."
        )


def test_committed_wf_enrichment_cloud_json_is_current():
    """Separate currency check: the COMMITTED wf_enrichment_cloud.json's companies
    node jsCode must match a fresh build too, so drift between source and the checked-
    in artifact is caught independently of the in-test-build guard above."""
    committed = _extract_code_nodes(json.loads(WF_CLOUD_PATH.read_text()))
    m._idc[0] = 0
    fresh = _extract_code_nodes(m.build_enrichment_cloud())
    for name in FROZEN_NODE_NAMES:
        assert committed[name] == fresh[name], (
            f"committed wf_enrichment_cloud.json {name!r} jsCode is stale — "
            "re-run scripts/build_cloud_workflows.py and commit the result."
        )


def test_committed_wf_enrichment_local_live_json_is_current():
    committed = _extract_code_nodes(json.loads(WF_LOCAL_LIVE_PATH.read_text()))
    m._idc[0] = 0
    fresh = _extract_code_nodes(m.build_enrichment_local_live())
    for name in FROZEN_NODE_NAMES:
        assert committed[name] == fresh[name], (
            f"committed wf_enrichment_local_live.json {name!r} jsCode is stale — "
            "re-run scripts/build_cloud_workflows.py and commit the result."
        )
