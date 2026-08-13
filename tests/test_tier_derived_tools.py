# tests/test_tier_derived_tools.py
#
# Phase 50 Plan 01 Task 1 -- offline test suite pinning the pure functions exposed by
# scripts/check_tier_null_propagation.py (D-05's probe) and scripts/check_tier_derived_parity.py
# (D-07's gate). Offline only: no network, no HubSpot credentials, no monkeypatched HTTP.
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from check_tier_null_propagation import (  # noqa: E402
    _writes_allowed,
    classify_probe_result,
    derived_tier,
    probe_formula_for,
    real_formula_for,
    settled_variant_for,
)
from check_tier_derived_parity import (  # noqa: E402
    KNOWN_STUCK_IDS,
    build_census_points,
    build_rows,
    classify_row,
    mirror_disagrees,
    render_census_markdown,
    render_evidence_markdown,
    render_mirror_section,
    render_parity_markdown,
    _current_null_variant,
)


# --- derived_tier: the ladder, mirroring WF1 exactly (spike Round 2, 7/7 accepted) -------

def test_derived_tier_boundary_70_69():
    assert derived_tier(70, False) == "A"
    assert derived_tier(69, False) == "B"


def test_derived_tier_boundary_40_39():
    assert derived_tier(40, False) == "B"
    assert derived_tier(39, False) == "C"


def test_derived_tier_boundary_15_14():
    assert derived_tier(15, False) == "C"
    assert derived_tier(14, False) == "Unscored"


def test_derived_tier_veto_precedes_score():
    assert derived_tier(85, True) == "D"


def test_derived_tier_negative_one_sentinel_lands_unscored():
    assert derived_tier(-1, False) == "Unscored"


def test_derived_tier_none_score_returns_none():
    # The blank branch under D-03's preferred uncoalesced variant.
    assert derived_tier(None, False) is None


# --- classify_probe_result ---------------------------------------------------------------

def test_classify_probe_result_value_is_uncoalesced_ok():
    assert classify_probe_result("Unscored") == "uncoalesced_ok"


@pytest.mark.parametrize("blank", [None, ""])
def test_classify_probe_result_blank_is_null_propagates(blank):
    assert classify_probe_result(blank) == "null_propagates"


# --- settled_variant_for / real_formula_for / probe_formula_for --------------------------

def test_settled_variant_for_maps_verdicts():
    assert settled_variant_for("uncoalesced_ok") == "uncoalesced"
    assert settled_variant_for("null_propagates") == "coalesced_minus_one"


def test_real_formula_for_uncoalesced_matches_spike_literal():
    formula = real_formula_for("uncoalesced")
    assert formula == (
        'if coalesce(lv_anti_icp_flag, 0) = 1 then "D" '
        'elseif lv_icp_fit_score >= 70 then "A" '
        'elseif lv_icp_fit_score >= 40 then "B" '
        'elseif lv_icp_fit_score >= 15 then "C" '
        'else "Unscored"'
    )


def test_real_formula_for_coalesced_wraps_every_bare_reference():
    formula = real_formula_for("coalesced_minus_one")
    assert formula.count("lv_icp_fit_score") == 3
    assert formula.count("coalesce(lv_icp_fit_score, -1)") == 3
    assert "lv_icp_fit_score >=" not in formula


def test_real_formula_for_unknown_variant_raises():
    with pytest.raises(ValueError):
        real_formula_for("bogus")


def test_probe_formula_for_substitutes_stand_in_property():
    formula = probe_formula_for("lv_tier_probe_score_abc")
    assert "lv_tier_probe_score_abc >= 70" in formula
    assert "lv_icp_fit_score" not in formula


# --- _writes_allowed: two-key gate, exact-string, disarmed by default ---------------------

@pytest.mark.parametrize(
    "dry_run, allow, expected",
    [
        (None, None, False),
        ("true", "true", False),
        ("false", "false", False),
        ("false", None, False),
        (None, "true", False),
        ("false", "true", True),
        ("False", "True", True),  # .lower() normalizes case the same as every sibling gate
    ],
)
def test_writes_allowed_only_when_both_keys_set(monkeypatch, dry_run, allow, expected):
    if dry_run is None:
        monkeypatch.delenv("DRY_RUN", raising=False)
    else:
        monkeypatch.setenv("DRY_RUN", dry_run)
    if allow is None:
        monkeypatch.delenv("ALLOW_TIER_NULL_PROBE", raising=False)
    else:
        monkeypatch.setenv("ALLOW_TIER_NULL_PROBE", allow)
    assert _writes_allowed() is expected


# --- classify_row ---------------------------------------------------------------------

def test_classify_row_known_stuck_id_lands_expected_mismatch():
    assert classify_row("9605273630", "C", "B", KNOWN_STUCK_IDS) == "expected_mismatch"


def test_classify_row_known_stuck_id_not_fixed_is_defect():
    assert classify_row("9605273630", "C", "C", KNOWN_STUCK_IDS) == "defect"


def test_classify_row_non_stuck_id_matching_is_match():
    assert classify_row("111", "A", "A", KNOWN_STUCK_IDS) == "match"


def test_classify_row_non_stuck_id_diverging_is_defect():
    assert classify_row("111", "A", "B", KNOWN_STUCK_IDS) == "defect"


def test_known_stuck_ids_are_the_four_from_windows_md():
    assert KNOWN_STUCK_IDS == frozenset({
        "9605273630", "9604738976", "17696004613", "19100977027",
    })


# --- render_parity_markdown -------------------------------------------------------------

def test_render_parity_markdown_empty_population_raises():
    with pytest.raises(ValueError):
        render_parity_markdown([], 0)


def test_render_parity_markdown_row_count_population_mismatch_raises():
    rows = [{"record_id": "1", "live_tier": "A", "derived_tier": "A",
              "classification": "match"}]
    with pytest.raises(ValueError):
        render_parity_markdown(rows, 2)


def test_render_parity_markdown_is_deterministic():
    rows = [
        {"record_id": "9605273630", "name": "Port Macquarie Race Club", "live_tier": "C",
         "derived_tier": "B", "fit_score": "45", "anti_icp_flag": None,
         "classification": "expected_mismatch"},
        {"record_id": "111", "name": "Some Co", "live_tier": "A", "derived_tier": "A",
         "fit_score": "80", "anti_icp_flag": None, "classification": "match"},
    ]
    first = render_parity_markdown(rows, 2)
    second = render_parity_markdown(rows, 2)
    assert first == second


# --- _teardown: archive order and loud partial-failure reporting -------------------------

def test_teardown_archives_calculated_property_before_numeric_property(monkeypatch):
    # The calculated property's formula references the numeric property; HubSpot 400s
    # archiving a property a live calculation still depends on. Regression for the leaked
    # lv_tier_probe_score_eb671fb7 disposable (2026-08-13 armed run).
    import check_tier_null_propagation as ctnp
    import src.hubspot_client as hsc

    archive_order = []
    monkeypatch.setattr(
        ctnp, "_archive_and_confirm_gone",
        lambda object_type, name: archive_order.append(name) or True,
    )
    monkeypatch.setattr(ctnp, "_company_gone", lambda company_id: True)
    monkeypatch.setattr(hsc, "delete_record", lambda *a, **k: None)

    result = ctnp._teardown("numeric_x", "calc_y", "company_z")

    assert archive_order == ["calc_y", "numeric_x"], archive_order
    assert result["all_gone"] is True


def test_teardown_partial_failure_is_reported_not_hidden(monkeypatch, capsys):
    import check_tier_null_propagation as ctnp
    import src.hubspot_client as hsc

    monkeypatch.setattr(
        ctnp, "_archive_and_confirm_gone",
        lambda object_type, name: name != "numeric_x",  # numeric leaks, calc archives clean
    )
    monkeypatch.setattr(ctnp, "_company_gone", lambda company_id: True)
    monkeypatch.setattr(hsc, "delete_record", lambda *a, **k: None)

    result = ctnp._teardown("numeric_x", "calc_y", "company_z")

    assert result["all_gone"] is False
    assert "TEARDOWN LEAKED" in capsys.readouterr().out


def test_render_parity_markdown_sorted_by_record_id():
    rows = [
        {"record_id": "200", "name": "B Co", "live_tier": "A", "derived_tier": "A",
         "fit_score": "80", "anti_icp_flag": None, "classification": "match"},
        {"record_id": "9605273630", "name": "Port Macquarie Race Club", "live_tier": "C",
         "derived_tier": "B", "fit_score": "45", "anti_icp_flag": None,
         "classification": "expected_mismatch"},
    ]
    text = render_parity_markdown(rows, 2)
    assert text.index("| 200 |") < text.index("| 9605273630 |")


# --- Phase 50 Plan 03: render_evidence_markdown / build_census_points / -----------------
# --- render_census_markdown (D-17 item 4, D-19) -----------------------------------------

_STUCK_RECORDS = [
    {"id": "9604738976", "name": "Bunbury Turf Club", "lv_icp_tier": "C",
     "lv_icp_tier_derived": "B", "lv_icp_fit_score": "45", "lv_anti_icp_flag": "false"},
    {"id": "9605273630", "name": "Port Macquarie Race Club", "lv_icp_tier": "C",
     "lv_icp_tier_derived": "B", "lv_icp_fit_score": "45", "lv_anti_icp_flag": "false"},
    {"id": "17696004613", "name": "Pinjarra Park", "lv_icp_tier": "C",
     "lv_icp_tier_derived": "B", "lv_icp_fit_score": "45", "lv_anti_icp_flag": "false"},
    {"id": "19100977027", "name": "Newcastle Harness Racing Club", "lv_icp_tier": "C",
     "lv_icp_tier_derived": "B", "lv_icp_fit_score": "45", "lv_anti_icp_flag": "false"},
]
_CLEAN_RECORD = {"id": "111", "name": "Some Co", "lv_icp_tier": "A",
                  "lv_icp_tier_derived": "A", "lv_icp_fit_score": "80",
                  "lv_anti_icp_flag": "false"}


def test_render_evidence_markdown_pass_verdict_and_denominator():
    rows = build_rows(_STUCK_RECORDS + [_CLEAN_RECORD])
    text = render_evidence_markdown(rows, len(rows), 712, "2026-08-14T00:00:00Z")
    assert "Only 5 of 712 companies" in text
    assert "D-07 VERDICT: PASS" in text
    for windows_id in (9, 10, 11, 12):
        assert f"| {windows_id} |" in text


def test_render_evidence_markdown_fail_verdict_names_defect_rows():
    broken = [dict(r) for r in _STUCK_RECORDS]
    broken[0]["lv_icp_tier_derived"] = "A"  # a real defect: not the accepted C->B mismatch
    rows = build_rows(broken + [_CLEAN_RECORD])
    text = render_evidence_markdown(rows, len(rows), 712, "2026-08-14T00:00:00Z")
    assert "D-07 VERDICT: FAIL" in text
    assert "9604738976" in text


def test_build_census_points_uses_blank_tier_key_for_none():
    rows = build_rows([{"id": "222", "name": "Blank Co", "lv_icp_tier": None,
                         "lv_icp_tier_derived": None, "lv_icp_fit_score": "0",
                         "lv_anti_icp_flag": "false"}])
    before, after = build_census_points(rows)
    assert before["tier_distribution"] == {"Unscored-or-blank": 1}
    assert after["tier_distribution"] == {"Unscored-or-blank": 1}


def test_render_census_markdown_matches_pre_registered_expectation():
    rows = build_rows(_STUCK_RECORDS + [_CLEAN_RECORD])
    before, after = build_census_points(rows)
    text = render_census_markdown(before, after, 646, "coalesced_minus_one", "2026-08-14T00:00:00Z")
    assert "Census matches the pre-registered expectation." in text
    assert "646 never-enriched companies" in text
    for windows_record in _STUCK_RECORDS:
        assert windows_record["id"] in text


def test_render_census_markdown_flags_unexpected_movement_as_defect():
    broken = [dict(r) for r in _STUCK_RECORDS]
    broken[0]["lv_icp_tier"] = "A"  # unexpected: not the pre-registered C->B move
    rows = build_rows(broken + [_CLEAN_RECORD])
    before, after = build_census_points(rows)
    text = render_census_markdown(before, after, 646, "coalesced_minus_one", "2026-08-14T00:00:00Z")
    assert "DEFECT: the census diverges from the pre-registered expectation" in text


def test_render_census_markdown_severity_callout_for_d_tier_records():
    """A vetoed record (Before tier D) that no longer reads D After triggers the explicit
    SEVERITY callout -- not just the generic DEFECT line -- naming the record so the
    consequence (derived property less safe than the stale enum for that record) is
    visible to anyone reading only this artifact."""
    vetoed = {"id": "18047161864", "name": "Simtech LED", "lv_icp_tier": "D",
              "lv_icp_tier_derived": "B", "lv_icp_fit_score": "40",
              "lv_anti_icp_flag": "true"}
    rows = build_rows(_STUCK_RECORDS + [_CLEAN_RECORD, vetoed])
    before, after = build_census_points(rows)
    text = render_census_markdown(before, after, 646, "coalesced_minus_one", "2026-08-14T00:00:00Z")
    assert "SEVERITY" in text
    assert "Simtech LED" in text
    assert "D-06/D-08 stay blocked" in text


def test_render_census_markdown_no_severity_callout_when_no_d_tier_movement():
    rows = build_rows(_STUCK_RECORDS + [_CLEAN_RECORD])
    before, after = build_census_points(rows)
    text = render_census_markdown(before, after, 646, "coalesced_minus_one", "2026-08-14T00:00:00Z")
    assert "SEVERITY" not in text


def test_render_census_markdown_population_mismatch_raises():
    """The census renderer must raise, not silently render a clean pass, when a
    distribution does not sum to its stated population count -- reusing
    scripts/build_rescore_report.py::_validate_point's own invariant."""
    before = {"label": "Before (lv_icp_tier)", "population_count": 2,
              "tier_distribution": {"A": 1}, "records": {}}
    after = {"label": "After (lv_icp_tier_derived)", "population_count": 2,
             "tier_distribution": {"A": 2}, "records": {}}
    with pytest.raises(ValueError):
        render_census_markdown(before, after, 0, "coalesced_minus_one", "2026-08-14T00:00:00Z")


def test_render_census_markdown_empty_population_raises():
    before = {"label": "Before (lv_icp_tier)", "population_count": 0,
              "tier_distribution": {}, "records": {}}
    after = {"label": "After (lv_icp_tier_derived)", "population_count": 0,
             "tier_distribution": {}, "records": {}}
    with pytest.raises(ValueError):
        render_census_markdown(before, after, 0, "coalesced_minus_one", "2026-08-14T00:00:00Z")


# --- Phase 50 Plan 06 (D-20): mirror_disagrees / render_mirror_section -------------------

def test_mirror_disagrees_flag_true_mirror_one_agrees():
    assert mirror_disagrees("true", "1") is False


def test_mirror_disagrees_flag_true_mirror_null_diverges():
    assert mirror_disagrees("true", None) is True


def test_mirror_disagrees_flag_false_mirror_null_agrees():
    assert mirror_disagrees("false", None) is False


def test_mirror_disagrees_flag_false_mirror_one_diverges():
    assert mirror_disagrees("false", "1") is True


def test_mirror_disagrees_guards_empty_string_mirror_before_coercion():
    assert mirror_disagrees("false", "") is False


def test_mirror_disagrees_flag_unset_treated_as_false():
    assert mirror_disagrees(None, None) is False


def test_render_mirror_section_no_divergence():
    rows = build_rows([
        {"id": "1", "name": "Vetoed Co", "lv_icp_tier": "D", "lv_icp_tier_derived": "D",
         "lv_icp_fit_score": "10", "lv_anti_icp_flag": "true", "lv_anti_icp_flag_num": "1"},
        {"id": "2", "name": "Clean Co", "lv_icp_tier": "A", "lv_icp_tier_derived": "A",
         "lv_icp_fit_score": "80", "lv_anti_icp_flag": "false", "lv_anti_icp_flag_num": None},
    ])
    text = render_mirror_section(rows)
    assert "No divergence found" in text


def test_render_mirror_section_flags_divergent_record():
    rows = build_rows([
        {"id": "18047161864", "name": "Simtech LED", "lv_icp_tier": "D",
         "lv_icp_tier_derived": "B", "lv_icp_fit_score": "40",
         "lv_anti_icp_flag": "true", "lv_anti_icp_flag_num": None},
    ])
    text = render_mirror_section(rows)
    assert "DEFECT: 1 record(s)" in text
    assert "18047161864" in text
    assert "Simtech LED" in text


# --- Phase 50 Plan 06 (D-21): _current_null_variant / the "uncoalesced_post_d21" ---------
# --- census branch -------------------------------------------------------------------

def test_current_null_variant_matches_the_shipped_uncoalesced_formula():
    """The shipped config/hubspot_properties.yaml formula (this plan's own D-21
    correction) must be classified uncoalesced_post_d21, not the frozen probe's
    coalesced_minus_one -- the whole point of this helper is to stop trusting the frozen
    probe for what the CURRENT formula does."""
    assert _current_null_variant() == "uncoalesced_post_d21"


def test_render_census_markdown_uncoalesced_post_d21_states_the_reversal_and_un_flip():
    rows = build_rows(_STUCK_RECORDS + [_CLEAN_RECORD])
    before, after = build_census_points(rows)
    text = render_census_markdown(before, after, 646, "uncoalesced_post_d21", "2026-08-14T00:00:00Z")
    assert "D-21 reversed D-04" in text
    assert "646 never-enriched companies" in text
    assert "reading blank" in text
    assert '"Unscored"` label the coalesced' in text
