"""operator-claude-plugin/tests/test_sweep_shim.py

Tests for the durable-home launcher shim (D-63-01). The tracer test
(`test_shim_execs_the_newest_installed_wrapper_end_to_end`) runs the REAL `/bin/sh`
shim as a subprocess against a temporary fake cache root — not mocked — because the
shim's entire job is process routing (bootstrap -> resolve -> exec), which a stubbed
version-resolution call would not actually prove.

Task 2 adds the staleness self-check tests to this same file (wrapper-state tests
driving the real `lv-sweep-run.sh`).
"""
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import durable_paths
import sweep_shim

REPO_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _stub_wrapper_text(record_file: Path) -> str:
    """A `/bin/sh` stand-in for `lv-sweep-run.sh` that records its own invocation
    (`$0 $1 $2 $3`) instead of running a real sweep, and exits 0."""
    quoted = "'" + str(record_file).replace("'", "'\\''") + "'"
    return (
        "#!/bin/sh\n"
        "set -u\n"
        'printf \'%s %s %s %s\\n\' "$0" "$1" "$2" "$3" >> ' + quoted + "\n"
        "exit 0\n"
    )


def _make_fake_install(cache_root: Path, version: str, record_file: Path) -> Path:
    """A fake version directory carrying REAL copies of sweep_shim.py and
    durable_paths.py (so the shim's bootstrap and `--newest` calls run against the
    real resolution logic, not a stub) plus a stubbed lv-sweep-run.sh."""
    install = cache_root / version
    scripts_dir = install / "scripts"
    scripts_dir.mkdir(parents=True)
    shutil.copy(REPO_SCRIPTS_DIR / "sweep_shim.py", scripts_dir / "sweep_shim.py")
    shutil.copy(REPO_SCRIPTS_DIR / "durable_paths.py", scripts_dir / "durable_paths.py")

    wrapper_dir = install / "skills" / "backend-sweep"
    wrapper_dir.mkdir(parents=True)
    wrapper = wrapper_dir / "lv-sweep-run.sh"
    wrapper.write_text(_stub_wrapper_text(record_file))
    wrapper.chmod(0o700)
    return install


def _make_candidate_dir(cache_root: Path, version: str) -> Path:
    """The minimum a directory needs to be a `newest_install_root` candidate: a
    version-shaped name and the wrapper marker file. Lighter than
    `_make_fake_install` for unit-level tests that never invoke the shim itself."""
    install = cache_root / version
    (install / "skills" / "backend-sweep").mkdir(parents=True)
    (install / "skills" / "backend-sweep" / "lv-sweep-run.sh").write_text("#!/bin/sh\n")
    return install


def test_shim_execs_the_newest_installed_wrapper_end_to_end(tmp_path):
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    record_file = tmp_path / "record.txt"

    _make_fake_install(cache_root, "1.0.0", record_file)
    _make_fake_install(cache_root, "1.1.0", record_file)

    durable = tmp_path / "durable"
    shim = sweep_shim.install_shim(cache_root=cache_root, durable=durable)
    shim_bytes_before = shim.read_bytes()
    shim_mode_before = stat.S_IMODE(shim.stat().st_mode)

    legacy_root = "some-legacy-root-the-shim-ignores"
    log_path = tmp_path / "sweep.log"

    result = subprocess.run(
        ["/bin/sh", str(shim), legacy_root, sys.executable, str(log_path)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr

    newest_wrapper = cache_root / "1.1.0" / "skills" / "backend-sweep" / "lv-sweep-run.sh"
    recorded = record_file.read_text().strip().splitlines()
    assert len(recorded) == 1
    fields = recorded[0].split(" ")
    assert fields[0] == str(newest_wrapper)
    assert fields[1] == str(cache_root / "1.1.0")

    # Update simulation: a newer version appears, the SAME shim is re-invoked with no
    # edit to the shim or the schedule, and the resolved root moves.
    _make_fake_install(cache_root, "1.2.0", record_file)
    result2 = subprocess.run(
        ["/bin/sh", str(shim), legacy_root, sys.executable, str(log_path)],
        capture_output=True, text=True, timeout=30,
    )
    assert result2.returncode == 0, result2.stderr

    recorded2 = record_file.read_text().strip().splitlines()
    assert len(recorded2) == 2
    fields2 = recorded2[1].split(" ")
    assert fields2[1] == str(cache_root / "1.2.0")

    assert shim.read_bytes() == shim_bytes_before
    assert stat.S_IMODE(shim.stat().st_mode) == shim_mode_before


def test_install_shim_is_idempotent(tmp_path):
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    durable = tmp_path / "durable"

    first = sweep_shim.install_shim(cache_root=cache_root, durable=durable)
    first_bytes = first.read_bytes()
    first_mode = stat.S_IMODE(first.stat().st_mode)
    assert first_mode == 0o700

    second = sweep_shim.install_shim(cache_root=cache_root, durable=durable)
    assert second == first
    assert second.read_bytes() == first_bytes
    assert stat.S_IMODE(second.stat().st_mode) == first_mode


def test_newest_install_root_returns_none_for_empty_cache_root(tmp_path):
    cache_root = tmp_path / "empty"
    cache_root.mkdir()
    assert sweep_shim.newest_install_root(cache_root) is None


def test_newest_install_root_returns_none_for_missing_cache_root(tmp_path):
    ghost = tmp_path / "does-not-exist"
    assert sweep_shim.newest_install_root(ghost) is None


def test_version_ordering_is_not_reimplemented(tmp_path, monkeypatch):
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    _make_candidate_dir(cache_root, "1.0.0")

    def _boom(name):
        raise RuntimeError("version ordering must live in durable_paths, not sweep_shim")

    monkeypatch.setattr(durable_paths, "_version_key", _boom)
    with pytest.raises(RuntimeError):
        sweep_shim.newest_install_root(cache_root)


def test_symlink_escaping_cache_root_is_skipped(tmp_path):
    """T-63-01: a symlink inside the (user-writable) cache root must not redirect the
    shim's exec target outside the plugin tree."""
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    outside = tmp_path / "outside" / "9.9.9"
    (outside / "skills" / "backend-sweep").mkdir(parents=True)
    (outside / "skills" / "backend-sweep" / "lv-sweep-run.sh").write_text("#!/bin/sh\n")

    (cache_root / "9.9.9").symlink_to(outside)

    assert sweep_shim.newest_install_root(cache_root) is None


def test_shim_text_shape():
    text = sweep_shim.shim_text("/some/cache/root")
    lines = text.splitlines()
    assert lines[0] == "#!/bin/sh"
    assert lines[1] == "set -u"
    assert "--newest" in text
    assert "exec" in text


def test_main_newest_prints_nothing_and_returns_1_when_unresolved(tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    rc = sweep_shim.main(["--newest", "--cache-root", str(empty)])
    assert rc == 1
    assert capsys.readouterr().out == ""
