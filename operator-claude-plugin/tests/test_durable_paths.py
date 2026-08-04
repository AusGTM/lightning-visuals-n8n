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


# --- "nothing anywhere yet" — the state every NEW operator starts in ----------------
#
# RB-10 (2026-08-04) found both resolvers returned the LEGACY path when the file existed
# nowhere, so a first-ever pointer or config was written into the versioned install
# directory and stranded by the next update. Every existing test seeded the durable file
# before asserting — including two whose fixtures were changed to pre-create it precisely
# BECAUSE the bare call fell through. That fallthrough was the bug; the fixture hid it.

def _fake_home(tmp_path, monkeypatch, durable_paths=None):
    """A fake HOME *and* an empty install root.

    Both halves matter. Without the empty PLUGIN_ROOT this test resolves to the REPO
    checkout's own `config/operator.local.json`, which really does exist — step 4 then
    returns legacy correctly and the test fails for a reason that is not the bug. That is
    the trap 33-03 fell into: it read the same failure as an environment quirk and seeded
    the durable file to get past it, which hid the fallthrough RB-10 later found live.
    Point PLUGIN_ROOT at an empty directory instead, so "nothing in this install" is
    actually true.
    """
    home = tmp_path / "home"
    (home / ".claude" / "plugins" / "data").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("LV_OPERATOR_CONFIG", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    if durable_paths is not None:
        empty_install = tmp_path / "empty-install"
        empty_install.mkdir()
        monkeypatch.setattr(durable_paths, "PLUGIN_ROOT", empty_install)
    return home


def test_a_first_ever_config_is_written_to_the_durable_home_not_the_install_dir(
        tmp_path, monkeypatch):
    """No config in the durable home, none in this install, none in any sibling — a brand
    new operator. The resolved path is where `initialize --create` will write it."""
    import importlib
    import durable_paths
    importlib.reload(durable_paths)
    _fake_home(tmp_path, monkeypatch, durable_paths)

    resolved = durable_paths.resolve_config_path()
    assert durable_paths.PLUGIN_ROOT not in resolved.parents, (
        "a first-ever config must not be born inside the versioned install directory")
    assert resolved.parent == durable_paths.durable_dir()


def test_a_first_ever_pointer_is_written_to_the_durable_home_not_the_install_dir(
        tmp_path, monkeypatch):
    """The exact RB-10 case: no `state/` in any install, so nothing to migrate."""
    import importlib
    import durable_paths
    importlib.reload(durable_paths)
    _fake_home(tmp_path, monkeypatch, durable_paths)

    resolved = durable_paths.resolve_state_path()
    assert durable_paths.PLUGIN_ROOT not in resolved.parents
    assert resolved.parent == durable_paths.durable_dir()


def test_an_uncreatable_durable_home_degrades_to_legacy_rather_than_raising(
        tmp_path, monkeypatch):
    """CONTEXT.md's degrade-never-strand rule. A resolver that raises here would make the
    plugin refuse to work because migration is impossible — the opposite of the intent."""
    import importlib
    import durable_paths
    importlib.reload(durable_paths)
    _fake_home(tmp_path, monkeypatch, durable_paths)

    def _boom(*a, **k):
        raise OSError("read-only")
    monkeypatch.setattr(durable_paths.Path, "mkdir", _boom)

    resolved = durable_paths.resolve_config_path()
    assert resolved == durable_paths.PLUGIN_ROOT / "config" / durable_paths.CONFIG_FILENAME
