# tests/test_bug10_company_search_transport.py
#
# BUG 10 (found live 2026-07-28, Phase 16.5 companies canary; fixed Phase 16.6):
# n8n's native `n8n-nodes-base.hubspot` node with `resource: company, operation: search`
# emits ONE item whose `json` is `null` on this n8n Cloud instance. The BYTE-IDENTICAL
# request — same filter, same property list, read straight out of the built node — issued
# directly against `POST /crm/v3/objects/companies/search` returns HTTP 200, `total:1`,
# with the real record. The node does not throw; execution status is `success`. The
# `resource: contact` twin (structurally identical, only `resource` differs) works.
#
# This is an n8n-platform-level defect (an opaque, non-vendored third-party node
# implementation, not this repo's code), confirmed only by a live differential test that
# this session may NOT re-run (deployment is deliberately disarmed). Per 16.6-CONTEXT.md,
# the offline-reproducible level is the NODE SHAPE / EMITTED REQUEST: this file asserts the
# six affected search nodes use a credential-bound httpRequest transport instead of the
# implicated native-node code path, and that the request each one emits is semantically
# identical (URL, filters, properties) to the native node it replaces — the strongest
# offline guard available for a defect that only manifests live.
#
# RED-before-green: every assertion in this file failed against the pre-fix committed
# workflow JSON (the six nodes were `n8n-nodes-base.hubspot` with `operation: "search"`,
# the exact shape implicated live). See 16.6-01-SUMMARY / the debug session file for the
# captured red-run output.
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_cloud_workflows import ENRICH_COMPANY_SEARCH_PROPERTIES_CSV  # noqa: E402

N8N_DIR = ROOT / "n8n"
SEARCH_URL = "https://api.hubapi.com/crm/v3/objects/companies/search"

# The six nodes enumerated in 16.6-CONTEXT.md's blast radius, and the exact filter/
# property shape each carries today (verified against the committed native-node JSON
# before this fix — see the debug session Evidence log). `body_tokens` are substrings the
# new node's `jsonBody` expression must contain — the same "assert token in code" idiom
# already used throughout this test suite (e.g. test_cloud_companies_branch.py) for
# checking generated expression/JS strings without hand-rolling a parser.
NODES = {
    "HubSpot Company Search": {
        "workflow": "wf_enrichment_cloud.json",
        "properties_csv": ENRICH_COMPANY_SEARCH_PROPERTIES_CSV,
        "body_tokens": [
            'propertyName: "domain"', 'operator: "EQ"',
            "$json.identity_keys.domain",
        ],
    },
    "HubSpot Company Fetch By Id": {
        "workflow": "wf_enrichment_cloud.json",
        "properties_csv": ENRICH_COMPANY_SEARCH_PROPERTIES_CSV,
        "body_tokens": [
            'propertyName: "hs_object_id"', 'operator: "EQ"',
            "$('Build Company Identity').item.json.object_id",
        ],
    },
    "SJ-3 Search (requested poller)": {
        "workflow": "wf_scheduled_maintenance_cloud.json",
        "properties_csv": "hs_object_id,lv_enrichment_requested,lv_enrichment_status",
        "body_tokens": [
            'propertyName: "lv_enrichment_requested"', 'operator: "EQ"', 'value: "true"',
            'propertyName: "lv_enrichment_status"', 'operator: "NEQ"', 'value: "running"',
        ],
    },
    "SJ-1 Search (input-gap scan)": {
        "workflow": "wf_scheduled_maintenance_cloud.json",
        # BUG 24: domain added so the lane's write gate can be satisfied by
        # TEST_RECORD_DOMAINS at all (it read it.json.domain, which the lane
        # never emitted, making the domain allowlist silently inert).
        "properties_csv": "hs_object_id,domain,lv_org_type,lv_produces_content",
        "body_tokens": [
            'propertyName: "lv_org_type"', 'operator: "NOT_HAS_PROPERTY"',
            'operator: "EQ"', 'value: "unknown"',
            'propertyName: "lv_produces_content"',
        ],
    },
    "SJ-2 Search (stale refresh)": {
        "workflow": "wf_scheduled_maintenance_cloud.json",
        "properties_csv": "hs_object_id,domain,lv_org_type,lv_produces_content,"  # BUG 24
                           "lv_org_type_verified_at,lv_produces_content_verified_at",
        "body_tokens": [
            'propertyName: "lv_org_type_verified_at"', 'operator: "LT"',
            'propertyName: "lv_produces_content_verified_at"',
            "$json.cutoff_ms",
        ],
    },
    "Review Search (approved=true)": {
        "workflow": "wf_scheduled_maintenance_cloud.json",
        "properties_csv": "hs_object_id,domain,lv_org_type,lv_produces_content,lv_revenue_band,"  # BUG 24
                           "lv_employee_band,lv_content_type,lv_sponsorship_reliant,"
                           "lv_is_hardware_vendor,lv_is_gambling_operator,"
                           "lv_enrichment_review_candidate_json,lv_enrichment_needs_review,"
                           "lv_enrichment_review_approved,lv_enrichment_review_reason",
        "body_tokens": [
            'propertyName: "lv_enrichment_review_approved"', 'operator: "EQ"', 'value: "true"',
        ],
    },
}

# The write operation on `company` that BUG 10's live trace never exercised (the trace
# only covered `operation: search`) AND that Phase 16.7-01 also left untouched:
# `company:create`. Pinned here as UNCHANGED so a future edit cannot silently claim it was
# fixed too. `HubSpot Company Update` was REMOVED from this list in Phase 16.7-01 (BUG
# 11): that node moved off the native hubspot node entirely (onto a credential-bound
# httpRequest PATCH — see tests/test_write_node_transport.py), so "unchanged" no longer
# describes it — pinning it here now would be false, not merely stale.
UNCHANGED_WRITE_NODES = ["HubSpot Company Create"]

# Scoped to the contacts SEARCH/FETCH nodes this guard was actually written to protect —
# the ONE live-proven path (resource:contact/operation:search returns the real record),
# which BUG 10's fix left byte-identical. "HubSpot Create"/"HubSpot Update" were REMOVED
# from the wf_enrichment_cloud.json list in Phase 16.7-01: "HubSpot Update" moved
# transport entirely (BUG 11 fix, see tests/test_write_node_transport.py) and so is no
# longer byte-identical to HEAD by design; "HubSpot Create" was never a search/fetch node
# this guard was scoped to protect in the first place — its own unchanged-ness is now
# pinned by tests/test_write_node_transport.py's create-node guard instead.
#
# "Dedupe Set Needs Review" was REMOVED for the same reason as "HubSpot Update", on the
# same grounds (BUG 18, 2026-07-29): it was never a contacts SEARCH/FETCH node, and it has
# moved off the native node onto the shared credential-bound PATCH. It could not have been
# byte-identical-and-correct in any case — it carried `operation: "update"`, which does not
# exist for resource:contact, so what this guard was pinning was a node with BUG 10's own
# defect. Its shape is now pinned by tests/test_hubspot_native_operation_validity.py.
# "HubSpot Search by Email" was REMOVED on the same grounds (BUG 22a, 2026-07-29): what
# this guard was pinning byte-for-byte was a node with an EMPTY filterGroupsValues — a
# search-by-email that searched by nothing and returned the portal's newest 100 contacts.
# Its correct shape is now pinned by tests/test_ingest_search_contract.py instead.
CONTACT_NODES_BY_WORKFLOW = {
    "wf_enrichment_cloud.json": ["HubSpot Search", "HubSpot Fetch By Id"],
    "wf_scheduled_maintenance_cloud.json": ["Dedupe Search (candidate contacts)"],
}


def _load(name: str) -> dict:
    return json.loads((N8N_DIR / name).read_text())


def _node(doc: dict, name: str) -> dict:
    return next(n for n in doc["nodes"] if n["name"] == name)


def _extract_properties(json_body: str) -> list:
    """Pulls the `properties: [...]` array literal out of a jsonBody expression and
    parses it as JSON — every entry is a plain double-quoted string (never a raw
    expression), so this is always valid JSON, unlike the surrounding object literal
    (which has unquoted keys and, for dynamic filter values, unquoted expressions)."""
    m = re.search(r"properties:\s*(\[[^\]]*\])", json_body)
    assert m, f"no `properties: [...]` array found in jsonBody: {json_body!r}"
    return json.loads(m.group(1))


def _csv_to_list(csv: str) -> list:
    return [p.strip() for p in csv.split(",") if p.strip()]


# --- vacuity guards ---------------------------------------------------------------------

def test_workflow_files_exist_and_carry_every_target_node():
    for name, cfg in NODES.items():
        doc = _load(cfg["workflow"])
        assert any(n["name"] == name for n in doc["nodes"]), (
            f"{name!r} not found in {cfg['workflow']} — fixture/build drifted"
        )


# --- the six affected nodes must NOT use the implicated native transport ----------------

@pytest.mark.parametrize("name", list(NODES))
def test_company_search_node_does_not_use_the_implicated_native_hubspot_search_op(name):
    """BUG 10: `n8n-nodes-base.hubspot` `resource: company, operation: search` emits a
    null-json item on this n8n Cloud instance (live-confirmed, 16.6-CONTEXT.md). This is
    the mechanical form of that fact: no node in the blast radius may carry that exact
    (type, resource, operation) triple after the fix."""
    cfg = NODES[name]
    doc = _load(cfg["workflow"])
    node = _node(doc, name)
    is_implicated_shape = (
        node.get("type") == "n8n-nodes-base.hubspot"
        and node.get("parameters", {}).get("resource") == "company"
        and node.get("parameters", {}).get("operation") == "search"
    )
    assert not is_implicated_shape, (
        f"{name} in {cfg['workflow']} still uses the native hubspot "
        "resource:company/operation:search shape BUG 10 proved returns null json live"
    )


# --- the replacement: credential-bound httpRequest, predefinedCredentialType -----------

@pytest.mark.parametrize("name", list(NODES))
def test_company_search_node_is_credential_bound_httprequest_via_hubspot_apptoken(name):
    cfg = NODES[name]
    doc = _load(cfg["workflow"])
    node = _node(doc, name)
    assert node["type"] == "n8n-nodes-base.httpRequest", (
        f"{name}: expected httpRequest transport, got {node.get('type')!r}"
    )
    params = node["parameters"]
    assert params.get("method") == "POST"
    assert params.get("url") == SEARCH_URL, f"{name}: wrong URL {params.get('url')!r}"
    # predefinedCredentialType reuses the SAME "LV HubSpot" credential the native node
    # used (hubspotAppToken) — never a new credential object, never $env/$vars.
    assert params.get("authentication") == "predefinedCredentialType", (
        f"{name}: authentication must be predefinedCredentialType so "
        "_node_requires_credential() treats this node as credential-bearing "
        "(deploy_n8n_workflows.py's _CREDENTIAL_BEARING_HTTP_AUTH_MODES)"
    )
    assert params.get("nodeCredentialType") == "hubspotAppToken", (
        f"{name}: nodeCredentialType must be hubspotAppToken to reuse the LV HubSpot "
        "credential deploy_n8n_workflows.py's NODE_CREDENTIAL_MAP already binds by this name"
    )
    assert node.get("onError") == "continueRegularOutput", (
        f"{name}: must keep the fail-closed onError the native node carried"
    )


@pytest.mark.parametrize("name", list(NODES))
def test_company_search_node_requests_the_expected_properties_as_a_real_json_array(name):
    """Properties must be a genuine JSON array in the body (never a CSV string) — the
    exact class of defect tests/test_hubspot_node_auth.py's CSV/list guard exists to
    catch for native hubspot nodes; this is that same guard's httpRequest-transport
    equivalent (that guard stops covering these 6 nodes once they change type)."""
    cfg = NODES[name]
    doc = _load(cfg["workflow"])
    node = _node(doc, name)
    body = node["parameters"]["jsonBody"]
    assert _extract_properties(body) == _csv_to_list(cfg["properties_csv"]), (
        f"{name}: jsonBody properties do not match the expected CSV-derived list"
    )


@pytest.mark.parametrize("name", list(NODES))
def test_company_search_node_body_preserves_the_original_filter_semantics(name):
    """Parity check against the native node's filterGroupsUi this node replaces (RESEARCH
    Pitfall 3 envelope: groups OR, filters-within-group AND) — the strongest offline proof
    available that the httpRequest replacement emits the SAME logical request the
    byte-identical live curl already proved succeeds."""
    cfg = NODES[name]
    doc = _load(cfg["workflow"])
    node = _node(doc, name)
    body = node["parameters"]["jsonBody"]
    for token in cfg["body_tokens"]:
        assert token in body, f"{name}: jsonBody missing expected token {token!r}\n{body}"


# --- company:create — explicitly UNCHANGED, defect status UNKNOWN ----------------------

@pytest.mark.parametrize("name", UNCHANGED_WRITE_NODES)
def test_company_create_is_not_a_search_node(name):
    """BUG 10's live trace exercised ONLY `operation: search`, and its fix must never have
    spread to the create path. This originally pinned the create node as NATIVE and
    unverified; Phase 16.9 (BUG 13) subsequently moved it onto a credential-bound
    httpRequest POST for reasons entirely unrelated to BUG 10 — see
    tests/test_write_node_transport.py for that guard. What this test still protects is the
    original property: whatever transport the create node uses, it is a CREATE against the
    collection endpoint and not a search."""
    doc = _load("wf_enrichment_cloud.json")
    node = _node(doc, name)
    params = node["parameters"]
    assert node["type"] == "n8n-nodes-base.httpRequest"
    assert params["method"] == "POST"
    assert params["url"].rstrip("/").endswith("/crm/v3/objects/companies")
    assert "/search" not in params["url"]

# --- contacts: byte-identical to HEAD (the one live-proven path must not regress) ------

def _git_show_head(rel_path: str) -> dict:
    out = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout
    return json.loads(out)


@pytest.mark.parametrize("workflow,names", list(CONTACT_NODES_BY_WORKFLOW.items()))
def test_every_contact_node_is_byte_identical_to_head(workflow, names):
    """Contacts is the one live-proven path (resource:contact/operation:search returns
    the real record). Proves by diff — not just "we didn't mean to touch it" — that every
    contact:search/create/update node's type AND parameters are untouched by this fix."""
    head_doc = _git_show_head(f"n8n/{workflow}")
    current_doc = _load(workflow)
    for name in names:
        head_node = _node(head_doc, name)
        current_node = _node(current_doc, name)
        assert current_node["type"] == head_node["type"], name
        assert current_node["parameters"] == head_node["parameters"], (
            f"{name} in {workflow}: parameters changed vs HEAD — contacts must stay "
            "byte-identical (16.6-CONTEXT.md hard requirement)"
        )
