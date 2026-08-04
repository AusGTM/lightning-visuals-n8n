"""The acceptance walk for the exact criterion UAT 2.2 names, against the exact file the
operator handed the plugin — joining Half A's deterministic widening to Half B's
suggest-and-confirm.

UAT 2.2 reads, verbatim: "Give it a CSV or XLSX with messy headers (`E-mail Address`,
`Ph.`) — Reads them without you renaming anything first."

Before this phase, SIX of `22-messy-headers.csv`'s seven headers dropped and every row
would have landed `needs_review` carrying only a job title. `E-mail Address` was not in
the alias table (only `email address` and `e-mail` were), and neither were `org.` or
`linkedin profile`. Half A added those three; Half B suggests `Ph.` and refuses
`Full Name` with its reason.

Uses the repo's REAL `config/column_mapping.yaml`, never a hand-rolled fixture — the same
choice `test_preview_rendering.py` makes, and for the same reason: a test against its own
private table proves nothing about the table the backend actually runs.
"""
import csv
from pathlib import Path

import pytest
from header_suggest import apply_confirmed_corrections, suggest_headers
from preview import build_preview, label_headers
from tabular import read_table

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PLUGIN_ROOT.parent
REAL_MAPPING_PATH = REPO_ROOT / "config" / "column_mapping.yaml"
SAMPLE = Path(__file__).parent / "samples" / "22-messy-headers.csv"

SAMPLE_HEADERS = [
    "Full Name",
    "E-mail Address",
    "Ph.",
    "Org.",
    "Position",
    "LinkedIn Profile",
    "Notes",
]


@pytest.fixture
def sample_suggest():
    headers, rows = read_table(SAMPLE)
    return suggest_headers(headers, rows, mapping_path=REAL_MAPPING_PATH)


def _entry(suggest, bucket, header):
    matches = [e for e in suggest[bucket] if e["header"] == header]
    assert matches, f"{header!r} not in {bucket}: {suggest[bucket]}"
    return matches[0]


# --- Half A: the deterministic half -------------------------------------------------


def test_four_headers_now_map_deterministically_where_two_did_before():
    """The inversion of 34-CONTEXT.md §2's six-of-seven-drop measurement."""
    labels = label_headers(SAMPLE_HEADERS, REAL_MAPPING_PATH)["labels"]
    mapped = {l["header"]: l["canonical"] for l in labels if not l["dropped"]}
    assert mapped == {
        "E-mail Address": "email",
        "Org.": "company",
        "Position": "jobtitle",
        "LinkedIn Profile": "linkedin_url",
    }
    assert [l["header"] for l in labels if l["dropped"]] == ["Full Name", "Ph.", "Notes"]


# --- Half B: suggest, refuse, report -------------------------------------------------


def test_full_name_is_routed_to_the_reviewed_splitter_never_to_the_matcher(sample_suggest):
    """Membership in `splittable` and a reason that names the column — deliberately NOT a
    fuzzy suggestion. No test in this file may assert a `suggestions` entry for Full Name:
    a test of that shape pins exactly the plausible-but-wrong behaviour the ordering
    pre-check exists to forbid.

    Superseded the flat refusal on 2026-08-05 by operator decision — the column is offered
    to the per-row splitter the operator reviews. What did NOT change: it never becomes a
    one-header-to-one-prop guess."""
    entry = _entry(sample_suggest, "splittable", "Full Name")
    assert entry["reason"]
    assert "Full Name" in entry["reason"]
    assert "name_split.py" in entry["next_command"]


def test_the_three_uat_name_shapes_land_in_their_intended_buckets():
    """The sample carries one name per risk shape so a UAT walk demonstrates all three:
    a particle surname that must stay whole, a three-part name that cannot be resolved
    without a person, and a single word that cannot be assigned to either field."""
    from name_split import propose_split

    particle = propose_split("Jan van der Berg")
    assert (particle["firstname"], particle["lastname"]) == ("Jan", "van der Berg")
    assert particle["confidence"] == "high"

    three_part = propose_split("Maria Jane Santos")
    assert three_part["confidence"] == "low"
    assert "middle name" in three_part["reason"]

    single = propose_split("Cher")
    assert single["lastname"] is None
    assert single["confidence"] == "low"


def test_ph_is_suggested_as_phone_and_needs_confirmation(sample_suggest):
    suggestion = _entry(sample_suggest, "suggestions", "Ph.")
    assert suggestion["suggestion"] == "phone"
    assert sample_suggest["needs_confirmation"] is True


def test_the_ph_suggestion_carries_the_columns_own_values(sample_suggest):
    """Measured: "photo" scores 0.6 against "phone" — HIGHER than "ph." does. Without the
    column's own values in front of them, an operator confirming Ph. -> phone is
    rubber-stamping, which is the ceremony 34-CONTEXT.md §3 says this must not be."""
    suggestion = _entry(sample_suggest, "suggestions", "Ph.")
    assert "03 9012 3344" in suggestion["sample_values"]


def test_notes_is_reported_unresolved_not_guessed_at(sample_suggest):
    _entry(sample_suggest, "unresolved", "Notes")
    assert not any(e["header"] == "Notes" for e in sample_suggest["suggestions"])


# --- The correction: header row only -------------------------------------------------


def test_correction_changes_the_header_row_and_nothing_else(tmp_path):
    corrected = Path(
        apply_confirmed_corrections(
            SAMPLE, {"Ph.": "phone"}, scratch_dir=tmp_path, mapping_path=REAL_MAPPING_PATH
        )
    )
    source_lines = SAMPLE.read_text(encoding="utf-8").splitlines()
    corrected_lines = corrected.read_text(encoding="utf-8").splitlines()

    assert corrected_lines[0] == source_lines[0].replace("Ph.", "phone")
    assert list(csv.reader(corrected_lines[1:])) == list(csv.reader(source_lines[1:]))


def test_the_committed_sample_is_byte_identical_after_the_whole_walk(tmp_path):
    before = SAMPLE.read_bytes()
    headers, rows = read_table(SAMPLE)
    suggest_headers(headers, rows, mapping_path=REAL_MAPPING_PATH)
    apply_confirmed_corrections(
        SAMPLE, {"Ph.": "phone"}, scratch_dir=tmp_path, mapping_path=REAL_MAPPING_PATH
    )
    assert SAMPLE.read_bytes() == before


def test_re_preview_of_the_corrected_file_reports_five_of_seven_mapping(tmp_path):
    """The honest remainder, not a claim of total success: Full Name and Notes still
    drop, and the operator sees that before approving."""
    corrected = apply_confirmed_corrections(
        SAMPLE, {"Ph.": "phone"}, scratch_dir=tmp_path, mapping_path=REAL_MAPPING_PATH
    )
    labels = build_preview(corrected, mapping_path=REAL_MAPPING_PATH)["header_labels"]
    assert len([l for l in labels if not l["dropped"]]) == 5
    assert [l["header"] for l in labels if l["dropped"]] == ["Full Name", "Notes"]


# --- The skill text and the CLI are two hand-maintained sides of one contract ---------


def test_skill_md_names_the_script_the_confirm_flag_and_the_corrected_artifact():
    """SKILL.md's instructions and header_suggest.py's argument form have no compiler
    between them — the same drift class `columnMapAliasParity.test.mjs` guards one layer
    down, where two alias tables agree by hand rather than by construction."""
    skill = (PLUGIN_ROOT / "skills" / "contact-upload" / "SKILL.md").read_text(encoding="utf-8")
    assert "scripts/header_suggest.py" in skill
    assert "--confirm" in skill
    cleanup = skill.split("10. **Clean up.**", 1)[1]
    assert "2b" in cleanup
