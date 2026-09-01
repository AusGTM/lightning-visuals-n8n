"""Composition test for Phase 62 Plan 05 Task 2 (the sequence-coverage ratchet).

Registers the census identity (`test_skill_sequence_coverage.py`'s `COVERED`) for
`skills/suggest-contacts/SKILL.md`'s one documented python block: the round's real join,
end to end, offline -- `eligibility` output feeding `discovery_plan`; the discovered
people feeding `select_people` with the family list `load_families` supplies; the
survivors feeding `synthesise_rows`; stage-2 fields merging onto those rows; and
`partition_for_dispatch` splitting them before `extraction.validate()` runs exactly once
per sendable row.

Synthetic fixtures throughout: an `example`-suffixed host, invented names, no real
discovered person committed anywhere in this file.
"""
import extraction
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

    records = suggest_contacts.synthesise_rows(
        company_row, selection["selected"], fetched_url, per_company_cap=5)
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

    sendable, held = suggest_contacts.partition_for_dispatch(
        [record["row"] for record in records])
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


def test_config_gate_style_modules_used_in_the_documented_block_are_real_scripts_modules():
    """A cheap guard against the census's own module-name derivation silently going
    stale: `scripts_modules()` derives its allowlist from `scripts/*.py` at runtime, so a
    rename of any module used in the new SKILL.md block would otherwise surface only as a
    confusing AST-identity mismatch rather than here, at the source."""
    assert callable(suggest_contacts.eligibility)
    assert callable(suggest_contacts.discovery_plan)
    assert callable(role_classify.load_families)
    assert callable(suggest_contacts.select_people)
    assert callable(suggest_contacts.synthesise_rows)
    assert callable(suggest_contacts.partition_for_dispatch)
    assert callable(extraction.validate)
    assert callable(suggest_contacts.round_artifact)
