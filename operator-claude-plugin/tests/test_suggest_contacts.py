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
import search_fallback
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
# role_classify.classify_title — partial, entity-aware, longest-wins (62-09 Task 1)
#
# Local fixture — the RULE is under test here, not the shipped YAML (that's Task 2).
# =====================================================================================

PARTIAL_FAMILY_LIST = [
    {"label": "board", "members": ["Director", "Board Of Directors"]},
    {"label": "secretary", "members": ["Secretary"]},
    {"label": "president", "members": ["President"]},
    {"label": "vice-president", "members": ["Vice President"]},
    {"label": "gm", "members": ["General Manager"]},
    {"label": "track", "members": ["Track Manager"]},
    {"label": "finance", "members": ["Finance and Admin Officer"]},
]

# Same families, order reversed — longest-wins must not depend on YAML position.
PARTIAL_FAMILY_LIST_REVERSED = list(reversed(PARTIAL_FAMILY_LIST))


def test_classify_title_partial_operator_named_cases():
    assert role_classify.classify_title("Secretary Manager", PARTIAL_FAMILY_LIST) == "secretary"
    assert role_classify.classify_title("Board Of Directors", PARTIAL_FAMILY_LIST) == "board"


def test_classify_title_never_sweeps_track_manager_into_general_manager():
    # THE OVER-MATCH NEGATIVE. Assert the returned label explicitly, not merely non-None.
    result = role_classify.classify_title("Track Manager", PARTIAL_FAMILY_LIST)
    assert result == "track"
    assert result != "gm"


def test_classify_title_longest_match_wins_order_independent():
    assert role_classify.classify_title("Vice President", PARTIAL_FAMILY_LIST) == "vice-president"
    # Re-assert with family order reversed — must not depend on YAML ordering.
    assert role_classify.classify_title("Vice President", PARTIAL_FAMILY_LIST_REVERSED) == "vice-president"


def test_classify_title_normalises_entities_ampersand_and_case_together():
    for title in (
        "Finance &amp; Admin Officer",
        "Finance & Admin Officer",
        "finance and admin officer",
    ):
        assert role_classify.classify_title(title, PARTIAL_FAMILY_LIST) == "finance"


def test_classify_title_does_not_match_tail_of_a_longer_word():
    family_list = [{"label": "board", "members": ["Director"]}]
    assert role_classify.classify_title("Directorate Assistant", family_list) is None
    assert role_classify.classify_title("Directors", family_list) is None


def test_classify_title_unchanged_contracts_still_hold_under_new_rule():
    assert role_classify.classify_title("", PARTIAL_FAMILY_LIST) is None
    assert role_classify.classify_title(None, PARTIAL_FAMILY_LIST) is None
    assert role_classify.classify_title("Head Chef", PARTIAL_FAMILY_LIST) is None


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


# --- gap closure (62-10, G-62-2): apex and www are one host, at the real seam -----------
#
# next_candidates routes through url_fallback.filter_candidates unmodified (Decision 1), so
# these are seam-level fixtures for the same shared fix, not a second implementation.


def test_next_candidates_accepts_the_recorded_www_companys_own_apex_sitemap():
    company_row = _company_row(row_id="c1", website="www.gladstoneturfclub.com.au")
    result = suggest_contacts.next_candidates(
        company_row, attempts=[],
        sitemap_urls=["https://gladstoneturfclub.com.au/dt_staff-sitemap.xml"],
    )
    assert result["accepted"] == ["https://gladstoneturfclub.com.au/dt_staff-sitemap.xml"]
    assert result["refused"] == []


def test_next_candidates_accepts_the_reverse_direction_recorded_apex_site_serves_www():
    company_row = _company_row(row_id="c1", website="gladstoneturfclub.com.au")
    result = suggest_contacts.next_candidates(
        company_row, attempts=[],
        sitemap_urls=["https://www.gladstoneturfclub.com.au/dt_staff-sitemap.xml"],
    )
    assert result["accepted"] == ["https://www.gladstoneturfclub.com.au/dt_staff-sitemap.xml"]
    assert result["refused"] == []


def test_next_candidates_still_refuses_the_attacker_host_naming_both_hosts():
    company_row = _company_row(row_id="c1", website="www.gladstoneturfclub.com.au")
    attacker = "https://evil.gladstoneturfclub.com.au.attacker.tld/x"
    result = suggest_contacts.next_candidates(company_row, attempts=[], sitemap_urls=[attacker])
    assert result["accepted"] == []
    reason = result["refused"][0]["reason"]
    assert "evil.gladstoneturfclub.com.au.attacker.tld" in reason
    assert "www.gladstoneturfclub.com.au" in reason


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


# =====================================================================================
# Gap closure (62-12, G-62-7) — operator ruling 2026-09-04: "the email domain should be
# related to the company." Replaces the removed
# test_partition_for_dispatch_is_a_thin_call_to_hold_emailless, which asserted the exact
# property this plan removes (partition_for_dispatch == hold_emailless, unconditionally).
# =====================================================================================

def test_partition_for_dispatch_agrees_with_hold_emailless_when_every_email_is_on_its_own_company_domain():
    """The replacement property: when every row's email is on its own company's
    domain, partition_for_dispatch's split matches hold_emailless's -- the new rule
    adds no extra holds it does not need to."""
    rows = [
        {"firstname": "Jamie", "lastname": "Fox", "company": "Example Racing Club"},
        {"firstname": "Alex", "lastname": "Nguyen", "company": "Example Racing Club",
         "email": "alex@example-racing-club.example"},
    ]
    company_domains = {"Example Racing Club": "https://example-racing-club.example"}

    sendable, held = suggest_contacts.partition_for_dispatch(rows, company_domains)
    expected_sendable, expected_held = extraction.hold_emailless(rows)

    assert sendable == expected_sendable
    assert [h["row"] for h in held] == [h["row"] for h in expected_held]
    assert held[0]["reason_code"] == "no_email"
    assert held[0]["reason"] == expected_held[0]["reason"]


def test_partition_for_dispatch_holds_the_stranger_hold_emailless_alone_would_send():
    """The measured defect, pinned as a fixture: Craig Smith's row has an email, so
    hold_emailless ALONE reports it sendable. partition_for_dispatch holds it because
    that email's domain belongs to a US insurer, not the club whose committee page
    named him."""
    rows = [{"firstname": "Craig", "lastname": "Smith", "company": "The Roma Turf Club",
             "email": "craig.smith@thehartford.com"}]
    company_domains = {"The Roma Turf Club": "romaturfclub.com.au"}

    # hold_emailless alone still returns the stranger as sendable -- proves
    # contact-upload and enrich-before-ingest (which call hold_emailless directly, never
    # partition_for_dispatch) are unaffected by this rule.
    alone_sendable, alone_held = extraction.hold_emailless(rows)
    assert alone_sendable == rows
    assert alone_held == []

    sendable, held = suggest_contacts.partition_for_dispatch(rows, company_domains)
    assert sendable == []
    assert len(held) == 1
    assert held[0]["reason_code"] == "email_domain_mismatch"
    assert held[0]["reason"] == (
        "email domain thehartford.com does not match romaturfclub.com.au"
    )


@pytest.mark.parametrize("email,website,expected_relation", [
    ("craig.smith@thehartford.com", "romaturfclub.com.au", "mismatch"),
    ("markoaten@oatens.com", "lismoreturfclub.com.au", "mismatch"),
    # Decision 3's accepted cost: this is plausibly the one genuinely correct address
    # in the round, and the strict rule holds it anyway (.com vs .com.au).
    ("kdaniel@lismoreturfclub.com", "lismoreturfclub.com.au", "mismatch"),
    ("kdaniel@lismoreturfclub.com.au", "lismoreturfclub.com.au", "related"),
    ("staff@mail.romaturfclub.com.au", "www.romaturfclub.com.au", "related"),
    # the send-direction sibling of 62-10's fetch-guard suffix trap
    ("x@romaturfclub.com.au.attacker.tld", "romaturfclub.com.au", "mismatch"),
])
def test_email_domain_relation_pins_the_measured_fixtures(email, website, expected_relation):
    assert suggest_contacts.email_domain_relation(email, website) == expected_relation


def test_email_domain_relation_tests_freemail_before_relatedness():
    """A gmail address must never be reported as a mismatch -- freemail is checked
    first, so the held pile can tell strangers from personal mailboxes at a glance."""
    assert suggest_contacts.email_domain_relation(
        "someone@gmail.com", "romaturfclub.com.au") == "freemail"


def test_email_domain_relation_company_domain_unknown():
    assert suggest_contacts.email_domain_relation(
        "someone@example.com", None) == "company_domain_unknown"
    assert suggest_contacts.email_domain_relation(
        "someone@example.com",
        "https://www.linkedin.com/company/x") == "company_domain_unknown"


def test_email_domain_relation_no_email():
    assert suggest_contacts.email_domain_relation("", "romaturfclub.com.au") == "no_email"
    assert suggest_contacts.email_domain_relation(None, "romaturfclub.com.au") == "no_email"


def test_partition_for_dispatch_labels_freemail_distinctly_from_mismatch():
    rows = [{"firstname": "Pat", "lastname": "Lee", "company": "The Roma Turf Club",
             "email": "pat.lee@gmail.com"}]
    company_domains = {"The Roma Turf Club": "romaturfclub.com.au"}

    sendable, held = suggest_contacts.partition_for_dispatch(rows, company_domains)
    assert sendable == []
    assert held[0]["reason_code"] == "email_domain_freemail"
    assert "does not match" not in held[0]["reason"]
    assert "gmail.com" in held[0]["reason"]


def test_partition_for_dispatch_holds_when_the_company_has_no_usable_recorded_domain():
    rows = [{"firstname": "Pat", "lastname": "Lee", "company": "Unknown Co",
             "email": "pat.lee@example.com"}]

    sendable, held = suggest_contacts.partition_for_dispatch(rows, {})
    assert sendable == []
    assert held[0]["reason_code"] == "company_domain_unknown"


def test_partition_for_dispatch_index_discipline_across_both_passes():
    """Every held entry's index is its ORIGINAL position in `rows`, for both the
    no-email pass and the relatedness pass -- never a position renumbered against the
    sendable sublist."""
    rows = [
        {"firstname": "A", "lastname": "One", "company": "Acme"},  # no email -> held@0
        {"firstname": "B", "lastname": "Two", "company": "Acme",
         "email": "b@acme.example"},  # related -> sendable
        {"firstname": "C", "lastname": "Three", "company": "Acme",
         "email": "c@stranger.example"},  # mismatch -> held@2
    ]
    company_domains = {"Acme": "acme.example"}

    sendable, held = suggest_contacts.partition_for_dispatch(rows, company_domains)
    assert sendable == [rows[1]]
    assert [h["index"] for h in held] == [0, 2]
    assert held[0]["reason_code"] == "no_email"
    assert held[1]["reason_code"] == "email_domain_mismatch"


def test_partition_for_dispatch_requires_company_domains_with_no_default():
    """Decision 4: an optional company_domains defaulting to None would be a
    one-keyword bypass of the operator ruling."""
    import inspect
    params = list(inspect.signature(suggest_contacts.partition_for_dispatch).parameters.values())
    assert len(params) == 2
    assert params[1].default is inspect.Parameter.empty


# =====================================================================================
# Quick 260905-ad2 — a company may carry MORE THAN ONE domain (D-ad2-01..05). The
# per-domain rule is byte-identical to today's; only the number of domains it is
# applied to changes. Roma Turf Club: site `romaturfclub.com.au`, published contact
# address `INFO@romaturfclub.org.au` — same organisation, two registrable domains.
# =====================================================================================

ROMA_BOTH = ["romaturfclub.com.au", "romaturfclub.org.au"]


def test_email_domain_relation_relates_an_alternate_domain_the_operator_supplied():
    """D-ad2-01/02: the Roma committee address passes WITH the alternate present."""
    assert suggest_contacts.email_domain_relation(
        "INFO@romaturfclub.org.au", ROMA_BOTH) == "related"


def test_email_domain_relation_still_holds_the_alternate_when_it_was_not_supplied():
    """The widening comes ONLY from what the operator supplied, never from the rule --
    and the one-element LIST form adds no leniency of its own over the bare string."""
    assert suggest_contacts.email_domain_relation(
        "INFO@romaturfclub.org.au", "romaturfclub.com.au") == "mismatch"
    assert suggest_contacts.email_domain_relation(
        "INFO@romaturfclub.org.au", ["romaturfclub.com.au"]) == "mismatch"


def test_email_domain_relation_holds_the_stranger_with_or_without_the_alternate():
    """The refusal that prompted the ruling survives untouched: `thehartford.com` is a
    US insurer, and a second Roma domain does not make it Roma's."""
    assert suggest_contacts.email_domain_relation(
        "craig.smith@thehartford.com", ROMA_BOTH) == "mismatch"
    assert suggest_contacts.email_domain_relation(
        "craig.smith@thehartford.com", "romaturfclub.com.au") == "mismatch"


def test_email_domain_relation_suffix_trap_is_refused_by_every_member_of_the_set():
    """T-ad2-01, direction 1 (send-direction): refused by EVERY member, not merely by
    the first one checked."""
    assert suggest_contacts.email_domain_relation(
        "x@romaturfclub.com.au.attacker.tld", ROMA_BOTH) == "mismatch"


def test_email_domain_relation_stays_fail_closed_in_the_reverse_direction():
    """T-ad2-01, direction 2: a company recorded only at a SUBDOMAIN does not relate an
    apex email. Single-directional, exactly as before."""
    assert suggest_contacts.email_domain_relation(
        "staff@romaturfclub.com.au", ["mail.romaturfclub.com.au"]) == "mismatch"


def test_email_domain_relation_relates_a_subdomain_of_an_alternate():
    assert suggest_contacts.email_domain_relation(
        "staff@mail.romaturfclub.org.au", ROMA_BOTH) == "related"


def test_email_domain_relation_reports_unknown_for_a_set_with_no_usable_domain():
    """D-ad2-04 / T-ad2-03: an all-unusable list and an empty list are
    `company_domain_unknown`, NEVER `mismatch` -- the assertion that proves a list never
    reaches `enrichment._clean_domain`'s `str(raw)` and reads as a pseudo-domain."""
    assert suggest_contacts.email_domain_relation(
        "someone@example.com", ["https://www.linkedin.com/company/x", ""]
    ) == "company_domain_unknown"
    assert suggest_contacts.email_domain_relation(
        "someone@example.com", []) == "company_domain_unknown"


def test_email_domain_relation_normalises_and_dedupes_the_set():
    """`_clean_domain` per member, order preserved, duplicates collapsed."""
    messy = ["romaturfclub.com.au", "https://www.ROMATURFCLUB.com.au/",
             "romaturfclub.org.au"]
    assert suggest_contacts.email_domain_relation(
        "info@romaturfclub.org.au", messy) == "related"
    reason = suggest_contacts._relation_reason(
        "mismatch", "craig.smith@thehartford.com", messy)
    assert reason == (
        "email domain thehartford.com does not match "
        "romaturfclub.com.au or romaturfclub.org.au"
    )


def test_partition_for_dispatch_reason_names_every_domain_that_was_compared():
    """D-ad2-05: two or more domains join with ` or `; ONE domain is today's string
    byte for byte, which is why the join only engages at two."""
    rows = [{"firstname": "Craig", "lastname": "Smith", "company": "The Roma Turf Club",
             "email": "craig.smith@thehartford.com"}]

    _, held_two = suggest_contacts.partition_for_dispatch(
        rows, {"The Roma Turf Club": ROMA_BOTH})
    assert held_two[0]["reason"] == (
        "email domain thehartford.com does not match "
        "romaturfclub.com.au or romaturfclub.org.au"
    )

    _, held_one = suggest_contacts.partition_for_dispatch(
        rows, {"The Roma Turf Club": ["romaturfclub.com.au"]})
    assert held_one[0]["reason"] == (
        "email domain thehartford.com does not match romaturfclub.com.au"
    )


def test_partition_for_dispatch_roma_sends_only_with_the_alternate_supplied():
    """Same rows, same rule, different supplied facts."""
    rows = [
        {"firstname": "Info", "lastname": "Desk", "company": "The Roma Turf Club",
         "email": "INFO@romaturfclub.org.au"},
        {"firstname": "Craig", "lastname": "Smith", "company": "The Roma Turf Club",
         "email": "craig.smith@thehartford.com"},
    ]

    sendable, held = suggest_contacts.partition_for_dispatch(
        rows, {"The Roma Turf Club": ROMA_BOTH})
    assert sendable == [rows[0]]
    assert [h["index"] for h in held] == [1]
    assert held[0]["reason_code"] == "email_domain_mismatch"

    sendable, held = suggest_contacts.partition_for_dispatch(
        rows, {"The Roma Turf Club": "romaturfclub.com.au"})
    assert sendable == []
    assert [h["reason_code"] for h in held] == [
        "email_domain_mismatch", "email_domain_mismatch"]

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


# =====================================================================================
# quick task 260904-5sd — the source-tier seam into synthesise_rows
#
# The tier rides `provenance`, never the row: `synthesise_rows` asserts every row key is
# canonical and `write_dispatch_csv` raises on a non-canonical key — the same constraint
# that forced `source_by_field` to be request-level (CLAUDE.md §13.0.2).
# =====================================================================================

def _tier_people():
    return [{"firstname": "Jamie", "lastname": "Fox", "jobtitle": "Director"}]


def test_synthesise_rows_without_a_source_tier_is_byte_identical_to_today():
    """Every existing call site is unaffected: no extra provenance key, same input
    literal. The new keyword is a no-op unless it is passed."""
    records = suggest_contacts.synthesise_rows(
        _company_row(), _tier_people(), "https://example-club.example/board",
        per_company_cap=2,
    )
    assert records[0]["provenance"] == {
        "input": "suggest_contacts_ladder",
        "locator": "https://example-club.example/board",
    }


def test_synthesise_rows_with_a_source_tier_declares_the_search_input_and_the_tier():
    records = suggest_contacts.synthesise_rows(
        _company_row(), _tier_people(), "https://www.linkedin.com/in/jamie-fox",
        per_company_cap=2, source_tier=2,
    )
    assert records[0]["provenance"] == {
        "input": "suggest_contacts_web_search",
        "locator": "https://www.linkedin.com/in/jamie-fox",
        "source_tier": 2,
    }


@pytest.mark.parametrize("bad_tier", [True, "2", 0, 4, 9, 1.0])
def test_an_unknown_source_tier_refuses_rather_than_downgrading_to_a_ladder_provenance(
        bad_tier):
    """A silent downgrade to the ladder provenance would bypass the D-5sd-05 gate
    entirely — the record would read as self-attested and send."""
    with pytest.raises(ValueError) as excinfo:
        suggest_contacts.synthesise_rows(
            _company_row(), _tier_people(), "https://racenet.example/committee",
            per_company_cap=2, source_tier=bad_tier,
        )
    assert repr(bad_tier) in str(excinfo.value)


def test_extraction_validate_still_accepts_a_record_carrying_the_extra_provenance_key():
    """`extraction.validate` checks provenance for `input` and `locator` PRESENCE only,
    so the extra key travels safely and is never written to HubSpot as a property."""
    records = suggest_contacts.synthesise_rows(
        _company_row(), _tier_people(), "https://www.linkedin.com/in/jamie-fox",
        per_company_cap=2, source_tier=2,
    )
    result = extraction.validate(suggest_contacts.round_artifact(records))
    assert result.rejected == []
    assert result.accepted[0]["provenance"]["source_tier"] == 2


def test_the_tier_gate_and_the_waterfall_gate_are_independent_and_both_must_hold():
    """The same person, the same successful merge, the same related-domain email — held
    at tier 3, sendable at tier 2 (D-5sd-01 + D-5sd-05). Drives the REAL
    `partition_for_dispatch` and the REAL `search_fallback.hold_weak_sources`, so drift
    in either module's `"suggest_contacts_web_search"` literal fails here."""
    company = _company_row()
    records = []
    for tier, firstname in ((2, "Jamie"), (3, "Robin")):
        people = [{"firstname": firstname, "lastname": "Fox", "jobtitle": "Director"}]
        locator = (
            "https://www.linkedin.com/in/jamie-fox" if tier == 2
            else "https://racenet.example/2019/committee"
        )
        records.extend(suggest_contacts.synthesise_rows(
            company, people, locator, per_company_cap=2, source_tier=tier))

    # The join key is minted once at the batch level, before either gate runs.
    minted = suggest_contacts.mint_row_ids(records)
    records = minted["records"]
    for record in records:
        record["row"]["email"] = (
            f"{record['row']['firstname'].lower()}@example-club.example"
        )

    company_domains = {company["name"]: company["website"]}
    sendable, held = suggest_contacts.partition_for_dispatch(
        [record["row"] for record in records], company_domains)
    # Gate 1 alone would send BOTH: the waterfall confirmed each with a related domain.
    assert {row["firstname"] for row in sendable} == {"Jamie", "Robin"}
    assert held == []

    sendable, held = search_fallback.hold_weak_sources(records, sendable, held)
    assert [row["firstname"] for row in sendable] == ["Jamie"]
    assert len(held) == 1
    assert held[0]["row"]["firstname"] == "Robin"
    assert held[0]["reason_code"] == "search_source_not_strong"
    assert "https://racenet.example/2019/committee" in held[0]["reason"]


def test_a_ladder_sourced_record_passes_the_new_gate_unchanged():
    """The no-op direction: a round with no search-sourced record behaves exactly as it
    did before this task."""
    company = _company_row()
    records = suggest_contacts.mint_row_ids(suggest_contacts.synthesise_rows(
        company, _tier_people(), "https://example-club.example/board",
        per_company_cap=2))["records"]
    records[0]["row"]["email"] = "jamie@example-club.example"

    company_domains = {company["name"]: company["website"]}
    sendable, held = suggest_contacts.partition_for_dispatch(
        [record["row"] for record in records], company_domains)
    after_sendable, after_held = search_fallback.hold_weak_sources(records, sendable, held)
    assert after_sendable == sendable
    assert after_held == held


def test_no_candidates_still_returns_give_up_messages_text_verbatim():
    """The docstring changed; the BEHAVIOUR did not. This task adds no branch inside
    `no_candidates` — the eligibility question is asked by the caller, before it decides
    whether the round looks anywhere else."""
    company_row = _company_row()
    attempts = [{"url": "https://example-club.example/sitemap.xml", "outcome": "empty",
                 "disposition": "empty"}]
    result = suggest_contacts.no_candidates(
        company_row, "https://example-club.example/board", attempts)
    assert result["outcome"] == "no_candidates_found"
    assert result["reason"] == url_fallback.give_up_message(
        "https://example-club.example/board", attempts)
