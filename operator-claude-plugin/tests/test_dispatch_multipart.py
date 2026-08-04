"""Tests for tabular.py's read/convert behavior and dispatch.py's multipart POST.

Grouped in one file per plan 23-04's <files> list: tabular's CSV/XLSX handling feeds
directly into dispatch's multipart body, so the two are exercised together the same way
they're actually used. Every dispatch test uses `stub_transport`; the autouse
`no_network` fixture (conftest.py) is what makes an accidental real POST impossible.
"""
import csv
import inspect
import io

import pytest

import config_gate
import tabular
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
    assert result == {"status": "accepted"}


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
