"""Tests for /operator-claude-plugin:initialize.

Two properties carry the whole thing: it is idempotent, and it cannot leak a secret. The
placeholder case is the one that actually bites — a file full of template text exists but
is NOT configured, and reporting it as ready sends the operator to an auth error three
steps later that nobody traces back to setup.
"""
import json
from pathlib import Path

import pytest

import config_gate
import durable_paths
import init_check

SECRET = "sk-super-secret-value-that-must-never-be-printed"


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "operator.local.json"


def _write(path, **values):
    path.write_text(json.dumps(values))
    return path


# --- state detection -------------------------------------------------------------------

def test_no_file_reports_no_file_and_names_the_absolute_path(config_path):
    report = init_check.inspect(config_path)

    assert report["status"] == init_check.STATUS_NO_FILE
    assert report["config_path"] == str(config_path)
    assert Path(report["config_path"]).is_absolute()
    assert "no settings file" in init_check.render(report).lower()


def test_a_fully_configured_file_reports_ready(config_path):
    _write(config_path, n8n_url="https://real.n8n.cloud", webhook_secret=SECRET,
           n8n_api_key="real-key")

    report = init_check.inspect(config_path)

    assert report["status"] == init_check.STATUS_READY
    assert all(row["ready"] for row in report["capabilities"].values())


def test_template_placeholders_are_NOT_treated_as_configured(config_path):
    """The file exists and looks filled in at a glance. It is not."""
    _write(config_path, n8n_url="https://<your-subdomain>.n8n.cloud",
           webhook_secret="<ask your admin>", n8n_api_key="<ask your admin>")

    report = init_check.inspect(config_path)

    assert report["status"] == init_check.STATUS_NEEDS_VALUES
    assert report["keys"]["n8n_url"] == "placeholder"
    assert report["keys"]["webhook_secret"] == "placeholder"
    assert not any(row["ready"] for row in report["capabilities"].values())
    assert "placeholder" in init_check.render(report)


def test_a_partly_configured_file_says_what_still_works(config_path):
    """PLUGIN-03 forbids over-refusing: no api key still uploads contacts fine."""
    _write(config_path, n8n_url="https://real.n8n.cloud", webhook_secret=SECRET)

    report = init_check.inspect(config_path)

    assert report["status"] == init_check.STATUS_NEEDS_VALUES
    assert report["capabilities"]["contact-upload"]["ready"] is True
    assert report["capabilities"]["review"]["ready"] is True
    assert report["capabilities"]["status"]["ready"] is False
    assert report["capabilities"]["status"]["needs"] == ["n8n_api_key"]

    rendered = init_check.render(report)
    assert "uploading contacts: ready" in rendered


def test_unparseable_json_is_its_own_state_not_a_crash(config_path):
    config_path.write_text("{ this is not json")

    report = init_check.inspect(config_path)

    assert report["status"] == init_check.STATUS_UNREADABLE
    assert "missing comma" in init_check.render(report)


# --- the property that matters most: no secret ever leaves ------------------------------

@pytest.mark.parametrize("state", ["ready", "partial", "placeholder"])
def test_no_rendered_output_or_report_ever_contains_a_secret_value(config_path, state):
    values = {
        "ready": dict(n8n_url="https://real.n8n.cloud", webhook_secret=SECRET,
                      n8n_api_key=SECRET),
        "partial": dict(n8n_url="https://real.n8n.cloud", webhook_secret=SECRET),
        "placeholder": dict(n8n_url="<x>", webhook_secret=SECRET),
    }[state]
    _write(config_path, **values)

    report = init_check.inspect(config_path)

    assert SECRET not in json.dumps(report)
    assert SECRET not in init_check.render(report)


def test_the_module_has_no_code_path_that_prints_a_config_value():
    """Not 'it happens not to' — there is no flag for it and no branch that could."""
    source = Path(init_check.__file__).read_text()
    assert "--show" not in source
    assert "cfg[" not in source, "values are read via _key_state only, never indexed out"
    assert "print(cfg" not in source


# --- idempotency ---------------------------------------------------------------------------

def test_running_the_check_twice_changes_nothing(config_path):
    _write(config_path, n8n_url="https://real.n8n.cloud", webhook_secret=SECRET,
           n8n_api_key="k")
    before = config_path.read_text()

    first = init_check.inspect(config_path)
    second = init_check.inspect(config_path)

    assert first == second
    assert config_path.read_text() == before


def test_create_never_overwrites_an_existing_config(config_path, monkeypatch):
    _write(config_path, n8n_url="https://real.n8n.cloud", webhook_secret=SECRET)
    before = config_path.read_text()

    outcome = init_check.create_from_example(config_path)

    assert outcome["created"] is False
    assert "already there" in outcome["reason"]
    assert config_path.read_text() == before


def test_create_puts_the_template_in_place_when_there_is_none(config_path):
    outcome = init_check.create_from_example(config_path)

    assert outcome["created"] is True
    assert config_path.exists()

    # and what it wrote is placeholders, so the very next check still says NEEDS_VALUES
    report = init_check.inspect(config_path)
    assert report["status"] == init_check.STATUS_NEEDS_VALUES


# --- the capability rows are not a second list -------------------------------------------

def test_capability_rows_come_from_config_gate_not_a_copy(config_path):
    _write(config_path, n8n_url="https://real.n8n.cloud", webhook_secret=SECRET,
           n8n_api_key="k")
    report = init_check.inspect(config_path)

    assert set(report["capabilities"]) == set(config_gate.CAPABILITY_KEYS)
    source = Path(init_check.__file__).read_text()
    assert "contact-upload" not in source, "capability names must not be hardcoded here"


# --- config_location: where the settings actually resolved from — 33-03 Task 3 ----------
#
# Every test here isolates HOME under tmp_path (never the operator's real ~/.claude) and
# calls init_check.inspect() with NO explicit path, so resolution runs the real
# durable_paths chain exactly as an operator's session would.

def test_config_location_is_env_when_lv_operator_config_is_set(tmp_path, monkeypatch):
    override = tmp_path / "override" / "operator.local.json"
    override.parent.mkdir(parents=True)
    _write(override, n8n_url="https://real.n8n.cloud", webhook_secret=SECRET, n8n_api_key="k")
    monkeypatch.setenv("LV_OPERATOR_CONFIG", str(override))

    report = init_check.inspect()

    assert report["config_location"] == "env"
    assert report["config_path"] == str(override)


def test_config_location_is_durable_when_the_config_lives_in_the_durable_home(
        tmp_path, monkeypatch):
    monkeypatch.delenv("LV_OPERATOR_CONFIG", raising=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    durable_dir = fake_home / ".claude" / "plugins" / "data" / durable_paths.PLUGIN_ID
    durable_dir.mkdir(parents=True)
    durable_cfg = durable_dir / "operator.local.json"
    _write(durable_cfg, n8n_url="https://real.n8n.cloud", webhook_secret=SECRET, n8n_api_key="k")

    report = init_check.inspect()

    assert report["config_location"] == "durable"
    assert report["config_path"] == str(durable_cfg)


def test_config_location_is_legacy_when_the_config_lives_in_the_installs_own_config_dir(
        tmp_path, monkeypatch):
    """Neither the env override nor the durable home — the pre-33-01 location, still a
    legitimate resolution result (a fresh install with nothing yet migrated up)."""
    monkeypatch.delenv("LV_OPERATOR_CONFIG", raising=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    fake_root = tmp_path / "plugin"
    (fake_root / "config").mkdir(parents=True)
    legacy_cfg = fake_root / "config" / "operator.local.json"
    _write(legacy_cfg, n8n_url="https://real.n8n.cloud", webhook_secret=SECRET, n8n_api_key="k")
    monkeypatch.setattr(durable_paths, "PLUGIN_ROOT", fake_root)

    report = init_check.inspect()

    assert report["config_location"] == "legacy"
    assert report["config_path"] == str(legacy_cfg)


def test_render_on_a_ready_config_names_the_resolved_path(config_path):
    _write(config_path, n8n_url="https://real.n8n.cloud", webhook_secret=SECRET, n8n_api_key="k")

    report = init_check.inspect(config_path)
    rendered = init_check.render(report)

    assert str(config_path) in rendered


def test_rendered_output_for_a_durable_config_never_mentions_migration(tmp_path, monkeypatch):
    """The honest, testable form of criterion 4's 'says nothing about migration having
    happened unless it happened' — init_check has no way to know whether THIS process
    moved anything, so it never claims it, on any branch, in any casing."""
    monkeypatch.delenv("LV_OPERATOR_CONFIG", raising=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    durable_dir = fake_home / ".claude" / "plugins" / "data" / durable_paths.PLUGIN_ID
    durable_dir.mkdir(parents=True)
    durable_cfg = durable_dir / "operator.local.json"
    _write(durable_cfg, n8n_url="https://real.n8n.cloud", webhook_secret=SECRET, n8n_api_key="k")

    report = init_check.inspect()
    rendered = init_check.render(report)

    assert report["config_location"] == "durable"
    assert "migrat" not in rendered.lower()
