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
import time

import requests

import executions_client
import report
import report_enrichment

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
