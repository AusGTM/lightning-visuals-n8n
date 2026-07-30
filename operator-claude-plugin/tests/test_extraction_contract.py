"""Pins `extraction.md`'s documented artifact schema to `extraction.py`'s real validator
(D-13 — the drift pin). `extraction.md` is instructions for Claude, not documentation about
the plugin, and its fenced JSON examples are executable documentation: this suite parses them
out of the file and runs them through the real validator, so the two halves of the contract
(the prompt half in `extraction.md`, the validation half in `extraction.py`) cannot silently
stop matching each other. This is the only automated defence available, since the extraction
step itself — Claude reading a source in-session — cannot be tested.
"""
import json
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import extraction  # noqa: E402

EXTRACTION_MD = PLUGIN_ROOT / "skills" / "contact-upload" / "extraction.md"


def _extraction_md_text() -> str:
    return EXTRACTION_MD.read_text(encoding="utf-8")


def _fenced_json_blocks(text: str) -> list[dict]:
    """Every ```json ... ``` fenced block in `text`, parsed, in document order. This is the
    "pin": it reads the *rendered* markdown, not a copy kept in the test, so an edit to
    extraction.md's example is exactly what this test re-checks against the real validator."""
    blocks = re.findall(r"```json\s*\n(.*?)```", text, re.DOTALL)
    return [json.loads(block) for block in blocks]


def test_extraction_md_exists_and_is_addressed_to_claude_as_instructions():
    text = _extraction_md_text()
    assert text.strip(), "extraction.md must not be empty"
    assert "you" in text.lower(), "the file must address Claude directly, in the imperative"


def test_first_fenced_example_artifact_is_accepted_by_the_real_validator_with_no_rejects():
    blocks = _fenced_json_blocks(_extraction_md_text())
    assert blocks, "extraction.md must contain at least one fenced JSON example artifact"

    artifact = blocks[0]
    result = extraction.validate(artifact)

    assert len(result.accepted) == 2
    assert result.rejected == []
    assert result.dropped_keys == []
    for record in result.accepted:
        assert record["provenance"]["input"]
        assert record["provenance"]["locator"]


def test_first_fenced_example_carries_the_documented_ambiguity():
    blocks = _fenced_json_blocks(_extraction_md_text())
    artifact = blocks[0]
    result = extraction.validate(artifact)

    assert len(result.ambiguities) == 1
    ambiguity = result.ambiguities[0]
    assert ambiguity["field"] == "jobtitle"


def test_every_canonical_prop_is_named_in_extraction_md():
    text = _extraction_md_text()
    for prop in extraction.canonical_props():
        assert prop in text, f"canonical prop {prop!r} is not named anywhere in extraction.md"


def test_extraction_md_references_extraction_py_as_the_validator_to_run():
    text = _extraction_md_text()
    assert "extraction.py" in text


def test_every_script_path_named_in_extraction_md_exists_on_disk():
    text = _extraction_md_text()
    referenced = set(re.findall(r"scripts/(\w+\.py)", text))
    assert referenced, "expected extraction.md to name at least one script by path"
    for script in referenced:
        assert (SCRIPTS_DIR / script).exists(), (
            f"extraction.md references scripts/{script}, which does not exist on disk"
        )


def test_screenshot_example_artifact_collapses_to_one_row_with_one_carried_ambiguity():
    """The second fenced example: two screenshot-sourced records naming the same person
    (email matches once trimmed/case-folded) but disagreeing on `jobtitle` — one image's
    clipped view reads one character short. Per D-08/D-09, dedupe on the identity rule is
    the validator's job, not something extraction.md instructs Claude to pre-decide; this
    runs the documented example through the real validator (including its dedupe pass) and
    asserts the two records collapse to exactly one accepted row, with the job-title
    disagreement carried through as exactly one ambiguity."""
    blocks = _fenced_json_blocks(_extraction_md_text())
    assert len(blocks) >= 2, "expected a second fenced example artifact for the screenshot case"

    artifact = blocks[1]
    assert artifact["source"]["kind"] == "screenshot"
    assert len(artifact["records"]) == 2, "the documented example starts as two records"

    result = extraction.validate(artifact)

    assert len(result.accepted) == 1, (
        "the two records name the same person and must collapse to one accepted row"
    )
    assert len(result.ambiguities) == 1, (
        "the jobtitle disagreement must be carried through as exactly one ambiguity"
    )
    assert result.ambiguities[0]["field"] == "jobtitle"


def test_extraction_md_states_the_fetch_failed_and_nothing_usable_outcomes_separately():
    text = _extraction_md_text()
    assert "url_not_allowed" in text
    assert "Fetch failed" in text or "fetch failed" in text.lower()
    assert "nothing usable" in text.lower() or "Nothing usable" in text


def test_extraction_md_states_the_no_automated_screenshot_capture_fence():
    text = _extraction_md_text()
    assert "capture" in text.lower()
    assert "web_fetch" in text
