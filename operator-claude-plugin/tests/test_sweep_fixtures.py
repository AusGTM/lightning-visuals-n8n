"""operator-claude-plugin/tests/test_sweep_fixtures.py

Phase 29 Plan 02 Task 1 — the guard on the sweep fixtures themselves.

29-03/04/05 all verify against mocked execution and backend-status payloads. Two of the
shapes they must reason about look HEALTHY and are not: a maintenance run reporting
`success` while one of its `onError: continueRegularOutput` search nodes quietly failed
(29-RESEARCH Pitfall 1 / D-08b), and a provider whose balance is UNKNOWN rather than zero
(Pitfall 5). This file exists to fail if a later edit collapses either into the ordinary
case — an unknown flattened to zero, or a false success read as a plain success.

Every stuck assertion runs `n8n_read.summarize_execution` — the function Phase 27 actually
shipped (D-14) — at the fixed `sweep_now` reference, never wall-clock, so a fixture cannot
drift across the threshold depending on when the suite runs.
"""
import n8n_read
from conftest import MAINTENANCE_SEARCH_NODES


# --- executions -----------------------------------------------------------------------

def test_healthy_executions_all_carry_both_timestamps(executions_healthy):
    """The no-notice baseline: nothing in flight, nothing failed, every duration knowable."""
    assert len(executions_healthy) >= 2
    for execution in executions_healthy:
        assert execution["status"] == "success"
        assert execution["startedAt"] and execution["stoppedAt"]


def test_healthy_executions_produce_no_stuck_verdict(executions_healthy, fake_config, sweep_now):
    verdicts = [n8n_read.summarize_execution(e, fake_config, now=sweep_now)["stuck"]
                for e in executions_healthy]
    assert verdicts == [False] * len(executions_healthy)


def test_failure_fixture_carries_a_named_workflow_and_error_status(executions_with_failure):
    errored = [e for e in executions_with_failure if e["status"] == "error"]
    assert len(errored) == 1
    assert errored[0]["workflowData"]["name"]


def test_stuck_fixture_holds_both_sides_of_the_threshold(executions_with_stuck, fake_config,
                                                         sweep_now):
    """A stuck check that flags every running execution must fail here, not pass."""
    verdicts = [n8n_read.summarize_execution(e, fake_config, now=sweep_now)["stuck"]
                for e in executions_with_stuck]
    assert True in verdicts, "no past-threshold running execution in the fixture"
    assert False in verdicts, "no within-threshold running execution in the fixture"


def test_missing_stopped_at_is_absent_not_zero(execution_missing_stopped_at):
    """Duration unknown. A fixture carrying `stoppedAt: 0` or an empty string would let a
    duration helper return 0 and still pass its own tests."""
    assert execution_missing_stopped_at["status"] == "running"
    assert "stoppedAt" not in execution_missing_stopped_at
    assert execution_missing_stopped_at["startedAt"]


def test_unreadable_start_yields_stuck_none_not_false(execution_unreadable_start, fake_config,
                                                      sweep_now):
    """Phase 27 D-07b(i): in flight with an age we cannot read is the third state. Rounding
    it to False reports a possibly-wedged run as fine."""
    summary = n8n_read.summarize_execution(execution_unreadable_start, fake_config, now=sweep_now)
    assert summary["stuck"] is None
    assert summary["in_flight"] is True
    assert summary["running_for_minutes"] is None


# --- the maintenance run that says success and is not (D-08b) --------------------------

def test_maintenance_fixture_reports_success_at_the_run_level(
        execution_maintenance_falsely_successful):
    assert execution_maintenance_falsely_successful["status"] == "success"
    assert execution_maintenance_falsely_successful["finished"] is True


def test_maintenance_fixture_keys_its_run_data_on_the_deployed_node_names(
        execution_maintenance_falsely_successful):
    """D-21: fixtures keyed on 29-RESEARCH's abbreviations would pass while the live sweep
    found nothing, because the abbreviations match no key in `runData`."""
    run_data = execution_maintenance_falsely_successful["data"]["resultData"]["runData"]
    assert set(MAINTENANCE_SEARCH_NODES) <= set(run_data)


def test_maintenance_fixture_carries_a_failed_search_under_a_successful_run(
        execution_maintenance_falsely_successful):
    run_data = execution_maintenance_falsely_successful["data"]["resultData"]["runData"]
    broken = [name for name in MAINTENANCE_SEARCH_NODES
              if run_data[name][0].get("error") is not None]
    healthy = [name for name in MAINTENANCE_SEARCH_NODES
               if run_data[name][0].get("error") is None]
    assert broken, "no failed search node — the fixture is just a plain success"
    assert healthy, "every search node failed — the fixture no longer looks healthy"
    assert run_data[broken[0]][0]["data"]["main"][0] == [], "a failed search still returned rows"


# --- backend status: three provider states, not two ------------------------------------

def _balances(fixture):
    return fixture["data"]["balances"]


def _health(fixture, source):
    return next(e for e in fixture["data"]["credential_health"] if e["source"] == source)


def test_healthy_backend_carries_numeric_balances(backend_status_healthy):
    assert backend_status_healthy["available"] is True
    credits = [b["credits"] for b in _balances(backend_status_healthy)]
    assert credits and all(isinstance(c, (int, float)) and c > 0 for c in credits)


def test_the_three_provider_states_are_three_distinguishable_shapes(
        backend_status_healthy, backend_status_unknown_balance,
        backend_status_unconfigured_provider):
    """Numeric, unknown, and never-probed. Pitfall 5: collapsing unknown into exhausted
    tells the operator Apollo is out of credits when the account simply cannot be read."""
    numeric = _balances(backend_status_healthy)[0]
    unknown = next(b for b in _balances(backend_status_unknown_balance) if b["credits"] is None)

    assert isinstance(numeric["credits"], (int, float))
    assert unknown["credits"] is None and unknown["configured"] is True
    assert unknown["unreadable"] is True
    assert _health(backend_status_unknown_balance, unknown["provider"])["state"] == "refused"

    # The third state is a provider that was never probed at all: absent from `balances`
    # entirely, present in credential_health as not_configured. That is the shape the
    # deployed endpoint actually emits — `Build Credit Status` maps over the REQUESTED
    # providers and hardcodes configured:true, so a `configured: false` balances row does
    # not exist in production (29-CONTEXT D-22).
    unconfigured = _health(backend_status_unconfigured_provider, "apollo")
    assert unconfigured["state"] == "unknown"
    assert unconfigured["reason"] == "not_configured"
    assert all(b["provider"] != "apollo" for b in _balances(backend_status_unconfigured_provider))


def test_exhausted_is_an_explicit_number_at_or_below_a_floor(backend_status_exhausted):
    """The only shape the quota-exhausted condition may fire on."""
    exhausted = [b for b in _balances(backend_status_exhausted) if b["credits"] == 0]
    assert exhausted
    assert exhausted[0]["unreadable"] is False
    assert exhausted[0]["error"] is None


def test_review_backlog_counts_are_numbers_above_any_plausible_threshold(
        backend_status_review_backlog):
    counts = backend_status_review_backlog["data"]["counts"]
    assert counts["companies_awaiting_review"] > 100
    assert counts["contacts_awaiting_review"] > 100


def test_a_zero_count_and_an_unreadable_count_are_two_shapes(backend_status_healthy,
                                                             backend_status_unknown_balance):
    """STATUS-06 / D-08 at the fixture level: a genuine 0 (nothing awaiting review) and an
    unreadable null (the search itself failed) are opposite findings. The healthy fixture
    carries the zero; the unknown fixture carries the null."""
    assert backend_status_healthy["data"]["counts"]["companies_awaiting_review"] == 0
    assert backend_status_unknown_balance["data"]["counts"]["companies_awaiting_review"] is None
