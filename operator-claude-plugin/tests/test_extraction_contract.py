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
