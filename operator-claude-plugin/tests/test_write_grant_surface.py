"""53-03 — the grant's OPERATOR-FACING surface, and the invariants it must not have cost.

Three files hold the grant between them, and the split is deliberate:

* `test_write_grant.py` — the authority and the shape contract (53-01/53-02).
* `test_write_grant_guardrails.py` — the two defences D-53-03 and D-53-04 asked for.
* this file — the surface an operator reaches (revocation by name, the allowlist wording,
  the bridge from a grant to a dispatch) and the milestone's must-not-lose invariants
  re-asserted against everything this phase built.

THE ONE INVARIANT THAT READS AS CHANGED AND IS NOT. The milestone's must-not-lose list
says arming is "planned, shown, confirmed by explicit yes, verified by an independent
re-read". Under a grant the yes is given ONCE, at grant open, over a shown envelope and a
named record set — and every individual arm is still verified by `n8n_control.apply_mutation`'s
independent re-read. D-53-04's whole point is the yes MOVING, not disappearing. A reader
who does not find that stated here will read the confirmation tests below as a regression.
"""
from pathlib import Path

import pytest

import chunking
import config_gate
import control_actions
import executions_client
import n8n_arming
import n8n_control
import write_grant

WORKFLOW_ID = "wf-enrichment-1"
CONTACTS_WORKFLOW_ID = "wf-contacts-1"
RECORD_ID = "12345"
OTHER_RECORD_ID = "67890"
THIRD_RECORD_ID = "24680"


def _base_workflow(record_writes='"false"', create='"false"', ids='""', domains='""'):
    """The same miniature two-gate shape `test_write_grant.py::_base_workflow` uses."""
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
    return {"data": [
        {"id": WORKFLOW_ID, "name": write_grant.LANES["enrichment"]},
        {"id": CONTACTS_WORKFLOW_ID, "name": write_grant.LANES["contacts"]},
    ]}


def _plan_reads(lanes=1):
    """`plan_grant`'s frozen call order: one workflow-list read per lane for id
    resolution, then one workflow read per lane for guardrail A's live write-safety read."""
    return [_workflow_list()] * lanes + [_base_workflow()] * lanes


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


def _open(config, transport, lanes=("enrichment",),
          ids=(RECORD_ID, OTHER_RECORD_ID, THIRD_RECORD_ID), domains=()):
    proposal = write_grant.plan_grant(
        config, lanes=list(lanes), object_type="companies", record_ids=list(ids),
        record_domains=list(domains), allow_create=False,
        label="the 2026-08-25 batch", transport=transport)
    assert proposal.get("kind") == write_grant.PROPOSAL_KIND, proposal
    grant = write_grant.open_grant(proposal, "yes", config)
    assert grant.get("state") == write_grant.OPEN, grant
    return grant


# --- GRANT-05: revocation, reachable by name --------------------------------------------

def test_revoke_grant_closes_the_grant_and_the_next_send_refuses(
        granting_config, stub_module_transport_factory):
    grant = _open(granting_config, stub_module_transport_factory(_plan_reads()))

    revoked = write_grant.revoke_grant(grant)

    assert revoked["state"] == write_grant.CLOSED
    assert revoked["closed_reason"] == write_grant.CLOSED_REVOKED
    refusal = write_grant.check_before_send(
        revoked, lane="enrichment", workflow_id=WORKFLOW_ID,
        record_ids=[RECORD_ID], record_domains=[])
    assert refusal["outcome"] == write_grant.REFUSED
    assert write_grant.CLOSED_REVOKED in refusal["detail"]


def test_revoking_twice_returns_the_closed_grant_unchanged(
        granting_config, stub_module_transport_factory):
    """An operator who says stop twice has not made a mistake."""
    grant = _open(granting_config, stub_module_transport_factory(_plan_reads()))

    once = write_grant.revoke_grant(grant)
    twice = write_grant.revoke_grant(once)

    assert twice == once


def test_revoking_a_grant_a_guardrail_closed_does_not_overwrite_its_close_reason(
        granting_config, stub_module_transport_factory):
    """The reason idempotency has to be REASON-PRESERVING and not merely non-raising.
    A grant closed for `two_consecutive_disarm_failures` that re-reads as
    `operator_revocation` misreports the one close the operator most needs to read
    correctly — which is exactly why 53-02 gave guardrail B its own reason set."""
    grant = _open(granting_config, stub_module_transport_factory(_plan_reads()))
    closed = write_grant.close_grant(grant, write_grant.CLOSED_DISARM_UNCONFIRMED)

    still_closed = write_grant.revoke_grant(closed)

    assert still_closed["closed_reason"] == write_grant.CLOSED_DISARM_UNCONFIRMED


def test_revoke_grants_docstring_states_what_a_revocation_does_not_stop():
    """GRANT-05 as re-scoped by the operator 2026-08-25. The behaviour is pinned by
    `test_write_grant.py::test_a_revocation_midway_does_not_stop_a_running_dispatch`,
    which drives a real 3-chunk dispatch; what is pinned HERE is that the promise an
    operator reads matches it. A docstring claiming chunk-level revocation would be the
    false claim 53-02's blocker was about."""
    doc = write_grant.revoke_grant.__doc__ or ""

    assert "next send" in doc.lower()
    assert "chunk" in doc.lower()
    assert "dispatch_plan" in doc


# --- the ACTION_KINDS boundary, and the plugin's map of what it can do -------------------

def test_the_mutation_allowlist_still_holds_exactly_its_four_entries():
    """The grant open is deliberately NOT here. `ACTION_KINDS` gates `execute_action`,
    documented as the only MUTATING path; opening a grant reads, computes and returns —
    it mutates nothing. Putting a read-only action on a mutation allowlist would blur the
    same capability-versus-authorization distinction D-53-01 keeps out of CAPABILITY_KEYS.

    Pinned BY NAME rather than by `len()`, so a later phase that adds a genuine mutating
    action reddens this deliberately instead of sliding a grant open in under a count."""
    assert control_actions.ACTION_KINDS == (
        "workflow_active", "arm_dispatch", "cadence", "job_enabled")
    assert write_grant.KIND not in control_actions.ACTION_KINDS
    assert write_grant.PROPOSAL_KIND not in control_actions.ACTION_KINDS


def test_the_out_of_allowlist_refusal_names_the_grant_path(control_config):
    """G-1's surface half. An operator who asks the plugin to turn writes on for a batch
    must not be told the plugin cannot do that, when it now can — this message is the
    operator's map of what this plugin can do."""
    result = control_actions.execute_action(
        {"kind": "edit_node", "workflow_id": WORKFLOW_ID}, "yes", control_config)

    detail = result["detail"]
    assert result["outcome"] == control_actions.REFUSED
    assert "write grant" in detail.lower()
    assert "batch" in detail.lower()
    assert "admin" in detail, "the existing clause naming who CAN do the rest stays"


@pytest.fixture
def control_config(fake_config):
    return dict(fake_config)


