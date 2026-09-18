# tests/test_probe_provider_discovery.py
#
# Phase 73.1 Plan 09 Task 1 (D-12/D-13) — offline proof for
# scripts/probe_provider_discovery.py. Fully hermetic: no test in this file makes a
# network call. Mirrors tests/test_check_provider_credits.py's monkeypatch-`requests`
# pattern (same repo convention for a live-only utility's offline test).
#
# scripts/probe_provider_discovery.py is a LIVE-ONLY, credit-spending utility. It is never
# invoked live here — every test below runs it against a stub transport.
import json

import pytest
import requests

import scripts.probe_provider_discovery as probe_module

DOMAIN = "example-racing.example"


class _FakeResponse:
    def __init__(self, status_code, json_body=None, ok=None):
        self.status_code = status_code
        self.ok = ok if ok is not None else 200 <= status_code < 300
        self._json_body = json_body

    def json(self):
        if self._json_body is None:
            raise ValueError("no json body")
        return self._json_body


def _raise(*args, **kwargs):
    raise AssertionError("a live provider request leaked past a guard/gate that should have refused")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Autouse — every test in this file starts with requests.get/post refusing to run.
    A test that needs a response installs its own stub transport; a test that expects
    zero calls (the opt-in gate) needs nothing further. Same rationale
    operator-claude-plugin/tests/conftest.py's `no_network` fixture states."""
    for var in ("LUSHA_API_KEY", "APOLLO_API_KEY", "ZOOMINFO_CLIENT_ID", "ZOOMINFO_CLIENT_SECRET",
                "ALLOW_DISCOVERY_PROBE", "DISCOVERY_PROBE_DOMAIN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(requests, "get", _raise)
    monkeypatch.setattr(requests, "post", _raise)


def _set_all_creds(monkeypatch):
    monkeypatch.setenv("LUSHA_API_KEY", "fake-lusha-key-SECRETVALUE1")
    monkeypatch.setenv("APOLLO_API_KEY", "fake-apollo-key-SECRETVALUE2")
    monkeypatch.setenv("ZOOMINFO_CLIENT_ID", "fake-zi-id-SECRETVALUE3")
    monkeypatch.setenv("ZOOMINFO_CLIENT_SECRET", "fake-zi-secret-SECRETVALUE4")


def _default_transport(monkeypatch, recorder, *, apollo_403=True, search_status=None):
    """Installs a stub transport recording every (method, url) call and returning a
    canned response per endpoint. `search_status` maps provider -> override status/body
    for its ONE search call; defaults to a healthy 200 with one person, no reveal fields.
    """
    search_status = search_status or {}

    zi_token_url = "https://api.zoominfo.com/gtm/oauth/v1/token"
    zi_usage_url = probe_module.credits_mod.PROVIDER_REGISTRY["zoominfo"]["credit"]["url"]
    apollo_usage_url = probe_module.credits_mod.PROVIDER_REGISTRY["apollo"]["credit"]["url"]
    lusha_usage_url = probe_module.credits_mod.PROVIDER_REGISTRY["lusha"]["credit"]["url"]

    def fake_get(url, headers=None, timeout=None, **kwargs):
        recorder.append(("GET", url))
        if url == lusha_usage_url:
            return _FakeResponse(200, {"credits": {"total": 100, "used": 10, "remaining": 90}})
        if url == zi_usage_url:
            return _FakeResponse(200, {"data": [{"attributes": {"usage": [
                {"limitType": "uniqueIdLimit", "usageRemaining": 500}]}}]})
        if url in probe_module.DISCOVERY_ENDPOINTS.values():
            return _response_for_search(url, search_status)
        return _FakeResponse(404, {"message": "unexpected GET in test stub"})

    def fake_post(url, headers=None, json=None, data=None, auth=None, timeout=None, **kwargs):
        recorder.append(("POST", url))
        if url == zi_token_url:
            return _FakeResponse(200, {"access_token": "fake-zi-bearer-SECRETVALUE5"})
        if url == apollo_usage_url:
            if apollo_403:
                return _FakeResponse(403, {"message": "forbidden: not a master key"})
            return _FakeResponse(200, {"remaining": 42})
        if url in probe_module.DISCOVERY_ENDPOINTS.values():
            return _response_for_search(url, search_status)
        return _FakeResponse(404, {"message": "unexpected POST in test stub"})

    def _response_for_search(url, overrides):
        provider = next(p for p, u in probe_module.DISCOVERY_ENDPOINTS.items() if u == url)
        if provider in overrides:
            return overrides[provider]
        if provider == "zoominfo":
            return _FakeResponse(200, {"data": [{"attributes": {"firstName": "A", "lastName": "B",
                                                                 "jobTitle": "Marketing Manager"}}]})
        if provider == "apollo":
            return _FakeResponse(200, {"people": [{"first_name": "A", "last_name": "B",
                                                     "title": "Marketing Manager"}]})
        if provider == "lusha":
            return _FakeResponse(200, {"data": [{"firstName": "A", "lastName": "B",
                                                   "jobTitle": "Marketing Manager"}]})
        raise AssertionError(f"no stub response for provider {provider}")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)


# --- Test 1: exactly one search call per provider, three total -----------------------

def test_exactly_one_search_call_per_provider(monkeypatch):
    _set_all_creds(monkeypatch)
    monkeypatch.setenv("ALLOW_DISCOVERY_PROBE", "true")
    recorder = []
    _default_transport(monkeypatch, recorder)

    verdict = probe_module.run_probe(DOMAIN)

    search_calls = [c for c in recorder if c[1] in probe_module.DISCOVERY_ENDPOINTS.values()]
    assert len(search_calls) == 3
    for provider, url in probe_module.DISCOVERY_ENDPOINTS.items():
        assert sum(1 for m, u in search_calls if u == url) == 1
    assert set(verdict["providers"].keys()) == {"zoominfo", "apollo", "lusha"}


# --- Test 2: opt-in gate — refuses with zero network calls ---------------------------

def test_refuses_without_opt_in_env_var(monkeypatch, capsys):
    _set_all_creds(monkeypatch)
    monkeypatch.setenv("DISCOVERY_PROBE_DOMAIN", DOMAIN)
    # ALLOW_DISCOVERY_PROBE deliberately left unset — requests.get/post still raise
    # (autouse fixture default), proving zero calls are made.
    rc = probe_module.main([])
    assert rc != 0
    assert "ALLOW_DISCOVERY_PROBE" in capsys.readouterr().out


# --- Test 3: never prints a key, an auth header, or a raw response object ------------

def test_never_prints_a_secret_or_a_raw_header(monkeypatch, capsys, tmp_path):
    _set_all_creds(monkeypatch)
    monkeypatch.setenv("ALLOW_DISCOVERY_PROBE", "true")
    monkeypatch.setenv("DISCOVERY_PROBE_DOMAIN", DOMAIN)
    monkeypatch.setattr(probe_module, "VERDICT_PATH", tmp_path / "verdict.json")
    recorder = []
    _default_transport(monkeypatch, recorder)

    rc = probe_module.main([])
    assert rc == 0

    out = capsys.readouterr().out
    written = (tmp_path / "verdict.json").read_text()

    secrets = ("SECRETVALUE1", "SECRETVALUE2", "SECRETVALUE3", "SECRETVALUE4", "SECRETVALUE5")
    for secret in secrets:
        assert secret not in out
        assert secret not in written


# --- Test 4: Apollo unreadable (403) -> documented price cited, never a zero delta ---

def test_apollo_unreadable_never_reports_a_zero_delta(monkeypatch):
    _set_all_creds(monkeypatch)
    monkeypatch.setenv("ALLOW_DISCOVERY_PROBE", "true")
    recorder = []
    _default_transport(monkeypatch, recorder, apollo_403=True)

    verdict = probe_module.run_probe(DOMAIN)
    apollo = verdict["providers"]["apollo"]

    assert apollo["balance_before"] is None
    assert apollo["balance_after"] is None
    assert apollo["delta"] is None
    assert apollo["delta"] != 0
    assert "documentation" in apollo["note"].lower() or "unreadable" in apollo["note"].lower()


# --- Test 5: endpoint-absent (404/400) is reported with status + message, no crash ---

def test_endpoint_absent_reports_status_and_message(monkeypatch):
    _set_all_creds(monkeypatch)
    monkeypatch.setenv("ALLOW_DISCOVERY_PROBE", "true")
    recorder = []
    overrides = {"lusha": _FakeResponse(404, {"message": "no such endpoint on this plan"})}
    _default_transport(monkeypatch, recorder, search_status=overrides)

    verdict = probe_module.run_probe(DOMAIN)
    lusha = verdict["providers"]["lusha"]

    assert lusha["status"] == 404
    assert lusha["people_returned"] is False
    assert lusha["note"] is not None
    assert "no such endpoint" in lusha["note"]
    # the other two providers are unaffected by lusha's failure
    assert verdict["providers"]["zoominfo"]["people_returned"] is True
    assert verdict["providers"]["apollo"]["people_returned"] is True


# --- Test 6: verdict document shape ---------------------------------------------------

def test_verdict_document_shape(monkeypatch, tmp_path):
    _set_all_creds(monkeypatch)
    monkeypatch.setenv("ALLOW_DISCOVERY_PROBE", "true")
    monkeypatch.setenv("DISCOVERY_PROBE_DOMAIN", DOMAIN)
    monkeypatch.setattr(probe_module, "VERDICT_PATH", tmp_path / "verdict.json")
    recorder = []
    _default_transport(monkeypatch, recorder)

    rc = probe_module.main([])
    assert rc == 0

    verdict = json.loads((tmp_path / "verdict.json").read_text())
    assert verdict["operator_ruling"] is None
    assert "probed_at" in verdict
    required_fields = {"endpoint", "status", "balance_before", "balance_after", "delta",
                        "people_returned", "reveal_fields_present"}
    for provider in ("zoominfo", "apollo", "lusha"):
        entry = verdict["providers"][provider]
        assert required_fields.issubset(entry.keys())


# --- Test 7: this file's own autouse fixture genuinely blocks network access ---------

def test_no_network_fixture_blocks_real_calls():
    with pytest.raises(AssertionError, match="leaked past a guard"):
        requests.get("https://example.invalid")
    with pytest.raises(AssertionError, match="leaked past a guard"):
        requests.post("https://example.invalid")
