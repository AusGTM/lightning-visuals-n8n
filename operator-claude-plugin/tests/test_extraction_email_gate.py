"""Tests for the STRUCT-02 email gate (Phase 37 Plan 02): `extraction.hold_emailless`
separates rows that can reach HubSpot from rows that cannot, naming each held row and
why; `extraction.write_dispatch_csv` refuses to write an emailless row at all rather
than writing it with an empty email cell (37-CONTEXT.md §1, §4.1)."""
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import extraction  # noqa: E402


# =====================================================================================
# Task 1: hold_emailless
# =====================================================================================


def test_hold_emailless_splits_email_row_into_sendable_and_emailless_row_into_held():
    sendable, held = extraction.hold_emailless([{"email": "a@b.c"}, {"firstname": "Ben"}])

    assert sendable == [{"email": "a@b.c"}]
    assert len(held) == 1
    assert held[0]["index"] == 1


def test_hold_emailless_holds_whitespace_only_email():
    sendable, held = extraction.hold_emailless([{"email": "   ", "firstname": "Ben"}])

    assert sendable == []
    assert len(held) == 1


def test_hold_emailless_holds_row_with_no_email_key_at_all():
    sendable, held = extraction.hold_emailless([{"firstname": "Ben", "lastname": "Baker", "company": "Widgets Co"}])

    assert sendable == []
    assert len(held) == 1


def test_hold_emailless_of_empty_list_returns_two_empty_lists():
    sendable, held = extraction.hold_emailless([])

    assert sendable == []
    assert held == []


def test_hold_emailless_every_row_appears_in_exactly_one_output_in_order():
    rows = [
        {"email": "a@b.c"},
        {"firstname": "Ben"},
        {"email": "c@d.e"},
        {"email": "   "},
    ]
    sendable, held = extraction.hold_emailless(rows)

    assert len(sendable) + len(held) == len(rows)
    assert sendable == [{"email": "a@b.c"}, {"email": "c@d.e"}]
    assert [entry["index"] for entry in held] == [1, 3]


def test_hold_emailless_held_entry_names_index_row_and_reason():
    row = {"firstname": "Ben", "lastname": "Baker", "company": "Widgets Co"}
    _, held = extraction.hold_emailless([row])

    entry = held[0]
    assert entry["index"] == 0
    assert entry["row"] == row
    assert isinstance(entry["reason"], str) and entry["reason"]


def test_hold_emailless_does_not_mutate_input_rows():
    rows = [{"email": "a@b.c"}, {"firstname": "Ben"}]
    before = [dict(r) for r in rows]

    extraction.hold_emailless(rows)

    assert rows == before


def test_hold_emailless_extraction_identity_rule_is_unchanged():
    # A firstname+lastname+company row is still a valid EXTRACTION row — hold_emailless
    # answers a different (INGEST) question and must not touch has_identity's rule.
    row = {"firstname": "A", "lastname": "B", "company": "C"}
    assert extraction.has_identity(row) is True

    _, held = extraction.hold_emailless([row])
    assert len(held) == 1  # valid to extract, still held from ingest


# =====================================================================================
# Task 2: write_dispatch_csv raises before any file is opened
# =====================================================================================


def test_write_dispatch_csv_raises_extraction_error_on_emailless_row(tmp_path):
    rows = [
        {"email": "a@b.c"},
        {"firstname": "Ben", "lastname": "Baker", "company": "Widgets Co"},
    ]
    out_path = tmp_path / "dispatch.csv"

    with pytest.raises(extraction.ExtractionError):
        extraction.write_dispatch_csv(rows, out_path)


def test_write_dispatch_csv_leaves_no_file_after_an_emailless_refusal(tmp_path):
    rows = [
        {"email": "a@b.c"},
        {"firstname": "Ben", "lastname": "Baker", "company": "Widgets Co"},
    ]
    out_path = tmp_path / "dispatch.csv"

    with pytest.raises(extraction.ExtractionError):
        extraction.write_dispatch_csv(rows, out_path)

    assert out_path.exists() is False


def test_write_dispatch_csv_error_names_row_index_and_points_at_hold_emailless(tmp_path):
    rows = [{"firstname": "Ben", "lastname": "Baker", "company": "Widgets Co"}]
    out_path = tmp_path / "dispatch.csv"

    with pytest.raises(extraction.ExtractionError) as exc_info:
        extraction.write_dispatch_csv(rows, out_path)

    assert exc_info.value.code == "emailless_row_cannot_ingest"
    message = str(exc_info.value)
    assert "Row 0" in message
    assert "hold_emailless" in message


def test_write_dispatch_csv_refuses_a_late_row_and_leaves_no_file(tmp_path):
    # The offending row is last — all rows must be checked before the first byte of the
    # CSV is written, not just the ones seen before a failure partway through.
    rows = [
        {"email": "a@b.c"},
        {"email": "c@d.e"},
        {"firstname": "Ben", "lastname": "Baker", "company": "Widgets Co"},
    ]
    out_path = tmp_path / "dispatch.csv"

    with pytest.raises(extraction.ExtractionError):
        extraction.write_dispatch_csv(rows, out_path)

    assert out_path.exists() is False


def test_write_dispatch_csv_with_every_row_carrying_email_behaves_as_before(tmp_path):
    rows = [{"email": "a@b.c"}, {"email": "c@d.e", "firstname": "Ben"}]
    out_path = tmp_path / "dispatch.csv"

    extraction.write_dispatch_csv(rows, out_path)

    assert out_path.exists() is True


def test_write_dispatch_csv_extra_key_refusal_still_fires_and_leaves_no_file(tmp_path):
    rows = [{"email": "a@b.c", "provenance": {"input": "x", "locator": "y"}}]
    out_path = tmp_path / "dispatch.csv"

    with pytest.raises(extraction.ExtractionError) as exc_info:
        extraction.write_dispatch_csv(rows, out_path)

    assert exc_info.value.code == "non_canonical_key_in_row"
    assert out_path.exists() is False
