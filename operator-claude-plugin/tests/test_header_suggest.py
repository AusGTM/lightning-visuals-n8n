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
