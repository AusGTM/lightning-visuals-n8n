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

D-70-05/D-70-07 (Phase 70 Plan 02): the webhook now answers immediately with an ack —
`{run_id, accepted, row_ids}` — never a row-carrying body. Every row's real outcome is
read from the settled execution's runData, unconditionally (sync and async alike, never
gated behind an opt-in flag): after the POST, this function ALWAYS calls
`watch.recover_dispatch(..., lane="ingest")` and treats its recovered rows as the
dispatch's row data. `written_records.append_chunk` is fed those recovered rows, not the
ack. The ack is retained under `result["ack"]` for diagnostics only — `result["body"]`
stays an alias of the SAME ack value (never the row array) so an existing reader of
`result["body"]` degrades to "the ack" rather than crashing on a shape it no longer
carries; migrating those readers to `result["rows"]` is D-70-08's job, not this plan's.

Return shape: `{"body": <alias of "ack">, "ack": <the raw POST response>,
"rows": <recovered per-row list, reconciled via report.reconcile>,
"raw_rows": <the SAME recovery, before reconciliation>, "recovered": <bool>,
"run_id": <str>, "written_records_failures": [...]}`.

D-70-22 (Phase 70 Plan 12, G-70-4): `raw_rows` is exposed for instrument comparison
only — `scripts/prove_phase70_runtime.py`'s ingest branch reads it so it compares like
with like against the walker's raw prediction. `report.reconcile` stamps a
`reported_outcome` key onto every row under `rows`, which the walker's prediction never
produces; comparing the reconciled rows against a raw prediction fails on that stamped
key alone (execution 12207), not on anything the runtime did. `rows` stays the
operator-facing set every existing caller reads — this is an ADDITIVE key from the
SAME single recovery call, never a second poll (the plugin suite permits exactly one
poll site).
"""
import json
import uuid

import requests

import config_gate
import report
import tabular
import written_records

# `watch` is imported LAZILY inside `dispatch()`, not at module load time: `watch` ->
# `run_manifest` -> `held_queue` -> `enrichment` imports `DispatchError`/`NotArmedError`
# FROM this module, so a module-level `import watch` here would be a circular import
# (this module partially initialized, `enrichment` importing from it before it finishes
# loading). Deferring the import to call time breaks the cycle with no behaviour change
# — every module is fully loaded by the time `dispatch()` is actually invoked.


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
             source_by_field=None, get_transport=requests.get, now=None, sleep=None,
             bound_seconds=None):
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
    # D-70-05 (Phase 70 Plan 02): the caller's own client-minted `run_id`, sent as a
    # plain multipart form FIELD. "Set Config" (scripts/build_cloud_workflows.py) echoes
    # it back as its own output field; that echo is what the recovery poll below
    # correlates on.
    #
    # OBSERVED LIVE 2026-09-10 (Phase 70 UAT Gate 1, executions 12200 vs 12201): the
    # load-bearing fact is the ABSENT Content-Type, not `filename=None`. n8n's multipart
    # parser treats any part carrying a Content-Type header as a FILE — a 3-tuple
    # `(None, value, "text/plain")` landed in `$binary.run_id` with `$json.body == {}`,
    # so the echo was null and every recovery poll ran to its 600s bound. A 2-tuple
    # `(None, value)` makes `requests` omit the header and n8n parses it into
    # `$json.body.run_id`. Never add a content type to these two parts.
    files["run_id"] = (None, run_id)
    # Phase 62 Plan 04 (D-62-17, CLAUDE.md 13.0.2 idiom): describes the REQUEST, not a
    # row — write_dispatch_csv raises on any non-canonical row key, so a per-row
    # `origin` column cannot travel this channel. Same 2-tuple rule as `run_id` above:
    # no filename AND no Content-Type, or n8n files it under `$binary` and the
    # `Set Config Fields` envelope read never sees it (the 3-tuple form shipped by
    # Phase 62 was never observed live before 2026-09-10). Absent/empty leaves `files`
    # byte-identical to every existing caller (no `data=` kwarg added, no second
    # send-shaped function).
    if source_by_field:
        files["source_by_field"] = (None, json.dumps(source_by_field))

    try:
        response = transport(url, headers=headers, files=files, timeout=30)
    except Exception:
        raise DispatchError(
            "Could not reach the n8n webhook. Check the connection and try again, or "
            "ask an admin to check the n8n Cloud instance if this persists."
        ) from None

    try:
        ack = response.json()
    except Exception:
        ack = {
            "status_code": getattr(response, "status_code", None),
            "text": getattr(response, "text", None),
        }

    import watch  # lazy — see the module-level comment on the circular import above

    # D-70-05/D-70-06 (Phase 70 Plan 02): the ack carries no row outcome (D-70-07) —
    # every row's real outcome is read from the settled execution's runData,
    # UNCONDITIONALLY (never gated behind an opt-in flag: sync and async both go
    # through this same recovery call). `report.reconcile` is what makes an ingest
    # row's `action` reflect the write node's OWN output rather than the pre-write
    # decision "Build Ingest Response" reports — routed through here rather than a
    # second copy of that rule.
    recovery = watch.recover_dispatch(
        config, run_id, expected_chunk_count=1, lane="ingest",
        transport=get_transport, now=now, sleep=sleep, bound_seconds=bound_seconds,
    )
    recovered_rows = recovery.get("responses") or []
    run_data = recovery.get("run_data") or {}
    rows = report.reconcile(recovered_rows, run_data)

    # D-59-10, mirrored from chunking.py:394-407 verbatim: a written-records bookkeeping
    # failure never stops this dispatch — the real result is returned either way — and
    # never goes unreported either. `append_chunk` is documented to return a falsey
    # result on an OSError rather than raising (T-59-04) — checked below. It can ALSO
    # raise `WrittenRecordsError` for a shape or forbidden-name problem in the recovered
    # rows (a defect in the DATA, not the environment) — caught below. Guarding only one
    # of the two paths would repeat the exact live silent-short-artifact class D-59-10
    # names. Fed the RECOVERED rows (D-70-05), never the ack.
    written_records_failures = []
    try:
        flushed = written_records.append_chunk(run_id, 0, rows)
    except written_records.WrittenRecordsError as e:
        flushed = False
        bookkeeping_reason = str(e)
    else:
        bookkeeping_reason = None if flushed else _IO_FAILURE_REASON
    if not flushed:
        written_records_failures.append({"chunk_index": 0, "reason": bookkeeping_reason})

    return {
        # D-70-07: retained for diagnostics only — never a row-outcome source. Kept
        # under both names: "ack" is this plan's own vocabulary, "body" is the
        # pre-existing key every caller before this plan reads, so an unmigrated
        # caller degrades to seeing the ack rather than crashing on a missing key
        # (D-70-08 migrates callers off it; this is not a compatibility shim for the
        # RETIRED row-array shape, which no caller can get any more either way).
        "ack": ack,
        "body": ack,
        "rows": rows,
        # D-70-22 (Phase 70 Plan 12): the SAME recovery, before report.reconcile stamps
        # "reported_outcome" — instrument comparison only, never the operator-facing set.
        "raw_rows": recovered_rows,
        "recovered": bool(recovery.get("recovered")),
        # Phase 70 UAT (2026-09-10): the settled execution ids the rows were read from,
        # so a caller (scripts/prove_phase70_runtime.py) can cite them without a second
        # poll. `matched_executions` is a COUNT, not an id list.
        "execution_ids": list(recovery.get("execution_ids") or []),
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
