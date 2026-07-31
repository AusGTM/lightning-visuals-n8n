# tests/test_verify_live_write_safety.py
#
# Phase 22 Plan 02 (T-22-06..10) — offline proof for scripts/verify_live_write_safety.py.
# Phase 23 Plan 07 (D-19) — reworked for discovery-scoped coverage: the read-back no
# longer names one workflow and two nodes, so the fixtures build NAMED workflows out of
# explicit (node name, declared subset) pairs and every `verify()` call passes a LIST.
# Fully hermetic: no network. Drives the behaviour table with small hand-built workflow
# dicts (never the real n8n/wf_*.json — this plan's read-back logic is proven against
# synthetic shapes so every refusal path is reachable without depending on the committed
# build's exact literals, which tests/test_deploy_write_safety_overlay.py and
# tests/test_write_gate_coverage.py already pin separately).
import pytest
import requests

import scripts.deploy_n8n_workflows as deploy
import scripts.verify_live_write_safety as verifier


def _raise_http(*args, **kwargs):
    raise AssertionError("a live n8n request leaked past a guard/gate that should have refused")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    for var in ("N8N_URL", "N8N_API_KEY", "N8N_EXPECTED_URL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(requests, "get", _raise_http)
    monkeypatch.setattr(requests, "post", _raise_http)
    monkeypatch.setattr(requests, "put", _raise_http)


# Declared off the verifier's OWN checked set, so a constant added to the overlay
# (ALLOW_HUBSPOT_REVIEW_WRITES was the fifth, Phase 30 Plan 01) fails loudly here as a
# stale fixture rather than silently going unchecked.
_DISARMED = {
    "ALLOW_HUBSPOT_RECORD_WRITES": "false",
    "ALLOW_HUBSPOT_CREATE": "false",
    "ALLOW_HUBSPOT_REVIEW_WRITES": "false",
    "TEST_RECORD_DOMAINS": "",
    "TEST_RECORD_IDS": "",
}
_ALIAS = {
    "writes": "ALLOW_HUBSPOT_RECORD_WRITES",
    "create": "ALLOW_HUBSPOT_CREATE",
    "review": "ALLOW_HUBSPOT_REVIEW_WRITES",
    "ids": "TEST_RECORD_IDS",
    "domains": "TEST_RECORD_DOMAINS",
}


def _node(name, declares=None, **overrides):
    """One Code node. `declares` is the SUBSET of constants this node writes into its
    jsCode (default: all of them) — the contact lane's `Decide Action` really does
    declare only the create flag, so a partial declaration must be expressible."""
    assert set(_DISARMED) == set(verifier.CHECKED_CONSTANTS), (
        "fixture is out of date with verifier.CHECKED_CONSTANTS: "
        f"{set(verifier.CHECKED_CONSTANTS) ^ set(_DISARMED)}"
    )
    values = dict(_DISARMED)
    for key, value in overrides.items():
        values[_ALIAS[key]] = value
    declared = tuple(declares) if declares is not None else tuple(_DISARMED)
    js_code = (
        "// unrelated preamble, e.g. taxonomy consts, should never confuse the parser\n"
        'const SOME_OTHER_CONST = "unrelated";\n'
        + "".join(f'const {n} = "{values[n]}";\n' for n in declared)
    )
    return {"name": name, "parameters": {"jsCode": js_code}}


def _wf(name, *nodes):
    return {"name": name, "nodes": list(nodes)}


def _enrichment(contact=None, company=None):
    """The pre-23-07 shape: one workflow, the two `Decide*` nodes — as a LIST, which is
    what `verify()` now takes."""
    nodes = []
    if contact is not None:
        nodes.append(_node("Decide Action", **contact))
    if company is not None:
        nodes.append(_node("Decide Company Action", **company))
    return [_wf("LV Enrichment (Cloud template)", *nodes)]


# --- spec parity: the checked set must never drift from the overlay's own set --------

def test_checked_constants_match_overlay_spec():
    assert set(verifier.CHECKED_CONSTANTS) == set(deploy._OVERLAY_FLAG_SPEC.keys())


def test_boolean_constants_are_derived_not_retyped():
    """Phase 30 Plan 01's fix, preserved by 23-07 rather than redone: the booleans are
    whatever the overlay declares minus the allowlists, so a sixth write-enabling flag is
    read back the moment it exists."""
    assert set(verifier.BOOLEAN_CONSTANTS) == (
        set(deploy._OVERLAY_FLAG_SPEC) - set(verifier.ALLOWLIST_CONSTANTS)
    )


# --- disarmed expectation --------------------------------------------------------------

def test_disarmed_passes_when_both_nodes_fully_disabled():
    result = verifier.verify(_enrichment(contact={}, company={}), "disarmed")
    assert result["ok"] is True
    assert result["reasons"] == []


def test_disarmed_fails_when_one_node_still_has_record_writes_enabled():
    result = verifier.verify(_enrichment(contact={"writes": "true", "ids": "201"}, company={}), "disarmed")
    assert result["ok"] is False
    assert any("Decide Action" in r and "ALLOW_HUBSPOT_RECORD_WRITES" in r for r in result["reasons"])


def test_disarmed_fails_on_stale_allowlist_even_with_flags_disabled():
    result = verifier.verify(_enrichment(contact={}, company={"ids": "9604614548"}), "disarmed")
    assert result["ok"] is False
    assert any("Decide Company Action" in r and "TEST_RECORD_IDS" in r for r in result["reasons"])


def test_disarmed_fails_when_review_writeback_is_still_armed():
    """Phase 30 Plan 01: ALLOW_HUBSPOT_REVIEW_WRITES is a write-enabling flag this
    read-back had no knowledge of when it was written. A live artifact with review
    writeback armed reporting `disarmed PASS` is the exact false-success this script
    exists to prevent, so the checked booleans are derived from the overlay set."""
    result = verifier.verify(_enrichment(contact={"review": "true", "ids": "201"}, company={}), "disarmed")
    assert result["ok"] is False
    assert any("Decide Action" in r and "ALLOW_HUBSPOT_REVIEW_WRITES" in r for r in result["reasons"])


# --- discovery: coverage follows the deployed artifacts (23-07 Task 1) -----------------

def test_disarmed_fails_on_an_armed_node_outside_the_enrichment_workflow():
    """The defect 23-06 Section B found live: the read-back named ONE workflow and TWO
    `Decide*` nodes, so an armed literal in the contact lane's write gates — a different
    workflow, differently named nodes — produced a confident `disarmed PASS` for a lane it
    never looked at."""
    workflows = [
        _wf("LV Enrichment (Cloud template)", _node("Decide Action"), _node("Decide Company Action")),
        _wf(
            "LV Contact Ingest (Cloud template)",
            _node("Decide Action", declares=("ALLOW_HUBSPOT_CREATE",)),
            _node("Build Write Patch", writes="true", ids="201"),
        ),
    ]
    result = verifier.verify(workflows, "disarmed")
    assert result["ok"] is False
    reason = next(r for r in result["reasons"] if "ALLOW_HUBSPOT_RECORD_WRITES" in r)
    assert "LV Contact Ingest (Cloud template)" in reason
    assert "Build Write Patch" in reason


def test_a_node_declaring_only_the_create_constant_is_judged_on_what_it_declares():
    """The contact lane's `Decide Action` declares ONLY the create flag (23-01). The old
    rule — every node must declare all five — reported that legitimate node as broken."""
    workflows = [
        _wf("LV Contact Ingest (Cloud template)", _node("Decide Action", declares=("ALLOW_HUBSPOT_CREATE",)))
    ]
    result = verifier.verify(workflows, "disarmed")
    assert result["ok"] is True
    assert result["reasons"] == []


def test_a_partially_declaring_node_still_fails_on_what_it_does_declare():
    workflows = [
        _wf(
            "LV Contact Ingest (Cloud template)",
            _node("Decide Action", declares=("ALLOW_HUBSPOT_CREATE",), create="true"),
        )
    ]
    result = verifier.verify(workflows, "disarmed")
    assert result["ok"] is False
    assert any("ALLOW_HUBSPOT_CREATE" in r and "Decide Action" in r for r in result["reasons"])


def test_a_workflow_with_no_declaring_node_contributes_nothing_and_is_not_an_error():
    workflows = [
        _wf("LV Enrichment (Cloud template)", _node("Decide Action"), _node("Decide Company Action")),
        _wf("Some Unrelated Workflow", {"name": "Set", "parameters": {"jsCode": "const x = 1;"}}),
        {"name": "Nodeless Workflow"},
    ]
    result = verifier.verify(workflows, "disarmed")
    assert result["ok"] is True
    assert result["declaring_nodes"] == 2


def test_a_scan_that_discovers_zero_declaring_nodes_fails_rather_than_passing():
    """A scan that matched nothing is otherwise indistinguishable from a disarmed
    instance — the vacuous-pass failure shape this milestone keeps hitting."""
    result = verifier.verify([_wf("Some Unrelated Workflow")], "disarmed")
    assert result["ok"] is False
    assert any("zero" in r.lower() or "no node" in r.lower() for r in result["reasons"])


def test_an_empty_workflow_list_is_also_a_zero_discovery_failure():
    result = verifier.verify([], "disarmed")
    assert result["ok"] is False
    assert result["reasons"]


def test_a_finding_names_the_workflow_because_a_node_name_alone_is_ambiguous():
    """Both `LV Enrichment (Cloud template)` and `LV Contact Ingest (Cloud template)`
    contain a node named `Decide Action`."""
    workflows = [
        _wf("LV Enrichment (Cloud template)", _node("Decide Action")),
        _wf("LV Contact Ingest (Cloud template)", _node("Decide Action", create="true")),
    ]
    result = verifier.verify(workflows, "disarmed")
    assert result["ok"] is False
    assert len(result["reasons"]) == 1
    assert "LV Contact Ingest (Cloud template)" in result["reasons"][0]
    assert "LV Enrichment (Cloud template)" not in result["reasons"][0]


# --- armed expectation ------------------------------------------------------------------

def test_armed_fails_when_review_writeback_is_also_enabled():
    """A dispatch armed window must not silently carry review writeback with it (D-02) —
    the canary's scope is record writes only."""
    workflows = _enrichment(
        contact={"writes": "true", "review": "true", "ids": "201"},
        company={"writes": "true", "ids": "201"},
    )
    result = verifier.verify(workflows, "armed", expected_allowlist="201")
    assert result["ok"] is False
    assert any("ALLOW_HUBSPOT_REVIEW_WRITES" in r for r in result["reasons"])


def test_armed_passes_with_requested_allowlist_and_writes_enabled_on_both_nodes():
    workflows = _enrichment(
        contact={"writes": "true", "ids": "201"},
        company={"writes": "true", "ids": "201"},
    )
    result = verifier.verify(workflows, "armed", expected_allowlist="201")
    assert result["ok"] is True
    assert result["reasons"] == []


def test_armed_fails_when_create_flag_is_also_enabled():
    """Backward compatibility, asserted rather than assumed: with no expected-armed set
    the armed expectation keeps Phase 22's exact meaning — record writes and nothing
    else — so an operator who forgets the new argument gets the STRICTER verdict."""
    workflows = _enrichment(
        contact={"writes": "true", "create": "true", "ids": "201"},
        company={"writes": "true", "ids": "201"},
    )
    result = verifier.verify(workflows, "armed", expected_allowlist="201")
    assert result["ok"] is False
    assert any("ALLOW_HUBSPOT_CREATE" in r for r in result["reasons"])


def test_armed_fails_when_live_allowlist_differs_from_requested():
    workflows = _enrichment(
        contact={"writes": "true", "ids": "999"},
        company={"writes": "true", "ids": "201"},
    )
    result = verifier.verify(workflows, "armed", expected_allowlist="201")
    assert result["ok"] is False
    reason = next(r for r in result["reasons"] if "Decide Action" in r and "Company" not in r)
    assert "999" in reason and "201" in reason


def test_armed_requires_a_non_empty_expected_allowlist():
    with pytest.raises(ValueError, match="requires a non-empty"):
        verifier.verify(_enrichment(contact={}, company={}), "armed", expected_allowlist=None)


# --- unknown expectation refuses, never silently no-ops ---------------------------------

def test_unknown_expectation_raises_from_verify():
    with pytest.raises(ValueError, match="unknown expectation"):
        verifier.verify(_enrichment(contact={}, company={}), "bogus")


def test_unknown_expectation_refused_by_cli_with_nonzero_exit(capsys):
    with pytest.raises(SystemExit) as exc:
        verifier.main(["--expectation", "bogus"])
    assert exc.value.code != 0
    assert "invalid choice" in capsys.readouterr().err.lower()


def test_armed_without_allowlist_refused_by_cli_with_nonzero_exit(capsys):
    with pytest.raises(SystemExit) as exc:
        verifier.main(["--expectation", "armed"])
    assert exc.value.code != 0
    assert "--allowlist" in capsys.readouterr().err


# --- output discipline: the node body is read but never printed in full ----------------

def test_report_output_never_leaks_the_full_jscode_body(capsys):
    marker = "SECRET_SENTINEL_NEVER_PRINTED_WHOLESALE"
    node = {
        "name": "Decide Action",
        "parameters": {"jsCode": (
            f'// {marker}\n'
            'const ALLOW_HUBSPOT_RECORD_WRITES = "false";\n'
            'const ALLOW_HUBSPOT_CREATE = "false";\n'
            'const TEST_RECORD_DOMAINS = "";\n'
            'const TEST_RECORD_IDS = "";\n'
        )},
    }
    workflows = [_wf("LV Enrichment (Cloud template)", node, _node("Decide Company Action"))]
    result = verifier.verify(workflows, "disarmed")
    verifier._print_report(result)
    out = capsys.readouterr().out
    assert marker not in out
    assert "false" in out  # the parsed literal values ARE printed


def test_report_states_its_own_coverage_so_the_operator_reads_it_rather_than_infers_it(capsys):
    workflows = [
        _wf("LV Enrichment (Cloud template)", _node("Decide Action"), _node("Decide Company Action")),
        _wf("LV Contact Ingest (Cloud template)", _node("Decide Action", declares=("ALLOW_HUBSPOT_CREATE",))),
    ]
    verifier._print_report(verifier.verify(workflows, "disarmed"))
    out = capsys.readouterr().out
    assert "LV Contact Ingest (Cloud template)" in out
    assert "declaring node" in out
    # A partially declaring node prints only what it declares.
    assert "ALLOW_HUBSPOT_REVIEW_WRITES" in out  # the enrichment nodes declare it
    assert out.count("ALLOW_HUBSPOT_CREATE") == 3


# --- no credentials: skip banner, exit 0, zero HTTP calls -------------------------------

def test_no_credentials_skips_with_zero_http_calls(capsys):
    rc = verifier.main([])
    assert rc == 0
    assert "skipped" in capsys.readouterr().out.lower()
