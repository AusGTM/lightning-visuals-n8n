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
import requests

import config_gate
import enrichment
from dispatch import DispatchError


class RowSpecError(Exception):
    """Raised when a rows list cannot become a matchable spec — empty, or a row that
    already carries a `row_id` of its own."""


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
