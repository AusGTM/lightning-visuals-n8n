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
    # Quick task 260904-447: the portal actually stores this DOUBLE-encoded.
    "Finance &amp;amp; Admin Officer",
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


# ==================== Quick task 260904-447 (double-encoded entities) ====================

def test_double_encoded_title_classifies_to_its_real_shipped_family():
    vocabulary = role_classify.load_families()
    result = role_classify.classify_title(
        "Finance &amp;amp; Admin Officer", vocabulary["families"]
    )
    assert result == "Treasurer"


def test_tokenize_drops_the_orphaned_amp_token_from_double_encoded_input():
    expected = ("finance", "and", "admin", "officer")
    assert role_classify._tokenize("Finance &amp;amp; Admin Officer") == expected
    assert role_classify._tokenize("Finance & Admin Officer") == expected


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


# =====================================================================================
# Quick task 260905-rf1: one-word club titles
#
# First live suggest-contacts round, Brisbane Roar FC (company 285507657175),
# 2026-09-04. The discovery ladder found three named staff on the club's own
# /about/contact-us/ page; the role filter classified all three to None and the round
# yielded 0 selected. These are observations from that sitting, not invented titles.
# =====================================================================================

# (D-rf1-01) title -> (expected family label, the person measured live)
BRISBANE_ROAR_ONE_WORD_TITLES = [
    ("Marketing", "Marketing", "Jordan Hayward"),
    ("Media", "Media", "Joseph Esposito"),
    ("Sponsorship", "Sponsorship", "Emma Hoadley"),
]


@pytest.mark.parametrize("title,expected,person", BRISBANE_ROAR_ONE_WORD_TITLES)
def test_shipped_vocabulary_classifies_the_live_one_word_club_titles(title, expected, person):
    vocabulary = role_classify.load_families()
    result = role_classify.classify_title(title, vocabulary["families"])
    assert result == expected, (
        f"{title!r} was the page title of {person} on Brisbane Roar FC's own contact "
        f"page (company 285507657175, measured 2026-09-04); it classified to {result!r}, "
        f"so the role filter selected 0 of 3 real staff in exactly the roles the "
        f"operator had asked for"
    )


# (D-rf1-02) The no-flip freeze. Measured 2026-09-05 against the shipped vocabulary
# BEFORE the three new families were appended; every row must return the same label
# after. The two "... Director" rows are the load-bearing ones: they hold only while the
# new one-token families sit AFTER `Board & Committee` in the YAML, because
# classify_title's tie-break on an equal-length match is first-wins by family order.
# This table is what pins append-at-end. A red here means a measured value is wrong and
# must be RE-MEASURED, never adjusted to fit.
FROZEN_TITLE_CLASSIFICATIONS = [
    ("Marketing Director", "Board & Committee"),
    ("Media Director", "Board & Committee"),
    ("Head of Marketing and Content", "Head of Marketing"),
    ("Marketing Manager", "Marketing Manager"),
    ("Communications Manager", "Communications Manager"),
    ("Media and Communications Manager", "Communications Manager"),
    ("Track Manager", "Track & Facilities"),
    ("Secretary Manager", "Secretary"),
    ("Chairman", "Chair"),
    ("CEO", "CEO"),
    ("President", "President"),
    ("Vice President", "Vice President"),
    ("Finance &amp;amp; Admin Officer", "Treasurer"),
]


@pytest.mark.parametrize("title,expected", FROZEN_TITLE_CLASSIFICATIONS)
def test_no_currently_correct_classification_flips(title, expected):
    vocabulary = role_classify.load_families()
    result = role_classify.classify_title(title, vocabulary["families"])
    assert result == expected, (
        f"{title!r} classified to {expected!r} before quick task 260905-rf1 and now "
        f"classifies to {result!r}. A vocabulary edit must not move a title that "
        f"already had a correct home -- if this is a '... Director' row, the one-token "
        f"families have most likely been moved ahead of 'Board & Committee', which "
        f"changes the equal-length tie-break"
    )


# (D-rf1-03) A bare token in two families is ambiguity, not a match, and classify_title
# would resolve it silently by YAML order rather than surfacing it.
def test_no_single_token_member_belongs_to_two_families():
    vocabulary = role_classify.load_families()
    token_owners = {}
    for family in vocabulary["families"]:
        label = family.get("label")
        for member in family.get("members") or []:
            tokens = role_classify._tokenize(member)
            if len(tokens) == 1:
                token_owners.setdefault(tokens[0], set()).add(label)
    collisions = {token: sorted(labels) for token, labels in token_owners.items() if len(labels) > 1}
    assert not collisions, (
        f"single-token member(s) owned by more than one family: {collisions} -- a bare "
        f"token matching two families is ambiguity, not a match, and classify_title's "
        f"equal-length tie-break would resolve it silently by YAML order, so which "
        f"family wins would depend on file layout rather than on the title"
    )
