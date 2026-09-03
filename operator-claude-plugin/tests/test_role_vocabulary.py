"""Tests for role_classify.py's loader/offer/select extensions (Phase 62 Plan 02 Task 2).

Covers `load_families()` (carries the evidence flag alongside the family list, never the
list alone), `offer_block()` (the D-62-07 disclosure sentence for an un-evidenced
vocabulary, recurrence counts for an evidenced one), and `chosen_families()` (validates a
round-level selection against the vocabulary's own labels). `classify_title()` itself is
unchanged and covered by test_suggest_contacts.py -- this file only re-proves it still
takes no path.
"""
import pathlib

import pytest

import role_classify

EVIDENCED_VOCABULARY = {
    "version": "lv-role-vocabulary-v1",
    "built_on": "2026-09-02",
    "source": "portal_jobtitle_inventory",
    "evidenced": True,
    "top_n": 8,
    "distinct_titles_sampled": 42,
    "families": [
        {"label": "CEO", "recurrence": 12, "evidenced": True, "members": ["Chief Executive Officer", "CEO"]},
        {"label": "Head of Broadcast", "recurrence": 5, "evidenced": True, "members": ["Head of Broadcast"]},
    ],
}


def test_shipped_vocabulary_loads_and_reports_evidenced_false():
    vocabulary = role_classify.load_families()
    assert vocabulary["evidenced"] is False
    assert vocabulary["source"] == "generic_fallback"
    assert vocabulary["families"]


def test_load_families_never_returns_the_list_alone():
    vocabulary = role_classify.load_families()
    for key in ("families", "evidenced", "source", "built_on", "top_n"):
        assert key in vocabulary


def test_load_families_missing_file_raises_naming_the_path(tmp_path):
    missing = tmp_path / "does-not-exist.yaml"
    with pytest.raises(role_classify.RoleVocabularyError) as excinfo:
        role_classify.load_families(path=missing)
    assert str(missing) in str(excinfo.value)


def test_load_families_unparseable_file_raises(tmp_path):
    bad = tmp_path / "broken.yaml"
    bad.write_text("families: [unterminated")
    with pytest.raises(role_classify.RoleVocabularyError):
        role_classify.load_families(path=bad)


def test_offer_block_un_evidenced_contains_disclosure_sentence():
    vocabulary = role_classify.load_families()
    block = role_classify.offer_block(vocabulary)
    assert "NOT derived from this portal's own contacts" in block


def test_offer_block_evidenced_shows_recurrence_and_omits_disclosure():
    block = role_classify.offer_block(EVIDENCED_VOCABULARY)
    assert "NOT derived from this portal's own contacts" not in block
    assert "CEO" in block
    assert "12" in block


def test_chosen_families_accepts_known_labels():
    result = role_classify.chosen_families(EVIDENCED_VOCABULARY, ["CEO", "Head of Broadcast"])
    assert result == ["CEO", "Head of Broadcast"]


def test_chosen_families_raises_on_unknown_label():
    with pytest.raises(role_classify.RoleVocabularyError):
        role_classify.chosen_families(EVIDENCED_VOCABULARY, ["CFO"])


def test_classify_title_works_with_default_vocabulary_path_pointed_at_nothing(monkeypatch, tmp_path):
    monkeypatch.setattr(role_classify, "DEFAULT_VOCABULARY_PATH", tmp_path / "nope.yaml")
    family_list = [{"label": "board", "members": ["Director", "Board Member"]}]
    assert role_classify.classify_title("Director", family_list) == "board"


# =====================================================================================
# Shipped-vocabulary coverage (62-09 Task 2, G-62-3)
#
# The seventeen job titles measured live on three racing-club board/committee pages in
# the 2026-09-03 sitting. The ladder named 43 people across those pages; the OLD
# (exact-label, 8-family) vocabulary selected 2. These are observations from that
# sitting, not invented titles -- see 62-UAT.md's G-62-3 entry.
# =====================================================================================

MEASURED_RACING_CLUB_TITLES = [
    "Chairman",
    "Deputy Chairman",
    "President",
    "Vice President",
    "Vice Chairman",
    "Director",
    "Board Of Directors",
    "Treasurer",
    "Secretary",
    "Secretary Manager",
    "Committee member",
    "Track Manager",
    "Catering Manager",
    "Racecourse Track Curator",
    "Executive Assistant",
    "Finance & Admin Officer",
    "Trackwork Supervisor",
    # The portal stores this HTML-entity-escaped -- an eighteenth case proving the
    # same coverage holds for the stored (unescaped-at-normalisation) form.
    "Finance &amp; Admin Officer",
]


@pytest.mark.parametrize("title", MEASURED_RACING_CLUB_TITLES)
def test_shipped_vocabulary_covers_every_measured_racing_club_title(title):
    vocabulary = role_classify.load_families()
    result = role_classify.classify_title(title, vocabulary["families"])
    assert result is not None, (
        f"{title!r} was measured live on a racing-club board page but classifies to "
        f"nothing in the shipped vocabulary"
    )


# Decision 2: these grade nouns appear in most job titles. A bare (single-token)
# member from this set would make its family match nearly every person on a board
# page and quietly spend the round's cap on people the operator did not choose.
FORBIDDEN_BARE_GRADE_NOUNS = {
    "manager", "officer", "executive", "assistant",
    "coordinator", "supervisor", "head", "lead",
}


def test_shipped_vocabulary_has_no_bare_grade_noun_members():
    vocabulary = role_classify.load_families()
    offenders = []
    for family in vocabulary["families"]:
        label = family.get("label")
        for member in family.get("members") or []:
            tokens = role_classify._tokenize(member)
            if len(tokens) == 1 and tokens[0] in FORBIDDEN_BARE_GRADE_NOUNS:
                offenders.append((label, member))
    assert not offenders, (
        f"bare grade noun member(s) found: {offenders} -- a single-token member from "
        f"{sorted(FORBIDDEN_BARE_GRADE_NOUNS)} would match nearly every person on a "
        f"board page and must be a multi-word member instead"
    )
