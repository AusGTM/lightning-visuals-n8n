# tests/test_zoominfo_company_client.py
#
# Phase 51 Plan 01 -- offline, mocked tests for scripts/zoominfo_company_client.py. Plain
# pytest, plain asserts, no classes/fixtures (matches tests/test_icp_scoring.py's style).
from scripts import zoominfo_company_client as z


def test_revenue_thousands_to_dollars():
    # Mirrors tests/n8n/enrichment.test.mjs's own THOUSANDS pin (Racing NSW / FanDuel) so
    # the two pins cross-check by inspection: revenue 268163 (thousands) == $268.163m,
    # banding "50-500M"; revenue 14050000 (thousands) == $14.05b, banding "1.2B+".
    assert z.zoominfo_revenue_to_dollars(268163) == 268163000
    assert z.zoominfo_revenue_band({"revenue": 268163}) == "50-500M"
    assert z.zoominfo_revenue_band({"revenue": 14050000}) == "1.2B+"


def test_revenue_band_edges_inclusive_lower():
    # Band cut points against src/normalizer.py's real dollar thresholds: a value
    # exactly on a cut point lands in the HIGHER band, since that's the case where a
    # thousand-fold unit error is invisible.
    assert z.zoominfo_revenue_band({"revenue": 5000}) == "5-50M"
    assert z.zoominfo_revenue_band({"revenue": 4999}) == "1-5M"
    assert z.zoominfo_revenue_band({"revenue": 50000}) == "50-500M"
    assert z.zoominfo_revenue_band({"revenue": 49999}) == "5-50M"


def test_revenue_band_empty_and_zero():
    assert z.zoominfo_revenue_band({}) is None
    assert z.zoominfo_revenue_band({"revenue": 0}) is None
    assert z.zoominfo_revenue_band({"revenue": None}) is None
    assert z.zoominfo_revenue_band({"revenue": "not-a-number"}) is None

    # Divergence guard: src.normalizer.normalize_revenue_band(0) is NOT None -- it bands
    # the lowest real band -- which is exactly why an unguarded zero must never reach it.
    from src.normalizer import normalize_revenue_band
    assert normalize_revenue_band(0) == "<1M"


def test_revenue_range_precedence():
    with_range = {"revenueRange": "$250 mil. - $500 mil.", "revenue": 268163}
    without_range = {"revenue": 268163}
    assert z.zoominfo_revenue_band(with_range) == "50-500M"
    assert z.zoominfo_revenue_band(without_range) == "50-500M"
    # Identical inputs always yield an identical band.
    assert z.zoominfo_revenue_band(with_range) == z.zoominfo_revenue_band(dict(with_range))


def test_country_region_blank_is_none():
    # This is the test that would have caught the false-veto bug.
    assert z.zoominfo_country_region("") is None
    assert z.zoominfo_country_region("   ") is None
    assert z.zoominfo_country_region(None) is None
    assert z.zoominfo_country_region("Australia") == "AU"
    assert z.zoominfo_country_region("United States") == "Other"

    # Companion: a candidate patch built from a blank-country match omits the region
    # key entirely, and compute_icp_score on that patch does NOT set anti_icp_flag.
    from scripts.backfill_dry_run import build_candidate_patch
    from src.icp_scoring import compute_icp_score
    from src.schemas import HubSpotRecord

    patch, conflict = build_candidate_patch({"country": "", "revenue": 268163})
    assert "lv_country_region_normalized" not in patch
    assert conflict is None

    record = HubSpotRecord(object_type="companies", id="999", properties={})
    result = compute_icp_score(record, patch)
    assert result.anti_icp_flag is False


def test_enrich_company_malformed_response_is_unmatched(monkeypatch):
    import requests

    class FakeResp:
        def __init__(self, ok=True, status_code=200, body=None):
            self.ok = ok
            self.status_code = status_code
            self._body = body

        def json(self):
            return self._body

    def make_post(response=None, raise_exc=None):
        def _post(url, json=None, headers=None, timeout=None):
            if raise_exc:
                raise raise_exc
            return response
        return _post

    # non-dict body
    monkeypatch.setattr(requests, "post", make_post(FakeResp(body="not a dict")))
    r = z.enrich_company("example.com", "tok")
    assert r["matched"] is False and r["reason"]

    # data is an empty list
    monkeypatch.setattr(requests, "post", make_post(FakeResp(body={"data": []})))
    r = z.enrich_company("example.com", "tok")
    assert r["matched"] is False and r["reason"]

    # first entry has type NoMatch
    monkeypatch.setattr(requests, "post", make_post(FakeResp(body={"data": [{"type": "NoMatch"}]})))
    r = z.enrich_company("example.com", "tok")
    assert r["matched"] is False and r["reason"] == "no_match"

    # the call raises
    monkeypatch.setattr(requests, "post", make_post(raise_exc=ConnectionError("boom")))
    r = z.enrich_company("example.com", "tok")
    assert r["matched"] is False and r["reason"] == "ConnectionError"
