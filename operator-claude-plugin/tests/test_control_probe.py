"""Task 1 of 28-02 — the disarmed semantics probe.

Three open questions this phase would otherwise BUILD ON as inferences (28-RESEARCH.md
Open Questions 1–3). The module that answers them performs a real PUT against production,
so nearly every test here is about what it REFUSES to do: it cannot run without
`ALLOW_N8N_PROBE=true`, it cannot run against an instance the config does not pin, and it
contains no code path that writes a write-safety constant at all.

The gate assertions all check `transport.calls == []` rather than 28-01's
`mutating_calls == []`. That is not an oversight and not a stricter reading of the same
rule: 28-01's `apply_mutation` MUST fetch fresh before it can compute a refusal, so its
refusals necessarily carry one GET (D-35). This module's gates run BEFORE any transport is
touched, so here the empty call log is achievable and is the stronger claim — an unset
environment variable leaves no trace on the network at all.
"""
import json

import pytest

import config_gate
import n8n_control
import probe_n8n_semantics as probe

PROBE_ON = "true"
NODE = "Review Trigger (15 min)"
COMMITTED_INTERVAL = [{"field": "minutes", "minutesInterval": 15}]


@pytest.fixture(autouse=True)
def _clean_probe_env(monkeypatch):
    """No test inherits the operator's shell. Each one sets what it means to set."""
    monkeypatch.delenv(probe.PROBE_ENV_VAR, raising=False)
    monkeypatch.delenv(probe.EXPECTED_URL_ENV_VAR, raising=False)


@pytest.fixture
def armed_probe(monkeypatch):
    """The environment gate satisfied — used by every test whose subject is not the gate."""
    monkeypatch.setenv(probe.PROBE_ENV_VAR, PROBE_ON)


def _schedule_node(name=NODE, interval=None):
    return {"name": name, "type": "n8n-nodes-base.scheduleTrigger",
            "parameters": {"rule": {"interval": interval or list(COMMITTED_INTERVAL)}}}


def _workflow(active=False, interval=None, settings=None):
    """Shaped like the live GET: the four PUT-able keys plus the keys n8n rejects on the
    way back in, so `put_body`'s filter has something to actually filter."""
    return {
        "id": "wf-1", "name": "LV Scheduled Maintenance (Cloud)", "active": active,
        "nodes": [_schedule_node(interval=interval),
                  {"name": "SJ-1 Trigger (hourly)", "type": "n8n-nodes-base.scheduleTrigger",
                   "parameters": {"rule": {"interval": [{"field": "hours", "hoursInterval": 1}]}}}],
        "connections": {}, "settings": settings if settings is not None else {},
        "tags": [], "versionId": "v-1", "createdAt": "2026-01-01T00:00:00.000Z",
    }


def _executions(*starts):
    return {"data": [{"id": f"e{i}", "startedAt": ts, "status": "success"}
                     for i, ts in enumerate(starts)]}


def _call(transport, verb, index=0):
    return [c for c in transport.calls if c["verb"] == verb][index]


def _every_subcommand(config, transport_factory, **kwargs):
    """Each probe entry point invoked once against its own fresh recorder."""
    for name, args in (("roundtrip", ("wf-1",)),
                       ("execute_probe", ("wf-1",)),
                       ("cadence_reload", ("wf-1", NODE))):
        transport = transport_factory([])
        yield name, getattr(probe, name)(*args, config, transport=transport, **kwargs), transport


# ---------------------------------------------------------------- the environment gate

def test_with_the_variable_unset_every_subcommand_refuses_without_calling_anything(
        fake_config, stub_module_transport_factory):
    for name, result, transport in _every_subcommand(fake_config, stub_module_transport_factory):
        assert result["verdict"] == probe.REFUSED, name
        assert transport.calls == [], f"{name} touched the network before its gate"
        assert probe.PROBE_ENV_VAR in result["detail"], (
            f"{name}'s refusal must name the variable an admin sets")


@pytest.mark.parametrize("value", ["", "1", "yes", "TRUE", "True", "false", " true"])
def test_only_the_exact_string_true_enables_the_probe(
        monkeypatch, value, fake_config, stub_module_transport_factory):
    """D-34: `ALLOW_N8N_PROBE` and `ALLOW_N8N_ARM` must agree on what counts as "on".
    A gate that accepts `1` here and refuses it there teaches the operator a rule that is
    false half the time."""
    monkeypatch.setenv(probe.PROBE_ENV_VAR, value)

    for name, result, transport in _every_subcommand(fake_config, stub_module_transport_factory):
        assert result["verdict"] == probe.REFUSED, f"{name} accepted {value!r}"
        assert transport.calls == []


def test_the_exact_string_true_does_enable_it(armed_probe, fake_config,
                                              stub_module_transport_factory):
    """Non-vacuity for the four tests above: the gate is refusing on the VALUE, not
    refusing unconditionally."""
    transport = stub_module_transport_factory([_workflow(), {}, _workflow()])

    result = probe.roundtrip("wf-1", fake_config, transport=transport)

    assert result["verdict"] != probe.REFUSED
    assert transport.verbs == ["get", "put", "get"]


# ------------------------------------------------------------------- the instance guard

def test_the_guard_compares_the_config_url_not_the_environment(
        armed_probe, monkeypatch, fake_config, stub_module_transport_factory):
    """The plugin authenticates from `config["n8n_url"]`, so that is the value the guard
    has to read. A guard on `os.getenv("N8N_URL")` — which this plugin never reads —
    cannot fire (D-29, T-28-09). Both hosts below are genuine `.n8n.cloud` tenants, so
    only the pin can tell them apart."""
    monkeypatch.setenv(probe.EXPECTED_URL_ENV_VAR, "https://expected-tenant.n8n.cloud")
    monkeypatch.setenv("N8N_URL", "https://expected-tenant.n8n.cloud")  # never consulted
    config = dict(fake_config, n8n_url="https://some-other-tenant.n8n.cloud")

    for name, result, transport in _every_subcommand(config, stub_module_transport_factory):
        assert result["verdict"] == probe.REFUSED, name
        assert transport.calls == []
        assert "some-other-tenant" in result["detail"] or "expected" in result["detail"].lower()


def test_a_matching_pin_is_accepted(armed_probe, monkeypatch, fake_config,
                                    stub_module_transport_factory):
    monkeypatch.setenv(probe.EXPECTED_URL_ENV_VAR, fake_config["n8n_url"])
    transport = stub_module_transport_factory([_workflow(), {}, _workflow()])

    assert probe.roundtrip("wf-1", fake_config, transport=transport)["verdict"] != probe.REFUSED


def test_with_no_pin_a_non_n8n_cloud_host_still_refuses(armed_probe, fake_config,
                                                        stub_module_transport_factory):
    """Never fail open. An unset pin narrows to "is an n8n host", it does not widen to
    "anything goes" (deploy_n8n_workflows.py::_instance_ok)."""
    config = dict(fake_config, n8n_url="https://attacker.example.com")

    for name, result, transport in _every_subcommand(config, stub_module_transport_factory):
        assert result["verdict"] == probe.REFUSED, name
        assert transport.calls == []


# ----------------------------------------------------------------- the credential gate

def test_a_config_without_an_api_key_refuses_through_require_capability(
        armed_probe, fake_config, stub_module_transport_factory, monkeypatch):
    """One credential source. The refusal is `config_gate`'s own words, produced by the
    same `require_capability` call every other plugin capability makes — not a second
    hand-rolled check that could drift from it (D-29)."""
    seen = []
    real = config_gate.require_capability
    monkeypatch.setattr(config_gate, "require_capability",
                        lambda cfg, cap: seen.append(cap) or real(cfg, cap))
    config = dict(fake_config)
    config.pop("n8n_api_key")

    for name, result, transport in _every_subcommand(config, stub_module_transport_factory):
        assert result["verdict"] == probe.REFUSED, name
        assert transport.calls == [], f"{name} constructed a transport before refusing"
        assert "n8n_api_key" in result["detail"]

    assert seen == ["control", "control", "control"], (
        "every subcommand must go through require_capability(cfg, 'control')")


# ------------------------------------------------------------------ roundtrip (D-20/A3)

def test_roundtrip_puts_back_exactly_what_put_body_produced(
        armed_probe, fake_config, stub_module_transport_factory):
    """The no-op claim, made checkable: byte-identical under a key-sorted dump."""
    fetched = _workflow(active=False, settings={"executionOrder": "v1"})
    transport = stub_module_transport_factory([fetched, {}, fetched])

    probe.roundtrip("wf-1", fake_config, transport=transport)

    sent = _call(transport, "put")["json"]
    assert json.dumps(sent, sort_keys=True) == json.dumps(n8n_control.put_body(fetched),
                                                          sort_keys=True)
    assert set(sent) == set(n8n_control.PUT_BODY_KEYS)
    assert "active" not in sent, "activation state is never a PUT concern"


def test_roundtrip_on_an_active_workflow_brackets_the_put_and_restores_active(
        armed_probe, fake_config, stub_module_transport_factory):
    live = _workflow(active=True)
    transport = stub_module_transport_factory([live, {}, {}, {}, live])

    result = probe.roundtrip("wf-1", fake_config, transport=transport)

    assert transport.verbs == ["get", "post", "put", "post", "get"]
    assert _call(transport, "post", 0)["url"].endswith("/deactivate")
    assert _call(transport, "post", 1)["url"].endswith("/activate")
    assert result["verdict"] == n8n_control.VERIFIED


def test_roundtrip_names_which_key_failed_to_survive(armed_probe, fake_config,
                                                     stub_module_transport_factory):
    """Open Question 3's community report, made observable on THIS instance: a `settings`
    object that comes back different is the finding, and the operator needs to know which
    of the two keys moved."""
    before = _workflow(settings={"executionOrder": "v1"})
    after = _workflow(settings={"executionOrder": "v1", "callerPolicy": "workflowsFromSameOwner"})
    transport = stub_module_transport_factory([before, {}, after])

    result = probe.roundtrip("wf-1", fake_config, transport=transport)

    assert result["verdict"] == n8n_control.FAILED
    assert result["diff"] == ["settings"]
    assert result["observed"]["settings"] == after["settings"]


def test_roundtrip_reports_failed_when_the_readback_is_unreadable(
        armed_probe, fake_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow(), {}, (500, {})])

    assert probe.roundtrip("wf-1", fake_config, transport=transport)["verdict"] == \
        n8n_control.FAILED


# --------------------------------------------------------------- execute_probe (A2)

@pytest.mark.parametrize("status", [404, 405])
def test_a_404_or_405_confirms_the_amendment_and_is_not_an_error(
        armed_probe, status, fake_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([(status, {"message": "not found"})])

    result = probe.execute_probe("wf-1", fake_config, transport=transport)

    assert result["verdict"] == probe.EXPECTED
    assert result["status_code"] == status
    assert transport.verbs == ["post"]
    assert transport.calls[0]["url"].endswith("/api/v1/workflows/wf-1/execute")


def test_a_2xx_is_a_finding_that_overturns_the_amendment_not_a_failure(
        armed_probe, fake_config, stub_module_transport_factory):
    """A "no" from a probe is a build instruction. So is an unexpected "yes" — it must
    surface as a finding to record, never as an error to swallow, and this phase acts on
    it nowhere."""
    transport = stub_module_transport_factory([(200, {"data": {"executionId": "1"}})])

    result = probe.execute_probe("wf-1", fake_config, transport=transport)

    assert result["verdict"] == probe.FINDING
    assert result["status_code"] == 200


def test_an_unexpected_status_is_inconclusive(armed_probe, fake_config,
                                              stub_module_transport_factory):
    transport = stub_module_transport_factory([(500, {})])

    assert probe.execute_probe("wf-1", fake_config,
                               transport=transport)["verdict"] == probe.INCONCLUSIVE


# -------------------------------------------------------------- cadence_reload (D-18/A1)

def _cadence_transport(factory, *, prior=None, probed=None, restored=None,
                       executions=None, active=True, polls=1):
    """The whole cadence sequence scripted in order: pre-read, the change mutation's
    five calls, `polls` polling reads, then the restore mutation's five."""
    prior = prior if prior is not None else list(COMMITTED_INTERVAL)
    probed = probed if probed is not None else [{"field": "minutes", "minutesInterval": 2}]
    restored = restored if restored is not None else prior
    return factory([
        _workflow(active=active, interval=prior),      # the probe's own pre-read
        _workflow(active=active, interval=prior),      # apply_mutation's fresh fetch
        {}, {}, {},                                    # deactivate, put, activate
        _workflow(active=active, interval=probed),     # the change read-back
        *[executions if executions is not None else _executions()] * polls,
        _workflow(active=active, interval=probed),     # restore's fresh fetch
        {}, {}, {},                                    # deactivate, put, activate
        _workflow(active=active, interval=restored),   # the restore read-back
    ])


def _cadence(config, transport, **kwargs):
    return probe.cadence_reload("wf-1", NODE, config, transport=transport,
                                window_minutes=1, poll_seconds=60, sleep=lambda _s: None,
                                **kwargs)


def test_cadence_reload_refuses_on_an_inactive_workflow(armed_probe, fake_config,
                                                        stub_module_transport_factory):
    """The question is specifically whether an ALREADY-RUNNING instance retimes.
    Activation is itself the load event by n8n's own model, so running this against an
    inactive workflow would produce an answer to a different question."""
    transport = stub_module_transport_factory([_workflow(active=False)])

    result = _cadence(fake_config, transport)

    assert result["verdict"] == probe.REFUSED
    assert transport.mutating_calls == []
    assert "active" in result["detail"]


def test_cadence_reload_refuses_when_the_named_node_is_not_there(
        armed_probe, fake_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow(active=True)])

    result = probe.cadence_reload("wf-1", "No Such Trigger", fake_config,
                                  transport=transport, sleep=lambda _s: None)

    assert result["verdict"] == probe.REFUSED
    assert transport.mutating_calls == []


def test_cadence_reload_changes_one_interval_then_puts_the_captured_one_back(
        armed_probe, fake_config, stub_module_transport_factory):
    transport = _cadence_transport(stub_module_transport_factory)

    result = _cadence(fake_config, transport)

    changing, restoring = [c["json"] for c in transport.calls if c["verb"] == "put"]
    assert probe.interval_of(changing, NODE) == [{"field": "minutes", "minutesInterval": 2}]
    assert probe.interval_of(restoring, NODE) == COMMITTED_INTERVAL, (
        "the restore must put back the CAPTURED interval, not a recomputed default")
    assert probe.interval_of(changing, "SJ-1 Trigger (hourly)") == \
        [{"field": "hours", "hoursInterval": 1}], "only one node's interval may move"
    assert result["verdict"] == n8n_control.VERIFIED
    assert result["restore_verdict"] == n8n_control.VERIFIED


def test_cadence_reload_reports_failed_when_the_restoring_readback_mismatches(
        armed_probe, fake_config, stub_module_transport_factory):
    """A probe that leaves a schedule changed is worse than a probe that answers
    nothing — so this verdict is reported separately and it drags the overall one down
    with it (T-28-08)."""
    transport = _cadence_transport(stub_module_transport_factory,
                                   restored=[{"field": "minutes", "minutesInterval": 2}])

    result = _cadence(fake_config, transport)

    assert result["restore_verdict"] == n8n_control.FAILED
    assert result["verdict"] == n8n_control.FAILED
    assert "by hand" in result["detail"], "an unrestored schedule needs a human instruction"


def test_cadence_reload_reports_the_observed_spacing_between_execution_starts(
        armed_probe, fake_config, stub_module_transport_factory):
    transport = _cadence_transport(
        stub_module_transport_factory,
        executions=_executions("2026-07-31T10:00:00.000Z", "2026-07-31T10:02:00.000Z",
                               "2026-07-31T10:04:00.000Z"))

    result = _cadence(fake_config, transport)

    assert result["spacing_minutes"] == [2.0, 2.0]
    assert result["probe_interval_minutes"] == 2
    assert len(result["observed_starts"]) == 3


def test_the_polling_window_is_bounded_by_construction(armed_probe, fake_config,
                                                       stub_module_transport_factory):
    """Not "bounded by a timeout somewhere" — the loop count is derived up front, so a
    stalled clock cannot extend the window a short-intervalled schedule runs in."""
    slept = []
    transport = _cadence_transport(stub_module_transport_factory, polls=4)

    probe.cadence_reload("wf-1", NODE, fake_config, transport=transport,
                         window_minutes=2, poll_seconds=30, sleep=slept.append)

    assert len(slept) == 3, "4 polls over a 2-minute window at 30s spacing, 3 waits"
    assert set(slept) == {30}


# ------------------------------------------------------------------- structural guards

def _source():
    return (probe.__file__ and open(probe.__file__, encoding="utf-8").read())


def test_the_module_names_no_write_safety_constant_at_all(armed_probe):
    """T-28-07. Arming is 28-03's job behind a human gate; a diagnostic that could arm by
    accident defeats the point of running the diagnostic first. Not "does not set one" —
    does not NAME one, so no future edit can reach for it by autocomplete."""
    assert "ALLOW_HUBSPOT" not in _source()
    assert not hasattr(probe, "set_write_safety")


def test_the_module_never_reads_the_backend_scripts_environment_variables():
    src = _source()
    assert 'getenv("N8N_URL")' not in src and "getenv('N8N_URL')" not in src
    assert "N8N_API_KEY" not in src, "credentials come from config_gate.load_config, only"


def test_the_module_writes_no_second_fetcher_or_put_filter():
    src = _source()
    assert "def fetch_workflow" not in src
    assert "def put_body" not in src
    assert "def assert_only_allowlisted_change" not in src
