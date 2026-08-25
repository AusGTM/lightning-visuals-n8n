"""53-02 Task 3 — the two guardrails 53-CONTEXT.md asked the planner to SURFACE, not assume.

Their own file, deliberately. These are the phase's proposed defences and the operator
asked for them by name, so a reviewer looking for them should find them somewhere a
reviewer looks — the same habit `test_enrich_before_ingest_skill_contract.py` follows for
its own safety contract.

The asymmetry the file exists to hold:

  GUARDRAIL A (D-53-03) refuses to open a grant over a backend where writes are already
  live, or where nobody can tell, and OFFERS a disarm without taking one. Its transport log
  is asserted to hold reads only, so a later edit cannot quietly make it act. A guardrail
  that silently repaired the state would delete the evidence that a previous session died
  armed — the one signal telling the operator what the client-held design is costing them.

  GUARDRAIL B (D-53-04) is the opposite case, and its two closes DO disarm: each closes
  having just observed live writes or having twice failed to turn them off, so it is
  closing a window its own run opened. `n8n_arming.disarm` is ungated by design, so this
  adds no authority anywhere — and the grant CLOSES EVEN WHEN THAT DISARM FAILS, because a
  failed closing disarm must never be a reason to leave the grant open.
"""
import inspect
from pathlib import Path

import pytest

import config_gate
import executions_client
import n8n_arming
import write_grant

WORKFLOW_ID = "wf-enrichment-1"
CONTACTS_WORKFLOW_ID = "wf-contacts-1"
RECORD_ID = "12345"


def _gate(record_writes='"false"', create='"false"', ids='""', domains='""'):
    return (f"const ALLOW_HUBSPOT_RECORD_WRITES = {record_writes};\n"
            f"const ALLOW_HUBSPOT_CREATE = {create};\n"
            f"const TEST_RECORD_IDS = {ids};\n"
            f"const TEST_RECORD_DOMAINS = {domains};\n"
            "function _writeSafetyAllows() { return false; }\n")


def _workflow(record_writes='"false"', create='"false"', ids='""', domains='""',
              name=None, second_gate=None):
    """Two declaring nodes, as the deployed workflows have. `second_gate` lets a test make
    them DISAGREE, which is a real desync shape (a partial deploy or a hand edit in the
    n8n UI) and must never be reported as a guess."""
    first = _gate(record_writes, create, ids, domains)
    return {
        "id": WORKFLOW_ID,
        "name": name or write_grant.LANES["enrichment"],
        "active": True, "settings": {}, "connections": {},
        "nodes": [
            {"name": "Update Write Gate", "parameters": {"jsCode": first}},
            {"name": "Create Write Gate",
             "parameters": {"jsCode": second_gate if second_gate is not None else first}},
            {"name": "Webhook", "parameters": {}},
        ],
    }


def _armed_workflow():
    return _workflow(record_writes='"true"', create='"true"',
                     ids='"9999,8888"', domains='"already.example"')


def _workflow_list():
    return {"data": [
        {"id": WORKFLOW_ID, "name": write_grant.LANES["enrichment"]},
        {"id": CONTACTS_WORKFLOW_ID, "name": write_grant.LANES["contacts"]},
    ]}


@pytest.fixture(autouse=True)
def _clean_arm_env(monkeypatch):
    monkeypatch.delenv(n8n_arming.ARM_ENV_VAR, raising=False)


@pytest.fixture(autouse=True)
def _clear_workflow_id_cache():
    executions_client._workflow_id_cache.clear()
    yield
    executions_client._workflow_id_cache.clear()


@pytest.fixture
def granting_config(fake_config):
    return {**fake_config, config_gate.WRITE_GRANT_SETTINGS_KEY: True}


def _plan(config, transport, lanes=("enrichment",)):
    return write_grant.plan_grant(
        config, lanes=list(lanes), object_type="companies", record_ids=[RECORD_ID],
        record_domains=[], allow_create=False, label="the guardrail batch",
        transport=transport)


def _open_grant(config, transport):
    proposal = _plan(config, transport)
    assert proposal.get("kind") == write_grant.PROPOSAL_KIND, proposal
    return write_grant.open_grant(proposal, "yes", config)


# =========================================================================================
# GUARDRAIL A — refuse to open over an already-armed backend (D-53-03)
# =========================================================================================

def test_an_open_over_a_live_armed_backend_refuses_and_names_what_it_found(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow_list(), _armed_workflow()])

    result = _plan(granting_config, transport)

    assert result["outcome"] == write_grant.REFUSED
    detail = result["detail"]
    # The workflow, by name and by id.
    assert write_grant.LANES["enrichment"] in detail
    assert WORKFLOW_ID in detail
    # Every dispatch flag it read, with its value.
    for flag in n8n_arming.DISPATCH_FLAGS:
        assert flag in detail
    assert "ALLOW_HUBSPOT_RECORD_WRITES, ALLOW_HUBSPOT_CREATE reads enabled" in detail
    assert result["faults"]["enrichment"]["live_flags"] == [
        "ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE"]
    # The record allowlist currently in force — without it the operator is guessing at
    # what that live window can already write.
    assert "9999,8888" in detail
    assert "already.example" in detail


def test_the_refusal_offers_a_disarm_and_does_not_perform_one(
        granting_config, stub_module_transport_factory):
    """D-53-03 mandates offer-only. The operator decides."""
    transport = stub_module_transport_factory([_workflow_list(), _armed_workflow()])

    result = _plan(granting_config, transport)

    assert result["offered_action"] == "disarm"
    assert "ask me to disarm" in result["detail"]
    assert "I have NOT changed anything" in result["detail"]


def test_guardrail_as_transport_log_holds_reads_only(
        granting_config, stub_module_transport_factory):
    """The pin that stops a later edit quietly making guardrail A act. A disarm would show
    up here as a PUT — `n8n_control.apply_mutation` cannot disarm without one."""
    transport = stub_module_transport_factory([_workflow_list(), _armed_workflow()])

    _plan(granting_config, transport)

    assert transport.verbs == ["get", "get"]
    assert transport.mutating_calls == []


def test_an_open_over_a_disarmed_backend_proceeds(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow_list(), _workflow()])

    proposal = _plan(granting_config, transport)

    assert proposal["kind"] == write_grant.PROPOSAL_KIND


def test_a_workflow_that_cannot_be_read_refuses_the_open(
        granting_config, stub_module_transport_factory):
    """THE ONE A HURRIED IMPLEMENTATION GETS WRONG. An unreadable write-safety state is not
    a disarmed one, and this guardrail fires exactly when something is already wrong."""
    transport = stub_module_transport_factory([_workflow_list(), (500, {"message": "no"})])

    result = _plan(granting_config, transport)

    assert result["outcome"] == write_grant.REFUSED
    assert "could not be read at all" in result["detail"]


def test_a_workflow_with_no_declarations_at_all_refuses_the_open(
        granting_config, stub_module_transport_factory):
    """A 200 carrying a body with nothing to read is the same answer as an unreachable
    one: nobody can say whether writes are on."""
    transport = stub_module_transport_factory([_workflow_list(), {"id": WORKFLOW_ID,
                                                                 "nodes": []}])

    result = _plan(granting_config, transport)

    assert result["outcome"] == write_grant.REFUSED
    assert "could not be read at all" in result["detail"]


def test_declaring_nodes_that_disagree_refuse_the_open_and_say_so(
        granting_config, stub_module_transport_factory):
    disagreeing = _workflow(second_gate=_gate(record_writes='"true"'))
    transport = stub_module_transport_factory([_workflow_list(), disagreeing])

    result = _plan(granting_config, transport)

    assert result["outcome"] == write_grant.REFUSED
    assert "declaring nodes disagree" in result["detail"]


def test_a_refused_open_still_carries_the_envelope(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow_list(), _armed_workflow()])

    result = _plan(granting_config, transport)

    assert result["envelope"]["record_count"] == 1


def test_guardrail_a_reads_every_lane_the_grant_covers(
        granting_config, stub_module_transport_factory):
    """A two-lane grant is two live reads. A lane read on neither's behalf is a lane whose
    armed state nobody checked."""
    contacts = _workflow(record_writes='"true"',
                         name=write_grant.LANES["contacts"])
    transport = stub_module_transport_factory(
        [_workflow_list(), _workflow_list(), _workflow(), contacts])

    result = _plan(granting_config, transport, lanes=("enrichment", "contacts"))

    assert result["outcome"] == write_grant.REFUSED
    assert "[contacts]" in result["detail"]
    assert "[enrichment]" not in result["detail"], "the clean lane must not be blamed"


def test_read_live_write_state_uses_the_shipped_reader_not_a_second_regex():
    """`n8n_read.read_write_safety` scans every node's code because the declaring set is
    not stable. A second regex here would recognise a different set."""
    source = inspect.getsource(write_grant.read_live_write_state)
    assert "n8n_read.read_write_safety" in source
    assert "re.compile" not in source


# =========================================================================================
# GUARDRAIL B — bound the disarm unknown (D-53-04)
# =========================================================================================

def _disarm(outcome):
    return {"disarm": {"outcome": outcome, "workflow_id": WORKFLOW_ID}}


def test_one_failure_then_a_verified_disarm_leaves_the_grant_open_and_disarms_nothing_extra(
        granting_config, stub_module_transport_factory):
    """D-53-04's chosen behaviour, kept intact: the bound is on the SECOND, not the first,
    so a transient blip does not abort a long run."""
    transport = stub_module_transport_factory([_workflow_list(), _workflow()])
    grant = _open_grant(granting_config, transport)
    before = len(transport.calls)

    grant = write_grant.record_send_outcome(
        grant, _disarm(n8n_arming.DISARM_FAILED), granting_config, transport=transport)
    assert grant["state"] == write_grant.OPEN
    assert grant["consecutive_disarm_failures"] == 1

    grant = write_grant.record_send_outcome(
        grant, _disarm(n8n_arming.DISARMED), granting_config, transport=transport)

    assert grant["state"] == write_grant.OPEN
    assert grant["consecutive_disarm_failures"] == 0
    assert len(transport.calls) == before, "no extra disarm was attempted"


def test_two_consecutive_disarm_failures_close_the_grant_and_attempt_a_disarm(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow_list(), _workflow()])
    grant = _open_grant(granting_config, transport)

    # The closing disarm's own read -> mutate -> verify sequence, ending disarmed.
    transport._responses.extend(
        [_armed_workflow(), _armed_workflow(), {}, {}, {}, _workflow()])

    for _ in range(2):
        grant = write_grant.record_send_outcome(
            grant, _disarm(n8n_arming.DISARM_FAILED), granting_config,
            transport=transport)

    assert grant["state"] == write_grant.CLOSED
    assert grant["closed_reason"] == write_grant.CLOSED_DISARM_UNCONFIRMED
    assert grant["closing_disarm"][0]["outcome"] == n8n_arming.DISARMED
    assert grant["closing_disarm_verified"] is True
    assert "put" in transport.verbs, "the close really did attempt a disarm"


def test_the_next_send_after_a_two_failure_close_is_refused(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow_list(), _workflow()])
    grant = _open_grant(granting_config, transport)
    transport._responses.extend(
        [_armed_workflow(), _armed_workflow(), {}, {}, {}, _workflow()])

    for _ in range(2):
        grant = write_grant.record_send_outcome(
            grant, _disarm(n8n_arming.DISARM_FAILED), granting_config,
            transport=transport)

    refusal = write_grant.check_before_send(
        grant, lane="enrichment", workflow_id=WORKFLOW_ID,
        record_ids=[RECORD_ID], record_domains=[])

    assert refusal["outcome"] == write_grant.REFUSED
    assert write_grant.CLOSED_DISARM_UNCONFIRMED in refusal["detail"]


def test_the_grant_closes_even_when_the_closing_disarm_itself_fails(
        granting_config, stub_module_transport_factory):
    """A failed closing disarm must NEVER be a reason to leave the grant open — that would
    let the run continue over exactly the state that triggered the guardrail."""
    transport = stub_module_transport_factory([_workflow_list(), _workflow()])
    grant = _open_grant(granting_config, transport)

    # The disarm's verifying re-read still shows writes enabled: DISARM_FAILED.
    transport._responses.extend(
        [_armed_workflow(), _armed_workflow(), {}, {}, {}, _armed_workflow()])

    for _ in range(2):
        grant = write_grant.record_send_outcome(
            grant, _disarm(n8n_arming.DISARM_FAILED), granting_config,
            transport=transport)

    assert grant["state"] == write_grant.CLOSED
    assert grant["closed_reason"] == write_grant.CLOSED_DISARM_UNCONFIRMED
    assert grant["closing_disarm"][0]["outcome"] == n8n_arming.DISARM_FAILED
    assert grant["closing_disarm_verified"] is False


def test_a_preflight_finding_writes_still_live_closes_the_grant_and_refuses_that_send(
        granting_config, stub_module_transport_factory):
    """Whatever the counter reads. A live write at the start of the next send means the
    previous window's disarm did not take, and the counter cannot know that."""
    transport = stub_module_transport_factory([_workflow_list(), _workflow()])
    grant = _open_grant(granting_config, transport)
    assert grant["consecutive_disarm_failures"] == 0

    transport._responses.extend([
        _armed_workflow(),                                        # the pre-flight read
        _armed_workflow(), _armed_workflow(), {}, {}, {}, _workflow(),   # closing disarm
    ])

    grant, refusal = write_grant.preflight_before_send(
        grant, granting_config, "enrichment", transport=transport)

    assert refusal["outcome"] == write_grant.REFUSED
    assert grant["state"] == write_grant.CLOSED
    assert grant["closed_reason"] == write_grant.CLOSED_WRITES_STILL_LIVE
    assert grant["closing_disarm"][0]["outcome"] == n8n_arming.DISARMED
    assert grant["closing_disarm_verified"] is True


def test_a_preflight_over_a_disarmed_lane_lets_the_send_through(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow_list(), _workflow()])
    grant = _open_grant(granting_config, transport)
    transport._responses.append(_workflow())

    unchanged, refusal = write_grant.preflight_before_send(
        grant, granting_config, "enrichment", transport=transport)

    assert refusal is None
    assert unchanged["state"] == write_grant.OPEN
    assert transport.mutating_calls == []


def test_a_preflight_that_cannot_read_does_not_close_the_grant(
        granting_config, stub_module_transport_factory):
    """Mid-run, an unreadable read is more likely an API blip than a live write, and
    D-53-04's whole point is that a blip must not abort a long run. Guardrail A refuses on
    unreadable at the OPEN, where refusing costs nothing."""
    transport = stub_module_transport_factory([_workflow_list(), _workflow()])
    grant = _open_grant(granting_config, transport)
    transport._responses.append((500, {"message": "no"}))

    unchanged, refusal = write_grant.preflight_before_send(
        grant, granting_config, "enrichment", transport=transport)

    assert refusal is None
    assert unchanged["state"] == write_grant.OPEN


def test_the_closing_disarm_calls_the_ungated_disarm_and_adds_no_authority():
    """`n8n_arming.disarm` is ungated by design — a kill switch that blocked disarming
    would strand an armed backend. Closing with a disarm therefore adds no authority
    anywhere, and this pins that it is THAT function being called."""
    source = inspect.getsource(write_grant._close_with_disarm)
    assert "n8n_arming.disarm(" in source
    assert "_arm_gate" not in source


# =========================================================================================
# T-53-12 — neither guardrail is switchable
# =========================================================================================

def test_neither_guardrail_reads_an_environment_variable_or_a_disabling_config_key():
    """A guardrail with an off switch is the guardrail's absence with extra steps."""
    for function in (write_grant.guardrail_a, write_grant.read_live_write_state,
                     write_grant.preflight_before_send, write_grant.record_send_outcome,
                     write_grant._close_with_disarm, write_grant._live_write_faults):
        source = inspect.getsource(function)
        for forbidden in ("os.environ", "getenv", "_ENABLED", "disable", "skip_guardrail",
                          "ALLOW_N8N_ARM"):
            assert forbidden not in source, (
                f"{forbidden!r} in {function.__name__} — a guardrail must not be "
                f"switchable")


def test_guardrail_a_cannot_be_skipped_by_passing_a_non_callable_preflight(
        granting_config, stub_module_transport_factory):
    """`preflight=None` means the real guardrail; anything non-callable is a TypeError
    rather than a skipped live read."""
    transport = stub_module_transport_factory([_workflow_list()])

    with pytest.raises(TypeError):
        write_grant.plan_grant(
            granting_config, lanes=["enrichment"], object_type="companies",
            record_ids=[RECORD_ID], record_domains=[], allow_create=False,
            label="bypass attempt", transport=transport, preflight=False)


def test_guardrail_a_runs_by_default_with_no_preflight_argument_at_all(
        granting_config, stub_module_transport_factory):
    """The default IS the guardrail. A `preflight=None` that meant "no check" would be a
    toggle by omission, which is the same defect wearing quieter clothes."""
    transport = stub_module_transport_factory([_workflow_list(), _armed_workflow()])

    result = _plan(granting_config, transport)

    assert result["outcome"] == write_grant.REFUSED
    assert result["guardrail"] == "A"


def test_nothing_a_guardrail_writes_reaches_disk():
    """GRANT-06 holds over 53-02's surfaces too."""
    source = Path(write_grant.__file__).read_text()
    for forbidden in ("open(", "write_text", "os.environ[", "setenv", "json.dump("):
        assert forbidden not in source
