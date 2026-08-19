# tests/test_backfill_dry_run.py
#
# Phase 51 Plan 01 -- offline, mocked tests for scripts/backfill_dry_run.py. Plain
# pytest, plain asserts, no classes/fixtures beyond plain helper functions (matches
# tests/test_icp_scoring.py's style). No live HubSpot or ZoomInfo call happens in this
# suite -- every network-touching function is monkeypatched.
from scripts import backfill_dry_run as b


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
