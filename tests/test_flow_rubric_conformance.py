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
    """40-04 (ENGINE-05) — gambling_score's mapper flow branch table must equal
    config/icp_scoring.yaml's graduated_deductions.gambling_operator: true -> -20,
    everything else -> 0. The flow must write only gambling_score — never
    lv_anti_icp_flag or lv_org_type — so the deduction stays independent of both
    the veto and the org-type branch (F9's original defect, T-40-15)."""
    flow = load_flow(flow_path)
    if not _is_flow(flow):
        pytest.skip(f"{flow_path} is not a flow archive")
    if find_static_branch_action(flow, "lv_is_gambling_operator") is None:
        pytest.skip(f"{flow_path} has no lv_is_gambling_operator STATIC_BRANCH action")

    rubric_deduction = load_rubric()["graduated_deductions"]["gambling_operator"]
    scores = extract_true_default_scores(flow, "lv_is_gambling_operator")

    assert scores["true"] == rubric_deduction, (
        f"{flow_path}: 'true' branch scores {scores['true']}, "
        f"rubric graduated_deductions.gambling_operator says {rubric_deduction}"
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
