"""operator-claude-plugin/tests/test_scale_up_retired.py

Phase 70 Plan 13 Task 3 (G-70-5, D-70-24). Was `test_scale_up_runtime.py`, the CLIENT-side
half of the substrate-3 scale-up proof. The n8n-side lane it paired with looped live on
2026-09-10 — 135 child executions in six minutes from four disarmed sends (12211-12348),
from a node whose only declared producer emitted zero items — and was deleted rather than
guarded, because only the ABSENCE of a self-referencing Execute Workflow node makes
recursion impossible on this engine.

So the cases that exercised the fan-out are gone, and the two that asserted the client
could not manufacture one are KEPT and re-framed: they were opt-out defaults, and they are
now permanent structural properties.

1. No envelope this plugin builds ever carries the fan-out key, and there is no parameter
   that could put one there.
2. There is no client-side depth knob, at either layer.
3. A caller still passing the retired keyword is swallowed, never raised at — the same
   retirement precedent the early-ack flag set in this same function (D-70-07).

Offline throughout: injected transport, no live n8n/HubSpot/Anthropic call anywhere.
"""
import inspect

import chunking

PROVIDERS = ["zoominfo", "lusha"]


def _one_chunk_plan():
    return chunking.plan_chunks(
        {"record_ids": ["1", "2"], "object_type": "companies"}, 2
    )


# --- 1. the key can never ride an envelope ------------------------------------------------

def test_no_envelope_this_plugin_builds_ever_carries_the_fan_out_key(
    fake_config, stub_module_transport_factory
):
    """Was "omitting the flag sends the byte-identical envelope" — an opt-out default.
    It is now unconditional: there is no branch left that could stamp the key."""
    transport = stub_module_transport_factory()
    chunking.dispatch_plan(
        _one_chunk_plan(), PROVIDERS, True, fake_config, transport=transport,
        run_id="fixed-run-id",
    )
    assert "scale_up" not in transport.calls[0]["json"]


def test_dispatch_plan_has_no_fan_out_parameter_at_all():
    """The opt-in is retired, not merely defaulted off — a defaulted-off flag is one
    keyword away from a runaway, and this engine has already shown what that costs."""
    params = set(inspect.signature(chunking.dispatch_plan).parameters)
    assert "scale_up" not in params


# --- 2. no client-side depth knob exists --------------------------------------------------

def test_dispatch_plan_has_no_depth_parameter_to_forge():
    """Kept verbatim in intent from the retired module: the client never had a way to
    name a fan depth, and must not gain one if the feature is ever reconsidered."""
    params = set(inspect.signature(chunking.dispatch_plan).parameters)
    assert "fan_depth" not in params
    assert "depth" not in params


def test_build_envelope_never_emits_a_depth_field_either():
    """Same assertion one layer down — `enrichment.build_envelope` is what actually shapes
    the wire payload."""
    envelope = chunking.enrichment.build_envelope(
        {"record_ids": ["1"], "object_type": "companies"}, PROVIDERS
    )
    assert "fan_depth" not in envelope
    assert "depth" not in envelope


# --- 3. a stale caller degrades, never errors ---------------------------------------------

def test_a_caller_still_passing_the_retired_keyword_is_ignored_not_rejected(
    fake_config, stub_module_transport_factory
):
    """The retirement precedent D-70-07 set for the early-ack flag in this same function:
    `**_ignored_legacy_kwargs` swallows it, so a stale caller degrades to the new
    behaviour instead of dying on a TypeError — and still sends no fan-out key."""
    transport = stub_module_transport_factory()
    chunking.dispatch_plan(
        _one_chunk_plan(), PROVIDERS, True, fake_config, transport=transport,
        run_id="fixed-run-id", scale_up=True,
    )
    assert "scale_up" not in transport.calls[0]["json"]
