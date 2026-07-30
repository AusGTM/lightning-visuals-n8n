"""Shared fixtures for operator-claude-plugin's test suite.

Puts operator-claude-plugin/scripts on sys.path so plugin modules import as flat names
(e.g. `import config_gate`) — importing a package literally called `scripts` from the repo
root would resolve to the REPO's own scripts/ package (test_no_backend_imports.py exists
to forbid exactly that collision).

The autouse `no_network` fixture is the point of this file: every plugin test runs with
`requests` stubbed so no test can ever perform a real POST, by construction rather than by
discipline (23-VALIDATION.md's Wave 0 critical constraint).
"""
import csv
import sys
from pathlib import Path

import openpyxl
import pytest
import requests

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
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
    """Syntactically valid config dict — never read from the operator's real config file."""
    return {
        "n8n_url": "https://fake-tenant.n8n.cloud",
        "webhook_secret": "fake-secret-for-tests-only",
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
