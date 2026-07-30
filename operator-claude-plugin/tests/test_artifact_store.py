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
import subprocess
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
    an environment constraint rather than a naming preference."""
    path = Path(artifact_store.state_path())
    assert not path.name.startswith(".")
    for part in path.parts:
        assert not part.startswith("."), part


def test_the_resolved_state_path_sits_inside_the_plugin_directory():
    assert PLUGIN_ROOT in Path(artifact_store.state_path()).parents


def test_the_resolved_state_path_is_ignored_by_version_control():
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(artifact_store.state_path())],
        cwd=REPO_ROOT, capture_output=True)
    assert result.returncode == 0, (
        "the state file must be gitignored — a committed pointer is a tampering surface "
        "(T-27-24)")


def test_the_store_exposes_exactly_load_save_and_collect():
    """Keeps the module from growing a fourth verb that writes something else."""
    public = {name for name in vars(artifact_store)
              if not name.startswith("_") and callable(getattr(artifact_store, name))
              and getattr(getattr(artifact_store, name), "__module__", None)
              == "artifact_store"}
    assert public == {"load", "save", "collect", "state_path"}
