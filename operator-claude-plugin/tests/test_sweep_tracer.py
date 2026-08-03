"""29-03 Task 1 — the tracer: one condition, every layer, end to end.

These drive `sweep_entry.run_sweep` — entrypoint in, notices out — over 29-02's
fixtures. Per-layer coverage arrives with 29-05's conditions; what THIS file proves is
that the layers connect, and that the two silences are different things: a healthy
backend is silent, a sweep that cannot run is never silent (D-15).
"""
import pytest

import config_gate
import sweep_entry

SWEEP_CONFIG = {
    "n8n_url": "https://fake-tenant.n8n.cloud",
    "n8n_api_key": "fake-key-for-tests",
    "webhook_secret": "fake-secret-for-tests",
}


class _BackendOK:
    """A 200 backend-status answer, so the healthy case's silence is earned by
    successful reads, not by unreadable ones."""
    status_code = 200

    @staticmethod
    def json():
        return {"queues": {}, "providers": {}}


def _post_ok(url, headers=None, json=None, timeout=None):
    return _BackendOK()


def _run(executions, sweep_now, stub_get_transport_factory, post=_post_ok,
         config=SWEEP_CONFIG):
    get = stub_get_transport_factory([{"data": executions}])
    return sweep_entry.run_sweep(config, get_transport=get, post_transport=post,
                                 now=sweep_now)


# --- the tracer path --------------------------------------------------------------------

def test_a_stuck_run_produces_exactly_one_notice_naming_it(
        executions_with_stuck, sweep_now, stub_get_transport_factory):
    notices = _run(executions_with_stuck, sweep_now, stub_get_transport_factory)

    assert len(notices) == 1, "the within-threshold run must not also fire"
    notice = notices[0]
    assert notice["condition"] == "stuck_execution"
    assert notice["execution_id"] == "e-301"
    assert "45 minutes" in notice["detail"]
    assert "\n" not in notice["headline"], "banner budget is one line (A5)"


def test_a_healthy_backend_produces_nothing_at_all(
        executions_healthy, sweep_now, stub_get_transport_factory):
    """Not an empty report, not an all-clear — nothing (NOTICE-04)."""
    notices = _run(executions_healthy, sweep_now, stub_get_transport_factory)
    assert notices == []


def test_the_within_threshold_run_alone_is_silent(sweep_now,
                                                  stub_get_transport_factory,
                                                  executions_with_stuck):
    """A condition that flags every running execution fails here."""
    within_only = [e for e in executions_with_stuck if e["id"] == "e-302"]
    assert within_only, "fixture changed shape"
    notices = _run(within_only, sweep_now, stub_get_transport_factory)
    assert notices == []


def test_an_unreadable_age_fires_its_own_notice_not_silence(
        execution_unreadable_start, sweep_now, stub_get_transport_factory):
    """The tri-state's None: in flight, age unknown. Rounding it down to fine is the
    bug Phase 27 D-07b(i) exists to prevent (D-14)."""
    notices = _run([execution_unreadable_start], sweep_now, stub_get_transport_factory)

    assert len(notices) == 1
    assert notices[0]["condition"] == "stuck_age_unreadable"
    assert "could not be read" in notices[0]["detail"]


# --- attribution ------------------------------------------------------------------------

def test_notices_carry_an_attribution_and_unrecognized_causes_go_to_admin(
        executions_with_stuck, sweep_now, stub_get_transport_factory):
    notice = _run(executions_with_stuck, sweep_now, stub_get_transport_factory)[0]

    assert notice["who_can_fix"] in ("operator", "admin")
    # A stuck-run cause is not in error_table's matched set, so the guardrail applies:
    # unmatched -> admin, decided inside error_table.translate, not here.
    assert notice["who_can_fix"] == "admin"


def test_no_notice_instructs_the_operator_to_run_anything(
        executions_with_stuck, sweep_now, stub_get_transport_factory):
    notice = _run(executions_with_stuck, sweep_now, stub_get_transport_factory)[0]
    text = (notice["headline"] + notice["detail"]).lower()
    for forbidden in ("run this", "terminal", "python3 ", "curl "):
        assert forbidden not in text


# --- D-15: a sweep that cannot run says so ----------------------------------------------

def test_the_sweep_capability_row_requires_all_three_keys():
    assert set(config_gate.CAPABILITY_KEYS["sweep"]) == {
        "n8n_url", "n8n_api_key", "webhook_secret"}


def test_a_config_missing_a_sweep_key_notices_rather_than_raising_or_silence(
        sweep_now, stub_get_transport_factory):
    config = {k: v for k, v in SWEEP_CONFIG.items() if k != "webhook_secret"}

    notices = sweep_entry.run_sweep(
        config, get_transport=stub_get_transport_factory([{"data": []}]),
        post_transport=_post_ok, now=sweep_now)

    assert len(notices) == 1
    assert notices[0]["condition"] == "sweep_not_configured"
    assert notices[0]["who_can_fix"] == "admin"
    assert "webhook_secret" in notices[0]["detail"], "names the missing KEY"
    assert "fake-" not in notices[0]["detail"], "never a value"
    assert "NOT watching" in notices[0]["headline"]


def test_a_gather_where_every_read_failed_notices_rather_than_silence(
        sweep_now, stub_get_transport_factory):
    """Zero fired conditions is only silence when the reads actually succeeded."""
    failing_get = stub_get_transport_factory([RuntimeError("connection refused")])

    def failing_post(url, headers=None, json=None, timeout=None):
        raise RuntimeError("connection refused")

    notices = sweep_entry.run_sweep(SWEEP_CONFIG, get_transport=failing_get,
                                    post_transport=failing_post, now=sweep_now)

    assert len(notices) == 1
    assert notices[0]["condition"] == "sweep_blind"
    assert "cannot see the backend" in notices[0]["headline"]


def test_a_half_dead_gather_stays_quiet_about_only_the_unreadable_half(
        executions_healthy, sweep_now, stub_get_transport_factory):
    """Executions readable + backend 404 (today's live state): healthy executions and
    no backend-fed conditions in this slice -> silence, NOT sweep_blind."""
    def post_404(url, headers=None, json=None, timeout=None):
        class R:
            status_code = 404
        return R()

    notices = _run(executions_healthy, sweep_now, stub_get_transport_factory,
                   post=post_404)
    assert notices == []
