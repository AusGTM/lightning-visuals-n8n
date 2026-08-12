"""tests/test_enrich_coverage_companies.py

Phase 48 Plan 01 (COVER-01, COVER-02) -- offline tests for
scripts/enrich_coverage_companies.py. No network calls anywhere in this module -- every
test either monkeypatches requests.post/requests.patch to raise, injects a fake searcher,
or exercises pure functions.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*` imports resolve

import scripts.enrich_coverage_companies as m  # noqa: E402
import scripts.remediate_veto_companies as rvc  # noqa: E402

RACING_NSW_ID = "15008671672"   # Racing NSW -- no captured research (PendingResearch)
EDITIX_ID = "17317381378"       # Editix -- D-03 un-enrichable marker
JAM_TV_ID = "17317850381"       # Jam TV -- broadcaster
WAIKATO_ID = "20538284384"      # Waikato Racing Club Inc -- individual_club_team
RUMBLE_ID = "20943964946"       # The Rumble / Pacific Action Sports -- content_producer


def _refuse_network(*_a, **_kw):
    raise AssertionError("no network call should be made in this test")


def _load_research(company_id):
    data = json.loads(m.RESEARCH_RESULTS_PATH.read_text())
    return data[company_id]


# --- Task 1: end-to-end tracer, Jam TV ------------------------------------------------------

def test_tracer_jam_tv_end_to_end_zero_network(monkeypatch):
    monkeypatch.setattr("requests.post", _refuse_network)
    monkeypatch.setattr("requests.patch", _refuse_network)

    research = _load_research(JAM_TV_ID)
    decision = m.decide_org_type(JAM_TV_ID, research)
    assert decision["org_type"] == "broadcaster"

    patch = m.build_coverage_patch(JAM_TV_ID, decision, "2026-08-12T00:00:00+00:00")
    assert patch["properties"] == {
        "lv_org_type": "broadcaster",
        "lv_org_type_verified_at": "2026-08-12T00:00:00+00:00",
    }

    estimate = m.estimate_phase48_cost(research_ids=[], written_ids=[JAM_TV_ID])
    assert estimate["web_research_calls"] == 0
    assert estimate["n8n_executions"] == 1
    assert estimate["lusha_credits"] == 0

    resolved = m.refuse_if_over_budget(estimate, [JAM_TV_ID])
    assert resolved == [JAM_TV_ID]

    # DRY_RUN defaults "true", ALLOW_ENRICH_COVERAGE defaults "false" -- both must flip.
    assert m.coverage_writes_allowed() is False


def _load_racing_nsw_research():
    path = m.ROOT / ".planning/phases/48-enrichment-coverage/48-RESEARCH-RACING-NSW.json"
    return json.loads(path.read_text())


def test_racing_nsw_decision_is_governing_body_league_overriding_the_returned_value():
    # Plan 48-03 Task 3 resolved Racing NSW to "regulator" (evidenced, not a guess).
    # Plan 48-07 Task 1: operator review rejected that classification and overrides it to
    # "governing_body_league" -- recorded as data (override_of/override_rationale), never
    # by editing the captured artifact.
    research = _load_racing_nsw_research()
    decision = m.decide_org_type(RACING_NSW_ID, research)
    assert decision["org_type"] == "governing_body_league"
    assert decision["override_of"] == "regulator"
    assert "QRIC" in decision["override_rationale"]
    assert "Racing NSW" in decision["override_rationale"]
    assert decision.get("basis")


def test_guard_never_flips_an_incoherent_regulator_to_another_value():
    # Task 3: the verbatim captured artifact is exactly the shape the guard exists for --
    # org_type='regulator' alongside evidenced content output and sponsorship reliance.
    # resolve_racing_nsw_decision refuses to promote it -- it does NOT guess a
    # replacement; the corrected value comes only from Task 1's authored override table.
    research = _load_racing_nsw_research()
    decision = m.resolve_racing_nsw_decision(research)

    assert decision["org_type"] == "unknown"
    assert decision["org_type"] != "governing_body_league"
    assert decision["reason"]


def test_load_captured_research_resolves_racing_nsw_via_path_override():
    # Racing NSW is not one of the 17 keys in 47-RESEARCH-RESULTS.json -- before this
    # task, _load_captured_research("15008671672") returned None and decide_org_type
    # raised an uncaught ValueError (the live blocker this task fixes). The override
    # file IS the research dict itself (unlike 47-RESEARCH-RESULTS.json, which is keyed
    # by company id) -- the loader must resolve both shapes correctly.
    racing_nsw = m._load_captured_research(RACING_NSW_ID)
    assert isinstance(racing_nsw, dict)
    assert "matched" in racing_nsw and "confidence" in racing_nsw

    jam_tv = m._load_captured_research(JAM_TV_ID)
    assert isinstance(jam_tv, dict)
    assert "matched" in jam_tv and "confidence" in jam_tv


def test_tracer_valid_org_types_imported_not_redeclared():
    assert m.VALID_ORG_TYPES is rvc.VALID_ORG_TYPES


def test_tracer_resolve_coverage_ids_refuses_unknown_id():
    with pytest.raises(rvc.PinRefused):
        m.resolve_coverage_ids(["0000000000"])


def test_tracer_resolve_coverage_ids_sorts_into_table_order():
    resolved = m.resolve_coverage_ids([WAIKATO_ID, RACING_NSW_ID])
    assert resolved == (RACING_NSW_ID, WAIKATO_ID)


def test_tracer_build_coverage_patch_rejects_out_of_vocabulary_org_type():
    with pytest.raises(ValueError):
        m.build_coverage_patch(
            WAIKATO_ID, {"org_type": "venue", "basis": "not a live option"},
            "2026-08-12T00:00:00+00:00",
        )


def test_tracer_refuse_if_over_budget_raises_and_never_returns_a_shorter_list():
    over_budget_estimate = m.estimate_phase48_cost(
        research_ids=[], written_ids=[JAM_TV_ID, WAIKATO_ID], proof_executions=0,
    )
    over_budget_estimate["n8n_budget_month"] = 1  # force n8n_executions > budget

    with pytest.raises(rvc.BudgetRefused):
        m.refuse_if_over_budget(over_budget_estimate, [JAM_TV_ID, WAIKATO_ID])
    # COVER-02: refuse whole, never trim -- there is no code path that returns a shorter
    # id list, so the only observable outcome of an over-budget estimate is the raise
    # above. Nothing further to assert here; the pytest.raises block IS the proof.


def test_budget_within_budget_returns_ids_unmodified_same_length_and_order():
    all_five = list(m.COVERAGE_COMPANY_ID_ORDER)
    estimate = m.estimate_phase48_cost(
        research_ids=["15008671672"], written_ids=all_five, proof_executions=1,
    )
    # 48-03-PLAN.md's expected shape: 1 web-research call, 6 n8n executions (5 recompute
    # POSTs + 1 disarmed proof-of-deploy execution), well within the 2,500/month budget.
    assert estimate["web_research_calls"] == 1
    assert estimate["n8n_executions"] == 6
    assert estimate["anthropic_estimate_usd"] == 0.0686

    resolved = m.refuse_if_over_budget(estimate, all_five)
    assert resolved == all_five
    assert len(resolved) == len(all_five)


def test_tracer_post_webhook_event_refuses_unarmed_before_any_transport_call():
    def _refuse_transport(*_a, **_kw):
        raise AssertionError("no transport call should be made when unarmed")

    class _FakeTransport:
        post = staticmethod(_refuse_transport)

    with pytest.raises(rvc.NotArmedError):
        m.post_webhook_event(JAM_TV_ID, armed=False, config={}, transport=_FakeTransport())


def test_tracer_dry_run_cli_prints_broadcaster_patch(monkeypatch, capsys):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)
    exit_code = m.main(["--ids", JAM_TV_ID, "--dry-run"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert '"lv_org_type": "broadcaster"' in captured.out
    assert "lv_anti_icp_flag" not in captured.out
    assert "lv_icp_fit_score" not in captured.out
    assert "lv_icp_tier" not in captured.out


# --- Task 2: full decision table + D-03 marker -----------------------------------------------

def test_mapping_jam_tv_is_broadcaster():
    research = _load_research(JAM_TV_ID)
    decision = m.decide_org_type(JAM_TV_ID, research)
    assert decision["org_type"] == "broadcaster"


def test_mapping_waikato_is_individual_club_team():
    research = _load_research(WAIKATO_ID)
    decision = m.decide_org_type(WAIKATO_ID, research)
    assert decision["org_type"] == "individual_club_team"


def test_mapping_rumble_is_content_producer_per_d05():
    research = _load_research(RUMBLE_ID)
    decision = m.decide_org_type(RUMBLE_ID, research)
    assert decision["org_type"] == "content_producer"


def test_marker_editix_is_unknown_with_reason():
    research = _load_research(EDITIX_ID)
    decision = m.decide_org_type(EDITIX_ID, research)
    assert decision["org_type"] == "unknown"
    assert decision.get("basis")


def test_marker_racing_nsw_is_resolved_not_pending():
    research = _load_racing_nsw_research()
    decision = m.decide_org_type(RACING_NSW_ID, research)
    assert decision["org_type"] in rvc.VALID_ORG_TYPES
    assert decision.get("basis")


def test_marker_coverage_state_distinguishes_never_attempted_from_attempted_unresolved():
    never_attempted = m.coverage_state({"lv_org_type": ""})
    attempted_unresolved = m.coverage_state(
        {"lv_org_type": "unknown", "lv_enrichment_review_reason": "identity unresolvable"}
    )
    assert never_attempted == "never_attempted"
    assert attempted_unresolved == "attempted_unresolved"
    assert never_attempted != attempted_unresolved


def test_marker_build_coverage_patch_editix_carries_non_empty_review_reason():
    decision = m.ORG_TYPE_DECISIONS[EDITIX_ID]
    patch = m.build_coverage_patch(EDITIX_ID, decision, "2026-08-12T00:00:00+00:00")
    assert patch["properties"]["lv_enrichment_review_reason"]


def test_marker_build_coverage_patch_others_carry_no_review_reason_key():
    for company_id in (JAM_TV_ID, WAIKATO_ID, RUMBLE_ID):
        decision = m.ORG_TYPE_DECISIONS[company_id]
        patch = m.build_coverage_patch(company_id, decision, "2026-08-12T00:00:00+00:00")
        assert not any("review_reason" in key for key in patch["properties"])


def test_marker_no_patch_contains_country_region_key():
    now_iso = "2026-08-12T00:00:00+00:00"
    for company_id in (JAM_TV_ID, WAIKATO_ID, RUMBLE_ID, EDITIX_ID):
        decision = m.ORG_TYPE_DECISIONS[company_id]
        patch = m.build_coverage_patch(company_id, decision, now_iso)
        assert not any("country_region" in key for key in patch["properties"])


# --- Task 3: live population re-derivation + reconciliation ----------------------------------

def test_population_derive_population_uses_exact_filters_and_properties():
    captured = {}

    def _fake_searcher(object_type, filters, properties, limit=100):
        captured["object_type"] = object_type
        captured["filters"] = filters
        captured["properties"] = properties
        return {"results": [{"id": JAM_TV_ID, "properties": {"name": "Jam TV"}}]}

    population = m.derive_population(searcher=_fake_searcher)

    assert captured["object_type"] == "companies"
    assert captured["filters"] == [
        {"propertyName": "lv_icp_fit_score", "operator": "HAS_PROPERTY"},
        {"propertyName": "lv_org_type", "operator": "NOT_HAS_PROPERTY"},
    ]
    assert population["count"] == 1
    assert population["ids"] == [JAM_TV_ID]
    assert population["derived_at"]


def test_reconcile_population_flags_drift_and_never_narrows():
    derived = {"ids": [EDITIX_ID, JAM_TV_ID, WAIKATO_ID, RUMBLE_ID]}  # RACING_NSW_ID missing

    reconciliation = m.reconcile_population(derived)

    assert reconciliation["drift"] is True
    assert RACING_NSW_ID in reconciliation["missing"]
    assert len(reconciliation["expected"]) == 5


def test_reconcile_population_no_drift_when_sets_match():
    derived = {"ids": list(m.COVERAGE_COMPANY_ID_ORDER)}

    reconciliation = m.reconcile_population(derived)

    assert reconciliation["drift"] is False
    assert reconciliation["missing"] == []
    assert reconciliation["unexpected"] == []


# --- Plan 48-03 Task 3: Racing NSW's one enum-constrained call, captured + mapped ------------

def test_racing_nsw_prompt_lists_all_9_options_and_the_unknown_instruction():
    from src.web_research import RACING_NSW_ORG_TYPE_SYSTEM, RESEARCH_SYSTEM

    for option in rvc.VALID_ORG_TYPES:
        assert option in RACING_NSW_ORG_TYPE_SYSTEM
    assert "unknown" in RACING_NSW_ORG_TYPE_SYSTEM.lower()
    # The shared production prompt is untouched by this plan.
    assert '"lv_org_type":<str>' in RESEARCH_SYSTEM


def test_racing_nsw_captured_artifact_is_unedited_and_the_override_is_recorded():
    assert len(m.ORG_TYPE_DECISIONS) == 5
    research = _load_racing_nsw_research()
    decision = m.ORG_TYPE_DECISIONS[RACING_NSW_ID]

    # The artifact is verbatim evidence: it still reads the model's original answer.
    assert research["data"]["lv_org_type"] == "regulator"
    # The decision diverges from it -- deliberately, not accidentally (was equality
    # before Task 1; now the divergence itself is the thing under test).
    assert decision["org_type"] == "governing_body_league"
    assert decision["org_type"] != research["data"]["lv_org_type"]
    # The divergence is recorded as data, not buried in prose.
    assert decision["override_of"] == research["data"]["lv_org_type"]
    assert decision["override_rationale"]


def test_resolve_racing_nsw_decision_out_of_vocabulary_routes_to_d03_marker():
    synthetic = {
        "matched": True, "confidence": 90,
        "data": {"lv_org_type": "venue"},  # not a VALID_ORG_TYPES member
        "evidence_by_field": {"lv_org_type": "https://example.org/about"},
    }
    decision = m.resolve_racing_nsw_decision(synthetic)

    # The out-of-vocabulary string itself never reaches the decision's org_type -- only
    # "unknown" (a VALID_ORG_TYPES member) is, which build_coverage_patch accepts (its own
    # out-of-vocabulary guard is exercised separately by
    # test_tracer_build_coverage_patch_rejects_out_of_vocabulary_org_type).
    assert decision["org_type"] == "unknown"
    assert decision["org_type"] in rvc.VALID_ORG_TYPES
    assert decision["reason"]


def test_resolve_racing_nsw_decision_bare_unknown_routes_to_d03_marker():
    synthetic = {
        "matched": True, "confidence": 40,
        "data": {"lv_org_type": "unknown"},
        "evidence_by_field": {},
        "evidence": {"evidence_summary": "Sources did not clearly support any option."},
    }
    decision = m.resolve_racing_nsw_decision(synthetic)

    assert decision["org_type"] == "unknown"
    assert decision["reason"]


def test_resolve_racing_nsw_decision_valid_enum_without_evidence_url_routes_to_d03_marker():
    synthetic = {
        "matched": True, "confidence": 85,
        "data": {"lv_org_type": "governing_body_league"},
        "evidence_by_field": {},  # no URL for lv_org_type specifically
    }
    decision = m.resolve_racing_nsw_decision(synthetic)

    assert decision["org_type"] == "unknown"
    assert decision["reason"]


def test_resolve_racing_nsw_decision_valid_enum_with_evidence_url_promotes():
    synthetic = {
        "matched": True, "confidence": 92,
        "data": {"lv_org_type": "governing_body_league"},
        "evidence_by_field": {"lv_org_type": "https://example.org/about"},
    }
    decision = m.resolve_racing_nsw_decision(synthetic)

    assert decision["org_type"] == "governing_body_league"
    assert "reason" not in decision
    assert decision["basis"]


def test_research_racing_nsw_calls_research_fn_with_the_enum_constrained_prompt():
    from src.web_research import RACING_NSW_ORG_TYPE_SYSTEM

    captured = {}

    def _fake_fetcher(object_type, record_id, properties):
        captured["fetch_args"] = (object_type, record_id, tuple(properties))
        return {"properties": {"name": "Racing NSW", "domain": "racingnsw.com.au"}}

    class _FakeResult:
        def model_dump(self):
            return {"provider": "claude_web", "matched": True, "data": {}}

    def _fake_research_fn(record, system_prompt=None):
        captured["record_id"] = record.id
        captured["system_prompt"] = system_prompt
        return _FakeResult()

    result = m.research_racing_nsw(fetcher=_fake_fetcher, research_fn=_fake_research_fn)

    assert captured["fetch_args"][0] == "companies"
    assert captured["fetch_args"][1] == RACING_NSW_ID
    assert captured["record_id"] == RACING_NSW_ID
    assert captured["system_prompt"] is RACING_NSW_ORG_TYPE_SYSTEM
    assert result == {"provider": "claude_web", "matched": True, "data": {}}
