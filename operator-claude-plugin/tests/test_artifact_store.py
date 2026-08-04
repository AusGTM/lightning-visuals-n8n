"""The plugin's only persisted state (27-05 Task 1).

D-09b bounds this deliberately: exactly an identifier and a timestamp, an
operator-configurable expiry defaulting to thirty days, garbage-collected on the next
plugin open. The bound is enforced here rather than by intention — a store that accepts
arbitrary keys becomes a general-purpose store in one commit, and the first thing parked
in it would be the conversation-scoped arming grant Phase 23 D-11 deliberately keeps off
disk entirely.

Every case that is not "a live pointer" returns nothing rather than raising: a stale or
broken pointer is indistinguishable in effect from no pointer, and must not produce an
error the operator has to read.
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import artifact_store

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "dashboard_artifact.json"


def _iso(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _write(path, **document):
    path.write_text(json.dumps(document), encoding="utf-8")


# --- load ------------------------------------------------------------------------------


def test_loading_with_no_state_file_returns_nothing_without_raising(state_file):
    assert not state_file.exists()
    assert artifact_store.load({}, path=state_file) is None


def test_loading_a_live_entry_returns_the_identifier(state_file):
    artifact_store.save("dash-1", path=state_file)
    assert artifact_store.load({}, path=state_file) == "dash-1"


def test_loading_a_malformed_file_returns_nothing_rather_than_raising(state_file):
    state_file.write_text("{not json at all", encoding="utf-8")
    assert artifact_store.load({}, path=state_file) is None


def test_loading_a_file_that_is_not_a_mapping_returns_nothing(state_file):
    state_file.write_text(json.dumps(["dash-1", "2026-07-31"]), encoding="utf-8")
    assert artifact_store.load({}, path=state_file) is None


def test_loading_an_entry_missing_either_field_returns_nothing(state_file):
    _write(state_file, artifact_id="dash-1")
    assert artifact_store.load({}, path=state_file) is None

    _write(state_file, saved_at=_iso())
    assert artifact_store.load({}, path=state_file) is None


def test_loading_an_unparseable_timestamp_returns_nothing(state_file):
    _write(state_file, artifact_id="dash-1", saved_at="whenever")
    assert artifact_store.load({}, path=state_file) is None


def test_loading_a_file_carrying_extra_fields_returns_only_the_identifier(state_file):
    """A file someone widened by hand must not become a channel for anything else."""
    _write(state_file, artifact_id="dash-1", saved_at=_iso(),
           url="https://claude.ai/artifact/dash-1", armed=True,
           webhook_secret="should-never-be-here")

    loaded = artifact_store.load({}, path=state_file)
    assert loaded == "dash-1"
    assert isinstance(loaded, str)


# --- expiry ----------------------------------------------------------------------------


def test_an_entry_older_than_the_configured_expiry_loads_as_nothing(state_file):
    _write(state_file, artifact_id="dash-1", saved_at=_iso(days_ago=8))
    assert artifact_store.load({"dashboard_artifact_ttl_days": 7}, path=state_file) is None


def test_an_entry_within_the_configured_expiry_loads_as_the_identifier(state_file):
    _write(state_file, artifact_id="dash-1", saved_at=_iso(days_ago=3))
    assert artifact_store.load({"dashboard_artifact_ttl_days": 7},
                               path=state_file) == "dash-1"


def test_the_expiry_falls_back_to_thirty_days_when_the_key_is_absent(state_file):
    _write(state_file, artifact_id="dash-1", saved_at=_iso(days_ago=8))
    assert artifact_store.load({}, path=state_file) == "dash-1"

    _write(state_file, artifact_id="dash-1", saved_at=_iso(days_ago=40))
    assert artifact_store.load({}, path=state_file) is None


def test_an_expiry_of_zero_days_expires_immediately(state_file):
    """The operator's off switch: zero means every pointer is already stale."""
    artifact_store.save("dash-1", path=state_file)
    assert artifact_store.load({"dashboard_artifact_ttl_days": 0}, path=state_file) is None


def test_an_unreadable_expiry_setting_falls_back_rather_than_raising(state_file):
    _write(state_file, artifact_id="dash-1", saved_at=_iso(days_ago=3))
    for junk in ("thirty", None, [], {"days": 30}):
        assert artifact_store.load({"dashboard_artifact_ttl_days": junk},
                                   path=state_file) == "dash-1"


# --- save ------------------------------------------------------------------------------


def test_saving_writes_exactly_two_fields(state_file):
    artifact_store.save("dash-1", path=state_file)
    document = json.loads(state_file.read_text())

    assert set(document) == {"artifact_id", "saved_at"}
    assert document["artifact_id"] == "dash-1"


def test_saving_stamps_a_current_timestamp_it_can_read_back(state_file):
    artifact_store.save("dash-1", path=state_file)
    saved_at = datetime.fromisoformat(json.loads(state_file.read_text())["saved_at"])

    assert saved_at.tzinfo is not None, "the stamp must be timezone-aware"
    assert abs((datetime.now(timezone.utc) - saved_at).total_seconds()) < 60


def test_saving_with_an_extra_field_raises_rather_than_persisting_it(state_file):
    """D-09b's whole point. The plausible next commit is `save(id, url=...)`."""
    with pytest.raises(ValueError):
        artifact_store.save("dash-1", path=state_file, url="https://claude.ai/x")
    with pytest.raises(ValueError):
        artifact_store.save("dash-1", path=state_file, armed=True)

    assert not state_file.exists(), "a rejected save must write nothing at all"


def test_saving_refuses_an_empty_identifier(state_file):
    with pytest.raises(ValueError):
        artifact_store.save("", path=state_file)
    assert not state_file.exists()


def test_saving_creates_the_state_directory_if_it_is_not_there(tmp_path):
    nested = tmp_path / "state" / "dashboard_artifact.json"
    artifact_store.save("dash-1", path=nested)
    assert nested.exists()


def test_saving_replaces_rather_than_accumulating(state_file):
    artifact_store.save("dash-1", path=state_file)
    artifact_store.save("dash-2", path=state_file)

    document = json.loads(state_file.read_text())
    assert document["artifact_id"] == "dash-2"
    assert set(document) == {"artifact_id", "saved_at"}


def test_nothing_written_carries_a_secret_a_url_or_a_record_identifier(state_file,
                                                                      fake_config):
    artifact_store.save("dash-1", config=fake_config, path=state_file)
    written = state_file.read_text()

    for value in fake_config.values():
        if isinstance(value, str) and value:
            assert value not in written
    assert "http" not in written
    assert "hs_object_id" not in written


# --- collect ---------------------------------------------------------------------------


def test_the_collection_step_deletes_an_expired_state_file(state_file):
    _write(state_file, artifact_id="dash-1", saved_at=_iso(days_ago=40))
    artifact_store.collect({}, path=state_file)
    assert not state_file.exists()


def test_the_collection_step_leaves_an_unexpired_state_file_untouched(state_file):
    artifact_store.save("dash-1", path=state_file)
    before = state_file.read_text()

    artifact_store.collect({}, path=state_file)
    assert state_file.exists()
    assert state_file.read_text() == before


def test_the_collection_step_on_a_missing_file_is_a_no_op(state_file):
    artifact_store.collect({}, path=state_file)  # must not raise
    assert not state_file.exists()


def test_the_collection_step_deletes_a_malformed_file(state_file):
    """Unreadable is indistinguishable from expired in effect — clear it rather than
    leaving a pointer nothing can ever use."""
    state_file.write_text("{not json at all", encoding="utf-8")
    artifact_store.collect({}, path=state_file)
    assert not state_file.exists()


# --- where the file lives --------------------------------------------------------------


def test_the_resolved_state_path_is_not_a_dotfile(state_file):
    """Phase 23 D-04: a dotfile is unreadable to tooling in this environment, so this is
    an environment constraint rather than a naming preference — and it is a constraint
    on the FILENAME, not on every ancestor directory. Before 33-03 this asserted no
    PATH PART started with a dot, which held only because the pointer lived inside
    `PLUGIN_ROOT/state/`; the durable home is `~/.claude/plugins/data/...`, which is
    itself under a dot directory, and the plugin's own install root already sits under
    `~/.claude/plugins/cache/` — a dot-prefixed ancestor was never what D-04 was
    protecting against, and narrowing to `path.name` is the only form of this
    assertion that can be true both before and after this phase's move."""
    path = Path(artifact_store.state_path())
    assert not path.name.startswith(".")


def _point_at_a_fake_durable_home(monkeypatch, tmp_path):
    """Isolation for the two location tests below: `CLAUDE_PLUGIN_DATA` is
    `durable_paths.durable_dir()`'s own env override, so setting it is enough to make
    `state_path()` resolve to a durable directory deterministically — WITHOUT touching
    this machine's real `~/.claude` (critical constraint: every test builds isolated
    state under `tmp_path`, never the operator's real state). Needed because in a bare
    repo checkout `PLUGIN_ROOT.parent` holds no version-named siblings to migrate and
    the real `~/.claude/plugins/data/...` does not exist either, so an un-isolated call
    would fall through resolution to the legacy path and assert the opposite of what
    these tests exist to prove."""
    fake_durable = tmp_path / "durable"
    fake_durable.mkdir()
    (fake_durable / "dashboard_artifact.json").write_text("{}")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(fake_durable))


def test_the_resolved_state_path_sits_outside_the_plugin_directory(monkeypatch, tmp_path):
    """This is the exact inverse of what this test asserted before 33-03 — and that is
    the point: a pointer living inside `PLUGIN_ROOT` (the versioned install directory)
    is exactly what made STATUS-05 silently false since the first plugin update, since
    every update discards its predecessor's install directory whole. Asserting the
    negative here means a future refactor that quietly puts the pointer back under
    `PLUGIN_ROOT/state/` fails loudly in this test rather than in an operator's next
    session."""
    _point_at_a_fake_durable_home(monkeypatch, tmp_path)
    assert PLUGIN_ROOT not in Path(artifact_store.state_path()).parents


def test_the_resolved_state_path_is_outside_the_repository_working_tree(monkeypatch, tmp_path):
    """Before 33-03 this shelled out to `git check-ignore`, which asserted the state
    path was gitignored (T-27-24) — but `git check-ignore` ERRORS on a path outside the
    working tree entirely, which is exactly where the durable home now resolves to.
    Asserting the path is outside `REPO_ROOT` is strictly stronger than asserting it is
    gitignored: a file git cannot see at all cannot be committed by any accident that a
    `.gitignore` entry alone would only prevent by convention (a stray `git add -f`
    still works on a gitignored-but-present file; it cannot work on a file that isn't
    under the repo root at all)."""
    _point_at_a_fake_durable_home(monkeypatch, tmp_path)
    assert REPO_ROOT not in Path(artifact_store.state_path()).parents


def test_the_store_exposes_exactly_load_save_and_collect():
    """Keeps the module from growing a fourth verb that writes something else."""
    public = {name for name in vars(artifact_store)
              if not name.startswith("_") and callable(getattr(artifact_store, name))
              and getattr(getattr(artifact_store, name), "__module__", None)
              == "artifact_store"}
    assert public == {"load", "save", "collect", "state_path"}


# --- entrypoint (subprocess), across a simulated version bump — 33-03 Task 2 --------
#
# Every test above calls load()/save() with an explicit path=, which is exactly the
# unit-level style criterion 5 identifies as insufficient for DEFAULT-path behaviour —
# and default-path behaviour is the entire subject of this phase (33-CONTEXT.md's own
# lesson, learned twice already this week: pin behaviour at the layer the operator
# actually reaches). These drive artifact_store.py's __main__ as a real subprocess.


def _run_store(argv, tmp_path, home=None, version="0.7.0"):
    """Run scripts/artifact_store.py as the skill runs it — a real subprocess against
    an isolated plugin-cache layout, mirroring test_config_gate.py::_run_cli.

    `artifact_store`'s `__main__` imports `config_gate`, which imports `durable_paths`
    — so all THREE modules are copied into the throwaway `<version>/scripts/`
    directory. A one- or two-module copy dies on ImportError the moment the subprocess
    re-imports config_gate.

    `home` lets two calls share ONE fake HOME across different version directories —
    that sharing is the whole point of the version-bump test below. Defaults to a
    fresh `tmp_path / "home"` when omitted.

    The subprocess env is a literal dict (`PATH` + the fake `HOME`), never
    `{**os.environ, ...}` — the same reason `_run_cli` builds it that way: the real
    `HOME` must never reach the subprocess, or a durable-home test could pass for the
    wrong reason.
    """
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    fake_home = home if home is not None else tmp_path / "home"
    fake_home.mkdir(parents=True, exist_ok=True)

    version_dir = (fake_home / ".claude" / "plugins" / "cache" / "lightning-visuals-operator"
                   / "operator-claude-plugin" / version)
    (version_dir / "scripts").mkdir(parents=True, exist_ok=True)
    for module in ("artifact_store.py", "config_gate.py", "durable_paths.py"):
        shutil.copyfile(scripts_dir / module, version_dir / "scripts" / module)

    run_env = {"PATH": os.environ.get("PATH", ""), "HOME": str(fake_home)}

    return subprocess.run([sys.executable, "artifact_store.py", *argv],
                          capture_output=True, text=True,
                          cwd=str(version_dir / "scripts"), env=run_env)


def _durable_state_target(home):
    return (home / ".claude" / "plugins" / "data"
           / "operator-claude-plugin-lightning-visuals-operator" / "dashboard_artifact.json")


def test_durable_home_lets_a_newer_version_load_what_an_older_version_saved(tmp_path):
    """STATUS-05's cross-session guarantee — "a brand-new conversation lands on the
    SAME dashboard URL, not a second one" — proven across a SIMULATED PLUGIN UPDATE.
    This was silently false since the first update before this phase: no install
    directory on the operator's machine held a pointer (33-CONTEXT.md's measured
    finding). 0.6.2 saves; 0.7.0 — a different install directory with no state/ of its
    own — reads the same identifier back, because 0.7.0's own resolution runs the
    sibling-scan migration (33-02) against 0.6.2's legacy pointer, exactly as it
    already does for the config."""
    home = tmp_path / "home"
    save_proc = _run_store(["save", "dash-abc"], tmp_path, home=home, version="0.6.2")
    assert save_proc.returncode == 0, save_proc.stderr

    load_proc = _run_store(["load"], tmp_path, home=home, version="0.7.0")
    assert load_proc.returncode == 0, load_proc.stderr
    payload = json.loads(load_proc.stdout)
    assert payload["artifact_id"] == "dash-abc"


def test_durable_load_on_a_fresh_home_with_nothing_anywhere_is_null_not_an_error(tmp_path):
    """A missing pointer is not an error — the ordinary first-ever-open case."""
    proc = _run_store(["load"], tmp_path)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["artifact_id"] is None


def test_durable_collect_with_no_config_present_still_runs_and_exits_zero(tmp_path):
    """The pointer is local state; a missing config must not stop collection — the
    status skill's own step 1 is what refuses in plain language, not this one."""
    proc = _run_store(["collect"], tmp_path)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True


def test_durable_save_lands_in_the_durable_directory_not_either_version_directory(tmp_path):
    """Positive statement of where the pointer goes once the durable home is already
    established (here, by the same migration test 1 above exercises). A future
    refactor that quietly puts it back under `PLUGIN_ROOT/state/` fails loudly HERE
    rather than in an operator's next session."""
    home = tmp_path / "home"
    _run_store(["save", "dash-first"], tmp_path, home=home, version="0.6.2")
    _run_store(["load"], tmp_path, home=home, version="0.7.0")  # migrates 0.6.2's pointer up

    proc = _run_store(["save", "dash-second"], tmp_path, home=home, version="0.7.0")
    assert proc.returncode == 0, proc.stderr

    durable_target = _durable_state_target(home)
    assert durable_target.exists()
    assert json.loads(durable_target.read_text())["artifact_id"] == "dash-second"

    for version in ("0.6.2", "0.7.0"):
        version_state = (home / ".claude" / "plugins" / "cache" / "lightning-visuals-operator"
                         / "operator-claude-plugin" / version / "state" / "dashboard_artifact.json")
        assert not version_state.exists(), f"the pointer must not be sitting in {version}'s own directory"
