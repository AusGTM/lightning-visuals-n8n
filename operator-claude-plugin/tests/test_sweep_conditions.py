"""Per-condition coverage for sweep_conditions.py (29-05).

test_sweep_tracer.py proved the layers connect end to end for the one condition 29-03
shipped. This file proves each condition 29-05 adds, in isolation, against every fixture
shape conftest carries for it — including the shapes that look healthy and are not.

Task 1: quota-exhausted and credential-failure — new judgment over Phase 27's existing
credit-probe data (D-08a), across all four provider fixture states.

Task 2: failed-scheduled-run, review-backlog, the maintenance workflow's swallowed-failure
blind spot (D-08b), and D-10's stuck-armed backstop.
"""
import error_table
import sweep_conditions
import sweep_read

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


# --- Task 2: failed-scheduled-run, review-backlog, swallowed-maintenance-failure,
# stuck-armed (D-08b, D-10) --------------------------------------------------------------

_SWEEP_CONFIG = {
    "n8n_url": "https://fake-tenant.n8n.cloud",
    "n8n_api_key": "fake-key-for-tests",
    "webhook_secret": "fake-secret-for-tests",
}


def _post_404(url, headers=None, json=None, timeout=None):
    class _Response:
        status_code = 404
    return _Response()


def _gather(executions, sweep_now, stub_get_transport_factory, workflows=None,
           post=_post_404):
    """Drives the real sweep_read.gather wiring over a fixture's raw execution list, so
    Task 2's conditions are proven against what gather ACTUALLY produces (workflow_id,
    the maintenance workflow's harvested run data) rather than a hand-built stand-in."""
    payloads = [{"data": executions}]
    maintenance_item = next(
        (e for e in executions
         if (e.get("workflowData") or {}).get("name") == sweep_read.MAINTENANCE_WORKFLOW_NAME),
        None)
    if maintenance_item is not None:
        payloads.append(maintenance_item)  # the extra gated get_execution response
    payloads.append({"data": workflows or []})
    get = stub_get_transport_factory(payloads)
    return sweep_read.gather(_SWEEP_CONFIG, get_transport=get, post_transport=post,
                             now=sweep_now)


# --- check_failed_run -------------------------------------------------------------------


def test_a_failed_run_fires_the_failed_run_condition_and_names_the_workflow(
        executions_with_failure, sweep_now, stub_get_transport_factory):
    gathered = _gather(executions_with_failure, sweep_now, stub_get_transport_factory)
    fired = sweep_conditions.evaluate(gathered)

    failed = [c for c in fired if c["condition"] == sweep_conditions.FAILED_RUN]
    assert len(failed) == 1
    assert failed[0]["execution_id"] == "e-202"
    assert failed[0]["workflow_name"]


def test_a_healthy_page_fires_no_failed_run_condition(executions_healthy, sweep_now,
                                                      stub_get_transport_factory):
    gathered = _gather(executions_healthy, sweep_now, stub_get_transport_factory)
    fired = sweep_conditions.evaluate(gathered)
    assert not any(c["condition"] == sweep_conditions.FAILED_RUN for c in fired)


# --- check_review_backlog ---------------------------------------------------------------


def test_review_backlog_fires_above_threshold_and_not_at_or_below_it(
        backend_status_review_backlog):
    fired = sweep_conditions.check_review_backlog(
        backend_status_review_backlog["data"]["counts"])
    assert any(c["condition"] == sweep_conditions.REVIEW_BACKLOG for c in fired)

    at_threshold = {"companies_awaiting_review": 10, "contacts_awaiting_review": 15}
    assert sum(at_threshold.values()) == sweep_conditions.DEFAULT_REVIEW_BACKLOG_THRESHOLD
    assert sweep_conditions.check_review_backlog(at_threshold) == []

    just_above = dict(at_threshold, contacts_awaiting_review=16)
    assert sweep_conditions.check_review_backlog(just_above) != []


def test_review_backlog_never_treats_an_unreadable_half_as_zero():
    half_unreadable = {"companies_awaiting_review": None, "contacts_awaiting_review": 9999}
    assert sweep_conditions.check_review_backlog(half_unreadable) == []


# --- check_swallowed_maintenance_failure -------------------------------------------------


def test_swallowed_maintenance_failure_fires_when_findings_exist():
    maintenance_errors = {"available": True, "reason": None, "findings": [{
        "node": "SJ-1 Search (input-gap scan)", "level": "node", "count": 1,
        "matched": True, "cause": "expired_credential",
        "sentence": "The saved login for one of the connected services was rejected.",
        "who_can_fix": "admin", "is_interpretation": False, "raw": "401",
    }]}
    fired = sweep_conditions.check_swallowed_maintenance_failure(maintenance_errors)
    assert len(fired) == 1
    assert fired[0]["condition"] == sweep_conditions.SWALLOWED_MAINTENANCE_FAILURE


def test_an_unreadable_maintenance_harvest_does_not_read_as_health():
    for unreadable in (
        {"available": False, "reason": "no_recent_maintenance_execution", "findings": []},
        {"available": False, "reason": "could_not_read_execution", "findings": []},
        {"available": False,
         "reason": "execution payload has no 'data' section (it was fetched without includeData)",
         "findings": []},
    ):
        assert sweep_conditions.check_swallowed_maintenance_failure(unreadable) == []


def test_the_falsely_successful_maintenance_run_fires_through_the_real_gather_wiring(
        execution_maintenance_falsely_successful, sweep_now, stub_get_transport_factory):
    """D-08b end to end: the fixture reports `status: success` — this must be caught
    through harvest_errors, not by run status, which is exactly what it hides."""
    gathered = _gather([execution_maintenance_falsely_successful], sweep_now,
                       stub_get_transport_factory)

    assert gathered["maintenance_errors"]["available"] is True
    assert gathered["maintenance_errors"]["findings"], "the fixture's failed search node must surface"

    fired = sweep_conditions.evaluate(gathered)
    assert any(c["condition"] == sweep_conditions.SWALLOWED_MAINTENANCE_FAILURE for c in fired)
    assert not any(c["condition"] == sweep_conditions.FAILED_RUN for c in fired), (
        "the execution's own status is 'success' — the ordinary failed-run check must "
        "not (and cannot) fire here; that is the whole point of the blind spot"
    )


# --- check_stuck_armed (D-10, D-16) ------------------------------------------------------


def _armed_workflow(workflow_id, name, flag):
    return {"id": workflow_id, "name": name, "nodes": [
        {"name": "Write Gate", "parameters": {"jsCode": f'const {flag} = "true";'}},
    ]}


def _disarmed_workflow(workflow_id, name):
    return {"id": workflow_id, "name": name, "nodes": [
        {"name": "Write Gate A",
         "parameters": {"jsCode": 'const ALLOW_HUBSPOT_RECORD_WRITES = "false";'}},
        {"name": "Write Gate B",
         "parameters": {"jsCode": 'const ALLOW_HUBSPOT_CREATE = "false";'}},
    ]}


def test_stuck_armed_fires_when_armed_with_nothing_running():
    workflows = {"available": True,
                "items": [_armed_workflow("wf-1", "LV Enrichment (Cloud template)",
                                          "ALLOW_HUBSPOT_RECORD_WRITES")]}
    fired = sweep_conditions.check_stuck_armed(workflows, executions_summaries=[])
    assert len(fired) == 1
    assert fired[0]["flag"] == "ALLOW_HUBSPOT_RECORD_WRITES"
    assert fired[0]["condition"] == sweep_conditions.STUCK_ARMED


def test_stuck_armed_does_not_fire_during_a_legitimate_in_flight_dispatch():
    workflows = {"available": True,
                "items": [_armed_workflow("wf-1", "LV Enrichment (Cloud template)",
                                          "ALLOW_HUBSPOT_RECORD_WRITES")]}
    summaries = [{"workflow_id": "wf-1", "in_flight": True}]
    assert sweep_conditions.check_stuck_armed(workflows, summaries) == []


def test_stuck_armed_does_not_fire_on_a_properly_disarmed_workflow():
    workflows = {"available": True,
                "items": [_disarmed_workflow("wf-1", "LV Enrichment (Cloud template)")]}
    assert sweep_conditions.check_stuck_armed(workflows, []) == []


def test_stuck_armed_fires_for_each_of_the_two_flags_independently():
    record_writes = {"available": True,
                     "items": [_armed_workflow("wf-1", "LV Enrichment (Cloud template)",
                                               "ALLOW_HUBSPOT_RECORD_WRITES")]}
    create = {"available": True,
             "items": [_armed_workflow("wf-2", "LV Contact Ingest (Cloud template)",
                                       "ALLOW_HUBSPOT_CREATE")]}

    assert sweep_conditions.check_stuck_armed(record_writes, [])[0]["flag"] == \
        "ALLOW_HUBSPOT_RECORD_WRITES"
    assert sweep_conditions.check_stuck_armed(create, [])[0]["flag"] == \
        "ALLOW_HUBSPOT_CREATE"


def test_stuck_armed_fires_on_disagreement_rather_than_being_swallowed_as_unknown():
    desynced = {"id": "wf-4", "name": "LV Enrichment (Cloud template)", "nodes": [
        {"name": "Gate A",
         "parameters": {"jsCode": 'const ALLOW_HUBSPOT_RECORD_WRITES = "true";'}},
        {"name": "Gate B",
         "parameters": {"jsCode": 'const ALLOW_HUBSPOT_RECORD_WRITES = "false";'}},
    ]}
    workflows = {"available": True, "items": [desynced]}

    fired = sweep_conditions.check_stuck_armed(workflows, [])
    matches = [c for c in fired if c["flag"] == "ALLOW_HUBSPOT_RECORD_WRITES"]
    assert matches, "a disagreement must fire, not be swallowed as unknown"
    assert "disagree" in matches[0]["reason"]


def test_stuck_armed_skips_a_workflow_whose_nodes_could_not_be_read():
    unreadable = {"id": "wf-5", "name": "LV Enrichment (Cloud template)"}  # no "nodes" key
    workflows = {"available": True, "items": [unreadable]}
    assert sweep_conditions.check_stuck_armed(workflows, []) == []
