# tests/test_cloud_companies_branch.py
#
# Phase 16 Task 5 — offline proof that build_enrichment_cloud() carries the full
# companies ICP branch: BFS-reachable from Webhook Trigger, the LOCAL-LIVE fixture
# emitter did NOT leak in (review #6), Approach C holds (no derived ICP output field
# in the canonical patch), and the review-loop producer contract (review consensus #2)
# is discharged by ENRICH_DECIDE_CO_CLOUD. Mirrors the graph-ancestry BFS precedent in
# tests/test_judge_spec.py / tests/test_architecture_guard.py.
import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_cloud_workflows import ENRICH_MERGE_CO  # noqa: E402

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


COMPANY_BRANCH_NODES = [
    "Build Company Identity", "HubSpot Company Search", "Adapt Company Search",
    "Company Gate", "Build Company Requests", "Lusha Company", "Apollo Org",
    "ZoomInfo Company Token Gate", "IF ZoomInfo Company Needs Mint", "ZoomInfo Mint Company",
    "ZoomInfo Company Cache Token", "ZoomInfo Company",
    "Normalize + Score Company", "Research Trigger Gate", "IF Research Needed",
    "Build Research Request", "Claude Web Research", "Validate Research Output",
    "Judge Gate", "IF Needs Judge", "Build Judge Request", "Judge Call",
    "Apply Judge Verdict", "Merge Company", "Decide Company Action",
    "IF Company Create", "HubSpot Company Create", "IF Company Enrich",
    "HubSpot Company Update",
]


def test_all_company_branch_nodes_are_bfs_reachable_from_webhook_trigger():
    doc = _load()
    reachable = _reachable_from(doc, "Webhook Trigger")
    node_names = {n["name"] for n in doc["nodes"]}
    missing_from_workflow = [n for n in COMPANY_BRANCH_NODES if n not in node_names]
    assert not missing_from_workflow, f"expected company-branch node(s) not built: {missing_from_workflow}"
    unreachable = [n for n in COMPANY_BRANCH_NODES if n not in reachable]
    assert not unreachable, f"company-branch node(s) not reachable from Webhook Trigger: {unreachable}"


def test_merge_company_node_present_in_built_cloud_workflow():
    doc = _load()
    names = [n["name"] for n in doc["nodes"]]
    assert names.count("Merge Company") >= 1


def test_emit_company_targets_fixture_emitter_did_not_leak_into_cloud():
    """review #6, VERIFIED: build_cloud_workflows.py's ENRICH_EMIT_COMPANIES hard-codes
    Harvey Norman/Racing NSW/Melbourne Racing Club/Australian Turf Club/FanDuel and
    ignores its input — porting it verbatim would make every Cloud webhook execution
    process those five fixtures instead of the company the event names. On the Cloud
    path the company branch begins at Build Company Identity, fed by the webhook
    payload, never a hard-coded row set."""
    doc = _load()
    names = [n["name"] for n in doc["nodes"]]
    assert "Emit Company Targets" not in names


def test_company_canonical_patch_never_contains_a_derived_icp_output_field():
    """Approach C (Phase 15 criterion 4): the company canonical patch must never carry
    lv_icp_fit_score/lv_icp_tier/lv_anti_icp_flag/lv_recommended_motion — HubSpot derives
    these, the pipeline writes only inputs. ENRICH_MERGE_CO's candidate-building code is
    the ONLY place a field name can enter mergeCompanies()'s candidateRow (and therefore
    canonicalPatch); none of the four forbidden output names appear there as a quoted
    candidate-field key. (mergeCompanies.js's DEFAULT_COMPANY_POLICY still declares
    lv_anti_icp_flag/lv_anti_icp_reason as veto_output classes — dead policy entries,
    since no candidate ever supplies those keys — this test targets the reachable
    surface, not the unreachable policy declaration.)"""
    forbidden = ["lv_icp_fit_score", "lv_icp_tier", "lv_anti_icp_flag", "lv_recommended_motion"]
    for field in forbidden:
        assert f'"{field}"' not in ENRICH_MERGE_CO, (
            f"{field} appears as a quoted candidate-field key in ENRICH_MERGE_CO — "
            "Approach C violation (a derived ICP output could enter the canonical patch)."
        )


def test_merge_companies_veto_policy_entries_carry_a_real_min_confidence():
    """D-04 / P2 (PIPELINE-DEFECTS-VALIDATION.md): DEFAULT_COMPANY_POLICY's
    lv_anti_icp_flag/lv_anti_icp_reason entries are dead-candidate-path policy (see
    test_company_canonical_patch_never_contains_a_derived_icp_output_field above), but
    min_confidence: 0 made _gate()'s `confidence < minConfidence` check unreachable
    (confidence is never negative) — any future accidental candidate would auto-promote
    a veto at any confidence. Guards the fix at its one shared site so a future edit back
    to 0 fails the suite instead of silently reopening P2."""
    text = (ROOT / "n8n" / "code" / "mergeCompanies.js").read_text()
    import re

    for field in ("lv_anti_icp_flag", "lv_anti_icp_reason"):
        m = re.search(rf'{field}:\s*\{{[^}}]*min_confidence:\s*(-?\d+)', text)
        assert m, f"could not find a min_confidence entry for {field} in mergeCompanies.js"
        assert int(m.group(1)) >= 80, (
            f"{field}'s min_confidence dropped below 80 — this reopens P2 "
            "(a future candidate for this dead policy path would auto-promote at low confidence)"
        )
    assert "min_confidence: 0" not in text, (
        "min_confidence: 0 still appears in mergeCompanies.js (acceptance criteria: "
        "neither veto entry may declare it anywhere in the file)"
    )


def test_decide_company_action_cloud_is_the_review_loop_producer():
    """review consensus #2 — mergeCompanies' canonicalPatch (mergeCompanies.js:209-211,
    VERIFIED) holds ONLY promote decisions; needs_review decisions are otherwise dropped.
    ENRICH_DECIDE_CO_CLOUD must write the review flags + a candidate JSON of the HELD
    needs_review decisions so 16-02's reviewApply has real candidates to apply
    post-approval."""
    doc = _load()
    node = next(n for n in doc["nodes"] if n["name"] == "Decide Company Action")
    code = node["parameters"]["jsCode"]
    for token in (
        "lv_enrichment_needs_review",
        "lv_enrichment_status",
        "lv_enrichment_review_reason",
        "lv_enrichment_review_candidate_json",
        'decision === "needs_review"',
    ):
        assert token in code, f"Decide Company Action jsCode missing {token!r}"


def test_decide_company_action_uses_stable_stringify_not_a_hand_rolled_serializer():
    """The plan explicitly requires reusing mergeCompanies' exported stableStringify
    rather than hand-rolling a second serializer (as the LOCAL variant's
    _stableStringify/_sortedForStringify duplicate does)."""
    doc = _load()
    node = next(n for n in doc["nodes"] if n["name"] == "Decide Company Action")
    code = node["parameters"]["jsCode"]
    assert "function stableStringify" in code  # from the inlined mergeCompanies.js
    assert "stableStringify(" in code  # actually called by the wrapper


def test_hubspot_company_create_is_a_credential_bound_httprequest_post():
    """Was pinned as the native n8n-nodes-base.hubspot node. Phase 16.9 (BUG 13) moved it:
    the native node carried `additionalFields: {}` so the computed patch was discarded, and
    its `name` expression read `$json.name`/`$json.identity_keys.*`, none of which exist on
    Decide Company Action's output (verified from live execution 12) — dereferencing the
    absent identity_keys would have thrown. It now POSTs {"properties": $json.properties}
    to the CRM v3 collection endpoint, credential-bound, with no error swallowing."""
    doc = _load()
    node = next(n for n in doc["nodes"] if n["name"] == "HubSpot Company Create")
    params = node["parameters"]
    assert node["type"] == "n8n-nodes-base.httpRequest"
    assert params["method"] == "POST"
    assert params["url"] == "https://api.hubapi.com/crm/v3/objects/companies"
    assert params["authentication"] == "predefinedCredentialType"
    assert params["nodeCredentialType"] == "hubspotAppToken"
    assert "$json.properties" in params["jsonBody"]
    assert "identity_keys" not in params["jsonBody"]
    assert node.get("onError") is None, "a rejected create must fail the execution"


def test_hubspot_company_update_node_is_credential_bound_httprequest_patch():
    """Phase 16.7-01 (BUG 11): "HubSpot Company Update" moved off the native hubspot node
    (committed with an EMPTY `updateFields` map — a placeholder that never referenced the
    computed patch) onto a credential-bound httpRequest PATCH that carries
    `{"properties": $json.properties}` directly, reusing the SAME "LV HubSpot" credential
    via predefinedCredentialType/nodeCredentialType:hubspotAppToken. See
    tests/test_write_node_transport.py for the full structural guard (onError absence,
    URL/body shape, credential-map presence) shared with the contacts mirror,
    "HubSpot Update"."""
    doc = _load()
    node = next(n for n in doc["nodes"] if n["name"] == "HubSpot Company Update")
    assert node["type"] == "n8n-nodes-base.httpRequest"
    assert node["parameters"]["method"] == "PATCH"
    assert node["parameters"]["url"] == (
        "=https://api.hubapi.com/crm/v3/objects/companies/{{ $json.hs_object_id }}"
    )
    assert node["parameters"]["authentication"] == "predefinedCredentialType"
    assert node["parameters"]["nodeCredentialType"] == "hubspotAppToken"


def test_hubspot_company_search_is_credential_bound_httprequest_via_predefined_credential_type():
    """BUG 10 / Phase 16.6 fix: "HubSpot Company Search" moved off the native hubspot node
    (which has no `operation: "search"` for resource:company) onto a credential-bound
    httpRequest node hitting the real CRM v3 search endpoint directly, reusing the SAME
    "LV HubSpot" credential via predefinedCredentialType/nodeCredentialType:hubspotAppToken
    — never a new credential, never $env/$vars. See
    tests/test_bug10_company_search_transport.py for the full node-shape guard."""
    doc = _load()
    node = next(n for n in doc["nodes"] if n["name"] == "HubSpot Company Search")
    assert node["type"] == "n8n-nodes-base.httpRequest"
    assert node["parameters"]["method"] == "POST"
    assert node["parameters"]["url"] == "https://api.hubapi.com/crm/v3/objects/companies/search"
    assert node["parameters"]["authentication"] == "predefinedCredentialType"
    assert node["parameters"]["nodeCredentialType"] == "hubspotAppToken"


def test_zoominfo_company_mint_node_is_credential_bound_basic_auth():
    """Task 2 decision (split-code-node) applied to the company branch too: the ONLY
    node that ever touches ZoomInfo client_id/client_secret is the credential-bound
    Mint HTTP node — matches deploy_n8n_workflows.py's NODE_CREDENTIAL_MAP entry."""
    doc = _load()
    node = next(n for n in doc["nodes"] if n["name"] == "ZoomInfo Mint Company")
    assert node["type"] == "n8n-nodes-base.httpRequest"
    assert node["parameters"]["authentication"] == "genericCredentialType"
    assert node["parameters"]["genericAuthType"] == "httpBasicAuth"


def test_lusha_company_uses_the_v3_post_contract_with_a_json_body():
    """Phase 20 (Lusha v2 -> v3 migration). docs/LUSHA-V3-CONTRACT.md §5 (live-confirmed
    2026-07-30): POST /v3/companies/search-and-enrich, body {"companies":[{"domain":...}]}
    — domain is still the only accepted identity property (BUG 17's finding carries
    forward unchanged under v3; adding companyName still 400s). Assert the transport, not
    just the URL string: a built node without a non-empty jsonBody would silently regress
    to the old query-string shape."""
    doc = _load()
    node = next(n for n in doc["nodes"] if n["name"] == "Lusha Company")
    p = node["parameters"]
    assert p["method"] == "POST"
    assert p["url"] == "https://api.lusha.com/v3/companies/search-and-enrich"
    assert p.get("jsonBody"), "POST must carry the built v3 companies body"
    assert p["genericAuthType"] == "httpHeaderAuth"


def test_build_company_requests_never_puts_companyname_in_the_lusha_body():
    """The v3-era form of BUG 17's guard: the prebuilt request body must never carry
    companyName, which Lusha rejects on this lane under both v2 and v3. Guard the builder
    source (delegates to the shared lushaCompanyBody() builder, no inline query-string
    assembly for Lusha) AND that builder's actual output, since either regressing would
    400 identically and just as invisibly (onError:continueRegularOutput lands a provider
    failure in the item, not the node)."""
    import subprocess

    from build_cloud_workflows import ENRICH_BUILD_CO_REQUESTS

    assert "lushaCompanyBody(id)" in ENRICH_BUILD_CO_REQUESTS
    assert "lusha_company_body" in ENRICH_BUILD_CO_REQUESTS
    assert "lusha_company_url" not in ENRICH_BUILD_CO_REQUESTS, \
        "no query-string assembly for Lusha should remain in this builder"

    harness = """
const { lushaCompanyBody } = require(%r);
const body = lushaCompanyBody({ domain: "racingnsw.com.au", companyName: "Racing NSW" });
console.log(JSON.stringify(body));
""" % str(ROOT / "n8n" / "code" / "lushaRequest.js")
    r = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr[:800]
    body = json.loads(r.stdout.strip())
    assert body == {"companies": [{"domain": "racingnsw.com.au"}]}
    assert "companyName" not in body["companies"][0]
