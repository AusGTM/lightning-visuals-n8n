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


def test_tracer_racing_nsw_has_no_decision_yet_raises_pending_research():
    with pytest.raises(m.PendingResearch):
        m.decide_org_type(RACING_NSW_ID, None)


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


def test_marker_racing_nsw_still_pending_research():
    with pytest.raises(m.PendingResearch):
        m.decide_org_type(RACING_NSW_ID, None)


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
