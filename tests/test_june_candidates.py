"""Offline tests for scripts/build_june_candidates.py (Phase 41, D-01..D-03, D-08).

Task 1: builder mapping, boolean-string coercion, confidence mapping, `_meta` shape, and
idempotent re-run against the committed snapshot.
Task 2: the hand-curated exception list and table-wide invariants.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest
import yaml

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


# --- Task 2: exception list + table-wide invariants -----------------------------------

def test_every_row_has_the_four_mandatory_keys(table):
    for record_id, row in table["rows"].items():
        for key in ("lv_org_type", "lv_produces_content", "lv_country_region_normalized",
                    "_confidence"):
            assert key in row, f"row {record_id} missing mandatory key {key}"


def test_qric_exception_maps_to_regulator(table):
    row = table["rows"]["16047156820"]
    assert row["lv_org_type"] == "regulator"
    assert row.get("_exception_reason")


def test_gambling_operator_exceptions_carry_veto_input_flag(table):
    for record_id in ("17861423879", "10024564084"):
        row = table["rows"][record_id]
        assert row["lv_org_type"] == "gambling_operator"
        assert row["lv_is_gambling_operator"] == "true"
        assert row.get("_exception_reason")


def test_hardware_vendor_exceptions_carry_veto_input_flag(table):
    for record_id in ("15274105699", "18047161864"):
        row = table["rows"][record_id]
        assert row["lv_org_type"] == "hardware_vendor"
        assert row["lv_is_hardware_vendor"] == "true"
        assert row.get("_exception_reason")


def test_no_row_asserts_an_unevidenced_negative_veto_flag(table):
    # June never asserted the negative -- an unevidenced "false" would suppress a real
    # hard veto for a company June simply didn't classify as hardware/gambling.
    for record_id, row in table["rows"].items():
        assert row.get("lv_is_hardware_vendor") != "false", record_id
        assert row.get("lv_is_gambling_operator") != "false", record_id


def test_every_lv_org_type_is_taxonomy_legal(table):
    taxonomy = yaml.safe_load((ROOT / "config" / "taxonomy.yaml").read_text())
    valid_org_types = set(taxonomy["org_types"].keys())
    for record_id, row in table["rows"].items():
        assert row["lv_org_type"] in valid_org_types, (
            f"row {record_id} has non-taxonomy lv_org_type {row['lv_org_type']!r}")


def test_confidence_distribution_matches_d03(table):
    from collections import Counter
    counts = Counter(row["_confidence"] for row in table["rows"].values())
    assert counts[85] == 49
    assert counts[65] == 16
    assert counts[40] == 1
