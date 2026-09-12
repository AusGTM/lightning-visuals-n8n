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
    route_overflow,
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


def stage_only_fake(record, field, current_value, candidates, policy):
    return {"decision": "stage_only", "confidence": 90, "reason": "test",
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
    # Phase 15: staging folds into the provenance blob — no flat zoominfo_/apollo_ staging
    # properties; staging_patch itself stays empty.
    assert mr.staging_patch == {}
    provenance = json.loads(mr.metadata_patch["lv_enrichment_provenance"])
    assert provenance["domain"]["source"] in ("zoominfo", "apollo", "lusha")

    # system_owned lv_org_type promotes
    assert mr.canonical_patch.get("lv_org_type") == "governing_body_league"


def test_sc4_full_source_attribution(monkeypatch):
    monkeypatch.setattr("src.merge_policy.classify_field_with_haiku", promote_fake)
    record = load_record()
    mr = build_merge_result(record, build_all_candidates(record))

    # Phase 15: per-field metadata rides in ONE provenance blob, not flat {field}_* keys.
    assert "lv_enrichment_provenance" in mr.metadata_patch
    provenance = json.loads(mr.metadata_patch["lv_enrichment_provenance"])
    entry = provenance["lv_org_type"]
    for key in ["source", "confidence", "verified_at", "validation_status", "value"]:
        assert key in entry, f"provenance[lv_org_type] missing {key}"

    # by design entry["evidence_url"] is the LIST (Phase 4 serializes; Phase 15 keeps it)
    org_cand = next(c for c in build_all_candidates(record) if c.canonical_field == "lv_org_type")
    assert entry["evidence_url"] == org_cand.evidence.evidence_urls
    assert isinstance(entry["evidence_url"], list)

    # the 2 company cache-key datetimes are real top-level properties (RT-5/SJ-2)
    assert "lv_org_type_verified_at" in mr.metadata_patch
    assert mr.metadata_patch["lv_org_type_verified_at"] == entry["verified_at"]
    if "lv_produces_content" in provenance:
        assert "lv_produces_content_verified_at" in mr.metadata_patch
        assert mr.metadata_patch["lv_produces_content_verified_at"] == provenance["lv_produces_content"]["verified_at"]


def test_sc4b_cache_key_not_stamped_unless_promoted(monkeypatch):
    # Bug 2 (STATE.md 16.3-01 "Found, not fixed"): the JS mergeContacts.js/mergeCompanies.js
    # stamp their cache-key verified_at datetime ONLY when a field is promoted (Phase
    # 16.2/16.3 stale-timestamp fix). Python's build_merge_result used to derive the same
    # cache-key datetimes (lv_org_type_verified_at / lv_produces_content_verified_at) from
    # `if field in provenance` alone -- true for ANY chosen candidate regardless of the
    # final decision. Force every field to stage_only: the provenance blob (audit trail)
    # must still record the candidate, but the cache-key datetime -- the thing RT-5/SJ-2's
    # stale-refresh scan reads -- must not be stamped, or a staged-not-promoted field would
    # look "freshly verified" and never get re-picked up.
    monkeypatch.setattr("src.merge_policy.classify_field_with_haiku", stage_only_fake)
    record = load_record()
    mr = build_merge_result(record, build_all_candidates(record))

    assert "lv_org_type" not in mr.canonical_patch

    provenance = json.loads(mr.metadata_patch["lv_enrichment_provenance"])
    assert "lv_org_type" in provenance, "audit trail must still record the evaluated candidate"

    assert "lv_org_type_verified_at" not in mr.metadata_patch


# --- integ: end-to-end wiring incl. Phase 2 scorer, offline, no monkeypatch ---

def test_integ_wires_icp_scorer():
    # Approach C (Phase 15 criterion 4): the write path to lv_icp_fit_score/lv_icp_tier is
    # retired — HubSpot owns the derived outputs. These assertions prove the write path is
    # GONE; reintroducing it turns them red. The engine still computes icp_score internally
    # (mr.icp_score is not None) for in-pipeline routing and the audit breakdown.
    record = load_record()
    mr = build_merge_result(record, build_all_candidates(record))
    assert "lv_icp_fit_score" not in mr.canonical_patch
    assert "lv_icp_tier" not in mr.canonical_patch
    assert mr.status_patch["enrichment_status"] in ("complete", "needs_review")
    assert mr.icp_score is not None


def test_group_candidates_buckets_by_field():
    cands = [make_candidate("a", "zoominfo", 1, 80), make_candidate("a", "apollo", 2, 70),
             make_candidate("b", "zoominfo", 3, 80)]
    grouped = group_candidates(cands)
    assert set(grouped.keys()) == {"a", "b"}
    assert len(grouped["a"]) == 2
    assert choose_best(grouped["a"], PRIORITY).provider == "zoominfo"


# --- Provenance-aware manual_protected (quick task 260904-pav) ---------------
# JS twin: tests/n8n/mergeCompanies.test.mjs's "Provenance-aware manual_protected"
# block. A `domain` the enrichment system parked itself (provenance source
# `create_seed`) may be corrected by the system's own later, better answer; every
# other provenance story refuses exactly as before.
PAV_SEEDED = "brisbanelions.com.au"
PAV_CORRECTED = "lions.com.au"
PAV_POLICY = {"class": "manual_protected", "min_confidence": 95,
              "system_correctable_sources": ["create_seed"]}


def pav_entry(**overrides):
    entry = {"source": "create_seed", "confidence": 0,
             "verified_at": "2026-09-04T00:00:00.000Z",
             "validation_status": "request_echo", "value": PAV_SEEDED}
    entry.update(overrides)
    return entry


def pav_record(blob):
    props = {"domain": PAV_SEEDED}
    if blob is not None:
        props["lv_enrichment_provenance"] = blob
    return HubSpotRecord(object_type="companies", id="285583534546", properties=props)


def pav_gate(blob, candidates=None, policy=None):
    candidates = candidates or [make_candidate("domain", "zoominfo", PAV_CORRECTED, 95)]
    return deterministic_gate(pav_record(blob), "domain", PAV_SEEDED, candidates,
                              policy or PAV_POLICY, PRIORITY)


def test_pav_create_seed_provenance_allows_correction():
    g = pav_gate(json.dumps({"domain": pav_entry()}))
    assert g["decision"] == "promote"


def test_pav_human_provenance_still_refuses():
    g = pav_gate(json.dumps({"domain": pav_entry(source="human")}))
    assert g["decision"] == "stage_only"
    assert g["reason"] == "Field is manual_protected."


def test_pav_no_provenance_refuses_fail_closed():
    assert pav_gate(None)["decision"] == "stage_only"


def test_pav_unparseable_blob_refuses_and_does_not_raise():
    assert pav_gate("{not json")["decision"] == "stage_only"


def test_pav_stale_recorded_value_refuses():
    # A human has since retyped the domain, or a previously REFUSED candidate left the
    # entry behind — either way the recorded value is no longer the current one.
    g = pav_gate(json.dumps({"domain": pav_entry(value="someone-elses.example")}))
    assert g["decision"] == "stage_only"


def test_pav_conflicting_candidates_block_the_correction():
    # The Python twin of the JS engine's opts.rowConflicted: this function has no
    # row-level conflict object, only its own candidate list.
    candidates = [make_candidate("domain", "zoominfo", PAV_CORRECTED, 95),
                  make_candidate("domain", "apollo", "franchisor.example", 95)]
    assert pav_gate(json.dumps({"domain": pav_entry()}),
                    candidates=candidates)["decision"] == "stage_only"


def test_pav_correction_still_held_to_min_confidence():
    candidates = [make_candidate("domain", "zoominfo", PAV_CORRECTED, 94)]
    g = pav_gate(json.dumps({"domain": pav_entry()}), candidates=candidates)
    assert g["decision"] == "needs_review"


def test_pav_field_without_system_correctable_sources_is_unchanged():
    policy = {"class": "manual_protected", "min_confidence": 95}
    g = pav_gate(json.dumps({"domain": pav_entry()}), policy=policy)
    assert g["decision"] == "stage_only"
    assert g["reason"] == "Field is manual_protected."


# --- Phase 72 Plan 04: recency/TTL gate for stale_refreshable fields -----------------
#
# Mirrors tests/n8n/mergeRecencyGate.test.mjs's shared fixture table -- the three
# engines (mergeContacts.js, mergeCompanies.js, this Python oracle) must agree
# field-for-field. Before this plan, ANY non-blank stale_refreshable candidate answered
# needs_review unconditionally, regardless of staleness -- this is genuinely new logic.

NOW = "2026-09-12T00:00:00+00:00"
STALE_400D = "2025-08-08T00:00:00+00:00"  # >365 days before NOW
FRESH_100D = "2026-06-04T00:00:00+00:00"  # <365 days before NOW

INDUSTRY_POLICY = {"class": "stale_refreshable", "min_confidence": 75, "stale_after_days": 365}


def industry_gate(current_value, candidates, *, now=NOW, history_by_field=None, policy=None):
    return deterministic_gate(None, "industry", current_value, candidates,
                               policy or INDUSTRY_POLICY, PRIORITY,
                               now=now, history_by_field=history_by_field)


def test_recency_stale_existing_value_plus_provider_observation_newer_promotes():
    g = industry_gate("Sports", [make_candidate("industry", "zoominfo", "Media Production", 90)],
                       history_by_field={"industry": STALE_400D})
    assert g["decision"] == "promote"


def test_recency_fresh_existing_value_needs_review_unchanged_pre72_reason():
    g = industry_gate("Sports", [make_candidate("industry", "zoominfo", "Media Production", 90)],
                       history_by_field={"industry": FRESH_100D})
    assert g["decision"] == "needs_review"
    assert g["reason"] == "Refresh candidate requires review in MVP."


def test_recency_no_history_timestamp_needs_review_naming_unknown_freshness():
    g = industry_gate("Sports", [make_candidate("industry", "zoominfo", "Media Production", 90)],
                       history_by_field=None)
    assert g["decision"] == "needs_review"
    assert "unknown freshness" in g["reason"].lower()


def test_recency_stale_but_candidate_carries_no_clock_needs_review():
    # A "csv"-provenanced candidate carries no observation time -- this is the Python
    # twin of the JS engines' clockless-source case (no real CSV concept exists in this
    # oracle, so a synthetic non-provider "csv" candidate proves the same mechanism).
    g = industry_gate("Sports", [make_candidate("industry", "csv", "Media Production", 90)],
                       history_by_field={"industry": STALE_400D})
    assert g["decision"] == "needs_review"
    assert g["reason"] != "Refresh candidate requires review in MVP."


def test_recency_blank_current_value_still_promotes_unconditionally():
    g = industry_gate(None, [make_candidate("industry", "csv", "Media Production", 90)])
    assert g["decision"] == "promote"


def test_recency_fill_blank_only_field_unaffected():
    policy = {"class": "fill_blank_only", "min_confidence": 70}
    g = deterministic_gate(None, "numberofemployees", "50",
                            [make_candidate("numberofemployees", "zoominfo", "80", 90)],
                            policy, PRIORITY, now=NOW, history_by_field={"numberofemployees": STALE_400D})
    assert g["decision"] == "stage_only"


def test_recency_manual_protected_field_unaffected():
    g = deterministic_gate(None, "domain", "example.example",
                            [make_candidate("domain", "zoominfo", "other.example", 95)],
                            {"class": "manual_protected", "min_confidence": 95}, PRIORITY,
                            now=NOW, history_by_field={"domain": STALE_400D})
    assert g["decision"] == "stage_only"


# --- Task 2: the pipeline's own provider-written value becomes correctable -----------

CONTACT_JOBTITLE_POLICY = {"class": "stale_refreshable", "min_confidence": 75,
                            "stale_after_days": 180,
                            "system_correctable_sources": ["apollo", "lusha", "zoominfo", "claude_web"]}
INDUSTRY_CORRECTABLE_POLICY = {**INDUSTRY_POLICY,
                                "system_correctable_sources": ["apollo", "lusha", "zoominfo", "claude_web"]}


def sc_provenance_entry(**overrides):
    entry = {"source": "apollo", "confidence": 85, "verified_at": "2026-01-01T00:00:00+00:00",
             "validation_status": "provider_only", "value": "Old Title"}
    entry.update(overrides)
    return entry


def contact_record(blob):
    props = {"jobtitle": "Old Title"}
    if blob is not None:
        props["lv_contact_enrichment_provenance"] = blob
    return HubSpotRecord(object_type="contacts", id="123", properties=props)


def test_sc_contact_provenance_names_provider_value_matches_no_conflict_promotes_even_when_not_past_ttl():
    # Deliberately FRESH history -- the TTL branch alone would refuse.
    g = deterministic_gate(
        contact_record(json.dumps({"jobtitle": sc_provenance_entry()})), "jobtitle", "Old Title",
        [make_candidate("jobtitle", "zoominfo", "New Title", 90)], CONTACT_JOBTITLE_POLICY, PRIORITY,
        now=NOW, history_by_field={"jobtitle": FRESH_100D})
    assert g["decision"] == "promote"


def test_sc_contact_provenance_value_no_longer_matches_current_does_not_promote():
    g = deterministic_gate(
        contact_record(json.dumps({"jobtitle": sc_provenance_entry(value="Someone Else Retyped This")})),
        "jobtitle", "Old Title",
        [make_candidate("jobtitle", "zoominfo", "New Title", 90)], CONTACT_JOBTITLE_POLICY, PRIORITY,
        now=NOW, history_by_field={"jobtitle": FRESH_100D})
    assert g["decision"] == "needs_review"


def test_sc_contact_provenance_source_human_does_not_promote():
    g = deterministic_gate(
        contact_record(json.dumps({"jobtitle": sc_provenance_entry(source="human")})),
        "jobtitle", "Old Title",
        [make_candidate("jobtitle", "zoominfo", "New Title", 90)], CONTACT_JOBTITLE_POLICY, PRIORITY,
        now=NOW, history_by_field={"jobtitle": FRESH_100D})
    assert g["decision"] == "needs_review"


def test_sc_industry_provenance_names_provider_value_matches_no_conflict_promotes_even_when_not_past_ttl():
    record = HubSpotRecord(object_type="companies", id="789", properties={
        "industry": "Sports",
        "lv_enrichment_provenance": json.dumps({
            "industry": {"source": "apollo", "confidence": 85,
                         "verified_at": "2026-01-01T00:00:00+00:00",
                         "validation_status": "provider_only", "value": "Sports"}}),
    })
    g = deterministic_gate(record, "industry", "Sports",
                            [make_candidate("industry", "zoominfo", "Media Production", 90)],
                            INDUSTRY_CORRECTABLE_POLICY, PRIORITY,
                            now=NOW, history_by_field={"industry": FRESH_100D})
    assert g["decision"] == "promote"


def test_sc_domain_create_seed_correction_under_manual_protected_is_unaffected_regression():
    # Regression: the pre-existing companies.domain / manual_protected correction path
    # (260904-pav) must keep working unchanged after object_type-aware provenance-key
    # selection lands.
    assert pav_gate(json.dumps({"domain": pav_entry()}))["decision"] == "promote"


# --- Phase 72 Plan 05 (D-72-11/D-72-12): overflow-slot routing -----------------------
# JS twin: tests/n8n/overflowSlots.test.mjs's identical fixture table, exercised against
# mergeContacts.js/mergeCompanies.js's opts.rankedByField. Here `route_overflow` is
# exercised directly against `group_candidates`' output — the same grouped dict
# `build_merge_result` mutates in place.


def test_route_overflow_contacts_runner_up_lands_in_overflow_slot():
    grouped = group_candidates([
        make_candidate("mobilephone", "zoominfo", "+61400000001", 90),
        make_candidate("mobilephone", "apollo", "+61400000002", 80),
    ])
    tails = route_overflow("contacts", grouped, {})
    assert choose_best(grouped["mobilephone"], PRIORITY).provider == "zoominfo"
    assert len(grouped["lv_mobilephone_2"]) == 1
    assert grouped["lv_mobilephone_2"][0].provider == "apollo"
    assert tails == {}


def test_route_overflow_companies_runner_up_lands_in_overflow_slot():
    grouped = group_candidates([
        make_candidate("phone", "zoominfo", "+61212340001", 90),
        make_candidate("phone", "apollo", "+61212340002", 80),
    ])
    tails = route_overflow("companies", grouped, {})
    assert grouped["lv_phone_2"][0].provider == "apollo"
    assert tails == {}


def test_route_overflow_third_candidate_is_provenance_tail_only_no_slot_3():
    grouped = group_candidates([
        make_candidate("mobilephone", "zoominfo", "+61400000001", 90),
        make_candidate("mobilephone", "apollo", "+61400000002", 80),
        make_candidate("mobilephone", "lusha", "+61400000003", 70),
    ])
    tails = route_overflow("contacts", grouped, {})
    assert "lv_mobilephone_3" not in grouped
    assert tails == {"mobilephone": [{"source": "lusha", "value": "+61400000003"}]}


def test_route_overflow_agreeing_candidates_do_not_manufacture_an_overflow():
    grouped = group_candidates([
        make_candidate("mobilephone", "zoominfo", "0400000001", 90),
        make_candidate("mobilephone", "apollo", "0400000001", 80),
    ])
    route_overflow("contacts", grouped, {})
    assert "lv_mobilephone_2" not in grouped


def test_route_overflow_field_with_no_configured_slot_is_a_noop():
    grouped = group_candidates([
        make_candidate("email", "zoominfo", "a@example.com", 90),
        make_candidate("email", "apollo", "b@example.com", 80),
    ])
    tails = route_overflow("contacts", grouped, {})
    assert "lv_email_2" not in grouped
    assert tails == {"email": [{"source": "apollo", "value": "b@example.com"}]}


def test_route_overflow_no_material_conflict_groups_touched_ro2():
    from src.judge import MATERIAL_CONFLICT_GROUPS
    watched = {f for g in MATERIAL_CONFLICT_GROUPS for f in g["fields"]}
    assert "phone" not in watched
    assert "mobilephone" not in watched
    assert "email" not in watched
