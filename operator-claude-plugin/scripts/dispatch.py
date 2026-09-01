"""operator-claude-plugin/scripts/dispatch.py

The only network call this plugin makes: a multipart POST to the deployed
`hubspot/contact-upload` webhook. `armed` has NO default — a caller that forgets it gets
a TypeError, never a silent send (D-11, D-13, T-23-01). Nothing about the grant is
persisted anywhere; it exists only as this call's argument.

written-records-misses-write (debug session, 2026-08-29): this is the contacts-ingest
WRITE path, and before this fix it never touched `written_records` at all —
`written_records.append_chunk`'s only call site was `chunking.dispatch_plan`'s loop, so a
run whose only write went through here (every `contact-upload` send, and
`enrich-before-ingest`'s own final ingest step) produced a `written_records-<run_id>.json`
artifact that omitted the write entirely, or — worse — reported `not_written` for it (walk
run 3, FINDING C, HubSpot contact 348695309760). Fixed by flushing HERE, at the write
site, mirroring `chunking.dispatch_plan`'s own D-59-07 inline-flush precedent
(`chunk_index=0` — this function sends exactly one request) and its D-59-10
catch/record/continue guard verbatim (chunking.py:394-407): a bookkeeping failure must
never stop this dispatch, and must never be silently swallowed either.

`run_id` is keyword-only, defaulting to a freshly generated one (`uuid.uuid4().hex`) —
the same default `chunking.dispatch_plan` gives itself. A caller that wants this write's
entry to land in the SAME file as an earlier `dispatch_plan` run in the same conversation
(`enrich-before-ingest`'s two-lane flow) passes that run's `outcome.run_id` through
explicitly; a standalone `contact-upload` send gets its own fresh file, same as any other
run.

Return shape is `{"body": <the raw response, exactly what this function returned before
this change>, "run_id": <str>, "written_records_failures": [...]}` rather than the bare
body — a bookkeeping failure has nowhere to be smuggled into a body that is sometimes a
bare list of row items, and D-59-10 requires it be surfaced, not swallowed. Every existing
consumer reads `result["body"]` in place of the old bare `result`.
"""
import json
import uuid

import requests

import config_gate
import tabular
import written_records


class NotArmedError(Exception):
    """Raised when dispatch is attempted without the operator's yes to this send."""


class DispatchError(Exception):
    """Raised when the transport itself fails. Never echoes the raw transport
    exception's text, which can carry request headers (T-23-09)."""


# Mirrors chunking.append_chunk's own I/O-failure wording (chunking.py:402) verbatim, so
# a reason string that names an I/O failure is greppable in one place across both
# transports.
_IO_FAILURE_REASON = "the written-records artifact could not be saved (an I/O failure)"


def dispatch(file_path, armed, config, transport=requests.post, *, run_id=None,
             source_by_field=None):
    # load_config() only enforces n8n_url (the universal minimum) — this is the guard
    # that stops a webhook_secret-less config from reaching the transmit path below
    # (mirrors review_queue.fetch_queue()'s require_capability call).
    config_gate.require_capability(config, "contact-upload")

    if not armed:
        raise NotArmedError(
            "Live writes are off for this send — nothing was sent. They turn on only "
            "when the operator says yes to the send just described, and that yes "
            "covers that one send."
        )

    if run_id is None:
        run_id = uuid.uuid4().hex

    csv_bytes = tabular.to_csv_bytes(file_path)
    url = config_gate.describe_target(config)
    headers = {"X-Enrichment-Secret": config["webhook_secret"]}
    files = {"data": ("contacts.csv", csv_bytes, "text/csv")}
    # Phase 62 Plan 04 (D-62-17, CLAUDE.md 13.0.2 idiom): describes the REQUEST, not a
    # row — write_dispatch_csv raises on any non-canonical row key, so a per-row
    # `origin` column cannot travel this channel. `filename=None` is load-bearing: it
    # makes `requests` emit a plain multipart form FIELD (no Content-Disposition
    # filename), which n8n's webhook parses into `$json.body.source_by_field` rather
    # than `$binary` — a filename would land it in binary instead, invisible to the
    # `Merge Contacts` node's envelope read. Absent/empty leaves `files` byte-identical
    # to every existing caller (no `data=` kwarg added, no second send-shaped function).
    if source_by_field:
        files["source_by_field"] = (None, json.dumps(source_by_field), "application/json")

    try:
        response = transport(url, headers=headers, files=files, timeout=30)
    except Exception:
        raise DispatchError(
            "Could not reach the n8n webhook. Check the connection and try again, or "
            "ask an admin to check the n8n Cloud instance if this persists."
        ) from None

    try:
        body = response.json()
    except Exception:
        body = {
            "status_code": getattr(response, "status_code", None),
            "text": getattr(response, "text", None),
        }

    # D-59-10, mirrored from chunking.py:394-407 verbatim: a written-records bookkeeping
    # failure never stops this dispatch — the real webhook response is returned either
    # way — and never goes unreported either. `append_chunk` is documented to return a
    # falsey result on an OSError rather than raising (T-59-04) — checked below. It can
    # ALSO raise `WrittenRecordsError` for a shape or forbidden-name problem in the
    # response body (a defect in the DATA, not the environment) — caught below. Guarding
    # only one of the two paths would repeat the exact live silent-short-artifact class
    # D-59-10 names.
    written_records_failures = []
    try:
        flushed = written_records.append_chunk(run_id, 0, body)
    except written_records.WrittenRecordsError as e:
        flushed = False
        bookkeeping_reason = str(e)
    else:
        bookkeeping_reason = None if flushed else _IO_FAILURE_REASON
    if not flushed:
        written_records_failures.append({"chunk_index": 0, "reason": bookkeeping_reason})

    return {
        "body": body,
        "run_id": run_id,
        "written_records_failures": written_records_failures,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3 or sys.argv[2] not in ("armed", "disarmed"):
        print(json.dumps({"ok": False, "error": "usage: dispatch.py <path> armed|disarmed"}))
        raise SystemExit(1)

    _file_path, _armed = sys.argv[1], sys.argv[2] == "armed"

    try:
        _cfg = config_gate.load_config()
    except config_gate.ConfigError as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    try:
        _result = dispatch(_file_path, _armed, _cfg)
    except (config_gate.ConfigError, NotArmedError, DispatchError,
            tabular.UnsupportedFileError, OSError) as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    # "response" stays the raw body — the documented CLI contract is unchanged — with
    # the new bookkeeping fields as siblings, not a replacement.
    print(json.dumps({
        "ok": True,
        "response": _result["body"],
        "run_id": _result["run_id"],
        "written_records_failures": _result["written_records_failures"],
    }))
