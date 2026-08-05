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
