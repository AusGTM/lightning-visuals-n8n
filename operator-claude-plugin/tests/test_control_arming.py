"""28-03 Task 2 — the arm -> dispatch -> disarm lifecycle.

The property under test throughout: a failed arm must never look dispatchable, and a
failed DISARM must never look finished. Everything else here serves those two.
"""
import json
import re
from pathlib import Path

import pytest

import n8n_arming
import n8n_control

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ID = "wf-test-1"


def _base_workflow(record_writes='"false"', create='"false"', ids='""', domains='""'):
    """A miniature two-gate workflow shaped like the real ones — declarations inside
    jsCode, plus a node with no code at all."""
    gate = (f"const ALLOW_HUBSPOT_RECORD_WRITES = {record_writes};\n"
            f"const ALLOW_HUBSPOT_CREATE = {create};\n"
            f"const TEST_RECORD_IDS = {ids};\n"
            f"const TEST_RECORD_DOMAINS = {domains};\n"
            "function _writeSafetyAllows() { return false; }\n")
    return {
        "id": WORKFLOW_ID,
        "name": "LV Contact Ingest (Cloud template)",
        "active": True,
        "settings": {},
        "connections": {},
        "nodes": [
            {"name": "Update Write Gate", "parameters": {"jsCode": gate}},
            {"name": "Create Write Gate", "parameters": {"jsCode": gate}},
            {"name": "Webhook", "parameters": {}},
        ],
    }


def _armed_workflow(ids='"12345"'):
    return _base_workflow(record_writes='"true"', create='"true"', ids=ids)


@pytest.fixture
def armed_env(monkeypatch):
    monkeypatch.setenv(n8n_arming.ARM_ENV_VAR, "true")


@pytest.fixture(autouse=True)
def _clean_arm_env(monkeypatch):
    monkeypatch.delenv(n8n_arming.ARM_ENV_VAR, raising=False)


def _arm(config, transport, ids=("12345",), domains=(), allow_create=False):
    return n8n_arming.arm_for_dispatch(WORKFLOW_ID, list(ids), list(domains), allow_create,
                                       config, transport=transport)


# --- the env kill switch ---------------------------------------------------------------

def test_with_the_gate_unset_the_arm_refuses_and_makes_no_call_at_all(
        fake_config, stub_module_transport_factory):
    """Not merely no MUTATING call — no call. The gate precedes transport construction, so
    a missing gate costs zero HTTP."""
    transport = stub_module_transport_factory([_base_workflow()])

    result = _arm(fake_config, transport)

    assert result["outcome"] == n8n_arming.REFUSED
    assert n8n_arming.ARM_ENV_VAR in result["detail"]
    assert transport.calls == []


@pytest.mark.parametrize("near_miss", ["", "1", "yes", "TRUE", "True", "true "])
def test_every_near_miss_value_refuses(near_miss, monkeypatch, fake_config,
                                       stub_module_transport_factory):
    """Semantics must match ALLOW_N8N_PROBE (28-02) exactly. A divergence between the two
    gates is itself the defect."""
    monkeypatch.setenv(n8n_arming.ARM_ENV_VAR, near_miss)
    transport = stub_module_transport_factory([_base_workflow()])

    result = _arm(fake_config, transport)

    assert result["outcome"] == n8n_arming.REFUSED
    assert transport.calls == []


def test_the_probe_and_the_arm_gates_HEADLESS_branch_use_the_same_comparison():
    """Re-pointed once, deliberately, on 2026-08-25 (53-01, D-53-01). Do not sweep this
    file; this is the only test here that moved.

    This test used to be called `test_the_probe_and_the_arm_gate_use_the_same_comparison`
    and claimed the arm gate AS A WHOLE was coupled to `ALLOW_N8N_PROBE`'s comparison. Its
    assertion still passes after 53-01 — the environment branch still compares against the
    exact string "true" — but its CLAIM had become false, and a test whose assertion passes
    while its claim is false is worse than a failing one: it reads as evidence for
    something nobody checked. So the name and the reason moved with the code.

    THE GATE SPLIT IS NOW THREE-WAY:

      1. The probe gate (`ALLOW_N8N_PROBE`) and the deploy gate (`ALLOW_N8N_DEPLOY`) stay
         environment-gated, unchanged.
      2. The arm gate's HEADLESS branch — no grant, which is `scheduled_arm.py` and every
         pre-53 caller — stays environment-gated on `ALLOW_N8N_ARM`, unchanged, and is what
         this test pins against the probe.
      3. The arm gate's INTERACTIVE branch — a grant present — moved to an admin-set key in
         operator.local.json, compared by IDENTITY against the JSON boolean `true` in
         `config_gate.write_grants_enabled`, which is the single definition of that
         comparison.

    Why (3) had to move: `_arm_gate()` required `ALLOW_N8N_ARM=true` in the session's SHELL
    environment, and an operator in Claude Desktop cannot set a shell variable — so the
    documented operator path ended in a refusal only an admin with terminal access could
    clear (G-2, live client UAT 2026-08-25). This is the repository's first deliberate
    exception to D-34's "authority gates are environment variables compared against the
    exact string true". A reader who changes one of the three gates must NOT assume the
    others followed.
    """
    arming_src = Path(n8n_arming.__file__).read_text()
    probe_src = (Path(n8n_arming.__file__).parent / "probe_n8n_semantics.py").read_text()
    assert re.search(r'!=\s*"true"', arming_src)
    assert re.search(r'!=\s*"true"', probe_src)

    # (3): the interactive branch's own comparison, pinned where it actually lives — in
    # config_gate, not here. Identity against the JSON boolean, never truthiness: `bool` is
    # an `int` subclass, so a truthiness test would accept 1, 1.0 and the string "true" as
    # authority and be silently weaker than the exact-string gate it replaces.
    config_gate_src = (Path(n8n_arming.__file__).parent / "config_gate.py").read_text()
    assert re.search(r"WRITE_GRANT_SETTINGS_KEY\)\s+is\s+True", config_gate_src)


def test_the_disarm_is_NOT_gated_on_the_kill_switch(fake_config,
                                                    stub_module_transport_factory):
    """A kill switch that blocked disarming would strand an armed backend — the exact
    failure this phase's ceremony exists to prevent."""
    transport = stub_module_transport_factory([
        _armed_workflow(), _armed_workflow(), {}, {}, {}, _base_workflow(),
    ])

    result = n8n_arming.disarm(WORKFLOW_ID, fake_config, transport=transport)

    assert result["outcome"] == n8n_arming.DISARMED
    assert transport.mutating_calls, "the disarm must actually have tried"


# --- the record allowlist ---------------------------------------------------------------

def test_an_empty_allowlist_refuses_and_mutates_nothing(armed_env, fake_config,
                                                        stub_module_transport_factory):
    """The deployed _writeSafetyAllows() denies everything on an empty allowlist, so
    arming the flag alone would report success while granting nothing."""
    transport = stub_module_transport_factory([_base_workflow()])

    result = _arm(fake_config, transport, ids=(), domains=())

    assert result["outcome"] == n8n_arming.REFUSED
    assert "empty" in result["detail"]
    assert transport.mutating_calls == []


def test_whitespace_only_entries_do_not_count_as_an_allowlist(armed_env, fake_config,
                                                              stub_module_transport_factory):
    transport = stub_module_transport_factory([_base_workflow()])

    result = _arm(fake_config, transport, ids=("", "   "), domains=())

    assert result["outcome"] == n8n_arming.REFUSED
    assert transport.mutating_calls == []


def test_a_successful_arm_is_bounded_to_exactly_the_dispatched_records(
        armed_env, fake_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([
        _base_workflow(),                                     # arm_for_dispatch's own read
        _base_workflow(),                                     # apply_mutation's fresh re-read
        {}, {}, {},                                           # deactivate, put, activate
        _base_workflow(record_writes='"true"', ids='"12345,67890"'),   # verification read
    ])

    result = n8n_arming.arm_for_dispatch(WORKFLOW_ID, ["12345", "67890"], [], False,
                                         fake_config, transport=transport)

    assert result["outcome"] == n8n_arming.ARMED
    assert result["record_ids"] == ["12345", "67890"]
    assert "cannot write a record outside that list" in result["consequence"]
    assert result["prior"]["ALLOW_HUBSPOT_RECORD_WRITES"] == "false"


# --- partial success is failure ---------------------------------------------------------

def test_an_arm_whose_readback_shows_a_node_still_disabled_is_failed(
        armed_env, fake_config, stub_module_transport_factory):
    """Declaring nodes disagreeing means a partial rewrite landed. The caller must not
    dispatch on it."""
    half_armed = _base_workflow(record_writes='"true"', ids='"12345"')
    half_armed["nodes"][1]["parameters"]["jsCode"] = \
        half_armed["nodes"][1]["parameters"]["jsCode"].replace(
            'const ALLOW_HUBSPOT_RECORD_WRITES = "true";',
            'const ALLOW_HUBSPOT_RECORD_WRITES = "false";')

    transport = stub_module_transport_factory([
        _base_workflow(), _base_workflow(), {}, {}, {}, half_armed,
    ])

    result = _arm(fake_config, transport)

    assert result["outcome"] == "failed"
    assert "DO NOT DISPATCH" in result["operator_note"]


# --- the loud disarm failure -------------------------------------------------------------

def test_a_disarm_whose_readback_still_reads_enabled_is_its_own_outcome(
        fake_config, stub_module_transport_factory):
    """Not a generic failure a caller might log and move past (D-03)."""
    transport = stub_module_transport_factory([
        _armed_workflow(), _armed_workflow(), {}, {}, {},
        _armed_workflow(),          # still armed after the disarm
    ])

    result = n8n_arming.disarm(WORKFLOW_ID, fake_config, transport=transport)

    assert result["outcome"] == n8n_arming.DISARM_FAILED
    assert "LV Contact Ingest (Cloud template)" in result["detail"]
    assert "true" in json.dumps(result["observed"])
    assert "LIVE WRITES MAY STILL BE ENABLED" in result["detail"]


def test_no_code_path_returns_a_successful_looking_result_for_a_failed_disarm():
    source = Path(n8n_arming.__file__).read_text()
    disarm_body = source.split("def disarm(", 1)[1].split("\nclass ", 1)[0]
    assert disarm_body.count('"outcome": DISARMED') == 1, (
        "exactly one success return in disarm — a second is how a failure gets folded "
        "into a success"
    )


# --- Phase 60, MEDIUM-2/LOW-5: targets and allowlist derived from what's actually declared -

def _review_only_workflow(review_writes='"false"', ids='""', domains='""'):
    """A gate node declaring ONLY the review write-safety constant (and its shared
    allowlist) — no dispatch constant at all. This is the shape MEDIUM-2 exists to prove
    `disarm` handles: BEFORE the fix, `disarm`'s node allowlist was always
    `_declaring_nodes(original)` (the DISPATCH_FLAGS default), so a node like this one would
    fall outside that allowlist and `apply_mutation`'s own allowlist assertion would refuse
    the very rewrite disarm needed to make."""
    gate = (f"const ALLOW_HUBSPOT_REVIEW_WRITES = {review_writes};\n"
            f"const TEST_RECORD_IDS = {ids};\n"
            f"const TEST_RECORD_DOMAINS = {domains};\n"
            "function _writeSafetyAllows() { return false; }\n")
    return {
        "id": WORKFLOW_ID,
        "name": "LV Review Decision (Cloud)",
        "active": True,
        "settings": {},
        "connections": {},
        "nodes": [{"name": "Review Gate", "parameters": {"jsCode": gate}}],
    }


def test_disarm_rewrites_a_node_declaring_only_the_review_constant(
        fake_config, stub_module_transport_factory):
    """MEDIUM-2 (cross-AI review, 2026-09-01): a fixture workflow whose gate node declares
    ONLY the review write-safety constant has that declaration rewritten by `disarm` rather
    than refused — proving the node allowlist and the mutation targets were derived from
    the SAME flag list (both from what the fetched workflow actually declares, via
    `n8n_read.read_write_safety` over `OVERLAYABLE_FLAGS`). With the allowlist reverted to
    `_declaring_nodes(original)`'s old DISPATCH_FLAGS default, this node would sit outside
    the allowed-node set and `apply_mutation` would refuse before any PUT — which is the
    failure this test exists to catch."""
    transport = stub_module_transport_factory([
        _review_only_workflow(review_writes='"true"', ids='"12345"'),
        _review_only_workflow(review_writes='"true"', ids='"12345"'),
        {}, {}, {},
        _review_only_workflow(),
    ])

    result = n8n_arming.disarm(WORKFLOW_ID, fake_config, transport=transport)

    assert result["outcome"] == n8n_arming.DISARMED
    assert transport.mutating_calls, "the disarm must actually have rewritten the node"


def test_disarm_refuses_before_mutating_when_the_pre_read_is_unreadable(
        fake_config, stub_module_transport_factory):
    """LOW-5 (cross-AI review, 2026-09-01): when `disarm`'s own pre-read cannot be parsed as
    a workflow, it returns DISARM_FAILED IMMEDIATELY, before any mutation is attempted —
    never falling back to a guessed flag list and reporting a clean verdict over state
    nobody actually read. The detail names the review write constant as UNVERIFIED, and no
    mutating request reaches the recorded call log."""
    transport = stub_module_transport_factory([(500, {})])   # non-2xx -> get_workflow: None

    result = n8n_arming.disarm(WORKFLOW_ID, fake_config, transport=transport)

    assert result["outcome"] == n8n_arming.DISARM_FAILED
    assert "ALLOW_HUBSPOT_REVIEW_WRITES" in result["detail"]
    assert "UNVERIFIED" in result["detail"]
    assert transport.mutating_calls == []


# --- the armed window --------------------------------------------------------------------

def test_a_raise_inside_the_window_still_attempts_the_disarm(
        armed_env, fake_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([
        _base_workflow(), _base_workflow(), {}, {}, {},
        _base_workflow(record_writes='"true"', ids='"12345"'),
        _armed_workflow(), _armed_workflow(), {}, {}, {}, _base_workflow(),   # the disarm
    ])

    with pytest.raises(RuntimeError, match="dispatch blew up"):
        with n8n_arming.armed_window(WORKFLOW_ID, ["12345"], [], False, fake_config,
                                     transport=transport) as window:
            raise RuntimeError("dispatch blew up")

    assert window.disarm_result["outcome"] == n8n_arming.DISARMED


def test_when_the_body_raises_AND_the_disarm_fails_both_are_visible(
        armed_env, fake_config, stub_module_transport_factory):
    """The disarm failure is the one that leaves state behind on a real backend, so it
    must not be buried under the body's traceback."""
    transport = stub_module_transport_factory([
        _base_workflow(), _base_workflow(), {}, {}, {},
        _base_workflow(record_writes='"true"', ids='"12345"'),
        _armed_workflow(), _armed_workflow(), {}, {}, {}, _armed_workflow(),  # disarm fails
    ])

    with pytest.raises(n8n_arming.DisarmFailed) as excinfo:
        with n8n_arming.armed_window(WORKFLOW_ID, ["12345"], [], False, fake_config,
                                     transport=transport):
            raise RuntimeError("dispatch blew up")

    assert excinfo.value.outcome["outcome"] == n8n_arming.DISARM_FAILED
    assert isinstance(excinfo.value.__cause__, RuntimeError)
    assert "dispatch blew up" in str(excinfo.value.__cause__)


def test_a_clean_body_with_a_failing_disarm_still_raises(
        armed_env, fake_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([
        _base_workflow(), _base_workflow(), {}, {}, {},
        _base_workflow(record_writes='"true"', ids='"12345"'),
        _armed_workflow(), _armed_workflow(), {}, {}, {}, _armed_workflow(),
    ])

    with pytest.raises(n8n_arming.DisarmFailed):
        with n8n_arming.armed_window(WORKFLOW_ID, ["12345"], [], False, fake_config,
                                     transport=transport):
            pass


# --- the field-level guard ----------------------------------------------------------------

def test_a_change_outside_the_declaration_lines_raises_before_any_network_call():
    """Node-level allowlisting alone would permit rewriting a whole gate's body."""
    original = _base_workflow()
    modified = json.loads(json.dumps(original))
    node = modified["nodes"][0]
    node["parameters"]["jsCode"] = node["parameters"]["jsCode"].replace(
        "function _writeSafetyAllows() { return false; }",
        "function _writeSafetyAllows() { return true; }")

    with pytest.raises(n8n_arming.ArmingRefused, match="outside its write-safety"):
        n8n_arming._assert_only_declaration_lines_changed(
            original, modified, ["Update Write Gate", "Create Write Gate"])


def test_the_declaration_lines_themselves_may_change():
    original = _base_workflow()
    modified, _ = n8n_arming.set_write_safety(
        original, {"ALLOW_HUBSPOT_RECORD_WRITES": True, "TEST_RECORD_IDS": "12345"})

    n8n_arming._assert_only_declaration_lines_changed(
        original, modified, ["Update Write Gate", "Create Write Gate"])


def test_the_declaring_node_set_is_discovered_not_hardcoded():
    """The declaring set moves — 23-01 added one, 30-01 added a constant to eight nodes,
    30-02 added a whole workflow. A hardcoded list silently narrows the guard."""
    workflow = _base_workflow()
    assert n8n_arming._declaring_nodes(workflow) == ["Create Write Gate", "Update Write Gate"]

    workflow["nodes"].append(
        {"name": "Third Gate",
         "parameters": {"jsCode": 'const ALLOW_HUBSPOT_CREATE = "false";'}})
    assert "Third Gate" in n8n_arming._declaring_nodes(workflow)

    source = Path(n8n_arming.__file__).read_text()
    assert "Write Gate\"" not in source, "a node name has been hardcoded into the module"


def test_review_writes_is_not_touched_by_a_dispatch_disarm():
    """30-01's D-02/D-08e: review writeback is a SEPARATE authority. Disarming the dispatch
    path must not silently revoke it, nor arming grant it."""
    assert "ALLOW_HUBSPOT_REVIEW_WRITES" not in n8n_arming.DISPATCH_FLAGS
    assert "ALLOW_HUBSPOT_REVIEW_WRITES" in n8n_arming.OVERLAYABLE_FLAGS
