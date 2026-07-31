# tests/test_check_hubspot_list_scope.py
#
# Phase 25 Plan 01 Task 1 — offline proof for scripts/check_hubspot_list_scope.py.
# Fully hermetic: `requests.get` is replaced by a raiser in an autouse fixture, so a test
# that forgets to mock fails loudly instead of reaching HubSpot. The script itself is a
# LIVE-ONLY probe (lives in scripts/, no `test_` prefix -> pytest never collects it);
# this file proves its pure classifier and its env gate, mirroring
# tests/test_check_provider_credits.py.
import json
import re
from pathlib import Path

import pytest
import requests

import scripts.check_hubspot_list_scope as probe


class _FakeResponse:
    def __init__(self, status_code, json_body=None, raise_json=False):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._json_body = json_body
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise json.JSONDecodeError("malformed", "doc", 0)
        return self._json_body


def _raise(*args, **kwargs):
    raise AssertionError("a live HubSpot request leaked past a guard/gate that should have refused")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)
    monkeypatch.setattr(requests, "get", _raise)
    monkeypatch.setattr(requests, "post", _raise)


# --- the pure classifier: one named branch per status ------------------------------------

def test_200_is_granted_and_carries_the_resolved_list_id():
    result = probe.classify_scope(200, {"list": {"listId": "4821", "name": "ANZ Racing Bodies"}})
    assert result["verdict"] == probe.GRANTED
    assert result["status"] == 200
    assert result["list_id"] == "4821"


def test_200_with_an_unexpected_body_shape_is_still_granted_with_no_list_id():
    for body in (None, {}, {"list": "not-a-dict"}, ["unexpected"]):
        result = probe.classify_scope(200, body)
        assert result["verdict"] == probe.GRANTED
        assert result["list_id"] is None


def test_404_is_granted_because_the_request_was_authorized_and_only_the_name_missed():
    result = probe.classify_scope(404, {"message": "list not found"})
    assert result["verdict"] == probe.GRANTED
    assert result["status"] == 404
    assert result["list_id"] is None


def test_403_is_denied():
    result = probe.classify_scope(403, {"message": "missing scopes"})
    assert result["verdict"] == probe.DENIED
    assert result["status"] == 403


def test_404_and_403_produce_different_verdicts():
    """The whole reason this probe exists: conflating these answers the question backwards."""
    assert probe.classify_scope(404, None)["verdict"] != probe.classify_scope(403, None)["verdict"]


def test_401_is_distinct_from_both_granted_and_denied():
    """A bad or absent token is not evidence about scope in either direction."""
    verdict = probe.classify_scope(401, {"message": "invalid authentication"})["verdict"]
    assert verdict == probe.UNAUTHENTICATED
    assert verdict != probe.GRANTED
    assert verdict != probe.DENIED


@pytest.mark.parametrize("status", [429, 500, 502, 418])
def test_other_statuses_are_inconclusive(status):
    assert probe.classify_scope(status, None)["verdict"] == probe.INCONCLUSIVE


def test_a_transport_failure_classifies_as_inconclusive():
    assert probe.classify_scope(None, None)["verdict"] == probe.INCONCLUSIVE


def test_every_verdict_carries_a_human_readable_reason():
    for status in (200, 404, 403, 401, 500, None):
        assert probe.classify_scope(status, None)["reason"].strip()


# --- the caller degrades, never propagates ------------------------------------------------

def test_transport_exception_yields_inconclusive_and_never_propagates(monkeypatch):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")

    def timeout_get(*args, **kwargs):
        raise requests.exceptions.Timeout("connect timeout")

    monkeypatch.setattr(requests, "get", timeout_get)
    result = probe.probe_list_scope("Any List", probe.COMPANIES_OBJECT_TYPE_ID)
    assert result["verdict"] == probe.INCONCLUSIVE
    assert result["status"] is None
    assert result["error"] == "Timeout"


def test_malformed_json_body_still_classifies_from_the_status_code(monkeypatch):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setattr(
        requests, "get",
        lambda url, headers=None, timeout=None: _FakeResponse(403, raise_json=True))
    assert probe.probe_list_scope("Any List", "0-2")["verdict"] == probe.DENIED


def test_the_probed_url_encodes_the_list_name_and_never_carries_the_token(monkeypatch):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "SUPER-SECRET-TOKEN-VALUE")
    seen = {}

    def capture_get(url, headers=None, timeout=None):
        seen["url"] = url
        seen["timeout"] = timeout
        return _FakeResponse(404, {"message": "not found"})

    monkeypatch.setattr(requests, "get", capture_get)
    probe.probe_list_scope("ANZ Racing / Bodies", "0-2")
    assert "ANZ%20Racing%20%2F%20Bodies" in seen["url"]
    assert "SUPER-SECRET-TOKEN-VALUE" not in seen["url"]
    assert seen["timeout"], "a live probe must carry a finite timeout"


# --- memberships summary reports a size, never a data extract (T-25-06) --------------------

def test_memberships_summary_reports_count_and_cursor_only():
    summary = probe.summarize_memberships(200, {
        "results": [{"recordId": "111"}, {"recordId": "222"}],
        "total": 2,
        "paging": {"next": {"after": "250"}},
    })
    assert summary["member_count"] == 2
    assert summary["has_paging_cursor"] is True
    assert summary["status"] == 200


def test_memberships_summary_leaks_no_record_ids():
    body = {"results": [{"recordId": "SECRET-RECORD-111"}], "total": 1}
    summary = probe.summarize_memberships(200, body)
    assert "SECRET-RECORD-111" not in json.dumps(summary)
    assert summary["has_paging_cursor"] is False


def test_memberships_summary_falls_back_to_the_results_length():
    summary = probe.summarize_memberships(200, {"results": [{"recordId": "1"}, {"recordId": "2"}]})
    assert summary["member_count"] == 2


def test_memberships_summary_degrades_to_none_on_an_unexpected_shape():
    assert probe.summarize_memberships(200, None)["member_count"] is None
    assert probe.summarize_memberships(500, None)["member_count"] is None


# --- env gate: no token means no call, and an answer that cannot read as "denied" ----------

def test_missing_token_skips_loudly_with_zero_requests_and_exit_zero(capsys):
    rc = probe.main(["Some Company List"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "skipped (no credentials)" in out
    assert "HUBSPOT_PRIVATE_APP_TOKEN" in out
    assert probe.DENIED not in out, "a skip must never read as a scope verdict"


def test_granted_404_run_exits_zero_and_issues_no_memberships_follow_up(monkeypatch, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    calls = []

    def one_get(url, headers=None, timeout=None):
        calls.append(url)
        return _FakeResponse(404, {"message": "not found"})

    monkeypatch.setattr(requests, "get", one_get)
    rc = probe.main(["a-deliberately-nonsense-name"])
    assert rc == 0
    assert len(calls) == 1, "a 404 resolves no list id, so there is nothing to count members of"
    out = capsys.readouterr().out
    assert probe.GRANTED in out
    assert "404" in out


def test_denied_run_exits_zero_because_a_403_is_an_answer(monkeypatch, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setattr(
        requests, "get",
        lambda url, headers=None, timeout=None: _FakeResponse(403, {"message": "missing scopes"}))
    assert probe.main(["Some Company List"]) == 0
    assert probe.DENIED in capsys.readouterr().out


@pytest.mark.parametrize("status", [401, 500])
def test_an_undetermined_answer_exits_non_zero(monkeypatch, status):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setattr(
        requests, "get",
        lambda url, headers=None, timeout=None: _FakeResponse(status, {"message": "nope"}))
    assert probe.main(["Some Company List"]) != 0


def test_granted_200_follows_up_with_exactly_one_memberships_probe(monkeypatch, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    calls = []

    def two_gets(url, headers=None, timeout=None):
        calls.append(url)
        if "/name/" in url:
            return _FakeResponse(200, {"list": {"listId": "4821"}})
        return _FakeResponse(200, {"results": [{"recordId": "LEAKY-RECORD-ID"}], "total": 1,
                                   "paging": {"next": {"after": "250"}}})

    monkeypatch.setattr(requests, "get", two_gets)
    rc = probe.main(["ANZ Racing Bodies"])
    assert rc == 0
    assert len(calls) == 2
    assert calls[1].endswith("/crm/v3/lists/4821/memberships")
    out = capsys.readouterr().out
    assert "member_count=1" in out
    assert "LEAKY-RECORD-ID" not in out


def test_output_states_that_this_settles_lists_and_not_saved_views(monkeypatch, capsys):
    """HubSpot saved views have no public API — the probe must not imply it resolved one."""
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setattr(
        requests, "get",
        lambda url, headers=None, timeout=None: _FakeResponse(404, {"message": "not found"}))
    probe.main(["Some Company List"])
    out = capsys.readouterr().out.lower()
    assert "saved view" in out


# --- the token never reaches a verdict, an exception, or stdout ----------------------------

def test_no_verdict_value_equals_the_token_it_was_given(monkeypatch, capsys):
    token = "SUPER-SECRET-TOKEN-VALUE"
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", token)
    monkeypatch.setattr(
        requests, "get",
        lambda url, headers=None, timeout=None: _FakeResponse(200, {"list": {"listId": "4821"}})
        if "/name/" in url else _FakeResponse(200, {"results": [], "total": 0}))

    verdict = probe.probe_list_scope("Some Company List", "0-2")
    for value in verdict.values():
        assert value != token
    assert token not in json.dumps(verdict, default=str)

    probe.main(["Some Company List"])
    assert token not in capsys.readouterr().out


def test_script_source_never_interpolates_the_token_env_var_into_a_print():
    """Mentioning the env var's NAME in a print is fine; interpolating its RESOLVED value
    into an f-string print() is what must never happen."""
    text = Path(probe.__file__).read_text()
    interpolation_re = re.compile(r"\{[^{}]*(?:getenv|environ)[^{}]*\}")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if "print(" not in line:
            continue
        for match in interpolation_re.findall(line):
            assert "HUBSPOT_PRIVATE_APP_TOKEN" not in match, (
                f"check_hubspot_list_scope.py:{lineno}: the token is interpolated into a "
                f"print() call: {line!r}")


def test_the_script_calls_load_dotenv_nowhere():
    """Every live script here is run through the documented dotenv wrapper; a script that
    loads .env itself makes the runbook's command a lie and hides a missing-creds skip."""
    assert "load_dotenv" not in Path(probe.__file__).read_text()
