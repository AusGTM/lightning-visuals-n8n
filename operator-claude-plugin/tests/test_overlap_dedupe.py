"""Tests for extraction.py's overlap dedupe (Task 1): a scrolled screenshot sequence
collapses onto the SAME identity rule STRUCT-02's pre-flight already applies (D-08), and
anything short of an exact identity-key match surfaces as an ambiguity instead of a
silent collapse (D-09) — never a similarity score, an edit distance, or a threshold
(24-RESEARCH.md Pitfall 5)."""
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import extraction  # noqa: E402


def _record(row, provenance):
    return {"row": row, "provenance": provenance}


def _prov(input_name, locator):
    return {"input": input_name, "locator": locator}


def test_two_records_same_email_differing_case_and_whitespace_collapse_to_one_row():
    """The two-screenshot overlap case criterion 4 names: a scrolled sequence reads the
    same person twice, OCR/vision-noisy on case and surrounding whitespace only."""
    artifact = {
        "records": [
            _record(
                {"email": "Amy@Example.com", "firstname": "Amy", "lastname": "Adams", "company": "Acme"},
                _prov("screenshot_1.png", "row 3"),
            ),
            _record(
                {"email": "  amy@example.com  ", "firstname": "Amy", "lastname": "Adams", "company": "Acme"},
                _prov("screenshot_2.png", "row 1"),
            ),
        ]
    }

    result = extraction.validate(artifact)

    assert len(result.accepted) == 1
    assert result.rejected == []


def test_two_records_same_name_and_company_no_email_either_side_collapse_to_one_row():
    artifact = {
        "records": [
            _record(
                {"firstname": "Ben", "lastname": "Baker", "company": "Widgets Co"},
                _prov("pasted_text", "line 5"),
            ),
            _record(
                {"firstname": " ben ", "lastname": "BAKER", "company": "widgets co"},
                _prov("pasted_text", "line 12"),
            ),
        ]
    }

    result = extraction.validate(artifact)

    assert len(result.accepted) == 1


def test_two_records_with_different_emails_do_not_collapse():
    artifact = {
        "records": [
            _record({"email": "a@example.com", "firstname": "Alice"}, _prov("pasted_text", "line 1")),
            _record({"email": "b@example.com", "firstname": "Bob"}, _prov("pasted_text", "line 2")),
        ]
    }

    result = extraction.validate(artifact)

    assert len(result.accepted) == 2


def test_merged_row_provenance_names_both_source_input_screenshots():
    """An operator auditing a merged row must be able to see it came from two captures."""
    artifact = {
        "records": [
            _record(
                {"email": "cara@example.com", "firstname": "Cara"},
                _prov("screenshot_1.png", "row 8"),
            ),
            _record(
                {"email": "CARA@EXAMPLE.COM", "firstname": "Cara"},
                _prov("screenshot_2.png", "row 2"),
            ),
        ]
    }

    result = extraction.validate(artifact)

    assert len(result.accepted) == 1
    merged_provenance = result.accepted[0]["provenance"]
    assert isinstance(merged_provenance, list)
    inputs = {p["input"] for p in merged_provenance}
    assert inputs == {"screenshot_1.png", "screenshot_2.png"}


def test_merge_carries_union_of_non_conflicting_fields_from_both_sides():
    """The surviving row carries the union of the fields the two sides supplied where
    they do not conflict — a field only one side captured is not lost in the merge."""
    artifact = {
        "records": [
            _record(
                {"email": "dee@example.com", "jobtitle": "CEO"},
                _prov("screenshot_1.png", "row 1"),
            ),
            _record(
                {"email": "dee@example.com", "linkedin_url": "https://linkedin.com/in/dee"},
                _prov("screenshot_2.png", "row 4"),
            ),
        ]
    }

    result = extraction.validate(artifact)

    assert len(result.accepted) == 1
    merged_row = result.accepted[0]["row"]
    assert merged_row["jobtitle"] == "CEO"
    assert merged_row["linkedin_url"] == "https://linkedin.com/in/dee"


def test_merge_conflict_on_non_identity_field_drops_value_and_adds_ambiguity():
    """Where two records collapse but disagree on a non-identity field, the value is
    absent from the merged row and the disagreement is reported instead of one source
    winning (never a guess)."""
    artifact = {
        "records": [
            _record(
                {"email": "erin@example.com", "jobtitle": "CEO"},
                _prov("screenshot_1.png", "row 1"),
            ),
            _record(
                {"email": "erin@example.com", "jobtitle": "CTO"},
                _prov("screenshot_2.png", "row 5"),
            ),
        ]
    }

    result = extraction.validate(artifact)

    assert len(result.accepted) == 1
    merged_row = result.accepted[0]["row"]
    assert "jobtitle" not in merged_row

    jobtitle_ambiguities = [a for a in result.ambiguities if a.get("field") == "jobtitle"]
    assert len(jobtitle_ambiguities) == 1
    assert "jobtitle" in jobtitle_ambiguities[0]["reason"]


def test_near_duplicate_one_side_missing_identity_field_kept_both_and_ambiguity_added():
    """Two records, each independently accepted via a DIFFERENT identity group, that
    agree on every field of a group one of them fully carries but is incomplete on the
    other side — the near-duplicate case D-09 describes. Neither is silently absorbed;
    both survive and an ambiguity asks whether they are the same person."""
    artifact = {
        "records": [
            _record(
                {"firstname": "Cara", "lastname": "Chen", "company": "Acme"},
                _prov("screenshot_1.png", "row 2"),
            ),
            _record(
                # Same first/last name, but company is unreadable/absent on this
                # capture — accepted independently via the email group instead.
                {"email": "cara@other.example", "firstname": "Cara", "lastname": "Chen"},
                _prov("screenshot_2.png", "row 9"),
            ),
        ]
    }

    result = extraction.validate(artifact)

    assert len(result.accepted) == 2

    near_dup_ambiguities = [a for a in result.ambiguities if a.get("field") == "company"]
    assert len(near_dup_ambiguities) == 1
    reason = near_dup_ambiguities[0]["reason"]
    assert "company" not in result.accepted[near_dup_ambiguities[0]["record_index"]]["row"]
    assert "same person" in reason


def test_dedupe_over_single_record_batch_returns_it_unchanged_and_reports_no_collapse():
    artifact = {
        "records": [
            _record({"email": "solo@example.com"}, _prov("pasted_text", "line 1")),
        ]
    }

    result = extraction.validate(artifact)

    assert len(result.accepted) == 1
    assert result.accepted[0]["provenance"] == _prov("pasted_text", "line 1")
    assert result.collapses == []
    assert result.ambiguities == []
