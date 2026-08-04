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
import stat
from pathlib import Path

import pytest

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


# --- 33-02 Task 2: `_newest_sibling_holding`'s four edge cases, `_atomic_write_0600`'s
# mode/cleanup — 33-RESEARCH.md § Research Findings 4. ------------------------------

_MARKER = Path("config") / "marker.json"


def _make_sibling(cache_root: Path, version: str, holds_marker: bool) -> Path:
    install = cache_root / version
    (install / "config").mkdir(parents=True)
    if holds_marker:
        (install / "config" / "marker.json").write_text('{"v": "%s"}' % version)
    return install


def test_mixed_valid_and_invalid_directory_names_returns_the_newest_valid_one(tmp_path, monkeypatch):
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    _make_sibling(cache_root, "0.1.0", holds_marker=True)
    _make_sibling(cache_root, "0.6.2", holds_marker=True)
    (cache_root / ".DS_Store").write_text("")
    (cache_root / "scratch").mkdir()

    # PLUGIN_ROOT must sit directly under cache_root, one level up from the version
    # dirs — a fictitious current version that doesn't collide with either sibling.
    monkeypatch.setattr(durable_paths, "PLUGIN_ROOT", cache_root / "9.9.9")
    result = durable_paths._newest_sibling_holding(_MARKER)
    assert result == cache_root / "0.6.2"


def test_a_newer_sibling_directory_holding_no_marker_loses_to_an_older_one_that_does(
        tmp_path, monkeypatch):
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    _make_sibling(cache_root, "0.1.0", holds_marker=True)
    _make_sibling(cache_root, "0.6.2", holds_marker=False)

    monkeypatch.setattr(durable_paths, "PLUGIN_ROOT", cache_root / "9.9.9")
    result = durable_paths._newest_sibling_holding(_MARKER)
    assert result == cache_root / "0.1.0"


def test_plugin_root_excluded_even_when_its_own_name_sorts_highest(tmp_path, monkeypatch):
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    _make_sibling(cache_root, "0.6.1", holds_marker=True)
    current = _make_sibling(cache_root, "0.6.2", holds_marker=True)

    # PLUGIN_ROOT points AT the highest-numbered, marker-holding directory — if
    # exclusion were by version-string comparison instead of resolved-path identity,
    # the scan would happily "migrate from" the current install itself.
    monkeypatch.setattr(durable_paths, "PLUGIN_ROOT", current)
    result = durable_paths._newest_sibling_holding(_MARKER)
    assert result == cache_root / "0.6.1"


def test_version_key_orders_double_digit_minor_above_single_digit():
    # String comparison gets this backwards ("0.10.0" < "0.9.0" lexicographically) —
    # the plugin is four minor versions from hitting it for real.
    assert durable_paths._version_key("0.10.0") > durable_paths._version_key("0.9.0")


def test_newest_sibling_holding_returns_none_for_a_cache_root_that_does_not_exist(
        tmp_path, monkeypatch):
    # The ordinary "fresh install, nothing to migrate" case (33-RESEARCH.md Finding 4)
    # — old install directories are pruned roughly two weeks after an update.
    ghost_root = tmp_path / "does-not-exist"
    monkeypatch.setattr(durable_paths, "PLUGIN_ROOT", ghost_root / "0.7.0")
    assert durable_paths._newest_sibling_holding(_MARKER) is None


def test_atomic_write_0600_leaves_the_target_at_mode_0600_with_no_leftover_temp_file(tmp_path):
    target = tmp_path / "durable" / "operator.local.json"
    durable_paths._atomic_write_0600(target, '{"n8n_url": "https://x.example"}')

    assert target.read_text(encoding="utf-8") == '{"n8n_url": "https://x.example"}'
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    # exactly one entry — the target — proves no temp file survived
    assert [p.name for p in target.parent.iterdir()] == [target.name]


def test_atomic_write_0600_leaves_no_leftover_entries_when_os_replace_fails(tmp_path, monkeypatch):
    target = tmp_path / "durable" / "operator.local.json"

    def _boom(*args, **kwargs):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(durable_paths.os, "replace", _boom)
    with pytest.raises(OSError):
        durable_paths._atomic_write_0600(target, "content")

    assert not target.exists()
    assert list(target.parent.iterdir()) == []
