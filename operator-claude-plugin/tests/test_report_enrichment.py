"""Tests for report_enrichment.py — the enrichment lane's half of the outcome
report (REPORT-02 as amended, 26-CONTEXT.md D-10/D-10a/D-10b).

Every test reads a redacted execution fixture (never a live payload) and drives
pure functions — no test performs a network call; the autouse `no_network` guard
(conftest.py) would fail the suite if one tried.
"""
import copy
import json
from pathlib import Path

import report_enrichment

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def _enrichment_execution():
    """A fresh deep copy per test so no test can mutate a fixture another test then
    reads (mirrors conftest.py's `contact_execution` fixture)."""
    return copy.deepcopy(json.loads((FIXTURES_DIR / "execution_enrichment.json").read_text()))


# =====================================================================================
# enrichment_row_ledger — reads Decide Company Action AND Decide Action, tagged by lane.
# =====================================================================================

def test_ledger_reads_both_lanes_present_in_one_execution():
    ledger, reason = report_enrichment.enrichment_row_ledger(_enrichment_execution())

    assert reason is None
    lanes = [row["_lane"] for row in ledger]
    assert lanes.count("companies") == 4
    assert lanes.count("contacts") == 2


def test_ledger_missing_both_decision_nodes_returns_empty_ledger_and_reason():
    execution = {"data": {"resultData": {"runData": {"Build Response": [{"data": {"main": [[]]}}]}}}}

    ledger, reason = report_enrichment.enrichment_row_ledger(execution)

    assert ledger == []
    assert reason is not None
    assert "Decide Company Action" in reason and "Decide Action" in reason


def test_ledger_never_raises_on_malformed_payload():
    for bad in (None, "garbage", 42, [], {}, {"data": "not-a-dict"}, {"data": {"resultData": None}}):
        ledger, reason = report_enrichment.enrichment_row_ledger(bad)
        assert ledger == []
        assert reason is not None


# =====================================================================================
# Outcome mapping — create/enrich/write_blocked/skip -> created/enriched/blocked/skipped.
# =====================================================================================

def test_write_blocked_row_renders_as_blocked_with_a_reason_never_enriched():
    ledger, _ = report_enrichment.enrichment_row_ledger(_enrichment_execution())
    blocked = next(row for row in ledger if row["action"] == "write_blocked")

    rendered = report_enrichment._build_row_report(blocked, 1)

    assert rendered["outcome"] == "blocked"
    assert rendered["outcome"] != "enriched"
    assert rendered["reason"]


def test_skip_row_renders_as_skipped_never_enriched():
    ledger, _ = report_enrichment.enrichment_row_ledger(_enrichment_execution())
    skipped = next(row for row in ledger if row["action"] == "skip")

    rendered = report_enrichment._build_row_report(skipped, 1)

    assert rendered["outcome"] == "skipped"
    assert rendered["outcome"] != "enriched"


def test_unrecognised_action_renders_as_unknown_never_a_success():
    row = {"_lane": "companies", "action": "some-future-action-this-code-has-never-seen"}

    rendered = report_enrichment._build_row_report(row, 1)

    assert rendered["outcome"] == "unknown"
    assert rendered["outcome"] not in report_enrichment.SUCCESS_OUTCOMES


# =====================================================================================
# Review flag — company lane has it, contact lane never does (D-11a, the trap).
# =====================================================================================

def test_company_row_with_review_flag_true_renders_needing_review():
    ledger, _ = report_enrichment.enrichment_row_ledger(_enrichment_execution())
    reviewed = next(row for row in ledger if row["_lane"] == "companies" and row.get("needs_review") is True)

    rendered = report_enrichment._build_row_report(reviewed, 1)

    assert rendered["review_state"] == "needs_review"


def test_company_row_with_review_flag_false_renders_not_needing_review():
    ledger, _ = report_enrichment.enrichment_row_ledger(_enrichment_execution())
    clear = next(row for row in ledger if row["_lane"] == "companies" and row.get("needs_review") is False)

    rendered = report_enrichment._build_row_report(clear, 1)

    assert rendered["review_state"] == "clear"


def test_contact_row_renders_review_state_as_unknown_never_false():
    ledger, _ = report_enrichment.enrichment_row_ledger(_enrichment_execution())
    contact_rows = [row for row in ledger if row["_lane"] == "contacts"]
    assert contact_rows, "fixture must carry at least one contact-lane row"

    for row in contact_rows:
        assert "needs_review" not in row, "fixture must mirror the real Decide Action shape (no review key)"
        rendered = report_enrichment._build_row_report(row, 1)
        assert rendered["review_state"] == "unknown"
        assert rendered["review_state"] != "clear", "absence must never be read as a clean bill of health"


# =====================================================================================
# Credits — real number, null-is-unknown, and the no-block-at-all fallback (D-10, T-26-07).
# =====================================================================================

def test_credits_real_number_renders_as_that_number():
    credits = report_enrichment.remaining_credits_from_response(_enrichment_execution())

    assert credits["lusha"] == 42


def test_credits_null_renders_as_unknown_distinguishable_from_zero():
    credits = report_enrichment.remaining_credits_from_response(_enrichment_execution())

    assert credits["apollo"] == "unknown"
    assert credits["apollo"] != 0
    assert credits["apollo"] is not None


def test_credits_zero_and_unknown_are_never_the_same_rendered_state():
    execution = _enrichment_execution()
    execution["data"]["resultData"]["runData"]["Build Response"][0]["data"]["main"][0][0]["json"][
        "remaining_credits"
    ] = [{"provider": "lusha", "credits": 0}, {"provider": "apollo", "credits": None}]

    credits = report_enrichment.remaining_credits_from_response(execution)

    assert credits["lusha"] == 0
    assert credits["apollo"] == "unknown"
    assert credits["lusha"] != credits["apollo"]


def test_missing_credits_block_renders_every_requested_provider_as_unknown():
    execution = {
        "data": {
            "resultData": {
                "runData": {
                    "Parse HubSpot Event": [
                        {
                            "executionStatus": "success",
                            "data": {
                                "main": [
                                    [{"json": {"providers_requested": ["lusha", "apollo", "zoominfo"]}}]
                                ]
                            },
                        }
                    ]
                    # No "Build Response" entry at all — the run may not have reached it.
                }
            }
        }
    }

    credits = report_enrichment.remaining_credits_from_response(execution)

    assert credits == {"lusha": "unknown", "apollo": "unknown", "zoominfo": "unknown"}


def test_remaining_credits_never_raises_on_malformed_payload():
    for bad in (None, "garbage", 42, [], {}, {"data": "not-a-dict"}):
        assert report_enrichment.remaining_credits_from_response(bad) == {}


# =====================================================================================
# build_enrichment_report — one shaped object, never raises (D-08/D-09 shape parity).
# =====================================================================================

def test_build_enrichment_report_counts_and_total_sum_correctly():
    r = report_enrichment.build_enrichment_report(_enrichment_execution(), handle=None)

    assert r["total"] == 6
    assert sum(r["counts"].values()) == 6
    assert r["counts"] == {"created": 2, "enriched": 2, "blocked": 1, "skipped": 1, "unknown": 0}


def test_build_enrichment_report_failing_rows_include_blocked_skipped_and_needs_review():
    r = report_enrichment.build_enrichment_report(_enrichment_execution(), handle=None)

    failing_outcomes = {row["outcome"] for row in r["failing_rows"]}
    assert "blocked" in failing_outcomes
    assert "skipped" in failing_outcomes
    assert any(row["review_state"] == "needs_review" for row in r["failing_rows"])


def test_build_enrichment_report_credits_present_and_distinguishable():
    r = report_enrichment.build_enrichment_report(_enrichment_execution(), handle=None)

    assert r["credits"]["lusha"] == 42
    assert r["credits"]["apollo"] == "unknown"


def test_build_enrichment_report_running_execution_is_never_rendered_finished():
    execution = _enrichment_execution()
    execution["status"] = "running"

    r = report_enrichment.build_enrichment_report(execution, handle=None)

    assert r["state"] == "in_flight"


def test_build_enrichment_report_never_raises_on_a_non_dict_execution():
    for bad in (None, "garbage", 42, []):
        r = report_enrichment.build_enrichment_report(bad, handle=None)
        assert r["state"] == "unknown"
        assert r["handle"] is None


# =====================================================================================
# Task 2 — the separation-of-concerns guard: rendered output carries no ICP trace at
# all, not even a placeholder (D-10a/D-10b). Scoped to OUTPUT, never source text.
# =====================================================================================

# The rendered-output ban: no key, no string value anywhere in the built report may
# match these, case-insensitively. "icp" catches every one of the Phase 15 derived
# fields (lv_icp_fit_score, lv_icp_tier, lv_anti_icp_flag, lv_anti_icp_reason,
# lv_icp_score_breakdown, lv_icp_scored_at, lv_icp_scoring_version, lv_icp_confidence,
# lv_icp_needs_review); "tier" is checked separately for the bare tier concept
# (lv_recommended_motion/lv_named_account_priority do not contain "icp").
_FORBIDDEN_SUBSTRINGS = ("icp", "tier")


def _scan_text_for_forbidden_terms(text):
    lowered = text.lower()
    return [term for term in _FORBIDDEN_SUBSTRINGS if term in lowered]


def test_built_report_object_carries_no_icp_trace_anywhere():
    r = report_enrichment.build_enrichment_report(_enrichment_execution(), handle={"execution_id": "54321"})

    # Serialising is what proves this of what the operator actually sees, rather than
    # of how the module happens to be commented — a source-text ban would forbid the
    # module from ever explaining itself in a docstring, which is not the goal.
    serialized = json.dumps(r, default=str)

    hits = _scan_text_for_forbidden_terms(serialized)
    assert not hits, f"rendered report carries a forbidden ICP/tier trace: {hits}"


def test_no_operator_facing_skill_body_mentions_icp_or_tier_not_even_a_placeholder():
    """Extends the same ban across every skill body under skills/ — including the
    enrichment skill a sibling plan (Phase 25) creates, the moment it lands. Assert
    the scan found at least one file so this cannot pass by scanning nothing."""
    skill_files = [p for p in SKILLS_DIR.rglob("*") if p.is_file()]
    assert skill_files, "scan found zero skill files under operator-claude-plugin/skills/"

    offenders = {}
    for path in skill_files:
        hits = _scan_text_for_forbidden_terms(path.read_text(encoding="utf-8"))
        if hits:
            offenders[str(path.relative_to(SKILLS_DIR))] = hits

    assert not offenders, (
        f"skill file(s) mention ICP/tier — the plugin must show neither a tier nor a "
        f"'not available' placeholder for one (D-10b): {offenders}"
    )
