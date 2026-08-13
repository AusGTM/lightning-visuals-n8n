"""Conformance: config/taxonomy.yaml is the single source of truth.

Each test cites a requirement ID from docs/WEB-RESEARCH-SPEC.md §2. These are DRIFT
GUARDS — they fail when a vocabulary value is added in one place and not the others,
which is the failure mode that otherwise shows up as a silent 0 score (`.get(org_type, 0)`)
or a HubSpot 400 at the very end of the pipeline.
"""
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name):
    return yaml.safe_load((ROOT / "config" / name).read_text())


@pytest.fixture(scope="module")
def taxonomy():
    return _load("taxonomy.yaml")


@pytest.fixture(scope="module")
def scoring():
    return _load("icp_scoring.yaml")


@pytest.fixture(scope="module")
def field_policy():
    return _load("field_policy.yaml")


# --- TX-1 / TX-2: org_type <-> icp_scoring ----------------------------------
def test_tx2_org_type_sets_are_identical(taxonomy, scoring):
    """TX-2: taxonomy org_types == icp_scoring base_score.org_type keys."""
    tax = set(taxonomy["org_types"])
    score = set(scoring["base_score"]["org_type"])
    assert tax == score, (
        f"missing from icp_scoring: {sorted(tax - score)}; "
        f"missing from taxonomy: {sorted(score - tax)}"
    )


def test_tx1_scores_match(taxonomy, scoring):
    """TX-1: every org_type's score equals its icp_scoring points."""
    score_cfg = scoring["base_score"]["org_type"]
    mismatched = {
        k: (v["score"], score_cfg.get(k))
        for k, v in taxonomy["org_types"].items()
        if v["score"] != score_cfg.get(k)
    }
    assert not mismatched, f"taxonomy score != icp_scoring points: {mismatched}"


# --- TX-3: evidence gating ---------------------------------------------------
def test_tx3_evidence_gated_set_matches_field_policy(taxonomy, field_policy):
    """TX-3: require_evidence_url_for == org_types with requires_evidence: true."""
    expected = {k for k, v in taxonomy["org_types"].items() if v.get("requires_evidence")}
    actual = set(
        field_policy["companies"]["lv_org_type"].get("require_evidence_url_for", [])
    )
    assert expected == actual, (
        f"taxonomy requires evidence for {sorted(expected)}; "
        f"field_policy gates {sorted(actual)}"
    )


# --- TX-4: no hand-maintained duplicate in the JS ----------------------------
def test_tx4_mergecompanies_has_no_handmaintained_enum():
    """TX-4: mergeCompanies.js must not carry its own copy of the gated list.

    The taxonomy is inlined at build time. A literal list here drifts silently.
    """
    src = (ROOT / "n8n" / "code" / "mergeCompanies.js").read_text()
    # A generated block is fine; a hand-typed array of org_type values is not.
    hand_typed = re.search(
        r"require_evidence_url_for:\s*\[[^\]]*governing_body_league", src
    )
    assert not hand_typed, (
        "mergeCompanies.js contains a hand-maintained require_evidence_url_for list. "
        "Generate it from config/taxonomy.yaml at build time (spec TX-4)."
    )


# --- TX-4 companion: generated JS artifact currency --------------------------
def test_taxonomy_generated_js_currency():
    """The Code-node vocabulary literal (n8n cannot read config/taxonomy.yaml at
    runtime, spec AR-4) must be exactly what the generator would emit right now.
    A stale checked-in file after a taxonomy.yaml edit is the drift TX-4 exists to
    catch; this is what proves the generated artifact -- the one representation
    that can't self-verify at runtime -- is never silently out of date."""
    import gen_taxonomy_js

    checked_in = (ROOT / "n8n" / "code" / "taxonomy.generated.js").read_text()
    assert gen_taxonomy_js.render() == checked_in, (
        "n8n/code/taxonomy.generated.js is stale. Regenerate with: "
        ".venv/bin/python scripts/gen_taxonomy_js.py"
    )


# --- TX-10 companion: generated JS carries the same definitions -------------
def test_tx10_generated_js_carries_org_type_definitions():
    """TX-10 (2026-08-13, Phase 49 Plan 03): the n8n vocabulary module MUST carry the
    same ORG_TYPE_DEFINITIONS content the Python prompts already render, mirroring
    test_tx10_every_org_type_has_a_definition_and_both_prompts_render_them above on the
    generated-JS side -- closes the folded todo
    .planning/todos/pending/2026-08-13-n8n-research-prompt-lacks-org-type-definitions.md."""
    from src.taxonomy import ORG_TYPE_DEFINITIONS

    generated = (ROOT / "n8n" / "code" / "taxonomy.generated.js").read_text()
    assert "const ORG_TYPE_DEFINITIONS = " in generated
    assert "ORG_TYPE_DEFINITIONS," in generated  # exported
    for definition in ORG_TYPE_DEFINITIONS.values():
        assert definition in generated, (
            f"definition {definition!r} missing from n8n/code/taxonomy.generated.js"
        )


# --- TX-5: declared vetoes exist --------------------------------------------
def test_tx5_declared_hard_vetoes_exist(taxonomy, scoring):
    """TX-5: any org_type declaring hard_veto names a real icp_scoring veto."""
    vetoes = set(scoring["hard_vetoes"])
    for name, spec in taxonomy["org_types"].items():
        key = spec.get("hard_veto")
        if key is not None:
            assert key in vetoes, f"{name} declares hard_veto '{key}' not in icp_scoring"


# --- TX-6 / TX-7: content types + defaults ----------------------------------
def test_tx6_content_types_declare_tristate(taxonomy):
    """TX-6: implies_content is exactly True, False, or None."""
    for name, spec in taxonomy["content_types"].items():
        assert "implies_content" in spec, f"{name} missing implies_content"
        assert spec["implies_content"] in (True, False, None), (
            f"{name}.implies_content must be true/false/null, got "
            f"{spec['implies_content']!r}"
        )


@pytest.mark.parametrize("vocab", ["org_types", "content_types"])
def test_tx7_exactly_one_default(taxonomy, vocab):
    """TX-7: exactly one default per vocabulary."""
    defaults = [k for k, v in taxonomy[vocab].items() if v.get("is_default")]
    assert defaults == ["unknown"], f"{vocab} defaults: {defaults}, expected ['unknown']"


# --- TX-8 / TX-9: synonym hygiene -------------------------------------------
@pytest.mark.parametrize("vocab", ["org_types", "content_types"])
def test_tx8_synonyms_are_unique(taxonomy, vocab):
    """TX-8: no synonym maps to two different canonical values."""
    seen = {}
    clashes = []
    for canonical, spec in taxonomy[vocab].items():
        for syn in spec.get("synonyms") or []:
            if syn in seen:
                clashes.append((syn, seen[syn], canonical))
            seen[syn] = canonical
    assert not clashes, f"ambiguous synonyms in {vocab}: {clashes}"


# --- TX-10: org_type definitions reach both research prompts ---------------
def test_tx10_every_org_type_has_a_definition_and_both_prompts_render_them(taxonomy):
    """TX-10 (2026-08-13, Phase 48 Plan 07): every org_types entry MUST carry a non-empty
    `definition`, and both Python research prompts MUST render the rendered block
    verbatim -- a discriminator present in one prompt and absent from the other is a
    silent divergence (the Racing NSW misclassification's root cause; see
    docs/WEB-RESEARCH-SPEC.md's dated §2 amendment)."""
    from src.taxonomy import ORG_TYPE_DEFINITIONS, org_type_definitions_block
    from src.web_research import RACING_NSW_ORG_TYPE_SYSTEM, RESEARCH_SYSTEM

    assert set(ORG_TYPE_DEFINITIONS) == set(taxonomy["org_types"])
    assert all(v.strip() for v in ORG_TYPE_DEFINITIONS.values())

    block = org_type_definitions_block()
    assert block in RESEARCH_SYSTEM
    assert block in RACING_NSW_ORG_TYPE_SYSTEM

    assert "QRIC" in ORG_TYPE_DEFINITIONS["regulator"]
    assert "Racing NSW" in ORG_TYPE_DEFINITIONS["governing_body_league"]


@pytest.mark.parametrize("vocab", ["org_types", "content_types"])
def test_tx9_synonyms_never_shadow_canonical_keys(taxonomy, vocab):
    """TX-9: a synonym may not equal a canonical key of the same vocabulary."""
    keys = set(taxonomy[vocab])
    shadowed = [
        (canonical, syn)
        for canonical, spec in taxonomy[vocab].items()
        for syn in (spec.get("synonyms") or [])
        if syn in keys
    ]
    assert not shadowed, f"synonyms shadowing canonical keys in {vocab}: {shadowed}"


# --- guards on the spec's own invariants ------------------------------------
def test_tristate_veto_wiring_is_intact(scoring):
    """§7: the no_content veto must stay enabled, else the tri-state rule is moot."""
    assert scoring["hard_vetoes"]["no_content"]["enabled"] is True


def test_icp_scoring_distinguishes_false_from_none():
    """§7 / TS-1: `is False` vetoes; None must NOT reach the veto branch.

    Guards the exact line the tri-state rule depends on.
    """
    src = (ROOT / "src" / "icp_scoring.py").read_text()
    assert "if produces_content is False:" in src, (
        "icp_scoring must veto on `is False` (identity), never on falsiness — "
        "`if not produces_content` would veto None too and auto-disqualify every "
        "company with no content evidence (spec TS-1)."
    )
