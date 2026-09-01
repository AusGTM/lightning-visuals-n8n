"""Tests for tabular.py's read/convert behavior and dispatch.py's multipart POST.

Grouped in one file per plan 23-04's <files> list: tabular's CSV/XLSX handling feeds
directly into dispatch's multipart body, so the two are exercised together the same way
they're actually used. Every dispatch test uses `stub_transport`; the autouse
`no_network` fixture (conftest.py) is what makes an accidental real POST impossible.
"""
import csv
import inspect
import io
import json

import pytest

import config_gate
import tabular
import written_records
from dispatch import DispatchError, NotArmedError, dispatch


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
    sample_csv, fake_config, stub_transport
):
    result = dispatch(str(sample_csv), True, fake_config, transport=stub_transport)

    assert len(stub_transport.calls) == 1
    call = stub_transport.calls[0]
    assert call["url"] == "https://fake-tenant.n8n.cloud/webhook/hubspot/contact-upload"
    assert call["headers"]["X-Enrichment-Secret"] == fake_config["webhook_secret"]

    filename, body, content_type = call["files"]["data"]
    assert content_type == "text/csv"
    assert body == sample_csv.read_bytes()

    assert call["timeout"]
    assert call["timeout"] > 0
    # `dispatch()` no longer returns the raw body directly (written-records-misses-write,
    # 2026-08-29) — the bookkeeping outcome must be surfaced, never smuggled into a body
    # that is sometimes a bare list of row items. `result["body"]` is exactly what this
    # assertion checked before that change.
    assert result["body"] == {"status": "accepted"}
    assert result["written_records_failures"] == []
    assert result["run_id"]


def test_armed_dispatch_with_xlsx_source_sends_converted_csv_bytes(
    sample_xlsx, fake_config, stub_transport
):
    dispatch(str(sample_xlsx), True, fake_config, transport=stub_transport)
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
    sample_csv, fake_config, stub_transport
):
    """Phase 62 Plan 04 (D-62-17): the default (omitted/None) must leave every existing
    caller's `files` dict unchanged — no `source_by_field` key at all."""
    dispatch(str(sample_csv), True, fake_config, transport=stub_transport)
    call = stub_transport.calls[0]
    assert set(call["files"].keys()) == {"data"}


def test_dispatch_with_source_by_field_adds_exactly_one_extra_multipart_part_no_data_kwarg(
    sample_csv, fake_config, stub_transport
):
    """A non-empty map adds ONE more entry to the EXISTING `files` dict — never a `data=`
    kwarg on the transport call (that would be a second, form-encoded body)."""
    source_map = {"firstname": "claude_web", "email": "lusha"}
    dispatch(str(sample_csv), True, fake_config, transport=stub_transport,
              source_by_field=source_map)
    call = stub_transport.calls[0]
    assert set(call["files"].keys()) == {"data", "source_by_field"}
    assert "data" not in call, "no data= kwarg was added to the transport call"

    filename, body, content_type = call["files"]["source_by_field"]
    # filename=None is load-bearing: it is what makes requests emit a plain multipart
    # FORM FIELD rather than a file part, so n8n's webhook parses it into
    # $json.body.source_by_field instead of $binary.
    assert filename is None
    assert json.loads(body) == source_map
    assert content_type == "application/json"


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
    """One row in Build Ingest Response's own shape (scripts/build_cloud_workflows.py:
    471-520, repo root) — the contacts webhook's real synchronous body is a JSON array of
    exactly these keys."""
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
    sample_csv, fake_config, stub_post_transport_factory, tmp_path, monkeypatch
):
    """The mandated regression test (debug file 'Hard constraints' #1): drives the real
    contacts write path's own entry point, `dispatch.dispatch`, the way an operator's real
    send reaches it — not a unit boundary a documented sequence never actually calls."""
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)

    transport = stub_post_transport_factory([_ingest_response_body()])
    result = dispatch(str(sample_csv), True, fake_config, transport=transport, run_id="r1")

    assert result["written_records_failures"] == []
    entries = written_records.load(path=artifact)
    assert len(entries) == 1
    assert entries[0]["hs_object_id"] == "348695309760"
    assert entries[0]["outcome"] == "written"
    assert entries[0]["action"] == "create"


def test_a_written_records_bookkeeping_failure_does_not_stop_the_contacts_dispatch(
    sample_csv, fake_config, stub_post_transport_factory, tmp_path, monkeypatch
):
    """D-59-10, mirrored: a bookkeeping failure (here, a `WrittenRecordsError` raised by a
    forbidden-looking response value) must never stop this dispatch — the caller still
    gets the real webhook response back, and the failure is named, not swallowed."""
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)

    transport = stub_post_transport_factory([_poisoned_ingest_body()])
    result = dispatch(str(sample_csv), True, fake_config, transport=transport, run_id="r1")

    assert result["body"] == _poisoned_ingest_body()
    assert len(result["written_records_failures"]) == 1
    assert result["written_records_failures"][0]["chunk_index"] == 0
    assert result["written_records_failures"][0]["reason"]


def test_an_io_failure_in_append_chunk_is_caught_by_the_same_guard(
    sample_csv, fake_config, stub_post_transport_factory, tmp_path, monkeypatch
):
    """The OTHER way the list can go short (`test_chunking.py`'s own Test 3 idiom):
    `append_chunk`'s documented falsey return on an `OSError`, driven directly rather than
    by inducing a real `OSError`, so this test cannot be confused with the
    raised-exception path above — one guard must catch both."""
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)
    import dispatch as dispatch_module
    monkeypatch.setattr(dispatch_module.written_records, "append_chunk", lambda *a, **k: False)

    transport = stub_post_transport_factory([_ingest_response_body()])
    result = dispatch(str(sample_csv), True, fake_config, transport=transport, run_id="r1")

    assert result["body"] == _ingest_response_body()
    assert len(result["written_records_failures"]) == 1
    assert "I/O failure" in result["written_records_failures"][0]["reason"]


def test_run_id_defaults_to_a_fresh_generated_value_when_omitted(
    sample_csv, fake_config, stub_post_transport_factory, tmp_path, monkeypatch
):
    """Mirrors `chunking.dispatch_plan`'s own default: a caller that does not care which
    file this write lands in (a standalone contact-upload send) still gets one."""
    artifact = tmp_path / "written_records.json"
    monkeypatch.setattr(written_records, "written_records_path", lambda run_id: artifact)

    transport = stub_post_transport_factory([_ingest_response_body()])
    result = dispatch(str(sample_csv), True, fake_config, transport=transport)

    assert result["run_id"]
    assert written_records.load(path=artifact)[0]["hs_object_id"] == "348695309760"
