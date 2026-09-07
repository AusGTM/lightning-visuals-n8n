"""Composition test for Phase 62 Plan 05 Task 2, amended by Plan 06 Task 2 (gap closure,
the sequence-coverage ratchet).

Registers the census identity (`test_skill_sequence_coverage.py`'s `COVERED`) for
`skills/suggest-contacts/SKILL.md`'s one documented python block: the round's real join,
end to end, offline -- `eligibility` output feeding `discovery_plan`; the discovered
people feeding `select_people` with the family list `load_families` supplies; the
survivors' cap resolved through `agreed_cap()` (its RETURN VALUE, not a literal) before
feeding `synthesise_rows`; stage-2 fields merging onto those rows; and
`partition_for_dispatch` splitting them before `extraction.validate()` runs exactly once
per sendable row.

Synthetic fixtures throughout: an `example`-suffixed host, invented names, no real
discovered person committed anywhere in this file.
"""
import pytest

import chunking
import enrichment
import extraction
import preingest
import role_classify
import search_fallback
import suggest_contacts
import url_fallback

FAMILY_LABEL = "Head of Broadcast"  # a real label in the shipped generic-fallback
# vocabulary (operator-claude-plugin/config/role_vocabulary.yaml) -- chosen so this test
# calls the real role_classify.load_families() rather than a synthetic family list, the
# same function the documented sequence names.


def _company_row(row_id, num_associated_contacts):
    return {
        "row_id": row_id,
        "name": f"Example Company {row_id}",
        "website": "https://example-club.example/board",
        "num_associated_contacts": num_associated_contacts,
    }


def test_a_company_marked_has_contacts_never_reaches_discovery_plan():
    """The first join: `eligibility` output gates which companies `discovery_plan` is
    ever called for. A company already carrying contacts is filtered out BEFORE
    discovery_plan runs -- never given a discovery attempt, never appearing in the set
    of companies a discovery_plan call was made for."""
    company_with_contacts = _company_row("has-1", num_associated_contacts=5)
    company_eligible = _company_row("elig-1", num_associated_contacts=0)
    company_rows = [company_with_contacts, company_eligible]

    verdicts = suggest_contacts.eligibility(company_rows)
    eligible_rows = [
        row for row, verdict in zip(company_rows, verdicts)
        if verdict["verdict"] == suggest_contacts.ELIGIBLE
    ]
    assert eligible_rows == [company_eligible]

    discovery_plans_built_for = []
    for row, verdict in zip(company_rows, verdicts):
        if verdict["verdict"] != suggest_contacts.ELIGIBLE:
            continue  # a has_contacts (or unknown) company never reaches discovery_plan
        suggest_contacts.discovery_plan(row)
        discovery_plans_built_for.append(row["row_id"])

    assert discovery_plans_built_for == ["elig-1"]
    assert "has-1" not in discovery_plans_built_for


def _attempt(url, disposition):
    """One `attempts` entry as `suggest-contacts/SKILL.md` step 5's transcription table
    describes it: the untouched free-prose `outcome` plus the typed `disposition` quick
    task 260904-5sd added, which is the ONLY thing `eligible_after_ladder` reads."""
    return {"url": url, "outcome": "the model's own prose, never branched on",
            "disposition": disposition}


def test_the_documented_round_pipeline_drives_its_real_joins_end_to_end():
    """The whole documented sequence from `skills/suggest-contacts/SKILL.md`'s python
    block, over three eligible companies whose ladders end three different ways:
    `eligibility` -> `discovery_plan` -> `eligible_after_ladder` -> (`rank_results` ->
    the search-sourced people, when eligible) -> (role list from) `load_families` ->
    `select_people` -> `synthesise_rows` -> `mint_row_ids` -> stage-2 merge ->
    `rejoin_enriched` -> `partition_for_dispatch` -> `hold_weak_sources` ->
    `extraction.validate()` once per sendable row.

    Six named joins, each asserted directly:
      1. a company marked has_contacts never reaches discovery_plan (see the test above;
         re-proven here inline against this test's own company set)
      2. a person dropped by select_people never appears in a synthesised row
      3. a row in the held half never appears in the dispatch set (never validated)
      4. a ladder carrying a `refused` disposition NEVER reaches the search path, and
         produces no search-sourced record at all (D-5sd-04)
      5. a clean-but-empty ladder DOES reach it, and its tier-2 person becomes sendable
         only once the merge fills a related-domain email (D-5sd-01: both gates)
      6. a tier-3 person is HELD despite the identically successful merge, with the
         source URL in the reason (D-5sd-05: the two gates are independent)
    """
    company_refused = _company_row("refused-1", num_associated_contacts=0)
    company_tier2 = _company_row("tier2-1", num_associated_contacts=0)
    company_tier3 = _company_row("tier3-1", num_associated_contacts=0)
    company_with_contacts = _company_row("has-2", num_associated_contacts=3)
    company_rows = [
        company_with_contacts, company_refused, company_tier2, company_tier3]

    verdicts = suggest_contacts.eligibility(company_rows)
    eligible = [
        row for row, verdict in zip(company_rows, verdicts)
        if verdict["verdict"] == suggest_contacts.ELIGIBLE
    ]
    # join 1, re-proven for this test's own fixtures
    assert eligible == [company_refused, company_tier2, company_tier3]

    vocabulary = role_classify.load_families()
    family_list = vocabulary["families"]
    assert any(family.get("label") == FAMILY_LABEL for family in family_list), (
        f"the shipped role vocabulary no longer carries {FAMILY_LABEL!r} -- update this "
        f"test's FAMILY_LABEL to a label that still exists"
    )
    chosen_families = [FAMILY_LABEL]
    figures = {"suggestion_allowance": {"priced_cap": 5}}
    per_company_cap = suggest_contacts.agreed_cap(5, figures)
    # Phase 64 Task 3: round-level, alongside per_company_cap -- the SKILL.md block
    # now resolves the walk's bar here too, never per company.
    bar = suggest_contacts.walk_bar(chosen_families, per_company_cap)

    # A refusal anywhere in a ladder; a clean empty ladder for the other two. The URLs
    # differ per company only so a failure names which one.
    attempts_by_row_id = {
        "refused-1": [_attempt("https://example-club.example/sitemap.xml", "empty"),
                      _attempt("https://example-club.example/wp-sitemap.xml", "refused")],
        "tier2-1": [_attempt("https://example-club.example/sitemap.xml", "empty")],
        "tier3-1": [_attempt("https://example-club.example/sitemap.xml", "empty")],
    }
    # What the model's own web search transcribed, per company. Real allowlisted hosts:
    # LinkedIn is tier 2, racenet.com.au is on the shipped tier-3 list.
    search_results_by_row_id = {
        "tier2-1": [{"url": "https://www.linkedin.com/in/jamie-fox"},
                    {"url": "https://random-blog.example/who-works-where"}],
        "tier3-1": [{"url": "https://racenet.com.au/2019/committee"}],
    }
    people_by_row_id = {
        "tier2-1": [
            {"firstname": "Jamie", "lastname": "Fox", "jobtitle": FAMILY_LABEL},
            {"firstname": "Alex", "lastname": "Nguyen", "jobtitle": "Receptionist"},
        ],
        "tier3-1": [{"firstname": "Robin", "lastname": "Lee", "jobtitle": FAMILY_LABEL}],
    }

    records = []
    searched_for = []
    dropped_names = set()
    for company_row in eligible:
        plan = suggest_contacts.discovery_plan(company_row)
        assert plan["candidates"], "the ladder must offer at least one candidate"
        assert plan["candidates"] == (
            url_fallback.plan_ladder(company_row["website"])["candidates"])

        attempts = attempts_by_row_id[company_row["row_id"]]
        # Phase 64 Task 3: the walk itself, driven for real. This fixture's ladder
        # never offers a same-host sitemap candidate to fetch (join 4/5/6 below are
        # about the SEARCH fallback, not the ladder walk), so `next_candidates`
        # correctly reports nothing accepted and `walk_pages` over zero folded pages
        # reports why the ladder itself is done -- `cap_exhausted` once its own
        # `attempts` have spent the whole budget, `ladder_exhausted` otherwise. This
        # is the walk's real terminal-ending join (D-64-08/D-64-11), independent of
        # `eligible_after_ladder`'s separate, attempts-keyed eligibility question
        # below.
        candidates = suggest_contacts.next_candidates(company_row, attempts, sitemap_urls=[])
        walk = suggest_contacts.walk_pages(
            [], candidates, bar, family_list, chosen_families, known_contacts=[])
        candidates = suggest_contacts.next_candidates(company_row, attempts, sitemap_urls=[])
        assert walk["people"] == []
        assert walk["ended"] in (
            suggest_contacts.WALK_CAP_EXHAUSTED, suggest_contacts.WALK_LADDER_EXHAUSTED,
        )

        # Phase 65 Task 1: the routing call, driven for real -- every company here has
        # an empty walk, so every one routes to the search fallback; the refused-1
        # company is refused at the very next gate regardless (D-65-10).
        cause_outcome = suggest_contacts.round_outcome(walk)
        assert cause_outcome["cause"] == suggest_contacts.CAUSE_NO_PEOPLE_FOUND
        assert cause_outcome["reentry"] == suggest_contacts.REENTRY_SEARCH_FALLBACK

        verdict = search_fallback.eligible_after_ladder(attempts)
        if not verdict["eligible"]:
            # join 4: a refused ladder terminates here. `no_candidates` reports
            # `give_up_message`'s own text and the round moves to the next company --
            # no search, no rank, no record.
            outcome = suggest_contacts.no_candidates(
                company_row, company_row["website"], attempts)
            assert outcome["outcome"] == "no_candidates_found"
            continue

        searched_for.append(company_row["row_id"])
        ranked = search_fallback.rank_results(
            search_results_by_row_id[company_row["row_id"]], plan["pasted_url"])
        assert len(ranked["accepted"]) == 1, (
            "only the allowlisted host may be fetched -- an unlisted one is rejected "
            "outright, never ranked last (D-5sd-02 tier 4)"
        )
        accepted = ranked["accepted"][0]

        # The people below come from a web_fetch of `accepted["url"]`, never from a
        # search snippet -- the ranker read the URL host and nothing else.
        selection = suggest_contacts.select_people(
            people_by_row_id[company_row["row_id"]], family_list, chosen_families,
            known_contacts=[])
        dropped_names.update(
            entry["person"]["firstname"] for entry in selection["dropped"])
        records.extend(suggest_contacts.synthesise_rows(
            company_row, selection["selected"], accepted["url"],
            per_company_cap=per_company_cap, source_tier=accepted["tier"]))

    # join 4, the other half: the refused company never reached the search path and
    # contributed no record at all.
    assert searched_for == ["tier2-1", "tier3-1"]
    assert len(records) == 2
    assert {record["row"]["firstname"] for record in records} == {"Jamie", "Robin"}
    # join 2: the person select_people dropped never appears in a synthesised row
    assert dropped_names == {"Alex"}
    assert "Alex" not in {record["row"]["firstname"] for record in records}
    assert [record["provenance"]["source_tier"] for record in records] == [2, 3]

    # The mint -- ONCE, over the whole accumulated batch, never per company.
    minted = suggest_contacts.mint_row_ids(records)

    # Stage 2 -- simulated response, IDENTICALLY successful for both people: each gets a
    # related-domain email from the waterfall. That is what makes joins 5 and 6 a test of
    # the SOURCE TIER rather than of the email rule.
    responses = [
        {"row_id": "row-1", "properties": {"email": "jamie.fox@example-club.example"}},
        {"row_id": "row-2", "properties": {"email": "robin.lee@example-club.example"}},
    ]
    merge_report = preingest.merge_enriched(minted["spec"]["rows"], responses)
    rejoined = suggest_contacts.rejoin_enriched(minted["records"], merge_report.rows)

    company_domains = {row["name"]: row["website"] for row in eligible}
    sendable, held = suggest_contacts.partition_for_dispatch(
        [record["row"] for record in rejoined], company_domains)
    # Gate 1 alone would send BOTH -- the waterfall confirmed each with a domain related
    # to the company that named them.
    assert {row["firstname"] for row in sendable} == {"Jamie", "Robin"}
    assert held == []

    sendable, held = search_fallback.hold_weak_sources(rejoined, sendable, held)
    # join 5: the tier-2 person survives BOTH gates.
    assert [row["firstname"] for row in sendable] == ["Jamie"]
    # join 6: the tier-3 person is held despite the same successful merge, and the
    # operator is given the source URL to judge for themselves.
    assert len(held) == 1
    assert held[0]["row"]["firstname"] == "Robin"
    assert held[0]["reason_code"] == "search_source_not_strong"
    assert "https://racenet.com.au/2019/committee" in held[0]["reason"]

    validated_count = 0
    validated_firstnames = []
    for record in rejoined:
        if record["row"] not in sendable:
            continue  # a held row never reaches extraction.validate()
        result = extraction.validate(suggest_contacts.round_artifact([record]))
        validated_count += 1
        assert result.rejected == []
        assert len(result.accepted) == 1
        assert result.accepted[0]["provenance"]["input"] == "suggest_contacts_web_search"
        validated_firstnames.append(result.accepted[0]["row"]["firstname"])

    # extraction.validate() called exactly once per sendable row
    assert validated_count == len(sendable) == 1
    assert validated_firstnames == ["Jamie"]
    # join 3: the held row (Robin) never appears in the dispatch set
    assert "Robin" not in validated_firstnames


# =====================================================================================
# Phase 64 code review CR-01/CR-02: the REAL documented per-company loop, driven with a
# growing `attempts` list and a real `next_candidates` re-invocation per fetch -- not a
# single static `candidates` dict built by hand. No test before this fix drove the loop
# with more than 2 accepted URLs, which is exactly why both defects (the premature
# `ladder_exhausted` and the dropped pasted-URL fetch) shipped with a green suite.
# =====================================================================================

_WALK_FAMILY_LIST = [{"label": "board", "members": ["Director"]}]
_WALK_CHOSEN_FAMILIES = ["board"]


def _walk_company_like_skill_md(company_row, sitemap_urls, bar, page_people_for):
    """Drives `skills/suggest-contacts/SKILL.md` step 7's per-company loop verbatim
    (post CR-01/CR-02 fix): the pasted URL is fetched first and folded into `pages`,
    then each ladder candidate is fetched in turn, with `candidates` re-derived from
    `sitemap_urls` MINUS what `pages` has already walked -- BEFORE each `walk_pages`
    call, never after.

    `page_people_for(url)` stands in for `web_fetch`. Returns `(pages,
    ladder_fetch_count, walk)`; `ladder_fetch_count` counts ladder fetches only,
    matching how CR-01's traced expected behaviour states them (the pasted URL is
    always fetched once, separately, before any ladder candidate).
    """
    plan = suggest_contacts.discovery_plan(company_row)
    pages, attempts = [], []
    candidates = suggest_contacts.next_candidates(company_row, attempts, sitemap_urls)
    accepted = list(candidates["accepted"])
    walk = {"people": [], "selected": [], "dropped": [], "scores": [], "ended": None,
            "bar": bar}

    pasted_url = plan.get("pasted_url")
    if pasted_url:
        pages.append({"url": pasted_url, "people": page_people_for(pasted_url)})
        walk = suggest_contacts.walk_pages(
            pages, candidates, bar, _WALK_FAMILY_LIST, _WALK_CHOSEN_FAMILIES,
            known_contacts=[])

    ladder_fetch_count = 0
    for candidate_url in accepted:
        if walk["ended"] is not None:
            break
        pages.append({"url": candidate_url, "people": page_people_for(candidate_url)})
        attempts.append({"url": candidate_url, "outcome": "ok", "disposition": "empty"})
        ladder_fetch_count += 1
        candidates = suggest_contacts.next_candidates(
            company_row, attempts,
            [u for u in sitemap_urls if u not in {p["url"] for p in pages}])
        walk = suggest_contacts.walk_pages(
            pages, candidates, bar, _WALK_FAMILY_LIST, _WALK_CHOSEN_FAMILIES,
            known_contacts=[])

    return pages, ladder_fetch_count, walk


def _nobody(url):
    """A page whose one person never clears the role filter -- classify_title finds no
    match for "Nobody" against `_WALK_FAMILY_LIST`, so every page scores 0 and the walk
    can only end via ladder/cap exhaustion, never `good_enough`. This isolates CR-01's
    budget-bookkeeping defect from the (already-tested) bar-clearing behaviour."""
    return [{"firstname": f"P-{url}", "lastname": "X", "jobtitle": "Nobody"}]


@pytest.mark.parametrize("candidate_count,expected_ended", [
    (3, "ladder_exhausted"),
    (5, "cap_exhausted"),
    (10, "cap_exhausted"),
])
def test_the_documented_loop_walks_every_candidate_the_budget_allows(
        candidate_count, expected_ended):
    """CR-01: re-deriving `candidates` from the FULL, unfiltered `sitemap_urls` after
    every fetch made `filter_candidates` (always a PREFIX of the URLs it is handed)
    return a shrinking prefix of the SAME front URLs -- never further down the list --
    so the walk read the ladder as exhausted after 3 fetches regardless of whether 3,
    5, or 10 candidates were actually offered. The fix narrows the input to what
    `pages` has not already walked, so all 5 of `MAX_FOLLOWUP_FETCHES` are spent
    before the walk reports itself exhausted."""
    company_row = _company_row_with_website(
        "walk-1", "https://walk-ladder.example/contact")
    sitemap_urls = [
        f"https://walk-ladder.example/u{i}" for i in range(1, candidate_count + 1)
    ]
    bar = suggest_contacts.walk_bar(_WALK_CHOSEN_FAMILIES, per_company_cap=3)

    pages, ladder_fetch_count, walk = _walk_company_like_skill_md(
        company_row, sitemap_urls, bar, _nobody)

    expected_fetches = min(candidate_count, url_fallback.MAX_FOLLOWUP_FETCHES)
    assert ladder_fetch_count == expected_fetches, (
        f"{candidate_count} same-host candidates must spend "
        f"{expected_fetches} ladder fetches (bounded only by "
        f"MAX_FOLLOWUP_FETCHES={url_fallback.MAX_FOLLOWUP_FETCHES}), not stop early"
    )
    assert walk["ended"] == expected_ended
    # every ladder fetch actually folded into `pages`, alongside the pasted URL
    assert len(pages) == expected_fetches + 1


def test_the_documented_loop_folds_the_pasted_page_and_a_later_ladder_page_into_one_union():
    """CR-02: the pasted URL's own fetch was never folded into `pages` at all --
    `walk_pages`'s own docstring says `pages` is "EVERY page fetched for this company,
    INCLUDING the pasted URL" and warns that dropping it "would silently drop the
    receptionist page -- the very page the live case starts from". This is the
    phase's headline case: a person named on the pasted `/contact` page and a person
    named on a later `/board/` ladder page both end up in the SAME `walk["people"]`
    union."""
    company_row = _company_row_with_website(
        "walk-2", "https://walk-ladder.example/contact")
    sitemap_urls = ["https://walk-ladder.example/board"]
    bar = suggest_contacts.walk_bar(_WALK_CHOSEN_FAMILIES, per_company_cap=99)

    def page_people(url):
        if url == "https://walk-ladder.example/contact":
            return [{"firstname": "Jane", "lastname": "Receptionist", "jobtitle": "Director"}]
        return [{"firstname": "Sam", "lastname": "Officer", "jobtitle": "Director"}]

    pages, ladder_fetch_count, walk = _walk_company_like_skill_md(
        company_row, sitemap_urls, bar, page_people)

    assert ladder_fetch_count == 1
    lastnames = {p["lastname"] for p in walk["people"]}
    assert lastnames == {"Receptionist", "Officer"}, (
        "the pasted page's person and the ladder page's person must both survive "
        "into the walk's own union"
    )
    selected_lastnames = {p["lastname"] for p in walk["selected"]}
    assert selected_lastnames == {"Receptionist", "Officer"}


def _company_row_with_website(row_id, website):
    return {
        "row_id": row_id,
        "name": f"Example Company {row_id}",
        "website": website,
        "num_associated_contacts": 0,
    }


def test_the_documented_round_reaches_an_accepted_chunk_and_an_enriched_sendable_row(
        fake_config, stub_module_transport_factory):
    """G-62-4 (blocker, live UAT 2026-09-03). Following `suggest-contacts/SKILL.md`
    exactly, stage 2 could not dispatch AT ALL: `preingest.build_rows_spec` is the
    single place `row_id` is minted and the skill never called it, so every chunk came
    back `ok=False` naming `row_id`. Drives the documented sequence over TWO eligible
    companies -- one is not enough to observe the mint's once-for-the-whole-batch
    property, since a per-company mint would produce `["row-1", "row-1"]`, which reads
    identically to `["row-1", "row-2"]` for a single company.

    This is also the second, independent seam this gap closes (Decision 2):
    `preingest.merge_enriched` returns FRESH rows and never mutates its input, so
    without `rejoin_enriched` the round's own records would still hold pre-merge rows
    and `partition_for_dispatch` would HOLD every row the waterfall had just filled.
    """
    company_a = _company_row_with_website(
        "co-a", "https://example-club-a.example/board")
    company_b = _company_row_with_website(
        "co-b", "https://example-club-b.example/committee")

    vocabulary = role_classify.load_families()
    family_list = vocabulary["families"]
    figures = {"suggestion_allowance": {"priced_cap": 5}}
    per_company_cap = suggest_contacts.agreed_cap(2, figures)

    records = []
    fetched_urls = {}
    for company_row, firstname, lastname in (
            (company_a, "Jamie", "Fox"), (company_b, "Robin", "Lee")):
        plan = suggest_contacts.discovery_plan(company_row)
        assert plan["candidates"], "the ladder must offer at least one candidate"
        fetched_url = plan["candidates"][0]["url"]
        fetched_urls[firstname] = fetched_url

        people = [{"firstname": firstname, "lastname": lastname, "jobtitle": FAMILY_LABEL}]
        selection = suggest_contacts.select_people(
            people, family_list, [FAMILY_LABEL], known_contacts=[])
        assert len(selection["selected"]) == 1
        records.extend(suggest_contacts.synthesise_rows(
            company_row, selection["selected"], fetched_url,
            per_company_cap=per_company_cap))

    assert len(records) == 2  # one selected person per company

    # The mint -- ONCE, over the whole batch, never per company.
    minted = suggest_contacts.mint_row_ids(records)
    assert minted["spec"]["object_type"] == "contacts"
    minted_ids = [row["row_id"] for row in minted["spec"]["rows"]]
    assert minted_ids == ["row-1", "row-2"], (
        "ids must be minted once across the WHOLE batch -- a per-company mint would "
        "produce ['row-1', 'row-1'], joining two different people onto one id"
    )
    assert minted["records"][0]["provenance"]["locator"] == fetched_urls["Jamie"]
    assert minted["records"][1]["provenance"]["locator"] == fetched_urls["Robin"]

    cfg = {**fake_config, "max_records_per_chunk": 5}
    ceiling = chunking.chunk_ceiling(cfg)
    plan = chunking.plan_chunks(minted["spec"], ceiling)
    assert plan.chunk_count == 1, "both rows must fit in one chunk for this fixture"

    providers = enrichment.resolve_providers(None, cfg)
    transport = stub_module_transport_factory()  # default accepted body, no scripting
    outcome = chunking.dispatch_plan(
        plan, providers, True, cfg, transport=transport,
        run_id="suggest-composition-test-run", async_ack=True)

    # THIS is the assertion that closes G-62-4.
    assert outcome.results[0].ok is True
    assert all(
        result.reason is None or "row_id" not in result.reason
        for result in outcome.results
    )

    # Stage 2 -- simulated response. Jamie's row gets an email from the waterfall;
    # Robin's waterfall lookup finds nothing, so Robin's row stays emailless.
    responses = [
        {"row_id": "row-1", "properties": {"email": "jamie.fox@example-club-a.example"}},
        {"row_id": "row-2", "properties": {}},
    ]
    merge_report = preingest.merge_enriched(minted["spec"]["rows"], responses)

    rejoined = suggest_contacts.rejoin_enriched(minted["records"], merge_report.rows)
    company_domains = {
        company_a["name"]: company_a["website"], company_b["name"]: company_b["website"],
    }
    sendable, held = suggest_contacts.partition_for_dispatch(
        [record["row"] for record in rejoined], company_domains)
    assert len(sendable) == 1 and sendable[0]["firstname"] == "Jamie", (
        "without rejoin_enriched, both rows would still be held -- the quiet wrong "
        "answer Decision 2 names"
    )
    assert len(held) == 1 and held[0]["row"]["firstname"] == "Robin"

    validated_count = 0
    for record in rejoined:
        if record["row"] not in sendable:
            continue  # a held row never reaches extraction.validate()
        result = extraction.validate(suggest_contacts.round_artifact([record]))
        validated_count += 1
        assert result.rejected == []
        assert len(result.accepted) == 1
        assert result.accepted[0]["provenance"]["locator"] == fetched_urls["Jamie"]

    assert validated_count == len(sendable) == 1


def test_mint_row_ids_propagates_row_spec_error_for_a_row_that_already_has_one():
    """The single mint site stays single: `mint_row_ids` never strips, re-mints or
    swallows `preingest.build_rows_spec`'s own refusal for a row that already carries
    an id."""
    record = {
        "record_type": "contacts",
        "row": {"firstname": "Jamie", "lastname": "Fox", "company": "Acme", "row_id": "row-1"},
        "provenance": {"input": "suggest_contacts_ladder", "locator": "https://example.example/board"},
    }
    with pytest.raises(preingest.RowSpecError):
        suggest_contacts.mint_row_ids([record])


def test_rejoin_enriched_raises_naming_the_missing_row_id():
    """A record whose id is absent from the merged set raises rather than silently
    leaving that record attached to a stale row."""
    record = {
        "record_type": "contacts",
        "row": {"row_id": "row-1", "firstname": "Jamie", "lastname": "Fox", "company": "Acme"},
        "provenance": {"input": "suggest_contacts_ladder", "locator": "https://example.example/board"},
    }
    merged_rows = [{"row_id": "row-2", "firstname": "Robin"}]
    with pytest.raises(ValueError) as excinfo:
        suggest_contacts.rejoin_enriched([record], merged_rows)
    assert "row-1" in str(excinfo.value)


def test_a_chosen_cap_above_the_priced_cap_refuses_and_synthesises_no_rows():
    """The refusal direction, end to end: a chosen cap above the figures dict's own
    priced_cap raises CapRefused at agreed_cap() and synthesise_rows() is never even
    reached for that company (62-06, CR-01/WR-01)."""
    company_row = _company_row("elig-3", num_associated_contacts=0)
    people = [{"firstname": "Jamie", "lastname": "Fox", "jobtitle": FAMILY_LABEL}]

    vocabulary = role_classify.load_families()
    selection = suggest_contacts.select_people(
        people, vocabulary["families"], [FAMILY_LABEL], known_contacts=[])
    assert len(selection["selected"]) == 1

    figures = {"suggestion_allowance": {"priced_cap": 3}}
    with pytest.raises(suggest_contacts.CapRefused) as excinfo:
        suggest_contacts.agreed_cap(5, figures)
    message = str(excinfo.value)
    assert "3" in message
    assert "5" in message
    # No rows were synthesised for this company -- the refusal happened before
    # synthesise_rows was ever called.


# =====================================================================================
# Phase 65 Task 2 — the terminal classify, driven for real over an interleaved batch:
# `rounds`' start/count slice keeps each company's own rows filtered against the
# BATCH-WIDE sendable/held lists (D-65-02, D-65-06, D-65-07).
# =====================================================================================

def test_two_interleaved_companies_each_get_their_own_cause_and_breakdown():
    """Company A's one person ends up with an email on a stranger's domain (held,
    zero sendable) -- all_held_on_email. Company B's one person ends up with a
    related-domain email and reaches the bar -- proposed. Both records interleave in
    ONE batch, minted and merged together, so this proves the `rows` filter scopes the
    shared `sendable`/`held` lists to each company's OWN rows rather than the whole
    batch's."""
    company_a = _company_row_with_website(
        "interleave-a", "https://example-club-a.example/board")
    company_b = _company_row_with_website(
        "interleave-b", "https://example-club-b.example/board")

    vocabulary = role_classify.load_families()
    family_list = vocabulary["families"]
    chosen_families = [FAMILY_LABEL]
    figures = {"suggestion_allowance": {"priced_cap": 1}}
    per_company_cap = suggest_contacts.agreed_cap(1, figures)
    bar = suggest_contacts.walk_bar(chosen_families, per_company_cap)

    rounds = []
    records = []
    for company_row, firstname, lastname in (
            (company_a, "Craig", "Smith"), (company_b, "Jamie", "Fox")):
        people = [{"firstname": firstname, "lastname": lastname, "jobtitle": FAMILY_LABEL}]
        selection = suggest_contacts.select_people(
            people, family_list, chosen_families, known_contacts=[])
        walk = {
            "people": people, "selected": selection["selected"],
            "dropped": selection["dropped"], "scores": [],
            "ended": suggest_contacts.WALK_GOOD_ENOUGH, "bar": bar,
        }
        company_records = suggest_contacts.synthesise_rows(
            company_row, selection["selected"], "https://example.example/board",
            per_company_cap)
        rounds.append({
            "company": company_row, "walk": walk, "fallback": None,
            "start": len(records), "count": len(company_records),
        })
        records.extend(company_records)

    # The mint -- ONCE, over the whole interleaved batch, never per company.
    minted = suggest_contacts.mint_row_ids(records)

    # Stage 2: Craig's waterfall email is a stranger's domain; Jamie's is related.
    responses = [
        {"row_id": "row-1", "properties": {"email": "craig.smith@thehartford.com"}},
        {"row_id": "row-2", "properties": {"email": "jamie.fox@example-club-b.example"}},
    ]
    merge_report = preingest.merge_enriched(minted["spec"]["rows"], responses)
    rejoined = suggest_contacts.rejoin_enriched(minted["records"], merge_report.rows)

    company_domains = {
        company_a["name"]: company_a["website"], company_b["name"]: company_b["website"],
    }
    sendable, held = suggest_contacts.partition_for_dispatch(
        [record["row"] for record in rejoined], company_domains)
    sendable, held = search_fallback.hold_weak_sources(rejoined, sendable, held)

    for entry in rounds:
        company_rows = [
            rec["row"] for rec in rejoined[entry["start"]:entry["start"] + entry["count"]]
        ]
        entry["outcome"] = suggest_contacts.round_outcome(
            entry["walk"], rows=company_rows, sendable=sendable, held=held,
            fallback=entry["fallback"])

    assert rounds[0]["outcome"]["cause"] == suggest_contacts.CAUSE_ALL_HELD_ON_EMAIL
    assert rounds[0]["outcome"]["reentry"] == suggest_contacts.REENTRY_NONE
    assert rounds[0]["outcome"]["breakdown"]["sendable"] == 0

    assert rounds[1]["outcome"]["cause"] == suggest_contacts.CAUSE_PROPOSED
    assert rounds[1]["outcome"]["reentry"] == suggest_contacts.REENTRY_NONE
    assert rounds[1]["outcome"]["breakdown"]["sendable"] == 1


def test_config_gate_style_modules_used_in_the_documented_block_are_real_scripts_modules():
    """A cheap guard against the census's own module-name derivation silently going
    stale: `scripts_modules()` derives its allowlist from `scripts/*.py` at runtime, so a
    rename of any module used in the new SKILL.md block would otherwise surface only as a
    confusing AST-identity mismatch rather than here, at the source."""
    assert callable(suggest_contacts.eligibility)
    assert callable(suggest_contacts.discovery_plan)
    assert callable(role_classify.load_families)
    assert callable(suggest_contacts.select_people)
    assert callable(suggest_contacts.agreed_cap)
    assert callable(suggest_contacts.synthesise_rows)
    assert callable(suggest_contacts.partition_for_dispatch)
    assert callable(extraction.validate)
    assert callable(suggest_contacts.round_artifact)
