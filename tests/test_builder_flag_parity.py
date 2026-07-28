# tests/test_builder_flag_parity.py
#
# Phase 16 Task 4 (infra) / Task 5 (this file — deferred, see 16-01-SUMMARY.md
# Deviations) — Criterion 5 parity guard. build_enrichment_local_live() (docker
# replica) and build_enrichment_cloud() (Cloud webhook) must reference an IDENTICAL
# 6-flag set and an IDENTICAL 6-secret set, sourced from ONE shared constant
# (CONFIG_FLAG_DEFAULTS / SECRET_ENV_NAMES) — a flag or secret added, dropped, or
# renamed in only one builder fails this test.
#
# The deferral: this test needs BOTH builders to actually reference the 6 flags in
# their BUILT output. Cloud only gains flag-consuming nodes once the companies branch
# is ported (Task 5) — writing this file in Task 4, before that port existed, would
# have failed Task 4's own <verify> step. Task 4 already built the shared single-source
# (CONFIG_FLAG_DEFAULTS/SECRET_ENV_NAMES) and the cloud-aware helper functions; Task 5
# wires them into the Cloud graph, which is what makes this test meaningful.
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_cloud_workflows import (  # noqa: E402
    CONFIG_FLAG_DEFAULTS,
    SECRET_ENV_NAMES,
    build_enrichment_cloud,
    build_enrichment_local_live,
)

EXPECTED_FLAGS = {
    "ALLOW_WEB_RESEARCH",
    "MAX_WEB_RESEARCH_PER_RUN",
    "ANTHROPIC_SONNET_MODEL",
    "WEB_RESEARCH_MAX_SEARCHES",
    "ALLOW_SONNET_ESCALATION",
    "MAX_SONNET_VALIDATIONS_PER_RUN",
}

EXPECTED_SECRETS = {
    "HUBSPOT_PRIVATE_APP_TOKEN",
    "LUSHA_API_KEY",
    "APOLLO_API_KEY",
    "ANTHROPIC_API_KEY",
    "ZOOMINFO_CLIENT_ID",
    "ZOOMINFO_CLIENT_SECRET",
}


def test_config_flag_defaults_is_exactly_the_six_flags():
    assert set(CONFIG_FLAG_DEFAULTS.keys()) == EXPECTED_FLAGS


def test_secret_env_names_is_exactly_the_six_secrets():
    assert set(SECRET_ENV_NAMES) == EXPECTED_SECRETS


def _all_jscode(workflow: dict) -> str:
    return "\n".join(
        n.get("parameters", {}).get("jsCode", "") for n in workflow["nodes"]
    )


def _all_credential_bound_node_names(workflow: dict) -> set:
    """Nodes carrying a genericCredentialType/predefinedCredentialType/native-HubSpot auth
    marker — Cloud's secret-binding mechanism (no header/body literal ever holds a secret
    value). predefinedCredentialType (BUG 10 / Phase 16.6: the 6 company-search nodes
    reusing the hubspotAppToken credential type via a generic httpRequest node) is the
    third credential-bearing mode alongside deploy_n8n_workflows.py's
    _CREDENTIAL_BEARING_HTTP_AUTH_MODES — must be recognized here too or this sweep
    silently stops covering those nodes."""
    bound = set()
    for n in workflow["nodes"]:
        params = n.get("parameters", {})
        if params.get("authentication") in ("genericCredentialType", "predefinedCredentialType"):
            bound.add(n["name"])
        elif n.get("type") == "n8n-nodes-base.hubspot":
            bound.add(n["name"])
    return bound


def test_local_live_references_all_six_flags_via_env_var_expressions():
    wf = build_enrichment_local_live()
    code = _all_jscode(wf)
    for flag in EXPECTED_FLAGS:
        assert f"$env.{flag}" in code or f"$vars.{flag}" in code, (
            f"build_enrichment_local_live() jsCode is missing a $vars/$env reference "
            f"to config flag {flag!r}"
        )


def test_cloud_references_all_six_flags_as_baked_literals():
    wf = build_enrichment_cloud()
    code = _all_jscode(wf)
    for flag in EXPECTED_FLAGS:
        assert f"const {flag} = " in code, (
            f"build_enrichment_cloud() jsCode is missing a baked `const {flag} = ...;` "
            "declaration (Criterion 5)."
        )
    # And zero runtime env-var lookup for any of them (belt-and-braces on top of
    # test_architecture_guard.py::test_no_env_or_vars_in_cloud_workflows, which checks
    # the SERIALIZED workflow file rather than the in-memory build).
    for flag in EXPECTED_FLAGS:
        assert f"$env.{flag}" not in code
        assert f"$vars.{flag}" not in code


def test_local_live_references_all_six_secrets_via_env_var_expressions():
    wf = build_enrichment_local_live()
    serialized = json.dumps(wf)
    for secret in EXPECTED_SECRETS:
        assert f"$env.{secret}" in serialized or f"$vars.{secret}" in serialized, (
            f"build_enrichment_local_live() is missing a $vars/$env reference to "
            f"secret {secret!r}"
        )


# Secret name -> the node(s) whose bound credential is expected to carry it (Cloud
# never references a secret env-var name directly — it is credential-bound instead).
SECRET_TO_CREDENTIAL_BOUND_NODES = {
    "HUBSPOT_PRIVATE_APP_TOKEN": {"HubSpot Search", "HubSpot Create", "HubSpot Update",
                                   "HubSpot Company Search", "HubSpot Company Create",
                                   "HubSpot Company Update"},
    "LUSHA_API_KEY": {"Lusha Enrich", "Lusha Company"},
    "APOLLO_API_KEY": {"Apollo Match", "Apollo Org"},
    "ANTHROPIC_API_KEY": {"Claude Web Research", "Judge Call",
                          "Contact Web Research", "Contact Judge Call"},
    "ZOOMINFO_CLIENT_ID": {"ZoomInfo Mint", "ZoomInfo Mint Company"},
    "ZOOMINFO_CLIENT_SECRET": {"ZoomInfo Mint", "ZoomInfo Mint Company"},
}


def test_cloud_references_all_six_secrets_via_credential_bound_nodes():
    wf = build_enrichment_cloud()
    bound = _all_credential_bound_node_names(wf)
    node_names = {n["name"] for n in wf["nodes"]}
    for secret, expected_nodes in SECRET_TO_CREDENTIAL_BOUND_NODES.items():
        present_nodes = expected_nodes & node_names
        assert present_nodes, f"none of the nodes credential-bound for {secret!r} exist: {expected_nodes}"
        assert present_nodes <= bound, (
            f"secret {secret!r}'s node(s) {present_nodes} are not credential-bound "
            f"(genericCredentialType / native HubSpot node) in build_enrichment_cloud()"
        )
    # And zero raw secret env-var name reference anywhere in the Cloud build.
    serialized = json.dumps(wf)
    for secret in EXPECTED_SECRETS:
        assert f"$env.{secret}" not in serialized
        assert f"$vars.{secret}" not in serialized


def test_every_generic_header_auth_http_node_hitting_anthropic_is_in_the_expected_set():
    """MEDIUM-5 reverse parity (Phase 16.2 Task 2): the forward assertion above only
    proves the EXPECTED anthropic nodes are credential-bound — it says nothing about an
    UNLISTED anthropic-calling HTTP node that also ended up credential-bound (harmless)
    or, worse, NOT bound (a silent 401). Assert every httpRequest node whose url targets
    api.anthropic.com is exactly the expected set — an unlisted node fails loudly here
    instead of deploying unbound."""
    wf = build_enrichment_cloud()
    anthropic_nodes = {
        n["name"] for n in wf["nodes"]
        if n.get("type") == "n8n-nodes-base.httpRequest"
        and "api.anthropic.com" in n.get("parameters", {}).get("url", "")
    }
    assert anthropic_nodes == SECRET_TO_CREDENTIAL_BOUND_NODES["ANTHROPIC_API_KEY"], (
        f"anthropic-calling HTTP nodes in the built workflow {anthropic_nodes} do not "
        f"exactly match the expected credential-bound set "
        f"{SECRET_TO_CREDENTIAL_BOUND_NODES['ANTHROPIC_API_KEY']} — an unlisted node "
        "would deploy unbound (401) or an expected node went missing"
    )
    bound = _all_credential_bound_node_names(wf)
    assert anthropic_nodes <= bound
