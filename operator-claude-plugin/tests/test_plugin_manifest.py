"""Tests for the plugin manifest and its one skill (PLUGIN-01, D-02, D-14b).

Verifies the packaging shape a plugin skill already gets for free: it is both
auto-triggered and slash-invocable as /operator-claude-plugin:contact-upload, with no
separate commands/ directory duplicating that entry point.
"""
import json
import re
from pathlib import Path

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
SKILL_PATH = PLUGIN_ROOT / "skills" / "contact-upload" / "SKILL.md"


def test_manifest_parses_and_has_the_required_keys():
    data = json.loads(MANIFEST_PATH.read_text())
    assert {"name", "description", "version", "author"} <= set(data)


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


def _skill_frontmatter() -> dict:
    text = SKILL_PATH.read_text()
    assert text.startswith("---"), "SKILL.md must open with YAML frontmatter"
    _, frontmatter, _ = text.split("---", 2)
    return yaml.safe_load(frontmatter)


def test_skill_exists_with_parseable_frontmatter_carrying_name_and_description():
    frontmatter = _skill_frontmatter()
    assert {"name", "description"} <= set(frontmatter)


def test_skill_body_references_only_scripts_that_exist_on_disk():
    text = SKILL_PATH.read_text()
    referenced = set(re.findall(r"scripts/(\w+\.py)", text))
    assert referenced, "expected the skill body to reference at least one script"
    for script in referenced:
        assert (PLUGIN_ROOT / "scripts" / script).exists(), (
            f"SKILL.md references scripts/{script}, which does not exist on disk"
        )
