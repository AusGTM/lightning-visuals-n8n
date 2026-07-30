"""Tests for DISPATCH-04.

Task 1 (this file's initial content): `report.classify_retryability()` and the
report-level re-sendable roll-up — which rows a re-send can actually fix.
"""
import report


def test_no_email_ambiguous_row_is_permanently_stuck(contact_execution):
    built = report.build_contact_report(contact_execution, handle={"execution_id": "12345"})
    stuck = [
        r for r in built["failing_rows"]
        if r.get("email_status") == "NO_EMAIL" and r.get("outcome") == "ambiguous"
    ]
    assert stuck, "fixture must carry a NO_EMAIL + ambiguous row for this test to mean anything"
    for row in stuck:
        assert row["retryability"] == "permanently_stuck"
        assert row["retry_reason"] is not None
        assert "email" in row["retry_reason"].lower()

    resendable_ids = {r["_identity"] for r in built["resendable_rows"]}
    for row in stuck:
        assert row["_identity"] not in resendable_ids, (
            "a permanently-stuck row must never appear in the re-sendable set"
        )


def test_review_row_with_a_reason_other_than_no_email_is_a_business_outcome(contact_execution):
    built = report.build_contact_report(contact_execution, handle={"execution_id": "12345"})
    # Fixture row 4: action=skip/outcome=rejected/email_status=NO_EMAIL but NOT
    # ambiguous — the marker requires NO_EMAIL *and* ambiguous together (D-11b). This
    # row fails for a business reason (missing required identity fields), not the
    # permanently-stuck one.
    business_rows = [r for r in built["failing_rows"] if r.get("outcome") == "rejected"]
    assert business_rows, "fixture must carry a non-ambiguous rejected row"
    for row in business_rows:
        assert row["retryability"] == "business_outcome"
        assert row["retryability"] != "permanently_stuck"
        assert row["retryability"] != "transport_failure"
        assert "same outcome" in row["retry_reason"]


def test_successfully_written_rows_are_nothing_to_retry(contact_execution):
    built = report.build_contact_report(contact_execution, handle={"execution_id": "12345"})
    for row in built["rows"]:
        if row["reported_label"] in report.SUCCESS_LABELS:
            assert row["retryability"] == "nothing_to_retry"
            assert row["retry_reason"] is None


def test_not_confirmed_row_is_a_transport_failure_and_is_resendable():
    # A decided update/create the write-safety gate filtered before it reached
    # HubSpot — the same shape as a chunk that never got a response or came back
    # with a server error (Phase 25's failed-chunk unit). Safe to re-send unchanged.
    row = {
        "action": "update",
        "reported_outcome": "not_confirmed",
        "outcome": "match",
        "contact_id": "contact-x",
        "email_status": "verified",
        "reason": "the write was gated or filtered before it reached HubSpot",
    }
    assert report.classify_retryability(row) == "transport_failure"


def test_classifier_never_raises_on_a_row_missing_every_field_it_reads():
    for row in ({}, {"action": "review"}, {"email_status": "NO_EMAIL"}, None, "not-a-dict"):
        state = report.classify_retryability(row)
        assert state in {
            "nothing_to_retry", "transport_failure", "permanently_stuck", "business_outcome",
        }


def test_resendable_rows_never_include_permanently_stuck_or_business_outcome(contact_execution):
    built = report.build_contact_report(contact_execution, handle={"execution_id": "12345"})
    for row in built["resendable_rows"]:
        assert row["retryability"] == "transport_failure"
