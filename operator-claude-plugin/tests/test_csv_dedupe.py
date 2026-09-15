"""Tests for csv_dedupe.py — the plugin pre-flight collapse for within-batch duplicate
CSV rows (D-73-03/D-73-04, F-A5).

The property under test is NOT similarity or fuzzy matching — this codebase has none,
deliberately (24-RESEARCH.md Pitfall 5) — it is exact, casefolded, trimmed identity-group
matching, reusing `extraction.py`'s own clustering primitives. The resolution differs
from `extraction.dedupe()` on purpose (D-73-04): the FIRST occurrence wins byte-for-byte,
with no field merge, and the loser is reported with the outcome `duplicate_in_csv` naming
the winner's row number rather than the two being folded into one merged row.

Row numbering matches this repo's own stress-session vocabulary (SESSION-2026-09-15.md:
"rows 37/38 = row 3") — the header is row 1, so the first data row is row 2.
"""
import csv
import inspect
from pathlib import Path

import csv_dedupe
from csv_dedupe import apply_dedupe, find_duplicates, propose_dedupe

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REAL_MAPPING_PATH = REPO_ROOT / "config" / "column_mapping.yaml"

HEADERS = ["Email Address", "First Name", "Last Name", "Company", "LinkedIn", "Job Title"]


def _write_csv(path, headers, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    return path


def _row(email="", first="", last="", company="", linkedin="", title=""):
    return [email, first, last, company, linkedin, title]


# --------------------------------------------------------------------------------------
# Behavior 1 + 2: case/whitespace-variant email dup — first wins verbatim, no field merge
# --------------------------------------------------------------------------------------


def test_case_and_whitespace_variant_email_collapses_first_wins_verbatim(tmp_path):
    path = tmp_path / "contacts.csv"
    _write_csv(path, HEADERS, [
        _row("priya@example.com", "Priya", "Whitcombe", "Turf Club", "", "Media Manager"),
        _row(" PRIYA@EXAMPLE.COM ", "PRIYA", "WHITCOMBE", "Turf Club", "", "Head of Broadcast"),
    ])

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH)

    assert result["collapsed"] == [{
        "row": 3,
        "duplicate_of": 2,
        "identity_key": "email",
        "outcome": "duplicate_in_csv",
    }]

    with Path(result["deduped_path"]).open(newline="", encoding="utf-8") as f:
        out = list(csv.reader(f))
    assert out[0] == HEADERS
    assert out[1:] == [_row("priya@example.com", "Priya", "Whitcombe", "Turf Club", "", "Media Manager")]

    # a value unique to the LOSER (its job title) must never appear on the surviving file
    assert "Head of Broadcast" not in Path(result["deduped_path"]).read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------
# Behavior 3: name+company identity group (no email) collapses on casefolded/trimmed match
# --------------------------------------------------------------------------------------


def test_name_and_company_group_collapses_when_email_absent(tmp_path):
    path = tmp_path / "contacts.csv"
    _write_csv(path, HEADERS, [
        _row("", "Colin", "Telfer", "Australian Turf Club", "", "Technical Manager"),
        _row("", "  colin  ", " TELFER ", "australian turf club", "", "Duplicate Row"),
    ])

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH)

    assert len(result["collapsed"]) == 1
    entry = result["collapsed"][0]
    assert entry["row"] == 3
    assert entry["duplicate_of"] == 2
    assert entry["identity_key"] == "firstname+lastname+company"
    assert entry["outcome"] == "duplicate_in_csv"

    with Path(result["deduped_path"]).open(newline="", encoding="utf-8") as f:
        out = list(csv.reader(f))
    assert out[1:] == [_row("", "Colin", "Telfer", "Australian Turf Club", "", "Technical Manager")]


# --------------------------------------------------------------------------------------
# Behavior 4: linkedin_url-only identity group
# --------------------------------------------------------------------------------------


def test_linkedin_url_only_group_collapses(tmp_path):
    path = tmp_path / "contacts.csv"
    li = "https://www.linkedin.com/in/uat-jimmy-busteed"
    _write_csv(path, HEADERS, [
        _row("", "Jimmy", "", "", li, "GM Hospitality"),
        _row("", "", "", "", " " + li.upper() + " ", "second sighting"),
    ])

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH)

    assert len(result["collapsed"]) == 1
    entry = result["collapsed"][0]
    assert entry["identity_key"] == "linkedin_url"
    assert entry["row"] == 3
    assert entry["duplicate_of"] == 2


# --------------------------------------------------------------------------------------
# Behavior 5: distinct people never collapse; identity-less rows pass through untouched
# and are never clustered with each other
# --------------------------------------------------------------------------------------


def test_distinct_people_and_identity_less_rows_are_never_collapsed(tmp_path):
    path = tmp_path / "contacts.csv"
    _write_csv(path, HEADERS, [
        _row("a@example.com", "Ann", "Adams", "Co A", "", ""),
        _row("b@example.com", "Bea", "Bell", "Co B", "", ""),
        _row("", "", "", "", "", "no identity here"),
        _row("", "", "", "", "", "no identity here either"),
    ])

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH)

    assert result["collapsed"] == []
    with Path(result["deduped_path"]).open(newline="", encoding="utf-8") as f:
        out = list(csv.reader(f))
    assert len(out) == 5  # header + all 4 original rows, untouched


# --------------------------------------------------------------------------------------
# Behavior 6: 3+ occurrences collapse to the single first one, every loser names the
# same winner
# --------------------------------------------------------------------------------------


def test_three_occurrences_all_losers_name_the_same_winner(tmp_path):
    path = tmp_path / "contacts.csv"
    _write_csv(path, HEADERS, [
        _row("priya@example.com", "Priya", "Whitcombe", "Turf Club", "", "row 3 in the real batch"),
        _row("", "not a dup", "", "", "", "unrelated row"),
        _row(" PRIYA@EXAMPLE.COM ", "PRIYA", "WHITCOMBE", "Turf Club", "", "row 37"),
        _row("Priya@Example.com", "priya", "whitcombe", "turf club", "", "row 38"),
    ])

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH)

    assert len(result["collapsed"]) == 2
    assert all(entry["duplicate_of"] == 2 for entry in result["collapsed"])
    assert all(entry["outcome"] == "duplicate_in_csv" for entry in result["collapsed"])
    assert {entry["row"] for entry in result["collapsed"]} == {4, 5}

    with Path(result["deduped_path"]).open(newline="", encoding="utf-8") as f:
        out = list(csv.reader(f))
    assert len(out) == 3  # header + winner + the unrelated row


# --------------------------------------------------------------------------------------
# Behavior 7: original column order and surviving rows' original order preserved
# --------------------------------------------------------------------------------------


def test_column_order_and_surviving_row_order_preserved(tmp_path):
    path = tmp_path / "contacts.csv"
    _write_csv(path, HEADERS, [
        _row("z@example.com", "Zed", "Zephyr", "Co Z", "", "first"),
        _row("priya@example.com", "Priya", "Whitcombe", "Turf Club", "", "third kept"),
        _row("PRIYA@EXAMPLE.COM", "PRIYA", "WHITCOMBE", "Turf Club", "", "dup of row above"),
        _row("a@example.com", "Ann", "Adams", "Co A", "", "last kept"),
    ])

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH)

    with Path(result["deduped_path"]).open(newline="", encoding="utf-8") as f:
        out = list(csv.reader(f))
    assert out[0] == HEADERS
    assert [r[5] for r in out[1:]] == ["first", "third kept", "last kept"]


# --------------------------------------------------------------------------------------
# propose mode: reports without writing anything
# --------------------------------------------------------------------------------------


def test_propose_reports_the_same_collapse_without_writing_a_file(tmp_path):
    path = tmp_path / "contacts.csv"
    _write_csv(path, HEADERS, [
        _row("priya@example.com", "Priya", "Whitcombe", "Turf Club", "", "kept"),
        _row("PRIYA@EXAMPLE.COM", "PRIYA", "WHITCOMBE", "Turf Club", "", "dup"),
    ])
    before = path.read_bytes()

    result = propose_dedupe(path, mapping_path=REAL_MAPPING_PATH)

    assert path.read_bytes() == before
    assert len(result["collapsed"]) == 1
    assert result["collapsed"][0]["row"] == 3
    assert result["collapsed"][0]["duplicate_of"] == 2
    assert result["original_count"] == 2
    assert result["kept_count"] == 1


# --------------------------------------------------------------------------------------
# find_duplicates: the shared clustering function apply/propose both call
# --------------------------------------------------------------------------------------


def test_find_duplicates_returns_kept_indices_and_collapsed_entries():
    headers = HEADERS
    rows = [
        _row("a@example.com", "Ann", "Adams", "Co A", "", ""),
        _row("A@EXAMPLE.COM", "ANN", "ADAMS", "CO A", "", "dup"),
        _row("b@example.com", "Bea", "Bell", "Co B", "", ""),
    ]
    kept, collapsed = find_duplicates(headers, rows, mapping_path=REAL_MAPPING_PATH)
    assert kept == [0, 2]
    assert len(collapsed) == 1


# --------------------------------------------------------------------------------------
# Acceptance criteria: the wrong reuse (extraction.dedupe / _merge_cluster) never happens,
# and no similarity/fuzzy comparison is introduced.
# --------------------------------------------------------------------------------------


def test_module_never_calls_extraction_dedupe_or_merge_cluster():
    src = inspect.getsource(csv_dedupe)
    assert "extraction.dedupe(" not in src
    assert "_merge_cluster" not in src


def test_module_introduces_no_similarity_or_fuzzy_matching():
    src = inspect.getsource(csv_dedupe)
    for banned in ("difflib", "SequenceMatcher", "fuzz", "levenshtein", "Levenshtein", ".ratio("):
        assert banned not in src


def test_module_imports_extraction_identity_primitives():
    src = inspect.getsource(csv_dedupe)
    assert "from extraction import" in src or "import extraction" in src
