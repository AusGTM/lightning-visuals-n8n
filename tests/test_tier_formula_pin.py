# tests/test_tier_formula_pin.py
#
# Phase 50 Plan 03, Task 1 (D-17 item 1) -- the guard that fails on a silent threshold or
# branch-order drift in `lv_icp_tier_derived`'s live `calculationFormula`. Same idiom as
# tests/test_rubric_change_guard.py (module docstring, ROOT/*_PATH constants, a PINNED_*
# literal, a `_diff_*` key-by-key helper, one `assert_*_pinned` comparison helper exercised
# by both the passing test and every mutation case, and the three-test shape).
#
# This baseline is re-baselined ONLY by an explicit, reviewed act: re-running
# scripts/check_tier_derived_parity.py against the live population and refreshing
# .planning/phases/50-derived-tier-property/50-TIER-PARITY-EVIDENCE.md -- never by simply
# editing PINNED_TIER_LADDER / PINNED_VETO_GUARD to make this test pass. Re-baselining the
# literal without re-running that comparator is exactly the unaccompanied change this guard
# exists to block.
#
# Two independent things are pinned against config/icp_scoring.yaml's tier_rules:
#   1. The literal submitted at property-create time (config/hubspot_properties.yaml's
#      declaration), which is byte-identical to what 50-NULL-PROBE.json recorded.
#   2. The LIVE, server-canonicalized text HubSpot actually stores and echoes back
#      (config/hubspot_flows/lv_icp_tier_derived-property.after.json's calculationFormula --
#      50-01-SUMMARY.md's own disclosed finding: HubSpot rewrites `=` to `equals`, double
#      quotes to single quotes, and inserts line breaks after some branches on create). The
#      live text is NOT byte-identical to the submitted literal, so this pin compares by
#      PARSED MEANING (per-tier bounds, branch order, veto guard shape), not by string
#      equality -- pinning byte-identity against the live text would fail spuriously on a
#      functionally-correct property, which is exactly the trap 50-01 flagged for this task.
#
# Offline only: no network, no HubSpot credentials, no src.hubspot_client import.
import json
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
RUBRIC_PATH = ROOT / "config" / "icp_scoring.yaml"
PROPERTIES_PATH = ROOT / "config" / "hubspot_properties.yaml"
NULL_PROBE_PATH = ROOT / ".planning" / "phases" / "50-derived-tier-property" / "50-NULL-PROBE.json"
LIVE_SNAPSHOT_PATH = (
    ROOT / "config" / "hubspot_flows" / "lv_icp_tier_derived-property.after.json"
)
PARITY_SCRIPT = "scripts/check_tier_derived_parity.py"

# Pinned 2026-08-13 against config/icp_scoring.yaml's tier_rules (A: min_score 70, B: 40,
# C: 15) and the settled D-04 ladder (50-NULL-PROBE.json: settled_variant=coalesced_minus_one).
# D as the hard-veto branch precedes every score branch; Unscored is the terminal else. Exactly
# five labels per D-09 -- config/icp_scoring.yaml's `recommended_motion` map names a sixth,
# "Needs Review", which is deliberately NOT added here (PARITY-01 stays a documented accepted
# divergence); one mutation case below proves the guard rejects its introduction.
PINNED_TIER_LADDER = {
    "veto_tier": "D",
    "score_bounds": [("A", 70), ("B", 40), ("C", 15)],
    "else_tier": "Unscored",
}

# The veto guard's condition must compare numerically -- coalesce(lv_anti_icp_flag, 0) = 1 --
# never a bare boolean and never coalesce(..., false). Both are live-proven 400s: the spike
# (TIER-DERIVATION-SPIKE-2026-08-13.md Round 1) found HubSpot booleans arrive in formula-land
# as BigDecimal, so a bare `lv_anti_icp_flag` in a condition and a `false` coalesce fallback
# both reject at property-create time.
PINNED_VETO_GUARD = "coalesce(lv_anti_icp_flag, 0) = 1"


def load_rubric() -> dict:
    with RUBRIC_PATH.open() as f:
        return yaml.safe_load(f)


def load_declared_formula() -> str:
    """The literal submitted at create time (config/hubspot_properties.yaml's declaration
    for lv_icp_tier_derived) -- byte-identical to 50-NULL-PROBE.json's recorded literal,
    both being the PRE-canonicalization text."""
    with PROPERTIES_PATH.open() as f:
        doc = yaml.safe_load(f)
    for prop in doc["companies"]["properties"]:
        if prop["name"] == "lv_icp_tier_derived":
            return prop["calculationFormula"]
    raise AssertionError("lv_icp_tier_derived is not declared in config/hubspot_properties.yaml")


def load_null_probe_literal() -> str:
    doc = json.loads(NULL_PROBE_PATH.read_text())
    return doc["calculation_formula"]


def load_live_formula() -> str:
    """The server-canonicalized text HubSpot actually stores and echoes back on GET --
    the one that governs what the live property really does. NOT byte-identical to
    load_declared_formula(); compared by parsed meaning only (see module docstring)."""
    doc = json.loads(LIVE_SNAPSHOT_PATH.read_text())
    return doc["calculationFormula"]


def _normalize_formula(text: str) -> str:
    """Collapses HubSpot's inserted line breaks/whitespace runs to single spaces and
    normalizes quote style ('/") and the "="/"equals" spelling, so the live-canonicalized
    text and the submitted literal compare on meaning, not on incidental serialization
    choices HubSpot itself introduces (50-01-SUMMARY.md's disclosed canonicalization
    finding)."""
    normalized = re.sub(r"\s+", " ", text.strip())
    normalized = normalized.replace("'", '"')
    normalized = re.sub(r"\bequals\b", "=", normalized)
    return normalized


_VETO_PREFIX_RE = re.compile(r'^if\s+(.+?)\s+then\s+"([^"]+)"')
_SCORE_BRANCH_RE = re.compile(r'elseif\s+(?:coalesce\(lv_icp_fit_score,\s*-?\d+\)|lv_icp_fit_score)\s*>=\s*(-?\d+)\s+then\s+"([^"]+)"')
_ELSE_RE = re.compile(r'else\s+"([^"]+)"\s*$')


def parse_formula(formula_text: str) -> dict:
    """Parses a calculation_equation ladder into {veto_tier, veto_guard, score_bounds
    (ordered list of (tier, min_score)), else_tier}. The veto branch is positional -- it
    MUST be the formula's opening `if` clause, which is exactly what "the veto branch
    precedes every score branch" means for a single if/elseif/else chain. A formula whose
    opening clause is not the anti-ICP guard (e.g. the veto demoted to a later elseif)
    fails to match here and raises, rather than silently parsing a demoted veto as valid.
    Raises ValueError naming which piece could not be found -- never returns a partial
    result."""
    normalized = _normalize_formula(formula_text)

    veto_match = _VETO_PREFIX_RE.match(normalized)
    if not veto_match:
        raise ValueError(
            f"formula does not open with a recognizable 'if <veto guard> then \"<tier>\"' "
            f"clause (veto branch must precede every score branch): {formula_text!r}"
        )

    score_bounds = [(tier, int(bound)) for bound, tier in _SCORE_BRANCH_RE.findall(normalized)]
    if not score_bounds:
        raise ValueError(f"formula has no recognizable score branches: {formula_text!r}")

    else_match = _ELSE_RE.search(normalized)
    if not else_match:
        raise ValueError(f"formula has no recognizable else branch: {formula_text!r}")

    return {
        "veto_tier": veto_match.group(2),
        "veto_guard": veto_match.group(1),
        "score_bounds": score_bounds,
        "else_tier": else_match.group(1),
    }


def _diff_ladder(pinned: dict, actual: dict) -> list:
    """Returns a sorted list of human-readable diff strings for every piece that differs
    between the pinned ladder and a parsed formula -- so the failure message can name
    exactly what moved without the next engineer re-reading the whole formula."""
    diffs = []

    if pinned["veto_tier"] != actual.get("veto_tier"):
        diffs.append(
            f"veto_tier: pinned={pinned['veto_tier']!r} actual={actual.get('veto_tier')!r}"
        )
    if pinned["else_tier"] != actual.get("else_tier"):
        diffs.append(
            f"else_tier: pinned={pinned['else_tier']!r} actual={actual.get('else_tier')!r}"
        )

    pinned_bounds = dict(pinned["score_bounds"])
    actual_bounds = dict(actual.get("score_bounds", []))
    for tier in sorted(set(pinned_bounds) | set(actual_bounds)):
        if pinned_bounds.get(tier) != actual_bounds.get(tier):
            diffs.append(
                f"score_bounds.{tier}: pinned={pinned_bounds.get(tier)!r} "
                f"actual={actual_bounds.get(tier)!r}"
            )

    pinned_order = [tier for tier, _ in pinned["score_bounds"]]
    actual_order = [tier for tier, _ in actual.get("score_bounds", [])]
    if pinned_order != actual_order and set(pinned_order) == set(actual_order):
        diffs.append(f"score branch order: pinned={pinned_order} actual={actual_order}")

    return sorted(diffs)


def assert_tier_formula_pinned(formula_text: str) -> None:
    """Raises AssertionError naming scripts/check_tier_derived_parity.py and the
    re-verification obligation if formula_text's ladder shape (veto branch position and
    label, score-tier lower bounds and order, else label) or veto guard shape differs from
    the pinned baseline. This is the single comparison helper both the passing tests and
    the mutation tests exercise -- so the guard's teeth are proven directly, not just its
    current pass/fail state against today's formula."""
    reverify_note = (
        f"Re-run {PARITY_SCRIPT} against the live population and refresh "
        "50-TIER-PARITY-EVIDENCE.md before changing this pin -- do not simply edit "
        "PINNED_TIER_LADDER / PINNED_VETO_GUARD to make this test pass."
    )

    try:
        actual = parse_formula(formula_text)
    except ValueError as exc:
        raise AssertionError(f"{exc}. {reverify_note}") from exc

    diffs = _diff_ladder(PINNED_TIER_LADDER, actual)
    if actual["veto_guard"] != PINNED_VETO_GUARD:
        diffs.append(
            f"veto_guard: pinned={PINNED_VETO_GUARD!r} actual={actual['veto_guard']!r}"
        )

    if diffs:
        raise AssertionError(
            f"lv_icp_tier_derived's calculationFormula has moved: {diffs}. {reverify_note}"
        )


# --- passing tests: prove the pin is accurate against today's live artifacts -------------

def test_pinned_ladder_matches_current_config():
    """The pinned ladder's per-tier lower bounds equal config/icp_scoring.yaml's tier_rules
    min_score values, key by key -- A at 70, B at 40, C at 15 -- and D/Unscored are the
    veto/else branches tier_rules itself declares (hard_veto / missing_required_inputs),
    which carry no min_score to compare."""
    rubric = load_rubric()
    tier_rules = rubric["tier_rules"]

    pinned_bounds = dict(PINNED_TIER_LADDER["score_bounds"])
    for tier in ("A", "B", "C"):
        assert pinned_bounds[tier] == tier_rules[tier]["min_score"], (
            f"tier {tier}: pinned min_score {pinned_bounds[tier]} != "
            f"config/icp_scoring.yaml's {tier_rules[tier]['min_score']}"
        )

    assert tier_rules["D"]["hard_veto"] is True
    assert tier_rules["Unscored"]["missing_required_inputs"] is True


def test_pinned_ladder_matches_declared_formula():
    """The declared calculationFormula in config/hubspot_properties.yaml is byte-identical
    to the literal 50-NULL-PROBE.json recorded (both are the pre-canonicalization text
    submitted at create time -- 50-01-SUMMARY.md confirmed this identity independently),
    and it parses back to the pinned per-tier bounds."""
    declared = load_declared_formula()
    probe_literal = load_null_probe_literal()
    assert declared == probe_literal, (
        "config/hubspot_properties.yaml's declared calculationFormula no longer matches "
        "50-NULL-PROBE.json's recorded literal -- one of the two was edited without the "
        "other. Both must stay byte-identical: they are the same pre-creation text."
    )
    assert_tier_formula_pinned(declared)


def test_live_calculation_formula_matches_pinned_ladder():
    """The LIVE, server-canonicalized text (config/hubspot_flows/lv_icp_tier_derived-
    property.after.json) -- NOT byte-identical to the submitted literal, per 50-01's
    disclosed canonicalization finding -- still parses to the exact same per-tier bounds,
    branch order, and veto guard shape as the pinned ladder. This is the pin that actually
    matters: it is the live property's real, running formula, and the one D-07's parity
    gate is silently trusting."""
    assert_tier_formula_pinned(load_live_formula())


# --- mutation tests: prove the guard has teeth --------------------------------------------

def _mutate_bound(formula: str, old: str, new: str) -> str:
    assert formula.count(old) >= 1, f"fixture assumption broken: {old!r} not found in formula"
    return formula.replace(old, new)


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda f: _mutate_bound(f, ">= 70", ">= 65"), id="A_moved_to_65"),
        pytest.param(lambda f: _mutate_bound(f, ">= 40", ">= 45"), id="B_moved_to_45"),
        pytest.param(lambda f: _mutate_bound(f, ">= 15", ">= 20"), id="C_moved_to_20"),
        pytest.param(
            lambda f: f.replace('if coalesce(lv_anti_icp_flag, 0) = 1 then "D" ', ""),
            id="D_veto_branch_removed",
        ),
        pytest.param(
            lambda f: f.replace(' else "Unscored"', ""),
            id="Unscored_else_branch_removed",
        ),
        pytest.param(
            lambda f: f.replace(
                'elseif coalesce(lv_icp_fit_score, -1) >= 15 then "C" else "Unscored"',
                'elseif coalesce(lv_icp_fit_score, -1) >= 15 then "C" '
                'elseif coalesce(lv_icp_fit_score, -1) >= 5 then "E" else "Unscored"',
            ),
            id="sixth_label_introduced",
        ),
        pytest.param(
            # Veto demoted below the score branches: the formula's opening `if` clause
            # becomes a score branch instead, and the veto guard reappears as a later
            # `elseif` -- no longer positionally first, which is exactly what "the veto
            # branch precedes every score branch" forbids.
            lambda f: (
                'if coalesce(lv_icp_fit_score, -1) >= 70 then "A" '
                'elseif coalesce(lv_anti_icp_flag, 0) = 1 then "D" '
                'elseif coalesce(lv_icp_fit_score, -1) >= 40 then "B" '
                'elseif coalesce(lv_icp_fit_score, -1) >= 15 then "C" else "Unscored"'
            ),
            id="veto_demoted_below_score_branches",
        ),
    ],
)
def test_mutated_ladder_fails_the_guard(mutate):
    formula = load_declared_formula()
    mutated = mutate(formula)
    with pytest.raises(AssertionError):
        assert_tier_formula_pinned(mutated)


@pytest.mark.parametrize(
    "guard_text",
    [
        # Bare boolean guard, no coalesce -- live-proven 400 (spike Round 1: HubSpot
        # booleans arrive in formula-land as BigDecimal, so a bare boolean reference in a
        # condition is rejected at property-create time).
        'if lv_anti_icp_flag = 1 then "D" '
        'elseif coalesce(lv_icp_fit_score, -1) >= 70 then "A" '
        'elseif coalesce(lv_icp_fit_score, -1) >= 40 then "B" '
        'elseif coalesce(lv_icp_fit_score, -1) >= 15 then "C" else "Unscored"',
        # coalesce(..., false) -- also live-proven 400 (coalesce's second argument must be
        # numeric, not a boolean literal).
        'if coalesce(lv_anti_icp_flag, false) = 1 then "D" '
        'elseif coalesce(lv_icp_fit_score, -1) >= 70 then "A" '
        'elseif coalesce(lv_icp_fit_score, -1) >= 40 then "B" '
        'elseif coalesce(lv_icp_fit_score, -1) >= 15 then "C" else "Unscored"',
    ],
    ids=["bare_boolean_guard", "coalesce_false_guard"],
)
def test_boolean_guard_shape_is_numeric(guard_text):
    """The pinned formula's veto guard compares numerically
    (coalesce(lv_anti_icp_flag, 0) = 1); a bare-boolean variant and a
    coalesce(..., false) variant each raise, because both are live-proven 400s
    (spike Round 1)."""
    with pytest.raises(AssertionError):
        assert_tier_formula_pinned(guard_text)


def test_sentinel_collision_is_behaviour_preserving():
    """Under the coalesced variant (D-04, the settled fallback), a genuine score of
    exactly -1 and a never-scored (null) company both derive "Unscored". This is a
    behaviour-preserving collision, not a new ambiguity: WF1's own action graph
    (4625147345, config/hubspot_flows/4625147345-wf1-set-icp-tier.after.json) has branches
    only for >=70 / 40-69 / 15-39 -- no branch below 15 -- so a genuine -1 score was
    already indistinguishable from a blank score under WF1 (neither ever matches a
    branch, so WF1 writes nothing for either). The coalesce(lv_icp_fit_score, -1)
    fallback therefore introduces no WF1-observable divergence between the two inputs;
    it only replaces the derived property's OWN blank result with the literal label
    "Unscored" for a never-scored company, which is D-04's disclosed ~646-record flip."""
    import sys as _sys

    _sys.path.insert(0, str(ROOT / "scripts"))
    from check_tier_null_propagation import derived_tier, real_formula_for  # noqa: E402

    assert derived_tier(-1, False) == "Unscored"
    coalesced = real_formula_for("coalesced_minus_one")
    assert coalesced.count("coalesce(lv_icp_fit_score, -1)") == 3, (
        "every bare lv_icp_fit_score reference in the shipped ladder must be wrapped in "
        "the -1 sentinel fallback, so a null score is coalesced to -1 before any "
        "comparison runs -- landing it on the exact same 'Unscored' branch as a genuine "
        "-1 score, rather than on a separate/undefined path."
    )


def test_failure_message_names_the_reverification_obligation():
    """A future refactor of assert_tier_formula_pinned's message text cannot silently
    drop the pointer to re-running scripts/check_tier_derived_parity.py -- asserted
    directly against the raised message, not by inspection of the source."""
    mutated = load_declared_formula().replace(">= 70", ">= 65")
    with pytest.raises(AssertionError) as excinfo:
        assert_tier_formula_pinned(mutated)
    message = str(excinfo.value)
    assert PARITY_SCRIPT in message
    assert "50-TIER-PARITY-EVIDENCE.md" in message
