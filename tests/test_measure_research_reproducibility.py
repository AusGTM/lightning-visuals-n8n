# tests/test_measure_research_reproducibility.py
#
# Phase 51 Plan 03 checkpoint round 2 -- offline, mocked test for
# scripts/measure_research_reproducibility.py's aggregation logic. Plain pytest, plain
# asserts, matches tests/test_icp_scoring.py's style. No live Anthropic/HubSpot/ZoomInfo
# call happens in this suite -- claude_web_research is monkeypatched.
from scripts import measure_research_reproducibility as m
from src.schemas import ProviderEvidence, ProviderResult


def _result(produces_content, org_type="individual_club_team", confidence=90, with_evidence=True):
    return ProviderResult(
        provider="claude_web",
        object_type="companies",
        matched=True,
        confidence=confidence,
        data={"lv_org_type": org_type, "lv_produces_content": produces_content,
              "lv_is_hardware_vendor": False, "lv_is_gambling_operator": False},
        evidence=ProviderEvidence(),
        evidence_by_field={"lv_produces_content": "https://example.com"} if with_evidence else {},
    )


def test_flip_detected_when_value_changes_across_repetitions(monkeypatch):
    # Company A: lv_produces_content flips false/true/false across 3 calls -- flipped.
    # Company B: every field stable across 3 calls -- not flipped.
    calls = {"n": 0}

    def mock_research(record):
        calls["n"] += 1
        if record.id == "A":
            sequence = [False, True, False]
            idx = (calls["n"] - 1) % 3
            return _result(sequence[idx])
        return _result(True)

    monkeypatch.setattr(m, "claude_web_research", mock_research)

    companies = [{"id": "A", "name": "Company A"}, {"id": "B", "name": "Company B"}]
    result = m.measure(companies, repetitions=3)

    assert result["anthropic_calls_made"] == 6
    assert result["per_field_flip_counts"]["lv_produces_content"] == 1  # only A flipped
    assert result["per_company"]["A"]["fields"]["lv_produces_content"]["flipped"] is True
    assert result["per_company"]["B"]["fields"]["lv_produces_content"]["flipped"] is False
    assert set(result["per_company"]["A"]["fields"]["lv_produces_content"]["distinct_values"]) == {False, True}


def test_matched_companies_excludes_unmatched_ids(monkeypatch):
    def mock_sample(size, media_slots):
        return [
            {"id": "9604726292", "name": "Narromine Turf Club"},  # UNMATCHED_IDS
            {"id": "9604623716", "name": "Taree Wingham Race Club"},  # UNMATCHED_IDS
            {"id": "9604630690", "name": "Gold Coast Turf Club"},
        ]

    monkeypatch.setattr(m, "select_diversified_never_scored_sample", mock_sample)

    companies = m.matched_companies()
    assert [c["id"] for c in companies] == ["9604630690"]


def test_observation_records_confidence_and_evidence_presence():
    result = _result(True, confidence=60, with_evidence=False)
    obs = m._observation(result)
    assert obs["confidence"] == 60
    assert obs["fields"]["lv_produces_content"]["has_evidence_url"] is False
    assert obs["fields"]["lv_produces_content"]["value"] is True


def test_observation_handles_none_result_without_crashing():
    # research_with_majority_vote returns None when every internal repetition fails --
    # _observation must record that as a valid, empty observation, not raise.
    obs = m._observation(None)
    assert obs["confidence"] is None
    assert obs["fields"]["lv_produces_content"]["value"] is None
    assert obs["fields"]["lv_produces_content"]["has_evidence_url"] is False


def test_matched_companies_respects_ids_filter(monkeypatch):
    def mock_sample(size, media_slots):
        return [
            {"id": "9604630690", "name": "Gold Coast Turf Club"},
            {"id": "9604732796", "name": "Warwick Turf Club"},
        ]

    monkeypatch.setattr(m, "select_diversified_never_scored_sample", mock_sample)

    companies = m.matched_companies(ids={"9604732796"})
    assert [c["id"] for c in companies] == ["9604732796"]


def test_measure_majority_vote_mode_calls_wrapper_and_counts_raw_calls(monkeypatch):
    # --mode majority_vote must call research_with_majority_vote (not claude_web_research
    # directly) and count RESEARCH_VOTE_REPETITIONS raw calls per invocation -- a ceiling
    # projection matching scripts.backfill_dry_run's own convention.
    calls = {"n": 0}

    def mock_vote(record):
        calls["n"] += 1
        return _result(True)

    monkeypatch.setattr(m, "research_with_majority_vote", mock_vote)

    companies = [{"id": "A", "name": "Company A"}]
    result = m.measure(companies, repetitions=2, mode="majority_vote")

    assert calls["n"] == 2  # 2 repetitions, one wrapper call each
    assert result["anthropic_calls_made"] == 2 * m.RESEARCH_VOTE_REPETITIONS
    assert result["mode"] == "majority_vote"
