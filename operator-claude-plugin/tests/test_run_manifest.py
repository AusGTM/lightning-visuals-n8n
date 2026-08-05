"""Tests for `run_manifest.py` (Phase 37 Plan 06):

Task 1: the manifest file itself — its own artifact, its own schema, its own refusal,
beside the dashboard pointer and never inside `artifact_store.py`.

Isolation mirrors `test_artifact_store.py`: `CLAUDE_PLUGIN_DATA` pointed at a `tmp_path`,
never real `~/.claude`. Most tests pass an explicit `path=` (the unit-level style used
throughout this suite); the two location tests below isolate via the env var instead,
since `manifest_path()`'s own default-path resolution is what they exercise.
"""
import json
import stat

import pytest

import artifact_store
import durable_paths
import run_manifest

# =====================================================================================
# Task 1a: manifest_path() — its own file, beside the dashboard pointer
# =====================================================================================


def _point_at_a_fake_durable_home(monkeypatch, tmp_path):
    """Mirrors test_artifact_store.py's identically-named helper: CLAUDE_PLUGIN_DATA is
    durable_paths.durable_dir()'s own env override, so setting it resolves state_path()
    deterministically without touching this machine's real ~/.claude."""
    fake_durable = tmp_path / "durable"
    fake_durable.mkdir()
    (fake_durable / "dashboard_artifact.json").write_text("{}")
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(fake_durable))


def test_manifest_path_shares_a_parent_with_the_dashboard_pointer_but_not_its_name(
        monkeypatch, tmp_path):
    _point_at_a_fake_durable_home(monkeypatch, tmp_path)
    manifest = run_manifest.manifest_path()
    dashboard = artifact_store.state_path()

    assert manifest != dashboard
    assert manifest.parent == dashboard.parent


def test_manifest_path_is_not_a_dotfile(monkeypatch, tmp_path):
    _point_at_a_fake_durable_home(monkeypatch, tmp_path)
    assert not run_manifest.manifest_path().name.startswith(".")


# =====================================================================================
# Task 1b: save() — the schema, the refusal
# =====================================================================================


def test_save_then_load_round_trips_the_verdicts(tmp_path):
    target = tmp_path / "run_manifest.json"
    verdicts = {"row-1": "matched", "row-2": "held"}

    run_manifest.save("run-abc", verdicts, path=target)

    assert run_manifest.load(path=target) == verdicts


def test_save_writes_at_mode_0600(tmp_path):
    target = tmp_path / "run_manifest.json"
    run_manifest.save("run-abc", {"row-1": "matched"}, path=target)

    mode = stat.S_IMODE(target.stat().st_mode)
    assert mode == 0o600


def test_save_refuses_a_verdict_outside_the_four_allowed_words(tmp_path):
    target = tmp_path / "run_manifest.json"
    with pytest.raises(run_manifest.ManifestError):
        run_manifest.save("run-abc", {"row-1": "definitely_not_a_verdict"}, path=target)
    assert not target.exists()


def test_save_refuses_an_arming_shaped_verdict_and_writes_nothing(tmp_path):
    target = tmp_path / "run_manifest.json"
    with pytest.raises(run_manifest.ManifestError):
        run_manifest.save("run-abc", {"r1": "armed"}, path=target)
    assert not target.exists()


def test_save_refuses_an_arming_shaped_key_naming_the_offending_key(tmp_path):
    target = tmp_path / "run_manifest.json"
    with pytest.raises(run_manifest.ManifestError) as exc:
        run_manifest.save("run-abc", {"armed_batch": "matched"}, path=target)
    assert "armed_batch" in str(exc.value)
    assert not target.exists()


def test_save_refuses_a_secret_shaped_key(tmp_path):
    target = tmp_path / "run_manifest.json"
    with pytest.raises(run_manifest.ManifestError) as exc:
        run_manifest.save("run-abc", {"webhook_secret": "matched"}, path=target)
    assert "webhook_secret" in str(exc.value)
    assert not target.exists()


def test_save_refuses_an_api_key_shaped_key(tmp_path):
    target = tmp_path / "run_manifest.json"
    with pytest.raises(run_manifest.ManifestError):
        run_manifest.save("run-abc", {"n8n_api_key": "matched"}, path=target)
    assert not target.exists()


def test_a_rejected_save_leaves_a_previously_saved_manifest_untouched(tmp_path):
    target = tmp_path / "run_manifest.json"
    run_manifest.save("run-1", {"row-1": "matched"}, path=target)
    before = target.read_text()

    with pytest.raises(run_manifest.ManifestError):
        run_manifest.save("run-2", {"row-2": "armed"}, path=target)

    assert target.read_text() == before


def test_a_save_that_fails_partway_leaves_the_previous_manifest_readable(
        tmp_path, monkeypatch):
    """The atomic-write property, not the validation guard above: even a WRITE-time
    failure (disk full, permission yanked mid-write) must not corrupt what was already
    on disk. Forces the failure inside durable_paths._atomic_write_0600's own
    os.replace, which is the last step of that pattern — everything before it touches
    only a temp file, so a failure there proves the whole target file, not just a
    validation guard, is what stays intact."""
    target = tmp_path / "run_manifest.json"
    run_manifest.save("run-1", {"row-1": "matched"}, path=target)
    before = target.read_text()

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(durable_paths.os, "replace", _boom)

    with pytest.raises(OSError):
        run_manifest.save("run-2", {"row-1": "enriched"}, path=target)

    assert target.read_text() == before


# =====================================================================================
# Task 1c: load() — every failure degrades to "no manifest"
# =====================================================================================


def test_load_on_a_missing_file_returns_empty_without_raising(tmp_path):
    target = tmp_path / "run_manifest.json"
    assert not target.exists()
    assert run_manifest.load(path=target) == {}


def test_load_on_malformed_json_returns_empty_without_raising(tmp_path):
    target = tmp_path / "run_manifest.json"
    target.write_text("not json", encoding="utf-8")
    assert run_manifest.load(path=target) == {}


def test_load_on_a_file_that_is_not_a_mapping_returns_empty(tmp_path):
    target = tmp_path / "run_manifest.json"
    target.write_text(json.dumps(["row-1", "matched"]), encoding="utf-8")
    assert run_manifest.load(path=target) == {}


def test_load_on_a_manifest_missing_the_verdicts_field_returns_empty(tmp_path):
    target = tmp_path / "run_manifest.json"
    target.write_text(json.dumps({"run_id": "run-1", "saved_at": "2026-08-05T00:00:00Z"}),
                      encoding="utf-8")
    assert run_manifest.load(path=target) == {}


def test_load_on_a_verdicts_map_carrying_an_invalid_word_returns_empty_not_partial(
        tmp_path):
    """One bad entry degrades the WHOLE manifest — never a partially-trusted map that
    silently drops just the bad row."""
    target = tmp_path / "run_manifest.json"
    target.write_text(json.dumps({
        "run_id": "run-1", "saved_at": "2026-08-05T00:00:00Z",
        "verdicts": {"row-1": "matched", "row-2": "not_a_real_verdict"},
    }), encoding="utf-8")
    assert run_manifest.load(path=target) == {}


def test_load_on_a_truncated_manifest_returns_empty(tmp_path):
    target = tmp_path / "run_manifest.json"
    run_manifest.save("run-1", {"row-1": "matched", "row-2": "enriched"}, path=target)
    full_text = target.read_text()
    target.write_text(full_text[:len(full_text) // 2], encoding="utf-8")

    assert run_manifest.load(path=target) == {}


# =====================================================================================
# The two artifacts are genuinely separate stores
# =====================================================================================


def test_saving_the_manifest_never_touches_the_dashboard_pointer_file(
        monkeypatch, tmp_path):
    _point_at_a_fake_durable_home(monkeypatch, tmp_path)
    dashboard_path = artifact_store.state_path()
    before = dashboard_path.read_text()

    run_manifest.save("run-1", {"row-1": "matched"})

    assert dashboard_path.read_text() == before
    assert run_manifest.manifest_path().exists()


def test_the_module_exposes_no_fourth_verb():
    """Keeps the module from growing an accidental extra write path — mirrors
    test_artifact_store.py's own 'exactly load/save/collect' guard, minus collect (this
    manifest has no TTL/GC concept; a stale manifest is just superseded by the next
    save)."""
    import inspect

    public = {name for name in vars(run_manifest)
              if not name.startswith("_") and inspect.isfunction(getattr(run_manifest, name))
              and getattr(run_manifest, name).__module__ == "run_manifest"}
    assert public == {"manifest_path", "save", "load"}
