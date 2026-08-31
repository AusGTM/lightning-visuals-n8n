"""Tests for `scripts/prove_zoominfo_balance.py` — Phase 57 Plan 04 Task 1 (T-57-19a).

The point of every test here is that the gate's TEXT existing is not the same claim as
the gate actually running before transport construction. A static AST or string check
proves the former; only counting calls on an injected transport double proves the latter
(REVIEW-57-M7). Every test in this module runs under `conftest.py`'s autouse `no_network`
fixture too, so a real `requests.post` slipping through would fail loudly rather than
silently succeed.
"""
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
ROOT = PLUGIN_ROOT.parent
ROOT_SCRIPTS_DIR = ROOT / "scripts"
if str(ROOT_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_SCRIPTS_DIR))

import prove_zoominfo_balance  # noqa: E402

FAKE_CONFIG = {
    "n8n_url": "https://fake-tenant.n8n.cloud",
    "webhook_secret": "fake-secret-for-tests-only",
}


def _zoominfo_row(**overrides):
    row = {"provider": "zoominfo", "configured": True, "credits": None,
           "unreadable": True, "error": "provider_error", "status": None}
    row.update(overrides)
    return row


def _lusha_row(credits):
    return {"provider": "lusha", "configured": True, "credits": credits,
            "unreadable": False, "error": None, "status": 200}


def _status_body(*, lusha_credits, zoominfo_row):
    return {"balances": [_lusha_row(lusha_credits), zoominfo_row],
            "checked_at": "2026-08-31T00:00:00Z"}


@pytest.fixture(autouse=True)
def _clear_gate_env(monkeypatch):
    """Every test starts from a clean gate — no ambient .env leaking a real 'true' or a
    real N8N_URL into an assertion about refusal."""
    monkeypatch.delenv("ALLOW_ZOOMINFO_BALANCE_PROBE", raising=False)
    monkeypatch.delenv("N8N_URL", raising=False)
    monkeypatch.delenv("N8N_EXPECTED_URL", raising=False)


# --------------------------------------------------------------- gate-off: zero calls


def test_gate_absent_issues_zero_calls_and_writes_no_verdict(
    stub_post_transport_factory, tmp_path,
):
    transport = stub_post_transport_factory()
    verdict_path = tmp_path / "verdict.json"

    result = prove_zoominfo_balance.probe_zoominfo_balance(
        transport=transport, config=FAKE_CONFIG, verdict_path=verdict_path,
    )

    assert transport.calls == []
    assert result.get("refused") is True
    assert not verdict_path.exists()


@pytest.mark.parametrize("value", ["True", "TRUE", "1", "yes", "false"])
def test_gate_truthy_non_exact_string_issues_zero_calls(
    value, monkeypatch, stub_post_transport_factory, tmp_path,
):
    monkeypatch.setenv("ALLOW_ZOOMINFO_BALANCE_PROBE", value)
    monkeypatch.setenv("N8N_URL", "https://fake-tenant.n8n.cloud")
    transport = stub_post_transport_factory()
    verdict_path = tmp_path / "verdict.json"

    result = prove_zoominfo_balance.probe_zoominfo_balance(
        transport=transport, config=FAKE_CONFIG, verdict_path=verdict_path,
    )

    assert transport.calls == []
    assert result.get("refused") is True
    assert not verdict_path.exists()


def test_wrong_instance_issues_zero_calls(
    monkeypatch, stub_post_transport_factory, tmp_path,
):
    monkeypatch.setenv("ALLOW_ZOOMINFO_BALANCE_PROBE", "true")
    monkeypatch.setenv("N8N_URL", "https://evil.example.com")
    transport = stub_post_transport_factory()
    verdict_path = tmp_path / "verdict.json"

    result = prove_zoominfo_balance.probe_zoominfo_balance(
        transport=transport, config=FAKE_CONFIG, verdict_path=verdict_path,
    )

    assert transport.calls == []
    assert result.get("refused") is True
    assert not verdict_path.exists()


# ------------------------------------------------------- gate-on: exactly two calls


def test_gate_on_recognised_instance_issues_exactly_two_calls_and_writes_verdict(
    monkeypatch, stub_post_transport_factory, tmp_path,
):
    monkeypatch.setenv("ALLOW_ZOOMINFO_BALANCE_PROBE", "true")
    monkeypatch.setenv("N8N_URL", "https://fake-tenant.n8n.cloud")

    body1 = _status_body(lusha_credits=500, zoominfo_row=_zoominfo_row())
    body2 = _status_body(lusha_credits=500, zoominfo_row=_zoominfo_row())
    transport = stub_post_transport_factory([body1, body2])
    verdict_path = tmp_path / "verdict.json"

    verdict = prove_zoominfo_balance.probe_zoominfo_balance(
        transport=transport, config=FAKE_CONFIG, verdict_path=verdict_path,
    )

    assert len(transport.calls) == 2
    hosts = {urlparse(call["url"]).netloc for call in transport.calls}
    assert hosts == {"fake-tenant.n8n.cloud"}

    assert verdict["verdict"] == "provider_error"
    assert verdict["lusha_before"] == 500
    assert verdict["lusha_after"] == 500
    assert verdict["lusha_delta"] == 0
    assert verdict["lusha_after_cost_unmeasured"] is True
    assert verdict_path.exists()


def test_gate_on_readable_zoominfo_balance_yields_readable_verdict(
    monkeypatch, stub_post_transport_factory, tmp_path,
):
    monkeypatch.setenv("ALLOW_ZOOMINFO_BALANCE_PROBE", "true")
    monkeypatch.setenv("N8N_URL", "https://fake-tenant.n8n.cloud")

    readable_row = _zoominfo_row(credits=1580, unreadable=False, error=None, status=200)
    body1 = _status_body(lusha_credits=500, zoominfo_row=readable_row)
    body2 = _status_body(lusha_credits=498, zoominfo_row=readable_row)
    transport = stub_post_transport_factory([body1, body2])
    verdict_path = tmp_path / "verdict.json"

    verdict = prove_zoominfo_balance.probe_zoominfo_balance(
        transport=transport, config=FAKE_CONFIG, verdict_path=verdict_path,
    )

    assert len(transport.calls) == 2
    assert verdict["verdict"] == "readable"
    assert verdict["zoominfo_raw_credits"] == 1580
    assert verdict["lusha_before"] == 500
    assert verdict["lusha_after"] == 498
    assert verdict["lusha_delta"] == -2


def test_gate_on_unrecognized_response_shape_is_distinguished_from_provider_error(
    monkeypatch, stub_post_transport_factory, tmp_path,
):
    monkeypatch.setenv("ALLOW_ZOOMINFO_BALANCE_PROBE", "true")
    monkeypatch.setenv("N8N_URL", "https://fake-tenant.n8n.cloud")

    shape_row = _zoominfo_row(error="unrecognized_response_shape", status=200)
    body1 = _status_body(lusha_credits=500, zoominfo_row=shape_row)
    body2 = _status_body(lusha_credits=500, zoominfo_row=shape_row)
    transport = stub_post_transport_factory([body1, body2])
    verdict_path = tmp_path / "verdict.json"

    verdict = prove_zoominfo_balance.probe_zoominfo_balance(
        transport=transport, config=FAKE_CONFIG, verdict_path=verdict_path,
    )

    assert verdict["verdict"] == "unrecognized_response_shape"
    assert verdict["verdict"] != "provider_error"
