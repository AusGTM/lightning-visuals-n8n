"""operator-claude-plugin/scripts/watch.py

The bounded in-session watch (NOTICE-01/NOTICE-02, 29-CONTEXT D-05/D-06/D-07). After a
dispatch, keeps re-checking a run's execution until it settles or a config-tunable bound
elapses — and always ends by returning one of exactly two report shapes, never nothing.

Per D-05a, THE BOUNDED PATH IS THE LOAD-BEARING MECHANISM, not a degraded fallback:
29-RESEARCH.md observed genuine unprompted mid-conversation follow-up in the CLI runtime
but could not confirm it in Claude Desktop (the actual target), and 29-HOST-PROBE.md A2
recorded that verdict as NO. So this module is built to work correctly with NO unprompted
delivery at all — the "bonus" layer at the bottom of this file only changes a `delivery_mode`
label on an otherwise-identical settled report; removing it changes nothing else.

Two terminal outcomes, structurally enforced by ``poll_until_settled`` having exactly two
``return`` statements, each producing a full report object via ``build_settled_report`` /
``build_still_running_report``. "Returns nothing" is not a reachable state in this
function — there is no code path between them.

BACKOFF SCHEDULE: (5, 5, 10, 15, 30, 60) seconds, widening then flat. The measured single-
record run is 32-39s (29-TIMING.md) so the first two 5s polls catch a fast run promptly;
widening toward 60s means a run that actually needs the full 600s default bound costs
roughly a dozen reads, not hundreds at a fixed tight interval. 60s is the ceiling because
n8n Cloud's own webhook response window is ~100s (26-CONTEXT D-13) — polling slower than
that would make an otherwise-fast settle feel needlessly laggy to the operator.

Reuses Phase 26's own outcome renderers rather than a second one (D-07's whole point):
``report.build_contact_report`` for a contact-upload dispatch, ``report_enrichment.
build_enrichment_report`` for an enrichment dispatch — selected by the ``lane`` the caller
already knows it dispatched. Every field discipline those renderers already hold (D-10a/
D-10b's ICP-is-out-of-scope, D-14's no-email-is-not-retryable) is inherited for free by
calling through, not re-implemented here.

The correlation this module watches is fallible by construction (26-CONTEXT D-12): neither
deployed workflow returns an execution id, so the run handle is a time-proximity guess
(``executions_client.find_execution_for_dispatch``). The still-running report says so
plainly rather than asserting the watched run with false confidence.
"""
import json
import time
from dataclasses import dataclass
from pathlib import Path

import requests

import executions_client
import report
import report_enrichment
import run_manifest
import scheduled_arm

try:
    import cost_guard
except Exception:  # pragma: no cover - cost_guard imports config_gate/backend_status only
    cost_guard = None


# =====================================================================================
# The bound (D-05/D-06/D-06a) — config first, the MEASURED default from 29-TIMING.md
# when absent, scaled for multi-record dispatches per 29-TIMING.md §3.
# =====================================================================================

# 29-TIMING.md §3: MEASURED (n=5 executions), not guessed. Ten minutes, ~15x the observed
# 38.9s max single-run duration — headroom is chosen in the safe direction, since a bound
# set too low trains the operator to stop believing "still running" at all (NOTICE-02).
DEFAULT_BOUND_SECONDS = 600.0

# 29-TIMING.md §3: the headroom rate (observed max + ~25%), used to scale the bound for a
# dispatch of more than one record — the enrichment workflow has no Split In Batches node,
# so an N-record dispatch takes roughly N times as long (25-RESEARCH.md).
PER_RECORD_HEADROOM_SECONDS = 45.0

BACKOFF_SCHEDULE_SECONDS = (5, 5, 10, 15, 30, 60)


def resolve_bound_seconds(config, record_count=None):
    """The bound this watch enforces. Config's own ``watch_bound_seconds`` wins when
    present and positive; the measured default otherwise — an admin raising it for a
    slow backend needs no code change (D-05). Scaled up (never down) for a known
    multi-record dispatch; ``record_count=None`` (the backend-resolved-list case) leaves
    the floor untouched rather than guessing a count.
    """
    try:
        configured = float((config or {}).get("watch_bound_seconds"))
        bound = configured if configured > 0 else DEFAULT_BOUND_SECONDS
    except (TypeError, ValueError):
        bound = DEFAULT_BOUND_SECONDS

    if isinstance(record_count, int) and record_count > 0:
        bound = max(bound, record_count * PER_RECORD_HEADROOM_SECONDS)
    return bound


# =====================================================================================
# The still-running report (D-07, NOTICE-02) — the run handle, and the correlation basis
# that makes its own fallibility visible rather than asserted (D-12).
# =====================================================================================

_CORRELATION_BASIS_NOTE = (
    "this run was matched by timing — the earliest execution that started at or after "
    "the dispatch — not by an execution id the backend returned. Neither deployed "
    "workflow references $execution.id (26-CONTEXT D-12), so this correlation could "
    "name the wrong run; that is stated here rather than assumed correct."
)


def build_still_running_report(run_handle, *, elapsed_seconds, bound_seconds):
    """The bound elapsed with the run unsettled. Never empty, never falsy: always this
    fixed shape, with the run handle and how to re-check carried through even when the
    handle itself is None (the correlation never found a candidate at all)."""
    return {
        "kind": "still_running",
        "state": "in_flight",
        "handle": run_handle,
        "elapsed_seconds": elapsed_seconds,
        "bound_seconds": bound_seconds,
        "correlation_basis": _CORRELATION_BASIS_NOTE,
        "recheck": {
            "how": "ask me to check this run again, any time — it keeps running on the backend",
            "execution_id": (run_handle or {}).get("execution_id"),
            "best_effort": (run_handle or {}).get("best_effort", True),
        },
    }


# =====================================================================================
# Cost actually incurred (D-10) — a delta between two balances the system already
# fetched. Unknown propagates at every step; it is never collapsed to zero (T-26-07's
# rule, applied here to a delta rather than a single reading).
# =====================================================================================

def _normalize_balance_reading(reading):
    """Coerces either ``cost_guard.fetch_balances``'s shape
    (``{provider: {credits, unreadable, reason}}``) or ``report_enrichment.
    remaining_credits_from_response``'s shape (``{provider: number|"unknown"}``) into one
    ``{provider: credits_or_None}`` mapping. None means unreadable; a real 0 stays 0."""
    if not isinstance(reading, dict):
        return {}
    normalized = {}
    for provider, value in reading.items():
        if isinstance(value, dict):
            normalized[provider] = None if value.get("unreadable") else value.get("credits")
        elif value == "unknown":
            normalized[provider] = None
        elif isinstance(value, (int, float)):
            normalized[provider] = value
        else:
            normalized[provider] = None
    return normalized


def compute_cost_delta(pre_balances, post_balances):
    """Per-provider credits spent this run: pre minus post. If EITHER end is unreadable
    the delta is unknown, never a difference computed against a substituted zero — that
    is the direction that understates spend, which erodes operator trust fastest.

    ``state`` is ``"known"`` only when every provider resolved; ``"partial"`` when some
    did and some did not (reported as partial, never as a smaller number); ``"unknown"``
    when none did or there is nothing to compare.
    """
    pre = _normalize_balance_reading(pre_balances)
    post = _normalize_balance_reading(post_balances)
    providers = sorted(set(pre) | set(post))

    per_provider = {}
    for provider in providers:
        p, q = pre.get(provider), post.get(provider)
        if p is None or q is None:
            per_provider[provider] = {"spent": None, "known": False}
        else:
            per_provider[provider] = {"spent": p - q, "known": True}

    known_flags = [entry["known"] for entry in per_provider.values()]
    if not known_flags:
        state = "unknown"
    elif all(known_flags):
        state = "known"
    elif any(known_flags):
        state = "partial"
    else:
        state = "unknown"

    return {"per_provider": per_provider, "state": state}


def token_usage_from_execution(execution):
    """Token usage recoverable from the settled execution's own data, read from ``Build
    Response``'s own output the same way ``remaining_credits`` is (never a live call).
    No deployed node currently emits a token-usage block, so this reads ``"unknown"``
    today — read defensively rather than hardcoding that absence, so a future node
    adding one is picked up with no code change here.
    """
    run_data = report._run_data(execution)
    if run_data is None:
        return "unknown"
    runs = run_data.get(report_enrichment.BUILD_RESPONSE_NODE)
    first_run = runs[0] if isinstance(runs, list) and runs else None
    items = report._node_output_items(first_run)
    if not items:
        return "unknown"
    first_json = items[0].get("json") if isinstance(items[0], dict) else None
    usage = (first_json or {}).get("token_usage") if isinstance(first_json, dict) else None
    return usage if isinstance(usage, dict) else "unknown"


def build_cost_report(pre_dispatch_balances, execution, config=None, transport=None):
    """The settled report's cost block: the credit delta plus token usage. Falls back to
    Phase 27's status endpoint only when the enrichment response itself carried no
    credits block at all (an empty dict, never a populated-but-unknown one, which is
    already meaningful and must not be overridden by a second read)."""
    post_balances = report_enrichment.remaining_credits_from_response(execution)
    if not post_balances and config is not None and cost_guard is not None:
        kwargs = {} if transport is None else {"transport": transport}
        post_balances = cost_guard.fetch_balances(config, **kwargs)

    return {
        "credits": compute_cost_delta(pre_dispatch_balances, post_balances),
        "tokens": token_usage_from_execution(execution),
    }


# =====================================================================================
# The bonus delivery layer (D-05a) — 29-HOST-PROBE.md A2 recorded NO. This changes only
# the settled report's `delivery_mode` label; removing the whole section would break
# nothing about the report's content.
# =====================================================================================

# 29-HOST-PROBE.md A2 (probed 2026-08-03): unprompted mid-conversation follow-up in
# Claude Desktop was NOT OBSERVED, treated as NO per 29-01 Task 2's rule that an
# unverified capability and an absent one get identical treatment. Single source of
# truth for the verdict — a future re-probe flips this one line, never a scattered set
# of call sites.
UNPROMPTED_FOLLOWUP_VERDICT = False


def bonus_delivery_available(config=None) -> bool:
    """Whether the settled report could be delivered unprompted mid-conversation. A
    config override (``watch_unprompted_followup_verdict``) lets a future re-probe flip
    this without a code change; absent, the recorded verdict above is authoritative.
    """
    override = (config or {}).get("watch_unprompted_followup_verdict") if config else None
    if isinstance(override, bool):
        return override
    return UNPROMPTED_FOLLOWUP_VERDICT


# =====================================================================================
# The settled report (NOTICE-01) — one renderer per lane, never a second convention.
# =====================================================================================

_LANE_RENDERERS = {
    "enrichment": report_enrichment.build_enrichment_report,
    "contact_upload": report.build_contact_report,
}


def build_settled_report(execution, run_handle, *, lane="enrichment",
                          pre_dispatch_balances=None, config=None, transport=None,
                          bonus_delivery_available=False):
    """Shapes a settled execution into the report the skill renders. Renders through
    Phase 26's own renderer for the dispatched lane — no second outcome convention, and
    every field discipline that renderer already holds (D-10a/D-10b's ICP exclusion,
    D-14's no-email-is-not-retryable) is inherited by calling through it, not
    reimplemented. The cost block only applies to the enrichment lane — contact-upload
    burns no provider credits, so there is nothing to compute a delta of.
    """
    renderer = _LANE_RENDERERS.get(lane, report_enrichment.build_enrichment_report)
    outcome = renderer(execution, handle=run_handle)

    cost = None
    if lane == "enrichment":
        cost = build_cost_report(pre_dispatch_balances, execution, config=config, transport=transport)

    return {
        **outcome,
        "kind": "settled",
        "cost": cost,
        "delivery_mode": "unprompted" if bonus_delivery_available else "next_opportunity",
    }


# =====================================================================================
# The poll loop (Task 1, D-05/D-07) — a pure function of an injected clock and an
# injected reader. Exactly two return statements; "returns nothing" is not reachable.
# =====================================================================================

def _is_settled(execution) -> bool:
    if not isinstance(execution, dict):
        return False
    return execution.get("status") in report.SETTLED_STATUSES


def poll_until_settled(read_once, bound_seconds, run_handle, *, now, sleep,
                        backoff_schedule=BACKOFF_SCHEDULE_SECONDS, lane="enrichment",
                        **settled_report_kwargs):
    """Polls ``read_once()`` (no args, returns an execution dict or None) until it
    settles or ``bound_seconds`` elapses against ``now()``. ``now`` and ``sleep`` are
    both injected so a test drives the bound boundary from either side without a real
    clock ever running — production supplies ``time.monotonic``/``time.sleep``, a test
    supplies a fake that advances deterministically on ``sleep``.

    Every invocation ends in one of exactly two calls: ``build_settled_report`` or
    ``build_still_running_report``. There is no third return and no bare ``return``.
    """
    start = now()
    attempt = 0
    while True:
        execution = read_once()
        if _is_settled(execution):
            return build_settled_report(execution, run_handle, lane=lane, **settled_report_kwargs)

        elapsed = now() - start
        if elapsed >= bound_seconds:
            return build_still_running_report(run_handle, elapsed_seconds=elapsed, bound_seconds=bound_seconds)

        wait = backoff_schedule[min(attempt, len(backoff_schedule) - 1)]
        sleep(wait)
        attempt += 1


# =====================================================================================
# Production entry point — wires the poll loop to the real executions API and the real
# clock. The watch performs no write and no dispatch on any path (T-29-14): every read
# below is a GET through executions_client, whose own default transport is
# ``requests.get``.
# =====================================================================================

def _read_once_factory(config, execution_id, transport):
    def _read_once():
        if not execution_id:
            # No candidate was ever found for this dispatch (D-12's correlation came up
            # empty). Reading nothing forever is the honest answer — the watch will
            # report "still running" at the bound rather than guessing a settlement.
            return None
        try:
            return executions_client.get_execution(config, execution_id, transport=transport)
        except executions_client.ExecutionsClientError:
            # A transient read failure is "could not confirm settlement this poll", not
            # "settled" and not "failed" — the loop simply tries again next poll.
            return None
    return _read_once


def watch(config, run_handle, *, lane="enrichment", record_count=None,
          pre_dispatch_balances=None, get_transport=requests.get,
          now=None, sleep=None):
    """One bounded watch, start to finish. Resolves the bound from config (D-05),
    polls the specific execution the run handle names (D-12's fallible correlation),
    and returns whichever of the two terminal reports applies.
    """
    bound_seconds = resolve_bound_seconds(config, record_count)
    execution_id = (run_handle or {}).get("execution_id")
    read_once = _read_once_factory(config, execution_id, get_transport)

    return poll_until_settled(
        read_once, bound_seconds, run_handle,
        now=now or time.monotonic, sleep=sleep or time.sleep,
        lane=lane, pre_dispatch_balances=pre_dispatch_balances, config=config,
        bonus_delivery_available=bonus_delivery_available(config),
    )


# =====================================================================================
# Async recovery (Phase 61 gap-closure, 2026-08-31, operator decision "Option B").
#
# A `mode: "propose"` dispatch (rows describing contacts not yet in HubSpot) needs the
# proposed field VALUES back, not merely a completion signal — that is the one thing
# `run_state.py` was deliberately built NOT to carry (CLAUDE.md §13.0.2: "Progress is
# read by the client... never by n8n"). `async_ack=True` makes the synchronous HTTP
# response an ack only (`{run_id, accepted, row_id}` — `Build Async Ack`,
# `scripts/build_cloud_workflows.py`), which `Build Async Ack` deterministically wins
# ("a single Code node vs. the full chain"), so the proposed values are NOT lost — they
# are simply not on the wire this way. `Build Response` still runs (the "unchanged
# chain" keeps executing after the early ack) and its own output is exactly the
# synchronous body's shape (`ENRICH_BUILD_RESPONSE` returns `{...row, remaining_credits,
# outcome_contract_version, ...}` per item — the same fields `preingest.parse_outcome`/
# `merge_enriched` already read). Reading `Build Response`'s output off the SETTLED
# EXECUTION recovers the identical payload a synchronous call would have returned on
# the wire — proven byte-for-byte by the differential live check in
# `.planning/phases/61-autonomous-batch-runs/61-ASYNC-RECOVERY-VERDICT.json`.
#
# Correlation is EXACT, never a timing guess: `Parse HubSpot Event` normalizes the
# caller's own client-minted `run_id` onto every event (the same idiom `recompute`
# established, CLAUDE.md §13.0/§13.0.2), so an execution is claimed by this run if and
# only if one of its own `Parse HubSpot Event` output items carries this run's `run_id`
# — never `executions_client.find_execution_for_dispatch`'s D-12 time-proximity
# fallback, which this module does not call here.
# =====================================================================================

def _execution_carries_run_id(execution, run_id) -> bool:
    run_data = report._run_data(execution)
    if run_data is None:
        return False
    for item in report_enrichment._first_node_items(run_data, report_enrichment.PARSE_EVENT_NODE):
        body = item.get("json") if isinstance(item, dict) else None
        if isinstance(body, dict) and body.get("run_id") == run_id:
            return True
    return False


def _build_response_rows(execution) -> list:
    """The SAME raw items `Build Response` emits as the synchronous webhook body,
    read from the settled execution instead of the HTTP response — byte-identical
    shape, never a second value channel.

    Reads EVERY run of `Build Response`, not just run 0 (62-11-DIAGNOSIS.md, G-62-6):
    a batch whose rows split at `Merge Winners` (one row needs research, one does not)
    reconverges on `Build Response` as one run per branch, each carrying one item —
    live-confirmed on executions 12096/12098, where a `runs[0]`-only read returned 1
    row against a summed `Build Response` total of 2. `report.all_node_items`
    concatenates every run in order, so both branches' rows come back.
    """
    run_data = report._run_data(execution)
    if run_data is None:
        return []
    items = report.all_node_items(run_data, report_enrichment.BUILD_RESPONSE_NODE)
    return [item["json"] for item in items if isinstance(item, dict) and isinstance(item.get("json"), dict)]


def find_executions_by_run_id(config, run_id, *, workflow_id=None, transport=requests.get,
                               limit=20) -> list:
    """One scan of the enrichment workflow's recent executions — no sleep, no retry of
    its own (the bounded wait lives in `recover_async_dispatch` below). Returns every
    execution whose own `Parse HubSpot Event` output names `run_id` exactly, settled or
    not — the caller decides what to do with an unsettled match.
    """
    if workflow_id is None:
        workflow_id = executions_client.resolve_workflow_id(
            config, transport=transport, workflow_name=scheduled_arm.ENRICHMENT_WORKFLOW_NAME,
        )
    if workflow_id is None:
        return []
    matches = []
    for candidate in executions_client.list_executions(config, workflow_id, transport=transport, limit=limit):
        execution_id = candidate.get("id") if isinstance(candidate, dict) else None
        if execution_id is None:
            continue
        execution = executions_client.get_execution(config, execution_id, transport=transport)
        if _execution_carries_run_id(execution, run_id):
            matches.append(execution)
    return matches


def recover_async_dispatch(config, run_id, expected_chunk_count, *, workflow_id=None,
                            transport=requests.get, now=None, sleep=None,
                            bound_seconds=None, backoff_schedule=BACKOFF_SCHEDULE_SECONDS) -> dict:
    """Waits — bounded, THIS module's own sanctioned poll site — for `expected_chunk_count`
    executions carrying `run_id` to settle, then returns their flattened `Build Response`
    rows: exactly the shape `preingest.merge_enriched` already consumes (one flat list of
    per-row dicts — see `chunking.DispatchOutcome.responses`'s own docstring for why a
    synchronous caller flattens before merging; this recovery path returns pre-flattened,
    since one settled execution's `Build Response` output already IS one chunk's rows).

    Never falls back to `executions_client.find_execution_for_dispatch`'s time-proximity
    correlation — a miss here is reported as `recovered: False`, not guessed.

    `{"recovered": True, "responses": [...], "matched_executions": N}` on success;
    `{"recovered": False, "responses": [], "matched_executions": N, "elapsed_seconds",
    "bound_seconds"}` when the bound elapses first — the caller (the skill) is expected
    to tell the operator this run is still going and offer to call this again with the
    SAME `run_id`, never to re-dispatch (that would send the same rows twice).
    """
    _now = now or time.monotonic
    _sleep = sleep or time.sleep
    bound = bound_seconds if bound_seconds is not None else DEFAULT_BOUND_SECONDS
    start = _now()
    attempt = 0
    while True:
        executions = find_executions_by_run_id(config, run_id, workflow_id=workflow_id, transport=transport)
        settled = [e for e in executions if _is_settled(e)]
        if len(settled) >= expected_chunk_count:
            responses = []
            for execution in settled:
                responses.extend(_build_response_rows(execution))
            return {"recovered": True, "responses": responses, "matched_executions": len(settled)}

        elapsed = _now() - start
        if elapsed >= bound:
            return {
                "recovered": False, "responses": [], "matched_executions": len(settled),
                "elapsed_seconds": elapsed, "bound_seconds": bound,
            }
        wait = backoff_schedule[min(attempt, len(backoff_schedule) - 1)]
        _sleep(wait)
        attempt += 1


# =====================================================================================
# Resume or fail loudly (Phase 61 Plan 05 Task 3, RUN-03, REVIEW-08/C15) — the
# REPORT-path half of "two consumers, two rules over one load". `run_manifest.py`
# itself is untouched: `load()`, `save()`, and `rows_to_resume` all stay exactly as they
# are, and the RESUME path (whatever calls `rows_to_resume` directly) keeps trusting
# `load()`'s existing degrade-to-`{}` behaviour unmodified — a raise there would strand
# a whole batch on one corrupt byte, which `run_manifest.load()`'s own module docstring
# already explains is the wrong trade (degrading to a full run costs money; degrading to
# a partial skip costs a contact).
#
# What is new here is the REPORT path: before trusting `rows_to_resume`'s result at
# all, classify the manifest FILE ITSELF — never `load()`'s return value, which
# collapses "never registered", "corrupted", and "a real, honest empty map" to the same
# `{}` by design. A classification this module could not confirm safe (ANOMALOUS or
# WRONG_RUN) takes the identical full-rerun path ABSENT would, but says a different,
# specific sentence — never presenting a corrupted or foreign-run state as a fresh first
# run (REVIEW-C15's resolved wording: full rerun, loudly disclosed, never a partial
# trust and never silently indistinguishable from "nothing has ever run here before").
# =====================================================================================

ABSENT = "absent"
PARSEABLE = "parseable"
ANOMALOUS = "anomalous"
WRONG_RUN = "wrong_run"


def classify_manifest_read(path=None, expected_run_id=None) -> str:
    """What a `run_manifest.py`-shaped file at `path` looks like, from a fresh probe —
    never raises. Mirrors `run_state.classify_read`'s own three-way reasoning
    (re-implemented here, not imported — this plugin's own precedent, see
    `run_state.py`'s forbidden-name-list comment, for why a shared predicate is
    duplicated rather than imported: a future change to one file's parsing must not
    silently change what this one enforces), plus a fourth answer 61-04's
    `load_scoped(expected_run_id=...)` already makes possible: `WRONG_RUN`, when the
    document is perfectly readable but stamped with someone else's run id.

    `PARSEABLE` is checked with the SAME schema `run_manifest.load()` itself enforces
    (dict document, a `verdicts` dict, every entry a string key mapped to one of
    `run_manifest.ALLOWED_VERDICTS`) — walked directly here rather than inferred from
    `load()`'s return, because `load()` returns `{}` for BOTH a corrupted file and a
    real, legitimately empty verdict map (a run registered but with no chunk dispatched
    yet), and those two must never classify the same way.
    """
    target = Path(path) if path is not None else run_manifest.manifest_path()
    if not target.exists():
        return ABSENT

    if expected_run_id is not None:
        scoped = run_manifest.load_scoped(path=target, expected_run_id=expected_run_id)
        if scoped.mismatch:
            return WRONG_RUN

    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ANOMALOUS
    if not isinstance(raw, dict):
        return ANOMALOUS
    verdicts = raw.get(run_manifest.VERDICTS_FIELD)
    if not isinstance(verdicts, dict):
        return ANOMALOUS
    for row_id, verdict in verdicts.items():
        if not isinstance(row_id, str) or verdict not in run_manifest.ALLOWED_VERDICTS:
            return ANOMALOUS
    return PARSEABLE


@dataclass(frozen=True)
class ResumeReport:
    """One resume decision, from the report side of REVIEW-08's split. `rows` is
    exactly what `run_manifest.rows_to_resume` returns for the one classification
    (`PARSEABLE`, and matching `expected_run_id` when one was given) that is safe to
    trust; for every other classification it is every row handed in, unmodified —
    `ABSENT`/`ANOMALOUS`/`WRONG_RUN` are all a full rerun, because none of them is
    trustworthy enough to skip a single row from. `disclosure` is ONE of exactly four
    fixed sentences, chosen by `classification` alone."""

    classification: str
    rows: tuple
    skipped: tuple
    still_held: tuple
    disclosure: str


def resume_or_disclose(rows, *, path=None, expected_run_id=None,
                        held_entries=None, current_outcomes=None) -> ResumeReport:
    """Classify the manifest first, THEN decide whether `run_manifest.rows_to_resume`'s
    result is safe to act on. `held_entries`/`current_outcomes` pass straight through to
    `rows_to_resume` for the `confidence_held` fingerprint comparison — see that
    function's own docstring; both default to `None` exactly as it does.
    """
    total = len(rows)
    classification = classify_manifest_read(path=path, expected_run_id=expected_run_id)

    if classification == PARSEABLE:
        manifest = run_manifest.load(path=path)
        result = run_manifest.rows_to_resume(
            rows, manifest, held_entries=held_entries, current_outcomes=current_outcomes,
        )
        disclosure = (
            f"resuming — {len(result.skipped)} of {total} already done, "
            f"{len(result.rows)} to go"
        )
        return ResumeReport(classification=classification, rows=result.rows,
                             skipped=result.skipped, still_held=result.still_held,
                             disclosure=disclosure)

    if classification == ABSENT:
        disclosure = f"no previous state — running all {total} rows"
    elif classification == WRONG_RUN:
        disclosure = (
            f"previous state belongs to a different run — rerunning all {total} rows, "
            "nothing was skipped"
        )
    else:  # ANOMALOUS
        disclosure = (
            f"previous state unreadable — rerunning all {total} rows, nothing was skipped"
        )

    return ResumeReport(classification=classification, rows=tuple(rows),
                         skipped=(), still_held=(), disclosure=disclosure)


def build_resume_completion_report(resume_report, this_pass_verdicts) -> dict:
    """The FINAL report once a resumed run's own dispatched rows have settled:
    distinguishes rows completed in THIS pass (`this_pass_verdicts`, this run's own
    fresh verdicts) from rows already complete when the run started
    (`resume_report.skipped`) — the plan's own `<behavior>` line. Merging the two into
    one count would make a resume indistinguishable from a run that started fresh and
    got lucky.
    """
    completed_this_pass = sum(
        1 for v in this_pass_verdicts.values()
        if v in (run_manifest.MATCHED, run_manifest.ENRICHED)
    )
    return {
        "disclosure": resume_report.disclosure,
        "already_done_before_this_pass": len(resume_report.skipped),
        "completed_this_pass": completed_this_pass,
        "still_held": len(resume_report.still_held),
    }
