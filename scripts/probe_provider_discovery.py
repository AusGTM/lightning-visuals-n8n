#!/usr/bin/env python3
"""scripts/probe_provider_discovery.py

Phase 73.1 Plan 09 Task 1 (D-12/D-13) / Task 2 (round-1 correction, rounds 2-4 live) —
one-shot, opt-in-guarded, credit-spending live probe answering the one question this
phase could not answer offline: do the three [ASSUMED] provider search-by-role
endpoints actually exist on this account, and what does a search call cost?

Round 1 (2026-09-18, pickleballaustralia.org.au) found all three original endpoints
wrong (ZoomInfo 400, Apollo 422 deprecated-route, Lusha 404) — see
.planning/phases/73.1-provider-backed-contact-discovery-as-source-tier-2/
73.1-D12-VERDICT.round1.json. Rounds 2-4 confirmed the corrected shapes live against
two domains (see 73.1-D12-VERDICT.json). The operator then ruled on D-12 (2026-09-18):
"ZoomInfo retained as tier-2 source, others (Apollo/Lusha) dropped for search phase.
Full waterfall only used on enrich." n8n/code/discoverySearch.js is now ZoomInfo-only,
shipping no Apollo/Lusha exports at all — so ZoomInfo alone is still DERIVED from that
module's own `DISCOVERY_ENDPOINTS`/`buildRequest`/`buildUrl` (via a short-lived
`node -e` subprocess), and this probe holds its OWN frozen copies of the retired
Apollo/Lusha endpoint/body/URL shapes so it can still probe all three: this script is
the evidence tool a FUTURE ruling would need, and D-12's ruling can be revisited.

Reuses scripts/check_provider_credits.py's balance-read machinery (PROVIDER_REGISTRY,
the per-provider `_CHECK` functions, the ZoomInfo token mint) rather than
re-implementing each provider's auth quirks a second time — one balance-read
implementation per provider, not two.

Issues exactly ONE search call per provider (D-11 waterfall order: ZoomInfo, Apollo,
Lusha), reading each provider's balance before and after. It does not loop, retry, or
paginate. Never prints a key, an auth header value, or a raw request/response object —
only the endpoint, the HTTP status, the balance before/after, the delta, and two
structural flags (people-returned, reveal-fields-present). A provider error body is read
for at most a message/description field, never passed through whole — the same rule the
ingest lane's create-error path already follows, because a raw provider error object can
carry the outbound request's own auth header back in an echo.

Apollo's usage endpoint returns per-endpoint rate limits, not a depleting credit pool, and
this account's (non-master) key reads 403 on it — so Apollo's balance is UNREADABLE and
its search can only ever be priced from vendor documentation, reported as such and never
as a zero delta.

Guarded by ALLOW_DISCOVERY_PROBE=true (same ALLOW_<NAME>_PROBE idiom as
scripts/probe_lusha_v3.py's ALLOW_LUSHA_PROBE) — every other guard in this repo is
structural; a script whose only protection is that nobody types its name is not guarded.

Usage (operator-invoked; `.env` is Read/Bash-permission-blocked, loaded in-process):
    ALLOW_DISCOVERY_PROBE=true .venv/bin/python -c "from dotenv import load_dotenv; \
load_dotenv(); import runpy; runpy.run_path('scripts/probe_provider_discovery.py', \
run_name='__main__')" -- --domain exampleracing.example
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import check_provider_credits as credits_mod  # noqa: E402

VERDICT_PATH = (
    ROOT / ".planning" / "phases"
    / "73.1-provider-backed-contact-discovery-as-source-tier-2"
    / "73.1-D12-VERDICT.json"
)

# D-11 waterfall order (CLAUDE.md §11 / RESEARCH.md): ZoomInfo > Apollo > Lusha — NOT
# provider_registry.py's PROVIDER_NAMES order, which is the unrelated enrich-lane order.
DISCOVERY_ORDER = ("zoominfo", "apollo", "lusha")

_DISCOVERY_SEARCH_JS = ROOT / "n8n" / "code" / "discoverySearch.js"


def _node_eval(js_expr):
    """Evaluate a JS expression against n8n/code/discoverySearch.js's own exports
    (`m`) and return the parsed JSON result -- so this probe builds its endpoints,
    request bodies and URLs from the SAME source of truth as the lane, never a second
    hand-copied literal that can silently drift. That drift is exactly what round 1 of
    this probe found: the shapes this script used to hardcode were wrong (ZoomInfo 400,
    Apollo 422, Lusha 404). One short-lived `node` subprocess per call; this probe
    issues at most three provider searches, so this runs only a handful of times per
    invocation -- never a hot path."""
    script = f"const m = require({json.dumps(str(_DISCOVERY_SEARCH_JS))}); console.log(JSON.stringify({js_expr}));"
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=10)
    if result.returncode != 0:
        raise RuntimeError(
            f"discoverySearch.js node-eval failed for {js_expr!r}: {result.stderr.strip()[:300]}")
    return json.loads(result.stdout)


# ZoomInfo is derived from n8n/code/discoverySearch.js's own exports -- it is the ONLY
# provider still in that module after the operator's D-12 ruling (2026-09-18,
# "search-only": ZoomInfo retained, Apollo/Lusha dropped from the shipped discovery lane
# -- see 73.1-D12-VERDICT.json's own `operator_ruling`/`consequences`). Apollo and Lusha
# are no longer exported by discoverySearch.js at all, so this probe holds its OWN
# frozen copies of their round-2-confirmed endpoint/body/URL below, independent of the
# shipped module -- kept alive deliberately, because this probe is the evidence tool a
# FUTURE ruling would need, and round 1's original "one source, no second copy"
# argument stops applying the moment the production copy is retired.
_RETIRED_PROVIDER_ENDPOINTS = {
    "apollo": "https://api.apollo.io/api/v1/mixed_people/api_search",
    "lusha": "https://api.lusha.com/prospecting/contact/search",
}

DISCOVERY_ENDPOINTS = {
    "zoominfo": _node_eval("m.DISCOVERY_ENDPOINTS")["zoominfo"],
    **_RETIRED_PROVIDER_ENDPOINTS,
}


def _search_request(provider, domain):
    """The rung-2 (unfiltered) search body for `provider`. ZoomInfo is built by
    n8n/code/discoverySearch.js's OWN buildRequest -- the shipped module, the same
    source of truth the production lane uses. Apollo and Lusha are no longer exported
    by that module (D-12 narrowed it to ZoomInfo-only), so this probe builds their
    (round-2-confirmed, frozen) bodies itself -- an evidence-only copy, not a second
    source for anything shipped."""
    if provider == "zoominfo":
        opts = json.dumps({"domain": domain, "roleTitles": [], "limit": 10})
        return _node_eval(f"m.buildRequest({json.dumps(provider)}, {opts})")
    if provider == "apollo":
        return {"q_organization_domains_list": [domain], "per_page": 10, "page": 1}
    if provider == "lusha":
        return {"filters": {"companies": {"include": {"domains": [domain]}}},
                "pages": {"page": 0, "size": 10}}
    raise ValueError(f"probe_provider_discovery._search_request: unknown provider {provider!r}")


def _search_url(provider, domain):
    """The URL to POST `_search_request`'s body to. ZoomInfo's pagination is a
    query-string parameter, built by discoverySearch.js's own buildUrl (the shipped
    source of truth); Apollo and Lusha are the bare (retired, evidence-only) endpoint --
    no pagination correction needed since round 2 already confirmed the bare form."""
    if provider == "zoominfo":
        opts = json.dumps({"domain": domain, "roleTitles": [], "limit": 10})
        return _node_eval(f"m.buildUrl({json.dumps(provider)}, {opts})")
    return DISCOVERY_ENDPOINTS[provider]


APOLLO_UNREADABLE_NOTE = (
    "Apollo's usage endpoint returns per-endpoint rate limits, not a depleting credit "
    "pool (memory `provider-credit-check-endpoints`), and this account's non-master key "
    "reads 403 on it. Balance is UNREADABLE on this account -- any Apollo search cost "
    "can only come from vendor documentation, never a measured delta."
)


def _search_headers(provider):
    """Auth headers for the search call, built the same way each provider's existing
    credit check already builds its own — never printed, never logged."""
    if provider == "zoominfo":
        token = credits_mod._mint_zoominfo_token()
        if not token:
            return None
        return {"Authorization": f"Bearer {token}",
                "Content-Type": "application/vnd.api+json",
                "Accept": "application/vnd.api+json"}
    if provider == "apollo":
        return {"X-Api-Key": os.getenv("APOLLO_API_KEY", ""), "Content-Type": "application/json"}
    if provider == "lusha":
        return {"api_key": os.getenv("LUSHA_API_KEY", ""), "Content-Type": "application/json"}
    raise ValueError(f"unknown provider {provider}")


def _safe_error_note(body):
    """At most a message/description off a raw error body — never the whole object,
    which can carry the outbound request's own auth header back in an echo (the ingest
    lane's create-error-path rule, applied here to a read path)."""
    if not isinstance(body, dict):
        return None
    for key in ("message", "description", "error", "errors"):
        if key in body:
            return str(body[key])[:300]
    return None


# EXACT value-bearing key names per provider -- never a substring scan of the whole
# response blob. Round 4 (2026-09-18, tennis.com.au, 73.1-D12-VERDICT.json) found the
# old substring check ('email' in blob / 'phone' in blob) a FALSE POSITIVE on Apollo:
# its preview item carries flag KEYS `has_email`/`has_direct_phone` (booleans, never a
# value), and the substring 'email'/'phone' matches those key NAMES even though no real
# reveal field is present. ZoomInfo's and Lusha's preview items are ALSO all `has*`
# flag keys (round 4 response_shape), so the same false-positive risk applies to them.
_REVEAL_KEYS = {
    "zoominfo": ("email", "directPhone", "mobilePhone", "phone", "supplementalEmail"),
    "apollo": ("email", "phone_numbers", "mobile_phone", "direct_phone", "phone"),
    "lusha": ("email", "emails", "phone", "phones", "mobilePhone"),
}


def _people_from_response(provider, body):
    """(people_returned, reveal_fields_present) — never raises on a malformed body.
    `reveal_fields_present` checks EXACT keys in `_REVEAL_KEYS` against the first
    returned item's own keys (or its `attributes` sub-object for ZoomInfo's JSON:API
    shape) -- see `_REVEAL_KEYS`'s own comment for why this replaced a substring scan."""
    if not isinstance(body, dict):
        return False, False
    if provider == "zoominfo":
        items = body.get("data")
    elif provider == "apollo":
        items = body.get("people")
    elif provider == "lusha":
        # [ASSUMED] response envelope -- round 1 never reached a 2xx to observe it.
        # Tolerate either shape, mirroring discoverySearch.js's normalizeResponse.
        items = body.get("data") if isinstance(body.get("data"), list) else body.get("contacts")
    else:
        items = None
    items = items if isinstance(items, list) else []
    if not items:
        return False, False
    first = items[0] if isinstance(items[0], dict) else {}
    candidate = first.get("attributes") if isinstance(first.get("attributes"), dict) else first
    reveal = any(k in candidate for k in _REVEAL_KEYS.get(provider, ()))
    return True, reveal


def _response_shape(body):
    """Redacted envelope description -- key names and list lengths only, never values.
    Round 2 returned 2xx from all three providers with people_returned=False and no way
    to tell 'nobody at this domain' from 'wrong envelope key'; this settles that."""
    if not isinstance(body, dict):
        return {"type": type(body).__name__}
    shape = {"top_keys": sorted(body.keys())[:20], "lists": {}}
    for k, v in body.items():
        if isinstance(v, list):
            entry = {"len": len(v)}
            if v and isinstance(v[0], dict):
                entry["item_keys"] = sorted(v[0].keys())[:25]
                attrs = v[0].get("attributes")
                if isinstance(attrs, dict):
                    entry["attribute_keys"] = sorted(attrs.keys())[:25]
            shape["lists"][k] = entry
        elif isinstance(v, dict) and k in ("meta", "pagination", "page"):
            shape[k] = {kk: vv for kk, vv in v.items() if isinstance(vv, (int, float, bool))}
        elif isinstance(v, (int, float)) and k in ("total", "total_entries", "totalResults", "count"):
            shape[k] = v
    return shape


def probe_provider(provider, domain):
    """Balance -> ONE search call -> balance again. Never loops or retries."""
    balance_before = credits_mod._CHECK[provider]()

    result = {
        "provider": provider,
        "endpoint": DISCOVERY_ENDPOINTS[provider],
        "status": None,
        "balance_before": balance_before.get("credits"),
        "balance_after": None,
        "delta": None,
        "people_returned": False,
        "reveal_fields_present": False,
        "note": None,
    }

    headers = _search_headers(provider)
    if headers is None:  # ZoomInfo token mint failed — no search call issued
        result["note"] = "auth token mint failed; no search call issued"
        result["balance_after"] = result["balance_before"]
        return result

    url = _search_url(provider, domain)
    body = _search_request(provider, domain)
    try:
        r = requests.post(url, headers=headers, json=body, timeout=30)
        result["status"] = r.status_code
        try:
            resp_body = r.json()
        except ValueError:
            resp_body = None

        if r.ok:
            people, reveal = _people_from_response(provider, resp_body or {})
            result["people_returned"] = people
            result["reveal_fields_present"] = reveal
            result["response_shape"] = _response_shape(resp_body)
        else:
            result["note"] = _safe_error_note(resp_body) or f"HTTP {r.status_code}, no parseable message"
    except Exception as exc:  # network error, timeout, etc — never crashes the probe
        result["note"] = type(exc).__name__

    balance_after = credits_mod._CHECK[provider]()
    result["balance_after"] = balance_after.get("credits")

    if provider == "apollo" and (result["balance_before"] is None or result["balance_after"] is None):
        result["balance_before"] = None
        result["balance_after"] = None
        result["delta"] = None
        result["note"] = (result["note"] + "; " if result["note"] else "") + APOLLO_UNREADABLE_NOTE
    elif result["balance_before"] is not None and result["balance_after"] is not None:
        result["delta"] = result["balance_before"] - result["balance_after"]

    return result


def _next_probe_round():
    """1 + however many round-N verdict snapshots already exist alongside VERDICT_PATH.
    Round 1's own snapshot (73.1-D12-VERDICT.round1.json) is preserved by hand before
    each correction; each later run bumps the round number rather than silently
    overwriting that history."""
    existing = list(VERDICT_PATH.parent.glob(f"{VERDICT_PATH.stem}.round*.json"))
    return len(existing) + 1


def run_probe(domain):
    verdict = {
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "probe_round": _next_probe_round(),
        "domain": domain,
        "providers": {p: probe_provider(p, domain) for p in DISCOVERY_ORDER},
        "operator_ruling": None,
    }
    return verdict


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]

    if os.getenv("ALLOW_DISCOVERY_PROBE", "false").lower() != "true":
        print("refused: set ALLOW_DISCOVERY_PROBE=true to run this probe. It spends "
              "real provider credit -- see phase 73.1 plan 09 Task 2's how-to-verify "
              "before running it.")
        return 1

    domain = None
    if "--domain" in argv:
        domain = argv[argv.index("--domain") + 1]
    domain = domain or os.getenv("DISCOVERY_PROBE_DOMAIN")
    if not domain:
        print("refused: no company domain given. Pass --domain <domain> or set "
              "DISCOVERY_PROBE_DOMAIN.")
        return 1

    verdict = run_probe(domain)

    for provider in DISCOVERY_ORDER:
        r = verdict["providers"][provider]
        print(f"{provider}: endpoint={r['endpoint']} status={r['status']} "
              f"balance_before={r['balance_before']} balance_after={r['balance_after']} "
              f"delta={r['delta']} people_returned={r['people_returned']} "
              f"reveal_fields_present={r['reveal_fields_present']}")
        if r["note"]:
            print(f"  note: {r['note']}")

    VERDICT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VERDICT_PATH.write_text(json.dumps(verdict, indent=2, default=str))
    print(f"\nverdict written to {VERDICT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
