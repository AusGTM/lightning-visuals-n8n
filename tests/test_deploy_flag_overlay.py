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
#
# quick-260730-fij: ALLOW_WEB_RESEARCH joined ALLOW_JUDGE_ESCALATION (quick-260730-din)
# as a default-true, non-overlayable flag — it now defaults `true` at build time and has
# no _OVERLAY_FLAG_SPEC entry. The write-safety family (ALLOW_HUBSPOT_RECORD_WRITES et
# al.) is the ONLY remaining overlayable target, so every mechanism test below that used
# to exercise ALLOW_WEB_RESEARCH now exercises ALLOW_HUBSPOT_RECORD_WRITES instead — same
# mechanism, different (still-overlayable) subject.
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
                "ENABLE_BAKED_FLAGS", "ALLOW_WEB_RESEARCH", "ALLOW_JUDGE_ESCALATION"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(requests, "get", raise_http)
    monkeypatch.setattr(requests, "post", raise_http)
    monkeypatch.setattr(requests, "put", raise_http)


def _load_enrichment_workflow() -> dict:
    return json.loads(ENRICHMENT_WF_PATH.read_text())


def _decls(workflow: dict, flag: str) -> list:
    """Same helper as tests/test_deploy_write_safety_overlay.py's `_decls` — copied
    rather than cross-imported (house convention). Extracts the raw RHS literal text
    (including quote characters for quoted-string flags) from each node's jsCode."""
    out = []
    for node in workflow.get("nodes", []):
        js = node.get("parameters", {}).get("jsCode")
        if isinstance(js, str):
            out += re.findall(rf"const\s+{flag}\s*=\s*([^;]+);", js)
    return out


def _hubspot_bound_node_names(workflow: dict) -> set:
    """Same helper as tests/test_fetch_by_id_topology.py's `_hubspot_bound_node_names` —
    copied rather than cross-imported (house convention: test files don't import each
    other). Native n8n-nodes-base.hubspot nodes PLUS httpRequest nodes carrying
    nodeCredentialType == hubspotAppToken (BUG 10/23: the search/fetch nodes that moved
    off the native node reuse this credential type via a generic httpRequest node)."""
    names = {n["name"] for n in workflow["nodes"] if n["type"] == "n8n-nodes-base.hubspot"}
    names |= {
        n["name"] for n in workflow["nodes"]
        if n.get("type") == "n8n-nodes-base.httpRequest"
        and n.get("parameters", {}).get("nodeCredentialType") == "hubspotAppToken"
    }
    return names


# --- (a) purity -----------------------------------------------------------------------

def test_enable_baked_flags_is_pure_input_untouched():
    wf = _load_enrichment_workflow()
    snapshot = copy.deepcopy(wf)
    new_wf, counts = deploy.enable_baked_flags(wf, ["ALLOW_HUBSPOT_RECORD_WRITES"])
    assert wf == snapshot  # input deep-equal to a pre-call snapshot
    assert new_wf is not wf
    assert counts["ALLOW_HUBSPOT_RECORD_WRITES"] > 0


# --- (b) exactness on the real artifact -------------------------------------------------

def test_enable_baked_flags_exactness_on_real_committed_artifact():
    wf = _load_enrichment_workflow()
    expected_count = len(_decls(wf, "ALLOW_HUBSPOT_RECORD_WRITES"))
    assert expected_count > 0
    # ALLOW_WEB_RESEARCH (quick-260730-fij) / ALLOW_JUDGE_ESCALATION (quick-260730-din)
    # are no longer overlayable — both default `true` at build time and have no
    # _OVERLAY_FLAG_SPEC entry at all.

    new_wf, counts = deploy.enable_baked_flags(wf, ["ALLOW_HUBSPOT_RECORD_WRITES"])
    assert counts["ALLOW_HUBSPOT_RECORD_WRITES"] == expected_count
    assert set(_decls(new_wf, "ALLOW_HUBSPOT_RECORD_WRITES")) == {'"true"'}


# --- (c) independence -------------------------------------------------------------------

def test_enable_baked_flags_independence_write_only():
    # ALLOW_WEB_RESEARCH / ALLOW_JUDGE_ESCALATION are armed `true` in the committed build
    # UNCONDITIONALLY — enabling only write-safety must not need, and cannot affect,
    # those already-armed declarations.
    wf = _load_enrichment_workflow()
    new_wf, _ = deploy.enable_baked_flags(wf, ["ALLOW_HUBSPOT_RECORD_WRITES"])
    serialized = json.dumps(new_wf)
    assert set(_decls(new_wf, "ALLOW_HUBSPOT_RECORD_WRITES")) == {'"true"'}
    assert "const ALLOW_WEB_RESEARCH = true;" in serialized
    assert "const ALLOW_JUDGE_ESCALATION = true;" in serialized
    # Unrequested write-safety siblings stay untouched.
    assert set(_decls(new_wf, "ALLOW_HUBSPOT_CREATE")) == {'"false"'}
    assert set(_decls(new_wf, "TEST_RECORD_IDS")) == {'""'}


# --- (d) fail closed on drift — the headline test ---------------------------------------

def test_enable_baked_flags_raises_on_spacing_variant_the_exact_rewrite_cannot_match():
    # No spaces around `=` — the exact-literal replace step cannot match this, and the
    # fail-closed re-scan must catch it and refuse rather than silently leaving it
    # disabled while reporting a successful rewrite elsewhere in the same workflow.
    workflow = {
        "name": "wf-drift-spacing",
        "nodes": [{"name": "Node A", "parameters": {
            "jsCode": 'const ALLOW_HUBSPOT_RECORD_WRITES="false";\nconsole.log(1);'
        }}],
    }
    with pytest.raises(ValueError, match="ALLOW_HUBSPOT_RECORD_WRITES"):
        deploy.enable_baked_flags(workflow, ["ALLOW_HUBSPOT_RECORD_WRITES"])


def test_enable_baked_flags_raises_on_numeric_literal_variant():
    # A numeric literal instead of the expected quoted-string boolean — again unreachable
    # by the exact replace, and again must be caught by the re-scan rather than silently
    # ignored. Subject is ALLOW_HUBSPOT_RECORD_WRITES (still overlayable) rather than
    # ALLOW_WEB_RESEARCH, which this test used before quick-260730-fij — that flag left
    # _OVERLAY_FLAG_SPEC entirely, so using it here would raise the "not overlayable"
    # error before ever reaching this numeric-literal re-scan branch.
    workflow = {
        "name": "wf-drift-numeric",
        "nodes": [{"name": "Node A", "parameters": {
            "jsCode": "const ALLOW_HUBSPOT_RECORD_WRITES = 0;\nconsole.log(1);"
        }}],
    }
    with pytest.raises(ValueError, match="ALLOW_HUBSPOT_RECORD_WRITES"):
        deploy.enable_baked_flags(workflow, ["ALLOW_HUBSPOT_RECORD_WRITES"])


def test_enable_baked_flags_never_returns_a_workflow_with_a_surviving_disabled_declaration():
    # The negative case stated explicitly: whatever this function returns (or it raises),
    # it must never hand back a workflow with a disabled declaration for a requested flag.
    # This prevents the exact false-success this phase is designed against — a deploy
    # that reports success while shipping a disabled build.
    workflow = {
        "name": "wf-drift-mixed",
        "nodes": [
            {"name": "Node A", "parameters": {"jsCode": 'const ALLOW_HUBSPOT_RECORD_WRITES = "false";'}},
            {"name": "Node B", "parameters": {"jsCode": 'const ALLOW_HUBSPOT_RECORD_WRITES="false";'}},
        ],
    }
    try:
        new_wf, _ = deploy.enable_baked_flags(workflow, ["ALLOW_HUBSPOT_RECORD_WRITES"])
    except ValueError:
        return  # raising is the correct fail-closed outcome
    serialized = json.dumps(new_wf)
    assert 'const ALLOW_HUBSPOT_RECORD_WRITES = "false";' not in serialized
    assert 'ALLOW_HUBSPOT_RECORD_WRITES="false"' not in serialized


# --- (e) non-overlayable names rejected --------------------------------------------------
#
# Phase 16.7 deliberately MOVED the write-safety constants into the overlayable set so the
# write-path canary can arm one record without a rebuild; their guards (an allowlist is
# mandatory in the same request, values are charset-restricted) live in
# tests/test_deploy_write_safety_overlay.py. Cost caps, model names, and both research/
# judge kill switches (now armed `true` at build time) stay out of reach permanently —
# those are what this parametrization protects.

@pytest.mark.parametrize("bad_flag", [
    "MAX_WEB_RESEARCH_PER_RUN",
    "MAX_JUDGE_VALIDATIONS_PER_RUN",
    "ANTHROPIC_RESEARCH_MODEL",
    "ANTHROPIC_JUDGE_MODEL",
    "ALLOW_JUDGE_ESCALATION",
    "ALLOW_WEB_RESEARCH",
])
def test_enable_baked_flags_rejects_non_overlayable_names(bad_flag):
    wf = _load_enrichment_workflow()
    with pytest.raises(ValueError, match=re.escape(bad_flag)):
        deploy.enable_baked_flags(wf, [bad_flag])


@pytest.mark.parametrize("bad_flag", [
    "MAX_WEB_RESEARCH_PER_RUN",
    "MAX_JUDGE_VALIDATIONS_PER_RUN",
    "ANTHROPIC_RESEARCH_MODEL",
    "ANTHROPIC_JUDGE_MODEL",
    "ALLOW_JUDGE_ESCALATION",
    "ALLOW_WEB_RESEARCH",
])
def test_requested_overlay_flags_rejects_non_overlayable_names_from_env(monkeypatch, bad_flag):
    monkeypatch.setenv("ENABLE_BAKED_FLAGS", bad_flag)
    with pytest.raises(ValueError, match=re.escape(bad_flag)):
        deploy._requested_overlay_flags()


# --- (f) zero declarations is not a raise at the function level -------------------------

def test_enable_baked_flags_zero_declarations_returns_unchanged_not_a_raise():
    # A synthetic workflow with no declaration of the requested (still-overlayable) flag
    # at all — every committed Cloud workflow bakes all four write-safety constants today,
    # so a real artifact can no longer demonstrate this branch; a bare in-memory workflow
    # does the same job without relying on that happening to stay true.
    wf = {"name": "wf-no-flags", "nodes": [
        {"name": "Node A", "parameters": {"jsCode": "console.log(1);"}},
    ]}
    new_wf, counts = deploy.enable_baked_flags(wf, ["ALLOW_HUBSPOT_RECORD_WRITES"])
    assert counts == {"ALLOW_HUBSPOT_RECORD_WRITES": 0}
    assert new_wf == wf


# --- (g) deploy-set refusal --------------------------------------------------------------

def test_main_refuses_at_deploy_set_level_when_requested_flag_matches_zero_declarations(
    monkeypatch, capsys
):
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_N8N_DEPLOY", "true")
    # TEST_RECORD_IDS alone is not a write-enabling flag, so the allowlist-mandatory
    # fail-safe in _requested_overlay_flags() does not fire — this isolates the
    # zero-declarations refusal this test targets.
    monkeypatch.setenv("ENABLE_BAKED_FLAGS", "TEST_RECORD_IDS=201")
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
    assert "TEST_RECORD_IDS" in out


# --- (h) ambient env inertness — Criterion 2 as an executable statement -----------------

def test_ambient_env_names_have_zero_effect_on_the_captured_put_body(monkeypatch):
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_N8N_DEPLOY", "true")
    # The .env-style Python-lane names — ENABLE_BAKED_FLAGS deliberately unset.
    # Both formerly-overlayable flags now bake `true` unconditionally at build time
    # (ALLOW_JUDGE_ESCALATION: quick-260730-din; ALLOW_WEB_RESEARCH: quick-260730-fij)
    # and have no _OVERLAY_FLAG_SPEC entry — setting either ambient var to its OPPOSITE
    # value ("false") is what actually proves the ambient env is inert; setting it to the
    # default would coincide with the baked value and prove nothing.
    monkeypatch.setenv("ALLOW_WEB_RESEARCH", "false")
    monkeypatch.setenv("ALLOW_JUDGE_ESCALATION", "false")

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
    # Committed default is `true` for both, and the ambient env value ("false") had zero
    # effect on either.
    assert "const ALLOW_WEB_RESEARCH = true;" in serialized
    assert "const ALLOW_WEB_RESEARCH = false;" not in serialized
    assert "const ALLOW_JUDGE_ESCALATION = true;" in serialized
    assert "const ALLOW_JUDGE_ESCALATION = false;" not in serialized


# --- (i) research and judge both default on, through the real path -----------------------
# Both ALLOW_WEB_RESEARCH (quick-260730-fij) and ALLOW_JUDGE_ESCALATION (quick-260730-din)
# now default `true` at build time and are baked unconditionally with no overlay involved.

def test_research_and_judge_default_on_through_real_path_unset_enable_baked_flags(monkeypatch):
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
    assert "const ALLOW_WEB_RESEARCH = true;" in serialized
    assert "const ALLOW_JUDGE_ESCALATION = true;" in serialized


# --- (j) enabled through the real path ----------------------------------------------------

def test_enabled_through_real_path_and_bind_credentials_succeeds(monkeypatch):
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_N8N_DEPLOY", "true")
    monkeypatch.setenv("ENABLE_BAKED_FLAGS", "ALLOW_HUBSPOT_RECORD_WRITES,TEST_RECORD_IDS=201")

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
    assert set(_decls(body, "ALLOW_HUBSPOT_RECORD_WRITES")) == {'"true"'}
    assert set(_decls(body, "TEST_RECORD_IDS")) == {'"201"'}
    # ALLOW_WEB_RESEARCH / ALLOW_JUDGE_ESCALATION are baked `true` unconditionally — no
    # overlay needed.
    serialized = json.dumps(body)
    assert "const ALLOW_WEB_RESEARCH = true;" in serialized
    assert "const ALLOW_JUDGE_ESCALATION = true;" in serialized
    # bind_credentials() composes with the overlay as main() does (proving composition,
    # not just the individual pieces): every HubSpot-credentialed node in the captured
    # body is bound. BUG 23 (Phase 17.01): a bare `type == "n8n-nodes-base.hubspot"`
    # filter went vacuous the moment the contacts search/fetch nodes joined companies on
    # the httpRequest transport (BUG 10) — this is the "a guard that silently stops
    # applying" failure mode caught before it happened. Widen the filter instead of
    # deleting the assert, reusing the house helper
    # (tests/test_fetch_by_id_topology.py's _hubspot_bound_node_names) rather than
    # inventing a third variant.
    hubspot_nodes = [n for n in body["nodes"] if n["name"] in _hubspot_bound_node_names(body)]
    assert hubspot_nodes
    for node in hubspot_nodes:
        assert "credentials" in node


# --- (k) dry-run visibility ----------------------------------------------------------------

def test_dry_run_visibility_prints_rewrite_plan_and_makes_zero_http_calls(monkeypatch, capsys):
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setenv("ENABLE_BAKED_FLAGS", "ALLOW_HUBSPOT_RECORD_WRITES,TEST_RECORD_IDS=201")
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
    assert "ALLOW_HUBSPOT_RECORD_WRITES" in out
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
