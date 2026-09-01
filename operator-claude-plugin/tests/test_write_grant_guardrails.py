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
import json
from pathlib import Path

import pytest

import config_gate
import executions_client
import n8n_arming
import review_decision
import write_grant

WORKFLOW_ID = "wf-enrichment-1"
CONTACTS_WORKFLOW_ID = "wf-contacts-1"
REVIEW_WORKFLOW_ID = "wf-review-1"
RECORD_ID = "12345"


# Phase 60 (D-60-01/D-60-05 widening): `_gate()`'s fifth constant matches the deployed
# shape — every deployed cloud workflow using the shared write-safety gate declares all
# five OVERLAYABLE_FLAGS regardless of which ones it branches on (60-RESEARCH.md, verified
# against the committed workflow JSON). Omitting it makes every disarmed-backend test read
# as UNREADABLE ("its write-safety state could not be read at all") rather than disarmed —
# a loud, obvious failure. If you see that message on a test that is supposed to proceed,
# the fix is to add the missing constant to the fixture, never to narrow the guardrail's
# widened read back down to dodge it.
def _gate(record_writes='"false"', create='"false"', ids='""', domains='""',
          review_writes='"false"'):
    return (f"const ALLOW_HUBSPOT_RECORD_WRITES = {record_writes};\n"
            f"const ALLOW_HUBSPOT_CREATE = {create};\n"
            f"const ALLOW_HUBSPOT_REVIEW_WRITES = {review_writes};\n"
            f"const TEST_RECORD_IDS = {ids};\n"
            f"const TEST_RECORD_DOMAINS = {domains};\n"
            "function _writeSafetyAllows() { return false; }\n")


def _workflow(record_writes='"false"', create='"false"', ids='""', domains='""',
              name=None, second_gate=None, review_writes='"false"'):
    """Two declaring nodes, as the deployed workflows have. `second_gate` lets a test make
    them DISAGREE, which is a real desync shape (a partial deploy or a hand edit in the
    n8n UI) and must never be reported as a guess."""
    first = _gate(record_writes, create, ids, domains, review_writes)
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


def _executions_page():
    """One exhausted executions-list page: no items, no cursor — `allowance_headroom`'s
    sample reads this as `listing_exhausted: True`, `sampled: True`, `count_in_window: 0`
    (REVIEW-57-H1). Inserted into every `plan_grant` transport script between the
    workflow-list read(s) and guardrail A's per-lane read(s) — the new step the headroom
    sample adds to the frozen call order (REVIEW-57-H9)."""
    return {"data": []}


# ------------------------------------------------------- Phase 60: the review lane's shape
#
# Mirrors test_write_grant.py's own `_review_workflow`/`_armed_review_workflow` fixtures —
# declares all 5 OVERLAYABLE_FLAGS on one node, matching the real deployed gate.
def _review_workflow(review_writes='"false"', record_writes='"false"', create='"false"',
                     ids='""', domains='""'):
    gate = _gate(record_writes, create, ids, domains, review_writes)
    return {
        "id": REVIEW_WORKFLOW_ID,
        "name": write_grant.LANES["review"],
        "active": True, "settings": {}, "connections": {},
        "nodes": [
            {"name": "Review Decision Gate", "parameters": {"jsCode": gate}},
            {"name": "Webhook", "parameters": {}},
        ],
    }


def _armed_review_workflow(ids=f'"{RECORD_ID}"'):
    return _review_workflow(review_writes='"true"', ids=ids)


def _review_workflow_list():
    return {"data": [{"id": REVIEW_WORKFLOW_ID, "name": write_grant.LANES["review"]}]}


def _all_lanes_workflow_list():
    return {"data": [
        {"id": WORKFLOW_ID, "name": write_grant.LANES["enrichment"]},
        {"id": CONTACTS_WORKFLOW_ID, "name": write_grant.LANES["contacts"]},
        {"id": REVIEW_WORKFLOW_ID, "name": write_grant.LANES["review"]},
    ]}


def _put_body_jscode(put_json):
    """The concatenated `jsCode` of every node in a recorded PUT's `json` body — reading
    the declaration lines directly rather than string-searching the JSON-escaped dump,
    which double-escapes the embedded quotes inside `jsCode` and never matches."""
    body = put_json or {}
    return "\n".join(
        (node.get("parameters") or {}).get("jsCode", "")
        for node in (body.get("nodes") or [])
        if isinstance(node, dict))


def _open_review_grant(config, transport, record_ids=(RECORD_ID,)):
    proposal = write_grant.plan_grant(
        config, lanes=["review"], object_type="companies",
        record_ids=list(record_ids), record_domains=[], allow_create=False,
        label="the review triage batch", transport=transport)
    assert proposal.get("kind") == write_grant.PROPOSAL_KIND, proposal
    return write_grant.open_grant(proposal, "yes", config)


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
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _armed_workflow()])

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
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _armed_workflow()])

    result = _plan(granting_config, transport)

    assert result["offered_action"] == "disarm"
    assert "ask me to disarm" in result["detail"]
    assert "I have NOT changed anything" in result["detail"]


def test_guardrail_as_transport_log_holds_reads_only(
        granting_config, stub_module_transport_factory):
    """The pin that stops a later edit quietly making guardrail A act. A disarm would show
    up here as a PUT — `n8n_control.apply_mutation` cannot disarm without one."""
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _armed_workflow()])

    _plan(granting_config, transport)

    assert transport.verbs == ["get", "get", "get"], (
        "workflow-list resolve, the new headroom sample, then guardrail A's own read "
        "(REVIEW-57-H9's re-sequenced frozen call order)")
    assert transport.mutating_calls == []


def test_an_open_over_a_disarmed_backend_proceeds(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _workflow()])

    proposal = _plan(granting_config, transport)

    assert proposal["kind"] == write_grant.PROPOSAL_KIND


def test_a_workflow_that_cannot_be_read_refuses_the_open(
        granting_config, stub_module_transport_factory):
    """THE ONE A HURRIED IMPLEMENTATION GETS WRONG. An unreadable write-safety state is not
    a disarmed one, and this guardrail fires exactly when something is already wrong."""
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), (500, {"message": "no"})])

    result = _plan(granting_config, transport)

    assert result["outcome"] == write_grant.REFUSED
    assert "could not be read at all" in result["detail"]


def test_a_workflow_with_no_declarations_at_all_refuses_the_open(
        granting_config, stub_module_transport_factory):
    """A 200 carrying a body with nothing to read is the same answer as an unreachable
    one: nobody can say whether writes are on."""
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), {"id": WORKFLOW_ID,
                                                                 "nodes": []}])

    result = _plan(granting_config, transport)

    assert result["outcome"] == write_grant.REFUSED
    assert "could not be read at all" in result["detail"]


def test_declaring_nodes_that_disagree_refuse_the_open_and_say_so(
        granting_config, stub_module_transport_factory):
    disagreeing = _workflow(second_gate=_gate(record_writes='"true"'))
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), disagreeing])

    result = _plan(granting_config, transport)

    assert result["outcome"] == write_grant.REFUSED
    assert "declaring nodes disagree" in result["detail"]


def test_a_refused_open_still_carries_the_envelope(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _armed_workflow()])

    result = _plan(granting_config, transport)

    assert result["envelope"]["record_count"] == 1


def test_guardrail_a_reads_every_lane_the_grant_covers(
        granting_config, stub_module_transport_factory):
    """A two-lane grant is two live reads. A lane read on neither's behalf is a lane whose
    armed state nobody checked."""
    contacts = _workflow(record_writes='"true"',
                         name=write_grant.LANES["contacts"])
    transport = stub_module_transport_factory(
        [_workflow_list(), _workflow_list(), _executions_page(), _workflow(), contacts])

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
# Phase 60, Task 1 — Guardrail A widened to see a stuck-open review authorization
# (D-60-01 consequence: review is now grantable, so a review flag left live by a crashed
# prior session is exactly the state D-53-03 built this guardrail to catch).
# =========================================================================================

def test_a_stuck_open_review_flag_refuses_the_open_and_names_it(
        granting_config, stub_module_transport_factory):
    """Behavior 1: a workflow whose gate declares ALLOW_HUBSPOT_REVIEW_WRITES enabled while
    both dispatch booleans read disabled REFUSES the open, and the refusal names the review
    flag and the allowlist currently in force."""
    dirty = _workflow(review_writes='"true"', ids='"9999,8888"', domains='"already.example"')
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), dirty])

    result = _plan(granting_config, transport)

    assert result["outcome"] == write_grant.REFUSED
    assert "ALLOW_HUBSPOT_REVIEW_WRITES reads enabled" in result["detail"]
    assert result["faults"]["enrichment"]["live_flags"] == ["ALLOW_HUBSPOT_REVIEW_WRITES"]
    assert "9999,8888" in result["detail"]
    assert "already.example" in result["detail"]


def test_the_armed_backend_refusal_still_names_only_the_two_dispatch_flags(
        granting_config, stub_module_transport_factory):
    """Behavior 2: the widening must not reorder or pollute the pre-existing armed-backend
    refusal. `test_an_open_over_a_live_armed_backend_refuses_and_names_what_it_found` (above
    this section) already pins this with the un-widened backend
    (`review_writes` stays at its disarmed default); this test re-asserts it explicitly as
    the Task 1 behavior it now is, so a reader looking for Behavior 2 finds it named."""
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _armed_workflow()])

    result = _plan(granting_config, transport)

    assert result["outcome"] == write_grant.REFUSED
    assert result["faults"]["enrichment"]["live_flags"] == [
        "ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE"]
    assert "ALLOW_HUBSPOT_REVIEW_WRITES" not in result["faults"]["enrichment"]["live_flags"]


def test_a_workflow_declaring_only_the_four_dispatch_constants_is_unreadable_and_refuses(
        granting_config, stub_module_transport_factory):
    """Behavior 3: a workflow declaring only the four dispatch constants (the shape a
    fixture built for a 2-lane world had) is now `readable: False` and refuses — an
    unreadable state is never evidence of a disarmed backend, and this is the direction the
    widening deliberately fails in."""
    four_const_only = {
        "id": WORKFLOW_ID, "name": write_grant.LANES["enrichment"],
        "active": True, "settings": {}, "connections": {},
        "nodes": [
            {"name": "Update Write Gate", "parameters": {"jsCode": (
                'const ALLOW_HUBSPOT_RECORD_WRITES = "false";\n'
                'const ALLOW_HUBSPOT_CREATE = "false";\n'
                'const TEST_RECORD_IDS = "";\n'
                'const TEST_RECORD_DOMAINS = "";\n'
                'function _writeSafetyAllows() { return false; }\n'
            )}},
            {"name": "Webhook", "parameters": {}},
        ],
    }
    transport = stub_module_transport_factory(
        [_workflow_list(), _executions_page(), four_const_only])

    result = _plan(granting_config, transport)

    assert result["outcome"] == write_grant.REFUSED
    assert "could not be read at all" in result["detail"]


def test_a_fully_disarmed_five_constant_workflow_still_proceeds(
        granting_config, stub_module_transport_factory):
    """Behavior 4: a fully disarmed five-constant workflow (the deployed shape) still
    proceeds — `guardrail_a` returns `None`. `_workflow()` already declares all five
    constants disarmed by default (Pitfall 2's fixture widening); this pins that the
    widened read does not turn a genuinely disarmed backend into a false refusal."""
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _workflow()])

    result = _plan(granting_config, transport)

    assert result["kind"] == write_grant.PROPOSAL_KIND


# =========================================================================================
# GUARDRAIL B — bound the disarm unknown (D-53-04)
# =========================================================================================

def _disarm(outcome):
    return {"disarm": {"outcome": outcome, "workflow_id": WORKFLOW_ID}}


def test_one_failure_then_a_verified_disarm_leaves_the_grant_open_and_disarms_nothing_extra(
        granting_config, stub_module_transport_factory):
    """D-53-04's chosen behaviour, kept intact: the bound is on the SECOND, not the first,
    so a transient blip does not abort a long run."""
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _workflow()])
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
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _workflow()])
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
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _workflow()])
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
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _workflow()])
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
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _workflow()])
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
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _workflow()])
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
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _workflow()])
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
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _armed_workflow()])

    result = _plan(granting_config, transport)

    assert result["outcome"] == write_grant.REFUSED
    assert result["guardrail"] == "A"


def test_nothing_a_guardrail_writes_reaches_disk():
    """GRANT-06 holds over 53-02's surfaces too."""
    source = Path(write_grant.__file__).read_text()
    for forbidden in ("open(", "write_text", "os.environ[", "setenv", "json.dump("):
        assert forbidden not in source


# =========================================================================================
# Phase 60, Task 2 (D-60-06) — ONE batch window for a whole triage sitting.
#
# No existing test in this repo exercised a multi-decision single window for ANY lane
# before this section: `authorize_send`/`armed_window` are per-send by design (each send
# opens and closes its own window), so `authorize_review_batch`'s batch-scoped window is
# genuinely NEW coverage, not a copy of an existing pattern. Every test below drives the
# recorded transport call sequence, not only the returned dicts — "arm once, disarm once"
# is a property of the CALL LOG, and a test that only inspected return values could not
# see it.
#
# The last two tests (MEDIUM-1, cross-AI review) pin the guard that keeps
# `preflight_before_send` from tripping over the batch window's own arm: the review lane's
# liveness check excludes the review flag itself and nothing else.
# =========================================================================================

def test_authorize_review_batch_on_a_three_lane_grant_returns_armed_with_the_grants_own_records(
        granting_config, stub_module_transport_factory):
    """Test 1: `authorize_review_batch` on an open three-lane grant returns `armed: True`,
    the review workflow id, and the grant's OWN `record_ids`/`record_domains` lists."""
    ids = [RECORD_ID, "18756544344"]
    transport = stub_module_transport_factory(
        [_all_lanes_workflow_list()] * 3 + [_executions_page()] +
        [_workflow(), _workflow(name=write_grant.LANES["contacts"]), _review_workflow()])
    proposal = write_grant.plan_grant(
        granting_config, lanes=["enrichment", "contacts", "review"],
        object_type="companies", record_ids=ids, record_domains=[],
        allow_create=False, label="the triage batch", transport=transport)
    assert proposal.get("kind") == write_grant.PROPOSAL_KIND, proposal
    grant = write_grant.open_grant(proposal, "yes", granting_config)

    batch = write_grant.authorize_review_batch(grant)

    assert batch["armed"] is True
    assert batch["workflow_id"] == REVIEW_WORKFLOW_ID
    assert batch["record_ids"] == ids
    assert batch["record_domains"] == []
    assert batch["refusal"] is None


def test_authorize_review_batch_refuses_a_grant_that_does_not_cover_review(
        granting_config, stub_module_transport_factory):
    """Test 2a: on a grant whose `lanes` omits `"review"` it returns `armed: False` with a
    refusal naming the lane."""
    transport = stub_module_transport_factory([_workflow_list(), _executions_page(), _workflow()])
    grant = _open_grant(granting_config, transport)

    batch = write_grant.authorize_review_batch(grant)

    assert batch["armed"] is False
    assert "review" in batch["detail"]


def test_authorize_review_batch_refuses_a_closed_grant_naming_the_close_reason(
        granting_config, stub_module_transport_factory):
    """Test 2b: on a closed grant it refuses, naming the close reason."""
    transport = stub_module_transport_factory(
        [_review_workflow_list(), _executions_page(), _review_workflow()])
    grant = _open_review_grant(granting_config, transport)
    closed = write_grant.revoke_grant(grant)

    batch = write_grant.authorize_review_batch(closed)

    assert batch["armed"] is False
    assert write_grant.CLOSED_REVOKED in batch["detail"]


def test_authorize_review_batch_costs_exactly_one_arm_and_one_disarm_across_three_decisions(
        granting_config, stub_module_transport_factory):
    """Test 3: one window, three decisions — the arm PUT happens once, three decision
    POSTs follow, the disarm PUT happens once, and the allowlist in the arm PUT is the
    grant's own record list and does not change between decisions."""
    ids = [RECORD_ID, "18756544344", "9604614548"]
    plan_transport = stub_module_transport_factory(
        [_review_workflow_list(), _executions_page(), _review_workflow()])
    grant = _open_review_grant(granting_config, plan_transport, record_ids=ids)

    batch = write_grant.authorize_review_batch(grant)
    assert batch["armed"] is True
    assert batch["record_ids"] == ids

    joined_ids = ",".join(ids)
    arm_transport = stub_module_transport_factory([
        _review_workflow(),                                              # arm's own pre-read
        _review_workflow(),                                              # apply_mutation's fresh read
        {}, {}, {},                                                      # deactivate, put, activate
        _review_workflow(review_writes='"true"', ids=f'"{joined_ids}"'),  # arm verification
        _armed_review_workflow(ids=f'"{joined_ids}"'),                    # disarm's own pre-read
        _armed_review_workflow(ids=f'"{joined_ids}"'),                    # apply_mutation's fresh read
        {}, {}, {},                                                      # deactivate, put, activate
        _review_workflow(),                                              # disarm verification
    ])
    decision_transport = stub_module_transport_factory()

    with n8n_arming.armed_review_window(
            batch["workflow_id"], batch["record_ids"], batch["record_domains"],
            granting_config, transport=arm_transport, grant=grant) as window:
        assert window.arm_result["outcome"] == n8n_arming.ARMED
        arm_put_calls = [c for c in arm_transport.calls if c["verb"] == "put"]
        assert len(arm_put_calls) == 1
        first_put_json = arm_put_calls[0].get("json")
        assert f'TEST_RECORD_IDS = "{joined_ids}"' in _put_body_jscode(first_put_json)

        for record_id in ids:
            decision = write_grant.authorize_send(
                grant, lane=write_grant.REVIEW_LANE, record_ids=[record_id],
                record_domains=[])
            assert decision["armed"] is True

            result = review_decision.submit_decision(
                granting_config, "companies", record_id, "approve", "looks right",
                "operator", review_armed=True, grant=grant, transport=decision_transport)
            assert result["available"] is True

            # The allowlist named in the arm PUT is byte-identical before and after every
            # decision — no second arm ever fires inside the window.
            put_calls_now = [c for c in arm_transport.calls if c["verb"] == "put"]
            assert len(put_calls_now) == 1
            assert json.dumps(put_calls_now[0].get("json"), sort_keys=True) == \
                json.dumps(first_put_json, sort_keys=True)

    assert window.disarm_result["outcome"] == n8n_arming.DISARMED
    all_put_calls = [c for c in arm_transport.calls if c["verb"] == "put"]
    assert len(all_put_calls) == 2, "exactly one arm PUT and one disarm PUT"
    assert len(decision_transport.calls) == 3
    assert all(c["verb"] == "post" for c in decision_transport.calls), (
        "all three decisions reached the decision path as POSTs")


def test_a_decision_outside_the_grants_records_refuses_but_the_window_still_disarms(
        granting_config, stub_module_transport_factory):
    """Test 4: a decision on a record the grant does not name is refused by
    `authorize_send` WHILE the window is open, and the window still disarms on exit."""
    ids = [RECORD_ID]
    plan_transport = stub_module_transport_factory(
        [_review_workflow_list(), _executions_page(), _review_workflow()])
    grant = _open_review_grant(granting_config, plan_transport, record_ids=ids)
    batch = write_grant.authorize_review_batch(grant)

    arm_transport = stub_module_transport_factory([
        _review_workflow(), _review_workflow(), {}, {}, {},
        _review_workflow(review_writes='"true"', ids=f'"{RECORD_ID}"'),
        _armed_review_workflow(ids=f'"{RECORD_ID}"'),
        _armed_review_workflow(ids=f'"{RECORD_ID}"'), {}, {}, {},
        _review_workflow(),
    ])
    with n8n_arming.armed_review_window(
            batch["workflow_id"], batch["record_ids"], batch["record_domains"],
            granting_config, transport=arm_transport, grant=grant) as window:
        assert window.arm_result["outcome"] == n8n_arming.ARMED

        out_of_scope = write_grant.authorize_send(
            grant, lane=write_grant.REVIEW_LANE, record_ids=["not-in-the-grant"],
            record_domains=[])

        assert out_of_scope["armed"] is False
        assert "not-in-the-grant" in out_of_scope["detail"]

    assert window.disarm_result["outcome"] == n8n_arming.DISARMED


def test_an_exception_mid_batch_propagates_and_the_window_still_disarms(
        granting_config, stub_module_transport_factory):
    """Test 5: an exception raised by the second of three decisions propagates AND the
    window still disarms (the `armed_window.__exit__` guarantee, unchanged)."""
    ids = [RECORD_ID]
    plan_transport = stub_module_transport_factory(
        [_review_workflow_list(), _executions_page(), _review_workflow()])
    grant = _open_review_grant(granting_config, plan_transport, record_ids=ids)
    batch = write_grant.authorize_review_batch(grant)

    arm_transport = stub_module_transport_factory([
        _review_workflow(), _review_workflow(), {}, {}, {},
        _review_workflow(review_writes='"true"', ids=f'"{RECORD_ID}"'),
        _armed_review_workflow(ids=f'"{RECORD_ID}"'),
        _armed_review_workflow(ids=f'"{RECORD_ID}"'), {}, {}, {},
        _review_workflow(),
    ])

    class _Boom(Exception):
        pass

    window_ref = {}
    with pytest.raises(_Boom):
        with n8n_arming.armed_review_window(
                batch["workflow_id"], batch["record_ids"], batch["record_domains"],
                granting_config, transport=arm_transport, grant=grant) as window:
            window_ref["window"] = window
            raise _Boom("the second decision blew up")

    assert window_ref["window"].disarm_result["outcome"] == n8n_arming.DISARMED


def test_a_mid_batch_revocation_refuses_the_next_decision_but_the_window_still_disarms(
        granting_config, stub_module_transport_factory):
    """Test 6: `revoke_grant` called after the first decision makes the second decision's
    `authorize_send` refuse (the grant is closed), and the window still disarms on exit."""
    ids = [RECORD_ID, "18756544344"]
    plan_transport = stub_module_transport_factory(
        [_review_workflow_list(), _executions_page(), _review_workflow()])
    grant = _open_review_grant(granting_config, plan_transport, record_ids=ids)
    batch = write_grant.authorize_review_batch(grant)
    joined_ids = ",".join(ids)

    arm_transport = stub_module_transport_factory([
        _review_workflow(), _review_workflow(), {}, {}, {},
        _review_workflow(review_writes='"true"', ids=f'"{joined_ids}"'),
        _review_workflow(review_writes='"true"', ids=f'"{joined_ids}"'),
        _review_workflow(review_writes='"true"', ids=f'"{joined_ids}"'), {}, {}, {},
        _review_workflow(),
    ])
    with n8n_arming.armed_review_window(
            batch["workflow_id"], batch["record_ids"], batch["record_domains"],
            granting_config, transport=arm_transport, grant=grant) as window:
        first = write_grant.authorize_send(
            grant, lane=write_grant.REVIEW_LANE, record_ids=[ids[0]], record_domains=[])
        assert first["armed"] is True

        grant = write_grant.revoke_grant(grant)

        second = write_grant.authorize_send(
            grant, lane=write_grant.REVIEW_LANE, record_ids=[ids[1]], record_domains=[])
        assert second["armed"] is False
        assert write_grant.CLOSED_REVOKED in second["detail"]

    assert window.disarm_result["outcome"] == n8n_arming.DISARMED


def test_a_review_lane_preflight_does_not_trip_over_its_own_batch_arm(
        granting_config, stub_module_transport_factory):
    """Test 7 (MEDIUM-1): `preflight_before_send(..., lane=REVIEW_LANE)` over a backend
    where ONLY the review flag reads live returns the grant unchanged and no refusal, and
    the grant's state is still open — the batch window cannot trip over its own arm."""
    plan_transport = stub_module_transport_factory(
        [_review_workflow_list(), _executions_page(), _review_workflow()])
    grant = _open_review_grant(granting_config, plan_transport)

    preflight_transport = stub_module_transport_factory([_armed_review_workflow()])

    returned_grant, refusal = write_grant.preflight_before_send(
        grant, granting_config, write_grant.REVIEW_LANE, transport=preflight_transport)

    assert refusal is None
    assert returned_grant is grant
    assert returned_grant["state"] == write_grant.OPEN
    assert preflight_transport.mutating_calls == [], (
        "no disarm PUT/POST may have run — the batch's own arm must not be closed")


def test_a_review_lane_preflight_still_closes_on_a_live_dispatch_flag(
        granting_config, stub_module_transport_factory):
    """Test 8 (MEDIUM-1): the same call over a backend where a DISPATCH flag reads live
    still closes the grant and refuses, so the exclusion narrows the review flag and
    nothing else. Running Test 7 against the un-narrowed tuple is what fails, which is the
    property this pair exists to pin."""
    plan_transport = stub_module_transport_factory(
        [_review_workflow_list(), _executions_page(), _review_workflow()])
    grant = _open_review_grant(granting_config, plan_transport)

    dirty = _review_workflow(record_writes='"true"', ids='"9999"')
    preflight_transport = stub_module_transport_factory([
        dirty,                # read_live_write_state's own read
        dirty,                # disarm's own pre-read
        dirty,                # apply_mutation's fresh read
        {}, {}, {},            # deactivate, put, activate
        _review_workflow(),    # verify (post-disarm)
    ])

    returned_grant, refusal = write_grant.preflight_before_send(
        grant, granting_config, write_grant.REVIEW_LANE, transport=preflight_transport)

    assert refusal is not None
    assert returned_grant["state"] == write_grant.CLOSED
    assert returned_grant["closed_reason"] == write_grant.CLOSED_WRITES_STILL_LIVE
