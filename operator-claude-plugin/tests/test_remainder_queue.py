"""Tests for `remainder_queue.py` (57-03 Task 2, D-57-01/D-57-04/D-57-05).

Isolation mirrors `test_written_records.py`'s `_patch_durable_dir` idiom: patching
`durable_paths.resolve_state_path` directly, so both `save()`'s write and `load()`'s
no-argument glob resolve into the same `tmp_path` directory a real durable home would
give them. Every test that would otherwise hit the module's own
`_refuses_real_durable_write_under_pytest` guard patches `resolve_state_path` first.
"""
import json
import stat

import pytest

import durable_paths
import remainder_queue as rq


def _patch_durable_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(
        durable_paths, "resolve_state_path",
        lambda *a, **k: tmp_path / "dashboard_artifact.json",
    )


# =====================================================================================
# remainder_path()
# =====================================================================================

def test_remainder_path_is_named_and_shares_the_durable_dir(monkeypatch, tmp_path):
    _patch_durable_dir(monkeypatch, tmp_path)
    path = rq.remainder_path("abc")
    assert path.name == "remainder_queue-abc.json"
    assert path.parent == tmp_path


def test_two_different_run_ids_never_share_a_path(monkeypatch, tmp_path):
    _patch_durable_dir(monkeypatch, tmp_path)
    assert rq.remainder_path("run-a") != rq.remainder_path("run-b")


# =====================================================================================
# build_entry() — shape and reason
# =====================================================================================

def test_build_entry_carries_the_spec_verbatim_and_the_record_count():
    entry = rq.build_entry(
        {"record_ids": ["1", "2"], "object_type": "companies"},
        rq.REASON_CEILING_BREACH,
    )
    assert entry["spec"] == {"record_ids": ["1", "2"], "object_type": "companies"}
    assert entry["reason"] == rq.REASON_CEILING_BREACH
    assert entry["record_count"] == 2
    assert entry["note"] is None


def test_build_entry_schema_is_exactly_four_keys():
    entry = rq.build_entry({"record_ids": ["1"]}, rq.REASON_CEILING_BREACH)
    assert set(entry) == {"spec", "reason", "record_count", "note"}


def test_build_entry_rejects_an_unrecognised_reason():
    with pytest.raises(rq.RemainderQueueError):
        rq.build_entry({"record_ids": ["1"]}, "not_a_real_reason")


def test_build_entry_rejects_a_non_dict_spec():
    with pytest.raises(rq.RemainderQueueError):
        rq.build_entry(["1", "2"], rq.REASON_CEILING_BREACH)


def test_build_entry_carries_a_note():
    entry = rq.build_entry(
        {"record_ids": ["1"]}, rq.REASON_CEILING_BREACH, note="stopped before chunk 2"
    )
    assert entry["note"] == "stopped before chunk 2"


def test_record_count_is_none_for_a_list_spec_the_backend_resolves():
    entry = rq.build_entry({"list": "my-list"}, rq.REASON_CEILING_BREACH)
    assert entry["record_count"] is None


# =====================================================================================
# build_entry() — the forbidden-marker refusal, one test per marker (REVIEW-57-L4: TEN)
# =====================================================================================

@pytest.mark.parametrize("marker", [
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
])
def test_build_entry_refuses_a_top_level_key_matching_any_forbidden_marker(marker):
    with pytest.raises(rq.RemainderQueueError):
        rq.build_entry({marker: "x", "record_ids": ["1"]}, rq.REASON_CEILING_BREACH)


def test_ten_forbidden_markers_not_nine():
    assert len(rq._FORBIDDEN_NAME_MARKERS) == 10
    assert "arm" in rq._FORBIDDEN_NAME_MARKERS


# =====================================================================================
# build_entry() — recursion across every container shape (REVIEW-57-M2)
# =====================================================================================

def test_forbidden_key_nested_inside_a_dict_value_raises():
    with pytest.raises(rq.RemainderQueueError):
        rq.build_entry({"meta": {"token": "x"}}, rq.REASON_CEILING_BREACH)


def test_forbidden_key_inside_a_list_member_raises():
    with pytest.raises(rq.RemainderQueueError):
        rq.build_entry({"people": [{"grant": "x"}]}, rq.REASON_CEILING_BREACH)


def test_forbidden_key_inside_a_dict_inside_a_list_raises():
    # The exact shape a `people`/`companies`/`rows` spec has.
    with pytest.raises(rq.RemainderQueueError):
        rq.build_entry(
            {"rows": [{"auth": {"token": "x"}}], "object_type": "contacts"},
            rq.REASON_CEILING_BREACH,
        )


def test_forbidden_key_inside_a_tuple_raises():
    with pytest.raises(rq.RemainderQueueError):
        rq.build_entry({"rows": ({"grant": "x"},)}, rq.REASON_CEILING_BREACH)


def test_value_under_a_matched_key_still_raises():
    with pytest.raises(rq.RemainderQueueError):
        rq.build_entry({"people": [{"grant": "op-grant-123"}]}, rq.REASON_CEILING_BREACH)


# =====================================================================================
# THE FALSE-POSITIVE TESTS (REVIEW-57-M2) — must PERSIST, never raise
# =====================================================================================

def test_armstrong_racing_persists():
    entry = rq.build_entry(
        {"people": [{"company": "Armstrong Racing"}]}, rq.REASON_CEILING_BREACH
    )
    assert entry["spec"]["people"][0]["company"] == "Armstrong Racing"


def test_armidale_jockey_club_persists():
    entry = rq.build_entry(
        {"companies": [{"name": "Armidale Jockey Club", "domain": "ajc.example"}]},
        rq.REASON_CEILING_BREACH,
    )
    assert entry["spec"]["companies"][0]["name"] == "Armidale Jockey Club"


def test_pharmacy_supplier_notes_persist():
    entry = rq.build_entry(
        {"rows": [{"row_id": "1", "notes": "pharmacy supplier"}], "object_type": "contacts"},
        rq.REASON_CEILING_BREACH,
    )
    assert entry["spec"]["rows"][0]["notes"] == "pharmacy supplier"


# =====================================================================================
# The authority test, pinning D-57-05
# =====================================================================================

def test_no_entry_build_entry_produces_ever_contains_a_forbidden_named_key():
    entry = rq.build_entry(
        {"people": [{"company": "Armstrong Racing"}]}, rq.REASON_CEILING_BREACH
    )
    assert not rq._first_forbidden_key(entry["spec"])


def test_a_spec_carrying_a_grant_is_refused():
    with pytest.raises(rq.RemainderQueueError):
        rq.build_entry({"grant": {"lanes": ["enrichment"]}}, rq.REASON_CEILING_BREACH)


# =====================================================================================
# save()
# =====================================================================================

def test_save_writes_a_0600_file_with_the_right_document_shape(monkeypatch, tmp_path):
    _patch_durable_dir(monkeypatch, tmp_path)
    entry = rq.build_entry({"record_ids": ["1"]}, rq.REASON_CEILING_BREACH)
    assert rq.save("run-1", [entry]) is True

    target = rq.remainder_path("run-1")
    assert target.exists()
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    document = json.loads(target.read_text())
    assert document["run_id"] == "run-1"
    assert "saved_at" in document
    assert document["entries"] == [entry]


def test_save_appends_to_an_existing_runs_file(monkeypatch, tmp_path):
    _patch_durable_dir(monkeypatch, tmp_path)
    e1 = rq.build_entry({"record_ids": ["1"]}, rq.REASON_CEILING_BREACH)
    e2 = rq.build_entry({"record_ids": ["2"]}, rq.REASON_ALLOWANCE_SPLIT)
    rq.save("run-1", [e1])
    rq.save("run-1", [e2])

    entries = rq.load(path=rq.remainder_path("run-1"))
    assert entries == [e1, e2]


def test_save_returns_false_never_raises_on_oserror(monkeypatch, tmp_path):
    _patch_durable_dir(monkeypatch, tmp_path)

    def _boom(path, content):
        raise OSError("disk full")

    monkeypatch.setattr(durable_paths, "_atomic_write_0600", _boom)
    entry = rq.build_entry({"record_ids": ["1"]}, rq.REASON_CEILING_BREACH)
    assert rq.save("run-1", [entry]) is False


def test_save_returns_false_never_raises_on_a_non_oserror_exception(monkeypatch, tmp_path):
    """REVIEW-57-M: deliberately wider than `written_records.append_chunk`'s
    `OSError`-only catch — a non-`OSError` escaping the bookkeeping must still not
    take down a live dispatch."""
    _patch_durable_dir(monkeypatch, tmp_path)

    def _boom(path, content):
        raise ValueError("not an OSError at all")

    monkeypatch.setattr(durable_paths, "_atomic_write_0600", _boom)
    entry = rq.build_entry({"record_ids": ["1"]}, rq.REASON_CEILING_BREACH)
    assert rq.save("run-1", [entry]) is False


def test_save_still_raises_on_a_forbidden_named_value_before_writing(monkeypatch, tmp_path):
    """A `RemainderQueueError` is a defect in the DATA, not the environment, and must
    propagate rather than be swallowed by the degrade-rather-than-halt guard above."""
    _patch_durable_dir(monkeypatch, tmp_path)
    bad_entry = {"spec": {"grant": "x"}, "reason": rq.REASON_CEILING_BREACH,
                 "record_count": None, "note": None}
    with pytest.raises(rq.RemainderQueueError):
        rq.save("run-1", [bad_entry])
    assert not rq.remainder_path("run-1").exists()


def test_save_refuses_the_real_durable_directory_under_pytest_when_unpatched():
    """Defense in depth (mirrors `written_records.py`'s own guard): with NOTHING
    patching `durable_paths.resolve_state_path`, `save()` must never land in the
    operator's real durable directory, even under pytest."""
    entry = rq.build_entry({"record_ids": ["1"]}, rq.REASON_CEILING_BREACH)
    assert rq.save("run-real-dir-guard", [entry]) is False
    assert not rq.remainder_path("run-real-dir-guard").exists()


# =====================================================================================
# load()
# =====================================================================================

def test_load_with_no_path_globs_and_unions_every_runs_file(monkeypatch, tmp_path):
    _patch_durable_dir(monkeypatch, tmp_path)
    rq.save("run-a", [rq.build_entry({"record_ids": ["1"]}, rq.REASON_CEILING_BREACH)])
    rq.save("run-b", [rq.build_entry({"record_ids": ["9"]}, rq.REASON_ALLOWANCE_SPLIT)])

    entries = rq.load()
    assert len(entries) == 2
    assert {e[rq.RUN_ID_FIELD] for e in entries} == {"run-a", "run-b"}


def test_load_skips_one_unreadable_file_without_suppressing_the_others(monkeypatch, tmp_path):
    _patch_durable_dir(monkeypatch, tmp_path)
    (tmp_path / "remainder_queue-bad.json").write_text("not json at all", encoding="utf-8")
    rq.save("run-good", [rq.build_entry({"record_ids": ["1"]}, rq.REASON_CEILING_BREACH)])

    entries = rq.load()
    assert len(entries) == 1
    assert entries[0][rq.RUN_ID_FIELD] == "run-good"


def test_load_over_a_document_whose_entries_is_not_a_list_returns_nothing(tmp_path):
    target = tmp_path / "one.json"
    target.write_text(json.dumps({"run_id": "r", "entries": "not-a-list"}))
    assert rq.load(path=target) == []


def test_load_over_a_document_whose_entries_contains_a_non_dict_returns_nothing(tmp_path):
    target = tmp_path / "one.json"
    target.write_text(json.dumps({"run_id": "r", "entries": [1, 2, 3]}))
    assert rq.load(path=target) == []


def test_load_with_explicit_path_and_no_file_returns_empty(tmp_path):
    assert rq.load(path=tmp_path / "does-not-exist.json") == []


def test_load_with_no_path_on_a_missing_durable_directory_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(
        durable_paths, "resolve_state_path",
        lambda *a, **k: tmp_path / "does-not-exist" / "dashboard_artifact.json",
    )
    assert rq.load() == []
