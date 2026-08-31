"""53-01 — the operator-openable write grant.

The property under test throughout: an operator with no shell can authorize a live write,
and CANNOT authorize a write outside the batch they named. Everything else here serves
those two.

The tracer test walks the whole path in one function on purpose — an admin-set key, a
planned grant, an explicit yes, an armed window, a verified disarm — because that is the
path G-2 said was unreachable from the operator's chair.
"""
import ast
import os
import re
import textwrap
from pathlib import Path

import pytest

import chunking
import config_gate
import control_actions
import dispatch
import durable_paths
import executions_client
import n8n_arming
import remainder_queue
import write_grant
import written_records

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


def _executions_page():
    """One exhausted executions-list page — `write_grant.allowance_headroom`'s sample
    (Phase 57). No items, no cursor: `listing_exhausted: True`, `sampled: True`,
    `count_in_window: 0`, so the default `fake_config` allowance (2500) reads back as
    fully remaining unless a test overrides it."""
    return {"data": []}


def _plan_reads(lanes=1, balances=None, guardrail=None):
    """Everything ONE `plan_grant` consumes, in `plan_grant`'s frozen call order:

        one /api/v1/workflows read per lane   (id resolution)
        one executions-list read              (Phase 57's headroom sample — ONE per
                                               grant, not per lane, sampled by `plan_grant`
                                               itself and handed to `envelope()` so it is
                                               never walked twice; REVIEW-57-H9)
        one status POST                       (balances — only when a provider is priced,
                                               computed inside `envelope()`)
        one workflow read per lane            (GUARDRAIL A's live write-safety read)

    The guardrail reads default to DISARMED bodies, because a scripted transport that runs
    out answers `{}` — which guardrail A correctly treats as unreadable and refuses on.
    """
    reads = [_workflow_list()] * lanes
    reads.append(_executions_page())
    if balances is not None:
        reads.append(balances)
    return reads + [guardrail if guardrail is not None else _base_workflow()] * lanes


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
        _executions_page(),                                     # Phase 57 headroom sample
        _base_workflow(),                                       # guardrail A's live read
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
    resolve_transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, resolve_transport)

    transport = stub_module_transport_factory([_base_workflow()])
    result = n8n_arming.arm_for_dispatch(WORKFLOW_ID, ["99999"], [], False,
                                         granting_config, transport=transport, grant=grant)

    assert result["outcome"] == n8n_arming.REFUSED
    assert "99999" in result["detail"], "the refusal must name the offending value"
    assert transport.calls == []


def test_a_domain_outside_the_grant_is_refused_before_any_transport_call(
        granting_config, stub_module_transport_factory):
    resolve_transport = stub_module_transport_factory(_plan_reads())
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
    resolve_transport = stub_module_transport_factory(_plan_reads())
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
    resolve_transport = stub_module_transport_factory(_plan_reads(lanes=2))
    grant = _open(granting_config, resolve_transport, lanes=("enrichment", "contacts"))

    for workflow_id in (WORKFLOW_ID, CONTACTS_WORKFLOW_ID):
        assert write_grant.covers(grant, workflow_id=workflow_id,
                                  record_ids=[RECORD_ID], record_domains=[]) is None


def test_the_empty_allowlist_refusal_still_fires_under_a_grant(
        granting_config, stub_module_transport_factory):
    """`covers` is a subset check, and the empty set is trivially a subset — so the
    grant must not become a way past the empty-allowlist refusal."""
    resolve_transport = stub_module_transport_factory(_plan_reads())
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
    resolve_transport = stub_module_transport_factory(_plan_reads())
    grant = write_grant.close_grant(_open(granting_config, resolve_transport),
                                    write_grant.CLOSED_REVOKED)

    transport = stub_module_transport_factory([_base_workflow()])
    result = n8n_arming.arm_for_dispatch(WORKFLOW_ID, [RECORD_ID], [], False,
                                         granting_config, transport=transport, grant=grant)

    assert result["outcome"] == n8n_arming.REFUSED
    assert write_grant.CLOSED_REVOKED in result["detail"]
    assert transport.calls == []


# F2 (2026-08-25, debug/resolved/walk-write-path-defects.md): the two pins immediately
# below are LEFT UNMODIFIED on purpose, not overlooked. F2 gives a per-send "yes" with no
# STANDING grant a path to arm — but it does so by having the SKILL layer synthesize a
# single-use grant via `write_grant.authorize_ungranted_send()` (which composes
# `plan_grant()` + `open_grant()`) and hand THAT to `n8n_arming.armed_window(...,
# grant=...)`. It never calls `arm_for_dispatch`/`armed_window` with `grant=None` for an
# interactive send. These two tests exercise EXACTLY that `grant=None` call shape, which
# stays reachable only from the headless path (`scheduled_arm.py`) and is untouched by F2
# — so both pins remain true and are kept byte-identical rather than rewritten for a
# design this session did not take.
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


# --- F2 (2026-08-25): authorize_ungranted_send — the per-send bridge with NO standing --
# --- grant open. Composes plan_grant()+open_grant() into a single-use grant. -------------

def test_authorize_ungranted_send_arms_with_the_same_guardrails_a_standing_grant_gets(
        granting_config, stub_module_transport_factory):
    """The tracer: settings key already on, no environment variable anywhere, one
    synthesized single-use grant, one armed window, one verified disarm."""
    transport = stub_module_transport_factory([
        _workflow_list(),                                       # plan_grant's lane resolve
        _executions_page(),                                     # Phase 57 headroom sample
        _base_workflow(),                                       # guardrail A's live read
        _base_workflow(), _base_workflow(), {}, {}, {},         # the arm
        _base_workflow(record_writes='"true"', ids=f'"{RECORD_ID}"'),   # arm verification
        _armed_workflow(), _armed_workflow(), {}, {}, {}, _base_workflow(),   # the disarm
    ])

    decision = write_grant.authorize_ungranted_send(
        granting_config, lane="enrichment", object_type="companies",
        record_ids=[RECORD_ID], record_domains=[], allow_create=False,
        label="this send", transport=transport)

    assert decision["armed"] is True
    assert decision["refusal"] is None
    assert decision["workflow_id"] == WORKFLOW_ID
    grant = decision["grant"]
    assert grant["kind"] == write_grant.KIND
    assert grant["state"] == write_grant.OPEN
    assert grant["record_ids"] == [RECORD_ID], "the grant must cover THIS send's records, never wider"

    with n8n_arming.armed_window(decision["workflow_id"], [RECORD_ID], [], False,
                                 granting_config, transport=transport,
                                 grant=decision["grant"]) as window:
        pass

    assert window.arm_result["outcome"] == n8n_arming.ARMED
    assert window.disarm_result["outcome"] == n8n_arming.DISARMED
    assert os.environ.get(n8n_arming.ARM_ENV_VAR) is None


# 260829-lg3: closes two GRANDFATHERED_UNCOVERED entries in
# test_skill_sequence_coverage.py -- (contact-upload, ...) and (enrich-before-ingest, ...)
# -- both registered under the identical call tuple `config_gate.load_config ->
# write_grant.authorize_send -> write_grant.authorize_ungranted_send ->
# n8n_arming.armed_window -> dispatch.dispatch`. Neither existing test drove
# dispatch.dispatch INSIDE an armed_window body: the grant-present authorize_send branch
# was never chained into armed_window at all, and
# test_authorize_ungranted_send_arms_with_the_same_guardrails_a_standing_grant_gets's
# `with armed_window(...): pass` stopped one call short of it. This test drives BOTH
# branches to a real dispatch.dispatch call and asserts on the returned result -- neither
# `with` body is `pass` any more.
def test_authorize_send_and_authorize_ungranted_send_each_drive_dispatch_inside_their_own_armed_window(
        granting_config, stub_module_transport_factory, stub_transport, sample_csv):
    # Branch 1: a standing, grant-present authorize_send.
    grant_transport = stub_module_transport_factory([
        _workflow_list(),                                       # plan_grant's lane resolve
        _executions_page(),                                     # Phase 57 headroom sample
        _base_workflow(),                                       # guardrail A's live read
        _base_workflow(), _base_workflow(), {}, {}, {},         # the arm
        _base_workflow(record_writes='"true"', ids=f'"{RECORD_ID}"'),   # arm verification
        _armed_workflow(), _armed_workflow(), {}, {}, {}, _base_workflow(),   # the disarm
    ])
    grant = _open(granting_config, grant_transport)
    decision = write_grant.authorize_send(
        grant, lane="enrichment", record_ids=[RECORD_ID], record_domains=[])
    assert decision["armed"] is True

    with n8n_arming.armed_window(decision["workflow_id"], [RECORD_ID], [], False,
                                 granting_config, transport=grant_transport,
                                 grant=decision["grant"]) as window:
        result = dispatch.dispatch(str(sample_csv), True, granting_config,
                                   transport=stub_transport)

    assert window.arm_result["outcome"] == n8n_arming.ARMED
    assert window.disarm_result["outcome"] == n8n_arming.DISARMED
    assert result["run_id"]
    assert len(stub_transport.calls) == 1

    # Branch 2: authorize_ungranted_send, no standing grant -- a FRESH transport instance,
    # since a stub_module_transport_factory's scripted queue is drained on use and cannot
    # be reused across the two branches. `_workflow_id_cache` is process-lifetime and was
    # already populated by branch 1's resolve of the SAME "enrichment" lane name, so it
    # must be cleared here or branch 2's plan_grant would skip its own workflow-list read
    # and consume the queue one entry out of step.
    executions_client._workflow_id_cache.clear()
    ungranted_transport = stub_module_transport_factory([
        _workflow_list(),
        _executions_page(),
        _base_workflow(),
        _base_workflow(), _base_workflow(), {}, {}, {},
        _base_workflow(record_writes='"true"', ids=f'"{RECORD_ID}"'),
        _armed_workflow(), _armed_workflow(), {}, {}, {}, _base_workflow(),
    ])
    decision2 = write_grant.authorize_ungranted_send(
        granting_config, lane="enrichment", object_type="companies",
        record_ids=[RECORD_ID], record_domains=[], allow_create=False,
        label="this send", transport=ungranted_transport)
    assert decision2["armed"] is True

    with n8n_arming.armed_window(decision2["workflow_id"], [RECORD_ID], [], False,
                                 granting_config, transport=ungranted_transport,
                                 grant=decision2["grant"]) as window2:
        # The SAME stub_transport instance is safe to reuse here, unlike the
        # module-shaped one above -- it has no scripted responses list, so it is not a
        # draining queue; it just always answers the default accepted body and appends
        # to .calls.
        result2 = dispatch.dispatch(str(sample_csv), True, granting_config,
                                    transport=stub_transport)

    assert window2.arm_result["outcome"] == n8n_arming.ARMED
    assert window2.disarm_result["outcome"] == n8n_arming.DISARMED
    assert result2["run_id"]
    assert len(stub_transport.calls) == 2


def test_authorize_ungranted_send_refuses_when_the_admin_has_not_enabled_write_grants(
        fake_config, stub_module_transport_factory):
    """No new settings key — the same `allow_write_grants` gate a standing grant needs."""
    transport = stub_module_transport_factory([])

    decision = write_grant.authorize_ungranted_send(
        fake_config, lane="enrichment", object_type="companies",
        record_ids=[RECORD_ID], record_domains=[], allow_create=False,
        label="this send", transport=transport)

    assert decision["armed"] is False
    assert decision["grant"] is None
    assert config_gate.WRITE_GRANT_SETTINGS_KEY in decision["detail"]
    assert transport.calls == []


def test_authorize_ungranted_send_refuses_over_a_dirty_backend_guardrail_a(
        granting_config, stub_module_transport_factory):
    """Guardrail A fires HERE too, at the moment of the send — there is no earlier "plan"
    turn on the ungranted path the way a standing grant has one."""
    transport = stub_module_transport_factory([
        _workflow_list(),
        _executions_page(),
        _armed_workflow(),   # guardrail A's live read: writes already enabled
    ])

    decision = write_grant.authorize_ungranted_send(
        granting_config, lane="enrichment", object_type="companies",
        record_ids=[RECORD_ID], record_domains=[], allow_create=False,
        label="this send", transport=transport)

    assert decision["armed"] is False
    assert decision["refusal"]["guardrail"] == "A"
    assert transport.mutating_calls == []


def test_authorize_ungranted_send_refuses_an_empty_record_set(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([])

    decision = write_grant.authorize_ungranted_send(
        granting_config, lane="enrichment", object_type="companies",
        record_ids=[], record_domains=[], allow_create=False,
        label="this send", transport=transport)

    assert decision["armed"] is False
    assert "empty" in decision["detail"]
    # D-59-08 (59-06 Task 2, FINDING 1): the ungranted path relays plan_grant's own
    # refusal verbatim, so it names the same resolution — consistent with
    # test_plan_grant_refuses_an_empty_record_set_at_plan_time below, never a second
    # wording for the same refusal.
    assert "read-only" in decision["detail"]
    assert transport.calls == []


def test_authorize_ungranted_send_never_widens_beyond_this_sends_own_records(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory(_plan_reads())

    decision = write_grant.authorize_ungranted_send(
        granting_config, lane="enrichment", object_type="companies",
        record_ids=[RECORD_ID], record_domains=[], allow_create=False,
        label="this send", transport=transport)

    assert decision["grant"]["record_ids"] == [RECORD_ID]
    assert decision["grant"]["lanes"] == ["enrichment"]


def test_authorize_ungranted_send_returns_the_same_shape_authorize_send_does(
        granting_config, stub_module_transport_factory):
    """A lane skill's dispatch code branches on `decision["armed"]` identically whichever
    function produced it — both must return exactly these five keys. RECORDED EDIT
    (F2 archive follow-up, 2026-08-25): the original body only ever called
    `authorize_send(None, ...)` and never touched `authorize_ungranted_send` at all, so
    the docstring's "both must return exactly these five keys" claim was unverified for
    one of the two named functions. Now calls both against the same shape assertion."""
    with_grant = write_grant.authorize_send(
        None, lane="enrichment", record_ids=[RECORD_ID], record_domains=[])
    assert set(with_grant) == {"armed", "workflow_id", "grant", "refusal", "detail"}

    transport = stub_module_transport_factory(_plan_reads())
    ungranted = write_grant.authorize_ungranted_send(
        granting_config, lane="enrichment", object_type="companies",
        record_ids=[RECORD_ID], record_domains=[], allow_create=False,
        label="this send", transport=transport)
    assert set(ungranted) == {"armed", "workflow_id", "grant", "refusal", "detail"}


def test_authorize_ungranted_sends_grant_never_reaches_arm_for_dispatch_with_grant_none():
    """The ungranted bridge is a DIFFERENT call shape from the two pins directly above —
    it always hands `arm_for_dispatch`/`armed_window` a real (non-None) grant object,
    never `grant=None`. Documented here as the structural fact those two pins' comment
    depends on, rather than left implicit."""
    import inspect
    source = inspect.getsource(write_grant.authorize_ungranted_send)
    assert "grant=None" not in source
    assert "arm_for_dispatch(" not in source, (
        "authorize_ungranted_send must never CALL arm_for_dispatch directly — it builds "
        "a grant and lets the caller's own armed_window(..., grant=...) do that, exactly "
        "like authorize_send's contract (naming it in a comment/docstring is fine)"
    )


# --- planning reads, never mutates --------------------------------------------------------

def test_plan_grant_makes_no_mutating_call_of_any_kind(granting_config,
                                                       stub_module_transport_factory):
    transport = stub_module_transport_factory(_plan_reads())

    proposal = _proposal(granting_config, transport)

    assert proposal["kind"] == write_grant.PROPOSAL_KIND
    assert transport.mutating_calls == []
    # Id resolution, then the Phase 57 headroom sample, then GUARDRAIL A's live
    # write-safety read. Reads only.
    assert transport.verbs == ["get", "get", "get"]


def test_plan_grant_refuses_an_empty_record_set_at_plan_time(granting_config,
                                                             stub_module_transport_factory):
    """Refused at PLAN time, not deferred to the arm: a grant over nothing would read as a
    grant while granting nothing."""
    transport = stub_module_transport_factory(_plan_reads())

    result = _proposal(granting_config, transport, ids=(), domains=())

    assert result["outcome"] == write_grant.REFUSED
    assert "empty record set" in result["detail"]
    assert transport.calls == []
    # D-59-08 (59-06 Task 2, FINDING 1 of 53-WALK-RECORD.md): the refusal is UNCHANGED
    # — still a refusal, its original explanation intact — and now also names what
    # would resolve it: a read-only HubSpot lookup for the record's own id, or its
    # company's domain.
    assert "read-only" in result["detail"]
    assert "domain" in result["detail"]


def test_the_empty_record_set_refusal_names_the_original_explanation_intact(
        granting_config, stub_module_transport_factory):
    """The WHY (a grant over nothing would report as success) must still be the first
    thing read, verbatim — the resolution-naming sentence is an ADDITION, not a
    replacement."""
    transport = stub_module_transport_factory(_plan_reads())

    result = _proposal(granting_config, transport, ids=(), domains=())

    assert result["detail"].startswith(
        "refusing to plan a grant over an empty record set. The deployed "
        "_writeSafetyAllows() returns false when both allowlists are empty, so a "
        "grant over nothing would report as a grant while granting nothing at all — "
        "worse than refusing, because it reads as success."
    )


def test_write_grant_module_never_calls_a_hubspot_search_endpoint():
    """T-59-26 (D-59-08): the empty-record-set refusal now NAMES a resolution path, but
    the resolution itself must never move inside write_grant.py — plan_grant is an
    authorization boundary, and giving it a lookup that can change what it grants is
    exactly the widening this phase's scope pins as untouched. A structural grep over
    the module SOURCE (never the compiled bytecode), so a later edit cannot move the
    lookup inside the authorization boundary without failing this test."""
    import inspect
    source = inspect.getsource(write_grant)
    forbidden = ("hubapi.com", "crm/v3/objects", "/search", "hubspot_search",
                "HubSpot Company Search", "hubspot_lookup(")
    for needle in forbidden:
        assert needle not in source, (
            f"{needle!r} found in write_grant.py's source — a HubSpot search call "
            f"does not belong inside the authorization boundary; resolution happens "
            f"in the skill, before the call to plan_grant, never inside it"
        )


def test_plan_grant_refuses_an_unknown_lane_by_name(granting_config,
                                                    stub_module_transport_factory):
    transport = stub_module_transport_factory(_plan_reads())

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
    transport = stub_module_transport_factory(_plan_reads())

    result = _proposal(fake_config, transport)

    assert result["outcome"] == write_grant.REFUSED
    assert config_gate.WRITE_GRANT_SETTINGS_KEY in result["detail"]
    assert "operator.local.json" in result["detail"]
    assert transport.calls == []


def test_the_preflight_seam_can_refuse_before_a_proposal_exists(
        granting_config, stub_module_transport_factory):
    """53-02's guardrail A lands as a fill, not a reshape."""
    transport = stub_module_transport_factory(_plan_reads())
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
    transport = stub_module_transport_factory(_plan_reads())
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
    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport, allow_create=True,
                  ids=(RECORD_ID,), domains=("known.example",))

    assert grant["object_type"] == "companies"
    assert grant["record_ids"] == [RECORD_ID]
    assert grant["record_domains"] == ["known.example"]
    assert grant["allow_create"] is True
    assert grant["lanes"] == ["enrichment"]
    assert grant["label"] == "the 2026-08-25 batch"
    assert grant["opened_at"].endswith("+00:00")
    # 53-02 filled the envelope (GRANT-02); the two below stay initialised-and-unwritten
    # until a close or a send outcome writes them.
    assert grant["envelope"]["record_count"] == 2
    assert grant["closed_reason"] is None
    assert grant["consecutive_disarm_failures"] == 0


# --- Phase 61 Plan 06 Task 3 (REVIEW-11) -------------------------------------------------
#
# "one grant is documentation-only" was PARTLY a real find and PARTLY a wrong premise.
# The wrong-premise half: `covers()` refuses any record id ABSENT from the grant's
# `record_ids` at grant time, and a company or contact CREATED during the batch has
# exactly such an id — reviewers read this as an unclosed gap. Verified against the
# real code below: `covers()` ALSO checks `record_domains`, symmetrically with
# `record_ids` (same refusal shape, same "outside the grant" wording). This skill's own
# batch-composition step (SKILL.md step 2) confirms every company's domain BEFORE the
# grant is opened — a domainless company is never let into the batch without one — so a
# same-run create's brand-new id is never the ONLY handle a later send has for it; its
# domain, already named at grant-open time, is. No change to write_grant.py's
# `covers()` was needed for this — these two tests ARE the verification the plan asked
# for, and the finding is recorded here rather than invented as a fix for a defect that
# does not exist.

def test_covers_admits_a_same_run_create_via_the_domain_named_at_grant_time(
        granting_config, stub_module_transport_factory):
    """`covers()` requires EVERY passed id/domain to be inside the grant (an AND, not
    an OR, across the two lists) — so a same-run create is covered only when the SEND
    itself is expressed by the domain the grant already named, not by the record's own
    brand-new id (which the grant could not have known at open time). A send that
    passes BOTH the unknown-at-grant-time id AND the known domain still refuses —
    passing the id at all, for a record whose id did not exist when the grant was
    planned, is not this skill's own calling convention (SKILL.md's own
    `record_ids=<this send's ids>` is empty for a record with no id yet); expressing
    the send by domain alone is."""
    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport, ids=(), domains=("newco.example",))

    # An id genuinely outside the grant, with no domain given, still refuses.
    id_only = write_grant.covers(
        grant, lane="enrichment", workflow_id=WORKFLOW_ID,
        record_ids=["999999"], record_domains=[])
    assert id_only is not None, "an id alone, absent from the grant, must still refuse"

    # The send for a same-run create, expressed the way this skill actually composes
    # it — by the domain the grant already named, with no id (none existed at grant
    # time) — is covered with no widening and no code change.
    covered = write_grant.covers(
        grant, lane="enrichment", workflow_id=WORKFLOW_ID,
        record_ids=[], record_domains=["newco.example"])
    assert covered is None, "a same-run create is covered via the domain named at grant time"


def test_covers_still_refuses_a_domain_never_named_at_grant_time(
        granting_config, stub_module_transport_factory):
    """GRANT-03 is unweakened by the finding above: a domain genuinely outside the
    grant still refuses, by name, exactly as it always has."""
    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport, ids=(), domains=("newco.example",))

    refusal = write_grant.covers(
        grant, lane="enrichment", workflow_id=WORKFLOW_ID,
        record_ids=[], record_domains=["unrelated.example"])
    assert refusal is not None
    assert refusal["outside_record_domains"] == ["unrelated.example"]


def test_close_grant_returns_a_copy_and_makes_no_network_call(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport)
    before = len(transport.calls)

    closed = write_grant.close_grant(grant, write_grant.CLOSED_BATCH_COMPLETE)

    assert closed["state"] == write_grant.CLOSED
    assert closed["closed_reason"] == write_grant.CLOSED_BATCH_COMPLETE
    assert grant["state"] == write_grant.OPEN, "the input must never be mutated"
    assert len(transport.calls) == before


# --- nothing reaches disk -----------------------------------------------------------------

def test_nothing_about_a_grant_is_written_to_disk_or_to_the_environment(
        granting_config, stub_module_transport_factory, monkeypatch, tmp_path):
    """GRANT-06 / D-53-03: the grant exists only as a value in the conversation."""
    monkeypatch.setattr(config_gate, "config_path", lambda *a, **k: tmp_path / "nope.json")
    env_before = dict(os.environ)
    transport = stub_module_transport_factory(_plan_reads())

    grant = _open(granting_config, transport)
    write_grant.close_grant(grant, write_grant.CLOSED_BATCH_COMPLETE)

    assert list(tmp_path.iterdir()) == []
    assert dict(os.environ) == env_before

    source = Path(write_grant.__file__).read_text()
    for forbidden in ("open(", "write_text", "os.environ[", "setenv", "json.dump("):
        assert forbidden not in source, (
            f"{forbidden!r} in write_grant.py — a grant must never become durable")


# --- Task 2: the authority's edges ---------------------------------------------------------
#
# Only the JSON boolean `true` authorizes. Parametrised the way
# `test_control_arming.py::test_every_near_miss_value_refuses` is, so a future edit that
# loosens the comparison fails on eleven rows rather than one.

_NEAR_MISS_SETTINGS_VALUES = [
    "true", "True", "TRUE", "1", "yes", 1, 1.0, "", False, None, "__absent__",
]


def _config_with(fake_config, value):
    if value == "__absent__":
        return dict(fake_config)
    return {**fake_config, config_gate.WRITE_GRANT_SETTINGS_KEY: value}


@pytest.mark.parametrize("near_miss", _NEAR_MISS_SETTINGS_VALUES)
def test_every_near_miss_settings_value_refuses_the_arm(near_miss, fake_config,
                                                        stub_module_transport_factory):
    """`bool` is an `int` subclass, so 1, 1.0 and True are indistinguishable under a
    truthiness test — and the string "true" is what this key REPLACED. Any of them parsing
    as authority would make the new gate silently weaker than the old one."""
    config = _config_with(fake_config, near_miss)
    grant = {"kind": write_grant.KIND, "state": write_grant.OPEN, "lanes": ["enrichment"],
             "workflow_ids": {"enrichment": WORKFLOW_ID}, "record_ids": [RECORD_ID],
             "record_domains": [], "closed_reason": None}

    transport = stub_module_transport_factory([_base_workflow()])
    result = n8n_arming.arm_for_dispatch(WORKFLOW_ID, [RECORD_ID], [], False, config,
                                         transport=transport, grant=grant)

    assert result["outcome"] == n8n_arming.REFUSED
    assert transport.calls == []


@pytest.mark.parametrize("near_miss", _NEAR_MISS_SETTINGS_VALUES)
def test_every_near_miss_settings_value_refuses_the_plan(near_miss, fake_config,
                                                         stub_module_transport_factory):
    config = _config_with(fake_config, near_miss)
    transport = stub_module_transport_factory(_plan_reads())

    result = _proposal(config, transport)

    assert result["outcome"] == write_grant.REFUSED
    assert transport.calls == []


def test_only_the_json_boolean_true_authorizes(fake_config):
    """The positive half of the parametrisation above — without it, a `write_grants_enabled`
    that returned False unconditionally would pass every row."""
    assert config_gate.write_grants_enabled(
        {**fake_config, config_gate.WRITE_GRANT_SETTINGS_KEY: True}) is True
    for near_miss in _NEAR_MISS_SETTINGS_VALUES:
        assert config_gate.write_grants_enabled(_config_with(fake_config, near_miss)) is False


def test_a_config_missing_the_key_entirely_refuses_by_name(fake_config,
                                                           stub_module_transport_factory):
    """The degrade-safely-when-absent path — which is what an existing operator's settings
    file looks like the day this ships."""
    assert config_gate.WRITE_GRANT_SETTINGS_KEY not in fake_config
    transport = stub_module_transport_factory(_plan_reads())

    result = _proposal(fake_config, transport)

    assert config_gate.WRITE_GRANT_SETTINGS_KEY in result["detail"]
    assert "operator.local.json" in result["detail"]
    assert "admin" in result["detail"]


def test_no_configured_value_reaches_any_refusal_string(stub_module_transport_factory):
    """T-27-12's convention: refusals name keys and files, never values."""
    secrets = {"n8n_url": "https://secret-tenant.n8n.cloud",
               "webhook_secret": "SECRET-WEBHOOK-VALUE",
               "n8n_api_key": "SECRET-API-KEY-VALUE",
               config_gate.WRITE_GRANT_SETTINGS_KEY: "true"}   # a near miss, so it refuses

    refusals = [
        _proposal(secrets, stub_module_transport_factory(_plan_reads())),
        write_grant.open_grant({"kind": write_grant.PROPOSAL_KIND}, "yes", secrets),
        n8n_arming.arm_for_dispatch(
            WORKFLOW_ID, [RECORD_ID], [], False, secrets,
            transport=stub_module_transport_factory([_base_workflow()]),
            grant={"kind": write_grant.KIND, "state": write_grant.OPEN,
                   "workflow_ids": {"enrichment": WORKFLOW_ID},
                   "record_ids": [RECORD_ID], "record_domains": []}),
    ]

    for refusal in refusals:
        assert refusal["outcome"] == write_grant.REFUSED, refusal
        for value in ("SECRET-WEBHOOK-VALUE", "SECRET-API-KEY-VALUE",
                      "secret-tenant.n8n.cloud"):
            assert value not in refusal["detail"]


def test_the_settings_key_is_not_a_capability_row():
    """D-53-01: `CAPABILITY_KEYS` means "these keys are PRESENT", not "an admin authorized
    this". Folding the key in would quietly change what a refusal MEANS, so a later
    well-meaning edit that does it fails here loudly."""
    assert config_gate.WRITE_GRANT_SETTINGS_KEY not in config_gate.CAPABILITY_KEYS
    assert config_gate.WRITE_GRANT_SETTINGS_KEY not in config_gate._CAPABILITY_DESCRIPTIONS
    for required_keys in config_gate.CAPABILITY_KEYS.values():
        assert config_gate.WRITE_GRANT_SETTINGS_KEY not in required_keys


# --- the two confirmation gates, checked behaviourally against one shared list --------------
#
# NOT by inspecting source text for a literal. A source pin asserting a string appears in
# two files proves TOKEN PRESENCE, not semantic agreement: a `.strip().lower()` added on one
# side still contains the literal and still matches, while accepting inputs the other
# refuses. Driving one list through both functions checks the property directly.

_NOT_YES = ["y", "Y", "YES", "Yes", "yes ", " yes", "ok", "sure", "", None, True]


def _bogus_proposal(kind):
    return {"kind": kind, "workflow_id": WORKFLOW_ID}


@pytest.mark.parametrize("confirmation", _NOT_YES)
def test_neither_confirmation_gate_accepts_anything_but_the_exact_string_yes(
        confirmation, granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory(_plan_reads())
    proposal = _proposal(granting_config, transport)

    opened = write_grant.open_grant(proposal, confirmation, granting_config)
    executed = control_actions.execute_action(
        _bogus_proposal("workflow_active"), confirmation, granting_config,
        transport=stub_module_transport_factory([]))

    assert opened["outcome"] == write_grant.REFUSED
    assert "not confirmed" in opened["detail"]
    assert executed["outcome"] == control_actions.REFUSED
    assert "not confirmed" in executed["detail"]


def test_both_confirmation_gates_proceed_on_the_exact_string_yes(
        granting_config, stub_module_transport_factory):
    """The positive half: without it, two functions that refused everything would pass the
    parametrisation above. `execute_action` is given an out-of-allowlist proposal, so
    getting PAST the confirmation gate is visible as a different refusal, with no
    transport call."""
    transport = stub_module_transport_factory(_plan_reads())
    proposal = _proposal(granting_config, transport)

    opened = write_grant.open_grant(proposal, "yes", granting_config)
    assert opened["kind"] == write_grant.KIND
    assert opened["state"] == write_grant.OPEN

    control_transport = stub_module_transport_factory([])
    executed = control_actions.execute_action(
        _bogus_proposal("not_an_action_kind"), "yes", granting_config,
        transport=control_transport)
    assert executed["outcome"] == control_actions.REFUSED
    assert "not confirmed" not in executed["detail"], (
        "it must have got PAST the confirmation gate")
    assert "I can't do that" in executed["detail"]
    assert control_transport.calls == []


def test_both_confirmation_gates_raise_type_error_when_the_argument_is_omitted(
        granting_config, stub_module_transport_factory):
    """No default, on both — a caller that forgets the confirmation gets a TypeError, never
    a silent yes."""
    transport = stub_module_transport_factory(_plan_reads())
    proposal = _proposal(granting_config, transport)

    with pytest.raises(TypeError):
        write_grant.open_grant(proposal, config=granting_config)
    with pytest.raises(TypeError):
        control_actions.execute_action(_bogus_proposal("workflow_active"),
                                       config=granting_config)


# =========================================================================================
# 53-02 Task 1 — the envelope: the arithmetic the operator reads BEFORE the yes (GRANT-02)
# =========================================================================================

PRICED_PROVIDERS = ["lusha", "zoominfo", "apollo"]


@pytest.fixture
def priced_config(granting_config):
    """A config that actually prices a batch: a provider selection and the chunk ceiling.

    `fake_config` deliberately carries neither, which is why the wave-1 tests above cost
    no status POST — that split is load-bearing for their scripted transports.
    """
    return {**granting_config,
            "enrichment_providers": list(PRICED_PROVIDERS),
            "max_records_per_chunk": 2}


def _balances(lusha=50, zoominfo=None, apollo=None):
    """What `hubspot/backend-status` answers. A `None` credit reads as unreadable in
    `cost_guard.fetch_balances` — the tri-state's `unknown`, not a zero."""
    rows = [{"provider": "lusha", "credits": lusha},
            {"provider": "zoominfo", "credits": zoominfo},
            {"provider": "apollo", "credits": apollo, "error": "403 — not a master key"}]
    return {"balances": rows}


def _priced_plan_reads(balances=None, lanes=1):
    """A priced plan: the same frozen order, with the balances POST populated."""
    return _plan_reads(lanes=lanes,
                       balances=balances if balances is not None else _balances())


def _priced_proposal(config, transport, **kwargs):
    return _proposal(config, transport, **kwargs)


def test_the_envelope_reports_every_figure_grant_02_names(
        priced_config, stub_module_transport_factory):
    """Record count, worst-case credits PER PROVIDER, worst-case Anthropic dollars, a
    projected execution count and the configured monthly allowance — all before a yes."""
    transport = stub_module_transport_factory(_priced_plan_reads())
    proposal = _priced_proposal(priced_config, transport, ids=("1", "2", "3", "4"))

    figures = proposal["envelope"]
    assert figures["record_count"] == 4
    assert set(figures["provider_credits"]) == {"lusha", "zoominfo", "apollo"}
    assert figures["provider_credits"]["lusha"]["credits"] == 8       # 2 credits/company
    assert figures["provider_credits"]["zoominfo"]["credits"] == pytest.approx(4.32)
    assert figures["anthropic_usd"] == pytest.approx(0.274496)
    # 4 records at a ceiling of 2 = 2 chunks; 2 webhook executions + 4 sub-executions.
    assert figures["chunk_count"] == 2
    assert figures["projected_executions"] == 6
    assert figures["monthly_execution_allowance"] == 2500


def test_the_execution_count_is_labelled_projected_and_never_measured(
        priced_config, stub_module_transport_factory):
    transport = stub_module_transport_factory(_priced_plan_reads())
    figures = _priced_proposal(priced_config, transport, ids=("1", "2"))["envelope"]

    assert figures["basis"]["projected_executions"] == write_grant.PROJECTED
    assert figures["basis"]["record_count"] == write_grant.MEASURED
    assert "projected, not measured" in figures["block"]


def test_the_anthropic_figure_is_labelled_projected_never_measured(
        priced_config, stub_module_transport_factory):
    """Phase 54 Task 3, 2026-08-27: `anthropic_usd` is a static rate-table multiplication
    (`record_count * config/cost_rates.json`'s dated per-record rate) — no code path in
    this repo reads back Anthropic's real token usage, so this figure has never been a
    measurement (OP-54-05). Before this date it was pinned to `write_grant.MEASURED`,
    which is the exact false audit trail T-54-03 exists to close. The executions and
    record_count bases are untouched by this change.

    Phase 54 Task 07, 2026-08-27 (WR-04): the rendered sentence itself called this same
    figure both a "worst case" (ceiling) and "a floor" (lower bound) — mutually exclusive
    claims about one number. `cost_rates.json`'s own citation for
    `anthropic_usd_per_record` says it is an observed all-in AVERAGE across two canary
    executions, not a bound in either direction, so real spend can land either side of
    it. This test scopes to the single Anthropic-spend line of `figures['block']` (not
    the whole block, which legitimately calls provider credits a ceiling a few lines
    above) and asserts the sentence commits to the one framing the citation supports —
    projection — and to neither discarded bound-word."""
    transport = stub_module_transport_factory(_priced_plan_reads())
    figures = _priced_proposal(priced_config, transport, ids=("1", "2"))["envelope"]

    assert figures["basis"]["anthropic_usd"] == write_grant.PROJECTED
    assert figures["basis"]["anthropic_usd"] != write_grant.MEASURED
    assert figures["basis"]["projected_executions"] == write_grant.PROJECTED
    assert figures["basis"]["record_count"] == write_grant.MEASURED

    anthropic_line = next(
        line for line in figures["block"].splitlines()
        if "Anthropic model spend" in line)
    assert "projection" in anthropic_line.lower()
    assert "worst case" not in anthropic_line.lower()
    assert "floor" not in anthropic_line.lower()


def test_an_unreadable_provider_balance_reads_unconfirmed_never_as_headroom(
        priced_config, stub_module_transport_factory):
    """cost_guard's tri-state, carried through unchanged: Apollo exposes no credit pool on
    this account, and rendering that as zero would be a standing false alarm."""
    transport = stub_module_transport_factory(_priced_plan_reads())
    figures = _priced_proposal(priced_config, transport, ids=("1",))["envelope"]

    assert figures["verdicts"]["apollo"]["verdict"] == "unknown"
    assert figures["verdicts"]["apollo"]["remaining_credits"] is None
    assert figures["verdicts"]["lusha"]["verdict"] == "ok"

    block = figures["block"]
    assert "unconfirmed" in block
    assert "| apollo | unknown | unknown | unconfirmed |" in block


def test_an_insufficient_balance_is_not_collapsed_into_unconfirmed(
        priced_config, stub_module_transport_factory):
    """The other side of the same branch: a READ balance that is genuinely too small must
    read as too small, not as unknown."""
    transport = stub_module_transport_factory(_priced_plan_reads(_balances(lusha=1)))
    figures = _priced_proposal(priced_config, transport, ids=("1", "2"))["envelope"]

    assert figures["verdicts"]["lusha"]["verdict"] == "insufficient"
    assert "NOT ENOUGH" in figures["block"]


def test_the_envelope_carries_the_rate_tables_measured_on_date_and_its_age(
        priced_config, stub_module_transport_factory):
    from datetime import date

    transport = stub_module_transport_factory(_priced_plan_reads())
    proposal = write_grant.plan_grant(
        priced_config, lanes=["enrichment"], object_type="companies",
        record_ids=["1"], record_domains=[], allow_create=False, label="dated",
        transport=transport, today=date(2026, 8, 25))

    figures = proposal["envelope"]
    assert figures["rates_measured_on"] == "2026-07-30"
    assert figures["rate_table_age_days"] == 26
    assert "Rates measured **2026-07-30**, 26 days ago" in figures["block"]


def test_a_config_with_no_allowance_key_degrades_one_line_not_the_whole_open(
        priced_config, stub_module_transport_factory):
    config = {k: v for k, v in priced_config.items()
              if k != "n8n_monthly_execution_allowance"}
    # No allowance key means `allowance_headroom` makes NO executions-list read at all
    # (Phase 57) — there is nothing to sample a remainder against — so this transport
    # script omits the `_executions_page()` step `_priced_plan_reads()` would otherwise
    # insert. It is now the SECOND entry (index 1), right after the workflow-list read
    # and before the balances POST — `plan_grant` samples headroom before calling
    # `envelope()`.
    transport = stub_module_transport_factory(_priced_plan_reads())
    transport._responses.pop(1)

    proposal = _priced_proposal(config, transport, ids=("1", "2"))
    figures = proposal["envelope"]

    assert proposal["kind"] == write_grant.PROPOSAL_KIND, "an absent key must not refuse"
    assert figures["allowance_configured"] is False
    assert figures["monthly_execution_allowance"] is None
    assert figures["basis"]["monthly_execution_allowance"] == write_grant.UNCONFIGURED
    # Every other figure still computed.
    assert figures["record_count"] == 2
    assert figures["projected_executions"] == 3
    assert figures["anthropic_usd"] is not None
    assert "unconfigured" in figures["block"]


def test_a_missing_chunk_ceiling_degrades_the_projection_not_the_grant(
        granting_config, stub_module_transport_factory):
    """`chunk_ceiling` refuses to guess a timeout bound — correctly, for a dispatch. A
    PROJECTION must not inherit that refusal and take the whole grant down with it."""
    transport = stub_module_transport_factory(_plan_reads())
    proposal = _proposal(granting_config, transport)   # fake_config has no ceiling key

    figures = proposal["envelope"]
    assert proposal["kind"] == write_grant.PROPOSAL_KIND
    assert figures["projected_executions"] is None
    assert figures["basis"]["projected_executions"] == write_grant.UNCONFIGURED
    assert figures["anthropic_usd"] is not None
    assert "not projected" in figures["block"]


def test_the_block_says_the_ceiling_now_constrains(
        priced_config, stub_module_transport_factory):
    """D-57-00 supersedes D-53-02: a number labelled ceiling now says it refuses, not
    only that it describes cost, and the old disclosure-only sentence is gone."""
    transport = stub_module_transport_factory(_priced_plan_reads())
    block = _priced_proposal(priced_config, transport)["envelope"]["block"]

    assert "they do not prevent it" not in block
    assert "refused" in block.lower()
    assert write_grant._CEILING_CONSTRAINT in block
    assert write_grant._ALLOWANCE_SAMPLED in block


def test_the_block_states_the_sampled_remaining_allowance(
        priced_config, stub_module_transport_factory):
    """An operator reading a share-of-allowance figure now sees what the sample actually
    found, not a hardcoded assertion that nothing was sampled."""
    transport = stub_module_transport_factory(_priced_plan_reads())
    figures = _priced_proposal(priced_config, transport)["envelope"]

    assert figures["remaining_allowance_sampled"] is True
    assert figures["spent_sampled"] == 0
    assert figures["remaining_sampled"] == 2500
    assert "Execution ceiling: **ok**" in figures["block"]


def test_the_block_names_the_verdict_in_all_three_states(
        priced_config, stub_module_transport_factory):
    """RUN-05's arithmetic must be legible in the operator's own reading order, not only
    inspectable on the returned dict."""
    ok_transport = stub_module_transport_factory(_priced_plan_reads())
    ok_block = _priced_proposal(priced_config, ok_transport)["envelope"]["block"]
    assert "Execution ceiling: **ok**" in ok_block

    over_config = {**priced_config, "n8n_monthly_execution_allowance": 1,
                   "max_records_per_chunk": 2}
    over_transport = stub_module_transport_factory(_priced_plan_reads())
    over_result = _priced_proposal(over_config, over_transport, ids=("1", "2", "3"))
    over_block = over_result["envelope"]["block"]
    assert "Execution ceiling: **OVER**" in over_block
    assert "execution(s) over" in over_block

    unknown_config = {k: v for k, v in priced_config.items()
                       if k != "n8n_monthly_execution_allowance"}
    unknown_transport = stub_module_transport_factory(_priced_plan_reads())
    unknown_transport._responses.pop(1)
    unknown_block = _priced_proposal(unknown_config, unknown_transport)["envelope"]["block"]
    assert "Execution ceiling: **unconfirmed**" in unknown_block


def test_the_block_carries_the_retention_caveat_when_sampled_from_an_exhausted_listing(
        priced_config, stub_module_transport_factory):
    """`_executions_page()` is a single no-cursor page — exhausted, not back-paged — so
    the sample rests on `listing_exhausted`, and the retention caveat must say so."""
    transport = stub_module_transport_factory(_priced_plan_reads())
    figures = _priced_proposal(priced_config, transport)["envelope"]

    assert figures["sample_listing_exhausted"] is True
    assert figures["sample_covers_full_window"] is not True
    assert write_grant.RETENTION_CAVEAT in figures["block"]


def test_plan_grant_walks_the_executions_list_exactly_once(
        priced_config, stub_module_transport_factory):
    """REVIEW-57-H9: `envelope()` must not re-sample what `plan_grant` already sampled.
    The frozen call order for a priced, one-lane grant is exactly FOUR transport calls:
    one workflow-list GET, one executions-list GET (the headroom sample), one balances
    POST, one guardrail-A workflow GET. A second executions-list read would make it
    five."""
    transport = stub_module_transport_factory(_priced_plan_reads())
    proposal = _priced_proposal(priced_config, transport)

    assert proposal["kind"] == write_grant.PROPOSAL_KIND
    assert len(transport.calls) == 4


def test_the_envelope_is_attached_to_the_grant_unchanged(
        priced_config, stub_module_transport_factory):
    """What was shown and what the grant is bound to are the same figures — not a
    recomputation that could differ from the one the operator read."""
    transport = stub_module_transport_factory(_priced_plan_reads())
    proposal = _priced_proposal(priced_config, transport, ids=("1", "2", "3"))

    grant = write_grant.open_grant(proposal, "yes", priced_config)

    assert grant["envelope"] == proposal["envelope"]
    assert grant["envelope"]["record_count"] == 3


def test_a_refused_open_still_tells_the_operator_what_the_batch_would_have_cost(
        priced_config, stub_module_transport_factory):
    transport = stub_module_transport_factory(_priced_plan_reads())
    proposal = _priced_proposal(priced_config, transport, ids=("1", "2"))

    refused = write_grant.open_grant(proposal, "no", priced_config)

    assert refused["outcome"] == write_grant.REFUSED
    assert refused["envelope"]["record_count"] == 2


def test_no_status_post_is_made_when_the_batch_prices_no_provider(
        granting_config, stub_module_transport_factory):
    """A grant that runs no provider has no balance to read, so it reads none."""
    transport = stub_module_transport_factory(_plan_reads())
    figures = _proposal(granting_config, transport)["envelope"]

    # One id-resolution read, one headroom-sample read (Phase 57), one guardrail-A read.
    # No POST: no provider, no balance.
    assert transport.verbs == ["get", "get", "get"]
    assert figures["provider_credits"] == {}
    assert "No provider credits: **0**" in figures["block"]


# =========================================================================================
# Phase 57 Task 1 — RUN-05: the refuse-before-starting ceiling (D-57-01)
# =========================================================================================


def test_allowance_headroom_reports_remaining_when_the_window_is_fully_covered(
        fake_config, stub_get_transport_factory):
    transport = stub_get_transport_factory([
        {"data": [{"id": "e-1", "status": "success",
                   "startedAt": "2026-01-01T00:00:00.000Z",
                   "stoppedAt": "2026-01-01T00:00:01.000Z", "finished": True}],
         "nextCursor": None},
    ])
    headroom = write_grant.allowance_headroom(fake_config, transport=transport)

    assert headroom["sampled"] is True
    assert headroom["allowance"] == fake_config["n8n_monthly_execution_allowance"]
    assert headroom["remaining_sampled"] == (
        fake_config["n8n_monthly_execution_allowance"] - headroom["spent_sampled"])


def test_allowance_headroom_treats_an_exhausted_listing_as_sampled(
        fake_config, stub_get_transport_factory):
    """REVIEW-57-H1, the quiet-instance half: no cursor, nothing older than the cutoff
    — the listing is exhausted, and that alone is a complete sample."""
    transport = stub_get_transport_factory([{"data": []}])
    headroom = write_grant.allowance_headroom(fake_config, transport=transport)

    assert headroom["sampled"] is True
    assert headroom["listing_exhausted"] is True
    assert headroom["covers_full_window"] is False
    assert "retention" in headroom["reason"].lower()
    assert headroom["remaining_sampled"] == fake_config["n8n_monthly_execution_allowance"]


def test_allowance_headroom_never_derives_a_remainder_from_a_truncated_sample(
        fake_config, monkeypatch):
    """Pitfall 4: a truncated (neither exhausted nor back-paged) sample must report
    `sampled: False` and `remaining_sampled: None` — never a number computed from a
    partial count."""
    import n8n_read

    def _fake_window(*a, **k):
        return {"count_in_window": 999, "observed_span_hours": 1.0,
                "covers_full_window": False, "listing_exhausted": False,
                "truncated_by_page_cap": True}

    monkeypatch.setattr(n8n_read, "executions_in_window", _fake_window)
    headroom = write_grant.allowance_headroom(fake_config)

    assert headroom["sampled"] is False
    assert headroom["remaining_sampled"] is None
    assert "truncat" in headroom["reason"].lower()


def test_allowance_headroom_names_the_missing_allowance_key(fake_config):
    config = {k: v for k, v in fake_config.items()
              if k != "n8n_monthly_execution_allowance"}
    headroom = write_grant.allowance_headroom(config)

    assert headroom["sampled"] is False
    assert headroom["allowance"] is None
    assert "n8n_monthly_execution_allowance" in headroom["reason"]


def test_allowance_headroom_sizes_the_page_budget_to_the_configured_allowance(
        fake_config, monkeypatch):
    """`ceil(2500 / 250) + 2 == 12` — the busy-instance half of REVIEW-57-H1."""
    import n8n_read

    seen = {}

    def _fake_window(*a, **k):
        seen["max_pages"] = k.get("max_pages")
        return {"count_in_window": 0, "observed_span_hours": 1.0,
                "covers_full_window": False, "listing_exhausted": True,
                "truncated_by_page_cap": False}

    monkeypatch.setattr(n8n_read, "executions_in_window", _fake_window)
    write_grant.allowance_headroom(fake_config)

    assert seen["max_pages"] >= 12


def test_ceiling_verdict_is_over_when_the_projection_exceeds_the_remainder():
    verdict = write_grant.ceiling_verdict(
        {"projected_executions": 10},
        {"sampled": True, "remaining_sampled": 5, "allowance": 100, "spent_sampled": 95})

    assert verdict["verdict"] == write_grant.CEILING_OVER
    assert verdict["shortfall"] == 5


def test_ceiling_verdict_is_ok_when_the_projection_fits():
    verdict = write_grant.ceiling_verdict(
        {"projected_executions": 5},
        {"sampled": True, "remaining_sampled": 5, "allowance": 100, "spent_sampled": 95})

    assert verdict["verdict"] == write_grant.CEILING_OK
    assert verdict["shortfall"] is None


def test_ceiling_verdict_is_unknown_whenever_the_headroom_is_unsampled():
    verdict = write_grant.ceiling_verdict(
        {"projected_executions": 10}, {"sampled": False, "remaining_sampled": None})
    assert verdict["verdict"] == write_grant.CEILING_UNKNOWN


def test_ceiling_verdict_is_unknown_when_there_is_no_projection_at_all():
    verdict = write_grant.ceiling_verdict(
        {"projected_executions": None},
        {"sampled": True, "remaining_sampled": 500, "allowance": 500, "spent_sampled": 0})
    assert verdict["verdict"] == write_grant.CEILING_UNKNOWN


# =====================================================================================
# split_for_allowance() — D-57-04, RUN-05's "offers a smaller batch"
# =====================================================================================

def test_affordable_record_count_cost_is_monotonic_over_a_range_of_n():
    """The assumption the binary search rests on, pinned rather than assumed: the
    `chunk_count + record_count` cost of N records never DECREASES as N grows, for any
    ceiling in a realistic range."""
    for ceiling in range(1, 6):
        costs = [-(-n // ceiling) + n for n in range(0, 50)]
        assert costs == sorted(costs), f"ceiling {ceiling}: cost is not monotonic in N"


def test_split_for_allowance_with_no_spec_returns_every_key_none():
    result = write_grant.split_for_allowance(
        {}, object_type="companies", headroom={"sampled": True, "remaining_sampled": 100})
    assert result["affordable_spec"] is None
    assert result["remainder_spec"] is None
    assert result["affordable"] is None
    assert result["remainder"] is None
    assert result["runs"] is None
    assert result["record_ceiling_per_run"] is None
    assert result["reason"]


def test_split_for_allowance_with_ids_and_domains_but_no_spec_still_refuses():
    """H-1's own removal: passing `record_ids=`/`record_domains=` alone, with no
    `spec=`, must NOT resurrect the parallel-split path that used to derive a scope
    independently of any work."""
    result = write_grant.split_for_allowance(
        {}, object_type="companies", record_ids=["1", "2"], record_domains=["a.example"],
        headroom={"sampled": True, "remaining_sampled": 100})
    assert result["affordable"] is None
    assert result["remainder"] is None


def test_split_for_allowance_with_an_unsampled_headroom_offers_no_split():
    result = write_grant.split_for_allowance(
        {"max_records_per_chunk": 2}, object_type="companies",
        spec={"record_ids": ["1", "2", "3"], "object_type": "companies"},
        headroom={"sampled": False, "remaining_sampled": None,
                  "reason": "the executions list could not be read."})
    assert result["affordable_spec"] is None
    assert result["remainder_spec"] is None
    assert result["affordable"] is None
    assert result["remainder"] is None
    assert "could not be read" in result["reason"]


def test_split_for_allowance_with_no_room_for_even_one_record_offers_none():
    result = write_grant.split_for_allowance(
        {"max_records_per_chunk": 2}, object_type="companies",
        spec={"record_ids": ["1", "2", "3"], "object_type": "companies"},
        headroom={"sampled": True, "remaining_sampled": 0})
    assert result["affordable_spec"] is None
    assert result["record_ceiling_per_run"] is None
    assert "not even one record fits" in result["reason"]


@pytest.mark.parametrize("build_spec,key", [
    (lambda: {"people": [{"n": i} for i in range(5)]}, "people"),
    (lambda: {"companies": [{"domain": f"{i}.example"} for i in range(5)]}, "companies"),
    (lambda: {"rows": [{"row_id": str(i)} for i in range(5)], "object_type": "contacts"},
     "rows"),
    (lambda: {"record_ids": [str(i) for i in range(5)], "object_type": "companies"},
     "record_ids"),
])
def test_the_two_product_test_affordable_and_remainder_specs_split_in_order(
        build_spec, key):
    """REVIEW-57-H8: the split spec — not the scope — is what a caller re-dispatches.
    A remainder fitting exactly 3 of 5 records (cost(3) = ceil(3/2) + 3 = 5)."""
    spec = build_spec()
    result = write_grant.split_for_allowance(
        {"max_records_per_chunk": 2}, object_type="companies", spec=spec,
        headroom={"sampled": True, "remaining_sampled": 5})

    assert result["record_ceiling_per_run"] == 3
    assert result["affordable_spec"][key] == spec[key][:3]
    assert result["remainder_spec"][key] == spec[key][3:]
    # chunking.plan_chunks must accept both halves without raising.
    chunking.plan_chunks(result["affordable_spec"], 2)
    chunking.plan_chunks(result["remainder_spec"], 2)


def test_a_domain_only_companies_spec_splits_scope_on_domains_alone():
    spec = {"companies": [{"domain": f"{i}.example"} for i in range(5)]}
    result = write_grant.split_for_allowance(
        {"max_records_per_chunk": 2}, object_type="companies", spec=spec,
        headroom={"sampled": True, "remaining_sampled": 5})

    assert result["affordable"] == {"record_domains": ["0.example", "1.example", "2.example"]}
    assert "record_ids" not in result["affordable"]
    assert result["remainder"] == {"record_domains": ["3.example", "4.example"]}
    assert "record_ids" not in result["remainder"]


def test_the_membership_test_an_interleaved_batch_projects_the_correct_scope():
    """REVIEW-57-H1, not a count test: work `[domain-create A, id-backed record B]`
    with N=1 must authorise A alone on the affordable side and B alone on the
    remainder side — the exact counterexample the plan names."""
    spec = {"record_ids": ["a.example.com", "12345"], "object_type": "companies"}
    result = write_grant.split_for_allowance(
        {"max_records_per_chunk": 2}, object_type="companies", spec=spec,
        headroom={"sampled": True, "remaining_sampled": 2})

    assert result["record_ceiling_per_run"] == 1
    assert result["affordable_spec"]["record_ids"] == ["a.example.com"]
    assert result["affordable"] == {"record_domains": ["a.example.com"]}
    assert result["remainder_spec"]["record_ids"] == ["12345"]
    assert result["remainder"] == {"record_ids": ["12345"]}


def test_the_membership_test_a_grouped_batch_projects_the_correct_scope():
    """The same interleaved-vs-grouped pair the plan asks for — ids grouped first,
    domains after, so a broken "cut ids then domains" implementation would coincide
    with the correct answer here but not in the interleaved case above."""
    spec = {"record_ids": ["1", "2", "a.example.com", "b.example.com"],
            "object_type": "companies"}
    result = write_grant.split_for_allowance(
        {"max_records_per_chunk": 2}, object_type="companies", spec=spec,
        headroom={"sampled": True, "remaining_sampled": 3})

    assert result["record_ceiling_per_run"] == 2
    assert result["affordable_spec"]["record_ids"] == ["1", "2"]
    assert result["affordable"] == {"record_ids": ["1", "2"]}
    assert result["remainder_spec"]["record_ids"] == ["a.example.com", "b.example.com"]
    assert result["remainder"] == {"record_domains": ["a.example.com", "b.example.com"]}


def test_the_scope_is_a_projection_every_affordable_record_is_backed_and_nothing_extra():
    spec = {"record_ids": ["1", "a.example", "2", "b.example", "3"],
            "object_type": "companies"}
    result = write_grant.split_for_allowance(
        {"max_records_per_chunk": 2}, object_type="companies", spec=spec,
        headroom={"sampled": True, "remaining_sampled": 5})

    affordable_records = result["affordable_spec"]["record_ids"]
    scope_members = (result["affordable"].get("record_ids", [])
                      + result["affordable"].get("record_domains", []))
    assert sorted(scope_members) == sorted(affordable_records)

    remainder_records = result["remainder_spec"]["record_ids"]
    remainder_scope_members = (result["remainder"].get("record_ids", [])
                                + result["remainder"].get("record_domains", []))
    assert sorted(remainder_scope_members) == sorted(remainder_records)


def test_runs_is_the_ceiling_of_total_over_the_affordable_size():
    spec = {"record_ids": [str(i) for i in range(5)], "object_type": "companies"}
    result = write_grant.split_for_allowance(
        {"max_records_per_chunk": 2}, object_type="companies", spec=spec,
        headroom={"sampled": True, "remaining_sampled": 5})
    assert result["record_ceiling_per_run"] == 3
    assert result["runs"] == 2  # ceil(5 / 3)


def test_split_for_allowance_never_carries_a_forbidden_named_key():
    """The authority test, pinning D-57-05."""
    spec = {"record_ids": [str(i) for i in range(5)], "object_type": "companies"}
    result = write_grant.split_for_allowance(
        {"max_records_per_chunk": 2}, object_type="companies", spec=spec,
        headroom={"sampled": True, "remaining_sampled": 5})
    markers = ("arm", "secret", "api_key", "apikey", "token", "credential",
               "password", "grant", "permission", "webhook")
    for key in result:
        assert not any(m in key.lower() for m in markers), key


# =====================================================================================
# plan_grant()'s CEILING_OVER refusal now carries split_offer
# =====================================================================================

def test_plan_grant_refusal_carries_a_split_offer(
        granting_config, stub_module_transport_factory):
    config = {**granting_config, "n8n_monthly_execution_allowance": 5,
              "max_records_per_chunk": 2}
    transport = stub_module_transport_factory(_plan_reads())

    result = _proposal(config, transport, ids=("1", "2", "3", "4", "5"))

    assert result["outcome"] == write_grant.REFUSED
    assert "split_offer" in result
    offer = result["split_offer"]
    assert offer["affordable_spec"] is not None
    assert offer["record_ceiling_per_run"] >= 1
    assert offer["record_ceiling_per_run"] < 5
    assert "queued for a future run" in result["detail"]
    assert "separately authorise" in result["detail"]


def _walk_keys(value):
    if isinstance(value, dict):
        for key, sub in value.items():
            yield key
            yield from _walk_keys(sub)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_keys(item)


def test_the_ceiling_over_refusal_payload_carries_no_forbidden_named_key(
        granting_config, stub_module_transport_factory):
    """The TEN forbidden-name markers (REVIEW-57-L4), scanned recursively over the
    WHOLE refusal payload including the nested `split_offer` — pinning D-57-05 at the
    one surface an operator actually reads."""
    config = {**granting_config, "n8n_monthly_execution_allowance": 5,
              "max_records_per_chunk": 2}
    transport = stub_module_transport_factory(_plan_reads())

    result = _proposal(config, transport, ids=("1", "2", "3", "4", "5"))
    assert result["outcome"] == write_grant.REFUSED

    markers = ("arm", "secret", "api_key", "apikey", "token", "credential",
               "password", "grant", "permission", "webhook")
    for key in _walk_keys(result):
        assert not any(m in str(key).lower() for m in markers), key


def test_a_ceiling_over_refusal_writes_nothing_to_the_remainder_queue(
        granting_config, stub_module_transport_factory, tmp_path, monkeypatch):
    """REVIEW-57-H5, the state-transition test: `plan_grant` is a planning surface and
    must not mutate durable state on a decision the operator has not taken."""
    monkeypatch.setattr(
        durable_paths, "resolve_state_path",
        lambda *a, **k: tmp_path / "dashboard_artifact.json")

    config = {**granting_config, "n8n_monthly_execution_allowance": 1,
              "max_records_per_chunk": 2}
    transport = stub_module_transport_factory(_plan_reads())

    result = _proposal(config, transport, ids=("1", "2", "3"))
    assert result["outcome"] == write_grant.REFUSED

    assert list(tmp_path.glob("remainder_queue*.json")) == []


def test_an_accepted_split_offers_remainder_can_be_saved_with_reason_allowance_split(
        granting_config, stub_module_transport_factory, tmp_path, monkeypatch):
    """`REASON_ALLOWANCE_SPLIT`'s producer is the runbook step AFTER a fresh grant
    opens (see `enrich-records/SKILL.md`) — this proves the shape the offer's
    `remainder_spec` hands to that step is directly usable."""
    monkeypatch.setattr(
        durable_paths, "resolve_state_path",
        lambda *a, **k: tmp_path / "dashboard_artifact.json")

    config = {**granting_config, "n8n_monthly_execution_allowance": 5,
              "max_records_per_chunk": 2}
    transport = stub_module_transport_factory(_plan_reads())

    result = _proposal(config, transport, ids=("1", "2", "3", "4", "5"))
    offer = result["split_offer"]
    assert offer["remainder_spec"] is not None

    entry = remainder_queue.build_entry(
        offer["remainder_spec"], remainder_queue.REASON_ALLOWANCE_SPLIT)
    assert remainder_queue.save("run-accepted-split", [entry]) is True

    saved = remainder_queue.load(
        path=remainder_queue.remainder_path("run-accepted-split"))
    assert saved[0]["reason"] == remainder_queue.REASON_ALLOWANCE_SPLIT


def _over_ceiling_config(granting_config):
    """A config whose sampled remainder cannot possibly cover the batch below —
    `n8n_monthly_execution_allowance: 1` against a 3-record batch (4 projected
    executions at the default 2-per-chunk ceiling)."""
    return {**granting_config, "n8n_monthly_execution_allowance": 1,
            "max_records_per_chunk": 2}


def test_plan_grant_refuses_an_over_ceiling_batch_before_anything_is_armed(
        granting_config, stub_module_transport_factory):
    config = _over_ceiling_config(granting_config)
    transport = stub_module_transport_factory(_plan_reads())

    result = _proposal(config, transport, ids=("1", "2", "3"))

    assert result["outcome"] == write_grant.REFUSED
    assert result["ceiling"]["verdict"] == write_grant.CEILING_OVER
    assert result["ceiling"]["projected_executions"] is not None
    assert result["ceiling"]["remaining_sampled"] is not None
    assert result["ceiling"]["shortfall"] is not None
    assert result["envelope"]["record_count"] == 3
    assert transport.mutating_calls == []


def test_plan_grant_with_override_true_and_a_reason_proceeds_and_records_it(
        granting_config, stub_module_transport_factory):
    config = _over_ceiling_config(granting_config)
    transport = stub_module_transport_factory(_plan_reads())

    result = _proposal(config, transport, ids=("1", "2", "3"))
    assert result["outcome"] == write_grant.REFUSED, "fixture must actually be over-ceiling"

    # The workflow-id cache is process-lifetime — the refusal above already resolved and
    # cached "enrichment", so the override call below must clear it or it would skip its
    # OWN workflow-list read and consume the script one entry out of step.
    executions_client._workflow_id_cache.clear()
    transport = stub_module_transport_factory(_plan_reads())
    proposal = write_grant.plan_grant(
        config, lanes=["enrichment"], object_type="companies",
        record_ids=["1", "2", "3"], record_domains=[], allow_create=False,
        label="over-ceiling, overridden", transport=transport,
        override=True, override_reason="operator accepted the overage on the call")

    assert proposal["kind"] == write_grant.PROPOSAL_KIND
    assert proposal["ceiling"]["overridden"] is True
    assert proposal["ceiling"]["override_reason"] == \
        "operator accepted the overage on the call"
    assert proposal["ceiling"]["override_authority"] == "operator"


def test_plan_grant_override_true_with_no_reason_raises_rather_than_proceeding(
        granting_config, stub_module_transport_factory):
    config = _over_ceiling_config(granting_config)
    transport = stub_module_transport_factory(_plan_reads())

    with pytest.raises(ValueError):
        write_grant.plan_grant(
            config, lanes=["enrichment"], object_type="companies",
            record_ids=["1", "2", "3"], record_domains=[], allow_create=False,
            label="over-ceiling, no reason", transport=transport, override=True)


def test_plan_grant_with_an_unconfigured_allowance_proceeds_as_unknown_not_refused(
        granting_config, stub_module_transport_factory):
    config = {**granting_config, "max_records_per_chunk": 2}
    del config["n8n_monthly_execution_allowance"]
    transport = stub_module_transport_factory(_plan_reads())
    # No allowance key means `allowance_headroom` makes no executions-list read at all
    # (see test_a_config_with_no_allowance_key_degrades_one_line_not_the_whole_open's
    # own note) — this script omits the inserted `_executions_page()` step.
    transport._responses.pop(1)

    proposal = _proposal(config, transport)

    assert proposal["kind"] == write_grant.PROPOSAL_KIND, proposal
    assert proposal["envelope"]["projected_executions"] is not None, (
        "the ceiling must read unknown because the ALLOWANCE is unconfigured, not "
        "because the chunk ceiling is also missing")
    assert proposal["ceiling"]["verdict"] == write_grant.CEILING_UNKNOWN


def test_record_dispatch_outcome_closes_the_grant_from_a_real_dispatch_ceiling_stop(
        granting_config, stub_module_transport_factory, tmp_path, monkeypatch):
    """The producer test (D-57-01, Pitfall 1): `record_send_outcome`'s `ceiling_breach`
    branch REACHED as a consequence of a real `chunking.dispatch_plan()` call, never by
    handing it a hand-built dict.

    57-05 Task 1/3: `enrich-records/SKILL.md`'s dispatch block now closes with a
    `run_report.record_audit` call right after this same `record_dispatch_outcome` —
    driven here for real too, over a `ceiling_stop` a real `dispatch_plan()` produced,
    never a hand-built dict (test_skill_sequence_coverage.py's registry)."""
    import chunking
    import run_report

    monkeypatch.setattr(run_report, "run_audit_path",
                        lambda run_id: tmp_path / f"run_audit-{run_id}.json")

    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport, ids=("1", "2", "3", "4", "5", "6"))

    plan = chunking.plan_chunks(
        {"record_ids": ["1", "2", "3", "4", "5", "6"], "object_type": "companies"}, 2)
    assert plan.chunk_count == 3

    send_transport = stub_module_transport_factory()  # default-accepted for every send
    outcome = chunking.dispatch_plan(
        plan, ["lusha"], True, granting_config, transport=send_transport,
        execution_ceiling=5)   # chunk 0 (1+2=3) + chunk 1 (2+2=4) fit; chunk 2 would be 7

    assert outcome.ceiling_stop is not None
    updated = write_grant.record_dispatch_outcome(grant, outcome, granting_config)

    assert updated["state"] == write_grant.CLOSED
    assert updated["closed_reason"] == write_grant.CLOSED_CEILING_BREACH

    import dataclasses
    run_report.record_audit(
        "test-run", disarm=None,
        ceiling_stop=dataclasses.asdict(outcome.ceiling_stop))
    assert run_report.load_audit("test-run")["ceiling_stop"]["chunk_index"] == \
        outcome.ceiling_stop.chunk_index, (
        "the ceiling-stop observed at run-end must be readable back byte-for-byte — "
        "this is the observation both runbooks persist right after this same "
        "record_dispatch_outcome call"
    )


def test_single_dispatch_outcome_composed_with_record_dispatch_outcome_closes_normally(
        granting_config, stub_module_transport_factory, tmp_path, monkeypatch):
    """A single-shot leg's `ceiling_stop` is unconditionally None — no chunk boundary to
    stop at — so composing it through `record_dispatch_outcome` derives no breach.

    57-05 Task 1/3: both `contact-upload/SKILL.md` and `enrich-before-ingest/SKILL.md`'s
    single-shot ingest legs follow this same `record_dispatch_outcome` with a
    `run_report.record_audit(disarm=...)` call — driven here for real, over the
    `disarm` result an `armed_window` actually produced (test_skill_sequence_coverage.py's
    registry)."""
    import chunking
    import run_report

    monkeypatch.setattr(run_report, "run_audit_path",
                        lambda run_id: tmp_path / f"run_audit-{run_id}.json")

    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport)

    outcome = chunking.single_dispatch_outcome(
        {"body": {}, "run_id": "ingest-run"}, record_count=3)
    updated = write_grant.record_dispatch_outcome(grant, outcome, granting_config)

    assert updated["state"] == write_grant.OPEN

    disarm_result = {"outcome": "disarmed", "workflow_id": "wf-1"}
    run_report.record_audit("ingest-run", disarm=disarm_result)
    assert run_report.load_audit("ingest-run")["disarm"] == disarm_result


def test_record_dispatch_outcome_leaves_the_grant_open_with_no_ceiling_stop(
        granting_config, stub_module_transport_factory):
    import chunking

    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport)

    plan = chunking.plan_chunks({"record_ids": ["1"], "object_type": "companies"}, 2)
    send_transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(plan, ["lusha"], True, granting_config,
                                     transport=send_transport)

    assert outcome.ceiling_stop is None
    updated = write_grant.record_dispatch_outcome(grant, outcome, granting_config)
    assert updated["state"] == write_grant.OPEN


def test_an_explicit_reason_overrides_a_derived_ceiling_breach(
        granting_config, stub_module_transport_factory):
    """REVIEW-57-M7: a crash during a ceiling-stopped dispatch must never be mislabelled
    a budget stop. This is the behaviour that can actually fail today — asserting the
    `CLOSED_UNHANDLED_ERROR` constant merely exists cannot."""
    import chunking

    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport, ids=("1", "2", "3", "4", "5", "6"))

    plan = chunking.plan_chunks(
        {"record_ids": ["1", "2", "3", "4", "5", "6"], "object_type": "companies"}, 2)
    send_transport = stub_module_transport_factory()
    outcome = chunking.dispatch_plan(
        plan, ["lusha"], True, granting_config, transport=send_transport,
        execution_ceiling=5)
    assert outcome.ceiling_stop is not None, "fixture must actually carry a ceiling stop"

    updated = write_grant.record_dispatch_outcome(
        grant, outcome, granting_config, reason=write_grant.CLOSED_UNHANDLED_ERROR)

    assert updated["state"] == write_grant.CLOSED
    assert updated["closed_reason"] == write_grant.CLOSED_UNHANDLED_ERROR, (
        "the explicit reason must win over the outcome's own ceiling_stop")


def test_record_dispatch_outcome_accepts_outcome_none_with_an_explicit_reason(
        granting_config, stub_module_transport_factory):
    """REVIEW-57-M5: an exception raised BEFORE `dispatch_plan()` returns leaves no
    outcome object to inspect. The closure handler must still be able to close the
    grant with its own explicit reason, with no outcome at all, and no
    `AttributeError`/`UnboundLocalError` escaping."""
    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport)

    updated = write_grant.record_dispatch_outcome(
        grant, None, granting_config, reason=write_grant.CLOSED_UNHANDLED_ERROR)

    assert updated["state"] == write_grant.CLOSED
    assert updated["closed_reason"] == write_grant.CLOSED_UNHANDLED_ERROR


# --- the at-the-yes disclosure (D-53-05) --------------------------------------------------

def test_a_two_lane_grant_names_both_lanes_and_points_at_the_written_records_list(
        granting_config, stub_module_transport_factory):
    """RECORDED EDIT -- D-59-07, operator, 2026-08-28; filename wording RECORDED EDIT
    again -- D-59-09, operator, 2026-08-29.

    This pin used to assert D-53-05's pre-emptive warning: that a two-lane grant's
    `consequence` said the HubSpot write is authorized BEFORE the enriched preview
    exists. That sentence is retired as operator-facing text, at the operator's
    decision -- 53-04 called it "the whole of what you got for the protection you
    traded", a warning nobody could act on until after the fact anyway.

    What the pin holds now: the `consequence` states plainly and non-blockingly that
    the grant enables enrichment and writes to HubSpot, and points at the post-run
    written-records list the operator can open in HubSpot and amend. D-59-09 moved that
    artifact from one file shared across runs to one file per run, so the filename
    assertion below changed from a single fixed name (`written_records.json`) to the
    per-run pattern `written_records*.json` -- the disclosure sentence itself also moved
    (see the single-lane twin below), but this test's job is still only the two-lane
    phrasing. The D-53-05 trade itself (one grant spans both lanes, the allowlist stays
    record-scoped) is UNCHANGED -- only what the operator reads in exchange for it
    changed. The negative assertion below is what makes this a re-point rather than a
    weakening: the retired sentence cannot come back unnoticed.
    """
    transport = stub_module_transport_factory(_plan_reads(lanes=2))
    proposal = _proposal(granting_config, transport, lanes=("enrichment", "contacts"))

    consequence = proposal["consequence"]
    # Both lanes NAMED INDIVIDUALLY — never collapsed into a collective phrase.
    assert "enrichment lane" in consequence
    assert "contacts lane" in consequence
    assert write_grant.LANES["enrichment"] in consequence
    assert write_grant.LANES["contacts"] in consequence
    # The plain, non-blocking statement of fact that replaced the retired warning.
    assert "enables enrichment and writes to HubSpot" in consequence
    assert "written_records*.json" in consequence
    # NEGATIVE — the retired pre-emptive warning must never come back, softened or not.
    assert "BEFORE the enriched preview exists" not in consequence


def test_a_single_lane_grant_claims_no_preview_trade_that_is_not_happening(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory(_plan_reads())
    consequence = _proposal(granting_config, transport)["consequence"]

    assert "enrichment lane" in consequence
    assert "contacts" not in consequence
    assert "enriched preview" not in consequence


def test_a_single_lane_grant_also_discloses_the_written_records_artifact(
        granting_config, stub_module_transport_factory):
    """The gap-4 twin (D-59-07/59-VERIFICATION.md): the artifact is written after EVERY
    dispatch regardless of lane count, so a one-lane grant must disclose it exactly like
    a two-lane one does -- before this fix the sentence lived only inside the
    `len(lane_names) > 1` branch (D-59-09 gap-closure, operator, 2026-08-29)."""
    transport = stub_module_transport_factory(_plan_reads())
    consequence = _proposal(granting_config, transport)["consequence"]

    assert "written_records*.json" in consequence
    assert "After the run, the records it actually wrote are listed" in consequence
    # The genuinely multi-lane phrasing must NOT leak into a single-lane grant's text.
    assert "covers both lanes at once" not in consequence


def test_the_consequence_carries_the_arm_dispatch_register_in_full(
        granting_config, stub_module_transport_factory):
    """53-CONTEXT's <specifics>: what turns on, bounded to what, what turns it off, and
    what happens if turning it off fails. All four, or the operator is approving a
    sentence that answers three of their questions."""
    transport = stub_module_transport_factory(_plan_reads())
    consequence = _proposal(granting_config, transport, domains=("known.example",))[
        "consequence"]

    assert "live writes will be enabled" in consequence.lower()      # what turns on
    assert "bounded to exactly" in consequence                       # bounded to what
    assert "OWN armed window" in consequence                         # what turns it off
    assert "disarm fails" in consequence                             # and if that fails
    assert "an admin must check n8n" in consequence


# =========================================================================================
# 53-02 Task 2 — lifetime and revocation: the five ways a grant ends, and the next send
# =========================================================================================

def test_grant_04s_expiry_set_is_exactly_the_five_it_names():
    """Pinned by NAME, not by cardinality: guardrail B adds close reasons of its own
    (Task 3), and a `len(CLOSE_REASONS) == 5` assertion would break on that while proving
    nothing about which five GRANT-04 requires."""
    assert write_grant.GRANT_04_REASONS == {
        write_grant.CLOSED_BATCH_COMPLETE,
        write_grant.CLOSED_CEILING_BREACH,
        write_grant.CLOSED_REVOKED,
        write_grant.CLOSED_SESSION_END,
        write_grant.CLOSED_UNHANDLED_ERROR,
    }
    assert write_grant.GRANT_04_REASONS <= write_grant.CLOSE_REASONS


@pytest.mark.parametrize("reason", sorted({
    "batch_complete", "ceiling_breach", "operator_revocation", "session_end",
    "unhandled_error"}))
def test_a_grant_closed_for_each_reason_carries_that_reason_by_name(
        granting_config, stub_module_transport_factory, reason):
    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport)

    closed = write_grant.close_grant(grant, reason)

    assert closed["state"] == write_grant.CLOSED
    assert closed["closed_reason"] == reason


def test_close_grant_refuses_a_free_text_reason(granting_config,
                                                stub_module_transport_factory):
    """A close reason that can be anything is a close reason nobody can report on."""
    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport)

    with pytest.raises(ValueError) as raised:
        write_grant.close_grant(grant, "the batch sort of finished I think")

    assert "batch_complete" in str(raised.value)
    assert grant["state"] == write_grant.OPEN


def test_check_before_send_refuses_a_closed_grant_and_names_the_closing_reason(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory(_plan_reads())
    grant = write_grant.close_grant(_open(granting_config, transport),
                                    write_grant.CLOSED_SESSION_END)

    refusal = write_grant.check_before_send(
        grant, lane="enrichment", workflow_id=WORKFLOW_ID,
        record_ids=[RECORD_ID], record_domains=[])

    assert refusal["outcome"] == write_grant.REFUSED
    assert write_grant.CLOSED_SESSION_END in refusal["detail"]


def test_check_before_send_names_the_records_a_send_would_have_reached_outside_the_grant(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport)

    refusal = write_grant.check_before_send(
        grant, lane="enrichment", workflow_id=WORKFLOW_ID,
        record_ids=[RECORD_ID, "99999"], record_domains=["outside.example"])

    assert refusal["outcome"] == write_grant.REFUSED
    assert refusal["outside_record_ids"] == ["99999"]
    assert refusal["outside_record_domains"] == ["outside.example"]


def test_check_before_send_passes_a_send_inside_the_grant(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport)

    assert write_grant.check_before_send(
        grant, lane="enrichment", workflow_id=WORKFLOW_ID,
        record_ids=[RECORD_ID], record_domains=[]) is None


# --- GRANT-05: the boundary is the SEND, and a running dispatch finishes ------------------

class _RevokingTransport:
    """A module-shaped transport that revokes the grant partway through a real
    `dispatch_plan`, so the limitation is exercised rather than described."""

    def __init__(self, inner, held, revoke_after_chunk):
        self._inner = inner
        self._held = held
        self._revoke_after = revoke_after_chunk
        self.sent = 0

    def post(self, *args, **kwargs):
        self.sent += 1
        response = self._inner.post(*args, **kwargs)
        if self.sent == self._revoke_after:
            self._held["grant"] = write_grant.revoke(self._held["grant"])
        return response

    def get(self, *args, **kwargs):
        return self._inner.get(*args, **kwargs)


def test_a_revocation_midway_does_not_stop_a_running_dispatch(
        granting_config, stub_module_transport_factory):
    """GRANT-05, as re-scoped by the operator 2026-08-25 — driven through the REAL
    dispatch loop, not two hand calls to `check_before_send`.

    Calling `check_before_send` twice by hand and asserting the second refuses would pass
    while GRANT-05 was entirely unimplemented. What is actually true, and what this pins,
    is that `chunking.dispatch_plan` never consults the grant: every remaining chunk goes,
    and the revoke bites on the NEXT SEND.
    """
    import chunking

    ids = [str(n) for n in range(1, 7)]
    grant_transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, grant_transport, ids=tuple(ids))
    held = {"grant": grant}

    plan = chunking.plan_chunks({"record_ids": ids, "object_type": "companies"}, 2)
    assert plan.chunk_count == 3, "the point of the test is that it is multi-chunk"

    transport = _RevokingTransport(stub_module_transport_factory(), held,
                                   revoke_after_chunk=1)
    outcome = chunking.dispatch_plan(plan, ["lusha"], True, granting_config,
                                     transport=transport)

    # EVERY chunk still went, including the two after the revoke.
    assert transport.sent == 3
    assert [r.ok for r in outcome.results] == [True, True, True]
    assert [[event["objectId"] for event in call["json"]["events"]]
            for call in transport._inner.calls] == [["1", "2"], ["3", "4"], ["5", "6"]]

    # And the revoke bites on the NEXT send.
    assert held["grant"]["state"] == write_grant.CLOSED
    assert held["grant"]["closed_reason"] == write_grant.CLOSED_REVOKED
    refusal = write_grant.check_before_send(
        held["grant"], lane="enrichment", workflow_id=WORKFLOW_ID,
        record_ids=["1"], record_domains=[])
    assert refusal["outcome"] == write_grant.REFUSED
    assert write_grant.CLOSED_REVOKED in refusal["detail"]


def test_a_revoked_run_still_records_every_record_it_wrote(
        granting_config, stub_module_transport_factory, tmp_path, monkeypatch):
    """D-59-07, sibling to the pin directly above (that test's body is left byte-
    identical — see its own docstring). Under D-59-06 a revoked run keeps writing to
    HubSpot until its chunks are exhausted, so the written-records artifact must show
    EVERY chunk the run sent, including the two dispatched AFTER the revoke — a list
    that stopped at the revoke would understate what actually landed, which is exactly
    the case this artifact exists for (the artifact does not know or care about grant
    state at all).

    `written_records.written_records_path` is redirected to a `tmp_path` file rather
    than an explicit `path=` kwarg on `dispatch_plan` — that function only grew a
    keyword-only `run_id`, not a path (59-01-PLAN.md's wiring section), so this is the
    seam `test_written_records.py`'s own crash test uses too.
    """
    import chunking

    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)

    ids = [str(n) for n in range(1, 7)]
    grant_transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, grant_transport, ids=tuple(ids))
    held = {"grant": grant}

    plan = chunking.plan_chunks({"record_ids": ids, "object_type": "companies"}, 2)
    assert plan.chunk_count == 3

    transport = _RevokingTransport(stub_module_transport_factory(), held,
                                   revoke_after_chunk=1)
    chunking.dispatch_plan(plan, ["lusha"], True, granting_config,
                           transport=transport, run_id="revoked-run")

    # The revoke fired, exactly like the pin above proves — and every chunk still ran.
    assert held["grant"]["state"] == write_grant.CLOSED
    entries = written_records.load(path=artifact)
    assert [e["chunk_index"] for e in entries] == [0, 1, 2], (
        "the two chunks dispatched AFTER the revoke must still be on the artifact — a "
        "revoked run keeps writing to HubSpot (D-59-06), so a list that stopped early "
        "would understate what actually landed"
    )


def test_dispatch_plan_has_no_grant_aware_hook_to_revoke_against():
    """The structural reason the boundary is the send. If a `grant` parameter ever appears
    on the dispatch loop, GRANT-05's scope can be tightened — and this test should be the
    thing that notices."""
    import inspect

    import chunking

    assert "grant" not in inspect.signature(chunking.dispatch_plan).parameters


# --- the disarm-failure counter -----------------------------------------------------------

def test_a_verified_disarm_resets_the_consecutive_failure_counter(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport)
    grant["consecutive_disarm_failures"] = 1

    updated = write_grant.record_send_outcome(
        grant, {"disarm": {"outcome": n8n_arming.DISARMED}}, granting_config)

    assert updated["consecutive_disarm_failures"] == 0
    assert updated["state"] == write_grant.OPEN
    assert grant["consecutive_disarm_failures"] == 1, "the input must never be mutated"


def test_one_disarm_failure_increments_the_counter_and_leaves_the_grant_open(
        granting_config, stub_module_transport_factory):
    """D-53-04: one failure fails that send only, so a transient blip cannot abort a long
    run. The bound is on the SECOND."""
    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport)

    updated = write_grant.record_send_outcome(
        grant, {"disarm": {"outcome": n8n_arming.DISARM_FAILED}}, granting_config)

    assert updated["consecutive_disarm_failures"] == 1
    assert updated["state"] == write_grant.OPEN


def test_an_outcome_carrying_no_disarm_verdict_leaves_the_counter_alone(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport)
    grant["consecutive_disarm_failures"] = 1

    updated = write_grant.record_send_outcome(grant, {}, granting_config)

    assert updated["consecutive_disarm_failures"] == 1


def test_a_ceiling_breach_closes_the_grant_rather_than_continuing(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport)

    updated = write_grant.record_send_outcome(
        grant, {"ceiling_breach": True}, granting_config)

    assert updated["state"] == write_grant.CLOSED
    assert updated["closed_reason"] == write_grant.CLOSED_CEILING_BREACH


def test_closing_a_grant_makes_no_network_call_on_the_three_vacuous_paths(
        granting_config, stub_module_transport_factory):
    """GRANT-04's disarm clause is VACUOUS on completion, revocation and session end —
    under per-send windows there is no window open at close time. Guardrail B's two paths
    are the ones where it is not, and they are Task 3's."""
    transport = stub_module_transport_factory(_plan_reads())
    grant = _open(granting_config, transport)
    before = len(transport.calls)

    for reason in (write_grant.CLOSED_BATCH_COMPLETE, write_grant.CLOSED_REVOKED,
                   write_grant.CLOSED_SESSION_END):
        write_grant.close_grant(grant, reason)

    assert len(transport.calls) == before


# =========================================================================================
# Phase 57 Task 4 — the runbook dispatch fences are executable Python, wired for the
# ceiling (REVIEW-57-M4/H6/H7/H8/H9). Verified by AST over the runbooks' REAL code, never
# by grep over prose (REVIEW-57-M-markdown / 57-VALIDATION.md's "caller path the test
# MUST drive" column) — a block that does not parse, or that mentions a name only in a
# comment, must fail these tests rather than satisfy them.
# =========================================================================================

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

_RUNBOOK_PATHS = {
    "enrich-records": SKILLS_DIR / "enrich-records" / "SKILL.md",
    "enrich-before-ingest": SKILLS_DIR / "enrich-before-ingest" / "SKILL.md",
    "contact-upload": SKILLS_DIR / "contact-upload" / "SKILL.md",
}

_PYTHON_FENCE_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)


def _python_blocks(path):
    """Every fenced ```python block in a SKILL.md, dedented and ready to `compile()`."""
    return [textwrap.dedent(b) for b in _PYTHON_FENCE_RE.findall(path.read_text())]


def _called_names(tree):
    """Every function/method name a parsed block CALLS — `foo()` and `mod.foo()` both
    contribute `"foo"` — so a comment mentioning a name can never satisfy a lookup that
    requires it to be called."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                found.add(func.attr)
            elif isinstance(func, ast.Name):
                found.add(func.id)
    return found


def _blocks_calling(path, *call_names):
    """Every fenced python block in `path` whose parsed AST calls EVERY name in
    `call_names` — never a block that merely mentions it in prose or an unrelated
    example (grok-4-6's cycle-2 LOW)."""
    matches = []
    for src in _python_blocks(path):
        tree = ast.parse(src)
        if set(call_names) <= _called_names(tree):
            matches.append((src, tree))
    return matches


@pytest.mark.parametrize("runbook", sorted(_RUNBOOK_PATHS))
def test_every_dispatch_fence_in_the_runbooks_is_valid_python(runbook):
    """REVIEW-57-M4: the angle-bracket placeholders (`<this send's ids>`, `<allow_
    create>`, etc.) were a hard SyntaxError. Every fenced python block must compile —
    an unparseable block would make every AST assertion below unreachable."""
    path = _RUNBOOK_PATHS[runbook]
    blocks = _python_blocks(path)
    assert blocks, f"expected at least one fenced python block in {path}"
    for i, src in enumerate(blocks):
        try:
            compile(src, f"{path.name}:block{i}", "exec")
        except SyntaxError as e:
            pytest.fail(f"{path} block {i} does not parse: {e}")


@pytest.mark.parametrize("runbook", ["enrich-records", "enrich-before-ingest"])
def test_the_dispatch_plan_lane_carries_execution_ceiling(runbook):
    """REVIEW-57-M4/H2: the two `chunking.dispatch_plan` lanes must pass their sampled
    (or self-bound) ceiling straight through, not leave the mid-run tally switched off."""
    matches = _blocks_calling(_RUNBOOK_PATHS[runbook], "dispatch_plan")
    assert matches, f"no block in {runbook}/SKILL.md calls dispatch_plan"
    for src, tree in matches:
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and getattr(n.func, "attr", None) == "dispatch_plan"]
        assert calls
        for call in calls:
            assert any(kw.arg == "execution_ceiling" for kw in call.keywords), (
                f"{runbook}/SKILL.md's dispatch_plan( call carries no execution_ceiling "
                f"keyword"
            )


@pytest.mark.parametrize("runbook", sorted(_RUNBOOK_PATHS))
def test_the_dispatch_close_runs_inside_a_try_finally(runbook):
    """REVIEW-57-H8/M5: grant closure on every exit — normal, ceiling-stopped, or
    crashed — never only on the happy path."""
    path = _RUNBOOK_PATHS[runbook]
    matches = _blocks_calling(path, "record_dispatch_outcome")
    assert matches, f"no block in {path} calls record_dispatch_outcome"
    for src, tree in matches:
        assert any(isinstance(n, ast.Try) and n.finalbody for n in ast.walk(tree)), (
            f"{path} closes a grant outside a try/finally"
        )


@pytest.mark.parametrize("runbook", ["enrich-before-ingest", "contact-upload"])
def test_the_single_shot_dispatch_is_guarded_and_expressed_in_one_vocabulary(runbook):
    """REVIEW-57-H7: the FOURTH dispatch path — `dispatch.dispatch` — has no chunk
    boundary to stop mid-run at, so it must be checked PRE-CALL, inside an `If`, and its
    spend expressed through `single_dispatch_outcome` — never a second spend
    vocabulary."""
    path = _RUNBOOK_PATHS[runbook]
    matches = _blocks_calling(path, "dispatch", "single_dispatch_outcome")
    assert matches, f"no block in {path} calls both dispatch.dispatch and single_dispatch_outcome"

    def _dispatch_dispatch_calls(node):
        return [n for n in ast.walk(node) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == "dispatch"
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "dispatch"]

    for src, tree in matches:
        guarded = False
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                dispatch_calls = _dispatch_dispatch_calls(node)
                single_calls = [
                    n for n in ast.walk(node) if isinstance(n, ast.Call)
                    and getattr(n.func, "attr", None) == "single_dispatch_outcome"]
                if dispatch_calls and single_calls:
                    guarded = True
        assert guarded, (
            f"{path}'s dispatch.dispatch( call must be enclosed by an If guarding it "
            f"against a remaining ceiling, and followed by single_dispatch_outcome "
            f"inside the same branch"
        )


@pytest.mark.parametrize("runbook", sorted(_RUNBOOK_PATHS))
def test_override_never_appears_literally_in_a_runbook(runbook):
    """REVIEW-57-M6: an override comes only from the operator's own answer in this
    conversation — never from a runbook's own source, a stored grant, or a config
    value. `# planner-discipline-allow: override=True` in 57-01-PLAN.md's own
    acceptance criteria names this literal deliberately; it must appear in NEITHER
    runbook."""
    path = _RUNBOOK_PATHS[runbook]
    assert "override=True" not in path.read_text()


@pytest.mark.parametrize("runbook", sorted(_RUNBOOK_PATHS))
def test_the_unknown_ceiling_branch_self_bounds_rather_than_going_unbounded(runbook):
    """REVIEW-57-H6: an unconfigured/unsampleable allowance must not switch off the
    mid-run tally too — the double-off hole. The CEILING_UNKNOWN branch's value
    expression must never be the `None` literal."""
    path = _RUNBOOK_PATHS[runbook]
    found = False
    for src in _python_blocks(path):
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                test = node.test
                if (isinstance(test, ast.Compare) and len(test.comparators) == 1
                        and isinstance(test.comparators[0], ast.Attribute)
                        and test.comparators[0].attr == "CEILING_UNKNOWN"):
                    found = True
                    assign = node.body[0]
                    assert isinstance(assign, ast.Assign), (
                        f"{path}'s CEILING_UNKNOWN branch's first statement is not a "
                        f"plain assignment"
                    )
                    is_none_literal = (
                        isinstance(assign.value, ast.Constant)
                        and assign.value.value is None
                    )
                    assert not is_none_literal, (
                        f"{path}'s CEILING_UNKNOWN branch assigns None — the "
                        f"self-bound ceiling must be the envelope's own "
                        f"projected_executions, never left unbounded"
                    )
    assert found, f"{path} has no branch comparing to write_grant.CEILING_UNKNOWN"


# =========================================================================================
# Phase 57 Task 3 — the handoff 57-01 Task 4 left for this plan, taken: the single-shot
# `dispatch.dispatch` legs' pre-call ceiling-breach branch must call
# `remainder_queue.save(...)` with a `REASON_CEILING_BREACH` entry, real code on the
# parsed tree — not the prose 57-01 left there (a `grep` for the module name would pass
# against prose too; this must not).
# =========================================================================================

def _is_would_be_ceiling_branch(node):
    """The `If` node guarding the pre-call ceiling check in both runbooks — the test
    always compares a `would_be` name against a ceiling, but the ceiling's own name
    differs between the two files (`remaining_execution_ceiling` vs
    `execution_ceiling`), so only `would_be` is required to identify it."""
    if not isinstance(node, ast.If):
        return False
    names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
    return "would_be" in names


@pytest.mark.parametrize("runbook", ["enrich-before-ingest", "contact-upload"])
def test_the_single_shot_ceiling_breach_writes_the_remainder_queue(runbook):
    path = _RUNBOOK_PATHS[runbook]
    matches = _blocks_calling(path, "dispatch", "single_dispatch_outcome")
    assert matches, f"no block in {path} calls both dispatch.dispatch and single_dispatch_outcome"

    for src, tree in matches:
        branch = next((n for n in ast.walk(tree) if _is_would_be_ceiling_branch(n)), None)
        assert branch is not None, f"{path} has no pre-call ceiling-breach If branch"

        save_calls = [
            n for n in ast.walk(branch) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute) and n.func.attr == "save"
            and isinstance(n.func.value, ast.Name) and n.func.value.id == "remainder_queue"
        ]
        assert save_calls, (
            f"{path}'s pre-call ceiling-breach branch has no remainder_queue.save(...) "
            f"call — this is the handoff 57-01 Task 4 left for 57-03 to wire; prose "
            f"here satisfies nothing"
        )
        assert any(
            isinstance(n, ast.Attribute) and n.attr == "REASON_CEILING_BREACH"
            for n in ast.walk(branch)
        ), f"{path}'s ceiling-breach branch never references REASON_CEILING_BREACH"


@pytest.mark.parametrize("runbook", ["enrich-before-ingest", "contact-upload"])
def test_the_single_shot_ceiling_breachs_remainder_save_never_raises_into_the_branch(
        runbook):
    """The same degrade-rather-than-halt rule the chunked `dispatch_plan` path follows
    (D-59-10): a `remainder_queue.RemainderQueueError` must be caught inside the
    breach branch, never left to propagate out of the runbook step."""
    path = _RUNBOOK_PATHS[runbook]
    matches = _blocks_calling(path, "dispatch", "single_dispatch_outcome")
    for src, tree in matches:
        branch = next((n for n in ast.walk(tree) if _is_would_be_ceiling_branch(n)), None)
        assert branch is not None
        excepts = [
            h for n in ast.walk(branch) if isinstance(n, ast.Try) for h in n.handlers
        ]
        assert any(
            isinstance(h.type, ast.Attribute) and h.type.attr == "RemainderQueueError"
            for h in excepts
        ), f"{path}'s ceiling-breach branch has no except remainder_queue.RemainderQueueError"


# =========================================================================================
# 57-05 Task 3 — both lane runbooks end by reading `run_report.build_run_report`, and
# record their audit facts as they observe them (`record_audit`), one call before the
# dispatch and one inside the `finally` — real code on the parsed tree, per
# `57-VALIDATION.md`'s "caller path the test MUST drive" column, never a markdown
# string search.
# =========================================================================================

def _nodes_inside_any_finally(tree):
    """Every node reachable from any `Try` node's `finalbody`, across the whole tree —
    used to tell a call made BEFORE a dispatch's try/finally from one made INSIDE its
    `finally:` clause, on the real parsed structure rather than by line position."""
    seen = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for stmt in node.finalbody:
                for sub in ast.walk(stmt):
                    seen.add(id(sub))
    return seen


def _calls_named(tree, name):
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and getattr(n.func, "attr", None) == name]


@pytest.mark.parametrize("runbook", ["enrich-records", "enrich-before-ingest"])
def test_build_run_report_is_called_with_an_outcomes_keyword(runbook):
    path = _RUNBOOK_PATHS[runbook]
    matches = _blocks_calling(path, "build_run_report")
    assert matches, f"no block in {path} calls build_run_report"
    for src, tree in matches:
        calls = _calls_named(tree, "build_run_report")
        assert calls
        for call in calls:
            assert any(kw.arg == "outcomes" for kw in call.keywords), (
                f"{path}'s build_run_report( call carries no outcomes keyword"
            )


@pytest.mark.parametrize("runbook", ["enrich-records", "enrich-before-ingest"])
def test_a_record_audit_call_exists_before_the_dispatch(runbook):
    path = _RUNBOOK_PATHS[runbook]
    matches = _blocks_calling(path, "record_audit")
    assert matches, f"no block in {path} calls record_audit"
    found = False
    for src, tree in matches:
        in_finally = _nodes_inside_any_finally(tree)
        calls = _calls_named(tree, "record_audit")
        if any(id(c) not in in_finally for c in calls):
            found = True
    assert found, (
        f"no block in {path} calls record_audit outside a finally clause — the "
        f"ceiling/balances observation must be recorded before dispatch, not only at "
        f"the end"
    )


@pytest.mark.parametrize("runbook", ["enrich-records", "enrich-before-ingest"])
def test_a_record_audit_call_exists_inside_the_finally(runbook):
    path = _RUNBOOK_PATHS[runbook]
    matches = _blocks_calling(path, "record_audit")
    assert matches, f"no block in {path} calls record_audit"
    found = False
    for src, tree in matches:
        in_finally = _nodes_inside_any_finally(tree)
        calls = _calls_named(tree, "record_audit")
        if any(id(c) in in_finally for c in calls):
            found = True
    assert found, (
        f"no block in {path} calls record_audit inside a finally clause — the disarm "
        f"result must be recorded on every exit, not only the happy path"
    )


def test_calls_named_finds_no_call_in_a_block_that_only_mentions_the_name_in_a_comment():
    """A block that merely MENTIONS a name in a comment (never calling it) must satisfy
    nothing — `_calls_named`/`_blocks_calling` find parsed CALL nodes only, never a
    comment or a docstring, which is what makes prose insufficient to pass the tests
    above (57-VALIDATION.md's "caller path the test MUST drive" column)."""
    src = "# record_audit and build_run_report happen somewhere, trust me\nx = 1\n"
    tree = ast.parse(src)
    assert not _calls_named(tree, "record_audit")
    assert not _calls_named(tree, "build_run_report")
