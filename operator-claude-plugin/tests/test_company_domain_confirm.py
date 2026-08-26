"""Tests for `company_domain.py` (Phase 58 Plan 03, Task 1) — INPUT-03's confirm/decline
lane: a proposed company domain is never written until the operator DECIDES.

Every test here exercises `apply_domain_decisions`'s validate-then-apply-atomically
discipline (mirrors `preingest.py::apply_match_decisions`) and `to_envelope_spec`'s
refusal on an undecided row — the two places "ambiguity resolves to not-armed" (VOCAB-05)
lives in code rather than only in prose.
"""
import copy
from unittest import mock

import pytest

import company_domain
import enrichment


def _proposal(row_id="row-1", name="Perth Racing", domain="perthracing.com.au",
              source="claude", reason="matches the operator's own paste", evidence_url=None):
    proposal = {
        "row_id": row_id, "name": name, "domain": domain,
        "source": source, "reason": reason,
    }
    if evidence_url is not None:
        proposal["evidence_url"] = evidence_url
    return proposal


# =====================================================================================
# apply_domain_decisions — empty resolved leaves everything undecided
# =====================================================================================

def test_apply_domain_decisions_with_empty_resolved_leaves_every_row_undecided():
    proposals = [_proposal(), _proposal(row_id="row-2", name="No Domain Ltd", domain=None)]
    result = company_domain.apply_domain_decisions(proposals, {})

    assert result["decided_with_domain"] == []
    assert result["decided_name_only"] == []
    assert len(result["undecided"]) == 2
    assert {row["row_id"] for row in result["undecided"]} == {"row-1", "row-2"}


# =====================================================================================
# Confirm — a decision equal to the row's own proposed domain
# =====================================================================================

def test_confirming_the_proposed_domain_decides_it_with_that_domain_and_source():
    proposals = [_proposal(domain="perthracing.com.au", source="claude")]
    result = company_domain.apply_domain_decisions(
        proposals, {"row-1": "perthracing.com.au"}
    )

    assert result["undecided"] == []
    assert len(result["decided_with_domain"]) == 1
    decided = result["decided_with_domain"][0]
    assert decided["row_id"] == "row-1"
    assert decided["name"] == "Perth Racing"
    assert decided["domain"] == "perthracing.com.au"
    assert decided["source"] == "claude"


def test_confirming_a_row_with_nothing_proposed_raises_naming_the_row():
    proposals = [_proposal(domain=None)]
    with pytest.raises(company_domain.DomainDecisionError) as exc:
        company_domain.apply_domain_decisions(proposals, {"row-1": None})
    assert "row-1" in str(exc.value)


def test_confirming_a_proposal_whose_own_value_is_a_profile_host_raises():
    """Defence in depth: a proposal built upstream from a page's own address must not
    become a domain merely because the operator said yes to it."""
    proposals = [_proposal(domain="linkedin.com")]
    with pytest.raises(company_domain.DomainDecisionError) as exc:
        company_domain.apply_domain_decisions(proposals, {"row-1": "linkedin.com"})
    message = str(exc.value)
    assert "linkedin.com" in message
    assert "website" in message.lower()


# =====================================================================================
# Operator correction — any other string
# =====================================================================================

def test_a_different_domain_string_is_an_operator_correction_with_no_research_pass():
    proposals = [_proposal(domain="perthracing.com.au", source="claude")]
    result = company_domain.apply_domain_decisions(
        proposals, {"row-1": "https://www.PerthRacingClub.com.au/about"}
    )
    decided = result["decided_with_domain"][0]
    assert decided["domain"] == "perthracingclub.com.au"
    assert decided["source"] == "operator"


def test_an_operator_correction_naming_a_profile_host_raises_naming_the_host():
    proposals = [_proposal(domain="perthracing.com.au")]
    with pytest.raises(company_domain.DomainDecisionError) as exc:
        company_domain.apply_domain_decisions(
            proposals, {"row-1": "https://www.linkedin.com/company/perth-racing"}
        )
    message = str(exc.value)
    assert "linkedin.com" in message
    assert "website" in message.lower()


# =====================================================================================
# Decline — moves the row to name-only, never removed
# =====================================================================================

def test_declining_moves_the_row_to_name_only_with_a_recorded_reason():
    proposals = [_proposal()]
    result = company_domain.apply_domain_decisions(
        proposals, {"row-1": company_domain.DECLINE_DOMAIN}
    )
    assert result["decided_with_domain"] == []
    assert result["undecided"] == []
    assert len(result["decided_name_only"]) == 1
    name_only = result["decided_name_only"][0]
    assert name_only["row_id"] == "row-1"
    assert name_only["name"] == "Perth Racing"
    assert "domain" not in name_only
    assert name_only["reason"]


# =====================================================================================
# Unknown row — raises naming the row
# =====================================================================================

def test_a_decision_for_a_row_never_proposed_raises_naming_the_row():
    proposals = [_proposal()]
    with pytest.raises(company_domain.DomainDecisionError) as exc:
        company_domain.apply_domain_decisions(proposals, {"row-does-not-exist": "x.example"})
    assert "row-does-not-exist" in str(exc.value)


# =====================================================================================
# Atomicity — one bad entry applies none of the good ones
# =====================================================================================

def test_all_or_nothing_a_bad_last_entry_applies_none_of_the_earlier_good_ones():
    proposals = [
        _proposal(row_id="row-1", name="Good Co", domain="good.example"),
        _proposal(row_id="row-2", name="Bad Co", domain="bad.example"),
    ]
    pristine = copy.deepcopy(proposals)
    resolved = {
        "row-1": "good.example",  # valid confirm
        "row-2": "https://www.linkedin.com/company/bad-co",  # invalid correction
    }

    with pytest.raises(company_domain.DomainDecisionError):
        company_domain.apply_domain_decisions(proposals, resolved)

    assert proposals == pristine, (
        "a raise must leave the caller's own input object exactly as it was"
    )


# =====================================================================================
# to_envelope_spec
# =====================================================================================

def test_to_envelope_spec_raises_when_a_row_is_undecided_naming_it():
    proposals = [_proposal()]
    decided = company_domain.apply_domain_decisions(proposals, {})
    with pytest.raises(company_domain.DomainDecisionError) as exc:
        company_domain.to_envelope_spec(decided)
    assert "row-1" in str(exc.value)


def test_to_envelope_spec_emits_one_company_entry_per_fully_decided_row():
    proposals = [
        _proposal(row_id="row-1", name="Confirmed Co", domain="confirmed.example"),
        _proposal(row_id="row-2", name="Corrected Co", domain="wrong.example"),
        _proposal(row_id="row-3", name="Declined Co", domain="declined.example"),
    ]
    resolved = {
        "row-1": "confirmed.example",
        "row-2": "https://corrected.example/",
        "row-3": company_domain.DECLINE_DOMAIN,
    }
    decided = company_domain.apply_domain_decisions(proposals, resolved)
    spec = company_domain.to_envelope_spec(decided)

    companies = {c["name"]: c for c in spec["companies"]}
    assert companies["Confirmed Co"]["domain"] == "confirmed.example"
    assert companies["Corrected Co"]["domain"] == "corrected.example"
    assert "domain" not in companies["Declined Co"]


def test_a_declined_row_appears_in_the_envelope_spec_with_name_and_no_domain_key():
    proposals = [_proposal(row_id="row-1", name="Declined Co", domain="declined.example")]
    decided = company_domain.apply_domain_decisions(
        proposals, {"row-1": company_domain.DECLINE_DOMAIN}
    )
    spec = company_domain.to_envelope_spec(decided)
    assert spec["companies"] == [{"name": "Declined Co"}]


def test_to_envelope_spec_over_a_fully_decided_set_can_feed_build_envelope():
    """The only path a domain travels to a webhook event — proven end to end."""
    proposals = [_proposal(row_id="row-1", name="Perth Racing", domain="perthracing.com.au")]
    decided = company_domain.apply_domain_decisions(proposals, {"row-1": "perthracing.com.au"})
    spec = company_domain.to_envelope_spec(decided)
    envelope = enrichment.build_envelope(spec, [])
    assert envelope["events"] == [
        {"objectType": "companies", "domain": "perthracing.com.au", "name": "Perth Racing"}
    ]


# =====================================================================================
# Guard reuse — no second implementation of the host logic
# =====================================================================================

def test_company_domain_calls_enrichment_clean_domain_rather_than_its_own_logic():
    proposals = [_proposal(domain="perthracing.com.au")]
    with mock.patch.object(
        enrichment, "_clean_domain", wraps=enrichment._clean_domain
    ) as spy:
        company_domain.apply_domain_decisions(proposals, {"row-1": "perthracing.com.au"})
    assert spy.called


def test_company_domain_module_defines_no_host_collection_of_its_own():
    """Prose recording the defect history is expected and must not trip this — only a
    module-level frozenset/set/tuple/list BINDING (a name this module itself assigns)
    would mean a second copy of the host logic exists here."""
    own_collections = [
        name for name, value in vars(company_domain).items()
        if not name.startswith("__")
        and isinstance(value, (frozenset, set, tuple, list))
    ]
    assert own_collections == [], (
        f"company_domain defines its own host collection(s): {own_collections}"
    )
