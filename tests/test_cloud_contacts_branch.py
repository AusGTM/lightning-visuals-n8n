# tests/test_cloud_contacts_branch.py
#
# Phase 16.2 Task 2 — offline proof that build_enrichment_cloud() carries the full
# contacts research->judge mirror: the ten contact-distinct nodes + Merge Winners are
# BFS-reachable from Webhook Trigger, both IF-false lanes fan straight into Merge
# Winners, the providers-bypass path still reaches the chain (research-only path, SC-3),
# and the contact research prompt names no company-ICP field (jobtitle/seniority-scoped,
# CONTEXT 1/7). Mirrors tests/test_cloud_companies_branch.py's BFS precedent.
import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_cloud_workflows import ENRICH_MERGE  # noqa: E402
from build_cloud_workflows import (  # noqa: E402
    CONTACTS_TARGET,
    _enrich_build_research_request_js,
)

WORKFLOW_PATH = ROOT / "n8n" / "wf_enrichment_cloud.json"


def _load():
    return json.loads(WORKFLOW_PATH.read_text())


def _reachable_from(doc: dict, start: str) -> set:
    conns = doc["connections"]
    seen = {start}
    q = deque([start])
    while q:
        cur = q.popleft()
        for branch in conns.get(cur, {}).get("main", []):
            for edge in branch:
                nm = edge["node"]
                if nm not in seen:
                    seen.add(nm)
                    q.append(nm)
    return seen


CONTACT_CHAIN_NODES = [
    "Contact Research Trigger Gate", "IF Contact Research Needed",
    "Build Contact Research Request", "Contact Web Research", "Validate Contact Research",
    "Contact Judge Gate", "IF Contact Needs Judge", "Build Contact Judge Request",
    "Contact Judge Call", "Apply Contact Judge Verdict",
]


def test_all_contact_chain_nodes_and_merge_winners_are_bfs_reachable_from_webhook_trigger():
    doc = _load()
    reachable = _reachable_from(doc, "Webhook Trigger")
    node_names = {n["name"] for n in doc["nodes"]}
    missing_from_workflow = [n for n in CONTACT_CHAIN_NODES if n not in node_names]
    assert not missing_from_workflow, f"expected contact chain node(s) not built: {missing_from_workflow}"
    unreachable = [n for n in CONTACT_CHAIN_NODES if n not in reachable]
    assert not unreachable, f"contact chain node(s) not reachable from Webhook Trigger: {unreachable}"
    assert "Merge Winners" in reachable


def test_both_if_false_lanes_fan_straight_into_merge_winners():
    doc = _load()
    conns = doc["connections"]
    research_false = [e["node"] for e in conns["IF Contact Research Needed"]["main"][1]]
    judge_false = [e["node"] for e in conns["IF Contact Needs Judge"]["main"][1]]
    assert research_false == ["Merge Winners"]
    assert judge_false == ["Merge Winners"]


def test_providers_bypass_only_path_still_reaches_the_contact_chain():
    """SC-3's research-only path: following ONLY the provider gates' false/bypass lanes
    (providers: none/off, zero provider HTTP calls) from Enrichment Gate must still reach
    the contact research chain entry, not dead-end before it."""
    doc = _load()
    reachable = _reachable_from(doc, "Enrichment Gate")
    assert "Contact Research Trigger Gate" in reachable
    assert "Merge Winners" in reachable


def test_contact_research_prompt_names_no_company_icp_field():
    """CONTEXT 1/7: the contact research chain is jobtitle/seniority-scoped only — no
    company-ICP field (org_type, produces_content, hardware/gambling vendor flags, revenue/
    employee bands) may appear in the built request-body wrapper."""
    body_js = _enrich_build_research_request_js(cloud=True, target=CONTACTS_TARGET)
    forbidden = ["lv_org_type", "lv_produces_content", "lv_content_type",
                 "lv_is_hardware_vendor", "lv_is_gambling_operator",
                 "lv_revenue_band", "lv_employee_band"]
    for field in forbidden:
        assert field not in body_js, f"contact research request body references company-ICP field {field!r}"


def test_contact_research_never_names_pii_fields():
    """CLAUDE.md Section 16 / CONTEXT: no phone/email/mobile field ever enters the
    contact research prompt — jobtitle/seniority ONLY."""
    body_js = _enrich_build_research_request_js(cloud=True, target=CONTACTS_TARGET)
    for forbidden in ["mobilephone", "\"phone\"", "\"email\""]:
        assert forbidden not in body_js, f"contact research request body references PII field {forbidden!r}"
    assert "jobtitle" in body_js
    assert "seniority" in body_js


def test_merge_winners_node_present_and_the_fold_is_wired_in():
    doc = _load()
    names = [n["name"] for n in doc["nodes"]]
    assert names.count("Merge Winners") >= 1
    assert "foldContactResearch" in ENRICH_MERGE, "ENRICH_MERGE must call the write-safety fold"


def test_ten_contact_distinct_nodes_are_code_or_if_or_http_as_expected():
    doc = _load()
    by_name = {n["name"]: n for n in doc["nodes"] if n["name"] in CONTACT_CHAIN_NODES}
    expected_types = {
        "Contact Research Trigger Gate": "n8n-nodes-base.code",
        "IF Contact Research Needed": "n8n-nodes-base.if",
        "Build Contact Research Request": "n8n-nodes-base.code",
        "Contact Web Research": "n8n-nodes-base.httpRequest",
        "Validate Contact Research": "n8n-nodes-base.code",
        "Contact Judge Gate": "n8n-nodes-base.code",
        "IF Contact Needs Judge": "n8n-nodes-base.if",
        "Build Contact Judge Request": "n8n-nodes-base.code",
        "Contact Judge Call": "n8n-nodes-base.httpRequest",
        "Apply Contact Judge Verdict": "n8n-nodes-base.code",
    }
    for name, expected_type in expected_types.items():
        assert by_name[name]["type"] == expected_type
