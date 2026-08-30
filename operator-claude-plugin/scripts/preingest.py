"""operator-claude-plugin/scripts/preingest.py

Phase 37's match lane: this module PROPOSES, and the OPERATOR DECIDES. It never
introduces a second identity authority — no fuzzy matcher, no client-side HubSpot
mirror. `Map Columns` (the deployed backend node) remains the only real
column-mapping authority elsewhere in this plugin, and the match search itself is
HubSpot's, run server-side; `fetch_matches` only sends the lookup.

The one rule that makes the whole flow safe: every row is joined to its verdict by
`row_id`, never by position. A dropped or reordered response item would otherwise
shift every later row onto the wrong person's verdict, and nothing downstream could
detect it (37-CONTEXT §12, §7).
"""
from dataclasses import dataclass, field

import requests

import chunking
import config_gate
import enrichment
import extraction
import preview
from dispatch import DispatchError
from tabular import read_table

# The six keys the backend's own `mediumCandidates()` ships (n8n/code/matchProposal.js)
# — this IS Phase 36's information-disclosure control (T-36-04), and this module must
# not widen it client-side. `hs_object_id` is the id key; this endpoint carries no
# record-modification timestamp field at all.
CANDIDATE_KEYS = ("hs_object_id", "firstname", "lastname", "email", "jobtitle", "company")

_TIER_HIGH = "high"
_TIER_MEDIUM = "medium"
_TIER_NONE = "none"
# _TIER_UNKNOWN is not named separately: every tier this backend can ship that is not
# one of the three above buckets as unchecked below — the same "no allow-list of a
# third state" asymmetry n8n/code/matchProposal.js's own isReturnOnly() uses.


# Phase 61 Plan 04 Task 1 (REVIEW-05): the only version this parser knows. A response
# item stamped with any other value (or none) parses as UNPARSEABLE_OUTCOME — an
# unrecognised contract is never assumed compatible.
OUTCOME_CONTRACT_VERSION = 1
_KNOWN_OUTCOME_CONTRACT_VERSIONS = frozenset({OUTCOME_CONTRACT_VERSION})


@dataclass(frozen=True)
class Outcome:
    """One row's typed outcome — Task 2's confidence table's ONLY input, never raw
    response JSON. `parseable=False` (the terminal, catch-all state) carries no signal
    at all; every field on that branch stays `None` so a caller cannot mistake "could
    not parse" for "parsed to an empty/negative answer"."""

    parseable: bool
    match_tier: str = None
    candidate_count: int = None
    provider_agreement: dict = None
    material_conflicts: list = None
    judge_adjudicated_fields: dict = None


UNPARSEABLE_OUTCOME = Outcome(parseable=False)


def parse_outcome(item):
    """One response item -> a typed `Outcome`. Pure: no I/O, no config read.

    Fails toward the hold, per Task 1's own contract: a missing
    `outcome_contract_version`, an unrecognised one, a missing/tierless `match`, or a
    missing `candidate_count` all parse as `UNPARSEABLE_OUTCOME` — a signal this parser
    cannot verify must never be read as a good one. `provider_agreement`,
    `material_conflicts`, and `judge_adjudicated_fields` are read as given, including
    `None` — a row that went through no enrichment carries them as an EXPLICIT null on
    the wire (Build Response, `scripts/build_cloud_workflows.py`), which is a fact
    ("no providers ran"), not a parse failure.
    """
    if not isinstance(item, dict):
        return UNPARSEABLE_OUTCOME

    version = item.get("outcome_contract_version")
    if version not in _KNOWN_OUTCOME_CONTRACT_VERSIONS:
        return UNPARSEABLE_OUTCOME

    match = item.get("match")
    if not isinstance(match, dict):
        return UNPARSEABLE_OUTCOME
    tier = match.get("tier")
    if not isinstance(tier, str) or not tier:
        return UNPARSEABLE_OUTCOME

    candidate_count = item.get("candidate_count")
    if not isinstance(candidate_count, int) or isinstance(candidate_count, bool):
        return UNPARSEABLE_OUTCOME

    return Outcome(
        parseable=True,
        match_tier=tier,
        candidate_count=candidate_count,
        provider_agreement=item.get("provider_agreement"),
        material_conflicts=item.get("material_conflicts"),
        judge_adjudicated_fields=item.get("judge_adjudicated_fields"),
    )


class RowSpecError(Exception):
    """Raised when a rows list cannot become a matchable spec — empty, or a row that
    already carries a `row_id` of its own."""


class ClassifyError(Exception):
    """Raised when a response cannot be classified safely — today, only a duplicated
    `row_id`: a duplicate means the join is not a function, and there is no safe
    choice between the two candidate verdicts."""


def build_rows_spec(rows):
    """Mint one `row_id` per row, once, at the whole-batch level — before anything is
    chunked. A per-chunk `enumerate` would mint the same id in two different chunks
    (each chunk restarts its own count from zero) and make the join in
    `classify_matches` ambiguous with no error, so ids are minted here, exactly once,
    and never re-derived downstream.

    Ids are a deterministic sequence over the batch (`row-1`, `row-2`, ...), not a
    UUID, so a re-run over the same input is comparable to its predecessor.

    Refuses a row that already carries a `row_id` (ids are minted in exactly one
    place) and refuses an empty rows list. Never mutates the caller's rows — returns
    fresh row dicts. This lane is contacts-only (37-CONTEXT §2 decision 6; there is no
    company canonical set).
    """
    if not rows:
        raise RowSpecError(
            "No rows were given, so there is nothing to match or enrich."
        )

    spec_rows = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise RowSpecError(f"Row {i} is not a record — cannot assign it a row_id.")
        if "row_id" in row:
            raise RowSpecError(
                f"Row {i} already carries a `row_id` ({row['row_id']!r}). Ids are "
                "minted exactly once, at the whole-batch level, before any chunking "
                "happens — a row arriving with one already would mean two things "
                "minted ids, which is exactly what makes the join ambiguous."
            )
        spec_rows.append({**row, "row_id": f"row-{i + 1}"})

    return {"rows": spec_rows, "object_type": "contacts"}


def refused_reason(items):
    """None, or the backend's own refusal reason string.

    The backend's whole-batch refusal is a SINGLE item shaped differently from every
    normal per-row response item: it carries an `outcome` field (no per-row response
    item ever does — those carry `action`/`row_id`/`mode`/`match`), and no `row_id` to
    join on. Detected by the PRESENCE of that field, never by counting items, so a
    chunk of exactly one row that got exactly one real match verdict is never
    mistaken for a refusal.
    """
    if items and isinstance(items[0], dict) and "outcome" in items[0]:
        return items[0].get("reason") or "the backend refused this chunk"
    return None


def fetch_matches(chunk, config, transport=requests.post):
    """One POST per chunk of rows — unarmed. Written attribute-shaped
    (`transport=requests.post`, dispatch.py's exact shape, deliberately NOT
    enrichment.py's module-shaped `transport=requests` default) so this function IS
    visible to `test_retry_reuses_dispatch.py`'s `_is_requests_send_attribute`
    matcher and lands on that guard's allowlist on purpose — never as a second
    invisible send path (37-CONTEXT §7/§12).

    Takes NO `armed` parameter at all. A match call sends an explicit EMPTY provider
    selection (`enrichment.build_envelope(chunk, [])`), so it burns no provider
    credit, and it reads HubSpot search results without writing anything HubSpot-side
    — there is nothing here for arming to protect.
    """
    config_gate.require_capability(config, "match")

    envelope = enrichment.build_envelope(chunk, [])
    url = enrichment.enrichment_target(config)
    headers = {"X-Enrichment-Secret": config["webhook_secret"]}

    try:
        response = transport(
            url, headers=headers, json=envelope, timeout=enrichment.DEFAULT_TIMEOUT,
        )
    except Exception:
        # Never relay the transport exception's text — it can echo request headers.
        raise DispatchError(
            "Could not reach the n8n match webhook. Check the connection and try "
            "again, or ask an admin to check the n8n Cloud instance if this persists."
        ) from None

    # A non-2xx status or an unreadable body is folded into the same DispatchError a
    # transport exception raises, rather than returned as data for the caller to
    # inspect — match_batch (Task 2) treats both as one failure class, and this
    # backend's status is opaque garbage for exactly the same reason a dead
    # connection is: nothing here was matched, and the chunk must be retried whole.
    status_code = getattr(response, "status_code", None)
    if not isinstance(status_code, int) or not 200 <= status_code < 300:
        raise DispatchError(
            "The match search for this chunk returned an unusable response. Nothing "
            "here was matched; the chunk needs to be retried."
        )

    try:
        body = response.json()
    except Exception:
        raise DispatchError(
            "The match search's response for this chunk could not be read. Nothing "
            "here was matched; the chunk needs to be retried."
        ) from None

    # The deployed webhook answers array-wrapped, a one-element list — n8n's normal
    # firstIncomingItem behaviour. Accepting only the bare dict is the exact bug that
    # made every real `hubspot/backend-status` answer read as unrecognized until
    # 29-05 (backend_status.py carries the identical fix). Accept both shapes.
    if isinstance(body, list):
        return body
    return [body]


@dataclass(frozen=True)
class MatchOutcome:
    """One batch's match verdicts, mirroring `chunking.DispatchOutcome`'s shape.

    `unchecked_row_ids` names every row id a chunk failure or backend refusal
    prevented from being looked at — this is `unchecked`, never `unmatched`:
    "we did not find one" and "we could not look" are different answers, and
    reporting one as the other would send the operator to spend money enriching a
    contact HubSpot may already hold.

    `failed_batch` is None when nothing failed — present/absent, not an empty
    container, mirroring `chunking.DispatchOutcome.failed_batch`.
    """

    responses: tuple = field(default_factory=tuple)
    unchecked_row_ids: frozenset = field(default_factory=frozenset)
    failure_reasons: tuple = field(default_factory=tuple)
    failed_batch: dict = None


def match_batch(plan, config, transport=requests.post):
    """Send every chunk of a rows plan, in plan order, one at a time — mirrors
    `chunking.dispatch_plan`'s sequential, skip-a-failing-chunk contract, without
    arming: there is nothing to arm, since `fetch_matches` takes no `armed`
    parameter, and `NotArmedError` can never be raised here so it is never caught
    here.

    Failure is defined in ONE place, inside `fetch_matches` itself: a transport
    exception, a non-2xx status, or an unreadable body all become `DispatchError`
    there. `chunking._StatusCapturingTransport` is not reused here — it wraps a
    MODULE-shaped transport (`transport.post(...)`), and `fetch_matches`'s transport
    is attribute-shaped (`transport(...)`, a bare callable) by design (see its own
    docstring), so the two wrapper shapes do not fit each other. Capturing the status
    inside `fetch_matches`'s own return, rather than writing a second
    status-capturing wrapper for a different transport shape, is the simpler of the
    two options the plan allows.

    The backend's whole-batch refusal (`refused_reason`) is handled the same way as
    a `DispatchError`: the whole chunk becomes `unchecked`, carrying the backend's own
    reason, and is never zipped against the chunk's row ids — it carries no join key,
    and there is exactly one of it regardless of how many rows were sent.
    """
    responses = []
    unchecked = set()
    failure_reasons = []
    failed_chunks = []

    for chunk in plan.chunks:
        chunk_row_ids = {row["row_id"] for row in chunk.get("rows", [])}

        try:
            items = fetch_matches(chunk, config, transport=transport)
        except DispatchError as exc:
            unchecked |= chunk_row_ids
            failure_reasons.append(str(exc))
            failed_chunks.append(chunk)
            continue

        reason = refused_reason(items)
        if reason is not None:
            unchecked |= chunk_row_ids
            failure_reasons.append(reason)
            failed_chunks.append(chunk)
            continue

        responses.extend(items)

    return MatchOutcome(
        responses=tuple(responses),
        unchecked_row_ids=frozenset(unchecked),
        failure_reasons=tuple(failure_reasons),
        failed_batch=chunking.failed_batch(failed_chunks),
    )


def classify_matches(rows, response, unchecked_row_ids=None):
    """Bucket every row into exactly one of four named groups — auto-matched,
    proposed, unmatched, unchecked — joined to its own verdict by `row_id`, never by
    position (37-CONTEXT §12). Pure: no network, no file, no config read.

    Walks the INPUT rows, not the response: walking the rows is what makes a
    response item missing for some row detectable; walking the response instead
    would make a silently-dropped row invisible.

    `unchecked_row_ids` (typically `MatchOutcome.unchecked_row_ids` from
    `match_batch`) is a pre-seeded unchecked set, so a row whose chunk never got a
    response is bucketed the same way as a row the backend explicitly could not look
    up — one state, two causes, both named `unchecked`.

    Exactly four tiers, and nothing branches on `action`. The backend's write-path-only
    match-review action fires only in the branch where the return-only predicate is
    false, and this client always sends the propose mode, so every response it ever
    receives carries the same "proposed" action, MEDIUM rows included (verified in
    36-04-SUMMARY.md). This function deliberately has no handler for that action, no
    fifth bucket for it, and no branch on `action` at all: a branch that can never be
    taken reads as coverage while being dead, and the day it stops being dead is the
    day this client started sending the write mode — a different bug entirely.

    A duplicated `row_id` in the response raises `ClassifyError` rather than letting
    the later item overwrite the earlier — there is no safe choice between the two.
    A response item whose `row_id` matches no input row is reported (in the
    `unknown_response_row_ids` key) but never attached to any row.
    """
    index = {}
    for item in response:
        if not isinstance(item, dict):
            continue
        row_id = item.get("row_id")
        if row_id is None:
            continue
        if row_id in index:
            raise ClassifyError(
                f"The response carries two items for row {row_id!r} — a duplicate "
                "id means the join is not a function, and there is no safe choice "
                "between the two."
            )
        index[row_id] = item

    seeded_unchecked = set(unchecked_row_ids or ())
    known_row_ids = {row["row_id"] for row in rows}
    unknown_response_row_ids = sorted(set(index) - known_row_ids)

    auto_matched, proposed, unmatched, unchecked = [], [], [], []

    for row in rows:
        row_id = row["row_id"]

        if row_id in seeded_unchecked:
            unchecked.append({"row_id": row_id, "row": row})
            continue

        item = index.get(row_id)
        if item is None:
            unchecked.append({"row_id": row_id, "row": row})
            continue

        match = item.get("match") or {}
        tier = match.get("tier")

        if tier == _TIER_HIGH:
            auto_matched.append({
                "row_id": row_id, "row": row, "hs_object_id": item.get("hs_object_id"),
            })
        elif tier == _TIER_MEDIUM:
            # The six-key projection is the backend's own information disclosure
            # control from Phase 36 (T-36-04) — never widened client-side. No
            # sorting, ranking, or pre-selection: the backend deliberately does not
            # sort candidates either, because ordering would imply a ranking neither
            # side is entitled to assert.
            candidates = [
                {key: candidate.get(key) for key in CANDIDATE_KEYS}
                for candidate in (match.get("candidates") or [])
                if isinstance(candidate, dict)
            ]
            proposed.append({
                "row_id": row_id,
                "row": row,
                "candidates": candidates,
                "ambiguous": len(candidates) > 1,
            })
        elif tier == _TIER_NONE:
            unmatched.append({"row_id": row_id, "row": row})
        else:
            # The unknown tier (or any unrecognized value) — "we could not look",
            # never "no record exists".
            unchecked.append({"row_id": row_id, "row": row})

    return {
        "auto_matched": auto_matched,
        "proposed": proposed,
        "unmatched": unmatched,
        "unchecked": unchecked,
        "unknown_response_row_ids": unknown_response_row_ids,
    }


class MatchDecisionError(Exception):
    """Raised when a `resolved` decision set cannot be applied at all: a decision
    naming a row that was never proposed, or a candidate id that is not among that
    row's OWN proposed candidates. This is the pure-function form of
    `header_suggest.apply_confirmed_corrections`'s guard-before-open rule (see its
    "both guards run BEFORE any file is opened" comment) — there is no file here to
    leave half-written, but there is a caller who would otherwise act on a
    half-applied decision set. Every entry in `resolved` is checked against both
    guards in one pass, BEFORE any of them is applied, so a call that raises here has
    applied nothing at all."""


# The sentinel a `resolved` entry uses to decline a proposal — never a real HubSpot
# object id (the backend's own candidate ids are numeric strings), so it can never
# collide with a genuine candidate.
DECLINE_MATCH = "decline"


def apply_match_decisions(classified, resolved):
    """Turn the operator's per-row decisions into an updated classification.

    `resolved` maps a `row_id` from `classified["proposed"]` to either one of that
    row's own candidate `hs_object_id`s (confirming the match) or `DECLINE_MATCH`
    (declining it). A proposed row absent from `resolved` stays in `proposed`,
    unresolved — never defaulted either way; the function never picks a candidate on
    the operator's behalf (the ambiguous-row property this exists to preserve).

    A confirmed row moves into `auto_matched`, carrying the chosen candidate's
    `hs_object_id` and `confirmed: True` — this is the ONLY thing a MEDIUM proposal
    becomes a decision (37-CONTEXT §4's `apply_match_decisions` key link). A declined
    row moves into `unmatched`, so it is picked up by enrichment like any other
    no-match row.

    Pure — no I/O, no network. Returns a NEW classification; `classified` and its own
    list/dict values are never mutated in place, so a refused call (raise) leaves the
    caller's own copy exactly as it was. `apply_match_decisions(classified, {})`
    returns a value equal to `classified`.
    """
    proposed_by_id = {entry["row_id"]: entry for entry in classified["proposed"]}

    # Validation pass — every entry in `resolved` is checked against both guards
    # BEFORE anything below is built. See MatchDecisionError's docstring for why this
    # must be a separate pass rather than folded into the apply loop below: an entry
    # validated only as it is applied lets an earlier valid entry take effect before
    # a later invalid one is even seen, which is exactly the half-applied set this
    # guards against.
    for row_id, decision in resolved.items():
        entry = proposed_by_id.get(row_id)
        if entry is None:
            raise MatchDecisionError(
                f"Row {row_id!r} was never proposed as a match — there is no "
                "candidate set to decide against. Nothing was applied."
            )
        if decision == DECLINE_MATCH:
            continue
        candidate_ids = {c.get("hs_object_id") for c in entry.get("candidates", [])}
        if decision not in candidate_ids:
            raise MatchDecisionError(
                f"Row {row_id!r}'s decision names candidate {decision!r}, which is "
                "not among that row's own proposed candidates "
                f"({sorted(cid for cid in candidate_ids if cid is not None)}). A "
                "decision cannot select a HubSpot record this row was never shown "
                "for. Nothing was applied."
            )

    # Apply pass — reached only once every entry above has passed both guards. Every
    # list below is a FRESH copy; nothing from `classified` is appended to in place.
    auto_matched = list(classified["auto_matched"])
    proposed = []
    unmatched = list(classified["unmatched"])

    for entry in classified["proposed"]:
        row_id = entry["row_id"]
        if row_id not in resolved:
            proposed.append(entry)
            continue
        decision = resolved[row_id]
        if decision == DECLINE_MATCH:
            unmatched.append({"row_id": row_id, "row": entry["row"]})
        else:
            auto_matched.append({
                "row_id": row_id, "row": entry["row"], "hs_object_id": decision,
                "confirmed": True,
            })

    return {
        "auto_matched": auto_matched,
        "proposed": proposed,
        "unmatched": unmatched,
        "unchecked": list(classified["unchecked"]),
        "unknown_response_row_ids": list(classified["unknown_response_row_ids"]),
    }


class MergeError(Exception):
    """Raised when a response set cannot be merged safely: a duplicated `row_id` (two
    items claiming one row means the join is not a function, and there is no safe
    choice between them — picking either would be a guess about which run actually
    produced which), or a response item that is not an object at all (this is the
    shape `chunking.dispatch_plan(...).responses` has when a caller forgets to
    flatten it first — each element is a whole chunk's raw body, not one row's
    response item — and silently treating that shape as 'no row_id' would file every
    row as `unanswered` with no error, which is exactly what happened before this
    raise existed; see FINDING 2, 53-WALK-RECORD.md). Nothing is merged when this
    raises."""


# The operator-facing sentence for a row no response item ever named — a frozen
# constant, not an inline string, so the merge layer and the render layer cannot drift
# into two phrasings of the same fact (mirrors `enrichment.VIEW_REFUSAL`'s own reason).
# It names the truth and nothing else: no verdict was received for this row because the
# backend answered before this row's result arrived, so nothing is known about what
# enrichment would have found — never a claim about the row's own data (T-38-01).
UNANSWERED_REASON = (
    "no verdict was received for this row — the backend answered before this row's "
    "result arrived, so nothing is known about what enrichment would have found"
)


@dataclass(frozen=True)
class MergeResult:
    """One merge's outcome, mirroring `MatchOutcome`'s payload-plus-report shape.
    `rows` is ready to hand straight to `extraction.hold_emailless` /
    `write_dispatch_csv` — every other field REPORTS a way the join could have
    strayed, rather than silently absorbing it.

    `unanswered` is one entry per row no response item named — `{"row_id", "row",
    "reason"}`, mirroring `extraction.hold_emailless`'s held-entry shape so a caller
    that renders one can render the other. This is NOT a row with nothing to add (that
    is a row whose response carried an empty `properties` map, walked normally); it is
    a row the backend never answered for at all, and conflating the two is exactly the
    fabrication this field exists to prevent (T-38-01)."""

    rows: tuple = field(default_factory=tuple)
    unknown_response_row_ids: tuple = field(default_factory=tuple)
    dropped_property_keys: tuple = field(default_factory=tuple)
    conflicts: tuple = field(default_factory=tuple)
    unanswered: tuple = field(default_factory=tuple)


def _present(value) -> bool:
    """Mirrors `extraction._present`'s trim-then-check rule, kept local rather than
    imported so this module never reaches into another module's private name."""
    return value is not None and str(value).strip() != ""


def merge_enriched(rows, responses):
    """Join `responses` onto `rows` by `row_id` — the ONLY join key, never position.
    Pure: no I/O, no config read.

    A waterfall response that was dropped, reordered, or duplicated is the central
    data-integrity risk this whole phase exists to close: a positional zip would
    shift every subsequent row's enrichment onto the wrong person, and nothing
    downstream could detect it (37-CONTEXT §12). Indexing the responses by `row_id`
    FIRST — refusing a duplicate id at index-build time, before a single row is
    walked — is what makes that structurally unreachable rather than merely
    untested.

    `responses` must already be a FLAT list of per-row response dicts — never
    `chunking.dispatch_plan(...).responses` passed straight through, which is one raw
    body PER CHUNK (each possibly itself a list — n8n's array-wrap). A response item
    that is not a dict raises `MergeError` rather than being silently treated as "no
    `row_id`" and skipped: a caller that forgot to flatten a nested per-chunk shape
    used to have every row file as `unanswered` with no error at all (FINDING 2,
    53-WALK-RECORD.md). Flatten first, exactly as `rerequest_unanswered` does for
    this same endpoint.

    Walks the ROWS, not the responses, so a row with no matching response is
    detectable (`unanswered`) rather than silently absent from the output —
    distinguishable from a row whose response carried an empty `properties` map,
    which is walked normally and simply has nothing to fill. In the operator's terms:
    a row the backend never answered for is not a row with nothing to add — it is a
    row nothing is known about at all, and that difference is the whole point of the
    group (T-38-01).

    Each response's `properties` map is filtered to `extraction.canonical_props()`
    before anything is written — a key outside that set is dropped and reported by
    row and name (`dropped_property_keys`), never widened onto the row. A widened row
    would otherwise raise at `write_dispatch_csv` much later, with a message about
    canonical keys rather than about enrichment; catching it here keeps the cause
    visible where it happened.

    Fill-not-overwrite: a `properties` value only fills a key the row currently holds
    empty or absent. A DIFFERING value for a key the row already holds non-empty is
    never written — it is recorded in `conflicts` instead. The spreadsheet is the
    operator's own assertion about their own data; silently replacing it with a
    vendor's guess is a change they would have no way to notice.

    Never mutates an input row — every merged row is a fresh dict.
    """
    index = {}
    for item in responses:
        if not isinstance(item, dict):
            raise MergeError(
                f"A response item was not an object ({item!r}) — merge_enriched needs "
                "a flat list of per-row response dicts, never a nested per-chunk shape. "
                "This is what `chunking.dispatch_plan(...).responses` looks like when "
                "it is passed straight through unflattened: each chunk's own body must "
                "be flattened first (see `preingest.rerequest_unanswered`, which "
                "already does this for the same endpoint). Nothing was merged."
            )
        row_id = item.get("row_id")
        if row_id is None:
            continue
        if row_id in index:
            raise MergeError(
                f"The response carries two items for row {row_id!r} — a duplicate "
                "id means the join is not a function, and there is no safe choice "
                "between the two. Nothing was merged."
            )
        index[row_id] = item

    known_row_ids = {row["row_id"] for row in rows}
    unknown_response_row_ids = sorted(set(index) - known_row_ids)

    allowed_keys = set(extraction.canonical_props())

    merged_rows = []
    dropped_property_keys = []
    conflicts = []
    unanswered = []

    for row in rows:
        row_id = row["row_id"]
        merged = dict(row)
        item = index.get(row_id)

        if item is None:
            unanswered.append({"row_id": row_id, "row": merged, "reason": UNANSWERED_REASON})
            merged_rows.append(merged)
            continue

        for key, value in (item.get("properties") or {}).items():
            if key not in allowed_keys:
                dropped_property_keys.append({"row_id": row_id, "key": key})
                continue
            current = merged.get(key)
            if _present(current):
                if str(value).strip() != str(current).strip():
                    conflicts.append({
                        "row_id": row_id, "field": key,
                        "kept": current, "provider_value": value,
                    })
                continue
            merged[key] = value

        merged_rows.append(merged)

    return MergeResult(
        rows=tuple(merged_rows),
        unknown_response_row_ids=tuple(unknown_response_row_ids),
        dropped_property_keys=tuple(dropped_property_keys),
        conflicts=tuple(conflicts),
        unanswered=tuple(unanswered),
    )


def rerequest_unanswered(rows, merge_report, providers, armed, config, transport=requests):
    """One re-request pass over `merge_report.unanswered`, dispatched through the SAME
    `chunking.dispatch_plan` -> `enrichment.dispatch_enrichment` path the first pass
    used. No new send path exists here — see the comment on the `dispatch_plan` call
    below, and `test_retry_reuses_dispatch.py`'s `_EXPECTED_SEND_SHAPED`, which this
    function must leave unchanged (T-38-03).

    Returns `merge_report` unchanged, with no plan built and no call made, when there
    is nothing unanswered — the whole point of this function is a re-request, and a
    re-request over nothing is not one.

    **Exactly once.** There is no loop, no retry counter and no recursion in this
    function's body. A silent retry loop against a backend that truncates under load
    turns one honest gap into an unbounded spend the operator never approved (T-38-04);
    the honest report of a row still unanswered after this one pass is a better outcome
    than a second guess at it.

    `armed` is threaded straight through as a required positional with no default,
    mirroring every other caller of `dispatch_plan`/`dispatch_enrichment` — the grant
    covers the batch it was spoken for, and this pass is part of that batch's
    execution, not a fresh one asking again on its own authority (T-38-03). A falsy
    `armed` raises `NotArmedError` from that existing gate before anything is sent.

    Reuses the unanswered rows' OWN `row_id` values for the re-request — `build_rows_spec`
    is deliberately never called here: it mints a fresh id per row and refuses one that
    already carries one, which is exactly right for a first pass and exactly wrong for
    this one. The ids are the join key every verdict the first pass recorded is keyed
    on; re-minting them would orphan all of it (T-38-05).

    Returns a `MergeResult` over the FULL original `rows` — a complete picture, not a
    fragment the caller has to stitch onto `merge_report` itself. A row the re-request
    answered drops out of `unanswered` automatically (via a second `merge_enriched`
    call, scoped to the re-requested rows only); a row it did not keeps its entry and
    its true reason, never a fabricated one — including a row whose own chunk failed
    outright, since a failed chunk simply carries no response item, the same "item is
    None" branch `merge_enriched` already handles.
    """
    unanswered_entries = tuple(merge_report.unanswered)
    if not unanswered_entries:
        return merge_report

    retry_rows = [entry["row"] for entry in unanswered_entries]
    spec = {"rows": retry_rows, "object_type": "contacts"}
    plan = chunking.plan_chunks(spec, chunking.chunk_ceiling(config))

    # No `transport.post`/`.put` call anywhere in this function's own body — `transport`
    # is only ever handed on to `dispatch_plan`, which is what keeps this function
    # invisible to `test_retry_reuses_dispatch.py`'s bare-module-default predicate: that
    # guard flags a function only when it BOTH defaults `transport` to the bare
    # `requests` module AND calls `transport.post`/`.put` directly in its own body: this
    # function does the first and not the second.
    outcome = chunking.dispatch_plan(plan, providers, armed, config, transport=transport)

    new_items = []
    for body in outcome.responses:
        # The deployed webhook answers array-wrapped, a one-element list — n8n's normal
        # firstIncomingItem behaviour, the same shape `fetch_matches` already
        # normalizes for this same endpoint. Accept both.
        new_items.extend(body if isinstance(body, list) else [body])

    retry_result = merge_enriched(retry_rows, new_items)

    retry_by_id = {row["row_id"]: row for row in retry_result.rows}
    answered_by_id = {row["row_id"]: row for row in merge_report.rows}
    merged_rows = tuple(
        retry_by_id.get(row["row_id"], answered_by_id.get(row["row_id"]))
        for row in rows
    )

    return MergeResult(
        rows=merged_rows,
        unknown_response_row_ids=(
            tuple(merge_report.unknown_response_row_ids) + retry_result.unknown_response_row_ids
        ),
        dropped_property_keys=(
            tuple(merge_report.dropped_property_keys) + retry_result.dropped_property_keys
        ),
        conflicts=tuple(merge_report.conflicts) + retry_result.conflicts,
        unanswered=retry_result.unanswered,
    )


class RowsFromTableError(Exception):
    """Raised when a table cannot become canonical-keyed rows: the mapping file could
    not be resolved. Never degrades to unmapped rows — `preview.label_headers`
    returns `available: False` in that case, which would silently produce rows with
    no canonical keys at all and fail much later at `write_dispatch_csv` with an
    unrelated message. Raised here instead, naming the missing mapping, the same way
    `extraction.py` treats it as a hard error."""


def rows_from_table(path, mapping_path=None):
    """Read a CSV/XLSX file into canonical-keyed rows, through
    `preview.label_headers`'s EXACT alias lookup only — the single mapping authority
    this function is allowed to consult (37-CONTEXT §4). `preview.py`'s own docstring
    (preview.py:39-44) forbids adding fuzzy matching to `label_headers`, because a
    smarter matcher there would mislabel a column the backend really does map — this
    function must not smuggle that back in by adding a second lookup of its own.
    Fuzzy suggestion already exists, in `header_suggest.py`, where the operator
    confirms it per header; this function proposes nothing and confirms nothing, it
    only maps what the table already, exactly, says.

    Reads with `tabular.read_table` — no second parser. Read-only end to end: the
    source file's bytes are identical before and after this call.

    A header the alias table does not recognise is dropped from every ROW (its
    column's values reach no row) but never silently from the CALLER — it is named,
    by its original header string, in the returned `dropped_headers` list.

    Refuses, naming the missing mapping, rather than degrading: an unresolved mapping
    (`resolve_mapping_path` returning `None`, or `label_headers` reporting
    `available: False`) would otherwise silently produce rows carrying no canonical
    keys at all.

    Returns `{"rows": [{canonical_prop: value, ...}, ...], "dropped_headers": [...]}`.
    """
    headers, table_rows = read_table(path)

    resolved_mapping = preview.resolve_mapping_path(mapping_path)
    label_result = preview.label_headers(headers, resolved_mapping)
    if resolved_mapping is None or not label_result["available"]:
        raise RowsFromTableError(
            "config/column_mapping.yaml could not be resolved — with no alias table "
            "to map headers against, there is no safe way to build canonical rows."
        )

    canonical_headers = [label["canonical"] for label in label_result["labels"]]
    dropped_headers = [
        label["header"] for label in label_result["labels"] if label["dropped"]
    ]

    rows = []
    for data_row in table_rows:
        row = {}
        for canonical, value in zip(canonical_headers, data_row):
            if canonical is not None:
                row[canonical] = value
        rows.append(row)

    return {"rows": rows, "dropped_headers": dropped_headers}


_NOTHING_REACHED_HUBSPOT = (
    "Nothing here has reached HubSpot yet — this is the last look before "
    "the operator's yes grants the write."
)


def _held_statement(total, held_count):
    """Names the batch at both boundaries (37-CONTEXT §5 step 6) — an omitted
    section is indistinguishable from a batch nobody checked."""
    if held_count == 0:
        return "No rows are held back here — every row in this batch is sendable."
    if held_count == total:
        return (
            f"All {total} rows in this batch are held back. Sending it as it stands "
            f"would write nothing to HubSpot."
        )
    return f"{held_count} of {total} rows are held back and will not be sent."


def _unanswered_statement(total, unanswered_count):
    """The unanswered counterpart to `_held_statement`'s both-boundaries treatment
    (T-38-01) — when nothing is unanswered, say so explicitly rather than omitting the
    section, same reason `_held_statement` names a batch at both boundaries."""
    if unanswered_count == 0:
        return "No rows are unanswered here — the backend returned a verdict for every row."
    if unanswered_count == total:
        return (
            f"All {total} rows in this batch are unanswered. The backend returned no "
            f"verdict for any of them."
        )
    return f"{unanswered_count} of {total} rows are unanswered and will be re-requested."


def render_enriched_preview(rows, merge_report=None):
    """The post-enrichment, pre-ingest render (37-CONTEXT §5 step 6) — the
    operator's one look at exactly what will reach HubSpot before "arm the
    upload" can be spoken. Pure: no network, no file write, no config read.

    `rows` are the SOURCE-supplied rows (pre-merge); `merge_report` is the
    `MergeResult` `merge_enriched(rows, responses)` returned. When `merge_report`
    is omitted, `rows` are rendered as their own merged form (nothing enriched).

    The SEND/HELD verdict is computed by calling `extraction.hold_emailless` over
    the rows as they will actually be sent (the MERGED rows, since enrichment can
    fill a previously-blank email) — never re-derived here. `write_dispatch_csv`
    refuses on that exact same predicate; a second one in this render could
    disagree with the gate, and the operator would grant the second arming on a
    display that does not match what the gate actually does next. As of T-38-01
    the gate is asked only about rows the backend actually ANSWERED for — an
    unanswered row is partitioned out first, so this does not weaken the
    one-predicate guarantee: `hold_emailless` remains the sole source of the
    SEND/HELD split, it is simply never asked a question about a row it has no
    evidence for.

    Ordering mirrors `report.build_contact_report`: counts first, every held row
    in FULL, then every unanswered row in FULL, then the sampled send rows — the
    adaptive-sample rule applies only to the SEND rows, reusing
    `preview._adaptive_sample` rather than inventing a fourth sampling
    convention. A held or unanswered row that got sampled out of a large batch
    would be a person nobody is told about (T-38-06).

    Returns structured data, not rendered markdown — `preview.build_extracted_preview`'s
    precedent: the skill owns the rendering.
    """
    merged_rows = list(merge_report.rows) if merge_report is not None else list(rows)
    conflicts = tuple(getattr(merge_report, "conflicts", None) or ())
    unanswered_entries = tuple(getattr(merge_report, "unanswered", None) or ())
    unanswered_row_ids = {entry["row_id"] for entry in unanswered_entries}

    original_by_id = {row.get("row_id"): row for row in rows}

    def _row_view(merged_row):
        row_id = merged_row.get("row_id")
        original = original_by_id.get(row_id, {})
        source_values = {
            key: value for key, value in original.items()
            if key != "row_id" and _present(value)
        }
        enriched_values = {
            key: value for key, value in merged_row.items()
            if key != "row_id" and _present(value) and not _present(original.get(key))
        }
        return {
            "row_id": row_id,
            "source_values": source_values,
            "enriched_values": enriched_values,
            # ponytail: the enrichment response `merge_enriched` consumes carries
            # one flat `properties` map per row — no per-provider attribution
            # reaches this layer. "the enrichment waterfall" is the honest,
            # aggregate source name; naming an individual provider here would be
            # a guess this module has no evidence for.
            "source": "the enrichment waterfall" if enriched_values else None,
        }

    # Unanswered rows are partitioned OUT before the gate is ever called (T-38-01)
    # — this is the fix: handing the gate every merged row, unanswered included,
    # is what let an unanswered row with no email land in `held` carrying the
    # gate's no-email reason, a claim about the row's data standing in for a claim
    # about the response.
    answered_rows = [row for row in merged_rows if row.get("row_id") not in unanswered_row_ids]

    sendable, held = extraction.hold_emailless(answered_rows)

    held_rows = [
        {**_row_view(entry["row"]), "verdict": "HELD", "reason": entry["reason"]}
        for entry in held
    ]

    # Never sampled — same rule the held rows already follow, same reason
    # (T-38-06): the reason is taken from the constant, never from the entry's own
    # `reason`, so a caller cannot smuggle a fabricated reason through this render.
    unanswered_rows = [
        {**_row_view(entry["row"]), "verdict": "UNANSWERED", "reason": UNANSWERED_REASON}
        for entry in unanswered_entries
    ]

    send_views = [
        {**_row_view(row), "verdict": "SEND", "reason": None} for row in sendable
    ]
    adaptive, send_rows = preview._adaptive_sample(send_views)

    total = len(merged_rows)
    held_count = len(held)
    unanswered_count = len(unanswered_entries)

    return {
        "total": total,
        "send_count": len(sendable),
        "held_count": held_count,
        "held_rows": held_rows,
        "unanswered_count": unanswered_count,
        "unanswered_rows": unanswered_rows,
        "adaptive": adaptive,
        "send_rows": send_rows,
        "conflicts": conflicts,
        "held_statement": _held_statement(total, held_count),
        "unanswered_statement": _unanswered_statement(total, unanswered_count),
        "nothing_reached_hubspot": _NOTHING_REACHED_HUBSPOT,
    }
