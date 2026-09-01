"""The chunk plan (25-06 Task 1) — the split the preview shows and dispatch sends.

Two assertions here carry the weight, and neither is a chunk-count assertion:

* the concatenation of every chunk equals the input id sequence EXACTLY, in order —
  an off-by-one in the split is invisible to a count assertion and silently drops or
  re-enriches a record;
* a backend-resolved list plan reports its record count as the word "unknown" — the
  client cannot count what the backend resolves (D-02), and a fabricated number here is
  the partial-read-impersonating-a-healthy-number shape this milestone has hit repeatedly.
"""
import ast
import inspect
import json
from pathlib import Path

import pytest
import requests

import chunking
import config_gate
import durable_paths
import enrichment
import executions_client
import n8n_arming
import preingest
import remainder_queue
import run_state
import watch
import write_grant
import written_records
from dispatch import NotArmedError, dispatch

CONFIG_EXAMPLE = (
    Path(__file__).resolve().parent.parent / "config" / "operator.local.example.json"
)


def ids(count, start=1):
    return [str(n) for n in range(start, start + count)]


def spec(count, object_type="companies"):
    return {"record_ids": ids(count), "object_type": object_type}


# ----------------------------------------------------------------------------------
# The ceiling is READ, never defaulted.
# ----------------------------------------------------------------------------------

def test_the_ceiling_comes_from_config():
    assert chunking.chunk_ceiling({"max_records_per_chunk": 3}) == 3


def test_a_config_without_the_ceiling_key_raises_rather_than_defaulting():
    """D-20: an absent key means the ceiling is UNCONFIGURED, not that 2 is safe.

    A fallback constant would be a third copy of a number that already exists in two
    files pinned together by tests/test_chunk_ceiling_contract.py.
    """
    with pytest.raises(chunking.ChunkPlanError) as excinfo:
        chunking.chunk_ceiling({"n8n_url": "https://fake.n8n.cloud"})
    assert "max_records_per_chunk" in str(excinfo.value)


def test_no_fallback_ceiling_constant_exists_in_the_module():
    """The number must appear nowhere in this module's source — not as a default
    argument, not as a module constant. Phase 25 has already shipped two copy-of-one-
    contract bugs (the list envelope, 13006fa; the ceiling itself, 1196c57)."""
    shipped = json.loads(CONFIG_EXAMPLE.read_text())["max_records_per_chunk"]
    tree = ast.parse(Path(chunking.__file__).read_text())

    defaults = [
        default
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for default in node.args.defaults + [d for d in node.args.kw_defaults if d]
    ]
    module_assignments = [
        node.value for node in tree.body if isinstance(node, (ast.Assign, ast.AnnAssign))
    ]
    literals = [
        node.value
        for node in defaults + module_assignments
        if isinstance(node, ast.Constant) and isinstance(node.value, int)
    ]
    assert shipped not in literals, (
        f"a default or module constant of {shipped} in chunking.py is a THIRD copy of "
        f"the chunk ceiling — read it from config instead"
    )


def test_a_ceiling_below_one_raises_rather_than_planning():
    for ceiling in (0, -1):
        with pytest.raises(chunking.ChunkPlanError):
            chunking.plan_chunks(spec(5), ceiling)


def test_a_non_integer_ceiling_raises():
    with pytest.raises(chunking.ChunkPlanError):
        chunking.chunk_ceiling({"max_records_per_chunk": "two"})


# ----------------------------------------------------------------------------------
# The `key` parameter: match reads its own ceiling with the identical no-fallback rule.
# ----------------------------------------------------------------------------------

def test_chunk_ceiling_with_no_key_argument_behaves_exactly_as_today():
    assert chunking.chunk_ceiling({"max_records_per_chunk": 3}) == 3
    with pytest.raises(chunking.ChunkPlanError):
        chunking.chunk_ceiling({})


def test_chunk_ceiling_reads_the_match_key_and_it_is_larger_than_the_write_ceiling():
    config = json.loads(CONFIG_EXAMPLE.read_text())
    match_ceiling = chunking.chunk_ceiling(config, key="max_rows_per_match_request")
    write_ceiling = chunking.chunk_ceiling(config)
    assert match_ceiling > write_ceiling


def _match_item(row_id, tier, hs_object_id=None):
    """Duplicated verbatim from test_run_manifest.py:415-422."""
    match = {"tier": tier}
    if tier == "medium":
        match["candidates"] = []
    item = {"row_id": row_id, "mode": "propose", "action": "proposed", "match": match}
    if hs_object_id is not None:
        item["hs_object_id"] = hs_object_id
    return item


def test_chunk_ceilings_real_match_key_return_flows_into_match_batch_and_classify_matches(
        fake_config, stub_post_transport_factory):
    """Closes the last GRANDFATHERED_UNCOVERED entry (enrich-before-ingest,
    (config_gate.load_config, chunking.plan_chunks, chunking.chunk_ceiling,
    preingest.match_batch, preingest.classify_matches)).

    ADDITIVE, placed immediately after the isolated-ceiling unit test above (left
    byte-identical) -- the registry's own reason names that test as insufficient BY
    ITSELF, since nothing there feeds `plan_chunks`/`match_batch`/`classify_matches`.
    `test_run_manifest.py::test_a_resume_re_requests_only_rows_that_still_needed_work`
    is the near-miss the registry also names: it passes `plan_chunks(spec, ceiling=5)`
    a LITERAL `5`, never `chunk_ceiling`'s real return -- also left untouched.
    """
    real_match_ceiling = json.loads(CONFIG_EXAMPLE.read_text())["max_rows_per_match_request"]
    cfg = {**fake_config, "max_rows_per_match_request": real_match_ceiling}

    row_spec = preingest.build_rows_spec([
        {"firstname": "First0", "lastname": "Doe0", "company": "Acme0"},
        {"firstname": "First1", "lastname": "Doe1", "company": "Acme1"},
        {"firstname": "First2", "lastname": "Doe2", "company": "Acme2"},
    ])

    ceiling = chunking.chunk_ceiling(cfg, key="max_rows_per_match_request")
    assert ceiling == real_match_ceiling, (
        "the ceiling fed to plan_chunks below must come from the real config path, "
        "never a hardcoded literal"
    )
    plan = chunking.plan_chunks(row_spec, ceiling)
    assert plan.chunk_count == 1

    row_ids = [row["row_id"] for row in row_spec["rows"]]
    match_transport = stub_post_transport_factory(responses=[[
        _match_item(row_ids[0], "high", hs_object_id="111"),
        _match_item(row_ids[1], "none"),
        _match_item(row_ids[2], "medium"),
    ]])
    outcome = preingest.match_batch(plan, cfg, transport=match_transport)
    classified = preingest.classify_matches(
        row_spec["rows"], outcome.responses, unchecked_row_ids=outcome.unchecked_row_ids)

    assert {entry["row_id"] for entry in classified["auto_matched"]} == {row_ids[0]}
    assert {entry["row_id"] for entry in classified["unmatched"]} == {row_ids[1]}
    assert {entry["row_id"] for entry in classified["proposed"]} == {row_ids[2]}


def test_chunk_ceiling_with_the_match_key_absent_raises_naming_that_key():
    with pytest.raises(chunking.ChunkPlanError) as excinfo:
        chunking.chunk_ceiling({}, key="max_rows_per_match_request")
    message = str(excinfo.value)
    assert "max_rows_per_match_request" in message
    assert "max_records_per_chunk" not in message


# ----------------------------------------------------------------------------------
# The split itself.
# ----------------------------------------------------------------------------------

def test_a_batch_at_the_limit_is_one_chunk_holding_every_id_in_order():
    plan = chunking.plan_chunks(spec(2), 2)
    assert plan.chunk_count == 1
    assert plan.chunks[0]["record_ids"] == ["1", "2"]


def test_a_batch_below_the_limit_is_one_chunk():
    plan = chunking.plan_chunks(spec(1), 2)
    assert plan.chunk_count == 1
    assert plan.row_counts == (1,)


def test_an_exact_multiple_produces_no_empty_trailing_chunk():
    plan = chunking.plan_chunks(spec(6), 2)
    assert plan.chunk_count == 3
    assert plan.row_counts == (2, 2, 2)
    assert all(chunk["record_ids"] for chunk in plan.chunks)


def test_a_remainder_lands_in_a_final_short_chunk():
    plan = chunking.plan_chunks(spec(7), 3)
    assert plan.row_counts == (3, 3, 1)
    assert plan.chunks[-1]["record_ids"] == ["7"]


def test_the_concatenation_of_every_chunk_is_the_input_sequence_exactly():
    """The assertion that catches an off-by-one a chunk count cannot see."""
    original = ids(23)
    plan = chunking.plan_chunks(
        {"record_ids": original, "object_type": "contacts"}, 4
    )
    flattened = [
        record_id for chunk in plan.chunks for record_id in chunk["record_ids"]
    ]
    assert flattened == original
    assert len(flattened) == len(set(flattened))


def test_every_chunk_carries_the_object_type_forward():
    plan = chunking.plan_chunks(spec(5, object_type="contacts"), 2)
    assert [chunk["object_type"] for chunk in plan.chunks] == ["contacts"] * 3


def test_an_empty_id_collection_raises_rather_than_planning_zero_chunks():
    """A zero-chunk plan renders as 'nothing to do' — an unreadable input must never
    impersonate an empty one."""
    with pytest.raises(chunking.ChunkPlanError):
        chunking.plan_chunks({"record_ids": [], "object_type": "companies"}, 2)


def test_a_spec_that_is_neither_ids_nor_a_list_raises():
    with pytest.raises(chunking.ChunkPlanError):
        chunking.plan_chunks({"object_type": "companies"}, 2)


def test_a_view_spec_is_refused_in_the_recorded_words():
    with pytest.raises(enrichment.ViewNotSupportedError) as excinfo:
        chunking.plan_chunks({"view": "My saved view"}, 2)
    assert str(excinfo.value) == enrichment.VIEW_REFUSAL


# ----------------------------------------------------------------------------------
# The backend-resolved list: one request, an honestly unknown count.
# ----------------------------------------------------------------------------------

def test_a_list_plan_is_one_request_with_an_unknown_record_count():
    plan = chunking.plan_chunks(
        {"list": "New Targets.xlsx", "object_type": "contacts"}, 2
    )
    assert plan.chunk_count == 1
    assert plan.record_count == chunking.UNKNOWN
    assert plan.row_counts == (chunking.UNKNOWN,)


def test_a_list_plans_unknown_count_is_the_word_unknown_not_a_number_or_zero():
    plan = chunking.plan_chunks({"list": "Some list", "object_type": "companies"}, 2)
    assert plan.record_count == "unknown"
    assert not isinstance(plan.record_count, (int, float))


def test_a_list_chunk_is_the_list_spec_verbatim():
    plan = chunking.plan_chunks(
        {"list": "New Targets.xlsx", "object_type": "contacts"}, 2
    )
    assert plan.chunks[0]["list"] == "New Targets.xlsx"
    assert "record_ids" not in plan.chunks[0]


def test_a_list_plan_ignores_the_ceiling_because_the_backend_enforces_its_own():
    """25-03 refuses an oversize list rather than chunking it; the client must not
    build a list paginator (D-15a)."""
    for ceiling in (1, 2, 50):
        plan = chunking.plan_chunks({"list": "L", "object_type": "contacts"}, ceiling)
        assert plan.chunk_count == 1


# ----------------------------------------------------------------------------------
# A rows spec: `plan_chunks` splits `spec["rows"]` the same way it splits
# `spec["record_ids"]` — positional, not a rewrite.
# ----------------------------------------------------------------------------------

def rows(count, start=1):
    return [{"row_id": f"r{n}"} for n in range(start, start + count)]


def test_a_rows_spec_splits_positionally_at_the_ceiling():
    plan = chunking.plan_chunks(
        {"rows": rows(3), "object_type": "contacts"}, 2
    )
    assert plan.row_counts == (2, 1)
    assert plan.record_count == 3
    assert [c["object_type"] for c in plan.chunks] == ["contacts", "contacts"]
    assert all("rows" in c for c in plan.chunks)


def test_a_rows_spec_chunk_never_exceeds_the_ceiling():
    plan = chunking.plan_chunks({"rows": rows(7), "object_type": "contacts"}, 3)
    assert all(len(c["rows"]) <= 3 for c in plan.chunks)
    assert plan.row_counts == (3, 3, 1)


def test_an_empty_rows_list_raises_rather_than_planning_a_chunk():
    with pytest.raises(chunking.ChunkPlanError):
        chunking.plan_chunks({"rows": [], "object_type": "contacts"}, 2)


def test_the_concatenation_of_every_rows_chunk_is_the_input_sequence_exactly():
    original = rows(23)
    plan = chunking.plan_chunks(
        {"rows": original, "object_type": "contacts"}, 4
    )
    flattened = [row for chunk in plan.chunks for row in chunk["rows"]]
    assert flattened == original


def test_a_failed_rows_batch_rebuilds_one_rows_spec_excluding_successful_chunks():
    """Mirrors the record_ids `failed_batch` rebuild exactly, direct on the pure
    function — a rows-shaped chunk concatenation, keeping original order and holding
    no row from a chunk that succeeded."""
    plan = chunking.plan_chunks({"rows": rows(6), "object_type": "contacts"}, 2)
    # Chunks 0 and 2 succeeded; only the middle chunk (r3, r4) failed.
    batch = chunking.failed_batch([plan.chunks[1]])
    assert batch == {
        "rows": [{"row_id": "r3"}, {"row_id": "r4"}],
        "object_type": "contacts",
    }


def test_a_failed_rows_batch_keeps_original_order_across_non_adjacent_chunks():
    plan = chunking.plan_chunks({"rows": rows(6), "object_type": "contacts"}, 2)
    # First and last chunks failed; the middle one succeeded.
    batch = chunking.failed_batch([plan.chunks[0], plan.chunks[2]])
    assert batch["rows"] == [
        {"row_id": "r1"}, {"row_id": "r2"}, {"row_id": "r5"}, {"row_id": "r6"}
    ]


# ----------------------------------------------------------------------------------
# What the preview renders, and what dispatch will send — one object.
# ----------------------------------------------------------------------------------

def test_the_plan_reports_a_chunk_count_and_a_row_count_per_chunk():
    plan = chunking.plan_chunks(spec(5), 2)
    assert plan.chunk_count == len(plan.chunks) == len(plan.row_counts)
    assert plan.row_counts == (2, 2, 1)
    assert plan.record_count == 5


def test_every_chunk_is_a_record_specification_the_envelope_builder_accepts():
    plan = chunking.plan_chunks(spec(3), 2)
    envelopes = [enrichment.build_envelope(c, ["lusha"]) for c in plan.chunks]
    assert [len(e["events"]) for e in envelopes] == [2, 1]
    assert envelopes[0]["events"][0] == {"objectId": "1", "objectType": "companies"}


def test_a_list_chunk_is_accepted_by_the_envelope_builder_as_the_nested_list_shape():
    """D-19: the list envelope is NESTED. A flat shape passes the backend's IF List
    Input gate and is then refused by every request."""
    plan = chunking.plan_chunks(
        {"list": "New Targets.xlsx", "object_type": "contacts"}, 2
    )
    envelope = enrichment.build_envelope(plan.chunks[0], ["lusha"])
    assert envelope["list"] == {"name": "New Targets.xlsx", "objectType": "contacts"}


# ==================================================================================
# Task 2 — sequential dispatch: skip a failure, hand the failures back as a batch.
#
# Two of these carry the weight: a failing MIDDLE chunk must still leave the third
# chunk's transport call on the record (a test that only counts failures passes against
# a dispatcher that aborts), and the failed batch must be asserted to EXCLUDE every id
# from a chunk that succeeded (a count-only assertion passes against a dispatcher that
# hands back the whole batch).
# ==================================================================================

PROVIDERS = ["zoominfo", "lusha"]


def three_chunk_plan():
    return chunking.plan_chunks(spec(6), 2)


def sent_ids(transport):
    return [
        [event["objectId"] for event in call["json"]["events"]]
        for call in transport.calls
    ]


def test_a_disarmed_plan_raises_before_any_chunk_is_sent(
    fake_config, stub_module_transport_factory
):
    transport = stub_module_transport_factory()
    with pytest.raises(NotArmedError):
        chunking.dispatch_plan(
            three_chunk_plan(), PROVIDERS, False, fake_config, transport=transport
        )
    assert transport.calls == []


def test_omitting_the_armed_argument_entirely_is_a_type_error(
    fake_config, stub_module_transport_factory
):
    with pytest.raises(TypeError):
        chunking.dispatch_plan(
            three_chunk_plan(), PROVIDERS, config=fake_config,
            transport=stub_module_transport_factory(),
        )


def test_no_function_in_this_module_gives_armed_a_default():
    """D-18: restrict the walk to functions — `inspect.signature` on a bare Exception
    subclass raises on Python 3.14, which is a defect in the check, not the module."""
    armed_functions = [
        f for _name, f in inspect.getmembers(chunking, inspect.isfunction)
        if inspect.getmodule(f) is chunking
        and "armed" in inspect.signature(f).parameters
    ]
    assert armed_functions
    assert all(
        inspect.signature(f).parameters["armed"].default is inspect.Parameter.empty
        for f in armed_functions
    )


def test_an_armed_three_chunk_plan_sends_three_requests_in_plan_order(
    fake_config, stub_module_transport_factory
):
    transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport
    )
    assert transport.verbs == ["post", "post", "post"]
    assert sent_ids(transport) == [["1", "2"], ["3", "4"], ["5", "6"]]
    assert [r.ok for r in outcome.results] == [True, True, True]


def test_every_request_carries_the_provider_selection_unchanged(
    fake_config, stub_module_transport_factory
):
    transport = stub_module_transport_factory()
    chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport
    )
    assert [call["json"]["providers"] for call in transport.calls] == [PROVIDERS] * 3


def test_a_failing_middle_chunk_does_not_stop_the_final_chunk_being_sent(
    fake_config, stub_module_transport_factory
):
    transport = stub_module_transport_factory(
        [{"ok": True}, (500, {"message": "boom"}), {"ok": True}]
    )
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport
    )
    assert sent_ids(transport) == [["1", "2"], ["3", "4"], ["5", "6"]]
    assert [r.ok for r in outcome.results] == [True, False, True]
    assert "500" in outcome.results[1].reason


# --- Phase 57 Task 1 (D-57-01, REVIEW-57-H2): the pre-send mid-run ceiling stop --------


def test_dispatch_plan_with_no_ceiling_behaves_byte_identically_to_today(
    fake_config, stub_module_transport_factory
):
    """The characterization pin: unchanged baseline, `ceiling_stop` always None."""
    transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport
    )
    assert transport.verbs == ["post", "post", "post"]
    assert outcome.ceiling_stop is None


def test_a_pre_send_ceiling_stops_before_the_breaching_chunk_is_sent(
    fake_config, stub_module_transport_factory
):
    """REVIEW-57-H2: the tally runs BEFORE the send. `three_chunk_plan()` is 3 chunks of
    2 rows each (projection 1+2 per chunk = 9 total); `execution_ceiling=6` is the exact
    projected cost of chunks 0 and 1 (2 chunks + 4 rows), so chunk 2 — which would take
    the running total to 9 — is never built or sent."""
    transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport,
        execution_ceiling=6,
    )
    assert transport.verbs == ["post", "post"]
    assert sent_ids(transport) == [["1", "2"], ["3", "4"]]
    assert outcome.ceiling_stop is not None
    assert outcome.ceiling_stop.chunk_index == 2, (
        "the index of the chunk that was NOT sent, not the last one that was")
    assert outcome.ceiling_stop.unsent_chunks == (three_chunk_plan().chunks[2],)
    assert outcome.ceiling_stop.remainder == {
        "record_ids": ["5", "6"], "object_type": "companies"}
    assert outcome.failed_batch is None, "a budget stop is never a chunk failure"
    assert [r.ok for r in outcome.results] == [True, True]
    assert len(outcome.results) == 2, "no result for a chunk that was never attempted"


def test_a_ceiling_exactly_equal_to_the_full_projection_sends_every_chunk(
    fake_config, stub_module_transport_factory
):
    """Strictly greater, not greater-or-equal: consuming the exact remaining allowance
    is permitted. `three_chunk_plan()`'s full projection is 3 chunks + 6 rows = 9."""
    transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport,
        execution_ceiling=9,
    )
    assert transport.verbs == ["post", "post", "post"]
    assert outcome.ceiling_stop is None


def test_zero_overshoot_across_every_possible_ceiling(
    fake_config, stub_module_transport_factory
):
    """REVIEW-57-H2's own pin: for every ceiling from 1 to the full projection, the
    realized projected spend of what was actually ATTEMPTED never exceeds the ceiling —
    the test that fails if the tally is ever moved back below the send."""
    full_projection = 9
    for ceiling in range(1, full_projection + 1):
        transport = stub_module_transport_factory()
        outcome = chunking.dispatch_plan(
            three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport,
            execution_ceiling=ceiling,
        )
        assert chunking.projected_spend(outcome) <= ceiling, (
            f"ceiling {ceiling}: realized spend {chunking.projected_spend(outcome)} "
            f"exceeded it")


def test_a_backend_resolved_list_plan_has_no_chunk_boundary_to_stop_at(
    fake_config, stub_module_transport_factory
):
    """`plan.row_counts == (chunking.UNKNOWN,)` is always a single chunk by
    construction — the tally is skipped and `ceiling_stop` stays None, documented as
    genuinely unbounded by this mechanism rather than guessed at."""
    plan = chunking.plan_chunks({"list": "some-hubspot-list", "object_type": "companies"}, 2)
    assert plan.row_counts == (chunking.UNKNOWN,)

    transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(
        plan, PROVIDERS, True, fake_config, transport=transport, execution_ceiling=1)

    assert outcome.ceiling_stop is None
    assert transport.verbs == ["post"]


# --- Phase 57 Task 3: the ceiling stop's remainder gets a durable home (D-57-01) -------

def _patch_durable_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(
        durable_paths, "resolve_state_path",
        lambda *a, **k: tmp_path / "dashboard_artifact.json",
    )


def test_a_mid_run_ceiling_stop_writes_the_unsent_record_ids_to_the_remainder_queue(
    fake_config, stub_module_transport_factory, tmp_path, monkeypatch
):
    _patch_durable_dir(monkeypatch, tmp_path)
    transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport,
        execution_ceiling=6, run_id="run-ceiling-ids",
    )
    assert outcome.ceiling_stop is not None

    entries = remainder_queue.load(
        path=remainder_queue.remainder_path("run-ceiling-ids"))
    assert len(entries) == 1
    assert entries[0]["reason"] == remainder_queue.REASON_CEILING_BREACH
    assert entries[0]["spec"] == {"record_ids": ["5", "6"], "object_type": "companies"}


def test_a_mid_run_ceiling_stop_writes_the_unsent_people_to_the_remainder_queue(
    fake_config, stub_module_transport_factory, tmp_path, monkeypatch
):
    """The exact shape the old `failed_batch` lost (REVIEW-57-H4) — a `people` plan
    proves the remainder queue rests on the now-lossless reconstruction."""
    _patch_durable_dir(monkeypatch, tmp_path)
    plan = chunking.plan_chunks({"people": [{"n": i} for i in range(6)]}, 2)
    transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(
        plan, PROVIDERS, True, fake_config, transport=transport,
        execution_ceiling=6, run_id="run-ceiling-people",
    )
    assert outcome.ceiling_stop is not None

    entries = remainder_queue.load(
        path=remainder_queue.remainder_path("run-ceiling-people"))
    assert len(entries) == 1
    assert entries[0]["reason"] == remainder_queue.REASON_CEILING_BREACH
    assert entries[0]["spec"]["people"] == [{"n": 4}, {"n": 5}]


def test_a_dispatch_with_no_ceiling_writes_no_remainder_file(
    fake_config, stub_module_transport_factory, tmp_path, monkeypatch
):
    _patch_durable_dir(monkeypatch, tmp_path)
    chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config,
        transport=stub_module_transport_factory(), run_id="run-no-ceiling",
    )
    assert remainder_queue.load(
        path=remainder_queue.remainder_path("run-no-ceiling")) == []


def test_a_remainder_queue_save_failure_during_a_ceiling_stop_does_not_raise_or_alter_the_outcome(
    fake_config, stub_module_transport_factory, tmp_path, monkeypatch
):
    """D-59-10's degrade-rather-than-halt rule, applied to the remainder queue: a save
    failure never propagates out of `dispatch_plan` and never changes any other field
    of the returned `DispatchOutcome`."""
    _patch_durable_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(remainder_queue, "save", lambda *a, **k: False)

    transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport,
        execution_ceiling=6, run_id="run-save-fails",
    )
    assert outcome.ceiling_stop is not None
    assert outcome.ceiling_stop.chunk_index == 2
    assert outcome.ceiling_stop.remainder == {
        "record_ids": ["5", "6"], "object_type": "companies"}
    assert "remainder queue" in outcome.ceiling_stop.reason.lower()
    assert outcome.failed_batch is None
    assert [r.ok for r in outcome.results] == [True, True]


def test_a_remainder_queue_error_during_a_ceiling_stop_does_not_raise(
    fake_config, stub_module_transport_factory, tmp_path, monkeypatch
):
    """A `RemainderQueueError` (a forbidden-named value — a data defect) must degrade
    the same way an I/O failure does at this call site: the dispatch itself never
    raises, only `CeilingStop.reason` names the miss."""
    _patch_durable_dir(monkeypatch, tmp_path)

    def _boom(*a, **k):
        raise remainder_queue.RemainderQueueError("looks like a grant")

    monkeypatch.setattr(remainder_queue, "build_entry", _boom)

    transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport,
        execution_ceiling=6, run_id="run-build-entry-fails",
    )
    assert outcome.ceiling_stop is not None
    assert "looks like a grant" in outcome.ceiling_stop.reason


def test_a_non_2xx_carrying_a_readable_json_body_is_still_a_failure(
    fake_config, stub_module_transport_factory
):
    """The clean-looking refusal: a 4xx whose body parses fine. Classifying on the
    parsed body alone reports it as a success."""
    transport = stub_module_transport_factory([(401, {"message": "unauthorized"})])
    outcome = chunking.dispatch_plan(
        chunking.plan_chunks(spec(2), 2), PROVIDERS, True, fake_config,
        transport=transport,
    )
    assert outcome.results[0].ok is False
    assert outcome.failed_batch == {"record_ids": ["1", "2"], "object_type": "companies"}


def test_a_transport_timeout_is_recorded_as_a_failed_chunk(
    fake_config, stub_module_transport_factory
):
    """D-11b: a timeout counts as a failure for the skip rule even though the backend
    may still be working. `DEFAULT_TIMEOUT` is 120 s, deliberately above the ~100 s
    Cloudflare ceiling, so a ceiling breach normally arrives as the backend's timeout."""
    transport = stub_module_transport_factory(
        [requests.exceptions.Timeout("read timed out"), {"ok": True}, {"ok": True}]
    )
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport
    )
    assert [r.ok for r in outcome.results] == [False, True, True]
    assert "timeout" in outcome.results[0].reason.lower()
    assert len(transport.calls) == 3


def test_a_timeouts_reason_differs_from_a_status_failures_reason(
    fake_config, stub_module_transport_factory
):
    transport = stub_module_transport_factory(
        [requests.exceptions.Timeout("t"), (503, {"m": "x"}), {"ok": True}]
    )
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport
    )
    assert outcome.results[0].reason != outcome.results[1].reason


def test_an_unreadable_response_body_is_a_failed_chunk_and_the_run_continues(
    fake_config, stub_module_transport_factory
):
    transport = stub_module_transport_factory(
        [(200, ValueError("not json")), {"ok": True}, {"ok": True}]
    )
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport
    )
    assert [r.ok for r in outcome.results] == [False, True, True]
    assert len(transport.calls) == 3


def test_a_run_in_which_every_chunk_fails_still_attempts_every_chunk(
    fake_config, stub_module_transport_factory
):
    transport = stub_module_transport_factory(
        [(500, {"m": 1}), requests.exceptions.Timeout("t"), (502, {"m": 3})]
    )
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport
    )
    assert len(transport.calls) == 3
    assert [r.ok for r in outcome.results] == [False, False, False]
    assert outcome.failed_batch["record_ids"] == ["1", "2", "3", "4", "5", "6"]


def test_a_run_with_no_failures_returns_no_failed_batch(
    fake_config, stub_module_transport_factory
):
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config,
        transport=stub_module_transport_factory(),
    )
    assert outcome.failed_batch is None


def test_the_failed_batch_holds_no_id_from_a_chunk_that_succeeded(
    fake_config, stub_module_transport_factory
):
    """A test that only counts failures passes against a dispatcher that hands back the
    whole batch."""
    transport = stub_module_transport_factory(
        [{"ok": True}, (500, {"m": "x"}), {"ok": True}]
    )
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport
    )
    assert outcome.failed_batch["record_ids"] == ["3", "4"]
    for succeeded in ("1", "2", "5", "6"):
        assert succeeded not in outcome.failed_batch["record_ids"]


def test_the_failed_batch_keeps_the_original_order_across_non_adjacent_chunks(
    fake_config, stub_module_transport_factory
):
    transport = stub_module_transport_factory(
        [(500, {"m": 1}), {"ok": True}, (500, {"m": 3})]
    )
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport
    )
    assert outcome.failed_batch["record_ids"] == ["1", "2", "5", "6"]


def test_the_failed_batch_is_accepted_unmodified_by_the_envelope_builder(
    fake_config, stub_module_transport_factory
):
    """D-13: Phase 26 re-DISPATCHES this object; it does not reconstruct one."""
    transport = stub_module_transport_factory(
        [{"ok": True}, (500, {"m": "x"}), {"ok": True}]
    )
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport
    )
    envelope = enrichment.build_envelope(outcome.failed_batch, PROVIDERS)
    assert envelope == {
        "providers": PROVIDERS,
        "events": [
            {"objectId": "3", "objectType": "companies"},
            {"objectId": "4", "objectType": "companies"},
        ],
    }


def test_the_failed_batch_replans_into_the_same_chunk_shape(
    fake_config, stub_module_transport_factory
):
    """The re-send is a plan of its own, not a special case — so a failed batch bigger
    than the ceiling is chunked again rather than sent whole."""
    transport = stub_module_transport_factory(
        [(500, {"m": 1}), (500, {"m": 2}), {"ok": True}]
    )
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport
    )
    replan = chunking.plan_chunks(outcome.failed_batch, 2)
    assert replan.chunk_count == 2
    assert replan.record_count == 4


def test_a_failed_list_chunk_comes_back_as_the_list_spec_not_as_ids(
    fake_config, stub_module_transport_factory
):
    """A list carries no ids the client knows, so the re-sendable unit is the list
    itself — never a fabricated id set."""
    transport = stub_module_transport_factory([(500, {"m": "x"})])
    plan = chunking.plan_chunks({"list": "New Targets.xlsx", "object_type": "contacts"}, 2)
    outcome = chunking.dispatch_plan(
        plan, PROVIDERS, True, fake_config, transport=transport
    )
    assert outcome.failed_batch == {"list": "New Targets.xlsx", "object_type": "contacts"}
    assert "record_ids" not in outcome.failed_batch


# --- Phase 57 Task 3 (REVIEW-57-H4): `failed_batch` reconstructs all five shapes -------


def test_failed_batch_reconstructs_every_person_across_multiple_chunks():
    """Before this fix, a multi-chunk `people` batch fell through to the `record_ids`
    branch, found nothing, and silently returned `chunks[0]` alone."""
    plan = chunking.plan_chunks({"people": [{"n": i} for i in range(5)]}, 2)
    batch = chunking.failed_batch(list(plan.chunks))
    assert len(batch["people"]) == 5
    assert batch["people"] == [{"n": i} for i in range(5)]
    assert "object_type" not in batch


def test_failed_batch_reconstructs_every_company_across_multiple_chunks():
    plan = chunking.plan_chunks(
        {"companies": [{"domain": f"{i}.example"} for i in range(5)]}, 2)
    batch = chunking.failed_batch(list(plan.chunks))
    assert len(batch["companies"]) == 5
    assert batch["companies"] == [{"domain": f"{i}.example"} for i in range(5)]
    assert "object_type" not in batch


@pytest.mark.parametrize("build_spec,key", [
    (lambda: {"record_ids": ids(5), "object_type": "companies"}, "record_ids"),
    (lambda: {"rows": [{"row_id": str(i)} for i in range(5)], "object_type": "contacts"},
     "rows"),
    (lambda: {"people": [{"n": i} for i in range(5)]}, "people"),
    (lambda: {"companies": [{"domain": f"{i}.example"} for i in range(5)]}, "companies"),
])
def test_failed_batch_round_trips_every_shape_losslessly(build_spec, key):
    """The property both the remainder queue and auto-split rest on: for each of the
    four list-bearing shapes, chunking then re-batching a 5-record spec over a ceiling
    of 2 yields a spec whose record count is 5 and whose records equal the original in
    order."""
    spec_dict = build_spec()
    plan = chunking.plan_chunks(spec_dict, 2)
    batch = chunking.failed_batch(list(plan.chunks))
    assert len(batch[key]) == 5
    assert batch[key] == spec_dict[key]


def test_failed_batch_single_chunk_list_passthrough_is_unchanged():
    plan = chunking.plan_chunks({"list": "New Targets.xlsx", "object_type": "contacts"}, 2)
    batch = chunking.failed_batch(list(plan.chunks))
    assert batch == {"list": "New Targets.xlsx", "object_type": "contacts"}


def test_result_records_report_which_chunk_failed_and_its_size(
    fake_config, stub_module_transport_factory
):
    transport = stub_module_transport_factory(
        [{"ok": True}, (500, {"m": "x"}), {"ok": True}]
    )
    outcome = chunking.dispatch_plan(
        chunking.plan_chunks(spec(5), 2), PROVIDERS, True, fake_config,
        transport=transport,
    )
    assert [r.index for r in outcome.results] == [0, 1, 2]
    assert [r.rows for r in outcome.results] == [2, 2, 1]
    assert outcome.results[1].ok is False


def test_result_records_carry_nothing_from_the_config(
    fake_config, stub_module_transport_factory
):
    """T-25-17: a relayed transport exception's text can echo request headers."""
    transport = stub_module_transport_factory(
        [requests.exceptions.Timeout(
            f"POST {fake_config['n8n_url']} X-Enrichment-Secret: "
            f"{fake_config['webhook_secret']}"
        )]
    )
    outcome = chunking.dispatch_plan(
        chunking.plan_chunks(spec(2), 2), PROVIDERS, True, fake_config,
        transport=transport,
    )
    rendered = repr(outcome.results)
    assert fake_config["webhook_secret"] not in rendered
    assert fake_config["n8n_url"] not in rendered


def test_a_gate_02_person_spec_carries_the_gates_own_message_through_dispatch(
    fake_config, stub_module_transport_factory
):
    """The integration test that would have caught CR-01: GATE-02's own example (a
    named person with no email, no linkedin_url, no lastname+company) driven through
    plan_chunks -> dispatch_plan, not through enrichment.build_envelope directly. A
    unit-only test repeats the exact blind spot that let this ship."""
    plan = chunking.plan_chunks({"people": [{"firstname": "John"}]}, 2)
    transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(
        plan, PROVIDERS, True, fake_config, transport=transport
    )
    assert "LinkedIn profile URL" in outcome.results[0].reason
    assert outcome.results[0].resolvable
    for entry in outcome.results[0].resolvable:
        assert set(entry) >= {"field", "sources", "detail"}


def test_a_gate_02_refusal_never_reaches_the_transport(
    fake_config, stub_module_transport_factory
):
    """The refusal happens before any send. This must not accidentally start proving
    a network round trip."""
    plan = chunking.plan_chunks({"people": [{"firstname": "John"}]}, 2)
    transport = stub_module_transport_factory()
    chunking.dispatch_plan(plan, PROVIDERS, True, fake_config, transport=transport)
    assert transport.calls == []


def test_a_transport_failure_still_carries_an_empty_resolvable_tuple(
    fake_config, stub_module_transport_factory
):
    """A caller must be able to iterate `.resolvable` unconditionally on every
    result — a transport-reason failure carries `()`, never `None`."""
    transport = stub_module_transport_factory([(500, {"message": "boom"})])
    outcome = chunking.dispatch_plan(
        chunking.plan_chunks(spec(2), 2), PROVIDERS, True, fake_config,
        transport=transport,
    )
    assert outcome.results[0].resolvable == ()


def test_a_refused_gate_02_chunk_still_lands_in_failed_batch(
    fake_config, stub_module_transport_factory
):
    """D-13's re-send contract is unchanged by this plan: a spec-refused chunk still
    carries into `outcome.failed_batch`."""
    plan = chunking.plan_chunks({"people": [{"firstname": "John"}]}, 2)
    transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(
        plan, PROVIDERS, True, fake_config, transport=transport
    )
    assert outcome.failed_batch == {"people": [{"firstname": "John"}]}



def test_dispatch_plan_never_writes_into_the_operators_real_durable_directory(
    fake_config, stub_module_transport_factory,
):
    """Regression test for bug_001 (2026-08-29 ultrareview). Deliberately does NOT
    monkeypatch `written_records.written_records_path` itself — every other test in
    this file either predates that concern or patches it individually; this one
    exercises exactly the gap those individual patches left open: a `dispatch_plan`
    caller with no patch of its own, which measurably deposited 413 stray
    `written_records-*.json` files into the operator's real state directory when this
    suite ran (53-WALK-RECORD-2.md FINDING A). Relies solely on conftest.py's
    `no_durable_writes` autouse fixture.
    """
    real_dir = durable_paths.durable_dir()
    before = set(real_dir.glob("written_records-*.json")) if real_dir.exists() else set()

    transport = stub_module_transport_factory()
    chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport
    )

    after = set(real_dir.glob("written_records-*.json")) if real_dir.exists() else set()
    assert after == before, (
        "dispatch_plan wrote into the operator's real durable directory — "
        "no_durable_writes (conftest.py) did not take effect"
    )


# ==================================================================================
# 59-09 gap closure (D-59-10) — a written-records bookkeeping failure never stops the
# dispatch. Two ways the list can go short (a raised WrittenRecordsError, and a falsey
# append_chunk return on an OSError) are guarded in ONE place and reported, never
# silent.
# ==================================================================================

def _poisoned_body():
    """A response item whose free-text `reason` contains a forbidden marker — the
    identical shape `test_written_records.py`'s own
    `test_a_value_naming_a_secret_refuses_rather_than_persisting` proves makes
    `written_records.classify_item` raise `WrittenRecordsError`."""
    return {"action": "write_blocked", "reason": "bad webhook_secret configured"}


def test_a_written_records_bookkeeping_failure_does_not_stop_the_dispatch(
    fake_config, stub_module_transport_factory, tmp_path, monkeypatch
):
    """Test 1 — the integration test that would have caught this gap: the MIDDLE
    chunk's response poisons `written_records.append_chunk` (it raises
    `WrittenRecordsError`), and the LATER chunk must still be sent — proved by the
    stub transport's own call count, not by inspection — and `dispatch_plan` must
    return normally rather than letting the exception escape."""
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)

    transport = stub_module_transport_factory(
        [{"ok": True}, _poisoned_body(), {"ok": True}]
    )
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport,
    )
    assert len(transport.calls) == 3
    assert sent_ids(transport) == [["1", "2"], ["3", "4"], ["5", "6"]]
    assert [r.ok for r in outcome.results] == [True, True, True], (
        "a bookkeeping miss is not a dispatch failure — this chunk's HubSpot write "
        "may already have landed"
    )


def test_the_bookkeeping_failure_is_named_loudly_in_the_dispatch_outcome(
    fake_config, stub_module_transport_factory, tmp_path, monkeypatch
):
    """Test 2 — the new field is non-empty, identifies the failing chunk, and carries
    a reason a human can act on."""
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)

    transport = stub_module_transport_factory(
        [{"ok": True}, _poisoned_body(), {"ok": True}]
    )
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport,
    )
    assert len(outcome.written_records_failures) == 1
    failure = outcome.written_records_failures[0]
    assert failure["chunk_index"] == 1
    assert failure["reason"]


def test_an_io_failure_in_append_chunk_is_caught_by_the_same_guard(
    fake_config, stub_module_transport_factory, tmp_path, monkeypatch
):
    """Test 3 — `append_chunk`'s documented falsey return on an `OSError` is the
    OTHER way the list can go short, and `dispatch_plan` ignored it before this plan.
    Driven directly (not by inducing a real `OSError`) so this test cannot be confused
    with the raised-exception path Tests 1/2 cover — one guard must catch both."""
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)
    real_append_chunk = written_records.append_chunk

    def _flaky_append_chunk(run_id, chunk_index, body, path=None):
        if chunk_index == 1:
            return False
        return real_append_chunk(run_id, chunk_index, body, path=path)

    monkeypatch.setattr(chunking.written_records, "append_chunk", _flaky_append_chunk)

    transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport,
    )
    assert len(transport.calls) == 3
    assert [f["chunk_index"] for f in outcome.written_records_failures] == [1]
    assert "I/O failure" in outcome.written_records_failures[0]["reason"]
    # Chunks 0 and 2 flushed normally through the same guard — only chunk 1 went short.
    assert [e["chunk_index"] for e in written_records.load(path=artifact)] == [0, 2]


def test_a_clean_run_reports_an_empty_written_records_failures_tuple(
    fake_config, stub_module_transport_factory, tmp_path, monkeypatch
):
    """Test 4 — the field is an empty tuple, never `None`, so a caller iterates it
    unconditionally."""
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)

    transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport,
    )
    assert outcome.written_records_failures == ()
    assert outcome.written_records_failures is not None


def test_a_bookkeeping_failure_does_not_flip_the_chunks_result_or_join_failed_batch(
    fake_config, stub_module_transport_factory, tmp_path, monkeypatch
):
    """Test 5 — the chunk whose bookkeeping failed keeps the `ChunkResult` it already
    earned: its HubSpot write may have succeeded, so a bookkeeping miss must not be
    reported as a dispatch failure, and it must not be added to `failed_batch` for
    re-send."""
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)

    transport = stub_module_transport_factory(
        [{"ok": True}, _poisoned_body(), {"ok": True}]
    )
    outcome = chunking.dispatch_plan(
        three_chunk_plan(), PROVIDERS, True, fake_config, transport=transport,
    )
    assert outcome.results[1].ok is True
    assert outcome.failed_batch is None


def test_the_dispatcher_iterates_the_plan_and_never_resplits_it(
    fake_config, stub_module_transport_factory
):
    """T-25-24: the operator approved a specific split. A dispatcher with its own
    splitting path can send a batch nobody saw — so a hand-built plan whose chunks
    exceed any ceiling is still sent exactly as given."""
    plan = chunking.ChunkPlan(
        chunks=({"record_ids": ["7", "8", "9"], "object_type": "companies"},),
        row_counts=(3,),
        record_count=3,
    )
    transport = stub_module_transport_factory()
    chunking.dispatch_plan(plan, PROVIDERS, True, fake_config, transport=transport)
    assert len(transport.calls) == 1
    assert sent_ids(transport) == [["7", "8", "9"]]


# ==================================================================================
# written-records-misses-write (debug session, 2026-08-29): D-59-09 promises ONE
# written-records file per run, but a run is not one transport — enrich-before-ingest
# dispatches through BOTH `chunking.dispatch_plan` (the enrichment lane) and
# `dispatch.dispatch` (the contacts write, scripts/dispatch.py) in the same run. That
# promise only holds if both transports flush under the SAME run_id — this pins the
# contract directly rather than leaving it living only in enrich-before-ingest/SKILL.md's
# prose (D-59-09's own "keep one run's enrichment entries and its write entries in the
# SAME file" requirement).
# ==================================================================================

def _ingest_response_body(hs_object_id="348695309760"):
    """One row in Build Ingest Response's own shape (scripts/build_cloud_workflows.py:
    471-520, repo root) — the contacts webhook's real synchronous body is a JSON array of
    exactly these keys."""
    return [{
        "action": "create", "outcome": "created", "contact_id": hs_object_id,
        "hs_object_id": hs_object_id, "email": "josh@seriesfutsal.com",
        "company_id": "283816805830", "company_match": "domain",
        "association": "associated", "reason": None, "email_status": None,
    }]


def test_enrichment_and_contacts_writes_from_the_same_run_share_one_file(
    fake_config, stub_module_transport_factory, stub_post_transport_factory, tmp_path,
    monkeypatch, sample_csv,
):
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)

    plan = chunking.plan_chunks(spec(2), 10)
    enrich_transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(plan, PROVIDERS, True, fake_config, transport=enrich_transport)

    write_transport = stub_post_transport_factory([_ingest_response_body()])
    dispatch(
        str(sample_csv), True, fake_config, transport=write_transport, run_id=outcome.run_id,
    )

    entries = written_records.load(path=artifact)
    assert len(entries) == 2, (
        "the enrichment lane's chunk and the contacts write must both land in the ONE "
        "file this run's run_id names — a caller that omits run_id= on the second call "
        "silently starts a second file instead"
    )
    assert {e.get("hs_object_id") for e in entries} == {None, "348695309760"}


# ==================================================================================
# 260829-lg3 Task 2: closes GRANDFATHERED_UNCOVERED entries #3 (enrich-before-ingest,
# with merge_enriched) and #7 (enrich-records, no merge_enriched) --  the documented
# waterfall: resolve_providers -> plan_chunks/chunk_ceiling -> authorize_send |
# authorize_ungranted_send -> armed_window -> dispatch_plan [-> merge_enriched].
#
# Arming scaffolding below is duplicated VERBATIM from test_write_grant.py -- sibling
# test modules importing each other is fragile under pytest's default import mode.
# ==================================================================================

WORKFLOW_ID = "wf-enrichment-1"
RECORD_ID = "12345"


# Phase 60 (D-60-01/D-60-05 widening): the fifth constant matches the deployed shape —
# see `test_write_grant.py::_base_workflow`'s identical comment. Omitting it here would
# make every fixture that drives `plan_grant`/guardrail A through this helper read as
# UNREADABLE rather than disarmed.
def _base_workflow(record_writes='"false"', create='"false"', ids='""', domains='""',
                   review_writes='"false"'):
    """Same miniature two-gate shape test_write_grant.py's own helper uses."""
    gate = (f"const ALLOW_HUBSPOT_RECORD_WRITES = {record_writes};\n"
            f"const ALLOW_HUBSPOT_CREATE = {create};\n"
            f"const ALLOW_HUBSPOT_REVIEW_WRITES = {review_writes};\n"
            f"const TEST_RECORD_IDS = {ids};\n"
            f"const TEST_RECORD_DOMAINS = {domains};\n"
            "function _writeSafetyAllows() { return false; }\n")
    return {
        "id": WORKFLOW_ID,
        "name": write_grant.LANES["enrichment"],
        "active": True,
        "settings": {},
        "connections": {},
        "nodes": [
            {"name": "Update Write Gate", "parameters": {"jsCode": gate}},
            {"name": "Create Write Gate", "parameters": {"jsCode": gate}},
            {"name": "Webhook", "parameters": {}},
        ],
    }


def _armed_workflow(ids=f'"{RECORD_ID}"'):
    return _base_workflow(record_writes='"true"', create='"true"', ids=ids)


def _workflow_list():
    """What `resolve_workflow_id` reads: the /api/v1/workflows collection."""
    return {"data": [{"id": WORKFLOW_ID, "name": write_grant.LANES["enrichment"]}]}


def _executions_page():
    """One exhausted executions-list page — `write_grant.allowance_headroom`'s new
    sample (Phase 57), inserted between the lane resolve and guardrail A's own read
    (REVIEW-57-H9's re-sequenced frozen call order)."""
    return {"data": []}


def _arming_sequence():
    """The proven open+arm+disarm sequence
    (test_write_grant.py::test_a_send_arms_under_an_opened_grant_with_no_environment_variable_set),
    duplicated verbatim: lane resolve, the Phase 57 headroom sample, guardrail A's live
    read, the arm, arm verification, then the disarm."""
    return [
        _workflow_list(),
        _executions_page(),
        _base_workflow(),
        _base_workflow(), _base_workflow(), {}, {}, {},
        _base_workflow(record_writes='"true"', ids=f'"{RECORD_ID}"'),
        _armed_workflow(), _armed_workflow(), {}, {}, {}, _base_workflow(),
    ]


@pytest.fixture(autouse=True)
def _clear_workflow_id_cache_between_chunking_tests():
    """`executions_client._workflow_id_cache` is process-lifetime — without this, a
    lane name resolved by one of the two tests below leaks into the other (both use
    the identical "enrichment" lane name), and the second test's `plan_grant` silently
    skips its own workflow-list read, consuming the scripted transport queue one entry
    out of step."""
    executions_client._workflow_id_cache.clear()
    yield
    executions_client._workflow_id_cache.clear()


@pytest.fixture
def granting_config(fake_config):
    """A config whose admin set the write-grant settings key to the JSON boolean true."""
    return {**fake_config, config_gate.WRITE_GRANT_SETTINGS_KEY: True}


def test_the_enrich_before_ingest_waterfall_chains_resolve_providers_through_merge_enriched(
        granting_config, stub_module_transport_factory):
    """Closes (enrich-before-ingest, (config_gate.load_config,
    enrichment.resolve_providers, chunking.plan_chunks, chunking.chunk_ceiling,
    write_grant.authorize_send, write_grant.authorize_ungranted_send,
    n8n_arming.armed_window, chunking.dispatch_plan, preingest.merge_enriched)).
    Uses the grant-present authorize_send branch (Task 1 already covers
    authorize_ungranted_send for this same file's Test 2 below -- deliberate
    diversity, not required by either registry reason individually)."""
    row_spec = preingest.build_rows_spec([
        {"firstname": "First0", "lastname": "Doe0", "company": "Acme0"},
        {"firstname": "First1", "lastname": "Doe1", "company": "Acme1"},
    ])
    cfg = {**granting_config, "max_records_per_chunk": 2}
    providers = enrichment.resolve_providers(None, cfg)
    ceiling = chunking.chunk_ceiling(cfg)
    plan = chunking.plan_chunks(row_spec, ceiling)
    assert plan.chunk_count == 1

    grant_transport = stub_module_transport_factory(_arming_sequence())
    proposal = write_grant.plan_grant(
        granting_config, lanes=["enrichment"], object_type="companies",
        record_ids=[RECORD_ID], record_domains=[], allow_create=False, label="test",
        transport=grant_transport)
    grant = write_grant.open_grant(proposal, "yes", granting_config)
    decision = write_grant.authorize_send(
        grant, lane="enrichment", record_ids=[RECORD_ID], record_domains=[])
    assert decision["armed"] is True

    row_ids = [row["row_id"] for row in row_spec["rows"]]
    scripted_body = [
        {"row_id": row_id, "properties": {"email": f"{row_id}@example.com"}}
        for row_id in row_ids
    ]

    with n8n_arming.armed_window(decision["workflow_id"], [RECORD_ID], [], False,
                                 granting_config, transport=grant_transport,
                                 grant=decision["grant"]) as window:
        dispatch_transport = stub_module_transport_factory([scripted_body])
        outcome = chunking.dispatch_plan(plan, providers, True, cfg,
                                         transport=dispatch_transport)

    assert window.arm_result["outcome"] == n8n_arming.ARMED
    assert window.disarm_result["outcome"] == n8n_arming.DISARMED
    assert len(dispatch_transport.calls) == 1

    flattened = [item for body in outcome.responses
                 for item in (body if isinstance(body, list) else [body])]
    merge_report = preingest.merge_enriched(row_spec["rows"], flattened)

    merged_by_row_id = {row["row_id"]: row for row in merge_report.rows}
    for row_id in row_ids:
        assert merged_by_row_id[row_id]["email"] == f"{row_id}@example.com", (
            "the scripted dispatch_plan response value must flow, unchanged, through "
            "the flatten idiom and into merge_enriched's merged row"
        )


def test_the_enrich_before_ingest_waterfall_submits_async_and_recovers_through_merge_enriched(
        granting_config, stub_module_transport_factory, stub_get_transport_factory):
    """Closes (enrich-before-ingest, (run_state.new_run_id, run_state.start_run,
    config_gate.load_config, enrichment.resolve_providers, chunking.plan_chunks,
    chunking.chunk_ceiling, write_grant.authorize_send, write_grant.authorize_ungranted_send,
    n8n_arming.armed_window, chunking.dispatch_plan, run_state.mark_dispatched,
    watch.recover_async_dispatch, preingest.merge_enriched)) — gap-closure, 2026-08-31,
    operator decision "Option B".

    Drives the REAL documented async sequence end to end with an injected transport at
    every boundary (dispatch's own POST, and the executions-API GETs
    `recover_async_dispatch` reads) — never a mock of `run_state`/`chunking`/`watch`/
    `preingest` themselves. Pins REVIEW-C14: the run's scope is registered
    (`run_state.start_run`, which writes the run's own state file) BEFORE
    `chunking.dispatch_plan` makes its first HTTP call.

    Live differential proof that recovery actually reproduces the synchronous body
    (rather than merely asserting it does, as an injected transport necessarily must):
    `.planning/phases/61-autonomous-batch-runs/61-ASYNC-RECOVERY-VERDICT.json`.
    """
    row_spec = preingest.build_rows_spec([
        {"firstname": "First0", "lastname": "Doe0", "company": "Acme0"},
    ])
    cfg = {**granting_config, "max_records_per_chunk": 2}
    providers = enrichment.resolve_providers(None, cfg)
    ceiling = chunking.chunk_ceiling(cfg)
    plan = chunking.plan_chunks(row_spec, ceiling)
    assert plan.chunk_count == 1
    row_id = row_spec["rows"][0]["row_id"]

    run_id = run_state.new_run_id()
    run_state.start_run(run_id, [row_id])
    assert run_state.run_state_path(run_id).exists(), (
        "REVIEW-C14: the run's own scope must be registered before any HTTP call is made"
    )

    grant_transport = stub_module_transport_factory(_arming_sequence())
    proposal = write_grant.plan_grant(
        granting_config, lanes=["enrichment"], object_type="companies",
        record_ids=[RECORD_ID], record_domains=[], allow_create=False, label="test",
        transport=grant_transport)
    grant = write_grant.open_grant(proposal, "yes", granting_config)
    decision = write_grant.authorize_send(
        grant, lane="enrichment", record_ids=[RECORD_ID], record_domains=[])
    assert decision["armed"] is True

    with n8n_arming.armed_window(decision["workflow_id"], [RECORD_ID], [], False,
                                 granting_config, transport=grant_transport,
                                 grant=decision["grant"]):
        dispatch_transport = stub_module_transport_factory()  # default accepted body
        outcome = chunking.dispatch_plan(plan, providers, True, cfg,
                                         transport=dispatch_transport,
                                         run_id=run_id, async_ack=True)

    assert outcome.run_id == run_id, "dispatch_plan must echo the SAME id, never mint a second one"
    assert dispatch_transport.calls[0]["json"]["async_ack"] is True
    assert dispatch_transport.calls[0]["json"]["run_id"] == run_id

    run_state.mark_dispatched(run_id, [row_id])
    progress = run_state.read_progress(run_id)
    assert progress.state == run_state.OK
    assert progress.total == 1
    assert progress.pending == 0
    assert progress.running == 1, (
        "no row has a run_manifest verdict yet — the async ack returns before the real "
        "work finishes, so the dispatched row reads as running, not done"
    )

    # The settled execution `recover_async_dispatch` must find BY run_id — never by
    # timing. `Build Response`'s own output is byte-identical to what the synchronous
    # webhook body would have carried (proven live, see the verdict file cited above).
    execution = {
        "id": "exec-1", "status": "success",
        "data": {"resultData": {"runData": {
            "Parse HubSpot Event": [{"data": {"main": [[{"json": {"run_id": run_id}}]]}}],
            "Build Response": [{"data": {"main": [[{"json": {
                "row_id": row_id, "action": "proposed", "object_type": "contacts",
                "outcome_contract_version": 1,
                "match": {"tier": "none", "auto": False, "reason": "searched, no hit",
                          "candidates": []},
                "candidate_count": 0, "provider_agreement": {}, "material_conflicts": None,
                "judge_adjudicated_fields": None,
                "properties": {"email": f"{row_id}@example.com"},
            }}]]}}],
        }}},
    }
    get_transport = stub_get_transport_factory([
        {"data": [{"id": "exec-1"}]},  # list_executions
        execution,  # get_execution
    ])
    recovery = watch.recover_async_dispatch(
        cfg, run_id, plan.chunk_count, workflow_id="wf-enrichment-cloud",
        transport=get_transport, now=lambda: 0.0, sleep=lambda seconds: None,
    )
    assert recovery["recovered"] is True
    assert recovery["matched_executions"] == 1
    assert len(get_transport.calls) == 2, (
        "workflow_id was supplied explicitly — resolve_workflow_id must not be called"
    )

    merge_report = preingest.merge_enriched(row_spec["rows"], recovery["responses"])
    merged_by_row_id = {row["row_id"]: row for row in merge_report.rows}
    assert merged_by_row_id[row_id]["email"] == f"{row_id}@example.com", (
        "the value recovered from the settled execution must flow, unchanged, into "
        "merge_enriched's merged row — exactly like the synchronous path does"
    )


def test_the_enrich_records_waterfall_chains_resolve_providers_through_dispatch_plan(
        granting_config, stub_module_transport_factory):
    """Closes (enrich-records, (config_gate.load_config, enrichment.resolve_providers,
    chunking.plan_chunks, chunking.chunk_ceiling, write_grant.authorize_send,
    write_grant.authorize_ungranted_send, n8n_arming.armed_window,
    chunking.dispatch_plan)) -- no merge_enriched in this tuple, since enrich-records
    targets records already in HubSpot, not a pre-ingest CSV. Uses the
    authorize_ungranted_send branch (deliberate diversity from the test above)."""
    record_spec = {"record_ids": ["100", "200"], "object_type": "companies"}
    cfg = {**granting_config, "max_records_per_chunk": 2}
    providers = enrichment.resolve_providers(None, cfg)
    ceiling = chunking.chunk_ceiling(cfg)
    plan = chunking.plan_chunks(record_spec, ceiling)
    assert plan.chunk_count == 1

    ungranted_transport = stub_module_transport_factory(_arming_sequence())
    decision = write_grant.authorize_ungranted_send(
        granting_config, lane="enrichment", object_type="companies",
        record_ids=[RECORD_ID], record_domains=[], allow_create=False,
        label="this send", transport=ungranted_transport)
    assert decision["armed"] is True

    with n8n_arming.armed_window(decision["workflow_id"], [RECORD_ID], [], False,
                                 granting_config, transport=ungranted_transport,
                                 grant=decision["grant"]) as window:
        dispatch_transport = stub_module_transport_factory()
        chunking.dispatch_plan(plan, providers, True, cfg, transport=dispatch_transport)

    assert window.arm_result["outcome"] == n8n_arming.ARMED
    assert window.disarm_result["outcome"] == n8n_arming.DISARMED

    call = dispatch_transport.calls[0]
    assert call["json"]["events"] == [
        {"objectId": "100", "objectType": "companies"},
        {"objectId": "200", "objectType": "companies"},
    ], "plan_chunks's real chunked record_ids must reach the wire"
    assert call["json"]["providers"] == enrichment.FULL_WATERFALL, (
        "resolve_providers's real return -- checked against an expectation independent "
        "of the `providers` variable itself, so a hardcoded literal reaching the wire "
        "would fail this assertion, not merely echo itself back -- must reach the wire"
    )
