# tests/test_june_run_arm.py
#
# Phase 41 Plan 02 Task 3 (D-06/F3) — offline coverage for scripts/june_run_arm.py.
# n8n_arming, config_gate and executions_client are all monkeypatched; no test touches
# a real n8n or HubSpot endpoint.
import sys
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
PLUGIN_SCRIPTS = ROOT / "operator-claude-plugin" / "scripts"
if str(PLUGIN_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SCRIPTS))

import config_gate  # noqa: E402
import executions_client  # noqa: E402
import n8n_arming  # noqa: E402

import scripts.june_run_arm as june_run_arm  # noqa: E402

FAKE_CONFIG = {"n8n_url": "https://fake-tenant.n8n.cloud", "n8n_api_key": "fake-key"}
FAKE_WORKFLOW_ID = "wf-enrichment-cloud"


@pytest.fixture(autouse=True)
def _stub_config(monkeypatch):
    monkeypatch.setattr(config_gate, "load_config", lambda *a, **kw: dict(FAKE_CONFIG))


@pytest.fixture
def _stub_resolve(monkeypatch):
    monkeypatch.setattr(
        executions_client, "resolve_workflow_id",
        lambda cfg, workflow_name=None, **kw: FAKE_WORKFLOW_ID,
    )


# --------------------------------------------------------------------------------------
# Arm mode
# --------------------------------------------------------------------------------------

def test_arm_calls_arm_for_dispatch_once_with_scoped_arguments(monkeypatch, _stub_resolve):
    calls = []

    def _fake_arm_for_dispatch(workflow_id, record_ids, record_domains, allow_create, config):
        calls.append({
            "workflow_id": workflow_id, "record_ids": record_ids,
            "record_domains": record_domains, "allow_create": allow_create,
        })
        return {"outcome": n8n_arming.ARMED, "record_ids": record_ids}

    monkeypatch.setattr(n8n_arming, "arm_for_dispatch", _fake_arm_for_dispatch)
    monkeypatch.setattr(n8n_arming, "armed_window", None)  # never touched -- see assertion below
    monkeypatch.setattr(n8n_arming, "disarm", None)

    outcome = june_run_arm.arm("111, 222 ,333")

    assert outcome["outcome"] == n8n_arming.ARMED
    assert len(calls) == 1
    assert calls[0] == {
        "workflow_id": FAKE_WORKFLOW_ID,
        "record_ids": ["111", "222", "333"],
        "record_domains": [],
        "allow_create": False,
    }


def test_arm_never_touches_armed_window_or_disarm(monkeypatch, _stub_resolve):
    monkeypatch.setattr(
        n8n_arming, "arm_for_dispatch",
        lambda *a, **kw: {"outcome": n8n_arming.ARMED},
    )

    def _boom(*a, **kw):
        raise AssertionError("must not be called by arm mode")

    monkeypatch.setattr(n8n_arming, "armed_window", _boom)
    monkeypatch.setattr(n8n_arming, "disarm", _boom)

    outcome = june_run_arm.arm("111")

    assert outcome["outcome"] == n8n_arming.ARMED


def test_ids_string_with_no_ids_refuses_without_calling_arm_for_dispatch(monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("arm_for_dispatch must not be called for an empty allowlist")

    monkeypatch.setattr(n8n_arming, "arm_for_dispatch", _boom)

    outcome = june_run_arm.arm("")

    assert outcome["outcome"] == "refused"
    assert "empty" in outcome["detail"].lower()


def test_unresolvable_workflow_name_refuses_without_calling_arm_for_dispatch(monkeypatch):
    monkeypatch.setattr(
        executions_client, "resolve_workflow_id",
        lambda cfg, workflow_name=None, **kw: None,
    )

    def _boom(*a, **kw):
        raise AssertionError("arm_for_dispatch must not be called for an unresolvable name")

    monkeypatch.setattr(n8n_arming, "arm_for_dispatch", _boom)

    outcome = june_run_arm.arm("111", workflow_name="Nonexistent Workflow")

    assert outcome["outcome"] == "refused"
    assert "no workflow named" in outcome["detail"].lower()


def test_arm_mode_exits_non_zero_with_allow_n8n_arm_absent_and_zero_transport_calls(
    monkeypatch, _stub_resolve,
):
    """ALLOW_N8N_ARM is left absent and n8n_arming.arm_for_dispatch runs for REAL (not
    monkeypatched) so its own `_arm_gate()` -- the library's single source of truth for
    this kill switch, never duplicated in the wrapper -- is what actually fires the
    refusal. requests.get/requests.post are patched to fail the test if either is ever
    invoked, proving the refusal costs zero HTTP calls."""
    monkeypatch.delenv("ALLOW_N8N_ARM", raising=False)

    calls = []

    def _record_get(*a, **kw):
        calls.append(("get", a, kw))
        raise AssertionError("no HTTP call is permitted when ALLOW_N8N_ARM is absent")

    def _record_post(*a, **kw):
        calls.append(("post", a, kw))
        raise AssertionError("no HTTP call is permitted when ALLOW_N8N_ARM is absent")

    monkeypatch.setattr(requests, "get", _record_get)
    monkeypatch.setattr(requests, "post", _record_post)

    outcome = june_run_arm.arm("111")

    assert outcome["outcome"] != n8n_arming.ARMED
    assert calls == []


# --------------------------------------------------------------------------------------
# Disarm mode
# --------------------------------------------------------------------------------------

def test_disarm_calls_disarm_once_and_never_arm_for_dispatch(monkeypatch, _stub_resolve):
    calls = []

    def _fake_disarm(workflow_id, config):
        calls.append(workflow_id)
        return {"outcome": n8n_arming.DISARMED, "workflow_id": workflow_id}

    def _boom(*a, **kw):
        raise AssertionError("disarm mode must never call arm_for_dispatch")

    monkeypatch.setattr(n8n_arming, "disarm", _fake_disarm)
    monkeypatch.setattr(n8n_arming, "arm_for_dispatch", _boom)

    outcome = june_run_arm.disarm()

    assert outcome["outcome"] == n8n_arming.DISARMED
    assert calls == [FAKE_WORKFLOW_ID]


def test_disarm_succeeds_with_allow_n8n_arm_absent(monkeypatch, _stub_resolve):
    monkeypatch.delenv("ALLOW_N8N_ARM", raising=False)
    monkeypatch.setattr(
        n8n_arming, "disarm", lambda workflow_id, config: {"outcome": n8n_arming.DISARMED},
    )

    outcome = june_run_arm.disarm()

    assert outcome["outcome"] == n8n_arming.DISARMED


def test_disarm_unresolvable_workflow_name_refuses_without_calling_disarm(monkeypatch):
    monkeypatch.setattr(
        executions_client, "resolve_workflow_id",
        lambda cfg, workflow_name=None, **kw: None,
    )

    def _boom(*a, **kw):
        raise AssertionError("disarm must not be called for an unresolvable name")

    monkeypatch.setattr(n8n_arming, "disarm", _boom)

    outcome = june_run_arm.disarm(workflow_name="Nonexistent Workflow")

    assert outcome["outcome"] == "refused"


def test_disarm_failed_exception_yields_the_outcome_payload(monkeypatch, _stub_resolve):
    failure_outcome = {
        "outcome": n8n_arming.DISARM_FAILED,
        "workflow_id": FAKE_WORKFLOW_ID,
        "detail": "DISARM FAILED -- LIVE WRITES MAY STILL BE ENABLED.",
    }

    def _fake_disarm(workflow_id, config):
        raise n8n_arming.DisarmFailed(failure_outcome)

    monkeypatch.setattr(n8n_arming, "disarm", _fake_disarm)

    outcome = june_run_arm.disarm()

    assert outcome == failure_outcome
    assert outcome["outcome"] != n8n_arming.DISARMED


# --------------------------------------------------------------------------------------
# main() -- exit codes and stdout
# --------------------------------------------------------------------------------------

def test_main_arm_prints_outcome_and_exits_zero_on_success(monkeypatch, _stub_resolve, capsys):
    monkeypatch.setattr(
        n8n_arming, "arm_for_dispatch",
        lambda *a, **kw: {"outcome": n8n_arming.ARMED, "record_ids": ["111"]},
    )

    exit_code = june_run_arm.main(["--ids", "111"])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert n8n_arming.ARMED in out


def test_main_disarm_flag_routes_to_disarm_mode(monkeypatch, _stub_resolve):
    calls = {"arm": 0, "disarm": 0}
    monkeypatch.setattr(
        n8n_arming, "disarm",
        lambda *a, **kw: (calls.__setitem__("disarm", calls["disarm"] + 1)
                          or {"outcome": n8n_arming.DISARMED}),
    )
    monkeypatch.setattr(
        n8n_arming, "arm_for_dispatch",
        lambda *a, **kw: (calls.__setitem__("arm", calls["arm"] + 1)
                          or {"outcome": n8n_arming.ARMED}),
    )

    exit_code = june_run_arm.main(["--disarm"])

    assert exit_code == 0
    assert calls == {"arm": 0, "disarm": 1}


def test_main_disarm_failure_exits_non_zero(monkeypatch, _stub_resolve, capsys):
    failure_outcome = {"outcome": n8n_arming.DISARM_FAILED, "detail": "still enabled"}

    def _fake_disarm(workflow_id, config):
        raise n8n_arming.DisarmFailed(failure_outcome)

    monkeypatch.setattr(n8n_arming, "disarm", _fake_disarm)

    exit_code = june_run_arm.main(["--disarm"])

    assert exit_code != 0
    out = capsys.readouterr().out
    assert "still enabled" in out


# --------------------------------------------------------------------------------------
# Phase 47.5 Plan 01 Task 3 — the DOMAIN allowlist
#
# n8n_arming.arm_for_dispatch has always accepted record_domains; only this wrapper hid it
# by passing [] unconditionally. Plan 03 cannot arm a not-yet-created disposable by id, so
# a domain allowlist is the only allowlist available to it.
# --------------------------------------------------------------------------------------

def test_arm_passes_a_domain_allowlist_through_to_arm_for_dispatch(monkeypatch, _stub_resolve):
    calls = []

    def _fake_arm_for_dispatch(workflow_id, record_ids, record_domains, allow_create, config):
        calls.append({"record_ids": record_ids, "record_domains": record_domains,
                      "allow_create": allow_create})
        return {"outcome": n8n_arming.ARMED}

    monkeypatch.setattr(n8n_arming, "arm_for_dispatch", _fake_arm_for_dispatch)

    outcome = june_run_arm.arm("", domains_csv="a.example, b.example ")

    assert outcome["outcome"] == n8n_arming.ARMED
    assert calls == [{"record_ids": [], "record_domains": ["a.example", "b.example"],
                      "allow_create": False}]


def test_arm_accepts_ids_and_domains_together(monkeypatch, _stub_resolve):
    calls = []
    monkeypatch.setattr(
        n8n_arming, "arm_for_dispatch",
        lambda workflow_id, record_ids, record_domains, allow_create, config: (
            calls.append((record_ids, record_domains)) or {"outcome": n8n_arming.ARMED}),
    )

    june_run_arm.arm("111", domains_csv="a.example")

    assert calls == [(["111"], ["a.example"])]


def test_arm_refuses_only_when_ids_AND_domains_are_both_empty(monkeypatch):
    """The refusal's reason is unchanged: an empty allowlist denies every write and would
    look like a successful arm. It just has to see both allowlists now, not only --ids."""
    def _boom(*a, **kw):
        raise AssertionError("arm_for_dispatch must not be called for an empty allowlist")

    monkeypatch.setattr(n8n_arming, "arm_for_dispatch", _boom)

    outcome = june_run_arm.arm("", domains_csv="")

    assert outcome["outcome"] == "refused"
    assert "empty" in outcome["detail"].lower()


def test_main_domains_flag_reaches_arm(monkeypatch, _stub_resolve):
    calls = []
    monkeypatch.setattr(
        n8n_arming, "arm_for_dispatch",
        lambda workflow_id, record_ids, record_domains, allow_create, config: (
            calls.append((record_ids, record_domains)) or {"outcome": n8n_arming.ARMED}),
    )

    exit_code = june_run_arm.main(["--domains", "a.example"])

    assert exit_code == 0
    assert calls == [([], ["a.example"])]


def test_domains_never_leak_into_disarm(monkeypatch, _stub_resolve):
    """The disarm path is not gated on the arming variable and is untouched by this task."""
    seen = []
    monkeypatch.setattr(
        n8n_arming, "disarm",
        lambda workflow_id, config: (seen.append(workflow_id)
                                     or {"outcome": n8n_arming.DISARMED}),
    )

    exit_code = june_run_arm.main(["--disarm", "--domains", "a.example"])

    assert exit_code == 0
    assert seen == [FAKE_WORKFLOW_ID]
