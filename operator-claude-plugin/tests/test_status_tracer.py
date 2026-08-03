"""The tracer: one question — "what is workflow X doing?" — end to end (27-03 Task 1).

Proves the credential split of D-01/D-02 as a code shape rather than as a claim: the
client reads workflow and execution state itself with the n8n API key it already holds,
and asks the backend endpoint only for what needs credentials it does not have. Neither
call carries the other's secret.
"""
import json

import backend_status
import n8n_read
import status

WORKFLOW_BODY = {
    "id": "wf-1",
    "name": "LV Contact Ingest (Cloud template)",
    "active": True,
    "nodes": [
        {"name": "Decide Action",
         "parameters": {"jsCode": 'const ALLOW_HUBSPOT_CREATE = "false";\nreturn [];'}},
        {"name": "HubSpot Create Write Gate",
         "parameters": {"jsCode": 'const ALLOW_HUBSPOT_CREATE = "false";'}},
    ],
}

LAST_EXECUTION_PAYLOAD = {"data": [{
    "id": "e-9", "status": "success",
    "startedAt": "2026-07-31T00:00:00.000Z", "stoppedAt": "2026-07-31T00:00:11.000Z",
}]}

# The shape 27-01 actually ships from `Build Status` — counts, credential_health,
# checked_at, plus `Build Credit Status`'s balances spread alongside.
BACKEND_BODY = {
    "counts": {
        "companies_requested_unresolved": 3,
        "companies_awaiting_review": 0,
        "contacts_requested_unresolved": None,
        "contacts_awaiting_review": 7,
    },
    "credential_health": [
        {"source": "lusha", "state": "ok", "status": 200, "reason": None},
        {"source": "apollo", "state": "refused", "status": 403, "reason": "http_403"},
    ],
    "checked_at": "2026-07-31T00:00:00.000Z",
    "balances": [
        {"provider": "lusha", "configured": True, "credits": 412, "unreadable": False,
         "error": None, "status": 200},
        {"provider": "apollo", "configured": True, "credits": None, "unreadable": True,
         "error": "http_403", "status": 403},
    ],
}


def _get_transport(factory):
    """Scripts the two GETs describe_workflow makes, in order: the workflow, then its
    most recent execution."""
    return factory([WORKFLOW_BODY, LAST_EXECUTION_PAYLOAD])


# --- describe_workflow: the composed answer ------------------------------------------


def test_describe_workflow_composes_on_off_write_safety_and_last_run(
        fake_config, stub_get_transport_factory):
    transport = _get_transport(stub_get_transport_factory)
    described = status.describe_workflow(fake_config, "wf-1", transport=transport)

    assert described["name"] == "LV Contact Ingest (Cloud template)"
    assert described["active"] is True
    assert described["write_safety"]["ALLOW_HUBSPOT_CREATE"]["value"] == "false"
    assert described["last_run"]["status"] == "success"
    assert described["in_flight"] is False


def test_describe_workflow_reads_state_from_the_api_not_from_local_config(
        fake_config, stub_get_transport_factory):
    """D-03: an inactive workflow reports off even though nothing local changed."""
    inactive = dict(WORKFLOW_BODY, active=False)
    transport = stub_get_transport_factory([inactive, LAST_EXECUTION_PAYLOAD])
    assert status.describe_workflow(fake_config, "wf-1", transport=transport)["active"] is False


def test_describe_workflow_is_unknown_end_to_end_when_the_workflow_cannot_be_read(
        fake_config, stub_get_transport_factory):
    transport = stub_get_transport_factory([(401, {"message": "unauthorized"}),
                                            LAST_EXECUTION_PAYLOAD])
    described = status.describe_workflow(fake_config, "wf-1", transport=transport)

    assert described["active"] is None
    assert described["write_safety"]["ALLOW_HUBSPOT_CREATE"]["value"] is None


def test_describe_workflow_never_returns_the_fetched_workflow_body(
        fake_config, stub_get_transport_factory):
    """T-27-11 at the composition seam, not only inside the extractor."""
    marker = "SECRET-INTERNALS-MARKER"
    body = json.loads(json.dumps(WORKFLOW_BODY))
    body["nodes"][0]["parameters"]["jsCode"] += f" // {marker}"
    transport = stub_get_transport_factory([body, LAST_EXECUTION_PAYLOAD])

    described = status.describe_workflow(fake_config, "wf-1", transport=transport)
    assert marker not in json.dumps(described)
    assert "nodes" not in described


# --- the credential boundary ----------------------------------------------------------


def test_the_two_calls_carry_different_secrets_and_never_each_others(
        fake_config, stub_get_transport_factory, stub_post_transport_factory):
    """D-01/D-02, T-27-13: same base URL, two different secrets, two different headers."""
    get_transport = _get_transport(stub_get_transport_factory)
    post_transport = stub_post_transport_factory([BACKEND_BODY])

    status.describe_workflow(fake_config, "wf-1", transport=get_transport)
    backend_status.fetch_backend_status(fake_config, transport=post_transport)

    read_headers = get_transport.calls[0]["headers"]
    backend_headers = post_transport.calls[0]["headers"]

    assert read_headers["X-N8N-API-KEY"] == fake_config["n8n_api_key"]
    assert "X-Enrichment-Secret" not in read_headers
    assert backend_headers["X-Enrichment-Secret"] == fake_config["webhook_secret"]
    assert "X-N8N-API-KEY" not in backend_headers


def test_the_plugin_constructs_no_provider_request_of_any_kind(
        fake_config, stub_get_transport_factory, stub_post_transport_factory):
    """D-01: provider balances arrive via the n8n-side endpoint only. Every URL this
    tracer touches lives under the configured n8n base."""
    get_transport = _get_transport(stub_get_transport_factory)
    post_transport = stub_post_transport_factory([BACKEND_BODY])

    status.describe_workflow(fake_config, "wf-1", transport=get_transport)
    backend_status.fetch_backend_status(fake_config, transport=post_transport)

    for call in get_transport.calls + post_transport.calls:
        assert call["url"].startswith(fake_config["n8n_url"])


# --- fetch_backend_status -------------------------------------------------------------


def test_fetch_backend_status_posts_once_to_the_status_endpoint(
        fake_config, stub_post_transport_factory):
    transport = stub_post_transport_factory([BACKEND_BODY])
    result = backend_status.fetch_backend_status(fake_config, transport=transport)

    assert len(transport.calls) == 1
    assert transport.calls[0]["url"] == (
        "https://fake-tenant.n8n.cloud/webhook/hubspot/backend-status")
    assert transport.calls[0]["timeout"] is not None
    assert result["available"] is True
    assert result["data"]["counts"]["companies_requested_unresolved"] == 3


def test_fetch_backend_status_degrades_rather_than_raising(fake_config,
                                                           stub_post_transport_factory):
    """T-27-14: one dead endpoint must not take the whole status answer down."""
    for scripted in (ConnectionError("dead"), (503, {}), (200, ValueError("not json"))):
        result = backend_status.fetch_backend_status(
            fake_config, transport=stub_post_transport_factory([scripted]))
        assert result["available"] is False
        assert result["reason"]
        assert result["data"] is None


def test_fetch_backend_status_accepts_the_bare_dict_shape(
        fake_config, stub_post_transport_factory):
    """Pinned alongside the array-wrapped test below so a future n8n change in either
    direction is caught."""
    result = backend_status.fetch_backend_status(
        fake_config, transport=stub_post_transport_factory([BACKEND_BODY]))
    assert result["available"] is True
    assert result["data"] == BACKEND_BODY


def test_fetch_backend_status_unwraps_the_live_array_wrapped_shape(
        fake_config, stub_post_transport_factory):
    """The live `hubspot/backend-status` webhook answers array-wrapped — a one-element
    list, n8n's normal firstIncomingItem behaviour (verified live 2026-08-03). The
    prerequisite bug fix this test pins: a bare-dict-only check rejected every real
    answer."""
    result = backend_status.fetch_backend_status(
        fake_config, transport=stub_post_transport_factory([[BACKEND_BODY]]))
    assert result["available"] is True
    assert result["data"] == BACKEND_BODY


def test_fetch_backend_status_rejects_shapes_that_are_neither(
        fake_config, stub_post_transport_factory):
    """Unwrapping is narrow: an empty list, a multi-element list and a non-dict element
    all stay `unrecognized_response_shape`, same as before the fix."""
    for scripted in ([], [BACKEND_BODY, BACKEND_BODY], ["not-a-dict"], [123]):
        result = backend_status.fetch_backend_status(
            fake_config, transport=stub_post_transport_factory([scripted]))
        assert result["available"] is False
        assert result["reason"] == "unrecognized_response_shape"


def test_fetch_backend_status_never_echoes_the_secret_in_its_reason(
        fake_config, stub_post_transport_factory):
    result = backend_status.fetch_backend_status(
        fake_config, transport=stub_post_transport_factory([ConnectionError("dead")]))
    assert fake_config["webhook_secret"] not in json.dumps(result)


# --- the module's read surface is read-only ------------------------------------------


def test_n8n_read_exposes_no_mutating_verb():
    """T-27-10: no activate, deactivate, PUT or DELETE path exists in this client at
    all, so no mutation is reachable even by a caller mistake."""
    forbidden = ("activate", "deactivate", "delete", "update", "put", "patch", "post")
    exported = [name for name in dir(n8n_read) if not name.startswith("_")]
    assert not [n for n in exported if any(verb in n.lower() for verb in forbidden)]

    source = (n8n_read.__file__ or "")
    assert source.endswith("n8n_read.py")
    text = open(source).read()
    for verb in ("requests.post", "requests.put", "requests.patch", "requests.delete"):
        assert verb not in text
