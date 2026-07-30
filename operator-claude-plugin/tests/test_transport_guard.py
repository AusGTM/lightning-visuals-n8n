"""Proves conftest.py's autouse network guard is not vacuous.

23-VALIDATION.md's Wave 0 critical constraint: a test that accidentally arms and sends a
real POST is worse than no test at all. This is the test that proves the guard actually
bites, and that stub_transport still works as the seam every dispatch test uses instead.
"""
import pytest
import requests


def test_requests_post_raises_inside_a_test():
    with pytest.raises(RuntimeError, match="test_requests_post_raises_inside_a_test"):
        requests.post("https://example.invalid/whatever", data=b"x")


def test_requests_request_raises_inside_a_test():
    with pytest.raises(RuntimeError, match="test_requests_request_raises_inside_a_test"):
        requests.request("POST", "https://example.invalid/whatever")


def test_session_request_raises_inside_a_test():
    with pytest.raises(RuntimeError, match="test_session_request_raises_inside_a_test"):
        requests.Session().request("POST", "https://example.invalid/whatever")


def test_stub_transport_records_without_raising(stub_transport):
    response = stub_transport(
        url="https://example.invalid/hubspot/contact-upload",
        headers={"X-Enrichment-Secret": "placeholder"},
        files={"data": ("contacts.csv", b"email\na@b.com\n", "text/csv")},
        timeout=30,
    )
    assert stub_transport.calls[-1]["url"] == "https://example.invalid/hubspot/contact-upload"
    assert stub_transport.calls[-1]["timeout"] == 30
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}
