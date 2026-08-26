"""operator-claude-plugin/scripts/measure_dispatch.py

Phase 54 — a READ-ONLY measurement module. It counts how many n8n executions one record
actually cost, off live execution history, and compares that count against
`write_grant.envelope()`'s `projected_executions` figure for the same record set.

This module never arms anything, never dispatches, and never touches the write-safety
gate. It calls exactly two read-only `executions_client` functions (`list_executions`,
`get_execution`) and nothing from the arming module (T-54-01). WINDOWS.md id 26 names the
gap this closes: `envelope()`'s execution count has never been checked against a real
count.

V7 discipline, mirroring the arming module's own refusal contract: a read that fails
RAISES `executions_client.ExecutionsClientError` and is never caught into a return value.
A `count` this module could not establish is `None`, never `0` — a `0` here would be
indistinguishable from a genuinely empty window, and this system does not get to guess
which one happened.
"""
import sys
from datetime import datetime

import executions_client

MEASURED = "measured"
UNMEASURED = "unmeasured"


def _parse_started_at(value):
    """Own copy of the ISO-parse `executions_client._parse_started_at` uses internally —
    that name is module-private, so this module parses its own rather than reaching into
    another module's private symbol for a five-line function."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def executions_in_window(config, workflow_id, started_after, started_before,
                          transport=None, limit=100):
    """Executions for one workflow, newest-first, whose `startedAt` falls in the
    half-open window `[started_after, started_before)`.

    Copies `scheduled_arm.find_latest_sj3_batch`'s list + filter-on-`startedAt` +
    reverse-sort shape rather than re-deriving it — same client, same ordering
    discipline (n8n's list order is never assumed).

    Only calls `executions_client.list_executions` — no `get_execution`, no arming call.
    A transport failure raises `ExecutionsClientError` and is never caught here; the
    caller decides what an unreadable window means.
    """
    kwargs = {} if transport is None else {"transport": transport}
    candidates = executions_client.list_executions(
        config, workflow_id, limit=limit, **kwargs)

    windowed = []
    for candidate in candidates or []:
        if not isinstance(candidate, dict):
            continue
        started = _parse_started_at(candidate.get("startedAt"))
        if started is None:
            continue
        if started_after <= started < started_before:
            windowed.append(candidate)

    windowed.sort(key=lambda c: c["startedAt"], reverse=True)
    return windowed


def passes_for_record(executions, record_key):
    """How many of `executions` touched `record_key` (a `hs_object_id` or a domain).

    Matches against `hs_object_id`/`objectId`/`domain` wherever an execution's own list
    entry carries one (n8n's `/executions` list items do not always expose a per-record
    key — a caller with genuinely no visibility into which execution touched which record
    should pass every execution it already scoped to one record's time window and rely on
    the window itself as the match, not this function inventing a match it cannot see).

    Returns `{"count": int, "execution_ids": [...], "basis": "measured"}` on a normal
    (possibly zero) count. Returns `{"count": None, "execution_ids": [], "basis":
    "unmeasured", "reason": "<why>"}` when `executions` is `None` (the caller's own signal
    that the read never happened) — `count` is `None` for an unread window, never `0`.
    """
    if executions is None:
        return {"count": None, "execution_ids": [], "basis": UNMEASURED,
                "reason": "no execution list was read for this window"}

    dicts = [e for e in executions if isinstance(e, dict)]
    key = str(record_key or "").strip()

    def _record_keys(execution):
        return {str(execution.get(field) or "").strip()
                for field in ("hs_object_id", "objectId", "domain")} - {""}

    any_record_key_present = any(_record_keys(e) for e in dicts)

    if key and any_record_key_present:
        # Some executions in this window carry a per-record identifier — match on it
        # rather than assuming every execution in the window belongs to this record.
        matched = [e.get("id") for e in dicts if key in _record_keys(e)]
    else:
        # No execution in this window carries a per-record identifier — the common shape
        # for n8n's own `/executions` list, which never exposes a domain/id payload
        # field. The caller already scoped the WINDOW to this one record's known send;
        # every execution inside it is treated as a pass for that record, rather than
        # this function silently reporting zero for a window it cannot look inside.
        matched = [e.get("id") for e in dicts]

    return {"count": len(matched), "execution_ids": matched, "basis": MEASURED}


def compare_to_projection(measured, projection):
    """`measured` (a `passes_for_record` result) against `projection`
    (`write_grant.envelope(...)`'s figures dict for the same record set).

    Reads `projection["projected_executions"]` verbatim — never recomputes the formula,
    per this repo's "don't hand-roll" discipline (54-RESEARCH.md `Don't Hand-Roll`).
    """
    projected = (projection or {}).get("projected_executions")
    projected_basis = ((projection or {}).get("basis") or {}).get("projected_executions")
    measured_count = (measured or {}).get("count")

    if measured_count is None:
        verdict = "unmeasured"
        delta = None
    elif projected is None:
        verdict = "unmeasured"
        delta = None
    else:
        delta = measured_count - projected
        verdict = "matches" if delta == 0 else "differs"

    return {
        "measured_executions": measured_count,
        "projected_executions": projected,
        "projection_basis": projected_basis,
        "delta": delta,
        "verdict": verdict,
    }


def _parse_iso(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _cli_main(argv):
    if len(argv) != 5:
        print(
            "usage: measure_dispatch.py <workflow_id> <started_after ISO> "
            "<started_before ISO> <record_key>", file=sys.stderr)
        return 2

    _, workflow_id, started_after_raw, started_before_raw, record_key = argv

    import config_gate
    config = config_gate.load_config()

    started_after = _parse_iso(started_after_raw)
    started_before = _parse_iso(started_before_raw)

    executions = executions_in_window(config, workflow_id, started_after, started_before)
    result = passes_for_record(executions, record_key)

    print(f"record: {record_key}")
    print(f"window: {started_after.isoformat()} .. {started_before.isoformat()}")
    print(f"measured executions: {result['count']} (basis={result['basis']})"
          + (f" reason={result.get('reason')}" if result.get("reason") else ""))
    print(f"execution ids: {result['execution_ids']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main(sys.argv))
