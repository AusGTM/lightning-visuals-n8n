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
import json
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
        # 40-05/D-01: HubSpot no longer writes lv_anti_icp_flag at all (the n8n pipeline
        # is the sole writer), and a bare disposable patch here never triggers a
        # pipeline run -- the field reads None, not "false". Same correction pattern
        # 40-05 already applied to test_f4_au_string_is_not_vetoed.
        assert props.get("lv_anti_icp_flag") != "true"


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
        # refresh path is lv_enrichment_requested + the 15-min SJ-3 poller (D-02).
        # WINDOWS.md #4 (Rule 1 fix, this plan): the poller's actual search property is
        # lv_enrichment_requested (VETO-WRITE-EVIDENCE.md's live-proven trigger), not
        # enrichment_requested -- the latter is never read by SJ-3 Extract Rows, so this
        # patch was a silent no-op that could never have triggered a poller pickup.
        patch_record("companies", company_id, {"lv_country_region_normalized": "AU"}, dry_run=False)
        patch_record("companies", company_id, {"lv_enrichment_requested": "true"}, dry_run=False)
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
    # 40-05: after D-01's veto-branch deletion, HubSpot no longer writes
    # lv_anti_icp_flag at all -- only the n8n pipeline does, and a bare disposable
    # patch here never triggers a pipeline run. The flag reads None, not "false".
    # This test's own bar is the plan's Task 1 acceptance criterion verbatim: "not
    # equal to 'true'" (the F4 regression case: an AU company must never be
    # vetoed by a stale spelling-variant branch), not a literal "false" -- asserting
    # "false" would require an architecture (HubSpot writes the flag) this plan
    # deliberately removed.
    with disposable_company() as company_id:
        patch_record("companies", company_id, {
            "lv_org_type": "broadcaster",
            "lv_produces_content": "true",
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "5-50M",
        }, dry_run=False)
        settle(company_id, "lv_anti_icp_flag")
        props = fetch_for_parity(company_id)
        assert props.get("lv_anti_icp_flag") != "true"
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


# --------------------------------------------------------------------------------------
# 40-07 Task 3: scripts/run_scoring_parity.py's flag-comparison Rule 1 fix (the third
# instance of the None-vs-"false" defect class 40-05/40-06 each fixed once in this
# module's live pytest assertions) and the documented Needs-Review-divergence classifier.
# Offline, no network -- build_report() takes a stubbed fetch_fn.
# --------------------------------------------------------------------------------------

def test_run_scoring_parity_flag_matches_treats_none_as_not_vetoed():
    import scripts.run_scoring_parity as parity_script

    assert parity_script._flag_matches(None, False) is True
    assert parity_script._flag_matches("false", False) is True
    assert parity_script._flag_matches("true", True) is True
    assert parity_script._flag_matches(None, True) is False
    assert parity_script._flag_matches("true", False) is False


def test_run_scoring_parity_classifies_needs_review_as_documented_divergence():
    import scripts.run_scoring_parity as parity_script

    def stub_fetch(_company_id):
        # lv_produces_content unset -> oracle downgrades to Needs Review at score 15.
        # Live values mirror what a real HubSpot record shows after the backfill seeds
        # its components and WF1 grades strictly off the numeric ladder (no Needs Review
        # enum value exists live) -- score agrees, tier is the live-enum "C", flag is
        # never written (null, not "false").
        return {
            "lv_org_type": "individual_club_team",
            "lv_country_region_normalized": "AU",
            "lv_icp_fit_score": "15",
            "lv_icp_tier": "C",
            "lv_anti_icp_flag": None,
        }

    report, exit_code = parity_script.build_report(["stub-1"], fetch_fn=stub_fetch)
    assert exit_code == 0
    assert report["assertions_executed"] == 1
    assert report["real_findings"] == []
    assert report["mismatches"][0]["classification"] == "documented_needs_review_divergence"
    assert "PASS" in report["verdict"]


def test_run_scoring_parity_real_score_mismatch_is_never_absorbed_as_divergence():
    """A live score that genuinely disagrees with the oracle must surface as a real
    finding, never silently classified as the Needs Review divergence just because the
    tier also happens to differ."""
    import scripts.run_scoring_parity as parity_script

    live_triple = {"lv_icp_fit_score": "999", "lv_icp_tier": "C", "lv_anti_icp_flag": None}
    expected_triple = {"lv_icp_fit_score": "15", "lv_icp_tier": "Needs Review", "lv_anti_icp_flag": "false"}

    class _FakeResult:
        anti_icp_flag = False

    classification = parity_script._classify_mismatch(live_triple, expected_triple, _FakeResult())
    assert classification == "real_finding"


def test_run_scoring_parity_verdict_denominator_counts_failed_fetches():
    """WR-03 fix: a company whose fetch_fn raises is counted in the numerator
    (real_findings) but was excluded from assertions_executed, so the old verdict text
    ("N of {assertions_executed} sampled companies diverge") silently dropped the very
    row that failed to fetch from its own denominator. The denominator must be the full
    sample size (len(sample_ids)), not the post-filter comparisons count."""
    import scripts.run_scoring_parity as parity_script

    def stub_fetch(company_id):
        if company_id == "raises":
            raise RuntimeError("boom")
        return {
            "lv_org_type": "governing_body_league",
            "lv_produces_content": True,
            "lv_country_region_normalized": "AU",
            "lv_revenue_band": "5-50M",
            "lv_icp_fit_score": "80",
            "lv_icp_tier": "A",
            "lv_anti_icp_flag": "false",
        }

    report, exit_code = parity_script.build_report(["raises", "ok-1"], fetch_fn=stub_fetch)
    assert exit_code == 1
    assert report["assertions_executed"] == 1  # unchanged: only successful fetches
    assert len(report["real_findings"]) == 1
    assert "1 of 2 sampled companies" in report["verdict"]
    assert "1 of 1 sampled companies" not in report["verdict"]


# --------------------------------------------------------------------------------------
# Phase 41 Plan 02 Task 2 -- the automated provenance assertion. Offline, stubbed
# fetch_fn, no network. DATA-01's "provenance stamped" bar measured on every record;
# enforced as a real_finding only when PARITY_REQUIRE_PROVENANCE=true.
# --------------------------------------------------------------------------------------

def test_fit_score_props_gains_five_provenance_properties_appended_not_inserted():
    original_first_fifteen = [
        "lv_org_type", "lv_produces_content", "lv_country_region_normalized",
        "lv_revenue_band", "lv_is_gambling_operator", "lv_is_hardware_vendor",
        "org_type_score", "geography_score", "annual_revenue_score",
        "produces_content_score", "gambling_score",
        "lv_icp_fit_score", "lv_icp_tier", "lv_anti_icp_flag", "lv_anti_icp_reason",
    ]
    assert FIT_SCORE_PROPS[:15] == original_first_fifteen
    for name in (
        "lv_enrichment_provenance",
        "lv_org_type_verified_at",
        "lv_produces_content_verified_at",
        "lv_enrichment_needs_review",
        "lv_enrichment_review_reason",
    ):
        assert name in FIT_SCORE_PROPS


def _matching_stub_props(provenance_json=None, needs_review=None, review_reason=None):
    """A record whose score/tier/flag already match the oracle -- isolates the
    provenance assertion from the pre-existing mismatch classifier."""
    props = {
        "lv_org_type": "governing_body_league",
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "5-50M",
        "lv_icp_fit_score": "80",
        "lv_icp_tier": "A",
        "lv_anti_icp_flag": "false",
    }
    if provenance_json is not None:
        props["lv_enrichment_provenance"] = provenance_json
    if needs_review is not None:
        props["lv_enrichment_needs_review"] = needs_review
    if review_reason is not None:
        props["lv_enrichment_review_reason"] = review_reason
    return props


def test_provenance_absent_is_recorded_but_not_a_real_finding_by_default(monkeypatch):
    monkeypatch.delenv("PARITY_REQUIRE_PROVENANCE", raising=False)
    import scripts.run_scoring_parity as parity_script

    report, exit_code = parity_script.build_report(
        ["c1"], fetch_fn=lambda _cid: _matching_stub_props()
    )

    assert exit_code == 0
    assert report["real_findings"] == []
    assert report["comparisons"][0]["provenance"] == {
        "present": False, "valid_json": False, "fields": [], "sources": [],
    }


def test_provenance_absent_is_a_real_finding_when_explicitly_required(monkeypatch):
    monkeypatch.setenv("PARITY_REQUIRE_PROVENANCE", "true")
    import scripts.run_scoring_parity as parity_script

    report, exit_code = parity_script.build_report(
        ["c1"], fetch_fn=lambda _cid: _matching_stub_props()
    )

    assert exit_code == 1
    assert len(report["real_findings"]) == 1
    assert report["real_findings"][0]["classification"] == "provenance_missing"


def test_provenance_valid_json_reports_fields_and_sources(monkeypatch):
    monkeypatch.delenv("PARITY_REQUIRE_PROVENANCE", raising=False)
    import scripts.run_scoring_parity as parity_script

    blob = json.dumps({
        "lv_org_type": {"source": "claude_web", "confidence": 88},
        "lv_produces_content": {"source": "june_2026", "confidence": 85},
    })

    report, exit_code = parity_script.build_report(
        ["c1"], fetch_fn=lambda _cid: _matching_stub_props(provenance_json=blob)
    )

    assert exit_code == 0
    assert report["real_findings"] == []
    prov = report["comparisons"][0]["provenance"]
    assert prov["present"] is True
    assert prov["valid_json"] is True
    assert prov["fields"] == ["lv_org_type", "lv_produces_content"]
    assert prov["sources"] == ["claude_web", "june_2026"]


def test_provenance_unparseable_json_is_a_real_finding_when_required(monkeypatch):
    monkeypatch.setenv("PARITY_REQUIRE_PROVENANCE", "true")
    import scripts.run_scoring_parity as parity_script

    report, exit_code = parity_script.build_report(
        ["c1"], fetch_fn=lambda _cid: _matching_stub_props(provenance_json="not-json{")
    )

    assert exit_code == 1
    assert report["comparisons"][0]["provenance"]["valid_json"] is False
    assert report["real_findings"][0]["classification"] == "provenance_missing"


def test_needs_review_and_review_reason_are_copied_onto_the_record(monkeypatch):
    monkeypatch.delenv("PARITY_REQUIRE_PROVENANCE", raising=False)
    import scripts.run_scoring_parity as parity_script

    report, _ = parity_script.build_report(
        ["c1"],
        fetch_fn=lambda _cid: _matching_stub_props(
            needs_review="true", review_reason="june dataset conflict"
        ),
    )

    record = report["comparisons"][0]
    assert record["needs_review"] == "true"
    assert record["review_reason"] == "june dataset conflict"


def test_empty_sample_still_fails_even_with_provenance_required(monkeypatch):
    monkeypatch.setenv("PARITY_REQUIRE_PROVENANCE", "true")
    import scripts.run_scoring_parity as parity_script

    report, exit_code = parity_script.build_report([])

    assert exit_code == 1
    assert report["assertions_executed"] == 0
    assert "zero assertions" in report["verdict"]


# --------------------------------------------------------------------------------------
# Phase 43 Plan 02, Task 1 (PIPE-03/D-02/C4) -- serialize_breakdown offline tests. No
# network: a real compute_icp_score result round-trips, and a SYNTHETIC oversized
# breakdown is constructed here (per 43-02-PLAN.md fact 3: a real payload is a few
# hundred bytes and can never trip shedding on its own).
# --------------------------------------------------------------------------------------

def test_serialize_breakdown_round_trips_a_real_result():
    import scripts.run_scoring_parity as parity_script

    r = score({
        "lv_org_type": "governing_body_league",
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "50-500M",
    })
    text = parity_script.serialize_breakdown(r)
    parsed = json.loads(text)
    assert parsed["total"] == r.score == 80
    assert parsed["version"] == CFG["version"]
    assert parsed["truncated"] is False
    assert parsed["hard_vetoes"] == []
    assert {"signal": "org_type", "value": "governing_body_league", "points": 40} in parsed["components"]


def test_serialize_breakdown_sheds_component_detail_before_bytes():
    """A SYNTHETIC oversized breakdown (fact 3 -- real ones never trip this). Bulky
    per-component `value` strings push the naive dump over budget; shedding drops just
    the `value` key and keeps signal/points/hard_vetoes/total intact."""
    import scripts.run_scoring_parity as parity_script
    from src.schemas import ICPScoreResult

    big_components = [
        {"signal": f"synthetic_{i}", "value": "x" * 500, "points": i}
        for i in range(300)
    ]
    result = ICPScoreResult(
        score=42,
        tier="B",
        anti_icp_flag=False,
        recommended_motion="work_direct",
        confidence=85,
        breakdown={
            "version": "lv-icp-v0.1",
            "components": big_components,
            "hard_vetoes": ["Non-ANZ geography"],
            "graduated_deductions": [],
        },
        scoring_version="lv-icp-v0.1",
    )

    text = parity_script.serialize_breakdown(result)
    assert len(text) <= parity_script.BREAKDOWN_PROPERTY_LIMIT
    parsed = json.loads(text)
    assert parsed["total"] == 42
    assert parsed["version"] == "lv-icp-v0.1"
    assert parsed["truncated"] is True
    assert parsed["hard_vetoes"] == ["Non-ANZ geography"]
    assert len(parsed["components"]) == 300
    for c in parsed["components"]:
        assert set(c.keys()) == {"signal", "points"}


def test_serialize_breakdown_falls_back_to_counts_when_shedding_detail_is_not_enough():
    """A SYNTHETIC breakdown so large that dropping component values and bounding veto
    strings still isn't enough (thousands of long hard-veto reasons). The output must
    still be valid JSON within budget and still carry the total -- never a byte slice
    through the middle of the assembled string (the rejected merge_policy.py idiom)."""
    import scripts.run_scoring_parity as parity_script
    from src.schemas import ICPScoreResult

    result = ICPScoreResult(
        score=-20,
        tier="D",
        anti_icp_flag=True,
        recommended_motion="disqualify",
        confidence=85,
        breakdown={
            "version": "lv-icp-v0.1",
            "components": [{"signal": "org_type", "value": "other", "points": 0}],
            "hard_vetoes": ["x" * 300] * 5000,
            "graduated_deductions": [],
        },
        scoring_version="lv-icp-v0.1",
    )

    text = parity_script.serialize_breakdown(result)
    assert len(text) <= parity_script.BREAKDOWN_PROPERTY_LIMIT
    parsed = json.loads(text)
    assert parsed["total"] == -20
    assert parsed["version"] == "lv-icp-v0.1"
    assert parsed["truncated"] is True
    # A naive json.dumps(...)[:60000] slice on this input would cut mid-string and fail
    # to parse -- json.loads succeeding above is the proof this path was never taken.


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
