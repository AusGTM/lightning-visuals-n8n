"""Tests for preview.py — the adaptive, display-only preview (D-07/D-08/D-09/D-10,
PREVIEW-01, PREVIEW-04).

Uses the repo's real config/column_mapping.yaml as the mapping fixture, since D-07
requires the preview to mirror the backend's own alias table, not a hand-rolled one.
"""
import csv
from pathlib import Path

import pytest

from preview import build_preview, label_headers

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REAL_MAPPING_PATH = REPO_ROOT / "config" / "column_mapping.yaml"


def test_label_headers_maps_known_alias_case_insensitively_and_whitespace_collapsed():
    result = label_headers(["Email Address", "  first   NAME "], REAL_MAPPING_PATH)
    assert result["available"] is True
    assert result["labels"][0] == {
        "header": "Email Address",
        "canonical": "email",
        "dropped": False,
    }
    assert result["labels"][1] == {
        "header": "  first   NAME ",
        "canonical": "firstname",
        "dropped": False,
    }


def test_label_headers_reports_unknown_header_as_dropped():
    result = label_headers(["Notes"], REAL_MAPPING_PATH)
    assert result["labels"][0] == {"header": "Notes", "canonical": None, "dropped": True}


def test_build_preview_small_batch_returns_every_row(tmp_path):
    path = tmp_path / "small.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Email Address", "First Name"])
        writer.writerows(
            [
                ["a@example.com", "Ann"],
                ["b@example.com", "Bea"],
                ["c@example.com", "Cid"],
            ]
        )

    preview = build_preview(path, REAL_MAPPING_PATH)

    assert preview["row_count"] == 3
    assert preview["adaptive"] is False
    assert preview["sample_rows"] == [
        ["a@example.com", "Ann"],
        ["b@example.com", "Bea"],
        ["c@example.com", "Cid"],
    ]


def test_build_preview_large_batch_returns_leading_10_trailing_3_and_fill_rates(sample_csv):
    preview = build_preview(sample_csv, REAL_MAPPING_PATH)

    assert preview["row_count"] == 25
    assert preview["adaptive"] is True
    assert len(preview["sample_rows"]["leading"]) == 10
    assert len(preview["sample_rows"]["trailing"]) == 3
    assert preview["sample_rows"]["leading"][0][0] == "person0@example.com"
    assert preview["sample_rows"]["trailing"][-1][0] == "person24@example.com"

    # fill rate per source column, including the dropped one ("Notes")
    assert set(preview["fill_rates"]) == {"Email Address", "First Name", "Mobile", "Notes"}
    assert all(rate == 1.0 for rate in preview["fill_rates"].values())


def test_build_preview_reports_dropped_headers_and_unmapped_canonical_props(sample_csv):
    preview = build_preview(sample_csv, REAL_MAPPING_PATH)

    labels_by_header = {row["header"]: row for row in preview["header_labels"]}
    assert labels_by_header["Notes"]["dropped"] is True
    assert labels_by_header["Notes"]["canonical"] is None
    assert labels_by_header["Email Address"]["canonical"] == "email"
    assert labels_by_header["Mobile"]["canonical"] == "phone"

    # no header in the fixture maps to these canonical props
    assert set(preview["unmapped_canonical_props"]) >= {
        "company",
        "jobtitle",
        "lastname",
        "linkedin_url",
    }


def test_build_preview_with_mapping_absent_still_returns_headers_rows_and_counts(sample_csv):
    missing_path = Path("/nonexistent/column_mapping.yaml")
    preview = build_preview(sample_csv, missing_path)

    assert preview["mapping_available"] is False
    assert preview["row_count"] == 25
    assert preview["headers"] == ["Email Address", "First Name", "Mobile", "Notes"]
    assert all(row["canonical"] is None and row["dropped"] is None for row in preview["header_labels"])


def test_build_preview_mutates_nothing_source_bytes_identical(sample_csv):
    before = sample_csv.read_bytes()

    build_preview(sample_csv, REAL_MAPPING_PATH)

    after = sample_csv.read_bytes()
    assert before == after


def test_build_preview_performs_no_network_call(sample_csv):
    # The autouse no_network fixture in conftest.py would raise if this reached
    # requests.post/request/Session.request — reaching the assertion below proves it
    # didn't.
    preview = build_preview(sample_csv, REAL_MAPPING_PATH)
    assert preview["row_count"] == 25


# =====================================================================================
# Phase 34-03 Task 3 — the corrected path is what is PREVIEWED and what is SENT.
#
# Every assertion below is on the RECORDED MULTIPART BODY, never on the path argument.
# That is the entire content of 34-RESEARCH.md Pitfall 3: `to_csv_bytes` re-reads raw
# bytes from whatever path it is handed rather than re-serializing anything `read_table`
# returned, so the path and the bytes can silently disagree. A test that checked which
# path was passed would pass against the exact bug this pins. Do not simplify these into
# a path comparison.
# =====================================================================================
from header_suggest import apply_confirmed_corrections  # noqa: E402
import tabular  # noqa: E402
from dispatch import dispatch  # noqa: E402


@pytest.fixture
def unmapped_header_csv(tmp_path):
    """A CSV carrying one header the alias table does not know, so the before/after label
    flip is visible in the test source rather than inferred."""
    path = tmp_path / "unmapped.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Email Address", "Ph."])
        writer.writerows([["a@example.com", "03 9012 3344"], ["b@example.com", "0400 555 010"]])
    return path


def _corrected(source, tmp_path):
    return Path(
        apply_confirmed_corrections(
            source, {"Ph.": "phone"}, scratch_dir=tmp_path / "scratch",
            mapping_path=REAL_MAPPING_PATH,
        )
    )


def test_re_preview_flips_the_confirmed_header_from_dropped_to_mapped(
    unmapped_header_csv, tmp_path
):
    before = build_preview(unmapped_header_csv, REAL_MAPPING_PATH)["header_labels"]
    assert {"header": "Ph.", "canonical": None, "dropped": True} in before

    after = build_preview(_corrected(unmapped_header_csv, tmp_path), REAL_MAPPING_PATH)
    assert {"header": "phone", "canonical": "phone", "dropped": False} in after["header_labels"]


def test_correcting_produces_a_second_file_it_does_not_mutate_the_first(
    unmapped_header_csv, tmp_path
):
    corrected = _corrected(unmapped_header_csv, tmp_path)
    assert tabular.to_csv_bytes(corrected) == corrected.read_bytes()
    assert b"phone" in tabular.to_csv_bytes(corrected)
    assert b"Ph." in tabular.to_csv_bytes(unmapped_header_csv)


def test_dispatching_the_corrected_path_puts_the_corrected_header_on_the_wire(
    unmapped_header_csv, tmp_path, fake_config, stub_transport
):
    corrected = _corrected(unmapped_header_csv, tmp_path)

    dispatch(corrected, True, fake_config, transport=stub_transport)
    sent = stub_transport.calls[0]["files"]["data"][1]
    assert sent.splitlines()[0] == b"Email Address,phone"

    dispatch(unmapped_header_csv, True, fake_config, transport=stub_transport)
    sent_original = stub_transport.calls[1]["files"]["data"][1]
    assert sent_original.splitlines()[0] == b"Email Address,Ph."


def test_an_xlsx_source_corrects_to_a_csv_copy_and_that_copy_is_what_is_sent(
    tmp_path, fake_config, stub_transport
):
    import openpyxl

    source = tmp_path / "contacts.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Email Address", "Ph."])
    ws.append(["a@example.com", "03 9012 3344"])
    wb.save(source)

    corrected = _corrected(source, tmp_path)
    assert corrected.suffix == ".csv"

    dispatch(corrected, True, fake_config, transport=stub_transport)
    assert stub_transport.calls[0]["files"]["data"][1] == corrected.read_bytes()
