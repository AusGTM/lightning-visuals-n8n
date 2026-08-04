"""Tests for INGEST-04 / DISPATCH-02 — the enrichment lane's client envelope.

The three silent-failure shapes this file exists to pin, none of which raises anything at
the backend:
  - an omitted/unknown `providers` value enriches nothing and returns a clean 200 (D-06a),
  - a saved-view name resolved as if it were a list enriches the WRONG record set
    (25-BLOCKERS.md amendment #7, 25-RESEARCH Pitfall 2),
  - a forgotten `armed` argument sends (Phase 23 D-11).
"""
import inspect
import json

import pytest

import config_gate
import enrichment


# =====================================================================================
# Provider selection — total, explicit, and loud about an unknown name.
# =====================================================================================

def test_no_override_returns_the_config_default_unchanged(fake_config):
    fake_config["enrichment_providers"] = ["lusha", "apollo"]
    assert enrichment.resolve_providers(None, fake_config) == ["lusha", "apollo"]


def test_override_wins_over_the_config_default(fake_config):
    fake_config["enrichment_providers"] = ["lusha", "apollo", "zoominfo"]
    assert enrichment.resolve_providers(["lusha"], fake_config) == ["lusha"]


def test_config_without_the_key_falls_back_to_the_full_waterfall(fake_config):
    """D-03's shipped default must not depend on whether the operator copied the key —
    a missing key resolving to [] would be a batch that enriches nothing."""
    assert "enrichment_providers" not in fake_config
    assert enrichment.resolve_providers(None, fake_config) == enrichment.FULL_WATERFALL


def test_explicitly_empty_selection_resolves_to_an_empty_list(fake_config):
    assert enrichment.resolve_providers([], fake_config) == []
    assert enrichment.resolve_providers("none", fake_config) == []


def test_all_resolves_to_the_named_waterfall_rather_than_the_bare_keyword(fake_config):
    """The preview has to state which providers this batch uses (D-06); "all" states
    nothing an operator can read."""
    assert enrichment.resolve_providers("all", fake_config) == enrichment.FULL_WATERFALL


def test_unknown_provider_name_raises_rather_than_being_dropped(fake_config):
    with pytest.raises(enrichment.ProviderSelectionError) as excinfo:
        enrichment.resolve_providers(["lusha", "clearbit"], fake_config)
    assert "clearbit" in str(excinfo.value)


def test_resolution_is_total_over_every_input_shape(fake_config):
    """No input path may return None or omit the answer — the backend has no default to
    fall back to."""
    for override in (None, [], ["lusha"], ["LUSHA", "lusha"], "all", "none", ("apollo",)):
        resolved = enrichment.resolve_providers(override, fake_config)
        assert isinstance(resolved, list)
    for bad in ("waterfall", 7, {"lusha": True}):
        with pytest.raises(enrichment.ProviderSelectionError):
            enrichment.resolve_providers(bad, fake_config)


def test_names_are_normalized_and_deduped(fake_config):
    assert enrichment.resolve_providers([" Lusha ", "LUSHA"], fake_config) == ["lusha"]


# =====================================================================================
# Envelope building.
# =====================================================================================

def test_record_ids_become_one_event_each_with_stringified_ids():
    envelope = enrichment.build_envelope(
        {"record_ids": [789, "790"], "object_type": "company"}, ["lusha"]
    )
    assert envelope["events"] == [
        {"objectId": "789", "objectType": "companies"},
        {"objectId": "790", "objectType": "companies"},
    ]


def test_record_id_order_is_preserved():
    ids = ["5", "3", "9", "1"]
    envelope = enrichment.build_envelope(
        {"record_ids": ids, "object_type": "contacts"}, []
    )
    assert [event["objectId"] for event in envelope["events"]] == ids


def test_events_carry_only_the_id_and_object_type():
    """The deployed parser spreads extra event keys onto the row. Sending more widens
    what crosses the boundary for no gain on a record that already exists (T-25-18)."""
    envelope = enrichment.build_envelope(
        {"record_ids": ["1"], "object_type": "contacts", "email": "a@b.c"}, ["lusha"]
    )
    assert set(envelope["events"][0]) == {"objectId", "objectType"}


def test_list_name_is_carried_verbatim_with_no_events_and_no_count():
    envelope = enrichment.build_envelope(
        {"list": "New Targets.xlsx", "object_type": "contacts"}, ["lusha"]
    )
    # NESTED, per D-19 — the backend reads isPlainObject(body.list) then .name/.objectType.
    # A flat {"list": "<name>", "objectType": ...} is refused by every request while both
    # sides' own tests stay green; see test_list_envelope_contract.py.
    assert envelope["list"] == {"name": "New Targets.xlsx", "objectType": "contacts"}
    assert "objectType" not in envelope, "objectType belongs inside `list`, not beside it"
    assert "events" not in envelope
    assert not any("count" in key.lower() for key in envelope)


def test_a_saved_view_is_refused_with_the_recorded_sentence():
    with pytest.raises(enrichment.ViewNotSupportedError) as excinfo:
        enrichment.build_envelope({"view": "My Q3 targets"}, ["lusha"])
    assert str(excinfo.value) == enrichment.VIEW_REFUSAL
    assert "doesn't expose views through its API" in str(excinfo.value)


def test_a_saved_view_is_never_resolved_as_a_list():
    """Pitfall 2: a view name colliding with a real list name would enrich the wrong
    record set with no error. Naming both must still refuse."""
    with pytest.raises(enrichment.ViewNotSupportedError):
        enrichment.build_envelope(
            {"view": "New Targets.xlsx", "list": "New Targets.xlsx",
             "object_type": "contacts"}, ["lusha"]
        )


def test_an_empty_id_collection_raises_rather_than_producing_an_empty_batch():
    for spec in ({"record_ids": [], "object_type": "contacts"},
                 {"record_ids": None, "object_type": "contacts"},
                 {"object_type": "contacts"},
                 {}):
        with pytest.raises(enrichment.RecordSpecError):
            enrichment.build_envelope(spec, ["lusha"])


def test_an_unrecognized_object_type_raises_rather_than_sending_unknown():
    """The deployed normalizer's fallback is the string "unknown", which downstream
    processes into nothing while still returning 200."""
    with pytest.raises(enrichment.RecordSpecError):
        enrichment.build_envelope({"record_ids": ["1"], "object_type": "deals"}, [])
    with pytest.raises(enrichment.RecordSpecError):
        enrichment.build_envelope({"list": "x", "object_type": None}, [])


def test_every_record_specification_form_carries_the_providers_key():
    for spec in ({"record_ids": ["1"], "object_type": "contacts"},
                 {"list": "New Targets.xlsx", "object_type": "contacts"}):
        for providers in ([], ["lusha"], enrichment.FULL_WATERFALL):
            envelope = enrichment.build_envelope(spec, providers)
            assert "providers" in envelope, (
                "an absent providers key resolves server-side to zero providers and "
                "still returns 200 — a silent no-op"
            )
            assert envelope["providers"] == providers


def test_the_envelope_is_json_serializable():
    body = enrichment.build_envelope(
        {"record_ids": [1, 2], "object_type": "companies"}, ["lusha"]
    )
    assert json.loads(json.dumps(body)) == body


# =====================================================================================
# Dispatch — disarmed by default, one call, no secret in any failure text.
# =====================================================================================

def _envelope():
    return enrichment.build_envelope(
        {"record_ids": ["789"], "object_type": "companies"}, ["lusha"]
    )


def test_disarmed_dispatch_raises_and_the_transport_records_zero_calls(
    fake_config, stub_module_transport_factory
):
    transport = stub_module_transport_factory()
    with pytest.raises(enrichment.NotArmedError):
        enrichment.dispatch_enrichment(_envelope(), False, fake_config, transport=transport)
    assert transport.calls == [], "the request must not exist at all when disarmed"


def test_missing_webhook_secret_refuses_before_the_transport_is_touched_even_when_armed(
    fake_config, stub_module_transport_factory
):
    """Regression guard for the load-config-over-refusal fix: `load_config()` no longer
    enforces `webhook_secret` for every caller, so `dispatch_enrichment()` must guard its
    own transmit path itself — otherwise a secret-less config would reach
    `config["webhook_secret"]` (KeyError) or send an empty secret header."""
    cfg = {k: v for k, v in fake_config.items() if k != "webhook_secret"}
    transport = stub_module_transport_factory()
    with pytest.raises(config_gate.ConfigError) as exc:
        enrichment.dispatch_enrichment(_envelope(), True, cfg, transport=transport)
    assert "webhook_secret" in str(exc.value)
    assert transport.calls == []


def test_dispatch_with_no_armed_argument_at_all_raises_a_type_error(
    fake_config, stub_module_transport_factory
):
    transport = stub_module_transport_factory()
    with pytest.raises(TypeError):
        enrichment.dispatch_enrichment(_envelope(), config=fake_config, transport=transport)
    assert transport.calls == []


def test_armed_dispatch_posts_the_envelope_once_to_the_enrichment_webhook(
    fake_config, stub_module_transport_factory
):
    transport = stub_module_transport_factory()
    envelope = _envelope()

    enrichment.dispatch_enrichment(envelope, True, fake_config, transport=transport)

    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["verb"] == "post"
    assert call["url"] == (
        "https://fake-tenant.n8n.cloud/webhook/hubspot/enrichment/event"
    )
    assert call["headers"] == {"X-Enrichment-Secret": fake_config["webhook_secret"]}
    assert call["json"] == envelope
    assert isinstance(call["timeout"], (int, float)) and call["timeout"] > 0


def test_armed_dispatch_returns_the_parsed_json_body(
    fake_config, stub_module_transport_factory
):
    transport = stub_module_transport_factory([{"status": "accepted"}])
    result = enrichment.dispatch_enrichment(_envelope(), True, fake_config, transport=transport)
    assert result == {"status": "accepted"}


def test_a_non_json_body_returns_the_status_and_raw_text(
    fake_config, stub_module_transport_factory
):
    transport = stub_module_transport_factory([(502, ValueError("not json"))])
    result = enrichment.dispatch_enrichment(_envelope(), True, fake_config, transport=transport)
    assert result["status_code"] == 502


def test_a_transport_exception_surfaces_without_the_secret(
    fake_config, stub_module_transport_factory
):
    boom = RuntimeError(
        f"connection refused; sent X-Enrichment-Secret: {fake_config['webhook_secret']}"
    )
    transport = stub_module_transport_factory([boom])
    with pytest.raises(enrichment.DispatchError) as excinfo:
        enrichment.dispatch_enrichment(_envelope(), True, fake_config, transport=transport)
    assert fake_config["webhook_secret"] not in str(excinfo.value)


def test_no_function_in_this_module_gives_armed_a_default():
    """The permanent form of 25-04's `armed`-has-no-default acceptance check.

    The plan's own one-liner walks `vars(module)` and calls `inspect.signature` on every
    callable — which on Python 3.14 raises `ValueError: no signature found for builtin
    type` on any bare `Exception` subclass, and so fails identically against Phase 23's
    `dispatch.py`. Restricting the walk to functions is the corrected form.
    """
    armed_takers = [
        func for _name, func in inspect.getmembers(enrichment, inspect.isfunction)
        if inspect.getmodule(func) is enrichment
        and "armed" in inspect.signature(func).parameters
    ]
    assert armed_takers, "this guard has gone vacuous — no function takes `armed` at all"
    for func in armed_takers:
        assert inspect.signature(func).parameters["armed"].default is inspect.Parameter.empty, (
            f"{func.__name__}()'s `armed` parameter gained a default — a forgotten "
            "argument must raise, never silently send (T-25-01)."
        )


def test_dispatch_persists_nothing_about_the_grant(
    fake_config, stub_module_transport_factory
):
    """The arming grant lives only as this call's argument (Phase 23 D-11) — a second,
    disarmed call must refuse exactly as the first would have."""
    transport = stub_module_transport_factory()
    enrichment.dispatch_enrichment(_envelope(), True, fake_config, transport=transport)
    with pytest.raises(enrichment.NotArmedError):
        enrichment.dispatch_enrichment(_envelope(), False, fake_config, transport=transport)
    assert len(transport.calls) == 1
