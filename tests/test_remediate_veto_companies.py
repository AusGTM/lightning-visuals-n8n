"""tests/test_remediate_veto_companies.py

Phase 47 Plan 01 -- offline tests for scripts/remediate_veto_companies.py. No network
calls anywhere in this module -- every test either monkeypatches requests.get/post to
raise, injects a fake get_record, or exercises pure functions.
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `scripts.*` imports resolve

import scripts.remediate_veto_companies as m  # noqa: E402

PINNED_ID = "9604732797"  # Tweed Valley Jockey Club

_FAKE_RECORD_PROPS = {
    "name": "Tweed Valley Jockey Club",
    "domain": "tvjc.example",
    "website": "https://tvjc.example",
    "country": "Australia",
    "industry": "Sports",
}


def _fake_get_record(object_type, record_id, properties):
    return {"id": record_id, "properties": dict(_FAKE_RECORD_PROPS)}


def _refuse_network(*_a, **_kw):
    raise AssertionError("no network call should be made in this test")


def _arm_credentials_and_env(monkeypatch, *, dry_run_unset=True):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", m.EXPECTED_PORTAL_ID)
    monkeypatch.setenv("USE_MOCK_WEB_RESEARCH", "true")
    if dry_run_unset:
        monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.delenv("ALLOW_VETO_REMEDIATION", raising=False)
    monkeypatch.delenv("VETO_MAX_RECORDS", raising=False)
    monkeypatch.setattr(m, "get_record", _fake_get_record)
    monkeypatch.setattr("requests.post", _refuse_network)
    monkeypatch.setattr("requests.get", _refuse_network)


# --- Task 1: tracer -----------------------------------------------------------------------

def test_tracer_single_pinned_company_disarmed_prints_all_payloads_no_network(monkeypatch, capsys):
    _arm_credentials_and_env(monkeypatch)

    exit_code = m.main(["--company-id", PINNED_ID])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "lv_country_region_normalized" in out
    assert "org_type_score" in out
    assert "lv_org_type_validation_status" in out
    assert "objectId" in out
    assert PINNED_ID in out


def test_pinned_id_order_and_disjoint_from_excluded():
    assert len(m.PINNED_COMPANY_ID_ORDER) == 17
    assert len(m.PINNED_COMPANY_IDS) == 17
    assert m.PINNED_COMPANY_IDS.isdisjoint(m.EXCLUDED_COMPANY_IDS)


def test_resolved_max_records_default_is_17(monkeypatch):
    monkeypatch.delenv("VETO_MAX_RECORDS", raising=False)
    assert m._resolved_max_records() == 17


def test_main_with_no_flags_resolves_to_all_17_in_pinned_order(monkeypatch, capsys):
    _arm_credentials_and_env(monkeypatch)

    exit_code = m.main([])

    assert exit_code == 0
    out = capsys.readouterr().out
    for line in out.splitlines():
        if line.startswith("RESOLVED_IDS:"):
            import json
            resolved = json.loads(line[len("RESOLVED_IDS:"):].strip())
            assert tuple(resolved) == m.PINNED_COMPANY_ID_ORDER
            break
    else:
        raise AssertionError("no RESOLVED_IDS line printed")


def test_module_never_calls_search_records():
    source = (ROOT / "scripts" / "remediate_veto_companies.py").read_text()
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "search_records" not in names
    assert "search_records" not in attrs


# --- Task 2: settle-and-assert -------------------------------------------------------------

def _no_sleep(_seconds):
    """Injectable sleeper that never actually sleeps -- pairs with _fake_clock so no
    settle test burns real wall-clock time."""


def _fake_clock(step=5.0):
    """Injectable replacement for time.monotonic(): each call advances by `step`,
    simulating the wall-clock time a real sleeper would have consumed, without ever
    calling time.sleep."""
    state = {"t": 0.0}

    def _clock():
        value = state["t"]
        state["t"] += step
        return value

    return _clock


def _reader_for(sequence_by_prop, constant_by_prop=None):
    """A fake `reader(object_type, record_id, properties)` -- properties is always a
    single-element list here (settle_and_assert polls one prop at a time). Values in
    sequence_by_prop are consumed in order (repeating the last once exhausted);
    constant_by_prop always returns the same value regardless of call count."""
    constant_by_prop = constant_by_prop or {}
    calls = {}

    def _reader(object_type, record_id, properties):
        prop = properties[0]
        if prop in constant_by_prop:
            return {"id": record_id, "properties": {prop: constant_by_prop[prop]}}
        seq = sequence_by_prop[prop]
        idx = min(calls.get(prop, 0), len(seq) - 1)
        calls[prop] = calls.get(prop, 0) + 1
        return {"id": record_id, "properties": {prop: seq[idx]}}

    return _reader


def test_settle_and_assert_returns_value_and_elapsed_when_stable_and_matches_expected(monkeypatch):
    monkeypatch.setattr(m.time, "monotonic", _fake_clock())
    reader = _reader_for({"lv_icp_tier": ["Unscored", "B", "B"]})

    value, elapsed = m.settle_and_assert(
        "9604732797", "lv_icp_tier", "B", timeout=60, interval=5, reader=reader, sleeper=_no_sleep,
    )

    assert value == "B"
    assert elapsed >= 0


def test_settle_and_assert_raises_settle_failed_when_stable_but_wrong_value(monkeypatch):
    monkeypatch.setattr(m.time, "monotonic", _fake_clock())
    reader = _reader_for({"lv_icp_tier": ["Unscored", "C", "C"]})

    with pytest.raises(m.SettleFailed) as exc_info:
        m.settle_and_assert(
            "9604732797", "lv_icp_tier", "B", timeout=60, interval=5, reader=reader, sleeper=_no_sleep,
        )

    message = str(exc_info.value)
    assert "9604732797" in message
    assert "C" in message
    assert "B" in message


def test_settle_and_assert_raises_settle_failed_on_timeout_never_stabilising(monkeypatch):
    monkeypatch.setattr(m.time, "monotonic", _fake_clock(step=5.0))
    calls = {"n": 0}

    def _never_stable(object_type, record_id, properties):
        calls["n"] += 1
        return {"id": record_id, "properties": {properties[0]: f"value-{calls['n']}"}}

    with pytest.raises(m.SettleFailed) as exc_info:
        m.settle_and_assert(
            "9604732797", "lv_icp_tier", "B", timeout=12, interval=5,
            reader=_never_stable, sleeper=_no_sleep,
        )

    assert "12" in str(exc_info.value)


def test_settle_tier_and_settle_veto_have_different_default_timeouts():
    import inspect
    assert inspect.signature(m.settle_tier).parameters["timeout"].default == 120
    assert inspect.signature(m.settle_veto).parameters["timeout"].default == 900


def test_settle_tier_delegates_to_settle_and_assert_with_lv_icp_tier(monkeypatch):
    monkeypatch.setattr(m.time, "monotonic", _fake_clock())
    reader = _reader_for({"lv_icp_tier": ["Unscored", "A", "A"]})

    value, _elapsed = m.settle_tier(
        "9604732797", "A", timeout=60, interval=5, reader=reader, sleeper=_no_sleep,
    )

    assert value == "A"


def test_settle_veto_passes_when_flag_true_for_a_genuine_non_non_anz_veto(monkeypatch):
    monkeypatch.setattr(m.time, "monotonic", _fake_clock())
    reader = _reader_for(
        {"lv_anti_icp_flag": ["unknown", "true", "true"]},
        constant_by_prop={
            "lv_anti_icp_reason": "Hardware/AV/LED vendor, not sports-media buyer",
        },
    )

    value, _elapsed = m.settle_veto(
        "18047161864", timeout=60, interval=5, reader=reader, sleeper=_no_sleep,
    )

    assert value == "true"


def test_settle_veto_fails_when_flag_true_still_carries_the_non_anz_reason(monkeypatch):
    monkeypatch.setattr(m.time, "monotonic", _fake_clock())
    reader = _reader_for(
        {"lv_anti_icp_flag": ["unknown", "true", "true"]},
        constant_by_prop={"lv_anti_icp_reason": "Non-ANZ geography"},
    )

    with pytest.raises(m.SettleFailed):
        m.settle_veto("9604732797", timeout=60, interval=5, reader=reader, sleeper=_no_sleep)
