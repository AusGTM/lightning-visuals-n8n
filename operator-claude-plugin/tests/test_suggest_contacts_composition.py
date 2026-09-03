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


def test_the_documented_round_pipeline_drives_its_real_joins_end_to_end():
    """The whole documented sequence from `skills/suggest-contacts/SKILL.md`'s python
    block, over one eligible company: `eligibility` -> `discovery_plan` -> (role list
    from) `load_families` -> `select_people` -> `synthesise_rows` -> (stage-2 merge,
    simulated -- no network call belongs in this offline test) -> `partition_for_dispatch`
    -> `extraction.validate()` once per sendable row.

    Three named joins, each asserted directly:
      1. a company marked has_contacts never reaches discovery_plan (see the test above;
         re-proven here inline against this test's own company set)
      2. a person dropped by select_people never appears in a synthesised row
      3. a row in the held half never appears in the dispatch set (never validated)
    """
    company_row = _company_row("elig-2", num_associated_contacts=0)
    company_with_contacts = _company_row("has-2", num_associated_contacts=3)
    company_rows = [company_with_contacts, company_row]

    verdicts = suggest_contacts.eligibility(company_rows)
    eligible = [
        row for row, verdict in zip(company_rows, verdicts)
        if verdict["verdict"] == suggest_contacts.ELIGIBLE
    ]
    assert eligible == [company_row]  # join 1, re-proven for this test's own fixtures

    plan = suggest_contacts.discovery_plan(company_row)
    assert plan["candidates"], "the ladder must offer at least one candidate"
    assert plan["candidates"] == url_fallback.plan_ladder(company_row["website"])["candidates"]
    fetched_url = plan["candidates"][0]["url"]

    people = [
        {"firstname": "Jamie", "lastname": "Fox", "jobtitle": FAMILY_LABEL},
        {"firstname": "Alex", "lastname": "Nguyen", "jobtitle": "Receptionist"},
        {"firstname": "Robin", "lastname": "Lee", "jobtitle": FAMILY_LABEL},
    ]
    chosen_families = [FAMILY_LABEL]

    vocabulary = role_classify.load_families()
    family_list = vocabulary["families"]
    assert any(family.get("label") == FAMILY_LABEL for family in family_list), (
        f"the shipped role vocabulary no longer carries {FAMILY_LABEL!r} -- update this "
        f"test's FAMILY_LABEL to a label that still exists"
    )

    selection = suggest_contacts.select_people(
        people, family_list, chosen_families, known_contacts=[])
    assert {p["firstname"] for p in selection["selected"]} == {"Jamie", "Robin"}
    assert selection["dropped"] == [
        {"person": people[1], "reason": "role_not_selected"}
    ]

    figures = {"suggestion_allowance": {"priced_cap": 5}}
    per_company_cap = suggest_contacts.agreed_cap(5, figures)
    records = suggest_contacts.synthesise_rows(
        company_row, selection["selected"], fetched_url, per_company_cap=per_company_cap)
    assert len(records) == 2
    synthesised_firstnames = {record["row"]["firstname"] for record in records}
    assert synthesised_firstnames == {"Jamie", "Robin"}
    # join 2: the person select_people dropped never appears in a synthesised row
    assert "Alex" not in synthesised_firstnames

    # Stage 2 -- simulated. Jamie's row gets an email from the waterfall; Robin's
    # waterfall lookup finds nothing, so Robin's row stays emailless.
    for record in records:
        if record["row"]["firstname"] == "Jamie":
            record["row"]["email"] = "jamie.fox@example-club.example"

    company_domains = {company_row["name"]: company_row["website"]}
    sendable, held = suggest_contacts.partition_for_dispatch(
        [record["row"] for record in records], company_domains)
    assert len(sendable) == 1 and sendable[0]["firstname"] == "Jamie"
    assert len(held) == 1 and held[0]["row"]["firstname"] == "Robin"

    validated_count = 0
    validated_firstnames = []
    for record in records:
        if record["row"] not in sendable:
            continue  # a held row never reaches extraction.validate()
        result = extraction.validate(suggest_contacts.round_artifact([record]))
        validated_count += 1
        assert result.rejected == []
        assert len(result.accepted) == 1
        validated_firstnames.append(result.accepted[0]["row"]["firstname"])

    # extraction.validate() called exactly once per sendable row
    assert validated_count == len(sendable) == 1
    assert validated_firstnames == ["Jamie"]
    # join 3: the held row (Robin) never appears in the dispatch set
    assert "Robin" not in validated_firstnames


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
