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


# Phase 60 (D-60-01/D-60-05 widening): the fifth constant matches the deployed shape —
# see `test_write_grant.py::_base_workflow`'s identical comment. Omitting it here would
# make every fixture that drives `plan_grant`/guardrail A through this helper read as
# UNREADABLE rather than disarmed.
def _base_workflow(record_writes='"false"', create='"false"', ids='""', domains='""',
                   review_writes='"false"'):
    """The same miniature two-gate shape `test_write_grant.py::_base_workflow` uses."""
    gate = (f"const ALLOW_HUBSPOT_RECORD_WRITES = {record_writes};\n"
            f"const ALLOW_HUBSPOT_CREATE = {create};\n"
            f"const ALLOW_HUBSPOT_REVIEW_WRITES = {review_writes};\n"
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


def _executions_page():
    """One exhausted executions-list page — `write_grant.allowance_headroom`'s new
    sample, inserted between the id resolves and guardrail A's own read (REVIEW-57-H9's
    re-sequenced frozen call order)."""
    return {"data": []}


def _plan_reads(lanes=1):
    """`plan_grant`'s frozen call order: one workflow-list read per lane for id
    resolution, then ONE executions-list read for the headroom sample (Phase 57,
    REVIEW-57-H9 — not per lane, the sample is per grant), then one workflow read per
    lane for guardrail A's live write-safety read."""
    return [_workflow_list()] * lanes + [_executions_page()] + [_base_workflow()] * lanes


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


# --- the bridge: an open grant becomes a dispatch's `armed` decision ---------------------

def test_authorize_send_returns_the_armed_decision_and_the_grant(
        granting_config, stub_module_transport_factory):
    grant = _open(granting_config, stub_module_transport_factory(_plan_reads()))

    decision = write_grant.authorize_send(
        grant, lane="enrichment", record_ids=[RECORD_ID], record_domains=[])

    assert decision["armed"] is True
    assert decision["workflow_id"] == WORKFLOW_ID
    assert decision["grant"] is grant
    assert decision["refusal"] is None


def test_authorize_send_refuses_under_a_closed_grant(
        granting_config, stub_module_transport_factory):
    grant = _open(granting_config, stub_module_transport_factory(_plan_reads()))
    revoked = write_grant.revoke_grant(grant)

    decision = write_grant.authorize_send(
        revoked, lane="enrichment", record_ids=[RECORD_ID], record_domains=[])

    assert decision["armed"] is False
    assert decision["refusal"]["outcome"] == write_grant.REFUSED


def test_authorize_send_refuses_a_lane_the_grant_does_not_cover(
        granting_config, stub_module_transport_factory):
    grant = _open(granting_config, stub_module_transport_factory(_plan_reads()))

    decision = write_grant.authorize_send(
        grant, lane="contacts", record_ids=[RECORD_ID], record_domains=[])

    assert decision["armed"] is False
    assert "contacts" in decision["refusal"]["detail"]


def test_authorize_send_refuses_records_outside_the_grant(
        granting_config, stub_module_transport_factory):
    grant = _open(granting_config, stub_module_transport_factory(_plan_reads()),
                  ids=(RECORD_ID,))

    decision = write_grant.authorize_send(
        grant, lane="enrichment", record_ids=["99999"], record_domains=[])

    assert decision["armed"] is False
    assert "99999" in decision["refusal"]["detail"]


def test_with_no_grant_the_bridge_names_the_per_send_phrase_and_does_not_refuse():
    """D-53-04 is explicit that the grant is an ADDITION rather than a replacement: with
    no grant open, today's per-send behaviour is unchanged. A bridge that refused the
    ungranted case would have removed the path it was supposed to leave alone."""
    decision = write_grant.authorize_send(
        None, lane="enrichment", record_ids=[RECORD_ID], record_domains=[])

    assert decision["armed"] is False
    assert decision["refusal"] is None, "no grant is not a refusal"
    assert "per-send" in decision["detail"] or "phrase" in decision["detail"]


# =========================================================================================
# THE MILESTONE'S "WHAT MUST NOT BE LOST" LIST, RE-ASSERTED
#
# One test per line of `.planning/milestones/v1.1-REQUIREMENTS.md`'s list that this phase
# could plausibly have regressed. Each docstring is the PROPERTY it defends, in the
# milestone's own words, so a future reader knows what would be lost by deleting it.


def test_the_armed_allowlist_is_the_SENDS_records_never_the_grants_whole_set(
        granting_config, stub_module_transport_factory):
    """MUST NOT BE LOST — record-scoped writes: "Arming a session must widen the allowlist
    to THE BATCH, never to EVERYTHING — the deployed backend must remain incapable of
    writing a record that was not in the run."

    With D-53-05 accepted, the record-scoped allowlist is the only remaining STRUCTURAL
    protection on the enrich-before-ingest path, so the send's window staying strictly
    narrower than the grant is load-bearing rather than tidy. This test fails the day
    anyone "simplifies" the bridge by passing the grant's record set to the arm."""
    grant = _open(granting_config, stub_module_transport_factory(_plan_reads()))
    assert len(grant["record_ids"]) == 3, "the grant is deliberately wider than the send"

    decision = write_grant.authorize_send(
        grant, lane="enrichment", record_ids=[RECORD_ID], record_domains=[])

    # The structural half: the bridge hands back a workflow id and a bool and NEVER a
    # record list, so there is nothing here for a caller to pass to the arm by mistake.
    # A future `authorize_send` that helpfully returned the grant's records would redden
    # this line before anyone had to notice the widened window at the arm.
    for key, value in decision.items():
        if key == "grant":
            continue
        assert OTHER_RECORD_ID not in repr(value), (
            f"the bridge leaked the grant's wider record set through {key!r}")

    transport = stub_module_transport_factory([
        _base_workflow(), _base_workflow(), {}, {}, {},
        _base_workflow(record_writes='"true"', ids=f'"{RECORD_ID}"'),
    ])
    arm = n8n_arming.arm_for_dispatch(
        decision["workflow_id"], [RECORD_ID], [], False, granting_config,
        transport=transport, grant=decision["grant"])

    assert arm["outcome"] == n8n_arming.ARMED
    assert arm["record_ids"] == [RECORD_ID]
    assert OTHER_RECORD_ID not in arm["record_ids"]
    assert THIRD_RECORD_ID not in arm["record_ids"]


def test_an_empty_allowlist_still_denies_everything_under_a_grant(
        granting_config, stub_module_transport_factory):
    """MUST NOT BE LOST — record-scoped writes, its other half: "an empty allowlist denies
    everything". `covers()` is a SUBSET test and the empty set is trivially a subset of
    anything, so without an independent refusal a grant would be a route straight past the
    check that exists because the deployed `_writeSafetyAllows` denies on an empty list."""
    grant = _open(granting_config, stub_module_transport_factory(_plan_reads()))

    transport = stub_module_transport_factory([_base_workflow()])
    arm = n8n_arming.arm_for_dispatch(WORKFLOW_ID, [], [], False, granting_config,
                                      transport=transport, grant=grant)

    assert arm["outcome"] == n8n_arming.REFUSED
    assert "empty" in arm["detail"]
    assert transport.mutating_calls == []


def test_a_send_under_a_grant_still_disarms_through_the_armed_window(
        granting_config, stub_module_transport_factory):
    """MUST NOT BE LOST — guaranteed disarm: "`armed_window` disarms on the way out even
    when the dispatch raises, and a `disarm_failed` is its own loudly-reported state."

    The grant is authority and envelope, NOT a held-open window: every send still opens and
    closes its own. This test drives the RAISING path, because that is the one where a
    "held open for the session" redesign would silently stop disarming."""
    grant = _open(granting_config, stub_module_transport_factory(_plan_reads()))

    transport = stub_module_transport_factory([
        _base_workflow(), _base_workflow(), {}, {}, {},
        _base_workflow(record_writes='"true"', ids=f'"{RECORD_ID}"'),
        _armed_workflow(), _armed_workflow(), {}, {}, {}, _base_workflow(),
    ])

    with pytest.raises(RuntimeError):
        with n8n_arming.armed_window(WORKFLOW_ID, [RECORD_ID], [], False, granting_config,
                                     transport=transport, grant=grant) as window:
            raise RuntimeError("the dispatch blew up mid-send")

    assert window.disarm_result["outcome"] == n8n_arming.DISARMED


def test_a_granted_arm_still_goes_THROUGH_apply_mutation_never_around_it(
        granting_config, stub_module_transport_factory, monkeypatch):
    """MUST NOT BE LOST — "arming is a mutation, so it is planned, shown, confirmed, and
    VERIFIED BY RE-READ; a 200 from n8n is never success."

    `n8n_control.apply_mutation` is the only allowlisted PUT path and carries the
    fetch → mutate → refuse-if-out-of-allowlist → deactivate → PUT → reactivate sequence
    whose reactivation is what forces the running instance to reload (D-18). A grant must
    arm through it, never around it. Pinned behaviourally with a recorder rather than by
    reading source, because a source grep passes on a call that is never reached."""
    grant = _open(granting_config, stub_module_transport_factory(_plan_reads()))

    seen = []
    real = n8n_control.apply_mutation

    def recording(*args, **kwargs):
        seen.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(n8n_control, "apply_mutation", recording)

    transport = stub_module_transport_factory([
        _base_workflow(), _base_workflow(), {}, {}, {},
        _base_workflow(record_writes='"true"', ids=f'"{RECORD_ID}"'),
    ])
    arm = n8n_arming.arm_for_dispatch(WORKFLOW_ID, [RECORD_ID], [], False, granting_config,
                                      transport=transport, grant=grant)

    assert arm["outcome"] == n8n_arming.ARMED
    assert seen, "the granted arm bypassed apply_mutation"


def test_the_yes_MOVED_it_did_not_disappear(granting_config,
                                            stub_module_transport_factory):
    """MUST NOT BE LOST — "arming is planned, shown, confirmed by explicit yes, verified by
    an independent re-read." This is the invariant that READS as changed and is not.

    Under a grant the yes is given ONCE, at grant open, over a shown envelope
    (`proposal["envelope"]["block"]` — the arithmetic) and a named record set
    (`proposal["consequence"]` — the at-the-yes sentence). It is not skipped: without the
    exact string "yes" no grant exists, and with no grant nothing arms. What was removed is
    the REPETITION (G-1), not the confirmation."""
    proposal = write_grant.plan_grant(
        granting_config, lanes=["enrichment"], object_type="companies",
        record_ids=[RECORD_ID], record_domains=[], allow_create=False,
        label="the batch", transport=stub_module_transport_factory(_plan_reads()))

    assert proposal["envelope"]["block"], "the arithmetic is shown before the yes"
    assert proposal["consequence"], "and so is what the yes covers"
    assert write_grant.open_grant(proposal, "no", granting_config)["outcome"] == \
        write_grant.REFUSED
    with pytest.raises(TypeError):
        write_grant.open_grant(proposal)          # omission is never a silent open


def test_no_grant_and_no_bridge_state_reaches_disk_or_the_environment(
        granting_config, stub_module_transport_factory, tmp_path, monkeypatch):
    """MUST NOT BE LOST — GRANT-06: "No grant can be inferred, defaulted, remembered across
    sessions, or written to disk." Re-asserted over 53-03's own surfaces, which are the
    ones that touch a settings file at all."""
    monkeypatch.setenv("LV_OPERATOR_CONFIG", str(tmp_path / "operator.local.json"))
    before = sorted(p.name for p in tmp_path.iterdir())

    grant = _open(granting_config, stub_module_transport_factory(_plan_reads()))
    write_grant.authorize_send(grant, lane="enrichment", record_ids=[RECORD_ID],
                               record_domains=[])
    write_grant.revoke_grant(grant)

    assert sorted(p.name for p in tmp_path.iterdir()) == before

    source = Path(write_grant.__file__).read_text()
    for forbidden in ("open(", "write_text", "os.environ[", "setenv", "json.dump("):
        assert forbidden not in source, f"{forbidden} appeared in write_grant.py"


def test_init_check_neither_writes_nor_migrates_a_grant_into_the_settings_file(tmp_path):
    """MUST NOT BE LOST — GRANT-06, on the one 53-03 surface that reads the settings file.
    Reporting whether write grants are enabled must never be a path that CREATES the key,
    defaults it, or migrates a file into having it."""
    import init_check

    path = tmp_path / "operator.local.json"
    path.write_text('{"n8n_url": "https://real.n8n.cloud", "webhook_secret": "s", '
                    '"n8n_api_key": "k"}')
    before = path.read_text()

    report = init_check.inspect(path)

    assert path.read_text() == before
    assert report["settings"][config_gate.WRITE_GRANT_SETTINGS_KEY]["enabled"] is False
    assert sorted(p.name for p in tmp_path.iterdir()) == ["operator.local.json"]


def test_the_shared_dispatch_loop_is_still_grant_unaware(granting_config):
    """MUST NOT BE LOST — honesty about GRANT-05's re-scoped boundary. The moment
    `chunking.dispatch_plan` gains a `grant` parameter, `revoke_grant`'s docstring — which
    promises revocation bites at the NEXT SEND and not mid-dispatch — stops being true, and
    this is the test that notices."""
    import inspect as _inspect

    assert "grant" not in _inspect.signature(chunking.dispatch_plan).parameters
