"""Tests for extraction.py's happy path (Task 1, the tracer): an extraction artifact on
disk becomes canonical rows and dispatch-ready CSV bytes, with no Anthropic API call and
no API key anywhere in this module (D-01, D-02)."""
import csv
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import extraction  # noqa: E402

CANONICAL_PROPS = ["company", "email", "firstname", "jobtitle", "lastname", "linkedin_url", "phone"]


def test_canonical_props_returns_exactly_the_seven_alias_targets():
    assert sorted(extraction.canonical_props()) == CANONICAL_PROPS


def test_has_identity_email_present_is_true():
    assert extraction.has_identity({"email": "a@b.c"}) is True


def test_has_identity_email_whitespace_only_is_false():
    assert extraction.has_identity({"email": "   "}) is False


def test_has_identity_name_and_company_group_is_true():
    assert extraction.has_identity({"firstname": "A", "lastname": "B", "company": "C"}) is True


def test_has_identity_name_and_company_group_whitespace_company_is_false():
    assert extraction.has_identity({"firstname": "A", "lastname": "B", "company": "  "}) is False


def test_load_artifact_on_valid_prose_artifact_returns_parsed_mapping(extraction_artifact):
    data = extraction.load_artifact(extraction_artifact)
    assert data["batch_id"] == "batch-1"
    assert data["source"]["kind"] == "prose"
    assert len(data["records"]) == 2


def test_validate_two_record_artifact_all_accepted_zero_rejected_with_provenance(extraction_artifact):
    artifact = extraction.load_artifact(extraction_artifact)
    result = extraction.validate(artifact)

    assert len(result.accepted) == 2
    assert result.rejected == []
    for record in result.accepted:
        assert record["provenance"]["input"]
        assert record["provenance"]["locator"]


def test_write_dispatch_csv_header_matches_canonical_props_and_round_trips(tmp_path, extraction_artifact):
    artifact = extraction.load_artifact(extraction_artifact)
    result = extraction.validate(artifact)
    rows = [record["row"] for record in result.accepted]

    out_path = tmp_path / "dispatch.csv"
    extraction.write_dispatch_csv(rows, out_path)

    with out_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        written_rows = list(reader)

    assert header == sorted(extraction.canonical_props())
    assert len(written_rows) == 2

    email_idx = header.index("email")
    firstname_idx = header.index("firstname")
    company_idx = header.index("company")

    assert written_rows[0][email_idx] == "amy@example.com"
    assert written_rows[1][email_idx] == ""  # Ben's row carries no email — empty cell
    assert written_rows[1][firstname_idx] == "Ben"
    assert written_rows[1][company_idx] == "Widgets Co"
