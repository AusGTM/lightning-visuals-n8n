"""operator-claude-plugin/scripts/run_state.py

Phase 61 Plan 05 Task 2 (RUN-01/RUN-03/RUN-04). The plugin's FIFTH persisted artifact
(`artifact_store.py` first, `run_manifest.py` second, `written_records.py` third,
`held_queue.py` fourth) — but unlike those four, this one holds no VERDICTS at all. It
holds exactly one thing `run_manifest.py` cannot: the run's own SCOPE — which row ids
this run covers, and which of them have actually been sent — so a progress read can
answer "pending" as well as "done"/"held"/"failed", which a verdict-only store can never
do (a row with no verdict yet is indistinguishable from a row nobody has heard of).

**Store decision (61-SPIKE-VERDICT.md, `## Operator Decision (Task 4)`, 2026-08-30,
carried into 61-01-SUMMARY.md's "Decisions Made").** The operator selected a HubSpot
object (run handle + progress, human-observable directly in the CRM the operator already
uses) PLUS the existing `run_manifest.py` (per-row verdicts) for async run state — not
n8n `staticData`, not the executions API alone. This module is the CLIENT-SIDE half of
that pair: it never calls HubSpot (PLUGIN-04's no-backend-import guard holds; this
plugin holds no HubSpot token and never will, per every other module in this directory),
and it never calls n8n's executions API either. It "reports over" `run_manifest.py` —
combining this run's own registered scope with `run_manifest.load_scoped()`'s run-scoped
verdicts — the same relationship `held_queue.py`'s own docstring describes for a
DIFFERENT pair of concerns. Creating the actual HubSpot run-state property is a live
write and is out of scope for this plan's offline tasks (1-3); it is this plan's own
Task 4 checkpoint's job, deployed and observed there, never assumed here.

**Dispatch decision — substrate 1, not substrate 3, for THIS plan (a deliberate,
disclosed departure from 61-01-SUMMARY.md's "strongest candidate" framing).**
61-SPIKE-VERDICT.md names substrate 3 (`Execute Workflow`, wait-for-completion off) as
unmetered and uncapped, and that finding is not wrong — it is carried forward below as
the SCALE-UP path. But P-11 already shows both a 40-record and a 300-record batch fit
the configured 2,500/month allowance under EITHER execution-cost reading, so substrate
3's unmetered/uncapped advantage is not load-bearing at THIS plan's scale. Substrate 3
realized in full is a materially larger, riskier build than substrate 1: either a
self-referencing `Execute Workflow` node inside `wf_enrichment_cloud.json` (an unprobed
publish-order interaction — the same "publish children before parent" constraint
`61-SPIKE-VERDICT.md`'s P-13 note names, now applied to a workflow calling ITSELF) or a
brand-new parent workflow with its own webhook path, which would mean the plugin's
dispatch target changes (`enrichment.py`'s `WEBHOOK_PATH`, `chunking.dispatch_plan`'s own
call site) — straining REVIEW-C14's explicit instruction to pass `run_id` into
`dispatch_plan`'s EXISTING parameter, not build a second submission path around it.
Substrate 1 ("Respond node moved to the front of the chain") needed none of that: P-07 was
probed LIVE on this exact n8n instance (execution `12035`, 2026-08-30) for exactly this
mechanism — a `Wait`-node stand-in for "the rest of the chain keeps running after Respond
fires" — and confirmed true. The concrete, additive n8n-side change this plan ships
(`scripts/build_cloud_workflows.py`'s `ENRICH_PARSE_EVENT_CLOUD` + the new `Build Async
Ack` node, both in `build_enrichment_cloud()`) is exactly substrate 1's own described
change: an opt-in per-request `async_ack` boolean that, when true, fans `Parse HubSpot
Event`'s output to an immediate ack alongside the UNCHANGED existing chain — see that
node's own comment for why `Respond to Webhook` receiving two arrivals in the async case
is the same documented "first arrival wins" property this workflow's `Build Response`
comment already carries for its own multiple inbound branches, not a new risk class.
Substrate 3's findings (the double execution-cost exemption, and the "publish children
before parent" constraint) remain the informed starting point for 61-06 if/when execution
volume actually approaches the allowance substrate 1's arithmetic does not need to worry
about yet.

**No poll loop lives here** (`tests/test_report_sufficiency.py`'s
`_POLL_LOOP_ALLOWED = {"watch.py"}` guard scans every OTHER plugin script for a `time`/
`sched` import, a `sleep()` call, or a `while` loop — this module contains none of the
three, by construction, not by discipline: every read here is a single, synchronous file
probe, exactly once per call).

**Schema.** A run id, a timestamp, `total_row_ids` (every row id this run covers, fixed
at registration time via `start_run()`, BEFORE the first chunk is dispatched — REVIEW-C14:
the id is minted by the CALLER before any HTTP call, and `total_row_ids` is registered
before the first one too, so "how many rows does this run cover" is answerable from the
first progress read even if zero chunks have been sent yet), and `dispatched_row_ids`
(the subset actually sent so far, grown incrementally via `mark_dispatched()`, once per
chunk — mirroring how `written_records.append_chunk` and `run_manifest`'s own verdict
writes already happen per chunk in `chunking.dispatch_plan`'s loop, a pattern this module
does not change and is not wired into by this plan — a caller composes the two).

**The read path classifies before it degrades**, mirroring `held_queue.classify_read`'s
own reasoning verbatim for a different file: `classify_read()` is a probe over the raw
file returning `ABSENT` (never registered — a legitimate zero, the same "read fine,
nothing there" answer `n8n_read.py`'s own docstring describes), `PARSEABLE` (a real,
readable document), or `ANOMALOUS` (present but unreadable/malformed/schema-mismatched —
a state this module could not read and must never present as zero, the literal contract
Task 2's own action text names). `read_progress()`'s three-way `state` field
(`NOT_STARTED`/`OK`/`UNREADABLE`) carries that same distinction through to every numeric
field: `NOT_STARTED` and `OK` report real integers (zero is a fine, honest answer for a
run that has not begun); `UNREADABLE` reports every count as `None` — Python's `None`
can never be silently summed or displayed as `0`, which is the whole point.

**The five-bucket invariant (REVIEW-A6, must_haves).** `read_progress()` computes
`pending`, `running`, `done`, `held`, and `failed` such that their sum always equals
`total` when `state == OK` — asserted here as a cheap, always-on sanity check (belt), and
independently asserted again in `test_run_state.py` (braces), so a future edit that
breaks the partition fails loudly in two places rather than one:
  - `done`    = verdicts in `{MATCHED, ENRICHED}` (genuinely complete, `run_manifest.py`'s
    own words).
  - `held`    = verdicts in `{HELD, CONFIDENCE_HELD}` (collected, not guessed, D-61-07).
  - `failed`  = verdicts in `{UNCHECKED, UNANSWERED}` — a row this run tried to reach an
    answer for and could not; still resumable (`run_manifest.rows_to_resume` re-includes
    both), but not "still in flight" from a PROGRESS DISPLAY's point of view, which is
    the distinction this bucket exists to draw.
  - `running` = dispatched, but no verdict recorded for it yet in THIS run's scoped
    manifest (`run_manifest.load_scoped(run_manifest_path(run_id), expected_run_id=run_id)`
    — the exact function 61-04 built naming 61-05 as the consumer).
  - `pending` = registered in `total_row_ids` but not yet in `dispatched_row_ids` at all.

`run_manifest_path(run_id)` is OPT-IN (61-04's own docstring): `run_manifest.save()`
still writes to the single shared `manifest_path()` by default. A caller that wants
`read_progress()` to see its verdicts must save to `run_manifest.run_manifest_path(run_id)`
explicitly — this module does not do that saving itself, the same "reports over, does
not own" relationship it has with `held_queue.py`.

Held-queue entries (`held_queue.py`) are deliberately NOT read here for counting purposes
— that store is a durable backlog spanning MANY runs (`held_queue.py`'s own docstring:
"ONE GLOBAL FILE... cleared in a single pass"), so it carries no per-entry run
attribution a progress read could scope by. `run_manifest`'s own `HELD`/`CONFIDENCE_HELD`
verdicts, which ARE run-scoped via `run_manifest_path(run_id)`, are the correct and
sufficient source for this run's held count.

**Spend against ceiling (RUN-04).** `spend_against_ceiling()` reuses the SAME projected
formula `write_grant.EXECUTIONS_BASIS` already documents (`chunk_count + record_count`)
against the configured `n8n_monthly_execution_allowance` — never a live read, because none
exists (P-05/P-12: n8n exposes no usage/quota endpoint to an API key). Labelled
`"projected"`, with 61-SPIKE-VERDICT.md's own P-10 finding folded into the caveat text: a
real, measured 2-record chunk (execution `11950`) showed this formula OVER-STATES cost by
a factor of roughly 3, so this figure is a ceiling estimate, never an invoice.

Carries `run_manifest.py`'s Phase 23 D-11 forbidden-name refusal verbatim in substance —
reimplemented, not imported, the same discipline `held_queue.py` and `written_records.py`
already apply to this identical list, so a future change to one cannot silently weaken
another: a row id shaped like an arming grant, a secret, or an API key is refused, never
persisted.

Writes through `durable_paths._atomic_write_0600`, same durable directory as every other
artifact in this family, filename deliberately not a dotfile (Phase 23 D-04). ONE FILE
PER RUN (`run_state-<run_id>.json`), mirroring `written_records.written_records_path`
and `run_manifest.run_manifest_path`'s exact naming shape — never a single shared file,
because this store's whole reason to exist is per-run SCOPE, which a shared file would
have nowhere to keep separate.
"""
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import durable_paths
import run_manifest

# --- schema ----------------------------------------------------------------------------

RUN_ID_FIELD = "run_id"
STAMP_FIELD = "saved_at"
TOTAL_FIELD = "total_row_ids"
DISPATCHED_FIELD = "dispatched_row_ids"

# classify_read()'s three answers.
ABSENT = "absent"
PARSEABLE = "parseable"
ANOMALOUS = "anomalous"

# read_progress()'s three states.
NOT_STARTED = "not_started"
OK = "ok"
UNREADABLE = "unreadable"

# Phase 23 D-11, reimplemented (not imported) per `run_manifest.py`/`held_queue.py`'s own
# precedent — a future change to one list must not silently weaken another.
_FORBIDDEN_NAME_MARKERS = (
    "arm", "secret", "api_key", "apikey", "token", "credential", "password",
    "grant", "permission", "webhook",
)

_DONE_VERDICTS = frozenset({run_manifest.MATCHED, run_manifest.ENRICHED})
_HELD_VERDICTS = frozenset({run_manifest.HELD, run_manifest.CONFIDENCE_HELD})
_FAILED_VERDICTS = frozenset({run_manifest.UNCHECKED, run_manifest.UNANSWERED})

# write_grant.EXECUTIONS_BASIS's own projected formula, reused rather than re-derived —
# see module docstring's "Spend against ceiling" section for the P-10 over-statement
# caveat this label carries forward.
SPEND_BASIS = (
    "projected: 1 webhook execution per chunk + 1 sub-execution per record "
    "(write_grant.EXECUTIONS_BASIS) — 61-SPIKE-VERDICT.md's P-10 found this formula "
    "OVER-STATES a real chunk's cost by roughly 3x, so treat this as a ceiling estimate, "
    "never an invoice"
)


class RunStateError(Exception):
    """Raised when a run's registered scope cannot be persisted safely — a row id whose
    name suggests an arming grant, a live-write permission, a secret, or an API key
    (Phase 23 D-11, see module docstring). Nothing is written when this raises."""


def _looks_forbidden(value) -> bool:
    lowered = str(value).lower()
    return any(marker in lowered for marker in _FORBIDDEN_NAME_MARKERS)


def new_run_id() -> str:
    """The one place this module mints a run id — the SAME shape
    `chunking.dispatch_plan` mints internally when a caller omits one
    (`uuid.uuid4().hex`, `chunking.py:336-337`). REVIEW-C14: a caller mints with this
    BEFORE calling `dispatch_plan`, then passes the SAME id to both `start_run()` here
    and `dispatch_plan(..., run_id=...)` — never two different ids for one run."""
    return uuid.uuid4().hex


def run_state_path(run_id) -> Path:
    """Where ONE run's own scope lives — resolved fresh on every call, the same durable
    directory `run_manifest.manifest_path()` and `held_queue.queue_path()` both resolve
    into, never a second resolution rule."""
    return durable_paths.resolve_state_path().parent / f"run_state-{run_id}.json"


def _validate_row_ids(row_ids):
    cleaned = []
    for row_id in row_ids:
        row_id = str(row_id)
        if _looks_forbidden(row_id):
            raise RunStateError(
                f"refusing to register row id {row_id!r} — its name suggests an arming "
                "grant, a live-write permission, a secret, or an API key. Nothing was "
                "written."
            )
        cleaned.append(row_id)
    return cleaned


def start_run(run_id, row_ids, path=None) -> None:
    """Registers this run's full scope BEFORE the first chunk is dispatched — one call,
    at submit time, with the SAME `run_id` the caller is about to pass to
    `dispatch_plan`. `row_ids` is every row this run covers, in the shape
    `enrichment.MATCH_LOOKUP_KEYS`-style rows already carry (`row["row_id"]`) — the one
    spec form `run_manifest.py`'s own verdict keying already assumes.

    Validates before writing (mirrors `run_manifest.save`'s validate-then-apply
    discipline): a save that raises leaves nothing on disk for this run.
    """
    cleaned = _validate_row_ids(row_ids)
    target = Path(path) if path is not None else run_state_path(run_id)
    document = {
        RUN_ID_FIELD: run_id,
        STAMP_FIELD: datetime.now(timezone.utc).isoformat(),
        TOTAL_FIELD: cleaned,
        DISPATCHED_FIELD: [],
    }
    durable_paths._atomic_write_0600(target, json.dumps(document))


def _load_document(run_id, path=None):
    """The raw document, or `None` if it cannot be read/parsed/validated. Shared by
    `classify_read()` and `mark_dispatched()`/`read_progress()` so all three agree on
    what "usable" means."""
    target = Path(path) if path is not None else run_state_path(run_id)
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(document, dict):
        return None
    total = document.get(TOTAL_FIELD)
    dispatched = document.get(DISPATCHED_FIELD)
    if not isinstance(total, list) or not isinstance(dispatched, list):
        return None
    if not all(isinstance(r, str) for r in total) or not all(isinstance(r, str) for r in dispatched):
        return None
    return document


def classify_read(run_id, path=None) -> str:
    """What this run's own state file looks like, from a fresh probe — never raises.
    `ABSENT` (never registered — a legitimate zero, not a failure to read), `PARSEABLE`
    (a real, readable document), or `ANOMALOUS` (present but unreadable, malformed, or
    schema-mismatched — must never present as zero, see module docstring)."""
    target = Path(path) if path is not None else run_state_path(run_id)
    if not target.exists():
        return ABSENT
    return PARSEABLE if _load_document(run_id, path) is not None else ANOMALOUS


def mark_dispatched(run_id, row_ids, path=None) -> None:
    """Records that `row_ids` (a subset of `total_row_ids`, typically one chunk's worth)
    have actually been sent — called once per chunk, the same per-chunk cadence
    `written_records.append_chunk` and a per-chunk `run_manifest.save` already use in
    `chunking.dispatch_plan`'s loop (this module is not wired into that loop by this
    plan; a caller composes the two). Read-merge-write over the ACCUMULATED set, never a
    bare overwrite — the same discipline Task 3 states explicitly for `run_manifest.save`
    (REVIEW-C13): a chunk that saved only its own ids would erase every prior chunk's.

    Raises `RunStateError` if the run was never registered (`start_run` first) or its
    file is anomalous — there is no scope to add to, and silently creating one here would
    let a caller skip `start_run`'s up-front total, which is the whole point of this
    module existing separately from `run_manifest.py`.
    """
    document = _load_document(run_id, path)
    if document is None:
        raise RunStateError(
            f"no registered scope for run {run_id!r} — call start_run() before "
            "mark_dispatched(). Nothing was written."
        )
    cleaned = _validate_row_ids(row_ids)
    dispatched = set(document[DISPATCHED_FIELD]) | set(cleaned)
    target = Path(path) if path is not None else run_state_path(run_id)
    document = {
        RUN_ID_FIELD: document.get(RUN_ID_FIELD, run_id),
        STAMP_FIELD: datetime.now(timezone.utc).isoformat(),
        TOTAL_FIELD: list(document[TOTAL_FIELD]),
        DISPATCHED_FIELD: sorted(dispatched),
    }
    durable_paths._atomic_write_0600(target, json.dumps(document))


@dataclass(frozen=True)
class Progress:
    """One progress read's answer. `state` decides how the numeric fields read:
    `NOT_STARTED`/`OK` carry real integers (zero is a fine, honest value); `UNREADABLE`
    carries `None` in every one — never a substituted zero (Task 2's own literal
    contract: a state this module could not read must never present as zero)."""

    run_id: str
    state: str
    total: int = None
    pending: int = None
    running: int = None
    done: int = None
    held: int = None
    failed: int = None


def _empty_progress(run_id, state) -> Progress:
    if state == NOT_STARTED:
        return Progress(run_id=run_id, state=state, total=0, pending=0, running=0,
                         done=0, held=0, failed=0)
    return Progress(run_id=run_id, state=state)


def read_progress(run_id, path=None, *, manifest_snapshot=None) -> Progress:
    """This run's progress, combining its OWN registered scope (this file) with
    `run_manifest`'s run-scoped verdicts. See module docstring's "five-bucket invariant"
    section for exactly how each bucket is derived.

    `manifest_snapshot` (57-05 Task 2, REVIEW-57-M1), keyword-only: an already-loaded
    `run_manifest.ScopedLoadResult` to derive verdicts from, instead of loading the
    manifest again here. Default (`None`) is byte-for-byte today's own internal load —
    every existing caller and test is unaffected. `run_report.build_run_report` is the
    one caller that passes a snapshot: it needs the SAME view of the manifest for both
    this run's progress bucket AND its per-row verdicts, and two independent loads of
    one file could in principle see two different states of it.
    """
    classification = classify_read(run_id, path)
    if classification != PARSEABLE:
        return _empty_progress(run_id, NOT_STARTED if classification == ABSENT else UNREADABLE)

    document = _load_document(run_id, path)
    total_ids = set(document[TOTAL_FIELD])
    dispatched_ids = set(document[DISPATCHED_FIELD]) & total_ids

    scoped = manifest_snapshot if manifest_snapshot is not None else run_manifest.load_scoped(
        run_manifest.run_manifest_path(run_id), expected_run_id=run_id
    )
    verdicts = {row_id: v for row_id, v in scoped.verdicts.items() if row_id in total_ids}

    done = sum(1 for v in verdicts.values() if v in _DONE_VERDICTS)
    held = sum(1 for v in verdicts.values() if v in _HELD_VERDICTS)
    failed = sum(1 for v in verdicts.values() if v in _FAILED_VERDICTS)
    verdicted_ids = set(verdicts)
    running = len(dispatched_ids - verdicted_ids)
    pending = len(total_ids - dispatched_ids)
    total = len(total_ids)

    # Belt (REVIEW-A6) — braces live again in test_run_state.py.
    assert pending + running + done + held + failed == total, (
        f"run {run_id!r}: progress buckets ({pending}+{running}+{done}+{held}+{failed}) "
        f"do not sum to total ({total}) — a row has gone missing from the partition."
    )

    return Progress(run_id=run_id, state=OK, total=total, pending=pending,
                     running=running, done=done, held=held, failed=failed)


def spend_against_ceiling(config, chunk_count, record_count) -> dict:
    """This run's projected execution cost against the configured monthly allowance —
    see module docstring's "Spend against ceiling" section. Never a live read; `None`
    allowance means the key is not configured, reported as such rather than guessed."""
    allowance = (config or {}).get("n8n_monthly_execution_allowance")
    projected = int(chunk_count) + int(record_count)
    return {
        "projected_executions": projected,
        "allowance": allowance if isinstance(allowance, (int, float)) else None,
        "basis": SPEND_BASIS,
    }
