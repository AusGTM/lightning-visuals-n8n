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
from datetime import datetime, timedelta, timezone
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

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _as_response(scripted, response_cls):
    """One scripted stub entry -> a response object. A bare payload means 200; a
    `(status_code, payload)` pair carries a status; an Exception instance is raised by
    the transport itself (a dead endpoint), and an Exception as the *payload* half of a
    pair is raised by `.json()` (a 200 carrying an unparseable body)."""
    if isinstance(scripted, Exception):
        raise scripted
    if isinstance(scripted, tuple):
        status_code, payload = scripted
        return response_cls(status_code=status_code, payload=payload)
    return response_cls(status_code=200, payload=scripted)


class _StubTransport:
    """Callable recording every call it's handed, in place of a real requests.post.

    With no `responses` it answers every call with the default accepted body (every
    dispatch test's usage). With one it replays them in order — see `_as_response` for
    the entry shapes, which cover a non-2xx, a dead endpoint and an unparseable body.
    """

    def __init__(self, responses=None):
        self._responses = list(responses) if responses is not None else None
        self.calls = []

    def __call__(self, url, headers=None, files=None, timeout=None, **kwargs):
        self.calls.append(
            {"url": url, "headers": headers, "files": files, "timeout": timeout, **kwargs}
        )
        if self._responses is None:
            return _StubResponse()
        scripted = self._responses.pop(0) if self._responses else {}
        return _as_response(scripted, _StubResponse)


@pytest.fixture
def stub_transport():
    """The seam every dispatch test uses in place of a real POST."""
    return _StubTransport()


@pytest.fixture
def stub_post_transport_factory():
    """Returns the `_StubTransport` class so a test can script POST responses
    (a 401, a dead endpoint, an unparseable body) rather than the default accepted one."""
    return _StubTransport


@pytest.fixture
def contact_execution():
    """A redacted execution payload shaped like `data.resultData.runData` for
    `hubspot/contact-upload`, with one `Decide Action` row per outcome (match/
    net_new/ambiguous/rejected) plus `HubSpot Update`, `HubSpot Create` and
    `Set Review` entries. Returns a fresh deep copy per test so no test can mutate a
    fixture another test then reads."""
    return copy.deepcopy(json.loads((FIXTURES_DIR / "execution_contact_upload.json").read_text()))


class _StubGetResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    @property
    def ok(self):
        return 200 <= self.status_code < 300

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _StubGetTransport:
    """Callable recording every GET a read client makes, returning a scripted response
    per call in order — in place of a real `requests.get`.

    A scripted entry is a bare payload (200), a `(status_code, payload)` pair, or an
    Exception (raised as a transport failure) — see `_as_response`.
    """

    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.calls = []

    def __call__(self, url, headers=None, params=None, timeout=None, **kwargs):
        self.calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
        scripted = self._payloads.pop(0) if self._payloads else {}
        return _as_response(scripted, _StubGetResponse)


class _StubModuleTransport:
    """A MODULE-shaped recorder: `.get`/`.post`/`.put` on one object, sharing one `calls`
    list so a whole mutation sequence reads back in order.

    Phase 28's modules take `transport` defaulting to the bare `requests` module (28-CONTEXT
    D-28) rather than to a single bound verb, so neither `_StubTransport` nor
    `_StubGetTransport` — both plain callables — fits them. Note that a module-shaped
    transport must be handed down to `n8n_read` as `transport.get`, since `_get_json` CALLS
    what it is given (D-33).

    Scripted entries are shared with `_as_response`: a bare payload (200), a
    `(status_code, payload)` pair, or an Exception raised as a transport failure. With no
    `responses` every call answers 200 with the default accepted body.
    """

    def __init__(self, responses=None):
        self._responses = list(responses) if responses is not None else None
        self.calls = []

    def _record(self, verb, url, **kwargs):
        self.calls.append({"verb": verb, "url": url, **kwargs})
        if self._responses is None:
            return _StubResponse()
        scripted = self._responses.pop(0) if self._responses else {}
        return _as_response(scripted, _StubResponse)

    def get(self, url, headers=None, params=None, timeout=None, **kwargs):
        return self._record("get", url, headers=headers, params=params, timeout=timeout)

    def post(self, url, headers=None, json=None, timeout=None, **kwargs):
        return self._record("post", url, headers=headers, json=json, timeout=timeout)

    def put(self, url, headers=None, json=None, timeout=None, **kwargs):
        return self._record("put", url, headers=headers, json=json, timeout=timeout)

    @property
    def verbs(self):
        return [call["verb"] for call in self.calls]

    @property
    def mutating_calls(self):
        """Every state-changing call. A refusal must leave this empty — the GET that a
        refusal necessarily performed first is not a mutation."""
        return [call for call in self.calls if call["verb"] in ("post", "put")]


@pytest.fixture
def stub_module_transport_factory():
    """Returns `_StubModuleTransport` so a control test can script a whole
    GET → POST → PUT → POST → GET sequence against one recorder."""
    return _StubModuleTransport


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


# =====================================================================================
# Phase 29 Plan 02 Task 1 — sweep fixtures.
#
# Every payload shape the unattended sweep must reason about, INCLUDING the two that look
# healthy and are not (29-RESEARCH Pitfalls 1 and 5). Built as plain data in the fixture
# body, not committed JSON, so a reviewer reads the shape in the test source.
#
# Execution keys mirror the real `/api/v1/executions` objects (`id`, `workflowId`,
# `status`, `startedAt`, `stoppedAt`, `finished`, `workflowData.name`) rather than a
# convenient simplification — a fixture whose keys differ from production is a test that
# passes while the code fails live.
# =====================================================================================

# The reference "now" every timing fixture is anchored to. Fixed, and passed into
# `n8n_read.summarize_execution(..., now=)` by the tests — a fixture anchored to
# wall-clock drifts across the stuck threshold depending on when the suite runs.
SWEEP_NOW = datetime(2026, 7, 31, 12, 0, 0, tzinfo=timezone.utc)

ENRICHMENT_WORKFLOW_ID = "wf-enrichment-cloud"
ENRICHMENT_WORKFLOW_NAME = "LV Enrichment (Cloud template)"
MAINTENANCE_WORKFLOW_ID = "wf-scheduled-maintenance-cloud"
MAINTENANCE_WORKFLOW_NAME = "LV Scheduled Maintenance (Cloud)"

# The five HubSpot-Search nodes in wf_scheduled_maintenance_cloud.json, VERBATIM as
# deployed (29-CONTEXT D-21 — 29-RESEARCH.md abbreviates them and the abbreviations match
# no key in `runData`). All five carry `onError: continueRegularOutput`, so any of them can
# fail while the run still reports success — which is the whole point of the
# `execution_maintenance_falsely_successful` fixture below.
MAINTENANCE_SEARCH_NODES = (
    "SJ-1 Search (input-gap scan)",
    "SJ-2 Search (stale refresh)",
    "SJ-3 Search (requested poller)",
    "Dedupe Search (candidate contacts)",
    "Review Search (approved=true)",
)


def _iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _execution(execution_id, *, status, started_minutes_ago, ran_for_seconds=None,
               workflow_id=ENRICHMENT_WORKFLOW_ID, workflow_name=ENRICHMENT_WORKFLOW_NAME,
               started_at=_iso):
    """One executions-collection item, relative to SWEEP_NOW.

    `ran_for_seconds=None` omits `stoppedAt` entirely — the key is ABSENT, the way n8n
    leaves it for a run still in flight, never present-and-zero.
    """
    started = SWEEP_NOW - timedelta(minutes=started_minutes_ago)
    execution = {
        "id": execution_id,
        "workflowId": workflow_id,
        "status": status,
        "startedAt": started_at(started),
        "finished": status not in ("running", "new", "waiting"),
        "workflowData": {"name": workflow_name},
    }
    if ran_for_seconds is not None:
        execution["stoppedAt"] = _iso(started + timedelta(seconds=ran_for_seconds))
    return execution


@pytest.fixture
def sweep_now():
    """The fixed reference every timing fixture is built against."""
    return SWEEP_NOW


@pytest.fixture
def executions_healthy():
    """The no-notice baseline: recent, finished, every duration knowable."""
    return [
        _execution("e-101", status="success", started_minutes_ago=30, ran_for_seconds=42),
        _execution("e-102", status="success", started_minutes_ago=95, ran_for_seconds=61),
        _execution("e-103", status="success", started_minutes_ago=180, ran_for_seconds=38),
    ]


@pytest.fixture
def executions_with_failure():
    """One genuinely failed run on a named workflow, among healthy ones."""
    return [
        _execution("e-201", status="success", started_minutes_ago=20, ran_for_seconds=40),
        _execution("e-202", status="error", started_minutes_ago=50, ran_for_seconds=12),
    ]


@pytest.fixture
def executions_with_stuck():
    """Both sides of the stuck threshold (default 15 min). A check that flags every
    running execution fails against this fixture instead of passing trivially."""
    return [
        _execution("e-301", status="running", started_minutes_ago=45),
        _execution("e-302", status="running", started_minutes_ago=2),
    ]


@pytest.fixture
def execution_missing_stopped_at():
    """In flight: `stoppedAt` absent, so the duration is UNKNOWN. Code treating the
    absence as zero drags a measured bound down, which is the failure direction that
    produces a watch giving up too early."""
    return _execution("e-401", status="running", started_minutes_ago=7)


@pytest.fixture
def execution_unreadable_start():
    """In flight with an unreadable `startedAt` — `summarize_execution` returns
    `stuck: None`, the third state Phase 27 D-07b(i) forbids rounding to False."""
    return _execution("e-402", status="running", started_minutes_ago=7,
                      started_at=lambda _moment: "not-a-timestamp")


def _search_node_run(*, failed=False):
    """One NodeRun for a maintenance HubSpot-Search node, in the `data.main[0]` shape the
    repo already walks (`enrichment_cost_ledger._node_output_items`)."""
    if failed:
        # `onError: continueRegularOutput` — the node records its error and the run
        # carries on, so the EXECUTION still reports success.
        return {"executionStatus": "error",
                "error": {"message": "401 - HubSpot credential rejected"},
                "data": {"main": [[]]}}
    return {"executionStatus": "success", "error": None,
            "data": {"main": [[{"json": {"total": 3}}]]}}


@pytest.fixture
def execution_maintenance_falsely_successful():
    """D-08b: the run says healthy, the backend is not.

    `status: success` on the scheduled-maintenance workflow while one of the five
    `onError: continueRegularOutput` search nodes returned an error and no rows. This is
    the shape that makes the sweep's blind spot testable — without it, "failed scheduled
    run" gets built against execution status alone and silently misses every upstream
    search failure (29-RESEARCH Pitfall 1).
    """
    execution = _execution("e-501", status="success", started_minutes_ago=12,
                           ran_for_seconds=9, workflow_id=MAINTENANCE_WORKFLOW_ID,
                           workflow_name=MAINTENANCE_WORKFLOW_NAME)
    run_data = {name: [_search_node_run()] for name in MAINTENANCE_SEARCH_NODES}
    run_data["SJ-1 Search (input-gap scan)"] = [_search_node_run(failed=True)]
    execution["data"] = {"resultData": {"runData": run_data}}
    return execution


def _backend_status(*, balances, credential_health, counts):
    """A `backend_status.fetch_backend_status()` result — `{available, reason, data}` with
    `data` being the endpoint body `Build Full Status` emits."""
    return {
        "available": True,
        "reason": None,
        "data": {
            "counts": counts,
            "credential_health": credential_health,
            "balances": balances,
            "checked_at": _iso(SWEEP_NOW),
        },
    }


def _balance(provider, credits, *, error=None, status=200):
    """One `Build Credit Status` balances row, in the shape that node actually emits:
    `configured` is hardcoded true for every REQUESTED provider, and `unreadable` is
    exactly `credits is None` (29-CONTEXT D-22)."""
    return {"provider": provider, "configured": True, "credits": credits,
            "unreadable": credits is None, "error": error, "status": status}


def _health(source, state, *, status=200, reason=None):
    return {"source": source, "state": state, "status": status, "reason": reason}


def _counts(companies_unresolved=2, companies_review=0, contacts_unresolved=4,
            contacts_review=1):
    return {
        "companies_requested_unresolved": companies_unresolved,
        "companies_awaiting_review": companies_review,
        "contacts_requested_unresolved": contacts_unresolved,
        "contacts_awaiting_review": contacts_review,
    }


@pytest.fixture
def backend_status_healthy():
    """Numeric balances well above any floor, nothing awaiting review. The zero here is a
    genuine zero — nothing to review — not an unreadable count."""
    return _backend_status(
        balances=[_balance("lusha", 412), _balance("zoominfo", 1580)],
        credential_health=[_health("lusha", "ok"), _health("zoominfo", "ok"),
                           _health("hubspot", "ok")],
        counts=_counts(companies_review=0, contacts_review=0),
    )


@pytest.fixture
def backend_status_unknown_balance():
    """Apollo's 403-by-design: `configured: true`, `credits: None`, `unreadable: true`,
    credential health `refused`. Never "exhausted", never "healthy" (Pitfall 5).

    The counts here are unreadable too (`null`, never `0`) — the endpoint's own STATUS-06
    contract for a search that failed rather than returned nothing.
    """
    return _backend_status(
        balances=[_balance("lusha", 412),
                  _balance("apollo", None, error="http_403", status=403)],
        credential_health=[_health("lusha", "ok"),
                           _health("apollo", "refused", status=403, reason="http_403")],
        counts=_counts(companies_unresolved=None, companies_review=None,
                       contacts_unresolved=None, contacts_review=None),
    )


@pytest.fixture
def backend_status_unconfigured_provider():
    """The third provider state: never probed at all. Absent from `balances` entirely
    (that node maps over the REQUESTED providers), present in credential_health as
    `state: unknown, reason: not_configured` — `deriveSourceHealth`'s real
    `configured: false` output (29-CONTEXT D-22)."""
    return _backend_status(
        balances=[_balance("lusha", 412)],
        credential_health=[_health("lusha", "ok"),
                           _health("apollo", "unknown", status=None,
                                   reason="not_configured")],
        counts=_counts(),
    )


@pytest.fixture
def backend_status_exhausted():
    """An EXPLICIT numeric balance at a floor — the only shape a quota-exhausted notice
    may fire on."""
    return _backend_status(
        balances=[_balance("lusha", 0), _balance("zoominfo", 1580)],
        credential_health=[_health("lusha", "ok"), _health("zoominfo", "ok")],
        counts=_counts(),
    )


@pytest.fixture
def backend_status_review_backlog():
    """Review counts far above any plausible threshold, with everything else healthy — so
    a backlog notice firing here is attributable to the backlog and nothing else."""
    return _backend_status(
        balances=[_balance("lusha", 412)],
        credential_health=[_health("lusha", "ok"), _health("hubspot", "ok")],
        counts=_counts(companies_review=137, contacts_review=284),
    )


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
