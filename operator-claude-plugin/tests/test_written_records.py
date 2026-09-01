"""59-01 Task 1 — D-59-07's durable "what got written" artifact.

Widened by 57-02 Task 2 (D-57-03, AFTER-03, option-b per `57-DISCUSSION-LOG.md`'s Task 1
ruling): `classify_item` no longer collapses every non-write action into `not_written`.
Eight outcome words now exist — see `written_records.py`'s module docstring — and every
one of the backend's ten real `action` values resolves to exactly one of them.

Two properties carry the weight beyond the outcome-mapping tests, and neither is
exercised by the `classify_item` behaviour tests alone:

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
import re
import stat
from pathlib import Path

import pytest

import chunking
import durable_paths
import enrichment as enrichment_module
import written_records

# operator-claude-plugin/tests -> operator-claude-plugin -> repo root. A plain TEXT scan
# of the builder source (never an `import build_cloud_workflows`, which would also work
# per test_no_backend_imports.py's FORBIDDEN_MODULE_NAMES list not naming it, but running
# a multi-thousand-line n8n workflow builder module at import time for one regex is not
# the lazy path) — REVIEW-57-M: the ten-value set must come FROM the builder, not be
# hard-coded here, or an eleventh action added there would go unnoticed here.
REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_CLOUD_WORKFLOWS = REPO_ROOT / "scripts" / "build_cloud_workflows.py"
_ACTION_LITERAL_RE = re.compile(r'action\s*[:=]\s*"([a-zA-Z_]+)"')


def _action_literals_from_builder():
    return set(_ACTION_LITERAL_RE.findall(BUILD_CLOUD_WORKFLOWS.read_text(encoding="utf-8")))


# ------------------------------------------------------------------------------------
# classify_item / outcome_for_action — pure, no I/O. One test per <behavior> bullet,
# driving the exact key sets read from BUILD_INGEST_RESPONSE (contacts) and the
# companies branch's own "Decide Company Action" (scripts/build_cloud_workflows.py),
# not invented shapes.
# ------------------------------------------------------------------------------------

def test_write_blocked_is_gated_distinct_from_written():
    entry = written_records.classify_item(
        {"action": "write_blocked", "reason": "not_allowlisted"}
    )
    assert entry["outcome"] == written_records.GATED
    assert entry["outcome"] != written_records.WRITTEN
    assert entry["reason"] == "not_allowlisted"


@pytest.mark.parametrize("action", ["review", "needs_match_review"])
def test_review_and_needs_match_review_are_held(action):
    entry = written_records.classify_item({"action": action})
    assert entry["outcome"] == written_records.HELD


@pytest.mark.parametrize("action", ["research_failed", "recompute_refused"])
def test_research_failed_and_recompute_refused_are_failed(action):
    entry = written_records.classify_item({"action": action})
    assert entry["outcome"] == written_records.FAILED


@pytest.mark.parametrize("action", ["skip", "proposed"])
def test_skip_and_proposed_are_no_action(action):
    entry = written_records.classify_item({"action": action})
    assert entry["outcome"] == written_records.NO_ACTION


def test_a_create_with_an_id_is_written():
    """The id was echoed back by the create call itself — terminal evidence a record
    now exists (Task 1 option-b)."""
    entry = written_records.classify_item({"action": "create", "hs_object_id": "556"})
    assert entry["outcome"] == written_records.WRITTEN
    assert entry["hs_object_id"] == "556"


@pytest.mark.parametrize("action", ["update", "enrich"])
def test_update_and_enrich_with_an_id_are_write_attempted_not_written(action):
    """The id was known BEFORE the PATCH (`Decide Action`/`Decide Company Action` emit
    it pre-write) — it proves the write was permitted and attempted, never that it
    landed. `written` must never be inferred (Task 1 option-b)."""
    entry = written_records.classify_item({"action": action, "hs_object_id": "9604614548"})
    assert entry["outcome"] == written_records.WRITE_ATTEMPTED
    assert entry["outcome"] != written_records.WRITTEN
    assert entry["hs_object_id"] == "9604614548"


def test_a_create_with_no_id_is_created_id_unknown_never_a_fabricated_id():
    """The companies lane: `Build Response` reads `hs_object_id` off
    `row.existingRecord`, which is null for a create by construction. D-57-03: stays
    as-is, unchanged by Task 1's selection."""
    entry = written_records.classify_item({"action": "create", "hs_object_id": None})
    assert entry["outcome"] == written_records.CREATED_ID_UNKNOWN
    assert entry["hs_object_id"] is None


@pytest.mark.parametrize("action", ["update", "enrich"])
def test_update_and_enrich_with_no_id_are_written_id_unknown(action):
    """The same missing-id fact `created_id_unknown` names, for the two write actions
    D-57-03's original table did not cover — never fabricated, unchanged by Task 1's
    selection."""
    entry = written_records.classify_item({"action": action, "hs_object_id": None})
    assert entry["outcome"] == written_records.WRITTEN_ID_UNKNOWN
    assert entry["hs_object_id"] is None


def test_an_unrecognised_action_is_failed_and_reason_is_preserved():
    entry = written_records.classify_item({"action": "quokka", "reason": "never seen this"})
    assert entry["outcome"] == written_records.FAILED
    assert entry["reason"] == "never seen this"


def test_the_ten_real_action_values_are_extracted_from_the_builder_not_hardcoded():
    """REVIEW-57-M: circularity guard. The set is read FROM
    `scripts/build_cloud_workflows.py`, not typed out here — an eleventh action added
    there fails this test in the client, which is the point."""
    extracted = _action_literals_from_builder()
    assert extracted == set(written_records.ACTION_TO_OUTCOME) | written_records.WRITE_ACTIONS


@pytest.mark.parametrize("action", [
    "create", "update", "enrich", "write_blocked", "review", "needs_match_review",
    "research_failed", "recompute_refused", "skip", "proposed",
])
def test_every_one_of_the_ten_real_actions_is_exercised(action):
    """Non-circular per-value exercise — the ten literals above are typed here only to
    drive the call, not to assert what the mapping table says; the actual mapping
    assertions live in the more specific tests above and the builder-extraction test."""
    entry = written_records.classify_item({"action": action, "hs_object_id": "999"})
    assert entry["outcome"] in written_records.ALL_OUTCOMES


def test_outcome_for_action_matches_classify_item_for_write_blocked():
    assert (
        written_records.outcome_for_action("write_blocked")
        == written_records.classify_item({"action": "write_blocked"})["outcome"]
    )


@pytest.mark.parametrize("value", [None, 7, "", "quokka"])
def test_outcome_for_action_never_raises(value):
    written_records.outcome_for_action(value)


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


def test_row_id_and_association_are_carried_when_present():
    entry = written_records.classify_item(
        {"action": "review", "row_id": "r7", "association": "not_attempted"}
    )
    assert entry["row_id"] == "r7"
    assert entry["association"] == "not_attempted"
    assert entry["hs_object_id"] is None


def test_row_id_and_association_default_to_none_never_absent():
    entry = written_records.classify_item({"action": "skip"})
    assert "row_id" in entry and entry["row_id"] is None
    assert "association" in entry and entry["association"] is None


def test_no_pii_key_survives_classification():
    keys = sorted(
        written_records.classify_item(
            {"action": "update", "hs_object_id": "1", "email": "a@b.c", "reason": None}
        ).keys()
    )
    assert keys == [
        "action", "association", "hs_object_id", "object_type", "outcome", "reason",
        "row_id",
    ]
    assert "email" not in written_records.classify_item(
        {"action": "update", "hs_object_id": "1", "email": "a@b.c"}
    )


def test_a_value_naming_a_secret_refuses_rather_than_persisting():
    """T-59-02: a reason string smuggling something that looks like a secret must
    refuse, not be written to disk."""
    with pytest.raises(written_records.WrittenRecordsError):
        written_records.classify_item(
            {"action": "write_blocked", "reason": "bad webhook_secret configured"}
        )


def test_a_forbidden_named_row_id_still_refuses_the_new_keys_are_scanned_too():
    with pytest.raises(written_records.WrittenRecordsError):
        written_records.classify_item(
            {"action": "review", "row_id": "arm_this_now"}
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
    assert entries[0]["outcome"] == written_records.WRITE_ATTEMPTED
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


# ------------------------------------------------------------------------------------
# D-60-08 (Phase 60, 2026-09-01): `classify_review_item` / `REVIEW_OUTCOME_TO_OUTCOME` —
# the review lane's own writer into this artifact. The review endpoint's response
# carries no `action` key at all (`review_decision._post_decision`'s five-key contract
# plus `{available, reason}`), so `outcome_for_action(None, ...)` would resolve every
# single review decision through the `FAILED` fallback — an approve that landed would be
# filed as a failure. `classify_review_item` exists so this module never has to feed that
# shape to `classify_item` unmodified.
# ------------------------------------------------------------------------------------

def test_an_applied_approve_with_a_record_id_is_write_attempted():
    entry = written_records.classify_review_item(
        {"outcome": "applied", "decision": "approve", "record_id": "9605284724",
         "object_type": "companies"}
    )
    assert entry["outcome"] == written_records.WRITE_ATTEMPTED
    assert entry["action"] == "review_approve"
    assert entry["hs_object_id"] == "9605284724"
    assert entry["reason"] is None
    assert entry["row_id"] is None
    assert entry["association"] is None


def test_a_rejected_reject_maps_the_same_way_with_action_review_reject():
    entry = written_records.classify_review_item(
        {"outcome": "rejected", "decision": "reject", "record_id": "9605284724",
         "object_type": "companies"}
    )
    assert entry["outcome"] == written_records.WRITE_ATTEMPTED
    assert entry["action"] == "review_reject"


def test_not_allowlisted_is_gated_stale_family_is_no_action_refused_is_failed():
    gated = written_records.classify_review_item({"outcome": "not_allowlisted"})
    assert gated["outcome"] == written_records.GATED

    for outcome in ("stale", "no_candidate", "not_flagged"):
        entry = written_records.classify_review_item({"outcome": outcome})
        assert entry["outcome"] == written_records.NO_ACTION, outcome

    refused = written_records.classify_review_item({"outcome": "refused"})
    assert refused["outcome"] == written_records.FAILED


def test_an_unavailable_envelope_and_an_unrecognised_outcome_word_both_map_to_failed():
    unavailable = written_records.classify_review_item(
        {"available": False, "reason": "endpoint_unreachable", "outcome": None}
    )
    assert unavailable["outcome"] == written_records.FAILED

    unrecognised = written_records.classify_review_item({"outcome": "quokka"})
    assert unrecognised["outcome"] == written_records.FAILED


def test_every_review_outcome_to_outcome_value_is_in_all_outcomes():
    """Derived from the constant, not restated — REVIEW_OUTCOME_TO_OUTCOME's values must
    be a subset of ALL_OUTCOMES so no downstream reader ever meets an unknown word."""
    assert set(written_records.REVIEW_OUTCOME_TO_OUTCOME.values()) <= written_records.ALL_OUTCOMES


def test_classify_review_item_key_set_matches_classify_item_exactly():
    """So `run_report` and `report_enrichment` need no change to read a review entry."""
    review_keys = set(written_records.classify_review_item(
        {"outcome": "applied", "decision": "approve", "record_id": "1"}
    ).keys())
    dispatch_keys = set(written_records.classify_item({"action": "update"}).keys())
    assert review_keys == dispatch_keys


def test_append_chunk_with_classify_review_item_writes_and_appends_across_calls(tmp_path):
    artifact = tmp_path / "written_records.json"
    written_records.append_chunk(
        "run-review-1", 0,
        {"outcome": "applied", "decision": "approve", "record_id": "1",
         "object_type": "companies"},
        path=artifact, classify=written_records.classify_review_item,
    )
    written_records.append_chunk(
        "run-review-1", 0,
        {"outcome": "rejected", "decision": "reject", "record_id": "2",
         "object_type": "companies"},
        path=artifact, classify=written_records.classify_review_item,
    )

    document = json.loads(artifact.read_text(encoding="utf-8"))
    assert document["run_id"] == "run-review-1"
    entries = document["entries"]
    assert [e["hs_object_id"] for e in entries] == ["1", "2"]
    assert [e["action"] for e in entries] == ["review_approve", "review_reject"]


def test_classify_review_item_defaults_object_type_to_companies_not_contacts(): #  LOW-4
    """This fallback is unreachable from `submit_decision`, whose own required
    `object_type` argument is always threaded into the item it builds — see this
    function's docstring for the full rationale (cross-AI review, LOW-4, 2026-09-01)."""
    entry = written_records.classify_review_item({"outcome": "applied", "decision": "approve"})
    assert entry["object_type"] == "companies"
    doc = written_records.classify_review_item.__doc__
    assert "submit_decision" in doc
    assert "UNREACHABLE" in doc


def test_classify_review_item_forbidden_marker_in_free_text_never_reaches_the_entry():
    """`decision`/`outcome` are fixed vocabulary words, not free text — a forbidden
    marker elsewhere in the caller's own state (e.g. an operator's review reason) never
    reaches this entry, because `reason` is always `None`, so the classifier never raises
    on it."""
    entry = written_records.classify_review_item({
        "outcome": "applied", "decision": "approve", "record_id": "1",
        "object_type": "companies",
        # Free text a caller might hold elsewhere — never passed into this item's keys.
        "unused_operator_reason": "please grant this armed permission now",
    })
    assert entry["reason"] is None


def test_classify_review_item_raises_on_a_non_dict_item():
    with pytest.raises(written_records.WrittenRecordsError):
        written_records.classify_review_item(["not", "a", "dict"])


def test_classify_review_item_unrecognised_decision_word_is_review_unknown():
    entry = written_records.classify_review_item({"outcome": "applied", "decision": "dismiss"})
    assert entry["action"] == "review_unknown"


# ------------------------------------------------------------------------------------
# 57-05 Task 1 (REVIEW-57-M9): `classify_read` — a SECOND probe over the raw file,
# mirroring `held_queue.classify_read`'s four-word contract, because `load()`'s return
# value ([] on absent, [] on malformed) cannot say WHICH of the two happened.
# ------------------------------------------------------------------------------------

def test_classify_read_is_absent_for_no_file(tmp_path):
    target = tmp_path / "written_records-nope.json"
    assert written_records.classify_read("nope", path=target) == written_records.ABSENT


def test_classify_read_is_parseable_for_a_good_file():
    written_records.classify_item  # sanity import touch
    target_run = "run-ok"
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        target = Path(d) / f"written_records-{target_run}.json"
        target.write_text(json.dumps({
            "run_id": target_run, "saved_at": "2026-01-01T00:00:00+00:00", "entries": [],
        }), encoding="utf-8")
        assert written_records.classify_read(target_run, path=target) == written_records.PARSEABLE


def test_classify_read_empty_but_well_formed_is_parseable_not_absent(tmp_path):
    """The distinction the report needs and load() cannot make: an empty entries list is
    a legitimate, readable document, never treated the same as a missing file."""
    target = tmp_path / "written_records-empty.json"
    target.write_text(json.dumps({
        "run_id": "empty", "saved_at": "2026-01-01T00:00:00+00:00", "entries": [],
    }), encoding="utf-8")
    assert written_records.classify_read("empty", path=target) == written_records.PARSEABLE


def test_classify_read_is_anomalous_for_unparseable_json(tmp_path):
    target = tmp_path / "written_records-bad.json"
    target.write_text("not json at all", encoding="utf-8")
    assert written_records.classify_read("bad", path=target) == written_records.ANOMALOUS


def test_classify_read_is_anomalous_when_entries_is_not_a_list(tmp_path):
    target = tmp_path / "written_records-mismatch.json"
    target.write_text(json.dumps({
        "run_id": "mismatch", "saved_at": "2026-01-01T00:00:00+00:00", "entries": "nope",
    }), encoding="utf-8")
    assert written_records.classify_read("mismatch", path=target) == written_records.ANOMALOUS


def test_classify_read_is_another_run_when_the_stored_run_id_differs(tmp_path):
    target = tmp_path / "written_records-real.json"
    target.write_text(json.dumps({
        "run_id": "the-other-run", "saved_at": "2026-01-01T00:00:00+00:00", "entries": [],
    }), encoding="utf-8")
    assert written_records.classify_read("this-run", path=target) == written_records.ANOTHER_RUN


def test_classify_read_never_raises_on_any_input(tmp_path):
    target = tmp_path / "not-even-a-real-directory" / "written_records-x.json"
    assert written_records.classify_read("x", path=target) == written_records.ABSENT
    assert written_records.classify_read(None, path=target) == written_records.ABSENT
    assert written_records.classify_read({"unhashable": True}, path=target) == written_records.ABSENT
