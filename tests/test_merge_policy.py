# tests/test_merge_policy.py
#
# Phase 3 runnable proof for the enrichment pipeline + non-clobber merge engine.
# Fully OFFLINE and DETERMINISTIC — no Anthropic call, no network, no API key.
#
# Two things to know:
#   1. Monkeypatch at the merge_policy IMPORT SITE. merge_policy binds
#      classify_field_with_haiku / validate_conflict_with_sonnet at import via
#      `from .classifier_haiku import ...`, so we patch `src.merge_policy.*`,
#      NOT `src.classifier_haiku.*` — patching the origin module has no effect.
#   2. build_merge_result and compute_icp_score read config/*.yaml relative to
#      cwd, so this suite must be run from the repo root (fixtures are loaded
#      cwd-independently via FIX_DIR below).
import json
from pathlib import Path

from src.schemas import HubSpotRecord, ProviderEvidence, CandidateValue
from src.providers import get_mock_provider_waterfall
from src.web_research import mock_claude_web_research
from src.normalizer import (
    provider_to_candidates,
    normalize_revenue_band,
    normalize_employee_band,
    normalize_bool,
    normalize_country_region,
)
from src.merge_policy import (
    build_merge_result,
    deterministic_gate,
    has_conflict,
    choose_best,
    group_candidates,
)

FIX_DIR = Path(__file__).resolve().parent / "fixtures"
PRIORITY = ["zoominfo", "apollo", "lusha", "claude_web"]


def load_record():
    return HubSpotRecord(**json.loads((FIX_DIR / "company_current.json").read_text()))


def make_candidate(field, provider, value, confidence, urls=None):
    return CandidateValue(
        canonical_field=field,
        provider=provider,
        value=value,
        normalized_value=value,
        confidence=confidence,
        evidence=ProviderEvidence(evidence_urls=urls or [], evidence_summary="test"),
    )


def promote_fake(record, field, current_value, candidates, policy):
    return {"decision": "promote", "confidence": 90, "reason": "test",
            "requires_sonnet_validation": False}


# --- SC1: mock adapters + web research satisfy the ProviderResult contract ---

def test_sc1a_mock_adapters_return_contract():
    record = load_record()
    for adapter in get_mock_provider_waterfall():
        result = adapter.enrich(record)
        assert result.provider
        assert isinstance(result.matched, bool)
        assert isinstance(result.confidence, int)
        assert isinstance(result.data, dict)
        assert result.evidence is not None
        assert isinstance(result.model_trace, dict)


def test_sc1b_mock_web_research_returns_contract():
    result = mock_claude_web_research(load_record())
    assert result.provider == "claude_web"
    assert result.matched is True
    assert result.confidence > 0
    assert result.evidence.evidence_urls


# --- normalizer coverage ---

def test_norm_a_provider_to_candidates():
    record = load_record()
    adapters = {a.name: a for a in get_mock_provider_waterfall()}
    apollo_cands = provider_to_candidates(adapters["apollo"].enrich(record))
    assert apollo_cands
    assert all(c.canonical_field and c.normalized_value is not None for c in apollo_cands)
    # unmatched lusha fixture yields no candidates
    assert provider_to_candidates(adapters["lusha"].enrich(record)) == []


def test_norm_b_scalar_normalizers():
    assert normalize_revenue_band(12000000) == "5-50M"
    assert normalize_revenue_band(65000000) == "50-500M"
    assert normalize_employee_band(220) == "201-500"
    assert normalize_bool("true") is True
    assert normalize_country_region("Australia") == "AU"
    assert normalize_country_region("Germany") == "Other"


# --- SC2: conflict resolves via the deterministic gate, escalates only on policy ---

def test_sc2_conflict_escalates_only_when_policy_allows():
    apollo = make_candidate("lv_revenue_band", "apollo", "5-50M", 74)
    zoominfo = make_candidate("lv_revenue_band", "zoominfo", "50-500M", 83)
    conflict = [apollo, zoominfo]
    assert has_conflict(conflict) is True

    policy = {"class": "system_owned", "min_confidence": 75, "allow_sonnet_escalation": True}
    gate = deterministic_gate(None, "lv_revenue_band", None, conflict, policy, PRIORITY)
    assert gate["decision"] == "needs_review"
    assert gate["chosen"].provider == "zoominfo"  # highest priority wins

    # single non-conflicting candidate, no escalation flag -> promote, not needs_review
    single_policy = {"class": "system_owned", "min_confidence": 75}
    single_gate = deterministic_gate(None, "lv_revenue_band", None, [zoominfo], single_policy, PRIORITY)
    assert single_gate["decision"] == "promote"


# --- SC3: field-ownership governance at the gate (CLAUDE.md §24.1 cases 14/15/16) ---

def test_sc3_gate_governance():
    cand = make_candidate("f", "zoominfo", "v", 90)

    # case 14: manual_protected -> stage_only
    g = deterministic_gate(None, "domain", "anything", [cand],
                           {"class": "manual_protected", "min_confidence": 80}, PRIORITY)
    assert g["decision"] == "stage_only"

    # case 15: fill_blank_only with existing value -> stage_only
    g = deterministic_gate(None, "phone", "555-1234", [cand],
                           {"class": "fill_blank_only", "min_confidence": 80}, PRIORITY)
    assert g["decision"] == "stage_only"

    # case 16: fill_blank_only with blank value -> promote
    g = deterministic_gate(None, "phone", "", [cand],
                           {"class": "fill_blank_only", "min_confidence": 80}, PRIORITY)
    assert g["decision"] == "promote"

    # system_owned above threshold -> promote
    g = deterministic_gate(None, "lv_org_type", None, [cand],
                           {"class": "system_owned", "min_confidence": 80}, PRIORITY)
    assert g["decision"] == "promote"


# --- SC3-e2e + SC4: non-clobber governance and full attribution end-to-end ---

def build_all_candidates(record):
    results = [a.enrich(record) for a in get_mock_provider_waterfall()]
    results.append(mock_claude_web_research(record))
    return [c for r in results for c in provider_to_candidates(r)]


def test_sc3_e2e_promote_forced_still_protects_manual(monkeypatch):
    monkeypatch.setattr("src.merge_policy.classify_field_with_haiku", promote_fake)
    record = load_record()
    mr = build_merge_result(record, build_all_candidates(record))

    # manual_protected domain never reaches canonical even with promote-forced classifier
    assert "domain" not in mr.canonical_patch
    assert "zoominfo_domain" in mr.staging_patch
    assert "apollo_domain" in mr.staging_patch

    # system_owned lv_org_type promotes
    assert mr.canonical_patch.get("lv_org_type") == "governing_body_league"


def test_sc4_full_source_attribution(monkeypatch):
    monkeypatch.setattr("src.merge_policy.classify_field_with_haiku", promote_fake)
    record = load_record()
    mr = build_merge_result(record, build_all_candidates(record))

    for key in [
        "lv_org_type_source",
        "lv_org_type_confidence",
        "lv_org_type_evidence_url",
        "lv_org_type_evidence_summary",
        "lv_org_type_verified_at",
        "lv_org_type_verified_by_model",
        "lv_org_type_validation_status",
    ]:
        assert key in mr.metadata_patch

    # by design {field}_evidence_url in metadata_patch is the LIST (Phase 4 serializes)
    org_cand = next(c for c in build_all_candidates(record) if c.canonical_field == "lv_org_type")
    assert mr.metadata_patch["lv_org_type_evidence_url"] == org_cand.evidence.evidence_urls
    assert isinstance(mr.metadata_patch["lv_org_type_evidence_url"], list)


# --- integ: end-to-end wiring incl. Phase 2 scorer, offline, no monkeypatch ---

def test_integ_wires_icp_scorer():
    record = load_record()
    mr = build_merge_result(record, build_all_candidates(record))
    assert "lv_icp_fit_score" in mr.canonical_patch
    assert "lv_icp_tier" in mr.canonical_patch
    assert mr.status_patch["enrichment_status"] in ("complete", "needs_review")
    assert mr.icp_score is not None


def test_group_candidates_buckets_by_field():
    cands = [make_candidate("a", "zoominfo", 1, 80), make_candidate("a", "apollo", 2, 70),
             make_candidate("b", "zoominfo", 3, 80)]
    grouped = group_candidates(cands)
    assert set(grouped.keys()) == {"a", "b"}
    assert len(grouped["a"]) == 2
    assert choose_best(grouped["a"], PRIORITY).provider == "zoominfo"
