"""Tests for PREVIEW-02's arithmetic half: the dated rate table, the batch estimate,
the balance read, and the tri-state comparison.

The two weight-bearing tests are `test_a_genuine_zero_and_an_unreadable_balance_yield
_different_verdicts` and `test_no_arithmetic_is_performed_on_an_unreadable_balance`.
The first pins D-10's distinction; the second pins that the implementation *branches*
on readability rather than computing first and relabelling afterwards — a verdict-string
assertion alone passes against that defect (25-CONTEXT D-17).
"""
from datetime import date
from pathlib import Path

import pytest

import cost_guard

PLUGIN_ROOT = Path(__file__).resolve().parent.parent

CONFIG = {"n8n_url": "https://example.invalid", "webhook_secret": "s3cr3t-placeholder"}


@pytest.fixture
def rates():
    return cost_guard.load_rates()


def _balance_row(provider, credits, *, error=None, status=200):
    """One `Build Credit Status` balances row in the shape that node actually emits."""
    return {"provider": provider, "configured": True, "credits": credits,
            "unreadable": credits is None, "error": error, "status": status}


def _body(*rows):
    return {"balances": list(rows), "checked_at": "2026-07-31T00:00:00Z"}


class _ExplodesOnArithmetic:
    """A balance value that refuses to be compared, subtracted or coerced.

    An implementation that computes before checking readability raises here; one that
    branches on readability first never touches it.
    """

    def _boom(self, *_args):
        raise AssertionError("arithmetic performed on an unreadable balance")

    __lt__ = __le__ = __gt__ = __ge__ = __eq__ = __ne__ = _boom
    __sub__ = __rsub__ = __add__ = __radd__ = _boom
    __bool__ = __float__ = __int__ = __index__ = _boom
    __hash__ = None


# --------------------------------------------------------------------------- rate table


def test_load_rates_returns_version_measurement_date_and_rates(rates):
    assert rates["version"]
    assert date.fromisoformat(rates["measured_on"]) == date(2026, 7, 30)
    assert rates["rates"]["lusha_contacts_first_time_enrich"]["value"] == 1


def test_a_missing_rate_table_raises_a_plugin_local_error_naming_the_file(tmp_path):
    missing = tmp_path / "no_such_rates.json"
    with pytest.raises(cost_guard.CostRateError) as excinfo:
        cost_guard.load_rates(missing)
    assert "no_such_rates.json" in str(excinfo.value)


def test_rate_table_age_is_computed_against_a_supplied_reference_date(rates):
    assert cost_guard.rate_table_age_days(rates, date(2026, 7, 30)) == 0
    assert cost_guard.rate_table_age_days(rates, date(2026, 8, 15)) == 16
    assert cost_guard.rate_table_age_days(rates, "2026-08-15") == 16


def test_an_unknown_rate_and_a_measured_zero_are_not_the_same_value(rates):
    assert rates["rates"]["apollo_per_match"]["value"] is None
    assert rates["rates"]["lusha_contacts_stored_id_reuse"]["value"] == 0


# ---------------------------------------------------------------------------- estimate


def test_a_companies_batch_with_lusha_uses_the_company_rate(rates):
    estimate = cost_guard.estimate_batch(10, "companies", ["lusha"], rates)
    assert estimate["provider_credits"]["lusha"]["credits"] == 20


def test_a_contacts_batch_with_lusha_uses_the_contact_rate(rates):
    estimate = cost_guard.estimate_batch(10, "contacts", ["lusha"], rates)
    assert estimate["provider_credits"]["lusha"]["credits"] == 10


def test_a_zoominfo_estimate_carries_its_own_confidence_label_through(rates):
    estimate = cost_guard.estimate_batch(50, "companies", ["zoominfo"], rates)
    assert estimate["provider_credits"]["zoominfo"]["credits"] == pytest.approx(54.0)
    assert "inferred" in estimate["provider_credits"]["zoominfo"]["confidence"]


def test_an_apollo_estimate_is_unknown_rather_than_zero_and_does_not_raise(rates):
    estimate = cost_guard.estimate_batch(10, "contacts", ["apollo"], rates)
    apollo = estimate["provider_credits"]["apollo"]
    assert apollo["credits"] is None
    assert apollo["credits"] != 0
    assert apollo["known"] is False


def test_an_empty_selection_costs_no_provider_credits_but_still_costs_anthropic(rates):
    estimate = cost_guard.estimate_batch(10, "contacts", [], rates)
    assert estimate["provider_credits"] == {}
    assert estimate["anthropic_usd"] == pytest.approx(0.68624)


def test_the_anthropic_figure_is_the_measured_per_record_rate_times_the_count(rates):
    per_record = rates["rates"]["anthropic_usd_per_record"]["value"]
    estimate = cost_guard.estimate_batch(7, "companies", ["lusha"], rates)
    assert estimate["anthropic_usd"] == pytest.approx(per_record * 7)


def test_an_estimate_carries_the_rate_tables_provenance_so_the_caller_need_not_reread_it(rates):
    estimate = cost_guard.estimate_batch(3, "contacts", ["lusha"], rates)
    assert estimate["rates_version"] == rates["version"]
    assert estimate["rates_measured_on"] == rates["measured_on"]


def test_a_backend_resolved_record_count_says_so_rather_than_inventing_a_number(rates):
    estimate = cost_guard.estimate_batch(None, "companies", ["lusha", "apollo"], rates)
    assert estimate["record_count_known"] is False
    assert estimate["record_count"] is None
    assert estimate["anthropic_usd"] is None
    for figure in estimate["provider_credits"].values():
        assert figure["credits"] is None
        assert figure["known"] is False


# ----------------------------------------------------------------------------- balances


def test_fetching_balances_posts_to_the_status_path_with_the_secret_and_a_timeout(
    stub_post_transport_factory,
):
    transport = stub_post_transport_factory([_body(_balance_row("lusha", 412))])
    balances = cost_guard.fetch_balances(CONFIG, transport=transport)

    call = transport.calls[-1]
    assert call["url"].endswith("/webhook/hubspot/backend-status")
    assert call["headers"]["X-Enrichment-Secret"] == CONFIG["webhook_secret"]
    assert isinstance(call["timeout"], int) and call["timeout"] > 0
    assert balances["lusha"]["credits"] == 412
    assert balances["lusha"]["unreadable"] is False


def test_an_unreachable_endpoint_yields_unreadable_for_all_three_providers(
    stub_post_transport_factory,
):
    transport = stub_post_transport_factory([ConnectionError("dead")])
    balances = cost_guard.fetch_balances(CONFIG, transport=transport)

    assert set(balances) == {"lusha", "apollo", "zoominfo"}
    for provider, balance in balances.items():
        assert balance["unreadable"] is True, provider
        assert balance["credits"] is None, provider
        assert balance["reason"]


def test_a_malformed_response_body_yields_unreadable_for_all_three_providers(
    stub_post_transport_factory,
):
    transport = stub_post_transport_factory([(200, ValueError("not json"))])
    balances = cost_guard.fetch_balances(CONFIG, transport=transport)
    assert all(balance["unreadable"] is True for balance in balances.values())
    assert all(balance["credits"] is None for balance in balances.values())


def test_a_provider_absent_from_the_response_is_unreadable_not_zero(
    stub_post_transport_factory,
):
    transport = stub_post_transport_factory([_body(_balance_row("lusha", 5))])
    balances = cost_guard.fetch_balances(CONFIG, transport=transport)
    assert balances["apollo"]["unreadable"] is True
    assert balances["apollo"]["credits"] is None


def test_no_returned_reason_echoes_the_configured_secret(stub_post_transport_factory):
    transport = stub_post_transport_factory([ConnectionError(CONFIG["webhook_secret"])])
    balances = cost_guard.fetch_balances(CONFIG, transport=transport)
    for balance in balances.values():
        assert CONFIG["webhook_secret"] not in str(balance["reason"])


# --------------------------------------------------------------------------- comparison


def _estimate(credits, *, known=True, provider="lusha", rate=1):
    return {
        "record_count": 10, "record_count_known": True,
        "provider_credits": {provider: {"credits": credits, "known": known,
                                        "rate": rate, "unit": "credits/contact",
                                        "confidence": "measured"}},
        "anthropic_usd": 0.68624,
        "rates_version": "test", "rates_measured_on": "2026-07-30",
    }


def _readable(credits):
    return {"lusha": {"credits": credits, "unreadable": False, "reason": None}}


def _unreadable(reason="http_403", credits=None):
    return {"lusha": {"credits": credits, "unreadable": True, "reason": reason}}


def test_an_estimate_under_a_readable_balance_is_ok():
    assert cost_guard.compare(_estimate(10), _readable(500))["lusha"]["verdict"] == "ok"


def test_an_estimate_over_a_readable_balance_is_insufficient():
    verdict = cost_guard.compare(_estimate(600), _readable(500))["lusha"]
    assert verdict["verdict"] == "insufficient"
    assert verdict["remaining_credits"] == 500


def test_a_readable_balance_of_exactly_zero_is_insufficient():
    assert cost_guard.compare(_estimate(10), _readable(0))["lusha"]["verdict"] == "insufficient"


def test_an_unreadable_balance_is_unknown_and_distinguishable_from_both_other_verdicts():
    verdict = cost_guard.compare(_estimate(10), _unreadable())["lusha"]
    assert verdict["verdict"] == "unknown"
    assert verdict["verdict"] not in {"ok", "insufficient"}
    assert "http_403" in verdict["reason"]
    assert verdict["remaining_credits"] is None


def test_a_genuine_zero_and_an_unreadable_balance_yield_different_verdicts():
    """D-10/D-17. An assertion of the form "unreadable is falsy" would pass against the
    exact defect this test exists to catch, so assert the two verdicts differ outright."""
    zero = cost_guard.compare(_estimate(10), _readable(0))["lusha"]
    unread = cost_guard.compare(_estimate(10), _unreadable())["lusha"]
    assert zero["verdict"] != unread["verdict"]
    assert (zero["verdict"], unread["verdict"]) == ("insufficient", "unknown")


def test_an_unknown_estimate_against_an_unreadable_balance_is_unknown_and_does_not_raise():
    verdict = cost_guard.compare(_estimate(None, known=False), _unreadable())["lusha"]
    assert verdict["verdict"] == "unknown"
    assert verdict["estimated_credits"] is None


def test_an_unknown_estimate_against_a_readable_balance_is_still_unknown():
    """A readable balance cannot rescue an unestimable cost — an `ok` here would be a
    false clearance. The reason must name WHICH of the two causes applies, so the
    operator can tell a missing rate from a backend-resolved record count."""
    no_rate = cost_guard.compare(
        _estimate(None, known=False, rate=None), _readable(500))["lusha"]
    assert no_rate["verdict"] == "unknown"
    assert "rate" in no_rate["reason"]

    no_count = cost_guard.compare(_estimate(None, known=False), _readable(500))["lusha"]
    assert no_count["verdict"] == "unknown"
    assert "record count" in no_count["reason"]


def test_no_arithmetic_is_performed_on_an_unreadable_balance():
    """The structural half of D-17: a balance value that raises on every comparison,
    coercion and arithmetic operator. Reaching it at all fails the test, so this cannot
    pass against an implementation that computed a verdict and relabelled it after."""
    balances = _unreadable(credits=_ExplodesOnArithmetic())
    verdict = cost_guard.compare(_estimate(10), balances)["lusha"]
    assert verdict["verdict"] == "unknown"
    assert verdict["remaining_credits"] is None


def test_a_backend_resolved_record_count_makes_every_verdict_unknown(rates):
    estimate = cost_guard.estimate_batch(None, "contacts", ["lusha"], rates)
    verdict = cost_guard.compare(estimate, _readable(500))["lusha"]
    assert verdict["verdict"] == "unknown"


def test_comparison_yields_one_verdict_per_estimated_provider(rates):
    estimate = cost_guard.estimate_batch(10, "contacts", ["lusha", "apollo", "zoominfo"], rates)
    verdicts = cost_guard.compare(estimate, {
        "lusha": {"credits": 500, "unreadable": False, "reason": None},
        "apollo": {"credits": None, "unreadable": True, "reason": "http_403"},
        "zoominfo": {"credits": 2, "unreadable": False, "reason": None},
    })
    assert set(verdicts) == {"lusha", "apollo", "zoominfo"}
    assert verdicts["lusha"]["verdict"] == "ok"
    assert verdicts["apollo"]["verdict"] == "unknown"
    assert verdicts["zoominfo"]["verdict"] == "insufficient"
