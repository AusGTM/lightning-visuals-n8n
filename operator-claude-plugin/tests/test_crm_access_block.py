"""Phase 73.1 Plan 04 Task 2 (D-14a/D-14b/D-14d, D-15a/D-15b/D-15c/D-15d).

Markdown has no include mechanism, so "one shared CRM-access block" is implemented as
one canonical source file (`config/crm_access_block.md`) plus this grep test, which
pins that every skill carries it verbatim — D-14d's own wording. File-discovery and
failure-message shape follow `test_mandatory_report_call_sites.py`'s existing idiom
rather than inventing a second one.
"""
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
BLOCK_PATH = PLUGIN_ROOT / "config" / "crm_access_block.md"

OPENING_MARKER = "<!-- CRM-ACCESS-BLOCK v1 (D-14a/D-14b/D-14d, D-15a/D-15b/D-15c/D-15d) -->"


def _skill_paths():
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def _block_text():
    return BLOCK_PATH.read_text(encoding="utf-8")


def test_every_skill_carries_the_crm_access_block():
    skill_paths = _skill_paths()
    assert len(skill_paths) == 11, (
        f"expected 11 skills, found {len(skill_paths)}: {skill_paths}")

    block_lines = [line for line in _block_text().splitlines() if line.strip()]

    for path in skill_paths:
        text = path.read_text(encoding="utf-8")
        for line in block_lines:
            assert line in text, (
                f"{path.relative_to(PLUGIN_ROOT)} is missing shared CRM-access line: "
                f"{line!r}")


def test_the_shared_block_states_the_portal_rule():
    text = _block_text()
    assert "22617666" in text
    assert "stop" in text.lower()
    assert "lookup proof" in text


def test_the_shared_block_states_the_session_grant_rule():
    text = _block_text()
    assert "covers(" in text
    assert "widen" in text
    assert "revoke" in text
    assert "one sentence" in text


def test_no_skill_carries_a_second_copy_of_the_rule():
    for path in _skill_paths():
        text = path.read_text(encoding="utf-8")
        count = text.count(OPENING_MARKER)
        assert count == 1, (
            f"{path.relative_to(PLUGIN_ROOT)} carries the opening marker {count} "
            f"time(s), expected exactly 1")


def test_the_shared_block_lives_outside_skills():
    assert BLOCK_PATH.exists(), f"canonical block missing at {BLOCK_PATH}"

    for entry in SKILLS_DIR.iterdir():
        if entry.is_dir():
            assert (entry / "SKILL.md").exists(), (
                f"{entry.relative_to(PLUGIN_ROOT)} has no SKILL.md — the plugin loader "
                f"enumerates skill directories, so a source file parked here risks "
                f"being read as a broken skill")
