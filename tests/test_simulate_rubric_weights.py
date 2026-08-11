# tests/test_simulate_rubric_weights.py
#
# Phase 46 Plan 01, Task 2 (tracer, tdd) -- proves the simulation path end to end for
# one record: an in-memory proposed rubric scores correctly, config/icp_scoring.yaml on
# disk stays untouched, and the gambling-deduction guard added to
# src/icp_scoring.py::compute_icp_score neither raises nor double-counts. No network, no
# credentials, no fixtures directory -- every case below drives compute_icp_score /
# scripts/simulate_rubric_weights.py against literal property dicts and in-memory cfgs.
import copy
import inspect

import yaml

import src.hubspot_client as hubspot_client
import scripts.simulate_rubric_weights as simulate_rubric_weights
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
