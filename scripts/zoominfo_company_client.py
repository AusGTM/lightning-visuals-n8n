#!/usr/bin/env python3
"""scripts/zoominfo_company_client.py

Phase 51 Plan 01 (D-02/FILL-03) -- a read-only ZoomInfo GTM company client. Adds the
`companies/enrich` call to Python for the first time (it previously existed only as
generated JS inside scripts/build_cloud_workflows.py's ENRICH_ZOOMINFO_CO_CACHED block).

Read-only: this module issues GET/POST requests to ZoomInfo's own API and makes NO
HubSpot call and NO n8n call. It never mutates any HubSpot record.

Run from the repo root (its only network-touching functions read credentials from the
process environment; `.env` is Read/Bash permission-blocked this session). Operator
invocation:
    .venv/bin/python -c \
        "from dotenv import load_dotenv; load_dotenv(); import runpy; \
         runpy.run_path('scripts/zoominfo_company_client.py', run_name='__main__')"

Auth is minted via scripts.check_provider_credits._mint_zoominfo_token -- the ONLY place
ZOOMINFO_CLIENT_ID/ZOOMINFO_CLIENT_SECRET are read, via `requests`' own `auth=` tuple.
This module never re-mints or re-parses that contract; it imports it.
"""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.check_provider_credits import _check_zoominfo, _mint_zoominfo_token  # noqa: E402
from src.normalizer import normalize_revenue_band  # noqa: E402

GTM_ENRICH_URL = "https://api.zoominfo.com/gtm/data/v1/companies/enrich"

# Every field below returned 200 when probed individually against companies/enrich
# (scripts/build_cloud_workflows.py:1682-1699, live-confirmed 2026-07-20). Do NOT add
# "companyType" -- it is not entitled and 400s (PFAPI0009).
ZOOM_CO_OUTPUT_FIELDS = [
    "id", "name", "website", "revenue", "revenueRange", "employeeCount", "employeeRange",
    "country", "primaryIndustry", "naicsCodes", "descriptionList", "foundedYear",
]


def zoominfo_credentials_present() -> bool:
    return bool(os.getenv("ZOOMINFO_CLIENT_ID")) and bool(os.getenv("ZOOMINFO_CLIENT_SECRET"))


def zoominfo_credit_balance():
    """Live ZoomInfo credit balance (int), or None on ANY failure -- never raises.
    Delegates entirely to scripts.check_provider_credits._check_zoominfo(); this function
    exists only to hand the caller a bare int/None instead of that function's status dict."""
    return _check_zoominfo().get("credits")


def zoominfo_revenue_to_dollars(raw):
    """GTM `revenue` is in THOUSANDS (confirmed live -- see n8n/code/normalizeProviders.js's
    own comment). Returns None for a non-numeric input and for any result at or below zero
    -- the zero-is-no-data rule the existing src.normalizer.normalize_revenue_band does NOT
    have (it would band a missing 0 as the lowest real band)."""
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        return None
    dollars = raw * 1000
    return dollars if dollars > 0 else None


def zoominfo_revenue_range_to_dollars(text):
    """Ports the JS `_revenueToDollars` regex (n8n/code/normalizeProviders.js): the first
    magnitude in the string, k/m/b suffix multiplier applied, LOWER bound in absolute
    dollars. The range string is already in dollars -- no thousands multiplier here."""
    if not isinstance(text, str) or not text.strip():
        return None
    m = re.search(r"([\d.]+)\s*([kmb]?)", text, re.IGNORECASE)
    if not m:
        return None
    try:
        n = float(m.group(1))
    except ValueError:
        return None
    unit = m.group(2).lower()
    if unit == "k":
        n *= 1e3
    elif unit == "m":
        n *= 1e6
    elif unit == "b":
        n *= 1e9
    return n if n > 0 else None


def zoominfo_revenue_band(attributes: dict):
    """Precedence already fixed in the JS reference: prefer a non-empty `revenueRange`
    string, else fall back to `zoominfo_revenue_to_dollars(attributes.get("revenue"))`. A
    None dollar figure returns None; otherwise delegates the dollars-to-band step to
    src.normalizer.normalize_revenue_band -- never re-lists the band cut points here."""
    if not isinstance(attributes, dict):
        return None
    revenue_range = attributes.get("revenueRange")
    if isinstance(revenue_range, str) and revenue_range.strip():
        dollars = zoominfo_revenue_range_to_dollars(revenue_range)
    else:
        dollars = zoominfo_revenue_to_dollars(attributes.get("revenue"))
    if dollars is None:
        return None
    band = normalize_revenue_band(dollars)
    return band if band != "unknown" else None


def zoominfo_country_region(value):
    """Mirrors the JS `normalizeCountryRegion` contract (n8n/code/normalizeProviders.js),
    NOT src.normalizer.normalize_country_region: a blank/whitespace-only/absent value
    returns None (never the truthy sentinel string "Unknown" the src normalizer emits,
    which compute_icp_score misreads as a non-ANZ hard-veto determination)."""
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    v = v.lower()
    if v in ("australia", "au", "aus"):
        return "AU"
    if v in ("new zealand", "nz"):
        return "NZ"
    return "Other"


def enrich_company(domain: str, token: str) -> dict:
    """POSTs the JSON:API companies/enrich envelope for one domain. Returns
    {"matched": bool, "attributes": dict, "reason": str | None} -- NEVER raises. Every
    extraction is isinstance-guarded (ASVS V5 / the _extract_zoominfo precedent): a
    malformed response degrades to matched=False with a stated reason. The token/
    credentials are never placed into the returned dict."""
    import requests

    payload = {
        "data": {
            "type": "CompanyEnrich",
            "attributes": {
                "matchCompanyInput": [{"companyWebsite": domain}],
                "outputFields": ZOOM_CO_OUTPUT_FIELDS,
            },
        }
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
    }

    try:
        r = requests.post(GTM_ENRICH_URL, json=payload, headers=headers, timeout=30)
        if not r.ok:
            return {"matched": False, "attributes": {}, "reason": f"http_{r.status_code}"}
        body = r.json()
    except Exception as exc:
        return {"matched": False, "attributes": {}, "reason": type(exc).__name__}

    if not isinstance(body, dict):
        return {"matched": False, "attributes": {}, "reason": "malformed_response_not_dict"}
    data = body.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return {"matched": False, "attributes": {}, "reason": "malformed_response_no_data"}
    entry = data[0]
    if entry.get("type") == "NoMatch":
        return {"matched": False, "attributes": {}, "reason": "no_match"}
    attributes = entry.get("attributes")
    if not isinstance(attributes, dict):
        return {"matched": False, "attributes": {}, "reason": "malformed_response_no_attributes"}
    return {"matched": True, "attributes": attributes, "reason": None}


def main(argv=None) -> int:
    if not zoominfo_credentials_present():
        print("skipped (no provider creds): ZOOMINFO_CLIENT_ID/ZOOMINFO_CLIENT_SECRET "
              "must both be set.")
        return 0
    balance = zoominfo_credit_balance()
    print(f"zoominfo credit balance: {balance}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
