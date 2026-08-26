"""Phase 54 Task 1 — measure_dispatch.py, offline.

A fake transport stands in for `requests.get` throughout (`conftest.py`'s autouse
`no_network` guard blocks a real socket for every test in this suite regardless). Nothing
here ever calls `n8n_arming`/`armed_window` — the module under test cannot, by
construction (see `test_the_module_never_imports_arming`).
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest

import executions_client
import measure_dispatch

WORKFLOW_ID = "wf-enrichment-1"


def _iso(hour, minute=0):
    return f"2026-08-26T{hour:02d}:{minute:02d}:00.000Z"


def _dt(hour, minute=0):
    return datetime(2026, 8, 26, hour, minute, tzinfo=timezone.utc)


class _RaisingTransport:
    def __call__(self, *args, **kwargs):
        raise ConnectionError("simulated transport failure")


def _list_transport(payload):
    def _get(url, headers=None, params=None, timeout=None):
        class _Resp:
            def json(self):
                return {"data": payload}
        return _Resp()
    return _get


# --------------------------------------------------------------- executions_in_window


def test_a_window_with_two_passes_for_one_record(monkeypatch):
    executions = [
        {"id": "e1", "startedAt": _iso(10, 0), "hs_object_id": "347569451461"},
        {"id": "e2", "startedAt": _iso(10, 1), "hs_object_id": "347569451461"},
        {"id": "e3", "startedAt": _iso(9, 0), "hs_object_id": "347569451461"},  # outside window
    ]
    transport = _list_transport(executions)
    windowed = measure_dispatch.executions_in_window(
        {"n8n_url": "https://fake.n8n.cloud", "n8n_api_key": "x"}, WORKFLOW_ID,
        _dt(9, 30), _dt(11, 0), transport=transport)

    assert [e["id"] for e in windowed] == ["e2", "e1"]  # newest-first

    result = measure_dispatch.passes_for_record(windowed, "347569451461")
    assert result == {"count": 2, "execution_ids": ["e2", "e1"], "basis": "measured"}


def test_a_window_with_one_pass_for_one_record(monkeypatch):
    executions = [
        {"id": "e1", "startedAt": _iso(10, 0), "hs_object_id": "347569451461"},
        {"id": "e2", "startedAt": _iso(10, 5), "hs_object_id": "999999999999"},
    ]
    transport = _list_transport(executions)
    windowed = measure_dispatch.executions_in_window(
        {"n8n_url": "https://fake.n8n.cloud", "n8n_api_key": "x"}, WORKFLOW_ID,
        _dt(9, 30), _dt(11, 0), transport=transport)

    result = measure_dispatch.passes_for_record(windowed, "347569451461")
    assert result == {"count": 1, "execution_ids": ["e1"], "basis": "measured"}


def test_a_window_with_no_per_record_key_treats_every_execution_as_a_pass():
    """The real shape of n8n's own `/executions` list — no domain/id payload field at
    all. The window itself, scoped by the caller to one record's known send, is the
    correlation; this must not silently report zero for a window it cannot look inside."""
    executions = [
        {"id": "e1", "startedAt": _iso(10, 0)},
        {"id": "e2", "startedAt": _iso(10, 1)},
    ]
    result = measure_dispatch.passes_for_record(executions, "347569451461")
    assert result["count"] == 2
    assert result["basis"] == "measured"


def test_a_raising_transport_propagates_rather_than_returning_zero():
    with pytest.raises(executions_client.ExecutionsClientError):
        measure_dispatch.executions_in_window(
            {"n8n_url": "https://fake.n8n.cloud", "n8n_api_key": "x"}, WORKFLOW_ID,
            _dt(9, 30), _dt(11, 0), transport=_RaisingTransport())


def test_an_unread_window_is_none_not_zero():
    """`passes_for_record`'s own contract for the caller's "the read never happened"
    signal — never a count of `0` masquerading as a genuine empty window."""
    result = measure_dispatch.passes_for_record(None, "347569451461")
    assert result["count"] is None
    assert result["basis"] == "unmeasured"
    assert "reason" in result


# --------------------------------------------------------------------- compare_to_projection


def test_compare_to_projection_matches():
    measured = {"count": 3, "execution_ids": ["e1", "e2", "e3"], "basis": "measured"}
    projection = {"projected_executions": 3, "basis": {"projected_executions": "projected"}}
    result = measure_dispatch.compare_to_projection(measured, projection)
    assert result["verdict"] == "matches"
    assert result["delta"] == 0
    assert result["measured_executions"] == 3
    assert result["projected_executions"] == 3


def test_compare_to_projection_differs_and_both_numbers_survive():
    measured = {"count": 1, "execution_ids": ["e1"], "basis": "measured"}
    projection = {"projected_executions": 2, "basis": {"projected_executions": "projected"}}
    result = measure_dispatch.compare_to_projection(measured, projection)

    assert result["verdict"] == "differs"
    assert result["delta"] == -1
    # Neither figure overwrites the other.
    assert result["measured_executions"] == 1
    assert result["projected_executions"] == 2
    assert result["projection_basis"] == "projected"


def test_compare_to_projection_unmeasured_when_the_read_never_happened():
    measured = {"count": None, "execution_ids": [], "basis": "unmeasured",
                "reason": "no execution list was read for this window"}
    projection = {"projected_executions": 2, "basis": {"projected_executions": "projected"}}
    result = measure_dispatch.compare_to_projection(measured, projection)

    assert result["verdict"] == "unmeasured"
    assert result["delta"] is None
    assert result["measured_executions"] is None
    assert result["projected_executions"] == 2


# ------------------------------------------------------------------------------- T-54-01


def test_the_module_never_imports_arming():
    """T-54-01 — pinned as a plain text scan of the shipped source, matching the plan's
    own grep-shaped acceptance criterion (a docstring mention would fail this the same
    way an import would)."""
    import measure_dispatch as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    for forbidden in ("n8n_arming", "arm_for_dispatch", "armed_window"):
        assert forbidden not in source, f"{forbidden!r} must never appear in measure_dispatch.py"
