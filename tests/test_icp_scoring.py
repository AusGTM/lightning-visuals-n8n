# tests/test_icp_scoring.py
#
# Runnable proof for Phase 2 (ICP scoring engine). Plain pytest, plain asserts.
# Every case drives compute_icp_score purely through candidate_patch on a
# companies record with empty properties. lv_country_region_normalized is always
# set explicitly so geography never falls back to the `country` property.
#
# Scope note: CLAUDE.md §24.1 cases 11-16 (provider org-type conflict -> Sonnet,
# content conflict -> Sonnet, missing evidence URL -> human review, manual domain
# -> stage only, existing phone -> stage only, blank phone + agreement -> promote)
# are NOT scoring behaviors — compute_icp_score has no provider-conflict, evidence,
# phone, or promote/stage logic. They belong to Phase 3's merge/escalation layer
# and will be covered by tests/test_merge_policy.py. The 16 cases below are the
# real scoring coverage (full veto set, full revenue-decay sweep, NZ geography,
# unknown-content, Unscored).
from src.schemas import HubSpotRecord
from src.icp_scoring import compute_icp_score


def score(patch):
    record = HubSpotRecord(object_type="companies", id="789", properties={})
    return compute_icp_score(record, patch)


def revenue_points(result):
    for c in result.breakdown["components"]:
        if c["signal"] == "revenue_band":
            return c["points"]
    raise AssertionError("no revenue_band component in breakdown")


def test_case_1_au_governing_body_tier_a():
    r = score({"lv_org_type": "governing_body_league", "lv_produces_content": True,
               "lv_country_region_normalized": "AU", "lv_revenue_band": "5-50M"})
    assert r.tier == "A"
    assert r.anti_icp_flag is False
    assert r.score == 80


def test_case_2_au_content_producer_tier_b():
    r = score({"lv_org_type": "content_producer", "lv_produces_content": True,
               "lv_country_region_normalized": "AU", "lv_revenue_band": "5-50M"})
    assert r.tier == "B"
    assert r.anti_icp_flag is False
    assert r.score == 60


def test_case_3_au_individual_club_tier_b():
    # Case 3 uses revenue 1-5M (a 0-point band), NOT mid-market. §24.1 case 3
    # does not pin a revenue band for the club (case 1 does). Phase 46 Plan 04 (D-01,
    # operator sign-off in 46-DECISION.md) moves individual_club_team from 5 to 15:
    # club(15)+content(20)+AU(10)+0-point-band(0)=45=Tier B. Renamed from
    # test_case_3_au_individual_club_tier_c (was 35/C under the pre-Phase-46 weight)
    # so the test's name doesn't lie about the tier it now produces.
    r = score({"lv_org_type": "individual_club_team", "lv_produces_content": True,
               "lv_country_region_normalized": "AU", "lv_revenue_band": "1-5M"})
    assert r.tier == "B"
    assert r.anti_icp_flag is False
    assert r.score == 45


def test_case_4_non_anz_veto():
    r = score({"lv_org_type": "governing_body_league", "lv_produces_content": True,
               "lv_country_region_normalized": "Other", "lv_revenue_band": "5-50M"})
    assert r.tier == "D"
    assert r.anti_icp_flag is True
    assert "Non-ANZ" in r.anti_icp_reason


def test_case_5_no_content_veto():
    r = score({"lv_org_type": "governing_body_league", "lv_produces_content": False,
               "lv_country_region_normalized": "AU", "lv_revenue_band": "5-50M"})
    assert r.tier == "D"
    assert r.anti_icp_flag is True
    assert "No broadcast or streaming content" in r.anti_icp_reason


def test_case_6_hardware_vendor_veto():
    r = score({"lv_org_type": "hardware_vendor", "lv_produces_content": True,
               "lv_is_hardware_vendor": True,
               "lv_country_region_normalized": "AU", "lv_revenue_band": "5-50M"})
    assert r.tier == "D"
    assert r.anti_icp_flag is True
    assert "Hardware/AV/LED vendor" in r.anti_icp_reason


def test_case_7_gambling_operator_deduction_not_veto():
    # Phase 46 Plan 04 (D-03, operator sign-off in 46-DECISION.md): the gambling
    # deduction is removed outright, not just re-valued -- a gambling-flagged record now
    # carries no graduated-deduction entry at all and scores the same as any other
    # non-gambling record with identical inputs: league(40)+content(20)+AU(10)+5-50M(10)=80.
    r = score({"lv_org_type": "governing_body_league", "lv_produces_content": True,
               "lv_is_gambling_operator": True,
               "lv_country_region_normalized": "AU", "lv_revenue_band": "5-50M"})
    assert r.anti_icp_flag is False
    assert r.score == 80
    assert r.breakdown["graduated_deductions"] == []


def test_case_8_revenue_500_750m_decay():
    r = score({"lv_org_type": "governing_body_league", "lv_produces_content": True,
               "lv_country_region_normalized": "AU", "lv_revenue_band": "500-750M"})
    assert r.anti_icp_flag is False
    assert r.score == 65
    assert revenue_points(r) == -5


def test_case_9_revenue_750m_1b_decay():
    r = score({"lv_org_type": "governing_body_league", "lv_produces_content": True,
               "lv_country_region_normalized": "AU", "lv_revenue_band": "750M-1B"})
    assert r.anti_icp_flag is False
    assert r.score == 55
    assert revenue_points(r) == -15


def test_case_10_revenue_1b_1_2b_decay():
    r = score({"lv_org_type": "governing_body_league", "lv_produces_content": True,
               "lv_country_region_normalized": "AU", "lv_revenue_band": "1B-1.2B"})
    assert r.anti_icp_flag is False
    assert r.score == 40
    assert revenue_points(r) == -30


def test_case_11_revenue_1_2b_plus_decay():
    r = score({"lv_org_type": "governing_body_league", "lv_produces_content": True,
               "lv_country_region_normalized": "AU", "lv_revenue_band": "1.2B+"})
    assert r.anti_icp_flag is False
    assert r.score == 20
    assert revenue_points(r) == -50


def test_case_12_unknown_org_needs_review():
    r = score({"lv_produces_content": True,
               "lv_country_region_normalized": "AU", "lv_revenue_band": "5-50M"})
    assert r.tier == "Needs Review"
    assert r.confidence == 55
    assert r.anti_icp_flag is False


def test_case_13_missing_content_needs_review():
    r = score({"lv_org_type": "governing_body_league",
               "lv_country_region_normalized": "AU", "lv_revenue_band": "5-50M"})
    assert r.tier == "Needs Review"
    assert r.confidence == 55
    assert r.anti_icp_flag is False


def test_case_14_unknown_org_low_score_unscored():
    r = score({"lv_produces_content": True,
               "lv_country_region_normalized": "AU", "lv_revenue_band": "1B-1.2B"})
    assert r.tier == "Unscored"
    assert r.confidence == 55
    assert r.score == 0


def test_case_15_nz_geography_tier_a():
    r = score({"lv_org_type": "governing_body_league", "lv_produces_content": True,
               "lv_country_region_normalized": "NZ", "lv_revenue_band": "5-50M"})
    assert r.tier == "A"
    assert r.anti_icp_flag is False
    assert r.score == 80


def test_case_16_version_stamp():
    r = score({"lv_org_type": "governing_body_league", "lv_produces_content": True,
               "lv_country_region_normalized": "AU", "lv_revenue_band": "5-50M"})
    assert r.scoring_version == "lv-icp-v0.1"
    assert r.breakdown["version"] == "lv-icp-v0.1"


def test_case_17_hard_veto_survives_confidence_downgrade():
    # Bug 1 (STATE.md "SCORING PRECEDENCE RULE", Phase 14 found-not-fixed): the
    # hardware-vendor veto fires (anti_icp_flag=True, tier="D") but org_type is
    # unknown, which ALSO trips the confidence-downgrade block. That block used to
    # overwrite tier/motion unconditionally, discarding the veto's own D/disqualify
    # label. A hard veto must win the label (CLAUDE.md 10.3); confidence still drops
    # to 55 because org_type really is unknown -- that uncertainty is real and stays
    # visible in the score breakdown even though it no longer changes the label.
    r = score({"lv_is_hardware_vendor": True, "lv_produces_content": True,
               "lv_country_region_normalized": "AU", "lv_revenue_band": "5-50M"})
    assert r.anti_icp_flag is True
    assert r.tier == "D"
    assert r.recommended_motion == "disqualify"
    assert r.confidence == 55


# --- 47.5-C: the hardware veto's OR trigger ---------------------------------------
# Decision 47.5-C-DECISION.md (or-retroactive): the veto fires on the boolean OR on
# lv_org_type == "hardware_vendor". Both paths are pinned here, not just the new one --
# a test covering only the org-type path would let the boolean path rot silently, and
# the boolean is the manual-override half of the reason the OR shape was chosen.
HARDWARE_REASON = "Hardware/AV/LED vendor, not sports-media buyer"

# (lv_is_hardware_vendor, lv_org_type, veto fires?)
HARDWARE_VETO_TABLE = [
    (True, "hardware_vendor", True),      # both triggers -- one reason, not two
    (True, "broadcaster", True),          # boolean alone: the manual-override path
    (None, "hardware_vendor", True),      # org type alone: Simtech LED's shape
    (False, "hardware_vendor", True),     # explicit false does NOT suppress the org type
    (None, "broadcaster", False),         # neither trigger
    (False, "broadcaster", False),
    (None, "unknown", False),
]


def test_hardware_veto_fires_on_either_trigger():
    for is_hw, org_type, expected in HARDWARE_VETO_TABLE:
        patch = {"lv_org_type": org_type, "lv_produces_content": True,
                 "lv_country_region_normalized": "AU", "lv_revenue_band": "5-50M"}
        if is_hw is not None:
            patch["lv_is_hardware_vendor"] = is_hw
        r = score(patch)
        assert r.anti_icp_flag is expected, f"{(is_hw, org_type)} -> flag {r.anti_icp_flag}"
        if expected:
            # Byte-identical reason, and exactly once even when both triggers hold.
            assert r.anti_icp_reason == HARDWARE_REASON, f"{(is_hw, org_type)}"
            assert r.breakdown["hard_vetoes"] == [HARDWARE_REASON]
            assert r.tier == "D"
        else:
            assert r.anti_icp_reason is None
            assert r.breakdown["hard_vetoes"] == []


def test_hardware_veto_keeps_third_position_in_the_join_via_the_org_type_trigger():
    # test_scoring_parity.py::test_veto_set_multiple_reasons_join pins this order live
    # off the BOOLEAN. The new trigger must land in the same slot, or the two engines'
    # joined reason strings diverge for an org-type-only hardware vendor.
    r = score({"lv_org_type": "hardware_vendor", "lv_produces_content": False,
               "lv_country_region_normalized": "US", "lv_revenue_band": "5-50M"})
    assert r.anti_icp_reason == "; ".join([
        "Non-ANZ geography",
        "No broadcast or streaming content",
        HARDWARE_REASON,
    ])
