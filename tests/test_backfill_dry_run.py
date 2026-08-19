# tests/test_backfill_dry_run.py
#
# Phase 51 Plan 01 -- offline, mocked tests for scripts/backfill_dry_run.py. Plain
# pytest, plain asserts, no classes/fixtures beyond plain helper functions (matches
# tests/test_icp_scoring.py's style). No live HubSpot or ZoomInfo call happens in this
# suite -- every network-touching function is monkeypatched.
import pytest

import scripts.backfill_seed_company_scores as backfill_seed
import src.icp_scoring as icp_scoring
from scripts import backfill_dry_run as b
from src.icp_scoring import compute_icp_score
from src.schemas import HubSpotRecord


def _mock_search_records_one_company(object_type, filters, properties, limit=100):
    return {
        "total": 1,
        "results": [
            {"id": "123", "properties": {"name": "Racing NSW", "domain": "racingnsw.com.au"}},
        ],
    }


def _mock_enrich_company_au_match(domain, token):
    return {
        "matched": True,
        "attributes": {"revenue": 268163, "country": "Australia"},
        "reason": None,
    }


def test_end_to_end_one_record_dry_run(monkeypatch):
    monkeypatch.setattr(b, "search_records", _mock_search_records_one_company)
    monkeypatch.setattr(b, "enrich_company", _mock_enrich_company_au_match)
    monkeypatch.setattr(b, "zoominfo_credit_balance", lambda: 1000)
    monkeypatch.setattr(b, "_mint_zoominfo_token", lambda: "fake-token")

    result = b.run_dry_run(sample_size=1)

    assert result["sample_size"] == 1
    assert len(result["rows"]) == 1
    assert result["skipped"] == []

    row = result["rows"][0]
    assert row["payload"]["lv_revenue_band"] == "50-500M"
    assert row["payload"]["lv_country_region_normalized"] == "AU"
    assert row["predicted_tier"] in {"A", "B", "C", "D", "Unscored"}


def test_cap_derivation():
    assert b.derive_credit_cap(108, 108) == 100
    assert b.derive_credit_cap(107, 108) == 99
    assert b.derive_credit_cap(50, 500) == 10
    assert b.derive_credit_cap(0, 108) == 0
    assert b.derive_credit_cap(-5, 108) == 0


def test_cap_boundary_refusal(monkeypatch):
    calls = []

    def mock_enrich(domain, token):
        calls.append(domain)
        return {"matched": True, "attributes": {"revenue": 268163, "country": "Australia"},
                "reason": None}

    def mock_search(object_type, filters, properties, limit=100):
        return {"total": 2, "results": [
            {"id": "1", "properties": {"name": "A", "domain": "a.com"}},
            {"id": "2", "properties": {"name": "B", "domain": "b.com"}},
        ]}

    monkeypatch.setattr(b, "search_records", mock_search)
    monkeypatch.setattr(b, "enrich_company", mock_enrich)
    monkeypatch.setattr(b, "zoominfo_credit_balance", lambda: 2)
    monkeypatch.setattr(b, "_mint_zoominfo_token", lambda: "fake-token")

    # balance 2, 108 hundredths/match -> cap = (2*100)//108 = 1. Sample == cap completes.
    result = b.run_dry_run(sample_size=1, credits_per_match_hundredths=108)
    assert result["credit_cap"] == 1
    assert len(calls) == 1

    # cap + 1 refuses WITHOUT ever calling enrich_company -- refused before spending a
    # credit is what is actually proven here.
    calls.clear()
    with pytest.raises(RuntimeError):
        b.run_dry_run(sample_size=2, credits_per_match_hundredths=108)
    assert calls == []


def test_predicted_tier_score_edges():
    assert b.predict_tier(70, False) == "A"
    assert b.predict_tier(69, False) == "B"
    assert b.predict_tier(40, False) == "B"
    assert b.predict_tier(39, False) == "C"
    assert b.predict_tier(15, False) == "C"
    assert b.predict_tier(14, False) == "Unscored"
    # veto branch wins over any score
    assert b.predict_tier(95, True) == "D"


def test_predicted_tier_excludes_needs_review():
    # No lv_org_type, no lv_produces_content -- the inputs that trigger the oracle's
    # low-confidence "Needs Review" relabel (score 20 is >= 15, so it downgrades rather
    # than going Unscored).
    patch = {"lv_country_region_normalized": "AU", "lv_revenue_band": "5-50M"}
    record = HubSpotRecord(object_type="companies", id="999", properties={})
    oracle_result = compute_icp_score(record, patch)
    assert oracle_result.tier == "Needs Review"

    row = b.build_dry_run_row("999", patch)
    assert row["predicted_tier"] != "Needs Review"
    assert row["predicted_tier"] in {"A", "B", "C", "D", "Unscored"}


def test_payload_key_set():
    patch = {
        "lv_org_type": "governing_body_league",
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
        "lv_revenue_band": "5-50M",
        "lv_is_hardware_vendor": False,
        "lv_is_gambling_operator": False,
    }
    row = b.build_dry_run_row("999", patch)
    assert set(row["payload"].keys()) == b.PERMITTED_PAYLOAD_KEYS
    for forbidden in ("lv_icp_fit_score", "lv_icp_tier_derived", "lv_anti_icp_flag", "lv_anti_icp_reason"):
        assert forbidden not in row["payload"]


def test_no_domain_skipped_before_provider_call(monkeypatch):
    calls = []

    def mock_enrich(domain, token):
        calls.append(domain)
        return {"matched": True, "attributes": {}, "reason": None}

    def mock_search(object_type, filters, properties, limit=100):
        return {"total": 1, "results": [
            {"id": "1", "properties": {"name": "NoDomain Co", "domain": ""}},
        ]}

    monkeypatch.setattr(b, "search_records", mock_search)
    monkeypatch.setattr(b, "enrich_company", mock_enrich)
    monkeypatch.setattr(b, "zoominfo_credit_balance", lambda: 1000)
    monkeypatch.setattr(b, "_mint_zoominfo_token", lambda: "fake-token")

    result = b.run_dry_run(sample_size=1)
    assert result["rows"] == []
    assert len(result["skipped"]) == 1
    assert calls == []


def test_imports_oracle_functions():
    # Object identity -- proves no local reimplementation shadows the import.
    assert b.compute_components is backfill_seed.compute_components
    assert b.compute_icp_score is icp_scoring.compute_icp_score
    assert b.anti_icp_flag_properties is icp_scoring.anti_icp_flag_properties
