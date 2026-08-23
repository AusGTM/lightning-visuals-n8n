# src/icp_scoring.py
#
# ICP scoring engine. Transcribed from CLAUDE.md §12.7 with exactly one
# documented correctness fix (see `content_points` below).
#
# Tier cutoffs are hard-coded here (>=70 A, >=40 B, >=15 C, else Unscored) and
# CONFIRMED to agree with config/icp_scoring.yaml `tier_rules` (A min 70,
# B 40-69, C 15-39) — config and code are consistent for the MVP.
import yaml
from .schemas import HubSpotRecord, ICPScoreResult


def load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def boolish(value):
    if isinstance(value, bool):
        return value
    if value in ["true", "True", "yes", "Yes", "1", 1]:
        return True
    if value in ["false", "False", "no", "No", "0", 0]:
        return False
    return None


def get_signal(record: HubSpotRecord, patch: dict, key: str, default=None):
    if key in patch:
        return patch.get(key)
    return record.properties.get(key, default)


def _parse_named_account_score_floor(value):
    """Defensive parse of lv_named_account_score_floor -- a plain HubSpot `number`
    property, but HubSpot returns numbers as strings over the API. None, "" and any
    non-numeric value all mean "no floor" and are returned as None (never raise); "60"
    and 60 both parse to 60.0. Quick task 260823-ono, post-CP1 retarget."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# Phase 50 Plan 06 (D-20): the veto is computed ONCE (compute_icp_score's own
# `anti_icp_flag` below) and this is a second SERIALIZATION of that single value, never a
# second derivation -- calculation_equation reads only numeric properties, so
# lv_anti_icp_flag_num is the only way lv_icp_tier_derived's veto branch can read the
# veto at all. src/merge_policy.py's Approach C removed the canonical write path in
# Phase 15 -- Python never PATCHes either property to HubSpot; this function exists so
# tests/test_icp_scoring.py can pin, offline, that the oracle's two serializations always
# agree, mirroring the single `flagIsSet` local scripts/build_cloud_workflows.py's
# `Decide Company Action` node assigns both properties from.
def anti_icp_flag_properties(flag: bool) -> dict:
    # D-04/P4 string-literal rule -- string values, never bare booleans, matching every
    # other HubSpot PATCH body in this repo.
    return {
        "lv_anti_icp_flag": "true" if flag else "false",
        "lv_anti_icp_flag_num": "1" if flag else "0",
    }


def compute_icp_score(record: HubSpotRecord, candidate_patch: dict, cfg: dict = None) -> ICPScoreResult:
    # Phase 46 Plan 01 (RUBRIC-02): additive, backward-compatible override -- every
    # existing two-positional-argument call site (tests/scoring_fixtures.py::expected_for,
    # scripts/backfill_seed_company_scores.py) keeps loading the on-disk rubric untouched.
    # Passing cfg= lets a caller (scripts/simulate_rubric_weights.py) score the same
    # record under a rubric that exists only in memory, never written to disk.
    cfg = cfg or load_yaml("config/icp_scoring.yaml")
    version = cfg.get("version", "unknown")

    org_type = get_signal(record, candidate_patch, "lv_org_type", "unknown") or "unknown"
    produces_content = boolish(get_signal(record, candidate_patch, "lv_produces_content"))
    # region_raw is the authoritative enrichment signal, checked BEFORE the native-country
    # fallback below: a blank/never-enriched lv_country_region_normalized is an absence of
    # enrichment, not a positive non-ANZ determination, and must never drive the hard veto
    # (debug: blank-region-fires-non-anz-veto -- 17 live companies, mostly AU racing clubs,
    # scored tier D off a blank region). `region` (with the country fallback applied) stays
    # for display/scoring only; region_key below keys off region_raw, not region.
    region_raw = get_signal(record, candidate_patch, "lv_country_region_normalized", None)
    region = region_raw
    if not region:
        region = get_signal(record, candidate_patch, "country", "Unknown")
    revenue_band = get_signal(record, candidate_patch, "lv_revenue_band", "unknown") or "unknown"

    is_hardware_vendor = boolish(get_signal(record, candidate_patch, "lv_is_hardware_vendor"))
    is_gambling_operator = boolish(get_signal(record, candidate_patch, "lv_is_gambling_operator"))
    # Quick task 260823-ono, retargeted post-CP1 (halt-b: enums are unreadable in a
    # calculation_equation on this portal -- CONTEXT.md's "Amendment 2026-08-23", operator
    # Option 1). floor_raw is defensively parsed: HubSpot returns numbers as strings, so
    # None, "" and any non-numeric junk all mean "no floor" -- never raise -- while "60"
    # and 60 both mean 60.0.
    floor_raw = get_signal(record, candidate_patch, "lv_named_account_score_floor", None)
    floor = _parse_named_account_score_floor(floor_raw)
    floor_active = floor is not None and floor > 0

    score = 0
    breakdown = {
        "version": version,
        "components": [],
        "hard_vetoes": [],
        "graduated_deductions": []
    }

    org_points = cfg["base_score"]["org_type"].get(org_type, 0)
    score += org_points
    breakdown["components"].append({"signal": "org_type", "value": org_type, "points": org_points})

    # DOCUMENTED DEVIATION from CLAUDE.md §12.7: the spec looked up produces_content
    # via .get(str(produces_content).lower(), 0). PyYAML parses the config's `true:`/
    # `false:` keys as Python booleans, so the dict is {True: 20, False: 0, "unknown": 0}
    # and a string lookup never matches — silently returning 0 and zeroing the +20
    # "produces content" rule (drops the flagship AU gov case from Tier A/80 to B/60).
    # Fix: look up the boolean/None value directly. True -> 20, False -> 0, None -> 0.
    content_points = cfg["base_score"]["produces_content"].get(produces_content, 0)
    score += content_points
    breakdown["components"].append({"signal": "produces_content", "value": produces_content, "points": content_points})

    if not region_raw:
        region_key = "unknown"
    else:
        region_key = region if region in ["AU", "NZ", "ANZ"] else "non_anz"
    geo_points = cfg["base_score"]["geography"].get(region_key, 0)
    score += geo_points
    breakdown["components"].append({"signal": "geography", "value": region, "points": geo_points})

    revenue_points = cfg["base_score"]["revenue_band"].get(revenue_band, 0)
    score += revenue_points
    breakdown["components"].append({"signal": "revenue_band", "value": revenue_band, "points": revenue_points})

    if is_gambling_operator:
        # Phase 46 Plan 01 (46-PATTERNS.md deviation, recorded in 46-01-SUMMARY.md):
        # .get-chained rather than the unconditional cfg["graduated_deductions"]
        # ["gambling_operator"] lookup, so a proposed cfg that has deleted the key (D-03,
        # Plan 04) scores 0 instead of raising KeyError. The breakdown entry is appended
        # only when the deduction is non-zero, so the current cfg (key present, -20)
        # still appends {"signal": "gambling_operator", "points": -20} unchanged.
        deduction = cfg.get("graduated_deductions", {}).get("gambling_operator", 0)
        score += deduction
        if deduction:
            breakdown["graduated_deductions"].append({"signal": "gambling_operator", "points": deduction})

    # Quick task 260823-ono, retargeted post-CP1 (CONTEXT.md's "Amendment 2026-08-23" --
    # supersedes the original enum decision). CP1 proved live that a `calculation_equation`
    # on this portal parses `string(<enum>)` but silently blanks once the enum has a value
    # (halt-b, 260823-ono-PROBE-VERDICT.json) -- so the mechanism is a plain operator-
    # editable NUMBER property, `lv_named_account_score_floor`, not an enumeration. A floor
    # value > 0 floors the score at that value for the five AU metro racing peak bodies
    # (ATC, MRC, SSR, BRC, Perth Racing) -- they govern and own tracks for smaller child
    # clubs and influence broadcasting via partner connections, which
    # individual_club_team's base weight under-values. Mirrors the HubSpot lv_icp_fit_score
    # calculation_equation floor (config/hubspot_flows/lv_icp_fit_score-property.after.json,
    # FORMULA-F) exactly -- no n8n mirror exists or is needed (Approach C removed the
    # canonical score/tier write from the n8n lane in Phase 15; see the quick task's
    # PLAN.md "Scope disclosures").
    #
    # Two pinned semantics, unchanged by the enum->number retarget:
    #   (a) NO CAP -- an earned base already >= 70 passes through `max()` untouched, same
    #       as the HubSpot formula's `max(<coalesced base>, <coalesced floor>)`.
    #   (b) The breakdown entry is appended even when the delta is 0 -- the override must
    #       be visible in the breakdown whether or not it actually raised the score.
    if floor_active:
        floored_score = max(score, int(floor))
        breakdown["components"].append({
            "signal": "named_account_score_floor", "value": floor,
            "points": floored_score - score,
        })
        score = floored_score

    anti_icp_flag = False
    anti_reasons = []

    if region_key == "non_anz":
        anti_icp_flag = True
        anti_reasons.append(cfg["hard_vetoes"]["non_anz"]["reason"])

    if produces_content is False:
        anti_icp_flag = True
        anti_reasons.append(cfg["hard_vetoes"]["no_content"]["reason"])

    # 47.5-C (47.5-C-DECISION.md, or-retroactive): the veto fires on EITHER trigger. The
    # boolean is suppressed by design — the research contract answers null without a cited
    # source, a true forces judge escalation, the D5 fail-safe demotes it back, and merge
    # then wants 85 confidence — so it sat on 1 of 66 live companies while lv_org_type,
    # which the pipeline reliably lands, said hardware_vendor for 2. OR rather than
    # replacing the boolean: purely additive (no record loses a veto) and the boolean
    # stays alive as a manual override. Must stay byte-identical to the JS port in
    # scripts/build_cloud_workflows.py's ENRICH_DECIDE_CO_CLOUD.
    if is_hardware_vendor or org_type == "hardware_vendor":
        anti_icp_flag = True
        anti_reasons.append(cfg["hard_vetoes"]["hardware_vendor"]["reason"])

    breakdown["hard_vetoes"] = anti_reasons

    if anti_icp_flag:
        tier = "D"
    elif score >= 70:
        tier = "A"
    elif score >= 40:
        tier = "B"
    elif score >= 15:
        tier = "C"
    else:
        tier = "Unscored"

    motion_map = cfg["recommended_motion"]
    recommended_motion = motion_map.get(tier, "research_more")

    # BUG FIX (STATE.md "SCORING PRECEDENCE RULE", Phase 14 found-not-fixed): a fired
    # hard veto must keep its D/disqualify label (CLAUDE.md 10.3) even when org_type/
    # produces_content is also missing. Confidence still drops to 55 either way -- the
    # underlying data really is incomplete and that stays visible in the breakdown --
    # but tier/recommended_motion are only downgraded when no veto has already won.
    confidence = 85
    if org_type == "unknown" or produces_content is None:
        confidence = 55
        # Quick task 260823-ono: the downgrade is guarded on WHETHER A FLOOR IS SET
        # (floor_active), not on whether the floor actually raised the score. The live
        # lv_icp_tier_derived ladder has no "Needs Review" branch at all (PARITY-01, an
        # accepted divergence) -- guarding on the override maximises parity with the live
        # ladder, and this is the exact record this task exists for: Perth Racing has
        # every input blank (org_type unknown, produces_content null) and must still land
        # on the floored score's tier, "B", not "Needs Review".
        if not anti_icp_flag and not floor_active:
            tier = "Needs Review" if score >= 15 else "Unscored"
            recommended_motion = "research_more"

    return ICPScoreResult(
        score=score,
        tier=tier,
        anti_icp_flag=anti_icp_flag,
        anti_icp_reason="; ".join(anti_reasons) if anti_reasons else None,
        recommended_motion=recommended_motion,
        confidence=confidence,
        breakdown=breakdown,
        scoring_version=version
    )
