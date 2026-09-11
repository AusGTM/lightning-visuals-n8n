"""Behavioural drift guard for the forbidden-name refusal, across all eight stores
(quick 260911-any, closing todo 2026-09-08-forbidden-name-markers-refuse-secretary-
and-armidale; widened to eight by quick task 260911-ss4's `match_state.py`).

Tuple equality alone (`test_run_report.py`'s `is not` checks) cannot catch a copy whose
*matcher* was left on the old raw-substring rule -- only running one corpus through
every module's own `_looks_forbidden`(-shaped) function, by name, can. Each of the
eight modules reimplements its own matcher on purpose (D-69-01); this file is what
keeps the eight reimplementations behaviourally identical.
"""
import held_queue
import match_state
import remainder_queue
import run_manifest
import run_report
import run_state
import suggestion_declines
import written_records

# Seven modules expose a plain `_looks_forbidden(value) -> bool`. `run_report` is the
# eighth and is handled separately below -- it splits into `_looks_forbidden_key`
# (all ten markers) and `_looks_forbidden_value` (eight, `arm`/`webhook` exempt).
_KEY_MATCHER_MODULES = (
    held_queue,
    suggestion_declines,
    run_manifest,
    run_state,
    written_records,
    remainder_queue,
    match_state,
)

# Real names/values a whole-token matcher must let through unrefused.
MUST_PASS = (
    "Secretary",
    "Armidale Jockey Club",
    "Armstrong Racing",
    "pharmacy supplier",
    "farm",
    "disarmed",
    "The Roma Turf Club",
)

# Markers, compounds, and inflected/cased forms a whole-token matcher must still refuse.
MUST_REFUSE = (
    "arm",
    "armed",
    "arming",
    "armed_row",
    "webhook_secret",
    "n8n_api_key",
    "N8N_API_KEY",
    "webhookSecret",
    "apiKey",
    "credentials",
    "permissions",
    "api_tokens",
    "passwords",
    "grants",
    "op-grant-123",
) + held_queue._FORBIDDEN_NAME_MARKERS


def test_every_key_matcher_passes_the_must_pass_corpus():
    offenders = {
        module.__name__: [value for value in MUST_PASS if module._looks_forbidden(value)]
        for module in _KEY_MATCHER_MODULES
    }
    offenders = {name: bad for name, bad in offenders.items() if bad}
    assert not offenders, offenders


def test_every_key_matcher_refuses_the_must_refuse_corpus():
    offenders = {
        module.__name__: [
            value for value in MUST_REFUSE if not module._looks_forbidden(value)
        ]
        for module in _KEY_MATCHER_MODULES
    }
    offenders = {name: bad for name, bad in offenders.items() if bad}
    assert not offenders, offenders


def test_run_report_key_matcher_passes_and_refuses_the_same_corpus():
    passing_offenders = [v for v in MUST_PASS if run_report._looks_forbidden_key(v)]
    refusing_offenders = [
        v for v in MUST_REFUSE if not run_report._looks_forbidden_key(v)
    ]
    assert not passing_offenders, passing_offenders
    assert not refusing_offenders, refusing_offenders


def test_run_report_value_matcher_is_exempt_from_arm_and_webhook_by_design():
    """`_VALUE_MARKERS` deliberately drops `arm`/`webhook` (see `run_report.py`'s own
    docstring) -- `disarmed` and free text mentioning a webhook execution must not
    refuse as a VALUE even though every key matcher above refuses `webhook_secret`."""
    assert run_report._looks_forbidden_value("disarmed") is False
    assert run_report._looks_forbidden_value("1 webhook execution per chunk") is False
    assert run_report._looks_forbidden_value("secret") is True
    assert run_report._looks_forbidden_value("api_key") is True


def test_all_seven_forbidden_name_marker_tuples_are_equal_by_value():
    """The existing `is not` (distinct-object) assertions in `test_run_report.py:
    116-118` stay untouched and unduplicated here -- this only pins that no copy's
    ENUMERATED marker list has drifted, which is what makes one shared corpus mean
    anything across seven independently reimplemented matchers."""
    tuples = (
        held_queue._FORBIDDEN_NAME_MARKERS,
        suggestion_declines._FORBIDDEN_NAME_MARKERS,
        run_manifest._FORBIDDEN_NAME_MARKERS,
        run_state._FORBIDDEN_NAME_MARKERS,
        run_report._FORBIDDEN_NAME_MARKERS,
        written_records._FORBIDDEN_NAME_MARKERS,
        remainder_queue._FORBIDDEN_NAME_MARKERS,
    )
    assert all(t == tuples[0] for t in tuples)
    assert len(tuples[0]) == 10
