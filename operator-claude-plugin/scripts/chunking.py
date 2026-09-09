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

5. (RETIRED 2026-09-10, Phase 70 Plan 03 Task 2, D-70-07.) A WRITTEN-RECORDS
   BOOKKEEPING FAILURE NEVER STOPS THE DISPATCH used to describe a `written_records.
   append_chunk` flush inside `dispatch_plan`'s own loop (D-59-10, operator,
   2026-08-29). That flush is DELETED WHOLE, not merely guarded further: the
   server-side change that makes `Build Ack` the workflow's ONLY responder input means
   this call's own synchronous `body` is ALWAYS just `{run_id, accepted, row_ids}`, for
   every request — never a real per-row outcome — so trusting it for written-records
   bookkeeping would be wrong on every call, not an edge case to guard. `dispatch_plan`
   no longer touches `written_records` at all; `DispatchOutcome.written_records_
   failures` stays on the dataclass for shape compatibility but is now always an empty
   tuple. A caller's real outcome is recovered from runData via `watch.recover_dispatch`,
   keyed on `run_id`. Left as a KNOWN, DEFERRED gap by this change: `run_report.py`'s
   end-of-run report currently reads `written_records.load()` for entries this function
   used to write — migrating it to runData is D-70-08's scope, not this one's.
"""
import json
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path

import requests

import enrichment
import remainder_queue
import report
import run_manifest
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
    a relayed transport exception's text can echo request headers (T-25-17).

    `resolvable` (D-59-08, 59-07 gap closure) is the one exception to "carries
    nothing beyond a bare reason": it mirrors `enrichment.RecordSpecError.resolvable`
    verbatim, defaulting to an empty tuple so a caller iterates it unconditionally on
    every result including successes. This is NOT a widening of T-25-17's rule —
    `RecordSpecError` is raised by `enrichment.build_envelope` BEFORE any request is
    built, and every GATE-02..GATE-05 message and resolvable entry is composed from
    the operator's own record spec, never from a transport response, an HTTP status,
    or a config value. Transport-sourced text (`DispatchError`'s fixed reason string,
    below) stays excluded exactly as T-25-17 requires; spec-sourced refusal text is
    admitted because it cannot carry a header, a webhook secret, or a config value —
    there is nothing of that shape to leak this early in the call."""

    index: int
    rows: object
    ok: bool
    reason: str = None
    resolvable: tuple = ()
    # D-70-09 (Phase 70 Plan 06): whether THIS chunk's leg can write at all, decided by
    # the very object that decides the mode — the built envelope — rather than by a
    # second reading of the spec somewhere downstream. `written_records` exists to
    # record WRITES; a propose / match / enrich-proposal leg sends nothing that can
    # write, so it must never enter the ledger, or the end-of-run report can label a
    # row that was never sent (the `None -> failed` shape observed live on run
    # `2bc3617b`). `None` means "not decided" — the chunk never reached envelope build.
    can_write: bool = None


@dataclass(frozen=True)
class CeilingStop:
    """A deliberate budget stop inside `dispatch_plan` (Phase 57, D-57-01). Categorically
    NOT a recovered-from failure — mirroring `DispatchOutcome.written_records_failures`'
    own D-59-10 precedent for a separate field on purpose: a budget stop must never flip
    a `ChunkResult.ok`, never add a chunk to `failed_chunks`, and never appear in
    `failed_batch` (Pitfall 5).

    `chunk_index` is the index of the chunk that was NOT sent — the first one that would
    have taken the running projected spend strictly above `execution_ceiling` — never the
    index of the last chunk that WAS sent. `unsent_chunks` is every remaining chunk from
    that index onward, in plan order. `remainder` is those chunks as ONE record
    specification (`chunking.failed_batch`'s own shape), ready to re-send under a fresh
    grant without being parsed out of a report. `reason` is a short, config-value-free
    sentence naming the ceiling and the projection that would have breached it.
    """

    chunk_index: int
    projected_executions: int
    execution_ceiling: int
    unsent_chunks: tuple
    remainder: object
    reason: str


@dataclass(frozen=True)
class DispatchOutcome:
    """`failed_batch` is None when nothing failed, so the caller branches on presence
    rather than on an empty container. When present it is a record specification the
    envelope builder accepts unmodified — that is the whole of D-13.

    `responses` IS ONE ACK PER CHUNK SENT, in chunk order — NOT a row outcome, and no
    longer a row outcome for ANY mode (D-70-05/D-70-07, Phase 70 Plan 06). `Build Ack`
    is the workflow's only responder input now, so each element is
    `{run_id, accepted, row_ids}` — the backend confirming it took the request, nothing
    about what it then decided. It is kept because a run that could not even be accepted
    is worth seeing, and because `_failure_reason` reads the STATUS around it.

    A CALLER THAT WANTS ROWS CALLS `dispatch_and_recover`, which reads them from the
    settled execution's runData correlated on `run_id`. Reading `responses` for a row
    outcome does not raise — it quietly reports nothing while sounding complete, which
    is exactly the shape FINDING 2 (53-WALK-RECORD.md) recorded when a caller passed
    this field on unflattened, and exactly the shape F4
    (uat-batch-review-row-reads-failed) proved live for the async case before the ack
    became universal.

    `run_id` is this run's own client-minted correlation handle: it rides every chunk's
    envelope, the backend echoes it on every event, and it is BOTH what
    `watch.recover_dispatch` correlates the settled execution on AND the id D-59-07's
    durable "what got written" artifact is filed under. Under D-59-09 each run flushes
    into its OWN file —
    `written_records.written_records_path(run_id)` — rather than a path shared across
    runs (see `written_records.py`'s own `append_chunk` for the flush).

    `written_records_failures` (D-59-10, 59-09 gap closure) names every chunk whose
    written-records bookkeeping failed — a raised `WrittenRecordsError` OR a falsey
    `append_chunk` return (its documented degrade on an `OSError`), one guard in the
    loop below catches both. Default is an empty tuple, NEVER `None`, so a caller
    iterates it unconditionally exactly like `responses` and `ChunkResult.resolvable`
    above. It is a SEPARATE field from `results` on purpose: by the time
    `append_chunk` runs, the chunk's own `ChunkResult` is already built and appended —
    frozen — and a bookkeeping miss is categorically NOT a dispatch failure (the
    HubSpot write for that chunk may already have landed), so it must never flip
    `ChunkResult.ok` or add the chunk to `failed_batch` for re-send. Each entry is
    `{"chunk_index": int, "reason": str}`. A non-empty tuple here means the run
    completed with an INCOMPLETE written-records list — D-59-10's named trade-off for
    never stopping the dispatch on this class of failure — and this field is the first
    of the four surfaces that must say so loudly (`scheduled_arm.py`'s outcome and
    exit code, and both skills' relay, are the other three).

    `ceiling_stop` (Phase 57, D-57-01): a `CeilingStop` when `dispatch_plan`'s running
    tally stopped BEFORE sending a chunk that would breach `execution_ceiling`, else
    `None`. Defaulting to `None` means every existing caller branches on presence exactly
    as it already does for `failed_batch`, and a call with no `execution_ceiling` (the
    byte-identical default) can never produce one. See `CeilingStop`'s own docstring for
    why this is a separate field from `failed_batch`/`ChunkResult.ok` rather than folded
    into either."""

    results: tuple
    failed_batch: dict = None
    responses: tuple = field(default_factory=tuple)
    run_id: str = None
    written_records_failures: tuple = field(default_factory=tuple)
    ceiling_stop: CeilingStop = None


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
        # [Rule 1 - Bug] `propose` was DROPPED here (found Phase 70 Plan 06 Task 2):
        # `enrichment.build_envelope` reads it off the spec to stamp `mode: "propose"`
        # request-level AND per-event, so a chunked enrich-proposal request arrived at
        # the backend as a WRITE — `isReturnOnly()` false, the write-safety gate the
        # only thing left between it and HubSpot. Carried per chunk, and only when set,
        # so a plain companies plan's chunk shape is byte-identical to today's.
        chunks = tuple(
            {"companies": list(companies[start:start + ceiling]),
             **({"propose": True} if spec.get("propose") else {})}
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


WRITE_MODE = "write"


def envelope_can_write(envelope) -> bool:
    """Can this envelope's leg write to HubSpot at all? (D-70-09, Phase 70 Plan 06.)

    Read off the BUILT envelope, never re-derived from the spec: `enrichment.
    build_envelope` is the one place that decides a leg's mode (structurally — a
    `rows`/`people` form pins `mode: "propose"` inside its own branch and never reads a
    mode from the caller), so asking the envelope is asking the decision itself. A
    second reading of the spec here is exactly the two-computations-that-agree-today
    shape this plan exists to remove.

    Mirrors the backend's own `isReturnOnly()` rule (CLAUDE.md 13.0/13.0.2): ANY mode
    other than `"write"` is return-only. Checked at request level AND per event, because
    the companies `propose` form stamps `mode` on both.
    """
    envelope = envelope if isinstance(envelope, dict) else {}
    if envelope.get("mode") not in (None, WRITE_MODE):
        return False
    for event in envelope.get("events") or []:
        if isinstance(event, dict) and event.get("mode") not in (None, WRITE_MODE):
            return False
    return True


def dispatch_plan(plan, providers, armed, config, transport=requests, *, run_id=None,
                   scale_up=False, execution_ceiling=None, **_ignored_legacy_kwargs):
    """Send every chunk of an approved plan, in plan order, one at a time.

    `armed` has NO default and is passed to each `dispatch_enrichment` call rather than
    captured. A disarmed call raises before any chunk is sent.

    A failing chunk is recorded and the run continues (D-12). Failure is defined in ONE
    place: an unsuccessful status, a transport exception including a timeout (D-11b), or
    an unreadable body where a readable one was expected.

    `run_id` (Phase 61 Plan 05 Task 2; generalised Phase 70 Plan 03 Task 2, D-70-07) is
    the caller's own client-minted handle. It ALWAYS rides the envelope now — the
    backend reads it unconditionally (`Parse HubSpot Event`) and every leg's rows are
    recovered from runData by this id (`watch.recover_dispatch`, landed 70-02), not from
    this call's own synchronous response. Keyword-only so an existing positional caller
    is unaffected; when omitted, one is generated (`uuid.uuid4().hex`) so every dispatch
    still gets a correlatable id without every call site naming a run of its own. This
    function stays deliberately GRANT-UNAWARE — no per-chunk revocation hook is added
    here (D-59-06/GRANT-05: revocation bites on the next send, not mid-run; see
    `test_dispatch_plan_has_no_grant_aware_hook_to_revoke_against`). A BUDGET stop is a
    different kind of early exit from a revocation, and the two must not be confused:
    it consults a plain number (`execution_ceiling`) it is handed, never a grant object,
    and the grant-close it enables happens in the CALLER, through
    `write_grant.record_dispatch_outcome` — never here.

    `**_ignored_legacy_kwargs` (Phase 70 Plan 03 Task 2, D-70-07): the retired early-ack
    opt-in this function used to accept (and any other stale keyword a caller has not
    yet stopped passing) is swallowed here rather than rejected — "a caller that still
    passes it is ignored, not rejected", so a stale caller degrades to the new
    behaviour instead of erroring on a `TypeError`.

    `execution_ceiling` (Phase 57, D-57-01), keyword-only, defaults to `None`: today's
    behaviour, byte-identical envelope, byte-identical `DispatchOutcome` with
    `ceiling_stop` always `None`. When an int, a running tally — computed at the TOP of
    each loop iteration, BEFORE `enrichment.build_envelope` or any transport call for
    that chunk — projects what this run's total spend would become if this chunk were
    sent (the same `chunk_count + record_count` formula `write_grant.EXECUTIONS_BASIS`
    and `run_state.spend_against_ceiling` already use, never re-derived). When that
    projection would take the running total STRICTLY ABOVE the ceiling, the loop stops
    BEFORE that chunk is built or sent — the breaching chunk is never dispatched — and a
    `CeilingStop` is attached to the returned `DispatchOutcome`. Consuming the EXACT
    remaining allowance is legitimate; the stop fires only on strictly-over, never on
    equal. The one shape this cannot bound: a backend-resolved list spec
    (`plan.row_counts[index] is chunking.UNKNOWN`) is always a single chunk by
    construction, so there is nothing mid-run to stop — the tally is skipped for it and
    `ceiling_stop` stays `None`; that one shape is genuinely unbounded by this mechanism,
    not silently guessed at.

    `scale_up` (Phase 61 Plan 06 Task 5, T-61-25, substrate-3 of 61-SPIKE-VERDICT.md — see
    `scripts/build_cloud_workflows.py`'s `SCALE_UP_MAX_FAN_DEPTH`/`ENRICH_BUILD_SCALE_UP_
    FAN_OUT` for the n8n-side mechanism): keyword-only, defaults to `False`, so every
    existing caller sends the byte-identical envelope it sends today. When `True`, rides
    the envelope as `scale_up: true` — the SAME opt-in-flag idiom `recompute` already
    established, "a pattern, not an invention." THERE IS NO `fan_depth` PARAMETER HERE,
    DELIBERATELY: the depth bound this feature's safety rests on (T-61-25) is a
    workflow-internal counter this workflow's OWN "Build Scale Up Fan-Out" node owns
    and increments — the client has no knob to request a depth, and cannot ask for one,
    structurally (see
    `test_scale_up_runtime.py::test_dispatch_plan_has_no_depth_parameter_to_forge`).

    D-70-07 (Phase 70 Plan 03 Task 2): this function no longer flushes `body` into
    `written_records` at all — the sync-body-trusting branch it used to take, skipped
    only for an opted-in early-ack request, is DELETED whole, because the server-side
    change that retired that opt-in (`Build Ack` is now the workflow's ONLY responder
    input, unconditionally) means `body` is ALWAYS just `{run_id, accepted, row_ids}`
    for EVERY call, never a real per-row outcome — the exact bogus-entry failure mode
    F4 (uat-batch-review-row-reads-failed, gap-closure 2026-09-09) already proved live
    for the async case is now universal, so the guard that used to skip it there now
    always applies. `written_records_failures` stays on `DispatchOutcome` for shape
    compatibility but is now always an empty tuple — no consumer's field goes missing,
    it simply never has anything to report. A caller's real outcome is recovered
    separately via `watch.recover_dispatch`, keyed on `run_id`, never through this
    artifact. `run_report.py`'s end-of-run report, which currently reads
    `written_records.load()` for entries THIS function used to write, is a KNOWN,
    DEFERRED gap this change opens — migrating it to read runData instead is D-70-08's
    scope, not this plan's; recorded in 70-03-SUMMARY.md, not silently papered over here.
    """
    # D-70-10 (Phase 70 Plan 06): BEFORE the first chunk is built or sent. runData is
    # the only channel a row's outcome can come back on, so a config that cannot read
    # the executions API cannot report on this send — refuse before the money is spent,
    # never fall back to a time-proximity guess. Lazy import: `watch` -> `scheduled_arm`
    # -> this module, so a module-level import would be circular.
    import watch as _watch
    _watch.require_executions_api(config)

    if run_id is None:
        run_id = uuid.uuid4().hex

    results = []
    responses = []
    failed_chunks = []
    written_records_failures = []
    ceiling_stop = None

    for index, chunk in enumerate(plan.chunks):
        rows = plan.row_counts[index]

        # THE TALLY, PRE-SEND (Phase 57, D-57-01, REVIEW-57-H2 — this placement is the
        # whole point). First statement of the loop body: before `_StatusCapturingTransport`,
        # before `enrichment.build_envelope`, before anything can be sent for THIS chunk.
        # `plan.row_counts[:index]` are the chunks ALREADY sent (never this one); `rows`
        # is this chunk's own count. Skipped entirely for a backend-resolved list spec
        # (`rows is UNKNOWN`) — that plan is always one chunk, so there is nothing mid-run
        # to stop.
        if execution_ceiling is not None and isinstance(rows, int):
            sent_rows = sum(r for r in plan.row_counts[:index] if isinstance(r, int))
            would_be = (index + 1) + sent_rows + rows
            if would_be > execution_ceiling:
                unsent = tuple(plan.chunks[index:])
                ceiling_stop = CeilingStop(
                    chunk_index=index,
                    projected_executions=would_be,
                    execution_ceiling=execution_ceiling,
                    unsent_chunks=unsent,
                    remainder=failed_batch(list(unsent)),
                    reason=(
                        f"sending chunk {index} would take this run's projected spend to "
                        f"{would_be} execution(s), over the {execution_ceiling}-execution "
                        f"ceiling — stopped before that chunk was built or sent."),
                )

                # D-57-01: the unsent remainder gets a durable, re-sendable home before
                # this run returns. Mirrors the `written_records.append_chunk` guard
                # immediately below (D-59-10's degrade-rather-than-halt rule, applied to
                # a second bookkeeping store): a `RemainderQueueError` or a falsey save
                # must never raise out of the dispatch and must never alter any other
                # field of the returned `DispatchOutcome` — only `CeilingStop.reason`
                # gains a sentence naming the bookkeeping miss, so it is not silent.
                try:
                    entry = remainder_queue.build_entry(
                        ceiling_stop.remainder, remainder_queue.REASON_CEILING_BREACH,
                        note=f"stopped before chunk {index}",
                    )
                    saved = remainder_queue.save(run_id, [entry])
                except remainder_queue.RemainderQueueError as e:
                    saved = False
                    save_failure_reason = str(e)
                else:
                    save_failure_reason = (
                        None if saved
                        else "the remainder queue could not be saved (an I/O failure)")
                if not saved:
                    ceiling_stop = replace(
                        ceiling_stop,
                        reason=(
                            f"{ceiling_stop.reason} The unsent remainder could not be "
                            f"saved to the remainder queue: {save_failure_reason}"),
                    )
                break

        watcher = _StatusCapturingTransport(transport)
        try:
            envelope = enrichment.build_envelope(chunk, providers)
            chunk_can_write = envelope_can_write(envelope)
            # D-70-07: always rides the envelope now — the server reads it
            # unconditionally, and every leg's rows are recovered from runData by this
            # id, not from this call's own synchronous response.
            envelope["run_id"] = run_id
            if scale_up:
                envelope["scale_up"] = True
            body = enrichment.dispatch_enrichment(envelope, armed, config, transport=watcher)
        except NotArmedError:
            # Not a chunk failure — nothing was sent and nothing should be. Let it out.
            raise
        except DispatchError:
            reason = "the request did not reach the enrichment webhook (a timeout counts here)"
            results.append(ChunkResult(index=index, rows=rows, ok=False, reason=reason))
            failed_chunks.append(chunk)
            continue
        except enrichment.RecordSpecError as e:
            # D-59-08 / 59-07 gap closure: the gate's own message and its resolvable
            # tuple, never a generic placeholder. A RecordSpecError always carries a
            # message the gate wrote, which is strictly better than one this module
            # would invent — so there is no fallback branch for an empty resolvable.
            results.append(ChunkResult(
                index=index, rows=rows, ok=False,
                reason=str(e), resolvable=getattr(e, "resolvable", ()),
            ))
            failed_chunks.append(chunk)
            continue

        reason = _failure_reason(watcher)
        results.append(
            ChunkResult(index=index, rows=rows, ok=reason is None, reason=reason,
                        can_write=chunk_can_write)
        )
        responses.append(body)
        # D-70-07 (Phase 70 Plan 03 Task 2): the `written_records.append_chunk` flush
        # that used to run here is DELETED — see this function's own docstring for why
        # `body` can never carry a real per-row outcome anymore, for ANY call. Nothing
        # is appended to `written_records_failures` either; it stays an always-empty
        # tuple below, for `DispatchOutcome` shape compatibility only.
        if reason is not None:
            failed_chunks.append(chunk)

    return DispatchOutcome(
        results=tuple(results),
        failed_batch=failed_batch(failed_chunks),
        responses=tuple(responses),
        run_id=run_id,
        written_records_failures=tuple(written_records_failures),
        ceiling_stop=ceiling_stop,
    )


def dispatch_and_recover(plan, providers, armed, config, transport=requests, *,
                          run_id=None, lane="enrichment", get_transport=None,
                          now=None, sleep=None, bound_seconds=None, workflow_id=None,
                          **dispatch_kwargs) -> dict:
    """Send an approved plan and read its rows back from the settled execution — the
    ONE dispatch-and-recover cycle, used by every mode (D-70-05, Phase 70 Plan 06).

    Before this, `dispatch_plan` returned acks and each caller decided for itself
    whether to believe the body or go to runData; that per-mode choice IS the second
    result channel this phase removes. There is no channel selection here: the POST's
    response is an ack (`{run_id, accepted, row_ids}`) and is never read for a row
    outcome, and every row comes from `watch.recover_dispatch`, correlated on this
    run's own client-minted `run_id` — never on time proximity (D-70-10).

    NO SECOND POLL SITE: the wait lives entirely inside `watch.recover_dispatch`, which
    `tests/test_report_sufficiency.py` permits as the plugin's only one. This function
    adds no `while`, no `sleep` and no `time` of its own.

    THE LEDGER GATE (D-70-09) lives here, at the call site, not inside
    `written_records.append_chunk`: restricting WHO calls it is smaller and more durable
    than teaching the ledger a new outcome. A leg whose envelope cannot write (propose,
    match, enrich-proposal) is never appended, so the end-of-run report cannot label a
    row that was never sent; those rows reach the operator through the enrichment
    outcome instead. A write leg is appended exactly as before, fed the RECOVERED rows.

    Returns `{"outcome": DispatchOutcome, "rows": [...], "recovered": bool,
    "run_id": str, "can_write": bool, "run_data": {...},
    "written_records_failures": [...]}`.
    """
    import watch as _watch  # lazy — see dispatch_plan's own note on the import cycle

    outcome = dispatch_plan(plan, providers, armed, config, transport=transport,
                            run_id=run_id, **dispatch_kwargs)

    recovery_kwargs = {"transport": get_transport} if get_transport is not None else {}
    if workflow_id is not None:
        recovery_kwargs["workflow_id"] = workflow_id
    recovery = _watch.recover_dispatch(
        config, outcome.run_id, expected_chunk_count=len(outcome.results) or 1,
        lane=lane, now=now, sleep=sleep, bound_seconds=bound_seconds, **recovery_kwargs)

    rows = recovery.get("responses") or []
    run_data = recovery.get("run_data") or {}
    # `report.reconcile` is what makes a row's `action` reflect the write node's OWN
    # output rather than the pre-write intent `Build Response` reports (Pitfall 3) —
    # routed through the SAME function `dispatch.dispatch` already uses for the ingest
    # lane, never a second copy of that rule.
    rows = report.reconcile(rows, run_data)

    can_write = any(r.can_write for r in outcome.results)

    written_records_failures = []
    if can_write and rows:
        try:
            flushed = written_records.append_chunk(outcome.run_id, 0, rows)
        except written_records.WrittenRecordsError as e:
            flushed = False
            bookkeeping_reason = str(e)
        else:
            bookkeeping_reason = (
                None if flushed
                else "the written-records artifact could not be saved (an I/O failure)")
        if not flushed:
            written_records_failures.append({"chunk_index": 0,
                                             "reason": bookkeeping_reason})

    return {
        "outcome": outcome,
        "rows": rows,
        "run_data": run_data,
        "recovered": bool(recovery.get("recovered")),
        "run_id": outcome.run_id,
        "can_write": can_write,
        "written_records_failures": written_records_failures,
    }


def projected_spend(outcome) -> int:
    """The chunks ATTEMPTED (not the whole plan — a caller that stopped on a
    `ceiling_stop` attempted fewer) plus the rows in them, read straight off a
    `DispatchOutcome` (Phase 57). The SAME `chunk_count + record_count` formula
    `write_grant.EXECUTIONS_BASIS`/`run_state.spend_against_ceiling` already use, never
    re-derived, so a caller running several `dispatch_plan` calls under one grant (the
    pair pipeline's match/enrich/re-request/ingest passes) can decrement its remaining
    allowance across them without a second formula to keep in sync.

    Reads `result.rows` off each `ChunkResult` in `outcome.results` — never
    `outcome.failed_batch` or `ceiling_stop.unsent_chunks`, which by definition were NOT
    sent and must not be charged. A chunk whose `rows` reads `chunking.UNKNOWN` (the
    backend-resolved list shape) contributes 0 rows to the sum — its own chunk still
    counts as 1 execution — because there is no client-side count to add; the caller is
    left to its own honest "unknown" rather than a guessed number.
    """
    attempted = tuple(outcome.results) if outcome is not None else ()
    row_total = sum(r.rows for r in attempted if isinstance(r.rows, int))
    return len(attempted) + row_total


def single_dispatch_outcome(result, *, record_count, run_id=None) -> DispatchOutcome:
    """Wrap a single-shot `dispatch.dispatch(...)` result into a real `DispatchOutcome`
    (Phase 57, REVIEW-57-H7) — the adapter the pair pipeline's FINAL ingest leg needs.

    That leg never reaches `dispatch_plan` at all: `enrich-before-ingest/SKILL.md:610`
    and `contact-upload/SKILL.md` both call `dispatch.dispatch(out_path, armed, cfg,
    run_id=...)`, a single-shot CSV send returning `{"body", "run_id",
    "written_records_failures"}` (`dispatch.py:58`, `:114`). Nothing charged its spend
    before this: `projected_spend` could not see it, and 57-05's `outcomes=` could not
    receive it. This wraps that dict into ONE `ChunkResult` carrying `record_count` rows,
    so `projected_spend` evaluates it to `1 + record_count` through the SAME formula
    every other leg uses — never a second spend vocabulary.

    `record_count` is keyword-only, deliberately: a positional call could silently swap
    it with `run_id` (both plausible-looking values at a call site), and the row count
    feeding straight into the execution-ceiling arithmetic is exactly the field a swap
    must not corrupt silently.

    `ceiling_stop` is unconditionally `None`: a single-shot send has no chunk boundary to
    stop AT mid-call — the ceiling check for this leg is PRE-CALL and lives in the
    runbook (Task 4), exactly as the `plan.row_counts == UNKNOWN` shape is documented on
    `dispatch_plan` above. This is a documented boundary of the mechanism, not an
    omission.
    """
    result = result if isinstance(result, dict) else {}
    written_records_failures = result.get("written_records_failures") or ()
    chunk_result = ChunkResult(index=0, rows=record_count, ok=True)
    return DispatchOutcome(
        results=(chunk_result,),
        failed_batch=None,
        responses=(result.get("body"),),
        run_id=run_id if run_id is not None else result.get("run_id"),
        written_records_failures=tuple(written_records_failures),
        ceiling_stop=None,
    )


def merge_chunk_verdicts(run_id, chunk_verdicts, path=None) -> None:
    """Persist one chunk's own verdicts WITHOUT erasing any prior chunk's (Phase 61
    Plan 05 Task 3, REVIEW-C13). `run_manifest.save` writes the supplied map as the
    COMPLETE document (`run_manifest.py:117-153`) — it does not merge. A caller that
    saved only `{this chunk's own rows}` per chunk would ERASE every earlier chunk's
    verdicts, turning "write per chunk" (meant to bound replay to one chunk) into a
    mechanism that guarantees a full replay of everything already done.

    So: load whatever this run has already accumulated (`run_manifest.load`, which
    already degrades a missing/corrupt file to `{}` — there is nothing new to trust
    here, only to not lose), merge this chunk's verdicts on top (this chunk's own value
    wins on any overlapping row id), and save the WHOLE resulting map.
    `run_manifest.save`'s whole-document semantics stay unchanged; the merge is this
    caller's job, not a second write mode on `save()`.

    Not wired into `dispatch_plan` itself: a verdict (`matched`/`enriched`/`held`/
    `unchecked`/`unanswered`/`confidence_held`) is derived downstream of a chunk's raw
    response — by Haiku, Sonnet, and `confidence.assess` — so `dispatch_plan` cannot
    compute one. A caller (the SKILL.md runbook) composes this the same way
    `run_state.mark_dispatched`'s own docstring already names for a different pair: "a
    caller composes the two."

    The crash window this bounds is exactly one chunk wide: a crash between this
    function's own load and its own save loses at most the CURRENT chunk's verdicts —
    the previous chunk's call to this function already completed its own save before
    this one started, so its verdicts are already on disk.

    `path` defaults to `run_manifest.manifest_path()` — the SAME single shared file
    `SKILL.md`'s existing resume step already reads across separate runs of this skill,
    never a per-run file (this is not `run_state.py`'s per-run scoping; the two stores
    make opposite defaults for opposite reasons, each already documented in its own
    module).
    """
    target = Path(path) if path is not None else run_manifest.manifest_path()
    accumulated = run_manifest.load(path=target)
    merged = dict(accumulated)
    merged.update(chunk_verdicts)
    run_manifest.save(run_id, merged, path=target)


# The four list-bearing shapes `plan_chunks` accepts, ordered — `failed_batch` and
# `write_grant.split_for_allowance` both walk this SAME tuple (Phase 57, REVIEW-57-H4/H8)
# so a shape added to one has an obvious place to be added to the other. `rows` and
# `record_ids` carry `object_type`; `people` and `companies` do not (37-CONTEXT §5 /
# CLAUDE.md section 13.0.1 — a `people`/`companies` event carries its own `objectType`
# per record, never one shared across the batch).
LIST_BEARING_KEYS = ("record_ids", "rows", "people", "companies")
KEYS_WITH_OBJECT_TYPE = frozenset({"record_ids", "rows"})


def failed_batch(chunks):
    """The failed chunks as ONE record specification, or None when nothing failed.

    Reconstructs EVERY shape `plan_chunks` accepts — `list` (single-chunk passthrough,
    below), `rows`, `people`, `companies` and `record_ids` (REVIEW-57-H4: this used to
    branch on `rows`/`record_ids` alone and silently return `chunks[0]` for a multi-chunk
    `people` or `companies` batch, dropping every record after the first chunk). Members
    keep their original order and no member from a successful chunk appears. The result
    is already a well-formed enrichment request by construction, so a caller re-sends it
    through the same armed dispatch path rather than parsing it out of log lines (D-13).
    """
    if not chunks:
        return None
    if len(chunks) == 1 and chunks[0].get("list"):
        return dict(chunks[0])

    key = next((k for k in LIST_BEARING_KEYS if k in chunks[0]), None)
    if key is None:
        return dict(chunks[0])

    members = [member for chunk in chunks for member in chunk.get(key, [])]
    if not members:
        return dict(chunks[0])

    result = {key: members}
    if key in KEYS_WITH_OBJECT_TYPE:
        result["object_type"] = chunks[0].get("object_type")
    return result


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
