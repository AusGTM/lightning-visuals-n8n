"""Tests for csv_dedupe.py — the plugin pre-flight collapse for within-batch duplicate
CSV rows (D-73-03/D-73-04, F-A5).

The property under test is NOT similarity or fuzzy matching — this codebase has none,
deliberately (24-RESEARCH.md Pitfall 5) — it is exact, casefolded, trimmed identity-group
matching, reusing `extraction.py`'s own clustering primitives. The resolution differs
from `extraction.dedupe()` on purpose (D-73-04): the FIRST occurrence wins byte-for-byte,
with no field merge, and the loser is reported with the outcome `duplicate_in_csv` naming
the winner's row number rather than the two being folded into one merged row.

Row numbers are spreadsheet rows (header = row 1, first data row = row 2) — see
csv_dedupe.py's own module docstring for why this deliberately differs by one from
SESSION-2026-09-15.md's own "rows 37/38 = row 3" prose, which counts data rows only.
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

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH, scratch_dir=tmp_path / "scratch")

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

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH, scratch_dir=tmp_path / "scratch")

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

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH, scratch_dir=tmp_path / "scratch")

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

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH, scratch_dir=tmp_path / "scratch")

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

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH, scratch_dir=tmp_path / "scratch")

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

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH, scratch_dir=tmp_path / "scratch")

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


# ========================================================================================
# Task 2 — preview surfacing (preview.py), the corrected file is what is SENT, the batch
# is never refused, and the D-73-21 scope guard (enrich-before-ingest untouched).
# ========================================================================================
import preingest  # noqa: E402
from dispatch import dispatch  # noqa: E402
from preview import build_preview, collapse_block  # noqa: E402


def test_collapse_block_always_returns_the_same_shape():
    assert collapse_block(None) == {"count": 0, "rows": []}
    assert collapse_block([]) == {"count": 0, "rows": []}
    entry = {"row": 3, "duplicate_of": 2, "identity_key": "email", "outcome": "duplicate_in_csv"}
    assert collapse_block([entry]) == {"count": 1, "rows": [entry]}


def test_build_preview_surfaces_the_collapse_and_the_pre_collapse_row_count(tmp_path):
    path = tmp_path / "contacts.csv"
    _write_csv(path, HEADERS, [
        _row("priya@example.com", "Priya", "Whitcombe", "Turf Club", "", "kept"),
    ])
    collapsed = [
        {"row": 37, "duplicate_of": 3, "identity_key": "email", "outcome": "duplicate_in_csv"},
        {"row": 38, "duplicate_of": 3, "identity_key": "email", "outcome": "duplicate_in_csv"},
    ]

    preview = build_preview(path, REAL_MAPPING_PATH, collapsed=collapsed)

    assert preview["row_count"] == 1
    assert preview["pre_collapse_row_count"] == 3
    assert preview["collapsed_rows"] == {"count": 2, "rows": collapsed}


def test_build_preview_with_no_collapse_reports_zero_not_a_missing_key(tmp_path):
    path = tmp_path / "contacts.csv"
    _write_csv(path, HEADERS, [_row("a@example.com", "Ann", "Adams", "Co A", "", "")])

    preview = build_preview(path, REAL_MAPPING_PATH)

    assert preview["collapsed_rows"] == {"count": 0, "rows": []}
    assert preview["pre_collapse_row_count"] == preview["row_count"]


def test_apply_dedupe_never_raises_and_keeps_exactly_the_winners(tmp_path):
    # D-73-04: the batch is never refused over a duplicate.
    path = tmp_path / "contacts.csv"
    _write_csv(path, HEADERS, [
        _row("priya@example.com", "Priya", "Whitcombe", "Turf Club", "", "row 3"),
        _row("PRIYA@EXAMPLE.COM", "PRIYA", "WHITCOMBE", "Turf Club", "", "row 37"),
        _row("Priya@Example.com", "priya", "whitcombe", "turf club", "", "row 38"),
    ])

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH, scratch_dir=tmp_path / "scratch")

    assert result["kept_count"] == 1


def test_only_the_deduped_file_reaches_the_wire(
    tmp_path, fake_config, stub_transport, dispatch_no_recovery_kwargs
):
    # Mirrors test_preview_rendering.py's Phase 34-03 pattern: assert on the recorded
    # multipart BODY BYTES, never on which path was passed (34-RESEARCH.md Pitfall 3).
    path = tmp_path / "contacts.csv"
    _write_csv(path, HEADERS, [
        _row("priya@example.com", "Priya", "Whitcombe", "Turf Club", "", "Media Manager"),
        _row("PRIYA@EXAMPLE.COM", "PRIYA", "WHITCOMBE", "Turf Club", "", "Head of Broadcast"),
    ])

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH, scratch_dir=tmp_path / "scratch")

    dispatch(result["deduped_path"], True, fake_config, transport=stub_transport,
              **dispatch_no_recovery_kwargs)
    sent = stub_transport.calls[0]["files"]["data"][1]
    assert b"Head of Broadcast" not in sent
    assert b"Media Manager" in sent
    assert sent.count(b"priya@example.com") + sent.count(b"PRIYA@EXAMPLE.COM") == 1


def test_enrich_before_ingest_row_id_minting_is_unaffected_by_a_duplicate_csv(tmp_path):
    # D-73-21: the collapse applies to the plain contact-upload lane only.
    path = tmp_path / "contacts.csv"
    _write_csv(path, HEADERS, [
        _row("priya@example.com", "Priya", "Whitcombe", "Turf Club", "", "row 3"),
        _row("PRIYA@EXAMPLE.COM", "PRIYA", "WHITCOMBE", "Turf Club", "", "row 37"),
    ])

    built = preingest.rows_from_table(path, mapping_path=REAL_MAPPING_PATH)
    spec = preingest.build_rows_spec(built["rows"])

    assert len(spec["rows"]) == 2
    assert [r["row_id"] for r in spec["rows"]] == ["row-1", "row-2"]


def test_preingest_never_imports_csv_dedupe():
    src = inspect.getsource(preingest)
    assert "csv_dedupe" not in src


# ========================================================================================
# Phase 74 Plan 03 Task 1 — WR-11 (short/long rows don't lose trailing identity fields to
# a zip that stops at the shorter sequence) and WR-12 (output/report paths derive from the
# input's full resolved path, so they land beside the input rather than in a fixed
# scratch dir keyed on the bare stem).
# ========================================================================================


def test_canonical_rows_pads_a_row_shorter_than_the_header_with_empty_trailing_columns():
    # HEADERS has 6 columns; this row supplies only the first 4 (Email/First/Last/
    # Company) — an exporter that omits trailing empty cells would produce exactly this
    # shape. The old zip-based pairing drops "LinkedIn"/"Job Title" from the dict
    # entirely instead of keying them to "".
    headers = HEADERS
    rows = [["a@example.com", "Ann", "Adams", "Co A"]]

    canonical = csv_dedupe._canonical_rows(headers, rows, mapping_path=REAL_MAPPING_PATH)

    assert canonical[0]["email"] == "a@example.com"
    assert canonical[0]["company"] == "Co A"
    assert canonical[0]["linkedin_url"] == ""
    assert canonical[0]["jobtitle"] == ""


def test_canonical_rows_ignores_overflow_fields_beyond_the_header_without_raising():
    headers = HEADERS
    rows = [["a@example.com", "Ann", "Adams", "Co A", "https://linkedin.com/x", "Manager",
              "an extra column the header never named"]]

    canonical = csv_dedupe._canonical_rows(headers, rows, mapping_path=REAL_MAPPING_PATH)

    assert canonical[0]["jobtitle"] == "Manager"  # not folded together with the overflow
    assert "an extra column the header never named" not in canonical[0].values()


def test_a_short_row_still_clusters_and_survives_dedupe_end_to_end(tmp_path):
    # Both rows are short by one trailing (empty) column; the surviving row's own
    # content must still round-trip through the deduped output untouched.
    path = tmp_path / "contacts.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(HEADERS)
        writer.writerow(["priya@example.com", "Priya", "Whitcombe", "Turf Club", ""])
        writer.writerow(["PRIYA@EXAMPLE.COM", "PRIYA", "WHITCOMBE", "Turf Club", ""])

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH, scratch_dir=tmp_path / "scratch")

    assert result["kept_count"] == 1
    with Path(result["deduped_path"]).open(newline="", encoding="utf-8") as f:
        out = list(csv.reader(f))
    assert out[1][:4] == ["priya@example.com", "Priya", "Whitcombe", "Turf Club"]


def test_apply_dedupe_writes_beside_the_input_by_default(tmp_path):
    input_dir = tmp_path / "somewhere" / "else"
    input_dir.mkdir(parents=True)
    path = input_dir / "contacts.csv"
    _write_csv(path, HEADERS, [
        _row("a@example.com", "Ann", "Adams", "Co A", "", ""),
    ])

    result = apply_dedupe(path, mapping_path=REAL_MAPPING_PATH)

    assert Path(result["deduped_path"]).parent == input_dir
    assert Path(result["collapsed_path"]).parent == input_dir


def test_apply_dedupe_default_output_does_not_collide_across_directories_sharing_a_stem(
        tmp_path):
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    path_a = dir_a / "contacts.csv"
    path_b = dir_b / "contacts.csv"
    _write_csv(path_a, HEADERS, [_row("a@example.com", "Ann", "Adams", "Co A", "", "")])
    _write_csv(path_b, HEADERS, [_row("b@example.com", "Bea", "Bell", "Co B", "", "")])

    result_a = apply_dedupe(path_a, mapping_path=REAL_MAPPING_PATH)
    result_b = apply_dedupe(path_b, mapping_path=REAL_MAPPING_PATH)

    assert Path(result_a["deduped_path"]).read_text(encoding="utf-8") != \
        Path(result_b["deduped_path"]).read_text(encoding="utf-8")
    assert "a@example.com" in Path(result_a["deduped_path"]).read_text(encoding="utf-8")
    assert "b@example.com" in Path(result_b["deduped_path"]).read_text(encoding="utf-8")
