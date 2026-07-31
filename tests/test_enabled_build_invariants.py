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

# quick-260730-din (ALLOW_JUDGE_ESCALATION) and quick-260730-fij (ALLOW_WEB_RESEARCH) each
# removed their flag from the overlayable set — both now bake `true` unconditionally in
# the committed build. The write-safety boolean family is the only surviving
# committed-disabled + overlayable flag, so it is what sections (2)/(3) below use to prove
# the enablement mechanism's OUTPUT stays safe. See test_committed_build_judge_escalation_
# is_always_true / test_committed_build_web_research_is_always_true for the arm-by-default
# guards; the committed-stays-disabled guard for the write-safety family itself lives in
# tests/test_deploy_write_safety_overlay.py::test_committed_build_carries_the_disabled_
# write_safety_literals (not duplicated here).
FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES",)

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


# --- (1a) the committed build ARMS web research by default (quick-260730-fij) -----------
# The inverse of the old "committed stays disabled" guard: this is the arm-by-default
# guarantee this task exists to deliver, and it has zero coverage without this test.

@pytest.mark.parametrize("wf_path", _built_cloud_workflow_paths(), ids=lambda p: p.name)
def test_committed_build_web_research_is_always_true(wf_path):
    text = wf_path.read_text()
    literals = _decl_literals(text, "ALLOW_WEB_RESEARCH")
    for literal in literals:
        assert literal == "true", (
            f"{wf_path.name} declares ALLOW_WEB_RESEARCH with literal {literal!r} — "
            "the committed build must always arm web research by default."
        )


def test_enrichment_workflow_declares_web_research_at_least_once():
    """Non-vacuity companion to the inverted test above."""
    text = ENRICHMENT_WF_PATH.read_text()
    literals = _decl_literals(text, "ALLOW_WEB_RESEARCH")
    assert literals, "wf_enrichment_cloud.json declares ALLOW_WEB_RESEARCH zero times — guard is vacuous"


# --- (1b) the committed build ARMS judge escalation by default (quick-260730-din) --------
# The inverse of (1): this is the arm-by-default guarantee the whole rename task exists
# to deliver, and it has zero coverage without this test.

@pytest.mark.parametrize("wf_path", _built_cloud_workflow_paths(), ids=lambda p: p.name)
def test_committed_build_judge_escalation_is_always_true(wf_path):
    text = wf_path.read_text()
    literals = _decl_literals(text, "ALLOW_JUDGE_ESCALATION")
    for literal in literals:
        assert literal == "true", (
            f"{wf_path.name} declares ALLOW_JUDGE_ESCALATION with literal {literal!r} — "
            "the committed build must always arm judge escalation by default."
        )


def test_enrichment_workflow_declares_judge_escalation_at_least_once():
    """Non-vacuity companion to the inverted test above."""
    text = ENRICHMENT_WF_PATH.read_text()
    literals = _decl_literals(text, "ALLOW_JUDGE_ESCALATION")
    assert literals, "wf_enrichment_cloud.json declares ALLOW_JUDGE_ESCALATION zero times — guard is vacuous"


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


# --- (3) the diff is exactly the one flag's declaration lines -----------------------------
# (quick-260730-fij: ALLOW_WEB_RESEARCH also left the overlayable set, so the write-safety
# family is now the only demonstration subject — ALLOW_HUBSPOT_RECORD_WRITES's 2
# declaration sites in wf_enrichment_cloud.json are the only lines that differ.)

def test_enabled_vs_committed_diff_touches_only_the_flag_lines():
    """The strongest single statement in this plan: serialize both builds with identical
    formatting, diff line-by-line, and assert every differing line is a declaration of
    the one overlayable flag. A cost cap, a model name, a node parameter or a position
    appearing here fails by construction — no enumeration of forbidden things required."""
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
        f"lines outside the flag's declarations differ between committed and enabled "
        f"builds: {offenders}"
    )


# --- (4) explicit write-safety and cost-cap assertions -------------------------------------

def test_enabled_build_unrequested_write_safety_siblings_are_unchanged():
    """The write-safety siblings NOT requested by FLAGS (ALLOW_HUBSPOT_CREATE and the
    allowlist pair) stay at their disabled literal — the independence property Task 1's
    mechanism tests prove directly, restated here against the artifact this file's own
    enable_baked_flags call produces."""
    committed_text = ENRICHMENT_WF_PATH.read_text()
    serialized = _enabled_enrichment_workflow_serialized()

    committed_literals = set(_decl_literals(committed_text, "ALLOW_HUBSPOT_CREATE"))
    enabled_literals = set(_decl_literals(serialized, "ALLOW_HUBSPOT_CREATE"))
    # Quoted-disabled literal (_write_safety_const wraps in json.dumps — a QUOTED
    # string, textually disjoint from the bare-boolean form _flag_const emits).
    assert committed_literals == {'\\"false\\"'}, (
        f"unexpected committed literal(s) for ALLOW_HUBSPOT_CREATE: {committed_literals}"
    )
    assert enabled_literals == committed_literals, (
        f"ALLOW_HUBSPOT_CREATE literal changed on the enabled build: "
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

    for name in ("MAX_WEB_RESEARCH_PER_RUN", "MAX_JUDGE_VALIDATIONS_PER_RUN"):
        committed_literals = _decl_literals(committed_text, name)
        enabled_literals = _decl_literals(serialized, name)
        assert committed_literals, f"{name} not found in committed build"
        assert enabled_literals == committed_literals, (
            f"{name} value changed on the enabled build: "
            f"committed={committed_literals} enabled={enabled_literals}"
        )
    # MAX_WEB_RESEARCH_PER_RUN stays pinned at "10" regardless of ALLOW_WEB_RESEARCH's
    # default flip (quick-260730-fij) — the pacing cap is untouched by this task.
    assert set(_decl_literals(committed_text, "MAX_WEB_RESEARCH_PER_RUN")) == {"10"}


# --- (5) parity with the builder -----------------------------------------------------------

def test_overlayable_flags_is_a_strict_subset_of_config_flag_defaults():
    """A test may import build_cloud_workflows freely; the deploy script may not
    (import-time codegen side effect into n8n/code/). If someone renames a flag in
    CONFIG_FLAG_DEFAULTS, tests/test_builder_flag_parity.py fails on the seven-name pin
    and this test fails on the subset check — the overlay cannot silently drift away
    from the thing it rewrites."""
    from scripts.build_cloud_workflows import WRITE_SAFETY_DEFAULTS, _write_safety_const

    assert deploy._OVERLAYABLE_FLAGS < set(CONFIG_FLAG_DEFAULTS) | set(WRITE_SAFETY_DEFAULTS)
    # This pin moved from FOUR names to five exactly once, on purpose (Phase 30 Plan 01).
    # Phase 23 D-16a deliberately REUSED ALLOW_HUBSPOT_CREATE rather than move it; review
    # writeback cannot do the same. Reusing ALLOW_HUBSPOT_RECORD_WRITES would collapse two
    # intentionally-separate authorities into one — Phase 28's arm/dispatch/disarm cycle
    # flips that flag, and nothing it arms may enable a review write (D-02) — and there is
    # no pre-existing second gate on the review path to reuse the way the contact lane
    # could reuse ALLOW_HUBSPOT_CREATE. So the review path gets its own overlayable
    # constant, ALLOW_HUBSPOT_REVIEW_WRITES (D-08e). A SIXTH name still fails here.
    assert deploy._OVERLAYABLE_FLAGS == {
        "ALLOW_HUBSPOT_RECORD_WRITES",
        "ALLOW_HUBSPOT_CREATE",
        "ALLOW_HUBSPOT_REVIEW_WRITES",
        "TEST_RECORD_IDS",
        "TEST_RECORD_DOMAINS",
    }
    # Cost caps, model names, and both research/judge kill switches (default-true,
    # quick-260730-fij / quick-260730-din) stay structurally out of reach — permanently
    # non-overlayable.
    assert not deploy._OVERLAYABLE_FLAGS & {
        "MAX_WEB_RESEARCH_PER_RUN", "MAX_JUDGE_VALIDATIONS_PER_RUN",
        "ANTHROPIC_RESEARCH_MODEL", "ANTHROPIC_JUDGE_MODEL", "ALLOW_JUDGE_ESCALATION",
        "ALLOW_WEB_RESEARCH",
    }
    # Each spec entry's disabled literal must be byte-identical to what the builder bakes —
    # otherwise the exact-literal rewrite silently matches nothing and the deploy refuses
    # (or worse, a future looser matcher rewrites the wrong declaration).
    for flag, (disabled_literal, _enabled, _takes_value) in deploy._OVERLAY_FLAG_SPEC.items():
        if flag in WRITE_SAFETY_DEFAULTS:
            assert _write_safety_const(flag) == f"const {flag} = {disabled_literal};"
        else:
            assert disabled_literal == "false"
