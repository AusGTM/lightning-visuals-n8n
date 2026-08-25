"""53-01 — the operator-openable write grant.

The property under test throughout: an operator with no shell can authorize a live write,
and CANNOT authorize a write outside the batch they named. Everything else here serves
those two.

The tracer test walks the whole path in one function on purpose — an admin-set key, a
planned grant, an explicit yes, an armed window, a verified disarm — because that is the
path G-2 said was unreachable from the operator's chair.
"""
import os
from pathlib import Path

import pytest

import config_gate
import executions_client
import n8n_arming
import write_grant

WORKFLOW_ID = "wf-enrichment-1"
CONTACTS_WORKFLOW_ID = "wf-contacts-1"
RECORD_ID = "12345"


def _base_workflow(record_writes='"false"', create='"false"', ids='""', domains='""'):
    """Same miniature two-gate shape `test_control_arming.py::_base_workflow` uses —
    declarations inside jsCode, plus a node with no code at all."""
    gate = (f"const ALLOW_HUBSPOT_RECORD_WRITES = {record_writes};\n"
            f"const ALLOW_HUBSPOT_CREATE = {create};\n"
            f"const TEST_RECORD_IDS = {ids};\n"
            f"const TEST_RECORD_DOMAINS = {domains};\n"
            "function _writeSafetyAllows() { return false; }\n")
    return {
        "id": WORKFLOW_ID,
        "name": write_grant.LANES["enrichment"],
        "active": True,
        "settings": {},
        "connections": {},
        "nodes": [
            {"name": "Update Write Gate", "parameters": {"jsCode": gate}},
            {"name": "Create Write Gate", "parameters": {"jsCode": gate}},
            {"name": "Webhook", "parameters": {}},
        ],
    }


def _armed_workflow(ids=f'"{RECORD_ID}"'):
    return _base_workflow(record_writes='"true"', create='"true"', ids=ids)


def _workflow_list():
    """What `resolve_workflow_id` reads: the /api/v1/workflows collection."""
    return {"data": [
        {"id": WORKFLOW_ID, "name": write_grant.LANES["enrichment"]},
        {"id": CONTACTS_WORKFLOW_ID, "name": write_grant.LANES["contacts"]},
    ]}


@pytest.fixture(autouse=True)
def _clean_arm_env(monkeypatch):
    """The whole point of this phase is arming with NO environment variable, so every test
    here starts from a deterministically unset one."""
    monkeypatch.delenv(n8n_arming.ARM_ENV_VAR, raising=False)


@pytest.fixture(autouse=True)
def _clear_workflow_id_cache():
    """`executions_client._workflow_id_cache` is process-lifetime — without this a resolved
    id leaks between tests and the "workflow not found" cases stop being reachable."""
    executions_client._workflow_id_cache.clear()
    yield
    executions_client._workflow_id_cache.clear()


@pytest.fixture
def granting_config(fake_config):
    """A config whose admin set the settings key to the JSON boolean true."""
    return {**fake_config, config_gate.WRITE_GRANT_SETTINGS_KEY: True}


def _proposal(config, transport, lanes=("enrichment",), ids=(RECORD_ID,), domains=(),
              allow_create=False):
    return write_grant.plan_grant(
        config, lanes=list(lanes), object_type="companies", record_ids=list(ids),
        record_domains=list(domains), allow_create=allow_create,
        label="the 2026-08-25 batch", transport=transport)


def _open(config, transport, **kwargs):
    proposal = _proposal(config, transport, **kwargs)
    assert proposal.get("kind") == write_grant.PROPOSAL_KIND, proposal
    return write_grant.open_grant(proposal, "yes", config)


# --- the tracer: an admin-set key, an opened grant, one send armed under it --------------

def test_a_send_arms_under_an_opened_grant_with_no_environment_variable_set(
        granting_config, stub_module_transport_factory):
    """G-2's blocker, removed end to end: settings key -> plan -> explicit yes -> arm ->
    dispatch -> verified disarm, with no shell anywhere in it."""
    transport = stub_module_transport_factory([
        _workflow_list(),                                       # plan_grant's lane resolve
        _base_workflow(), _base_workflow(), {}, {}, {},         # the arm
        _base_workflow(record_writes='"true"', ids=f'"{RECORD_ID}"'),   # arm verification
        _armed_workflow(), _armed_workflow(), {}, {}, {}, _base_workflow(),   # the disarm
    ])

    grant = _open(granting_config, transport)
    assert grant["kind"] == write_grant.KIND
    assert grant["state"] == write_grant.OPEN
    assert grant["workflow_ids"]["enrichment"] == WORKFLOW_ID

    with n8n_arming.armed_window(WORKFLOW_ID, [RECORD_ID], [], False, granting_config,
                                 transport=transport, grant=grant) as window:
        pass

    assert window.arm_result["outcome"] == n8n_arming.ARMED
    assert window.arm_result["record_ids"] == [RECORD_ID]
    assert window.disarm_result["outcome"] == n8n_arming.DISARMED
    assert os.environ.get(n8n_arming.ARM_ENV_VAR) is None, (
        "the whole point: no shell variable was involved at any step")


# --- scope: GRANT-03 binds inside arm_for_dispatch ---------------------------------------

def test_a_record_outside_the_grant_is_refused_before_any_transport_call(
        granting_config, stub_module_transport_factory):
    """An EMPTY call log, not merely an empty mutating one — that is what distinguishes a
    refusal that happened before transport construction from one that merely did not
    mutate."""
    resolve_transport = stub_module_transport_factory([_workflow_list()])
    grant = _open(granting_config, resolve_transport)

    transport = stub_module_transport_factory([_base_workflow()])
    result = n8n_arming.arm_for_dispatch(WORKFLOW_ID, ["99999"], [], False,
                                         granting_config, transport=transport, grant=grant)

    assert result["outcome"] == n8n_arming.REFUSED
    assert "99999" in result["detail"], "the refusal must name the offending value"
    assert transport.calls == []


def test_a_domain_outside_the_grant_is_refused_before_any_transport_call(
        granting_config, stub_module_transport_factory):
    resolve_transport = stub_module_transport_factory([_workflow_list()])
    grant = _open(granting_config, resolve_transport, ids=(), domains=("known.example",))

    transport = stub_module_transport_factory([_base_workflow()])
    result = n8n_arming.arm_for_dispatch(WORKFLOW_ID, [], ["other.example"], False,
                                         granting_config, transport=transport, grant=grant)

    assert result["outcome"] == n8n_arming.REFUSED
    assert "other.example" in result["detail"]
    assert transport.calls == []


def test_a_grant_on_one_lane_cannot_arm_another_lanes_workflow(
        granting_config, stub_module_transport_factory):
    """The scope check is on the workflow id, not only on the records: a grant over the
    enrichment lane must not arm the contact-ingest workflow for the same records."""
    resolve_transport = stub_module_transport_factory([_workflow_list()])
    grant = _open(granting_config, resolve_transport, lanes=("enrichment",))

    transport = stub_module_transport_factory([_base_workflow()])
    result = n8n_arming.arm_for_dispatch(CONTACTS_WORKFLOW_ID, [RECORD_ID], [], False,
                                         granting_config, transport=transport, grant=grant)

    assert result["outcome"] == n8n_arming.REFUSED
    assert CONTACTS_WORKFLOW_ID in result["detail"]
    assert transport.calls == []


def test_a_grant_spanning_both_lanes_arms_either_of_them(granting_config,
                                                         stub_module_transport_factory):
    """D-53-05, operator, 2026-08-25: one grant may span both lanes of
    enrich-before-ingest. What it must NOT do is widen beyond the named record set — that
    is what the two refusals above hold."""
    # Two lanes, two distinct workflow names, so two collection reads.
    resolve_transport = stub_module_transport_factory([_workflow_list(), _workflow_list()])
    grant = _open(granting_config, resolve_transport, lanes=("enrichment", "contacts"))

    for workflow_id in (WORKFLOW_ID, CONTACTS_WORKFLOW_ID):
        assert write_grant.covers(grant, workflow_id=workflow_id,
                                  record_ids=[RECORD_ID], record_domains=[]) is None


def test_the_empty_allowlist_refusal_still_fires_under_a_grant(
        granting_config, stub_module_transport_factory):
    """`covers` is a subset check, and the empty set is trivially a subset — so the
    grant must not become a way past the empty-allowlist refusal."""
    resolve_transport = stub_module_transport_factory([_workflow_list()])
    grant = _open(granting_config, resolve_transport)

    transport = stub_module_transport_factory([_base_workflow()])
    result = n8n_arming.arm_for_dispatch(WORKFLOW_ID, [], [], False, granting_config,
                                         transport=transport, grant=grant)

    assert result["outcome"] == n8n_arming.REFUSED
    assert "empty" in result["detail"]
    assert transport.mutating_calls == []


# --- authority: the settings key, not the grant object -----------------------------------

def test_a_grant_presented_against_a_config_without_the_key_refuses(
        fake_config, stub_module_transport_factory):
    """A fabricated grant is not authority. The key is re-read from config at ARM time."""
    forged = {"kind": write_grant.KIND, "state": write_grant.OPEN,
              "lanes": ["enrichment"], "workflow_ids": {"enrichment": WORKFLOW_ID},
              "record_ids": [RECORD_ID], "record_domains": [], "closed_reason": None}

    transport = stub_module_transport_factory([_base_workflow()])
    result = n8n_arming.arm_for_dispatch(WORKFLOW_ID, [RECORD_ID], [], False, fake_config,
                                         transport=transport, grant=forged)

    assert result["outcome"] == n8n_arming.REFUSED
    assert config_gate.WRITE_GRANT_SETTINGS_KEY in result["detail"]
    assert "operator.local.json" in result["detail"]
    assert transport.calls == []


def test_a_closed_grant_refuses_and_names_why_it_closed(granting_config,
                                                        stub_module_transport_factory):
    resolve_transport = stub_module_transport_factory([_workflow_list()])
    grant = write_grant.close_grant(_open(granting_config, resolve_transport),
                                    "the operator revoked it")

    transport = stub_module_transport_factory([_base_workflow()])
    result = n8n_arming.arm_for_dispatch(WORKFLOW_ID, [RECORD_ID], [], False,
                                         granting_config, transport=transport, grant=grant)

    assert result["outcome"] == n8n_arming.REFUSED
    assert "the operator revoked it" in result["detail"]
    assert transport.calls == []


def test_with_no_grant_and_no_environment_variable_the_arm_refuses_at_zero_http_cost(
        granting_config, stub_module_transport_factory):
    """Today's behaviour, unchanged — and unchanged even on a config that HAS the settings
    key: without a grant the authority is still the environment variable."""
    transport = stub_module_transport_factory([_base_workflow()])

    result = n8n_arming.arm_for_dispatch(WORKFLOW_ID, [RECORD_ID], [], False,
                                         granting_config, transport=transport)

    assert result["outcome"] == n8n_arming.REFUSED
    assert n8n_arming.ARM_ENV_VAR in result["detail"]
    assert transport.calls == []


def test_the_no_grant_refusal_names_both_routes(granting_config,
                                                stub_module_transport_factory):
    """An operator reading the refusal must learn the remedy they CAN use, not only the
    one that needs a terminal."""
    transport = stub_module_transport_factory([_base_workflow()])
    result = n8n_arming.arm_for_dispatch(WORKFLOW_ID, [RECORD_ID], [], False,
                                         granting_config, transport=transport)

    assert n8n_arming.ARM_ENV_VAR in result["detail"]
    assert config_gate.WRITE_GRANT_SETTINGS_KEY in result["detail"]


# --- planning reads, never mutates --------------------------------------------------------

def test_plan_grant_makes_no_mutating_call_of_any_kind(granting_config,
                                                       stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow_list()])

    proposal = _proposal(granting_config, transport)

    assert proposal["kind"] == write_grant.PROPOSAL_KIND
    assert transport.mutating_calls == []
    assert transport.verbs == ["get"]


def test_plan_grant_refuses_an_empty_record_set_at_plan_time(granting_config,
                                                             stub_module_transport_factory):
    """Refused at PLAN time, not deferred to the arm: a grant over nothing would read as a
    grant while granting nothing."""
    transport = stub_module_transport_factory([_workflow_list()])

    result = _proposal(granting_config, transport, ids=(), domains=())

    assert result["outcome"] == write_grant.REFUSED
    assert "empty record set" in result["detail"]
    assert transport.calls == []


def test_plan_grant_refuses_an_unknown_lane_by_name(granting_config,
                                                    stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow_list()])

    result = _proposal(granting_config, transport, lanes=("review",))

    assert result["outcome"] == write_grant.REFUSED
    assert "review" in result["detail"]
    assert transport.calls == []


def test_the_review_lane_is_not_grantable(granting_config, stub_module_transport_factory):
    """30-01's D-02/D-08e: review writeback is a SEPARATE authority. A dispatch grant must
    not reach it."""
    assert "review" not in write_grant.LANES
    assert "ALLOW_HUBSPOT_REVIEW_WRITES" not in n8n_arming.DISPATCH_FLAGS


def test_plan_grant_refuses_when_a_lane_does_not_resolve(granting_config,
                                                         stub_module_transport_factory):
    transport = stub_module_transport_factory([{"data": []}])

    result = _proposal(granting_config, transport)

    assert result["outcome"] == write_grant.REFUSED
    assert "enrichment" in result["detail"]
    assert transport.mutating_calls == []


def test_plan_grant_refuses_without_the_settings_key(fake_config,
                                                     stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow_list()])

    result = _proposal(fake_config, transport)

    assert result["outcome"] == write_grant.REFUSED
    assert config_gate.WRITE_GRANT_SETTINGS_KEY in result["detail"]
    assert "operator.local.json" in result["detail"]
    assert transport.calls == []


def test_the_preflight_seam_can_refuse_before_a_proposal_exists(
        granting_config, stub_module_transport_factory):
    """53-02's guardrail A lands as a fill, not a reshape."""
    transport = stub_module_transport_factory([_workflow_list()])
    seen = {}

    def _preflight(config, workflow_ids, given_transport):
        seen.update({"workflow_ids": workflow_ids, "transport": given_transport})
        return {"outcome": write_grant.REFUSED, "detail": "writes are already armed"}

    result = write_grant.plan_grant(
        granting_config, lanes=["enrichment"], object_type="companies",
        record_ids=[RECORD_ID], record_domains=[], allow_create=False, label="batch",
        transport=transport, preflight=_preflight)

    assert result["detail"] == "writes are already armed"
    assert seen["workflow_ids"] == {"enrichment": WORKFLOW_ID}
    assert seen["transport"] is transport


# --- opening: a proposal and an explicit yes ----------------------------------------------

def test_open_grant_without_a_confirmation_raises_type_error(granting_config,
                                                             stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow_list()])
    proposal = _proposal(granting_config, transport)

    with pytest.raises(TypeError):
        write_grant.open_grant(proposal, config=granting_config)


def test_open_grant_refuses_anything_that_is_not_a_proposal(granting_config):
    """A caller that skipped planning has nothing to open."""
    result = write_grant.open_grant({"kind": "something_else"}, "yes", granting_config)

    assert result["outcome"] == write_grant.REFUSED
    assert "proposal" in result["detail"]


def test_the_grant_carries_what_it_covers(granting_config, stub_module_transport_factory):
    """GRANT-01: object types, the record set, whether creates are included, and the lanes
    it covers — all stated on the grant itself."""
    transport = stub_module_transport_factory([_workflow_list()])
    grant = _open(granting_config, transport, allow_create=True,
                  ids=(RECORD_ID,), domains=("known.example",))

    assert grant["object_type"] == "companies"
    assert grant["record_ids"] == [RECORD_ID]
    assert grant["record_domains"] == ["known.example"]
    assert grant["allow_create"] is True
    assert grant["lanes"] == ["enrichment"]
    assert grant["label"] == "the 2026-08-25 batch"
    assert grant["opened_at"].endswith("+00:00")
    # 53-02 fills these; initialised here so its guardrails are a fill, not a reshape.
    assert grant["envelope"] is None
    assert grant["closed_reason"] is None
    assert grant["consecutive_disarm_failures"] == 0


def test_close_grant_returns_a_copy_and_makes_no_network_call(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow_list()])
    grant = _open(granting_config, transport)
    before = len(transport.calls)

    closed = write_grant.close_grant(grant, "the batch finished")

    assert closed["state"] == write_grant.CLOSED
    assert closed["closed_reason"] == "the batch finished"
    assert grant["state"] == write_grant.OPEN, "the input must never be mutated"
    assert len(transport.calls) == before


# --- nothing reaches disk -----------------------------------------------------------------

def test_nothing_about_a_grant_is_written_to_disk_or_to_the_environment(
        granting_config, stub_module_transport_factory, monkeypatch, tmp_path):
    """GRANT-06 / D-53-03: the grant exists only as a value in the conversation."""
    monkeypatch.setattr(config_gate, "config_path", lambda *a, **k: tmp_path / "nope.json")
    env_before = dict(os.environ)
    transport = stub_module_transport_factory([_workflow_list()])

    grant = _open(granting_config, transport)
    write_grant.close_grant(grant, "done")

    assert list(tmp_path.iterdir()) == []
    assert dict(os.environ) == env_before

    source = Path(write_grant.__file__).read_text()
    for forbidden in ("open(", "write_text", "os.environ[", "setenv", "json.dump("):
        assert forbidden not in source, (
            f"{forbidden!r} in write_grant.py — a grant must never become durable")
