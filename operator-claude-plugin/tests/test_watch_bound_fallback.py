"""Tests for watch.py Task 1 — the never-goes-quiet guarantee (D-05, D-07, NOTICE-02).

Drives ``poll_until_settled`` from both sides of the bound using a fake clock that
advances only when the loop itself calls ``sleep`` — no test here ever calls a real
``time.sleep``, so the suite stays fast and the bound boundary is exercised
deterministically rather than by timing luck.
"""
import json
from pathlib import Path

import report
import watch

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_CONFIG = PLUGIN_ROOT / "config" / "operator.local.example.json"


class FakeClock:
    """`.now()` reads the current fake time; `.sleep(seconds)` advances it — the loop's
    own two injection points (`now=`/`sleep=`), never a real clock."""

    def __init__(self, start=0.0):
        self.t = start
        self.sleeps = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += seconds


def _in_flight_execution(execution_id="e-1"):
    return {"id": execution_id, "status": "running", "startedAt": "2026-08-03T10:00:00.000Z"}


def _settled_execution(execution_id="e-1"):
    return {
        "id": execution_id,
        "status": "success",
        "startedAt": "2026-08-03T10:00:00.000Z",
        "stoppedAt": "2026-08-03T10:00:35.000Z",
        "data": {"resultData": {"runData": {}}},
    }


# =====================================================================================
# resolve_bound_seconds — config first, the measured default when absent (D-05/D-06).
# =====================================================================================

def test_bound_uses_measured_default_when_key_absent():
    assert watch.resolve_bound_seconds({}) == watch.DEFAULT_BOUND_SECONDS == 600.0


def test_bound_uses_config_value_when_present():
    assert watch.resolve_bound_seconds({"watch_bound_seconds": 900}) == 900.0


def test_bound_falls_back_on_unparseable_config_value():
    assert watch.resolve_bound_seconds({"watch_bound_seconds": "not-a-number"}) == watch.DEFAULT_BOUND_SECONDS


def test_bound_falls_back_on_non_positive_config_value():
    assert watch.resolve_bound_seconds({"watch_bound_seconds": 0}) == watch.DEFAULT_BOUND_SECONDS
    assert watch.resolve_bound_seconds({"watch_bound_seconds": -5}) == watch.DEFAULT_BOUND_SECONDS


def test_bound_scales_up_for_a_known_multi_record_dispatch():
    # max(600, 20 * 45) = 900 — the per-dispatch floor never drops below the measured
    # single-record default, only rises for a bigger known batch.
    assert watch.resolve_bound_seconds({}, record_count=20) == 900.0


def test_bound_scaling_never_lowers_the_floor_for_a_small_known_count():
    assert watch.resolve_bound_seconds({}, record_count=2) == watch.DEFAULT_BOUND_SECONDS


def test_bound_scaling_ignores_an_unknown_record_count():
    # record_count=None is the backend-resolved-list case (D-02 elsewhere in this
    # milestone) — nothing to scale by, so the floor is left alone rather than guessed.
    assert watch.resolve_bound_seconds({}, record_count=None) == watch.DEFAULT_BOUND_SECONDS


# =====================================================================================
# poll_until_settled — settles-just-inside the bound.
# =====================================================================================

def test_settles_before_the_bound_returns_a_settled_report():
    clock = FakeClock()
    reads = [_in_flight_execution(), _in_flight_execution(), _settled_execution()]

    def read_once():
        return reads.pop(0)

    result = watch.poll_until_settled(
        read_once, bound_seconds=600, run_handle={"execution_id": "e-1", "best_effort": True},
        now=clock.now, sleep=clock.sleep,
    )

    assert result["kind"] == "settled"
    assert result["state"] == "finished"
    assert clock.t < 600, "must not have needed to approach the bound to settle"
    assert not reads, "the loop must stop polling the instant it settles"


def test_settled_result_is_never_empty_or_falsy():
    clock = FakeClock()
    result = watch.poll_until_settled(
        lambda: _settled_execution(), bound_seconds=600,
        run_handle={"execution_id": "e-1"}, now=clock.now, sleep=clock.sleep,
    )
    assert result
    assert result is not None


# =====================================================================================
# poll_until_settled — unsettled-at-the-bound (NOTICE-02's headline guarantee).
# =====================================================================================

def test_unsettled_at_the_bound_returns_still_running_with_handle_and_recheck():
    clock = FakeClock()
    handle = {"execution_id": "e-99", "status": "running", "best_effort": True}

    result = watch.poll_until_settled(
        lambda: _in_flight_execution("e-99"), bound_seconds=20,
        run_handle=handle, now=clock.now, sleep=clock.sleep,
    )

    assert result["kind"] == "still_running"
    assert result["state"] == "in_flight"
    assert result["handle"] == handle
    assert result["elapsed_seconds"] >= result["bound_seconds"]
    assert result["recheck"]["execution_id"] == "e-99"
    assert result["recheck"]["how"]


def test_unsettled_result_is_never_empty_or_falsy():
    clock = FakeClock()
    result = watch.poll_until_settled(
        lambda: None, bound_seconds=15, run_handle=None, now=clock.now, sleep=clock.sleep,
    )
    assert result
    assert result is not None
    assert result["handle"] is None, "an absent handle must still be carried explicitly, never omitted"


def test_no_reader_input_ever_returns_a_third_shape():
    """Across a spread of reader behaviours (settled immediately, never settles, always
    None, a malformed non-dict payload), every result is one of exactly two kinds."""
    clock_factories = [FakeClock, FakeClock, FakeClock, FakeClock]
    readers = [
        lambda: _settled_execution(),
        lambda: _in_flight_execution(),
        lambda: None,
        lambda: "not-a-dict-execution",
    ]
    for clock_cls, reader in zip(clock_factories, readers):
        clock = clock_cls()
        result = watch.poll_until_settled(
            reader, bound_seconds=10, run_handle={"execution_id": "e-x"},
            now=clock.now, sleep=clock.sleep,
        )
        assert result["kind"] in {"settled", "still_running"}


def test_the_still_running_report_states_the_correlation_basis_is_timing_not_an_id():
    clock = FakeClock()
    result = watch.poll_until_settled(
        lambda: _in_flight_execution(), bound_seconds=10,
        run_handle={"execution_id": "e-1", "best_effort": True},
        now=clock.now, sleep=clock.sleep,
    )
    basis = result["correlation_basis"].lower()
    assert "timing" in basis
    assert "not by an execution id" in basis
    assert result["recheck"]["best_effort"] is True


def test_backoff_widens_rather_than_hammering_a_tight_interval():
    clock = FakeClock()
    watch.poll_until_settled(
        lambda: _in_flight_execution(), bound_seconds=200,
        run_handle=None, now=clock.now, sleep=clock.sleep,
    )
    # Strictly non-decreasing, and not every wait is the tightest interval — a poll loop
    # that hammered a fixed 5s interval for the whole bound would fail this.
    assert clock.sleeps == sorted(clock.sleeps)
    assert max(clock.sleeps) > clock.sleeps[0]


# =====================================================================================
# The config key ships with the measured default (acceptance criterion, D-05).
# =====================================================================================

def test_example_config_parses_as_json_and_carries_watch_bound_seconds():
    parsed = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    assert parsed["watch_bound_seconds"] == 600


# =====================================================================================
# Structural guard: SETTLED_STATUSES is report.py's own convention, not a second one.
# =====================================================================================

def test_is_settled_uses_reports_own_settled_statuses_constant():
    for status in report.SETTLED_STATUSES:
        assert watch._is_settled({"status": status})
    assert not watch._is_settled({"status": "running"})
    assert not watch._is_settled({"status": "some-new-status-never-seen"})
    assert not watch._is_settled(None)
    assert not watch._is_settled("not-a-dict")
