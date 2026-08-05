"""Tests for `preingest.py`'s post-match lane (Phase 37 Plan 04):

Task 2: `merge_enriched` (join by `row_id`, refuse a duplicate, ignore an unknown).

Task 3: `rows_from_table` (one mapping authority — `preview.label_headers`'s exact
alias lookup — read-only).
"""
from pathlib import Path

import pytest

import extraction
import preingest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = PLUGIN_ROOT / "tests" / "samples"


def _rows(n):
    return preingest.build_rows_spec([
        {"firstname": f"First{i}", "lastname": "Doe", "company": "GCTC"}
        for i in range(n)
    ])["rows"]


def _unanswered_ids(result):
    return {entry["row_id"] for entry in result.unanswered}


def _response(row_id, properties=None):
    return {
        "action": "enriched", "object_type": "contacts", "hs_object_id": None,
        "gap_flag": False, "row_id": row_id, "mode": "enrich", "match": None,
        "properties": properties or {},
    }


# =====================================================================================
# Task 2: merge_enriched
# =====================================================================================

def test_a_response_items_properties_merge_onto_the_matching_row_only():
    rows = _rows(2)
    responses = [_response(rows[0]["row_id"], {"email": "first0@x.com"})]

    result = preingest.merge_enriched(rows, responses)

    merged = {r["row_id"]: r for r in result.rows}
    assert merged[rows[0]["row_id"]]["email"] == "first0@x.com"
    assert "email" not in merged[rows[1]["row_id"]]


def test_shuffled_response_order_still_lands_on_the_right_rows():
    rows = _rows(3)
    responses = [
        _response(rows[2]["row_id"], {"email": "third@x.com"}),
        _response(rows[0]["row_id"], {"email": "first@x.com"}),
        _response(rows[1]["row_id"], {"email": "second@x.com"}),
    ]

    result = preingest.merge_enriched(rows, responses)

    merged = {r["row_id"]: r for r in result.rows}
    assert merged[rows[0]["row_id"]]["email"] == "first@x.com"
    assert merged[rows[1]["row_id"]]["email"] == "second@x.com"
    assert merged[rows[2]["row_id"]]["email"] == "third@x.com"


def test_reversing_response_order_changes_no_rows_merged_values():
    rows = _rows(3)
    responses = [
        _response(rows[0]["row_id"], {"email": "first@x.com"}),
        _response(rows[1]["row_id"], {"email": "second@x.com"}),
        _response(rows[2]["row_id"], {"email": "third@x.com"}),
    ]

    forward = preingest.merge_enriched(rows, responses)
    backward = preingest.merge_enriched(rows, list(reversed(responses)))

    def by_id(result):
        return {r["row_id"]: r for r in result.rows}

    assert by_id(forward) == by_id(backward)


def test_two_response_items_sharing_a_row_id_raises_and_merges_nothing():
    rows = _rows(1)
    responses = [
        _response(rows[0]["row_id"], {"email": "a@x.com"}),
        _response(rows[0]["row_id"], {"email": "b@x.com"}),
    ]
    with pytest.raises(preingest.MergeError):
        preingest.merge_enriched(rows, responses)


def test_a_response_item_matching_no_row_is_reported_and_merged_nowhere():
    rows = _rows(1)
    responses = [
        _response(rows[0]["row_id"], {"email": "a@x.com"}),
        _response("row-does-not-exist", {"email": "b@x.com"}),
    ]
    result = preingest.merge_enriched(rows, responses)

    assert result.unknown_response_row_ids == ("row-does-not-exist",)
    assert len(result.rows) == 1


def test_removing_the_middle_response_item_does_not_shift_the_trailing_rows():
    # A positional zip would let response[2] (meant for rows[2]) silently attach to
    # rows[1] once rows[1]'s own response item is missing — exactly the misalignment
    # the row_id join makes unreachable.
    rows = _rows(3)
    responses = [
        _response(rows[0]["row_id"], {"email": "first@x.com"}),
        _response(rows[2]["row_id"], {"email": "third@x.com"}),
    ]

    result = preingest.merge_enriched(rows, responses)

    merged = {r["row_id"]: r for r in result.rows}
    assert merged[rows[0]["row_id"]]["email"] == "first@x.com"
    assert "email" not in merged[rows[1]["row_id"]]
    assert merged[rows[2]["row_id"]]["email"] == "third@x.com"
    assert rows[1]["row_id"] in _unanswered_ids(result)


def test_a_row_with_no_matching_response_keeps_its_values_and_is_marked_unanswered():
    rows = _rows(2)
    responses = [_response(rows[0]["row_id"], {})]

    result = preingest.merge_enriched(rows, responses)

    assert rows[1]["row_id"] in _unanswered_ids(result)
    assert rows[0]["row_id"] not in _unanswered_ids(result), (
        "a row whose response carried an empty properties map is distinguishable "
        "from a row with no response at all"
    )


def test_an_unanswered_entry_carries_row_id_row_and_the_true_reason():
    rows = _rows(2)
    responses = [_response(rows[0]["row_id"], {})]

    result = preingest.merge_enriched(rows, responses)

    assert len(result.unanswered) == 1
    entry = result.unanswered[0]
    assert entry["row_id"] == rows[1]["row_id"]
    assert entry["row"]["row_id"] == rows[1]["row_id"]
    assert entry["reason"] == preingest.UNANSWERED_REASON


def test_an_unanswered_row_that_carries_a_source_email_is_still_unanswered():
    # An unanswered row is excluded from the sendable set even when it has an email —
    # we do not know what the waterfall would have added, so it is never guessed at.
    rows = _rows(2)
    rows[1]["email"] = "has-email@x.com"
    responses = [_response(rows[0]["row_id"], {})]

    result = preingest.merge_enriched(rows, responses)

    assert rows[1]["row_id"] in _unanswered_ids(result)


def test_a_properties_key_outside_canonical_props_is_dropped_and_reported():
    rows = _rows(1)
    responses = [_response(rows[0]["row_id"], {"lastmodifieddate": "2026-01-01"})]

    result = preingest.merge_enriched(rows, responses)

    merged = result.rows[0]
    assert "lastmodifieddate" not in merged
    assert {"row_id": rows[0]["row_id"], "key": "lastmodifieddate"} in \
        result.dropped_property_keys


def test_a_non_empty_source_value_is_never_overwritten_and_is_reported_as_conflict():
    rows = _rows(1)
    rows[0]["jobtitle"] = "Director"
    responses = [_response(rows[0]["row_id"], {"jobtitle": "Analyst"})]

    result = preingest.merge_enriched(rows, responses)

    assert result.rows[0]["jobtitle"] == "Director"
    assert result.conflicts == (
        {"row_id": rows[0]["row_id"], "field": "jobtitle",
         "kept": "Director", "provider_value": "Analyst"},
    )


def test_an_empty_source_value_is_filled_by_the_response():
    rows = _rows(1)
    rows[0]["jobtitle"] = ""
    responses = [_response(rows[0]["row_id"], {"jobtitle": "Analyst"})]

    result = preingest.merge_enriched(rows, responses)

    assert result.rows[0]["jobtitle"] == "Analyst"
    assert not result.conflicts


def test_merge_enriched_does_not_mutate_input_rows():
    rows = _rows(1)
    snapshot = dict(rows[0])
    responses = [_response(rows[0]["row_id"], {"jobtitle": "Analyst"})]

    preingest.merge_enriched(rows, responses)

    assert rows[0] == snapshot


def test_every_merged_row_key_is_in_canonical_props_or_row_id():
    rows = _rows(1)
    responses = [_response(rows[0]["row_id"], {
        "email": "a@x.com", "phone": "555", "linkedin_url": "https://x.com",
    })]

    result = preingest.merge_enriched(rows, responses)

    allowed = set(extraction.canonical_props()) | {"row_id"}
    for row in result.rows:
        assert set(row) <= allowed


# =====================================================================================
# Task 3: rows_from_table
# =====================================================================================

def test_exact_alias_headers_produce_one_canonical_row_per_data_row_in_file_order():
    result = preingest.rows_from_table(SAMPLES_DIR / "clean-uat-contacts.csv")

    assert len(result["rows"]) == 3
    assert result["rows"][0]["email"] == "alice@example.com"
    assert result["rows"][0]["firstname"] == "Alice"
    assert result["rows"][1]["firstname"] == "Bob"


def test_a_header_the_alias_table_does_not_recognise_is_dropped_and_reported():
    result = preingest.rows_from_table(SAMPLES_DIR / "clean-uat-contacts.csv")

    assert "Notes" in result["dropped_headers"]
    for row in result["rows"]:
        assert "notes" not in row and "Notes" not in row


def test_a_header_merely_similar_to_an_alias_does_not_map():
    # 22-messy-headers.csv's "Ph." is close to "phone" under difflib but is not an
    # exact alias — must be dropped, never fuzzy-mapped.
    result = preingest.rows_from_table(SAMPLES_DIR / "22-messy-headers.csv")

    assert "Ph." in result["dropped_headers"]
    for row in result["rows"]:
        assert "phone" not in row


def test_case_and_whitespace_variants_of_an_alias_still_map():
    # "Org." is an exact alias for "company" (case/whitespace-normalized).
    result = preingest.rows_from_table(SAMPLES_DIR / "22-messy-headers.csv")

    assert result["rows"][0]["company"] == "Southern Cross Racing Club"


def test_the_source_files_bytes_are_identical_before_and_after():
    path = SAMPLES_DIR / "clean-uat-contacts.csv"
    before = path.read_bytes()

    preingest.rows_from_table(path)

    assert path.read_bytes() == before


def test_a_headers_only_file_with_no_data_rows_returns_an_empty_row_list():
    result = preingest.rows_from_table(SAMPLES_DIR / "26-empty.csv")
    assert result["rows"] == []


def test_when_the_mapping_file_cannot_be_resolved_it_refuses():
    with pytest.raises(preingest.RowsFromTableError):
        preingest.rows_from_table(
            SAMPLES_DIR / "clean-uat-contacts.csv",
            mapping_path="/nonexistent/column_mapping.yaml",
        )
