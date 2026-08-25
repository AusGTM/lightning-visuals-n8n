"""0.7.1 — an empty input must not read as a healthy zero (UAT 2.6).

Two-sided by construction: the library half proves what `build_preview` actually reports
for an empty file, and the skill half proves the skill body has a branch that acts on it.
Either alone is insufficient — the library returning `row_count: 0` is only a defect
because nothing above it explains the zero, and a skill branch keyed on a field the
preview does not carry would be prose.
"""
import re
from pathlib import Path

import preview

SKILL = (Path(__file__).resolve().parent.parent
         / "skills" / "contact-upload" / "SKILL.md").read_text()


def test_an_empty_file_previews_as_zero_rows_with_no_headers(tmp_path):
    """The library half. Not a bug on its own — it is the input to the skill's branch."""
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    p = preview.build_preview(empty)
    assert p["row_count"] == 0
    assert p["headers"] == []


def test_a_header_only_file_previews_as_zero_rows_with_headers(tmp_path):
    """The case an operator hits most: a real export with the data left behind. Distinct
    from the empty file, and the skill is required to tell them apart."""
    header_only = tmp_path / "headers.csv"
    header_only.write_text("Email Address,First Name,Last Name\n")
    p = preview.build_preview(header_only)
    assert p["row_count"] == 0
    assert p["headers"], "headers survive even when no data rows do"


def test_the_skill_stops_at_the_preview_when_there_are_no_rows():
    """The skill half. Without this branch the documented flow proceeds to 'ask for
    approval' and offers the arming phrase for a batch containing nothing."""
    assert "If `row_count` is 0" in SKILL, "the branch must key on the field the preview carries"
    assert "do not continue to step 4" in SKILL


def test_the_skill_names_the_likely_causes_rather_than_just_reporting_zero():
    """'0 rows' is a number. An operator needs to know what to change."""
    for cause in ("empty file", "header", "wrong sheet"):
        assert cause in SKILL, f"the zero-row branch should name {cause!r} as a likely cause"


def test_the_skill_does_not_invite_consent_for_an_empty_batch():
    """The 0.6.2 lesson, applied to a second case: never offer a decision that cannot be
    honoured. Scoped to the zero-row paragraph so the legitimate consent instructions in
    steps 5-6 do not satisfy it by accident.

    RECORDED EDIT -- VOCAB-05, 2026-08-25. Was
    `test_the_skill_does_not_invite_arming_for_an_empty_batch`, asserting the words "do not
    offer the arming phrase". The phrase died; the property is unchanged -- a batch that
    cannot be sent must not have its send asked for."""
    para = re.search(r"\*\*If `row_count` is 0.*?(?=\n\n4\. )", SKILL, re.S)
    assert para, "zero-row branch not found"
    assert "do not ask for this send at all" in para.group(0).lower()
