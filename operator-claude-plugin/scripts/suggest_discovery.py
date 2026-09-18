"""operator-claude-plugin/scripts/suggest_discovery.py

The plugin-side client for the sixth cloud workflow, `LV Suggest Discovery (Cloud
template)` (Phase 73.1 Plan 07's read-only provider-discovery lane). Copies
`backend_status.py`'s four-part shape exactly: a `<NAME>_PATH` constant, a
`<name>_target(config)` builder that never includes the secret, an `_unavailable(reason)`
degrade helper, and `fetch_discovery(config, body, transport=requests.post)` doing a
plain `json=` POST with the `X-Enrichment-Secret` header — a form-encoded upload is a
different transport entirely. This is a JSON envelope, not the row-set CSV upload
`dispatch.py` exists for; that module's shape is purpose-built for a different transport
and is deliberately not reused here.

Never echoes a transport exception's text — it can carry request headers — and never
returns a blank-but-successful mapping: the same two disciplines `backend_status.py`
states about itself. A failure here degrades to `{available: False, reason, data: None}`.

D-07's hybrid response channel: the webhook answers synchronously with a data body
(`{run_id, companies: [...]}`) — the fast path. On timeout or a PARTIAL body — fewer
companies returned than were sent, or `companies` missing outright — the caller recovers
the same people from settled runData, keyed on the client-minted `run_id`, through
`watch.recover_async_dispatch`'s existing `workflow_name`/`echo_node`/`response_node`
keyword overrides (zero change to `watch.py`: this module neither imports it nor is
imported by it — recovery is the CALLER's own step, at the call site where the run
bookkeeping already lives). The three literals below are exported so the caller never
hard-codes them: `DISCOVERY_WORKFLOW_NAME` (the workflow's own name),
`DISCOVERY_ECHO_NODE` (`Parse Discovery Request` — the first node `run_id` lands on, one
item per company, per plan 07's D-08/D-09 parser), and `DISCOVERY_RESPONSE_NODE`
(`Respond to Webhook` — plan 07's own recorded response-node literal).

`run_id` is minted by the CALLER with `run_state.new_run_id()` — the sole existing mint
point — never a fresh ad hoc `uuid.uuid4()` call; this module accepts whatever `run_id`
the caller already put in `body` and never mints its own.
"""
import requests

DISCOVERY_PATH = "webhook/hubspot/suggest/discover"
DEFAULT_TIMEOUT = 30

# Phase 73.1 Plan 07's contract (73.1-07-SUMMARY.md): the workflow's own name, the node
# `run_id` first lands on (one item per company), and the response node's literal name.
# Exported so a caller passes these to `watch.recover_async_dispatch` as its
# `workflow_name`/`echo_node`/`response_node` overrides rather than hard-coding them.
DISCOVERY_WORKFLOW_NAME = "LV Suggest Discovery (Cloud template)"
DISCOVERY_ECHO_NODE = "Parse Discovery Request"
DISCOVERY_RESPONSE_NODE = "Respond to Webhook"


def discovery_target(config: dict) -> str:
    """The endpoint this module POSTs to. Never includes the secret."""
    return f"{str(config.get('n8n_url') or '').rstrip('/')}/{DISCOVERY_PATH}"


def _unavailable(reason: str) -> dict:
    return {"available": False, "reason": reason, "data": None}


def fetch_discovery(config: dict, body: dict, transport=requests.post) -> dict:
    """One POST carrying the D-08 envelope (`{run_id, per_company_cap, companies: [...]}`).

    Returns `{available, reason, data}`. When `available` is True, `data` is the parsed
    response body with one extra key folded in: `data["complete"]` is False when the
    body came back naming fewer companies than `body["companies"]` sent, or with no
    `companies` key at all — D-07's signal that the caller should take the runData
    recovery path rather than reading a short list as "the rest found nobody".
    `data["complete"]` is True only when every sent company came back.
    """
    if not config.get("webhook_secret"):
        # Refuse locally rather than sending an unauthenticated request that would 401.
        return _unavailable("webhook_secret_not_configured")

    headers = {"X-Enrichment-Secret": config["webhook_secret"]}

    try:
        response = transport(discovery_target(config), headers=headers, json=body,
                             timeout=DEFAULT_TIMEOUT)
    except Exception:
        # Never echo the transport exception's text — it can carry request headers.
        return _unavailable("endpoint_unreachable")

    status_code = getattr(response, "status_code", None)
    if not isinstance(status_code, int) or not 200 <= status_code < 300:
        return _unavailable(f"http_{status_code}" if status_code else "no_response")

    try:
        parsed = response.json()
    except Exception:
        return _unavailable("unparseable_response")

    if isinstance(parsed, list):
        # Same one-element-list unwrap `backend_status.py` documents (n8n's normal
        # firstIncomingItem behaviour) — other consumers of this webhook family may
        # rely on the wrapping, so it is unwrapped here, not disabled at the source.
        if len(parsed) != 1 or not isinstance(parsed[0], dict):
            return _unavailable("unrecognized_response_shape")
        parsed = parsed[0]

    if not isinstance(parsed, dict):
        return _unavailable("unrecognized_response_shape")

    sent_companies = body.get("companies") if isinstance(body, dict) else None
    sent_count = len(sent_companies) if isinstance(sent_companies, list) else None
    returned_companies = parsed.get("companies")
    complete = isinstance(returned_companies, list) and (
        sent_count is None or len(returned_companies) == sent_count)

    data = dict(parsed)
    data["complete"] = complete
    return {"available": True, "reason": None, "data": data}
