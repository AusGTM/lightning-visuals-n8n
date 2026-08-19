# tests/test_backfill_dry_run.py
#
# Phase 51 Plan 01/02 -- offline, mocked tests for scripts/backfill_dry_run.py. Plain
# pytest, plain asserts, no classes/fixtures beyond plain helper functions (matches
# tests/test_icp_scoring.py's style). No live HubSpot, ZoomInfo or Anthropic call happens
# in this suite -- every network-touching function is monkeypatched.
import json

import pytest

import scripts.backfill_seed_company_scores as backfill_seed
import src.icp_scoring as icp_scoring
from scripts import backfill_dry_run as b
from src.icp_scoring import compute_icp_score
from src.schemas import HubSpotRecord, ProviderEvidence, ProviderResult


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


# --- Plan 02 Task 1: gap-fill research lane + matched/unmatched partition contract ------

def test_unmatched_skip_log(monkeypatch):
    def mock_search(object_type, filters, properties, limit=100):
        return {"total": 1, "results": [
            {"id": "1", "properties": {"name": "NoMatch Co", "domain": "nomatch.com"}},
        ]}

    def mock_enrich(domain, token):
        return {"matched": False, "attributes": {}, "reason": "no_match"}

    monkeypatch.setattr(b, "search_records", mock_search)
    monkeypatch.setattr(b, "enrich_company", mock_enrich)
    monkeypatch.setattr(b, "zoominfo_credit_balance", lambda: 1000)
    monkeypatch.setattr(b, "_mint_zoominfo_token", lambda: "fake-token")

    result = b.run_dry_run(sample_size=1)

    assert result["rows"] == []
    assert len(result["skipped"]) == 1
    entry = result["skipped"][0]
    assert entry["reason"]
    assert "payload" not in entry
    assert entry["id"] == "1"
    assert entry["domain"] == "nomatch.com"


def test_no_research_for_unmatched_record(monkeypatch):
    calls = []

    def mock_research(record):
        calls.append(record)
        raise AssertionError("claude_web_research must never be called for an unmatched record")

    def mock_search(object_type, filters, properties, limit=100):
        return {"total": 1, "results": [
            {"id": "1", "properties": {"name": "NoMatch Co", "domain": "nomatch.com"}},
        ]}

    def mock_enrich(domain, token):
        return {"matched": False, "attributes": {}, "reason": "no_match"}

    monkeypatch.setattr(b, "search_records", mock_search)
    monkeypatch.setattr(b, "enrich_company", mock_enrich)
    monkeypatch.setattr(b, "claude_web_research", mock_research)
    monkeypatch.setattr(b, "zoominfo_credit_balance", lambda: 1000)
    monkeypatch.setattr(b, "_mint_zoominfo_token", lambda: "fake-token")

    result = b.run_dry_run(sample_size=1, research=True)

    assert calls == []
    assert result["rows"] == []
    assert result["research_calls_made"] == 0


def test_research_only_fills_missing_fields():
    # ZoomInfo already answered lv_org_type -- research's answer must NOT overwrite it.
    already_filled = {"lv_org_type": "governing_body_league"}
    research_result = ProviderResult(
        provider="claude_web", object_type="companies", matched=True, confidence=80,
        data={"lv_org_type": "content producer", "lv_produces_content": None},
        evidence=ProviderEvidence(),
    )
    merged = b.apply_research_to_patch(already_filled, research_result)
    assert merged["lv_org_type"] == "governing_body_league"

    # Missing lv_org_type receives the NORMALIZED research value (raw "content producer"
    # -> canonical "content_producer" via src.taxonomy.normalize_org_type).
    merged2 = b.apply_research_to_patch({}, research_result)
    assert merged2["lv_org_type"] == "content_producer"

    # A null answer (lv_produces_content) leaves the key absent -- never defaulted.
    assert "lv_produces_content" not in merged2

    # research_gap_fields must issue NO call at all when every gap field is already
    # answered by ZoomInfo (matched attributes irrelevant here, patch is what's checked).
    full_patch = {f: True for f in b.GAP_FILL_FIELDS}
    assert b.research_gap_fields({"id": "1", "name": "X", "domain": "x.com"}, {}, full_patch) is None

    # A None research_result (research call failed/degraded) is a safe no-op.
    assert b.apply_research_to_patch({"lv_revenue_band": "5-50M"}, None) == {"lv_revenue_band": "5-50M"}


def test_partition_exclusive_and_total(monkeypatch):
    def mock_search(object_type, filters, properties, limit=100):
        return {"total": 4, "results": [
            {"id": "1", "properties": {"name": "Matched Co", "domain": "matched.com"}},
            {"id": "2", "properties": {"name": "Unmatched Co", "domain": "unmatched.com"}},
            {"id": "3", "properties": {"name": "NoDomain Co", "domain": ""}},
            {"id": "4", "properties": {"name": "MatchedEmpty Co", "domain": "matchedempty.com"}},
        ]}

    def mock_enrich(domain, token):
        if domain == "matched.com":
            return {"matched": True, "attributes": {"revenue": 268163, "country": "Australia"}, "reason": None}
        if domain == "matchedempty.com":
            # Exactly-touching case: matched=True but yielded an empty attributes dict.
            return {"matched": True, "attributes": {}, "reason": None}
        return {"matched": False, "attributes": {}, "reason": "no_match"}

    monkeypatch.setattr(b, "search_records", mock_search)
    monkeypatch.setattr(b, "enrich_company", mock_enrich)
    monkeypatch.setattr(b, "zoominfo_credit_balance", lambda: 1000)
    monkeypatch.setattr(b, "_mint_zoominfo_token", lambda: "fake-token")

    result = b.run_dry_run(sample_size=4)

    row_ids = {row["id"] for row in result["rows"]}
    skip_ids = {entry["id"] for entry in result["skipped"]}

    assert row_ids.isdisjoint(skip_ids)
    assert row_ids | skip_ids == {"1", "2", "3", "4"}
    assert len(row_ids) + len(skip_ids) == 4
    # the exactly-touching record lands on exactly one side -- the matched (rows) side.
    assert "4" in row_ids
    assert "4" not in skip_ids


# --- Plan 02 Task 2: sizing plan gate (FILL-01/D-03) -------------------------------------

def test_sizing_plan_recorded_before_enrich(monkeypatch):
    calls = []

    def mock_enrich(domain, token):
        calls.append(domain)
        return {"matched": True, "attributes": {"revenue": 268163, "country": "Australia"}, "reason": None}

    def mock_search(object_type, filters, properties, limit=100):
        return {"total": 5, "results": [
            {"id": str(i), "properties": {"name": f"C{i}", "domain": f"c{i}.com"}} for i in range(1, 6)
        ]}

    monkeypatch.setattr(b, "search_records", mock_search)
    monkeypatch.setattr(b, "enrich_company", mock_enrich)
    monkeypatch.setattr(b, "zoominfo_credit_balance", lambda: 1)
    monkeypatch.setattr(b, "_mint_zoominfo_token", lambda: "fake-token")

    # balance 1, 108 hundredths/match -> cap = (1*100)//108 = 0. sample_size=1 > cap -> refused.
    with pytest.raises(RuntimeError):
        b.run_dry_run(sample_size=1, credits_per_match_hundredths=108)
    assert calls == []


def test_sample_above_cap_refused(monkeypatch):
    def mock_search(object_type, filters, properties, limit=100):
        return {"total": 0, "results": []}

    monkeypatch.setattr(b, "search_records", mock_search)
    monkeypatch.setattr(b, "zoominfo_credit_balance", lambda: 108)

    # cap = (108*100)//108 = 100 -- sample_size == cap is accepted.
    plan = b.build_sizing_plan(100, credits_per_match_hundredths=108)
    assert plan["credit_cap"] == 100
    assert plan["sample_size"] == 100

    # cap + 1 refuses, both numbers named in the message.
    with pytest.raises(RuntimeError) as exc_info:
        b.build_sizing_plan(101, credits_per_match_hundredths=108)
    message = str(exc_info.value)
    assert "101" in message
    assert "100" in message


# --- Plan 02 Task 3: empty-sample and ordering edge probes -------------------------------

def test_empty_sample_writes_valid_artifacts(monkeypatch, tmp_path):
    def mock_search(object_type, filters, properties, limit=100):
        return {"total": 2, "results": [
            {"id": "1", "properties": {"name": "A", "domain": "a.com"}},
            {"id": "2", "properties": {"name": "B", "domain": "b.com"}},
        ]}

    def mock_enrich(domain, token):
        return {"matched": False, "attributes": {}, "reason": "no_match"}

    monkeypatch.setattr(b, "search_records", mock_search)
    monkeypatch.setattr(b, "enrich_company", mock_enrich)
    monkeypatch.setattr(b, "zoominfo_credit_balance", lambda: 1000)
    monkeypatch.setattr(b, "_mint_zoominfo_token", lambda: "fake-token")
    monkeypatch.setattr(b, "_has_credentials", lambda: True)
    monkeypatch.setattr(b, "zoominfo_credentials_present", lambda: True)
    monkeypatch.setattr(b, "_portal_ok", lambda: True)
    monkeypatch.setattr(b, "patch_record", lambda *a, **k: {"dry_run": True})

    out_path = tmp_path / "predictions.json"
    skip_path = tmp_path / "skip.json"

    exit_code = b.main(["--sample", "2", "--out", str(out_path), "--skip-out", str(skip_path)])
    assert exit_code == 0

    predictions = json.loads(out_path.read_text())
    assert predictions["rows"] == []
    assert predictions["population_total"] is not None
    assert predictions["credit_cap"] is not None
    assert predictions["sample_size"] == 2

    skip_log = json.loads(skip_path.read_text())
    assert len(skip_log["entries"]) == 2
    assert skip_log["counts"]["rows"] == 0
    assert skip_log["counts"]["skipped"] == 2


def test_sample_order_is_ascending_id_stable(monkeypatch):
    def mock_search(object_type, filters, properties, limit=100):
        return {"total": 3, "results": [
            {"id": "10021111653", "properties": {"name": "Big", "domain": "big.com"}},
            {"id": "9604614548", "properties": {"name": "Small", "domain": "small.com"}},
            {"id": "17317381378", "properties": {"name": "Mid", "domain": "mid.com"}},
        ]}

    monkeypatch.setattr(b, "search_records", mock_search)

    sample1 = b.select_never_scored_sample(3)
    sample2 = b.select_never_scored_sample(3)
    ids1 = [c["id"] for c in sample1]
    ids2 = [c["id"] for c in sample2]

    assert ids1 == ids2
    # Numeric order, not lexicographic: "9604614548" < "10021111653" numerically but
    # would sort AFTER it as a plain string.
    assert ids1 == ["9604614548", "10021111653", "17317381378"]
