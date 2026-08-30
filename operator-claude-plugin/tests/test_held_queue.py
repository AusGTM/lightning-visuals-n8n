"""Tests for `held_queue.py` (Phase 61 Plan 04 Task 3, D-61-07 / REVIEW-06/HIGH-6).

Isolation mirrors `test_run_manifest.py`: most tests pass an explicit `path=`; the
location tests isolate via `CLAUDE_PLUGIN_DATA` instead.
"""
import json
import stat

import pytest

import confidence
import durable_paths
import held_queue
import preingest
import run_manifest


def _point_at_a_fake_durable_home(monkeypatch, tmp_path):
    fake_durable = tmp_path / "durable"
    fake_durable.mkdir()
    (fake_durable / "dashboard_artifact.json").write_text("{}")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(fake_durable))


def _outcome(tier="medium", candidate_count=1, **overrides):
    base = dict(parseable=True, match_tier=tier, candidate_count=candidate_count,
                provider_agreement=None, material_conflicts=None,
                judge_adjudicated_fields=None)
    base.update(overrides)
    return preingest.Outcome(**base)


# =====================================================================================
# queue_path()
# =====================================================================================


def test_queue_path_shares_a_parent_with_the_manifest_but_not_its_name(monkeypatch, tmp_path):
    _point_at_a_fake_durable_home(monkeypatch, tmp_path)
    assert held_queue.queue_path().parent == run_manifest.manifest_path().parent
    assert held_queue.queue_path() != run_manifest.manifest_path()


def test_queue_path_is_not_a_dotfile(monkeypatch, tmp_path):
    _point_at_a_fake_durable_home(monkeypatch, tmp_path)
    assert not held_queue.queue_path().name.startswith(".")


# =====================================================================================
# fingerprint() — the per-hold_code, observable-signal-only hash (REVIEW-C10/C12)
# =====================================================================================


def test_fingerprint_is_identical_across_a_changed_timestamp_run_id_and_credit_balance():
    """Volatile per-run fields never enter the hash — they are not even parameters."""
    outcome_a = _outcome(tier="medium", candidate_count=1)
    outcome_b = _outcome(tier="medium", candidate_count=1)
    assert held_queue.fingerprint(confidence.HOLD_NO_TABLE_ROW_MATCHED, outcome_a) == \
        held_queue.fingerprint(confidence.HOLD_NO_TABLE_ROW_MATCHED, outcome_b)


def test_fingerprint_is_identical_whether_enrichment_signals_are_present_absent_or_different():
    """The property that makes the whole invariant hold: the free match pass cannot
    observe provider_agreement/material_conflicts/judge_adjudicated_fields, so they
    must never affect the hash."""
    base = held_queue.fingerprint(
        confidence.HOLD_UNADJUDICATED_CONFLICT,
        _outcome(tier="high", candidate_count=0, provider_agreement=None,
                  material_conflicts=None, judge_adjudicated_fields=None),
    )
    with_signals = held_queue.fingerprint(
        confidence.HOLD_UNADJUDICATED_CONFLICT,
        _outcome(tier="high", candidate_count=0,
                  provider_agreement={"jobtitle": ["apollo"]},
                  material_conflicts=[{"group": "country", "fields": ["country"]}],
                  judge_adjudicated_fields={"country": 90}),
    )
    different_signals = held_queue.fingerprint(
        confidence.HOLD_UNADJUDICATED_CONFLICT,
        _outcome(tier="high", candidate_count=0,
                  provider_agreement={"jobtitle": []},
                  material_conflicts=[{"group": "org_type", "fields": ["lv_org_type"]}],
                  judge_adjudicated_fields=None),
    )
    assert base == with_signals == different_signals


def test_fingerprint_changes_when_the_hold_code_differs():
    outcome = _outcome(tier="unknown", candidate_count=0)
    assert held_queue.fingerprint(confidence.HOLD_UNKNOWN_TIER, outcome) != \
        held_queue.fingerprint(confidence.HOLD_NO_MATCH, outcome)


def test_fingerprint_changes_when_match_tier_differs():
    a = held_queue.fingerprint(confidence.HOLD_NO_MATCH, _outcome(tier="none", candidate_count=0))
    b = held_queue.fingerprint(confidence.HOLD_NO_MATCH, _outcome(tier="unknown", candidate_count=0))
    assert a != b


def test_fingerprint_changes_when_candidate_count_differs():
    a = held_queue.fingerprint(confidence.HOLD_AMBIGUOUS_CANDIDATES, _outcome(tier="medium", candidate_count=2))
    b = held_queue.fingerprint(confidence.HOLD_AMBIGUOUS_CANDIDATES, _outcome(tier="medium", candidate_count=3))
    assert a != b


def test_fingerprint_of_an_unparseable_outcome_stays_identical_across_calls():
    a = held_queue.fingerprint(confidence.HOLD_UNPARSEABLE, preingest.UNPARSEABLE_OUTCOME)
    b = held_queue.fingerprint(confidence.HOLD_UNPARSEABLE, preingest.UNPARSEABLE_OUTCOME)
    assert a == b


# =====================================================================================
# build_entry() / save() / load() — the schema, the allowlist, the refusal
# =====================================================================================


def test_build_entry_carries_observed_signals_and_fingerprint_as_separate_fields():
    row = {"row_id": "row-1", "email": "a@example.com", "phone": "0400000000"}
    outcome = _outcome(tier="none", candidate_count=0)
    entry = held_queue.build_entry(
        row, confidence.HOLD_NO_MATCH, "no match found", outcome,
        observed_signals={"note": "checked email and linkedin"},
    )
    assert entry["hold_code"] == confidence.HOLD_NO_MATCH
    assert entry["observed_signals"] == {"note": "checked email and linkedin"}
    assert entry["resume_fingerprint"] == held_queue.fingerprint(confidence.HOLD_NO_MATCH, outcome)


def test_build_entry_only_persists_allowlisted_row_fields():
    row = {"row_id": "row-1", "email": "a@example.com", "phone": "0400000000",
           "some_random_spreadsheet_column": "should not be persisted"}
    entry = held_queue.build_entry(row, confidence.HOLD_NO_MATCH, "no match", _outcome())
    assert entry["row"] == {"row_id": "row-1", "email": "a@example.com"}
    assert "phone" not in entry["row"]
    assert "some_random_spreadsheet_column" not in entry["row"]


def test_save_then_load_round_trips_entries(tmp_path):
    target = tmp_path / "held_queue.json"
    entry = held_queue.build_entry(
        {"row_id": "row-1", "email": "a@example.com"},
        confidence.HOLD_NO_MATCH, "no match found", _outcome())
    held_queue.save("run-1", {"row-1": entry}, path=target)

    assert held_queue.load(path=target) == {"row-1": entry}


def test_save_writes_at_mode_0600(tmp_path):
    target = tmp_path / "held_queue.json"
    entry = held_queue.build_entry(
        {"row_id": "row-1", "email": "a@example.com"},
        confidence.HOLD_NO_MATCH, "no match", _outcome())
    held_queue.save("run-1", {"row-1": entry}, path=target)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_save_refuses_a_hold_code_outside_the_closed_set(tmp_path):
    target = tmp_path / "held_queue.json"
    bad_entry = {"hold_code": "definitely_not_a_real_code", "reason": "x",
                 "observed_signals": {}, "resume_fingerprint": "abc", "row": {}}
    with pytest.raises(held_queue.HeldQueueError):
        held_queue.save("run-1", {"row-1": bad_entry}, path=target)
    assert not target.exists()


def test_save_refuses_an_arming_shaped_key(tmp_path):
    target = tmp_path / "held_queue.json"
    entry = held_queue.build_entry({"row_id": "row-1"}, confidence.HOLD_NO_MATCH, "x", _outcome())
    with pytest.raises(held_queue.HeldQueueError):
        held_queue.save("run-1", {"armed_row": entry}, path=target)
    assert not target.exists()


def test_save_refuses_an_arming_shaped_value_inside_observed_signals(tmp_path):
    target = tmp_path / "held_queue.json"
    entry = held_queue.build_entry(
        {"row_id": "row-1"}, confidence.HOLD_NO_MATCH, "x", _outcome(),
        observed_signals={"leaked": "n8n_api_key=super-secret"},
    )
    with pytest.raises(held_queue.HeldQueueError):
        held_queue.save("run-1", {"row-1": entry}, path=target)
    assert not target.exists()


def test_a_rejected_save_leaves_a_previously_saved_queue_untouched(tmp_path):
    target = tmp_path / "held_queue.json"
    good = held_queue.build_entry({"row_id": "row-1"}, confidence.HOLD_NO_MATCH, "x", _outcome())
    held_queue.save("run-1", {"row-1": good}, path=target)
    before = target.read_text()

    bad = {"hold_code": "nope", "reason": "x", "observed_signals": {},
           "resume_fingerprint": "abc", "row": {}}
    with pytest.raises(held_queue.HeldQueueError):
        held_queue.save("run-2", {"row-2": bad}, path=target)

    assert target.read_text() == before


# =====================================================================================
# load() degrades whole on any anomaly
# =====================================================================================


def test_load_on_a_missing_file_returns_empty(tmp_path):
    assert held_queue.load(path=tmp_path / "held_queue.json") == {}


def test_load_on_malformed_json_returns_empty(tmp_path):
    target = tmp_path / "held_queue.json"
    target.write_text("not json", encoding="utf-8")
    assert held_queue.load(path=target) == {}


def test_load_on_a_truncated_queue_returns_empty(tmp_path):
    target = tmp_path / "held_queue.json"
    entry = held_queue.build_entry({"row_id": "row-1"}, confidence.HOLD_NO_MATCH, "x", _outcome())
    held_queue.save("run-1", {"row-1": entry}, path=target)
    full_text = target.read_text()
    target.write_text(full_text[: len(full_text) // 2], encoding="utf-8")
    assert held_queue.load(path=target) == {}


def test_load_on_an_entry_with_an_invalid_hold_code_degrades_the_whole_queue(tmp_path):
    target = tmp_path / "held_queue.json"
    target.write_text(json.dumps({
        "run_id": "run-1", "saved_at": "2026-08-30T00:00:00Z",
        "entries": {
            "row-1": {"hold_code": confidence.HOLD_NO_MATCH, "reason": "x",
                       "observed_signals": {}, "resume_fingerprint": "abc", "row": {}},
            "row-2": {"hold_code": "not_a_real_code", "reason": "x",
                       "observed_signals": {}, "resume_fingerprint": "def", "row": {}},
        },
    }), encoding="utf-8")
    assert held_queue.load(path=target) == {}


# =====================================================================================
# classify_read() — the four-way review-pass classification (REVIEW-C11)
# =====================================================================================


def test_classify_read_on_a_missing_file_is_absent(tmp_path):
    assert held_queue.classify_read(path=tmp_path / "held_queue.json") == held_queue.ABSENT


def test_classify_read_on_a_good_file_is_parseable(tmp_path):
    target = tmp_path / "held_queue.json"
    entry = held_queue.build_entry({"row_id": "row-1"}, confidence.HOLD_NO_MATCH, "x", _outcome())
    held_queue.save("run-1", {"row-1": entry}, path=target)
    assert held_queue.classify_read(path=target) == held_queue.PARSEABLE


def test_classify_read_on_malformed_json_is_anomalous(tmp_path):
    target = tmp_path / "held_queue.json"
    target.write_text("not json", encoding="utf-8")
    assert held_queue.classify_read(path=target) == held_queue.ANOMALOUS


def test_classify_read_never_reports_a_row_count_for_an_anomalous_file(tmp_path):
    """An unreadable file cannot tell you how many rows it held — the classification
    is a bare word, never a number invented from a file nobody could parse."""
    target = tmp_path / "held_queue.json"
    target.write_text("not json", encoding="utf-8")
    result = held_queue.classify_read(path=target)
    assert isinstance(result, str)
    assert result == held_queue.ANOMALOUS


def test_classify_read_on_a_different_runs_file_is_another_run(tmp_path):
    target = tmp_path / "held_queue.json"
    entry = held_queue.build_entry({"row_id": "row-1"}, confidence.HOLD_NO_MATCH, "x", _outcome())
    held_queue.save("run-1", {"row-1": entry}, path=target)
    assert held_queue.classify_read(path=target, expected_run_id="run-2") == held_queue.ANOTHER_RUN
    assert held_queue.classify_read(path=target, expected_run_id="run-1") == held_queue.PARSEABLE


def test_load_still_degrades_whole_regardless_of_classify_reads_answer(tmp_path):
    """The loader's own contract is unchanged by adding classify_read() — it still
    degrades to empty on an anomaly rather than raising or partially trusting."""
    target = tmp_path / "held_queue.json"
    target.write_text("not json", encoding="utf-8")
    assert held_queue.classify_read(path=target) == held_queue.ANOMALOUS
    assert held_queue.load(path=target) == {}


# =====================================================================================
# Write order relative to run_manifest.py (REVIEW-07's other half)
# =====================================================================================


def test_a_failed_manifest_write_after_a_successful_queue_write_leaves_the_row_unresumed_not_lost(
        tmp_path, monkeypatch):
    """queue-then-manifest: a crash between the two writes leaves a queue entry for a
    row the manifest does not mention. That row is simply re-run on the next resume
    (rows_to_resume treats an absent verdict as "include") — the safe direction, never
    a silent drop."""
    queue_target = tmp_path / "held_queue.json"
    manifest_target = tmp_path / "run_manifest.json"

    entry = held_queue.build_entry(
        {"row_id": "row-1", "email": "a@example.com"},
        confidence.HOLD_NO_MATCH, "no match found", _outcome(tier="none", candidate_count=0))
    held_queue.save("run-1", {"row-1": entry}, path=queue_target)

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(durable_paths.os, "replace", _boom)
    with pytest.raises(OSError):
        run_manifest.save("run-1", {"row-1": run_manifest.CONFIDENCE_HELD}, path=manifest_target)

    # The queue entry survived; the manifest never recorded the verdict.
    assert held_queue.load(path=queue_target) == {"row-1": entry}
    assert run_manifest.load(path=manifest_target) == {}

    # And a resume treats the row as needing work again — re-run, not stranded.
    result = run_manifest.rows_to_resume(
        [{"row_id": "row-1", "email": "a@example.com"}],
        run_manifest.load(path=manifest_target),
    )
    assert result.rows == ({"row_id": "row-1", "email": "a@example.com"},)
