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
import confidence
import held_queue


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
