"""59-01 Task 1 — D-59-07's durable "what got written" artifact.

Two properties carry the weight, and neither is exercised by the `classify_item`
behaviour tests alone:

* the flush is INLINE in `chunking.dispatch_plan`'s loop, not assembled after it — a run
  that dies mid-loop must still leave the durable file holding every chunk that landed
  before the crash (`test_a_dispatch_that_crashes_mid_loop_...`);
* no row the backend refused is ever reported as written.

Every test that drives `chunking.dispatch_plan` redirects `written_records.written_records_path`
to a `tmp_path` file via `monkeypatch` rather than touching the operator's real durable
home — the same discipline every existing test in this suite already follows for
`durable_paths`-resolved files (`run_manifest.py`, `artifact_store.py`), just applied
through a monkeypatch instead of a `path=` kwarg because `chunking.dispatch_plan` itself
takes no such parameter (see 59-01-PLAN.md's wiring section — only `run_id` was added).
"""
import json
import stat

import pytest

import chunking
import durable_paths
import enrichment as enrichment_module
import written_records

# ------------------------------------------------------------------------------------
# classify_item — pure, no I/O. One test per <behavior> bullet, driving the exact key
# sets read from BUILD_INGEST_RESPONSE (contacts) and the companies branch's own
# "Decide Company Action" (scripts/build_cloud_workflows.py), not invented shapes.
# ------------------------------------------------------------------------------------

def test_an_update_with_an_id_is_written():
    entry = written_records.classify_item(
        {"action": "update", "hs_object_id": "123", "email": "a@b.c"}
    )
    assert entry["outcome"] == written_records.WRITTEN
    assert entry["hs_object_id"] == "123"
    assert entry["action"] == "update"


def test_an_enrich_with_an_id_is_written():
    entry = written_records.classify_item(
        {"action": "enrich", "hs_object_id": "9604614548"}
    )
    assert entry["outcome"] == written_records.WRITTEN
    assert entry["hs_object_id"] == "9604614548"


def test_a_create_with_a_resolved_id_is_written():
    """The contacts lane resolves a real post-write id on create."""
    entry = written_records.classify_item({"action": "create", "hs_object_id": "556"})
    assert entry["outcome"] == written_records.WRITTEN
    assert entry["hs_object_id"] == "556"


def test_a_create_with_no_id_is_created_id_unknown_never_a_fabricated_id():
    """The companies lane: `Build Response` reads `hs_object_id` off
    `row.existingRecord`, which is null for a create by construction."""
    entry = written_records.classify_item({"action": "create", "hs_object_id": None})
    assert entry["outcome"] == written_records.CREATED_ID_UNKNOWN
    assert entry["hs_object_id"] is None


def test_a_write_blocked_row_is_not_written_and_carries_the_reason_verbatim():
    entry = written_records.classify_item(
        {"action": "write_blocked", "reason": "not_allowlisted"}
    )
    assert entry["outcome"] == written_records.NOT_WRITTEN
    assert entry["reason"] == "not_allowlisted"


@pytest.mark.parametrize(
    "action", ["proposed", "skip", "needs_match_review", "review", "held", "bogus"]
)
def test_every_non_write_action_is_not_written(action):
    entry = written_records.classify_item({"action": action, "hs_object_id": "999"})
    assert entry["outcome"] == written_records.NOT_WRITTEN


def test_a_non_dict_item_raises_rather_than_being_skipped():
    """The FINDING 2 discipline (53-WALK-RECORD.md, commit 9e603d6): fail loud on a
    shape mismatch instead of silently filing it as absent."""
    with pytest.raises(written_records.WrittenRecordsError):
        written_records.classify_item(["not", "a", "dict"])


def test_object_type_defaults_to_contacts_when_the_item_carries_none():
    """`BUILD_INGEST_RESPONSE` bodies (contacts lane) never carry `object_type` at all,
    and the companies branch's own skip-terminal reaching `Build Response` without
    passing through `Decide Company Action` applies this identical default."""
    entry = written_records.classify_item({"action": "enrich", "hs_object_id": "1"})
    assert entry["object_type"] == "contacts"


def test_object_type_is_carried_through_when_present():
    entry = written_records.classify_item(
        {"action": "enrich", "hs_object_id": "1", "object_type": "companies"}
    )
    assert entry["object_type"] == "companies"


def test_no_pii_key_survives_classification():
    keys = sorted(
        written_records.classify_item(
            {"action": "update", "hs_object_id": "1", "email": "a@b.c", "reason": None}
        ).keys()
    )
    assert keys == ["action", "hs_object_id", "object_type", "outcome", "reason"]


def test_a_value_naming_a_secret_refuses_rather_than_persisting():
    """T-59-02: a reason string smuggling something that looks like a secret must
    refuse, not be written to disk."""
    with pytest.raises(written_records.WrittenRecordsError):
        written_records.classify_item(
            {"action": "write_blocked", "reason": "bad webhook_secret configured"}
        )


# ------------------------------------------------------------------------------------
# append_chunk — the durable flush.
# ------------------------------------------------------------------------------------

def test_three_chunks_appended_leave_one_file_holding_all_three_in_order(tmp_path):
    artifact = tmp_path / "written_records.json"
    for index, hs_id in enumerate(["1", "2", "3"]):
        written_records.append_chunk(
            "run-a", index, {"action": "update", "hs_object_id": hs_id}, path=artifact
        )

    entries = written_records.load(path=artifact)
    assert [e["chunk_index"] for e in entries] == [0, 1, 2]
    assert [e["hs_object_id"] for e in entries] == ["1", "2", "3"]


def test_append_chunk_flattens_a_list_body_into_one_entry_per_row(tmp_path):
    artifact = tmp_path / "written_records.json"
    written_records.append_chunk(
        "run-b", 0,
        [{"action": "update", "hs_object_id": "1"}, {"action": "create", "hs_object_id": None}],
        path=artifact,
    )
    entries = written_records.load(path=artifact)
    assert len(entries) == 2
    assert entries[0]["outcome"] == written_records.WRITTEN
    assert entries[1]["outcome"] == written_records.CREATED_ID_UNKNOWN


def test_two_different_run_ids_written_to_the_same_explicit_path_are_appended_not_replaced(tmp_path):
    """D-59-09 removed the run-id-mismatch replace branch: under per-run files this
    never fires in production (two runs never share a path — see `written_records_path`),
    so what is left at the explicit-`path=` escape hatch is simpler — a document already
    on disk is always appended to, whichever `run_id` wrote it last."""
    artifact = tmp_path / "written_records.json"
    written_records.append_chunk(
        "run-old", 0, {"action": "update", "hs_object_id": "1"}, path=artifact
    )
    written_records.append_chunk(
        "run-new", 0, {"action": "update", "hs_object_id": "2"}, path=artifact
    )
    entries = written_records.load(path=artifact)
    assert [e["hs_object_id"] for e in entries] == ["1", "2"]


def test_append_chunk_to_an_unwritable_path_does_not_raise(tmp_path):
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocked.chmod(0o000)
    try:
        target = blocked / "sub" / "written_records.json"
        result = written_records.append_chunk(
            "run-c", 0, {"action": "update", "hs_object_id": "1"}, path=target
        )
        assert not result
    finally:
        blocked.chmod(0o700)


def test_append_chunk_propagates_a_written_records_error_rather_than_swallowing_it(tmp_path):
    """A shape/forbidden-name problem is a defect in the data, not an environment
    condition — it must NOT be caught by the OSError guard."""
    artifact = tmp_path / "written_records.json"
    with pytest.raises(written_records.WrittenRecordsError):
        written_records.append_chunk("run-d", 0, "not-a-dict-or-list", path=artifact)


# ------------------------------------------------------------------------------------
# load — degrades WHOLE, never partially.
# ------------------------------------------------------------------------------------

def test_load_on_a_missing_file_returns_empty(tmp_path):
    assert written_records.load(path=tmp_path / "nope.json") == []


def test_load_on_truncated_json_returns_empty(tmp_path):
    target = tmp_path / "truncated.json"
    target.write_text('{"run_id": "x", "entries": [{"chunk_index": 0,', encoding="utf-8")
    assert written_records.load(path=target) == []


def test_load_on_a_non_dict_json_document_returns_empty(tmp_path):
    target = tmp_path / "bad_shape.json"
    target.write_text("[1, 2, 3]", encoding="utf-8")
    assert written_records.load(path=target) == []


def test_load_on_entries_holding_a_non_dict_item_returns_empty_not_partial(tmp_path):
    target = tmp_path / "half_written.json"
    target.write_text(
        '{"run_id": "x", "entries": [{"chunk_index": 0, "action": "update"}, "oops"]}',
        encoding="utf-8",
    )
    assert written_records.load(path=target) == []


# ------------------------------------------------------------------------------------
# THE TRACER'S OWN TEST — the crash-survival gap 59-VALIDATION.md names.
#
# `enrichment.dispatch_enrichment` — not the transport `stub_module_transport_factory`
# hands `chunking.dispatch_plan` — is monkeypatched to raise. `dispatch_enrichment`
# itself wraps EVERY exception a transport's `.post()` raises (including a bare
# RuntimeError) into `DispatchError` (its own `except Exception:` block, `enrichment.py`),
# and `chunking.dispatch_plan`'s loop deliberately CATCHES `DispatchError` and continues
# (D-11b) — so a RuntimeError injected at the transport layer would never reach this
# test the way it needs to. Injecting at the boundary `dispatch_plan`'s loop actually
# calls per chunk is what lets a bare RuntimeError — deliberately not one of the three
# exception types the loop's try/except names (`NotArmedError`/`DispatchError`/
# `enrichment.RecordSpecError`) — escape exactly as a killed process would.
# ------------------------------------------------------------------------------------

def test_a_dispatch_that_crashes_mid_loop_leaves_a_durable_file_holding_earlier_chunks(
    fake_config, stub_module_transport_factory, tmp_path, monkeypatch
):
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)

    plan = chunking.plan_chunks(
        {"record_ids": [str(n) for n in range(1, 6)], "object_type": "companies"}, 1
    )
    assert plan.chunk_count == 5, "the point of the test is a mid-run crash, not a one-off"

    real_dispatch_enrichment = enrichment_module.dispatch_enrichment
    calls = {"count": 0}

    def _flaky(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 3:
            raise RuntimeError("simulated process kill mid-dispatch")
        return real_dispatch_enrichment(*args, **kwargs)

    monkeypatch.setattr(chunking.enrichment, "dispatch_enrichment", _flaky)

    with pytest.raises(RuntimeError):
        chunking.dispatch_plan(
            plan, ["lusha"], True, fake_config,
            transport=stub_module_transport_factory(), run_id="crash-run",
        )

    entries = written_records.load(path=artifact)
    assert [e["chunk_index"] for e in entries] == [0, 1], (
        "chunks 0 and 1 must already be on disk — the flush happened INLINE, before "
        "the crash on chunk index 2"
    )


def test_a_clean_five_chunk_run_leaves_all_five_chunks_on_disk(
    fake_config, stub_module_transport_factory, tmp_path, monkeypatch
):
    """The positive control for the crash test above — without it, an implementation
    that flushed nothing would still pass the crash assertion vacuously (0 == 0 is not
    what `[0, 1]` asserts against, but this pins the happy path explicitly anyway)."""
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)

    plan = chunking.plan_chunks(
        {"record_ids": [str(n) for n in range(1, 6)], "object_type": "companies"}, 1
    )
    chunking.dispatch_plan(
        plan, ["lusha"], True, fake_config,
        transport=stub_module_transport_factory(), run_id="clean-run",
    )

    entries = written_records.load(path=artifact)
    assert [e["chunk_index"] for e in entries] == [0, 1, 2, 3, 4]


# ------------------------------------------------------------------------------------
# D-59-09 (operator, 2026-08-29) — one artifact per run_id, and a reader that globs and
# unions. `durable_paths.resolve_state_path` is monkeypatched directly (not
# `written_records.written_records_path`) so that BOTH `append_chunk`'s per-run write
# and `load()`'s no-argument glob resolve into the SAME tmp_path directory, exactly as
# they would against one real durable home.
# ------------------------------------------------------------------------------------

def _patch_durable_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(
        durable_paths, "resolve_state_path",
        lambda *a, **k: tmp_path / "dashboard_artifact.json",
    )


def test_two_interleaved_dispatch_runs_against_one_durable_directory_do_not_clobber_each_other(
    fake_config, stub_module_transport_factory, tmp_path, monkeypatch
):
    """THE test the gap needed — driven through `dispatch_plan`, not `append_chunk`
    alone (a unit test of `append_chunk` in isolation is exactly the kind of test that
    let this gap ship). Two REAL runs, interleaved by hand: run A flushes a chunk, run B
    (a DIFFERENT run_id) flushes into the same durable directory, then run A flushes
    again. Under the pre-D-59-09 shared path, run B's flush would replace run A's
    earlier chunk on disk (the old run-id-mismatch branch); under per-run paths nothing
    is lost and no lock is involved."""
    _patch_durable_dir(monkeypatch, tmp_path)

    plan_a_first = chunking.ChunkPlan(
        chunks=({"record_ids": ["1"], "object_type": "companies"},),
        row_counts=(1,), record_count=1,
    )
    plan_b = chunking.ChunkPlan(
        chunks=({"record_ids": ["9"], "object_type": "companies"},),
        row_counts=(1,), record_count=1,
    )
    plan_a_second = chunking.ChunkPlan(
        chunks=({"record_ids": ["2"], "object_type": "companies"},),
        row_counts=(1,), record_count=1,
    )

    chunking.dispatch_plan(plan_a_first, ["lusha"], True, fake_config,
                            transport=stub_module_transport_factory(), run_id="run-a")
    chunking.dispatch_plan(plan_b, ["lusha"], True, fake_config,
                            transport=stub_module_transport_factory(), run_id="run-b")
    chunking.dispatch_plan(plan_a_second, ["lusha"], True, fake_config,
                            transport=stub_module_transport_factory(), run_id="run-a")

    entries_a = written_records.load(path=written_records.written_records_path("run-a"))
    entries_b = written_records.load(path=written_records.written_records_path("run-b"))
    assert len(entries_a) == 2, "run A's earlier chunk must survive run B's later flush"
    assert len(entries_b) == 1


def test_load_with_no_path_unions_every_runs_file_and_names_the_run_on_each_entry(
    fake_config, stub_module_transport_factory, tmp_path, monkeypatch
):
    _patch_durable_dir(monkeypatch, tmp_path)

    plan_a = chunking.plan_chunks({"record_ids": ["1"], "object_type": "companies"}, 1)
    plan_b = chunking.plan_chunks({"record_ids": ["9"], "object_type": "companies"}, 1)
    chunking.dispatch_plan(plan_a, ["lusha"], True, fake_config,
                            transport=stub_module_transport_factory(), run_id="run-a")
    chunking.dispatch_plan(plan_b, ["lusha"], True, fake_config,
                            transport=stub_module_transport_factory(), run_id="run-b")

    entries = written_records.load()
    assert len(entries) == 2, "one entry per run, one record each"
    assert {e[written_records.RUN_ID_FIELD] for e in entries} == {"run-a", "run-b"}


def test_load_globs_and_finds_a_legacy_pre_change_filename_too(tmp_path, monkeypatch):
    """The glob is `written_records*.json`, NOT hyphen-anchored — an artifact an
    operator already has under the pre-D-59-09 shared filename must not vanish."""
    _patch_durable_dir(monkeypatch, tmp_path)
    directory = tmp_path
    legacy = directory / "written_records.json"
    legacy.write_text(json.dumps({
        "run_id": "legacy-run",
        "saved_at": "2026-01-01T00:00:00+00:00",
        "entries": [{
            "chunk_index": 0, "action": "update", "hs_object_id": "1",
            "object_type": "contacts", "outcome": "written", "reason": None,
        }],
    }), encoding="utf-8")

    written_records.append_chunk("run-new", 0, {"action": "update", "hs_object_id": "2"})

    entries = written_records.load()
    assert {e["hs_object_id"] for e in entries} == {"1", "2"}


def test_load_with_no_path_on_a_missing_durable_directory_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(
        durable_paths, "resolve_state_path",
        lambda *a, **k: tmp_path / "does-not-exist" / "dashboard_artifact.json",
    )
    assert written_records.load() == []


def test_load_with_no_path_skips_one_unreadable_file_without_suppressing_the_others(
    tmp_path, monkeypatch
):
    _patch_durable_dir(monkeypatch, tmp_path)
    (tmp_path / "written_records-bad.json").write_text("not json at all", encoding="utf-8")
    written_records.append_chunk("run-good", 0, {"action": "update", "hs_object_id": "1"})

    entries = written_records.load()
    assert [e["hs_object_id"] for e in entries] == ["1"]


def test_load_with_no_path_skips_a_schema_mismatched_file_without_suppressing_the_others(
    tmp_path, monkeypatch
):
    _patch_durable_dir(monkeypatch, tmp_path)
    (tmp_path / "written_records-mismatch.json").write_text("[1, 2, 3]", encoding="utf-8")
    written_records.append_chunk("run-good", 0, {"action": "update", "hs_object_id": "1"})

    entries = written_records.load()
    assert [e["hs_object_id"] for e in entries] == ["1"]


def test_the_per_run_file_is_written_0600_and_is_not_a_dotfile(tmp_path, monkeypatch):
    _patch_durable_dir(monkeypatch, tmp_path)
    written_records.append_chunk("run-perm", 0, {"action": "update", "hs_object_id": "1"})

    target = written_records.written_records_path("run-perm")
    assert target.exists()
    assert not target.name.startswith("."), "Phase 23 D-04: must not be a dotfile"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
