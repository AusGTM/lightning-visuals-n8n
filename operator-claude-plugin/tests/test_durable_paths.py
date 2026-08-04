"""Unit-level companion to test_config_gate.py's entrypoint tests — NOT a replacement
for them (criterion 5). Everything an operator actually reaches is asserted through the
CLI subprocess in `test_config_gate.py::_run_cli`; what lives here is the small amount of
pure path logic a subprocess test cannot observe directly (`durable_dir()`'s own return
value, and `resolve_config_path()`'s explicit-path passthrough).

In-process `monkeypatch.setenv`/`delenv` is acceptable HERE precisely because these tests
assert on the resolver FUNCTION's own return value, not on plugin behaviour — the failure
mode the `_run_cli` docstring warns about (isolation must hold at the process boundary,
not the Python-object boundary) is about asserting operator-visible behaviour in-process,
which these tests do not do.
"""
from pathlib import Path

import durable_paths


def test_env_var_honoured_verbatim(monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", "/some/harness/path")
    assert durable_paths.durable_dir() == Path("/some/harness/path")


def test_computed_formula_used_when_env_var_is_absent(monkeypatch, tmp_path):
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    expected = (tmp_path / ".claude" / "plugins" / "data"
                / "operator-claude-plugin-lightning-visuals-operator")
    assert durable_paths.durable_dir() == expected


def test_empty_string_env_var_falls_through_to_computed_branch(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", "")
    monkeypatch.setenv("HOME", str(tmp_path))
    expected = (tmp_path / ".claude" / "plugins" / "data"
                / "operator-claude-plugin-lightning-visuals-operator")
    assert durable_paths.durable_dir() == expected


def test_plugin_id_matches_the_install_manifests_pluginid_under_at_to_dash():
    # This IS the harness's own `pluginId` (`operator-claude-plugin@lightning-visuals-operator`)
    # under the documented `@` -> `-` substitution — changing it silently orphans every
    # existing operator's durable-home config (33-RESEARCH.md Finding 1).
    assert durable_paths.PLUGIN_ID == "operator-claude-plugin-lightning-visuals-operator"


def test_resolve_config_path_explicit_returns_the_path_unchanged_even_if_missing(tmp_path):
    # The contract that keeps every pre-existing test in the suite working — the one that
    # would break most quietly if someone later added an existence check to step 1.
    missing = tmp_path / "does" / "not" / "exist" / "operator.local.json"
    assert durable_paths.resolve_config_path(missing) == missing
