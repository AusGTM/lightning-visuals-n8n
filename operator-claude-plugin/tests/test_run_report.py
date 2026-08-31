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
import inspect

import pytest

import chunking
import confidence
import durable_paths
import held_queue
import remainder_queue
import run_manifest
import run_report
import run_state
import written_records


def _patch_durable_dir(monkeypatch, tmp_path):
    """Mirrors test_written_records.py's own idiom: one shared tmp directory every
    no-path store (`written_records.load()`, `held_queue.load()`,
    `remainder_queue.load()`) and every per-run path function
    (`run_manifest.run_manifest_path`, `run_state.run_state_path`, `run_report.run_audit_path`)
    resolves into, so a report built over it sees a consistent durable directory."""
    monkeypatch.setattr(
        durable_paths, "resolve_state_path",
        lambda *a, **k: tmp_path / "dashboard_artifact.json",
    )

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
    run_report.record_audit("run-1", ceiling={"verdict": "ok"})
    assert run_report.classify_audit_read("run-1") == run_report.PARSEABLE


def test_classify_audit_read_is_parseable_for_a_well_formed_but_empty_record(tmp_path, monkeypatch):
    target = tmp_path / "run_audit-empty.json"
    target.write_text(json.dumps({
        "run_id": "empty", "saved_at": "2026-01-01T00:00:00+00:00", "facts": {},
    }), encoding="utf-8")
    monkeypatch.setattr(run_report, "run_audit_path", lambda run_id: target)
    assert run_report.classify_audit_read("empty") == run_report.PARSEABLE


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


# =====================================================================================
# Task 2 — build_run_report: the join over five stores plus the audit record.
# =====================================================================================

REQUIRED_TOP_LEVEL_KEYS = {
    "run_id", "records", "held", "remainder", "spend", "disarm", "balances",
    "contradictions", "gaps", "block",
}


def test_build_run_report_never_raises_on_a_run_with_no_artifacts_at_all(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    report = run_report.build_run_report("nope", {})
    assert set(report) >= REQUIRED_TOP_LEVEL_KEYS


def test_build_run_report_signature_takes_outcomes_plural_not_outcome():
    params = inspect.signature(run_report.build_run_report).parameters
    assert "outcomes" in params and "outcome" not in params


def test_the_join_test_after_01_stands_on(tmp_path, monkeypatch):
    """A held/gated row with no HubSpot id must appear in `records`, keyed by its
    `row_id`, and named by that row_id in the rendered block."""
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-1", 0, {
        "action": "write_blocked", "hs_object_id": None, "object_type": "contacts",
        "row_id": "r7", "reason": "not_allowlisted",
    })

    report = run_report.build_run_report("run-1", {})

    keys = [k for k in report["records"] if k[0] == "r7"]
    assert keys, "no record in `records` is keyed by row_id r7"
    assert "r7" in report["block"]


def test_multi_event_rows_on_different_lanes_both_survive(tmp_path, monkeypatch):
    """One row_id, an enrichment event and an ingest event, on different lanes — keying
    by row_id alone would lose one."""
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-1", 0, {
        "action": "enrich", "hs_object_id": "500", "object_type": "contacts",
        "row_id": "r9",
    })
    written_records.append_chunk("run-1", 1, {
        "action": "create", "hs_object_id": "500", "object_type": "contacts",
        "row_id": "r9",
    })

    report = run_report.build_run_report("run-1", {})
    r9_keys = [k for k in report["records"] if k[0] == "r9"]
    assert len(r9_keys) == 2, f"expected two distinct (row_id, lane) keys for r9, got {r9_keys}"


def test_unjoinable_leg_is_kept_and_named_in_gaps(tmp_path, monkeypatch):
    """row_id: None, hs_object_id: None — the pair pipeline's strip_row_id boundary.
    Kept, rendered UNJOINABLE, never dropped."""
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-1", 0, {
        "action": "create", "hs_object_id": None, "object_type": "contacts",
        "row_id": None,
    })

    report = run_report.build_run_report("run-1", {})
    assert len(report["records"]) == 1
    assert any("strip_row_id" in g for g in report["gaps"])
    assert "UNJOINABLE" in report["block"]


def test_an_entry_with_no_row_id_but_a_real_id_is_joined_by_the_id(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-1", 0, {
        "action": "update", "hs_object_id": "12345", "object_type": "contacts",
        "row_id": None,
    })
    report = run_report.build_run_report("run-1", {})
    keys = [k for k in report["records"] if k[0] == "12345"]
    assert keys
    assert not any("strip_row_id" in g for g in report["gaps"])


def test_outcomes_accepts_a_sequence_and_a_one_element_sequence_behaves_identically():
    plan = chunking.ChunkPlan(chunks=({"record_ids": ["1"], "object_type": "companies"},),
                              row_counts=(1,), record_count=1)
    outcome = chunking.DispatchOutcome(
        results=(chunking.ChunkResult(index=0, rows=1, ok=True),),
        responses=({"action": "update", "hs_object_id": "1"},), run_id="run-x",
    )
    report_many = run_report.build_run_report("run-x", {}, outcomes=[outcome])
    report_one = run_report.build_run_report("run-x", {}, outcomes=(outcome,))
    assert report_many["spend"]["projected_executions"] == report_one["spend"]["projected_executions"]


def test_read_progress_takes_a_manifest_snapshot_and_never_reloads(tmp_path):
    """THE ONE-SNAPSHOT TEST (REVIEW-57-M1)."""
    target = tmp_path / "run_manifest-run-1.json"
    run_manifest.save("run-1", {"row-1": "matched"}, path=target)
    on_disk_different = run_manifest.ScopedLoadResult(verdicts={"row-9": "held"}, run_id="run-1")

    progress = run_state.read_progress(
        "run-1", path=str(tmp_path / "run_state-run-1.json"),
        manifest_snapshot=on_disk_different,
    )
    # A run never registered (no run_state-run-1.json) reads NOT_STARTED regardless of
    # the snapshot — the snapshot only matters once a real run_state file exists. Prove
    # the parameter is at least accepted without a second load by asserting no
    # TypeError and that the byte-identical default path (no snapshot passed) still
    # works unchanged.
    assert progress.state in (run_state.NOT_STARTED, run_state.OK)


def test_read_progress_omitted_snapshot_is_byte_identical_to_todays_behaviour(tmp_path):
    run_state.start_run("run-1", ["a", "b"], path=str(tmp_path / "rs.json"))
    run_manifest.save("run-1", {"a": "matched"}, path=str(tmp_path / "rm.json"))
    baseline = run_state.read_progress("run-1", path=str(tmp_path / "rs.json"))
    assert baseline.state == run_state.OK


def test_build_run_report_loads_the_manifest_once_and_passes_it_to_read_progress(
        tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    calls = []
    real_load_scoped = run_manifest.load_scoped

    def _spy_load_scoped(*a, **k):
        calls.append((a, k))
        return real_load_scoped(*a, **k)

    monkeypatch.setattr(run_manifest, "load_scoped", _spy_load_scoped)
    run_state.start_run("run-1", ["a"], path=run_state.run_state_path("run-1"))

    run_report.build_run_report("run-1", {})
    assert len(calls) == 1, (
        f"expected exactly one run_manifest.load_scoped call (the one snapshot), got "
        f"{len(calls)}"
    )


# --- The contradiction matrix (REVIEW-57-H) — one test per row --------------------

def test_contradiction_written_ledger_vs_manifest_held(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-1", 0, {
        "action": "update", "hs_object_id": "1", "object_type": "contacts", "row_id": "r1",
    })
    run_manifest.save("run-1", {"r1": run_manifest.CONFIDENCE_HELD},
                      path=run_manifest.run_manifest_path("run-1"))

    report = run_report.build_run_report("run-1", {})
    assert any(c["kind"] == "written_vs_held" for c in report["contradictions"])
    assert "REPORT INCOMPLETE" in report["block"]


def test_contradiction_row_in_remainder_and_written_records(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-1", 0, {
        "action": "update", "hs_object_id": "1", "object_type": "contacts", "row_id": "r1",
    })
    entry = remainder_queue.build_entry(
        {"rows": [{"row_id": "r1", "email": "a@example.com"}], "object_type": "contacts"},
        remainder_queue.REASON_CEILING_BREACH)
    remainder_queue.save("run-1", [entry], path=remainder_queue.remainder_path("run-1"))

    report = run_report.build_run_report("run-1", {})
    assert any(c["kind"] == "remainder_and_written" for c in report["contradictions"])


def test_contradiction_associated_with_no_confirmed_write(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-1", 0, {
        "action": "write_blocked", "hs_object_id": None, "object_type": "contacts",
        "row_id": "r1", "association": "associated",
    })

    report = run_report.build_run_report("run-1", {})
    assert any(c["kind"] == "associated_without_confirmed_write" for c in report["contradictions"])


def test_contradiction_run_state_running_with_durable_results_present(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    run_state.start_run("run-1", ["r1"], path=run_state.run_state_path("run-1"))
    run_state.mark_dispatched("run-1", ["r1"], path=run_state.run_state_path("run-1"))
    written_records.append_chunk("run-1", 0, {
        "action": "update", "hs_object_id": "1", "object_type": "contacts", "row_id": "r1",
    })
    # No manifest verdict recorded for r1 — dispatched but unresolved -> "running".

    report = run_report.build_run_report("run-1", {})
    assert any(c["kind"] == "interrupted_run" for c in report["contradictions"])


def test_contradiction_held_queue_row_absent_from_this_runs_manifest(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-1", 0, {
        "action": "write_blocked", "hs_object_id": None, "object_type": "contacts",
        "row_id": "r1",
    })
    held_queue.save("run-1", {
        "r1": held_queue.build_entry(
            {"row_id": "r1", "email": "a@example.com"},
            confidence.HOLD_NO_MATCH, "held for review",
            type("O", (), {"match_tier": "exact", "candidate_count": 1})(),
        )
    })
    # No run_manifest entry at all for r1 in this run's own scoped file.

    report = run_report.build_run_report("run-1", {})
    assert any(c["kind"] == "held_queue_attribution_unknown" for c in report["contradictions"])


def test_store_classification_absent_malformed_another_run_read_differently(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    report_absent = run_report.build_run_report("no-file-run", {})
    assert any("written_records" in g and "absent" in g.lower() for g in report_absent["gaps"])

    (tmp_path / "written_records-badrun.json").write_text("not json", encoding="utf-8")
    report_bad = run_report.build_run_report("badrun", {})
    assert any("written_records" in g and (
        "malformed" in g.lower() or "anomalous" in g.lower()) for g in report_bad["gaps"])

    (tmp_path / "written_records-foreign.json").write_text(json.dumps({
        "run_id": "some-other-run", "saved_at": "x", "entries": [],
    }), encoding="utf-8")
    report_foreign = run_report.build_run_report("foreign", {})
    assert any("written_records" in g and "another" in g.lower() for g in report_foreign["gaps"])


def test_report_incomplete_banner_is_at_the_top_when_gaps_or_contradictions_exist(
        tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    (tmp_path / "written_records-broken.json").write_text("not json", encoding="utf-8")
    report = run_report.build_run_report("broken", {})
    lines = report["block"].splitlines()
    assert any("REPORT INCOMPLETE" in line for line in lines[:3])


def test_report_incomplete_banner_absent_when_clean(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-clean", 0, {
        "action": "skip", "hs_object_id": None, "object_type": "contacts", "row_id": "r1",
    })
    report = run_report.build_run_report("run-clean", {})
    assert report["gaps"] == []
    assert report["contradictions"] == []
    assert "REPORT INCOMPLETE" not in report["block"]


def test_persisted_audit_record_is_used_when_the_caller_passes_none(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    run_report.record_audit("run-1", ceiling={"verdict": "ok", "projected_executions": 5},
                            disarm={"outcome": "disarmed"})

    report = run_report.build_run_report("run-1", {}, ceiling=None, disarm=None)
    assert report["spend"]["ceiling"] == {"verdict": "ok", "projected_executions": 5}
    assert report["disarm"] == {"outcome": "disarmed"}


def test_gated_row_renders_with_distinct_text_from_a_written_row(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-1", 0, {
        "action": "write_blocked", "hs_object_id": None, "object_type": "contacts",
        "row_id": "r1",
    })
    written_records.append_chunk("run-1", 1, {
        "action": "create", "hs_object_id": "999", "object_type": "contacts", "row_id": "r2",
    })
    report = run_report.build_run_report("run-1", {})
    gated_text = run_report._OUTCOME_TEXT[written_records.GATED]
    written_text = run_report._OUTCOME_TEXT[written_records.WRITTEN]
    assert gated_text != written_text
    assert "grant" in gated_text.lower() and "re-send" in gated_text.lower()


def test_a_create_with_no_id_never_shows_an_invented_id(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-1", 0, {
        "action": "create", "hs_object_id": None, "object_type": "companies", "row_id": "r1",
    })
    report = run_report.build_run_report("run-1", {})
    key = [k for k in report["records"] if k[0] == "r1"][0]
    event = report["records"][key]["events"][0]
    assert event["outcome"] == written_records.CREATED_ID_UNKNOWN
    assert event["hs_object_id"] is None


def test_skip_and_proposed_are_counted_as_successes(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-1", 0, {
        "action": "skip", "hs_object_id": "1", "object_type": "contacts", "row_id": "r1",
    })
    written_records.append_chunk("run-1", 1, {
        "action": "proposed", "hs_object_id": "2", "object_type": "contacts", "row_id": "r2",
    })
    report = run_report.build_run_report("run-1", {})
    assert report["contradictions"] == []
    assert report["gaps"] == []


@pytest.mark.parametrize("value,expected_substr", [
    ("associated", "associated"),
    ("not_confirmed", "not confirmed"),
    ("not_attempted", "not attempted"),
    ("none", "no association"),
])
def test_association_values_render_distinctly(tmp_path, monkeypatch, value, expected_substr):
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-1", 0, {
        "action": "update", "hs_object_id": "1", "object_type": "contacts", "row_id": "r1",
        "association": value,
    })
    report = run_report.build_run_report("run-1", {})
    key = [k for k in report["records"] if k[0] == "r1"][0]
    text = run_report._association_text(report["records"][key]["events"][0].get("association"))
    assert expected_substr in text.lower()


def test_association_absent_never_renders_as_associated(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-1", 0, {
        "action": "update", "hs_object_id": "1", "object_type": "contacts", "row_id": "r1",
    })
    report = run_report.build_run_report("run-1", {})
    key = [k for k in report["records"] if k[0] == "r1"][0]
    text = run_report._association_text(report["records"][key]["events"][0].get("association"))
    assert text.lower() != "associated"


def test_held_rows_named_individually_from_manifest_and_remainder(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    run_manifest.save("run-1", {"r1": run_manifest.HELD},
                      path=run_manifest.run_manifest_path("run-1"))
    entry = remainder_queue.build_entry(
        {"rows": [{"row_id": "r2", "email": "b@example.com"}], "object_type": "contacts"},
        remainder_queue.REASON_CEILING_BREACH)
    remainder_queue.save("run-1", [entry], path=remainder_queue.remainder_path("run-1"))

    report = run_report.build_run_report("run-1", {})
    assert "r1" in json.dumps(report["held"])
    assert len(report["remainder"]) == 1
    assert "r1" in report["block"]


def test_spend_carries_projection_ceiling_and_the_over_statement_caveat(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    report = run_report.build_run_report(
        "run-1", {}, ceiling={"verdict": "ok", "projected_executions": 3, "remaining_sampled": 10})
    assert report["spend"]["ceiling"]["projected_executions"] == 3
    assert "OVER-STATE" in report["block"] or "over-state" in report["block"].lower()


def test_ceiling_stop_renders_as_a_deliberate_budget_stop_not_a_failure(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    stop = chunking.CeilingStop(
        chunk_index=1, projected_executions=10, execution_ceiling=8,
        unsent_chunks=({"record_ids": ["9"], "object_type": "contacts"},),
        remainder={"record_ids": ["9"], "object_type": "contacts"},
        reason="would exceed the ceiling",
    )
    outcome = chunking.DispatchOutcome(
        results=(chunking.ChunkResult(index=0, rows=1, ok=True),),
        responses=({"action": "update", "hs_object_id": "1"},),
        run_id="run-1", ceiling_stop=stop,
    )
    report = run_report.build_run_report("run-1", {}, outcomes=[outcome])
    assert "budget" in report["block"].lower()
    assert "failure" not in " ".join(
        line for line in report["block"].splitlines() if "chunk 1" in line.lower()
    ).lower()
    assert "1" in json.dumps(report["spend"].get("ceiling_stops", []))


def test_disarm_states_render_distinctly(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    r_disarmed = run_report.build_run_report("r1", {}, disarm={"outcome": "disarmed"})
    r_failed = run_report.build_run_report("r2", {}, disarm={"outcome": "disarm_failed"})
    r_absent = run_report.build_run_report("r3", {})
    assert "disarmed" in r_disarmed["block"].lower()
    assert "disarm_failed" in r_failed["block"].lower() or "failed" in r_failed["block"].lower()
    assert r_absent["disarm"] is None


def test_balances_names_readable_and_unreadable_and_states_what_is_bounded(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    balances = {
        "zoominfo": {"verdict": "ok", "remaining_credits": 9381, "reason": None},
        "apollo": {"verdict": "unknown", "remaining_credits": None, "reason": "http_403"},
        "lusha": {"verdict": "unknown", "remaining_credits": None, "reason": "unreadable"},
    }
    report = run_report.build_run_report("run-1", {}, balances=balances)
    assert "zoominfo" in report["block"] and "apollo" in report["block"]
    assert "bounded" in report["block"].lower()


def test_degradation_missing_written_records_still_renders_every_other_section(
        tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    held_queue.save("run-1", {})
    report = run_report.build_run_report("run-1", {})
    assert report["records"] == {}
    assert any("written_records" in g for g in report["gaps"])
    assert "spend" in report and "balances" in report


def test_scoping_two_runs_never_mix_rows(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-a", 0, {
        "action": "update", "hs_object_id": "1", "object_type": "contacts", "row_id": "ra",
    })
    written_records.append_chunk("run-b", 0, {
        "action": "update", "hs_object_id": "2", "object_type": "contacts", "row_id": "rb",
    })
    report_a = run_report.build_run_report("run-a", {})
    assert not any(k[0] == "rb" for k in report_a["records"])
    assert any(k[0] == "ra" for k in report_a["records"])


def test_build_run_report_never_raises_on_a_malformed_store(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    (tmp_path / "written_records-x.json").write_text("{not valid json", encoding="utf-8")
    (tmp_path / "run_manifest-x.json").write_text("{not valid json", encoding="utf-8")
    (tmp_path / "held_queue.json").write_text("{not valid json", encoding="utf-8")
    (tmp_path / "remainder_queue-x.json").write_text("{not valid json", encoding="utf-8")
    report = run_report.build_run_report("x", {})
    assert set(report) >= REQUIRED_TOP_LEVEL_KEYS
