# tests/test_fetch_by_id_topology.py
#
# Phase 16.4-02 Task 2 — pytest TOPOLOGY tier for the fetch-by-objectId lane 16.4-01 built.
# Pins the lane's structural guarantees mechanically (node placement, edge targets, node
# shapes, allowed HubSpot operations, node-name row recovery, credential binding) so a
# future edit that silently regresses any of them fails loudly here rather than being
# caught only by chance in an unrelated test. Mirrors tests/test_cloud_write_path.py's
# _load()/_node()/_reachable_from() helpers (same style, not a fork of the idiom) and
# tests/test_cloud_companies_branch.py's BFS-reachability convention.
#
# TEST-ONLY: this file makes zero production edits. A red here that implicates
# n8n/code/adaptFetchById.js or scripts/build_cloud_workflows.py is a STOP-and-report
# condition per this plan's frontmatter prohibitions, not a target to "fix" from here.
import json
import re
import sys
from collections import deque
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_cloud_workflows import (  # noqa: E402
    ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV,
    ENRICH_CONTACT_SEARCH_PROPERTIES_CSV,
    ENRICH_COMPANY_SEARCH_PROPERTIES_CSV,
)

import scripts.deploy_n8n_workflows as deploy  # noqa: E402

WORKFLOW_PATH = ROOT / "n8n" / "wf_enrichment_cloud.json"


def _load():
    return json.loads(WORKFLOW_PATH.read_text())


def _node(doc, name):
    return next(n for n in doc["nodes"] if n["name"] == name)


def _reachable_from(doc, start):
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


def _sole_outgoing_target(doc, name):
    """The one node `name`'s single outgoing edge targets — asserts there IS exactly one
    outgoing edge/branch/target first, so this can't silently pass on a shape it wasn't
    written to check."""
    conns = doc["connections"].get(name, {}).get("main", [])
    assert len(conns) == 1, f"{name} does not have exactly one outgoing branch: {conns}"
    assert len(conns[0]) == 1, f"{name}'s outgoing branch does not have exactly one edge: {conns[0]}"
    return conns[0][0]["node"]


def _strip_comments(js: str) -> str:
    """Drop lines whose trimmed form starts with `//` — a comment naming a node/token must
    not satisfy a structural guard that is supposed to prove the CODE does something."""
    return "\n".join(line for line in js.split("\n") if not line.strip().startswith("//"))


# Per-branch config, symmetric where the two branches' shapes are symmetric. Both branches
# use the credential-bound httpRequest transport as of BUG 23 (Phase 17.01) — contacts
# joined companies (BUG 10 / Phase 16.6) on the same shape, so `url` is now common to both.
BRANCHES = {
    "contacts": {
        "identity_builder": "Build Identity",
        "gate_if": "IF Bare Event",
        "fetch_node": "HubSpot Fetch By Id",
        "adapter": "Adapt Fetch By Id",
        "search_node": "HubSpot Search",
        "existing_gate": "Enrichment Gate",
        "resource": "contact",
        "properties_csv": ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV,
        "url": "https://api.hubapi.com/crm/v3/objects/contacts/search",
    },
    "companies": {
        "identity_builder": "Build Company Identity",
        "gate_if": "IF Company Bare Event",
        "fetch_node": "HubSpot Company Fetch By Id",
        "adapter": "Adapt Company Fetch By Id",
        "search_node": "HubSpot Company Search",
        "existing_gate": "Company Gate",
        "resource": "company",
        "properties_csv": ENRICH_COMPANY_SEARCH_PROPERTIES_CSV,
        "url": "https://api.hubapi.com/crm/v3/objects/companies/search",
    },
}


# --- gate existence + true/false lane targets -----------------------------------------

@pytest.mark.parametrize("branch", ["contacts", "companies"])
def test_gate_exists_and_true_false_lanes_target_fetch_and_search_respectively(branch):
    cfg = BRANCHES[branch]
    doc = _load()
    gate = _node(doc, cfg["gate_if"])
    assert gate["type"] == "n8n-nodes-base.if"
    true_branch, false_branch = doc["connections"][cfg["gate_if"]]["main"]
    assert true_branch[0]["node"] == cfg["fetch_node"], (
        f"{cfg['gate_if']} true lane must target {cfg['fetch_node']!r}"
    )
    assert false_branch[0]["node"] == cfg["search_node"], (
        f"{cfg['gate_if']} false lane must target {cfg['search_node']!r} (the existing lane, unmoved)"
    )


# --- gate is immediately downstream of its identity builder (placement, pinned) --------

@pytest.mark.parametrize("branch", ["contacts", "companies"])
def test_gate_sits_immediately_downstream_of_its_identity_builder(branch):
    cfg = BRANCHES[branch]
    doc = _load()
    target = _sole_outgoing_target(doc, cfg["identity_builder"])
    assert target == cfg["gate_if"], (
        f"{cfg['identity_builder']}'s single outgoing edge must target {cfg['gate_if']!r} "
        f"directly (got {target!r}) — the gate must sit immediately after the identity "
        "builder, never before Route By Object Type (RESEARCH: identity_keys isn't "
        "computable that early, and moving it would break the pinned Route By Object Type "
        "edge assertion in tests/test_cloud_write_path.py)"
    )


# --- fetch node shape: type, typeVersion, transport, onError, filter ---------------------
#
# BOTH branches use the credential-bound httpRequest transport as of BUG 23 (Phase 17.01):
# companies moved first (BUG 10 / Phase 16.6: n8n's HubSpot node has no
# `operation: "search"` for resource:company at all — confirmed by reading
# CompanyDescription.ts's companyOperations option list, which has no "search" entry, only
# create/delete/get/getAll/getRecentlyCreatedUpdated/searchByDomain/update; the native node
# silently returned json:null live). Contacts joined it for a different reason: its native
# `operation: "search"` genuinely exists and genuinely returns the record on a hit, but
# emits ZERO items on zero hits and n8n stops the chain there (live-established by
# execution 22, BUG 22) — see tests/test_enrichment_contacts_search_transport.py for the
# full guard, and tests/test_bug10_company_search_transport.py for the companies guard.

@pytest.mark.parametrize("branch", ["contacts", "companies"])
def test_fetch_node_is_credential_bound_httprequest_filtered_on_hs_object_id(branch):
    cfg = BRANCHES[branch]
    doc = _load()
    node = _node(doc, cfg["fetch_node"])
    assert node["type"] == "n8n-nodes-base.httpRequest"
    assert node["typeVersion"] == 4.2
    assert node["onError"] == "continueRegularOutput"
    params = node["parameters"]
    assert params["method"] == "POST"
    assert params["url"] == cfg["url"]
    assert params["authentication"] == "predefinedCredentialType"
    assert params["nodeCredentialType"] == "hubspotAppToken"
    body = params["jsonBody"]
    assert 'propertyName: "hs_object_id"' in body
    assert 'operator: "EQ"' in body
    assert cfg["identity_builder"] in body, (
        f"{cfg['fetch_node']}'s jsonBody must name its own branch's identity builder "
        f"({cfg['identity_builder']!r}) by node name"
    )


# --- property CSVs -----------------------------------------------------------------------

def test_contact_fetch_by_id_properties_csv_adds_company_and_linkedin_to_the_search_csv():
    assert ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV.startswith(ENRICH_CONTACT_SEARCH_PROPERTIES_CSV)
    added = ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV[len(ENRICH_CONTACT_SEARCH_PROPERTIES_CSV):]
    assert "company" in added.split(",")
    assert "lv_linkedin_url" in added.split(",")


def _csv_to_list(csv: str) -> list:
    return [p.strip() for p in csv.split(",") if p.strip()]


# NOTE (2026-07-28): the two tests below previously asserted that the built node's
# `properties` equalled the CSV STRING constant. That pinned a real bug: n8n forwards this
# value verbatim into the CRM v3 search body, where HubSpot requires an ARRAY and rejects a
# string with a 400 VALIDATION_ERROR. Confirmed live from an actual execution of
# HubSpot Fetch By Id. The CSV constants remain the readable source of truth at the call
# sites; the BUILT node now carries the split list, so these assertions compare against
# `_csv_to_list(...)`. The constants themselves are unchanged.

def _extract_json_body_properties(json_body: str) -> list:
    """Companies (BUG 10 / Phase 16.6): properties live inside the single jsonBody
    expression as a JS array literal, not a separate additionalFields.properties field.
    Every entry is a plain double-quoted string (never a raw expression), so the
    `properties: [...]` substring is always valid JSON on its own."""
    m = re.search(r"properties:\s*(\[[^\]]*\])", json_body)
    assert m, f"no `properties: [...]` array found in jsonBody: {json_body!r}"
    return json.loads(m.group(1))


def test_company_fetch_by_id_properties_are_identical_to_the_company_search_properties():
    doc = _load()
    fetch_props = _extract_json_body_properties(
        _node(doc, "HubSpot Company Fetch By Id")["parameters"]["jsonBody"])
    search_props = _extract_json_body_properties(
        _node(doc, "HubSpot Company Search")["parameters"]["jsonBody"])
    assert fetch_props == search_props == _csv_to_list(ENRICH_COMPANY_SEARCH_PROPERTIES_CSV)


# BUG 23 (Phase 17.01): contacts joined companies on the httpRequest jsonBody transport, so
# the two branches' property checks merge into one parametrized test using the SAME
# extractor (previously contacts read additionalFields.properties directly, since the
# native node carried a separate field for it).
@pytest.mark.parametrize("branch", ["contacts", "companies"])
def test_fetch_node_properties_match_expected(branch):
    cfg = BRANCHES[branch]
    doc = _load()
    node = _node(doc, cfg["fetch_node"])
    body_props = _extract_json_body_properties(node["parameters"]["jsonBody"])
    assert body_props == _csv_to_list(cfg["properties_csv"])


# --- adapter convergence: both adapters' single outgoing edge targets the EXISTING gate --

@pytest.mark.parametrize("branch", ["contacts", "companies"])
def test_adapter_converges_on_the_existing_gate(branch):
    cfg = BRANCHES[branch]
    doc = _load()
    assert _node(doc, cfg["adapter"])["type"] == "n8n-nodes-base.code"
    target = _sole_outgoing_target(doc, cfg["adapter"])
    assert target == cfg["existing_gate"], (
        f"{cfg['adapter']}'s single outgoing edge must target {cfg['existing_gate']!r} — "
        "both lanes (fetch-by-id and the existing search) must converge on the SAME gate"
    )


# --- the generic guard: no native HubSpot node remains in this workflow ----------------
#
# BUG 23 (Phase 17.01): this used to be a mechanical guard against the legacy
# single-record retrieval operation, over EVERY n8n-nodes-base.hubspot node in the built
# workflow — not just the two new fetch nodes. It is now VACUOUS for wf_enrichment_cloud
# .json: the contacts transport swap left zero native n8n-nodes-base.hubspot nodes in this
# workflow (companies moved in Phase 16.6), so there is nothing left for an
# operation-allowlist to check. Loosening/deleting it would silently stop catching a
# future regression; instead it asserts the stronger fact directly — the reason the
# allowlist mattered in the first place (RESEARCH Pitfall 1: the legacy single-record
# retrieval operation routes to a sunset endpoint with a non-flat property shape) no
# longer applies here because the operation-dispatching node type itself is gone.

def test_no_native_hubspot_node_remains_in_the_workflow():
    doc = _load()
    native = [n["name"] for n in doc["nodes"] if n["type"] == "n8n-nodes-base.hubspot"]
    assert not native, (
        f"wf_enrichment_cloud.json still contains native n8n-nodes-base.hubspot node(s): "
        f"{native} — BUG 23's fix requires zero native HubSpot nodes in this workflow"
    )


# --- node-name row recovery (bd682a2 guard), stated structurally -----------------------

@pytest.mark.parametrize("branch", ["contacts", "companies"])
def test_adapter_jscode_reads_its_identity_builder_and_fetch_node_by_name_and_never_the_bare_current_item(branch):
    cfg = BRANCHES[branch]
    doc = _load()
    code = _strip_comments(_node(doc, cfg["adapter"])["parameters"]["jsCode"])
    assert f"$('{cfg['identity_builder']}')" in code, (
        f"{cfg['adapter']} must recover the pre-hop row from {cfg['identity_builder']!r} by node name"
    )
    assert f"$('{cfg['fetch_node']}')" in code, (
        f"{cfg['adapter']} must read the fetch response from {cfg['fetch_node']!r} by node name"
    )
    bare_json = re.findall(r"\$json\b", code)
    bare_input = re.findall(r"\$input\b", code)
    assert not bare_json and not bare_input, (
        f"{cfg['adapter']} reads the bare current item ($json/$input) — this is the "
        "bd682a2 bug class: an HTTP node has already REPLACED the current item with its "
        "own response by the time this Code node runs, so the row must be recovered BY "
        f"NODE NAME only (found: $json x{len(bare_json)}, $input x{len(bare_input)})"
    )


# --- belt-and-braces: Route By Object Type's exact edges, duplicated from -----------------
# --- tests/test_cloud_write_path.py deliberately (that file stays the pinned original) ---

def test_route_by_object_type_edges_are_unchanged_belt_and_braces():
    doc = _load()
    router = _node(doc, "Route By Object Type")
    assert router["type"] == "n8n-nodes-base.if"
    true_branch, false_branch = doc["connections"]["Route By Object Type"]["main"]
    assert true_branch[0]["node"] == "Build Company Identity"
    assert false_branch[0]["node"] == "Build Identity"


# --- generic credential guard (T-16.4-10): every HubSpot node in THIS workflow is bound --
#
# Scoped to wf_enrichment_cloud.json ONLY. wf_scheduled_maintenance_cloud.json currently
# carries 9 unmapped HubSpot nodes (SJ-1/2/3, Dedupe, Review) and wf_contact_ingest_cloud.json
# carries 1 ("HubSpot Search by Email") — a PRE-EXISTING gap outside this phase's fence.
# Widening this guard to those workflows now would go red on work this phase did not do;
# they are recorded (not fixed) in 16.4-02-SUMMARY.md / STATE.md Blockers/Concerns instead.
#
# BUG 10 / Phase 16.6: also sweeps httpRequest nodes bound via predefinedCredentialType/
# nodeCredentialType:hubspotAppToken (the 2 company-search nodes in this workflow) — a
# type=="n8n-nodes-base.hubspot"-only filter would silently stop covering them the moment
# their transport changed, exactly the "guard that silently stops applying" failure mode.

def _hubspot_bound_node_names(doc: dict) -> set:
    names = {n["name"] for n in doc["nodes"] if n["type"] == "n8n-nodes-base.hubspot"}
    names |= {
        n["name"] for n in doc["nodes"]
        if n["type"] == "n8n-nodes-base.httpRequest"
        and n.get("parameters", {}).get("nodeCredentialType") == "hubspotAppToken"
    }
    return names


def test_every_hubspot_node_in_the_enrichment_workflow_is_registered_and_bound_to_lv_hubspot():
    doc = _load()
    hubspot_node_names = _hubspot_bound_node_names(doc)
    assert hubspot_node_names, "no HubSpot-credentialed nodes found — guard would be vacuous"
    for name in hubspot_node_names:
        assert name in deploy.NODE_CREDENTIAL_MAP, (
            f"{name!r} is a HubSpot-credentialed node in wf_enrichment_cloud.json but has no "
            "NODE_CREDENTIAL_MAP entry — it would deploy UNBOUND and 401 at runtime "
            "(T-16.4-10, the gpt #9 lesson repeated)"
        )
        entry = deploy.NODE_CREDENTIAL_MAP[name]
        assert entry == {"cred_type": "hubspotAppToken", "cred_name": "LV HubSpot"}, (
            f"{name!r} is mapped to an unexpected credential: {entry}"
        )


def test_the_httprequest_hubspot_sweep_actually_finds_all_four_search_nodes():
    """Vacuity guard for the widened sweep above: proves the httpRequest half of
    _hubspot_bound_node_names actually fires. BUG 23 (Phase 17.01) widened this from the
    two company search nodes to all four — the native half is now permanently empty for
    this workflow (test_no_native_hubspot_node_remains_in_the_workflow), so every
    HubSpot-credentialed node this sweep can possibly find arrives via the httpRequest
    branch."""
    doc = _load()
    names = _hubspot_bound_node_names(doc)
    assert {
        "HubSpot Search", "HubSpot Fetch By Id",
        "HubSpot Company Search", "HubSpot Company Fetch By Id",
    } <= names
