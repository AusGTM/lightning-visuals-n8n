# tests/test_icp_named_account_floor.py
#
# Quick task 260823-ono -- offline proof for src/icp_scoring.py's core_racing floor.
# `lv_named_account_priority == "core_racing"` floors the score at 60 (no cap) for the
# five AU metro racing peak bodies (ATC, MRC, SSR, BRC, Perth Racing). Mirrors
# tests/test_icp_scoring.py's plain-assert style (score() helper on an empty-properties
# record, driven purely through candidate_patch).
from src.schemas import HubSpotRecord
from src.icp_scoring import compute_icp_score


def score(patch):
    record = HubSpotRecord(object_type="companies", id="789", properties={})
    return compute_icp_score(record, patch)


def named_account_component(result):
    for c in result.breakdown["components"]:
        if c["signal"] == "named_account_priority":
            return c
    return None


def test_base_35_floors_to_60_tier_b():
    # individual_club_team(15) + produces_content True(20) + no region signal(0, "unknown"
    # geography -- never region_key "non_anz", so this does NOT fire the non-ANZ veto) +
    # revenue "1-5M"(0) = 35 pre-floor -- below Tier B's 40 cutoff on its own.
    r = score({
        "lv_org_type": "individual_club_team", "lv_produces_content": True,
        "lv_revenue_band": "1-5M", "lv_named_account_priority": "core_racing",
    })
    assert r.score == 60
    assert r.tier == "B"
    assert r.anti_icp_flag is False
    comp = named_account_component(r)
    assert comp == {"signal": "named_account_priority", "value": "core_racing", "points": 25}


def test_earned_base_above_70_is_not_capped():
    # governing_body_league(40) + content(20) + AU(10) + revenue "5-50M"(10) = 80 -- already
    # well above the 60 floor. The floor must NOT clamp it down; it stays 80/A.
    r = score({
        "lv_org_type": "governing_body_league", "lv_produces_content": True,
        "lv_country_region_normalized": "AU", "lv_revenue_band": "5-50M",
        "lv_named_account_priority": "core_racing",
    })
    assert r.score == 80
    assert r.tier == "A"
    comp = named_account_component(r)
    # Delta is 0 (max(80, 60) == 80) but the breakdown entry is still present -- the
    # override must be visible whether or not it actually bit.
    assert comp == {"signal": "named_account_priority", "value": "core_racing", "points": 0}


def test_all_blank_inputs_floors_to_60_tier_b_not_needs_review():
    # Perth Racing's exact shape: no org_type, no produces_content, no region, no
    # revenue -- everything defaults (org_type "unknown" -> 0, content None -> 0,
    # region_key "unknown" -> 0, revenue "unknown" -> 0). Pre-floor score is 0. Without
    # the override guard this would hit the "unknown org_type" downgrade block and land
    # on "Unscored"/"Needs Review" instead of the floored tier.
    r = score({"lv_named_account_priority": "core_racing"})
    assert r.score == 60
    assert r.tier == "B"
    assert r.anti_icp_flag is False
    assert r.confidence == 55  # inputs really are missing -- that stays visible
    comp = named_account_component(r)
    assert comp == {"signal": "named_account_priority", "value": "core_racing", "points": 60}


def test_veto_fired_keeps_tier_d_even_with_a_floored_score():
    # hardware_vendor org type fires the hardware veto regardless of the named-account
    # override. The score is still floored (visible in the breakdown / .score), but tier
    # stays "D" -- a fired veto always wins the label, floor or not.
    r = score({
        "lv_org_type": "hardware_vendor", "lv_produces_content": True,
        "lv_country_region_normalized": "AU", "lv_revenue_band": "1-5M",
        "lv_named_account_priority": "core_racing",
    })
    assert r.score == 60  # hardware_vendor(0) + content(20) + AU(10) + 1-5M(0) = 30 -> 60
    assert r.tier == "D"
    assert r.anti_icp_flag is True
    assert "Hardware/AV/LED vendor" in r.anti_icp_reason


def test_record_without_the_enum_is_unaffected():
    # No lv_named_account_priority at all -- byte-identical to tests/test_icp_scoring.py's
    # test_case_1_au_governing_body_tier_a. The addition is purely additive.
    r = score({
        "lv_org_type": "governing_body_league", "lv_produces_content": True,
        "lv_country_region_normalized": "AU", "lv_revenue_band": "5-50M",
    })
    assert r.score == 80
    assert r.tier == "A"
    assert r.anti_icp_flag is False
    assert named_account_component(r) is None


def test_non_core_racing_enum_value_is_unaffected():
    # An enum value OTHER than "core_racing" has no scoring effect (CONTEXT.md: "Other
    # enum values: no scoring effect yet").
    r = score({
        "lv_org_type": "individual_club_team", "lv_produces_content": True,
        "lv_revenue_band": "1-5M", "lv_named_account_priority": "non_racing_best_fit",
    })
    assert r.score == 35
    assert named_account_component(r) is None
