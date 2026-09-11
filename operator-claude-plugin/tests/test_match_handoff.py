"""operator-claude-plugin/tests/test_match_handoff.py

Quick task 260911-ss5 (F9). Drives `match_handoff.py`'s save/load/classify_read round
trip: the matched-id handoff `enrich-before-ingest` step 7 now persists so the ids it
hands to `enrich-records` survive the process (`.planning/UAT-autonomous-batch-
2026-09-09.md`, F9's second half).

Every test passes an explicit `path=tmp_path / "..."` per `conftest.py`'s autouse
`no_durable_writes` fixture -- this module never resolves into the operator's real
durable directory (except the one dedicated pytest-safety-probe test below, which
deliberately calls with no `path=` to prove the guard fires).
"""
import os
from pathlib import Path

import pytest

import match_handoff


def _full_auto_matched_entry(row_id="row-1", hs_object_id="3601", confirmed=None):
    entry = {
        "row_id": row_id,
        "row": {
            "row_id": row_id, "firstname": "John", "lastname": "Miller",
            "email": "john.miller@example.com", "phone": "+61 400 000 000",
        },
        "hs_object_id": hs_object_id,
    }
    if confirmed is not None:
        entry["confirmed"] = confirmed
    return entry


def test_handoff_path_resolves_into_the_shared_durable_directory(monkeypatch, tmp_path):
    import durable_paths
    monkeypatch.setattr(
        durable_paths, "resolve_state_path", lambda *a, **k: tmp_path / "x.json")
    path = match_handoff.handoff_path("r1")
    assert path.name == "match_handoff-r1.json"
    assert path.parent == tmp_path


def test_record_handoff_projects_to_three_keys_and_no_spreadsheet_value_on_disk(tmp_path):
    path = tmp_path / "match_handoff-r1.json"
    entries = [_full_auto_matched_entry(confirmed=True)]

    ok = match_handoff.record_handoff("r1", entries, path=path)

    assert ok
    raw = path.read_text(encoding="utf-8")
    assert "John" not in raw
    assert "Miller" not in raw
    assert "john.miller@example.com" not in raw
    assert "+61 400 000 000" not in raw

    loaded = match_handoff.load("r1", path=path)
    assert loaded == [{"row_id": "row-1", "hs_object_id": "3601", "confirmed": True}]


def test_confirmed_defaults_to_falsey_when_the_entry_carries_no_confirmed_key(tmp_path):
    """An email auto-match at step 2 carries no `confirmed` key at all -- only a
    step-3 operator decision adds one. The handoff must not invent a True."""
    path = tmp_path / "match_handoff-r2.json"
    entries = [_full_auto_matched_entry(row_id="row-1", hs_object_id="3601")]

    match_handoff.record_handoff("r2", entries, path=path)
    loaded = match_handoff.load("r2", path=path)

    assert loaded == [{"row_id": "row-1", "hs_object_id": "3601", "confirmed": False}]


def test_load_of_an_absent_file_returns_empty_list(tmp_path):
    path = tmp_path / "match_handoff-nope.json"
    assert match_handoff.load("nope", path=path) == []


def test_load_of_a_malformed_file_returns_empty_list(tmp_path):
    path = tmp_path / "match_handoff-broken.json"
    path.write_text("not json")
    assert match_handoff.load("broken", path=path) == []


def test_load_of_another_runs_file_returns_empty_list_never_a_partial(tmp_path):
    path = tmp_path / "match_handoff-shared.json"
    match_handoff.record_handoff("run-a", [_full_auto_matched_entry()], path=path)

    assert match_handoff.load("run-b", path=path) == []


def test_classify_read_reports_all_four_states(tmp_path):
    absent_path = tmp_path / "match_handoff-absent.json"
    assert match_handoff.classify_read("absent", path=absent_path) == match_handoff.ABSENT

    parseable_path = tmp_path / "match_handoff-parseable.json"
    match_handoff.record_handoff("parseable", [_full_auto_matched_entry()], path=parseable_path)
    assert match_handoff.classify_read("parseable", path=parseable_path) == match_handoff.PARSEABLE

    anomalous_path = tmp_path / "match_handoff-anomalous.json"
    anomalous_path.write_text("{not valid json")
    assert match_handoff.classify_read("anomalous", path=anomalous_path) == match_handoff.ANOMALOUS

    another_run_path = tmp_path / "match_handoff-shared2.json"
    match_handoff.record_handoff("run-x", [_full_auto_matched_entry()], path=another_run_path)
    assert match_handoff.classify_read("run-y", path=another_run_path) == match_handoff.ANOTHER_RUN


def test_classify_read_never_raises_on_anything():
    match_handoff.classify_read("whatever", path=Path("/nonexistent/dir/x.json"))


def test_record_handoff_called_twice_overwrites_rather_than_accumulates(tmp_path):
    path = tmp_path / "match_handoff-r3.json"
    match_handoff.record_handoff("r3", [_full_auto_matched_entry(row_id="row-1", hs_object_id="3601")], path=path)
    match_handoff.record_handoff("r3", [_full_auto_matched_entry(row_id="row-1", hs_object_id="3601")], path=path)

    loaded = match_handoff.load("r3", path=path)
    assert loaded == [{"row_id": "row-1", "hs_object_id": "3601", "confirmed": False}]


def test_a_second_shorter_call_replaces_a_declined_proposal_can_leave_the_handoff(tmp_path):
    path = tmp_path / "match_handoff-r4.json"
    match_handoff.record_handoff("r4", [
        _full_auto_matched_entry(row_id="row-1", hs_object_id="3601"),
        _full_auto_matched_entry(row_id="row-4", hs_object_id="3501", confirmed=True),
    ], path=path)
    match_handoff.record_handoff("r4", [
        _full_auto_matched_entry(row_id="row-1", hs_object_id="3601"),
    ], path=path)

    loaded = match_handoff.load("r4", path=path)
    assert loaded == [{"row_id": "row-1", "hs_object_id": "3601", "confirmed": False}]


def test_record_handoff_with_an_empty_list_writes_a_file_that_classifies_parseable(tmp_path):
    """An all-unmatched batch legitimately hands nothing onward -- a different fact
    from 'step 7 never ran' (Task 2's absent-handoff gap depends on this)."""
    path = tmp_path / "match_handoff-r5.json"

    ok = match_handoff.record_handoff("r5", [], path=path)

    assert ok
    assert path.exists()
    assert match_handoff.classify_read("r5", path=path) == match_handoff.PARSEABLE
    assert match_handoff.load("r5", path=path) == []


def test_a_grant_shaped_key_raises_and_writes_nothing(tmp_path):
    path = tmp_path / "match_handoff-r6.json"
    entries = [{"row_id": "row-1", "hs_object_id": "3601", "webhook_secret": "xxx"}]

    with pytest.raises(match_handoff.MatchHandoffError):
        match_handoff.record_handoff("r6", entries, path=path)

    assert not path.exists()


def test_a_grant_shaped_row_id_raises_and_writes_nothing(tmp_path):
    path = tmp_path / "match_handoff-r7.json"
    entries = [{"row_id": "op-grant-123", "hs_object_id": "3601"}]

    with pytest.raises(match_handoff.MatchHandoffError):
        match_handoff.record_handoff("r7", entries, path=path)

    assert not path.exists()


def test_a_grant_shaped_run_id_raises_and_writes_nothing(tmp_path):
    path = tmp_path / "match_handoff-grant.json"

    with pytest.raises(match_handoff.MatchHandoffError):
        match_handoff.record_handoff("op-grant-123", [_full_auto_matched_entry()], path=path)

    assert not path.exists()


def test_a_row_named_grant_persists_unchanged(tmp_path):
    """The guard scans NAMES only (keys), never string VALUES -- a person's first name
    being 'Grant' is not a forbidden name (mirrors match_state.py's own guard)."""
    path = tmp_path / "match_handoff-grant2.json"
    entries = [{
        "row_id": "row-1",
        "row": {"row_id": "row-1", "firstname": "Grant", "lastname": "Dewsbury"},
        "hs_object_id": "7101",
    }]

    match_handoff.record_handoff("grant2", entries, path=path)
    loaded = match_handoff.load("grant2", path=path)

    assert loaded == [{"row_id": "row-1", "hs_object_id": "7101", "confirmed": False}]


def test_refuses_a_real_durable_write_under_pytest_if_unpatched():
    """Defense in depth mirrored from written_records.py/remainder_queue.py: a test
    that forgets to pass path= must not decorate the operator's real durable
    directory."""
    import durable_paths

    ok = match_handoff.record_handoff(
        "pytest-safety-probe", [_full_auto_matched_entry()])

    assert ok is False
    assert not (durable_paths.durable_dir() / "match_handoff-pytest-safety-probe.json").exists()
