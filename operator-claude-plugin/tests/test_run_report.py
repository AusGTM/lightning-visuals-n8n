"""Tests for `run_report.py` (57-05 — AFTER-01, AFTER-03's operator-facing half, G-4's
disclosure half).

Task 1: the evidence layer — `record_audit`/`load_audit`/`classify_audit_read`, the
per-run ephemeral-observations record (GRANT-06/D-57-05: observations only, never a
grant), and `written_records.classify_read`/`run_manifest.classify_read` (covered in
their own test files).

Task 2 (added later in this same file): `build_run_report` — the join over five stores
plus the audit record.
"""
import json

import pytest

import durable_paths
import held_queue
import run_report
import written_records

# =====================================================================================
# Task 1 — record_audit / load_audit / classify_audit_read
# =====================================================================================


def test_record_audit_writes_and_load_audit_reads_it_back(tmp_path, monkeypatch):
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: tmp_path / f"run_audit-{run_id}.json")
    ok = run_report.record_audit("run-1", ceiling={"verdict": "ok"})
    assert ok
    assert run_report.load_audit("run-1") == {"ceiling": {"verdict": "ok"}}


def test_load_audit_on_an_absent_file_returns_an_empty_mapping_without_raising(tmp_path, monkeypatch):
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: tmp_path / f"run_audit-{run_id}.json")
    assert run_report.load_audit("nope") == {}


def test_record_audit_merges_rather_than_replaces_across_two_calls(tmp_path, monkeypatch):
    """THE MERGE TEST (REVIEW-57-M11) — the entire reason this record exists: the
    ceiling verdict is observed at grant time, the disarm result at the end of the run.
    A second call must not erase the first."""
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: tmp_path / f"run_audit-{run_id}.json")
    run_report.record_audit("run-1", ceiling={"verdict": "ok", "spent_sampled": 3})
    run_report.record_audit("run-1", disarm={"outcome": "disarmed"})

    facts = run_report.load_audit("run-1")
    assert facts["ceiling"] == {"verdict": "ok", "spent_sampled": 3}
    assert facts["disarm"] == {"outcome": "disarmed"}


def test_record_audit_second_call_can_update_a_key_the_first_call_also_set(tmp_path, monkeypatch):
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: tmp_path / f"run_audit-{run_id}.json")
    run_report.record_audit("run-1", balances={"lusha": "unknown"})
    run_report.record_audit("run-1", balances={"lusha": "ok"})
    assert run_report.load_audit("run-1")["balances"] == {"lusha": "ok"}


def test_record_audit_raises_on_a_grant_shaped_key_anywhere_in_its_arguments(tmp_path, monkeypatch):
    """THE AUTHORITY TEST, pinning GRANT-06/D-57-05."""
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: tmp_path / f"run_audit-{run_id}.json")
    with pytest.raises(run_report.RunReportError):
        run_report.record_audit("run-1", disarm={"grant": "nope"})


@pytest.mark.parametrize("marker", [
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
])
def test_record_audit_raises_on_every_forbidden_marker_as_a_nested_key(tmp_path, monkeypatch, marker):
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: tmp_path / f"run_audit-{run_id}.json")
    with pytest.raises(run_report.RunReportError):
        run_report.record_audit("run-1", balances={"outer": {marker: "x"}})


def test_record_audit_does_not_raise_on_the_disarm_word_disarmed(tmp_path, monkeypatch):
    """`disarm`/`disarmed` legitimately contain the substring "arm" — the scan must not
    refuse the module's own vocabulary."""
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: tmp_path / f"run_audit-{run_id}.json")
    assert run_report.record_audit("run-1", disarm={"outcome": "disarmed"})


def test_record_audit_does_not_raise_on_the_executions_basis_text(tmp_path, monkeypatch):
    """`EXECUTIONS_BASIS` legitimately contains "webhook" — a real, load-bearing
    observation, never grant-shaped authority."""
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: tmp_path / f"run_audit-{run_id}.json")
    basis = "1 webhook execution per chunk + 1 sub-execution per record"
    assert run_report.record_audit("run-1", ceiling={"basis": basis, "verdict": "ok"})


def test_record_audit_returns_falsey_never_raises_on_a_write_failure(tmp_path, monkeypatch):
    def _boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: tmp_path / f"run_audit-{run_id}.json")
    monkeypatch.setattr(durable_paths, "_atomic_write_0600", _boom)
    assert run_report.record_audit("run-1", ceiling={"verdict": "ok"}) is False


def test_the_forbidden_marker_tuple_is_a_fresh_object_not_a_borrowed_reference():
    assert run_report._FORBIDDEN_NAME_MARKERS is not written_records._FORBIDDEN_NAME_MARKERS
    assert run_report._FORBIDDEN_NAME_MARKERS is not held_queue._FORBIDDEN_NAME_MARKERS


def test_classify_audit_read_is_absent_for_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: tmp_path / f"run_audit-{run_id}.json")
    assert run_report.classify_audit_read("nope") == run_report.ABSENT


def test_classify_audit_read_is_parseable_for_a_good_record_including_an_empty_one(tmp_path, monkeypatch):
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: tmp_path / f"run_audit-{run_id}.json")
    run_report.record_audit("run-1")
    assert run_report.classify_audit_read("run-1") == run_report.PARSEABLE


def test_classify_audit_read_is_anomalous_for_unparseable_json(tmp_path, monkeypatch):
    target = tmp_path / "run_audit-bad.json"
    target.write_text("not json at all", encoding="utf-8")
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: target)
    assert run_report.classify_audit_read("bad") == run_report.ANOMALOUS


def test_classify_audit_read_is_anomalous_for_a_non_mapping_document(tmp_path, monkeypatch):
    target = tmp_path / "run_audit-list.json"
    target.write_text("[1, 2, 3]", encoding="utf-8")
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: target)
    assert run_report.classify_audit_read("list") == run_report.ANOMALOUS


def test_classify_audit_read_is_another_run_when_the_stored_run_id_differs(tmp_path, monkeypatch):
    target = tmp_path / "run_audit-real.json"
    target.write_text(json.dumps({
        "run_id": "the-other-run", "saved_at": "2026-01-01T00:00:00+00:00", "facts": {},
    }), encoding="utf-8")
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: target)
    assert run_report.classify_audit_read("this-run") == run_report.ANOTHER_RUN


def test_classify_audit_read_never_raises_on_any_input(tmp_path, monkeypatch):
    target = tmp_path / "not-even-a-real-directory" / "run_audit-x.json"
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: target)
    assert run_report.classify_audit_read("x") == run_report.ABSENT


def test_record_audit_refuses_a_real_durable_write_under_pytest_if_unpatched():
    """Defense in depth mirrored from `written_records.py`/`remainder_queue.py`: if a
    test forgets to patch `run_audit_path`, the write must not land in the operator's
    real durable directory."""
    assert run_report.record_audit("pytest-safety-probe", ceiling={"verdict": "ok"}) is False
    assert not (durable_paths.durable_dir() / "run_audit-pytest-safety-probe.json").exists()
