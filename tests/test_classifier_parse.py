# Regression tests for the live-path JSON parsing in the Haiku classifier.
# The live SDK returns `msg.content` as a LIST of blocks (content[0].text), and
# models sometimes wrap JSON in prose or ```json fences. Both broke the verbatim
# SPEC transcription (§12.5/§12.6: `json.loads(msg.content.text)`); these guard the fix.
import pytest
from src.classifier_haiku import _parse_json


def test_parses_bare_json():
    assert _parse_json('{"decision": "promote", "confidence": 90}') == {
        "decision": "promote",
        "confidence": 90,
    }


def test_parses_fenced_json():
    text = 'Here is the result:\n```json\n{"decision": "stage_only"}\n```'
    assert _parse_json(text) == {"decision": "stage_only"}


def test_parses_prose_wrapped_json():
    text = 'The field should be {"decision": "reject", "confidence": 10} based on evidence.'
    assert _parse_json(text) == {"decision": "reject", "confidence": 10}


def test_raises_on_no_json():
    with pytest.raises(ValueError):
        _parse_json("no json here at all")
