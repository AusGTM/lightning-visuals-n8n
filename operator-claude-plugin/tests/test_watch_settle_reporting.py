"""Tests for watch.py Task 2 — the settled report: per-record outcomes rendered through
Phase 26's own renderer, plus the cost actually incurred (NOTICE-01, 26-CONTEXT D-10/
D-10a/D-10b/D-14).

Reuses the same execution fixtures Phase 26's own test suites already built —
``execution_enrichment.json`` (via a local copy helper, mirroring test_report_enrichment.
py) for the enrichment lane and conftest.py's ``contact_execution`` for the contact-upload
lane's no-email row — rather than inventing a third fixture set for the same shapes.
"""
import copy
import json
from pathlib import Path

import report_enrichment
import watch

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _enrichment_execution():
    return copy.deepcopy(json.loads((FIXTURES_DIR / "execution_enrichment.json").read_text()))


_HANDLE = {"execution_id": "54321", "best_effort": True}

# The fixture's own known credit reading (test_report_enrichment.py pins these too):
# lusha a real number, apollo unknown (403-by-design, never rendered as zero).
_POST_SETTLE_CREDITS_FIXTURE = {"lusha": 42, "apollo": None}


def _pre_dispatch_balances(*, apollo_unreadable=True):
    return {
        "lusha": {"credits": 500, "unreadable": False, "reason": None},
        "apollo": (
            {"credits": None, "unreadable": True, "reason": "http_403"}
            if apollo_unreadable else
            {"credits": 60, "unreadable": False, "reason": None}
        ),
    }


# =====================================================================================
# Per-record outcomes render through Phase 26's own renderer — no second convention.
# =====================================================================================

def test_settled_report_renders_the_same_counts_as_report_enrichment_directly():
    execution = _enrichment_execution()
    direct = report_enrichment.build_enrichment_report(execution, handle=_HANDLE)

    watched = watch.build_settled_report(
        execution, _HANDLE, lane="enrichment", pre_dispatch_balances=_pre_dispatch_balances(),
    )

    assert watched["kind"] == "settled"
    # 2026-08-31, 57-02 Task 3: `report_enrichment._empty_counts()` is now keyed on
    # `written_records.ALL_OUTCOMES` (D-57-03, Task 1 option-b's eight-word vocabulary)
    # rather than its own retired table. This test reuses the same fixture as
    # `test_report_enrichment.py`'s own re-pointed pin and moves in lockstep with it,
    # not a second decision — see that file's
    # `test_build_enrichment_report_counts_and_total_sum_correctly` for the row-by-row
    # derivation.
    assert watched["counts"] == direct["counts"] == {
        "written": 0, "write_attempted": 2, "created_id_unknown": 2,
        "written_id_unknown": 0, "gated": 1, "held": 0, "failed": 0, "no_action": 1,
    }
    assert watched["total"] == direct["total"] == 6
    assert watched["failing_rows"] == direct["failing_rows"]
    assert watched["handle"] == _HANDLE


def test_settled_report_never_re_renders_a_second_outcome_shape():
    """The report carries exactly the renderer's own keys plus watch.py's two additions
    — no shadow copy of counts/rows computed a second way."""
    execution = _enrichment_execution()
    direct = report_enrichment.build_enrichment_report(execution, handle=_HANDLE)
    watched = watch.build_settled_report(
        execution, _HANDLE, lane="enrichment", pre_dispatch_balances=_pre_dispatch_balances(),
    )

    without_additions = {k: v for k, v in watched.items() if k not in ("kind", "cost", "delivery_mode")}
    assert without_additions == direct


# =====================================================================================
# The cost actually incurred (D-10) — a delta between two already-fetched balances.
# =====================================================================================

def test_cost_delta_known_end_to_end_is_the_arithmetic_difference():
    execution = _enrichment_execution()
    pre = _pre_dispatch_balances(apollo_unreadable=False)  # both ends known this time

    report = watch.build_settled_report(
        execution, _HANDLE, lane="enrichment", pre_dispatch_balances=pre,
    )

    lusha = report["cost"]["credits"]["per_provider"]["lusha"]
    assert lusha["known"] is True
    assert lusha["spent"] == 500 - 42  # pre minus post, per D-10's own arithmetic


def test_cost_delta_with_one_unknown_end_is_reported_as_unknown_never_zero():
    execution = _enrichment_execution()
    pre = _pre_dispatch_balances(apollo_unreadable=True)  # apollo's pre-dispatch balance never read

    report = watch.build_settled_report(
        execution, _HANDLE, lane="enrichment", pre_dispatch_balances=pre,
    )

    apollo = report["cost"]["credits"]["per_provider"]["apollo"]
    assert apollo["known"] is False
    assert apollo["spent"] is None
    assert apollo["spent"] != 0, "an unreadable delta must never collapse to zero spend"
    assert report["cost"]["credits"]["state"] == "partial", (
        "lusha resolved and apollo did not — partial, not silently dropped to a smaller number"
    )


def test_cost_delta_when_neither_end_is_known_reports_state_unknown():
    delta = watch.compute_cost_delta(None, {})
    assert delta["per_provider"] == {}
    assert delta["state"] == "unknown"


def test_token_usage_defaults_to_unknown_when_no_node_emits_it():
    execution = _enrichment_execution()
    assert watch.token_usage_from_execution(execution) == "unknown"


def test_contact_upload_lane_carries_no_cost_block_at_all():
    # Contact-upload burns no provider credits (only enrichment does) — there is
    # nothing to compute a delta of, so the field is structurally absent rather than
    # rendered as an unknown figure that implies a cost exists to be found.
    contact_execution = copy.deepcopy(
        json.loads((FIXTURES_DIR / "execution_contact_upload.json").read_text())
    )
    report = watch.build_settled_report(contact_execution, _HANDLE, lane="contact_upload")
    assert report["cost"] is None


# =====================================================================================
# No ICP field or placeholder anywhere (D-10a/D-10b) — same scan idiom as
# test_report_enrichment.py's own guard, applied to the watch's report shape too.
# =====================================================================================

_FORBIDDEN_SUBSTRINGS = ("icp", "tier")


def test_settled_report_carries_no_icp_trace_anywhere():
    execution = _enrichment_execution()
    report = watch.build_settled_report(
        execution, _HANDLE, lane="enrichment", pre_dispatch_balances=_pre_dispatch_balances(),
    )
    serialized = json.dumps(report, default=str).lower()
    hits = [term for term in _FORBIDDEN_SUBSTRINGS if term in serialized]
    assert not hits, f"settled report carries a forbidden ICP/tier trace: {hits}"


# =====================================================================================
# The no-email row (D-14) — inherited from report.py's own retryability engine by
# calling through it, never re-derived here.
# =====================================================================================

def test_no_email_ambiguous_row_is_described_as_needing_an_email_not_as_retryable(contact_execution):
    report = watch.build_settled_report(contact_execution, _HANDLE, lane="contact_upload")

    stuck = [
        row for row in report["failing_rows"]
        if row.get("email_status") == "NO_EMAIL" and row.get("outcome") == "ambiguous"
    ]
    assert stuck, "fixture must carry a NO_EMAIL + ambiguous row for this test to mean anything"
    for row in stuck:
        assert row["retryability"] == "permanently_stuck"
        assert "email" in row["retry_reason"].lower()
        assert row["_identity"] not in {r["_identity"] for r in report["resendable_rows"]}, (
            "a permanently-stuck row must never be presented as safe to re-send"
        )


# =====================================================================================
# The bonus delivery layer changes only `delivery_mode` — everything else is identical
# whether or not the capability is available (D-05a: removing it breaks nothing else).
# =====================================================================================

def test_report_is_identical_regardless_of_bonus_delivery_availability():
    execution = _enrichment_execution()
    pre = _pre_dispatch_balances()

    with_bonus = watch.build_settled_report(
        execution, _HANDLE, lane="enrichment", pre_dispatch_balances=pre,
        bonus_delivery_available=True,
    )
    without_bonus = watch.build_settled_report(
        execution, _HANDLE, lane="enrichment", pre_dispatch_balances=pre,
        bonus_delivery_available=False,
    )

    assert with_bonus["delivery_mode"] != without_bonus["delivery_mode"]
    strip = lambda r: {k: v for k, v in r.items() if k != "delivery_mode"}  # noqa: E731
    assert strip(with_bonus) == strip(without_bonus)


def test_bonus_delivery_available_reads_the_recorded_verdict_as_no_by_default():
    # 29-HOST-PROBE.md A2: NOT OBSERVED, treated as NO. Absent an override, this must
    # stay False so nothing in the watch depends on an unconfirmed platform primitive.
    assert watch.bonus_delivery_available({}) is False
    assert watch.bonus_delivery_available(None) is False


def test_bonus_delivery_available_honours_an_explicit_config_override():
    assert watch.bonus_delivery_available({"watch_unprompted_followup_verdict": True}) is True
    assert watch.bonus_delivery_available({"watch_unprompted_followup_verdict": False}) is False
