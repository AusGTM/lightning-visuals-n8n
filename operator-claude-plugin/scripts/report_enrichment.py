"""operator-claude-plugin/scripts/report_enrichment.py

The enrichment lane's half of the outcome report (REPORT-02, as amended by
26-CONTEXT.md D-10a/D-10b, and by 57-02 which collapses this module's outcome
vocabulary onto `written_records`'s — see below). Per record: the operator-facing
outcome, the review-state (needs_review / clear / unknown — NEVER inferred false when
the backend is silent), and the provider-credit ledger from the response body. Nothing
about ICP anywhere — HubSpot owns those derived outputs (Phase 15 "Approach C"; see
src/merge_policy.py, n8n/code/mergeCompanies.js, config/field_policy.yaml) and a
placeholder here would re-couple exactly what that decision decoupled.

Reuses report.py's `_run_data`/`_node_output_items` traversal (26-01) rather than a
second implementation of the same `data.resultData.runData` walk — same defensive
contract: a missing key, a non-list run entry, or a non-mapping payload yields an
empty/insufficient result plus a stated reason, never an exception.

**57-02: one action-to-outcome vocabulary, not two (D-57-03, REVIEW-57).** This module
used to keep its own private action-to-outcome table, covering only 6 of the backend's
10 real `action` values (`update`, `review`, `research_failed` and `recompute_refused`
all rendered `"unknown"`, uncovered by any test) and using different words for the same
concepts `written_records.py` names (`"blocked"` where D-57-03 says `gated`). Leaving
two tables to drift is not an option here — CLAUDE.md section 13.0.1 records what a
second copy of one rule costs. `_outcome_for_row` now delegates to
`written_records.outcome_for_action`, the single pure vocabulary both client-side
readers resolve through.

It delegates to that pure function, **never to `written_records`'s validating entry
builder** — cross-AI review caught why: the entry builder raises `WrittenRecordsError`
for a malformed item and for a forbidden-named value (`written_records.py:100-115`,
`:150-190`), while `build_enrichment_report` promises never to raise (see its own
docstring below). Delegating to the validating builder would import persistence
validation into a never-raise report surface and turn a malformed row into a report
that fails instead of a report that says the row was malformed.
`written_records.outcome_for_action` is pure and total by construction, so this module
reuses it with no such risk.
"""

import written_records
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

# 57-02: this module's own action-to-outcome table is gone (D-57-03) — see the module
# docstring. `SUCCESS_OUTCOMES` is the "landed, or nothing left to do" set: a write the
# backend was allowed to make is not a failing row, even though it is not yet CONFIRMED
# landed (that is what the word itself, not the bucket, is for). `created_id_unknown`
# and `written_id_unknown` are deliberately NOT in this set — an id that never came back
# is a row worth a second look, not a clean success.
SUCCESS_OUTCOMES = {
    written_records.WRITTEN, written_records.WRITE_ATTEMPTED, written_records.NO_ACTION,
}

# Neither decision node's return statement carries a per-row "why" for write_blocked
# or skip (they strip everything upstream except action/object_type/hs_object_id/
# gap_flag/(needs_review)/properties) — these are the accurate, static explanations
# of what each outcome means, read from the node's own jsCode. Keyed by OUTCOME (the
# same convention this table always used), not by the backend `action` — `held` covers
# both `review` and `needs_match_review` for the same reason it always covered
# `needs_match_review` alone, and `no_action` covers both `skip` and `proposed`.
_OUTCOME_REASON = {
    written_records.GATED:
        "this row would have been written — open a grant and re-send it to write it "
        "(ALLOW_HUBSPOT_RECORD_WRITES / ALLOW_HUBSPOT_CREATE / the test-record allowlist "
        "did not allow this write)",
    # Phase 54-02 (T-54-05/T-54-06): the two-pass shapes that still cost a second full
    # pass — named where the operator reads the result, not just in the skill that
    # requests it. Generalised in 57-02 to cover `review` as well as `needs_match_review`
    # — a same-surname/company match is one reason a row lands here, not the only one.
    written_records.HELD:
        "this row was held for review before writing — a same-surname/company match, "
        "an unresolved company association, or another gap the decision node flagged. "
        "Confirming it and sending it again re-runs the whole lookup for that row, so "
        "it costs the same as this run did",
    written_records.NO_ACTION:
        "no action was needed on this row: either it was a look-only preview and "
        "nothing was saved (saving it means running the same look again, at the same "
        "cost as this run), or the record already had complete, fresh, valid data and "
        "needed no enrichment",
    written_records.FAILED:
        "this action failed, was refused, or is an outcome this module has never seen "
        "before — retry it, or fix the input",
    written_records.WRITE_ATTEMPTED:
        "the write was permitted and attempted, but the id was already known before "
        "the write and proves nothing about whether it landed — spot-check this "
        "record if it matters",
    written_records.CREATED_ID_UNKNOWN:
        "the record was likely created, but the response carried no id to confirm it; "
        "the id is unrecoverable and is never fabricated",
    written_records.WRITTEN_ID_UNKNOWN:
        "the write was permitted and attempted, and the response carried no id either "
        "— open this row's record and confirm",
}

_ACTION_LANE_ORDER = (("companies", DECIDE_COMPANY_ACTION_NODE), ("contacts", DECIDE_CONTACT_ACTION_NODE))


def _empty_counts():
    """Keyed on `written_records.ALL_OUTCOMES` — derived, never restated, so this
    follows Task 1's checkpoint selection automatically (57-02)."""
    return {outcome: 0 for outcome in written_records.ALL_OUTCOMES}


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
    """Delegates to `written_records.outcome_for_action` — the one pure, total,
    never-raising vocabulary both client-side readers resolve through (57-02, D-57-03).
    NEVER `written_records`'s validating entry builder: that raises for a malformed item
    and for a forbidden-named value, and this module's `build_enrichment_report`
    promises never to raise (see its own docstring)."""
    return written_records.outcome_for_action(row.get("action"), row.get("hs_object_id"))


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


# `match` (matchProposal.js's `summarizeMatch`) is a SEPARATE fact from `action`: it says
# how the row's identity was resolved (an exact hit, a same-surname-and-company proposal,
# no hit, or "could not look"), independent of whether the write-safety gate then allowed
# the write. Surfacing it is F3's other half — the 2026-08-25 walk's body carried
# `match.reason: "searched, no hit"` alongside `action: "write_blocked"` and neither
# reached the operator. The dict key is `match_level`, never `match_tier` — this module's
# own report is scanned by `test_built_report_object_carries_no_icp_trace_anywhere` for
# the literal substring "tier" (an ICP-scoping guard, D-10a/D-10b), and `match_tier` would
# trip a ban that has nothing to do with ICP scoring. `summarizeMatch`'s own field is still
# named `tier` in the n8n code this reads from; only the PYTHON key changes name.
def _match_info_for_row(row):
    match = row.get("match")
    if not isinstance(match, dict):
        return None, None
    return match.get("tier"), match.get("reason")


def _build_row_report(row, row_number):
    outcome = _outcome_for_row(row)
    match_level, match_reason = _match_info_for_row(row)
    return {
        "row_number": row_number,
        "_identity": _row_identity(row, row_number),
        "lane": row.get("_lane"),
        # 57-02: the raw backend action, alongside the outcome word — counts are by
        # outcome, but a renderer still needs to say how many written rows were
        # creates versus enriches.
        "action": row.get("action"),
        "outcome": outcome,
        "review_state": _review_state_for_row(row),
        "reason": _OUTCOME_REASON.get(outcome),
        "match_level": match_level,
        "match_reason": match_reason,
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
# build_sync_report (F3, 2026-08-25) — the SYNCHRONOUS webhook body, read the same way
# enrichment_row_ledger() reads the executions API, so a chunk's own response can be
# relayed honestly without a second fetch and without a lane skill re-deriving the
# write_blocked -> "blocked" mapping in prose. The 2026-08-25 walk's defect was never
# that this mapping was missing (it existed here, unused) — it was that
# `skills/enrich-records/SKILL.md` step 8 never called anything that read the body's
# `action`/`match` fields at all, and its own "do not claim per-record outcomes" rule
# (written to stop the client INVENTING outcomes) was read broadly enough to suppress a
# RECEIVED one instead.
# =====================================================================================

def build_sync_report(body):
    """Shape one chunk's synchronous webhook body — `chunking.DispatchOutcome.responses`
    already carries these, one per chunk that reached the backend — into the same
    outcome/reason/match shape `_build_row_report` computes from the executions API.

    `body` is whatever `enrichment.dispatch_enrichment` returned for that chunk: normally
    a JSON array (n8n's `respondWith: allIncomingItems` on "Respond to Webhook" — ONE item
    per row in the chunk, each carrying the same action/match/hs_object_id/object_type
    shape `Decide Action`/`Decide Company Action` emit, live-confirmed on execution
    11948), a bare object for a caller that still hands one row un-wrapped, or
    `{status_code, text}` — `dispatch_enrichment`'s own fallback when the body could not
    be parsed as JSON at all.

    Returns `(rows, reason)`. `reason` is `None` on success; `rows` is `[]` and `reason`
    names what was missing when nothing usable could be read — never an exception, never
    a partial guess, the same contract `enrichment_row_ledger()` holds. This is a
    WHOLE-BODY refusal (not best-effort per item): a body shaped unlike a decision
    response at all (e.g. the `{status_code, text}` fallback) means nothing here can be
    trusted, not that everything except the odd item can be.
    """
    if not isinstance(body, (list, dict)):
        return [], "the response body was not a JSON object or array"
    items = body if isinstance(body, list) else [body]
    if not items:
        return [], "the response body was an empty array"

    rows = []
    for i, item in enumerate(items, start=1):
        if not isinstance(item, dict) or "action" not in item:
            return [], "the response body did not carry a per-row action"
        lane = "companies" if item.get("object_type") == "companies" else "contacts"
        rows.append(_build_row_report({**item, "_lane": lane}, i))
    return rows, None


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
