"""Tests for extraction.py's rejection/reporting behavior (Task 2): identity pre-flight
separation, non-canonical key reporting, and named artifact-level errors
(STRUCT-02, INGEST-03, INGEST-06)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import extraction  # noqa: E402


def _record(row, provenance=None):
    return {
        "row": row,
        "provenance": provenance
        if provenance is not None
        else {"input": "pasted_text", "locator": "line 1"},
    }


def test_record_missing_identity_is_rejected_with_reason_naming_the_rule_and_not_accepted():
    artifact = {"records": [_record({"jobtitle": "CEO"})]}
    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1
    assert result.rejected[0]["index"] == 0
    assert "identity" in result.rejected[0]["reason"]


def test_whitespace_only_identity_field_is_rejected_diverging_deliberately_from_file_loader_has_identity():
    """src/file_loader.py::_has_identity does NOT trim whitespace and would wrongly
    accept this row as having a present email; the plugin mirrors the deployed n8n
    `Map Columns` node's requiredIdentity(), which trims before checking presence — this
    is the deliberate divergence 24-RESEARCH.md's Pitfall 3 documents."""
    artifact = {"records": [_record({"email": "   "})]}
    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1


def test_non_canonical_key_is_stripped_and_reported_and_row_still_accepted():
    artifact = {
        "records": [_record({"email": "a@b.c", "twitter_url": "https://twitter.com/a"})]
    }
    result = extraction.validate(artifact)

    assert len(result.accepted) == 1
    assert "twitter_url" not in result.accepted[0]["row"]
    assert {"index": 0, "key": "twitter_url"} in result.dropped_keys


def test_malformed_record_does_not_prevent_surrounding_records_from_being_accepted():
    artifact = {
        "records": [
            _record({"email": "good1@example.com"}),
            "not a record object",
            _record({"email": "good2@example.com"}),
        ]
    }
    result = extraction.validate(artifact)

    assert len(result.accepted) == 2
    assert len(result.rejected) == 1
    assert result.rejected[0]["index"] == 1


def test_record_row_not_an_object_is_rejected():
    artifact = {"records": [{"row": "not an object", "provenance": {"input": "x", "locator": "y"}}]}
    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1


def test_record_missing_provenance_entirely_is_rejected():
    artifact = {"records": [{"row": {"email": "a@b.c"}}]}
    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1


def test_record_provenance_missing_locator_is_rejected():
    artifact = {"records": [{"row": {"email": "a@b.c"}, "provenance": {"input": "pasted_text"}}]}
    result = extraction.validate(artifact)

    assert result.accepted == []
    assert len(result.rejected) == 1


def test_load_artifact_missing_path_raises_artifact_not_found(tmp_path):
    with pytest.raises(extraction.ExtractionError) as exc_info:
        extraction.load_artifact(tmp_path / "does-not-exist.json")
    assert exc_info.value.code == "artifact_not_found"


def test_load_artifact_not_json_raises_artifact_not_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not json at all {{{", encoding="utf-8")
    with pytest.raises(extraction.ExtractionError) as exc_info:
        extraction.load_artifact(path)
    assert exc_info.value.code == "artifact_not_json"


def test_load_artifact_wrong_top_level_shape_raises_artifact_wrong_shape(tmp_path):
    path = tmp_path / "wrong_shape.json"
    path.write_text(json.dumps(["just", "a", "list"]), encoding="utf-8")
    with pytest.raises(extraction.ExtractionError) as exc_info:
        extraction.load_artifact(path)
    assert exc_info.value.code == "artifact_wrong_shape"


def test_load_artifact_empty_records_raises_artifact_empty(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"records": []}), encoding="utf-8")
    with pytest.raises(extraction.ExtractionError) as exc_info:
        extraction.load_artifact(path)
    assert exc_info.value.code == "artifact_empty"


def test_cli_exits_nonzero_and_prints_code_on_missing_artifact(tmp_path):
    missing = tmp_path / "does-not-exist.json"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "extraction.py"), str(missing)],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["code"] == "artifact_not_found"
