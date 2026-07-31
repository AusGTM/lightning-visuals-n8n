# tests/test_verify_live_write_safety.py
#
# Phase 22 Plan 02 (T-22-06..10) — offline proof for scripts/verify_live_write_safety.py.
# Fully hermetic: no network. Drives the behaviour table with small hand-built workflow
# dicts (never the real n8n/wf_enrichment_cloud.json — this plan's read-back logic is
# proven against synthetic shapes so every refusal path is reachable without depending
# on the committed build's exact literals, which tests/test_deploy_write_safety_overlay.py
# already pins separately).
import json

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


def _node(name, writes="false", create="false", review="false", ids="", domains=""):
    values = {
        "ALLOW_HUBSPOT_RECORD_WRITES": writes,
        "ALLOW_HUBSPOT_CREATE": create,
        "ALLOW_HUBSPOT_REVIEW_WRITES": review,
        "TEST_RECORD_DOMAINS": domains,
        "TEST_RECORD_IDS": ids,
    }
    # Declared off the verifier's OWN checked set, so a constant added to the overlay
    # (ALLOW_HUBSPOT_REVIEW_WRITES was the fifth, Phase 30 Plan 01) fails loudly here as
    # a missing fixture value rather than making every node report a missing constant.
    assert set(values) == set(verifier.CHECKED_CONSTANTS), (
        "fixture is out of date with verifier.CHECKED_CONSTANTS: "
        f"{set(verifier.CHECKED_CONSTANTS) ^ set(values)}"
    )
    js_code = (
        "// unrelated preamble, e.g. taxonomy consts, should never confuse the parser\n"
        'const SOME_OTHER_CONST = "unrelated";\n'
        + "".join(f'const {k} = "{v}";\n' for k, v in values.items())
    )
    return {"name": name, "parameters": {"jsCode": js_code}}


def _wf(contact=None, company=None):
    nodes = []
    if contact is not None:
        nodes.append(_node("Decide Action", **contact))
    if company is not None:
        nodes.append(_node("Decide Company Action", **company))
    return {"name": "LV Enrichment (Cloud template)", "nodes": nodes}


# --- spec parity: the checked set must never drift from the overlay's own set --------

def test_checked_constants_match_overlay_spec():
    assert set(verifier.CHECKED_CONSTANTS) == set(deploy._OVERLAY_FLAG_SPEC.keys())


# --- disarmed expectation --------------------------------------------------------------

def test_disarmed_passes_when_both_nodes_fully_disabled():
    wf = _wf(contact={}, company={})
    result = verifier.verify(wf, "disarmed")
    assert result["ok"] is True
    assert result["reasons"] == []


def test_disarmed_fails_when_one_node_still_has_record_writes_enabled():
    wf = _wf(contact={"writes": "true", "ids": "201"}, company={})
    result = verifier.verify(wf, "disarmed")
    assert result["ok"] is False
    assert any("Decide Action" in r and "ALLOW_HUBSPOT_RECORD_WRITES" in r for r in result["reasons"])


def test_disarmed_fails_on_stale_allowlist_even_with_flags_disabled():
    wf = _wf(contact={}, company={"ids": "9604614548"})
    result = verifier.verify(wf, "disarmed")
    assert result["ok"] is False
    assert any("Decide Company Action" in r and "TEST_RECORD_IDS" in r for r in result["reasons"])


def test_disarmed_fails_when_review_writeback_is_still_armed():
    """Phase 30 Plan 01: ALLOW_HUBSPOT_REVIEW_WRITES is a write-enabling flag this
    read-back had no knowledge of when it was written. A live artifact with review
    writeback armed reporting `disarmed PASS` is the exact false-success this script
    exists to prevent, so the checked booleans are derived from the overlay set."""
    wf = _wf(contact={"review": "true", "ids": "201"}, company={})
    result = verifier.verify(wf, "disarmed")
    assert result["ok"] is False
    assert any("Decide Action" in r and "ALLOW_HUBSPOT_REVIEW_WRITES" in r for r in result["reasons"])


# --- armed expectation ------------------------------------------------------------------

def test_armed_fails_when_review_writeback_is_also_enabled():
    """A dispatch armed window must not silently carry review writeback with it (D-02) —
    the canary's scope is record writes only."""
    wf = _wf(
        contact={"writes": "true", "review": "true", "ids": "201"},
        company={"writes": "true", "ids": "201"},
    )
    result = verifier.verify(wf, "armed", expected_allowlist="201")
    assert result["ok"] is False
    assert any("ALLOW_HUBSPOT_REVIEW_WRITES" in r for r in result["reasons"])


def test_armed_passes_with_requested_allowlist_and_writes_enabled_on_both_nodes():
    wf = _wf(
        contact={"writes": "true", "ids": "201"},
        company={"writes": "true", "ids": "201"},
    )
    result = verifier.verify(wf, "armed", expected_allowlist="201")
    assert result["ok"] is True
    assert result["reasons"] == []
    # The report states the allowlist value read back from the live artifact.
    for report in result["nodes"]:
        assert report["constants"]["TEST_RECORD_IDS"] == "201"


def test_armed_fails_when_create_flag_is_also_enabled():
    wf = _wf(
        contact={"writes": "true", "create": "true", "ids": "201"},
        company={"writes": "true", "ids": "201"},
    )
    result = verifier.verify(wf, "armed", expected_allowlist="201")
    assert result["ok"] is False
    assert any("ALLOW_HUBSPOT_CREATE" in r for r in result["reasons"])


def test_armed_fails_when_live_allowlist_differs_from_requested():
    wf = _wf(
        contact={"writes": "true", "ids": "999"},
        company={"writes": "true", "ids": "201"},
    )
    result = verifier.verify(wf, "armed", expected_allowlist="201")
    assert result["ok"] is False
    reason = next(r for r in result["reasons"] if "Decide Action" in r)
    assert "999" in reason and "201" in reason


def test_armed_requires_a_non_empty_expected_allowlist():
    wf = _wf(contact={}, company={})
    with pytest.raises(ValueError, match="requires a non-empty"):
        verifier.verify(wf, "armed", expected_allowlist=None)


# --- malformed / missing shapes never raise --------------------------------------------

def test_missing_write_decision_node_fails_with_explicit_reason_not_an_exception():
    wf = _wf(contact={}, company=None)  # "Decide Company Action" entirely absent
    result = verifier.verify(wf, "disarmed")
    assert result["ok"] is False
    assert any("Decide Company Action" in r and "not found" in r for r in result["reasons"])


def test_node_missing_one_of_the_four_constants_fails_with_explicit_reason():
    incomplete_node = {
        "name": "Decide Action",
        "parameters": {"jsCode": 'const ALLOW_HUBSPOT_RECORD_WRITES = "false";\n'},
    }
    wf = {"name": "LV Enrichment (Cloud template)", "nodes": [incomplete_node, _node("Decide Company Action")]}
    result = verifier.verify(wf, "disarmed")
    assert result["ok"] is False
    assert any("missing constant" in r and "Decide Action" in r for r in result["reasons"])


# --- unknown expectation refuses, never silently no-ops ---------------------------------

def test_unknown_expectation_raises_from_verify():
    wf = _wf(contact={}, company={})
    with pytest.raises(ValueError, match="unknown expectation"):
        verifier.verify(wf, "bogus")


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
    wf = {"name": "LV Enrichment (Cloud template)", "nodes": [node, _node("Decide Company Action")]}
    result = verifier.verify(wf, "disarmed")
    verifier._print_report(result)
    out = capsys.readouterr().out
    assert marker not in out
    assert "false" in out  # the parsed literal values ARE printed


# --- no credentials: skip banner, exit 0, zero HTTP calls -------------------------------

def test_no_credentials_skips_with_zero_http_calls(capsys):
    rc = verifier.main([])
    assert rc == 0
    assert "skipped" in capsys.readouterr().out.lower()
