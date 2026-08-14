# tests/test_check_schema_drift.py
#
# Phase 42 Plan 01 Task 2 — offline test suite pinning scripts/check_schema_drift.py's
# comparator state machine and exit codes. Pure pytest: no network, no credentials, no
# monkeypatched HTTP. classify_property() and exit_code_for() are pure functions written
# precisely so this is possible (Task 1).
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from check_schema_drift import (  # noqa: E402
    D04_COMPANY_PROPERTY_SCOPE,
    DO_NOT_ARCHIVE_COMPANY_PROPERTIES,
    DO_NOT_ARCHIVE_FLOW_IDS,
    RETIRED_FLOW_IDS,
    ACCEPTED_DIVERGENCES,
    classify_property,
    exit_code_for,
    _compute_do_not_archive,
)

BASELINE_SNAPSHOT = (
    ROOT / "config" / "hubspot_migration" / "baseline"
    / "portal-schema-companies-phase42-pre.json"
)


def _live_option(value, label=None, display_order=0, hidden=False):
    # Shape the live API actually returns (RESEARCH.md "Enum-Value Comparison" §D-06):
    # {description, displayOrder, hidden, label, value}.
    return {
        "description": "",
        "displayOrder": display_order,
        "hidden": hidden,
        "label": label if label is not None else value,
        "value": value,
    }


def _yaml_option(value, label=None, display_order=0, hidden=False):
    # Shape the manifest uses (config/hubspot_properties.yaml): {label, value,
    # displayOrder, hidden} -- no `description` key.
    return {
        "label": label if label is not None else value,
        "value": value,
        "displayOrder": display_order,
        "hidden": hidden,
    }


# --- classify_property state machine -----------------------------------------------

def test_in_sync_when_type_fieldtype_and_enum_values_agree():
    declared = {
        "name": "lv_org_type", "label": "LV Org Type", "type": "enumeration",
        "fieldType": "select", "groupName": "lv_enrichment",
        "options": [_yaml_option("governing_body_league"), _yaml_option("other")],
    }
    live = {
        "name": "lv_org_type", "label": "LV Org Type", "type": "enumeration",
        "fieldType": "select", "groupName": "lv_enrichment",
        "options": [_live_option("governing_body_league"), _live_option("other")],
    }
    assert classify_property("lv_org_type", declared, live) == "in_sync"


def test_enum_mismatch_when_only_option_value_sets_differ():
    declared = {
        "name": "lv_icp_tier", "label": "ICP Tier", "type": "enumeration",
        "fieldType": "select", "groupName": "companyinformation",
        "options": [_yaml_option("A"), _yaml_option("B"), _yaml_option("Needs Review")],
    }
    live = {
        "name": "lv_icp_tier", "label": "ICP Tier", "type": "enumeration",
        "fieldType": "select", "groupName": "companyinformation",
        "options": [_live_option("A"), _live_option("B"), _live_option("Unscored")],
    }
    assert classify_property("lv_icp_tier", declared, live) == "enum_mismatch"


def test_type_mismatch_when_type_or_fieldtype_differ():
    declared = {
        "name": "lv_icp_confidence", "label": "ICP Confidence", "type": "number",
        "fieldType": "number", "groupName": "companyinformation", "options": [],
    }
    live = {
        "name": "lv_icp_confidence", "label": "ICP Confidence", "type": "string",
        "fieldType": "text", "groupName": "companyinformation", "options": [],
    }
    assert classify_property("lv_icp_confidence", declared, live) == "type_mismatch"


def test_cosmetic_only_when_only_label_displayorder_or_description_differ():
    declared = {
        "name": "lv_produces_content", "label": "Produces Content (old label)",
        "type": "bool", "fieldType": "booleancheckbox", "groupName": "lv_enrichment",
        "options": [_yaml_option("true"), _yaml_option("false")],
    }
    live = {
        "name": "lv_produces_content", "label": "LV Produces Content",
        "type": "bool", "fieldType": "booleancheckbox", "groupName": "lv_enrichment",
        "options": [_live_option("true"), _live_option("false")],
    }
    assert classify_property("lv_produces_content", declared, live) == "cosmetic_only"


def test_missing_from_yaml_when_live_and_undeclared():
    live = {
        "name": "org_type_score", "label": "Org Type Score", "type": "number",
        "fieldType": "number", "groupName": "companyinformation", "options": [],
    }
    assert classify_property("org_type_score", None, live) == "missing_from_yaml"


def test_fabricated_entry_when_declared_and_absent_live():
    """F2 guard: a yaml entry for a property the portal does not have -- exactly what
    fabricating an entry from the superseded CLAUDE.md design list would produce."""
    declared = {
        "name": "lv_never_created", "label": "Never Created", "type": "string",
        "fieldType": "text", "groupName": "lv_enrichment", "options": [],
    }
    assert classify_property("lv_never_created", declared, None) == "fabricated_entry"


def test_documented_gap_for_in_scope_name_neither_live_nor_declared():
    assert classify_property("lv_icp_scored_at", None, None) == "documented_gap"


# --- exit_code_for --------------------------------------------------------------------

def _report(properties, do_not_archive_ok=True):
    return {
        "do_not_archive": {"ok": do_not_archive_ok},
        "properties": properties,
    }


def test_exit_code_2_when_do_not_archive_property_absent_even_if_all_in_sync():
    report = _report(
        properties=[{"name": "lv_org_type", "status": "in_sync"}],
        do_not_archive_ok=False,
    )
    assert exit_code_for(report) == 2


def test_exit_code_2_when_do_not_archive_flow_disabled_even_if_all_in_sync():
    report = _report(
        properties=[{"name": "lv_org_type", "status": "in_sync"}],
        do_not_archive_ok=False,
    )
    assert exit_code_for(report) == 2


def test_exit_code_1_for_fabricated_entry_alone():
    report = _report(
        properties=[{"name": "lv_never_created", "status": "fabricated_entry"}],
        do_not_archive_ok=True,
    )
    assert exit_code_for(report) == 1


def test_exit_code_0_when_only_non_in_sync_statuses_are_cosmetic_and_documented_gap():
    report = _report(
        properties=[
            {"name": "lv_produces_content", "status": "cosmetic_only"},
            {"name": "lv_icp_scored_at", "status": "documented_gap"},
            {"name": "lv_org_type", "status": "in_sync"},
        ],
        do_not_archive_ok=True,
    )
    assert exit_code_for(report) == 0


# --- F4: the component-score scope guard -----------------------------------------------

def test_five_score_names_are_members_of_d04_scope():
    """F4 regression guard. The repo's only pre-existing reference detector
    (tests/test_hubspot_schema_coverage.py:33, `PROPERTY_RE`) uses a `lv_`/`enrichment_`
    namespace-prefix regex that structurally cannot match these five names. A comparator
    built by copying that regex would classify the live scoring engine as unreferenced and
    mark it archive-eligible -- exactly what D-01's do-not-archive set exists to prevent.
    This test pins that D04_COMPANY_PROPERTY_SCOPE is an explicit name list, not a regex."""
    five_score_names = {
        "org_type_score", "geography_score", "annual_revenue_score",
        "produces_content_score", "gambling_score",
    }
    assert five_score_names.issubset(D04_COMPANY_PROPERTY_SCOPE)
    for name in five_score_names:
        assert not name.startswith("lv_") and not name.startswith("enrichment_")


# --- F5: the accepted-divergence guard --------------------------------------------------

def test_lv_icp_tier_accepted_divergence_present_and_contributes_no_exit_code():
    """F5 regression guard. The live lv_icp_tier enum's value count is five (A/B/C/D/
    Unscored); config/icp_scoring.yaml's recommended_motion map names a sixth label,
    'Needs Review', deliberately deferred in Phase 40. This phase REPORTS that divergence
    rather than fixing it -- fixing it would require a portal-side enum-option addition,
    which D-05 forbids in reconciliation and D-07/D-08 do not authorize. A report whose
    only anomaly is this accepted divergence must still exit 0."""
    ids = {d["id"] for d in ACCEPTED_DIVERGENCES}
    assert "PARITY-01-tier-label" in ids
    entry = next(d for d in ACCEPTED_DIVERGENCES if d["id"] == "PARITY-01-tier-label")
    assert entry["property"] == "lv_icp_tier_derived"

    report = _report(
        properties=[{"name": "lv_icp_tier", "status": "in_sync"}],
        do_not_archive_ok=True,
    )
    report["accepted_divergences"] = ACCEPTED_DIVERGENCES
    assert exit_code_for(report) == 0


# --- do-not-archive set consistency -----------------------------------------------------

# Phase 50 Plan 06 (D-20): postdates the committed phase42-pre snapshot (2026-08-13) --
# the property could not have existed in a Phase 42 capture, so it is carved out of the
# committed-snapshot tripwire by name below rather than making that assertion fail on a
# property the snapshot predates.
_POSTDATES_PHASE42_SNAPSHOT = frozenset({"lv_anti_icp_flag_num"})


def test_do_not_archive_sets_have_expected_sizes():
    assert len(DO_NOT_ARCHIVE_COMPANY_PROPERTIES) == 11
    assert len(DO_NOT_ARCHIVE_FLOW_IDS) == 5
    assert len(D04_COMPANY_PROPERTY_SCOPE) == 15


def test_do_not_archive_company_properties_appear_in_committed_snapshot():
    """Turns the committed phase42-pre snapshot into a permanent offline tripwire: if a
    later change removes one of the do-not-archive names from the live schema and someone
    re-captures the snapshot under the same label, this test goes red without needing a
    network call.

    Skipped (not failed) until the live snapshot exists -- Task 1's live steps are an
    operator-run checkpoint, not something this offline test suite can produce itself."""
    import pytest

    if not BASELINE_SNAPSHOT.exists():
        pytest.skip(
            f"{BASELINE_SNAPSHOT} not yet captured -- run the 42-01 checkpoint's live "
            "snapshot command, then re-run this suite to activate the tripwire."
        )

    doc = json.loads(BASELINE_SNAPSHOT.read_text())
    results = doc.get("results") or doc.get("body", {}).get("results") or []
    assert results, f"{BASELINE_SNAPSHOT.name} has no results[] -- snapshot shape changed"
    live_names = {p["name"] for p in results}
    checked = DO_NOT_ARCHIVE_COMPANY_PROPERTIES - _POSTDATES_PHASE42_SNAPSHOT
    missing = checked - live_names
    assert not missing, (
        f"do-not-archive propert(y/ies) absent from the committed phase42-pre snapshot: "
        f"{sorted(missing)} -- the live scoring engine may be damaged"
    )


# --- RETIRED_FLOW_IDS: live-AND-disabled invariant (D-08, Phase 50 Plan 05) -------------

def _all_live_companies():
    return {name: {"name": name} for name in DO_NOT_ARCHIVE_COMPANY_PROPERTIES}


def _all_live_flows_enabled():
    return {
        flow_id: {"id": flow_id, "isEnabled": True}
        for flow_id in DO_NOT_ARCHIVE_FLOW_IDS
    }


def test_retired_flow_live_and_disabled_is_ok():
    live_flows = _all_live_flows_enabled()
    live_flows["4625147345"] = {"id": "4625147345", "isEnabled": False}
    result = _compute_do_not_archive(_all_live_companies(), live_flows)
    assert result["ok"] is True
    retired = next(rf for rf in result["retired_flows"] if rf["id"] == "4625147345")
    assert retired["live"] is True and retired["is_enabled"] is False


def test_retired_flow_absent_is_not_ok():
    live_flows = _all_live_flows_enabled()
    # "4625147345" deliberately absent -- deleted, not just disabled.
    result = _compute_do_not_archive(_all_live_companies(), live_flows)
    assert result["ok"] is False
    retired = next(rf for rf in result["retired_flows"] if rf["id"] == "4625147345")
    assert retired["live"] is False


def test_retired_flow_live_and_enabled_is_not_ok():
    live_flows = _all_live_flows_enabled()
    live_flows["4625147345"] = {"id": "4625147345", "isEnabled": True}
    result = _compute_do_not_archive(_all_live_companies(), live_flows)
    assert result["ok"] is False
    retired = next(rf for rf in result["retired_flows"] if rf["id"] == "4625147345")
    assert retired["live"] is True and retired["is_enabled"] is True


def test_retired_flow_ids_contains_wf1():
    assert "4625147345" in RETIRED_FLOW_IDS
