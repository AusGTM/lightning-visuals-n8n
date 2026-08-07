"""Offline tests for scripts/build_june_candidates.py (Phase 41, D-01..D-03, D-08).

Task 1: builder mapping, boolean-string coercion, confidence mapping, `_meta` shape, and
idempotent re-run against the committed snapshot.
Task 2 (added later): the hand-curated exception list and table-wide invariants.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_june_candidates as bjc  # noqa: E402

SNAPSHOT_PATH = ROOT / "config" / "june_candidates_source.json"
TABLE_PATH = ROOT / "config" / "june_candidates.json"


@pytest.fixture(scope="module")
def source_records():
    return json.loads(SNAPSHOT_PATH.read_text())


@pytest.fixture(scope="module")
def table():
    return json.loads(TABLE_PATH.read_text())


def test_snapshot_exists_and_hash_matches_meta(table):
    assert SNAPSHOT_PATH.exists()
    digest = hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest()
    assert digest == table["_meta"]["source_sha256"]


def test_meta_shape(table):
    meta = table["_meta"]
    assert meta["record_count"] == 66
    assert meta["mapping_version"] == "june-2026-v1"
    assert meta["source_path"]
    assert meta["generated_at"]
    assert len(table["rows"]) == 66
    for key in table["rows"]:
        assert isinstance(key, str)


def test_racing_nsw_row_maps_correctly(table):
    row = table["rows"]["15008671672"]
    assert row["lv_org_type"] == "governing_body_league"
    assert row["lv_produces_content"] == "true"
    assert isinstance(row["lv_produces_content"], str)
    assert row["lv_country_region_normalized"] == "AU"
    assert row["_confidence"] == 85
    assert row["_evidence"]["lv_org_type"].startswith("http")


def test_no_bare_json_booleans_serialized(table):
    # HubSpot EQ filters compare strings only -- a bare JSON `true` for
    # lv_produces_content would be the exact landmine CLAUDE.md/RESEARCH.md flag.
    raw = TABLE_PATH.read_text()
    assert '"lv_produces_content": true' not in raw
    assert '"lv_produces_content": false' not in raw


def test_map_row_confidence_mapping():
    assert bjc.map_row({"id": "1", "confidence": "high"})["_confidence"] == 85
    assert bjc.map_row({"id": "2", "confidence": "medium"})["_confidence"] == 65
    assert bjc.map_row({"id": "3", "confidence": "low"})["_confidence"] == 40


def test_map_row_org_type_deterministic_table():
    cases = {
        "Team/Club": "individual_club_team",
        "League/Governing-Body": "governing_body_league",
        "Broadcaster/Production": "broadcaster",
        "Other": "other",
        "Non-sports-leisure": "other",
    }
    for perplexity_value, expected in cases.items():
        row = bjc.map_row({"id": "x", "org_type": perplexity_value})
        assert row["lv_org_type"] == expected


def test_map_row_omits_blank_fields_rather_than_writing_null():
    row = bjc.map_row({"id": "1"})
    # No hq_country, no confidence, no produces-content, no sources -> nothing but the
    # deterministic org_type default ("Other" bucket) and _name should be present.
    assert "lv_country_region_normalized" not in row
    assert "_confidence" not in row
    assert "lv_produces_content" not in row
    assert "_evidence" not in row


def test_builder_idempotent_against_committed_snapshot(tmp_path):
    out_path = tmp_path / "june_candidates_rerun.json"
    rows = bjc.build(json.loads(SNAPSHOT_PATH.read_text()))
    committed_rows = json.loads(TABLE_PATH.read_text())["rows"]
    assert rows == committed_rows
