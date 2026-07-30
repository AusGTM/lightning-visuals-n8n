#!/usr/bin/env python3
"""scripts/check_provider_credits.py

Phase 16.1 Plan 02 (SC-6, reviews A3/A6) — read-only CLI printing each provider's
remaining credits. Mirrors scripts/provision_n8n_credentials.py's idiom: a
`_has_<provider>()` gate per provider; when NONE are present, print a "skipped (no
provider creds)" banner and exit 0 (zero HTTP calls).

Imports PROVIDER_REGISTRY from the SIDE-EFFECT-FREE scripts/provider_registry.py
(reviews A3) — NEVER scripts/build_cloud_workflows.py, whose import writes
taxonomy.generated.js/escalation.generated.js codegen files as a side effect. A read-only
balance check must not mutate the repo just by being imported/run.

On ANY 4xx/5xx/timeout/malformed response this script reports `credits: None` for that
provider — it NEVER raises (SC-4/SC-6's "never fail" contract, same as the runtime
extractCredits in n8n/code/providerSelection.js, whose three extractors are re-implemented
here in Python — small enough to keep as explicit functions, not a shared cross-language
parser; ponytail: don't build a JSONPath engine for 3 providers).

NEVER prints a secret value — only credit numbers + HTTP status codes. The ZoomInfo bearer
is minted inline (Basic-auth POST, client_id:client_secret via `requests`' own `auth=`
tuple — never a manually-built header string, never printed).

Live-only utility: excluded from the offline pytest suite by the same convention as
scripts/deploy_n8n_workflows.py / scripts/provision_n8n_credentials.py (lives in
scripts/, no `test_` prefix — pytest never collects it). Its functions are unit-tested
offline with MOCKED requests in tests/test_check_provider_credits.py (reviews A6) — no
live call happens in the suite.

Usage:
    python scripts/check_provider_credits.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from provider_registry import PROVIDER_REGISTRY  # noqa: E402 — side-effect-free (A3)


def _has_lusha() -> bool:
    return bool(os.getenv("LUSHA_API_KEY"))


def _has_apollo() -> bool:
    return bool(os.getenv("APOLLO_API_KEY"))


def _has_zoominfo() -> bool:
    return bool(os.getenv("ZOOMINFO_CLIENT_ID")) and bool(os.getenv("ZOOMINFO_CLIENT_SECRET"))


_HAS = {"lusha": _has_lusha, "apollo": _has_apollo, "zoominfo": _has_zoominfo}


# --- null-safe extractors (mirror n8n/code/providerSelection.js extractCredits) --------
# Every extractor returns None on ANY shape mismatch — never raises. isinstance(x, bool)
# is excluded from the numeric check because bool is a subclass of int in Python.

def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _extract_lusha(raw):
    # 200 body -> { credits: { total, used, remaining } } [VERIFIED: live curl 200]
    if not isinstance(raw, dict):
        return None
    credits = raw.get("credits")
    if not isinstance(credits, dict):
        return None
    remaining = credits.get("remaining")
    return remaining if _is_number(remaining) else None


def _extract_apollo(raw):
    # THIS account's key 403s (non-master) [VERIFIED: live curl 403] -> raw carries no
    # `remaining` field -> None. A master key's body is read defensively: only a
    # top-level numeric `remaining` is trusted.
    if not isinstance(raw, dict):
        return None
    remaining = raw.get("remaining")
    return remaining if _is_number(remaining) else None


def _extract_zoominfo(raw):
    # JSON:API: data[0].attributes.usage[] keyed by limitType. [VERIFIED: live curl 200]
    # Real balance lives under limitType == "uniqueIdLimit"; fall back to the first entry
    # with a non-zero totalLimit before giving up (a different ZoomInfo plan may report
    # its balance under another key — RESEARCH.md Open Question #1).
    if not isinstance(raw, dict):
        return None
    data = raw.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return None
    attributes = data[0].get("attributes")
    usage = attributes.get("usage") if isinstance(attributes, dict) else None
    if not isinstance(usage, list):
        return None
    entry = next((u for u in usage if isinstance(u, dict) and u.get("limitType") == "uniqueIdLimit"), None)
    if entry is None:
        entry = next(
            (u for u in usage if isinstance(u, dict) and _is_number(u.get("totalLimit")) and u["totalLimit"] > 0),
            None,
        )
    if entry is None:
        return None
    remaining = entry.get("usageRemaining")
    return remaining if _is_number(remaining) else None


_EXTRACT = {"lusha": _extract_lusha, "apollo": _extract_apollo, "zoominfo": _extract_zoominfo}


# --- read-only usage calls (never the enrichment/match/person/company data endpoint) ---

def _check_lusha() -> dict:
    import requests
    credit = PROVIDER_REGISTRY["lusha"]["credit"]
    try:
        r = requests.get(
            credit["url"], headers={credit["header"]: os.getenv("LUSHA_API_KEY", "")}, timeout=15)
        raw = r.json() if r.ok else None
        return {"provider": "lusha", "status": r.status_code,
                "credits": _extract_lusha(raw) if raw is not None else None}
    except Exception as exc:
        return {"provider": "lusha", "status": None, "credits": None, "error": type(exc).__name__}


def _check_apollo() -> dict:
    import requests
    credit = PROVIDER_REGISTRY["apollo"]["credit"]
    try:
        r = requests.post(
            credit["url"], headers={credit["header"]: os.getenv("APOLLO_API_KEY", "")}, timeout=15)
        raw = r.json() if r.ok else None
        return {"provider": "apollo", "status": r.status_code,
                "credits": _extract_apollo(raw) if raw is not None else None}
    except Exception as exc:
        return {"provider": "apollo", "status": None, "credits": None, "error": type(exc).__name__}


def _mint_zoominfo_token():
    """Inline Basic-auth POST — the ONLY place client_id/client_secret are read, via
    `requests`' own `auth=` tuple (never a manually-built header string). Returns the
    bearer token string, or None on ANY failure — never raises, never prints the secret
    values (grant_type=client_credentials ONLY, no `scope` — a `scope` 400s)."""
    import requests
    cid = os.getenv("ZOOMINFO_CLIENT_ID", "")
    csec = os.getenv("ZOOMINFO_CLIENT_SECRET", "")
    try:
        r = requests.post(
            "https://api.zoominfo.com/gtm/oauth/v1/token",
            auth=(cid, csec), data={"grant_type": "client_credentials"}, timeout=15)
        if not r.ok:
            return None
        token = r.json().get("access_token")
        return token if isinstance(token, str) and token else None
    except Exception:
        return None


def _check_zoominfo() -> dict:
    credit = PROVIDER_REGISTRY["zoominfo"]["credit"]
    token = _mint_zoominfo_token()
    if not token:
        # Mint failed — NO usage GET is issued (reviews A6).
        return {"provider": "zoominfo", "status": None, "credits": None, "error": "mint_failed"}
    import requests
    try:
        r = requests.get(
            credit["url"], headers={"Authorization": f"Bearer {token}", "Accept": credit["accept"]}, timeout=15)
        raw = r.json() if r.ok else None
        return {"provider": "zoominfo", "status": r.status_code,
                "credits": _extract_zoominfo(raw) if raw is not None else None}
    except Exception as exc:
        return {"provider": "zoominfo", "status": None, "credits": None, "error": type(exc).__name__}


_CHECK = {"lusha": _check_lusha, "apollo": _check_apollo, "zoominfo": _check_zoominfo}


def main(argv=None) -> int:
    configured = [name for name in PROVIDER_REGISTRY if _HAS[name]()]
    if not configured:
        print("skipped (no provider creds): none of LUSHA_API_KEY / APOLLO_API_KEY / "
              "ZOOMINFO_CLIENT_ID+ZOOMINFO_CLIENT_SECRET are set.")
        return 0

    for name in PROVIDER_REGISTRY:  # canonical order: lusha, apollo, zoominfo
        if name not in configured:
            print(f"{name}: skipped (no credentials configured)")
            continue
        result = _CHECK[name]()
        print(f"{name}: credits={result['credits']} status={result.get('status')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
