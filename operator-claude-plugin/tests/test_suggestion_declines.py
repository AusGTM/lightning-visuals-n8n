"""Tests for `suggestion_declines.py` (Phase 69 Plan 01).

Isolation mirrors `test_held_queue.py`: most tests pass an explicit `path=`; the
location tests isolate via `CLAUDE_PLUGIN_DATA` instead.
"""
import ast
import json
import stat
from pathlib import Path

import pytest

import confidence
import extraction
import held_queue
import search_fallback
import suggest_contacts
import suggestion_declines


def _point_at_a_fake_durable_home(monkeypatch, tmp_path):
    fake_durable = tmp_path / "durable"
    fake_durable.mkdir()
    (fake_durable / "dashboard_artifact.json").write_text("{}")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(fake_durable))


# =====================================================================================
# End-to-end: a real `partition_for_dispatch` held entry -> keyed, built, saved, loaded
# =====================================================================================


def test_a_real_held_person_survives_key_build_save_and_load(tmp_path):
    """No name in this fixture contains a `_FORBIDDEN_NAME_MARKERS` substring -- this
    test proves the happy path; the marker's false positives are proved separately in
    plan 01's Task 3."""
    rows = [
        {"firstname": "Craig", "lastname": "Smith", "company": "The Roma Turf Club",
         "email": "craig.smith@thehartford.com"},
        {"firstname": "Pat", "lastname": "Lee", "company": "The Roma Turf Club"},
    ]
    company_domains = {"The Roma Turf Club": "romaturfclub.com.au"}
    rounds = [
        {"start": 0, "count": 2, "company": {"id": "9999", "name": "The Roma Turf Club"}},
    ]

    sendable, held = suggest_contacts.partition_for_dispatch(rows, company_domains)
    assert sendable == []
    assert len(held) == 2

    run_id = "run-1"
    entries = {}
    for entry in held:
        company_id = suggest_contacts.company_id_for_index(rounds, entry["index"])
        key = suggestion_declines.entry_key(company_id, entry["row"])
        assert key is not None
        entries[key] = suggestion_declines.build_entry(
            entry["row"], entry["reason_code"], entry["reason"], run_id, company_id,
        )

    target = tmp_path / "suggestion_declines.json"
    suggestion_declines.save(entries, path=target)
    loaded = suggestion_declines.load(path=target)

    assert loaded == entries
    assert len(loaded) == 2
    reason_codes = {entry["reason_code"] for entry in loaded.values()}
    assert reason_codes == {"email_domain_mismatch", "no_email"}


# =====================================================================================
# HELD-02: PARTITION_REASON_CODES disjoint from confidence.ALL_HOLD_CODES
# =====================================================================================


def test_partition_reason_codes_disjoint_from_all_hold_codes():
    partition = set(suggest_contacts.PARTITION_REASON_CODES)
    hold = set(confidence.ALL_HOLD_CODES)
    assert partition
    assert hold
    assert partition & hold == set()


def test_partition_reason_codes_pinned_to_their_three_real_sources():
    assert "no_email" in suggest_contacts.PARTITION_REASON_CODES
    assert (
        set(suggest_contacts._RELATION_REASON_CODES.values())
        <= set(suggest_contacts.PARTITION_REASON_CODES)
    )
    assert search_fallback.SOURCE_TIER_HOLD_CODE in suggest_contacts.PARTITION_REASON_CODES


def test_suggestion_declines_module_does_not_import_confidence():
    source = Path(suggestion_declines.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    assert "confidence" not in imported


# =====================================================================================
# save() — 0600, allowlist, forbidden-name refusal
# =====================================================================================


def test_save_writes_at_mode_0600(tmp_path):
    target = tmp_path / "suggestion_declines.json"
    entry = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-1", "123")
    suggestion_declines.save({"123::pat|lee": entry}, path=target)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_build_entry_only_persists_allowlisted_row_fields_and_never_row_id():
    row = {"row_id": "row-1", "firstname": "Pat", "lastname": "Lee", "company": "Acme",
           "email": "pat@acme.example", "some_random_spreadsheet_column": "nope"}
    entry = suggestion_declines.build_entry(row, "no_email", "x", "run-1", "123")
    assert "row_id" not in entry["row"]
    assert "some_random_spreadsheet_column" not in entry["row"]
    assert set(entry["row"].keys()) <= set(suggestion_declines.ROW_FIELD_ALLOWLIST)


# =====================================================================================
# entry_key()
# =====================================================================================


def test_entry_key_is_none_when_company_id_is_missing():
    assert suggestion_declines.entry_key(None, {"firstname": "Amy", "lastname": "A"}) is None
    assert suggestion_declines.entry_key("", {"firstname": "Amy", "lastname": "A"}) is None


def test_entry_key_is_none_when_the_name_is_incomplete():
    assert suggestion_declines.entry_key("123", {"firstname": "Amy"}) is None


# =====================================================================================
# company_id_for_index()
# =====================================================================================


def test_company_id_for_index_returns_the_owning_companys_id():
    rounds = [
        {"start": 0, "count": 2, "company": {"id": "111"}},
        {"start": 2, "count": 1, "company": {"id": "222"}},
    ]
    assert suggest_contacts.company_id_for_index(rounds, 0) == "111"
    assert suggest_contacts.company_id_for_index(rounds, 1) == "111"
    assert suggest_contacts.company_id_for_index(rounds, 2) == "222"
    assert suggest_contacts.company_id_for_index(rounds, 3) is None


# =====================================================================================
# queue_path()
# =====================================================================================


def test_queue_path_shares_a_parent_with_held_queue_but_not_its_name(monkeypatch, tmp_path):
    _point_at_a_fake_durable_home(monkeypatch, tmp_path)
    assert suggestion_declines.queue_path().parent == held_queue.queue_path().parent
    assert suggestion_declines.queue_path().name == "suggestion_declines.json"
