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
    """No name in this fixture matches a `_FORBIDDEN_NAME_MARKERS` whole token -- this
    test proves the happy path; the marker's genuine (whole-token) refusals are proved
    separately in plan 01's Task 3."""
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


# =====================================================================================
# classify_read() — three states, no ANOTHER_RUN (D-69-03)
# =====================================================================================


def test_classify_read_on_a_missing_file_is_absent(tmp_path):
    target = tmp_path / "suggestion_declines.json"
    assert suggestion_declines.classify_read(path=target) == suggestion_declines.ABSENT


def test_classify_read_on_a_good_file_is_parseable(tmp_path):
    target = tmp_path / "suggestion_declines.json"
    entry = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-1", "123")
    suggestion_declines.save({"123::pat|lee": entry}, path=target)
    assert suggestion_declines.classify_read(path=target) == suggestion_declines.PARSEABLE


def test_classify_read_on_malformed_json_is_anomalous(tmp_path):
    target = tmp_path / "suggestion_declines.json"
    target.write_text("not json", encoding="utf-8")
    assert suggestion_declines.classify_read(path=target) == suggestion_declines.ANOMALOUS


def test_classify_read_on_an_entry_with_an_unknown_reason_code_is_anomalous(tmp_path):
    target = tmp_path / "suggestion_declines.json"
    target.write_text(json.dumps({
        "entries": {
            "123::pat|lee": {
                "reason_code": "not_a_real_code", "reason": "x", "run_id": "run-1",
                "company_id": "123", "row": {}, "provenance": {},
                "recorded_at": "2026-01-01T00:00:00+00:00",
            },
        },
    }), encoding="utf-8")
    assert suggestion_declines.classify_read(path=target) == suggestion_declines.ANOMALOUS


def test_classify_read_on_a_document_with_two_different_run_ids_is_parseable(tmp_path):
    """There is no 'wrong run' state for this store -- D-69-03 makes the document
    inherently multi-run by design."""
    target = tmp_path / "suggestion_declines.json"
    entry_a = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-1", "123")
    entry_b = suggestion_declines.build_entry(
        {"firstname": "Sam", "lastname": "Cole"}, "no_email", "x", "run-2", "456")
    suggestion_declines.save({"123::pat|lee": entry_a, "456::sam|cole": entry_b}, path=target)
    assert suggestion_declines.classify_read(path=target) == suggestion_declines.PARSEABLE


def test_load_still_degrades_whole_for_every_case_classify_read_calls_anomalous(tmp_path):
    target = tmp_path / "suggestion_declines.json"
    target.write_text("not json", encoding="utf-8")
    assert suggestion_declines.classify_read(path=target) == suggestion_declines.ANOMALOUS
    assert suggestion_declines.load(path=target) == {}


# =====================================================================================
# partition_by_run() — pure, no I/O
# =====================================================================================


def test_partition_by_run_splits_on_each_entrys_own_run_id():
    entry_a = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-2", "123")
    entry_b = suggestion_declines.build_entry(
        {"firstname": "Sam", "lastname": "Cole"}, "no_email", "x", "run-1", "456")
    entries = {"123::pat|lee": entry_a, "456::sam|cole": entry_b}

    result = suggestion_declines.partition_by_run(entries, "run-2")

    assert result["this_run"] == {"123::pat|lee": entry_a}
    assert result["backlog"] == {"456::sam|cole": entry_b}
    assert set(result["this_run"]) & set(result["backlog"]) == set()
    assert {**result["this_run"], **result["backlog"]} == entries


def test_partition_by_run_with_run_id_none_puts_everything_in_backlog():
    entry_a = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-1", "123")
    entries = {"123::pat|lee": entry_a}

    result = suggestion_declines.partition_by_run(entries, None)

    assert result["this_run"] == {}
    assert result["backlog"] == entries


def test_partition_by_run_on_an_empty_map_raises_nothing():
    result = suggestion_declines.partition_by_run({}, "run-1")
    assert result == {"this_run": {}, "backlog": {}}


# =====================================================================================
# apply_action() — pure, returns a NEW dict
# =====================================================================================


def test_apply_action_defer_returns_an_equal_map_and_does_not_mutate_the_input():
    entry_a = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-1", "123")
    entries = {"123::pat|lee": entry_a}
    before = dict(entries)

    result = suggestion_declines.apply_action(entries, "123::pat|lee", "defer")

    assert result == before
    assert entries == before


def test_apply_action_delete_removes_the_key_and_adds_no_tombstone():
    entry_a = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-1", "123")
    entry_b = suggestion_declines.build_entry(
        {"firstname": "Sam", "lastname": "Cole"}, "no_email", "x", "run-1", "456")
    entries = {"123::pat|lee": entry_a, "456::sam|cole": entry_b}

    result = suggestion_declines.apply_action(entries, "123::pat|lee", "delete")

    assert set(result.keys()) == set(entries.keys()) - {"123::pat|lee"}


def test_apply_action_send_removes_the_key():
    entry_a = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-1", "123")
    entries = {"123::pat|lee": entry_a}

    result = suggestion_declines.apply_action(entries, "123::pat|lee", "send")

    assert "123::pat|lee" not in result


def test_apply_action_export_leaves_the_map_unchanged():
    entry_a = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-1", "123")
    entries = {"123::pat|lee": entry_a}

    result = suggestion_declines.apply_action(entries, "123::pat|lee", "export")

    assert result == entries


def test_apply_action_raises_on_an_action_outside_drain_actions():
    entry_a = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-1", "123")
    entries = {"123::pat|lee": entry_a}
    with pytest.raises(suggestion_declines.SuggestionDeclineError):
        suggestion_declines.apply_action(entries, "123::pat|lee", "bogus")


def test_apply_action_raises_on_a_key_absent_from_the_map():
    with pytest.raises(suggestion_declines.SuggestionDeclineError):
        suggestion_declines.apply_action({}, "nope", "defer")


# =====================================================================================
# Idempotency
# =====================================================================================


def test_saving_the_same_map_twice_produces_byte_identical_file_content(tmp_path):
    target = tmp_path / "suggestion_declines.json"
    entry = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-1", "123")
    entries = {"123::pat|lee": entry}

    suggestion_declines.save(entries, path=target)
    first = target.read_bytes()
    suggestion_declines.save(entries, path=target)
    second = target.read_bytes()

    assert first == second


def test_rekeying_the_same_person_from_a_later_run_replaces_the_entry_and_does_not_grow(tmp_path):
    target = tmp_path / "suggestion_declines.json"
    entry_a = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-1", "123")
    suggestion_declines.save({"123::pat|lee": entry_a}, path=target)
    assert len(suggestion_declines.load(path=target)) == 1

    entry_b = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "email_domain_mismatch", "y", "run-2", "123")
    suggestion_declines.save({"123::pat|lee": entry_b}, path=target)

    loaded = suggestion_declines.load(path=target)
    assert len(loaded) == 1
    assert loaded["123::pat|lee"]["run_id"] == "run-2"


# =====================================================================================
# Refused save leaves the previous file byte-identical
# =====================================================================================


def test_a_refused_save_leaves_the_previous_file_byte_identical(tmp_path):
    target = tmp_path / "suggestion_declines.json"
    good = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-1", "123")
    suggestion_declines.save({"123::pat|lee": good}, path=target)
    before = target.read_bytes()

    bad = {
        "reason_code": "not_a_real_code", "reason": "x", "run_id": "run-2",
        "company_id": "456", "row": {}, "provenance": {}, "recorded_at": "x",
    }
    with pytest.raises(suggestion_declines.SuggestionDeclineError):
        suggestion_declines.save({"123::pat|lee": good, "456::sam|cole": bad}, path=target)

    assert target.read_bytes() == before


# =====================================================================================
# CR-01: save() must refuse to overwrite an anomalous pre-existing file
# =====================================================================================


def test_save_refuses_to_overwrite_a_preexisting_anomalous_file(tmp_path):
    """A single unreadable store file must never be silently clobbered by one round's
    entries (CR-01) -- the exact loss D-69-03's reversibility note calls one-way."""
    target = tmp_path / "suggestion_declines.json"
    target.write_bytes(b"garbage, not json at all")
    before = target.read_bytes()

    entry = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-1", "123")

    with pytest.raises(suggestion_declines.SuggestionDeclineError):
        suggestion_declines.save({"123::pat|lee": entry}, path=target)

    assert target.read_bytes() == before, "the pre-existing backlog must survive untouched"


# =====================================================================================
# Allowlist non-drift
# =====================================================================================


def test_row_field_allowlist_matches_canonical_props_and_excludes_row_id():
    assert set(suggestion_declines.ROW_FIELD_ALLOWLIST) == set(extraction.canonical_props())
    assert "row_id" not in suggestion_declines.ROW_FIELD_ALLOWLIST


# =====================================================================================
# IN-02: export_rows raises SuggestionDeclineError, not a bare KeyError
# =====================================================================================


def test_export_rows_raises_suggestion_decline_error_on_an_unknown_key(tmp_path):
    entry = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-1", "123")
    entries = {"123::pat|lee": entry}
    out_path = tmp_path / "export.csv"

    with pytest.raises(suggestion_declines.SuggestionDeclineError):
        suggestion_declines.export_rows(entries, ["999::nope|nope"], out_path)


# =====================================================================================
# quick 260911-any: whole-token matching -- Secretary and Armidale save; real markers
# still refuse
# =====================================================================================


def test_a_secretary_at_armidale_jockey_club_saves_and_loads_back_unchanged(tmp_path):
    """'Secretary' contains the substring 'secret' and 'Armidale Jockey Club' contains
    the substring 'arm' -- both false-tripped the old substring matcher. Whole-token
    matching must let both through."""
    target = tmp_path / "suggestion_declines.json"
    entry = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee", "company": "Armidale Jockey Club",
         "jobtitle": "Secretary"},
        "no_email", "x", "run-1", "123",
    )
    key = "123::pat|lee"
    suggestion_declines.save({key: entry}, path=target)

    loaded = suggestion_declines.load(path=target)
    assert loaded[key]["row"]["company"] == "Armidale Jockey Club"
    assert loaded[key]["row"]["jobtitle"] == "Secretary"


def test_a_genuine_marker_in_provenance_or_reason_still_refuses_nothing_written(tmp_path):
    """The `unstorable` reporting path (plan 02) stays load-bearing: a genuine
    marker -- a `provenance` key named `grant`, or a `reason` carrying a raw secret --
    is still refused via `first_refusal`, and `save` still raises with nothing
    written."""
    target = tmp_path / "suggestion_declines.json"
    entry = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email", "x", "run-1", "123",
        provenance={"grant": "op-grant-123"},
    )
    key = "123::pat|lee"

    sentence = suggestion_declines.first_refusal(key, entry)
    assert sentence is not None

    with pytest.raises(suggestion_declines.SuggestionDeclineError):
        suggestion_declines.save({key: entry}, path=target)
    assert not target.exists()

    leaked_entry = suggestion_declines.build_entry(
        {"firstname": "Pat", "lastname": "Lee"}, "no_email",
        "n8n_api_key=super-secret", "run-1", "123",
    )
    with pytest.raises(suggestion_declines.SuggestionDeclineError):
        suggestion_declines.save({key: leaked_entry}, path=target)
    assert not target.exists()
