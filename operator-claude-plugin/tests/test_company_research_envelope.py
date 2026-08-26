"""Tests for the backend-domain-research envelope line (Phase 58 Plan 04).

D-58-08/09/10: backend domain research is its own priced, declinable envelope line, and
striking it converges every affected row onto the same name-only path a denied proposal
already lands on. This file exercises both halves:

- `cost_guard.research_line` (Task 1) — the arithmetic: count, named rows, and an honest
  cost state that is never a fabricated number and never a zero standing in for unknown.
- `company_domain.needs_research` / `company_domain.decline_research` (Task 2) — the
  decision half: which rows need it, and what striking the line does to them.
"""
import re
from pathlib import Path

import pytest

import company_domain
import cost_guard

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
DOLLAR_DIGIT = re.compile(r"\$\d")


def _proposal(row_id, name, domain=None, source="claude", reason="test"):
    return {"row_id": row_id, "name": name, "domain": domain, "source": source,
            "reason": reason}


@pytest.fixture
def rates():
    return cost_guard.load_rates()


# ============================================================================= Task 1
# cost_guard.research_line
# ============================================================================= Task 1


def test_the_rate_table_carries_a_null_company_domain_research_entry_like_apollo(rates):
    entry = rates["rates"]["company_domain_research"]
    assert entry["value"] is None
    assert set(entry) == set(rates["rates"]["apollo_per_match"])
    assert "unit" in entry and "citation" in entry and "confidence" in entry


def test_pricing_research_for_rows_returns_their_count_and_identity(rates):
    rows = [{"row_id": "row-1", "name": "Futsal Australia"},
            {"row_id": "row-2", "name": "No Domain Ltd"}]
    line = cost_guard.research_line(rows, rates)
    assert line["count"] == 2
    assert line["row_ids"] == {"row-1", "row-2"}
    assert line["rows"] == rows


def test_an_unmeasured_rate_renders_no_dollar_figure_and_no_zero(rates):
    assert rates["rates"]["company_domain_research"]["value"] is None
    rows = [{"row_id": "row-1", "name": "Futsal Australia"}]
    line = cost_guard.research_line(rows, rates)
    assert line["known"] is False
    assert line["cost_usd"] is None
    assert not DOLLAR_DIGIT.search(line["line"])
    assert "$0" not in line["line"]


def test_a_measured_rate_renders_a_figure_proving_the_null_branch_is_not_the_only_path(rates):
    import copy
    measured = copy.deepcopy(rates)
    measured["rates"]["company_domain_research"]["value"] = 0.05
    rows = [{"row_id": "row-1", "name": "Futsal Australia"},
            {"row_id": "row-2", "name": "No Domain Ltd"}]
    line = cost_guard.research_line(rows, measured)
    assert line["known"] is True
    assert line["cost_usd"] == pytest.approx(0.10)
    assert DOLLAR_DIGIT.search(line["line"])


def test_zero_rows_says_no_company_needs_research_not_a_zero_cost_line(rates):
    line = cost_guard.research_line([], rates)
    assert line["count"] == 0
    assert not DOLLAR_DIGIT.search(line["line"])
    assert "$0" not in line["line"]
    assert line["state"] == "no_rows"


def test_zero_rows_says_no_research_needed_even_with_a_measured_rate(rates):
    import copy
    measured = copy.deepcopy(rates)
    measured["rates"]["company_domain_research"]["value"] = 0.05
    line = cost_guard.research_line([], measured)
    assert line["state"] == "no_rows"
    assert line["cost_usd"] is None
    assert not DOLLAR_DIGIT.search(line["line"])


def test_the_named_rows_and_the_decision_structures_needs_research_rows_are_the_same_set(
    rates,
):
    proposals = [
        _proposal("row-1", "Perth Racing", domain="perthracing.com.au"),
        _proposal("row-2", "Futsal Australia", domain=None),
        _proposal("row-3", "Federation of Australian Futsal", domain="faf.org.au"),
    ]
    needs = company_domain.needs_research(proposals, requested_check={"row-3"})
    line = cost_guard.research_line(needs, rates)
    assert line["row_ids"] == {row["row_id"] for row in needs}
    assert line["row_ids"] == {"row-2", "row-3"}


# ============================================================================= Task 2
# company_domain.needs_research / company_domain.decline_research
# ============================================================================= Task 2


def test_a_row_with_a_proposed_domain_is_absent_from_the_needs_research_set():
    proposals = [_proposal("row-1", "Perth Racing", domain="perthracing.com.au")]
    needs = company_domain.needs_research(proposals)
    assert needs == []


def test_a_row_with_nothing_proposed_and_a_row_the_operator_asked_to_check_are_both_in():
    proposals = [
        _proposal("row-1", "Futsal Australia", domain=None),
        _proposal("row-2", "Federation of Australian Futsal", domain="faf.org.au"),
    ]
    needs = company_domain.needs_research(proposals, requested_check={"row-2"})
    assert {row["row_id"] for row in needs} == {"row-1", "row-2"}
    for row in needs:
        assert "name" in row


def test_with_no_research_decisions_every_needs_research_row_is_still_treated_as_researching():
    proposals = [_proposal("row-1", "Futsal Australia", domain=None)]
    needs = company_domain.needs_research(proposals)
    resolved = {}
    declined = company_domain.decline_research(resolved, needs)
    # No strike happened — decline_research was never called by the caller in this path,
    # so resolved is untouched and the row is exactly where it started: undecided, still
    # priced and still slated to research, not silently dropped or auto-declined.
    assert resolved == {}
    assert declined == resolved  # sanity: this test does not call decline_research for real
    decided = company_domain.apply_domain_decisions(proposals, resolved)
    assert {row["row_id"] for row in decided["undecided"]} == {"row-1"}


def test_striking_the_line_moves_exactly_the_needs_research_rows_to_name_only_and_nothing_else():
    proposals = [
        _proposal("row-1", "Futsal Australia", domain=None),
        _proposal("row-2", "Perth Racing", domain="perthracing.com.au"),
    ]
    needs = company_domain.needs_research(proposals)
    resolved = {"row-2": "perthracing.com.au"}  # operator already confirmed this one
    struck = company_domain.decline_research(resolved, needs)
    # The already-resolved row-2 decision is untouched.
    assert struck["row-2"] == "perthracing.com.au"
    assert struck["row-1"] is company_domain.DECLINE_DOMAIN

    decided = company_domain.apply_domain_decisions(proposals, struck)
    assert decided["undecided"] == []
    assert {row["row_id"] for row in decided["decided_with_domain"]} == {"row-2"}
    assert {row["row_id"] for row in decided["decided_name_only"]} == {"row-1"}


def test_a_declined_research_row_and_a_declined_proposal_row_are_the_same_shape():
    proposals = [
        _proposal("row-1", "Futsal Australia", domain=None),
        _proposal("row-2", "No Domain Ltd", domain=None),
    ]
    needs = company_domain.needs_research(proposals)
    struck = company_domain.decline_research({}, needs)
    decided_via_strike = company_domain.apply_domain_decisions(proposals, struck)

    decided_via_manual_decline = company_domain.apply_domain_decisions(
        proposals, {"row-1": company_domain.DECLINE_DOMAIN,
                    "row-2": company_domain.DECLINE_DOMAIN},
    )

    by_id_strike = {r["row_id"]: r for r in decided_via_strike["decided_name_only"]}
    by_id_manual = {r["row_id"]: r for r in decided_via_manual_decline["decided_name_only"]}
    assert by_id_strike == by_id_manual


def test_striking_the_line_leaves_an_empty_undecided_group_empty_so_envelope_spec_does_not_raise():
    proposals = [_proposal("row-1", "Futsal Australia", domain=None)]
    needs = company_domain.needs_research(proposals)
    struck = company_domain.decline_research({}, needs)
    decided = company_domain.apply_domain_decisions(proposals, struck)
    assert decided["undecided"] == []
    spec = company_domain.to_envelope_spec(decided)
    assert spec == {"companies": [{"name": "Futsal Australia"}]}


def test_decline_research_never_overrides_an_explicit_operator_decision():
    proposals = [_proposal("row-1", "Futsal Australia", domain=None)]
    needs = company_domain.needs_research(proposals)
    resolved = {"row-1": "futsalaustralia.com.au"}  # operator supplied a correction
    struck = company_domain.decline_research(resolved, needs)
    assert struck["row-1"] == "futsalaustralia.com.au"


def test_enrich_records_skill_documents_the_research_line():
    text = (PLUGIN_ROOT / "skills" / "enrich-records" / "SKILL.md").read_text()
    assert "research" in text.lower()
    assert "domain research" in text.lower() or "website looked up" in text.lower()
