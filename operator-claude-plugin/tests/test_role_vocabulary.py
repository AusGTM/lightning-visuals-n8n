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
