"""Tests for config_gate.py — the refuse-before-any-network-call gate (D-06, PLUGIN-03).

Every test passes an explicit path so the real (gitignored) operator config is never
touched.
"""
import json
import os

import pytest

from config_gate import ConfigError, describe_target, load_config, require_capability


def test_missing_file_names_the_file_and_points_at_the_example(tmp_path):
    missing = tmp_path / "operator.local.json"
    with pytest.raises(ConfigError) as exc:
        load_config(missing)
    message = str(exc.value)
    assert "operator.local.json" in message
    assert "operator.local.example.json" in message


def test_empty_webhook_secret_does_not_raise_status_still_needs_it_only(tmp_path):
    """PLUGIN-03 regression: `load_config()` enforces only `n8n_url`, the one key every
    capability needs. A blank `webhook_secret` used to take the whole status read down
    even though status's own capability row (`n8n_url`, `n8n_api_key`) never lists it —
    see `.planning/debug/resolved/load-config-over-refusal.md`."""
    cfg_path = tmp_path / "operator.local.json"
    cfg_path.write_text(json.dumps({"n8n_url": "https://fake.n8n.cloud", "webhook_secret": ""}))
    cfg = load_config(cfg_path)
    assert cfg["webhook_secret"] == ""
    # status needs n8n_api_key, not webhook_secret, so it still refuses cleanly here —
    # naming the key it actually needs, not webhook_secret.
    with pytest.raises(ConfigError) as exc:
        require_capability(cfg, "status")
    assert "n8n_api_key" in str(exc.value)
    assert "webhook_secret" not in str(exc.value)


def test_empty_webhook_secret_still_refuses_contact_upload_by_name(tmp_path):
    """The corollary this fix must not break: capabilities that DO need `webhook_secret`
    (contact-upload, review, enrichment, sweep) still refuse — just at the capability
    layer instead of the blanket `load_config()` layer."""
    cfg_path = tmp_path / "operator.local.json"
    cfg_path.write_text(json.dumps({"n8n_url": "https://fake.n8n.cloud", "webhook_secret": ""}))
    cfg = load_config(cfg_path)
    for capability in ("contact-upload", "review", "enrichment"):
        with pytest.raises(ConfigError) as exc:
            require_capability(cfg, capability)
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


# --- the CLI entrypoint, not the function beneath it -------------------------------
#
# The upload lane's preflight is `python3 scripts/config_gate.py` (contact-upload
# SKILL.md step 1), and these drive that ENTRYPOINT as a subprocess. Asserting on
# `load_config()` alone is what let two defects ship this week: the over-refusal (the
# CLI refused where the function degraded) and then its own loose end (the CLI stopped
# refusing where the skill still needed a verdict). The layer the operator reaches is
# the layer under test here.

def _run_cli(config_json, tmp_path, env=None, durable_config=None):
    """Run scripts/config_gate.py as the skill runs it — as a real subprocess, against an
    ISOLATED plugin root so the operator's own gitignored config is never read.

    config_gate imports durable_paths, so both modules are copied into the throwaway
    `scripts/` directory — config_gate no longer "imports nothing from its siblings", and
    a single-file copy would make every durable-home test die on ImportError.

    A fake `HOME` (`tmp_path / "home"`) is what redirects `Path.home()`-based resolution
    at the PROCESS boundary, not the Python-object boundary — the same lesson this
    harness's own history already recorded: its first version silently read the
    operator's REAL config because `runpy` discarded a path override. Monkeypatching
    `Path.home` in-process, or patching an attribute on an in-process `durable_paths`
    import, would be vulnerable to the identical class of bug the moment `config_gate.py`
    runs as a fresh subprocess that re-imports the module — isolation has to hold where
    the subprocess actually looks, not where the test happens to be running.

    `durable_config`, when given, is written to this fake home's durable directory
    (`~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/operator.local.json`).

    The subprocess `env` is built from a literal dict (`PATH` + the fake `HOME`, plus any
    caller overrides) — NEVER `{**os.environ, ...}` — so the real `HOME` can never reach
    the subprocess and no durable-home test can pass for the wrong reason.
    """
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    root = tmp_path / "plugin"
    (root / "scripts").mkdir(parents=True)
    (root / "config").mkdir()
    shutil.copyfile(scripts_dir / "config_gate.py", root / "scripts" / "config_gate.py")
    shutil.copyfile(scripts_dir / "durable_paths.py", root / "scripts" / "durable_paths.py")
    if config_json is not None:
        (root / "config" / "operator.local.json").write_text(json.dumps(config_json))

    fake_home = tmp_path / "home"
    if durable_config is not None:
        durable_dir = (fake_home / ".claude" / "plugins" / "data"
                       / "operator-claude-plugin-lightning-visuals-operator")
        durable_dir.mkdir(parents=True, exist_ok=True)
        (durable_dir / "operator.local.json").write_text(json.dumps(durable_config))
    else:
        fake_home.mkdir(parents=True, exist_ok=True)

    run_env = {"PATH": os.environ.get("PATH", ""), "HOME": str(fake_home), **(env or {})}

    return subprocess.run([sys.executable, "config_gate.py"], capture_output=True,
                          text=True, cwd=str(root / "scripts"), env=run_env)


def test_cli_reports_can_send_true_when_the_upload_lane_is_configured(tmp_path, fake_config):
    proc = _run_cli(fake_config, tmp_path)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["can_send"] is True
    assert payload["send_blocked_reason"] is None


def test_cli_still_answers_ok_without_a_webhook_secret_but_says_it_cannot_send(
        tmp_path, fake_config):
    """The UAT 1.2 re-walk finding, pinned. Previewing needs no secret, so the preflight
    must NOT refuse — but it must tell the skill that sending is impossible, or the
    operator is invited to arm a send that dispatch() will refuse."""
    cfg = {k: v for k, v in fake_config.items() if k != "webhook_secret"}
    proc = _run_cli(cfg, tmp_path)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)

    assert payload["ok"] is True, "a loadable config is still ok — previewing works"
    assert payload["target"], "the operator is still told where this lane would send"
    assert payload["can_send"] is False
    reason = payload["send_blocked_reason"]
    assert "webhook_secret" in reason, "names the missing key"
    assert "operator.local.json" in reason, "names where to fix it"
    assert fake_config["webhook_secret"] not in proc.stdout, "never echoes a secret"


def test_cli_refuses_outright_when_the_universal_key_is_missing(tmp_path, fake_config):
    """`n8n_url` is the one key every capability needs, so its absence is still a hard
    refusal with a non-zero exit — not a can_send verdict."""
    cfg = {k: v for k, v in fake_config.items() if k != "n8n_url"}
    proc = _run_cli(cfg, tmp_path)
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert "n8n_url" in payload["error"]
    assert "can_send" not in payload


# --- durable-home resolution, pinned at the CLI entrypoint (33-01) -----------------
#
# Every assertion here drives config_gate.py as a subprocess against a fake HOME —
# never load_config() directly — per criterion 5: the 0.6.1 and 0.6.2 defects both
# shipped invisibly to tests that called the resolver function in-process.

def test_cli_durable_home_is_read_when_the_installs_own_config_is_empty(tmp_path, fake_config):
    proc = _run_cli(None, tmp_path, durable_config=fake_config)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["target"] == "https://fake-tenant.n8n.cloud/webhook/hubspot/contact-upload"


def test_cli_legacy_same_install_path_still_resolves_when_durable_home_is_empty(
        tmp_path, fake_config):
    """Today's behaviour, unchanged (33-01 criterion 6): an operator with no durable-home
    file and a config in the same install's config/ directory sees the same result as
    before this phase."""
    proc = _run_cli(fake_config, tmp_path)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["target"] == "https://fake-tenant.n8n.cloud/webhook/hubspot/contact-upload"


def test_cli_durable_home_wins_when_both_are_present(tmp_path, fake_config):
    legacy_cfg = {**fake_config, "n8n_url": "https://legacy-install.n8n.cloud"}
    durable_cfg = {**fake_config, "n8n_url": "https://durable-home.n8n.cloud"}
    proc = _run_cli(legacy_cfg, tmp_path, durable_config=durable_cfg)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["target"] == "https://durable-home.n8n.cloud/webhook/hubspot/contact-upload"


def test_skill_documents_the_can_send_contract():
    """Two-sided: the CLI emits `can_send`, and the skill body must act on it. A field no
    skill reads is a field that silently stops mattering."""
    from pathlib import Path
    skill = (Path(__file__).resolve().parent.parent
             / "skills" / "contact-upload" / "SKILL.md").read_text()
    assert "can_send" in skill, "step 1 must read the send-readiness verdict"
    assert "send_blocked_reason" in skill, "and relay the reason it carries"
    assert "do not offer the arming phrase" in skill, \
        "an operator who cannot send must not be invited to arm"
