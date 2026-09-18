# tests/test_probe_provider_discovery.py
#
# Phase 73.1 Plan 09 Task 1 (D-12/D-13) / Task 2 (round-1 correction) — offline proof for
# scripts/probe_provider_discovery.py. Fully hermetic: no test in this file makes a
# network call. Mirrors tests/test_check_provider_credits.py's monkeypatch-`requests`
# pattern (same repo convention for a live-only utility's offline test).
#
# scripts/probe_provider_discovery.py is a LIVE-ONLY, credit-spending utility. It is never
# invoked live here — every test below runs it against a stub transport.
#
# Round 1 (2026-09-18, pickleballaustralia.org.au) found all three original [ASSUMED]
# endpoints wrong. The probe script now DERIVES its endpoints/bodies/URLs from
# n8n/code/discoverySearch.js's own (corrected) exports instead of holding a second,
# hand-copied literal — see 73.1-D12-VERDICT.round1.json for the recorded failures.
import json

import pytest
import requests

import scripts.probe_provider_discovery as probe_module

DOMAIN = "example-racing.example"


def _base_url(url):
    """Strip any query string -- ZoomInfo's corrected pagination rides `?page[size]=..`
    on the URL itself (round-1 correction), so the URL actually POSTed no longer equals
    `DISCOVERY_ENDPOINTS["zoominfo"]` verbatim. Apollo/Lusha are unaffected (no query
    string), so this is a no-op for them."""
    return url.split("?", 1)[0]


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
        if _base_url(url) in probe_module.DISCOVERY_ENDPOINTS.values():
            return _response_for_search(_base_url(url), search_status)
        return _FakeResponse(404, {"message": "unexpected GET in test stub"})

    def fake_post(url, headers=None, json=None, data=None, auth=None, timeout=None, **kwargs):
        recorder.append(("POST", url))
        if url == zi_token_url:
            return _FakeResponse(200, {"access_token": "fake-zi-bearer-SECRETVALUE5"})
        if url == apollo_usage_url:
            if apollo_403:
                return _FakeResponse(403, {"message": "forbidden: not a master key"})
            return _FakeResponse(200, {"remaining": 42})
        if _base_url(url) in probe_module.DISCOVERY_ENDPOINTS.values():
            return _response_for_search(_base_url(url), search_status)
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

    search_calls = [c for c in recorder if _base_url(c[1]) in probe_module.DISCOVERY_ENDPOINTS.values()]
    assert len(search_calls) == 3
    for provider, url in probe_module.DISCOVERY_ENDPOINTS.items():
        assert sum(1 for m, u in search_calls if _base_url(u) == url) == 1
    assert set(verdict["providers"].keys()) == {"zoominfo", "apollo", "lusha"}


# --- Test 8 (round-1 correction): endpoints are DERIVED, not a second hardcoded copy ---

def test_endpoints_zoominfo_derived_apollo_lusha_frozen_evidence_copies():
    """ZoomInfo's endpoint must be DERIVED from n8n/code/discoverySearch.js's own
    (shipped) constant -- round 1 found the original hardcoded copy wrong (ZoomInfo
    400). Apollo and Lusha are no longer exported by that module at all (D-12 operator
    ruling 2026-09-18 narrowed the shipped lane to ZoomInfo-only), so this probe holds
    its own frozen, round-2-confirmed copies for them -- still all three URLs present,
    same values as before the ruling."""
    assert probe_module.DISCOVERY_ENDPOINTS == {
        "zoominfo": "https://api.zoominfo.com/gtm/data/v1/contacts/search",
        "apollo": "https://api.apollo.io/api/v1/mixed_people/api_search",
        "lusha": "https://api.lusha.com/prospecting/contact/search",
    }
    # ZoomInfo's copy must still be DERIVED -- not just equal by coincidence.
    import subprocess
    result = subprocess.run(
        ["node", "-e",
         f"const m = require({json.dumps(str(probe_module._DISCOVERY_SEARCH_JS))}); "
         "console.log(JSON.stringify(m.DISCOVERY_ENDPOINTS));"],
        capture_output=True, text=True, timeout=10)
    js_endpoints = json.loads(result.stdout)
    assert js_endpoints == {"zoominfo": probe_module.DISCOVERY_ENDPOINTS["zoominfo"]}, (
        "discoverySearch.js must export ZoomInfo ONLY -- if this fails, either the "
        "shipped module regained a provider (update the probe's own retired-provider "
        "copies) or the probe's derived value has drifted from the shipped one")


# --- Test 9 (round-1 correction): ZoomInfo's request body/URL come from
# discoverySearch.js itself; Apollo/Lusha are the probe's own frozen copies ------------

def test_search_request_and_url_zoominfo_derived_apollo_lusha_frozen():
    """ZoomInfo's per-provider request body and URL must come from
    discoverySearch.js's own buildRequest/buildUrl -- the shipped source of truth.
    Apollo and Lusha are no longer exported by that module (D-12 ruling), so the probe
    builds their bodies/URLs itself; this pins that the frozen copies still match the
    round-2-confirmed shapes.

    73.1-11 Task 3 correction: ZoomInfo's URL is now BARE (no query string) -- execution
    12670 400'd live on a literal-bracket query string appended to the URL, while the
    byte-identical request succeeded outside n8n; pagination now rides `_search_params`
    (`params=`), never a hand-joined URL string."""
    apollo_body = probe_module._search_request("apollo", "example.org")
    assert apollo_body["q_organization_domains_list"] == ["example.org"]

    zoominfo_url = probe_module._search_url("zoominfo", "example.org")
    assert zoominfo_url == probe_module.DISCOVERY_ENDPOINTS["zoominfo"]
    assert "?" not in zoominfo_url

    zoominfo_params = probe_module._search_params("zoominfo")
    assert zoominfo_params == {"page[size]": 10, "page[number]": 1}

    lusha_body = probe_module._search_request("lusha", "example.org")
    assert lusha_body["filters"]["companies"]["include"]["domains"] == ["example.org"]

    apollo_url = probe_module._search_url("apollo", "example.org")
    assert apollo_url == probe_module.DISCOVERY_ENDPOINTS["apollo"]
    assert probe_module._search_params("apollo") == {}
    lusha_url = probe_module._search_url("lusha", "example.org")
    assert lusha_url == probe_module.DISCOVERY_ENDPOINTS["lusha"]
    assert probe_module._search_params("lusha") == {}


# --- Round 4 correction: reveal_fields_present must not false-positive on a provider's
# own `has_*` flag key names ------------------------------------------------------------

def test_apollo_has_email_flag_key_is_not_a_reveal_field(monkeypatch):
    """Round 4 (2026-09-18, tennis.com.au) found Apollo's preview item carries
    has_email/has_direct_phone FLAG keys, never a real email/phone value -- the OLD
    substring check ('email' in blob) treated the flag key NAME itself as a reveal
    field, a false positive. The fixed check reads exact value-bearing keys only."""
    _set_all_creds(monkeypatch)
    monkeypatch.setenv("ALLOW_DISCOVERY_PROBE", "true")
    recorder = []
    overrides = {"apollo": _FakeResponse(200, {"people": [
        {"first_name": "A", "last_name_obfuscated": "B...", "title": "GM",
         "has_email": True, "has_direct_phone": True}]})}
    _default_transport(monkeypatch, recorder, search_status=overrides)

    verdict = probe_module.run_probe(DOMAIN)
    apollo = verdict["providers"]["apollo"]
    assert apollo["people_returned"] is True
    assert apollo["reveal_fields_present"] is False


def test_a_real_reveal_value_is_still_detected(monkeypatch):
    """The fixed exact-key check must still catch a GENUINE reveal field -- proving the
    fix narrows the check, it does not blind it."""
    _set_all_creds(monkeypatch)
    monkeypatch.setenv("ALLOW_DISCOVERY_PROBE", "true")
    recorder = []
    overrides = {"apollo": _FakeResponse(200, {"people": [
        {"first_name": "A", "last_name": "B", "title": "GM", "email": "a@example.org"}]})}
    _default_transport(monkeypatch, recorder, search_status=overrides)

    verdict = probe_module.run_probe(DOMAIN)
    assert verdict["providers"]["apollo"]["reveal_fields_present"] is True


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
