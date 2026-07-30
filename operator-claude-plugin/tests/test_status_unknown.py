"""Unknown renders as the word unknown, and a half-configured plugin says what still
works instead of presenting as broken (27-03 Task 2 — D-08, PLUGIN-03).

The failure this guards against is quiet: an operator reading a blank, or a 0, where the
backend simply could not tell, concludes "healthy" — the opposite of the truth. Apollo is
the live example: this account's key is not a master key and 403s by design, so its
balance is permanently unreadable and permanently NOT zero (27-RESEARCH Pitfall 4).
"""
import json

import pytest

import backend_status
import config_gate
import status

ALL_NULL_BACKEND = {
    "available": True,
    "reason": None,
    "data": {
        "counts": {
            "companies_requested_unresolved": None,
            "companies_awaiting_review": None,
            "contacts_requested_unresolved": None,
            "contacts_awaiting_review": None,
        },
        "credential_health": [
            {"source": "lusha", "state": "unknown", "status": None, "reason": "no_response"},
            {"source": "apollo", "state": "unknown", "status": None, "reason": "not_configured"},
        ],
        "checked_at": None,
        "balances": [
            {"provider": "lusha", "configured": True, "credits": None, "unreadable": True,
             "error": "no_response", "status": None},
        ],
    },
}


# --- the renderer ---------------------------------------------------------------------


def test_null_renders_as_the_word_unknown():
    assert status.render(None) == "unknown"


def test_an_absent_key_renders_as_unknown_not_as_a_blank():
    assert status.render({}.get("nope")) == "unknown"
    assert status.render("") == "unknown"
    assert status.render("   ") == "unknown"


def test_a_genuine_zero_and_a_null_render_differently():
    """The whole point: 'out of credit' and 'we cannot tell' are opposite findings."""
    assert status.render(0) == "0"
    assert status.render(0) != status.render(None)


def test_false_renders_as_off_and_is_never_conflated_with_unknown():
    assert status.render(False) == "off"
    assert status.render(True) == "on"
    assert status.render(False) != status.render(None)


def test_a_refused_source_never_renders_with_a_healthy_sounding_word():
    rendered = status.render_source_health(
        {"source": "apollo", "state": "refused", "status": 403, "reason": "http_403"}).lower()
    assert "refused" in rendered
    for healthy in ("ok", "healthy", "fine", "good", "available"):
        assert healthy not in rendered


def test_an_unknown_source_renders_as_unknown_not_as_refused():
    rendered = status.render_source_health(
        {"source": "apollo", "state": "unknown", "status": None,
         "reason": "not_configured"}).lower()
    assert "unknown" in rendered
    assert "refused" not in rendered


def test_an_all_null_backend_renders_with_no_zero_standing_in_for_a_missing_count():
    rendered = status.render_backend_status(ALL_NULL_BACKEND)
    assert all(value == "unknown" for value in rendered["counts"].values())
    assert "0" not in json.dumps(rendered)


def test_an_unreadable_balance_renders_as_unknown_never_as_zero_credits():
    rendered = status.render_backend_status(ALL_NULL_BACKEND)
    assert rendered["balances"][0]["credits"] == "unknown"


def test_a_genuine_zero_count_survives_the_renderer():
    payload = json.loads(json.dumps(ALL_NULL_BACKEND))
    payload["data"]["counts"]["companies_awaiting_review"] = 0
    rendered = status.render_backend_status(payload)
    assert rendered["counts"]["companies_awaiting_review"] == "0"
    assert rendered["counts"]["companies_requested_unresolved"] == "unknown"


def test_an_unavailable_backend_renders_every_count_unknown_not_zero():
    rendered = status.render_backend_status(
        {"available": False, "reason": "endpoint_unreachable", "data": None})
    assert rendered["available"] is False
    assert set(rendered["counts"].values()) == {"unknown"}
    assert "0" not in json.dumps(rendered["counts"])


# --- the half-configured plugin --------------------------------------------------------


def test_status_capability_refuses_when_the_api_key_is_absent(fake_config):
    cfg = {k: v for k, v in fake_config.items() if k != "n8n_api_key"}
    with pytest.raises(config_gate.ConfigError) as exc:
        config_gate.require_capability(cfg, "status")
    assert "n8n_api_key" in str(exc.value)


def test_that_refusal_points_at_the_example_file_and_says_what_still_works(fake_config):
    cfg = {k: v for k, v in fake_config.items() if k != "n8n_api_key"}
    with pytest.raises(config_gate.ConfigError) as exc:
        config_gate.require_capability(cfg, "status")
    message = str(exc.value)
    assert "operator.local.example.json" in message
    assert "contact-upload" in message  # a missing API key is not the plugin being broken


def test_no_capability_refusal_ever_contains_a_configured_value(fake_config):
    cfg = {k: v for k, v in fake_config.items() if k != "n8n_api_key"}
    with pytest.raises(config_gate.ConfigError) as exc:
        config_gate.require_capability(cfg, "status")
    message = str(exc.value)
    for value in fake_config.values():
        if isinstance(value, str) and value:
            assert value not in message


def test_a_fully_configured_config_passes_both_capabilities(fake_config):
    for capability in ("contact-upload", "status"):
        config_gate.require_capability(fake_config, capability)
    assert set(config_gate.usable_capabilities(fake_config)) == {"contact-upload", "status"}


def test_the_status_capability_does_not_require_the_webhook_secret(fake_config):
    """The workflow/execution half needs only the API key — losing the webhook secret
    costs the backend-supplied half, not the whole answer."""
    cfg = {k: v for k, v in fake_config.items() if k != "webhook_secret"}
    config_gate.require_capability(cfg, "status")
    assert config_gate.usable_capabilities(cfg) == ["status"]


def test_the_status_read_refuses_before_any_transport_is_constructed(fake_config):
    """A transport that raises if called at all: the refusal must land first."""
    def _never_called(*args, **kwargs):
        raise AssertionError("a transport was constructed before the config gate refused")

    cfg = {k: v for k, v in fake_config.items() if k != "n8n_api_key"}
    with pytest.raises(config_gate.ConfigError):
        status.status_report(cfg, "wf-1", get_transport=_never_called,
                             post_transport=_never_called)


def test_a_missing_webhook_secret_still_reports_the_workflow_half(
        fake_config, stub_get_transport_factory):
    cfg = {k: v for k, v in fake_config.items() if k != "webhook_secret"}
    get_transport = stub_get_transport_factory([
        {"id": "wf-1", "name": "LV Contact Ingest (Cloud template)", "active": True, "nodes": []},
        {"data": []},
    ])

    def _never_called(*args, **kwargs):
        raise AssertionError("the backend endpoint must not be called without a secret")

    report = status.status_report(cfg, "wf-1", get_transport=get_transport,
                                  post_transport=_never_called)
    assert report["workflow"]["active"] is True
    assert report["backend"]["available"] is False
    assert report["backend"]["reason"] == "webhook_secret_not_configured"


def test_fetch_backend_status_sends_nothing_without_a_secret(fake_config):
    cfg = {k: v for k, v in fake_config.items() if k != "webhook_secret"}

    def _never_called(*args, **kwargs):
        raise AssertionError("an unauthenticated request was constructed")

    assert backend_status.fetch_backend_status(cfg, transport=_never_called)["available"] is False


# --- the committed template -------------------------------------------------------------


def test_the_example_config_documents_every_key_a_capability_requires():
    example = json.loads(
        (config_gate.PLUGIN_ROOT / "config" / config_gate.EXAMPLE_CONFIG_NAME).read_text())
    for keys in config_gate.CAPABILITY_KEYS.values():
        for key in keys:
            assert key in example, f"{key} is required but absent from the committed template"
    assert "stuck_execution_minutes" in example
    assert isinstance(example["stuck_execution_minutes"], int)
