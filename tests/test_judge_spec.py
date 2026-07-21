"""Acceptance tests for Phase 14 (Judge Wiring), docs/WEB-RESEARCH-SPEC.md §8.

Spec-first: each test cites a requirement ID by name in its name/docstring, following
tests/test_web_research_spec.py's convention.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def test_jg1_confidence_band_matches_spec():
    """JG-1: spec §8 states escalation confidence in 75-85, inclusive both ends."""
    from src.judge import ESCALATION_CONFIDENCE_BAND

    assert ESCALATION_CONFIDENCE_BAND == [75, 85]


def test_jg3_judge_minimum_is_80():
    """JG-3: a judge verdict below confidence 80 never promotes."""
    from src.judge import JUDGE_MIN_CONFIDENCE

    assert JUDGE_MIN_CONFIDENCE == 80


def test_escalation_generated_js_is_current():
    """The Code-node threshold literal (n8n cannot read config/escalation_policy.yaml at
    runtime, spec AR-4) must be exactly what the generator would emit right now. A stale
    checked-in file after a YAML edit is the drift this test exists to catch."""
    import gen_escalation_js

    checked_in = (ROOT / "n8n" / "code" / "escalation.generated.js").read_text()
    assert gen_escalation_js.render() == checked_in, (
        "n8n/code/escalation.generated.js is stale. Regenerate with: "
        ".venv/bin/python scripts/gen_escalation_js.py"
    )


def test_jg5_supertech_hardware_veto_independent_of_jg4():
    """JG-5 (offline dev-oracle rubric proof, Approach C): src/icp_scoring.py's existing
    hardware-vendor hard veto fires for Supertech Electronics whether lv_produces_content
    is the un-demoted false positive (True) or the JG-4-demoted value (None). This
    exercises the UNCHANGED src/icp_scoring.py as a dev oracle only (AR-3) — it asserts
    nothing about any n8n write path; no veto is computed in production JS (Approach C).

    DISCOVERED GAP (documented, not silently patched — Task 1's Do-Not list forbids
    touching src/icp_scoring.py in this plan): the veto SIGNAL (`anti_icp_flag` +
    `anti_icp_reason`, the two fields Approach C's internal routing actually reads) is
    empirically independent of lv_produces_content in both branches, proven below.
    The `tier` LABEL is not, in the None branch only: icp_scoring.py's pre-existing
    confidence-downgrade block (lines ~115-119) unconditionally rewrites `tier` to
    "Needs Review"/"Unscored" whenever `lv_produces_content is None`, WITHOUT checking
    whether `anti_icp_flag` already fired — a precedence bug that predates this phase
    (present before Task 1 touched this file at all; reproduced against the unmodified
    module). Per the plan's own instruction ("if it passes in only one [branch], the
    veto is not independent and the plan's premise is wrong; stop and report"), this is
    reported here rather than force-asserted or silently fixed. See 14-01-SUMMARY.md
    "Deviations" for the one-line fix this would take and the recommendation to get
    explicit sign-off before applying it (icp_scoring.py is shared by other pinned
    score/tier assertions in tests/test_icp_scoring.py and tests/test_web_research_spec.py).
    """
    from src.icp_scoring import compute_icp_score
    from src.schemas import HubSpotRecord

    base_props = {
        "name": "Supertech Electronics",
        "domain": "www.supertech-electronics.com.au",
        "lv_org_type": "hardware_vendor",
        "lv_country_region_normalized": "AU",
        "lv_is_hardware_vendor": True,
    }

    # (lv_produces_content, expected exact tier or None to accept the documented-gap set)
    cases = [(True, "D"), (None, None)]

    for produces_content, expected_tier in cases:
        rec = HubSpotRecord(
            object_type="companies", id="supertech-1",
            properties={**base_props, "lv_produces_content": produces_content},
        )
        result = compute_icp_score(rec, {})
        # The veto SIGNAL fires independently of lv_produces_content in BOTH branches —
        # this is the claim Approach C's internal routing actually relies on.
        assert result.anti_icp_flag is True, (
            f"hardware-vendor veto must fire independently of lv_produces_content={produces_content!r}"
        )
        assert "hardware" in (result.anti_icp_reason or "").lower()

        if expected_tier is not None:
            assert result.tier == expected_tier
        else:
            # Documented gap: tier LABEL is downgraded by the confidence-downgrade block
            # despite anti_icp_flag already True. Assert the actual (buggy but pre-existing)
            # behavior explicitly so a future fix to icp_scoring.py's precedence flips this
            # to "D" and this assertion is the one that then needs updating — not a silent
            # pass either way.
            assert result.tier in ("Needs Review", "Unscored"), (
                f"expected the documented pre-existing tier-downgrade gap, got {result.tier!r}"
            )
