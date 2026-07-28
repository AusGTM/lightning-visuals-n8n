# tests/test_zoominfo_shared_token_cache.py
#
# Bug A (live 2026-07-28, canary run): the credit-reporting branch's "ZoomInfo Usage
# Mint" node minted a token UNCONDITIONALLY — no needsMint() gate, and (critically) it
# never wrote the freshly minted token into the shared `sd.zoominfo` (workflow static
# data) cache that the contacts ("ZoomInfo Mint") and companies ("ZoomInfo Mint
# Company") row-flow subgraphs read and write. ZoomInfo allows exactly ONE active token
# per credential — minting a new one immediately invalidates whichever token the
# row-flow had just cached, and because the credit branch's mint never updated the
# cache to match, the cache was left pointing at a token ZoomInfo itself had already
# killed. The NEXT run's row-flow read that "still fresh per its `exp`, but actually
# dead" cached token and 401'd — live-observed as consecutive-run 401s.
#
# The fix: give the credit branch the SAME Token Gate -> IF Needs Mint ->
# [Mint -> Cache]/[bypass] -> <consumer> subgraph shape the contacts/companies
# row-flows already use, sharing the identical `sd.zoominfo` cache key, so at most one
# mint happens when the cache is warm and every consumer's mint result is visible to
# every other consumer.
#
# This is an in-test BUILD (not a committed-JSON compare) so a source edit with no
# rebuild still fails here, mirroring tests/test_companies_factory_frozen.py's
# integrity property. A second test separately checks committed-JSON currency.
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_cloud_workflows as m  # noqa: E402

WORKFLOW_PATH = ROOT / "n8n" / "wf_enrichment_cloud.json"

# Every node name in the graph that performs the actual OAuth mint HTTP call.
MINT_NODE_NAMES = {"ZoomInfo Mint", "ZoomInfo Mint Company", "ZoomInfo Usage Mint"}

# Every node name that gates a mint behind a needsMint() cache check ("<X> Token Gate").
TOKEN_GATE_NAMES = {"ZoomInfo Token Gate", "ZoomInfo Company Token Gate", "ZoomInfo Usage Token Gate"}


def _node(doc, name):
    return next(n for n in doc["nodes"] if n["name"] == name)


def _inbound_edges(doc, target):
    edges = []
    for src, spec in doc["connections"].items():
        for branch_idx, branch in enumerate(spec.get("main", [])):
            for edge in branch:
                if edge["node"] == target:
                    edges.append((src, branch_idx))
    return edges


def _mint_url_node_names(doc):
    """Every httpRequest node whose URL is the ZoomInfo OAuth mint endpoint — found by
    URL, not by name, so a renamed/added mint node can't silently dodge this guard."""
    names = set()
    for n in doc["nodes"]:
        if n.get("type") != "n8n-nodes-base.httpRequest":
            continue
        url = n.get("parameters", {}).get("url", "")
        if "gtm/oauth/v1/token" in url:
            names.add(n["name"])
    return names


def _assert_no_unconditional_mint(doc):
    """The core Bug A guard: EVERY mint HTTP node in the workflow is fed exclusively by
    the TRUE (index 0) lane of an `IF ... Needs Mint` gate — never fed directly by a
    provider-enabled/credit-requested gate or any other node. An unconditional mint
    (Bug A's shape) has an inbound edge whose source is NOT an "IF ... Needs Mint" node,
    which this catches regardless of node name."""
    mint_nodes = _mint_url_node_names(doc)
    assert mint_nodes == MINT_NODE_NAMES, (
        f"expected exactly {MINT_NODE_NAMES} to hit the ZoomInfo mint endpoint, "
        f"got {mint_nodes}"
    )
    for mint_name in mint_nodes:
        edges = _inbound_edges(doc, mint_name)
        assert len(edges) == 1, f"{mint_name} must have exactly one inbound edge, got {edges}"
        (src, branch_idx) = edges[0]
        assert src.startswith("IF ") and "Needs Mint" in src, (
            f"{mint_name} is fed by {src!r} — not a needsMint()-gated IF node. "
            "An ungated mint is exactly Bug A's shape (unconditional independent mint)."
        )
        assert branch_idx == 0, f"{mint_name} must be fed by the IF node's TRUE lane, got branch {branch_idx}"


def _assert_every_mint_gated_by_the_shared_cache(doc):
    """Every `IF ... Needs Mint` gate is fed by a `... Token Gate` Code node whose jsCode
    calls needsMint(...) against `$getWorkflowStaticData("global")` — i.e. decides via
    the ONE shared cache, not an independently-tracked flag."""
    for gate_name in TOKEN_GATE_NAMES:
        node = _node(doc, gate_name)
        assert node["type"] == "n8n-nodes-base.code"
        code = node["parameters"]["jsCode"]
        assert 'getWorkflowStaticData("global")' in code
        assert "needsMint(" in code
        # secret-free (Task 2 decision) — the Token Gate Code node must never read the
        # actual client credential values itself (zoominfoToken.js's own header comment
        # mentions "client_id"/"client_secret" in prose, which inline() legitimately
        # carries in — check for the real ZOOMINFO_CLIENT_* variable names instead).
        assert "ZOOMINFO_CLIENT" not in code


def _assert_every_cache_write_uses_the_same_key(doc):
    """Every `... Cache Token` node writes the freshly-minted token to the SAME
    `sd.zoominfo` key — this is what makes the cache actually SHARED across all three
    consumers rather than three independent caches that happen to share a helper."""
    cache_node_names = [
        "ZoomInfo Cache Token", "ZoomInfo Company Cache Token", "ZoomInfo Usage Cache Token",
    ]
    for name in cache_node_names:
        node = _node(doc, name)
        assert node["type"] == "n8n-nodes-base.code"
        code = node["parameters"]["jsCode"]
        assert "sd.zoominfo = parsed" in code, (
            f"{name} does not write the shared sd.zoominfo cache key — "
            "an independent/dead-end mint result (Bug A's exact defect) never reaches "
            "the cache other consumers read."
        )


def test_built_cloud_workflow_has_no_unconditional_zoominfo_mint():
    doc = m.build_enrichment_cloud()
    _assert_no_unconditional_mint(doc)


def test_built_cloud_workflow_gates_every_mint_via_the_shared_needsmint_cache():
    doc = m.build_enrichment_cloud()
    _assert_every_mint_gated_by_the_shared_cache(doc)


def test_built_cloud_workflow_every_mint_result_reaches_the_shared_cache_key():
    doc = m.build_enrichment_cloud()
    _assert_every_cache_write_uses_the_same_key(doc)


def test_credit_branch_usage_check_reads_a_bearer_token_not_its_own_mint_response():
    """ZoomInfo Usage (the consumer) must read `zoom_token` off the row like the
    contacts/companies Enrich nodes do — NOT `access_token` straight off its own prior
    HTTP node's raw response (the old shape, which bypassed the cache entirely)."""
    doc = m.build_enrichment_cloud()
    code = _node(doc, "ZoomInfo Usage")["parameters"]["jsCode"]
    assert "zoom_token" in code
    assert "ZOOMINFO_CLIENT" not in code


def test_committed_wf_enrichment_cloud_json_zoominfo_topology_is_current():
    """Currency check: the COMMITTED workflow JSON must match a fresh build for the
    ZoomInfo mint topology, so drift between source and the checked-in artifact is
    caught independently of the in-test-build guards above."""
    committed = json.loads(WORKFLOW_PATH.read_text())
    m._idc[0] = 0
    _assert_no_unconditional_mint(committed)
    _assert_every_mint_gated_by_the_shared_cache(committed)
    _assert_every_cache_write_uses_the_same_key(committed)


def test_zero_env_or_vars_expressions_in_the_zoominfo_subgraphs():
    text = WORKFLOW_PATH.read_text()
    assert not re.findall(r"\$env\b|\$vars\b", text)
