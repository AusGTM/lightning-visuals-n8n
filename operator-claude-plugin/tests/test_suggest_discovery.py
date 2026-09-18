"""operator-claude-plugin/scripts/suggest_discovery.py — Phase 73.1 Plan 08 Task 1.

The plugin's client for the sixth cloud workflow (plan 07's read-only provider-discovery
lane). Copies `backend_status.py`'s four-part shape (see that module and
`test_status_unknown.py`'s idiom, though that file tests the *renderer*, not the client —
`test_review_queue.py` is the closer analog for a POST-with-body client). Never a real
network call — the autouse `no_network` fixture (conftest.py) guarantees that; this file
additionally uses `stub_post_transport_factory` to script responses explicitly.
"""
import suggest_discovery


SENT_BODY = {
    "run_id": "run-abc123",
    "per_company_cap": 2,
    "companies": [
        {"company_id": "1", "name": "Alpha Co", "domain": "alpha.example",
         "role_families": ["general_manager"], "num_associated_contacts": 0, "gap": True},
        {"company_id": "2", "name": "Beta Co", "domain": "beta.example",
         "role_families": ["general_manager"], "num_associated_contacts": 3, "gap": False},
    ],
}


def _full_response():
    return {
        "run_id": "run-abc123",
        "companies": [
            {"company_id": "1", "num_associated_contacts": 0,
             "people": [{"firstname": "Sam", "lastname": "Lee", "jobtitle": "GM",
                         "provider": "apollo"}]},
            {"company_id": "2", "num_associated_contacts": 3, "people": []},
        ],
    }


# --- Test 1: discovery_target -----------------------------------------------------------


def test_discovery_target_joins_url_and_path_and_handles_trailing_slash(fake_config):
    cfg = dict(fake_config)
    cfg["n8n_url"] = "https://x.n8n.cloud/"
    target = suggest_discovery.discovery_target(cfg)
    assert target == "https://x.n8n.cloud/webhook/hubspot/suggest/discover"
    assert target.endswith(suggest_discovery.DISCOVERY_PATH)


def test_discovery_target_never_contains_the_secret(fake_config):
    cfg = dict(fake_config)
    cfg["webhook_secret"] = "sekrit-42-do-not-leak"
    target = suggest_discovery.discovery_target(cfg)
    assert "sekrit-42-do-not-leak" not in target


# --- Test 2: no webhook_secret -> unavailable, no transport call ------------------------


def test_no_webhook_secret_returns_unavailable_and_makes_no_transport_call(
    fake_config, stub_post_transport_factory,
):
    cfg = {k: v for k, v in fake_config.items() if k != "webhook_secret"}
    transport = stub_post_transport_factory()
    result = suggest_discovery.fetch_discovery(cfg, SENT_BODY, transport=transport)
    assert result["available"] is False
    assert result["reason"] == "webhook_secret_not_configured"
    assert transport.calls == []


# --- Test 3: json=, never multipart, carries the secret header --------------------------


def test_post_is_json_never_multipart_and_carries_the_secret_header(
    fake_config, stub_post_transport_factory,
):
    transport = stub_post_transport_factory([_full_response()])
    suggest_discovery.fetch_discovery(fake_config, SENT_BODY, transport=transport)
    assert len(transport.calls) == 1
    call = transport.calls[0]
    assert call["json"] == SENT_BODY
    assert call["files"] is None
    assert call["headers"]["X-Enrichment-Secret"] == fake_config["webhook_secret"]


# --- Test 4: transport exception -> unavailable, exception text never echoed ------------


def test_transport_exception_returns_unavailable_and_never_echoes_the_exception_text(
    fake_config, stub_post_transport_factory,
):
    secret_bearing_error = Exception("connection reset — Authorization: Bearer topsecret")
    transport = stub_post_transport_factory([secret_bearing_error])
    result = suggest_discovery.fetch_discovery(fake_config, SENT_BODY, transport=transport)
    assert result == {"available": False, "reason": "endpoint_unreachable", "data": None}
    assert "topsecret" not in result["reason"]
    assert "Authorization" not in result["reason"]


# --- Test 5: non-2xx -> unavailable naming the status, not the body ---------------------


def test_non_2xx_status_names_the_status_class_not_the_body(
    fake_config, stub_post_transport_factory,
):
    transport = stub_post_transport_factory([(500, {"secret_leak": "should never surface"})])
    result = suggest_discovery.fetch_discovery(fake_config, SENT_BODY, transport=transport)
    assert result["available"] is False
    assert result["reason"] == "http_500"
    assert result["data"] is None
    assert "secret_leak" not in result["reason"]


# --- Test 6: well-formed 200 -> parsed {run_id, companies} under data -------------------


def test_well_formed_200_returns_parsed_run_id_and_companies_under_data(
    fake_config, stub_post_transport_factory,
):
    transport = stub_post_transport_factory([_full_response()])
    result = suggest_discovery.fetch_discovery(fake_config, SENT_BODY, transport=transport)
    assert result["available"] is True
    assert result["reason"] is None
    assert result["data"]["run_id"] == "run-abc123"
    assert len(result["data"]["companies"]) == 2
    assert result["data"]["complete"] is True


# --- Test 7: a partial body is marked incomplete, carrying what arrived -----------------


def test_partial_body_missing_companies_key_is_marked_incomplete(
    fake_config, stub_post_transport_factory,
):
    transport = stub_post_transport_factory([{"run_id": "run-abc123"}])
    result = suggest_discovery.fetch_discovery(fake_config, SENT_BODY, transport=transport)
    assert result["available"] is True
    assert result["data"]["complete"] is False
    assert result["data"]["run_id"] == "run-abc123"


def test_partial_body_with_fewer_companies_than_sent_is_marked_incomplete_carrying_what_arrived(
    fake_config, stub_post_transport_factory,
):
    short = {
        "run_id": "run-abc123",
        "companies": [{"company_id": "1", "num_associated_contacts": 0, "people": []}],
    }
    transport = stub_post_transport_factory([short])
    result = suggest_discovery.fetch_discovery(fake_config, SENT_BODY, transport=transport)
    assert result["available"] is True
    assert result["data"]["complete"] is False
    # what DID arrive is still carried, never discarded
    assert len(result["data"]["companies"]) == 1
    assert result["data"]["companies"][0]["company_id"] == "1"


# --- Test 8: the module exposes the workflow/response-node literals as constants --------


def test_module_exposes_workflow_and_response_node_literals_as_constants():
    assert suggest_discovery.DISCOVERY_WORKFLOW_NAME
    assert suggest_discovery.DISCOVERY_ECHO_NODE
    assert suggest_discovery.DISCOVERY_RESPONSE_NODE
    assert isinstance(suggest_discovery.DISCOVERY_WORKFLOW_NAME, str)
    assert isinstance(suggest_discovery.DISCOVERY_ECHO_NODE, str)
    assert isinstance(suggest_discovery.DISCOVERY_RESPONSE_NODE, str)


# --- Test 9: watch.py is not imported by this module, and this module makes recovery ----
# the CALLER's step -------------------------------------------------------------------


def test_module_does_not_import_watch():
    import inspect

    import suggest_discovery as module

    source = inspect.getsource(module)
    assert "import watch" not in source
    assert "from watch" not in source
    assert not hasattr(module, "watch")


def test_fetch_discovery_uses_the_module_level_requests_post_by_default():
    """Signature discipline, mirroring backend_status/review_queue: the default
    transport is bound to the `requests.post` this module imported at load time — a
    caller that omits `transport=` still calls the real thing in production. Compared by
    name/module rather than identity: the autouse `no_network` fixture monkeypatches
    `requests.post` for the DURATION of this test, so a fresh `requests.post` read here
    is the patched stand-in, not the function this module's default actually bound to at
    import time."""
    import inspect

    sig = inspect.signature(suggest_discovery.fetch_discovery)
    default = sig.parameters["transport"].default
    assert callable(default)
    assert getattr(default, "__name__", None) in ("post", "_blocked")
