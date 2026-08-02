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


@pytest.mark.parametrize("skill_path", SKILL_PATHS, ids=lambda p: p.parent.name)
def test_every_skill_references_only_scripts_that_exist_on_disk(skill_path):
    text = skill_path.read_text()
    referenced = set(re.findall(r"scripts/(\w+\.py)", text))
    assert referenced, f"{skill_path.parent.name}: expected at least one script reference"
    for script in referenced:
        assert (PLUGIN_ROOT / "scripts" / script).exists(), (
            f"{skill_path.parent.name}/SKILL.md references scripts/{script}, "
            f"which does not exist on disk"
        )
