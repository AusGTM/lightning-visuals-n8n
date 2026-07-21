# tests/test_hubspot_properties_config.py
#
# Phase 15 Task 2 — offline validation of config/hubspot_properties.yaml, the desired-state
# manifest scripts/sync_hubspot_properties.py diffs against. Pure parse + assert, no network.
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "hubspot_properties.yaml"

# (type, fieldType) pairs HubSpot's CRM v3 Properties API actually accepts
# (RESEARCH.md §2.1: type in string|number|date|datetime|bool|enumeration).
VALID_TYPE_FIELDTYPE_PAIRS = {
    ("string", "text"),
    ("string", "textarea"),
    ("number", "number"),
    ("date", "date"),
    ("datetime", "date"),
    ("bool", "booleancheckbox"),
    ("enumeration", "select"),
    ("enumeration", "checkbox"),
    ("enumeration", "radio"),
}


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def test_config_parses():
    cfg = load_config()
    assert "companies" in cfg
    assert "contacts" in cfg


def test_every_property_name_is_lv_prefixed():
    cfg = load_config()
    for object_type in ("companies", "contacts"):
        for prop in cfg[object_type]["properties"]:
            assert prop["name"].startswith("lv_"), f"{object_type}.{prop['name']} is not lv_-prefixed (PN-1)"


def test_every_type_fieldtype_pair_is_valid():
    cfg = load_config()
    for object_type in ("companies", "contacts"):
        for prop in cfg[object_type]["properties"]:
            pair = (prop["type"], prop["fieldType"])
            assert pair in VALID_TYPE_FIELDTYPE_PAIRS, f"{object_type}.{prop['name']} has invalid pair {pair}"


def test_enumeration_properties_have_nonempty_options():
    cfg = load_config()
    for object_type in ("companies", "contacts"):
        for prop in cfg[object_type]["properties"]:
            if prop["type"] == "enumeration":
                assert prop["options"], f"{object_type}.{prop['name']} is enumeration with no options"
                for opt in prop["options"]:
                    assert opt.get("label") and opt.get("value") is not None


def test_no_duplicate_names_within_an_object_type():
    cfg = load_config()
    for object_type in ("companies", "contacts"):
        names = [p["name"] for p in cfg[object_type]["properties"]]
        assert len(names) == len(set(names)), f"{object_type} has duplicate property names"


def test_review_surface_names_appear_once_per_object():
    # The 9 review-surface names are intentionally mirrored on BOTH objects — once each,
    # never duplicated within a single object type (covered by the prior test) but expected
    # to appear on both companies AND contacts.
    cfg = load_config()
    review_names = {
        "lv_enrichment_needs_review", "lv_enrichment_review_reason",
        "lv_enrichment_review_candidate_json", "lv_enrichment_review_approved",
        "lv_enrichment_reviewed_by", "lv_enrichment_reviewed_at",
        "lv_icp_needs_review", "lv_anti_icp_reason", "lv_icp_score_breakdown",
    }
    for object_type in ("companies", "contacts"):
        names = {p["name"] for p in cfg[object_type]["properties"]}
        assert review_names.issubset(names), f"{object_type} is missing review-surface properties"


def test_every_groupname_is_a_declared_group():
    cfg = load_config()
    for object_type in ("companies", "contacts"):
        group_names = {g["name"] for g in cfg[object_type]["groups"]}
        for prop in cfg[object_type]["properties"]:
            assert prop["groupName"] in group_names, (
                f"{object_type}.{prop['name']} references undeclared group {prop['groupName']}")


def test_exact_counts_guard_against_manifest_drift():
    cfg = load_config()
    assert len(cfg["companies"]["properties"]) == 19
    assert len(cfg["contacts"]["properties"]) == 14
    assert len(cfg["companies"]["groups"]) == 1
    assert len(cfg["contacts"]["groups"]) == 1


def test_lv_org_type_and_lv_produces_content_not_listed_for_creation():
    # These two already exist in the portal (2026-07-20 audit) — the manifest only lists
    # what is MISSING; listing them would be harmless but the plan explicitly omits them.
    cfg = load_config()
    company_names = {p["name"] for p in cfg["companies"]["properties"]}
    assert "lv_org_type" not in company_names
    assert "lv_produces_content" not in company_names
