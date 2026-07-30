"""Tests for config_gate.py — the refuse-before-any-network-call gate (D-06, PLUGIN-03).

Every test passes an explicit path so the real (gitignored) operator config is never
touched.
"""
import json

import pytest

from config_gate import ConfigError, describe_target, load_config


def test_missing_file_names_the_file_and_points_at_the_example(tmp_path):
    missing = tmp_path / "operator.local.json"
    with pytest.raises(ConfigError) as exc:
        load_config(missing)
    message = str(exc.value)
    assert "operator.local.json" in message
    assert "operator.local.example.json" in message


def test_empty_webhook_secret_raises_naming_that_key(tmp_path):
    cfg_path = tmp_path / "operator.local.json"
    cfg_path.write_text(json.dumps({"n8n_url": "https://fake.n8n.cloud", "webhook_secret": ""}))
    with pytest.raises(ConfigError) as exc:
        load_config(cfg_path)
    assert "webhook_secret" in str(exc.value)


def test_missing_n8n_url_raises_naming_that_key(tmp_path):
    cfg_path = tmp_path / "operator.local.json"
    cfg_path.write_text(json.dumps({"webhook_secret": "shh"}))
    with pytest.raises(ConfigError) as exc:
        load_config(cfg_path)
    assert "n8n_url" in str(exc.value)


def test_non_https_n8n_url_raises(tmp_path):
    cfg_path = tmp_path / "operator.local.json"
    cfg_path.write_text(json.dumps({"n8n_url": "http://not-secure.example", "webhook_secret": "shh"}))
    with pytest.raises(ConfigError) as exc:
        load_config(cfg_path)
    assert "n8n_url" in str(exc.value)


def test_malformed_json_raises_configerror_not_a_parser_traceback(tmp_path):
    cfg_path = tmp_path / "operator.local.json"
    cfg_path.write_text("{not valid json")
    with pytest.raises(ConfigError):
        load_config(cfg_path)


def test_valid_file_returns_the_parsed_mapping(tmp_path, fake_config):
    cfg_path = tmp_path / "operator.local.json"
    cfg_path.write_text(json.dumps(fake_config))
    cfg = load_config(cfg_path)
    assert cfg["n8n_url"] == fake_config["n8n_url"]
    assert cfg["webhook_secret"] == fake_config["webhook_secret"]


def test_describe_target_returns_the_endpoint_without_the_secret(fake_config):
    target = describe_target(fake_config)
    assert target == "https://fake-tenant.n8n.cloud/webhook/hubspot/contact-upload"
    assert fake_config["webhook_secret"] not in target


def test_no_configerror_message_ever_contains_the_secret_value(tmp_path):
    cfg_path = tmp_path / "operator.local.json"
    cfg_path.write_text(
        json.dumps({"n8n_url": "not-https", "webhook_secret": "super-secret-value"})
    )
    with pytest.raises(ConfigError) as exc:
        load_config(cfg_path)
    assert "super-secret-value" not in str(exc.value)
