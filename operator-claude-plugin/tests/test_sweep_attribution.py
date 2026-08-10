"""29-05 Task 3 — silence when healthy, grouping when several fire, attribution on every
notice.

Drives `sweep_entry.run_sweep` end to end, the same way test_sweep_tracer.py does for the
single-condition tracer, but for the multi-condition and D-15 cases this task adds.
"""
import config_gate
import sweep_conditions
import sweep_entry
import sweep_notify

SWEEP_CONFIG = {
    "n8n_url": "https://fake-tenant.n8n.cloud",
    "n8n_api_key": "fake-key-for-tests",
    "webhook_secret": "fake-secret-for-tests",
    # Configured (Phase 45) so these pre-existing fixtures stay quiet on the
    # burn-rate condition rather than spuriously firing burn_rate_not_configured.
    "n8n_monthly_execution_allowance": 2500,
}


def _post_ok(url, headers=None, json=None, timeout=None):
    class _Response:
        status_code = 200

        @staticmethod
        def json():
            return {"queues": {}, "providers": {}}
    return _Response()


# --- healthy is silent, structurally -----------------------------------------------------


def test_an_all_healthy_input_produces_no_notice_at_all(executions_healthy, sweep_now,
                                                        stub_get_transport_factory):
    get = stub_get_transport_factory([{"data": executions_healthy}])
    notices = sweep_entry.run_sweep(SWEEP_CONFIG, get_transport=get,
                                    post_transport=_post_ok, now=sweep_now)
    assert notices == []


def test_sweep_conditions_render_of_nothing_fired_is_the_empty_list():
    assert sweep_notify.render([]) == []


# --- D-15's cannot-run notices are preserved, not swallowed by structural silence --------


def test_a_missing_capability_still_notices_rather_than_silence(sweep_now,
                                                                 stub_get_transport_factory):
    config = {k: v for k, v in SWEEP_CONFIG.items() if k != "webhook_secret"}
    notices = sweep_entry.run_sweep(
        config, get_transport=stub_get_transport_factory([{"data": []}]),
        post_transport=_post_ok, now=sweep_now)

    assert len(notices) == 1
    assert notices[0]["condition"] == "sweep_not_configured"
    assert notices[0]["who_can_fix"] == "admin"


def test_an_all_reads_unavailable_gather_still_notices_rather_than_silence(sweep_now,
                                                                           stub_get_transport_factory):
    def failing_get(url, headers=None, params=None, timeout=None):
        raise RuntimeError("connection refused")

    def failing_post(url, headers=None, json=None, timeout=None):
        raise RuntimeError("connection refused")

    notices = sweep_entry.run_sweep(SWEEP_CONFIG, get_transport=failing_get,
                                    post_transport=failing_post, now=sweep_now)

    assert len(notices) == 1
    assert notices[0]["condition"] == "sweep_blind"


# --- single fired condition renders exactly as 29-03 shipped it -------------------------


def test_one_fired_condition_renders_as_its_own_single_notice():
    fired = [{"condition": sweep_conditions.STUCK, "execution_id": "e-1",
             "workflow_name": "LV Enrichment (Cloud template)",
             "reason": "a run has been going for 45 minutes"}]
    notices = sweep_notify.render(fired)
    assert len(notices) == 1
    assert notices[0]["condition"] == sweep_conditions.STUCK


# --- several fired conditions group into one delivery ------------------------------------


def _synthetic_conditions(count):
    return [{"condition": f"synthetic_condition_{i}", "workflow_name": "a backend workflow",
            "reason": f"synthetic reason number {i}"} for i in range(count)]


def test_several_simultaneous_conditions_produce_one_grouped_delivery_with_a_stated_count():
    fired = _synthetic_conditions(sweep_notify.GROUPED_DETAIL_CEILING + 2)
    notices = sweep_notify.render(fired)

    assert len(notices) == 1
    notice = notices[0]
    assert notice["condition"] == "grouped"
    assert "\n" not in notice["headline"], "banner budget is one line (A5)"
    assert "2 more" in notice["detail"]
    # Nothing dropped silently: every fired condition's own tag is traceable in the
    # detail — the shown ones by name, the rest by the stated count.
    for shown in fired[:sweep_notify.GROUPED_DETAIL_CEILING]:
        assert shown["condition"] in notice["detail"]


def test_the_most_actionable_item_is_first_in_the_grouped_delivery():
    # The first two synthetic reasons don't match error_table's table (admin by
    # default); the third's text matches the malformed_record pattern, which
    # error_table attributes to the OPERATOR — despite arriving last in `fired`, it must
    # sort to the front of the group.
    fired = [
        {"condition": "admin_only_a", "reason": "an unrecognised failure signature"},
        {"condition": "admin_only_b", "reason": "another unrecognised failure signature"},
        {"condition": "operator_fixable",
         "reason": "the CRM returned a 400 bad request — property values were not valid"},
    ]
    notices = sweep_notify.render(fired)
    assert len(notices) == 1
    assert "operator_fixable" in notices[0]["headline"]
    assert notices[0]["detail"].index("[operator_fixable]") < notices[0]["detail"].index("[admin_only_a]")


# --- an unrecognized cause defaults to admin and is labelled an interpretation -----------


def test_an_unrecognized_cause_is_attributed_to_admin_with_the_interpretation_label_and_raw_text():
    fired = [{"condition": "some_new_condition", "execution_id": None,
             "reason": "a completely novel failure signature never seen before"}]
    notice = sweep_notify.render(fired)[0]

    assert notice["who_can_fix"] == "admin"
    assert notice["is_interpretation"] is True
    assert "novel failure signature" in notice["raw"]
    assert "interpretation" in notice["detail"].lower()
    assert notice["raw"] in notice["detail"]


# --- every generated notice carries an attribution field --------------------------------


def test_every_generated_notice_carries_an_operator_or_admin_attribution_field():
    single = sweep_notify.render([{"condition": "x", "reason": "unrecognised text"}])
    grouped = sweep_notify.render(_synthetic_conditions(3))

    for notice in single + grouped:
        assert notice["who_can_fix"] in ("operator", "admin")


# --- no notice ever instructs the operator to run anything --------------------------------


def test_no_notice_in_a_grouped_delivery_instructs_the_operator_to_run_anything():
    fired = _synthetic_conditions(3) + [{
        "condition": sweep_conditions.STUCK_ARMED, "workflow_name": "LV Enrichment (Cloud template)",
        "flag": "ALLOW_HUBSPOT_RECORD_WRITES",
        "reason": ("ALLOW_HUBSPOT_RECORD_WRITES is armed on LV Enrichment (Cloud template) "
                  "with nothing currently dispatching against it; check and disarm it "
                  "from the backend-control skill rather than editing the workflow directly"),
    }]
    notices = sweep_notify.render(fired)
    text = "\n".join(n["headline"] + n["detail"] for n in notices).lower()
    for forbidden in ("run this", "terminal", "python3 ", "curl "):
        assert forbidden not in text
