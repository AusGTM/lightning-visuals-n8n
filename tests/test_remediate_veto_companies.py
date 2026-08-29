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
# properties call. D-21 (Amendment 2026-08-12): build_metadata_patch only ever emits
# LIVE_METADATA_STAMP_KEYS (2 keys, not the full 21 METADATA_SUFFIXES combinations) --
# this fake set mirrors the guard's actual narrowed checked set, not an inflated one.
_FAKE_LIVE_PROPERTY_NAMES = (
    {"name", "domain", "website", "country", "industry"}
    | set(m.INPUT_PROPS)
    | set(m.LIVE_METADATA_STAMP_KEYS)
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


def test_settle_tier_delegates_to_settle_and_assert_with_lv_icp_tier_derived(monkeypatch):
    monkeypatch.setattr(m.time, "monotonic", _fake_clock())
    reader = _reader_for({"lv_icp_tier_derived": ["Unscored", "A", "A"]})

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


# --- discovered live 2026-08-12: none of the 17 real research results returned a member
# of the lv_org_type enum -- these tests pin the fix (D-14/D-17) against real observed
# free-text shapes rather than only the hand-crafted enum fixtures above.

def test_out_of_enum_org_type_free_text_is_left_unresolved_not_guessed():
    # "Event organizer / Sports league operator" (The Rumble's actual live result) must
    # NOT be keyword-mapped to governing_body_league -- that is the exact D-17 "they are
    # all clubs" guessing failure mode.
    result = _provider_result(
        data={"lv_org_type": "Event organizer / Sports league operator"},
        evidence_by_field={"lv_org_type": "https://therumble.example/about"},
    )
    patch = m.build_input_patch("999", result)
    assert "lv_org_type" not in patch["properties"]
    reasons = m.unresolved_reasons("999", result)
    assert "not a recognized lv_org_type enum value" in reasons["lv_org_type"]


def test_boolean_hardware_vendor_signal_classifies_org_type_when_free_text_does_not():
    # Simtech LED's actual live shape: lv_org_type is free text ("private_company") but
    # lv_is_hardware_vendor is a schema-conformant boolean. D-16/D-17's expected outcome.
    result = _provider_result(
        data={"lv_org_type": "private_company", "lv_is_hardware_vendor": True},
        evidence_by_field={"lv_is_hardware_vendor": "https://simtechled.example/products"},
    )
    patch = m.build_input_patch("999", result)
    assert patch["properties"]["lv_org_type"] == "hardware_vendor"


def test_boolean_hardware_vendor_signal_without_evidence_stays_unresolved():
    result = _provider_result(
        data={"lv_org_type": "private_company", "lv_is_hardware_vendor": True},
        evidence_by_field={},
    )
    patch = m.build_input_patch("999", result)
    assert "lv_org_type" not in patch["properties"]


def test_gambling_operator_boolean_never_derives_org_type_even_when_evidenced():
    # Regression guard for a real bug found live 2026-08-12: lv_is_gambling_operator
    # fired true for 8 of 17 records -- every one a not-for-profit racing club that
    # merely hosts on-track TAB/bookmaker facilities (standard for every AU racecourse),
    # not a gambling operator itself. Unlike hardware_vendor, this boolean is proven
    # unreliable for org_type derivation and must never be used for it, evidenced or not.
    result = _provider_result(
        data={"lv_org_type": "Sports club / Racing club", "lv_is_gambling_operator": True},
        evidence_by_field={"lv_is_gambling_operator": "https://club.example/sponsors"},
    )
    org_type, evidence_field = m._classify_org_type(result.data)
    assert org_type is None
    assert evidence_field is None
    patch = m.build_input_patch("999", result)
    assert "lv_org_type" not in patch["properties"]


def test_region_normalizer_accepts_only_unambiguous_australia_and_new_zealand_forms():
    assert m._normalize_region("Australia") == "AU"
    assert m._normalize_region("Australia - NSW") == "AU"
    # A state/territory name qualified by the country is still unambiguous -- the
    # actual live shape returned for two of the 17 records.
    assert m._normalize_region("New South Wales, Australia") == "AU"
    assert m._normalize_region("NSW, Australia") == "AU"
    assert m._normalize_region("New Zealand") == "NZ"
    # Ambiguous/foreign free text (Jam TV's actual live result -- entity-resolution
    # doubt against jamtv.it, an Italian company) must NOT default to "Other": that
    # would manufacture a genuine non-ANZ veto from an ambiguous or mismatched read.
    assert m._normalize_region("Italy") is None
    assert m._normalize_region(None) is None


def test_ambiguous_region_free_text_is_left_unresolved_with_a_reason_not_defaulted():
    result = _provider_result(data={"lv_country_region_normalized": "Italy"})
    patch = m.build_input_patch("999", result)
    assert "lv_country_region_normalized" not in patch["properties"]
    reasons = m.unresolved_reasons("999", result)
    assert "Italy" in reasons["lv_country_region_normalized"]


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


# --- Phase 47.5 Plan 01 Task 3: the recompute-capable D-18 POST -------------------------
#
# The webhook helper is the only on-demand trigger the recompute lane has. No test here
# performs a network call -- every one injects a fake transport.


class _FakeResponse:
    status_code = 200

    def raise_for_status(self):
        return None


class _FakeTransport:
    """Records the single POST it receives. Never reaches the network."""

    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return _FakeResponse()


_WEBHOOK_CONFIG = {
    "n8n_url": "https://fake-tenant.n8n.cloud/",
    "webhook_secret": "fake-secret",
}

_D18_KEYS = {"objectId", "objectType", "subscriptionType", "propertyName", "occurredAt"}


def test_build_webhook_event_default_shape_is_unchanged_by_the_recompute_option():
    """The D-18 array element every prior phase posted must stay byte-shape identical when
    the new options are not used -- an always-present `recompute: false` or `domain: null`
    key would change the event body for every existing caller."""
    event = m.build_webhook_event(PINNED_ID)
    assert isinstance(event, list) and len(event) == 1
    assert set(event[0]) == _D18_KEYS
    assert "recompute" not in event[0]
    assert "domain" not in event[0]
    assert event[0]["objectId"] == PINNED_ID
    assert event[0]["objectType"] == "company"


def test_build_webhook_event_carries_a_real_json_boolean_recompute_when_requested():
    """Parse HubSpot Event normalizes with `event.recompute === true`, so the string
    "true" would silently NOT arm the lane. Assert the real boolean, by identity."""
    event = m.build_webhook_event(PINNED_ID, recompute=True)
    assert event[0]["recompute"] is True
    assert set(event[0]) == _D18_KEYS | {"recompute"}


def test_build_webhook_event_omits_recompute_entirely_when_false():
    assert "recompute" not in m.build_webhook_event(PINNED_ID, recompute=False)[0]


def test_build_webhook_event_carries_a_domain_when_given_and_omits_it_when_none():
    """A domain-carrying event routes through `HubSpot Company Search` (domain EQ) rather
    than the bare-event fetch-by-id lane, which is what populates identity_keys.domain so
    _writeSafetyAllows can match a TEST_RECORD_DOMAINS allowlist -- the only allowlist that
    can be armed for a company that does not exist yet (plan 03's disposable)."""
    with_domain = m.build_webhook_event(PINNED_ID, domain="tvjc.example")
    assert with_domain[0]["domain"] == "tvjc.example"
    assert set(with_domain[0]) == _D18_KEYS | {"domain"}

    assert "domain" not in m.build_webhook_event(PINNED_ID, domain=None)[0]


def test_post_webhook_event_threads_recompute_and_domain_into_the_body():
    transport = _FakeTransport()

    m.post_webhook_event(
        PINNED_ID, True, _WEBHOOK_CONFIG, transport=transport,
        recompute=True, domain="tvjc.example",
    )

    assert len(transport.calls) == 1
    body = transport.calls[0]["json"]
    assert body[0]["recompute"] is True
    assert body[0]["domain"] == "tvjc.example"
    assert transport.calls[0]["headers"]["X-Enrichment-Secret"] == "fake-secret"


def test_post_webhook_event_read_timeout_defaults_to_300_seconds():
    """Phase 47 correction 4: this function hardcoded timeout=30, and a lane that reaches
    Decide runs far longer than that -- Phase 47 burned a window on a read timeout against a
    run n8n had ALREADY COMPLETED, and patched it in a throwaway driver's transport wrapper
    (.planning/phases/47-veto-remediation/47-armed-driver.py) instead of in the script. The
    correction belongs here."""
    transport = _FakeTransport()

    m.post_webhook_event(PINNED_ID, True, _WEBHOOK_CONFIG, transport=transport)

    assert transport.calls[0]["timeout"] == 300


def test_post_webhook_event_timeout_is_overridable_per_call():
    transport = _FakeTransport()

    m.post_webhook_event(PINNED_ID, True, _WEBHOOK_CONFIG, transport=transport, timeout=12)

    assert transport.calls[0]["timeout"] == 12


def test_post_webhook_event_still_refuses_when_not_armed_even_with_recompute():
    """`armed` stays a positional with no default -- the recompute option must not become a
    second way to reach the network unarmed."""
    transport = _FakeTransport()

    with pytest.raises(m.NotArmedError):
        m.post_webhook_event(
            PINNED_ID, False, _WEBHOOK_CONFIG, transport=transport, recompute=True)

    assert transport.calls == []


# --- 2026-08-29 bare-assert sweep: the D-07 guard is now src.guards.assert_disjoint,
# not a bare `assert` -- prove it still fires under PYTHONOPTIMIZE=1 (the whole point
# of the change; see also tests/test_guards.py for the shared helper's own coverage).

def test_forbidden_props_guard_survives_pythonoptimize_at_the_real_call_site():
    import os
    import subprocess
    import textwrap

    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        import scripts.remediate_veto_companies as m
        from src.schemas import ProviderEvidence, ProviderResult

        m.FORBIDDEN_PROPS = frozenset({{"lv_org_type"}})
        result = ProviderResult(
            provider="claude_web", object_type="companies", matched=True, confidence=90,
            data={{"lv_org_type": "broadcaster"}},
            evidence=ProviderEvidence(evidence_urls=["https://example.org"]),
        )
        try:
            m.build_input_patch("test-id", result)
        except ValueError as exc:
            assert "forbidden derived-field key" in str(exc), exc
            print("GUARD FIRED")
        else:
            print("GUARD DID NOT FIRE")
    """)

    proc = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "PYTHONOPTIMIZE": "1"},
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "GUARD FIRED" in proc.stdout, proc.stdout


def test_pinned_excluded_disjoint_guard_survives_pythonoptimize():
    """The module-level PINNED_COMPANY_IDS/EXCLUDED_COMPANY_IDS invariant (2026-08-29
    sweep: this used to be a bare `assert`, evaluated at import time) -- a collision
    would let a verified-correct non-ANZ record become write-eligible."""
    import os
    import subprocess
    import textwrap

    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        from src.guards import assert_disjoint
        try:
            assert_disjoint({{"a"}}, {{"a"}}, "a pinned id and an excluded id collided")
        except ValueError as exc:
            print("GUARD FIRED")
        else:
            print("GUARD DID NOT FIRE")
    """)

    proc = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "PYTHONOPTIMIZE": "1"},
        capture_output=True, text=True, timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "GUARD FIRED" in proc.stdout, proc.stdout
