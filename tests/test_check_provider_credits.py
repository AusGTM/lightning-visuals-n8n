# tests/test_check_provider_credits.py
#
# Phase 16.1 Plan 02 Task 2 (reviews A6) — offline proof for scripts/check_provider_credits.py.
# Fully hermetic: no network. Mirrors tests/test_deploy_n8n_workflows.py's monkeypatch
# pattern. check_provider_credits.py itself is a LIVE-ONLY utility — this file proves its
# functions' failure paths with MOCKED requests; the script is never invoked live here.
import json

import pytest
import requests

import scripts.check_provider_credits as check_credits


class _FakeResponse:
    def __init__(self, status_code, json_body=None, ok=None, raise_json=False):
        self.status_code = status_code
        self.ok = ok if ok is not None else 200 <= status_code < 300
        self._json_body = json_body
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise json.JSONDecodeError("malformed", "doc", 0)
        return self._json_body


def _raise(*args, **kwargs):
    raise AssertionError("a live provider request leaked past a guard/gate that should have refused")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    for var in ("LUSHA_API_KEY", "APOLLO_API_KEY", "ZOOMINFO_CLIENT_ID", "ZOOMINFO_CLIENT_SECRET"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(requests, "get", _raise)
    monkeypatch.setattr(requests, "post", _raise)


# --- import surface (reviews A3) --------------------------------------------------------

def test_imports_side_effect_free_provider_registry_not_the_builder():
    src = (check_credits.ROOT / "scripts" / "check_provider_credits.py").read_text()
    assert "import build_cloud_workflows" not in src
    assert "from provider_registry import" in src


def test_importing_the_script_writes_no_generated_codegen_files():
    import glob
    before = set(glob.glob(str(check_credits.ROOT) + "/**/*", recursive=True))
    import importlib
    importlib.reload(check_credits)
    after = set(glob.glob(str(check_credits.ROOT) + "/**/*", recursive=True))
    assert after == before, f"importing check_provider_credits created file(s): {after - before}"


# --- no-creds skip path: zero requests, exit 0 --------------------------------------------

def test_no_creds_skips_cleanly_with_zero_requests(capsys):
    rc = check_credits.main()
    assert rc == 0
    assert "skipped (no provider creds)" in capsys.readouterr().out


# --- partial creds: only configured providers are called ---------------------------------

def test_partial_creds_only_calls_the_configured_provider(monkeypatch, capsys):
    monkeypatch.setenv("LUSHA_API_KEY", "fake-lusha-key")
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append((url, headers))
        return _FakeResponse(200, {"credits": {"total": 4200, "used": 82, "remaining": 4118}})

    monkeypatch.setattr(requests, "get", fake_get)
    rc = check_credits.main()
    assert rc == 0
    assert len(calls) == 1  # only Lusha called
    out = capsys.readouterr().out
    assert "lusha: credits=4118" in out
    assert "apollo: skipped (no credentials configured)" in out
    assert "zoominfo: skipped (no credentials configured)" in out


# --- Lusha success extraction --------------------------------------------------------------

def test_lusha_success_extraction(monkeypatch):
    monkeypatch.setenv("LUSHA_API_KEY", "fake-lusha-key")
    monkeypatch.setattr(
        requests, "get",
        lambda url, headers=None, timeout=None: _FakeResponse(
            200, {"credits": {"total": 4200, "used": 82, "remaining": 4118}}))
    result = check_credits._check_lusha()
    assert result == {"provider": "lusha", "status": 200, "credits": 4118}


# --- Apollo 403 (live-validated, non-master key) -> null -----------------------------------

def test_apollo_403_degrades_to_null_credits(monkeypatch):
    monkeypatch.setenv("APOLLO_API_KEY", "fake-apollo-key")
    monkeypatch.setattr(
        requests, "post",
        lambda url, headers=None, timeout=None: _FakeResponse(
            403, {"error": "API_INACCESSIBLE"}, ok=False))
    result = check_credits._check_apollo()
    assert result["credits"] is None
    assert result["status"] == 403


# --- ZoomInfo mint failure -> null, NO usage GET issued -------------------------------------

def test_zoominfo_mint_failure_never_issues_the_usage_get(monkeypatch):
    monkeypatch.setenv("ZOOMINFO_CLIENT_ID", "fake-id")
    monkeypatch.setenv("ZOOMINFO_CLIENT_SECRET", "fake-secret")
    get_calls = []
    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeResponse(401, {"error": "invalid_client"}, ok=False))
    monkeypatch.setattr(requests, "get", lambda *a, **k: (get_calls.append(1), _raise())[1])

    result = check_credits._check_zoominfo()
    assert result["credits"] is None
    assert result["error"] == "mint_failed"
    assert get_calls == []  # no usage GET was ever attempted


def test_zoominfo_success_extraction_prefers_unique_id_limit(monkeypatch):
    monkeypatch.setenv("ZOOMINFO_CLIENT_ID", "fake-id")
    monkeypatch.setenv("ZOOMINFO_CLIENT_SECRET", "fake-secret")
    monkeypatch.setattr(
        requests, "post",
        lambda *a, **k: _FakeResponse(200, {"access_token": "fake-bearer-token", "expires_in": 86400}))
    monkeypatch.setattr(
        requests, "get",
        lambda url, headers=None, timeout=None: _FakeResponse(200, {"data": [{"attributes": {"usage": [
            {"limitType": "requestLimit", "totalLimit": 0, "usageRemaining": 0},
            {"limitType": "recordLimit", "totalLimit": 0, "usageRemaining": 0},
            {"limitType": "uniqueIdLimit", "totalLimit": 12000, "usageRemaining": 9345},
        ]}}]}))
    result = check_credits._check_zoominfo()
    assert result == {"provider": "zoominfo", "status": 200, "credits": 9345}


# --- timeout + malformed JSON -> null, never raises ------------------------------------------

def test_timeout_degrades_to_null_without_raising(monkeypatch):
    monkeypatch.setenv("LUSHA_API_KEY", "fake-lusha-key")

    def timeout_get(*args, **kwargs):
        raise requests.exceptions.Timeout("connect timeout")

    monkeypatch.setattr(requests, "get", timeout_get)
    result = check_credits._check_lusha()
    assert result["credits"] is None
    assert result["status"] is None


def test_malformed_json_degrades_to_null_without_raising(monkeypatch):
    monkeypatch.setenv("LUSHA_API_KEY", "fake-lusha-key")
    monkeypatch.setattr(
        requests, "get",
        lambda url, headers=None, timeout=None: _FakeResponse(200, raise_json=True))
    result = check_credits._check_lusha()
    assert result["credits"] is None


# --- captured output never contains the supplied fake secret values --------------------------

def test_captured_output_never_contains_the_fake_secret_values(monkeypatch, capsys):
    monkeypatch.setenv("LUSHA_API_KEY", "SUPER-SECRET-LUSHA-VALUE")
    monkeypatch.setenv("APOLLO_API_KEY", "SUPER-SECRET-APOLLO-VALUE")
    monkeypatch.setenv("ZOOMINFO_CLIENT_ID", "SUPER-SECRET-ZI-ID")
    monkeypatch.setenv("ZOOMINFO_CLIENT_SECRET", "SUPER-SECRET-ZI-SECRET")

    monkeypatch.setattr(
        requests, "get",
        lambda url, headers=None, timeout=None: _FakeResponse(200, {"credits": {"remaining": 1}})
        if "lusha" in url else _FakeResponse(200, {"data": [{"attributes": {"usage": []}}]}))
    monkeypatch.setattr(
        requests, "post",
        lambda url, headers=None, timeout=None, auth=None, data=None: _FakeResponse(403, {"error": "nope"}, ok=False)
        if "apollo" in url else _FakeResponse(200, {"access_token": "fake-bearer-token"}))

    check_credits.main()
    out = capsys.readouterr().out
    for secret in ("SUPER-SECRET-LUSHA-VALUE", "SUPER-SECRET-APOLLO-VALUE",
                   "SUPER-SECRET-ZI-ID", "SUPER-SECRET-ZI-SECRET"):
        assert secret not in out


@pytest.mark.parametrize("secret_name", [
    "LUSHA_API_KEY", "APOLLO_API_KEY", "ZOOMINFO_CLIENT_ID", "ZOOMINFO_CLIENT_SECRET",
])
def test_script_source_never_interpolates_a_secret_env_var_into_a_print(secret_name):
    """Mentioning a secret env var's NAME in a print is fine; interpolating its RESOLVED
    value into an f-string print() is what must never happen."""
    import re
    text = (check_credits.ROOT / "scripts" / "check_provider_credits.py").read_text()
    interpolation_re = re.compile(r"\{[^{}]*(?:getenv|environ)[^{}]*\}")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if "print(" not in line:
            continue
        for match in interpolation_re.findall(line):
            assert secret_name not in match, (
                f"check_provider_credits.py:{lineno}: secret env var {secret_name!r} is "
                f"interpolated into a print() call: {line!r}"
            )
