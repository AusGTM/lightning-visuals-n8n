"""tests/test_company_propose_mode_event.py

Phase 58 Plan 02 (INPUT-02/INPUT-03) -- offline pins for the propose-mode event body and
the disarmed `--plan` path of scripts/probe_company_propose_mode.py. No network call
anywhere in this module: every test either freezes time and asserts a pure function's
return value, or injects a fake transport/config_loader that raises on any use it should
not reach.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*` imports resolve

import scripts.remediate_veto_companies as remediate  # noqa: E402
import scripts.probe_company_propose_mode as probe  # noqa: E402

COMPANY_ID = "1"

_FIXED_OCCURRED_AT_MS = 1_700_000_000_000


def _freeze_time(monkeypatch):
    monkeypatch.setattr(remediate.time, "time", lambda: _FIXED_OCCURRED_AT_MS / 1000)


# --- build_webhook_event: no existing caller's body shape moved -------------------------

def test_build_webhook_event_no_mode_no_recompute_is_byte_identical_to_before(monkeypatch):
    """The plain D-18 event this repo has always posted -- no `mode`, no `recompute`,
    no `domain` -- must stay exactly this shape (an inline expected dict), confirming
    the Phase 58 `mode` addition changed nothing for every existing caller."""
    _freeze_time(monkeypatch)

    event = remediate.build_webhook_event(COMPANY_ID)

    expected = [{
        "objectId": COMPANY_ID,
        "objectType": "company",
        "subscriptionType": "company.propertyChange",
        "propertyName": "lv_country_region_normalized",
        "occurredAt": _FIXED_OCCURRED_AT_MS,
    }]
    assert event == expected
    assert "mode" not in event[0]
    assert "recompute" not in event[0]


def test_build_webhook_event_recompute_and_mode_ride_together(monkeypatch):
    """The exact combination the probe sends: `recompute` is a real JSON boolean (`is
    True`, not `== "true"` -- Parse HubSpot Event normalizes with `=== true`), `mode` is
    the string "propose", and neither displaces the other."""
    _freeze_time(monkeypatch)

    event = remediate.build_webhook_event(COMPANY_ID, recompute=True, mode="propose")

    assert event[0]["recompute"] is True
    assert event[0]["mode"] == "propose"
    assert event[0]["objectId"] == COMPANY_ID


def test_build_webhook_event_mode_omitted_entirely_when_not_set(monkeypatch):
    _freeze_time(monkeypatch)
    assert "mode" not in remediate.build_webhook_event(COMPANY_ID)[0]
    assert "mode" not in remediate.build_webhook_event(COMPANY_ID, recompute=True)[0]


# --- post_webhook_event forwards mode unchanged ------------------------------------------

class _FakeTransport:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return _FakeResponse()


class _FakeResponse:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"ok": True}


_WEBHOOK_CONFIG = {
    "n8n_url": "https://fake-tenant.n8n.cloud/",
    "webhook_secret": "fake-secret",
}


def test_post_webhook_event_threads_mode_into_the_body():
    transport = _FakeTransport()

    remediate.post_webhook_event(
        COMPANY_ID, True, _WEBHOOK_CONFIG, transport=transport,
        recompute=True, mode="propose",
    )

    assert len(transport.calls) == 1
    body = transport.calls[0]["json"]
    assert body[0]["recompute"] is True
    assert body[0]["mode"] == "propose"


def test_post_webhook_event_omits_mode_when_not_given():
    transport = _FakeTransport()

    remediate.post_webhook_event(COMPANY_ID, True, _WEBHOOK_CONFIG, transport=transport)

    assert "mode" not in transport.calls[0]["json"][0]


# --- probe: build_probe_event -------------------------------------------------------------

def test_build_probe_event_rides_recompute_and_propose_mode_together(monkeypatch):
    _freeze_time(monkeypatch)
    event = probe.build_probe_event(COMPANY_ID)
    assert event[0]["recompute"] is True
    assert event[0]["mode"] == "propose"
    assert event[0]["objectId"] == COMPANY_ID


# --- probe: --plan makes no network call, prints the event and target -------------------

def _refuse_any_call(*_a, **_kw):
    raise AssertionError("no network call should be made in --plan mode")


class _RefusingTransport:
    def post(self, *_a, **_kw):
        _refuse_any_call()

    def get(self, *_a, **_kw):
        _refuse_any_call()


def test_probe_plan_mode_exits_zero_prints_event_and_makes_no_network_call(capsys):
    exit_code = probe.main(
        ["--plan"],
        config_loader=lambda: dict(_WEBHOOK_CONFIG),
        poster=_refuse_any_call,
        observer=_refuse_any_call,
        transport=_RefusingTransport(),
    )
    assert exit_code == 0

    out = capsys.readouterr().out
    assert "event body" in out
    assert "target url" in out
    assert probe.TARGET_COMPANY_ID in out
    assert "propose" in out


def test_probe_plan_mode_handles_an_unloadable_config_without_crashing(capsys):
    def _raise_config_error():
        raise probe.config_gate.ConfigError("no config file")

    exit_code = probe.main(
        ["--plan"],
        config_loader=_raise_config_error,
        poster=_refuse_any_call,
        observer=_refuse_any_call,
    )
    assert exit_code == 0
    assert "unresolvable" in capsys.readouterr().out


# --- probe: --execute reuses remediate_veto_companies.post_webhook_event, unchanged ------

def test_probe_default_poster_is_remediate_veto_companies_post_webhook_event():
    """Assert by reference, not by reading prose: the probe's live path is the SAME
    function object this repo already uses for every other webhook dispatch -- no second
    transport was written."""
    import inspect
    sig = inspect.signature(probe.main)
    assert sig.parameters["poster"].default is remediate.post_webhook_event


def test_probe_execute_without_arming_refuses_before_any_network_call(monkeypatch):
    """`--execute` with ALLOW_VETO_REMEDIATION unset must hit NotArmedError inside the
    real post_webhook_event -- before transport.post is ever called."""
    exit_code = probe.main(
        ["--execute"],
        config_loader=lambda: dict(_WEBHOOK_CONFIG),
        transport=_RefusingTransport(),
        env={},
    )
    assert exit_code == 1


def test_probe_execute_refuses_when_config_is_unloadable():
    def _raise_config_error():
        raise probe.config_gate.ConfigError("no config file")

    exit_code = probe.main(
        ["--execute"],
        config_loader=_raise_config_error,
        env={"ALLOW_VETO_REMEDIATION": "true"},
    )
    assert exit_code == 1


# --- probe: mutually exclusive flags -------------------------------------------------------

def test_probe_requires_exactly_one_of_plan_or_execute():
    with pytest.raises(SystemExit):
        probe.main([])
    with pytest.raises(SystemExit):
        probe.main(["--plan", "--execute"])
