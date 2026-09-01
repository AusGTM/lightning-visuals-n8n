"""Tests for `preingest.parse_outcome` (Phase 61 Plan 04 Task 1, REVIEW-05).

The client-side half of the outcome contract: turn one per-row response item into a
typed `Outcome`. Fail toward the hold — a missing signal or an unrecognised version
must parse as unparseable, never as a good value; explicit `null` for a signal the row
genuinely never produced (no enrichment ran) must parse as a good, present-but-absent
value, never as unparseable — the two are different facts and this parser is what keeps
them from collapsing into one.
"""
import preingest


def _item(**overrides):
    base = {
        "row_id": "row-1",
        "outcome_contract_version": 1,
        "match": {"tier": "high", "auto": True, "reason": "matched by email", "candidates": []},
        "candidate_count": 0,
        "provider_agreement": None,
        "material_conflicts": None,
        "judge_adjudicated_fields": None,
    }
    base.update(overrides)
    return base


def test_a_well_formed_item_parses_with_every_signal_present():
    outcome = preingest.parse_outcome(_item(
        match={"tier": "medium", "candidates": [{"hs_object_id": "1"}, {"hs_object_id": "2"}]},
        candidate_count=2,
        provider_agreement={"jobtitle": ["apollo"]},
        material_conflicts=[{"group": "country", "fields": ["country"]}],
        judge_adjudicated_fields={"jobtitle": 88},
    ))

    assert outcome.parseable is True
    assert outcome.match_tier == "medium"
    assert outcome.candidate_count == 2
    assert outcome.provider_agreement == {"jobtitle": ["apollo"]}
    assert outcome.material_conflicts == [{"group": "country", "fields": ["country"]}]
    assert outcome.judge_adjudicated_fields == {"jobtitle": 88}


def test_a_row_with_no_enrichment_signals_parses_as_present_with_explicit_nulls():
    """Explicit absence ("no providers ran") must never read as unparseable — only a
    MISSING key or an unknown version does."""
    outcome = preingest.parse_outcome(_item())

    assert outcome.parseable is True
    assert outcome.provider_agreement is None
    assert outcome.material_conflicts is None
    assert outcome.judge_adjudicated_fields is None


def test_a_missing_outcome_contract_version_is_unparseable():
    item = _item()
    del item["outcome_contract_version"]
    outcome = preingest.parse_outcome(item)
    assert outcome.parseable is False


def test_an_unknown_outcome_contract_version_is_unparseable():
    outcome = preingest.parse_outcome(_item(outcome_contract_version=999))
    assert outcome.parseable is False


def test_version_2_also_parses_num_associated_contacts_read_separately_not_through_outcome(
):
    """Phase 62 Plan 04 (D-62-16): version 2 is now known (widened, not moved — the
    currently-deployed backend still stamps 1). num_associated_contacts is read by
    suggest_contacts.eligibility() off the raw row, never through this Outcome dataclass,
    so a version-2 item with no such field on it (and no such field on Outcome) still
    parses exactly like a version-1 one."""
    outcome = preingest.parse_outcome(_item(outcome_contract_version=2))
    assert outcome.parseable is True
    assert not hasattr(outcome, "num_associated_contacts")


def test_a_missing_candidate_count_is_unparseable():
    item = _item()
    del item["candidate_count"]
    outcome = preingest.parse_outcome(item)
    assert outcome.parseable is False


def test_a_missing_match_is_unparseable():
    item = _item()
    del item["match"]
    outcome = preingest.parse_outcome(item)
    assert outcome.parseable is False


def test_a_match_with_no_tier_is_unparseable():
    outcome = preingest.parse_outcome(_item(match={"candidates": []}))
    assert outcome.parseable is False


def test_a_non_dict_item_is_unparseable():
    assert preingest.parse_outcome(None).parseable is False
    assert preingest.parse_outcome("not a dict").parseable is False
    assert preingest.parse_outcome([1, 2, 3]).parseable is False


def test_the_unparseable_outcome_names_no_signal():
    outcome = preingest.parse_outcome(None)
    assert outcome.match_tier is None
    assert outcome.candidate_count is None
    assert outcome.provider_agreement is None
    assert outcome.material_conflicts is None
    assert outcome.judge_adjudicated_fields is None
