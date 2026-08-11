# tests/test_simulate_rubric_weights.py
#
# Phase 46 Plan 01, Task 2 (tracer, tdd) -- proves the simulation path end to end for
# one record: an in-memory proposed rubric scores correctly, config/icp_scoring.yaml on
# disk stays untouched, and the gambling-deduction guard added to
# src/icp_scoring.py::compute_icp_score neither raises nor double-counts. No network, no
# credentials, no fixtures directory -- every case below drives compute_icp_score /
# scripts/simulate_rubric_weights.py against literal property dicts and in-memory cfgs.
import copy

import yaml

from src.icp_scoring import compute_icp_score, load_yaml
from src.schemas import HubSpotRecord
from scripts.simulate_rubric_weights import (
    PROPOSED_OVERRIDES,
    RUBRIC_PATH,
    build_proposed_cfg,
    simulate_row,
)


def _record(props: dict) -> HubSpotRecord:
    return HubSpotRecord(object_type="companies", id="0", properties=props)


CURRENT_CFG = load_yaml(str(RUBRIC_PATH))


def test_proposed_overrides_carries_only_d01_this_task():
    """Task 2 populates only D-01 (individual_club_team -> 15). Plan 02 adds D-02/D-03 --
    this pins the wave-1 scope so a later addition is a deliberate, reviewed diff, not a
    silent scope creep."""
    assert PROPOSED_OVERRIDES == [
        ("base_score.org_type.individual_club_team", 15),
    ]


def test_build_proposed_cfg_never_writes_to_disk():
    """`config/icp_scoring.yaml` on disk stays byte-identical after building and using a
    proposed cfg -- the simulation's central invariant (RUBRIC-02)."""
    before = RUBRIC_PATH.read_bytes()
    proposed = build_proposed_cfg(CURRENT_CFG)
    assert proposed["base_score"]["org_type"]["individual_club_team"] == 15
    after = RUBRIC_PATH.read_bytes()
    assert before == after


def test_build_proposed_cfg_does_not_mutate_current_cfg():
    """build_proposed_cfg must deep-copy, never mutate its input -- a shared-reference
    bug here would make CURRENT_CFG silently carry the proposed weight too."""
    current_copy = copy.deepcopy(CURRENT_CFG)
    build_proposed_cfg(CURRENT_CFG)
    assert CURRENT_CFG == current_copy
    assert CURRENT_CFG["base_score"]["org_type"]["individual_club_team"] == 5


def test_au_club_scores_35_c_under_current_and_45_b_under_proposed():
    """The behavior this whole task exists to prove: one record, two rubrics, two
    different tiers -- club(5)+content(20)+AU(10)+1-5M(0)=35=C today,
    club(15)+content(20)+AU(10)+1-5M(0)=45=B under D-01."""
    props = {
        "lv_org_type": "individual_club_team",
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "1-5M",
    }
    proposed_cfg = build_proposed_cfg(CURRENT_CFG)

    row = simulate_row(props, CURRENT_CFG, proposed_cfg)

    assert row["oracle_current_score"] == 35
    assert row["oracle_current_tier"] == "C"
    assert row["oracle_proposed_score"] == 45
    assert row["oracle_proposed_tier"] == "B"


def test_simulate_row_carries_distinct_live_and_oracle_columns():
    """Three columns, not two -- the live HubSpot value, the oracle-under-current-config
    control, and the oracle-under-proposed-config effect must all be present and
    independently addressable."""
    props = {
        "lv_org_type": "individual_club_team",
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "1-5M",
        "lv_icp_fit_score": "35",
        "lv_icp_tier": "C",
    }
    proposed_cfg = build_proposed_cfg(CURRENT_CFG)

    row = simulate_row(props, CURRENT_CFG, proposed_cfg)

    assert row["live_score"] == "35"
    assert row["live_tier"] == "C"
    assert row["oracle_current_score"] == 35
    assert row["oracle_current_tier"] == "C"
    assert row["oracle_proposed_score"] == 45
    assert row["oracle_proposed_tier"] == "B"


def test_gambling_scores_without_raising_when_proposed_cfg_omits_the_key():
    """A proposed cfg with no graduated_deductions.gambling_operator key must not
    KeyError -- it contributes 0 and appends no breakdown entry."""
    proposed_cfg = copy.deepcopy(CURRENT_CFG)
    del proposed_cfg["graduated_deductions"]["gambling_operator"]

    r = compute_icp_score(
        _record({}),
        {
            "lv_org_type": "governing_body_league",
            "lv_produces_content": True,
            "lv_is_gambling_operator": True,
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "5-50M",
        },
        cfg=proposed_cfg,
    )

    assert r.score == 80  # 40 + 20 + 10 + 10 - 0 (no deduction contributed)
    assert r.breakdown["graduated_deductions"] == []


def test_gambling_still_deducts_20_under_current_cfg():
    """The same gambling record under the *current* cfg (key present, -20) still
    deducts 20 and still appends the breakdown entry -- the before/after contrast the
    proposed-cfg test above depends on."""
    r = compute_icp_score(
        _record({}),
        {
            "lv_org_type": "governing_body_league",
            "lv_produces_content": True,
            "lv_is_gambling_operator": True,
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "5-50M",
        },
        cfg=CURRENT_CFG,
    )

    assert r.score == 60  # 40 + 20 + 10 + 10 - 20
    assert {"signal": "gambling_operator", "points": -20} in r.breakdown["graduated_deductions"]


def test_blank_org_type_contributes_zero_under_both_rubrics():
    """A record with blank lv_org_type contributes 0 org-type points under both the
    current and the proposed rubric -- the proposed rubric only reweights
    individual_club_team, it does not touch the blank/unknown fallback."""
    props = {
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "5-50M",
    }
    proposed_cfg = build_proposed_cfg(CURRENT_CFG)

    current = compute_icp_score(_record({}), props, cfg=CURRENT_CFG)
    proposed = compute_icp_score(_record({}), props, cfg=proposed_cfg)

    def org_type_points(result):
        for c in result.breakdown["components"]:
            if c["signal"] == "org_type":
                return c["points"]
        raise AssertionError("no org_type component in breakdown")

    assert org_type_points(current) == 0
    assert org_type_points(proposed) == 0


def test_compute_icp_score_two_positional_args_still_works():
    """Backward compatibility: every existing two-positional-argument call site
    (tests/scoring_fixtures.py::expected_for, scripts/backfill_seed_company_scores.py)
    must keep working untouched -- cfg defaults to loading the on-disk rubric."""
    r = compute_icp_score(
        _record({}),
        {
            "lv_org_type": "governing_body_league",
            "lv_produces_content": True,
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "5-50M",
        },
    )
    assert r.score == 80
    assert r.tier == "A"
