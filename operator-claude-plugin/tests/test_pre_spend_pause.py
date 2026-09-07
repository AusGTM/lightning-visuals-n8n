"""Tests for watch.py's pre-spend pause (D-68-05, Phase 68 plan 01 Task 1).

A real, once-per-round wall-clock pause immediately before the first credit-spending
call of a batch, so the window between the operator reading the stated line and
reacting actually exists. Every test here drives the pause through an injected
`sleep` recorder -- mirroring `poll_until_settled`'s `now=`/`sleep=` DI idiom
(test_watch_bound_fallback.py) -- so no test in this suite ever performs a real
wall-clock wait.
"""
import watch


def test_pre_spend_pause_seconds_in_band():
    assert isinstance(watch.PRE_SPEND_PAUSE_SECONDS, int)
    assert 5 <= watch.PRE_SPEND_PAUSE_SECONDS <= 10


def test_pre_spend_pause_calls_injected_sleep_once_with_default_seconds():
    calls = []
    watch.pre_spend_pause(sleep=calls.append)
    assert calls == [watch.PRE_SPEND_PAUSE_SECONDS]


def test_pre_spend_pause_explicit_seconds_wins_unrounded():
    calls = []
    watch.pre_spend_pause(3, sleep=calls.append)
    assert calls == [3]


def test_pre_spend_pause_resolves_time_sleep_when_no_sleep_injected(monkeypatch):
    calls = []
    monkeypatch.setattr(watch.time, "sleep", calls.append)
    watch.pre_spend_pause()
    assert calls == [watch.PRE_SPEND_PAUSE_SECONDS]


def test_pre_spend_pause_holds_no_state_across_calls():
    calls = []
    watch.pre_spend_pause(sleep=calls.append)
    watch.pre_spend_pause(sleep=calls.append)
    assert calls == [watch.PRE_SPEND_PAUSE_SECONDS, watch.PRE_SPEND_PAUSE_SECONDS]
