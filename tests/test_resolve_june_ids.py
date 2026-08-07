# tests/test_resolve_june_ids.py
#
# Phase 41 Plan 02 Task 1 (D-09) — offline coverage for scripts/resolve_june_ids.py.
# Every test stubs src.hubspot_client's `requests` reference; none touches the live
# portal.
import pytest
import requests

import scripts.resolve_june_ids as rji
from src import hubspot_client


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)

    def json(self):
        return self._payload


class FakeTransport:
    """Stub for src.hubspot_client's `requests` reference. GET responses are keyed by
    the company id embedded in the URL's final path segment; POST (search) responses
    are consumed in FIFO order, matching the domain-then-name sequence _resolve_one
    issues."""

    def __init__(self, get_responses=None, search_responses=None):
        self.get_responses = dict(get_responses or {})
        self.search_responses = list(search_responses or [])
        self.calls = []

    def get(self, url, headers=None, params=None, timeout=None):
        company_id = url.rstrip("/").rsplit("/", 1)[-1]
        self.calls.append(("get", company_id))
        return self.get_responses[company_id]

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(("post", json))
        return self.search_responses.pop(0)


class _RefusingTransport:
    """Any call is a test failure -- used to prove zero HTTP calls on refusal."""

    def get(self, *a, **kw):
        raise AssertionError("get_record must not be called when the script refuses")

    def post(self, *a, **kw):
        raise AssertionError("search_records must not be called when the script refuses")


@pytest.fixture(autouse=True)
def _credentials(monkeypatch):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token-for-tests-only")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", rji.EXPECTED_PORTAL_ID)


def _patch_transport(monkeypatch, transport):
    monkeypatch.setattr(hubspot_client, "requests", transport)


# ----------------------------------------------------------------------------------
# build_report -- the four resolution outcomes
# ----------------------------------------------------------------------------------

def test_live_outcome(monkeypatch):
    transport = FakeTransport(get_responses={
        "111": FakeResponse(200, {"properties": {
            "name": "Acme", "domain": "acme.com",
            "annualrevenue": "5000000", "numberofemployees": "50",
        }}),
    })
    _patch_transport(monkeypatch, transport)

    rows = {"111": {"_name": "Acme"}}
    source = {"111": {"name": "Acme"}}
    report, exit_code = rji.build_report(rows, source, {"source_sha256": "abc"})

    assert exit_code == 0
    assert report["resolved_ids"] == ["111"]
    assert report["unmatched"] == []
    rec = report["records"][0]
    assert rec["outcome"] == "live"
    assert rec["resolved_id"] == "111"
    assert rec["domain"] == "acme.com"
    assert rec["annualrevenue_present"] is True
    assert rec["numberofemployees_present"] is True
    assert report["source_sha256"] == "abc"
    assert len(transport.calls) == 1  # exactly one GET, no search issued


def test_rematched_outcome_via_domain_search(monkeypatch):
    transport = FakeTransport(
        get_responses={"222": FakeResponse(404, {})},
        search_responses=[
            FakeResponse(200, {"results": [
                {"id": "999", "properties": {"name": "New Co", "domain": "example.com"}}
            ]}),
        ],
    )
    _patch_transport(monkeypatch, transport)

    rows = {"222": {"_evidence": {"lv_org_type": "https://www.example.com/about"}}}
    source = {"222": {"name": "Old Co"}}
    report, exit_code = rji.build_report(rows, source, {})

    assert exit_code == 0
    rec = report["records"][0]
    assert rec["outcome"] == "rematched"
    assert rec["resolved_id"] == "999"
    assert report["resolved_ids"] == ["999"]
    # domain search hit on the first try -- no name search issued.
    assert transport.calls == [("get", "222"), ("post", None)] or transport.calls[1][0] == "post"


def test_ambiguous_outcome_excludes_id_from_resolved(monkeypatch):
    transport = FakeTransport(
        get_responses={"333": FakeResponse(404, {})},
        search_responses=[
            FakeResponse(200, {"results": [
                {"id": "a", "properties": {}}, {"id": "b", "properties": {}},
            ]}),
        ],
    )
    _patch_transport(monkeypatch, transport)

    rows = {"333": {"_evidence": {"lv_org_type": "https://dupe.example/about"}}}
    source = {"333": {"name": "Dupe Co"}}
    report, exit_code = rji.build_report(rows, source, {})

    rec = report["records"][0]
    assert rec["outcome"] == "ambiguous"
    assert "333" not in report["resolved_ids"]
    assert "333" in report["unmatched"]
    # ambiguous stops the re-match immediately -- name search never runs.
    assert len(transport.calls) == 2


def test_unmatched_outcome_when_no_search_hits(monkeypatch):
    transport = FakeTransport(
        get_responses={"444": FakeResponse(404, {})},
        search_responses=[FakeResponse(200, {"results": []})],  # name search only
    )
    _patch_transport(monkeypatch, transport)

    rows = {"444": {}}  # no _evidence -> no domain search issued
    source = {"444": {"name": "Ghost Co"}}
    report, exit_code = rji.build_report(rows, source, {})

    rec = report["records"][0]
    assert rec["outcome"] == "unmatched"
    assert "444" not in report["resolved_ids"]
    assert "444" in report["unmatched"]
    assert exit_code == 1  # nothing resolved at all


def test_unmatched_outcome_when_name_also_absent(monkeypatch):
    """A dead id with no evidence-derived domain and no source-snapshot name issues no
    search at all -- unmatched without a wasted call."""
    transport = FakeTransport(get_responses={"555": FakeResponse(404, {})})
    _patch_transport(monkeypatch, transport)

    rows = {"555": {}}
    source = {}  # no name recorded for this id
    report, _ = rji.build_report(rows, source, {})

    rec = report["records"][0]
    assert rec["outcome"] == "unmatched"
    assert len(transport.calls) == 1  # only the initial GET


def test_non_404_error_is_recorded_as_unmatched_not_raised(monkeypatch):
    transport = FakeTransport(get_responses={"666": FakeResponse(500, {})})
    _patch_transport(monkeypatch, transport)

    rows = {"666": {}}
    report, _ = rji.build_report(rows, {}, {})

    rec = report["records"][0]
    assert rec["outcome"] == "unmatched"
    assert "error" in rec


# ----------------------------------------------------------------------------------
# False-green guard
# ----------------------------------------------------------------------------------

def test_empty_rows_table_is_a_failure():
    report, exit_code = rji.build_report({}, {}, {})
    assert exit_code != 0
    assert "zero" in report["verdict"].lower()
    assert "examined" in report["verdict"].lower()


# ----------------------------------------------------------------------------------
# main() -- credential / portal refusal gates, zero HTTP calls
# ----------------------------------------------------------------------------------

def test_main_refuses_without_token(monkeypatch, tmp_path):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)
    monkeypatch.setattr(hubspot_client, "requests", _RefusingTransport())
    monkeypatch.setattr(rji, "REPORT_PATH", tmp_path / "report.json")

    exit_code = rji.main()

    assert exit_code != 0


def test_main_refuses_on_wrong_portal(monkeypatch, tmp_path):
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "not-the-right-portal")
    monkeypatch.setattr(hubspot_client, "requests", _RefusingTransport())
    monkeypatch.setattr(rji, "REPORT_PATH", tmp_path / "report.json")

    exit_code = rji.main()

    assert exit_code != 0


def test_main_end_to_end_with_stubbed_files_and_transport(monkeypatch, tmp_path, capsys):
    candidates_path = tmp_path / "june_candidates.json"
    source_path = tmp_path / "june_candidates_source.json"
    candidates_path.write_text(
        '{"_meta": {"source_sha256": "deadbeef"}, '
        '"rows": {"111": {"_name": "Acme"}}}'
    )
    source_path.write_text('{"111": {"name": "Acme"}}')

    monkeypatch.setattr(rji, "CANDIDATES_PATH", candidates_path)
    monkeypatch.setattr(rji, "SOURCE_SNAPSHOT_PATH", source_path)
    monkeypatch.setattr(rji, "REPORT_PATH", tmp_path / "41-id-resolution.json")

    transport = FakeTransport(get_responses={
        "111": FakeResponse(200, {"properties": {"name": "Acme", "domain": "acme.com"}}),
    })
    _patch_transport(monkeypatch, transport)

    exit_code = rji.main()

    assert exit_code == 0
    assert (tmp_path / "41-id-resolution.json").exists()
    out = capsys.readouterr().out
    assert "111" in out  # the resolved id list printed on the final stdout line
