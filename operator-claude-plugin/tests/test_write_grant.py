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
    # 53-02 filled the envelope (GRANT-02); the two below stay initialised-and-unwritten
    # until a close or a send outcome writes them.
    assert grant["envelope"]["record_count"] == 2
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
    transport = stub_module_transport_factory([_workflow_list()])

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
    transport = stub_module_transport_factory([_workflow_list()])

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
        _proposal(secrets, stub_module_transport_factory([_workflow_list()])),
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
    transport = stub_module_transport_factory([_workflow_list()])
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
    transport = stub_module_transport_factory([_workflow_list()])
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
    transport = stub_module_transport_factory([_workflow_list()])
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
    """The frozen call order a priced `plan_grant` consumes: one workflow-collection read
    per lane, then ONE status POST for balances."""
    return [_workflow_list()] * lanes + [balances if balances is not None else _balances()]


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
    transport = stub_module_transport_factory([_workflow_list()])
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
    transport = stub_module_transport_factory([_workflow_list()])
    figures = _proposal(granting_config, transport)["envelope"]

    assert transport.verbs == ["get"]
    assert figures["provider_credits"] == {}
    assert "No provider credits: **0**" in figures["block"]


# --- the at-the-yes disclosure (D-53-05) --------------------------------------------------

def test_a_two_lane_grant_names_both_lanes_and_states_the_preview_trade(
        granting_config, stub_module_transport_factory):
    """D-53-05's traded protection, pinned by a test rather than by prose. This is the ONE
    rendering the operator reads AT THE YES — the skill contract pins SKILL.md and the
    53-04 checkpoint pins the human walk, but neither pins this sentence."""
    transport = stub_module_transport_factory([_workflow_list(), _workflow_list()])
    proposal = _proposal(granting_config, transport, lanes=("enrichment", "contacts"))

    consequence = proposal["consequence"]
    # Both lanes NAMED INDIVIDUALLY — never collapsed into a collective phrase.
    assert "enrichment lane" in consequence
    assert "contacts lane" in consequence
    assert write_grant.LANES["enrichment"] in consequence
    assert write_grant.LANES["contacts"] in consequence
    # And the sentence the ordering protection was traded FOR.
    assert "BEFORE the enriched preview exists" in consequence


def test_a_single_lane_grant_claims_no_preview_trade_that_is_not_happening(
        granting_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([_workflow_list()])
    consequence = _proposal(granting_config, transport)["consequence"]

    assert "enrichment lane" in consequence
    assert "contacts" not in consequence
    assert "enriched preview" not in consequence


def test_the_consequence_carries_the_arm_dispatch_register_in_full(
        granting_config, stub_module_transport_factory):
    """53-CONTEXT's <specifics>: what turns on, bounded to what, what turns it off, and
    what happens if turning it off fails. All four, or the operator is approving a
    sentence that answers three of their questions."""
    transport = stub_module_transport_factory([_workflow_list()])
    consequence = _proposal(granting_config, transport, domains=("known.example",))[
        "consequence"]

    assert "live writes will be enabled" in consequence.lower()      # what turns on
    assert "bounded to exactly" in consequence                       # bounded to what
    assert "OWN armed window" in consequence                         # what turns it off
    assert "disarm fails" in consequence                             # and if that fails
    assert "an admin must check n8n" in consequence
