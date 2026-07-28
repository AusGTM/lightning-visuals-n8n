# tests/test_enabled_build_invariants.py
#
# Phase 16.5 Task 2 — the artifact invariants: the two ARTIFACTS the deploy-time overlay
# produces (the committed one and the in-flight enabled one) each satisfy the invariants
# that make it safe to deploy the second. Task 1 proved the mechanism (purity, exactness,
# fail-closed); this file proves what the mechanism's OUTPUT is provably safe.
import json
import re
import sys
from pathlib import Path

import pytest

import scripts.deploy_n8n_workflows as deploy
from tests.test_architecture_guard import _ENV_OR_VARS_RE

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_cloud_workflows import CONFIG_FLAG_DEFAULTS  # noqa: E402
N8N = ROOT / "n8n"
ENRICHMENT_WF_PATH = N8N / "wf_enrichment_cloud.json"

FLAGS = ("ALLOW_WEB_RESEARCH", "ALLOW_SONNET_ESCALATION")

# Secret env-var runtime-lookup forms this repo's builders use — the docker-replica
# ($env.NAME / $vars.NAME) reads. If any of these appear in the ENABLED build, a secret
# lookup expression has leaked into the Cloud artifact.
SECRET_ENV_NAMES = [
    "HUBSPOT_PRIVATE_APP_TOKEN",
    "LUSHA_API_KEY",
    "APOLLO_API_KEY",
    "ANTHROPIC_API_KEY",
    "ZOOMINFO_CLIENT_ID",
    "ZOOMINFO_CLIENT_SECRET",
]


def _built_cloud_workflow_paths():
    return sorted(N8N.glob("wf_*_cloud.json"))


def _decl_literals(text: str, flag: str) -> list:
    return re.findall(rf"const {re.escape(flag)} = ([^;]+);", text)


# --- (1) the committed build stays disabled (Criterion 1) ------------------------------

@pytest.mark.parametrize("wf_path", _built_cloud_workflow_paths(), ids=lambda p: p.name)
@pytest.mark.parametrize("flag", FLAGS)
def test_committed_build_flag_declarations_are_always_disabled(wf_path, flag):
    """What makes it impossible to commit an enabled build by accident, and the reason
    the enablement mechanism had to live at deploy time rather than in the repo. A
    workflow declaring the flag zero times passes vacuously — the companion
    non-vacuity test below is what keeps this guard from passing by declaring nothing."""
    text = wf_path.read_text()
    literals = _decl_literals(text, flag)
    for literal in literals:
        assert literal == "false", (
            f"{wf_path.name} declares {flag} with literal {literal!r} — the committed "
            "build must never carry an enabled research/escalation flag."
        )


def test_enrichment_workflow_declares_both_flags_at_least_once():
    """Non-vacuity: the parametrized guard above could otherwise pass by having every
    workflow declare neither flag. Pin that the one workflow that DOES declare them
    (wf_enrichment_cloud.json) actually does, so the guard is exercised for real."""
    text = ENRICHMENT_WF_PATH.read_text()
    for flag in FLAGS:
        literals = _decl_literals(text, flag)
        assert literals, f"wf_enrichment_cloud.json declares {flag} zero times — guard is vacuous"


# --- (2) Criterion 5 survives enablement -------------------------------------------------

def _enabled_enrichment_workflow_serialized() -> str:
    wf = json.loads(ENRICHMENT_WF_PATH.read_text())
    enabled_wf, counts = deploy.enable_baked_flags(wf, list(FLAGS))
    assert all(counts[flag] > 0 for flag in FLAGS), "enablement produced zero rewrites — cannot proceed"
    return json.dumps(enabled_wf)


def test_enabled_build_has_zero_env_or_vars_expressions():
    """Criterion 5 is a property of what RUNS, not of what is stored — the committed
    build is already guarded by test_architecture_guard.py; this asserts the same
    regex against the TRANSFORMED (deployed) artifact."""
    serialized = _enabled_enrichment_workflow_serialized()
    matches = _ENV_OR_VARS_RE.findall(serialized)
    assert not matches, f"enabled build contains {len(matches)} $env/$vars expression(s)"


def test_enabled_build_has_no_secret_lookup_form_for_any_secret_name():
    serialized = _enabled_enrichment_workflow_serialized()
    for secret in SECRET_ENV_NAMES:
        assert f"$env.{secret}" not in serialized
        assert f"$vars.{secret}" not in serialized


# --- (3) the diff is exactly the four flag lines ------------------------------------------

def test_enabled_vs_committed_diff_touches_only_the_four_flag_lines():
    """The strongest single statement in this plan: serialize both builds with identical
    formatting, diff line-by-line, and assert every differing line is a declaration of
    one of the two overlayable flags. A cost cap, a write-safety constant, a model name,
    a node parameter or a position appearing here fails by construction — no enumeration
    of forbidden things required."""
    committed_wf = json.loads(ENRICHMENT_WF_PATH.read_text())
    enabled_wf, counts = deploy.enable_baked_flags(committed_wf, list(FLAGS))
    assert all(counts[flag] > 0 for flag in FLAGS)

    committed_lines = json.dumps(committed_wf, indent=2, sort_keys=True).splitlines()
    enabled_lines = json.dumps(enabled_wf, indent=2, sort_keys=True).splitlines()
    assert len(committed_lines) == len(enabled_lines), (
        "enablement changed the line count — a structural change beyond a literal swap"
    )

    flag_decl_re = re.compile(r'"?const (' + "|".join(FLAGS) + r') = ')
    differing = [
        (a, b) for a, b in zip(committed_lines, enabled_lines) if a != b
    ]
    assert differing, "enabled build is byte-identical to committed — enablement did not run"
    offenders = [(a, b) for a, b in differing if not flag_decl_re.search(b)]
    assert not offenders, (
        f"lines outside the two flags' declarations differ between committed and enabled "
        f"builds: {offenders}"
    )


# --- (4) explicit write-safety and cost-cap assertions -------------------------------------

def test_enabled_build_write_safety_constants_are_unchanged():
    committed_text = ENRICHMENT_WF_PATH.read_text()
    serialized = _enabled_enrichment_workflow_serialized()

    for name in ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE"):
        committed_literals = set(_decl_literals(committed_text, name))
        enabled_literals = set(_decl_literals(serialized, name))
        # Quoted-disabled literal (_write_safety_const wraps in json.dumps — a QUOTED
        # string, textually disjoint from the bare-boolean form _flag_const emits).
        assert committed_literals == {'\\"false\\"'}, (
            f"unexpected committed literal(s) for {name}: {committed_literals}"
        )
        assert enabled_literals == committed_literals, (
            f"{name} literal changed on the enabled build: "
            f"committed={committed_literals} enabled={enabled_literals}"
        )

    for name in ("TEST_RECORD_DOMAINS", "TEST_RECORD_IDS"):
        committed_literals = set(_decl_literals(committed_text, name))
        enabled_literals = set(_decl_literals(serialized, name))
        assert enabled_literals == committed_literals, (
            f"{name} allowlist literal changed on the enabled build: "
            f"committed={committed_literals} enabled={enabled_literals}"
        )


def test_enabled_build_cost_caps_are_unchanged():
    committed_text = ENRICHMENT_WF_PATH.read_text()
    serialized = _enabled_enrichment_workflow_serialized()

    for name in ("MAX_WEB_RESEARCH_PER_RUN", "MAX_SONNET_VALIDATIONS_PER_RUN"):
        committed_literals = _decl_literals(committed_text, name)
        enabled_literals = _decl_literals(serialized, name)
        assert committed_literals, f"{name} not found in committed build"
        assert enabled_literals == committed_literals, (
            f"{name} value changed on the enabled build: "
            f"committed={committed_literals} enabled={enabled_literals}"
        )


# --- (5) parity with the builder -----------------------------------------------------------

def test_overlayable_flags_is_a_strict_subset_of_config_flag_defaults():
    """A test may import build_cloud_workflows freely; the deploy script may not
    (import-time codegen side effect into n8n/code/). If someone renames a flag in
    CONFIG_FLAG_DEFAULTS, tests/test_builder_flag_parity.py fails on the six-name pin
    and this test fails on the subset check — the overlay cannot silently drift away
    from the thing it rewrites."""
    assert deploy._OVERLAYABLE_FLAGS < set(CONFIG_FLAG_DEFAULTS.keys())
    assert deploy._OVERLAYABLE_FLAGS == {"ALLOW_WEB_RESEARCH", "ALLOW_SONNET_ESCALATION"}
