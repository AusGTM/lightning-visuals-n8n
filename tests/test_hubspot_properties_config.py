# tests/test_hubspot_properties_config.py
#
# Phase 15 Task 2 — offline validation of config/hubspot_properties.yaml, the desired-state
# manifest scripts/sync_hubspot_properties.py diffs against. Pure parse + assert, no network.
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "hubspot_properties.yaml"

# (type, fieldType) pairs HubSpot's CRM v3 Properties API actually accepts
# (RESEARCH.md §2.1: type in string|number|date|datetime|bool|enumeration).
#
# Phase 42 Plan 02 (D-04): added ("number", "calculation_equation") -- the live pair for
# lv_icp_fit_score, a calculated property proven live in this portal (plan-01 snapshot,
# config/hubspot_migration/baseline/portal-schema-companies-phase42-pre.json). This guard's
# protective intent (catch a type/fieldType pair the Properties API would reject at create
# time, a live 400 nobody sees until a migration runs) still holds for every other pair --
# only this one calculated-property pair, empirically live, is now accepted.
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
    ("number", "calculation_equation"),
    ("string", "calculation_equation"),  # Phase 50 Plan 01: lv_icp_tier_derived (D-14)
}


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def test_config_parses():
    cfg = load_config()
    assert "companies" in cfg
    assert "contacts" in cfg


# Phase 20 Plan 04 (REQ-lusha-id-staging): the two opaque Lusha record-identifier staging
# properties are deliberately NOT lv_-prefixed. PN-1 governs CANONICAL enriched fields
# (ICP inputs/outputs the merge policy writes); these two are a raw third-party provider
# id, staged for request-side reuse only, and the plan names them lusha_contact_id /
# lusha_company_id explicitly (docs/LUSHA-V3-CONTRACT.md, 20-04-PLAN.md) — an intentional,
# narrow exception to the blanket PN-1 rule, not a drift.
#
# Phase 42 Plan 02 (D-04): the five component-score properties
# (org_type_score/geography_score/annual_revenue_score/produces_content_score/
# gambling_score) are ALSO exempt. PN-1's protective intent is: don't let this manifest
# invent a wrongly-namespaced property that then gets created live under a name that
# collides with HubSpot's own or another integration's. These five were created directly
# against the portal during Phase 40's remediation, named by the flows that write them —
# they are the live scoring engine's own terms, not project-namespaced enriched fields. The
# manifest is mirroring an existing live name here, never proposing a new one, so PN-1's
# collision risk does not apply. The rule still fires for any other name outside both
# exemption sets.
_PN1_EXEMPT_NAMES = {
    "lusha_contact_id", "lusha_company_id",
    "org_type_score", "geography_score", "annual_revenue_score",
    "produces_content_score", "gambling_score",
}


def test_every_property_name_is_lv_prefixed():
    cfg = load_config()
    for object_type in ("companies", "contacts"):
        for prop in cfg[object_type]["properties"]:
            if prop["name"] in _PN1_EXEMPT_NAMES:
                continue
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


# Phase 42 Plan 02 (D-04): this guard was protecting against a typo'd groupName that
# compute_group_diff (scripts/sync_hubspot_properties.py:96-98) would then try to create as
# a brand-new group on the portal. That protection still fires for anything not in EITHER
# accepted source below. The expansion adds a second accepted source because a HubSpot-
# native group (companyinformation, home to the ICP output properties and the five
# component scores) is a legitimate groupName that must NEVER be declared in the yaml's own
# groups: list -- doing so is the one path by which this expansion could cause a portal
# write. This frozenset, populated from the live groupName values the plan-01 snapshot
# shows for the newly-mirrored properties, is the deliberate alternative: accepted without
# declaration, and never fed into compute_group_diff because it never touches groups:.
_NATIVE_GROUPS_ACCEPTED_WITHOUT_DECLARATION = frozenset({"companyinformation"})


def test_every_groupname_is_a_declared_group():
    cfg = load_config()
    for object_type in ("companies", "contacts"):
        group_names = {g["name"] for g in cfg[object_type]["groups"]}
        for prop in cfg[object_type]["properties"]:
            assert (
                prop["groupName"] in group_names
                or prop["groupName"] in _NATIVE_GROUPS_ACCEPTED_WITHOUT_DECLARATION
            ), f"{object_type}.{prop['name']} references undeclared group {prop['groupName']}"


def test_exact_counts_guard_against_manifest_drift():
    # This test exists to catch accidental manifest drift; its numbers are expected to move
    # with any deliberate expansion. Phase 42 Plan 02 (D-04) expanded companies from 22 to
    # 32 (the ten properties drift-report-phase42-pre.json classified missing_from_yaml).
    # Contacts and the group counts are untouched -- D-04 scopes the expansion to company
    # scoring properties only.
    # Phase 50 Plan 01 (D-01/D-14) added exactly one company property, lv_icp_tier_derived,
    # bumping the count 32 -> 33. Phase 50 Plan 06 (D-20) added a second,
    # lv_anti_icp_flag_num (the numeric veto mirror), bumping 33 -> 34. Phase 50 Plan 05
    # (D-06, D-24) removed lv_icp_tier's declaration after it was archived live, bumping
    # 34 -> 33.
    # Quick task 260823-ono added one company property, lv_named_account_score_floor
    # (the metro peak-body override number, retargeted post-CP1 from an enum after
    # halt-b), bumping 33 -> 34.
    cfg = load_config()
    assert len(cfg["companies"]["properties"]) == 34
    assert len(cfg["contacts"]["properties"]) == 17
    assert len(cfg["companies"]["groups"]) == 1
    assert len(cfg["contacts"]["groups"]) == 1


def test_lv_org_type_and_lv_produces_content_are_declared_with_live_matching_shape():
    # SUPERSEDED (Phase 42 Plan 02, D-04): this test originally asserted lv_org_type and
    # lv_produces_content were ABSENT, because the manifest was a create-only "what's
    # missing" list at the time and both already existed live. D-04 overturns that premise --
    # the manifest is now a full mirror, so both must be PRESENT. The replacement assertion
    # protects the stronger property: presence with shape matching the live snapshot, not
    # mere absence.
    import json
    from pathlib import Path as _Path

    cfg = load_config()
    company_props = {p["name"]: p for p in cfg["companies"]["properties"]}
    assert "lv_org_type" in company_props
    assert "lv_produces_content" in company_props

    snapshot_path = (
        _Path(__file__).resolve().parent.parent
        / "config" / "hubspot_migration" / "baseline"
        / "portal-schema-companies-phase42-pre.json"
    )
    live_by_name = {p["name"]: p for p in json.loads(snapshot_path.read_text())["results"]}
    for name in ("lv_org_type", "lv_produces_content"):
        declared = company_props[name]
        live = live_by_name[name]
        assert declared["type"] == live["type"]
        assert declared["fieldType"] == live["fieldType"]
        assert declared["groupName"] == live["groupName"]
        declared_values = {str(o["value"]) for o in declared["options"]}
        live_values = {str(o["value"]) for o in live["options"]}
        assert declared_values == live_values


def test_sj3_control_properties_exist_on_both_objects():
    # Phase 16 Task 3 — SJ-3 predicate prerequisite (CLAUDE.md §4.1).
    cfg = load_config()
    for object_type in ("companies", "contacts"):
        names = {p["name"] for p in cfg[object_type]["properties"]}
        assert "lv_enrichment_requested" in names, f"{object_type} missing lv_enrichment_requested"
        assert "lv_enrichment_status" in names, f"{object_type} missing lv_enrichment_status"


def test_lv_enrichment_requested_has_explicit_true_false_options():
    cfg = load_config()
    for object_type in ("companies", "contacts"):
        prop = next(p for p in cfg[object_type]["properties"] if p["name"] == "lv_enrichment_requested")
        assert prop["type"] == "bool"
        values = {opt["value"] for opt in prop["options"]}
        assert values == {"true", "false"}


def test_lv_enrichment_status_has_exactly_six_status_values():
    expected = {"queued", "running", "complete", "failed", "needs_review", "skipped"}
    cfg = load_config()
    for object_type in ("companies", "contacts"):
        prop = next(p for p in cfg[object_type]["properties"] if p["name"] == "lv_enrichment_status")
        assert prop["type"] == "enumeration"
        values = {opt["value"] for opt in prop["options"]}
        assert values == expected


# Phase 20 Plan 04 (REQ-lusha-id-staging) --------------------------------------------

def test_lusha_id_staging_properties_declared_with_expected_shape():
    cfg = load_config()
    contact_prop = next(p for p in cfg["contacts"]["properties"] if p["name"] == "lusha_contact_id")
    assert contact_prop["type"] == "string"
    assert contact_prop["fieldType"] == "text"
    assert contact_prop["groupName"] == "lv_enrichment_contacts"
    assert contact_prop["options"] == []

    company_prop = next(p for p in cfg["companies"]["properties"] if p["name"] == "lusha_company_id")
    assert company_prop["type"] == "string"
    assert company_prop["fieldType"] == "text"
    assert company_prop["groupName"] == "lv_enrichment"
    assert company_prop["options"] == []


def test_lusha_id_staging_properties_appear_in_search_property_lists():
    """A config entry with no matching search-list entry would silently break the
    read-back path (existingRecord.lusha_contact_id / .lusha_company_id never populated) —
    this is the failure mode worth pinning, per the plan's own acceptance criteria."""
    import sys
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "scripts"))
    from build_cloud_workflows import (  # noqa: E402
        ENRICH_CONTACT_SEARCH_PROPERTIES_CSV,
        ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV,
        ENRICH_COMPANY_SEARCH_PROPERTIES_CSV,
        HS_SEARCH_BODY_EXPR,
        HS_CO_SEARCH_BODY_EXPR,
    )

    assert "lusha_contact_id" in ENRICH_CONTACT_SEARCH_PROPERTIES_CSV.split(",")
    assert "lusha_contact_id" in ENRICH_CONTACT_FETCH_BY_ID_PROPERTIES_CSV.split(",")
    assert "lusha_company_id" in ENRICH_COMPANY_SEARCH_PROPERTIES_CSV.split(",")
    assert '"lusha_contact_id"' in HS_SEARCH_BODY_EXPR
    assert '"lusha_company_id"' in HS_CO_SEARCH_BODY_EXPR


def test_lv_country_region_normalized_appears_in_the_company_fetch_property_list():
    """fix-40 VETO-01/02 live evidence run: this property was absent from
    ENRICH_COMPANY_SEARCH_PROPERTIES_CSV (the ONE list feeding both "HubSpot Company
    Search" and "HubSpot Company Fetch By Id"), so `existingRecord.
    lv_country_region_normalized` was always `undefined` -- ENRICH_DECIDE_CO_CLOUD's veto
    derivation reads that field directly as its fallback (not through mergeCompanies'
    policy gate), so `_regionKey(undefined)` fired a spurious "Non-ANZ geography" veto on
    real AU/NZ companies whenever no candidate this run freshly re-promoted region. Unlike
    lusha_company_id (a read-back-path property), this is a correctness-critical scoring
    input -- pin it here so removing it again fails the suite instead of silently
    reopening the live-caught defect."""
    import sys
    from pathlib import Path as _Path

    root = _Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "scripts"))
    from build_cloud_workflows import ENRICH_COMPANY_SEARCH_PROPERTIES_CSV  # noqa: E402

    assert "lv_country_region_normalized" in ENRICH_COMPANY_SEARCH_PROPERTIES_CSV.split(",")
