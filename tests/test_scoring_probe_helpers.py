"""tests/test_scoring_probe_helpers.py

Phase 39 Task 3 — pure-function unit tests for the disarmed-by-default
availability probe (scripts/probe_scoring_tool_availability.py). No network calls:
classifier tests exercise fixture dicts; the two main() tests assert the
credential/portal gates refuse before any requests.get is reached.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*` imports resolve

from scripts.probe_scoring_tool_availability import (  # noqa: E402
    classify_account_info,
    find_score_properties,
    main,
)
from src.hubspot_client import delete_record  # noqa: E402


def test_classify_account_info_documented_shape_has_no_tier_field():
    body = {
        "portalId": 22617666,
        "accountType": "STANDARD",
        "timeZone": "Australia/Sydney",
        "companyCurrency": "AUD",
        "uiDomain": "app-ap1.hubspot.com",
        "dataHostingLocation": "ap1",
    }
    result = classify_account_info(body)
    assert result["has_tier_field"] is False
    assert result["portal_id"] == 22617666
    assert result["ui_domain"] == "app-ap1.hubspot.com"
    assert result["data_hosting_location"] == "ap1"


def test_classify_account_info_detects_tier_field_when_present():
    # The negative finding above must be a measurement, not a classifier that can
    # only ever say False — this fixture proves the True branch is reachable.
    body = {"portalId": 22617666, "hubTier": "professional"}
    result = classify_account_info(body)
    assert result["has_tier_field"] is True


def test_classify_account_info_empty_body_does_not_raise():
    result = classify_account_info({})
    assert result["has_tier_field"] is False
    assert result["portal_id"] is None


def test_find_score_properties_filters_by_field_type():
    results = [
        {"name": "a", "fieldType": "text"},
        {"name": "b", "fieldType": "calculation_score"},
    ]
    assert find_score_properties(results) == [{"name": "b", "fieldType": "calculation_score"}]


def test_find_score_properties_empty_list():
    assert find_score_properties([]) == []


def test_main_no_token_skips_and_makes_no_http_call(monkeypatch, capsys):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)

    def _fail(*a, **kw):
        raise AssertionError("no HTTP call should be made")

    monkeypatch.setattr("requests.get", _fail)
    assert main() == 0
    assert "skipped" in capsys.readouterr().out


def test_main_wrong_portal_refuses_and_makes_no_http_call(monkeypatch, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "99999999")

    def _fail(*a, **kw):
        raise AssertionError("no HTTP call should be made")

    monkeypatch.setattr("requests.get", _fail)
    assert main() == 1
    assert "REFUSED" in capsys.readouterr().out


# --- Phase 39 Plan 03 Task 1: delete_record() -----------------------------------------

def test_delete_record_dry_run_default_makes_no_network_call_and_prints_no_auth(monkeypatch, capsys):
    def _fail(*a, **kw):
        raise AssertionError("no HTTP call should be made in dry-run")

    monkeypatch.setattr("requests.delete", _fail)
    result = delete_record("companies", "789")  # dry_run defaults to True
    out = capsys.readouterr().out
    assert result == {"dry_run": True}
    assert '"method": "DELETE"' in out
    assert "https://api.hubapi.com/crm/v3/objects/companies/789" in out
    assert "Authorization" not in out
    assert "Bearer" not in out


def test_delete_record_dry_run_explicit_true_matches_default(monkeypatch, capsys):
    def _fail(*a, **kw):
        raise AssertionError("no HTTP call should be made in dry-run")

    monkeypatch.setattr("requests.delete", _fail)
    result = delete_record("companies", "789", dry_run=True)
    assert result == {"dry_run": True}


def test_delete_record_live_calls_requests_delete_and_returns_response(monkeypatch):
    calls = {}

    class _FakeResponse:
        status_code = 204

        def raise_for_status(self):
            pass

    def _fake_delete(url, headers=None, timeout=None):
        calls["url"] = url
        calls["headers"] = headers
        calls["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr("requests.delete", _fake_delete)
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")

    response = delete_record("companies", "789", dry_run=False)
    assert calls["url"] == "https://api.hubapi.com/crm/v3/objects/companies/789"
    assert response.status_code == 204
