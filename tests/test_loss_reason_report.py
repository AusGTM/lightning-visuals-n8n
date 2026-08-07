# tests/test_loss_reason_report.py
#
# Phase 43 Plan 03 (PIPE-04, D-04/D-05). Every test here is offline -- every fetch
# build_report() calls is stubbed, so zero network is reachable from this module. The
# headline case is the fully empty dataset (D-04's explicit "not an edge case"
# instruction): it comes first, on purpose.
import scripts.build_loss_reason_report as report_module

build_report = report_module.build_report
render_report = report_module.render_report


def test_empty_dataset_renders_zero_counts_and_exits_success():
    report, exit_code = build_report(
        probe_fn=lambda name: True,
        search_deals_fn=lambda: [],
        fetch_associations_fn=lambda deal_id: [],
        fetch_company_fn=lambda company_id: None,
    )
    assert exit_code == 0
    assert report["deals_examined"] == 0
    assert report["deals_with_reason"] == 0

    text = render_report(report)
    assert "**Closed-lost deals examined:** 0" in text
    assert "lv-icp-v0.1" in text


def test_no_filled_reasons_states_examined_count_and_none_carried_a_reason():
    deals = [
        {"id": "1", "properties": {"hs_primary_associated_company": "100"}},
        {"id": "2", "properties": {"hs_primary_associated_company": "101"}},
    ]
    report, exit_code = build_report(
        probe_fn=lambda name: True,
        search_deals_fn=lambda: deals,
        fetch_associations_fn=lambda deal_id: [],
        fetch_company_fn=lambda company_id: None,
    )
    assert exit_code == 0
    assert report["deals_examined"] == 2
    assert report["deals_with_reason"] == 0
    assert "nothing to cross-tabulate yet" in report["verdict"]
    assert report["cross_tab"] == {}


def test_property_absent_vs_present_empty_wording_differs():
    absent_report, _ = build_report(
        probe_fn=lambda name: False,
        search_deals_fn=lambda: [],
        fetch_associations_fn=lambda deal_id: [],
        fetch_company_fn=lambda company_id: None,
    )
    present_empty_report, _ = build_report(
        probe_fn=lambda name: True,
        search_deals_fn=lambda: [{"id": "1", "properties": {}}],
        fetch_associations_fn=lambda deal_id: [],
        fetch_company_fn=lambda company_id: None,
    )

    absent_text = render_report(absent_report)
    present_text = render_report(present_empty_report)

    assert "does not exist in this portal" in absent_text
    assert "does not exist in this portal" not in present_text
    assert "0% filled" in present_text


def test_populated_cross_tab_counts():
    deals = [
        {"id": "1", "properties": {"lv_closed_lost_reason": "price_affordability", "hs_primary_associated_company": "100"}},
        {"id": "2", "properties": {"lv_closed_lost_reason": "price_affordability", "hs_primary_associated_company": "101"}},
        {"id": "3", "properties": {"lv_closed_lost_reason": "cloud_fear", "hs_primary_associated_company": "100"}},
    ]
    companies = {"100": {"lv_icp_tier": "A"}, "101": {"lv_icp_tier": "B"}}

    report, exit_code = build_report(
        probe_fn=lambda name: True,
        search_deals_fn=lambda: deals,
        fetch_associations_fn=lambda deal_id: [],
        fetch_company_fn=lambda cid: companies.get(cid),
    )

    assert exit_code == 0
    assert report["cross_tab"]["price_affordability"]["A"] == 1
    assert report["cross_tab"]["price_affordability"]["B"] == 1
    assert report["cross_tab"]["cloud_fear"]["A"] == 1
    assert report["joined_primary"] == 3
    assert report["joined_fallback"] == 0
    assert report["unjoined"] == 0
    assert report["deals_with_reason"] == 3


def test_native_reason_used_when_custom_field_is_empty():
    deals = [
        {"id": "1", "properties": {"closed_lost_reason": "no budget", "hs_primary_associated_company": "100"}},
    ]
    report, exit_code = build_report(
        probe_fn=lambda name: True,
        search_deals_fn=lambda: deals,
        fetch_associations_fn=lambda deal_id: [],
        fetch_company_fn=lambda cid: {"lv_icp_tier": "C"},
    )
    assert exit_code == 0
    assert report["cross_tab"]["no budget"]["C"] == 1


def test_associations_v4_fallback_used_when_primary_property_is_empty():
    deals = [
        {"id": "1", "properties": {"lv_closed_lost_reason": "incumbent_satisfied"}},
    ]
    report, exit_code = build_report(
        probe_fn=lambda name: True,
        search_deals_fn=lambda: deals,
        fetch_associations_fn=lambda deal_id: ["200"],
        fetch_company_fn=lambda cid: {"lv_icp_tier": "B"},
    )
    assert exit_code == 0
    assert report["joined_primary"] == 0
    assert report["joined_fallback"] == 1
    assert report["unjoined"] == 0
    assert report["cross_tab"]["incumbent_satisfied"]["B"] == 1


def test_unjoinable_deal_lands_in_unknown_bucket_not_dropped():
    deals = [
        {"id": "9", "properties": {"lv_closed_lost_reason": "no_budget"}},
    ]
    report, exit_code = build_report(
        probe_fn=lambda name: True,
        search_deals_fn=lambda: deals,
        fetch_associations_fn=lambda deal_id: [],  # v4 fallback also empty -- unjoinable
        fetch_company_fn=lambda cid: None,
    )
    assert exit_code == 0
    assert report["unjoined"] == 1
    assert "9" in report["unjoined_deal_ids"]
    assert report["cross_tab"]["no_budget"]["Unknown"] == 1


def test_missing_credentials_exits_non_zero_and_prints_explicit_skip(monkeypatch, capsys):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)

    exit_code = report_module.main([])

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "skipped" in captured.out.lower()
    assert "no credentials" in captured.out.lower()
