"""operator-claude-plugin/scripts/report.py

Turns a contact-upload dispatch result into a per-record ledger the operator can act
on: `contact_row_ledger()` reads the decision node's own output (never a terminal
node), `reconcile()` refuses to claim a write that never landed, and
`build_contact_report()` shapes the result into one report object — counts first, the
failing rows in full, an honest in-flight/unknown state, and the run handle. The
skill (SKILL.md) owns wording; this module only returns data.

Every entry point here is pure and defensive: a missing key, a non-list run entry, or
a non-mapping payload yields an empty/insufficient result plus a stated reason, never
an exception and never a partial guess — mirroring
scripts/enrichment_cost_ledger.py's `_node_output_items` idiom.
"""

# `Decide Action` runs upstream of `Set Review` (an Edit-Fields node whose sole
# assignment is `queue`, dropping every other field per n8n's default Set-node
# behavior) and of the terminal write nodes — it is the one point in the pipeline
# where every row's action, outcome, identity and reason are all still present
# together (D-11).
DECIDE_ACTION_NODE = "Decide Action"

# The terminal write node whose own output confirms (or refutes) a decided
# update/create actually reached HubSpot (Pitfall 3 / T-26-01).
WRITE_NODE_FOR_ACTION = {"update": "HubSpot Update", "create": "HubSpot Create"}

# A `Decide Action` execution status outside this set (including one that is absent
# or unrecognised) is never rendered as finished — the same "unknown is not zero/
# success" discipline Phase 25 D-10 applies to credit balances.
SETTLED_STATUSES = {"success", "error", "crashed", "canceled"}

_ACTION_TO_LABEL = {
    "create": "created",
    "update": "updated_matched",
    "review": "needs_review",
    "skip": "rejected",
    "not_confirmed": "not_confirmed",
}
SUCCESS_LABELS = {"created", "updated_matched"}

# Phase 23 D-08's own adaptive-display threshold — one convention across preview and
# report (D-09).
SMALL_BATCH_THRESHOLD = 20


# =====================================================================================
# Reading the decision node (Pattern 1) — never the terminal nodes.
# =====================================================================================

def _run_data(execution):
    if not isinstance(execution, dict):
        return None
    data = execution.get("data")
    if not isinstance(data, dict):
        return None
    result_data = data.get("resultData")
    if not isinstance(result_data, dict):
        return None
    run_data = result_data.get("runData")
    if not isinstance(run_data, dict):
        return None
    return run_data


def _node_output_items(run):
    """A single NodeRun's output items (`data.main[0]`) — defensive against any shape
    mismatch: never raises, returns [] on anything unexpected. Mirrors
    scripts/enrichment_cost_ledger.py's `_node_output_items`."""
    if not isinstance(run, dict):
        return []
    data = run.get("data")
    if not isinstance(data, dict):
        return []
    main = data.get("main")
    if not isinstance(main, list) or not main:
        return []
    branch = main[0]
    return branch if isinstance(branch, list) else []


def contact_row_ledger(execution):
    """Authoritative per-row outcome for `hubspot/contact-upload`, read from
    `Decide Action`'s own output — NOT `Set Review`, `HubSpot Update` or
    `HubSpot Create`. `Set Review` outputs only `{"queue": "needs_review"}` per row
    (n8n's Edit-Fields default keeps only explicitly-set fields), so a report built
    from it cannot tell two rows apart (D-11).

    Returns `(ledger, reason)`. `reason` is `None` on success; on any missing/
    malformed shape, `ledger` is `[]` and `reason` names what was missing — never an
    exception, never a partial guess.
    """
    run_data = _run_data(execution)
    if run_data is None:
        return [], "execution payload has no readable data.resultData.runData"

    runs = run_data.get(DECIDE_ACTION_NODE)
    if not isinstance(runs, list) or not runs:
        return [], f"'{DECIDE_ACTION_NODE}' node did not run or is absent from this execution"

    first_run = runs[0]
    if not isinstance(first_run, dict):
        return [], f"'{DECIDE_ACTION_NODE}' run entry is not a mapping"

    items = _node_output_items(first_run)
    ledger = [
        item["json"] for item in items
        if isinstance(item, dict) and isinstance(item.get("json"), dict)
    ]
    return ledger, None


# =====================================================================================
# Reconciling "decided" against "written" (Pattern 2 / Pitfall 3 / T-26-01).
# =====================================================================================

def _write_node_produced_output(run_data, node_name):
    runs = run_data.get(node_name)
    first_run = runs[0] if isinstance(runs, list) and runs else None
    if first_run is None:
        # Absent entirely: the write-safety gate filtered every row before the write
        # node ever ran. Same conclusion as "ran with zero items" — never confirmed.
        return False
    return len(_node_output_items(first_run)) > 0


def reconcile(ledger, run_data):
    """`Decide Action`'s `action` is an intent computed before the downstream
    write-safety gate, not a completed fact (Pitfall 3). For each row whose intent
    was update or create, cross-reference the corresponding terminal node's own run —
    only report the success label when that node actually produced output items.
    When it produced none, downgrade to `not_confirmed` rather than asserting a write
    that never landed (T-26-01) — the conservative direction is the only safe one.

    Returns a new list of row dicts, each carrying a `reported_outcome` key alongside
    every field `Decide Action` already supplied.
    """
    if not isinstance(run_data, dict):
        run_data = {}

    write_produced = {
        action: _write_node_produced_output(run_data, node_name)
        for action, node_name in WRITE_NODE_FOR_ACTION.items()
    }

    reconciled = []
    for row in ledger:
        if not isinstance(row, dict):
            continue
        entry = dict(row)
        action = entry.get("action")
        if action in WRITE_NODE_FOR_ACTION and not write_produced[action]:
            entry["reported_outcome"] = "not_confirmed"
            entry["reason"] = (
                entry.get("reason")
                or "the write was gated or filtered before it reached HubSpot — not confirmed written"
            )
        else:
            entry["reported_outcome"] = action
        reconciled.append(entry)
    return reconciled


def _label_for_row(row):
    outcome = row.get("reported_outcome") or row.get("action")
    # An outcome this module doesn't recognise is never rendered as a success —
    # conservative default, same discipline as an unknown execution status.
    return _ACTION_TO_LABEL.get(outcome, "needs_review")


def _row_identity(row, row_number):
    return row.get("contact_id") or row.get("hs_object_id") or f"row {row_number}"


def _empty_counts():
    return {"created": 0, "updated_matched": 0, "needs_review": 0, "rejected": 0, "not_confirmed": 0}


def _group_rejected_reasons(failing_rows):
    """Groups failing rows sharing an identical `reason` string, so a batch that
    failed for one systemic cause reads as one finding with a count rather than as
    many identical lines. Rows with no reason at all are grouped under a stated
    placeholder rather than silently dropped."""
    groups: dict = {}
    for row in failing_rows:
        reason = row.get("reason") or "(no reason recorded)"
        groups.setdefault(reason, {"reason": reason, "count": 0, "rows": []})
        groups[reason]["count"] += 1
        groups[reason]["rows"].append(row.get("_identity"))
    return sorted(groups.values(), key=lambda g: g["count"], reverse=True)


# =====================================================================================
# Sufficiency of the synchronous webhook body (D-01's first leg).
# =====================================================================================

def sync_response_is_sufficient(body) -> bool:
    """The synchronous webhook body is used only when it can actually identify rows.
    A body is sufficient when every item carries a row-identifying key (a contact id,
    a HubSpot object id, an email) or is a full HubSpot object with both an `id` and
    a `properties` map. A body whose items carry only the review queue marker
    (`Set Review`'s own output, `{"queue": "needs_review"}`) is insufficient by
    construction (D-11, Pitfall 1) — the caller falls through to the executions-API
    path rather than rendering an unusable report. Empty bodies, scalars and
    non-mapping items are all insufficient.
    """
    if body is None:
        return False
    items = body if isinstance(body, list) else [body]
    if not items:
        return False
    for item in items:
        if not isinstance(item, dict):
            return False
        has_identity = any(k in item for k in ("contact_id", "hs_object_id", "email"))
        has_hubspot_object = "id" in item and "properties" in item
        if not (has_identity or has_hubspot_object):
            return False
    return True


# =====================================================================================
# Shaping the report object — one shape, one renderer (D-08/D-09).
# =====================================================================================

def build_contact_report(execution, handle):
    """Shapes an already-fetched execution into the report object the skill renders.
    Never raises: a missing execution (a pruned run, a 404 the caller already turned
    into `None`) yields a report whose `state` is explicitly `"unknown"` with the
    handle intact, rather than a guess.

    Any execution status outside `SETTLED_STATUSES` — including one that is absent
    or unrecognised — renders `state="in_flight"`. Unknown is never rendered as
    finished (the same discipline Phase 25 D-10 applies to credit balances).
    """
    if not isinstance(execution, dict):
        return {
            "source": "executions_api",
            "state": "unknown",
            "reason": "the execution could not be fetched (pruned run, or not found)",
            "counts": _empty_counts(),
            "total": 0,
            "rows": [],
            "failing_rows": [],
            "reason_groups": [],
            "adaptive": False,
            "handle": handle,
        }

    state = "finished" if execution.get("status") in SETTLED_STATUSES else "in_flight"

    ledger, ledger_reason = contact_row_ledger(execution)
    run_data = _run_data(execution) or {}
    reconciled = reconcile(ledger, run_data)

    counts = _empty_counts()
    rows = []
    for i, row in enumerate(reconciled, start=1):
        identity = _row_identity(row, i)
        label = _label_for_row(row)
        counts[label] += 1
        rows.append({**row, "row_number": i, "_identity": identity, "reported_label": label})

    for row in rows:
        state_for_row = classify_retryability(row)
        row["retryability"] = state_for_row
        row["retry_reason"] = _retry_reason(state_for_row)

    failing_rows = [row for row in rows if row["reported_label"] not in SUCCESS_LABELS]
    total = len(rows)
    adaptive = total > SMALL_BATCH_THRESHOLD

    return {
        "source": "executions_api",
        "state": state,
        "reason": ledger_reason,
        "counts": counts,
        "total": total,
        # Full ledger only for a small batch (D-08/D-09) — a large batch shows the
        # counts plus the full failing subset, never every successful row.
        "rows": rows if not adaptive else None,
        "failing_rows": failing_rows,
        "reason_groups": _group_rejected_reasons(failing_rows),
        # The re-sendable set (DISPATCH-04): only rows a re-send can actually fix.
        # Permanently-stuck and business-outcome rows are named in failing_rows but
        # deliberately excluded here.
        "resendable_rows": [row for row in failing_rows if row["retryability"] == "transport_failure"],
        "adaptive": adaptive,
        "handle": handle,
    }


# =====================================================================================
# Retryability classification (DISPATCH-04) — what a re-send can actually fix.
#
# Four states, matching the plan's own naming:
#   - nothing_to_retry:  the row already landed (created / updated-matched).
#   - transport_failure: the row's action was decided but never confirmed written —
#     the same shape as Phase 25's failed-chunk unit (a send that never got a
#     response, or came back with a server error). Re-sending is safe and may fix it.
#   - permanently_stuck: no usable email + an ambiguous identity outcome (D-11b/D-14).
#     The deployed workflow resolves identity by email only, so this row lands in
#     review on every attempt no matter how many times it is re-sent.
#   - business_outcome:  the row reached a decision (review/reject) for any other
#     reason. Re-sending it unchanged reproduces the identical outcome.
# =====================================================================================

_RETRY_REASONS = {
    "nothing_to_retry": None,
    "transport_failure": (
        "this row's write was never confirmed to reach HubSpot — safe to re-send unchanged"
    ),
    "permanently_stuck": (
        "this row will reach review on every attempt — the deployed workflow resolves "
        "identity by email only, so it needs an email address or manual handling in "
        "HubSpot, not a re-send"
    ),
    "business_outcome": "re-sending this row unchanged will reproduce the same outcome",
}


def _retry_reason(state):
    return _RETRY_REASONS.get(state)


def classify_retryability(row):
    """Classifies a single ledger row (raw from `contact_row_ledger()`, or already
    shaped by `build_contact_report()`) into one of the four retryability states
    above. Never raises: a row missing any field this reads still gets a state,
    matching every other function in this module.
    """
    if not isinstance(row, dict):
        return "business_outcome"

    label = row.get("reported_label") or _label_for_row(row)

    if label in SUCCESS_LABELS:
        return "nothing_to_retry"
    if label == "not_confirmed":
        return "transport_failure"
    if row.get("email_status") == "NO_EMAIL" and row.get("outcome") == "ambiguous":
        return "permanently_stuck"
    return "business_outcome"
