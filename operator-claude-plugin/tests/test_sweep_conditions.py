"""Per-condition coverage for sweep_conditions.py (29-05).

test_sweep_tracer.py proved the layers connect end to end for the one condition 29-03
shipped. This file proves each condition 29-05 adds, in isolation, against every fixture
shape conftest carries for it — including the shapes that look healthy and are not.

Task 1: quota-exhausted and credential-failure — new judgment over Phase 27's existing
credit-probe data (D-08a), across all four provider fixture states.
"""
import error_table
import sweep_conditions

# --- classify_quota / classify_credential ------------------------------------------------


def test_unknown_balance_yields_unknown_from_the_quota_check_and_fires_no_exhausted_notice(
        backend_status_unknown_balance):
    data = backend_status_unknown_balance["data"]
    balances, health = data["balances"], data["credential_health"]

    assert sweep_conditions.classify_quota("apollo", balances, health) == "unknown"

    fired = sweep_conditions.check_quota_and_credentials(data)
    assert not any(c["condition"] == sweep_conditions.QUOTA_EXHAUSTED and c["provider"] == "apollo"
                   for c in fired), "an unreadable balance must never fire exhausted-quota"


def test_unconfigured_provider_is_a_distinct_outcome_from_both_unknown_and_exhausted(
        backend_status_unconfigured_provider):
    data = backend_status_unconfigured_provider["data"]
    balances, health = data["balances"], data["credential_health"]

    outcome = sweep_conditions.classify_quota("apollo", balances, health)
    assert outcome == "not_configured"
    assert outcome not in ("unknown", "exhausted", "ok")

    fired = sweep_conditions.check_quota_and_credentials(data)
    assert not any(c["provider"] == "apollo" for c in fired), (
        "a provider never probed at all must not fire either condition")


def test_exhausted_fires_and_a_balance_just_above_the_floor_does_not(backend_status_exhausted):
    data = backend_status_exhausted["data"]
    balances, health = data["balances"], data["credential_health"]

    assert sweep_conditions.classify_quota("lusha", balances, health) == "exhausted"
    assert sweep_conditions.classify_quota("zoominfo", balances, health) == "ok"

    fired = sweep_conditions.check_quota_and_credentials(data)
    exhausted_providers = {c["provider"] for c in fired if c["condition"] == sweep_conditions.QUOTA_EXHAUSTED}
    assert exhausted_providers == {"lusha"}

    # The boundary itself: one credit above a floor of 5 must not fire.
    just_above = [{"provider": "lusha", "configured": True, "credits": 6, "unreadable": False}]
    assert sweep_conditions.classify_quota("lusha", just_above, health, floor=5) == "ok"
    at_floor = [{"provider": "lusha", "configured": True, "credits": 5, "unreadable": False}]
    assert sweep_conditions.classify_quota("lusha", at_floor, health, floor=5) == "exhausted"


def test_a_zero_balance_with_a_working_credential_is_exhausted_not_a_credential_failure():
    balances = [{"provider": "lusha", "configured": True, "credits": 0, "unreadable": False}]
    health = [{"source": "lusha", "state": "ok", "status": 200, "reason": None}]

    assert sweep_conditions.classify_quota("lusha", balances, health) == "exhausted"
    assert sweep_conditions.classify_credential("lusha", health) is False

    fired = sweep_conditions.check_quota_and_credentials(
        {"balances": balances, "credential_health": health})
    conditions = {c["condition"] for c in fired}
    assert sweep_conditions.QUOTA_EXHAUSTED in conditions
    assert sweep_conditions.CREDENTIAL_FAILURE not in conditions


def test_a_refused_credential_fires_credential_failure(backend_status_unknown_balance):
    data = backend_status_unknown_balance["data"]
    assert sweep_conditions.classify_credential("apollo", data["credential_health"]) is True

    fired = sweep_conditions.check_quota_and_credentials(data)
    assert any(c["condition"] == sweep_conditions.CREDENTIAL_FAILURE and c["provider"] == "apollo"
               for c in fired)


def test_both_conditions_attribute_to_an_admin(backend_status_unknown_balance,
                                               backend_status_exhausted):
    fired = (sweep_conditions.check_quota_and_credentials(backend_status_unknown_balance["data"])
             + sweep_conditions.check_quota_and_credentials(backend_status_exhausted["data"]))
    assert fired, "fixture must fire at least one of each condition for this test to mean anything"
    conditions = {c["condition"] for c in fired}
    assert sweep_conditions.QUOTA_EXHAUSTED in conditions
    assert sweep_conditions.CREDENTIAL_FAILURE in conditions
    for condition in fired:
        assert error_table.translate(condition["reason"])["who_can_fix"] == "admin"


def test_a_healthy_backend_fires_neither_condition(backend_status_healthy):
    fired = sweep_conditions.check_quota_and_credentials(backend_status_healthy["data"])
    assert fired == []


# --- evaluate() wiring the backend half in alongside the executions half ----------------


def test_evaluate_fires_quota_and_credential_conditions_from_a_gather(
        backend_status_unknown_balance):
    gathered = {"executions": {"available": False, "summaries": []},
               "backend": backend_status_unknown_balance}
    fired = sweep_conditions.evaluate(gathered)
    assert any(c["condition"] == sweep_conditions.CREDENTIAL_FAILURE for c in fired)


def test_evaluate_skips_backend_conditions_when_the_backend_is_unavailable():
    gathered = {"executions": {"available": False, "summaries": []},
               "backend": {"available": False, "reason": "http_404", "data": None}}
    assert sweep_conditions.evaluate(gathered) == []
