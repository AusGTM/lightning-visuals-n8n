# tests/test_deploy_write_safety_overlay.py
#
# Phase 16.7 — extending the deploy-time overlay from the two boolean research kill
# switches to the write-safety constants, including the ones whose point is a VALUE
# (TEST_RECORD_IDS / TEST_RECORD_DOMAINS) rather than a flip.
#
# The property that matters here is not "can it arm writes" but "can it arm writes ONLY
# in a shape that is still bounded": a non-empty allowlist is mandatory in the same
# request, the value lands as a quoted JS string literal (never injected JS), and the
# fail-closed re-scan still refuses a workflow that would deploy carrying anything other
# than the requested literal.
import json
from pathlib import Path

import pytest
import requests

import scripts.deploy_n8n_workflows as deploy

ROOT = Path(__file__).resolve().parents[1]
ENRICHMENT_WF_PATH = ROOT / "n8n" / "wf_enrichment_cloud.json"


def raise_http(*args, **kwargs):
    raise AssertionError("a live n8n request leaked past a guard/gate that should have refused")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    for var in ("N8N_URL", "N8N_API_KEY", "N8N_EXPECTED_URL", "ALLOW_N8N_DEPLOY", "DRY_RUN",
                "ENABLE_BAKED_FLAGS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(requests, "get", raise_http)
    monkeypatch.setattr(requests, "post", raise_http)
    monkeypatch.setattr(requests, "put", raise_http)


def _wf() -> dict:
    return json.loads(ENRICHMENT_WF_PATH.read_text())


def _decls(workflow: dict, flag: str) -> list:
    import re
    out = []
    for node in workflow.get("nodes", []):
        js = node.get("parameters", {}).get("jsCode")
        if isinstance(js, str):
            out += re.findall(rf"const\s+{flag}\s*=\s*([^;]+);", js)
    return out


# --- the committed artifact is the disabled baseline this whole overlay presumes ------

def test_committed_build_carries_the_disabled_write_safety_literals():
    wf = _wf()
    assert set(_decls(wf, "ALLOW_HUBSPOT_RECORD_WRITES")) == {'"false"'}
    assert set(_decls(wf, "ALLOW_HUBSPOT_CREATE")) == {'"false"'}
    assert set(_decls(wf, "TEST_RECORD_IDS")) == {'""'}
    assert set(_decls(wf, "TEST_RECORD_DOMAINS")) == {'""'}


# --- the canary shape: writes on, ONE record, creates still off -----------------------

def test_canary_shape_rewrites_writes_on_and_allowlists_exactly_one_id(monkeypatch):
    monkeypatch.setenv("ENABLE_BAKED_FLAGS",
                       "ALLOW_HUBSPOT_RECORD_WRITES,TEST_RECORD_IDS=201")
    requested = deploy._requested_overlay_flags()
    assert requested == {"ALLOW_HUBSPOT_RECORD_WRITES": '"true"', "TEST_RECORD_IDS": '"201"'}

    new_wf, counts = deploy.enable_baked_flags(_wf(), requested)
    assert counts["ALLOW_HUBSPOT_RECORD_WRITES"] > 0
    assert counts["TEST_RECORD_IDS"] > 0
    assert set(_decls(new_wf, "ALLOW_HUBSPOT_RECORD_WRITES")) == {'"true"'}
    assert set(_decls(new_wf, "TEST_RECORD_IDS")) == {'"201"'}
    # Untouched by this request — creates stay off and the domain allowlist stays empty.
    assert set(_decls(new_wf, "ALLOW_HUBSPOT_CREATE")) == {'"false"'}
    assert set(_decls(new_wf, "TEST_RECORD_DOMAINS")) == {'""'}


@pytest.mark.parametrize("bad", ['201";DROP', "201 OR 1", 'a"b', "201;", "id with space", "*"])
def test_values_outside_the_id_domain_charset_are_refused(monkeypatch, bad):
    """A value carrying a quote or a `;` would split a declaration the fail-closed
    re-scan then could not verify — so the charset is refused at the door rather than
    escaped and hoped about."""
    monkeypatch.setenv("ENABLE_BAKED_FLAGS",
                       f"ALLOW_HUBSPOT_RECORD_WRITES,TEST_RECORD_IDS={bad}")
    with pytest.raises(ValueError, match="not a plain id/domain list"):
        deploy._requested_overlay_flags()


def test_multi_id_and_domain_values_are_accepted_and_land_as_string_literals(monkeypatch):
    # `,` separates ENTRIES, so a multi-id allowlist uses `|` and is rendered back to the
    # comma-separated form _writeSafetyAllows() splits on.
    monkeypatch.setenv(
        "ENABLE_BAKED_FLAGS",
        "ALLOW_HUBSPOT_RECORD_WRITES,TEST_RECORD_IDS=201|301,"
        "TEST_RECORD_DOMAINS=mrc.racing.com")
    requested = deploy._requested_overlay_flags()
    assert requested["TEST_RECORD_IDS"] == '"201,301"'
    assert requested["TEST_RECORD_DOMAINS"] == '"mrc.racing.com"'
    new_wf, _ = deploy.enable_baked_flags(_wf(), requested)
    for decl in _decls(new_wf, "TEST_RECORD_IDS"):
        assert json.loads(decl) == "201,301"
    for decl in _decls(new_wf, "TEST_RECORD_DOMAINS"):
        assert json.loads(decl) == "mrc.racing.com"


# --- the fail-safes ------------------------------------------------------------------

def test_writes_without_an_allowlist_are_refused(monkeypatch):
    monkeypatch.setenv("ENABLE_BAKED_FLAGS", "ALLOW_HUBSPOT_RECORD_WRITES")
    with pytest.raises(ValueError, match="without an allowlist"):
        deploy._requested_overlay_flags()


def test_writes_with_an_explicitly_empty_allowlist_are_refused(monkeypatch):
    monkeypatch.setenv("ENABLE_BAKED_FLAGS", "ALLOW_HUBSPOT_RECORD_WRITES,TEST_RECORD_IDS=")
    with pytest.raises(ValueError):
        deploy._requested_overlay_flags()


def test_create_without_record_writes_is_refused(monkeypatch):
    monkeypatch.setenv("ENABLE_BAKED_FLAGS", "ALLOW_HUBSPOT_CREATE,TEST_RECORD_IDS=201")
    with pytest.raises(ValueError, match="no effect unless"):
        deploy._requested_overlay_flags()


def test_bare_allowlist_flag_is_refused_because_it_would_be_a_silent_no_op(monkeypatch):
    monkeypatch.setenv("ENABLE_BAKED_FLAGS", "TEST_RECORD_IDS")
    with pytest.raises(ValueError, match="requires an explicit value"):
        deploy._requested_overlay_flags()


def test_boolean_kill_switch_rejects_a_value(monkeypatch):
    monkeypatch.setenv("ENABLE_BAKED_FLAGS", "ALLOW_WEB_RESEARCH=true")
    with pytest.raises(ValueError, match="takes no value"):
        deploy._requested_overlay_flags()


@pytest.mark.parametrize("cap", ["MAX_WEB_RESEARCH_PER_RUN", "MAX_JUDGE_VALIDATIONS_PER_RUN",
                                 "ANTHROPIC_RESEARCH_MODEL", "ANTHROPIC_JUDGE_MODEL"])
def test_cost_caps_and_models_stay_non_overlayable(monkeypatch, cap):
    monkeypatch.setenv("ENABLE_BAKED_FLAGS", f"{cap}=999")
    with pytest.raises(ValueError, match="unknown flag"):
        deploy._requested_overlay_flags()


def test_rescan_refuses_when_a_declaration_survives_in_an_unreachable_form():
    """A spacing drift the exact-literal replace cannot reach must raise, not deploy
    a workflow that silently keeps the old value."""
    workflow = {"name": "drifted", "nodes": [
        {"parameters": {"jsCode": 'const TEST_RECORD_IDS  =  "";\n'}},
    ]}
    with pytest.raises(ValueError, match="still carries literal"):
        deploy.enable_baked_flags(workflow, {"TEST_RECORD_IDS": '"201"'})


def test_unrequested_write_flags_are_untouched_by_a_research_only_request(monkeypatch):
    monkeypatch.setenv("ENABLE_BAKED_FLAGS", "ALLOW_WEB_RESEARCH")
    requested = deploy._requested_overlay_flags()
    assert requested == {"ALLOW_WEB_RESEARCH": "true"}
    new_wf, _ = deploy.enable_baked_flags(_wf(), requested)
    assert set(_decls(new_wf, "ALLOW_HUBSPOT_RECORD_WRITES")) == {'"false"'}
    assert set(_decls(new_wf, "TEST_RECORD_IDS")) == {'""'}
