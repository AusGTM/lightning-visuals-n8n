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
from dispatch import DispatchError

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
    """Raised when a response set cannot be merged safely — today, only a duplicated
    `row_id`. Two items claiming one row means the join is not a function, and there
    is no safe choice between them; picking either would be a guess about which run
    actually produced which. Nothing is merged when this raises."""


@dataclass(frozen=True)
class MergeResult:
    """One merge's outcome, mirroring `MatchOutcome`'s payload-plus-report shape.
    `rows` is ready to hand straight to `extraction.hold_emailless` /
    `write_dispatch_csv` — every other field REPORTS a way the join could have
    strayed, rather than silently absorbing it."""

    rows: tuple = field(default_factory=tuple)
    unknown_response_row_ids: tuple = field(default_factory=tuple)
    dropped_property_keys: tuple = field(default_factory=tuple)
    conflicts: tuple = field(default_factory=tuple)
    unenriched_row_ids: tuple = field(default_factory=tuple)


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

    Walks the ROWS, not the responses, so a row with no matching response is
    detectable (`unenriched_row_ids`) rather than silently absent from the output —
    distinguishable from a row whose response carried an empty `properties` map,
    which is walked normally and simply has nothing to fill.

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
        row_id = item.get("row_id") if isinstance(item, dict) else None
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
    unenriched_row_ids = []

    for row in rows:
        row_id = row["row_id"]
        merged = dict(row)
        item = index.get(row_id)

        if item is None:
            unenriched_row_ids.append(row_id)
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
        unenriched_row_ids=tuple(unenriched_row_ids),
    )
