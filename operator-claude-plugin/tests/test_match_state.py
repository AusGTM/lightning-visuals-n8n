"""operator-claude-plugin/tests/test_match_state.py

Quick task 260911-ss4 (F1). Drives `match_state.py`'s save/load/classify_read round
trip on the RECORDED UAT batch-1 shape (`.planning/UAT-autonomous-batch-2026-09-09.md`)
-- never an invented one -- so the composition this file pins is exactly the sequence
`skills/enrich-before-ingest/SKILL.md` steps 2 and 3 now document: match once, persist,
apply the operator's step-3 decision, persist again.

Every test passes an explicit `path=tmp_path / "..."` per `conftest.py`'s autouse
`no_durable_writes` fixture -- this module never resolves into the operator's real
durable directory.
"""
from pathlib import Path

import pytest

import match_state
import preingest
import run_report


# =====================================================================================
# The recorded UAT batch-1 shape (a254d1eda71246a2a964922cdf5c2bd2, 2026-09-11):
# row-1 auto_matched by email (John Miller, hs_object_id 3601); row-4 proposed with one
# candidate (Craig Sheppard, hs_object_id 3501 -- the row the operator answered
# "4. approve" on); row-2/row-3 unmatched (Katie Poggioli, Jimmy Busteed -- the two
# rows execution 12372 actually enriched).
# =====================================================================================

def _recorded_batch_1_classification():
    return {
        "auto_matched": [
            {
                "row_id": "row-1",
                "row": {
                    "row_id": "row-1", "firstname": "John", "lastname": "Miller",
                    "email": "john.miller@example.com",
                },
                "hs_object_id": "3601",
            },
        ],
        "proposed": [
            {
                "row_id": "row-4",
                "row": {
                    "row_id": "row-4", "firstname": "Craig", "lastname": "Sheppard",
                    "company": "Acme Racing",
                },
                "candidates": [
                    {
                        "hs_object_id": "3501", "firstname": "Craig",
                        "lastname": "Sheppard", "email": "craig.sheppard@acme.example",
                        "jobtitle": "Ops Manager", "company": "Acme Racing",
                    },
                ],
                "ambiguous": False,
            },
        ],
        "unmatched": [
            {
                "row_id": "row-2",
                "row": {"row_id": "row-2", "firstname": "Katie", "lastname": "Poggioli"},
            },
            {
                "row_id": "row-3",
                "row": {"row_id": "row-3", "firstname": "Jimmy", "lastname": "Busteed"},
            },
        ],
        "unchecked": [],
        "unknown_response_row_ids": [],
    }


RUN_ID = "a254d1eda71246a2a964922cdf5c2bd2"


def test_the_recorded_batch_round_trips_through_save_load_apply_and_save_again(tmp_path):
    """Drives the exact sequence SKILL.md steps 2 and 3 now document:
    `match_state.save` -> `match_state.load` -> `preingest.apply_match_decisions` ->
    `match_state.save` -> `match_state.load` again -- with no in-memory reuse across the
    save/load boundary, so this proves the FILE round-trips, not just the object."""
    path = tmp_path / f"match_state-{RUN_ID}.json"
    classified = _recorded_batch_1_classification()

    match_state.save(RUN_ID, classified, path=path)
    loaded = match_state.load(RUN_ID, path=path)

    assert loaded == classified
    assert loaded is not classified

    resolved = {"row-4": "3501"}
    decided = preingest.apply_match_decisions(loaded, resolved)
    match_state.save(RUN_ID, decided, path=path)
    loaded_again = match_state.load(RUN_ID, path=path)

    assert [e["hs_object_id"] for e in loaded_again["auto_matched"]] == ["3601", "3501"]
    assert [e["row_id"] for e in loaded_again["unmatched"]] == ["row-2", "row-3"]
    assert loaded_again["proposed"] == []


def test_a_row_named_grant_persists_unchanged(tmp_path):
    """The load-bearing case: recorded UAT batch 2, row-1, Grant Dewsbury. A
    value-scanning guard (`held_queue._first_forbidden`'s own shape) would tokenise
    "Grant Dewsbury" and refuse the save -- this module's guard scans NAMES only, so a
    person named Grant persists and reads back unchanged."""
    path = tmp_path / "match_state-batch-2.json"
    classified = {
        "auto_matched": [], "proposed": [],
        "unmatched": [
            {
                "row_id": "row-1",
                "row": {"row_id": "row-1", "firstname": "Grant", "lastname": "Dewsbury"},
            },
        ],
        "unchecked": [], "unknown_response_row_ids": [],
    }

    match_state.save("batch-2", classified, path=path)
    loaded = match_state.load("batch-2", path=path)

    assert loaded == classified


def test_a_forbidden_shaped_row_key_is_refused_and_nothing_is_written(tmp_path):
    path = tmp_path / "match_state-run-x.json"
    classified = {
        "auto_matched": [], "proposed": [],
        "unmatched": [
            {"row_id": "row-9", "row": {"row_id": "row-9", "webhook_secret": "xxx"}},
        ],
        "unchecked": [], "unknown_response_row_ids": [],
    }

    with pytest.raises(match_state.MatchStateError):
        match_state.save("run-x", classified, path=path)

    assert not path.exists()


def test_a_forbidden_shaped_row_id_is_refused_and_nothing_is_written(tmp_path):
    path = tmp_path / "match_state-run-y.json"
    classified = {
        "auto_matched": [], "proposed": [],
        "unmatched": [
            {"row_id": "op-grant-123", "row": {"row_id": "op-grant-123", "firstname": "A"}},
        ],
        "unchecked": [], "unknown_response_row_ids": [],
    }

    with pytest.raises(match_state.MatchStateError):
        match_state.save("run-y", classified, path=path)

    assert not path.exists()


def test_load_on_an_absent_file_raises_naming_the_run(tmp_path):
    path = tmp_path / "match_state-nope.json"

    with pytest.raises(match_state.MatchStateError) as excinfo:
        match_state.load("nope", path=path)

    assert "nope" in str(excinfo.value)


def test_load_on_a_malformed_file_raises(tmp_path):
    path = tmp_path / "match_state-broken.json"
    path.write_text("not json")

    with pytest.raises(match_state.MatchStateError):
        match_state.load("broken", path=path)


def test_load_on_another_runs_file_raises_rather_than_handing_back_its_rows(tmp_path):
    path = tmp_path / "match_state-shared.json"
    match_state.save("run-a", _recorded_batch_1_classification(), path=path)

    with pytest.raises(match_state.MatchStateError):
        match_state.load("run-b", path=path)


def test_classify_read_reports_absent_parseable_and_anomalous(tmp_path):
    absent_path = tmp_path / "match_state-absent.json"
    assert match_state.classify_read("absent", path=absent_path) == match_state.ABSENT

    parseable_path = tmp_path / "match_state-parseable.json"
    match_state.save("parseable", _recorded_batch_1_classification(), path=parseable_path)
    assert match_state.classify_read("parseable", path=parseable_path) == match_state.PARSEABLE

    anomalous_path = tmp_path / "match_state-anomalous.json"
    anomalous_path.write_text("{not valid json")
    assert match_state.classify_read("anomalous", path=anomalous_path) == match_state.ANOMALOUS


def test_classify_read_never_raises_on_anything():
    """Belt-and-braces: classify_read is the non-raising probe by contract."""
    match_state.classify_read("whatever", path=Path("/nonexistent/dir/x.json"))


# =====================================================================================
# run_report.prune_durable_state: match_state-*.json joins the 7-day short-TTL family
# beside run_state-*.json.
# =====================================================================================

def _patch_durable_dir(monkeypatch, tmp_path):
    import durable_paths
    monkeypatch.setattr(durable_paths, "resolve_state_path", lambda *a, **k: tmp_path / "x.json")


def _age_file(path, days):
    import os
    from datetime import datetime, timedelta, timezone
    stamp = (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
    os.utime(path, (stamp, stamp))


def test_prune_durable_state_deletes_a_match_state_file_past_the_short_ttl(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    target = tmp_path / "match_state-abc.json"
    target.write_text("{}")
    _age_file(target, run_report.PRUNE_SHORT_TTL_DAYS + 1)

    deleted = run_report.prune_durable_state()

    assert deleted == ["match_state-abc.json"]
    assert not target.exists()


def test_prune_durable_state_keeps_a_fresh_match_state_file(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    target = tmp_path / "match_state-abc.json"
    target.write_text("{}")
    _age_file(target, run_report.PRUNE_SHORT_TTL_DAYS - 1)

    deleted = run_report.prune_durable_state()

    assert deleted == []
    assert target.exists()
