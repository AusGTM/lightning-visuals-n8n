"""operator-claude-plugin/tests/test_scale_up_runtime.py

Phase 61 Plan 06 Task 5 (T-61-25, RUN-02/AFTER-02's substrate-3 scale-up path). The
CLIENT-side half of the proof — the n8n-side depth bound and topology are pinned in
tests/n8n/scaleUpFanOutFlow.test.mjs. This file proves three things, each offline with an
injected transport, no live n8n/HubSpot/Anthropic call anywhere in it:

1. `chunking.dispatch_plan`'s `scale_up` keyword defaults to `False` and, when omitted or
   `False`, sends the byte-identical envelope every existing caller sends today (mirrors
   61-05's own async_ack precedent, which this plan's own docstring calls "a pattern, not
   an invention").
2. There is NO client-side depth knob to forge. `dispatch_plan` accepts `scale_up` only —
   never a `fan_depth`/`depth` parameter — so a caller cannot manufacture the trust the
   n8n-side depth counter is built to withhold (`scripts/build_cloud_workflows.py`'s
   `SCALE_UP_MAX_FAN_DEPTH`/`ENRICH_BUILD_SCALE_UP_FAN_OUT`). Asserted structurally via
   `inspect.signature`, not by trying and catching a call that happens to fail today.
3. The five-bucket invariant (`run_state.read_progress`'s own internal assertion) holds
   over a run shaped like a fanned-out one: some rows done, one held, one FAILED (a
   "child failed" outcome), some still running. No new production accounting code is
   introduced for this — `run_state.py`/`run_manifest.py` already partition a run this
   way; this proves scale-up's shape is nothing new to them.
"""
import inspect

import chunking
import run_manifest
import run_state


def _point_at_a_fake_durable_home(monkeypatch, tmp_path):
    # Mirrors test_run_state.py's own fixture verbatim (a small, load-bearing helper this
    # repo's own precedent says to copy rather than import — see held_queue.py's own
    # docstring for why a shared predicate this small is duplicated, not imported).
    fake_durable = tmp_path / "durable"
    fake_durable.mkdir()
    (fake_durable / "dashboard_artifact.json").write_text("{}")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(fake_durable))


PROVIDERS = ["zoominfo", "lusha"]


def _one_chunk_plan():
    return chunking.plan_chunks(
        {"record_ids": ["1", "2"], "object_type": "companies"}, 2
    )


# --- 1. flag off is byte-identical -------------------------------------------------------

def test_scale_up_defaults_to_false(fake_config, stub_module_transport_factory):
    """No caller has to opt out — the parameter's own default is the safe one."""
    default = inspect.signature(chunking.dispatch_plan).parameters["scale_up"].default
    assert default is False


def test_omitting_scale_up_sends_the_byte_identical_envelope_every_existing_caller_sends_today(
    fake_config, stub_module_transport_factory
):
    with_flag_omitted = stub_module_transport_factory()
    chunking.dispatch_plan(_one_chunk_plan(), PROVIDERS, True, fake_config, transport=with_flag_omitted)

    with_flag_false = stub_module_transport_factory()
    chunking.dispatch_plan(
        _one_chunk_plan(), PROVIDERS, True, fake_config, transport=with_flag_false,
        scale_up=False,
    )

    assert with_flag_omitted.calls[0]["json"] == with_flag_false.calls[0]["json"]
    assert "scale_up" not in with_flag_omitted.calls[0]["json"], (
        "a request that never opts in must not even carry the key — the byte-identical "
        "envelope this task's must_haves require"
    )


def test_scale_up_true_adds_exactly_one_key_to_the_envelope_and_changes_nothing_else(
    fake_config, stub_module_transport_factory
):
    off = stub_module_transport_factory()
    chunking.dispatch_plan(_one_chunk_plan(), PROVIDERS, True, fake_config, transport=off)

    on = stub_module_transport_factory()
    chunking.dispatch_plan(
        _one_chunk_plan(), PROVIDERS, True, fake_config, transport=on, scale_up=True,
    )

    off_envelope = off.calls[0]["json"]
    on_envelope = on.calls[0]["json"]
    assert on_envelope["scale_up"] is True
    without_the_new_key = {k: v for k, v in on_envelope.items() if k != "scale_up"}
    assert without_the_new_key == off_envelope


# --- 2. no client-side depth knob exists --------------------------------------------------

def test_dispatch_plan_has_no_depth_parameter_to_forge():
    """The depth bound this feature's safety rests on (T-61-25) is a workflow-internal
    counter n8n's own "Build Scale Up Fan-Out" node owns and increments
    (scripts/build_cloud_workflows.py). If the client ever gained a `fan_depth`/`depth`
    parameter here, a caller could pass a fabricated one straight through the envelope
    and defeat the "no depth supplied still terminates" guarantee at its source, rather
    than at the guard. There must be no such knob, structurally."""
    params = set(inspect.signature(chunking.dispatch_plan).parameters)
    assert "fan_depth" not in params
    assert "depth" not in params


def test_build_envelope_never_emits_a_depth_field_either():
    """Same assertion one layer down — `enrichment.build_envelope` is what actually
    shapes the wire payload `scale_up` rides on; it must carry no depth field for
    dispatch_plan's own `scale_up` branch to inject one into."""
    envelope = chunking.enrichment.build_envelope(
        {"record_ids": ["1"], "object_type": "companies"}, PROVIDERS
    )
    assert "fan_depth" not in envelope
    assert "depth" not in envelope


# --- 3. the five-bucket invariant holds over a fanned-out-shaped run ---------------------

def test_five_bucket_invariant_holds_over_a_run_shaped_like_a_fanned_out_one(
    monkeypatch, tmp_path
):
    """Simulates what a scale_up=true run's CLIENT-side accounting would look like: every
    row dispatched in ONE POST (the parent's own single top-level execution), then
    verdicts arriving as if some fanned-out children succeeded, one was held, and one
    FAILED without stranding the rest — read_progress()'s own internal five-bucket
    assertion (REVIEW-A6) is the mechanism this proves compatible, not a new one."""
    _point_at_a_fake_durable_home(monkeypatch, tmp_path)
    run_id = "run-scale-up-1"
    row_ids = ["r1", "r2", "r3", "r4", "r5"]
    run_state.start_run(run_id, row_ids)
    # A fanned-out dispatch marks the WHOLE batch dispatched in one call — there is no
    # per-chunk loop on the client side once the parent fans out internally.
    run_state.mark_dispatched(run_id, row_ids)
    run_manifest.save(run_id, {
        "r1": run_manifest.MATCHED,          # a child that ran and matched
        "r2": run_manifest.ENRICHED,          # a child that ran and enriched
        "r3": run_manifest.HELD,              # a child that held rather than landing
        "r4": run_manifest.UNCHECKED,         # a child that FAILED — the batch is not stranded
        # r5 carries no verdict yet — still "running" (its child has not reported back).
    }, path=run_manifest.run_manifest_path(run_id))

    progress = run_state.read_progress(run_id)
    assert progress.state == run_state.OK
    assert progress.total == 5
    assert progress.done == 2
    assert progress.held == 1
    assert progress.failed == 1
    assert progress.running == 1
    assert progress.pending == 0
    assert (
        progress.pending + progress.running + progress.done + progress.held
        + progress.failed
    ) == progress.total, "a fanned-out run's failed child must not strand the batch's own accounting"
