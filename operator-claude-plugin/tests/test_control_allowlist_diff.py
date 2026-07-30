"""Task 2 — the PUT half: the four-key body filter, the structural allowlist diff, and the
prior-active-restoring bracket.

`PUT /api/v1/workflows/{id}` replaces `nodes`/`connections`/`settings` wholesale, so
anything that drifts between the fetch and the PUT lands in production. The diff below is
what makes an out-of-allowlist change impossible rather than merely unattempted (D-15,
D-19) — and it runs BEFORE the deactivate, because a refusal that has already deactivated
a live workflow is a failed mutation dressed as a refusal.
"""
import copy

import pytest

import n8n_control

ALLOWED = {"Decide Action"}
FLAG_OFF = 'const ALLOW_HUBSPOT_RECORD_WRITES = "false";'
FLAG_ON = 'const ALLOW_HUBSPOT_RECORD_WRITES = "true";'


def _workflow(active=False):
    """A GET response's real shape: the four PUT-able keys plus everything n8n rejects on
    the way back in."""
    return {
        "id": "wf-1",
        "name": "LV Contact Ingest (Cloud template)",
        "active": active,
        "tags": [],
        "createdAt": "2026-01-01T00:00:00.000Z",
        "updatedAt": "2026-07-31T00:00:00.000Z",
        "versionId": "v-1",
        "staticData": None,
        "pinData": {},
        "meta": {"instanceId": "abc"},
        "nodes": [
            {"name": "Decide Action", "type": "n8n-nodes-base.code",
             "parameters": {"jsCode": FLAG_OFF}},
            {"name": "HubSpot Update", "type": "n8n-nodes-base.httpRequest",
             "parameters": {"url": "https://api.hubapi.com/x"}},
        ],
        "connections": {"Decide Action": {"main": [[{"node": "HubSpot Update"}]]}},
        "settings": {"executionOrder": "v1"},
    }


def _flag(workflow):
    """The narrow reader a caller hands `apply_mutation` — never a whole-body comparison."""
    for node in (workflow or {}).get("nodes", []):
        if node.get("name") == "Decide Action":
            return node["parameters"]["jsCode"]
    return None


def _arm(workflow):
    for node in workflow["nodes"]:
        if node["name"] == "Decide Action":
            node["parameters"]["jsCode"] = FLAG_ON


# --- the four-key body filter --------------------------------------------------------------


def test_put_body_keeps_exactly_the_four_keys_n8n_accepts():
    body = n8n_control.put_body(_workflow(active=True))
    assert set(body) == {"name", "nodes", "connections", "settings"}


def test_put_body_drops_every_key_n8n_rejects():
    body = n8n_control.put_body(_workflow(active=True))
    for rejected in ("id", "active", "tags", "createdAt", "updatedAt", "staticData",
                     "versionId", "pinData", "meta"):
        assert rejected not in body, f"{rejected} in a PUT body is a 400, not a silent strip"


# --- the structural diff ---------------------------------------------------------------------


def test_a_change_confined_to_an_allowlisted_node_passes():
    original = _workflow()
    modified = copy.deepcopy(original)
    _arm(modified)
    n8n_control.assert_only_allowlisted_change(original, modified, ALLOWED)


def test_a_change_to_a_node_outside_the_allowlist_is_refused_by_name():
    original = _workflow()
    modified = copy.deepcopy(original)
    modified["nodes"][1]["parameters"]["url"] = "https://evil.example/x"
    with pytest.raises(n8n_control.MutationRefused) as exc:
        n8n_control.assert_only_allowlisted_change(original, modified, ALLOWED)
    assert "HubSpot Update" in str(exc.value)


def test_adding_a_node_is_refused():
    original = _workflow()
    modified = copy.deepcopy(original)
    modified["nodes"].append({"name": "Exfiltrate", "type": "n8n-nodes-base.httpRequest",
                              "parameters": {}})
    with pytest.raises(n8n_control.MutationRefused) as exc:
        n8n_control.assert_only_allowlisted_change(original, modified, ALLOWED)
    assert "Exfiltrate" in str(exc.value)


def test_removing_a_node_is_refused():
    original = _workflow()
    modified = copy.deepcopy(original)
    modified["nodes"] = [n for n in modified["nodes"] if n["name"] != "HubSpot Update"]
    with pytest.raises(n8n_control.MutationRefused) as exc:
        n8n_control.assert_only_allowlisted_change(original, modified, ALLOWED)
    assert "HubSpot Update" in str(exc.value)


def test_a_changed_connections_graph_is_refused():
    original = _workflow()
    modified = copy.deepcopy(original)
    modified["connections"] = {}
    with pytest.raises(n8n_control.MutationRefused) as exc:
        n8n_control.assert_only_allowlisted_change(original, modified, ALLOWED)
    assert "connections" in str(exc.value)


def test_changed_settings_are_refused():
    original = _workflow()
    modified = copy.deepcopy(original)
    modified["settings"] = {"executionOrder": "v0"}
    with pytest.raises(n8n_control.MutationRefused) as exc:
        n8n_control.assert_only_allowlisted_change(original, modified, ALLOWED)
    assert "settings" in str(exc.value)


def test_an_allowlisted_name_absent_from_the_original_is_refused():
    """A typo in a node name would otherwise produce a PUT that changes nothing while
    reporting a successful mutation."""
    original = _workflow()
    with pytest.raises(n8n_control.MutationRefused) as exc:
        n8n_control.assert_only_allowlisted_change(original, copy.deepcopy(original),
                                                   {"Decide Acton"})
    assert "Decide Acton" in str(exc.value)


def test_duplicate_node_names_are_refused_rather_than_silently_collapsed():
    original = _workflow()
    original["nodes"].append(dict(original["nodes"][1]))
    with pytest.raises(n8n_control.MutationRefused):
        n8n_control.assert_only_allowlisted_change(original, copy.deepcopy(original), ALLOWED)


# --- the bracket ------------------------------------------------------------------------------


def test_a_refusal_makes_no_mutating_call_at_all(fake_config, stub_module_transport_factory):
    """Nothing was deactivated, nothing was PUT. The single GET in the log is the
    always-fetch-fresh read the refusal itself needed (T-28-06)."""
    transport = stub_module_transport_factory([_workflow()])

    def _mutate_outside_the_allowlist(workflow):
        workflow["nodes"][1]["parameters"]["url"] = "https://evil.example/x"

    with pytest.raises(n8n_control.MutationRefused):
        n8n_control.apply_mutation("wf-1", _mutate_outside_the_allowlist, ALLOWED,
                                   fake_config, verify_fn=_flag, transport=transport)

    assert transport.mutating_calls == []
    assert transport.verbs == ["get"]


def test_a_workflow_that_was_off_is_not_turned_on_by_a_content_mutation(
        fake_config, stub_module_transport_factory):
    armed = _workflow()
    _arm(armed)
    transport = stub_module_transport_factory([_workflow(active=False), {}, armed])

    result = n8n_control.apply_mutation("wf-1", _arm, ALLOWED, fake_config,
                                        verify_fn=_flag, transport=transport)

    assert not any(call["url"].endswith("/activate") for call in transport.calls)
    assert not any(call["url"].endswith("/deactivate") for call in transport.calls)
    assert transport.verbs == ["get", "put", "get"]
    assert result.verdict == n8n_control.VERIFIED


def test_a_workflow_that_was_on_is_bracketed_deactivate_put_activate(
        fake_config, stub_module_transport_factory):
    armed = _workflow(active=True)
    _arm(armed)
    transport = stub_module_transport_factory([
        _workflow(active=True),   # fetch fresh
        {},                       # deactivate
        {},                       # PUT
        {},                       # activate — restoring the PRIOR state
        armed,                    # independent read-back
    ])

    result = n8n_control.apply_mutation("wf-1", _arm, ALLOWED, fake_config,
                                        verify_fn=_flag, transport=transport)

    assert transport.verbs == ["get", "post", "put", "post", "get"]
    assert transport.calls[1]["url"].endswith("/deactivate")
    assert transport.calls[3]["url"].endswith("/activate")
    assert result.verdict == n8n_control.VERIFIED


def test_the_put_body_sent_is_the_filtered_one(fake_config, stub_module_transport_factory):
    armed = _workflow()
    _arm(armed)
    transport = stub_module_transport_factory([_workflow(), {}, armed])

    n8n_control.apply_mutation("wf-1", _arm, ALLOWED, fake_config, verify_fn=_flag,
                               transport=transport)

    sent = next(call for call in transport.calls if call["verb"] == "put")["json"]
    assert set(sent) == {"name", "nodes", "connections", "settings"}
    assert _flag(sent) == FLAG_ON


def test_an_unreadable_pre_fetch_attempts_nothing(fake_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([(500, {})])
    result = n8n_control.apply_mutation("wf-1", _arm, ALLOWED, fake_config,
                                        verify_fn=_flag, transport=transport)
    assert result.verdict == n8n_control.FAILED
    assert transport.mutating_calls == []


def test_a_failed_reactivation_says_the_workflow_was_left_off(
        fake_config, stub_module_transport_factory):
    """The loudest failure this module has: a workflow that was live is now off, and no
    read-back can make that acceptable."""
    transport = stub_module_transport_factory([
        _workflow(active=True), {}, {}, (500, {}),
    ])

    result = n8n_control.apply_mutation("wf-1", _arm, ALLOWED, fake_config,
                                        verify_fn=_flag, transport=transport)

    assert result.verdict == n8n_control.FAILED
    assert "LEFT DEACTIVATED" in result.detail


def test_the_workflow_is_always_fetched_fresh_and_never_passed_in():
    """T-28-06: a cached workflow object is the self-inflicted tampering path, so
    apply_mutation takes no workflow argument at all."""
    import inspect
    params = set(inspect.signature(n8n_control.apply_mutation).parameters)
    assert "workflow" not in params and "original" not in params
    assert "verify_fn" in params
    assert inspect.signature(n8n_control.apply_mutation).parameters[
        "verify_fn"].default is inspect.Parameter.empty
