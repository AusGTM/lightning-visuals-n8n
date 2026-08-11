# tests/test_flow_rubric_conformance.py
#
# Phase 40 Plan 01 (D-05) — offline conformance guard. Asserts every archived
# config/hubspot_flows/*.after.json flow's branch-value point table equals
# config/icp_scoring.yaml's rubric of record. Glob-driven parametrization: a
# mapper flow with no .after.json yet is simply not collected, so this module
# stays green through waves 2-4 as each later plan (40-04/40-05/40-06) adds its
# own .after.json and its own extractor. Zero network — pure JSON/YAML reads.
import glob
import json
from pathlib import Path

import pytest
import yaml

from src.normalizer import normalize_revenue_band

ROOT = Path(__file__).resolve().parent.parent
RUBRIC_PATH = ROOT / "config" / "icp_scoring.yaml"
FLOWS_DIR = ROOT / "config" / "hubspot_flows"


def load_rubric() -> dict:
    with RUBRIC_PATH.open() as f:
        return yaml.safe_load(f)


def load_flow(path) -> dict:
    with Path(path).open() as f:
        return json.load(f)


def extract_org_type_branch_scores(flow: dict) -> dict:
    """Walks the STATIC_BRANCH action keyed on lv_org_type and returns
    {branch_value: int(points)} by following each branch's nextActionId to the
    SINGLE_CONNECTION action that sets org_type_score. 4626124224
    ("Update Score Based on Org Type") is the only flow this extractor targets;
    40-05/40-06 add their own extractors for geography/revenue/tier rather than
    overloading this one."""
    actions_by_id = {a["actionId"]: a for a in flow["actions"]}
    branch_action = next(
        a for a in flow["actions"]
        if a.get("type") == "STATIC_BRANCH"
        and a.get("inputValue", {}).get("propertyName") == "lv_org_type"
    )
    scores = {}
    for branch in branch_action["staticBranches"]:
        target = actions_by_id[branch["connection"]["nextActionId"]]
        scores[branch["branchValue"]] = int(target["fields"]["value"]["staticValue"])
    return scores


def extract_org_type_default_branch_score(flow: dict) -> int:
    """Phase 46 Plan 01 (Task 1) -- extract_org_type_branch_scores above walks
    staticBranches only, leaving flow 4626124224's defaultBranch (the path a
    blank or unrecognised lv_org_type takes -- 18 live records) unasserted.
    Returns the int points the defaultBranch target writes to org_type_score."""
    actions_by_id = {a["actionId"]: a for a in flow["actions"]}
    branch_action = next(
        a for a in flow["actions"]
        if a.get("type") == "STATIC_BRANCH"
        and a.get("inputValue", {}).get("propertyName") == "lv_org_type"
    )
    default_target = actions_by_id[branch_action["defaultBranch"]["nextActionId"]]
    return int(default_target["fields"]["value"]["staticValue"])


def find_static_branch_action(flow: dict, property_name: str):
    """Returns the STATIC_BRANCH action keyed on property_name, or None if the
    flow has no such branch (40-04's two-terms-only extractors)."""
    return next(
        (a for a in flow["actions"]
         if a.get("type") == "STATIC_BRANCH"
         and a.get("inputValue", {}).get("propertyName") == property_name),
        None,
    )


def extract_true_default_scores(flow: dict, property_name: str) -> dict:
    """Walks a STATIC_BRANCH action keyed on property_name that has exactly one
    named branch ("true") plus a defaultBranch (40-04's produces-content and
    gambling mapper shape — every other value, including "false"/empty/absent,
    falls to the same default action). Returns
    {"true": int(points), "__default__": int(points)}."""
    actions_by_id = {a["actionId"]: a for a in flow["actions"]}
    branch_action = find_static_branch_action(flow, property_name)
    true_branch = next(b for b in branch_action["staticBranches"] if b["branchValue"] == "true")
    true_target = actions_by_id[true_branch["connection"]["nextActionId"]]
    default_target = actions_by_id[branch_action["defaultBranch"]["nextActionId"]]
    return {
        "true": int(true_target["fields"]["value"]["staticValue"]),
        "__default__": int(default_target["fields"]["value"]["staticValue"]),
    }


def written_property_names(flow: dict) -> set:
    """All company property names any SINGLE_CONNECTION action in this flow
    writes to. Used to assert a mapper flow's blast radius — T-40-15's
    mitigation for the gambling flow re-conflating the deduction with the
    veto."""
    return {
        a["fields"]["property_name"]
        for a in flow["actions"]
        if a.get("type") == "SINGLE_CONNECTION"
    }


def _after_json_paths() -> list:
    return sorted(glob.glob(str(FLOWS_DIR / "*.after.json")))


def _is_flow(doc: dict) -> bool:
    """Distinguishes an Automation v4 flow archive from a property-definition
    snapshot (both live in config/hubspot_flows/*.after.json, e.g. 40-04 Task 3's
    lv_icp_fit_score-property.after.json) — flows have an "actions" list, property
    snapshots don't."""
    return "actions" in doc


def test_rubric_loads():
    rubric = load_rubric()
    assert "base_score" in rubric
    assert "org_type" in rubric["base_score"]


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_org_type_flow_matches_rubric(flow_path):
    flow = load_flow(flow_path)
    if not _is_flow(flow):
        pytest.skip(f"{flow_path} is not a flow archive")
    has_org_type_branch = any(
        a.get("type") == "STATIC_BRANCH"
        and a.get("inputValue", {}).get("propertyName") == "lv_org_type"
        for a in flow["actions"]
    )
    if not has_org_type_branch:
        pytest.skip(f"{flow_path} has no lv_org_type STATIC_BRANCH action")

    rubric_org_type = load_rubric()["base_score"]["org_type"]
    flow_scores = extract_org_type_branch_scores(flow)

    assert set(flow_scores.keys()) <= set(rubric_org_type.keys()), (
        f"flow branch keys {sorted(flow_scores.keys())} must be a subset of "
        f"rubric org_type keys {sorted(rubric_org_type.keys())}"
    )
    for branch_value, points in flow_scores.items():
        assert points == rubric_org_type[branch_value], (
            f"{flow_path}: branch '{branch_value}' scores {points}, "
            f"rubric says {rubric_org_type[branch_value]}"
        )


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_org_type_flow_defaultbranch_scores_zero(flow_path):
    """Phase 46 Plan 01 (Task 1) -- closes the blank-lv_org_type parity gap.
    extract_org_type_branch_scores walks staticBranches only, so flow
    4626124224's defaultBranch (the path a blank or unrecognised lv_org_type
    takes -- 18 live records per 46-RESEARCH.md) was previously unasserted.
    This guards that the defaultBranch target writes org_type_score "0",
    matching the oracle's cfg["base_score"]["org_type"].get(org_type, 0)
    fallback in src/icp_scoring.py. This assertion passes today -- it is a
    guard, not a fix."""
    flow = load_flow(flow_path)
    if not _is_flow(flow):
        pytest.skip(f"{flow_path} is not a flow archive")
    has_org_type_branch = any(
        a.get("type") == "STATIC_BRANCH"
        and a.get("inputValue", {}).get("propertyName") == "lv_org_type"
        for a in flow["actions"]
    )
    if not has_org_type_branch:
        pytest.skip(f"{flow_path} has no lv_org_type STATIC_BRANCH action")

    assert extract_org_type_default_branch_score(flow) == 0, (
        f"{flow_path}: defaultBranch must write org_type_score 0, matching the "
        "oracle's .get(org_type, 0) fallback for a blank/unrecognised lv_org_type"
    )


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_produces_content_flow_matches_rubric(flow_path):
    """40-04 (ENGINE-02) — produces_content_score's mapper flow branch table must
    equal config/icp_scoring.yaml's base_score.produces_content: true -> 20,
    everything else (including "false"/empty/absent) -> 0."""
    flow = load_flow(flow_path)
    if not _is_flow(flow):
        pytest.skip(f"{flow_path} is not a flow archive")
    if find_static_branch_action(flow, "lv_produces_content") is None:
        pytest.skip(f"{flow_path} has no lv_produces_content STATIC_BRANCH action")

    rubric = load_rubric()["base_score"]["produces_content"]
    scores = extract_true_default_scores(flow, "lv_produces_content")

    assert scores["true"] == rubric[True], (
        f"{flow_path}: 'true' branch scores {scores['true']}, rubric says {rubric[True]}"
    )
    assert scores["__default__"] == rubric[False] == rubric["unknown"], (
        f"{flow_path}: default branch scores {scores['__default__']}, "
        f"rubric says false={rubric[False]} unknown={rubric['unknown']}"
    )
    assert written_property_names(flow) == {"produces_content_score"}, (
        f"{flow_path}: must write only produces_content_score, "
        f"found {written_property_names(flow)}"
    )


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_gambling_flow_matches_rubric(flow_path):
    """Phase 46 Plan 04 (D-03) — the gambling deduction is removed outright, not merely
    re-valued: config/icp_scoring.yaml's graduated_deductions no longer carries a
    gambling_operator key at all (46-DECISION.md operator sign-off). This test no longer
    reads a rubric key that doesn't exist -- its job becomes: both branches of the
    gambling flow write 0. The flow must still write only gambling_score — never
    lv_anti_icp_flag or lv_org_type — so the deduction stays independent of both
    the veto and the org-type branch (F9's original defect, T-40-15)."""
    flow = load_flow(flow_path)
    if not _is_flow(flow):
        pytest.skip(f"{flow_path} is not a flow archive")
    if find_static_branch_action(flow, "lv_is_gambling_operator") is None:
        pytest.skip(f"{flow_path} has no lv_is_gambling_operator STATIC_BRANCH action")

    assert "gambling_operator" not in load_rubric().get("graduated_deductions", {}), (
        f"{flow_path}: rubric still carries graduated_deductions.gambling_operator -- "
        "D-03 removed this key entirely"
    )

    scores = extract_true_default_scores(flow, "lv_is_gambling_operator")

    assert scores["true"] == 0, (
        f"{flow_path}: 'true' branch scores {scores['true']}, expected 0 (D-03)"
    )
    assert scores["__default__"] == 0, (
        f"{flow_path}: default branch scores {scores['__default__']}, expected 0"
    )
    assert written_property_names(flow) == {"gambling_score"}, (
        f"{flow_path}: must write only gambling_score (T-40-15), "
        f"found {written_property_names(flow)}"
    )


def find_list_branch_action(flow: dict, property_name: str):
    """Returns the LIST_BRANCH action whose listBranches filter on property_name via
    a single-AND-group MULTISTRING filter (40-05's geography/revenue mapper shape),
    or None if the flow has no such branch."""
    for a in flow["actions"]:
        if a.get("type") != "LIST_BRANCH":
            continue
        for lb in a.get("listBranches", []):
            for ab in lb["filterBranch"].get("filterBranches", []):
                for f in ab.get("filters", []):
                    if f.get("property") == property_name:
                        return a
    return None


def extract_list_branch_multistring_scores(flow: dict, property_name: str) -> dict:
    """Walks a LIST_BRANCH action keyed on property_name (40-05's geography/revenue
    mapper shape: one listBranch per single-value MULTISTRING IS_EQUAL_TO filter,
    each routing to its own SINGLE_CONNECTION target) and returns
    {branch_value: int(points)}, plus '__default__' for the defaultBranch target
    (every value not named by any listBranch, including empty/absent)."""
    actions_by_id = {a["actionId"]: a for a in flow["actions"]}
    branch_action = find_list_branch_action(flow, property_name)
    scores = {}
    for lb in branch_action["listBranches"]:
        target = actions_by_id[lb["connection"]["nextActionId"]]
        points = int(target["fields"]["value"]["staticValue"])
        for ab in lb["filterBranch"].get("filterBranches", []):
            for f in ab.get("filters", []):
                if f.get("property") != property_name:
                    continue
                for v in f["operation"].get("values", []):
                    scores[v] = points
    default_target = actions_by_id[branch_action["defaultBranch"]["nextActionId"]]
    scores["__default__"] = int(default_target["fields"]["value"]["staticValue"])
    return scores


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_geography_flow_matches_rubric(flow_path):
    """40-05 (ENGINE-03) — geography_score's mapper flow branch table must equal
    config/icp_scoring.yaml's base_score.geography: AU/NZ/ANZ (the canonical enum
    values only) -> 10, every other value including Other/Unknown/empty/absent -> 0
    (the rubric's non_anz/unknown buckets). Also guards against F4's class of bug:
    the branch values must never be a spelling-variant list (Australia/Aus/New
    Zealand) reintroduced instead of the canonical enum."""
    flow = load_flow(flow_path)
    if not _is_flow(flow):
        pytest.skip(f"{flow_path} is not a flow archive")
    if find_list_branch_action(flow, "lv_country_region_normalized") is None:
        pytest.skip(f"{flow_path} has no lv_country_region_normalized LIST_BRANCH action")

    rubric = load_rubric()["base_score"]["geography"]
    scores = extract_list_branch_multistring_scores(flow, "lv_country_region_normalized")

    for region in ("AU", "NZ", "ANZ"):
        assert scores.get(region) == rubric[region], (
            f"{flow_path}: branch '{region}' scores {scores.get(region)}, "
            f"rubric says {rubric[region]}"
        )
    assert scores["__default__"] == rubric["non_anz"] == rubric["unknown"], (
        f"{flow_path}: default branch scores {scores['__default__']}, "
        f"rubric says non_anz={rubric['non_anz']} unknown={rubric['unknown']}"
    )
    spelling_variants = {"Australia", "Aus", "New Zealand"}
    present = spelling_variants & (set(scores.keys()) - {"__default__"})
    assert not present, (
        f"{flow_path}: branch values include spelling variants {present} "
        "instead of the canonical enum only (F4's exact bug shape)"
    )
    assert written_property_names(flow) == {"geography_score"}, (
        f"{flow_path}: must write only geography_score, found {written_property_names(flow)}"
    )


REVENUE_BAND_KEYS = (
    "<1M", "1-5M", "5-50M", "50-500M", "500-750M", "750M-1B", "1B-1.2B", "1.2B+", "unknown",
)


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_revenue_flow_matches_rubric(flow_path):
    """40-05 (ENGINE-04) — annual_revenue_score's mapper flow branch table must equal
    config/icp_scoring.yaml's base_score.revenue_band exactly: the set of branch keys
    must equal the nine rubric keys (not a subset — a missing band silently scores 0),
    each mapped to the configured points, including the 750M-1B=-15/500-750M=-5 pair
    F10 inverted live."""
    flow = load_flow(flow_path)
    if not _is_flow(flow):
        pytest.skip(f"{flow_path} is not a flow archive")
    if find_list_branch_action(flow, "lv_revenue_band") is None:
        pytest.skip(f"{flow_path} has no lv_revenue_band LIST_BRANCH action")

    rubric = load_rubric()["base_score"]["revenue_band"]
    scores = extract_list_branch_multistring_scores(flow, "lv_revenue_band")
    branch_keys = set(scores.keys()) - {"__default__"}

    assert branch_keys == set(REVENUE_BAND_KEYS) == set(rubric.keys()), (
        f"{flow_path}: branch keys {sorted(branch_keys)} must equal the nine rubric "
        f"revenue_band keys {sorted(rubric.keys())} exactly"
    )
    for band, points in rubric.items():
        assert scores[band] == points, (
            f"{flow_path}: band '{band}' scores {scores[band]}, rubric says {points}"
        )
    assert scores["__default__"] == 0, (
        f"{flow_path}: default branch scores {scores['__default__']}, expected 0"
    )
    assert written_property_names(flow) == {"annual_revenue_score"}, (
        f"{flow_path}: must write only annual_revenue_score, found {written_property_names(flow)}"
    )


VETO_PROPERTY_NAMES = {"lv_anti_icp_flag", "lv_anti_icp_reason"}


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_no_archived_flow_writes_veto_properties(flow_path):
    """D-01 permanent guard (T-40-17's mitigation) — once 40-03's n8n pipeline became
    the sole writer of the veto fields, no HubSpot workflow may ever write
    lv_anti_icp_flag or lv_anti_icp_reason again. Scans every archived .after.json
    flow's SINGLE_CONNECTION actions; this is the repo-wide guard that HubSpot never
    silently reclaims veto ownership in a future edit."""
    flow = load_flow(flow_path)
    if not _is_flow(flow):
        pytest.skip(f"{flow_path} is not a flow archive")
    written = written_property_names(flow)
    offenders = written & VETO_PROPERTY_NAMES
    assert not offenders, (
        f"{flow_path} writes {offenders} — HubSpot must never write the veto again (D-01)"
    )


def test_revenue_boundary_contract_offline():
    """40-05 Task 2 (ENGINE-04's boundary contract) — asserted offline against
    src/normalizer.py, since after the retarget HubSpot never sees a raw dollar
    figure: normalize_revenue_band's exact boundaries at 500M/750M/1B/1.2B, composed
    with the rubric, must yield -5/-15/-30/-50 respectively. F10 lived at exactly the
    750M/500M pair (750M scored -5 live instead of -15) -- this pins all four."""
    rubric = load_rubric()["base_score"]["revenue_band"]
    boundaries = {
        500_000_000: "500-750M",
        750_000_000: "750M-1B",
        1_000_000_000: "1B-1.2B",
        1_200_000_000: "1.2B+",
    }
    for dollars, expected_band in boundaries.items():
        band = normalize_revenue_band(dollars)
        assert band == expected_band, (
            f"normalize_revenue_band({dollars}) = {band!r}, expected {expected_band!r}"
        )
        assert rubric[band] == rubric[expected_band]
    assert rubric["500-750M"] == -5
    assert rubric["750M-1B"] == -15
    assert rubric["1B-1.2B"] == -30
    assert rubric["1.2B+"] == -50


FIT_SCORE_PROPERTY_PATH = FLOWS_DIR / "lv_icp_fit_score-property.after.json"

FIT_SCORE_COMPONENT_NAMES = (
    "org_type_score",
    "geography_score",
    "annual_revenue_score",
    "produces_content_score",
    "gambling_score",
)


def test_fit_score_formula_references_all_five_components():
    """40-04 Task 3 (D-06) — lv_icp_fit_score's archived post-PATCH calculationFormula
    must name all five component properties. Fails loudly if a term is dropped,
    reconstructed, or misspelled rather than extended from the fetched syntax."""
    if not FIT_SCORE_PROPERTY_PATH.exists():
        pytest.skip(f"{FIT_SCORE_PROPERTY_PATH} not archived yet")

    with FIT_SCORE_PROPERTY_PATH.open() as f:
        after = json.load(f)

    formula = after["calculationFormula"]
    for name in FIT_SCORE_COMPONENT_NAMES:
        assert name in formula, f"calculationFormula '{formula}' is missing '{name}'"


# Phase 41 task #3 -- the regression guard for the null-blanking defect. HubSpot blanks a
# calculated property entirely when ANY referenced term is null, and research legitimately
# answers null for gambling_score on ~95% of companies, so the bare five-term sum left
# 63 of 66 records with NO SCORE for a whole phase while the sweep reported PASS.
# Evidence: .planning/phases/41-.../41-FORMULA-SPIKE.md (three constructs verified live).
FIT_SCORE_GUARDED_COMPONENTS = (
    "geography_score",
    "annual_revenue_score",
    "produces_content_score",
    "gambling_score",
)
FIT_SCORE_SENTINEL_COMPONENT = "org_type_score"


def test_fit_score_formula_guards_every_nullable_component():
    """Reverting any coalesce() guard fails here. This is the guard against recurrence,
    not the fix itself -- the fix is one PATCH and is invisible to the repo otherwise."""
    if not FIT_SCORE_PROPERTY_PATH.exists():
        pytest.skip(f"{FIT_SCORE_PROPERTY_PATH} not archived yet")

    with FIT_SCORE_PROPERTY_PATH.open() as f:
        formula = json.load(f)["calculationFormula"]

    for name in FIT_SCORE_GUARDED_COMPONENTS:
        assert f"coalesce({name}, 0)" in formula, (
            f"'{name}' is not null-guarded in calculationFormula '{formula}'. A single "
            "null term blanks the whole score -- that defect cost Phase 41 63 records."
        )


def test_fit_score_formula_leaves_org_type_score_unguarded_as_the_sentinel():
    """org_type_score stays bare ON PURPOSE. The org-type mapper writes it for every
    enriched company ('unknown' scores 0, so it is never skipped), which makes it the
    'this record has been through the pipeline' sentinel. Guarding it too would make all
    646 never-enriched companies compute to 0 and enroll every one of them in the tier
    flow -- blank must keep meaning 'never scored'."""
    if not FIT_SCORE_PROPERTY_PATH.exists():
        pytest.skip(f"{FIT_SCORE_PROPERTY_PATH} not archived yet")

    with FIT_SCORE_PROPERTY_PATH.open() as f:
        formula = json.load(f)["calculationFormula"]

    assert f"coalesce({FIT_SCORE_SENTINEL_COMPONENT}" not in formula, (
        f"'{FIT_SCORE_SENTINEL_COMPONENT}' must NOT be null-guarded -- see docstring. "
        f"Formula: '{formula}'"
    )
    assert FIT_SCORE_SENTINEL_COMPONENT in formula


# ----------------------------------------------------------------------------------
# 40-06 (ENGINE-07/VETO-03) — WF1 "Set ICP Tier" tier-ladder conformance.
# WF1's shape differs from the geography/revenue mapper flows above: its two
# LIST_BRANCH actions compare directly against a single value (STRING/NUMBER/
# NUMBER_RANGED), not a MULTISTRING "values" list, so it gets its own extractors
# rather than reusing extract_list_branch_multistring_scores.
# ----------------------------------------------------------------------------------

def _tier_ladder_target_value(flow: dict, target_action_id: str) -> str:
    actions_by_id = {a["actionId"]: a for a in flow["actions"]}
    return actions_by_id[target_action_id]["fields"]["value"]["staticValue"]


def extract_wf1_veto_branch(flow: dict):
    """Returns (filter_operation_dict, written_tier_value) for the LIST_BRANCH action
    keyed on lv_anti_icp_flag, or None if the flow has no such branch."""
    branch_action = find_list_branch_action(flow, "lv_anti_icp_flag")
    if branch_action is None:
        return None
    lb = branch_action["listBranches"][0]
    filt = lb["filterBranch"]["filterBranches"][0]["filters"][0]
    tier_value = _tier_ladder_target_value(flow, lb["connection"]["nextActionId"])
    return filt["operation"], tier_value


def extract_wf1_score_ladder(flow: dict) -> dict:
    """Walks the LIST_BRANCH action keyed on lv_icp_fit_score and returns
    {lower_bound: tier_value} for each NUMBER_RANGED/NUMBER branch, plus the
    fall-through branch's tier under '__default__' (WF1 has no defaultBranch on this
    action -- the fourth listBranch, IS_LESS_THAN 15, plays that role)."""
    branch_action = find_list_branch_action(flow, "lv_icp_fit_score")
    ladder = {}
    for lb in branch_action["listBranches"]:
        filt = lb["filterBranch"]["filterBranches"][0]["filters"][0]
        op = filt["operation"]
        tier_value = _tier_ladder_target_value(flow, lb["connection"]["nextActionId"])
        if op["operator"] == "IS_LESS_THAN":
            ladder["__default__"] = tier_value
        else:
            ladder[op.get("lowerBound", op.get("value"))] = tier_value
    return ladder


def _wf1_enrollment_hs_names(flow: dict) -> set:
    return {
        f["operation"]["value"]
        for branch in flow["enrollmentCriteria"]["eventFilterBranches"]
        for f in branch["filters"]
        if f["property"] == "hs_name"
    }


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_wf1_enrollment_includes_score_and_veto_flag(flow_path):
    """VETO-03/F7 — WF1 must enroll on both lv_icp_fit_score known and
    lv_anti_icp_flag known, so a flag change alone re-enrolls a company whose score
    has not moved."""
    flow = load_flow(flow_path)
    if not _is_flow(flow) or find_list_branch_action(flow, "lv_anti_icp_flag") is None:
        pytest.skip(f"{flow_path} is not WF1")

    hs_names = _wf1_enrollment_hs_names(flow)
    assert {"lv_icp_fit_score", "lv_anti_icp_flag"} <= hs_names, (
        f"{flow_path}: enrollment criteria {sorted(hs_names)} must include both "
        "lv_icp_fit_score and lv_anti_icp_flag"
    )
    assert flow["enrollmentCriteria"]["shouldReEnroll"] is True


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_wf1_veto_branch_compares_string_true_and_writes_d(flow_path):
    """D-04 — the pipeline writes lv_anti_icp_flag as the quoted string "true", and
    HubSpot EQ filters compare strings, so WF1's veto branch must compare against the
    string "true", not a BOOL literal. The branch it guards must write D."""
    flow = load_flow(flow_path)
    if not _is_flow(flow) or find_list_branch_action(flow, "lv_anti_icp_flag") is None:
        pytest.skip(f"{flow_path} is not WF1")

    result = extract_wf1_veto_branch(flow)
    op, tier_value = result
    assert op["operationType"] == "STRING", f"{flow_path}: veto filter must be STRING, got {op['operationType']}"
    assert op["operator"] == "IS_EQUAL_TO"
    assert op["value"] == "true", f"{flow_path}: veto filter must compare to the string 'true', got {op['value']!r}"
    assert tier_value == "D", f"{flow_path}: veto branch must write D, got {tier_value!r}"


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_wf1_score_ladder_thresholds_match_rubric(flow_path):
    """ENGINE-07/F8 — the score-band ladder's thresholds must equal
    config/icp_scoring.yaml tier_rules' A/B/C min_score values (70/40/15), read from
    the rubric rather than hard-coded here, and the fall-through branch (below 15)
    must write Unscored, not D."""
    flow = load_flow(flow_path)
    if not _is_flow(flow) or find_list_branch_action(flow, "lv_icp_fit_score") is None:
        pytest.skip(f"{flow_path} is not WF1")

    tier_rules = load_rubric()["tier_rules"]
    ladder = extract_wf1_score_ladder(flow)

    assert ladder.get(tier_rules["A"]["min_score"]) == "A", (
        f"{flow_path}: score ladder at {tier_rules['A']['min_score']} must write A, got {ladder}"
    )
    assert ladder.get(tier_rules["B"]["min_score"]) == "B", (
        f"{flow_path}: score ladder at {tier_rules['B']['min_score']} must write B, got {ladder}"
    )
    assert ladder.get(tier_rules["C"]["min_score"]) == "C", (
        f"{flow_path}: score ladder at {tier_rules['C']['min_score']} must write C, got {ladder}"
    )
    assert ladder.get("__default__") == "Unscored", (
        f"{flow_path}: fall-through (below {tier_rules['C']['min_score']}) must write "
        f"Unscored, got {ladder.get('__default__')!r} (F8's exact defect shape if this is 'D')"
    )


def _wf1_written_tier_values(flow: dict) -> set:
    """Every distinct lv_icp_tier value any SINGLE_CONNECTION action in this flow can
    write."""
    return {
        a["fields"]["value"]["staticValue"]
        for a in flow["actions"]
        if a.get("type") == "SINGLE_CONNECTION"
        and a["fields"]["property_name"] == "lv_icp_tier"
    }


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_wf1_writable_tier_values_exactly_five(flow_path):
    """Permanent regression guard (Task 3) — the complete set of lv_icp_tier values
    WF1 can ever write is exactly A, B, C, D and Unscored. Needs Review is
    deliberately absent: src/icp_scoring.py can emit it (the confidence-downgrade
    branch when lv_org_type/lv_produces_content is missing), but no HubSpot workflow
    in this phase models that branch and no Phase 40 requirement asks for one --
    REQUIREMENTS.md lists the review-queue policy as an explicitly deferred future
    requirement, and 40-02's parity harness records this exact divergence as an
    accepted, documented assumption (not a gap to "fix" by adding an option here)."""
    flow = load_flow(flow_path)
    if not _is_flow(flow) or find_list_branch_action(flow, "lv_anti_icp_flag") is None:
        pytest.skip(f"{flow_path} is not WF1")

    assert _wf1_written_tier_values(flow) == {"A", "B", "C", "D", "Unscored"}, (
        f"{flow_path}: writable tier values {_wf1_written_tier_values(flow)} must be "
        "exactly {'A', 'B', 'C', 'D', 'Unscored'}"
    )


@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_wf1_d_is_written_only_on_the_veto_guarded_branch(flow_path):
    """Direct F8 regression guard (Task 3) — this is the assertion that would have
    caught F8 when it was introduced: D must be reachable through exactly one path,
    the LIST_BRANCH keyed on lv_anti_icp_flag, and the score-band ladder (keyed on
    lv_icp_fit_score alone) must never write D on any branch, including the
    fall-through."""
    flow = load_flow(flow_path)
    if not _is_flow(flow) or find_list_branch_action(flow, "lv_anti_icp_flag") is None:
        pytest.skip(f"{flow_path} is not WF1")

    veto_op, veto_tier = extract_wf1_veto_branch(flow)
    assert veto_tier == "D"

    score_ladder = extract_wf1_score_ladder(flow)
    score_only_d_branches = [bound for bound, tier in score_ladder.items() if tier == "D"]
    assert not score_only_d_branches, (
        f"{flow_path}: the score-only ladder writes D on branch(es) {score_only_d_branches} "
        "-- D must be reachable only through the veto-guarded branch (F8)"
    )


# ----------------------------------------------------------------------------------
# 40-REVIEW.md WR-02/WR-04 — documented, not-yet-fixed edges (PORTAL-FACTS.md has the
# full rationale for why these are locked in as regression guards rather than live-PUT
# changed in this pass: no HUBSPOT_PRIVATE_APP_TOKEN available to run a D-07 round-trip
# here, and both are currently behaviorally harmless per the analysis below). These
# tests exist so a future silent shape change is caught and reviewed deliberately.
# ----------------------------------------------------------------------------------

@pytest.mark.parametrize("flow_path", _after_json_paths())
def test_wf1_score_ladder_action_has_no_default_branch_documented_race(flow_path):
    """WR-02 — action '3' (the lv_icp_fit_score ladder) has no top-level
    'defaultBranch' key, unlike action '2' (the veto check) in the same flow and unlike
    action '1' in every geography/revenue/org-type mapper flow. A genuinely blank
    lv_icp_fit_score reaching this action matches none of the four named branches and,
    with no defaultBranch to fall through to, writes nothing that pass -- see
    PORTAL-FACTS.md's 'WR-02' section for why this is a real but self-correcting race
    (WF1 re-enrolls once the score itself becomes known) and not being live-edited in
    this pass. If this assertion ever needs to flip (a defaultBranch is added), update
    PORTAL-FACTS.md's WR-02 note in the same change."""
    flow = load_flow(flow_path)
    if not _is_flow(flow) or find_list_branch_action(flow, "lv_anti_icp_flag") is None:
        pytest.skip(f"{flow_path} is not WF1")

    score_ladder_action = next(
        a for a in flow["actions"]
        if a.get("type") == "LIST_BRANCH"
        and any(
            f.get("property") == "lv_icp_fit_score"
            for lb in a.get("listBranches", [])
            for ab in lb["filterBranch"].get("filterBranches", [])
            for f in ab.get("filters", [])
        )
    )
    assert "defaultBranch" not in score_ladder_action, (
        f"{flow_path}: action {score_ladder_action['actionId']!r} now has a "
        "defaultBranch -- WR-02's documented race is fixed, update PORTAL-FACTS.md's "
        "WR-02 section and this assertion together"
    )
    veto_action = next(
        a for a in flow["actions"]
        if a.get("type") == "LIST_BRANCH"
        and any(
            f.get("property") == "lv_anti_icp_flag"
            for lb in a.get("listBranches", [])
            for ab in lb["filterBranch"].get("filterBranches", [])
            for f in ab.get("filters", [])
        )
    )
    assert "defaultBranch" in veto_action, (
        f"{flow_path}: veto action {veto_action['actionId']!r} unexpectedly lost its "
        "defaultBranch (the sibling comparison WR-02 relies on)"
    )


def _mapper_flow_enrolls_on_createdate(flow: dict) -> bool:
    return any(
        f["operation"].get("value") == "createdate"
        for branch in flow["enrollmentCriteria"]["eventFilterBranches"]
        for f in branch["filters"]
        if f["property"] == "hs_name"
    )


def test_mapper_flow_createdate_enrollment_is_currently_two_of_five():
    """WR-04 — exactly gambling-score and produces-content-score (40-04's two flows)
    enroll on 'createdate IS_KNOWN' in addition to their own property change; the
    other three component mapper flows (org-type, geography, annual-revenue) enroll
    only on their own property. See PORTAL-FACTS.md's 'WR-04' section: this asymmetry
    is currently harmless because the calculated lv_icp_fit_score formula blanks on
    any null component term regardless of which 2-of-5 terms are pre-seeded to 0. This
    is a locked-in snapshot of the current (inconsistent) state, not an endorsement --
    if a future change normalizes all five flows one way or the other, update this
    assertion and PORTAL-FACTS.md's WR-04 section together."""
    mapper_paths = {
        "gambling-score": FLOWS_DIR / "gambling-score.after.json",
        "produces-content-score": FLOWS_DIR / "produces-content-score.after.json",
        "org-type-score": FLOWS_DIR / "4626124224-org-type-score.after.json",
        "geography-score": FLOWS_DIR / "4626722240-geography-score.after.json",
        "annual-revenue-score": FLOWS_DIR / "4626722237-annual-revenue-score.after.json",
    }
    enrolls_on_createdate = {
        name: _mapper_flow_enrolls_on_createdate(load_flow(path))
        for name, path in mapper_paths.items()
    }
    assert enrolls_on_createdate == {
        "gambling-score": True,
        "produces-content-score": True,
        "org-type-score": False,
        "geography-score": False,
        "annual-revenue-score": False,
    }, f"createdate enrollment mix changed: {enrolls_on_createdate}"
