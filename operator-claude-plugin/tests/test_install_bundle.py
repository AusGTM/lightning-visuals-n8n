"""The operator install bundle (install/) — the one surface a non-technical operator runs.

Pins three things a broken bundle would silently get wrong:
  - the installer parses under the bash that ships with macOS (3.2 — no mapfile,
    no ${var,,}, no associative arrays), because `bash install.sh` is the documented path;
  - nothing tracked still points at the retired double-click `install.command`, which
    macOS Gatekeeper blocks for a user who cannot grant the "open anyway" permission;
  - the installer never persists ALLOW_N8N_ARM: that is the headless/cron authority
    (D-34, D-53-01) and writing it into ~/.claude/settings.json's `env` would pre-authorise
    every desktop session past the allow_write_grants chain.
"""
import re
import subprocess
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PLUGIN_ROOT.parent
INSTALLER = PLUGIN_ROOT / "install" / "install.sh"


def test_installer_exists_and_parses_under_system_bash():
    assert INSTALLER.is_file()
    subprocess.run(["/bin/bash", "-n", str(INSTALLER)], check=True)


def test_installer_uses_no_bash4_only_constructs():
    text = INSTALLER.read_text()
    for needle in ("mapfile", "readarray", "declare -A", ",,}", "^^}"):
        assert needle not in text, f"{needle!r} is bash 4+; macOS ships bash 3.2"


def test_installer_never_persists_the_headless_arm_authority():
    text = INSTALLER.read_text()
    # It may NAME the variable in a comment explaining why it is not set; it must never
    # assign or export it, and must never write an "env" object into settings.json.
    assert not re.search(r"^\s*(export\s+)?ALLOW_N8N_ARM=", text, re.M)
    assert '"env"' not in text


def test_installer_installs_the_cli_when_only_the_desktop_app_is_present():
    text = INSTALLER.read_text()
    assert "curl -fsSL https://claude.ai/install.sh | bash" in text
    assert "xcode-select --install" in text


def test_installer_sweeps_only_the_registry_installed_version():
    text = INSTALLER.read_text()
    assert "claude plugin list --json" in text, "sweep must read Claude Code's own registry"
    assert "sort -V" not in text, "newest-folder is not installed-folder (the 0.14.0 incident)"
    assert 'rm -rf "$d"' in text and '[ "$d" != "$INSTALLED" ]' in text


def test_no_tracked_file_still_names_the_retired_double_click_installer():
    tracked = subprocess.run(
        ["git", "ls-files", "operator-claude-plugin", "docs", "README.md", "tests/demo-adversarial"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout.split()
    hits = []
    for rel in tracked:
        if rel.endswith("CHANGELOG.md") or (REPO_ROOT / rel).resolve() == Path(__file__).resolve():
            continue  # history may name it; this test names it by definition
        p = REPO_ROOT / rel
        try:
            if "install.command" in p.read_text():
                hits.append(rel)
        except (UnicodeDecodeError, IsADirectoryError):
            continue
    assert not hits, hits
