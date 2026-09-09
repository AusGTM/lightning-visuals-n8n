# tests/test_remaining_credits_response.py
#
# Phase 16.1 Plan 02 Task 1 — offline BFS/structural proof of the single-item credit
# branch (reviews C1 — each provider's usage/credit check fires AT MOST ONCE per run, fed
# from a dedicated single-item node off "Parse HubSpot Event", never the multi-row
# terminal/enrichment flow) and the honest "Build Response" convergence (reviews C3 —
# reachable from every terminal branch; per-batch first-arrival semantics are documented,
# NOT hard-determinism, and are NOT asserted here — response ordering + the 0-event case
# are Track B execution-level test items). Mirrors the BFS pattern in
# tests/test_cloud_companies_branch.py / tests/test_provider_gate_topology.py.
import json
import re
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

WORKFLOW_PATH = ROOT / "n8n" / "wf_enrichment_cloud.json"


def _load():
    return json.loads(WORKFLOW_PATH.read_text())


def _node(doc, name):
    return next(n for n in doc["nodes"] if n["name"] == name)


def _inbound_edges(doc, target):
    """Every (source_node, branch_index) pair with an edge landing on `target`."""
    edges = []
    for src, spec in doc["connections"].items():
        for branch_idx, branch in enumerate(spec.get("main", [])):
            for edge in branch:
                if edge["node"] == target:
                    edges.append((src, branch_idx))
    return edges


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


# --- (a) once-per-run structural proof (reviews C1) -----------------------------------

def test_credit_request_is_a_single_item_node_fed_only_by_parse_hubspot_event():
    """Phase 70 Plan 04 (D-70-04): "Credit Request" gained a SECOND source —
    "IF List Expanded"'s false (refusal) lane, index 1 — since "Parse HubSpot Event"
    never runs on that path and "Build Credits Summary" must still deliver exactly
    once for "Credits Broadcast" (a combineAll merge) to never starve."""
    doc = _load()
    assert set(_inbound_edges(doc, "Credit Request")) == {
        ("Parse HubSpot Event", 0), ("IF List Expanded", 1),
    }
    code = _node(doc, "Credit Request")["parameters"]["jsCode"]
    # Deliberately does NOT read $input.all() for cardinality — it always emits exactly
    # one item, reading $input.first() to identify THIS execution's delivery.
    assert "$input.first()" in code
    assert "providers_requested" in code


def test_each_credit_gate_is_fed_only_by_credit_request_not_a_terminal_or_row_node():
    doc = _load()
    for gate in ("IF Lusha Credit Requested", "IF Apollo Credit Requested",
                 "IF ZoomInfo Credit Requested"):
        assert _inbound_edges(doc, gate) == [("Credit Request", 0)], (
            f"{gate} must be fed ONLY by the single-item Credit Request node"
        )


def test_each_credit_http_nodes_only_inbound_is_its_own_gate_true_lane():
    """The C1 once-per-run structural proof: a credit HTTP node's only inbound is its own
    `IF <provider> Credit Requested` TRUE (index 0) lane — never a terminal / multi-row
    enrichment node (which would fire once per row -> the live-observed Lusha 429)."""
    doc = _load()
    expected_gate = {
        "Lusha Usage": "IF Lusha Credit Requested",
        "Apollo Usage": "IF Apollo Credit Requested",
        # Bug A fix (live 2026-07-28): ZoomInfo no longer mints straight off the credit
        # gate — it goes through the SAME Token Gate / IF Needs Mint / Mint / Cache Token
        # shape the row-flow subgraphs use first, sharing the sd.zoominfo cache instead
        # of minting an ungated, independently-tracked token (see
        # tests/test_zoominfo_shared_token_cache.py for the full topology proof).
        "ZoomInfo Usage Token Gate": "IF ZoomInfo Credit Requested",
    }
    for credit_node, gate_name in expected_gate.items():
        edges = _inbound_edges(doc, credit_node)
        assert edges == [(gate_name, 0)], (
            f"{credit_node} must have exactly ONE inbound edge — its own {gate_name} "
            f"TRUE (index 0) output — got {edges}"
        )
    # ZoomInfo Usage Mint only fires behind its own needsMint() gate, never directly off
    # the credit-requested gate (that direct edge is exactly Bug A's shape).
    assert _inbound_edges(doc, "ZoomInfo Usage Mint") == [("IF ZoomInfo Usage Needs Mint", 0)]
    # ZoomInfo Usage (the secret-free GET) is fed by BOTH the IF's mint-then-cache lane
    # and its cache-hit bypass lane — mirroring the row-flow Enrich nodes' convergence.
    assert set(_inbound_edges(doc, "ZoomInfo Usage")) == {
        ("IF ZoomInfo Usage Needs Mint", 1), ("ZoomInfo Usage Cache Token", 0),
    }


def test_credit_gates_false_lane_feeds_its_own_skip_sentinel():
    """Phase 70 Plan 04 (D-70-04): a not-requested provider's gate false lane no longer
    dead-ends — it feeds a static "... Credit Skipped" marker, so "Collect Credits"
    (append, 3 inputs) still receives exactly one {provider, requested, credits} item
    per provider every execution, real or skipped."""
    doc = _load()
    expected_skip = {
        "IF Lusha Credit Requested": "Lusha Credit Skipped",
        "IF Apollo Credit Requested": "Apollo Credit Skipped",
        "IF ZoomInfo Credit Requested": "ZoomInfo Credit Skipped",
    }
    for gate, skip_node in expected_skip.items():
        conns = doc["connections"][gate]["main"]
        assert conns[1] == [{"node": skip_node, "type": "main", "index": 0}], (
            f"{gate} false lane must feed {skip_node} (got {conns[1]})"
        )


# --- (b) credit HTTP node shape: onError, credential-bound, ZoomInfo Accept header ------

def test_lusha_and_apollo_usage_nodes_are_credential_bound_header_auth():
    doc = _load()
    for name in ("Lusha Usage", "Apollo Usage"):
        node = _node(doc, name)
        assert node["type"] == "n8n-nodes-base.httpRequest"
        assert node["onError"] == "continueRegularOutput"
        assert node["parameters"]["authentication"] == "genericCredentialType"
        assert node["parameters"]["genericAuthType"] == "httpHeaderAuth"


def test_zoominfo_usage_mint_is_credential_bound_basic_auth():
    doc = _load()
    node = _node(doc, "ZoomInfo Usage Mint")
    assert node["type"] == "n8n-nodes-base.httpRequest"
    assert node["onError"] == "continueRegularOutput"
    assert node["parameters"]["authentication"] == "genericCredentialType"
    assert node["parameters"]["genericAuthType"] == "httpBasicAuth"


def test_zoominfo_usage_get_sets_the_vnd_api_json_accept_header():
    doc = _load()
    code = _node(doc, "ZoomInfo Usage")["parameters"]["jsCode"]
    assert "application/vnd.api+json" in code
    # secret-free (C2) — never reads the actual ZOOMINFO_CLIENT_* credential values
    # (zoominfoToken.js's own header comment mentions "client_id"/"client_secret" in
    # prose, which inline() legitimately carries in, so check the real var names).
    assert "ZOOMINFO_CLIENT" not in code


def test_zero_env_or_vars_expressions_in_the_credit_branch():
    assert not re.findall(r"\$env\b|\$vars\b", WORKFLOW_PATH.read_text())


# --- (c) Build Response convergence: 5 real terminals + 2 re-pointed lanes + unsupported
#         + the companies skip terminal (Phase 47.5 RECOMP-02)

BUILD_RESPONSE_SOURCES = {
    ("HubSpot Create", 0), ("HubSpot Update", 0), ("Skip (NoOp)", 0),
    # Phase 61 Plan 06 Task 2 (REVIEW-C17): "HubSpot Company Create" no longer feeds
    # Build Response directly — "Adapt Company Create" is spliced between them to
    # capture the created company's id and join it to its planned dependency by value.
    ("Adapt Company Create", 0), ("HubSpot Company Update", 0),
    ("IF Enrich", 1), ("IF Company Enrich", 1),
    ("Unsupported Object Type", 0),
    # Phase 47.5 Plan 01 (RECOMP-02): the companies branch's skip terminal. Until now a
    # complete company died at Normalize + Score Company with zero rows out, so the caller
    # got a bare 200 with no body and could not tell "complete, nothing to do" from
    # "something broke". This is the direct companies mirror of ("Skip (NoOp)", 0) above,
    # which the contacts branch has always had. The assertion below stays EXACT equality —
    # this extends the expected set, it does not relax the check.
    ("IF Company Skip", 0),
    # Phase 48 Plan 02 (D-04): the research-error failure terminal. An error-shaped Claude
    # Web Research payload (Anthropic 400, e.g. credit exhaustion) now terminates
    # observably at Build Response via Build Research Failure Response, carrying
    # action:"research_failed" and a stated reason, instead of silently flowing into
    # Validate Research Output / Merge Company / Decide Company Action as if it were real
    # data. Extends the expected set again; exact equality is preserved.
    ("Build Research Failure Response", 0),
    # Phase 70 Plan 03 Task 2 (D-70-07): the ELEVENTH input, added via
    # `_append_merge_input` after this merge was already sized to the ten above —
    # carries a list-expansion refusal or a scale-up dispatch confirmation, both
    # mutually exclusive with the other ten firing at all this execution.
    ("Build Refusal Row", 0),
}


def test_build_response_is_reachable_from_every_terminal_branch():
    """Fails if only the five real terminal nodes converge — the two re-pointed
    IF-enrich-false lanes, the unsupported terminal and the companies skip terminal must
    ALSO feed Build Response.

    Phase 70 Plan 03 (D-70-01): all eleven terminals now converge on "Build Response
    Merge" first. Phase 70 Plan 04 (D-70-04): "Credits Broadcast" (a combineAll merge)
    sits between that Merge and "Build Response" — broadcasting "Build Credits
    Summary"'s single `remaining_credits` item onto every row — so "Build Response"'s
    own sole inbound edge is now that broadcast merge, one hop further back. The eleven
    real sources are checked another level further back, against "Build Response
    Merge" itself."""
    doc = _load()
    assert _inbound_edges(doc, "Build Response") == [("Credits Broadcast", 0)]
    # "Filter Build Response Rows" drops the starved-lane sentinel markers BEFORE the
    # combineAll broadcast — otherwise the cartesian product would make every one of
    # those 10 empty `{}` items non-empty too (broadcasting `remaining_credits` onto
    # them), defeating Build Response's own non-empty filter.
    assert set(_inbound_edges(doc, "Credits Broadcast")) == {
        ("Filter Build Response Rows", 0), ("Build Credits Summary", 0),
    }
    assert _inbound_edges(doc, "Filter Build Response Rows") == [("Build Response Merge", 0)]
    merge_edges = {(src, idx) for (src, idx) in _inbound_edges(doc, "Build Response Merge")
                   if "Sentinel" not in src}
    assert merge_edges == BUILD_RESPONSE_SOURCES, (
        f"Build Response Merge inbound (non-sentinel) edges {merge_edges} != "
        f"expected {BUILD_RESPONSE_SOURCES}"
    )


def test_build_response_feeds_respond_to_webhook():
    """Phase 70 Plan 03 Task 2 (D-70-07): "Build Response" is now a terminal leaf with
    NO outgoing connection at all — the caller reads its output from runData, never the
    HTTP response body. "Build Ack" is the sole producer "Respond to Webhook" hears
    from."""
    doc = _load()
    spec = doc["connections"].get("Build Response")
    targets = [e["node"] for b in (spec or {}).get("main", []) for e in b]
    assert targets == []
    ack_targets = [e["node"] for b in doc["connections"]["Build Ack"]["main"] for e in b]
    assert ack_targets == ["Respond to Webhook"]
    node = _node(doc, "Respond to Webhook")
    assert node["type"] == "n8n-nodes-base.respondToWebhook"


def test_webhook_uses_response_node_mode_not_last_node():
    """Proves the MODE FLAG, not response determinism — per-batch first-arrival semantics
    are documented (Build Response's own jsCode comment), not asserted here (reviews C3)."""
    text = WORKFLOW_PATH.read_text()
    assert text.count('"responseMode": "responseNode"') == 1
    assert '"responseMode": "lastNode"' not in text


def test_unsupported_terminal_reaches_build_response_not_dead_ended():
    doc = _load()
    reachable = _reachable_from(doc, "Unsupported Object Type")
    assert "Build Response" in reachable


# --- (d) Build Response reads remaining_credits off the row, never by name -------------

def test_build_response_reads_remaining_credits_off_the_row_never_by_name():
    """Phase 70 Plan 04 (D-70-04): "Credits Broadcast" precomputes `remaining_credits`
    (via "Build Credits Summary") and merges it onto every row before "Build Response"
    ever runs — no nodeAll, no by-name lookup of any usage node."""
    doc = _load()
    code = _node(doc, "Build Response")["parameters"]["jsCode"]
    assert "$('" not in code and '$("' not in code
    assert "row.remaining_credits" in code


def test_build_credits_summary_filters_to_requested_providers_only():
    """The membership test `providers_requested.map(...)` used to apply now lives on
    each provider's own lane (the `requested` flag "IF <provider> Credit Requested"
    already computed) — "Build Credits Summary" filters on it, never re-deriving
    providers_requested itself."""
    doc = _load()
    code = _node(doc, "Build Credits Summary")["parameters"]["jsCode"]
    assert "$('" not in code and '$("' not in code
    assert "$input.all()" in code
    assert "filter((r) => r && r.requested)" in code


def test_collect_credits_has_one_input_per_provider_real_or_skipped():
    doc = _load()
    for adapt_node, skip_node in (
        ("Adapt Lusha Usage", "Lusha Credit Skipped"),
        ("Adapt Apollo Usage", "Apollo Credit Skipped"),
        ("Adapt ZoomInfo Usage", "ZoomInfo Credit Skipped"),
    ):
        adapt_targets = [e["node"] for b in doc["connections"][adapt_node]["main"] for e in b]
        skip_targets = [e["node"] for b in doc["connections"][skip_node]["main"] for e in b]
        assert adapt_targets == ["Collect Credits"]
        assert skip_targets == ["Collect Credits"]
        # Both mutually-exclusive lanes for the SAME provider must land on the SAME
        # merge input index, or "Collect Credits" would starve on whichever branch
        # fires this run.
        adapt_idx = doc["connections"][adapt_node]["main"][0][0]["index"]
        skip_idx = doc["connections"][skip_node]["main"][0][0]["index"]
        assert adapt_idx == skip_idx


def test_adapt_usage_nodes_tag_provider_identity_statically():
    doc = _load()
    for node_name, provider in (("Adapt Lusha Usage", "lusha"), ("Adapt Apollo Usage", "apollo"),
                                 ("Adapt ZoomInfo Usage", "zoominfo")):
        code = _node(doc, node_name)["parameters"]["jsCode"]
        assert f"provider: {provider!r}" in code
        assert "extractCredits(" in code
        assert "$('" not in code


# --- determinism -------------------------------------------------------------------------

def test_zero_env_or_vars_expressions_workflow_wide():
    assert not re.findall(r"\$env\b|\$vars\b", WORKFLOW_PATH.read_text())
