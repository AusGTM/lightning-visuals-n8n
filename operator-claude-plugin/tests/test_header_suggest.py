"""Tests for header_suggest.py — Phase 34 Half B: the client suggests a canonical prop
for a header the backend's own alias table doesn't recognise, the operator confirms
per header, and the writer corrects only the header row of the file the client sends.

Direct-import + fixture assertions cover the pure-logic behavior (matching
test_dispatch_multipart.py's convention for modules with no OS-path-resolution
dependency — header_suggest.py is exactly that shape: pure file I/O against an explicit
path, same category as tabular.py). The "no header is rewritten without an explicit
operator confirmation" property (ROADMAP criterion 5, non-negotiable 1) is additionally
proven by driving the CLI as a real subprocess against an isolated plugin root — the
layer the operator reaches.
"""
import csv
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import header_suggest as hs
import preview
import tabular

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _write_csv(path, headers, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def _csv_bytes(headers, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def _run_header_cli(tmp_path, source_bytes, *confirm_pairs):
    """Build an ISOLATED plugin root and run header_suggest.py against it as a real
    subprocess — the layer the operator reaches (non-negotiable 1), never the
    in-process function, for any property about what actually gets written to disk.

    The WHOLE `scripts/` directory is copied, not just header_suggest.py and its direct
    siblings: header_suggest imports preview, which imports preview_enrichment, which
    imports chunking/cost_guard/enrichment — a selective copy would die on ImportError.
    Copying the tree is also what makes SCRATCH_DIR (computed from header_suggest's own
    __file__) resolve INSIDE this throwaway root, so no test ever writes into the real
    plugin's scratch directory.

    Only `column_mapping.yaml` is copied into the isolated `config/` — the plugin's own
    committed mapping, never the operator's real `operator-claude-plugin/config/`
    directory, which in a dev checkout also holds a gitignored `operator.local.json`
    carrying real credentials. Non-negotiable 5 forbids any test from reaching real
    config; a blanket directory copy would violate that by accident.
    """
    root = tmp_path / "plugin"
    shutil.copytree(SCRIPTS_DIR, root / "scripts")
    (root / "config").mkdir(parents=True)
    shutil.copyfile(
        CONFIG_DIR / "column_mapping.yaml", root / "config" / "column_mapping.yaml"
    )

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    source_path = input_dir / "contacts.csv"
    source_path.write_bytes(source_bytes)

    argv = [sys.executable, str(root / "scripts" / "header_suggest.py"), str(source_path)]
    for pair in confirm_pairs:
        argv += ["--confirm", pair]

    proc = subprocess.run(argv, capture_output=True, text=True)
    parsed = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc.returncode, parsed, root, source_path


# --- Task 1: the tracer — Ph. is suggested, confirmed, corrected on disk, and
# re-previews as phone -----------------------------------------------------------------

PHONE_EMAIL_HEADERS = ["Ph.", "Email Address"]
PHONE_EMAIL_ROWS = [
    ["555-0100", "amy@example.com"],
    ["", "ben@example.com"],
    ["555-0102", ""],
    ["555-0103", "cara@example.com"],
]


@pytest.fixture
def phone_email_csv(tmp_path):
    path = tmp_path / "contacts.csv"
    _write_csv(path, PHONE_EMAIL_HEADERS, PHONE_EMAIL_ROWS)
    return path


def test_suggest_headers_maps_exact_alias_and_suggests_the_fuzzy_match(phone_email_csv):
    headers, rows = tabular.read_table(str(phone_email_csv))
    result = hs.suggest_headers(headers, rows)

    assert result["mapped"] == [{"header": "Email Address", "canonical": "email"}]
    assert len(result["suggestions"]) == 1
    suggestion = result["suggestions"][0]
    assert suggestion["header"] == "Ph."
    assert suggestion["suggestion"] == "phone"
    assert suggestion["score"] == 0.5
    assert result["needs_confirmation"] is True


def test_suggestion_carries_up_to_three_non_empty_sample_values(phone_email_csv):
    headers, rows = tabular.read_table(str(phone_email_csv))
    result = hs.suggest_headers(headers, rows)
    suggestion = result["suggestions"][0]
    # Column 0 ("Ph.") has one blank cell among four; only non-empty cells surface,
    # capped at three.
    assert suggestion["sample_values"] == ["555-0100", "555-0102", "555-0103"]


def test_apply_confirmed_corrections_rewrites_only_the_confirmed_header(
    phone_email_csv, tmp_path
):
    scratch = tmp_path / "scratch"
    corrected_path = hs.apply_confirmed_corrections(
        str(phone_email_csv), {"Ph.": "phone"}, scratch_dir=scratch
    )

    corrected = Path(corrected_path)
    assert corrected.parent == scratch
    lines = corrected.read_text().splitlines()
    assert lines[0] == "phone,Email Address"
    # every data row survives byte-for-byte
    assert lines[1:] == phone_email_csv.read_text().splitlines()[1:]


def test_reprepreview_shows_phone_mapped_after_correction_source_bytes_unchanged(
    phone_email_csv, tmp_path
):
    original_bytes = phone_email_csv.read_bytes()
    scratch = tmp_path / "scratch"
    corrected_path = hs.apply_confirmed_corrections(
        str(phone_email_csv), {"Ph.": "phone"}, scratch_dir=scratch
    )

    before = preview.build_preview(str(phone_email_csv))
    ph_label = next(l for l in before["header_labels"] if l["header"] == "Ph.")
    assert ph_label["dropped"] is True

    after = preview.build_preview(corrected_path)
    phone_label = next(l for l in after["header_labels"] if l["header"] == "phone")
    assert phone_label["canonical"] == "phone"
    assert phone_label["dropped"] is False

    # the source file itself was never touched
    assert phone_email_csv.read_bytes() == original_bytes


def test_to_csv_bytes_of_the_corrected_file_carries_the_corrected_header(
    phone_email_csv, tmp_path
):
    """Pitfall 3: to_csv_bytes() for a .csv source returns path.read_bytes() verbatim —
    proving this against the CORRECTED path is what proves dispatch would send the
    corrected header, not the original one."""
    scratch = tmp_path / "scratch"
    corrected_path = hs.apply_confirmed_corrections(
        str(phone_email_csv), {"Ph.": "phone"}, scratch_dir=scratch
    )
    wire_bytes = tabular.to_csv_bytes(corrected_path)
    assert wire_bytes == Path(corrected_path).read_bytes()
    assert wire_bytes.splitlines()[0] == b"phone,Email Address"


def test_suggest_headers_returns_unavailable_when_the_mapping_cannot_be_resolved():
    result = hs.suggest_headers(["Ph.", "Email Address"], mapping_path="/no/such/file.yaml")
    assert result["available"] is False
    assert result["suggestions"] == []
    assert result["mapped"] == []
    assert result["needs_confirmation"] is False


def test_cli_no_confirm_prints_the_suggestion_and_writes_nothing(tmp_path):
    returncode, payload, root, _source = _run_header_cli(
        tmp_path, _csv_bytes(PHONE_EMAIL_HEADERS, PHONE_EMAIL_ROWS)
    )
    assert returncode == 0, payload
    assert payload["ok"] is True
    assert payload["suggest"]["suggestions"][0]["suggestion"] == "phone"
    assert not (root / "scratch").exists() or not list((root / "scratch").glob("*"))


def test_cli_confirm_writes_the_corrected_file_under_the_isolated_scratch_dir(tmp_path):
    returncode, payload, root, source_path = _run_header_cli(
        tmp_path, _csv_bytes(PHONE_EMAIL_HEADERS, PHONE_EMAIL_ROWS), "Ph.=phone"
    )
    assert returncode == 0, payload
    assert payload["ok"] is True
    assert payload["rewritten"] == {"Ph.": "phone"}

    corrected_path = Path(payload["corrected_path"])
    assert corrected_path.parent == root / "scratch"
    assert corrected_path.read_text().splitlines()[0] == "phone,Email Address"
    # the source file the operator gave us is untouched
    assert source_path.read_bytes() == _csv_bytes(PHONE_EMAIL_HEADERS, PHONE_EMAIL_ROWS)


def test_header_suggest_reuses_previews_normalizer_and_never_reparses_the_yaml():
    """Structural check on the module itself: no second normalizer, no second YAML
    read — either would be the hand-maintained-drift class Pitfall 4 describes one
    layer up."""
    source = (SCRIPTS_DIR / "header_suggest.py").read_text()
    assert "preview._normalize_header" in source
    assert "yaml" not in source
    assert "def _normalize" not in source


# --- Task 2: a name column never reaches the matcher; it is routed to the reviewed
# splitter instead (operator decision 2026-08-05, superseding the flat refusal) -------


def test_full_name_is_routed_to_the_splitter_never_to_the_matcher():
    result = hs.suggest_headers(["Full Name"])
    assert result["suggestions"] == []
    assert len(result["splittable"]) == 1
    assert result["needs_confirmation"] is False

    entry = result["splittable"][0]
    assert entry["header"] == "Full Name"
    assert entry["reason"]
    assert "Full Name" in entry["reason"]
    assert "name_split.py" in entry["next_command"]


@pytest.mark.parametrize(
    "header",
    ["Full Name", "FULLNAME", "full_name", "Name", "Contact Name", "Person Name",
     "  FULL   Name "],
)
def test_every_name_shape_and_casing_whitespace_variant_is_routed_to_the_splitter(header):
    result = hs.suggest_headers([header])
    assert result["suggestions"] == []
    assert len(result["splittable"]) == 1


def test_splittable_entry_carries_sample_values_like_every_other_entry():
    result = hs.suggest_headers(
        ["Full Name"], rows=[["Amy Adams"], ["Ben Baker"], ["Cara Cruz"], ["Dan Diaz"]]
    )
    entry = result["splittable"][0]
    assert entry["sample_values"] == ["Amy Adams", "Ben Baker", "Cara Cruz"]


def test_needs_confirmation_is_false_when_the_only_unrecognised_header_is_full_name():
    result = hs.suggest_headers(["Email Address", "Full Name"])
    assert result["needs_confirmation"] is False
    assert result["suggestions"] == []


def test_no_cutoff_can_make_full_name_produce_a_suggestion(monkeypatch):
    """The regression this constant exists to prevent: assert the ORDERING property
    directly, not only its consequence. At SUGGEST_CUTOFF=0.1 — a cutoff at which
    every canonical prop matches everything — Full Name still yields zero suggestions.
    This fails if the pre-check is ever moved after the difflib call."""
    monkeypatch.setattr(hs, "SUGGEST_CUTOFF", 0.1)
    result = hs.suggest_headers(["Full Name"])
    assert result["suggestions"] == []
    assert len(result["splittable"]) == 1


# --- Task 3: nothing is rewritten without a confirmation, and nothing arbitrary can
# be written --------------------------------------------------------------------------

THREE_UNRECOGNISED_HEADERS = ["Ph.", "Org.", "Notes"]
THREE_UNRECOGNISED_ROWS = [
    ["555-0100", "Acme Inc", "vip"],
    ["555-0101", "Widgets Co", ""],
]


def test_cli_with_no_confirm_writes_nothing_for_a_file_with_three_unrecognised_headers(
    tmp_path,
):
    returncode, payload, root, _source = _run_header_cli(
        tmp_path, _csv_bytes(THREE_UNRECOGNISED_HEADERS, THREE_UNRECOGNISED_ROWS)
    )
    assert returncode == 0, payload
    scratch = root / "scratch"
    assert not scratch.exists() or list(scratch.glob("*")) == []


def test_cli_confirm_rewrites_only_the_named_header_org_passes_through_unchanged(
    tmp_path,
):
    returncode, payload, root, source_path = _run_header_cli(
        tmp_path,
        _csv_bytes(THREE_UNRECOGNISED_HEADERS, THREE_UNRECOGNISED_ROWS),
        "Ph.=phone",
    )
    assert returncode == 0, payload
    corrected = Path(payload["corrected_path"])
    header_line = corrected.read_text().splitlines()[0]
    assert header_line == "phone,Org.,Notes"


def test_corrected_data_rows_equal_the_source_rows_cell_for_cell(tmp_path):
    returncode, payload, root, source_path = _run_header_cli(
        tmp_path,
        _csv_bytes(THREE_UNRECOGNISED_HEADERS, THREE_UNRECOGNISED_ROWS),
        "Ph.=phone",
    )
    assert returncode == 0, payload
    corrected = Path(payload["corrected_path"])
    assert (
        corrected.read_text().splitlines()[1:]
        == source_path.read_text().splitlines()[1:]
    )


def test_cli_confirm_to_a_non_canonical_target_is_refused_and_writes_nothing(tmp_path):
    returncode, payload, root, _source = _run_header_cli(
        tmp_path,
        _csv_bytes(THREE_UNRECOGNISED_HEADERS, THREE_UNRECOGNISED_ROWS),
        "Ph.=photo_url",
    )
    assert returncode == 1
    assert payload["ok"] is False
    assert "photo_url" in payload["error"]
    for prop in ("email", "phone", "company"):
        assert prop in payload["error"]  # the accepted props are listed too

    scratch = root / "scratch"
    assert not scratch.exists() or list(scratch.glob("*")) == []


def test_cli_confirm_of_a_name_shaped_header_is_refused_and_writes_nothing(tmp_path):
    headers = ["Full Name", "Email Address"]
    rows = [["Amy Adams", "amy@example.com"]]
    returncode, payload, root, _source = _run_header_cli(
        tmp_path, _csv_bytes(headers, rows), "Full Name=firstname"
    )
    assert returncode == 1
    assert payload["ok"] is False
    assert "Full Name" in payload["error"]

    scratch = root / "scratch"
    assert not scratch.exists() or list(scratch.glob("*")) == []


def test_apply_confirmed_corrections_raises_when_the_mapping_is_unavailable(tmp_path):
    path = tmp_path / "contacts.csv"
    _write_csv(path, ["Ph."], [["555-0100"]])
    with pytest.raises(hs.HeaderSuggestError):
        hs.apply_confirmed_corrections(
            str(path), {"Ph.": "phone"}, mapping_path="/no/such/file.yaml"
        )


def test_apply_confirmed_corrections_raises_for_non_canonical_target_no_write(tmp_path):
    path = tmp_path / "contacts.csv"
    _write_csv(path, ["Ph."], [["555-0100"]])
    scratch = tmp_path / "scratch"
    with pytest.raises(hs.HeaderSuggestError):
        hs.apply_confirmed_corrections(str(path), {"Ph.": "photo_url"}, scratch_dir=scratch)
    assert not scratch.exists()


def test_apply_confirmed_corrections_raises_for_name_shaped_source_header_no_write(
    tmp_path,
):
    path = tmp_path / "contacts.csv"
    _write_csv(path, ["Full Name"], [["Amy Adams"]])
    scratch = tmp_path / "scratch"
    with pytest.raises(hs.HeaderSuggestError):
        hs.apply_confirmed_corrections(str(path), {"Full Name": "firstname"}, scratch_dir=scratch)
    assert not scratch.exists()


def test_git_status_short_shows_no_writes_to_the_real_plugin_scratch_directory():
    """The whole test suite above never writes into the real plugin's scratch/
    directory — every write goes through an isolated root's own scratch_dir. This is
    a structural sanity check, not a substitute for the `git status --short
    operator-claude-plugin/scratch` command the plan's own <verification> runs."""
    real_scratch = SCRIPTS_DIR.parent / "scratch"
    assert not real_scratch.exists() or list(real_scratch.glob("*")) == []
