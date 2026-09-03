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


# =====================================================================================
# Task 3 — D-62-18's dedupe pre-filter, and the emailless hold (D-62-09/SUGGEST-04)
# =====================================================================================

def test_select_people_drops_already_associated_person_with_reason_before_the_cap():
    known_contacts = [{"firstname": "Jamie", "lastname": "Fox"}]
    people = [
        {"firstname": "Jamie", "lastname": "Fox", "jobtitle": "Director"},
        {"firstname": "Alex", "lastname": "Nguyen", "jobtitle": "Director"},
        {"firstname": "Sam", "lastname": "Lee", "jobtitle": "Board Member"},
        {"firstname": "Robin", "lastname": "Chen", "jobtitle": "Chairperson"},
    ]

    selection = suggest_contacts.select_people(
        people, FAMILY_LIST, chosen_families=["board"], known_contacts=known_contacts
    )

    selected_names = {(p["firstname"], p["lastname"]) for p in selection["selected"]}
    assert ("Jamie", "Fox") not in selected_names
    assert selected_names == {("Alex", "Nguyen"), ("Sam", "Lee"), ("Robin", "Chen")}

    dropped_for_jamie = [
        d for d in selection["dropped"] if d["person"]["firstname"] == "Jamie"
    ]
    assert len(dropped_for_jamie) == 1
    assert dropped_for_jamie[0]["reason"] == "already_associated"

    # The per-company cap still admits a full complement of the remaining people.
    records = suggest_contacts.synthesise_rows(
        _company_row(), selection["selected"],
        "https://example-club.example/sitemap.xml", per_company_cap=3,
    )
    assert len(records) == 3


def test_select_people_does_not_drop_an_ambiguous_near_match():
    known_contacts = [{"firstname": "Jamie", "lastname": "Foxx"}]  # different spelling
    people = [{"firstname": "Jamie", "lastname": "Fox", "jobtitle": "Director"}]

    selection = suggest_contacts.select_people(
        people, FAMILY_LIST, chosen_families=["board"], known_contacts=known_contacts
    )

    assert len(selection["selected"]) == 1


def test_select_people_dedupe_is_case_and_whitespace_insensitive_exact_match_only():
    known_contacts = [{"firstname": "  jamie ", "lastname": "FOX"}]
    people = [{"firstname": "Jamie", "lastname": "Fox", "jobtitle": "Director"}]

    selection = suggest_contacts.select_people(
        people, FAMILY_LIST, chosen_families=["board"], known_contacts=known_contacts
    )

    assert selection["selected"] == []
    assert selection["dropped"][0]["reason"] == "already_associated"


def test_partition_for_dispatch_is_a_thin_call_to_hold_emailless():
    rows = [
        {"firstname": "Jamie", "lastname": "Fox", "company": "Example Racing Club"},
        {"firstname": "Alex", "lastname": "Nguyen", "company": "Example Racing Club",
         "email": "alex@example.com"},
    ]

    sendable, held = suggest_contacts.partition_for_dispatch(rows)
    expected_sendable, expected_held = extraction.hold_emailless(rows)

    assert sendable == expected_sendable
    assert held == expected_held
    assert len(held) == 1
    assert held[0]["row"]["firstname"] == "Jamie"
    assert sendable == [rows[1]]


def test_suggest_contacts_has_no_branch_keyed_on_a_suggestion_origin_flag():
    source = SUGGEST_CONTACTS_PATH.read_text(encoding="utf-8")
    for forbidden in ("is_suggestion", "suggestion_origin", "from_suggestion"):
        assert forbidden not in source.casefold()


# =====================================================================================
# Gap closure (62-06) — CR-01/WR-01: synthesise_rows' cap guard and agreed_cap()
# =====================================================================================

FIVE_PEOPLE = [
    {"firstname": f"Person{i}", "lastname": "Lee", "jobtitle": "Director"}
    for i in range(5)
]


def test_synthesise_rows_refuses_a_none_cap_rather_than_uncapping():
    with pytest.raises(suggest_contacts.CapRefused):
        suggest_contacts.synthesise_rows(
            _company_row(), FIVE_PEOPLE,
            "https://example-club.example/sitemap.xml", per_company_cap=None,
        )


def test_synthesise_rows_refuses_a_negative_cap_rather_than_truncating_the_wrong_end():
    with pytest.raises(suggest_contacts.CapRefused):
        suggest_contacts.synthesise_rows(
            _company_row(), FIVE_PEOPLE,
            "https://example-club.example/sitemap.xml", per_company_cap=-1,
        )


def test_synthesise_rows_refuses_a_string_cap():
    with pytest.raises(suggest_contacts.CapRefused):
        suggest_contacts.synthesise_rows(
            _company_row(), FIVE_PEOPLE,
            "https://example-club.example/sitemap.xml", per_company_cap="2",
        )


def test_synthesise_rows_refuses_a_bool_cap():
    with pytest.raises(suggest_contacts.CapRefused):
        suggest_contacts.synthesise_rows(
            _company_row(), FIVE_PEOPLE,
            "https://example-club.example/sitemap.xml", per_company_cap=True,
        )


def test_synthesise_rows_zero_cap_is_legal_and_returns_no_rows():
    records = suggest_contacts.synthesise_rows(
        _company_row(), FIVE_PEOPLE,
        "https://example-club.example/sitemap.xml", per_company_cap=0,
    )
    assert records == []


def test_agreed_cap_returns_chosen_cap_when_under_priced_cap():
    figures = {"suggestion_allowance": {"priced_cap": 3}}
    assert suggest_contacts.agreed_cap(2, figures) == 2


def test_agreed_cap_returns_chosen_cap_when_equal_to_priced_cap():
    figures = {"suggestion_allowance": {"priced_cap": 3}}
    assert suggest_contacts.agreed_cap(3, figures) == 3


def test_agreed_cap_refuses_a_chosen_cap_above_the_priced_cap_naming_both_numbers():
    figures = {"suggestion_allowance": {"priced_cap": 3}}
    with pytest.raises(suggest_contacts.CapRefused) as excinfo:
        suggest_contacts.agreed_cap(5, figures)
    message = str(excinfo.value)
    assert "3" in message
    assert "5" in message


def test_agreed_cap_refuses_when_suggestion_allowance_is_none():
    with pytest.raises(suggest_contacts.CapRefused):
        suggest_contacts.agreed_cap(2, {"suggestion_allowance": None})


def test_agreed_cap_refuses_when_suggestion_allowance_is_absent():
    with pytest.raises(suggest_contacts.CapRefused):
        suggest_contacts.agreed_cap(2, {})


@pytest.mark.parametrize("bad_chosen_cap", [None, 0, -1, True])
def test_agreed_cap_refuses_a_malformed_chosen_cap(bad_chosen_cap):
    figures = {"suggestion_allowance": {"priced_cap": 3}}
    with pytest.raises(suggest_contacts.CapRefused):
        suggest_contacts.agreed_cap(bad_chosen_cap, figures)


# =====================================================================================
# Gap closure (62-07, G-62-1) — a company recorded with a BARE domain (measured live on
# this portal at 83.5% of companies-with-a-website) must reach a fetchable, host-bound
# ladder through BOTH discovery_plan and next_candidates. Every fixture below is a bare
# domain: today's suite has none, which is exactly how this shipped broken.
# =====================================================================================

from urllib.parse import urlsplit  # noqa: E402 — grouped with this gap-closure section


def test_bare_domain_discovery_plan_is_host_bound_and_sitemap_only():
    plan = suggest_contacts.discovery_plan({
        "row_id": "c1", "name": "Bunbury Turf Club",
        "website": "bunburyturfclub.com.au", "num_associated_contacts": 0,
    })
    assert plan["host"] == "bunburyturfclub.com.au"
    assert plan["pasted_url"] == "https://bunburyturfclub.com.au"
    urls = [c["url"] for c in plan["candidates"]]
    assert urls == [
        "https://bunburyturfclub.com.au/sitemap.xml",
        "https://bunburyturfclub.com.au/wp-sitemap.xml",
    ]


def test_bare_domain_discovery_plan_candidates_have_no_empty_authority():
    plan = suggest_contacts.discovery_plan({
        "row_id": "c1", "name": "Bunbury Turf Club",
        "website": "bunburyturfclub.com.au", "num_associated_contacts": 0,
    })
    for candidate in plan["candidates"]:
        assert urlsplit(candidate["url"]).netloc == "bunburyturfclub.com.au"


def test_bare_domain_with_www_prefix_survives_verbatim():
    plan = suggest_contacts.discovery_plan({
        "row_id": "c2", "name": "Alice Springs Turf Club",
        "website": "www.alicespringsturfclub.org.au", "num_associated_contacts": 0,
    })
    assert plan["host"] == "www.alicespringsturfclub.org.au"


@pytest.mark.parametrize("scheme_bearing_value", [
    "https://bunburyturfclub.com.au",
    "https://www.bunburyturfclub.com.au/",
    "https://gctc.com.au/board-of-directors/",
])
def test_scheme_bearing_website_is_a_byte_identical_no_op(scheme_bearing_value):
    row = {
        "row_id": "c3", "name": "Example", "website": scheme_bearing_value,
        "num_associated_contacts": 0,
    }
    assert suggest_contacts.discovery_plan(row) == url_fallback.plan_ladder(scheme_bearing_value)


def test_scheme_bearing_wordpress_url_still_leads_with_its_rest_rung():
    row = {
        "row_id": "c3", "name": "GCTC",
        "website": "https://gctc.com.au/board-of-directors/",
        "num_associated_contacts": 0,
    }
    plan = suggest_contacts.discovery_plan(row)
    assert plan["candidates"][0]["url"] == (
        "https://gctc.com.au/wp-json/wp/v2/pages?slug=board-of-directors"
    )


def test_next_candidates_second_call_site_accepts_a_same_host_sitemap_url_for_a_bare_domain():
    company_row = {"row_id": "c1", "website": "bunburyturfclub.com.au"}
    result = suggest_contacts.next_candidates(
        company_row, attempts=[], sitemap_urls=["https://bunburyturfclub.com.au/board/"]
    )
    assert result["accepted"] == ["https://bunburyturfclub.com.au/board/"]
    assert result["refused"] == []


def test_next_candidates_bare_domain_budget_threading_is_unaffected():
    company_row = {"row_id": "c1", "website": "bunburyturfclub.com.au"}
    attempts = [{"url": f"u{i}", "outcome": "empty"} for i in range(4)]
    result = suggest_contacts.next_candidates(
        company_row, attempts, ["https://bunburyturfclub.com.au/board/"]
    )
    assert result["budget_remaining"] == 1


@pytest.mark.parametrize("unusable_value", [
    "linkedin.com/company/futsal-australia",
    "unknown",
])
def test_unusable_recorded_value_takes_the_documented_no_candidates_path(unusable_value):
    row = {"row_id": "c4", "name": "Mystery", "website": unusable_value,
           "num_associated_contacts": 0}
    plan = suggest_contacts.discovery_plan(row)
    assert plan["candidates"] == []
    assert any(unusable_value in note for note in plan["notes"])

    with pytest.raises(ValueError) as excinfo:
        suggest_contacts.next_candidates(row, attempts=[], sitemap_urls=[])
    assert unusable_value in str(excinfo.value)


def test_discovery_plan_with_no_website_or_domain_is_unchanged():
    row = {"row_id": "c5", "name": "No Site Co", "num_associated_contacts": 0}
    plan = suggest_contacts.discovery_plan(row)
    assert plan == {
        "pasted_url": None,
        "host": None,
        "cap": url_fallback.MAX_FOLLOWUP_FETCHES,
        "candidates": [],
        "notes": [
            "this company has no usable website or domain -- cannot build a "
            "discovery ladder"
        ],
    }
