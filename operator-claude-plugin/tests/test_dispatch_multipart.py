"""Tests for tabular.py's read/convert behavior and dispatch.py's multipart POST.

Grouped in one file per plan 23-04's <files> list: tabular's CSV/XLSX handling feeds
directly into dispatch's multipart body, so the two are exercised together the same way
they're actually used. Every dispatch test uses `stub_transport`; the autouse
`no_network` fixture (conftest.py) is what makes an accidental real POST impossible.

Phase 70 Plan 02 (D-70-05/D-70-07): the webhook now answers with an ack only — every
armed test below ALSO scripts a `get_transport` (via `_recovery_get_transport`) for the
unconditional post-POST recovery poll `dispatch()` now makes. `_ingest_workflow_id_cache`
seeds `executions_client`'s process-lifetime workflow-id cache so a test's own recovery
stub sequence is exactly [list_executions, get_execution] — never a third, unscripted
`resolve_workflow_id` GET racing a cache another test file may have already populated.
"""
import csv
import inspect
import io
import json

import pytest

import config_gate
import executions_client
import tabular
import watch
import written_records
from dispatch import DispatchError, NotArmedError, dispatch

_INGEST_WORKFLOW_ID = "wf-ingest-cloud-test"


@pytest.fixture(autouse=True)
def _ingest_workflow_id_cache():
    """Seeds, then restores, `executions_client`'s module-level workflow-id cache for
    just the ingest workflow name — sidesteps a `resolve_workflow_id` GET this file's
    own stub sequences never script, mirroring `test_watch_settle_reporting.py`'s own
    `workflow_id="wf-enrichment-cloud"` explicit-pass precedent (this file's caller,
    `dispatch()`, does not expose a `workflow_id` passthrough, so the cache is the only
    seam)."""
    key = watch.INGEST_WORKFLOW_NAME
    previous = executions_client._workflow_id_cache.get(key)
    executions_client._workflow_id_cache[key] = _INGEST_WORKFLOW_ID
    yield
    if previous is None:
        executions_client._workflow_id_cache.pop(key, None)
    else:
        executions_client._workflow_id_cache[key] = previous


def _settled_ingest_execution(run_id, rows, execution_id="exec-ingest-1"):
    """A settled execution shaped like `data.resultData.runData` carrying "Set
    Config"'s own `run_id` echo (D-70-05's correlation basis) and "Build Ingest
    Response"'s per-row output (D-70-07: the row data the ack no longer carries)."""
    return {
        "id": execution_id,
        "status": "success",
        "data": {"resultData": {"runData": {
            "Set Config": [{"data": {"main": [[{"json": {"run_id": run_id}}]]}}],
            "Build Ingest Response": [{"data": {"main": [[{"json": r} for r in rows]]}}],
        }}},
    }


def _recovery_get_transport(stub_get_transport_factory, run_id, rows,
                             execution_id="exec-ingest-1"):
    """The GET sequence `dispatch()`'s unconditional recovery poll makes for a run that
    settles on the FIRST check: `list_executions`, then `get_execution`."""
    return stub_get_transport_factory([
        {"data": [{"id": execution_id}]},
        _settled_ingest_execution(run_id, rows, execution_id),
    ])


# --- tabular.py: read_table + to_csv_bytes -----------------------------------------


def test_read_table_csv_returns_headers_verbatim_and_every_row(sample_csv):
    headers, rows = tabular.read_table(str(sample_csv))
    assert headers == ["Email Address", "First Name", "Mobile", "Notes"]
    assert len(rows) == 25


def test_read_table_xlsx_matches_csv_headers_and_values(sample_csv, sample_xlsx):
    csv_headers, csv_rows = tabular.read_table(str(sample_csv))
    xlsx_headers, xlsx_rows = tabular.read_table(str(sample_xlsx))
    assert xlsx_headers == csv_headers
    assert xlsx_rows == csv_rows


def test_to_csv_bytes_csv_source_is_the_original_bytes_unchanged(sample_csv):
    assert tabular.to_csv_bytes(str(sample_csv)) == sample_csv.read_bytes()


def test_to_csv_bytes_xlsx_source_matches_headers_and_values_no_remap(sample_xlsx):
    body = tabular.to_csv_bytes(str(sample_xlsx))
    rows = list(csv.reader(io.StringIO(body.decode("utf-8"))))
    expected_headers, expected_rows = tabular.read_table(str(sample_xlsx))
    assert rows[0] == expected_headers
    assert rows[1:] == expected_rows


def test_to_csv_bytes_unsupported_extension_raises(tmp_path):
    bad = tmp_path / "contacts.txt"
    bad.write_text("hello")
    with pytest.raises(tabular.UnsupportedFileError):
        tabular.to_csv_bytes(str(bad))


# --- dispatch.py: the arming gate and the multipart contract -----------------------


def test_armed_parameter_has_no_default():
    assert inspect.signature(dispatch).parameters["armed"].default is inspect.Parameter.empty


def test_missing_armed_argument_raises_typeerror(sample_csv, fake_config):
    with pytest.raises(TypeError):
        dispatch(str(sample_csv), config=fake_config)


def test_unarmed_raises_and_stub_records_zero_calls(sample_csv, fake_config, stub_transport):
    with pytest.raises(NotArmedError):
        dispatch(str(sample_csv), False, fake_config, transport=stub_transport)
    assert stub_transport.calls == []


def test_armed_dispatch_calls_the_stub_exactly_once_with_the_deployed_contract(
    sample_csv, fake_config, stub_transport, stub_get_transport_factory
):
    run_id = "r-deployed-contract"
    get_transport = _recovery_get_transport(stub_get_transport_factory, run_id, [])
    result = dispatch(str(sample_csv), True, fake_config, transport=stub_transport,
                       run_id=run_id, get_transport=get_transport,
                       now=lambda: 0.0, sleep=lambda seconds: None)

    assert len(stub_transport.calls) == 1
    call = stub_transport.calls[0]
    assert call["url"] == "https://fake-tenant.n8n.cloud/webhook/hubspot/contact-upload"
    assert call["headers"]["X-Enrichment-Secret"] == fake_config["webhook_secret"]

    filename, body, content_type = call["files"]["data"]
    assert content_type == "text/csv"
    assert body == sample_csv.read_bytes()

    assert call["timeout"]
    assert call["timeout"] > 0
    # D-70-07: the webhook answers with an ack only — never the row-carrying body this
    # assertion checked before Phase 70 Plan 02. `result["ack"]` (and its `result["body"]`
    # alias) is exactly that ack now; the row data lives at `result["rows"]`, read from
    # the settled execution's runData (D-70-05), never the POST response.
    assert result["ack"] == {"status": "accepted"}
    assert result["body"] == result["ack"]
    assert result["rows"] == []
    assert result["recovered"] is True
    assert result["written_records_failures"] == []
    assert result["run_id"] == run_id


def test_armed_dispatch_with_xlsx_source_sends_converted_csv_bytes(
    sample_xlsx, fake_config, stub_transport, stub_get_transport_factory
):
    get_transport = _recovery_get_transport(stub_get_transport_factory, "r-xlsx", [])
    dispatch(str(sample_xlsx), True, fake_config, transport=stub_transport,
              run_id="r-xlsx", get_transport=get_transport,
              now=lambda: 0.0, sleep=lambda seconds: None)
    call = stub_transport.calls[0]
    _, body, content_type = call["files"]["data"]
    assert content_type == "text/csv"
    assert body == tabular.to_csv_bytes(str(sample_xlsx))


def test_unreadable_file_raises_before_the_transport_is_touched(fake_config, stub_transport, tmp_path):
    missing = tmp_path / "does-not-exist.csv"
    with pytest.raises(OSError):
        dispatch(str(missing), True, fake_config, transport=stub_transport)
    assert stub_transport.calls == []


def test_unsupported_extension_raises_before_the_transport_is_touched(
    fake_config, stub_transport, tmp_path
):
    bad = tmp_path / "contacts.txt"
    bad.write_text("hello")
    with pytest.raises(tabular.UnsupportedFileError):
        dispatch(str(bad), True, fake_config, transport=stub_transport)
    assert stub_transport.calls == []


def test_transport_exception_becomes_a_plain_language_dispatch_error_not_the_raw_text(
    sample_csv, fake_config
):
    def _raising_transport(*args, **kwargs):
        raise RuntimeError("connection refused to header X-Enrichment-Secret: real-secret-value")

    with pytest.raises(DispatchError) as exc:
        dispatch(str(sample_csv), True, fake_config, transport=_raising_transport)
    assert "real-secret-value" not in str(exc.value)


def test_dispatch_with_source_by_field_none_produces_a_byte_identical_files_dict(
    sample_csv, fake_config, stub_transport, stub_get_transport_factory
):
    """Phase 62 Plan 04 (D-62-17): the default (omitted/None) must leave every existing
    caller's `files` dict unchanged apart from D-70-05's own `run_id` field (Phase 70
    Plan 02) — no `source_by_field` key at all."""
    get_transport = _recovery_get_transport(stub_get_transport_factory, "r-sbf-none", [])
    dispatch(str(sample_csv), True, fake_config, transport=stub_transport,
              run_id="r-sbf-none", get_transport=get_transport,
              now=lambda: 0.0, sleep=lambda seconds: None)
    call = stub_transport.calls[0]
    assert set(call["files"].keys()) == {"data", "run_id"}


def test_dispatch_with_source_by_field_adds_exactly_one_extra_multipart_part_no_data_kwarg(
    sample_csv, fake_config, stub_transport, stub_get_transport_factory
):
    """A non-empty map adds ONE more entry to the EXISTING `files` dict — never a `data=`
    kwarg on the transport call (that would be a second, form-encoded body)."""
    source_map = {"firstname": "claude_web", "email": "lusha"}
    get_transport = _recovery_get_transport(stub_get_transport_factory, "r-sbf", [])
    dispatch(str(sample_csv), True, fake_config, transport=stub_transport,
              source_by_field=source_map, run_id="r-sbf", get_transport=get_transport,
              now=lambda: 0.0, sleep=lambda seconds: None)
    call = stub_transport.calls[0]
    assert set(call["files"].keys()) == {"data", "source_by_field", "run_id"}
    assert "data" not in call, "no data= kwarg was added to the transport call"

    part = call["files"]["source_by_field"]
    # A 2-tuple (no filename AND no Content-Type) is load-bearing: n8n's multipart
    # parser files any part carrying a Content-Type header under $binary, not
    # $json.body (observed live 2026-09-10, Phase 70 UAT Gate 1). A third element
    # here would silently break the envelope read again.
    assert len(part) == 2, "no content type on a multipart form FIELD"
    filename, body = part
    assert filename is None
    assert json.loads(body) == source_map
    assert len(call["files"]["run_id"]) == 2 and call["files"]["run_id"][0] is None


def test_missing_webhook_secret_refuses_before_the_transport_is_touched_even_when_armed(
    sample_csv, fake_config, stub_transport
):
    """Regression guard for the load-config-over-refusal fix: `load_config()` no longer
    enforces `webhook_secret` for every caller, so `dispatch()` must guard its own
    transmit path itself — otherwise a secret-less config would reach
    `config["webhook_secret"]` (KeyError) or send an empty secret header."""
    cfg = {k: v for k, v in fake_config.items() if k != "webhook_secret"}
    with pytest.raises(config_gate.ConfigError) as exc:
        dispatch(str(sample_csv), True, cfg, transport=stub_transport)
    assert "webhook_secret" in str(exc.value)
    assert stub_transport.calls == []


# =====================================================================================
# written-records-misses-write (debug session, 2026-08-29): `dispatch()` is the ONLY
# network call this plugin makes for the contacts write path — before this fix it never
# touched `written_records` at all, so a run whose only write went through here produced
# an artifact reporting `not_written`/`hs_object_id: null` for a write that actually
# landed in HubSpot (walk run 3, FINDING C, HubSpot contact 348695309760). Recorded at
# the write site, mirroring `chunking.dispatch_plan`'s own D-59-07 inline-flush precedent
# and its D-59-10 catch/record/continue guard (chunking.py:394-407) verbatim.
# =====================================================================================

def _ingest_response_body(hs_object_id="348695309760"):
    """One row in Build Ingest Response's own shape (scripts/build_cloud_workflows.py) —
    Phase 70 Plan 02 (D-70-05/D-70-07): this is now what the settled execution's runData
    carries, recovered via the GET poll, never the webhook's synchronous POST body."""
    return [{
        "action": "create", "outcome": "created", "contact_id": hs_object_id,
        "hs_object_id": hs_object_id, "email": "josh@seriesfutsal.com",
        "company_id": "283816805830", "company_match": "domain",
        "association": "associated", "reason": None, "email_status": None,
    }]


def _poisoned_ingest_body():
    """A response item whose free-text `reason` contains a forbidden marker — the same
    shape `test_chunking.py`'s own `_poisoned_body()` uses to make
    `written_records.classify_item` raise `WrittenRecordsError`."""
    return [{"action": "write_blocked", "reason": "bad webhook_secret configured"}]


def test_a_contacts_write_is_named_in_the_written_records_artifact(
    sample_csv, fake_config, stub_transport, stub_get_transport_factory, tmp_path, monkeypatch
):
    """The mandated regression test (debug file 'Hard constraints' #1): drives the real
    contacts write path's own entry point, `dispatch.dispatch`, the way an operator's real
    send reaches it — not a unit boundary a documented sequence never actually calls."""
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)

    get_transport = _recovery_get_transport(stub_get_transport_factory, "r1", _ingest_response_body())
    result = dispatch(str(sample_csv), True, fake_config, transport=stub_transport,
                       run_id="r1", get_transport=get_transport,
                       now=lambda: 0.0, sleep=lambda seconds: None)

    assert result["recovered"] is True
    assert result["written_records_failures"] == []
    entries = written_records.load(path=artifact)
    assert len(entries) == 1
    assert entries[0]["hs_object_id"] == "348695309760"
    assert entries[0]["outcome"] == "written"
    assert entries[0]["action"] == "create"


def test_a_written_records_bookkeeping_failure_does_not_stop_the_contacts_dispatch(
    sample_csv, fake_config, stub_transport, stub_get_transport_factory, tmp_path, monkeypatch
):
    """D-59-10, mirrored: a bookkeeping failure (here, a `WrittenRecordsError` raised by a
    forbidden-looking response value) must never stop this dispatch — the caller still
    gets a real result back, and the failure is named, not swallowed."""
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)

    get_transport = _recovery_get_transport(stub_get_transport_factory, "r1", _poisoned_ingest_body())
    result = dispatch(str(sample_csv), True, fake_config, transport=stub_transport,
                       run_id="r1", get_transport=get_transport,
                       now=lambda: 0.0, sleep=lambda seconds: None)

    # D-70-07: the ack, never the poisoned row data — that lives at result["rows"] now,
    # recovered from runData.
    assert result["ack"] == {"status": "accepted"}
    assert len(result["written_records_failures"]) == 1
    assert result["written_records_failures"][0]["chunk_index"] == 0
    assert result["written_records_failures"][0]["reason"]


def test_an_io_failure_in_append_chunk_is_caught_by_the_same_guard(
    sample_csv, fake_config, stub_transport, stub_get_transport_factory, tmp_path, monkeypatch
):
    """The OTHER way the list can go short (`test_chunking.py`'s own Test 3 idiom):
    `append_chunk`'s documented falsey return on an `OSError`, driven directly rather than
    by inducing a real `OSError`, so this test cannot be confused with the
    raised-exception path above — one guard must catch both."""
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)
    import dispatch as dispatch_module
    monkeypatch.setattr(dispatch_module.written_records, "append_chunk", lambda *a, **k: False)

    get_transport = _recovery_get_transport(stub_get_transport_factory, "r1", _ingest_response_body())
    result = dispatch(str(sample_csv), True, fake_config, transport=stub_transport,
                       run_id="r1", get_transport=get_transport,
                       now=lambda: 0.0, sleep=lambda seconds: None)

    assert result["rows"][0]["action"] == "create"
    assert result["rows"][0]["hs_object_id"] == "348695309760"
    assert len(result["written_records_failures"]) == 1
    assert "I/O failure" in result["written_records_failures"][0]["reason"]


def test_run_id_defaults_to_a_fresh_generated_value_when_omitted(
    sample_csv, fake_config, stub_transport, stub_get_transport_factory, tmp_path, monkeypatch
):
    """Mirrors `chunking.dispatch_plan`'s own default: a caller that does not care which
    file this write lands in (a standalone contact-upload send) still gets one. The
    generated value is pinned via a `uuid4` monkeypatch so the recovery poll's own
    "Set Config" echo (D-70-05's correlation basis) can be scripted to match it exactly —
    dispatch() has no way to know what a caller never supplied ahead of time."""
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)
    import dispatch as dispatch_module

    class _FixedUUID:
        hex = "fresh-generated-run-id"

    monkeypatch.setattr(dispatch_module.uuid, "uuid4", lambda: _FixedUUID())

    get_transport = _recovery_get_transport(
        stub_get_transport_factory, "fresh-generated-run-id", _ingest_response_body())
    result = dispatch(str(sample_csv), True, fake_config, transport=stub_transport,
                       get_transport=get_transport, now=lambda: 0.0, sleep=lambda seconds: None)

    assert result["run_id"] == "fresh-generated-run-id"
    assert written_records.load(path=artifact)[0]["hs_object_id"] == "348695309760"
