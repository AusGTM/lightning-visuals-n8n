"""Tests for `cost_guard.suggestion_line()` (Phase 62, D-62-11/12/14).

Prices a suggestion round's two-component ceiling: stage 1 (discovery, page fetches,
dollar figure unmeasured) and stage 2 (enrich the people stage 1 named, provider
credits at the CONTACTS rate regardless of the batch's own object_type).
"""
from pathlib import Path

import pytest

import cost_guard
import url_fallback

PLUGIN_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def rates():
    return cost_guard.load_rates()


# --------------------------------------------------------------------------- no rows


def test_zero_companies_yields_no_rows_and_no_figures(rates):
    result = cost_guard.suggestion_line(0, 3, rates)
    assert result["state"] == "no_rows"
    assert result["stage1_state"] == "no_rows"
    assert result["stage1_fetch_ceiling"] == 0
    assert result["stage1_cost_usd"] is None
    assert result["stage2_contact_ceiling"] == 0
    assert result["stage2_credit_ceiling"] is None
    assert result["known"] is False


# ------------------------------------------------------------------ stage-1 unmeasured


def test_non_empty_set_with_shipped_null_rate_is_unmeasured_not_zero(rates):
    result = cost_guard.suggestion_line(5, 3, rates)
    assert result["stage1_state"] == "unmeasured"
    assert result["stage1_cost_usd"] is None
    assert "$0" not in result["line"]


def test_stage1_fetch_ceiling_equals_companies_times_max_followup_fetches(rates):
    result = cost_guard.suggestion_line(7, 2, rates)
    assert result["stage1_fetch_ceiling"] == 7 * url_fallback.MAX_FOLLOWUP_FETCHES
    assert cost_guard.MAX_FETCHES_PER_COMPANY == url_fallback.MAX_FOLLOWUP_FETCHES


# ------------------------------------------------------------------------- stage-2


def test_stage2_credit_ceiling_equals_companies_times_cap_times_contact_rate(rates):
    result = cost_guard.suggestion_line(10, 3, rates)
    contact_rate = rates["rates"][cost_guard.SUGGESTION_STAGE2_RATE_KEY]["value"]
    assert contact_rate == 1
    assert result["stage2_contact_ceiling"] == 10 * 3
    assert result["stage2_credit_ceiling"] == 10 * 3 * contact_rate


def test_stage2_uses_contacts_rate_key_even_for_a_companies_object_type_batch(rates):
    # suggestion_line takes no object_type parameter at all -- stage 2 always prices
    # people (the CONTACTS rate), regardless of what kind of batch discovered them.
    result = cost_guard.suggestion_line(4, 2, rates)
    assert result["stage2_rate"] == rates["rates"]["lusha_contacts_first_time_enrich"]["value"]
    assert cost_guard.SUGGESTION_STAGE2_RATE_KEY == "lusha_contacts_first_time_enrich"


# ------------------------------------------------------------------------- rendering


def test_line_names_both_a_fetch_figure_and_a_credit_figure(rates):
    result = cost_guard.suggestion_line(6, 3, rates)
    assert "fetch" in result["line"]
    assert "credit" in result["line"]
    assert "ceiling" in result["line"].lower()


def test_line_never_presents_the_credit_figure_alone(rates):
    result = cost_guard.suggestion_line(6, 3, rates)
    # Both component substrings must be present together in the one sentence.
    assert "stage 1" in result["line"]
    assert "stage 2" in result["line"]


# --------------------------------------------------------------------------- rate table


def test_suggestion_stage1_discovery_rate_ships_null(rates):
    assert rates["rates"]["suggestion_stage1_discovery"]["value"] is None
    assert rates["rates"]["suggestion_stage1_discovery"]["unit"] == "USD/company"
