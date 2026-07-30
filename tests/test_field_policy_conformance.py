# tests/test_field_policy_conformance.py
#
# Plan 21-02 Task 2 — drift guard between the two hand-mirrored company field-policy
# tables: config/field_policy.yaml's `companies:` block (read by src/merge_policy.py,
# the Python oracle) and n8n/code/mergeCompanies.js's DEFAULT_COMPANY_POLICY (inlined
# into the live n8n Code node). Unlike the taxonomy vocabulary (which has a generator
# and its own currency test, see tests/test_taxonomy_conformance.py), this pair is
# maintained entirely by hand with zero protection today — this test IS the protection.
#
# The JS table is read by shelling out to `node` and asking the module for its own
# DEFAULT_COMPANY_POLICY serialized as JSON, never by regex-parsing the source: the
# object literal carries a computed value (lv_org_type.require_evidence_url_for is a
# reference to the generated taxonomy module, not a literal array), which a text parse
# would get wrong.
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not on PATH")


def _yaml_companies_policy():
    return yaml.safe_load((ROOT / "config" / "field_policy.yaml").read_text())["companies"]


def _js_companies_policy():
    result = subprocess.run(
        [NODE, "-e",
         "console.log(JSON.stringify(require('./n8n/code/mergeCompanies.js')"
         ".DEFAULT_COMPANY_POLICY))"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def yaml_policy():
    return _yaml_companies_policy()


@pytest.fixture(scope="module")
def js_policy():
    return _js_companies_policy()


def test_key_sets_are_identical(yaml_policy, js_policy):
    yaml_keys = set(yaml_policy)
    js_keys = set(js_policy)
    assert yaml_keys == js_keys, (
        f"field_policy.yaml companies block and mergeCompanies.js "
        f"DEFAULT_COMPANY_POLICY have drifted -- both surfaces must be edited in the "
        f"same commit. Missing from n8n/code/mergeCompanies.js: "
        f"{sorted(yaml_keys - js_keys)}; missing from config/field_policy.yaml: "
        f"{sorted(js_keys - yaml_keys)}"
    )


def test_class_matches_for_every_shared_key(yaml_policy, js_policy):
    mismatched = {
        field: (yaml_policy[field]["class"], js_policy[field]["class"])
        for field in yaml_policy
        if field in js_policy and yaml_policy[field]["class"] != js_policy[field]["class"]
    }
    assert not mismatched, (
        "config/field_policy.yaml and n8n/code/mergeCompanies.js disagree on `class` "
        f"for these fields (yaml, js): {mismatched}. Edit both files in the same commit."
    )


def test_min_confidence_matches_where_yaml_declares_it(yaml_policy, js_policy):
    # Only assert where YAML actually declares min_confidence -- the two veto_output
    # fields (lv_anti_icp_flag/lv_anti_icp_reason) carry no min_confidence on the YAML
    # side, and forcing a comparison there would just encode JS's placeholder 0 as a
    # second source of truth nobody asked for.
    mismatched = {
        field: (yaml_policy[field]["min_confidence"], js_policy[field].get("min_confidence"))
        for field in yaml_policy
        if field in js_policy
        and "min_confidence" in yaml_policy[field]
        and yaml_policy[field]["min_confidence"] != js_policy[field].get("min_confidence")
    }
    assert not mismatched, (
        "config/field_policy.yaml and n8n/code/mergeCompanies.js disagree on "
        f"`min_confidence` for these fields (yaml, js): {mismatched}. Edit both files "
        "in the same commit."
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
