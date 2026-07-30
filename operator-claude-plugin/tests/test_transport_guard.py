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


def test_requests_put_raises_inside_a_test():
    """Phase 28 is the first that can PUT to a live workflow. `requests.put` routes through
    the already-patched `Session.request`, so this is a coverage assertion rather than a new
    guard — but a mutating verb's containment must be stated, not inferred from an
    implementation detail of the requests package."""
    with pytest.raises(RuntimeError, match="test_requests_put_raises_inside_a_test"):
        requests.put("https://example.invalid/api/v1/workflows/wf-1", json={})


def test_requests_get_raises_inside_a_test():
    with pytest.raises(RuntimeError, match="test_requests_get_raises_inside_a_test"):
        requests.get("https://example.invalid/api/v1/workflows/wf-1")


def test_stub_module_transport_records_every_verb_on_one_log(stub_module_transport_factory):
    """The module-shaped seam Phase 28's `transport=requests` default needs: `.get`,
    `.post` and `.put` on one object, sharing one ordered call log (D-33)."""
    transport = stub_module_transport_factory()
    transport.get("https://example.invalid/api/v1/workflows/wf-1")
    transport.post("https://example.invalid/api/v1/workflows/wf-1/deactivate")
    transport.put("https://example.invalid/api/v1/workflows/wf-1", json={"name": "x"})

    assert transport.verbs == ["get", "post", "put"]
    assert len(transport.mutating_calls) == 2
    assert transport.calls[1]["json"] is None
    assert transport.calls[2]["json"] == {"name": "x"}


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
