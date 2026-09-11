"""Tests for `held_queue.classify_facet` (260911-w6p, F2-2, Task 1).

The operator's 2026-09-11 F2 ruling: a `no_match` hold conflates two situations the
operator answers with two different verbs -- a provider NOT_FOUND at a company that is
not in HubSpot, and a rich reveal of a real new person at a company that IS. This file
pins the read-time classifier that separates them.

The four fixtures below are the real entries from run a254d1eda71246a2a964922cdf5c2bd2
(2026-09-11), recorded in `.planning/UAT-autonomous-batch-2026-09-09.md` line 65 and
still on the operator's disk -- frozen inline here, never read from the durable
plugin-data directory.
"""
from datetime import datetime

import pytest

import confidence
import held_queue
import run_manifest


def _outcome(tier="medium", candidate_count=1, **overrides):
    import preingest
    base = dict(parseable=True, match_tier=tier, candidate_count=candidate_count,
                provider_agreement=None, material_conflicts=None,
                judge_adjudicated_fields=None)
    base.update(overrides)
    return preingest.Outcome(**base)


def _entry(email, company, hold_code=confidence.HOLD_NO_MATCH):
    """A frozen `held_queue.json` entry shape -- not built via `build_entry`, since
    the recorded a254d1e entries are what we are pinning against, not a fresh
    construction."""
    return {
        "hold_code": hold_code,
        "reason": "no match found for this row",
        "observed_signals": {},
        "resume_fingerprint": "a254d1e" + "0" * 57,
        "row": {"email": email, "company": company},
    }


# The recorded a254d1e entries (line 65, .planning/UAT-autonomous-batch-2026-09-09.md).
KATIE_ENTRY = _entry("secretary@athertonturfclub.com.au", "Atherton Turf Club")
JIMMY_ENRICHED_ENTRY = _entry("jbusteed@australianturfclub.com.au", "Australian Turf Club")
JIMMY_AS_RECORDED_TODAY_ENTRY = _entry("", "Australian Turf Club")
BARRY_ENTRY = _entry("Devraclb@bigpond.net.au", "Devonport Racing Club")

ATC_DOMAINS = {"australianturfclub.com.au"}

# Phase 71 (D-71-04): the stable key each frozen entry's own `row` derives -- computed,
# never a new hardcoded literal (RESEARCH Pitfall 2).
KATIE_KEY = held_queue.stable_key(KATIE_ENTRY["row"])
JIMMY_KEY = held_queue.stable_key(JIMMY_ENRICHED_ENTRY["row"])


# =====================================================================================
# Task 1 -- classify_facet()
# =====================================================================================


def test_katie_with_atc_known_reads_needs_company_her_own_domain_is_not_in_the_set():
    assert held_queue.classify_facet(KATIE_ENTRY, ATC_DOMAINS) == held_queue.FACET_NEEDS_COMPANY


def test_jimmy_enriched_with_atc_known_reads_new_person():
    assert held_queue.classify_facet(JIMMY_ENRICHED_ENTRY, ATC_DOMAINS) == held_queue.FACET_NEW_PERSON


def test_jimmy_exactly_as_recorded_today_empty_email_reads_nothing_found():
    assert held_queue.classify_facet(JIMMY_AS_RECORDED_TODAY_ENTRY, ATC_DOMAINS) == \
        held_queue.FACET_NOTHING_FOUND


def test_barry_at_a_freemail_isp_domain_reads_nothing_found():
    assert held_queue.classify_facet(BARRY_ENTRY, ATC_DOMAINS) == held_queue.FACET_NOTHING_FOUND


def test_jimmy_enriched_with_no_domains_supplied_reads_needs_company_the_safe_default():
    assert held_queue.classify_facet(JIMMY_ENRICHED_ENTRY) == held_queue.FACET_NEEDS_COMPANY


def test_a_messy_supplied_domain_still_matches_jimmy():
    messy = {"https://www.AustralianTurfClub.com.au/"}
    assert held_queue.classify_facet(JIMMY_ENRICHED_ENTRY, messy) == held_queue.FACET_NEW_PERSON


def test_an_unadjudicated_conflict_hold_is_not_a_faceted_hold():
    conflict_entry = _entry(
        "jbusteed@australianturfclub.com.au", "Australian Turf Club",
        hold_code=confidence.HOLD_UNADJUDICATED_CONFLICT,
    )
    assert held_queue.classify_facet(conflict_entry, ATC_DOMAINS) is None


def test_all_hold_codes_is_still_exactly_the_six_existing_words():
    assert confidence.ALL_HOLD_CODES == frozenset({
        confidence.HOLD_UNPARSEABLE,
        confidence.HOLD_UNADJUDICATED_CONFLICT,
        confidence.HOLD_UNKNOWN_TIER,
        confidence.HOLD_NO_MATCH,
        confidence.HOLD_AMBIGUOUS_CANDIDATES,
        confidence.HOLD_NO_TABLE_ROW_MATCHED,
    })
    assert len(confidence.ALL_HOLD_CODES) == 6


def test_a_non_dict_entry_returns_none():
    assert held_queue.classify_facet(None) is None
    assert held_queue.classify_facet("not a dict") is None


def test_a_row_with_no_row_key_at_all_reads_nothing_found():
    assert held_queue.classify_facet({"hold_code": confidence.HOLD_NO_MATCH}) == \
        held_queue.FACET_NOTHING_FOUND


def test_a_non_string_email_reads_nothing_found():
    entry = _entry(None, "Some Company")
    assert held_queue.classify_facet(entry) == held_queue.FACET_NOTHING_FOUND


def test_an_email_with_no_at_sign_reads_nothing_found():
    entry = _entry("not-an-email", "Some Company")
    assert held_queue.classify_facet(entry) == held_queue.FACET_NOTHING_FOUND


def test_an_email_with_two_at_signs_reads_nothing_found():
    entry = _entry("a@b@c.com", "Some Company")
    assert held_queue.classify_facet(entry) == held_queue.FACET_NOTHING_FOUND


# =====================================================================================
# Task 2 -- record_verb() / entry_verb() / is_settled() / open_entries()
# =====================================================================================


def _saved_two_row_queue(tmp_path):
    target = tmp_path / "held_queue.json"
    entries = {KATIE_KEY: dict(KATIE_ENTRY), JIMMY_KEY: dict(JIMMY_ENRICHED_ENTRY)}
    held_queue.save("run-1", entries, path=target)
    return target, entries


def test_record_verb_round_trips_verb_timestamp_and_run_id(tmp_path):
    target, entries = _saved_two_row_queue(tmp_path)

    held_queue.record_verb(KATIE_KEY, held_queue.VERB_CREATE, "run-2", path=target)
    loaded = held_queue.load(path=target)

    status = loaded[KATIE_KEY]["status"]
    assert status["verb"] == held_queue.VERB_CREATE
    assert status["run_id"] == "run-2"
    stamp = datetime.fromisoformat(status["at"])
    assert stamp.tzinfo is not None  # UTC ISO timestamp, not a naive one

    # every other field of Katie's entry, and all of Jimmy's, byte-identical
    assert {k: v for k, v in loaded[KATIE_KEY].items() if k != "status"} == entries[KATIE_KEY]
    assert loaded[JIMMY_KEY] == entries[JIMMY_KEY]


def test_record_verb_refuses_an_unrecognised_verb_and_leaves_the_file_untouched(tmp_path):
    target, _ = _saved_two_row_queue(tmp_path)
    before = target.read_text()

    with pytest.raises(held_queue.HeldQueueError):
        held_queue.record_verb(KATIE_KEY, "delete", "run-2", path=target)

    assert target.read_text() == before


def test_record_verb_refuses_a_row_id_not_in_the_queue(tmp_path):
    target, _ = _saved_two_row_queue(tmp_path)
    before = target.read_text()

    with pytest.raises(held_queue.HeldQueueError):
        held_queue.record_verb("row-99", held_queue.VERB_SKIP, "run-2", path=target)

    assert target.read_text() == before


def test_record_verb_refuses_a_grant_shaped_run_id(tmp_path):
    target, _ = _saved_two_row_queue(tmp_path)
    before = target.read_text()

    with pytest.raises(held_queue.HeldQueueError):
        held_queue.record_verb(KATIE_KEY, held_queue.VERB_CREATE, "armed-run-1", path=target)

    assert target.read_text() == before


def test_a_malformed_status_on_disk_degrades_load_to_empty_and_classifies_anomalous(tmp_path):
    """`save()` itself refuses to write a bad-verb status (vocabulary-checked on the
    write side too), so this simulates a hand-edited/half-written file directly, the
    same way `test_load_on_an_entry_with_an_invalid_hold_code_degrades_the_whole_
    queue` in `test_held_queue.py` does for a bad `hold_code`."""
    import json as _json
    target = tmp_path / "held_queue.json"
    entry = dict(KATIE_ENTRY)
    entry["status"] = {"verb": "delete"}  # not one of ALL_VERBS
    target.write_text(_json.dumps({
        "run_id": "run-1", "saved_at": "2026-09-11T00:00:00Z",
        "entries": {KATIE_KEY: entry},
    }), encoding="utf-8")

    assert held_queue.load(path=target) == {}
    assert held_queue.classify_read(path=target) == held_queue.ANOMALOUS


def test_a_non_dict_status_on_disk_also_degrades_load_to_empty_and_classifies_anomalous(tmp_path):
    import json as _json
    target = tmp_path / "held_queue.json"
    entry = dict(KATIE_ENTRY)
    entry["status"] = "create"  # not a dict at all
    target.write_text(_json.dumps({
        "run_id": "run-1", "saved_at": "2026-09-11T00:00:00Z",
        "entries": {KATIE_KEY: entry},
    }), encoding="utf-8")

    assert held_queue.load(path=target) == {}
    assert held_queue.classify_read(path=target) == held_queue.ANOMALOUS


def test_an_entry_with_no_status_at_all_loads_exactly_as_it_does_today(tmp_path):
    target, entries = _saved_two_row_queue(tmp_path)
    loaded = held_queue.load(path=target)
    assert loaded == entries
    assert held_queue.entry_verb(loaded[KATIE_KEY]) is None
    assert not held_queue.is_settled(loaded[KATIE_KEY])


def test_open_entries_drops_settled_and_keeps_retry_and_undecided():
    created = dict(KATIE_ENTRY)
    created["status"] = {"verb": held_queue.VERB_CREATE, "at": "x", "run_id": "run-1"}
    skipped = dict(JIMMY_ENRICHED_ENTRY)
    skipped["status"] = {"verb": held_queue.VERB_SKIP, "at": "x", "run_id": "run-1"}
    dropped = dict(BARRY_ENTRY)
    dropped["status"] = {"verb": held_queue.VERB_DROP, "at": "x", "run_id": "run-1"}
    retried = dict(BARRY_ENTRY)
    retried["status"] = {"verb": held_queue.VERB_RETRY, "at": "x", "run_id": "run-1"}
    undecided = dict(KATIE_ENTRY)

    entries = {
        "created": created, "skipped": skipped, "dropped": dropped,
        "retried": retried, "undecided": undecided,
    }
    assert held_queue.open_entries(entries) == {"retried": retried, "undecided": undecided}


# =====================================================================================
# Task 3 -- rows_to_resume() honours a settled/retry verb before the fingerprint
# =====================================================================================


def _held_row(row_id, verb=None):
    entry = held_queue.build_entry(
        {"row_id": row_id, "email": "jbusteed@australianturfclub.com.au",
         "firstname": "Jimmy", "lastname": "Busteed"},
        confidence.HOLD_NO_MATCH, "no match found", _outcome(tier="none", candidate_count=0),
    )
    if verb is not None:
        entry = dict(entry)
        entry["status"] = {"verb": verb, "at": "x", "run_id": "run-1"}
    return entry


@pytest.mark.parametrize("verb", [held_queue.VERB_CREATE, held_queue.VERB_SKIP, held_queue.VERB_DROP])
def test_a_settled_row_is_not_resumed_even_when_the_fingerprint_now_differs(verb):
    """The exact case a fingerprint comparison gets wrong: the created person now
    matches at a high tier, so the free-match-pass fingerprint differs from the one
    recorded at hold time -- and the settled verb must win regardless."""
    entry = _held_row("row-1", verb=verb)
    manifest = {"row-1": run_manifest.CONFIDENCE_HELD}
    current_outcome_now_matches = _outcome(tier="high", candidate_count=1)

    result = run_manifest.rows_to_resume(
        [{"row_id": "row-1", "firstname": "Jimmy", "lastname": "Busteed"}],
        manifest,
        held_entries={"row-1": entry},
        current_outcomes={"row-1": current_outcome_now_matches},
    )

    assert result.rows == ()
    assert result.still_held == ()
    assert result.skipped == ({"row_id": "row-1", "verdict": run_manifest.CONFIDENCE_HELD},)


def test_a_retry_row_is_resumed_even_when_the_fingerprint_is_equal():
    outcome = _outcome(tier="none", candidate_count=0)
    entry = _held_row("row-1", verb=held_queue.VERB_RETRY)
    manifest = {"row-1": run_manifest.CONFIDENCE_HELD}

    result = run_manifest.rows_to_resume(
        [{"row_id": "row-1", "firstname": "Jimmy", "lastname": "Busteed"}],
        manifest,
        held_entries={"row-1": entry},
        current_outcomes={"row-1": outcome},  # identical fingerprint to hold time
    )

    assert len(result.rows) == 1
    assert result.rows[0]["row_id"] == "row-1"
    assert result.still_held == ()
    assert result.skipped == ()


def test_an_entry_with_no_status_keeps_todays_fingerprint_behaviour_exactly():
    outcome = _outcome(tier="none", candidate_count=0)
    entry = _held_row("row-1")  # no verb recorded
    manifest = {"row-1": run_manifest.CONFIDENCE_HELD}

    # equal fingerprint -> still held
    equal = run_manifest.rows_to_resume(
        [{"row_id": "row-1", "firstname": "Jimmy", "lastname": "Busteed"}],
        manifest, held_entries={"row-1": entry}, current_outcomes={"row-1": outcome},
    )
    assert equal.rows == ()
    assert equal.still_held == ({"row_id": "row-1", "verdict": run_manifest.CONFIDENCE_HELD},)

    # differing fingerprint -> resumed
    differing = run_manifest.rows_to_resume(
        [{"row_id": "row-1", "firstname": "Jimmy", "lastname": "Busteed"}],
        manifest, held_entries={"row-1": entry},
        current_outcomes={"row-1": _outcome(tier="high", candidate_count=1)},
    )
    assert len(differing.rows) == 1

    # missing entry or missing current outcome -> resumed
    missing_entry = run_manifest.rows_to_resume(
        [{"row_id": "row-1", "firstname": "Jimmy", "lastname": "Busteed"}],
        manifest, held_entries={}, current_outcomes={"row-1": outcome},
    )
    assert len(missing_entry.rows) == 1
    missing_current = run_manifest.rows_to_resume(
        [{"row_id": "row-1", "firstname": "Jimmy", "lastname": "Busteed"}],
        manifest, held_entries={"row-1": entry}, current_outcomes={},
    )
    assert len(missing_current.rows) == 1
