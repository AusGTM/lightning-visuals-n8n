"""Tests for `confidence.py` (Phase 61 Plan 04 Task 2, D-61-07).

Every decision-table row gets its own test — the table is meant to be legible on one
screen, and a row nobody exercises is a policy nobody can audit (REVIEW-A5). Plus the
determinism property (same inputs, same verdict, called twice) and the property that
every HELD verdict names a signal.
"""
import confidence
import preingest


def _outcome(tier="high", candidate_count=0, provider_agreement=None,
             material_conflicts=None, judge_adjudicated_fields=None, parseable=True):
    return preingest.Outcome(
        parseable=parseable,
        match_tier=tier,
        candidate_count=candidate_count,
        provider_agreement=provider_agreement,
        material_conflicts=material_conflicts,
        judge_adjudicated_fields=judge_adjudicated_fields,
    )


# =====================================================================================
# Row 0: unparseable
# =====================================================================================


def test_an_unparseable_outcome_is_held():
    outcome = preingest.UNPARSEABLE_OUTCOME
    verdict = confidence.assess(outcome)
    assert verdict.verdict == confidence.HELD
    assert verdict.hold_code == confidence.HOLD_UNPARSEABLE
    assert verdict.reason


def test_the_unparseable_hold_code_is_match_stage():
    assert confidence.HOLD_UNPARSEABLE not in confidence.ENRICHMENT_STAGE_HOLD_CODES


# =====================================================================================
# Row 1: an unadjudicated material conflict holds regardless of tier
# =====================================================================================


def test_a_high_tier_match_with_an_unadjudicated_conflict_is_held_not_confident():
    outcome = _outcome(tier="high", material_conflicts=[
        {"group": "country", "fields": ["lv_country_region_normalized", "country"]},
    ])
    verdict = confidence.assess(outcome)
    assert verdict.verdict == confidence.HELD
    assert verdict.hold_code == confidence.HOLD_UNADJUDICATED_CONFLICT
    assert "country" in verdict.reason


def test_an_adjudicated_conflict_field_clears_the_hold_and_the_row_is_confident():
    """The ban is on an UNADJUDICATED conflict, not on the field itself — an
    adjudicated verdict on any member field resolves the whole group."""
    outcome = _outcome(
        tier="high",
        material_conflicts=[{"group": "country", "fields": ["country"]}],
        judge_adjudicated_fields={"country": 91},
    )
    verdict = confidence.assess(outcome)
    assert verdict.verdict == confidence.CONFIDENT


def test_the_unadjudicated_conflict_hold_code_is_enrichment_stage():
    assert confidence.HOLD_UNADJUDICATED_CONFLICT in confidence.ENRICHMENT_STAGE_HOLD_CODES


def test_only_one_hold_code_is_enrichment_stage():
    assert confidence.ENRICHMENT_STAGE_HOLD_CODES == {confidence.HOLD_UNADJUDICATED_CONFLICT}


# =====================================================================================
# Row 2: the ONLY confident row
# =====================================================================================


def test_a_high_tier_match_with_no_conflict_is_confident():
    verdict = confidence.assess(_outcome(tier="high"))
    assert verdict.verdict == confidence.CONFIDENT
    assert verdict.hold_code is None
    assert verdict.reason is None


# =====================================================================================
# Row 3: unknown tier
# =====================================================================================


def test_an_unknown_tier_is_never_confident():
    verdict = confidence.assess(_outcome(tier="unknown"))
    assert verdict.verdict == confidence.HELD
    assert verdict.hold_code == confidence.HOLD_UNKNOWN_TIER
    assert verdict.reason


# =====================================================================================
# Row 4: no match
# =====================================================================================


def test_a_none_tier_is_held():
    verdict = confidence.assess(_outcome(tier="none"))
    assert verdict.verdict == confidence.HELD
    assert verdict.hold_code == confidence.HOLD_NO_MATCH


# =====================================================================================
# Row 5: ambiguous medium-tier candidates
# =====================================================================================


def test_medium_tier_with_more_than_one_candidate_is_held_ambiguous():
    verdict = confidence.assess(_outcome(tier="medium", candidate_count=3))
    assert verdict.verdict == confidence.HELD
    assert verdict.hold_code == confidence.HOLD_AMBIGUOUS_CANDIDATES
    assert "3" in verdict.reason


# =====================================================================================
# Row 6: the terminal, total-table catch-all (REVIEW-A5)
# =====================================================================================


def test_medium_tier_with_exactly_one_candidate_falls_to_the_terminal_held_row():
    verdict = confidence.assess(_outcome(tier="medium", candidate_count=1))
    assert verdict.verdict == confidence.HELD
    assert verdict.hold_code == confidence.HOLD_NO_TABLE_ROW_MATCHED


def test_a_vocabulary_drifted_tier_falls_to_the_terminal_held_row_not_a_confident_default():
    """A fifth match tier this table has never seen must never default confident."""
    verdict = confidence.assess(_outcome(tier="some_future_tier_nobody_wrote_a_row_for"))
    assert verdict.verdict == confidence.HELD
    assert verdict.hold_code == confidence.HOLD_NO_TABLE_ROW_MATCHED


# =====================================================================================
# REVIEW-C8: agreedBy is corroboration, never a rescue, and never a hold on its own
# =====================================================================================


def test_provider_agreement_alone_never_promotes_an_otherwise_held_row_to_confident():
    verdict = confidence.assess(_outcome(tier="unknown", provider_agreement={"jobtitle": ["apollo", "lusha"]}))
    assert verdict.verdict == confidence.HELD


def test_provider_agreement_absent_is_not_by_itself_a_hold_on_an_otherwise_confident_row():
    """A row with no enrichment (provider_agreement is None) is judged on its match
    signals alone — absence of agreement is not disagreement."""
    verdict = confidence.assess(_outcome(tier="high", provider_agreement=None))
    assert verdict.verdict == confidence.CONFIDENT


def test_provider_agreement_present_but_empty_is_still_not_a_hold_on_a_confident_row():
    verdict = confidence.assess(_outcome(tier="high", provider_agreement={"jobtitle": []}))
    assert verdict.verdict == confidence.CONFIDENT


# =====================================================================================
# Determinism
# =====================================================================================


def test_the_same_outcome_produces_the_same_verdict_called_twice():
    outcome = _outcome(tier="medium", candidate_count=2)
    first = confidence.assess(outcome)
    second = confidence.assess(outcome)
    assert first == second


# =====================================================================================
# Every held verdict names a signal
# =====================================================================================


def test_every_held_verdict_produced_above_names_a_reason():
    tiers_and_extras = [
        {"tier": "unknown"},
        {"tier": "none"},
        {"tier": "medium", "candidate_count": 2},
        {"tier": "medium", "candidate_count": 1},
        {"tier": "high", "material_conflicts": [{"group": "g", "fields": ["f"]}]},
    ]
    for kwargs in tiers_and_extras:
        verdict = confidence.assess(_outcome(**kwargs))
        assert verdict.verdict == confidence.HELD
        assert verdict.reason, f"held verdict for {kwargs} names no reason"
        assert verdict.hold_code, f"held verdict for {kwargs} carries no hold_code"


def test_the_unparseable_outcome_also_names_a_reason():
    verdict = confidence.assess(preingest.UNPARSEABLE_OUTCOME)
    assert verdict.reason
    assert verdict.hold_code
