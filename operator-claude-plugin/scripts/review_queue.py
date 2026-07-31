"""operator-claude-plugin/scripts/review_queue.py

The read half of review triage: fetch the flagged backlog through the n8n
`hubspot/review/queue` endpoint (the client holds no HubSpot credential, D-05) and render
each held conflict in language a non-technical operator can adjudicate (REVIEW-01, D-11).

THE POLICY LOOKUP IS DISPLAY-ONLY. `policy_class()` reads `config/field_policy.yaml` to
TELL the operator a field is protected before they invest in a decision (D-06). Nothing in
this module may branch on the returned class to block, filter, reorder or alter a decision.
The backend is the single policy authority; a client that refuses locally becomes a second
authority that drifts from it (D-07). Same read-only-lookup pattern as Phase 23 D-07's
column-mapping preview: read the config to explain, never to decide.

WHAT THE PROTECTION CLAIM IS SCOPED TO (D-31, open): the class filter is enforced by the
review-DECISION endpoint (`n8n/code/reviewDecision.js` `PROTECTED_CLASSES`). The separate
15-minute approval sweep (`reviewApply.js`) allowlists by key presence, so `domain` and
`annualrevenue` remain writable on that path. Every protection sentence rendered here names
the decision endpoint. Do not widen it to a general claim.

TRANSPORT SHAPE (D-17, Phase 28 D-28/D-33): `transport` defaults to the BARE `requests`
module and the call goes through `transport.post(...)` — never `transport=requests.post`,
never a direct `requests.post(...)`. `tests/test_retry_reuses_dispatch.py` scans every
plugin script for a send-shaped default and allowlists exactly two functions;
this module must never join that list. If the guard fires here, this module is wrong.

Auth is `X-Enrichment-Secret` — the webhook secret, as `backend_status.py` uses. The secret
is placed in a header and nowhere else: never rendered, never logged, never echoed in a
refusal (T-30-20).

What is NOT rendered: `lv_enrichment_provenance` / `lv_contact_enrichment_provenance`. It
arrives as a raw string that can be kilobytes, and the held candidate already carries the
source, confidence, reason and evidence URL per field (30-04's handoff #4).
"""
import json
from pathlib import Path

import requests

import config_gate

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PLUGIN_ROOT.parent
DEFAULT_POLICY_PATH = REPO_ROOT / "config" / "field_policy.yaml"

QUEUE_PATH = "webhook/hubspot/review/queue"
DEFAULT_TIMEOUT = 30

# The two ownership classes `reviewDecision.js` refuses to write, quoted from its own
# PROTECTED_CLASSES so the label the operator reads matches what the endpoint does.
PROTECTED_CLASSES = ("manual_protected", "review_required")

# HubSpot's own object-type ids, for the record URL.
_OBJECT_TYPE_IDS = {"companies": "0-2", "contacts": "0-1"}

_CANDIDATE_KEY = "lv_enrichment_review_candidate_json"
_REASON_KEY = "lv_enrichment_review_reason"

_SOURCE_DISCLOSURE = (
    "Each conflict below names the ONE source the pipeline resolved to. The full "
    "provider-by-provider disagreement is computed during scoring and never stored, so a "
    "single source named here is not evidence that the providers agreed."
)

_PROTECTED_DISCLOSURE = (
    "Fields marked PROTECTED are refused by the review-decision endpoint this plugin "
    "submits to. That scope is exact: approving inside HubSpot instead goes through a "
    "separate 15-minute sweep which does not apply this check."
)

_policy_cache = {}


def queue_target(config: dict) -> str:
    """The endpoint this module POSTs to. Never includes the secret."""
    return f"{str(config.get('n8n_url') or '').rstrip('/')}/{QUEUE_PATH}"


def _unavailable(reason: str) -> dict:
    return {"available": False, "reason": reason, "object_type": None,
            "total": None, "returned": 0, "rows": []}


def fetch_queue(config: dict, object_type: str = "companies", limit=None,
                transport=requests) -> dict:
    """One POST. Returns `{available, reason, object_type, total, returned, rows}`.

    The response is ONE envelope, never one item per record (D-32): `.rows` is the page and
    `total` is the whole backlog, so `total > returned` means truncated and never "queue
    empty".

    `search_ok: false` is a FAILURE, not an empty queue (D-33). HubSpot search nodes run
    `onError: continueRegularOutput`, so a 401 or a 429 arrives as an item with no results
    array — rendering that as "0 flagged records" would tell the operator their backlog is
    clear when it was never read.
    """
    config_gate.require_capability(config, "review")

    headers = {"X-Enrichment-Secret": config["webhook_secret"]}
    body = {"object_type": object_type}
    if limit is not None:
        body["limit"] = limit

    try:
        response = transport.post(queue_target(config), headers=headers, json=body,
                                  timeout=DEFAULT_TIMEOUT)
    except Exception:
        # Never echo the transport exception's text — it can carry request headers.
        return _unavailable("endpoint_unreachable")

    status_code = getattr(response, "status_code", None)
    if not isinstance(status_code, int) or not 200 <= status_code < 300:
        return _unavailable(f"http_{status_code}" if status_code else "no_response")

    try:
        payload = response.json()
    except Exception:
        return _unavailable("unparseable_response")

    if not isinstance(payload, dict):
        return _unavailable("unrecognized_response_shape")

    if payload.get("search_ok") is False:
        return _unavailable("hubspot_search_did_not_run")

    rows = payload.get("rows")
    rows = rows if isinstance(rows, list) else []
    return {"available": True, "reason": None,
            "object_type": payload.get("object_type"),
            "total": payload.get("total"), "returned": len(rows), "rows": rows}


def _load_policy(policy_path):
    """The whole `object -> field -> {class, ...}` map, cached per resolved path. `{}` when
    the file is absent or unreadable — an unavailable policy costs the protected LABEL, and
    must never be mistaken for "nothing is protected" by a caller that decides on it. Which
    is why nothing here decides on it (D-06/D-07)."""
    path = Path(policy_path) if policy_path is not None else DEFAULT_POLICY_PATH
    key = str(path)
    if key not in _policy_cache:
        try:
            import yaml

            with path.open(encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
            _policy_cache[key] = loaded if isinstance(loaded, dict) else {}
        except Exception:
            _policy_cache[key] = {}
    return _policy_cache[key]


def policy_class(object_type: str, field: str, policy_path=None):
    """This field's ownership class, or None when the policy does not name it.

    DISPLAY ONLY — see the module docstring. None means "the policy says nothing", which is
    not the same as "unprotected"; both render as unmarked, and neither blocks anything.
    """
    entry = (_load_policy(policy_path).get(object_type) or {}).get(field)
    if not isinstance(entry, dict):
        return None
    klass = entry.get("class")
    return klass if isinstance(klass, str) and klass else None


def record_link(object_type: str, record_id, portal_id):
    """The HubSpot record URL, or None when the portal id (or the id) is missing.

    None rather than a partial URL: the caller renders the raw id and names what is missing,
    which an operator can act on. A broken link is worse than no link.
    """
    type_id = _OBJECT_TYPE_IDS.get(object_type)
    if not portal_id or not record_id or not type_id:
        return None
    return f"https://app.hubspot.com/contacts/{portal_id}/record/{type_id}/{record_id}"


def _show(value) -> str:
    """A missing key is `unknown`; a present-but-empty value is `(blank)`. Opposite
    findings, never collapsed into one reassuring blank (D-08)."""
    if value is None:
        return "unknown"
    text = str(value).strip()
    return text if text else "(blank)"


def held_decisions(row: dict) -> list:
    """The held candidate decisions on one row, parsed from the raw JSON string.

    A contact is candidate-less by EMPTINESS, not key absence (D-34): the contacts lane DOES
    request this property and HubSpot returns `""`. `[]` for empty, unparseable, or any
    shape that is not a list of objects — an unreadable candidate is rendered as "nothing to
    approve", never guessed at.
    """
    raw = (row or {}).get(_CANDIDATE_KEY)
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return [d for d in parsed if isinstance(d, dict)] if isinstance(parsed, list) else []


def _record_name(row: dict) -> str:
    for key in ("name", "email", "firstname"):
        value = (row.get(key) or "").strip() if isinstance(row.get(key), str) else ""
        if value:
            return value
    return f"Record {_show(row.get('hs_object_id'))}"


def _decision_lines(decision: dict, policy_lookup) -> list:
    field = decision.get("field")
    klass = policy_lookup(field) if field else None
    protected = klass in PROTECTED_CLASSES

    lines = [
        f"- **{_show(field)}**"
        + (f" — PROTECTED ({klass}): a decision made here will not overwrite it."
           if protected else ""),
        f"  - HubSpot holds now: {_show(decision.get('current_value'))}",
        f"  - The pipeline wants to set: {_show(decision.get('chosen_value'))}",
        f"  - Proposed by: {_show(decision.get('source_provider'))}, "
        f"confidence {_show(decision.get('confidence'))}",
        f"  - Held back because: {_show(decision.get('reason'))}",
    ]
    evidence = decision.get("evidence_url")
    if isinstance(evidence, str) and evidence.strip():
        lines.append(f"  - Evidence: {evidence.strip()}")
    return lines


def _icp_line(row: dict):
    """The scored-company narrative, only where it exists — it is what makes a company's
    flag intelligible at all."""
    parts = []
    if row.get("lv_icp_tier"):
        parts.append(f"ICP tier {_show(row.get('lv_icp_tier'))} "
                     f"(score {_show(row.get('lv_icp_fit_score'))})")
    if row.get("lv_anti_icp_reason"):
        parts.append(f"anti-ICP: {_show(row.get('lv_anti_icp_reason'))}")
    return "; ".join(parts) if parts else None


def render_record(row: dict, policy_lookup, link_lookup) -> str:
    row = row if isinstance(row, dict) else {}
    record_id = row.get("hs_object_id")
    link = link_lookup(row)

    lines = [f"## {_record_name(row)}"]
    lines.append(
        f"Open in HubSpot: {link}" if link else
        f"HubSpot record id {_show(record_id)} — no link, because `hubspot_portal_id` is "
        "not set in config/operator.local.json."
    )
    if row.get(_REASON_KEY):
        lines.append(f"Flagged because: {_show(row.get(_REASON_KEY))}")

    decisions = held_decisions(row)
    if decisions:
        for decision in decisions:
            lines.extend(_decision_lines(decision, policy_lookup))
    else:
        lines.append("Nothing is being proposed for this record — there is no stored "
                     "candidate to approve, only a reason to record.")

    icp = _icp_line(row)
    if icp:
        lines.append(icp)
    return "\n".join(lines)


def render_queue(rows, total, policy_lookup, link_lookup) -> str:
    """The whole queue as text. Performs no I/O: the rows are already fetched and both
    lookups are injected."""
    rows = list(rows or [])
    if not rows:
        return ("# Records waiting on a review decision\n"
                "Nothing needs review right now — the queue is empty.")

    shown = len(rows)
    if isinstance(total, int) and total > shown:
        count_line = (f"{total} records are flagged; the {shown} below are this page. "
                      "Ask for more to see the rest.")
    else:
        count_line = f"{_show(total) if total is not None else shown} flagged, all shown below."

    records = [render_record(row, policy_lookup, link_lookup) for row in rows]

    header = "# Records waiting on a review decision\n" + count_line + "\n\n" + _SOURCE_DISCLOSURE
    # Only when something is actually marked: an unearned protection sentence on a page with
    # no protected field trains the operator to skip the one that matters.
    if any("PROTECTED (" in record for record in records):
        header += "\n\n" + _PROTECTED_DISCLOSURE

    return "\n\n".join([header] + records)
