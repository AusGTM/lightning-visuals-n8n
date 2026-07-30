"""Shared fixtures for operator-claude-plugin's test suite.

Puts operator-claude-plugin/scripts on sys.path so plugin modules import as flat names
(e.g. `import config_gate`) — importing a package literally called `scripts` from the repo
root would resolve to the REPO's own scripts/ package (test_no_backend_imports.py exists
to forbid exactly that collision).

The autouse `no_network` fixture is the point of this file: every plugin test runs with
`requests` stubbed so no test can ever perform a real POST (or GET — the guard patches
`Session.request`, which `requests.get` routes through too), by construction rather than
by discipline (23-VALIDATION.md's Wave 0 critical constraint).
"""
import copy
import csv
import json
import sys
from pathlib import Path

import openpyxl
import pytest
import requests

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
FIXTURES_DIR = PLUGIN_ROOT / "tests" / "fixtures"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Messy headers exercising config/column_mapping.yaml's alias table: "Email Address",
# "First Name" and "Mobile" all resolve to a canonical prop; "Notes" is not in the alias
# table and must render as dropped in the preview (23-05).
CSV_HEADER = ["Email Address", "First Name", "Mobile", "Notes"]
CSV_ROW_COUNT = 25  # > 20 so the first-10/last-3 preview branch (D-08) is exercisable


def _sample_rows():
    return [
        [f"person{i}@example.com", f"First{i}", f"04{i:08d}", f"note {i}"]
        for i in range(CSV_ROW_COUNT)
    ]


@pytest.fixture
def sample_csv(tmp_path):
    """A CSV with messy headers + one header the alias table does not know, and enough
    rows for the >20-row preview branch."""
    path = tmp_path / "contacts.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        writer.writerows(_sample_rows())
    return path


@pytest.fixture
def sample_xlsx(tmp_path):
    """Same content as sample_csv, generated at fixture time with openpyxl — visible in
    test source rather than a committed binary."""
    path = tmp_path / "contacts.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(CSV_HEADER)
    for row in _sample_rows():
        ws.append(row)
    wb.save(path)
    return path


@pytest.fixture
def fake_config():
    """Syntactically valid config dict — never read from the operator's real config file.

    Includes `n8n_api_key`: the executions-API fallback (26-01) authenticates with
    `X-N8N-API-KEY`, distinct from `webhook_secret`'s `X-Enrichment-Secret`
    (26-CONTEXT.md key_links) — both live in the same config file per REQUIREMENTS.md's
    credential-boundary table.
    """
    return {
        "n8n_url": "https://fake-tenant.n8n.cloud",
        "webhook_secret": "fake-secret-for-tests-only",
        "n8n_api_key": "fake-n8n-api-key-for-tests-only",
        "column_mapping_path": None,
    }


class _StubResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"status": "accepted"}

    def json(self):
        return self._payload


class _StubTransport:
    """Callable recording every call it's handed, in place of a real requests.post."""

    def __init__(self):
        self.calls = []

    def __call__(self, url, headers=None, files=None, timeout=None, **kwargs):
        self.calls.append(
            {"url": url, "headers": headers, "files": files, "timeout": timeout, **kwargs}
        )
        return _StubResponse()


@pytest.fixture
def stub_transport():
    """The seam every dispatch test uses in place of a real POST."""
    return _StubTransport()


@pytest.fixture
def contact_execution():
    """A redacted execution payload shaped like `data.resultData.runData` for
    `hubspot/contact-upload`, with one `Decide Action` row per outcome (match/
    net_new/ambiguous/rejected) plus `HubSpot Update`, `HubSpot Create` and
    `Set Review` entries. Returns a fresh deep copy per test so no test can mutate a
    fixture another test then reads."""
    return copy.deepcopy(json.loads((FIXTURES_DIR / "execution_contact_upload.json").read_text()))


class _StubGetResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _StubGetTransport:
    """Callable recording every GET `executions_client.py` makes, returning a scripted
    payload per call in order — in place of a real `requests.get`."""

    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.calls = []

    def __call__(self, url, headers=None, params=None, timeout=None, **kwargs):
        self.calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
        payload = self._payloads.pop(0) if self._payloads else {}
        return _StubGetResponse(payload)


@pytest.fixture
def stub_get_transport_factory():
    """Returns the `_StubGetTransport` class so a test can script its own sequence of
    payloads (workflow list, then execution list, then execution fetch, ...)."""
    return _StubGetTransport


def _default_extraction_records():
    """Two records exercising both identity groups: one via email, one via
    firstname+lastname+company — matching config/column_mapping.yaml's `any_of` groups."""
    return [
        {
            "row": {
                "email": "amy@example.com",
                "firstname": "Amy",
                "lastname": "Adams",
                "company": "Acme",
            },
            "provenance": {
                "input": "pasted_text",
                "locator": "line 3: 'Amy Adams, amy@example.com, Acme'",
            },
        },
        {
            "row": {"firstname": "Ben", "lastname": "Baker", "company": "Widgets Co"},
            "provenance": {
                "input": "pasted_text",
                "locator": "line 5: 'Ben Baker, Widgets Co'",
            },
        },
    ]


@pytest.fixture
def extraction_artifact_factory(tmp_path):
    """Builds an extraction-artifact JSON file under tmp_path with sane defaults a test
    can override (batch_id, source, records, ambiguities), or writes arbitrary raw text
    verbatim (for malformed-artifact tests) — so later tests build variants without each
    one hand-writing JSON."""

    def _make(
        filename="extracted.json",
        batch_id="batch-1",
        source=None,
        records=None,
        ambiguities=None,
        raw_text=None,
    ):
        path = tmp_path / filename
        if raw_text is not None:
            path.write_text(raw_text, encoding="utf-8")
            return path

        artifact = {
            "batch_id": batch_id,
            "source": source if source is not None else {"kind": "prose", "detail": "pasted text"},
            "records": _default_extraction_records() if records is None else records,
            "ambiguities": [] if ambiguities is None else ambiguities,
        }
        path.write_text(json.dumps(artifact), encoding="utf-8")
        return path

    return _make


@pytest.fixture
def extraction_artifact(extraction_artifact_factory):
    """A valid two-record prose extraction artifact written to tmp_path."""
    return extraction_artifact_factory()


@pytest.fixture(autouse=True)
def no_network(monkeypatch, request):
    """Any requests.post/request/Session.request call inside a test raises immediately.

    Autouse so a later plan's test cannot opt out by forgetting to request a fixture — the
    guard applies to every test in this suite by construction, not by discipline.
    """
    test_name = request.node.name

    def _blocked(*args, **kwargs):
        raise RuntimeError(
            f"Network access blocked in test '{test_name}': plugin tests must use "
            "stub_transport instead of a real requests call."
        )

    monkeypatch.setattr(requests, "post", _blocked)
    monkeypatch.setattr(requests, "request", _blocked)
    monkeypatch.setattr(requests.Session, "request", _blocked)
