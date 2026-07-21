"""Acceptance tests for docs/WEB-RESEARCH-SPEC.md.

Spec-first: these encode the contract BEFORE the implementation exists. Unbuilt
requirements are marked `xfail(strict=True)` — when the implementation lands they flip to
XPASS, which strict mode reports as a FAILURE, forcing the marker to be removed. So the
suite stays green today and tells you exactly what to delete tomorrow.

Each test cites a requirement ID. Do not add a test here without one.
"""
import importlib

import pytest
import yaml

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAXONOMY = yaml.safe_load((ROOT / "config" / "taxonomy.yaml").read_text())
ORG_TYPES = set(TAXONOMY["org_types"])
CONTENT_TYPES = set(TAXONOMY["content_types"])

# The normalizer module does not exist yet (spec §3). Import lazily so collection works.
unbuilt = pytest.mark.xfail(strict=True, reason="not yet implemented — see spec §3/§6")


def _norm_mod():
    return importlib.import_module("src.taxonomy")


# --- §3 Normalization --------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("governing_body_league", "governing_body_league"),  # NM-2 exact
        ("league", "governing_body_league"),                 # NM-2 synonym
        ("Governing Body", "governing_body_league"),         # NM-3 case + space
        ("governing-body", "governing_body_league"),         # NM-3 punctuation
        ("  GOVERNING  BODY ", "governing_body_league"),     # NM-3 collapse
        ("bookmaker", "gambling_operator"),
        ("LED vendor", "hardware_vendor"),
        ("completely made up", "unknown"),                   # NM-1 fallback
        (None, "unknown"),
        ("", "unknown"),
    ],
)
def test_nm1_nm3_org_type_normalization(raw, expected):
    """NM-1/2/3: canonical key or the default, never anything else."""
    assert _norm_mod().normalize_org_type(raw) == expected


def test_nm1_never_returns_off_vocabulary():
    """NM-1: HubSpot rejects unknown enum values — this is correctness, not hygiene."""
    norm = _norm_mod().normalize_org_type
    for junk in ["sports thing", "<script>", "governing_body_leagueX", "42"]:
        assert norm(junk) in ORG_TYPES


def test_nm4_default_sets_needs_review():
    """NM-4: falling back to the default flags the record for review."""
    result = _norm_mod().normalize_org_type_result("something unmappable")
    assert result["value"] == "unknown"
    assert result["needs_review"] is True


def test_nm5_content_types_drop_unknown_and_dedupe():
    """NM-5: unrecognised entries are dropped, not passed through; result deduped."""
    out = _norm_mod().normalize_content_types(
        ["live stream", "streaming", "bogus_value", "highlights"]
    )
    assert set(out) <= CONTENT_TYPES
    assert "bogus_value" not in out
    assert len(out) == len(set(out))
    assert "streaming" in out and "highlights" in out


# --- §6 Output contract ------------------------------------------------------
def test_oc1_evidence_is_keyed_per_field():
    """OC-1: mergeCompanies takes {field: url}; a flat list does not satisfy the gate."""
    from src.web_research import claude_web_research  # noqa: F401

    result = _norm_mod().to_provider_result(
        {
            "data": {"lv_org_type": "governing_body_league", "lv_produces_content": True},
            "evidence_by_field": {
                "lv_org_type": "https://example.org/about",
                "lv_produces_content": "https://example.org/watch-live",
            },
        }
    )
    assert isinstance(result.evidence_by_field, dict)
    assert result.evidence_by_field["lv_produces_content"].startswith("http")


def test_oc2_oc3_output_values_are_canonical():
    """OC-2/OC-3: emitted org_type and content_type are post-normalization."""
    out = _norm_mod().validate_research_output(
        {
            "data": {
                "lv_org_type": "peak body",           # synonym
                "lv_content_type": ["live stream", "nonsense"],
                "lv_produces_content": True,
            },
            "evidence_by_field": {
                "lv_org_type": "https://x/about",
                "lv_produces_content": "https://x/live",
            },
        }
    )
    assert out["data"]["lv_org_type"] == "governing_body_league"
    assert set(out["data"]["lv_content_type"]) <= CONTENT_TYPES


def test_oc4_malformed_output_does_not_raise():
    """OC-4: unparseable model output -> matched: False, never an exception."""
    out = _norm_mod().validate_research_output("not json at all")
    assert out["matched"] is False


# --- §7 Tri-state ------------------------------------------------------------
def test_ts1_ts2_thin_evidence_yields_null_not_false():
    """TS-1/TS-2: a failed search is NOT evidence of absence.

    The ICP core is thin-web-presence ANZ clubs; emitting False here fires the
    no_content hard veto and permanently disqualifies a real prospect.
    """
    out = _norm_mod().validate_research_output(
        {
            "data": {"lv_org_type": "individual_club_team", "lv_produces_content": False},
            "evidence_by_field": {"lv_org_type": "https://x/about"},
            "evidence": {"evidence_urls": []},  # nothing found
        }
    )
    assert out["data"]["lv_produces_content"] is None, (
        "unevidenced False must be coerced to None (TS-2)"
    )


def test_ts3_false_requires_evidence_url():
    """TS-3: an evidenced False is allowed through."""
    out = _norm_mod().validate_research_output(
        {
            "data": {"lv_org_type": "individual_club_team", "lv_produces_content": False},
            "evidence_by_field": {
                "lv_org_type": "https://x/about",
                "lv_produces_content": "https://x/media",
            },
            "evidence": {"evidence_urls": ["https://x/media", "https://x/about"]},
        }
    )
    assert out["data"]["lv_produces_content"] is False


def test_ts4_queue_self_targets_no_blanket_gate():
    """TS-4: null routes by score — low scorers Unscored (no queue), plausible
    prospects Needs Review. This is why no blanket human gate is needed.

    Runs against the REAL scorer, so it guards live behaviour today.
    """
    from src.icp_scoring import compute_icp_score
    from src.schemas import HubSpotRecord

    def score(props):
        rec = HubSpotRecord(object_type="companies", id="1", properties=props)
        return compute_icp_score(rec, {})

    # no-content retailer: nothing to review, disqualifies itself quietly
    retailer = score({"lv_org_type": "other", "lv_produces_content": "",
                      "lv_country_region_normalized": "AU"})
    assert retailer.tier == "Unscored"
    assert retailer.anti_icp_flag is False, "null must NEVER fire the veto (TS-1)"

    # plausible prospect missing content evidence: correctly queued
    club = score({"lv_org_type": "governing_body_league", "lv_produces_content": "",
                  "lv_country_region_normalized": "AU"})
    assert club.tier == "Needs Review"
    assert club.anti_icp_flag is False


def test_ts1_null_and_false_are_not_interchangeable():
    """TS-1: the whole tri-state design in one assertion, against the real scorer."""
    from src.icp_scoring import compute_icp_score
    from src.schemas import HubSpotRecord

    base = {"lv_org_type": "governing_body_league", "lv_country_region_normalized": "AU"}

    def score(pc):
        rec = HubSpotRecord(object_type="companies", id="1",
                            properties={**base, "lv_produces_content": pc})
        return compute_icp_score(rec, {})

    assert score("").anti_icp_flag is False        # unknown -> parked
    assert score("false").anti_icp_flag is True    # evidenced absence -> vetoed
    assert score("false").tier == "D"


# --- §9 Acceptance / golden set ---------------------------------------------
def test_at2_off_vocabulary_from_model_becomes_unknown():
    """AT-2: the model ignoring the enum must not reach HubSpot."""
    out = _norm_mod().validate_research_output(
        {
            "data": {"lv_org_type": "esports_organiser", "lv_produces_content": True},
            "evidence_by_field": {"lv_org_type": "https://x/about",
                                  "lv_produces_content": "https://x/live"},
        }
    )
    assert out["data"]["lv_org_type"] == "unknown"
    assert out["needs_review"] is True


def test_er1_entity_resolution_present():
    """ER-1: represents is constrained to the documented set."""
    allowed = {"group", "subsidiary", "franchise_outlet", "single_entity", "unknown"}
    out = _norm_mod().validate_research_output(
        {
            "data": {"lv_org_type": "other", "lv_produces_content": None},
            "entity_resolution": {"represents": "franchise_outlet",
                                  "likely_revenue_band": "1.2B+", "notes": ""},
            "evidence_by_field": {},
        }
    )
    assert out["entity_resolution"]["represents"] in allowed
