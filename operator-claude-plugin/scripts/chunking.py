"""operator-claude-plugin/scripts/chunking.py

The split and the sequence: one plan object that the preview renders and that dispatch
iterates, plus a sequential sender that skips a failing chunk and hands the failures back
as a batch Phase 26 can re-send rather than re-derive.

Four facts this module exists to honour:

1. THE CEILING IS READ FROM CONFIG, NEVER DEFAULTED (D-20). It is declared twice already
   — backend `ENRICH_MAX_LIST_RECORDS` and client `max_records_per_chunk`, pinned equal by
   `tests/test_chunk_ceiling_contract.py` — and a fallback constant here would be a third
   copy. Phase 25 has already shipped two copy-of-one-contract bugs. An absent key means
   the ceiling is UNCONFIGURED, which is an error, not a silent 2.
2. ONE PLAN, BUILT ONCE. The dispatcher has no splitting path of its own; it iterates what
   the operator approved. A preview whose plan is recomputed at send time is not a
   contract (PREVIEW-03, T-25-24).
3. A LIST IS ONE REQUEST WITH AN HONESTLY UNKNOWN COUNT (D-02). The client cannot count
   what the backend resolves, so the plan says `unknown` — the word — and the backend
   enforces its own bound by refusing (25-03, D-15a). There is no client-side list
   paginator here and there must not be one.
4. `armed` HAS NO DEFAULT and is threaded per call, never captured. A whole batch sent by
   a caller who forgot the flag is strictly worse than one record sent that way, and a
   captured flag outlives the decision that granted it.

Chunk size is a correctness property: the enrichment workflow has no batching node, so
every record in a POST runs the full provider + Haiku + Sonnet chain before the response
fires, against a ~100 s Cloudflare ceiling. A timeout is therefore a CHUNK FAILURE for the
skip rule (D-11b) — telling "the backend rejected it" from "the backend timed out while
still working" is Phase 26's job, and conflating them here would either duplicate work or
throw away the chunks that would have succeeded.
"""
import json
import uuid
from dataclasses import dataclass, field

import requests

import enrichment
import written_records
from dispatch import DispatchError, NotArmedError

CEILING_KEY = "max_records_per_chunk"

# The word, not a number and never zero. A count the client cannot read renders as this;
# a plan built on an unreadable input must not present as "0 chunks" or "nothing to do".
UNKNOWN = "unknown"


class ChunkPlanError(Exception):
    """Raised when a plan cannot be built: no ids, an unusable ceiling, or a
    specification that is neither record ids nor a list."""


@dataclass(frozen=True)
class ChunkPlan:
    """What the preview renders and what dispatch sends — the same object.

    `chunks` are record specifications in the exact shape `enrichment.build_envelope`
    already takes, so a chunk (and later a failed batch) is dispatched, not reconstructed.
    `record_count` and each entry of `row_counts` are ints, or `UNKNOWN` for a
    backend-resolved list.
    """

    chunks: tuple
    row_counts: tuple
    record_count: object

    @property
    def chunk_count(self):
        return len(self.chunks)


@dataclass(frozen=True)
class ChunkResult:
    """One chunk's outcome. Deliberately small and carries nothing from the config —
    a relayed transport exception's text can echo request headers (T-25-17)."""

    index: int
    rows: object
    ok: bool
    reason: str = None


@dataclass(frozen=True)
class DispatchOutcome:
    """`failed_batch` is None when nothing failed, so the caller branches on presence
    rather than on an empty container. When present it is a record specification the
    envelope builder accepts unmodified — that is the whole of D-13.

    `responses` is ONE RAW BODY PER CHUNK SENT, in chunk order — never one item per
    row. Each element is exactly what `enrichment.dispatch_enrichment` returned for
    that chunk: normally a JSON array (n8n's own `respondWith: allIncomingItems`
    behaviour, one item per row in that chunk) or, for a caller that still hands one
    row un-wrapped, a bare dict. A caller that needs a flat list of per-row response
    items — to index by `row_id`, for instance — must flatten this first:
    `[item for body in outcome.responses for item in (body if isinstance(body, list)
    else [body])]`. `preingest.rerequest_unanswered` does exactly this before calling
    `preingest.merge_enriched`. Passing `responses` straight through unflattened is
    the exact defect FINDING 2 (53-WALK-RECORD.md) recorded: it silently files every
    row as unanswered with no error.

    `run_id` is the id every chunk was flushed under, into D-59-07's durable
    "what got written" artifact — `written_records.written_records_path()`, keyed by
    this same id (see `written_records.py`'s own `append_chunk` for the flush)."""

    results: tuple
    failed_batch: dict = None
    responses: tuple = field(default_factory=tuple)
    run_id: str = None


def chunk_ceiling(config, key=CEILING_KEY):
    """The configured maximum records per POST for `key`. No fallback — see fact 1
    above. `key` defaults to the write-path ceiling (`CEILING_KEY`); passing
    `key="max_rows_per_match_request"` reads the match lane's own ceiling with the
    identical no-fallback refusal, naming that key in every message it raises rather
    than the module constant."""
    value = (config or {}).get(key)
    if value is None:
        raise ChunkPlanError(
            f"`{key}` is not set in the operator config, so I don't know how "
            f"many records one request may carry. Copy that key across from "
            f"config/operator.local.example.json — the ceiling is a timeout bound, not "
            f"a preference, so I won't guess one."
        )
    if isinstance(value, bool) or not isinstance(value, int):
        raise ChunkPlanError(
            f"`{key}` must be a whole number of records — got {value!r}."
        )
    if value < 1:
        raise ChunkPlanError(
            f"`{key}` is {value}, which would send nothing at all. It must be at "
            f"least 1."
        )
    return value


def plan_chunks(spec, ceiling):
    """Split a record specification into the ordered chunks dispatch will send.

    Pure: no I/O, no network, no config read. `ceiling` comes from `chunk_ceiling()`.
    """
    if not isinstance(spec, dict):
        raise ChunkPlanError(
            "A record specification must name record IDs, a list, or a view."
        )
    if spec.get("view"):
        raise enrichment.ViewNotSupportedError()

    if spec.get("list"):
        # One request. The backend resolves and counts it, and refuses rather than
        # truncating when it is oversize (D-15a) — so there is nothing to split and no
        # count to state.
        return ChunkPlan(chunks=(dict(spec),), row_counts=(UNKNOWN,), record_count=UNKNOWN)

    if not isinstance(ceiling, int) or isinstance(ceiling, bool) or ceiling < 1:
        raise ChunkPlanError(
            f"A chunk ceiling must be at least 1 record — got {ceiling!r}."
        )

    if "rows" in spec:
        rows = spec["rows"]
        if not isinstance(rows, (list, tuple)) or not rows:
            raise ChunkPlanError(
                "No rows were given, so there is nothing to match or enrich and "
                "nothing to plan. Provide at least one row."
            )
        object_type = spec.get("object_type")
        chunks = tuple(
            {"rows": list(rows[start:start + ceiling]), "object_type": object_type}
            for start in range(0, len(rows), ceiling)
        )
        return ChunkPlan(
            chunks=chunks,
            row_counts=tuple(len(chunk["rows"]) for chunk in chunks),
            record_count=len(rows),
        )

    if "people" in spec:
        people = spec["people"]
        if not isinstance(people, (list, tuple)) or not people:
            raise ChunkPlanError(
                "No people were given, so there is nothing to enrich and nothing to plan. "
                "Name at least one person."
            )
        chunks = tuple(
            {"people": list(people[start:start + ceiling])}
            for start in range(0, len(people), ceiling)
        )
        return ChunkPlan(
            chunks=chunks,
            row_counts=tuple(len(chunk["people"]) for chunk in chunks),
            record_count=len(people),
        )

    if "companies" in spec:
        # 2026-08-25: companies that may not be in HubSpot yet. Chunked exactly like a
        # rows batch — the backend matches each on `domain` and creates only what it
        # cannot find, so a chunk boundary changes nothing about the outcome.
        companies = spec["companies"]
        if not isinstance(companies, (list, tuple)) or not companies:
            raise ChunkPlanError(
                "No companies were given, so there is nothing to enrich and nothing to "
                "plan. Name at least one company with its website domain."
            )
        chunks = tuple(
            {"companies": list(companies[start:start + ceiling])}
            for start in range(0, len(companies), ceiling)
        )
        return ChunkPlan(
            chunks=chunks,
            row_counts=tuple(len(chunk["companies"]) for chunk in chunks),
            record_count=len(companies),
        )

    record_ids = spec.get("record_ids")
    if not isinstance(record_ids, (list, tuple)) or not record_ids:
        raise ChunkPlanError(
            "No record IDs were given, so there is nothing to enrich and nothing to "
            "plan. Paste the record IDs, or name a HubSpot list."
        )

    object_type = spec.get("object_type")
    chunks = tuple(
        {"record_ids": list(record_ids[start:start + ceiling]), "object_type": object_type}
        for start in range(0, len(record_ids), ceiling)
    )
    return ChunkPlan(
        chunks=chunks,
        row_counts=tuple(len(chunk["record_ids"]) for chunk in chunks),
        record_count=len(record_ids),
    )


class _StatusCapturingTransport:
    """Wraps the caller's transport to observe the response `dispatch_enrichment` has
    already consumed.

    `dispatch_enrichment` returns a parsed body on success and a `{status_code, text}`
    shim on an unparseable one, so a non-2xx carrying a readable JSON body is otherwise
    indistinguishable from a success — a clean-looking result for a request the backend
    refused. That is the exact failure shape this phase keeps hitting, so the status and
    the parseability are captured here rather than inferred from the return value.
    """

    def __init__(self, inner):
        self._inner = inner
        self.status_code = None
        self.parseable = None

    def post(self, *args, **kwargs):
        response = self._inner.post(*args, **kwargs)
        self.status_code = getattr(response, "status_code", None)
        try:
            response.json()
            self.parseable = True
        except Exception:
            self.parseable = False
        return response


def _failure_reason(watcher):
    """Why this chunk failed, or None if it did not. Short, and free of config values."""
    status = watcher.status_code
    if status is not None and not 200 <= status < 300:
        return f"the backend returned HTTP {status}"
    if watcher.parseable is False:
        return "the backend's response was not readable"
    return None


def dispatch_plan(plan, providers, armed, config, transport=requests, *, run_id=None):
    """Send every chunk of an approved plan, in plan order, one at a time.

    `armed` has NO default and is passed to each `dispatch_enrichment` call rather than
    captured. A disarmed call raises before any chunk is sent.

    A failing chunk is recorded and the run continues (D-12). Failure is defined in ONE
    place: an unsuccessful status, a transport exception including a timeout (D-11b), or
    an unreadable body where a readable one was expected.

    `run_id` names the D-59-07 written-records artifact this run flushes into, per
    chunk (see `written_records.py`). Keyword-only so an existing positional caller is
    unaffected; when omitted, one is generated (`uuid.uuid4().hex`) so every dispatch
    still gets the artifact without every call site naming a run of its own. This
    function stays deliberately GRANT-UNAWARE — no per-chunk revocation hook is added
    here (D-59-06/GRANT-05: revocation bites on the next send, not mid-run; see
    `test_dispatch_plan_has_no_grant_aware_hook_to_revoke_against`).
    """
    if run_id is None:
        run_id = uuid.uuid4().hex

    results = []
    responses = []
    failed_chunks = []

    for index, chunk in enumerate(plan.chunks):
        rows = plan.row_counts[index]
        watcher = _StatusCapturingTransport(transport)
        try:
            envelope = enrichment.build_envelope(chunk, providers)
            body = enrichment.dispatch_enrichment(envelope, armed, config, transport=watcher)
        except NotArmedError:
            # Not a chunk failure — nothing was sent and nothing should be. Let it out.
            raise
        except DispatchError:
            reason = "the request did not reach the enrichment webhook (a timeout counts here)"
            results.append(ChunkResult(index=index, rows=rows, ok=False, reason=reason))
            failed_chunks.append(chunk)
            continue
        except enrichment.RecordSpecError:
            results.append(ChunkResult(
                index=index, rows=rows, ok=False,
                reason="this chunk could not be turned into a request",
            ))
            failed_chunks.append(chunk)
            continue

        reason = _failure_reason(watcher)
        results.append(
            ChunkResult(index=index, rows=rows, ok=reason is None, reason=reason)
        )
        responses.append(body)
        # D-59-07: flushed INLINE, immediately after the line above, never assembled
        # after the loop. `DispatchOutcome` is built in one statement once the
        # loop completes, so a crash of the calling process between this chunk and the
        # next would lose everything the loop had accumulated if this call moved out of
        # the loop — that is the exact partial-run guarantee this artifact exists for.
        # `append_chunk` never raises on an I/O failure (T-59-04): a bookkeeping miss
        # must never become a mid-run stop.
        written_records.append_chunk(run_id, index, body)
        if reason is not None:
            failed_chunks.append(chunk)

    return DispatchOutcome(
        results=tuple(results),
        failed_batch=failed_batch(failed_chunks),
        responses=tuple(responses),
        run_id=run_id,
    )


def failed_batch(chunks):
    """The failed chunks as ONE record specification, or None when nothing failed.

    Ids keep their original order and no id from a successful chunk appears. The result
    is already a well-formed enrichment request by construction, so Phase 26 re-sends it
    through the same armed dispatch path rather than parsing it out of log lines (D-13).
    """
    if not chunks:
        return None
    if len(chunks) == 1 and chunks[0].get("list"):
        return dict(chunks[0])

    if "rows" in chunks[0]:
        rows = [row for chunk in chunks for row in chunk.get("rows", [])]
        if not rows:
            return dict(chunks[0])
        return {"rows": rows, "object_type": chunks[0].get("object_type")}

    record_ids = [
        record_id for chunk in chunks for record_id in chunk.get("record_ids", [])
    ]
    if not record_ids:
        return dict(chunks[0])
    return {"record_ids": record_ids, "object_type": chunks[0].get("object_type")}


if __name__ == "__main__":
    import sys

    import config_gate

    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "error": "usage: chunking.py <spec-json>"}))
        raise SystemExit(1)

    try:
        _spec = json.loads(sys.argv[1])
        _cfg = config_gate.load_config()
        _plan = plan_chunks(_spec, chunk_ceiling(_cfg))
    except (json.JSONDecodeError, config_gate.ConfigError, ChunkPlanError,
            enrichment.RecordSpecError) as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    print(json.dumps({
        "ok": True,
        "chunk_count": _plan.chunk_count,
        "row_counts": list(_plan.row_counts),
        "record_count": _plan.record_count,
        "chunks": list(_plan.chunks),
    }))
