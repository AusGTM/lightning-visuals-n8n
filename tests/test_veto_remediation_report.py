"""tests/test_veto_remediation_report.py

Phase 47 Plan 03 (VETO-01, COVER-01, COVER-02) -- offline tests for
scripts/veto_remediation_report.py. No network calls anywhere in this module -- every
test either monkeypatches requests.post to raise, injects a fake reader/lister, or
exercises pure functions.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*` imports resolve

import scripts.veto_remediation_report as m  # noqa: E402
import scripts.remediate_veto_companies as rvc  # noqa: E402

PINNED_ID = "9604732797"  # Tweed Valley Jockey Club -- first in PINNED_COMPANY_ID_ORDER
SECOND_PINNED_ID = "9604794661"  # Sapphire Coast Turf Club (Bega Valley)


def _refuse_network(*_a, **_kw):
    raise AssertionError("no network call should be made in this test")


_ROW_TEMPLATE = {
    "name": None,
    "lv_org_type": None,
    "lv_produces_content": None,
    "lv_country_region_normalized": None,
    "lv_icp_fit_score": None,
    "lv_icp_tier": None,
    "lv_anti_icp_flag": None,
    "lv_anti_icp_reason": None,
}


def _row(company_id, **overrides):
    row = {"id": company_id, **_ROW_TEMPLATE}
    row.update(overrides)
    return row


# --- Task 1: snapshot / predict / diff / classify ------------------------------------------

def test_snapshot_is_pure_read_and_completes_with_requests_post_raising(monkeypatch):
    monkeypatch.setattr("requests.post", _refuse_network)

    def _fake_reader(object_type, record_id, properties):
        assert object_type == "companies"
        return {"id": record_id, "properties": {p: f"{record_id}-{p}" for p in properties}}

    rows = m.snapshot([PINNED_ID], reader=_fake_reader)

    assert len(rows) == 1
    assert rows[0]["id"] == PINNED_ID
    for prop in m.OBSERVED_PROPS:
        assert rows[0][prop] == f"{PINNED_ID}-{prop}"


def test_snapshot_returns_rows_in_pinned_id_order_regardless_of_input_order():
    def _fake_reader(object_type, record_id, properties):
        return {"id": record_id, "properties": {}}

    # SECOND_PINNED_ID comes after PINNED_ID in PINNED_COMPANY_ID_ORDER -- passed reversed.
    rows = m.snapshot([SECOND_PINNED_ID, PINNED_ID], reader=_fake_reader)

    assert [r["id"] for r in rows] == [PINNED_ID, SECOND_PINNED_ID]


def test_snapshot_carries_all_eight_observed_keys_plus_id():
    def _fake_reader(object_type, record_id, properties):
        return {"id": record_id, "properties": {}}

    rows = m.snapshot([PINNED_ID], reader=_fake_reader)

    assert len(m.OBSERVED_PROPS) == 8
    assert set(rows[0].keys()) == set(m.OBSERVED_PROPS) | {"id"}


def test_predict_computes_score_and_tier_via_expected_score_and_tier():
    row = _row(PINNED_ID)
    candidate_inputs = {
        "lv_org_type": "governing_body_league",
        "lv_produces_content": True,
        "lv_country_region_normalized": "AU",
    }

    score, tier = m.predict(row, candidate_inputs)

    assert (score, tier) == (70, "A")


def test_classify_cleared_when_flag_not_true():
    row = _row(PINNED_ID, lv_anti_icp_flag="false", lv_anti_icp_reason="")
    assert m.classify(row) == "cleared"


def test_classify_still_non_anz_when_reason_contains_non_anz_reason():
    row = _row(PINNED_ID, lv_anti_icp_flag="true", lv_anti_icp_reason="Non-ANZ geography")
    assert m.classify(row) == "still_non_anz"


def test_classify_residual_other_veto_when_reason_is_a_different_hard_veto():
    row = _row(
        "18047161864", lv_anti_icp_flag="true",
        lv_anti_icp_reason="Hardware/AV/LED vendor, not sports-media buyer",
    )
    assert m.classify(row) == "residual_other_veto"


def test_classify_correct_non_anz_for_the_d23_true_veto_record():
    # D-23: Jam TV 17317850381 is the Italian broadcaster jamtv.it. Its non-ANZ veto is
    # CORRECT and Phase 47 preserved it deliberately. Protective intent: without this
    # exemption, `--mode after` REFUSES on the one record required to be in exactly this
    # state, reporting a false failure to anyone re-running the report after Phase 47.
    row = _row("17317850381", lv_anti_icp_flag="true", lv_anti_icp_reason="Non-ANZ geography")
    assert m.classify(row) == "correct_non_anz"


def test_classify_d23_exemption_is_keyed_by_id_not_by_reason_text():
    # Protective intent: the exemption must NOT generalise. Any OTHER record carrying the
    # same reason string is still a real failure -- that is the whole bar of VETO-01.
    row = _row("9604732797", lv_anti_icp_flag="true", lv_anti_icp_reason="Non-ANZ geography")
    assert m.classify(row) == "still_non_anz"


def test_classify_still_non_anz_wins_when_reason_carries_both_vetoes():
    # A record can carry multiple simultaneous vetoes joined with "; " -- the non-ANZ
    # substring anywhere in the joined string is still a failing classification.
    row = _row(
        PINNED_ID, lv_anti_icp_flag="true",
        lv_anti_icp_reason="Hardware/AV/LED vendor, not sports-media buyer; Non-ANZ geography",
    )
    assert m.classify(row) == "still_non_anz"


def test_diff_reports_id_present_on_only_one_side_rather_than_dropping_it():
    before_rows = [_row(PINNED_ID), _row(SECOND_PINNED_ID)]
    after_rows = [_row(PINNED_ID, lv_anti_icp_flag="false", lv_anti_icp_reason="")]

    result = m.diff(before_rows, after_rows)

    assert SECOND_PINNED_ID in result
    assert result[SECOND_PINNED_ID]["present_before"] is True
    assert result[SECOND_PINNED_ID]["present_after"] is False
    assert result[SECOND_PINNED_ID]["classification"] is None


def test_diff_reports_changed_properties_and_classification_for_a_cleared_record():
    before_rows = [_row(
        PINNED_ID, lv_org_type=None, lv_icp_tier="D",
        lv_anti_icp_flag="true", lv_anti_icp_reason="Non-ANZ geography",
    )]
    after_rows = [_row(
        PINNED_ID, lv_org_type="individual_club_team", lv_icp_tier="C",
        lv_anti_icp_flag="false", lv_anti_icp_reason="",
    )]

    result = m.diff(before_rows, after_rows)

    assert result[PINNED_ID]["present_before"] is True
    assert result[PINNED_ID]["present_after"] is True
    assert result[PINNED_ID]["classification"] == "cleared"
    assert "lv_org_type" in result[PINNED_ID]["changed"]
    assert "lv_icp_tier" in result[PINNED_ID]["changed"]
    assert "name" not in result[PINNED_ID]["changed"]  # unchanged (both None)


def test_report_script_imports_no_write_helper():
    tree = ast.parse((ROOT / "scripts" / "veto_remediation_report.py").read_text())
    names = {
        a.name
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and (n.module or "").endswith("hubspot_client")
        for a in n.names
    }
    assert names <= {"get_record", "search_records"}, names


# --- Task 2: live property-existence guard --------------------------------------------------

def test_missing_property_names_returns_both_absent_sorted():
    live_names = {"lv_org_type", "lv_produces_content"}
    payload_keys = {"lv_org_type", "lv_produces_content", "lv_org_type_source", "lv_new_field"}

    missing = m.missing_property_names(payload_keys, live_names)

    assert missing == ["lv_new_field", "lv_org_type_source"]


def test_missing_property_names_empty_when_fully_covered():
    live_names = {"a", "b", "c"}
    payload_keys = {"a", "b"}

    assert m.missing_property_names(payload_keys, live_names) == []


def test_live_property_names_delegates_to_injected_lister_and_returns_name_set():
    def _fake_lister(object_type):
        assert object_type == "companies"
        return [{"name": "lv_org_type"}, {"name": "lv_produces_content"}]

    names = m.live_property_names("companies", lister=_fake_lister)

    assert names == {"lv_org_type", "lv_produces_content"}


def test_checked_name_set_includes_derived_read_only_fields_and_veto_03_search_names():
    # The four derived read-only fields (never written, always read) plus the two
    # VETO-03 acceptance-search property names -- all must be inside OBSERVED_PROPS.
    derived = {"lv_icp_fit_score", "lv_icp_tier", "lv_anti_icp_flag", "lv_anti_icp_reason"}
    veto_03_search_names = {"lv_anti_icp_reason", "lv_country_region_normalized"}

    assert derived <= set(m.OBSERVED_PROPS)
    assert veto_03_search_names <= set(m.OBSERVED_PROPS)


def test_d21_narrows_metadata_patch_to_only_the_two_live_stamp_keys():
    # D-21 (Amendment 2026-08-12): Task 2's live guard found 19 of the 21 D-09 stamp
    # names absent from the portal. build_metadata_patch -- the function whose output
    # feeds the guard's checked payload-key set -- must emit ONLY the two that exist.
    assert rvc.LIVE_METADATA_STAMP_KEYS == ("lv_org_type_verified_at", "lv_produces_content_verified_at")

    class _Result:
        provider = "claude_web"
        confidence = 88
        evidence_by_field = {}
        evidence = None

    patch = rvc.build_metadata_patch("999", _Result(), list(rvc.INPUT_PROPS))

    assert set(patch["properties"].keys()) == set(rvc.LIVE_METADATA_STAMP_KEYS)


def test_d21_metadata_record_keeps_the_full_seven_suffix_trail():
    # The full trail is not dropped -- it moves to build_metadata_record, which is
    # never PATCHed (never passed to the property guard or batch_update_companies).
    from src.schemas import ProviderEvidence, ProviderResult

    result = ProviderResult(
        provider="claude_web", object_type="companies", matched=True, confidence=88,
        data={}, evidence=ProviderEvidence(evidence_urls=["https://a.example"]),
    )

    record = rvc.build_metadata_record("999", result, ["lv_org_type"])

    expected_keys = {f"lv_org_type{suffix}" for suffix in rvc.METADATA_SUFFIXES}
    assert set(record["properties"].keys()) == expected_keys
    assert len(expected_keys) == 7


def test_remediate_main_with_fake_lister_missing_one_stamp_refuses_and_calls_no_write(monkeypatch):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", rvc.EXPECTED_PORTAL_ID)
    monkeypatch.setenv("USE_MOCK_WEB_RESEARCH", "true")
    monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.delenv("ALLOW_VETO_REMEDIATION", raising=False)
    monkeypatch.setenv("VETO_MAX_RECORDS", "1")

    def _fake_get_record(object_type, record_id, properties):
        return {"id": record_id, "properties": {
            "name": "Tweed Valley Jockey Club", "domain": "tvjc.example",
            "website": "https://tvjc.example", "country": "Australia", "industry": "Sports",
        }}

    monkeypatch.setattr(rvc, "get_record", _fake_get_record)
    monkeypatch.setattr("requests.post", _refuse_network)
    monkeypatch.setattr("requests.get", _refuse_network)

    # D-21: the guard only ever checks the NARROWED metadata stamp set
    # (rvc.LIVE_METADATA_STAMP_KEYS -- 2 keys, not the full 21). A lister missing one of
    # those two is the "missing one stamp" case now.
    almost_everything = (
        {"name", "domain", "website", "country", "industry"}
        | set(rvc.INPUT_PROPS)
        | (set(rvc.LIVE_METADATA_STAMP_KEYS) - {"lv_org_type_verified_at"})
        | {"org_type_score", "geography_score", "annual_revenue_score",
           "produces_content_score", "gambling_score"}
        | set(rvc.FORBIDDEN_PROPS)
    )

    def _fake_lister(object_type):
        return [{"name": n} for n in sorted(almost_everything)]

    monkeypatch.setattr(rvc, "_live_property_lister", _fake_lister)

    write_calls = []
    monkeypatch.setattr(rvc, "batch_update_companies", lambda *a, **kw: write_calls.append((a, kw)))

    exit_code = rvc.main(["--company-id", PINNED_ID])

    assert exit_code != 0
    assert write_calls == []


def test_remediate_main_with_fake_lister_covering_everything_proceeds(monkeypatch):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", rvc.EXPECTED_PORTAL_ID)
    monkeypatch.setenv("USE_MOCK_WEB_RESEARCH", "true")
    monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.delenv("ALLOW_VETO_REMEDIATION", raising=False)
    monkeypatch.setenv("VETO_MAX_RECORDS", "1")

    def _fake_get_record(object_type, record_id, properties):
        return {"id": record_id, "properties": {
            "name": "Tweed Valley Jockey Club", "domain": "tvjc.example",
            "website": "https://tvjc.example", "country": "Australia", "industry": "Sports",
        }}

    monkeypatch.setattr(rvc, "get_record", _fake_get_record)
    monkeypatch.setattr("requests.post", _refuse_network)
    monkeypatch.setattr("requests.get", _refuse_network)

    everything = (
        {"name", "domain", "website", "country", "industry"}
        | set(rvc.INPUT_PROPS)
        | set(rvc.LIVE_METADATA_STAMP_KEYS)
        | {"org_type_score", "geography_score", "annual_revenue_score",
           "produces_content_score", "gambling_score"}
        | set(rvc.FORBIDDEN_PROPS)
    )

    monkeypatch.setattr(rvc, "_live_property_lister", lambda object_type: [{"name": n} for n in sorted(everything)])

    exit_code = rvc.main(["--company-id", PINNED_ID])

    assert exit_code == 0
