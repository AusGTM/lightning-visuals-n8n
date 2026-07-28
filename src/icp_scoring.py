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


def compute_icp_score(record: HubSpotRecord, candidate_patch: dict) -> ICPScoreResult:
    cfg = load_yaml("config/icp_scoring.yaml")
    version = cfg.get("version", "unknown")

    org_type = get_signal(record, candidate_patch, "lv_org_type", "unknown") or "unknown"
    produces_content = boolish(get_signal(record, candidate_patch, "lv_produces_content"))
    region = get_signal(record, candidate_patch, "lv_country_region_normalized", None)
    if not region:
        region = get_signal(record, candidate_patch, "country", "Unknown")
    revenue_band = get_signal(record, candidate_patch, "lv_revenue_band", "unknown") or "unknown"

    is_hardware_vendor = boolish(get_signal(record, candidate_patch, "lv_is_hardware_vendor"))
    is_gambling_operator = boolish(get_signal(record, candidate_patch, "lv_is_gambling_operator"))

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

    region_key = region if region in ["AU", "NZ", "ANZ"] else "non_anz"
    geo_points = cfg["base_score"]["geography"].get(region_key, 0)
    score += geo_points
    breakdown["components"].append({"signal": "geography", "value": region, "points": geo_points})

    revenue_points = cfg["base_score"]["revenue_band"].get(revenue_band, 0)
    score += revenue_points
    breakdown["components"].append({"signal": "revenue_band", "value": revenue_band, "points": revenue_points})

    if is_gambling_operator:
        deduction = cfg["graduated_deductions"]["gambling_operator"]
        score += deduction
        breakdown["graduated_deductions"].append({"signal": "gambling_operator", "points": deduction})

    anti_icp_flag = False
    anti_reasons = []

    if region_key == "non_anz":
        anti_icp_flag = True
        anti_reasons.append(cfg["hard_vetoes"]["non_anz"]["reason"])

    if produces_content is False:
        anti_icp_flag = True
        anti_reasons.append(cfg["hard_vetoes"]["no_content"]["reason"])

    if is_hardware_vendor:
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
        if not anti_icp_flag:
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
