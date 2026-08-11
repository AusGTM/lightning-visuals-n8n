# tests/test_simulate_rubric_weights.py
#
# Phase 46 Plan 01 (tracer, tdd) proved the simulation path end to end for one record.
# Plan 02 (this revision) grows it to the full RUBRIC-02 shape: PROPOSED_OVERRIDES carries
# all three decided levers (D-01/D-02/D-03), SCENARIOS adds club-weight sensitivity
# (10/15/20), build_simulation adds row-set selection/cross-check, D-10 flags, tier
# distributions, movement summary, and render_markdown. No network, no credentials, no
# fixtures directory for these cases -- every test below drives compute_icp_score /
# scripts/simulate_rubric_weights.py against literal property dicts, in-memory cfgs, and
# (for the row-set finding) the real committed 41-final-population.json cross-check file
# (a local, offline read -- no live call).
import copy
import inspect

import src.hubspot_client as hubspot_client
import scripts.simulate_rubric_weights as simulate_rubric_weights
from src.icp_scoring import compute_icp_score, load_yaml
from src.schemas import HubSpotRecord
from scripts.simulate_rubric_weights import (
    PROPOSED_OVERRIDES,
    RUBRIC_PATH,
    SCENARIOS,
    build_proposed_cfg,
    build_scenario_cfg,
    build_simulation,
    simulate_row,
)


def _record(props: dict) -> HubSpotRecord:
    return HubSpotRecord(object_type="companies", id="0", properties=props)


CURRENT_CFG = load_yaml(str(RUBRIC_PATH))

# Phase 46 Plan 04: config/icp_scoring.yaml now carries the POST-decision weights
# (individual_club_team=15, regulator=-20, graduated_deductions={}) -- CURRENT_CFG above
# reflects the on-disk file directly, so it is no longer a stand-in for "before this
# phase's weight change." The delta-comparison tests below need an explicit frozen
# snapshot of the PRE-Phase-46 rubric (individual_club_team=5, regulator=5,
# graduated_deductions={"gambling_operator": -20}) to keep exercising
# build_proposed_cfg's/build_scenario_cfg's delta-computation code path with the same
# arithmetic 46-RESEARCH.md verified by direct execution -- now anchored to an explicit
# historical baseline instead of implicitly relying on the on-disk file being pre-decision.
PRE_PHASE_46_CFG = copy.deepcopy(CURRENT_CFG)
PRE_PHASE_46_CFG["base_score"]["org_type"]["individual_club_team"] = 5
PRE_PHASE_46_CFG["base_score"]["org_type"]["regulator"] = 5
PRE_PHASE_46_CFG["graduated_deductions"]["gambling_operator"] = -20


# --- PROPOSED_OVERRIDES / SCENARIOS shape (Plan 02 grows Plan 01's one-lever scope) ---

def test_proposed_overrides_carries_all_three_levers():
    """Plan 02 grows PROPOSED_OVERRIDES from Plan 01's single D-01 entry to all three
    decided levers -- D-01 (club->15), D-02 (regulator->-20, a DIRECT base_score.org_type
    weight per 46-RESEARCH.md Open Question 5's live-executed finding, not a new
    graduated_deductions key), D-03 (gambling deduction key deleted outright)."""
    assert PROPOSED_OVERRIDES == [
        ("base_score.org_type.individual_club_team", 15),
        ("base_score.org_type.regulator", -20),
        ("graduated_deductions.gambling_operator", None),
    ]


def test_build_proposed_cfg_adds_no_new_graduated_deductions_key():
    """D-02's regulator deduction is a direct base_score.org_type value, not a new
    graduated_deductions key -- deleting gambling_operator must leave graduated_deductions
    empty, never a new key added in its place."""
    proposed = build_proposed_cfg(CURRENT_CFG)
    assert proposed["graduated_deductions"] == {}


def test_scenarios_differ_only_by_club_weight():
    """SCENARIOS defines exactly three scenarios whose only difference is the club weight
    (10 / 15 / 20)."""
    assert len(SCENARIOS) == 3
    assert sorted(s["club_weight"] for s in SCENARIOS) == [10, 15, 20]
    assert len({s["name"] for s in SCENARIOS}) == 3


def test_build_scenario_cfg_club_15_matches_build_proposed_cfg():
    """The primary scenario (club weight 15) is byte-identical to build_proposed_cfg's
    output -- a single source of truth for the primary weight set."""
    assert build_scenario_cfg(CURRENT_CFG, 15) == build_proposed_cfg(CURRENT_CFG)


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
    # Phase 46 Plan 04: config/icp_scoring.yaml now carries the landed D-01 weight (15),
    # not the pre-decision 5 -- CURRENT_CFG reads the on-disk file directly.
    assert CURRENT_CFG["base_score"]["org_type"]["individual_club_team"] == 15


# --- Per-weight arithmetic (D-01/D-02/D-03 worked examples, verified in 46-RESEARCH.md) ---

def test_au_club_scores_35_c_under_current_and_45_b_under_proposed():
    """club(5)+content(20)+AU(10)+1-5M(0)=35=C under the pre-Phase-46 baseline,
    club(15)+content(20)+AU(10)+1-5M(0)=45=B under D-01 (landed in config/icp_scoring.yaml
    by this phase -- PRE_PHASE_46_CFG stands in for "current" so this test keeps
    exercising the delta build_proposed_cfg computes, now that the on-disk file itself
    already carries the proposed values)."""
    props = {
        "lv_org_type": "individual_club_team",
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "1-5M",
    }
    proposed_cfg = build_proposed_cfg(PRE_PHASE_46_CFG)

    row = simulate_row(props, PRE_PHASE_46_CFG, proposed_cfg)

    assert row["oracle_current_score"] == 35
    assert row["oracle_current_tier"] == "C"
    assert row["oracle_proposed_score"] == 45
    assert row["oracle_proposed_tier"] == "B"


def test_regulator_moves_to_10_unscored_under_proposed():
    """D-02's own worked example: regulator(5)+content(20)+AU(10)=35=C under the
    pre-Phase-46 baseline, regulator(-20)+content(20)+AU(10)=10=Unscored under the
    proposed rubric (landed in config/icp_scoring.yaml by this phase)."""
    props = {
        "lv_org_type": "regulator",
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
    }
    proposed_cfg = build_proposed_cfg(PRE_PHASE_46_CFG)

    row = simulate_row(props, PRE_PHASE_46_CFG, proposed_cfg)

    assert row["oracle_current_score"] == 35
    assert row["oracle_current_tier"] == "C"
    assert row["oracle_proposed_score"] == 10
    assert row["oracle_proposed_tier"] == "Unscored"


def test_gambling_row_gains_20_under_proposed():
    """D-03's worked example: league(40)+content(20)+AU(10)+5-50M(10)-gambling(20)=60
    under the pre-Phase-46 baseline; with the deduction removed outright (landed in
    config/icp_scoring.yaml by this phase), the same inputs score 80."""
    props = {
        "lv_org_type": "governing_body_league",
        "lv_produces_content": True,
        "lv_is_gambling_operator": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "5-50M",
    }
    proposed_cfg = build_proposed_cfg(PRE_PHASE_46_CFG)

    row = simulate_row(props, PRE_PHASE_46_CFG, proposed_cfg)

    assert row["oracle_current_score"] == 60
    assert row["oracle_proposed_score"] == 80


def test_simulate_row_carries_distinct_live_and_oracle_columns():
    """Three columns, not two -- the live HubSpot value, the oracle-under-current-config
    control, and the oracle-under-proposed-config effect must all be present and
    independently addressable. Uses PRE_PHASE_46_CFG as the "current" input (see its
    module-level comment) so oracle_current still differs from oracle_proposed now that
    config/icp_scoring.yaml itself carries the landed weights."""
    props = {
        "lv_org_type": "individual_club_team",
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "1-5M",
        "lv_icp_fit_score": "35",
        "lv_icp_tier": "C",
    }
    proposed_cfg = build_proposed_cfg(PRE_PHASE_46_CFG)

    row = simulate_row(props, PRE_PHASE_46_CFG, proposed_cfg)

    assert row["live_score"] == "35"
    assert row["live_tier"] == "C"
    assert row["oracle_current_score"] == 35
    assert row["oracle_current_tier"] == "C"
    assert row["oracle_proposed_score"] == 45
    assert row["oracle_proposed_tier"] == "B"


def test_gambling_scores_without_raising_when_proposed_cfg_omits_the_key():
    """A cfg with no graduated_deductions.gambling_operator key must not KeyError -- it
    contributes 0 and appends no breakdown entry. Phase 46 Plan 04 (D-03) landed this
    exact no-key state in config/icp_scoring.yaml itself, so CURRENT_CFG already omits
    the key -- no del needed to construct the case this test exercises."""
    proposed_cfg = copy.deepcopy(CURRENT_CFG)

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


def test_gambling_still_deducts_20_under_pre_phase_46_cfg():
    """The same gambling record under the pre-Phase-46 baseline cfg (key present, -20)
    still deducts 20 and still appends the breakdown entry -- the before/after contrast
    the proposed-cfg test above depends on. Renamed from
    test_gambling_still_deducts_20_under_current_cfg: config/icp_scoring.yaml's real
    "current" no longer carries this key at all after D-03 landed (Phase 46 Plan 04) --
    PRE_PHASE_46_CFG is the explicit historical stand-in this test now needs."""
    r = compute_icp_score(
        _record({}),
        {
            "lv_org_type": "governing_body_league",
            "lv_produces_content": True,
            "lv_is_gambling_operator": True,
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "5-50M",
        },
        cfg=PRE_PHASE_46_CFG,
    )

    assert r.score == 60  # 40 + 20 + 10 + 10 - 20
    assert {"signal": "gambling_operator", "points": -20} in r.breakdown["graduated_deductions"]


def test_blank_org_type_contributes_zero_under_both_rubrics():
    """A record with blank lv_org_type contributes 0 org-type points under both the
    current and the proposed rubric -- the proposed rubric only reweights
    individual_club_team/regulator, it does not touch the blank/unknown fallback."""
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


# --- build_simulation: row set, D-10 flags, distributions, movement, false-green guard ---

def test_empty_row_set_yields_failure_verdict_and_nonzero_exit():
    payload, exit_code = build_simulation([], fetch_fn=lambda _id: {}, current_cfg=CURRENT_CFG)
    assert exit_code == 1
    assert "FAIL" in payload["verdict"]


def test_false_veto_row_keeps_live_and_oracle_columns_distinct():
    """The false-veto shape (D-10): HubSpot's live tier reads D off a stale blank-region
    veto write; the oracle (which carries the blank-region veto fix -- 46-RESEARCH.md)
    does not veto and computes a real tier. Both values must stay distinct and
    addressable, and the row must carry the false_veto flag."""
    props = {
        "lv_org_type": "individual_club_team",
        "lv_produces_content": True,
        "lv_country_region_normalized": "",
        "lv_icp_fit_score": "10",
        "lv_icp_tier": "D",
        "lv_anti_icp_flag": "true",
        "lv_anti_icp_reason": "Non-ANZ geography",
    }
    payload, exit_code = build_simulation(["1"], fetch_fn=lambda _id: props, current_cfg=CURRENT_CFG)

    assert exit_code == 0
    row = payload["rows"][0]
    assert row["live_tier"] == "D"
    assert row["oracle_current_tier"] != "D"
    assert "false_veto" in row["flags"]


def test_blank_org_type_row_is_flagged_in_build_simulation():
    props = {
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "5-50M",
    }
    payload, exit_code = build_simulation(["1"], fetch_fn=lambda _id: props, current_cfg=CURRENT_CFG)

    assert exit_code == 0
    row = payload["rows"][0]
    assert "blank_org_type" in row["flags"]
    # unknown(0)+content(20)+AU(10)+5-50M(10) = 40 under both rubrics -- the proposed
    # rubric only reweights individual_club_team/regulator/gambling.
    assert row["oracle_current_score"] == 40
    assert row["oracle_proposed_score"] == 40


def test_row_set_divergence_finding_populated_against_cross_check():
    """Uses the real committed 41-final-population.json (66 ids) as the cross-check --
    an offline, local read, no live call. A stub row set of unrelated ids must produce a
    non-empty, non-silent divergence finding."""
    payload, exit_code = build_simulation(
        ["1001", "1002", "1003"],
        fetch_fn=lambda _id: {
            "lv_org_type": "individual_club_team",
            "lv_produces_content": True,
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "1-5M",
        },
        current_cfg=CURRENT_CFG,
    )

    assert exit_code == 0
    finding = payload["row_set_finding"]
    assert finding["live_count"] == 3
    assert finding["cross_check_count"] == 66
    assert finding["matches_exactly"] is False
    assert finding["symmetric_difference_count"] == 69
    assert set(finding["only_in_live"]) == {"1001", "1002", "1003"}


def test_movement_summary_counts_tier_changes_by_org_type():
    # current_cfg=PRE_PHASE_46_CFG (not CURRENT_CFG): config/icp_scoring.yaml already
    # carries the landed D-01 weight, so passing the real on-disk cfg here would make
    # oracle_current and oracle_proposed identical for the club row and this test could
    # no longer observe a movement. PRE_PHASE_46_CFG is the explicit historical baseline
    # that keeps exercising the "moves C -> B" case this test is named for.
    props_by_id = {
        "1": {  # club: moves C -> B
            "lv_org_type": "individual_club_team",
            "lv_produces_content": True,
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "1-5M",
        },
        "2": {  # league: unaffected by any of the three levers
            "lv_org_type": "governing_body_league",
            "lv_produces_content": True,
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "5-50M",
        },
    }
    payload, exit_code = build_simulation(
        ["1", "2"], fetch_fn=lambda cid: props_by_id[cid], current_cfg=PRE_PHASE_46_CFG,
    )

    assert exit_code == 0
    movement = payload["movement_summary"]
    assert movement["total_rows"] == 2
    assert movement["changed_tier_count"] == 1
    assert movement["unchanged_tier_count"] == 1
    assert movement["by_org_type"]["individual_club_team"] == {"changed": 1, "unchanged": 0}
    assert movement["by_org_type"]["governing_body_league"] == {"changed": 0, "unchanged": 1}


def test_sensitivity_tiers_present_for_10_and_20_not_15():
    props = {
        "lv_org_type": "individual_club_team",
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "1-5M",
    }
    payload, exit_code = build_simulation(["1"], fetch_fn=lambda _id: props, current_cfg=CURRENT_CFG)

    assert exit_code == 0
    row = payload["rows"][0]
    assert set(row["sensitivity_tiers"].keys()) == {"club_10", "club_20"}
    # club(10)+content(20)+AU(10)+1-5M(0)=40=B; club(20)+...=50=B -- both cross the B
    # floor for this record; the sensitivity table exists precisely to show that margin.
    assert row["sensitivity_tiers"]["club_10"] == "B"
    assert row["sensitivity_tiers"]["club_20"] == "B"


def test_render_markdown_includes_portal_row_count_and_flags():
    props = {
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "5-50M",
    }
    payload, exit_code = build_simulation(["1"], fetch_fn=lambda _id: props, current_cfg=CURRENT_CFG)
    assert exit_code == 0

    md = simulate_rubric_weights.render_markdown(payload)

    assert simulate_rubric_weights.EXPECTED_PORTAL_ID in md
    assert "blank_org_type" in md
    assert "Rows simulated:** 1" in md
    assert "Sensitivity" in md


# --- Zero-write proof (Plan 01 Task 3) -- unchanged, preserved verbatim ---

def _write_capable_hubspot_client_names() -> list:
    """Enumerates src/hubspot_client.py's write-capable functions by introspection
    (every write function's signature takes a dry_run parameter; get_record and
    search_records do not) rather than hardcoding a guessed list -- self-updating if
    a future writer is added to that module."""
    names = []
    for name, obj in vars(hubspot_client).items():
        if inspect.isfunction(obj) and obj.__module__ == hubspot_client.__name__:
            if "dry_run" in inspect.signature(obj).parameters:
                names.append(name)
    return sorted(names)


def test_write_capable_names_enumerated_are_the_expected_four():
    """Sanity pin on the enumeration itself (Phase 46 Plan 01, Task 3) -- if
    src/hubspot_client.py's write surface ever changes shape, this fails loudly
    instead of the two zero-write tests below silently checking a stale/incomplete
    list."""
    assert _write_capable_hubspot_client_names() == [
        "batch_update_companies", "create_record", "delete_record", "patch_record",
    ]


def test_zero_write_static_scan_finds_no_write_import():
    """RUBRIC-02 / D-08 (Phase 46 Plan 01, Task 3) -- static half of the zero-write
    proof. Reads scripts/simulate_rubric_weights.py's own source text and asserts
    none of src/hubspot_client.py's write-capable function names (patch_record,
    create_record, delete_record, batch_update_companies) appears anywhere in it.
    This is the phase's single highest-value invariant (T-46-01): the simulation
    must never reach a HubSpot write endpoint. A docstring claim is not the
    deliverable -- this test goes red the instant a future edit reaches for a
    write."""
    source = inspect.getsource(simulate_rubric_weights)
    for name in _write_capable_hubspot_client_names():
        assert name not in source, (
            f"scripts/simulate_rubric_weights.py's source text contains the "
            f"write-capable name {name!r} -- RUBRIC-02/D-08 forbids this"
        )


def test_zero_write_namespace_scan_finds_no_write_binding():
    """RUBRIC-02 / D-08 (Phase 46 Plan 01, Task 3) -- the import-namespace half of
    the zero-write proof. Catches a wildcard or aliased import the text scan alone
    would miss: after import, none of src/hubspot_client.py's write-capable names
    is bound anywhere in scripts.simulate_rubric_weights's own module namespace."""
    bound_names = set(vars(simulate_rubric_weights).keys())
    offenders = bound_names & set(_write_capable_hubspot_client_names())
    assert not offenders, (
        f"scripts/simulate_rubric_weights.py's namespace binds write-capable "
        f"names {offenders} -- RUBRIC-02/D-08 forbids this"
    )


def test_zero_write_behavioural_stub_records_read_only_calls():
    """RUBRIC-02 / D-08 (Phase 46 Plan 01, Task 3) -- behavioural half of the
    zero-write proof. Drives the simulation's batch entry point (main()) with a
    fetch_fn stub that records every call, and asserts the run completes having
    performed reads only, with the stub invoked exactly once per requested id and
    no other outbound path exercised."""
    calls = []

    def fetch_stub(company_id):
        calls.append(company_id)
        return {
            "lv_org_type": "individual_club_team",
            "lv_produces_content": True,
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "1-5M",
        }

    ids = ["1001", "1002", "1003"]
    report, exit_code = simulate_rubric_weights.main(ids=ids, fetch_fn=fetch_stub)

    assert exit_code == 0
    assert calls == ids
    assert len(report["rows"]) == len(ids)


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
