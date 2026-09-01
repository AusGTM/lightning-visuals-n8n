"""Tests for suggest_contacts.py + role_classify.py (Phase 62 Plan 01).

Task 1 builds the tracer slice end to end, offline: one company with zero associated
contacts, through eligibility, the sitemap ladder (called as a library, never
re-implemented), the role filter, row synthesis, and into `extraction.validate()` as a
proposal that resolves on identity group 2 (firstname+lastname+company).
"""
import pathlib

import pytest

import extraction
import role_classify
import suggest_contacts
import url_fallback

SUGGEST_CONTACTS_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "scripts" / "suggest_contacts.py"
)

FAMILY_LIST = [
    {"label": "board", "members": ["Director", "Board Member", "Chairperson"]},
    {"label": "executive", "members": ["Chief Executive Officer", "General Manager"]},
]


def _company_row(row_id="c1", website="https://example-club.example/board",
                  num_associated_contacts=0, just_created=False):
    row = {"row_id": row_id, "name": "Example Racing Club", "website": website}
    if just_created:
        row["just_created"] = True
    else:
        row["num_associated_contacts"] = num_associated_contacts
    return row


# =====================================================================================
# role_classify.classify_title — pure, no I/O, family list always a parameter
# =====================================================================================

def test_classify_title_matches_case_and_whitespace_insensitively():
    assert role_classify.classify_title("  director  ", FAMILY_LIST) == "board"
    assert role_classify.classify_title("Chief Executive Officer", FAMILY_LIST) == "executive"


def test_classify_title_returns_none_for_no_match():
    assert role_classify.classify_title("Head Chef", FAMILY_LIST) is None


def test_classify_title_returns_none_for_blank_title():
    assert role_classify.classify_title("", FAMILY_LIST) is None
    assert role_classify.classify_title(None, FAMILY_LIST) is None


def test_classify_title_never_derives_its_own_family_list():
    # Structural: the module must not import anything that could build a family list
    # itself (no HubSpot client, no model call) — it only ever decides against one
    # handed in as a parameter.
    source = (
        pathlib.Path(__file__).resolve().parent.parent
        / "scripts" / "role_classify.py"
    ).read_text(encoding="utf-8")
    assert "import requests" not in source
    assert "anthropic" not in source.casefold()


# =====================================================================================
# eligibility — D-62-16 tri-state, readability before magnitude
# =====================================================================================

def test_eligibility_zero_contacts_is_eligible():
    verdicts = suggest_contacts.eligibility([_company_row(num_associated_contacts=0)])
    assert verdicts[0]["verdict"] == suggest_contacts.ELIGIBLE


def test_eligibility_nonzero_contacts_has_contacts():
    verdicts = suggest_contacts.eligibility([_company_row(num_associated_contacts=3)])
    assert verdicts[0]["verdict"] == suggest_contacts.HAS_CONTACTS


def test_eligibility_missing_count_is_unknown_never_eligible():
    row = {"row_id": "c2", "name": "Mystery Co", "website": "https://mystery.example"}
    verdicts = suggest_contacts.eligibility([row])
    assert verdicts[0]["verdict"] == suggest_contacts.UNKNOWN
    assert suggest_contacts.CONTACT_COUNT_PROPERTY in verdicts[0]["reason"]


def test_eligibility_just_created_company_is_eligible_by_construction():
    verdicts = suggest_contacts.eligibility([_company_row(just_created=True)])
    assert verdicts[0]["verdict"] == suggest_contacts.ELIGIBLE
    assert "created" in verdicts[0]["reason"]


def test_eligibility_raises_before_returning_any_verdict_on_a_malformed_row():
    rows = [_company_row(row_id="c1"), {"name": "No Id Co"}]
    with pytest.raises(Exception):
        suggest_contacts.eligibility(rows)


# =====================================================================================
# Task 1 tracer — the whole chain, offline, in one test
# =====================================================================================

def test_tracer_one_company_one_person_one_validated_proposal():
    company_row = _company_row()

    verdicts = suggest_contacts.eligibility([company_row])
    assert verdicts[0]["verdict"] == suggest_contacts.ELIGIBLE

    plan = suggest_contacts.discovery_plan(company_row)
    assert plan["candidates"], "the ladder must offer at least one candidate for a company with a usable website"
    # discovery_plan must call url_fallback.plan_ladder rather than rebuild the rung order
    assert plan["candidates"] == url_fallback.plan_ladder(company_row["website"])["candidates"]

    fetched_url = plan["candidates"][0]["url"]

    people = [{"firstname": "Jamie", "lastname": "Fox", "jobtitle": "Director"}]
    selection = suggest_contacts.select_people(
        people, FAMILY_LIST, chosen_families=["board"], known_contacts=[]
    )
    assert len(selection["selected"]) == 1
    assert selection["selected"][0]["firstname"] == "Jamie"

    records = suggest_contacts.synthesise_rows(
        company_row, selection["selected"], fetched_url, per_company_cap=3
    )
    assert len(records) == 1
    assert records[0]["record_type"] == "contacts"
    assert records[0]["provenance"]["locator"] == fetched_url
    assert records[0]["provenance"]["input"] == "suggest_contacts_ladder"

    artifact = suggest_contacts.round_artifact(records)
    result = extraction.validate(artifact)

    assert result.rejected == []
    assert result.dropped_keys == []
    assert len(result.accepted) == 1
    accepted_row = result.accepted[0]["row"]
    assert accepted_row["firstname"] == "Jamie"
    assert accepted_row["lastname"] == "Fox"
    assert accepted_row["company"] == "Example Racing Club"
    assert accepted_row["jobtitle"] == "Director"
    assert "email" not in accepted_row
    assert "phone" not in accepted_row


def test_synthesise_rows_person_without_lastname_fails_identity_no_widening():
    company_row = _company_row()
    person = {"firstname": "Jamie", "jobtitle": "Director"}
    records = suggest_contacts.synthesise_rows(
        company_row, [person], "https://example-club.example/sitemap.xml", per_company_cap=3
    )
    assert "lastname" not in records[0]["row"]

    artifact = suggest_contacts.round_artifact(records)
    result = extraction.validate(artifact)
    assert result.accepted == []
    assert len(result.rejected) == 1


def test_synthesise_rows_honors_per_company_cap():
    company_row = _company_row()
    people = [
        {"firstname": f"Person{i}", "lastname": "Lee", "jobtitle": "Director"}
        for i in range(5)
    ]
    records = suggest_contacts.synthesise_rows(
        company_row, people, "https://example-club.example/sitemap.xml", per_company_cap=2
    )
    assert len(records) == 2


def test_round_artifact_wraps_records_dict_only():
    records = [{"record_type": "contacts", "row": {}, "provenance": {}}]
    assert suggest_contacts.round_artifact(records) == {"records": records}


def test_suggest_contacts_module_is_pure_no_http_client():
    source = SUGGEST_CONTACTS_PATH.read_text(encoding="utf-8")
    assert "import requests" not in source
    assert "urllib.request" not in source


# =====================================================================================
# Task 2 — the per-company fetch budget and the give-up path (D-62-03)
# =====================================================================================

def test_company_budget_resets_between_two_companies_in_one_round():
    attempts_company_a = [{"url": f"u{i}", "outcome": "empty"} for i in range(4)]
    attempts_company_b = []
    assert suggest_contacts.company_budget(attempts_company_a) == 4
    assert suggest_contacts.company_budget(attempts_company_b) == 0


def test_next_candidates_refuses_off_host_url_with_url_fallbacks_own_reason():
    company_row = _company_row(website="https://example-club.example/board")
    off_host = "https://other-host.example/board"

    result = suggest_contacts.next_candidates(company_row, attempts=[], sitemap_urls=[off_host])
    expected = url_fallback.filter_candidates(
        company_row["website"], [off_host], already_fetched=0
    )

    assert result == expected
    assert result["refused"][0]["url"] == off_host


def test_next_candidates_threads_this_companys_own_budget():
    company_row = _company_row(website="https://example-club.example/board")
    same_host_url = "https://example-club.example/sitemap.xml"
    attempts = [{"url": f"u{i}", "outcome": "empty"} for i in range(4)]

    result = suggest_contacts.next_candidates(company_row, attempts, [same_host_url])

    assert result["budget_remaining"] == 1
    assert same_host_url in result["accepted"]


def test_no_candidates_records_give_up_messages_own_text():
    company_row = _company_row()
    pasted_url = company_row["website"]
    attempts = [{"url": "https://example-club.example/wp-sitemap.xml", "outcome": "empty"}]

    result = suggest_contacts.no_candidates(company_row, pasted_url, attempts)

    assert result["outcome"] == "no_candidates_found"
    assert result["reason"] == url_fallback.give_up_message(pasted_url, attempts)
    assert result["company"] == company_row


def test_suggest_contacts_never_falls_through_to_a_second_search_provider():
    source = SUGGEST_CONTACTS_PATH.read_text(encoding="utf-8")
    for forbidden in ("google", "bing", "duckduckgo", "search_engine", "retry_other_host"):
        assert forbidden not in source.casefold()
