# tests/test_file_loader.py
#
# Offline proof for Phase 6 file ingestion (parse + map + reject-malformed).
# No network, no API key. Committed csv/json fixtures loaded cwd-relative from
# the repo root; the xlsx fixture is GENERATED in-test (openpyxl embeds a
# nondeterministic timestamp, so no binary is committed).
import pytest

from src.file_loader import load_rows, ingest_file

CSV_PATH = "tests/fixtures/uploads/contacts.csv"
JSON_PATH = "tests/fixtures/uploads/contacts.json"

# The header + three data rows shared by all three formats (2 accepted, 1 reject).
_HEADER = ["Email Address", "First Name", "Last Name", "Job Title", "Phone", "Company", "LinkedIn", "Notes"]
_DATA = [
    ["alice@example.com", "Alice", "Anderson", "Sales Manager", "0412 345 678", "Example Racing League", "https://linkedin.com/in/alice", "note-a"],
    ["", "Bob", "Baker", "Analyst", "0400 111 222", "Example Media Co", "https://linkedin.com/in/bob", "note-b"],
    ["", "", "", "Coordinator", "0400 222 333", "", "", "note-c"],
]

ROW_A = {
    "email": "alice@example.com",
    "firstname": "Alice",
    "lastname": "Anderson",
    "jobtitle": "Sales Manager",
    "phone": "0412 345 678",
    "company": "Example Racing League",
    "linkedin_url": "https://linkedin.com/in/alice",
}
ROW_B = {
    "email": "",
    "firstname": "Bob",
    "lastname": "Baker",
    "jobtitle": "Analyst",
    "phone": "0400 111 222",
    "company": "Example Media Co",
    "linkedin_url": "https://linkedin.com/in/bob",
}


@pytest.fixture
def xlsx_path(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(_HEADER)
    for row in _DATA:
        ws.append(row)  # all string cells; blank cell = ""
    p = tmp_path / "contacts.xlsx"
    wb.save(p)
    wb.close()
    return str(p)


def test_same_rows_across_formats(xlsx_path):
    csv_b = ingest_file(CSV_PATH)
    json_b = ingest_file(JSON_PATH)
    xlsx_b = ingest_file(xlsx_path)

    for batch in (csv_b, json_b, xlsx_b):
        assert batch.rows == [ROW_A, ROW_B]

    # one interface, three formats -> identical accepted rows
    assert csv_b.rows == json_b.rows == xlsx_b.rows

    # unmapped 'Notes' dropped; Phase 6 does NOT normalize (phone stays raw)
    assert "Notes" not in csv_b.rows[0] and "notes" not in csv_b.rows[0]
    assert csv_b.rows[0]["phone"] == "0412 345 678"


def test_required_key_missing_rejected(xlsx_path):
    for path in (CSV_PATH, JSON_PATH, xlsx_path):
        batch = ingest_file(path)
        assert len(batch.rejects) == 1
        rej = batch.rejects[0]
        assert rej.reason == "no identity key"
        assert rej.row_index == 2
        # Row C (Coordinator) is never silently promoted into accepted rows.
        assert all(r.get("jobtitle") != "Coordinator" for r in batch.rows)


def test_bom_parsed():
    # utf-8-sig strips the BOM so the first header alias-matches to 'email'.
    batch = ingest_file(CSV_PATH)
    assert "email" in batch.rows[0]
    assert batch.rows[0]["email"] == "alice@example.com"


def test_unsupported_extension(tmp_path):
    p = tmp_path / "data.txt"
    p.write_text("nope")
    with pytest.raises(ValueError):
        load_rows(str(p))
