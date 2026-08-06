# tests/test_scoring_parity.py
#
# Phase 40 Plan 02 (D-11/D-12/D-13, PARITY-01/PARITY-02) — the standing drift guard.
# Two tiers in one module:
#   1. Offline oracle-vs-rubric tier (below) — parametrized directly off
#      config/icp_scoring.yaml, asserted against src/icp_scoring.compute_icp_score.
#      Zero network. Green the moment this task lands.
#   2. Live tier (added in Task 2) — behind RUN_LIVE_PARITY, drives disposable
#      companies through the real HubSpot flow chain and asserts live state against the
#      same oracle. Every requirement in this phase (ENGINE-01..07, VETO-01..03) has a
#      named, selectable live test here; PARITY-02's F4/F7/F9/F10 scratch scenarios are
#      encoded as named regression cases with a collection-time completeness guard.
#
# Flagged assumption (recorded per this plan's <output> instruction): compute_icp_score
# downgrades tier to "Needs Review" when lv_org_type is unknown or lv_produces_content is
# null and no veto fired (src/icp_scoring.py lines 120-125). No HubSpot workflow in this
# phase models that branch, and no Phase 40 requirement asks for it — REQUIREMENTS.md
# lists the review-queue policy as an explicitly deferred future requirement. This harness
# therefore treats an oracle "Needs Review" result as an accepted, documented divergence
# from live HubSpot's A/B/C/D-only lv_icp_tier enum (PORTAL-FACTS.md confirms Unscored is
# the only non-letter value live today), not a parity failure to chase.
import copy
import os

import pytest
import yaml

from src import icp_scoring
from src.hubspot_client import patch_record
from src.icp_scoring import compute_icp_score
from src.normalizer import normalize_revenue_band
from src.schemas import HubSpotRecord
from tests.scoring_fixtures import (
    FIT_SCORE_PROPS,  # noqa: F401 -- re-exported for the live tier / script wrapper parity
    disposable_company,
    expected_for,  # noqa: F401 -- re-exported for the live tier
    fetch_for_parity,  # noqa: F401 -- re-exported for the live tier
    settle,
)

CFG = yaml.safe_load(open("config/icp_scoring.yaml"))

# D-11 / 40-RESEARCH.md A3: env-var skipif, not a registered pytest marker — this repo
# has no pytest config and every existing gated script (probe_scoring_recalc_latency.py,
# snapshot_hubspot_schema.py) already uses env-var gating, not markers.
live = pytest.mark.skipif(
    os.getenv("RUN_LIVE_PARITY") != "true",
    reason="opt-in: set RUN_LIVE_PARITY=true to hit the live HubSpot portal",
)

ORG_TYPE_POINTS = CFG["base_score"]["org_type"]
PRODUCES_CONTENT_POINTS = CFG["base_score"]["produces_content"]
REVENUE_BAND_POINTS = CFG["base_score"]["revenue_band"]
HARD_VETOES = CFG["hard_vetoes"]


def score(patch):
    """Same oracle-call shape as tests/test_icp_scoring.py (which stays pure-oracle,
    network-free — this module is a NEW file, not an edit to it)."""
    record = HubSpotRecord(object_type="companies", id="789", properties={})
    return compute_icp_score(record, patch)


def _component(result, signal):
    for c in result.breakdown["components"]:
        if c["signal"] == signal:
            return c
    raise AssertionError(f"no {signal!r} component in breakdown")


# --------------------------------------------------------------------------------------
# Offline tier — zero network, parametrized off config/icp_scoring.yaml (not a literal
# hand-copied table). Must be green the moment this task lands.
# --------------------------------------------------------------------------------------

def test_org_type_sweep_offline_matches_config():
    assert len(ORG_TYPE_POINTS) == 9


@pytest.mark.parametrize("org_type,points", sorted(ORG_TYPE_POINTS.items()))
def test_engine_06_org_type_sweep_offline(org_type, points):
    r = score({
        "lv_org_type": org_type,
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "5-50M",
    })
    assert _component(r, "org_type")["points"] == points


@pytest.mark.parametrize("value,expected_points", [
    (True, PRODUCES_CONTENT_POINTS[True]),
    (False, PRODUCES_CONTENT_POINTS[False]),
    (None, 0),
])
def test_produces_content_contributes_20_offline(value, expected_points):
    patch = {
        "lv_org_type": "governing_body_league",
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "5-50M",
    }
    if value is not None:
        patch["lv_produces_content"] = value
    r = score(patch)
    assert _component(r, "produces_content")["points"] == expected_points


@pytest.mark.parametrize("band,points", sorted(REVENUE_BAND_POINTS.items()))
def test_revenue_boundary_bands_offline(band, points):
    r = score({
        "lv_org_type": "governing_body_league",
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": band,
    })
    assert _component(r, "revenue_band")["points"] == points


def test_revenue_boundary_750000000_normalizes_to_750m_1b_offline():
    # ENGINE-04's exact boundary contract, asserted against src/normalizer.py: 750000000
    # normalizes to "750M-1B" (which scores -15), not "500-750M" (-5).
    band = normalize_revenue_band(750000000)
    assert band == "750M-1B"
    r = score({
        "lv_org_type": "governing_body_league",
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": band,
    })
    assert _component(r, "revenue_band")["points"] == -15


def test_gambling_deducts_20_without_veto_offline():
    r = score({
        "lv_org_type": "broadcaster",
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "5-50M",
        "lv_is_gambling_operator": True,
    })
    assert r.anti_icp_flag is False
    deduction = CFG["graduated_deductions"]["gambling_operator"]
    assert {"signal": "gambling_operator", "points": deduction} in r.breakdown["graduated_deductions"]


def test_tier_band_boundaries_offline(monkeypatch):
    """The tier cutoffs in src/icp_scoring.py (score>=70 A, >=40 B, >=15 C, else Unscored)
    are exercised directly, through compute_icp_score itself, at the boundary scores this
    plan's <behavior> block names: 70, 69, 40, 39, 15, 14, and a negative score. Real
    config/icp_scoring.yaml component values are all multiples of 5 (org {0,5,20,40},
    content {0,20}, geography {0,10}, revenue {0,10,-5,-15,-30,-50}), so several of the
    named boundaries (69, 39, 14) cannot be reached through any real input combination.
    A synthetic org_type point value is monkeypatched into a full copy of the real config
    so the code path under test is compute_icp_score's own cutoff branch, not a
    duplicated >= comparison living only in this test file."""
    base_cfg = yaml.safe_load(open("config/icp_scoring.yaml"))
    cases = [
        (70, "A"), (69, "B"), (40, "B"), (39, "C"), (15, "C"), (14, "Unscored"), (-5, "Unscored"),
    ]
    for target_score, expected_tier in cases:
        cfg = copy.deepcopy(base_cfg)
        # produces_content True (20) + AU geography (10) + revenue "<1M" (0) = 30 fixed
        # baseline, none of the three hard-veto inputs set -> anti_icp_flag stays False.
        cfg["base_score"]["org_type"]["_boundary_probe"] = target_score - 30
        monkeypatch.setattr(icp_scoring, "load_yaml", lambda _path, _cfg=cfg: _cfg)
        r = score({
            "lv_org_type": "_boundary_probe",
            "lv_produces_content": True,
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "<1M",
        })
        assert r.anti_icp_flag is False
        assert r.tier == expected_tier, (
            f"score={target_score} expected tier={expected_tier} got={r.tier}"
        )


def test_disposable_company_fixture_asserts_portal_before_creating(monkeypatch):
    """tests/scoring_fixtures.py's disposable_company() must refuse to create anything if
    HUBSPOT_PORTAL_ID doesn't match the expected portal — asserted offline via
    monkeypatch, no network call reachable from this test."""
    from tests import scoring_fixtures

    monkeypatch.delenv("HUBSPOT_PORTAL_ID", raising=False)
    with pytest.raises(AssertionError):
        with scoring_fixtures.disposable_company():
            pass  # pragma: no cover -- create_record must never be reached


# --------------------------------------------------------------------------------------
# Live tier — behind RUN_LIVE_PARITY only (D-13: no offline substitute for veto cases;
# every test here drives a real disposable company through the real HubSpot flow chain).
# These are expected to FAIL until their owning plan lands (40-03 veto cases, 40-04
# produces_content/gambling, 40-05 geography/revenue, 40-06 tier) — that is the intended
# state of this task, not a defect in it.
# --------------------------------------------------------------------------------------

@live
def test_engine_01_au_governing_body_scores_80_tier_a():
    with disposable_company() as company_id:
        patch_record("companies", company_id, {
            "lv_org_type": "governing_body_league",
            "lv_produces_content": "true",
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "50-500M",
        }, dry_run=False)
        settle(company_id, "lv_icp_tier")
        props = fetch_for_parity(company_id)
        assert props.get("lv_icp_fit_score") == "80"
        assert props.get("lv_icp_tier") == "A"


@live
def test_produces_content_contributes_20():
    with disposable_company() as company_id:
        patch_record("companies", company_id, {
            "lv_org_type": "broadcaster",
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "5-50M",
        }, dry_run=False)
        settle(company_id, "lv_icp_fit_score")
        without_content = fetch_for_parity(company_id)

        patch_record("companies", company_id, {"lv_produces_content": "true"}, dry_run=False)
        settle(company_id, "lv_icp_fit_score")
        with_content = fetch_for_parity(company_id)

        delta = (
            int(with_content.get("lv_icp_fit_score") or 0)
            - int(without_content.get("lv_icp_fit_score") or 0)
        )
        assert delta == 20
        assert with_content.get("produces_content_score") == "20"


@live
def test_engine_03_native_inputs_move_nothing():
    with disposable_company() as company_id:
        patch_record("companies", company_id, {
            "country": "Australia",
            "annualrevenue": "10000000",
        }, dry_run=False)
        settle(company_id, "geography_score")
        native_only = fetch_for_parity(company_id)
        assert native_only.get("geography_score") in (None, "0", 0)
        assert native_only.get("annual_revenue_score") in (None, "0", 0)

        patch_record("companies", company_id, {
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "5-50M",
        }, dry_run=False)
        settle(company_id, "geography_score")
        canonical = fetch_for_parity(company_id)
        assert canonical.get("geography_score") == "10"
        assert canonical.get("annual_revenue_score") == "10"


@live
@pytest.mark.parametrize("band,points", sorted(REVENUE_BAND_POINTS.items()))
def test_revenue_boundary_bands(band, points):
    with disposable_company() as company_id:
        patch_record("companies", company_id, {
            "lv_org_type": "broadcaster",
            "lv_produces_content": "true",
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": band,
        }, dry_run=False)
        settle(company_id, "annual_revenue_score")
        props = fetch_for_parity(company_id)
        assert props.get("annual_revenue_score") == str(points)


@live
def test_gambling_deducts_20_without_veto():
    with disposable_company() as company_id:
        patch_record("companies", company_id, {
            "lv_org_type": "broadcaster",
            "lv_produces_content": "true",
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "5-50M",
            "lv_is_gambling_operator": "true",
        }, dry_run=False)
        settle(company_id, "lv_icp_fit_score")
        props = fetch_for_parity(company_id)
        assert props.get("org_type_score") == "20"
        assert props.get("gambling_score") == "-20"
        assert props.get("lv_anti_icp_flag") == "false"


@live
@pytest.mark.parametrize("org_type,points", sorted(ORG_TYPE_POINTS.items()))
def test_org_type_sweep(org_type, points):
    with disposable_company() as company_id:
        patch_record("companies", company_id, {"lv_org_type": org_type}, dry_run=False)
        settle(company_id, "org_type_score")
        props = fetch_for_parity(company_id)
        assert props.get("org_type_score") == str(points)


@live
def test_f8_sub15_no_veto_is_unscored():
    # org_type "other" (0) + content True (20) + AU (10) + 1.2B+ (-50) = -20: genuinely
    # below 15 with none of the three hard-veto inputs set (D-03/ENGINE-07).
    with disposable_company() as company_id:
        patch_record("companies", company_id, {
            "lv_org_type": "other",
            "lv_produces_content": "true",
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "1.2B+",
        }, dry_run=False)
        settle(company_id, "lv_icp_tier")
        props = fetch_for_parity(company_id)
        assert props.get("lv_icp_tier") == "Unscored"
        assert props.get("lv_icp_tier") != "D"


@live
@pytest.mark.parametrize("veto_props,reason_key", [
    ({"lv_country_region_normalized": "US"}, "non_anz"),
    ({"lv_produces_content": "false"}, "no_content"),
    ({"lv_is_hardware_vendor": "true"}, "hardware_vendor"),
])
def test_veto_set_all_three_hard_vetoes(veto_props, reason_key):
    base = {
        "lv_org_type": "broadcaster",
        "lv_produces_content": "true",
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "5-50M",
    }
    base.update(veto_props)
    with disposable_company() as company_id:
        patch_record("companies", company_id, base, dry_run=False)
        settle(company_id, "lv_anti_icp_flag")
        props = fetch_for_parity(company_id)
        assert props.get("lv_anti_icp_flag") == "true"
        assert props.get("lv_anti_icp_reason") == HARD_VETOES[reason_key]["reason"]
        assert props.get("lv_icp_tier") == "D"


@live
def test_veto_set_multiple_reasons_join():
    with disposable_company() as company_id:
        patch_record("companies", company_id, {
            "lv_org_type": "broadcaster",
            "lv_produces_content": "false",
            "lv_country_region_normalized": "US",
            "lv_is_hardware_vendor": "true",
            "lv_revenue_band": "5-50M",
        }, dry_run=False)
        settle(company_id, "lv_anti_icp_flag")
        props = fetch_for_parity(company_id)
        expected_reason = "; ".join([
            HARD_VETOES["non_anz"]["reason"],
            HARD_VETOES["no_content"]["reason"],
            HARD_VETOES["hardware_vendor"]["reason"],
        ])
        assert props.get("lv_anti_icp_reason") == expected_reason


@live
def test_veto_clear_after_correction():
    with disposable_company() as company_id:
        patch_record("companies", company_id, {
            "lv_org_type": "broadcaster",
            "lv_produces_content": "true",
            "lv_country_region_normalized": "US",
            "lv_revenue_band": "5-50M",
        }, dry_run=False)
        settle(company_id, "lv_anti_icp_flag")
        vetoed = fetch_for_parity(company_id)
        assert vetoed.get("lv_anti_icp_flag") == "true"

        # D-01/D-02: the flag is owned and cleared by the n8n pipeline, not a HubSpot
        # workflow — correcting the input alone isn't enough. The operator-documented
        # refresh path is enrichment_requested + the 15-min poller (D-02).
        patch_record("companies", company_id, {"lv_country_region_normalized": "AU"}, dry_run=False)
        patch_record("companies", company_id, {"enrichment_requested": "true"}, dry_run=False)
        settle(company_id, "lv_anti_icp_flag", timeout=900, interval=15)
        cleared = fetch_for_parity(company_id)
        assert cleared.get("lv_anti_icp_flag") == "false"
        assert cleared.get("lv_anti_icp_reason") in (None, "")
        assert cleared.get("lv_icp_tier") != "D"


@live
def test_tier_on_flag_change_without_score_change():
    with disposable_company() as company_id:
        patch_record("companies", company_id, {
            "lv_org_type": "broadcaster",
            "lv_produces_content": "true",
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "5-50M",
        }, dry_run=False)
        settle(company_id, "lv_icp_fit_score")
        before = fetch_for_parity(company_id)
        score_before = before.get("lv_icp_fit_score")

        patch_record("companies", company_id, {"lv_anti_icp_flag": "true"}, dry_run=False)
        settle(company_id, "lv_icp_tier")
        after = fetch_for_parity(company_id)
        assert after.get("lv_icp_fit_score") == score_before
        assert after.get("lv_icp_tier") == "D"


@live
def test_f4_au_string_is_not_vetoed():
    with disposable_company() as company_id:
        patch_record("companies", company_id, {
            "lv_org_type": "broadcaster",
            "lv_produces_content": "true",
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "5-50M",
        }, dry_run=False)
        settle(company_id, "lv_anti_icp_flag")
        props = fetch_for_parity(company_id)
        assert props.get("lv_anti_icp_flag") == "false"
        assert props.get("geography_score") == "10"


@live
def test_f7_tier_lag():
    # Thin alias: F7's live signature is exactly the flag-change/no-score-change race
    # this test already asserts.
    test_tier_on_flag_change_without_score_change()


@live
def test_f9_gambling_conflation():
    # Thin alias: F9's live signature is exactly the gambling deduction/no-veto
    # separation this test already asserts.
    test_gambling_deducts_20_without_veto()


@live
def test_f10_boundary_overlap():
    # Thin alias: F10's live signature is exactly the 750M-1B boundary case within the
    # revenue-boundary sweep.
    test_revenue_boundary_bands("750M-1B", REVENUE_BAND_POINTS["750M-1B"])


def test_run_scoring_parity_zero_assertion_guard_offline():
    """scripts/run_scoring_parity.py's false-green guard (T-40-05), proven offline: an
    empty sample must never report success. build_report() takes no network path when
    sample_ids is empty, so this needs no portal and no credentials."""
    import scripts.run_scoring_parity as parity_script

    report, exit_code = parity_script.build_report([])
    assert exit_code != 0
    assert report["assertions_executed"] == 0
    assert "zero assertions" in report["verdict"]


def test_parity_02_named_case_completeness():
    """Collection-time guard, runs offline so it can never be skipped away: PARITY-02
    requires F4/F7/F9/F10 encoded as named, selectable regression cases. This makes that
    mechanically true rather than a claim — if any of the four names disappears from this
    module, this test fails."""
    import sys

    this_module = sys.modules[__name__]
    test_names = [name for name in dir(this_module) if name.startswith("test_")]
    for token in ("f4", "f7", "f9", "f10"):
        assert any(token in name for name in test_names), (
            f"no test function name contains {token!r} — PARITY-02's named regression "
            "case for this defect is missing"
        )
