"""Task 1 — the CONTROL-02 tracer: turning a workflow on or off, end to end.

The point of this file is the verdict, not the call. Any implementation can POST to
/activate and read a 200 back; what this phase has to prove is that a 200 alone never
becomes "verified", and that the answer comes from a SEPARATE read whose value is compared
against what was asked for (D-14, D-17).
"""
import pytest

import config_gate
import n8n_control


def _workflow(active, name="LV Contact Ingest (Cloud template)"):
    return {"id": "wf-1", "name": name, "active": active, "nodes": [],
            "connections": {}, "settings": {}}


def test_turning_an_inactive_workflow_on_is_get_post_get(fake_config,
                                                         stub_module_transport_factory):
    transport = stub_module_transport_factory([
        _workflow(False),   # the prior-state read
        _workflow(True),    # the activate call's own echo — never the read-back
        _workflow(True),    # the independent read-back
    ])

    result = n8n_control.set_active("wf-1", True, fake_config, transport=transport)

    assert transport.verbs == ["get", "post", "get"]
    assert transport.calls[1]["url"].endswith("/api/v1/workflows/wf-1/activate")
    assert transport.calls[1]["json"] is None, "activate takes no request body"
    assert transport.calls[-1]["verb"] == "get"
    assert result.verdict == n8n_control.VERIFIED
    assert result.verified is True


def test_turning_an_active_workflow_off_posts_to_deactivate(fake_config,
                                                            stub_module_transport_factory):
    transport = stub_module_transport_factory([
        _workflow(True), _workflow(False), _workflow(False),
    ])

    result = n8n_control.set_active("wf-1", False, fake_config, transport=transport)

    assert transport.calls[1]["url"].endswith("/api/v1/workflows/wf-1/deactivate")
    assert result.verdict == n8n_control.VERIFIED
    assert result.observed is False


def test_a_readback_still_showing_the_old_value_is_failed_not_verified(
        fake_config, stub_module_transport_factory):
    """Every status code here is 200. The workflow is still off. That is the stale-instance
    case, and it must not pass as success."""
    transport = stub_module_transport_factory([
        _workflow(False), _workflow(True), _workflow(False),
    ])

    result = n8n_control.set_active("wf-1", True, fake_config, transport=transport)

    assert result.verdict == n8n_control.FAILED
    assert result.observed is False
    assert result.requested is True
    assert result.detail


def test_the_reversal_quotes_the_prior_value(fake_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([
        _workflow(False), _workflow(True), _workflow(True),
    ])

    result = n8n_control.set_active("wf-1", True, fake_config, transport=transport)

    assert result.prior is False
    assert result.reversal == "it was off; to undo, I'll turn it back off."


def test_the_reversal_for_an_active_workflow_names_turning_it_back_on(
        fake_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([
        _workflow(True), _workflow(False), _workflow(False),
    ])

    result = n8n_control.set_active("wf-1", False, fake_config, transport=transport)

    assert result.reversal == "it was on; to undo, I'll turn it back on."


def test_a_non_2xx_on_the_activate_call_is_failed_with_a_detail(
        fake_config, stub_module_transport_factory):
    transport = stub_module_transport_factory([
        _workflow(False), (500, {"message": "boom"}),
    ])

    result = n8n_control.set_active("wf-1", True, fake_config, transport=transport)

    assert result.verdict == n8n_control.FAILED
    assert result.detail
    assert "500" in result.detail
    assert result.observed is None, "no read-back verdict may be fabricated after a failure"
    assert transport.verbs == ["get", "post"], "no read-back is attempted after a failed POST"


def test_an_unreadable_readback_is_failed(fake_config, stub_module_transport_factory):
    """n8n_read.get_workflow returns None for every failure mode there is. An unreadable
    read-back is not a verified one."""
    transport = stub_module_transport_factory([
        _workflow(False), _workflow(True), (503, {}),
    ])

    result = n8n_control.set_active("wf-1", True, fake_config, transport=transport)

    assert result.verdict == n8n_control.FAILED
    assert result.observed is None


def test_an_unreadable_prior_state_attempts_no_mutation(fake_config,
                                                        stub_module_transport_factory):
    transport = stub_module_transport_factory([(401, {})])

    result = n8n_control.set_active("wf-1", True, fake_config, transport=transport)

    assert result.verdict == n8n_control.FAILED
    assert transport.mutating_calls == []


def test_the_activate_call_carries_the_api_key_header(fake_config,
                                                      stub_module_transport_factory):
    transport = stub_module_transport_factory([
        _workflow(False), _workflow(True), _workflow(True),
    ])

    n8n_control.set_active("wf-1", True, fake_config, transport=transport)

    assert transport.calls[1]["headers"]["X-N8N-API-KEY"] == fake_config["n8n_api_key"]


# --- reuse, not reimplementation ---------------------------------------------------------


def test_the_control_module_defines_no_reader_of_its_own():
    """Both readers come from n8n_read: a duplicate reader cannot detect the desync it is
    itself the cause of (D-26, D-27)."""
    source = (n8n_control.__file__ and open(n8n_control.__file__, encoding="utf-8").read())
    assert "def read_write_safety" not in source
    assert "def fetch_workflow" not in source
    assert "import n8n_read" in source


# --- the capability row -------------------------------------------------------------------


def test_control_is_its_own_capability_needing_the_api_key(fake_config):
    assert config_gate.CAPABILITY_KEYS["control"] == ("n8n_url", "n8n_api_key")
    config_gate.require_capability(fake_config, "control")


def test_control_refuses_in_plain_language_without_the_api_key(fake_config):
    cfg = {k: v for k, v in fake_config.items() if k != "n8n_api_key"}
    with pytest.raises(config_gate.ConfigError) as exc:
        config_gate.require_capability(cfg, "control")
    message = str(exc.value)
    assert "n8n_api_key" in message
    assert "contact-upload" in message, "a missing API key is not the plugin being broken"
    for value in fake_config.values():
        if isinstance(value, str) and value:
            assert value not in message
