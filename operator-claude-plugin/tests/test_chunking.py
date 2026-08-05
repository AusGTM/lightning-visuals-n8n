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
import enrichment
from dispatch import NotArmedError

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
