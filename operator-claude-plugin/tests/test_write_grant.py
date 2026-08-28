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
import control_actions
import executions_client
import n8n_arming
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


def _plan_reads(lanes=1, balances=None, guardrail=None):
    """Everything ONE `plan_grant` consumes, in `plan_grant`'s frozen call order:

        one /api/v1/workflows read per lane   (id resolution)
        one status POST                       (balances — only when a provider is priced)
        one workflow read per lane            (GUARDRAIL A's live write-safety read)

    The guardrail reads default to DISARMED bodies, because a scripted transport that runs
    out answers `{}` — which guardrail A correctly treats as unreadable and refuses on.
    """
    reads = [_workflow_list()] * lanes
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
    # Id resolution, then GUARDRAIL A's live write-safety read. Reads only.
    assert transport.verbs == ["get", "get"]


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
    transport = stub_module_transport_factory(_priced_plan_reads())

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


def test_the_block_says_the_ceiling_discloses_rather_than_constrains(
        priced_config, stub_module_transport_factory):
    """D-53-02, in the operator's own register and not only in a docstring. A number
    labelled ceiling that cannot refuse anything must say so where it is read."""
    transport = stub_module_transport_factory(_priced_plan_reads())
    block = _priced_proposal(priced_config, transport)["envelope"]["block"]

    assert "they do not prevent it" in block
    assert "name a smaller batch" in block.lower()


def test_the_block_states_the_remaining_allowance_gap(
        priced_config, stub_module_transport_factory):
    """An operator reading a share-of-allowance figure will otherwise assume it accounts
    for what the schedulers have already spent this month. It does not."""
    transport = stub_module_transport_factory(_priced_plan_reads())
    figures = _priced_proposal(priced_config, transport)["envelope"]

    assert figures["remaining_allowance_sampled"] is False
    assert "not against what is left of it this month" in figures["block"]


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

    # One id-resolution read and one guardrail-A read. No POST: no provider, no balance.
    assert transport.verbs == ["get", "get"]
    assert figures["provider_credits"] == {}
    assert "No provider credits: **0**" in figures["block"]


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
