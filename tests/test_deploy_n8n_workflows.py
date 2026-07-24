# tests/test_deploy_n8n_workflows.py
#
# Phase 16 Task 1 — offline proof for scripts/deploy_n8n_workflows.py AND
# scripts/provision_n8n_credentials.py (both new scripts' tests live here, per plan).
# Fully deterministic: no network. Mirrors tests/test_sync_hubspot_properties.py's
# hermetic monkeypatch pattern.
#
# Phase 16.1 Plan 02 Task 3 (reviews C2/A5) extends this file with: the credit-node
# deploy-binding proof (NODE_CREDENTIAL_MAP additions from Task 1's single-item credit
# branch) and a deploy-never-calls-/activate guard.
import json
import re
from pathlib import Path

import pytest
import requests

import scripts.deploy_n8n_workflows as deploy
import scripts.provision_n8n_credentials as provision

ROOT = Path(__file__).resolve().parents[1]


def raise_http(*args, **kwargs):
    raise AssertionError("a live n8n request leaked past a guard/gate that should have refused")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    for var in ("N8N_URL", "N8N_API_KEY", "N8N_EXPECTED_URL", "ALLOW_N8N_DEPLOY", "DRY_RUN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(requests, "get", raise_http)
    monkeypatch.setattr(requests, "post", raise_http)
    monkeypatch.setattr(requests, "put", raise_http)


# --- compute_workflow_diff: pure function, no I/O ----------------------------------

def test_diff_create_vs_update_matched_by_name_not_internal_id():
    local = [{"name": "A", "id": "local-a-id", "nodes": []},
             {"name": "B", "id": "local-b-id", "nodes": []}]
    live = [{"id": "live-b-id", "name": "B"}]  # only B exists live, under a DIFFERENT id
    diff = deploy.compute_workflow_diff(local, live)
    assert [w["name"] for w in diff["create"]] == ["A"]
    assert len(diff["update"]) == 1
    assert diff["update"][0]["id"] == "live-b-id"
    assert diff["update"][0]["body"]["name"] == "B"


def test_diff_is_idempotent_when_everything_already_matches():
    local = [{"name": "A", "nodes": []}]
    live = [{"id": "x", "name": "A"}]
    diff = deploy.compute_workflow_diff(local, live)
    assert diff["create"] == []
    assert len(diff["update"]) == 1


# --- bind_credentials: pure function, fail-closed -----------------------------------

def test_bind_credentials_attaches_id_per_node_via_node_name_map():
    workflow = {"name": "wf", "nodes": [
        {"name": "Lusha Enrich", "type": "n8n-nodes-base.httpRequest"},
        {"name": "Apollo Match", "type": "n8n-nodes-base.httpRequest"},
        {"name": "Some Code Node", "type": "n8n-nodes-base.code"},
    ]}
    name_to_id = {"LV Lusha": "cred-lusha-1", "LV Apollo": "cred-apollo-1"}
    bound = deploy.bind_credentials(workflow, name_to_id)

    lusha = next(n for n in bound["nodes"] if n["name"] == "Lusha Enrich")
    assert lusha["credentials"] == {"httpHeaderAuth": {"id": "cred-lusha-1", "name": "LV Lusha"}}
    apollo = next(n for n in bound["nodes"] if n["name"] == "Apollo Match")
    assert apollo["credentials"] == {"httpHeaderAuth": {"id": "cred-apollo-1", "name": "LV Apollo"}}
    # Lusha/Apollo share the httpHeaderAuth TYPE but are disambiguated by node name into
    # two DIFFERENT credential ids — never collapsed to the same credential.
    assert lusha["credentials"] != apollo["credentials"]
    # Unmapped nodes (Code nodes, Webhook, Switch, ...) are left untouched.
    code = next(n for n in bound["nodes"] if n["name"] == "Some Code Node")
    assert "credentials" not in code
    # Pure function: the input workflow dict is not mutated.
    assert "credentials" not in workflow["nodes"][0]


def test_bind_credentials_fails_closed_on_unresolvable_credential_name():
    workflow = {"name": "wf", "nodes": [{"name": "Lusha Enrich", "type": "n8n-nodes-base.httpRequest"}]}
    with pytest.raises(ValueError, match="LV Lusha"):
        deploy.bind_credentials(workflow, name_to_id={})


# --- _instance_ok: no fail-open (review consensus #4) --------------------------------

def test_instance_ok_true_when_expected_url_matches(monkeypatch):
    monkeypatch.setenv("N8N_URL", "https://example.com/anything")
    monkeypatch.setenv("N8N_EXPECTED_URL", "https://example.com/anything")
    assert deploy._instance_ok() is True


def test_instance_ok_false_when_expected_url_mismatches(monkeypatch):
    monkeypatch.setenv("N8N_URL", "https://wrong.example.com")
    monkeypatch.setenv("N8N_EXPECTED_URL", "https://right.example.com")
    assert deploy._instance_ok() is False


def test_instance_ok_true_for_bare_n8n_cloud_host_when_expected_unset(monkeypatch):
    monkeypatch.setenv("N8N_URL", "https://my-instance.n8n.cloud")
    assert deploy._instance_ok() is True


def test_instance_ok_refuses_non_cloud_host_when_expected_unset_no_fail_open(monkeypatch):
    monkeypatch.setenv("N8N_URL", "https://not-n8n-cloud.example.com")
    assert deploy._instance_ok() is False


def test_instance_ok_refuses_when_n8n_url_entirely_unset(monkeypatch):
    monkeypatch.delenv("N8N_EXPECTED_URL", raising=False)
    assert deploy._instance_ok() is False


def test_main_refuses_with_zero_http_calls_on_bad_instance(monkeypatch, capsys):
    monkeypatch.setenv("N8N_URL", "https://not-n8n-cloud.example.com")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    rc = deploy.main()
    assert rc != 0
    assert "REFUSED" in capsys.readouterr().out


# --- no-creds skip path: never breaks the offline suite ------------------------------

def test_deploy_no_creds_skips_cleanly(capsys):
    rc = deploy.main()
    assert rc == 0
    assert "skipped (no n8n creds)" in capsys.readouterr().out


def test_provision_no_creds_skips_cleanly(capsys):
    rc = provision.main()
    assert rc == 0
    assert "skipped (no n8n creds)" in capsys.readouterr().out


# --- two-key write gate: DRY_RUN=false AND ALLOW_N8N_DEPLOY=true, nothing less -------

def test_dry_run_default_makes_zero_write_calls(monkeypatch, capsys):
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setattr(deploy, "_get_live_workflows", lambda: [])
    monkeypatch.setattr(deploy, "_load_local_workflows", lambda: [{"name": "A", "nodes": []}])
    rc = deploy.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "Workflows to create" in out


def test_one_key_only_still_refuses_write(monkeypatch, capsys):
    # DRY_RUN=false alone (ALLOW_N8N_DEPLOY unset/false) must NOT unlock writes.
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setattr(deploy, "_get_live_workflows", lambda: [])
    monkeypatch.setattr(deploy, "_load_local_workflows", lambda: [{"name": "A", "nodes": []}])
    create_calls = []
    monkeypatch.setattr(deploy, "_create_workflow_live",
                         lambda body: (create_calls.append(body), (201, None))[1])
    rc = deploy.main()
    assert rc == 0
    assert create_calls == []
    assert "DRY RUN" in capsys.readouterr().out


def test_both_keys_set_dispatches_create_and_update_matched_by_name(monkeypatch, capsys):
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_N8N_DEPLOY", "true")
    monkeypatch.setattr(deploy, "_get_live_workflows", lambda: [{"id": "live-b", "name": "B"}])
    monkeypatch.setattr(
        deploy, "_load_local_workflows",
        lambda: [{"name": "A", "nodes": []}, {"name": "B", "nodes": []}])
    monkeypatch.setattr(deploy, "_load_credential_id_map", lambda: {})

    create_calls, update_calls = [], []
    monkeypatch.setattr(deploy, "_create_workflow_live",
                         lambda body: (create_calls.append(body), (201, None))[1])
    monkeypatch.setattr(deploy, "_update_workflow_live",
                         lambda wid, body: (update_calls.append((wid, body)), (200, None))[1])

    rc = deploy.main()
    assert rc == 0
    assert [c["name"] for c in create_calls] == ["A"]
    assert [u[0] for u in update_calls] == ["live-b"]


def test_unresolvable_credential_fails_deploy_closed_not_unbound(monkeypatch, capsys):
    # A workflow that needs a credential the id-map doesn't have must fail the deploy,
    # not silently create an unbound node.
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_N8N_DEPLOY", "true")
    monkeypatch.setattr(deploy, "_get_live_workflows", lambda: [])
    monkeypatch.setattr(
        deploy, "_load_local_workflows",
        lambda: [{"name": "A", "nodes": [{"name": "Lusha Enrich",
                                           "type": "n8n-nodes-base.httpRequest"}]}])
    monkeypatch.setattr(deploy, "_load_credential_id_map", lambda: {})  # LV Lusha missing

    create_calls = []
    monkeypatch.setattr(deploy, "_create_workflow_live",
                         lambda body: (create_calls.append(body), (201, None))[1])

    rc = deploy.main()
    assert rc == 1
    assert create_calls == []  # never reaches the write call
    assert "PARTIAL FAILURE" in capsys.readouterr().out


# --- provision_n8n_credentials.py: create-if-missing, schema-checked, no secret prints -

def test_provision_dry_run_prints_would_create_without_writing(monkeypatch, capsys):
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setattr(provision, "_get_live_credentials", lambda: [])
    rc = provision.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "would create credential 'LV HubSpot'" in out


def test_provision_create_if_missing_never_updates_existing(monkeypatch):
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_N8N_DEPLOY", "true")
    monkeypatch.setattr(provision, "_get_live_credentials",
                         lambda: [{"name": "LV HubSpot", "id": "existing-id"}])

    create_calls = []
    monkeypatch.setattr(provision, "_create_credential_live",
                         lambda name, cred_type, data: (create_calls.append(name), 201)[1])

    manifest = [{"name": "LV HubSpot", "type": "hubspotAppToken",
                 "data_fn": lambda: {"accessToken": "unused"}}]
    id_map, failures = provision.provision(manifest, live_writes=True)

    assert create_calls == []  # never POSTed — already exists
    assert id_map == {"LV HubSpot": "existing-id"}
    assert failures == []


def test_provision_zoominfo_dry_run_is_skipped_not_a_failure(monkeypatch, capsys):
    # Dry-run (live_writes=False): nothing is created for ANY manifest entry, ZoomInfo
    # included — this is a skip, not a failure.
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setattr(provision, "_get_live_credentials", lambda: [])
    id_map, failures = provision.provision(provision.CREDENTIAL_MANIFEST, live_writes=False)
    assert "LV ZoomInfo" not in id_map
    assert failures == []


def test_provision_zoominfo_credential_type_resolved_by_task2_decision():
    # Task 2 decision (split-code-node): ZoomInfo is a generic Basic Auth credential,
    # never a native OAuth2 credential — the placeholder from Task 1 is filled.
    entry = next(e for e in provision.CREDENTIAL_MANIFEST if e["name"] == "LV ZoomInfo")
    assert entry["type"] == "httpBasicAuth"
    assert provision.ZOOMINFO_CREDENTIAL_TYPE == "httpBasicAuth"


def test_provision_zoominfo_data_shape_matches_basic_auth_schema(monkeypatch):
    # httpBasicAuth's schema is {user, password} — client_id maps to user, client_secret
    # to password (never client_id/client_secret keys, which httpBasicAuth doesn't have).
    monkeypatch.setenv("ZOOMINFO_CLIENT_ID", "fake-id")
    monkeypatch.setenv("ZOOMINFO_CLIENT_SECRET", "fake-secret")
    data = provision._zoominfo_data()
    assert set(data.keys()) == {"user", "password"}
    assert data["user"] == "fake-id"
    assert data["password"] == "fake-secret"


def test_provision_id_map_written_carries_only_names_and_ids(tmp_path):
    path = provision.write_credential_id_map({"LV Lusha": "cred-123"}, path=tmp_path / "map.json")
    written = json.loads(path.read_text())
    assert written == {"LV Lusha": "cred-123"}
    # No secret-shaped value anywhere in the written file.
    raw = path.read_text()
    assert "api_key" not in raw
    assert "sk-ant" not in raw


# --- no secret env var value is ever printed by either script ------------------------

_SECRET_ENV_NAMES = [
    "HUBSPOT_PRIVATE_APP_TOKEN", "LUSHA_API_KEY", "APOLLO_API_KEY", "ANTHROPIC_API_KEY",
    "ZOOMINFO_CLIENT_ID", "ZOOMINFO_CLIENT_SECRET", "N8N_API_KEY",
]


@pytest.mark.parametrize("module_path", [
    "scripts/deploy_n8n_workflows.py",
    "scripts/provision_n8n_credentials.py",
])
def test_neither_script_interpolates_a_secret_env_var_into_a_print(module_path):
    """Mentioning a secret env var's NAME in a print (e.g. "set N8N_API_KEY") is fine
    and expected (operator guidance). What must never happen is an f-string INTERPOLATING
    the resolved value — `f"...{os.getenv('X')}..."` or `f"...{os.environ['X']}..."`."""
    text = (deploy.ROOT / module_path).read_text()
    interpolation_re = re.compile(
        r"\{[^{}]*(?:getenv|environ)[^{}]*\}")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if "print(" not in line:
            continue
        for match in interpolation_re.findall(line):
            for name in _SECRET_ENV_NAMES:
                if name in match:
                    pytest.fail(
                        f"{module_path}:{lineno}: secret env var {name!r} is interpolated "
                        f"into a print() call: {line!r}")


def test_deploy_set_is_cloud_only_no_env_leak():
    """Deploy set must be EXACTLY the Cloud workflows (wf_*_cloud.json) — never the
    docker-replica fixtures (wf_enrichment_local*.json etc.) that legitimately keep
    $env/$vars (AR-4) and would import as broken/unbound nodes on n8n Cloud.
    Regression guard for the deploy_n8n_workflows.py glob (16-VERIFICATION follow-up)."""
    cloud_files = sorted(p.name for p in deploy.N8N_DIR.glob("wf_*_cloud.json"))
    all_files = sorted(p.name for p in deploy.N8N_DIR.glob("wf_*.json"))
    local_files = [f for f in all_files if f not in cloud_files]
    assert local_files, "expected some local (non-cloud) wf_*.json fixtures to exist"

    loaded = deploy._load_local_workflows()
    assert 0 < len(loaded) == len(cloud_files)

    for wf in loaded:
        text = json.dumps(wf)
        assert "$env." not in text and "$vars." not in text, (
            f"deploy set workflow {wf.get('name')!r} still references $env/$vars — "
            "would import unbound on n8n Cloud"
        )


# --- Phase 16.1 Plan 02 Task 3 (reviews C2) — credit-node deploy binding -----------------

CREDIT_NODE_EXPECTED_CREDENTIAL = {
    "Lusha Usage": "LV Lusha",
    "Apollo Usage": "LV Apollo",
    "ZoomInfo Usage Mint": "LV ZoomInfo",
}


def _load_built_enrichment_workflow():
    return json.loads((ROOT / "n8n" / "wf_enrichment_cloud.json").read_text())


def test_every_credit_node_is_registered_in_node_credential_map():
    """The three credit-check HTTP nodes from Plan 02 Task 1 must all be mapped — an
    unmapped credit node would deploy UNBOUND -> 401 -> credits:null forever, invisibly
    (reviews C2)."""
    for node_name in CREDIT_NODE_EXPECTED_CREDENTIAL:
        assert node_name in deploy.NODE_CREDENTIAL_MAP, (
            f"{node_name!r} is a credit-check HTTP node but has no NODE_CREDENTIAL_MAP "
            "entry — it would deploy unbound (reviews C2)"
        )


def test_bind_credentials_binds_every_credit_node_in_the_built_workflow_to_its_expected_credential():
    wf = _load_built_enrichment_workflow()
    node_names = {n["name"] for n in wf["nodes"]}
    for node_name in CREDIT_NODE_EXPECTED_CREDENTIAL:
        assert node_name in node_names, f"built workflow is missing credit node {node_name!r}"

    name_to_id = {"LV Lusha": "id-lusha", "LV Apollo": "id-apollo", "LV ZoomInfo": "id-zoominfo",
                  "LV HubSpot": "id-hubspot", "LV Anthropic": "id-anthropic",
                  "LV Enrichment Webhook": "id-webhook-secret"}
    bound = deploy.bind_credentials(wf, name_to_id)
    bound_by_name = {n["name"]: n for n in bound["nodes"]}

    for node_name, expected_cred_name in CREDIT_NODE_EXPECTED_CREDENTIAL.items():
        node = bound_by_name[node_name]
        assert "credentials" in node, f"{node_name!r} was not bound"
        cred_block = next(iter(node["credentials"].values()))
        assert cred_block["name"] == expected_cred_name
        assert cred_block["id"] == name_to_id[expected_cred_name]

    # ZoomInfo Usage (the secret-free Bearer-only GET) needs no binding at all.
    zoom_usage = bound_by_name["ZoomInfo Usage"]
    assert "credentials" not in zoom_usage


def test_an_unmapped_credit_node_would_fail_deploy_closed():
    """If a credit node's name were somehow removed from NODE_CREDENTIAL_MAP, bind
    would fail closed (never silently import unbound) — proven directly on
    bind_credentials, the same fail-closed contract as every other mapped node."""
    workflow = {"name": "wf", "nodes": [{"name": "Lusha Usage", "type": "n8n-nodes-base.httpRequest"}]}
    with pytest.raises(ValueError, match="LV Lusha"):
        deploy.bind_credentials(workflow, name_to_id={})  # LV Lusha missing from the id-map


# --- Phase 16.1 Plan 02 Task 3 (reviews A5/kimi LOW-1) — deploy never calls /activate -----

def test_deploy_never_posts_to_any_activate_endpoint(monkeypatch, capsys):
    """Functional guarantee behind SC-7's active:false marker: n8n's Public API ignores
    `active` on create, so the real guard is that deploy issues NO POST to
    `.../activate` for either workflow — proven by recording every POST call."""
    monkeypatch.setenv("N8N_URL", "https://foo.n8n.cloud")
    monkeypatch.setenv("N8N_API_KEY", "fake-key")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_N8N_DEPLOY", "true")
    monkeypatch.setattr(deploy, "_get_live_workflows", lambda: [])
    monkeypatch.setattr(
        deploy, "_load_local_workflows",
        lambda: [{"name": "LV Enrichment (Cloud template)", "nodes": []},
                  {"name": "LV Scheduled Maintenance (Cloud)", "nodes": []}])
    monkeypatch.setattr(deploy, "_load_credential_id_map", lambda: {})

    post_calls = []
    monkeypatch.setattr(deploy, "_create_workflow_live",
                         lambda body: (post_calls.append(("create", body.get("name"))), (201, None))[1])

    rc = deploy.main()
    assert rc == 0
    assert post_calls == [("create", "LV Enrichment (Cloud template)"),
                           ("create", "LV Scheduled Maintenance (Cloud)")]
    # No call site anywhere in this run ever targets an /activate URL.
    assert not any("activate" in str(call) for call in post_calls)


def test_deploy_has_no_activate_function_or_call_site():
    """Belt-and-braces static guard: the module defines no activate-named function and no
    call site references one — activation is a deliberate separate operator-runbook step,
    never performed by this script. (The docstring's own prose mentions "/activate" to
    document why — that's intentional and not what this guards against.)"""
    import ast
    tree = ast.parse((ROOT / "scripts" / "deploy_n8n_workflows.py").read_text())
    func_names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert not any("activate" in name.lower() for name in func_names)
    call_names = {
        n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
        for n in ast.walk(tree) if isinstance(n, ast.Call)
    }
    assert not any("activate" in name.lower() for name in call_names if name)
