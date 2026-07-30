"""operator-claude-plugin/scripts/report_enrichment.py

The enrichment lane's half of the outcome report (REPORT-02, as amended by
26-CONTEXT.md D-10a/D-10b). Per record: the operator-facing outcome (created /
enriched / blocked / skipped), the review-state (needs_review / clear / unknown —
NEVER inferred false when the backend is silent), and the provider-credit ledger
from the response body. Nothing about ICP anywhere — HubSpot owns those derived
outputs (Phase 15 "Approach C"; see src/merge_policy.py, n8n/code/mergeCompanies.js,
config/field_policy.yaml) and a placeholder here would re-couple exactly what that
decision decoupled.

Reuses report.py's `_run_data`/`_node_output_items` traversal (26-01) rather than a
second implementation of the same `data.resultData.runData` walk — same defensive
contract: a missing key, a non-list run entry, or a non-mapping payload yields an
empty/insufficient result plus a stated reason, never an exception.
"""

from report import SETTLED_STATUSES, SMALL_BATCH_THRESHOLD, _node_output_items, _run_data

# The enrichment workflow runs one or both lanes in a single execution (a batch can
# carry both company and contact events) — read whichever of these are present,
# never just the first one found (unlike the contact-ingest workflow, which only
# ever has one). Both deployed workflows contain a node literally named
# "Decide Action"; within an ENRICHMENT execution it is always the contact lane,
# because the company lane's is named "Decide Company Action" instead (D-11c).
DECIDE_COMPANY_ACTION_NODE = "Decide Company Action"
DECIDE_CONTACT_ACTION_NODE = "Decide Action"
BUILD_RESPONSE_NODE = "Build Response"
PARSE_EVENT_NODE = "Parse HubSpot Event"

# The four values the deployed decision nodes emit (write_blocked comes from the
# write-safety gate refusing a create/enrich, computed downstream of the original
# create/enrich/skip intent — see Enrichment Gate / Company Gate). Anything else is
# an anomaly this module has never seen and renders "unknown" — conservative, same
# "never guess a success" discipline Phase 25 D-10 applies to credit balances.
_ACTION_TO_OUTCOME = {
    "create": "created",
    "enrich": "enriched",
    "write_blocked": "blocked",
    "skip": "skipped",
}
SUCCESS_OUTCOMES = {"created", "enriched"}

# Neither decision node's return statement carries a per-row "why" for write_blocked
# or skip (they strip everything upstream except action/object_type/hs_object_id/
# gap_flag/(needs_review)/properties) — these are the accurate, static explanations
# of what each outcome means, read from the node's own jsCode.
_OUTCOME_REASON = {
    "blocked": "the write-safety gate did not allow this write "
               "(ALLOW_HUBSPOT_RECORD_WRITES / ALLOW_HUBSPOT_CREATE / the test-record allowlist)",
    "skipped": "no enrichment needed: required fields were present, fresh and valid",
}

_ACTION_LANE_ORDER = (("companies", DECIDE_COMPANY_ACTION_NODE), ("contacts", DECIDE_CONTACT_ACTION_NODE))


def _empty_counts():
    return {"created": 0, "enriched": 0, "blocked": 0, "skipped": 0, "unknown": 0}


def _empty_review_counts():
    return {"needs_review": 0, "clear": 0, "unknown": 0}


# =====================================================================================
# Reading the decision nodes (Pattern 1) — never the terminal write nodes.
# =====================================================================================

def enrichment_row_ledger(execution):
    """Per-record ledger for `hubspot/enrichment`, read from `Decide Company Action`
    and/or `Decide Action`'s own output — never a terminal write node. Both lanes are
    read when both are present (one enrichment batch can carry both object types);
    each row is tagged with its own `_lane` so the review-flag rule below can never
    mistake one lane's row for the other's (D-11a/key_links).

    Returns `(ledger, reason)`. `reason` is `None` on success; when neither decision
    node ran, `ledger` is `[]` and `reason` names what was missing — never an
    exception, never a partial guess.
    """
    run_data = _run_data(execution)
    if run_data is None:
        return [], "execution payload has no readable data.resultData.runData"

    ledger = []
    for lane, node_name in _ACTION_LANE_ORDER:
        runs = run_data.get(node_name)
        first_run = runs[0] if isinstance(runs, list) and runs else None
        if not isinstance(first_run, dict):
            continue
        for item in _node_output_items(first_run):
            if isinstance(item, dict) and isinstance(item.get("json"), dict):
                ledger.append({**item["json"], "_lane": lane})

    if not ledger:
        return [], (
            f"neither '{DECIDE_COMPANY_ACTION_NODE}' nor '{DECIDE_CONTACT_ACTION_NODE}' "
            "ran or is present in this execution"
        )
    return ledger, None


def _outcome_for_row(row):
    return _ACTION_TO_OUTCOME.get(row.get("action"), "unknown")


def _review_state_for_row(row):
    """The company decision node emits a top-level `needs_review` boolean derived
    from its merge decisions; the contact one emits no such field at all (D-11a,
    key_links). An absent flag is unknown — never inferred false, the same rule
    Phase 25 D-10 sets for an unreadable credit balance."""
    if row.get("_lane") != "companies":
        return "unknown"

    flag = row.get("needs_review")
    if isinstance(flag, bool):
        return "needs_review" if flag else "clear"

    # Defensive fallback: the properties patch itself carries the same signal
    # (`lv_enrichment_needs_review`) whenever the top-level field is missing.
    properties = row.get("properties")
    if isinstance(properties, dict) and "lv_enrichment_needs_review" in properties:
        return "needs_review" if properties.get("lv_enrichment_needs_review") else "clear"

    return "unknown"


def _row_identity(row, row_number):
    return row.get("hs_object_id") or f"row {row_number}"


def _build_row_report(row, row_number):
    outcome = _outcome_for_row(row)
    return {
        "row_number": row_number,
        "_identity": _row_identity(row, row_number),
        "lane": row.get("_lane"),
        "outcome": outcome,
        "review_state": _review_state_for_row(row),
        "reason": _OUTCOME_REASON.get(outcome),
    }


# =====================================================================================
# Provider credits (D-10) — read from `Build Response`'s own output, never a live call.
# =====================================================================================

def _first_node_items(run_data, node_name):
    runs = run_data.get(node_name)
    first_run = runs[0] if isinstance(runs, list) and runs else None
    if not isinstance(first_run, dict):
        return []
    return _node_output_items(first_run)


def remaining_credits_from_response(execution):
    """Provider credit balances from `Build Response`'s own `remaining_credits`
    list — appended AFTER the decision nodes, so this reads a different node than
    `enrichment_row_ledger()` does (key_links). Returns `{provider: value}` where
    `value` is either the real balance (a genuine 0 included) or the literal string
    `"unknown"` — unknown and zero must never collapse into the same rendered state
    (Phase 25 D-10, T-26-07). The client never queries a provider itself; every
    figure here already came back on the enrichment response.

    When `Build Response` carries no `remaining_credits` block at all (node absent,
    empty run, or the key missing), every provider named in `Parse HubSpot Event`'s
    own `providers_requested` is still rendered, each `"unknown"` — a missing
    balance must stay visible, never silently omitted.
    """
    run_data = _run_data(execution)
    if run_data is None:
        return {}

    build_response_items = _first_node_items(run_data, BUILD_RESPONSE_NODE)
    if build_response_items:
        first_json = build_response_items[0].get("json")
        credits_list = first_json.get("remaining_credits") if isinstance(first_json, dict) else None
        if isinstance(credits_list, list):
            return {
                entry["provider"]: entry.get("credits") if isinstance(entry.get("credits"), (int, float)) else "unknown"
                for entry in credits_list
                if isinstance(entry, dict) and entry.get("provider")
            }

    parse_event_items = _first_node_items(run_data, PARSE_EVENT_NODE)
    if parse_event_items:
        first_json = parse_event_items[0].get("json")
        requested = first_json.get("providers_requested") if isinstance(first_json, dict) else None
        if isinstance(requested, list):
            return {provider: "unknown" for provider in requested if provider}

    return {}


# =====================================================================================
# Shaping the report object — same shape as report.py's build_contact_report (D-08/
# D-09), so one renderer serves both lanes. NO ICP field anywhere (D-10a/D-10b).
# =====================================================================================

def build_enrichment_report(execution, handle=None):
    """Shapes an already-fetched enrichment execution into the report object the
    skill renders. Never raises: a missing/malformed execution yields a report
    whose `state` is `"unknown"` with the handle intact, rather than a guess — the
    same contract `report.build_contact_report()` holds.
    """
    if not isinstance(execution, dict):
        return {
            "source": "executions_api",
            "state": "unknown",
            "reason": "the execution could not be fetched (pruned run, or not found)",
            "counts": _empty_counts(),
            "review_counts": _empty_review_counts(),
            "total": 0,
            "rows": [],
            "failing_rows": [],
            "credits": {},
            "adaptive": False,
            "handle": handle,
        }

    state = "finished" if execution.get("status") in SETTLED_STATUSES else "in_flight"

    ledger, reason = enrichment_row_ledger(execution)
    counts = _empty_counts()
    review_counts = _empty_review_counts()
    rows = []
    for i, row in enumerate(ledger, start=1):
        report_row = _build_row_report(row, i)
        counts[report_row["outcome"]] += 1
        review_counts[report_row["review_state"]] += 1
        rows.append(report_row)

    failing_rows = [
        row for row in rows
        if row["outcome"] not in SUCCESS_OUTCOMES or row["review_state"] == "needs_review"
    ]
    total = len(rows)
    adaptive = total > SMALL_BATCH_THRESHOLD

    return {
        "source": "executions_api",
        "state": state,
        "reason": reason,
        "counts": counts,
        "review_counts": review_counts,
        "total": total,
        "rows": rows if not adaptive else None,
        "failing_rows": failing_rows,
        "credits": remaining_credits_from_response(execution),
        "adaptive": adaptive,
        "handle": handle,
    }
