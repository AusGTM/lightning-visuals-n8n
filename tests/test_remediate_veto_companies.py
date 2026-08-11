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
from src.schemas import ProviderEvidence, ProviderResult  # noqa: E402

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


# Task 2 (T-47-13): a fake lister covering every property name any built payload or the
# report script's OBSERVED_PROPS could ever check, so Plan 01's tests -- which predate
# the live property-existence guard -- keep exercising main() without a live HubSpot
# properties call. Deliberately a superset, not the literal live portal set.
_ALL_METADATA_PROPS = {
    f"{field}{suffix}" for field in m.INPUT_PROPS for suffix in m.METADATA_SUFFIXES
}
_FAKE_LIVE_PROPERTY_NAMES = (
    {"name", "domain", "website", "country", "industry"}
    | set(m.INPUT_PROPS)
    | _ALL_METADATA_PROPS
    | {"org_type_score", "geography_score", "annual_revenue_score",
       "produces_content_score", "gambling_score"}
    | set(m.FORBIDDEN_PROPS)
)


def _fake_property_lister(object_type):
    return [{"name": n} for n in sorted(_FAKE_LIVE_PROPERTY_NAMES)]


def _arm_credentials_and_env(monkeypatch, *, dry_run_unset=True):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", m.EXPECTED_PORTAL_ID)
    monkeypatch.setenv("USE_MOCK_WEB_RESEARCH", "true")
    if dry_run_unset:
        monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.delenv("ALLOW_VETO_REMEDIATION", raising=False)
    monkeypatch.delenv("VETO_MAX_RECORDS", raising=False)
    monkeypatch.setattr(m, "get_record", _fake_get_record)
    monkeypatch.setattr(m, "_live_property_lister", _fake_property_lister)
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


# --- Task 3: pin, cap, never-write, budget, D-20 clobber verify guard suite ----------------

def _provider_result(data, evidence_by_field=None, evidence_urls=None, evidence_summary=None,
                      provider="claude_web", confidence=85):
    return ProviderResult(
        provider=provider,
        object_type="companies",
        matched=True,
        confidence=confidence,
        data=data,
        evidence=ProviderEvidence(evidence_urls=evidence_urls or [], evidence_summary=evidence_summary),
        evidence_by_field=evidence_by_field or {},
    )


# Four structurally different fixture shapes -- an evidenced evidence-required org type,
# an evidenced hardware-vendor veto candidate, an unevidenced-but-not-gated club, and a
# fully-unresolved record.
_RESULT_GOVERNING_BODY = _provider_result(
    data={"lv_org_type": "governing_body_league", "lv_produces_content": True,
          "lv_country_region_normalized": "AU"},
    evidence_by_field={"lv_org_type": "https://a.example/about",
                        "lv_produces_content": "https://a.example/watch"},
)
_RESULT_HARDWARE_VENDOR = _provider_result(
    data={"lv_org_type": "hardware_vendor", "lv_produces_content": False,
          "lv_country_region_normalized": "AU"},
    evidence_by_field={"lv_org_type": "https://b.example/products",
                        "lv_produces_content": "https://b.example/about"},
)
_RESULT_CLUB_NO_EVIDENCE = _provider_result(
    data={"lv_org_type": "individual_club_team", "lv_produces_content": True,
          "lv_country_region_normalized": "NZ"},
)
_RESULT_UNKNOWN = _provider_result(
    data={"lv_org_type": "unknown", "lv_produces_content": None,
          "lv_country_region_normalized": "Unknown"},
)
FIXTURE_RESULTS = [_RESULT_GOVERNING_BODY, _RESULT_HARDWARE_VENDOR, _RESULT_CLUB_NO_EVIDENCE, _RESULT_UNKNOWN]


def test_never_writes_a_forbidden_derived_field_key_across_fixtures():
    assert len(FIXTURE_RESULTS) >= 4
    for result in FIXTURE_RESULTS:
        input_patch = m.build_input_patch("999", result)
        written_fields = list(input_patch["properties"].keys())
        metadata_patch = m.build_metadata_patch("999", result, written_fields)
        component_patch = m.build_component_patch("999", input_patch["properties"])
        for patch in (input_patch, metadata_patch, component_patch):
            assert m.FORBIDDEN_PROPS.isdisjoint(patch["properties"].keys())


def test_metadata_patch_never_writes_a_forbidden_key_even_when_all_fields_written():
    result = _RESULT_GOVERNING_BODY
    written_fields = list(m.INPUT_PROPS)  # pretend every input field was written
    metadata_patch = m.build_metadata_patch("999", result, written_fields)
    assert m.FORBIDDEN_PROPS.isdisjoint(metadata_patch["properties"].keys())


def test_produces_content_false_without_evidence_is_omitted_with_a_reason():
    result = _provider_result(data={"lv_produces_content": False}, evidence_by_field={})
    patch = m.build_input_patch("999", result)
    assert "lv_produces_content" not in patch["properties"]
    reasons = m.unresolved_reasons("999", result)
    assert "lv_produces_content" in reasons


@pytest.mark.parametrize("excluded_id,name", [
    ("10024564084", "Entain"),
    ("15860277364", "Gravity Media"),
    ("17317184159", "Ironman"),
])
def test_resolve_pinned_ids_refuses_excluded_ids(excluded_id, name):
    with pytest.raises(m.PinRefused) as exc_info:
        m.resolve_pinned_ids([excluded_id])
    assert excluded_id in str(exc_info.value)


def test_resolve_pinned_ids_refuses_arbitrary_unpinned_id():
    with pytest.raises(m.PinRefused) as exc_info:
        m.resolve_pinned_ids(["99999999"])
    assert "99999999" in str(exc_info.value)


def test_resolve_pinned_ids_returns_deterministic_order_regardless_of_input_order():
    import random
    shuffled = list(m.PINNED_COMPANY_ID_ORDER)
    random.Random(42).shuffle(shuffled)
    assert m.resolve_pinned_ids(shuffled) == m.PINNED_COMPANY_ID_ORDER


def test_enforce_sample_cap_all_17_true_at_default(monkeypatch):
    monkeypatch.delenv("VETO_MAX_RECORDS", raising=False)
    assert m.enforce_sample_cap(list(m.PINNED_COMPANY_ID_ORDER)) is True


def test_enforce_sample_cap_refuses_below_17(monkeypatch):
    monkeypatch.setenv("VETO_MAX_RECORDS", "5")
    assert m.enforce_sample_cap(list(m.PINNED_COMPANY_ID_ORDER)) is False


def test_resolved_max_records_clamps_above_17_and_falls_back_on_non_integer(monkeypatch):
    monkeypatch.setenv("VETO_MAX_RECORDS", "25")
    assert m._resolved_max_records() == 17
    monkeypatch.setenv("VETO_MAX_RECORDS", "not-a-number")
    assert m._resolved_max_records() == 17


def test_writes_allowed_false_for_every_non_both_keys_combo(monkeypatch):
    monkeypatch.delenv("ALLOW_VETO_REMEDIATION", raising=False)
    monkeypatch.setenv("DRY_RUN", "false")
    assert m._writes_allowed() is False

    monkeypatch.setenv("ALLOW_VETO_REMEDIATION", "true")
    monkeypatch.setenv("DRY_RUN", "true")
    assert m._writes_allowed() is False

    monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.setenv("ALLOW_VETO_REMEDIATION", "true")
    assert m._writes_allowed() is False  # DRY_RUN unset defaults to "true"

    monkeypatch.setenv("ALLOW_VETO_REMEDIATION", "true")
    monkeypatch.setenv("DRY_RUN", "false")
    assert m._writes_allowed() is True


def test_estimate_cost_reports_expected_keys_for_all_17():
    estimate = m.estimate_cost(list(m.PINNED_COMPANY_ID_ORDER))
    assert estimate["web_research_calls"] == 17
    assert estimate["n8n_executions"] == 17
    assert estimate["n8n_budget_month"] == m.N8N_EXECUTION_BUDGET_MONTH
    assert estimate["lusha_credits"] == 0
    assert 0 <= estimate["redundant_research_calls"] <= 17
    assert estimate["anthropic_estimate_usd"] > 0


def test_refuse_if_over_budget_raises_above_budget_and_never_truncates_when_ok():
    ids = ["1", "2", "3"]
    over_budget = {"n8n_executions": 3000, "n8n_budget_month": 2500}
    with pytest.raises(m.BudgetRefused):
        m.refuse_if_over_budget(over_budget, ids)

    under_budget = {"n8n_executions": 17, "n8n_budget_month": 2500}
    result = m.refuse_if_over_budget(under_budget, ids)
    assert result is ids


def test_verify_post_run_detects_a_lost_metadata_stamp():
    live_props = {
        "lv_org_type": "governing_body_league",
        "lv_org_type_source": "claude_web",
        # lv_org_type_validation_status was lost by a re-research lane (D-20).
    }

    def _reader(object_type, record_id, properties):
        return {"id": record_id, "properties": dict(live_props)}

    diverged = m.verify_post_run(
        "999",
        expected_inputs={"lv_org_type": "governing_body_league"},
        expected_metadata={
            "lv_org_type_source": "claude_web",
            "lv_org_type_validation_status": "web_researched",
        },
        reader=_reader,
    )

    assert diverged == {"lv_org_type_validation_status"}


def test_verify_post_run_returns_empty_set_when_everything_matches():
    live_props = {"lv_org_type": "governing_body_league", "lv_org_type_source": "claude_web"}

    def _reader(object_type, record_id, properties):
        return {"id": record_id, "properties": dict(live_props)}

    diverged = m.verify_post_run(
        "999",
        expected_inputs={"lv_org_type": "governing_body_league"},
        expected_metadata={"lv_org_type_source": "claude_web"},
        reader=_reader,
    )

    assert diverged == set()
