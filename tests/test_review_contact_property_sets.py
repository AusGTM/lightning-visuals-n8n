"""Phase 54 Plan 06 (WR-02) — drift guard for the contacts review-decision baseline.

Two assertions:
  (a) every config/field_policy.yaml `contacts` key appears in
      REVIEW_CONTACT_DECISION_PROPERTIES_CSV -- the non-clobber invariant. A policy field
      added later and not refetched here comes back `undefined` to reviewApply, which
      normalizes it to `null` and silently reads a manually-edited field as unchanged
      (the exact bypass WR-02 named).
  (b) against the CHECKED-IN n8n/wf_review_decision_cloud.json (not an in-memory
      build_cloud() result): `Review Contact Fetch By Id` and `Review Contact Verify
      Fetch` request a representative unfetched-today policy field (`mobilephone`), and
      `Review Queue Contact Search` does not -- proving the split reached the built
      artifact and doubling as a currency guard for these three nodes.
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_cloud_workflows as bcw  # noqa: E402

BUILT_JSON = ROOT / "n8n" / "wf_review_decision_cloud.json"


def _yaml_contacts_policy_keys():
    return set(yaml.safe_load((ROOT / "config" / "field_policy.yaml").read_text())["contacts"])


def test_decision_csv_carries_every_contacts_policy_key():
    decision_keys = set(bcw.REVIEW_CONTACT_DECISION_PROPERTIES_CSV.split(","))
    yaml_keys = _yaml_contacts_policy_keys()
    missing = yaml_keys - decision_keys
    assert not missing, (
        f"REVIEW_CONTACT_DECISION_PROPERTIES_CSV is missing config/field_policy.yaml "
        f"`contacts` keys: {sorted(missing)} -- edit both in the same commit, or "
        f"reviewApply's compare-and-set baseline cannot see these fields live."
    )


def _node_by_name(nodes, name):
    for n in nodes:
        if n.get("name") == name:
            return n
    raise AssertionError(f"node {name!r} not found in {BUILT_JSON}")


def _json_body(node):
    return node["parameters"]["jsonBody"]


def test_built_json_decision_nodes_request_widened_set_and_queue_node_does_not():
    data = json.loads(BUILT_JSON.read_text())
    nodes = data["nodes"]

    fetch_by_id = _node_by_name(nodes, "Review Contact Fetch By Id")
    verify_fetch = _node_by_name(nodes, "Review Contact Verify Fetch")
    queue_search = _node_by_name(nodes, "Review Queue Contact Search")

    marker = "mobilephone"  # a representative unfetched-today DEFAULT_CONTACT_POLICY key
    assert marker in _json_body(fetch_by_id), (
        f"{BUILT_JSON} is stale -- 'Review Contact Fetch By Id' does not request "
        f"{marker!r}. Regenerate with: python3 scripts/build_cloud_workflows.py"
    )
    assert marker in _json_body(verify_fetch), (
        f"{BUILT_JSON} is stale -- 'Review Contact Verify Fetch' does not request "
        f"{marker!r}. Regenerate with: python3 scripts/build_cloud_workflows.py"
    )
    assert marker not in _json_body(queue_search), (
        f"{BUILT_JSON}'s 'Review Queue Contact Search' unexpectedly requests {marker!r} -- "
        f"the up-to-100-record queue read must stay narrow (mirrors the companies lane's "
        f"own wide/narrow split); do not widen REVIEW_CONTACT_QUEUE_PROPERTIES_CSV."
    )
