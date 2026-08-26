"""tests/test_fix_sfv_region.py

Phase 58 Plan 05 Task 4 -- offline pins for scripts/fix_sfv_region.py: the pure payload
builders, the disarmed `--plan` path, and `--execute`'s refusal ordering. No network call
anywhere in this module -- every test either asserts a pure function's return value, or
injects fakes that raise on any use they should not reach.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*` imports resolve

import scripts.fix_sfv_region as fix  # noqa: E402
from scripts.remediate_veto_companies import FORBIDDEN_PROPS, PINNED_COMPANY_IDS  # noqa: E402


def _refuse_any_call(*_a, **_kw):
    raise AssertionError("no call should be made in this path")


_WEBHOOK_CONFIG = {"n8n_url": "https://fake-tenant.n8n.cloud/", "webhook_secret": "fake-secret"}


# --- pure payload builders ----------------------------------------------------------------

def test_build_region_patch_corrects_region_and_clears_review_state():
    props = fix.build_region_patch()
    assert props == {
        "lv_country_region_normalized": "AU",
        "lv_enrichment_status": "complete",
        "lv_enrichment_needs_review": "false",
    }


def test_build_region_patch_never_touches_a_derived_veto_field():
    props = fix.build_region_patch()
    assert FORBIDDEN_PROPS.isdisjoint(props)


def test_target_company_id_is_pinned_and_not_in_the_phase_47_set():
    """The pinned id is a literal not shared with remediate_veto_companies.py's own
    17-record set -- this script is a separate, one-record remediation."""
    assert fix.TARGET_COMPANY_ID == "283816805830"
    assert fix.TARGET_COMPANY_ID not in PINNED_COMPANY_IDS


def test_build_recompute_event_carries_recompute_true_and_nothing_else():
    event = fix.build_recompute_event()
    assert len(event) == 1
    body = event[0]
    assert body["recompute"] is True
    assert body["objectId"] == fix.TARGET_COMPANY_ID
    assert body["objectType"] == "company"
    assert "mode" not in body
    assert "domain" not in body


# --- --plan: no network call, prints both leg payloads -------------------------------------

def test_plan_mode_exits_zero_prints_both_legs_and_makes_no_network_call(capsys):
    exit_code = fix.main(
        ["--plan"],
        config_loader=lambda: dict(_WEBHOOK_CONFIG),
        patcher=_refuse_any_call,
        reader=_refuse_any_call,
        poster=_refuse_any_call,
        settler=_refuse_any_call,
        has_credentials=_refuse_any_call,
        portal_ok=_refuse_any_call,
    )
    assert exit_code == 0

    out = capsys.readouterr().out
    assert fix.TARGET_COMPANY_ID in out
    assert "lv_country_region_normalized" in out
    assert "recompute" in out
    assert "target company id" in out.lower()


def test_plan_mode_handles_an_unloadable_config_without_crashing(capsys):
    def _raise_config_error():
        raise fix.config_gate.ConfigError("no config file")

    exit_code = fix.main(
        ["--plan"],
        config_loader=_raise_config_error,
        patcher=_refuse_any_call,
        reader=_refuse_any_call,
        poster=_refuse_any_call,
        settler=_refuse_any_call,
        has_credentials=_refuse_any_call,
        portal_ok=_refuse_any_call,
    )
    assert exit_code == 0
    assert "unresolvable" in capsys.readouterr().out


# --- --execute refusal ordering: arm check comes first, before any leg ---------------------

def test_execute_without_arming_refuses_before_any_call(capsys):
    exit_code = fix.main(
        ["--execute"],
        config_loader=lambda: dict(_WEBHOOK_CONFIG),
        patcher=_refuse_any_call,
        reader=_refuse_any_call,
        poster=_refuse_any_call,
        settler=_refuse_any_call,
        has_credentials=_refuse_any_call,
        portal_ok=_refuse_any_call,
        env={},
    )
    assert exit_code == 1
    assert "REFUSED" in capsys.readouterr().out


def test_execute_refuses_on_wrong_portal_before_any_leg(capsys):
    exit_code = fix.main(
        ["--execute"],
        config_loader=lambda: dict(_WEBHOOK_CONFIG),
        patcher=_refuse_any_call,
        reader=_refuse_any_call,
        poster=_refuse_any_call,
        settler=_refuse_any_call,
        has_credentials=_refuse_any_call,
        portal_ok=lambda: False,
        env={"ALLOW_VETO_REMEDIATION": "true"},
    )
    assert exit_code == 1
    assert "REFUSED" in capsys.readouterr().out


def test_execute_refuses_on_missing_credentials_before_any_leg(capsys):
    exit_code = fix.main(
        ["--execute"],
        config_loader=lambda: dict(_WEBHOOK_CONFIG),
        patcher=_refuse_any_call,
        reader=_refuse_any_call,
        poster=_refuse_any_call,
        settler=_refuse_any_call,
        has_credentials=lambda: False,
        portal_ok=lambda: True,
        env={"ALLOW_VETO_REMEDIATION": "true"},
    )
    assert exit_code == 1
    assert "REFUSED" in capsys.readouterr().out


# --- --execute happy path: both legs run in order, write_blocked is reported plainly -------

class _FakeResponse:
    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


def test_execute_reports_write_blocked_plainly(capsys):
    calls = []

    def fake_patcher(object_type, record_id, properties, dry_run):
        calls.append(("patch", object_type, record_id, properties, dry_run))
        return {"id": record_id, "properties": properties}

    def fake_poster(company_id, armed, config, recompute):
        calls.append(("post", company_id, armed, recompute))
        return _FakeResponse({"action": "write_blocked", "hs_object_id": company_id})

    def fake_settler(company_id):
        calls.append(("settle", company_id))
        return ("true", 5.0)

    def fake_reader(object_type, record_id, properties):
        calls.append(("read", object_type, record_id, tuple(properties)))
        return {"properties": {p: None for p in properties}}

    exit_code = fix.main(
        ["--execute"],
        config_loader=lambda: dict(_WEBHOOK_CONFIG),
        patcher=fake_patcher,
        reader=fake_reader,
        poster=fake_poster,
        settler=fake_settler,
        has_credentials=lambda: True,
        portal_ok=lambda: True,
        env={"ALLOW_VETO_REMEDIATION": "true"},
    )

    assert exit_code == 0
    assert calls[0][0] == "patch"
    assert calls[0][2] == fix.TARGET_COMPANY_ID
    assert calls[0][3] == fix.build_region_patch()
    assert calls[0][4] is False
    assert calls[1] == ("post", fix.TARGET_COMPANY_ID, True, True)
    assert calls[2][0] == "settle"
    assert calls[3][0] == "read"

    out = capsys.readouterr().out
    assert "VETO NOT WRITTEN" in out
    assert "write window" in out


def test_execute_settle_failure_reports_nonzero(capsys):
    from scripts.remediate_veto_companies import SettleFailed

    def fake_patcher(*_a, **_kw):
        return {"dry_run": False}

    def fake_poster(*_a, **_kw):
        return _FakeResponse({"action": "enrich"})

    def fake_settler(_company_id):
        raise SettleFailed("did not settle")

    def fake_reader(_object_type, _record_id, properties):
        return {"properties": {p: None for p in properties}}

    exit_code = fix.main(
        ["--execute"],
        config_loader=lambda: dict(_WEBHOOK_CONFIG),
        patcher=fake_patcher,
        reader=fake_reader,
        poster=fake_poster,
        settler=fake_settler,
        has_credentials=lambda: True,
        portal_ok=lambda: True,
        env={"ALLOW_VETO_REMEDIATION": "true"},
    )

    assert exit_code == 1
    assert "SETTLE FAILED" in capsys.readouterr().out


# --- mutually exclusive flags ---------------------------------------------------------------

def test_requires_exactly_one_of_plan_or_execute():
    with pytest.raises(SystemExit):
        fix.main([])
    with pytest.raises(SystemExit):
        fix.main(["--plan", "--execute"])
