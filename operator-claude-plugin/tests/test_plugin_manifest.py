"""Tests for the plugin manifest and EVERY skill (PLUGIN-01, D-02, D-14b).

Verifies the packaging shape a plugin skill already gets for free: it is both
auto-triggered and slash-invocable, with no separate commands/ directory duplicating
that entry point.

Widened by 28-05 Task 2 from a hardcoded contact-upload path to a glob over
skills/*/SKILL.md: the hardcoded form silently skipped every skill added after 23-04 —
by widening day that was five of the six. The glob is asserted non-empty first, because
a glob matching nothing passes vacuously, which is how this kind of widening quietly
stops testing anything.
"""
import json
import re
from pathlib import Path

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
SKILL_PATHS = sorted(PLUGIN_ROOT.glob("skills/*/SKILL.md"))


def test_the_skill_glob_is_not_vacuous():
    assert len(SKILL_PATHS) >= 3, (
        f"expected at least contact-upload, backend-status and backend-control; "
        f"found {[p.parent.name for p in SKILL_PATHS]}"
    )


def test_manifest_parses_and_has_the_required_keys():
    data = json.loads(MANIFEST_PATH.read_text())
    assert {"name", "description", "version", "author"} <= set(data)
    # `claude plugin validate` rejects a bare string here; asserting presence alone let
    # that through and A1 caught it live (23-06 Section A).
    assert isinstance(data["author"], dict), "author must be an object, not a string"
    assert data["author"].get("name"), "author.name must be non-empty"


def test_claude_plugin_directory_contains_only_the_manifest():
    entries = [p.name for p in (PLUGIN_ROOT / ".claude-plugin").iterdir()]
    assert entries == ["plugin.json"], (
        "only plugin.json belongs in .claude-plugin/ — skills/, commands/, agents/, "
        "and hooks/ all live at the plugin root, one level up"
    )


def test_no_commands_directory_exists():
    assert not (PLUGIN_ROOT / "commands").exists(), (
        "a plugin skill is already both auto-triggered and slash-invocable — a "
        "commands/ directory would be a second, redundant entry point (D-14b)"
    )


import pytest


def _skill_frontmatter(path) -> dict:
    text = path.read_text()
    assert text.startswith("---"), f"{path.parent.name}: SKILL.md must open with YAML frontmatter"
    _, frontmatter, _ = text.split("---", 2)
    return yaml.safe_load(frontmatter)


@pytest.mark.parametrize("skill_path", SKILL_PATHS, ids=lambda p: p.parent.name)
def test_every_skill_has_parseable_frontmatter_carrying_name_and_description(skill_path):
    frontmatter = _skill_frontmatter(skill_path)
    assert {"name", "description"} <= set(frontmatter)
    assert frontmatter["name"] == skill_path.parent.name, (
        "the frontmatter name must match the directory, or the slash invocation "
        "documented in the description resolves to nothing"
    )


# Phase 43 Plan 03 (D-06/C3): loss-reason-report is the first skill that shells out to a
# BACKEND-repo script (scripts/build_loss_reason_report.py, in the repo the plugin is a
# thin client for) rather than one of the plugin's own scripts/. Named, not a general
# "allowed sources" mechanism -- one exemption, one comment, one citation, so a future
# skill that quietly starts referencing an unshipped path still fails this guard.
BACKEND_REPO_SCRIPTS = {"loss-reason-report": {"build_loss_reason_report.py"}}


@pytest.mark.parametrize("skill_path", SKILL_PATHS, ids=lambda p: p.parent.name)
def test_every_skill_references_only_scripts_that_exist_on_disk(skill_path):
    text = skill_path.read_text()
    referenced = set(re.findall(r"scripts/(\w+\.py)", text))
    assert referenced, f"{skill_path.parent.name}: expected at least one script reference"
    backend_scripts = BACKEND_REPO_SCRIPTS.get(skill_path.parent.name, set())
    for script in referenced:
        if script in backend_scripts:
            # Must exist in the backend repo's scripts/ (one level up from the plugin
            # root) and must NOT be shadow-copied into the plugin's own scripts/ -- the
            # whole point of shelling out is never forking the backend script.
            assert (PLUGIN_ROOT.parent / "scripts" / script).exists(), (
                f"{skill_path.parent.name}/SKILL.md references backend-repo scripts/{script}, "
                f"which does not exist in the backend repo's scripts/ directory"
            )
            assert not (PLUGIN_ROOT / "scripts" / script).exists(), (
                f"{skill_path.parent.name}/SKILL.md references backend-repo scripts/{script}, "
                f"but a same-named file also exists under the plugin's own scripts/ -- "
                f"this skill must shell out to the backend repo, never a shadow copy"
            )
            continue
        assert (PLUGIN_ROOT / "scripts" / script).exists(), (
            f"{skill_path.parent.name}/SKILL.md references scripts/{script}, "
            f"which does not exist on disk"
        )


def test_no_shipped_document_instructs_a_manual_config_copy():
    """REQUIREMENTS.md's Out-of-Scope line: 'Terminal instructions to the operator are a
    requirement failure.' The code stopped needing a hand-copy of operator.local.json
    between install directories in 33-02 (the sibling-scan migration); this is the second
    side of that pin — a doc that still tells the operator to do it by hand is as much a
    defect as code that requires it.
    """
    for name in ("README.md", "CHANGELOG.md"):
        text = (PLUGIN_ROOT / name).read_text()
        assert "operator.local.json across" not in text, (
            f"{name} still instructs the operator to move operator.local.json by hand "
            f"between install directories — the durable-home migration (33-02) makes "
            f"this both false and unnecessary"
        )
