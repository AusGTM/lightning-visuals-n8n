"""operator-claude-plugin/scripts/backend_status.py

The other half of the credential split (D-01): the facts the plugin is NOT entitled to
read itself — provider balances, HubSpot queue and review counts, credential health —
arrive from the n8n-side `hubspot/backend-status` endpoint, which holds those
credentials. The plugin never constructs a provider request of any kind, and holds no
provider key to construct one with.

Auth is `X-Enrichment-Secret` — the webhook secret, NOT the `X-N8N-API-KEY` the Public
API reads take. Both live at the same base URL, so crossing them yields a 401 that looks
like a configuration problem (T-27-13).

The live endpoint answers ARRAY-WRAPPED — a one-element list, n8n's normal
`firstIncomingItem` behaviour (verified live 2026-08-03) — so a bare-dict-only check
rejected every real answer. A single-element list unwraps to its element before the
dict check; an empty list, a multi-element list, or a non-dict element is still
`unrecognized_response_shape`. The n8n side is not changed — other consumers of this
webhook may rely on the wrapping.

A failure here degrades to an unavailable result with a reason. It never raises and
never returns an empty-but-successful-looking mapping: one dead endpoint must not take
the whole status answer down (T-27-14), and a blank that reads as healthy is exactly the
wrong conclusion (D-08).
"""
import requests

STATUS_PATH = "webhook/hubspot/backend-status"
DEFAULT_TIMEOUT = 30


def status_target(config: dict) -> str:
    """The endpoint this module POSTs to. Never includes the secret."""
    return f"{str(config.get('n8n_url') or '').rstrip('/')}/{STATUS_PATH}"


def _unavailable(reason: str) -> dict:
    return {"available": False, "reason": reason, "data": None}


def fetch_backend_status(config: dict, transport=requests.post) -> dict:
    """One POST. Returns `{available, reason, data}`.

    The endpoint takes no request body — it probes all three providers unconditionally,
    since a status check has no notion of which providers a batch uses.
    """
    if not config.get("webhook_secret"):
        # Refuse locally rather than sending an unauthenticated request that would 401.
        return _unavailable("webhook_secret_not_configured")

    headers = {"X-Enrichment-Secret": config["webhook_secret"]}

    try:
        response = transport(status_target(config), headers=headers, json={},
                             timeout=DEFAULT_TIMEOUT)
    except Exception:
        # Never echo the transport exception's text — it can carry request headers.
        return _unavailable("endpoint_unreachable")

    status_code = getattr(response, "status_code", None)
    if not isinstance(status_code, int) or not 200 <= status_code < 300:
        return _unavailable(f"http_{status_code}" if status_code else "no_response")

    try:
        body = response.json()
    except Exception:
        return _unavailable("unparseable_response")

    if isinstance(body, list):
        if len(body) != 1 or not isinstance(body[0], dict):
            return _unavailable("unrecognized_response_shape")
        body = body[0]

    if not isinstance(body, dict):
        return _unavailable("unrecognized_response_shape")

    return {"available": True, "reason": None, "data": body}
