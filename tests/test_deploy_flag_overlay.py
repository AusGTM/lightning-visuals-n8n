# tests/test_deploy_flag_overlay.py
#
# Phase 16.5 Task 1 — the deploy-time research/escalation overlay mechanism's own
# tests: purity, exactness against the real built artifact, independence, fail-closed
# on drift, rejection of non-overlayable names, ambient-env inertness, deploy-set-level
# refusal, and dry-run visibility.
#
# Artifact invariants (committed stays disabled, Criterion 5 on the enabled build, the
# diff-is-only-the-four-lines proof) live in tests/test_enabled_build_invariants.py.
# The offline oracle for the enabled research/judge lanes lives in
# tests/n8n/enabledResearchLaneFlow.test.mjs. This file is the mechanism only.
import copy
import json
import re
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
                "ENABLE_BAKED_FLAGS", "ALLOW_WEB_RESEARCH", "ALLOW_SONNET_ESCALATION"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(requests, "get", raise_http)
    monkeypatch.setattr(requests, "post", raise_http)
    monkeypatch.setattr(requests, "put", raise_http)


def _load_enrichment_workflow() -> dict:
    return json.loads(ENRICHMENT_WF_PATH.read_text())


# --- (a) purity -----------------------------------------------------------------------

def test_enable_baked_flags_is_pure_input_untouched():
    wf = _load_enrichment_workflow()
    snapshot = copy.deepcopy(wf)
    new_wf, counts = deploy.enable_baked_flags(wf, ["ALLOW_WEB_RESEARCH"])
    assert wf == snapshot  # input deep-equal to a pre-call snapshot
    assert new_wf is not wf
    assert counts["ALLOW_WEB_RESEARCH"] > 0


# --- (b) exactness on the real artifact -------------------------------------------------

def test_enable_baked_flags_exactness_on_real_committed_artifact():
    raw = ENRICHMENT_WF_PATH.read_text()
    expected_research_count = raw.count("const ALLOW_WEB_RESEARCH = false;")
    expected_escalation_count = raw.count("const ALLOW_SONNET_ESCALATION = false;")
    assert expected_research_count > 0
    assert expected_escalation_count > 0

    wf = _load_enrichment_workflow()
    new_wf, counts = deploy.enable_baked_flags(
        wf, ["ALLOW_WEB_RESEARCH", "ALLOW_SONNET_ESCALATION"]
    )
    assert counts["ALLOW_WEB_RESEARCH"] == expected_research_count
    assert counts["ALLOW_SONNET_ESCALATION"] == expected_escalation_count

    serialized = json.dumps(new_wf)
    assert re.findall(r"const ALLOW_WEB_RESEARCH = (\w+);", serialized) == \
        ["true"] * expected_research_count
    assert re.findall(r"const ALLOW_SONNET_ESCALATION = (\w+);", serialized) == \
        ["true"] * expected_escalation_count


# --- (c) independence -------------------------------------------------------------------

def test_enable_baked_flags_independence_research_only():
    wf = _load_enrichment_workflow()
    new_wf, _ = deploy.enable_baked_flags(wf, ["ALLOW_WEB_RESEARCH"])
    serialized = json.dumps(new_wf)
    assert "const ALLOW_WEB_RESEARCH = true;" in serialized
    assert "const ALLOW_SONNET_ESCALATION = false;" in serialized
    assert "const ALLOW_SONNET_ESCALATION = true;" not in serialized


def test_enable_baked_flags_independence_escalation_only():
    wf = _load_enrichment_workflow()
    new_wf, _ = deploy.enable_baked_flags(wf, ["ALLOW_SONNET_ESCALATION"])
    serialized = json.dumps(new_wf)
    assert "const ALLOW_SONNET_ESCALATION = true;" in serialized
    assert "const ALLOW_WEB_RESEARCH = false;" in serialized
    assert "const ALLOW_WEB_RESEARCH = true;" not in serialized


# --- (d) fail closed on drift — the headline test ---------------------------------------

def test_enable_baked_flags_raises_on_spacing_variant_the_exact_rewrite_cannot_match():
    # No spaces around `=` — the exact-literal replace step cannot match this, and the
    # fail-closed re-scan must catch it and refuse rather than silently leaving it
    # disabled while reporting a successful rewrite elsewhere in the same workflow.
    workflow = {
        "name": "wf-drift-spacing",
        "nodes": [{"name": "Node A", "parameters": {
            "jsCode": "const ALLOW_WEB_RESEARCH=false;\nconsole.log(1);"
        }}],
    }
    with pytest.raises(ValueError, match="ALLOW_WEB_RESEARCH"):
        deploy.enable_baked_flags(workflow, ["ALLOW_WEB_RESEARCH"])


def test_enable_baked_flags_raises_on_numeric_literal_variant():
    # A numeric literal instead of the expected boolean — again unreachable by the exact
    # replace, and again must be caught by the re-scan rather than silently ignored.
    workflow = {
        "name": "wf-drift-numeric",
        "nodes": [{"name": "Node A", "parameters": {
            "jsCode": "const ALLOW_SONNET_ESCALATION = 0;\nconsole.log(1);"
        }}],
    }
    with pytest.raises(ValueError, match="ALLOW_SONNET_ESCALATION"):
        deploy.enable_baked_flags(workflow, ["ALLOW_SONNET_ESCALATION"])


def test_enable_baked_flags_never_returns_a_workflow_with_a_surviving_disabled_declaration():
    # The negative case stated explicitly: whatever this function returns (or it raises),
    # it must never hand back a workflow with a disabled declaration for a requested flag.
    # This prevents the exact false-success this phase is designed against — a deploy
    # that reports success while shipping a disabled build.
    workflow = {
        "name": "wf-drift-mixed",
        "nodes": [
            {"name": "Node A", "parameters": {"jsCode": "const ALLOW_WEB_RESEARCH = false;"}},
            {"name": "Node B", "parameters": {"jsCode": "const ALLOW_WEB_RESEARCH=false;"}},
        ],
    }
    try:
        new_wf, _ = deploy.enable_baked_flags(workflow, ["ALLOW_WEB_RESEARCH"])
    except ValueError:
        return  # raising is the correct fail-closed outcome
    serialized = json.dumps(new_wf)
    assert "const ALLOW_WEB_RESEARCH = false;" not in serialized
    assert "ALLOW_WEB_RESEARCH=false" not in serialized


# --- (e) non-overlayable names rejected --------------------------------------------------
#
# Phase 16.7 deliberately MOVED the write-safety constants into the overlayable set so the
# write-path canary can arm one record without a rebuild; their guards (an allowlist is
# mandatory in the same request, values are charset-restricted) live in
# tests/test_deploy_write_safety_overlay.py. Cost caps and model names stay out of reach
# permanently — those are what this parametrization protects.

@pytest.mark.parametrize("bad_flag", [
    "MAX_WEB_RESEARCH_PER_RUN",
    "MAX_SONNET_VALIDATIONS_PER_RUN",
    "ANTHROPIC_SONNET_MODEL",
])
def test_enable_baked_flags_rejects_non_overlayable_names(bad_flag):
    wf = _load_enrichment_workflow()
    with pytest.raises(ValueError, match=re.escape(bad_flag)):
        deploy.enable_baked_flags(wf, [bad_flag])


@pytest.mark.parametrize("bad_flag", [
    "MAX_WEB_RESEARCH_PER_RUN",
    "MAX_SONNET_VALIDATIONS_PER_RUN",
    "ANTHROPIC_SONNET_MODEL",
])
def test_requested_overlay_flags_rejects_non_overlayable_names_from_env(monkeypatch, bad_flag):
    monkeypatch.setenv("ENABLE_BAKED_FLAGS", bad_flag)
    with pytest.raises(ValueError, match=re.escape(bad_flag)):
        deploy._requested_overlay_flags()


# --- (f) zero declarations is not a raise at the function level -------------------------

def test_enable_baked_flags_zero_declarations_returns_unchanged_not_a_raise():
    wf = json.loads((ROOT / "n8n" / "wf_contact_ingest_cloud.json").read_text())
    raw = json.dumps(wf)
    assert "ALLOW_WEB_RESEARCH" not in raw and "ALLOW_SONNET_ESCALATION" not in raw
    new_wf, counts = deploy.enable_baked_flags(
        wf, ["ALLOW_WEB_RESEARCH", "ALLOW_SONNET_ESCALATION"]
    )
    assert counts == {"ALLOW_WEB_RESEARCH": 0, "ALLOW_SONNET_ESCALATION": 0}
    assert new_wf == wf


# --- (g) deploy-set refusal --------------------------------------------------------------

def test_main_refuses_at_deploy_set_level_when_requested_flag_matches_zero_declarations(
    monkeypatch, capsys
):
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_N8N_DEPLOY", "true")
    monkeypatch.setenv("ENABLE_BAKED_FLAGS", "ALLOW_WEB_RESEARCH")
    monkeypatch.setattr(deploy, "_get_live_workflows", lambda: [])
    monkeypatch.setattr(
        deploy, "_load_local_workflows",
        lambda: [{"name": "A", "nodes": [{"name": "N", "parameters": {"jsCode": "console.log(1);"}}]}],
    )
    monkeypatch.setattr(deploy, "_load_credential_id_map", lambda: {})

    create_calls, update_calls = [], []
    monkeypatch.setattr(deploy, "_create_workflow_live",
                         lambda body: (create_calls.append(body), (201, None))[1])
    monkeypatch.setattr(deploy, "_update_workflow_live",
                         lambda wid, body: (update_calls.append((wid, body)), (200, None))[1])

    rc = deploy.main()
    assert rc == 1
    assert create_calls == []
    assert update_calls == []
    out = capsys.readouterr().out
    assert "REFUSED" in out
    assert "ALLOW_WEB_RESEARCH" in out


# --- (h) ambient env inertness — Criterion 2 as an executable statement -----------------

def test_ambient_env_names_have_zero_effect_on_the_captured_put_body(monkeypatch):
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_N8N_DEPLOY", "true")
    # The .env-style Python-lane names, both true — ENABLE_BAKED_FLAGS deliberately unset.
    monkeypatch.setenv("ALLOW_WEB_RESEARCH", "true")
    monkeypatch.setenv("ALLOW_SONNET_ESCALATION", "true")

    real_wf = _load_enrichment_workflow()
    monkeypatch.setattr(deploy, "_get_live_workflows", lambda: [{"id": "live-id", "name": real_wf["name"]}])
    monkeypatch.setattr(deploy, "_load_local_workflows", lambda: [real_wf])
    name_to_id = {"LV Lusha": "id-lusha", "LV Apollo": "id-apollo", "LV ZoomInfo": "id-zoominfo",
                  "LV HubSpot": "id-hubspot", "LV Anthropic": "id-anthropic",
                  "LV Enrichment Webhook": "id-webhook-secret"}
    monkeypatch.setattr(deploy, "_load_credential_id_map", lambda: name_to_id)

    update_calls = []
    monkeypatch.setattr(deploy, "_update_workflow_live",
                         lambda wid, body: (update_calls.append((wid, body)), (200, None))[1])

    rc = deploy.main()
    assert rc == 0
    assert len(update_calls) == 1
    body = update_calls[0][1]
    serialized = json.dumps(body)
    assert "const ALLOW_WEB_RESEARCH = false;" in serialized
    assert "const ALLOW_SONNET_ESCALATION = false;" in serialized
    assert "const ALLOW_WEB_RESEARCH = true;" not in serialized
    assert "const ALLOW_SONNET_ESCALATION = true;" not in serialized


# --- (i) default-off through the real path -----------------------------------------------

def test_default_off_through_real_path_unset_enable_baked_flags(monkeypatch):
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_N8N_DEPLOY", "true")

    real_wf = _load_enrichment_workflow()
    monkeypatch.setattr(deploy, "_get_live_workflows", lambda: [{"id": "live-id", "name": real_wf["name"]}])
    monkeypatch.setattr(deploy, "_load_local_workflows", lambda: [real_wf])
    name_to_id = {"LV Lusha": "id-lusha", "LV Apollo": "id-apollo", "LV ZoomInfo": "id-zoominfo",
                  "LV HubSpot": "id-hubspot", "LV Anthropic": "id-anthropic",
                  "LV Enrichment Webhook": "id-webhook-secret"}
    monkeypatch.setattr(deploy, "_load_credential_id_map", lambda: name_to_id)

    update_calls = []
    monkeypatch.setattr(deploy, "_update_workflow_live",
                         lambda wid, body: (update_calls.append((wid, body)), (200, None))[1])

    rc = deploy.main()
    assert rc == 0
    body = update_calls[0][1]
    serialized = json.dumps(body)
    assert "const ALLOW_WEB_RESEARCH = false;" in serialized
    assert "const ALLOW_SONNET_ESCALATION = false;" in serialized


# --- (j) enabled through the real path ----------------------------------------------------

def test_enabled_through_real_path_and_bind_credentials_succeeds(monkeypatch):
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_N8N_DEPLOY", "true")
    monkeypatch.setenv("ENABLE_BAKED_FLAGS", "ALLOW_WEB_RESEARCH,ALLOW_SONNET_ESCALATION")

    real_wf = _load_enrichment_workflow()
    monkeypatch.setattr(deploy, "_get_live_workflows", lambda: [{"id": "live-id", "name": real_wf["name"]}])
    monkeypatch.setattr(deploy, "_load_local_workflows", lambda: [real_wf])
    name_to_id = {"LV Lusha": "id-lusha", "LV Apollo": "id-apollo", "LV ZoomInfo": "id-zoominfo",
                  "LV HubSpot": "id-hubspot", "LV Anthropic": "id-anthropic",
                  "LV Enrichment Webhook": "id-webhook-secret"}
    monkeypatch.setattr(deploy, "_load_credential_id_map", lambda: name_to_id)

    update_calls = []
    monkeypatch.setattr(deploy, "_update_workflow_live",
                         lambda wid, body: (update_calls.append((wid, body)), (200, None))[1])

    rc = deploy.main()
    assert rc == 0
    body = update_calls[0][1]
    serialized = json.dumps(body)
    assert "const ALLOW_WEB_RESEARCH = true;" in serialized
    assert "const ALLOW_SONNET_ESCALATION = true;" in serialized
    assert "const ALLOW_WEB_RESEARCH = false;" not in serialized
    assert "const ALLOW_SONNET_ESCALATION = false;" not in serialized
    # bind_credentials() composes with the overlay as main() does (proving composition,
    # not just the individual pieces): every hubspot node in the captured body is bound.
    hubspot_nodes = [n for n in body["nodes"] if n.get("type") == "n8n-nodes-base.hubspot"]
    assert hubspot_nodes
    for node in hubspot_nodes:
        assert "credentials" in node


# --- (k) dry-run visibility ----------------------------------------------------------------

def test_dry_run_visibility_prints_rewrite_plan_and_makes_zero_http_calls(monkeypatch, capsys):
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setenv("ENABLE_BAKED_FLAGS", "ALLOW_WEB_RESEARCH,ALLOW_SONNET_ESCALATION")
    # DRY_RUN default (true), ALLOW_N8N_DEPLOY unset — write gate closed.

    real_wf = _load_enrichment_workflow()
    monkeypatch.setattr(deploy, "_get_live_workflows", lambda: [{"id": "live-id", "name": real_wf["name"]}])
    monkeypatch.setattr(deploy, "_load_local_workflows", lambda: [real_wf])

    create_calls, update_calls = [], []
    monkeypatch.setattr(deploy, "_create_workflow_live",
                         lambda body: (create_calls.append(body), (201, None))[1])
    monkeypatch.setattr(deploy, "_update_workflow_live",
                         lambda wid, body: (update_calls.append((wid, body)), (200, None))[1])

    rc = deploy.main()
    assert rc == 0
    assert create_calls == []
    assert update_calls == []
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "ALLOW_WEB_RESEARCH" in out
    assert "ALLOW_SONNET_ESCALATION" in out
    assert "rewritten" in out


# --- module hygiene: never import build_cloud_workflows (that module has import-time
# codegen side effects into n8n/code/) -------------------------------------------------

def test_deploy_module_never_imports_build_cloud_workflows():
    import ast
    tree = ast.parse((ROOT / "scripts" / "deploy_n8n_workflows.py").read_text())
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    assert not any("build_cloud_workflows" in m for m in imported_modules)
