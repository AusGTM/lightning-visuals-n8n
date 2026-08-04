"""Tests for name_split.py — the reviewed first/last split (operator decision 2026-08-05).

The property under test is NOT "the splitter is clever". It is: every split the operator
cannot verify at a glance is reported as such with its reason named, and the writer cannot
apply a split the operator did not resolve, because it has no splitter of its own.
"""
import csv
from pathlib import Path

import pytest
from name_split import (
    NameSplitError,
    apply_name_split,
    propose_column_split,
    propose_split,
)


# --- the confident cases --------------------------------------------------------------


def test_two_tokens_split_high_confidence():
    p = propose_split("Priya Raman")
    assert (p["firstname"], p["lastname"]) == ("Priya", "Raman")
    assert p["confidence"] == "high"
    assert p["reason"] is None


def test_a_comma_states_the_order_explicitly():
    p = propose_split("Raman, Priya")
    assert (p["firstname"], p["lastname"]) == ("Priya", "Raman")
    assert p["confidence"] == "high"


@pytest.mark.parametrize(
    "raw,first,last",
    [
        ("Jan van der Berg", "Jan", "van der Berg"),
        ("Maria de los Santos", "Maria", "de los Santos"),
        ("Ana da Silva", "Ana", "da Silva"),
        ("Sean O' Brien", "Sean", "O' Brien"),
    ],
)
def test_a_particle_keeps_the_surname_whole(raw, first, last):
    """The failure the original refusal existed to prevent: whitespace-splitting these
    turns one surname into fragments."""
    p = propose_split(raw)
    assert (p["firstname"], p["lastname"]) == (first, last)
    assert p["confidence"] == "high"


# --- the cases that must NOT look confident -------------------------------------------


def test_a_single_word_leaves_the_surname_blank_and_says_why():
    p = propose_split("Cher")
    assert p["firstname"] == "Cher"
    assert p["lastname"] is None
    assert p["confidence"] == "low"
    assert "single word" in p["reason"]


def test_three_parts_without_a_particle_is_flagged_not_guessed():
    """A middle name and a two-word surname are the same shape to a machine."""
    p = propose_split("Maria Jane Santos")
    assert p["confidence"] == "low"
    assert "middle name" in p["reason"]
    # It still proposes something — the operator needs a starting point, not a blank.
    assert (p["firstname"], p["lastname"]) == ("Maria", "Jane Santos")


def test_an_empty_cell_is_reported_not_split():
    p = propose_split("   ")
    assert (p["firstname"], p["lastname"]) == (None, None)
    assert p["confidence"] == "low"
    assert "empty" in p["reason"]


def test_two_commas_cannot_be_read():
    p = propose_split("Raman, Priya, Dr")
    assert (p["firstname"], p["lastname"]) == (None, None)
    assert "more than one comma" in p["reason"]


def test_titles_and_suffixes_are_recorded_not_silently_dropped():
    p = propose_split("Dr. Priya Raman PhD")
    assert (p["firstname"], p["lastname"]) == ("Priya", "Raman")
    assert p["title"] == "Dr."
    assert p["suffix"] == "PhD"


def test_a_title_only_cell_has_no_name_left():
    p = propose_split("Dr.")
    assert (p["firstname"], p["lastname"]) == (None, None)
    assert "nothing left" in p["reason"]


# --- the column summary ----------------------------------------------------------------


def test_column_summary_surfaces_exactly_the_rows_needing_attention():
    result = propose_column_split(["Priya Raman", "Cher", "Maria Jane Santos", "Jan van der Berg"])
    assert result["total"] == 4
    assert result["high_confidence"] == 2
    assert [r["index"] for r in result["needs_attention"]] == [1, 2]


# --- the writer applies what it is TOLD, and nothing else -------------------------------


@pytest.fixture
def names_csv(tmp_path):
    path = tmp_path / "contacts.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Full Name", "Email Address", "Org."])
        w.writerow(["Priya Raman", "p@example.com", "Southern Cross"])
        w.writerow(["Jan van der Berg", "j@example.com", "Meridian"])
    return path


def test_apply_replaces_the_source_column_with_firstname_lastname(names_csv, tmp_path):
    out = Path(apply_name_split(
        names_csv, "Full Name", [("Priya", "Raman"), ("Jan", "van der Berg")],
        scratch_dir=tmp_path / "scratch",
    ))
    rows = list(csv.reader(out.open(newline="")))
    assert rows[0] == ["Email Address", "Org.", "firstname", "lastname"]
    assert rows[1] == ["p@example.com", "Southern Cross", "Priya", "Raman"]
    assert rows[2] == ["j@example.com", "Meridian", "Jan", "van der Berg"]


def test_apply_writes_the_operators_values_not_its_own_proposal(names_csv, tmp_path):
    """The writer has no splitter to fall back on. Hand it a correction the heuristic
    would never produce and it must write exactly that."""
    out = Path(apply_name_split(
        names_csv, "Full Name", [("Priya", "Raman"), ("Jan van", "der Berg")],
        scratch_dir=tmp_path / "scratch",
    ))
    rows = list(csv.reader(out.open(newline="")))
    assert rows[2][-2:] == ["Jan van", "der Berg"]


def test_apply_refuses_a_row_count_mismatch_and_writes_nothing(names_csv, tmp_path):
    scratch = tmp_path / "scratch"
    with pytest.raises(NameSplitError, match="may not line up"):
        apply_name_split(names_csv, "Full Name", [("Priya", "Raman")], scratch_dir=scratch)
    assert not scratch.exists() or not list(scratch.iterdir())


def test_apply_refuses_an_unknown_column(names_csv, tmp_path):
    with pytest.raises(NameSplitError, match="not a column"):
        apply_name_split(names_csv, "Name", [("a", "b"), ("c", "d")],
                         scratch_dir=tmp_path / "scratch")


def test_apply_refuses_to_overwrite_a_populated_firstname_column(tmp_path):
    path = tmp_path / "already.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Full Name", "firstname"])
        w.writerow(["Priya Raman", "Priyanka"])
    with pytest.raises(NameSplitError, match="already has a populated"):
        apply_name_split(path, "Full Name", [("Priya", "Raman")],
                         scratch_dir=tmp_path / "scratch")


def test_the_source_file_is_unchanged(names_csv, tmp_path):
    before = names_csv.read_bytes()
    apply_name_split(names_csv, "Full Name", [("Priya", "Raman"), ("Jan", "van der Berg")],
                     scratch_dir=tmp_path / "scratch")
    assert names_csv.read_bytes() == before
