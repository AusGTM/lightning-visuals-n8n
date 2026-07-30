"""Tests proving STRUCT-01 stays exactly true in both directions (Task 3):
provenance is visible in the preview and structurally impossible in the dispatch CSV
(24-RESEARCH.md question 6)."""
import csv
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import extraction  # noqa: E402
import preview  # noqa: E402


def _result_with_one_accepted_row():
    return extraction.ExtractionResult(
        accepted=[
            {
                "row": {"email": "a@b.c", "firstname": "Amy"},
                "provenance": {"input": "pasted_text", "locator": "line 1"},
            }
        ],
        rejected=[],
        dropped_keys=[],
        ambiguities=[],
    )


def test_dispatch_csv_header_is_subset_of_canonical_props_with_no_provenance_column(tmp_path):
    result = _result_with_one_accepted_row()
    rows = [record["row"] for record in result.accepted]

    out_path = tmp_path / "dispatch.csv"
    extraction.write_dispatch_csv(rows, out_path)

    with out_path.open(newline="", encoding="utf-8") as f:
        header = set(next(csv.reader(f)))

    assert header <= set(extraction.canonical_props())
    assert "provenance" not in header


def test_build_extracted_preview_surfaces_provenance_for_the_same_record_the_csv_omits_it_from():
    result = _result_with_one_accepted_row()
    preview_data = preview.build_extracted_preview(result)

    assert preview_data["sample_rows"][0]["provenance"]["input"] == "pasted_text"
    assert preview_data["sample_rows"][0]["provenance"]["locator"] == "line 1"


def test_build_extracted_preview_carries_rejected_dropped_keys_and_ambiguities():
    result = extraction.ExtractionResult(
        accepted=[],
        rejected=[{"index": 0, "reason": "no identity present"}],
        dropped_keys=[{"index": 0, "key": "twitter_url"}],
        ambiguities=["ambiguous title casing on row 2"],
    )
    preview_data = preview.build_extracted_preview(result)

    assert preview_data["rejected"] == result.rejected
    assert preview_data["dropped_keys"] == result.dropped_keys
    assert preview_data["ambiguities"] == result.ambiguities


def test_build_extracted_preview_performs_no_network_call_and_writes_no_file(tmp_path):
    before = set(tmp_path.iterdir())
    preview.build_extracted_preview(_result_with_one_accepted_row())
    after = set(tmp_path.iterdir())
    assert before == after  # nothing written; no_network autouse fixture covers the network half


def test_write_dispatch_csv_raises_on_row_with_key_outside_canonical_set(tmp_path):
    rows = [{"email": "a@b.c", "provenance": {"input": "x", "locator": "y"}}]
    out_path = tmp_path / "dispatch.csv"

    with pytest.raises(extraction.ExtractionError):
        extraction.write_dispatch_csv(rows, out_path)
