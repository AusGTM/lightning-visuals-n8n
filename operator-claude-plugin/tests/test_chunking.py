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
import json
from pathlib import Path

import pytest

import chunking
import enrichment

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
