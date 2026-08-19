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
    # Baseline (agreeing/no-HubSpot-country) case: no conflict, source stays zoominfo.
    assert row["country_conflict"] is None
    assert row["sources"]["lv_country_region_normalized"] == "zoominfo"


def _mock_search_records_gold_coast(object_type, filters, properties, limit=100):
    return {
        "total": 1,
        "results": [
            {"id": "9604630690", "properties": {
                "name": "Gold Coast Turf Club", "domain": "gctc.com.au",
                "website": "https://gctc.com.au", "country": "Australia",
                "industry": "Sports",
            }},
        ],
    }


def _mock_enrich_company_wrong_country(domain, token):
    # The real Gold Coast Turf Club shape (51-03 checkpoint finding): ZoomInfo returned
    # "Netherlands" for an Australian turf club, which would otherwise fire a spurious
    # non-ANZ hard veto on top of the (separate, legitimate) no-content veto.
    return {
        "matched": True,
        "attributes": {"revenue": 29407, "country": "Netherlands"},
        "reason": None,
    }


def test_country_conflict_hubspot_wins(monkeypatch):
    monkeypatch.setattr(b, "search_records", _mock_search_records_gold_coast)
    monkeypatch.setattr(b, "enrich_company", _mock_enrich_company_wrong_country)
    monkeypatch.setattr(b, "zoominfo_credit_balance", lambda: 1000)
    monkeypatch.setattr(b, "_mint_zoominfo_token", lambda: "fake-token")

    result = b.run_dry_run(sample_size=1)

    assert result["skipped"] == []
    row = result["rows"][0]

    # HubSpot's own country (Australia) wins over ZoomInfo's disagreeing value
    # (Netherlands) -- no false non-ANZ veto.
    assert row["payload"]["lv_country_region_normalized"] == "AU"
    assert row["sources"]["lv_country_region_normalized"] == "hubspot"
    assert "Non-ANZ geography" not in (row["anti_icp_reason"] or "")

    # The conflict is visible in the artifact, not silently resolved.
    conflict = row["country_conflict"]
    assert conflict is not None
    assert conflict["hubspot_country"] == "Australia"
    assert conflict["hubspot_region"] == "AU"
    assert conflict["zoominfo_country"] == "Netherlands"
    assert conflict["zoominfo_region"] == "Other"
    assert conflict["resolved_region"] == "AU"


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
        evidence_by_field={"lv_org_type": "https://example.com/about"},
    )
    merged = b.apply_research_to_patch(already_filled, research_result)
    assert merged["lv_org_type"] == "governing_body_league"

    # Missing lv_org_type receives the NORMALIZED research value (raw "content producer"
    # -> canonical "content_producer" via src.taxonomy.normalize_org_type), gated by
    # config/field_policy.yaml's min_confidence=80 (met exactly) and require_evidence_url_for
    # (content_producer is listed; evidence_by_field supplies it above).
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


def test_field_policy_gate_rejects_below_min_confidence():
    # config/field_policy.yaml: lv_produces_content min_confidence=85. confidence=84 is
    # one point below the gate -- must be treated as absent, never promoted.
    research_result = ProviderResult(
        provider="claude_web", object_type="companies", matched=True, confidence=84,
        data={"lv_produces_content": True},
        evidence=ProviderEvidence(),
        evidence_by_field={"lv_produces_content": "https://example.com/watch-live"},
    )
    merged = b.apply_research_to_patch({}, research_result)
    assert "lv_produces_content" not in merged


def test_field_policy_gate_rejects_missing_required_evidence_url():
    # confidence clears the gate (90 >= 85) but lv_produces_content requires an evidence
    # URL and none is supplied -- must still be treated as absent.
    research_result = ProviderResult(
        provider="claude_web", object_type="companies", matched=True, confidence=90,
        data={"lv_produces_content": True},
        evidence=ProviderEvidence(),
        evidence_by_field={},
    )
    merged = b.apply_research_to_patch({}, research_result)
    assert "lv_produces_content" not in merged


def test_field_policy_gate_accepts_at_exact_threshold_with_evidence():
    # confidence == min_confidence (85, inclusive) plus a cited evidence URL -- promoted.
    research_result = ProviderResult(
        provider="claude_web", object_type="companies", matched=True, confidence=85,
        data={"lv_produces_content": True},
        evidence=ProviderEvidence(),
        evidence_by_field={"lv_produces_content": "https://example.com/watch-live"},
    )
    merged = b.apply_research_to_patch({}, research_result)
    assert merged["lv_produces_content"] is True


def test_field_policy_gate_org_type_only_requires_evidence_for_gated_types():
    # individual_club_team is NOT in require_evidence_url_for -- confidence alone (>=80)
    # is enough, no evidence_by_field entry needed.
    research_result = ProviderResult(
        provider="claude_web", object_type="companies", matched=True, confidence=80,
        data={"lv_org_type": "individual club team"},
        evidence=ProviderEvidence(),
        evidence_by_field={},
    )
    merged = b.apply_research_to_patch({}, research_result)
    assert merged["lv_org_type"] == "individual_club_team"

    # governing_body_league IS gated -- same confidence, no evidence -- stays absent.
    research_result_gated = ProviderResult(
        provider="claude_web", object_type="companies", matched=True, confidence=80,
        data={"lv_org_type": "governing body league"},
        evidence=ProviderEvidence(),
        evidence_by_field={},
    )
    merged_gated = b.apply_research_to_patch({}, research_result_gated)
    assert "lv_org_type" not in merged_gated


def _research_result(produces_content, confidence=90, with_evidence=True, org_type="individual club team"):
    return ProviderResult(
        provider="claude_web", object_type="companies", matched=True, confidence=confidence,
        data={"lv_org_type": org_type, "lv_produces_content": produces_content,
              "lv_is_hardware_vendor": None, "lv_is_gambling_operator": None},
        evidence=ProviderEvidence(evidence_urls=[f"https://example.com/{produces_content}"]),
        evidence_by_field={"lv_produces_content": "https://example.com/watch-live"} if with_evidence else {},
    )


def test_majority_vote_picks_majority_bool_and_confidence_of_agreeing_calls_only(monkeypatch):
    # 2 of 3 calls say True (confidence 90, 92); the outvoted False call (confidence 60)
    # must NOT drag the returned confidence down -- mean of the 2 agreeing calls (91), not
    # the mean of all 3 (~80.7). This is a genuine 2-1 lv_produces_content disagreement, so
    # (checkpoint round 3) it now escalates to the judge -- mocked here to agree with the
    # natural majority (True), keeping this test's original assertions meaningful for what
    # they actually test: the confidence-of-agreeing-calls averaging, not the judge path.
    sequence = [
        _research_result(True, confidence=90),
        _research_result(False, confidence=60),
        _research_result(True, confidence=92),
    ]
    calls = {"n": 0}

    def mock_research(record):
        result = sequence[calls["n"]]
        calls["n"] += 1
        return result

    def mock_judge(record, field, current_value, candidates, haiku_result, policy):
        return _judge_result(chosen_value=True, evidence_url="https://example.com/watch-live")

    monkeypatch.setattr(b, "claude_web_research", mock_research)
    monkeypatch.setattr(b, "validate_conflict_with_sonnet", mock_judge)
    record = HubSpotRecord(object_type="companies", id="1", properties={"name": "X"})
    result = b.research_with_majority_vote(record)

    assert calls["n"] == 3
    assert result.data["lv_produces_content"] is True
    assert result.confidence == 91
    assert result.evidence_by_field["lv_produces_content"] == "https://example.com/watch-live"


def test_majority_vote_tie_resolves_to_absent_not_false(monkeypatch):
    # 2 repetitions, one True one False -- a tie must resolve to "no majority" (key absent
    # from the returned data), never a defaulted False (which would wrongly fire the
    # no-content hard veto on a genuinely disputed answer). This tie is ALSO a genuine
    # disagreement, so it escalates to the judge (checkpoint round 3) -- mocked here to a
    # deliberate needs_review so the absent outcome is asserted explicitly, not an
    # accident of whatever ANTHROPIC_API_KEY happens to be set in the ambient environment.
    sequence = [_research_result(True), _research_result(False)]
    calls = {"n": 0}

    def mock_research(record):
        result = sequence[calls["n"]]
        calls["n"] += 1
        return result

    def mock_judge(record, field, current_value, candidates, haiku_result, policy):
        return _judge_result(decision="needs_review", chosen_value=None, confidence=50)

    monkeypatch.setattr(b, "claude_web_research", mock_research)
    monkeypatch.setattr(b, "validate_conflict_with_sonnet", mock_judge)
    record = HubSpotRecord(object_type="companies", id="1", properties={"name": "X"})
    result = b.research_with_majority_vote(record, repetitions=2)

    assert "lv_produces_content" not in result.data


def test_majority_vote_all_calls_fail_returns_none(monkeypatch):
    def mock_research(record):
        raise RuntimeError("simulated live-call failure")

    monkeypatch.setattr(b, "claude_web_research", mock_research)
    record = HubSpotRecord(object_type="companies", id="1", properties={"name": "X"})
    assert b.research_with_majority_vote(record) is None


def test_majority_bool_and_majority_str_helpers_never_guess_on_a_tie():
    assert b._majority_bool([True, False]) is None
    assert b._majority_bool([None, None]) is None
    assert b._majority_bool([True, True, False]) is True
    assert b._majority_str(["a", "b"]) is None
    assert b._majority_str(["a", "a", "b"]) == "a"


def test_research_gap_fields_routes_through_majority_vote(monkeypatch):
    # research_gap_fields must issue RESEARCH_VOTE_REPETITIONS raw calls, not one, and the
    # returned result must be the majority-voted answer.
    calls = {"n": 0}

    def mock_research(record):
        calls["n"] += 1
        return _research_result(True)

    monkeypatch.setattr(b, "claude_web_research", mock_research)
    result = b.research_gap_fields({"id": "1", "name": "X", "domain": "x.com"}, {}, {})

    assert calls["n"] == b.RESEARCH_VOTE_REPETITIONS
    assert result.data["lv_produces_content"] is True


def _judge_result(decision="promote", chosen_value=True, confidence=90, evidence_url="https://example.com/e"):
    return {
        "decision": decision, "chosen_provider": "claude_web", "chosen_value": chosen_value,
        "confidence": confidence, "reason": "test", "validation_status": "sonnet_validated",
        "evidence_url": evidence_url, "evidence_summary": "test",
    }


def test_conflicting_produces_content_escalates_to_judge_and_overrides_majority(monkeypatch):
    # 2 True, 1 False -- majority is True, but votes are NOT unanimous, so this must
    # escalate. The judge's answer (False here) must win over the raw majority (True),
    # proving the escalation actually overrides the vote rather than just annotating it.
    sequence = [_research_result(True), _research_result(True), _research_result(False)]
    calls = {"n": 0}

    def mock_research(record):
        result = sequence[calls["n"]]
        calls["n"] += 1
        return result

    judge_calls = {"n": 0}

    def mock_judge(record, field, current_value, candidates, haiku_result, policy):
        judge_calls["n"] += 1
        assert field == "lv_produces_content"
        assert len(candidates) == 3  # one candidate per repetition that answered the field
        return _judge_result(chosen_value=False)

    monkeypatch.setattr(b, "claude_web_research", mock_research)
    monkeypatch.setattr(b, "validate_conflict_with_sonnet", mock_judge)
    record = HubSpotRecord(object_type="companies", id="1", properties={"name": "X"})
    judge_state = {"calls_made": 0, "cap_hit": False}
    result = b.research_with_majority_vote(record, judge_state=judge_state)

    assert judge_calls["n"] == 1
    assert judge_state["calls_made"] == 1
    assert result.data["lv_produces_content"] is False
    assert result.evidence_by_field["lv_produces_content"] == "https://example.com/e"


def test_judge_low_confidence_leaves_produces_content_absent(monkeypatch):
    # SS15.1 human_review: sonnet_confidence_below 80 -> the field stays absent, never a
    # defaulted False (a defaulted False on lv_produces_content IS the hard veto).
    sequence = [_research_result(True), _research_result(True), _research_result(False)]
    calls = {"n": 0}

    def mock_research(record):
        result = sequence[calls["n"]]
        calls["n"] += 1
        return result

    def mock_judge(record, field, current_value, candidates, haiku_result, policy):
        return _judge_result(confidence=70)  # below the 80 threshold

    monkeypatch.setattr(b, "claude_web_research", mock_research)
    monkeypatch.setattr(b, "validate_conflict_with_sonnet", mock_judge)
    record = HubSpotRecord(object_type="companies", id="1", properties={"name": "X"})
    result = b.research_with_majority_vote(record, judge_state={"calls_made": 0, "cap_hit": False})

    assert "lv_produces_content" not in result.data
    assert "lv_produces_content" not in result.evidence_by_field


def test_non_conflicting_produces_content_never_calls_the_judge(monkeypatch):
    # All 3 repetitions agree -- research_with_majority_vote must never escalate a
    # unanimous field. This is what keeps judge spend proportional to actual conflicts.
    def mock_research(record):
        return _research_result(True)

    def mock_judge(*args, **kwargs):
        raise AssertionError("judge must not be called for a non-conflicting field")

    monkeypatch.setattr(b, "claude_web_research", mock_research)
    monkeypatch.setattr(b, "validate_conflict_with_sonnet", mock_judge)
    record = HubSpotRecord(object_type="companies", id="1", properties={"name": "X"})
    judge_state = {"calls_made": 0, "cap_hit": False}
    result = b.research_with_majority_vote(record, judge_state=judge_state)

    assert result.data["lv_produces_content"] is True
    assert judge_state["calls_made"] == 0


def test_judge_cap_asserted_before_spending(monkeypatch):
    # Cap already spent -- must refuse to spend another judge call (fail safe: leave the
    # field absent) rather than raising or silently exceeding MAX_JUDGE_VALIDATIONS_PER_RUN.
    sequence = [_research_result(True), _research_result(True), _research_result(False)]
    calls = {"n": 0}

    def mock_research(record):
        result = sequence[calls["n"]]
        calls["n"] += 1
        return result

    def mock_judge(*args, **kwargs):
        raise AssertionError("judge must not be called once the cap is already spent")

    monkeypatch.setattr(b, "claude_web_research", mock_research)
    monkeypatch.setattr(b, "validate_conflict_with_sonnet", mock_judge)
    monkeypatch.setattr(b, "MAX_JUDGE_VALIDATIONS_DEFAULT", 1)
    record = HubSpotRecord(object_type="companies", id="1", properties={"name": "X"})
    judge_state = {"calls_made": 1, "cap_hit": False}  # cap of 1 already spent
    result = b.research_with_majority_vote(record, judge_state=judge_state)

    assert "lv_produces_content" not in result.data
    assert judge_state["cap_hit"] is True
    assert judge_state["calls_made"] == 1  # unchanged -- no call was spent


def test_run_dry_run_research_cap_budgets_for_vote_repetitions(monkeypatch):
    # sample_size=4 at RESEARCH_VOTE_REPETITIONS=3 projects 12 calls -- must refuse against
    # a cap of 10, even though 4 alone would have fit the old one-call-per-company budget.
    monkeypatch.setattr(b, "search_records", _mock_search_records_one_company)
    monkeypatch.setattr(b, "zoominfo_credit_balance", lambda: 1000)
    with pytest.raises(RuntimeError, match="exceeds the research call cap"):
        b.run_dry_run(sample_size=4, research=True, max_research_calls=10)


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


def test_diversified_sample_stratifies_by_industry(monkeypatch):
    # 2 media-bucket companies (unsorted ids) + 3 plain ones (unsorted ids) -- mirrors the
    # live population's GAMBLING_CASINOS-cluster-vs-SPORTS/BROADCAST_MEDIA split.
    def mock_search(object_type, filters, properties, limit=100):
        return {"total": 5, "results": [
            {"id": "300", "properties": {"name": "Gambling Co", "domain": "g.com", "industry": "GAMBLING_CASINOS"}},
            {"id": "100", "properties": {"name": "Broadcaster", "domain": "b.com", "industry": "BROADCAST_MEDIA"}},
            {"id": "500", "properties": {"name": "Sports League", "domain": "s.com", "industry": "SPORTS"}},
            {"id": "200", "properties": {"name": "Gambling Co 2", "domain": "g2.com", "industry": "GAMBLING_CASINOS"}},
            {"id": "400", "properties": {"name": "Amusement Park", "domain": "a.com", "industry": "Amusement Parks, Arcades & Attractions"}},
        ]}

    monkeypatch.setattr(b, "search_records", mock_search)

    sample = b.select_diversified_never_scored_sample(4, media_slots=2)
    ids = [c["id"] for c in sample]

    # Media bucket (BROADCAST_MEDIA id=100, SPORTS id=500) first, ascending id within the
    # bucket; then the residual pool fills the rest by ascending id, excluding the two
    # media picks.
    assert ids == ["100", "500", "200", "300"]
    assert [c["industry"] for c in sample] == [
        "BROADCAST_MEDIA", "SPORTS", "GAMBLING_CASINOS", "GAMBLING_CASINOS",
    ]

    # Deterministic: a second call with the same mocked page returns the same order.
    assert [c["id"] for c in b.select_diversified_never_scored_sample(4, media_slots=2)] == ids


def test_diversified_sample_media_slots_short_falls_back_to_fill(monkeypatch):
    # Only 1 media-bucket company exists -- media_slots=2 cannot be satisfied; the fill
    # pool must make up the difference rather than returning a short sample.
    def mock_search(object_type, filters, properties, limit=100):
        return {"total": 3, "results": [
            {"id": "100", "properties": {"name": "Broadcaster", "domain": "b.com", "industry": "BROADCAST_MEDIA"}},
            {"id": "200", "properties": {"name": "Club", "domain": "c.com", "industry": "GAMBLING_CASINOS"}},
            {"id": "300", "properties": {"name": "Club 2", "domain": "c2.com", "industry": "GAMBLING_CASINOS"}},
        ]}

    monkeypatch.setattr(b, "search_records", mock_search)

    sample = b.select_diversified_never_scored_sample(3, media_slots=2)
    assert [c["id"] for c in sample] == ["100", "200", "300"]


def test_run_dry_run_diversified_records_selection_rule(monkeypatch):
    def mock_search(object_type, filters, properties, limit=100):
        return {"total": 2, "results": [
            {"id": "100", "properties": {"name": "Broadcaster", "domain": "b.com", "industry": "BROADCAST_MEDIA"}},
            {"id": "200", "properties": {"name": "Club", "domain": "c.com", "industry": "GAMBLING_CASINOS"}},
        ]}

    monkeypatch.setattr(b, "search_records", mock_search)
    monkeypatch.setattr(b, "enrich_company", _mock_enrich_company_au_match)
    monkeypatch.setattr(b, "zoominfo_credit_balance", lambda: 1000)
    monkeypatch.setattr(b, "_mint_zoominfo_token", lambda: "fake-token")

    result = b.run_dry_run(sample_size=2, diversified=True, media_slots=1)

    assert result["sample_selection_rule"] == "diversified_industry_stratified"
    assert result["media_slots"] == 1
    assert [row["id"] for row in result["rows"]] == ["100", "200"]
    assert [row["industry"] for row in result["rows"]] == ["BROADCAST_MEDIA", "GAMBLING_CASINOS"]


def test_run_dry_run_default_records_ascending_id_rule(monkeypatch):
    monkeypatch.setattr(b, "search_records", _mock_search_records_one_company)
    monkeypatch.setattr(b, "enrich_company", _mock_enrich_company_au_match)
    monkeypatch.setattr(b, "zoominfo_credit_balance", lambda: 1000)
    monkeypatch.setattr(b, "_mint_zoominfo_token", lambda: "fake-token")

    result = b.run_dry_run(sample_size=1)

    assert result["sample_selection_rule"] == "ascending_id"
    assert result["media_slots"] is None
