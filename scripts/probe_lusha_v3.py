#!/usr/bin/env python3
"""scripts/probe_lusha_v3.py

Phase 20 Plan 01 (REQ-lusha-v3-contract-probe) — live-probe prover for the Lusha v3
Enrichment API (`/v3/contacts/search-and-enrich`, `/v3/companies/search-and-enrich`,
and the two-step `/v3/contacts/search` -> `/v3/contacts/enrich` pair) before any request
builder in `build_cloud_workflows.py` changes.

Read-only prover, mirrors `scripts/check_provider_credits.py`'s idioms:
  - `LUSHA_API_KEY` via `os.getenv` only. Absent -> "skipped (no LUSHA_API_KEY)", exit 0,
    ZERO HTTP calls.
  - The secret value is NEVER printed. Every echoed request header shows `api_key: <redacted>`.
  - NEVER raises. Every transport error becomes a step with `status: 0` and an `err` string.

Disarmed by default (T-20-02, cost-abuse mitigation): live HTTP only when
`ALLOW_LUSHA_PROBE=true`. Disarmed mode prints the full ladder of request shapes this
script WOULD send (method, URL, redacted headers, JSON body) and makes ZERO HTTP calls, so
the literals are inspectable/greppable offline.

Cost guard: reads `GET /v3/account/usage` -> `credits.remaining` before and after every
billable step. Aborts the remaining ladder and prints `PROBE ABORTED: credit cap reached`
if the cumulative delta exceeds `PROBE_MAX_CREDITS` (default 40), or if the number of
billable calls exceeds `PROBE_MAX_BILLABLE` (default 8).

Never probes `/prospecting/*` (RESEARCH.md Pitfall 1 — a different Lusha product line,
out of scope per CLAUDE.md/REQUIREMENTS.md). A response shaped like the Prospecting API
(top-level `requestId` paired with a plural `contactIds` array) is recorded as a
wrong-endpoint warning, never treated as the enrichment contract.

Usage:
    # Disarmed — prints the request ladder, zero HTTP calls, safe to run any time.
    .venv/bin/python scripts/probe_lusha_v3.py

    # Live — spends real credits. Load .env in-process (this repo's `.env` is agent-
    # permission-blocked for Read/Bash cat; never `cat .env`).
    ALLOW_LUSHA_PROBE=true .venv/bin/python -c \\
      "from dotenv import load_dotenv; load_dotenv(); import runpy; \\
       runpy.run_path('scripts/probe_lusha_v3.py', run_name='__main__')" -- --out /tmp/lusha-v3-probe.json
"""
import json
import os
import sys
from pathlib import Path

CONTACTS_URL = "https://api.lusha.com/v3/contacts/search-and-enrich"
CONTACTS_SEARCH_URL = "https://api.lusha.com/v3/contacts/search"
CONTACTS_ENRICH_URL = "https://api.lusha.com/v3/contacts/enrich"
COMPANIES_URL = "https://api.lusha.com/v3/companies/search-and-enrich"
USAGE_URL = "https://api.lusha.com/v3/account/usage"

PROBE_MAX_CREDITS = int(os.getenv("PROBE_MAX_CREDITS", "40"))
PROBE_MAX_BILLABLE = int(os.getenv("PROBE_MAX_BILLABLE", "8"))

# Known 2026-07-30 matcher (scripts/dryrun_batch.mjs CANDIDATES) — the tracer identity.
CONTACT_IDENTITY = {
    "firstName": "Kyle", "lastName": "Bettler",
    "companyName": "Racing NSW", "companyDomain": "racingnsw.com.au",
}
COMPANY_DOMAIN = "racingnsw.com.au"
NO_MATCH_IDENTITY = {
    "firstName": "Zzz", "lastName": "Qqqnotreal",
    "companyName": "Nonexistent Holdings Pty Ltd",
    "companyDomain": "nonexistent-holdings-zz.example",
}

RATE_HEADER_HINTS = ("rate", "left", "limit")


def _redacted_headers():
    return {"api_key": "<redacted>", "Content-Type": "application/json"}


def _rate_headers(headers):
    return {k: v for k, v in headers.items() if any(h in k.lower() for h in RATE_HEADER_HINTS)}


def _request(method, url, key, body=None, timeout=30):
    """Never raises. Returns (status, response_body, headers, err)."""
    import requests
    headers = {"api_key": key, "Content-Type": "application/json"}
    try:
        r = requests.request(method, url, headers=headers, json=body, timeout=timeout)
        try:
            rbody = r.json()
        except ValueError:
            rbody = r.text
        return r.status_code, rbody, dict(r.headers), None
    except Exception as exc:  # never raise — mirrors check_provider_credits.py contract
        return 0, None, {}, str(exc)


def _get_credits(key):
    status, body, _headers, _err = _request("GET", USAGE_URL, key)
    if status == 200 and isinstance(body, dict):
        credits = body.get("credits")
        if isinstance(credits, dict):
            remaining = credits.get("remaining")
            if isinstance(remaining, (int, float)) and not isinstance(remaining, bool):
                return remaining
    return None


def _check_prospecting_leak(body, step_name, ledger):
    """Record (never raise) a wrong-endpoint warning if a response looks like the
    OUT-OF-SCOPE Prospecting API (top-level requestId + plural contactIds array) rather
    than the Enrichment API this probe targets."""
    if isinstance(body, dict) and "requestId" in body and isinstance(body.get("contactIds"), list):
        ledger["steps"].append({
            "name": f"{step_name}_WRONG_ENDPOINT_WARNING",
            "warning": ("response shape matches the Prospecting API (requestId + "
                        "contactIds), not the Enrichment API this probe targets — "
                        "out of scope per CLAUDE.md"),
        })


def _new_ledger():
    return {
        "steps": [],
        "totals": {"billable_calls": 0, "total_credit_delta": 0,
                   "aborted": False, "abort_reason": None},
    }


def _record_billable_step(ledger, name, method, url, request_body, key):
    """Runs one billable POST, recording credits before/after and the credit delta.
    Never raises. Returns the step dict (already appended to the ledger)."""
    credits_before = _get_credits(key)
    status, resp_body, headers, err = _request(method, url, key, request_body)
    credits_after = _get_credits(key)
    ledger["totals"]["billable_calls"] += 1
    delta = None
    if credits_before is not None and credits_after is not None:
        delta = credits_before - credits_after
        ledger["totals"]["total_credit_delta"] += delta
    step = {
        "name": name, "method": method, "url": url,
        "request_body": request_body,
        "status": status, "response_body": resp_body,
        "headers": _rate_headers(headers),
        "credits_before": credits_before, "credits_after": credits_after,
        "credit_delta": delta, "err": err,
    }
    ledger["steps"].append(step)
    _check_prospecting_leak(resp_body, name, ledger)
    return step


def _cap_breached(ledger):
    if ledger["totals"]["billable_calls"] >= PROBE_MAX_BILLABLE:
        ledger["totals"]["aborted"] = True
        ledger["totals"]["abort_reason"] = (
            f"PROBE_MAX_BILLABLE ({PROBE_MAX_BILLABLE}) reached")
        print("PROBE ABORTED: credit cap reached (billable call cap)")
        return True
    if ledger["totals"]["total_credit_delta"] > PROBE_MAX_CREDITS:
        ledger["totals"]["aborted"] = True
        ledger["totals"]["abort_reason"] = (
            f"cumulative credit delta {ledger['totals']['total_credit_delta']} "
            f"> PROBE_MAX_CREDITS {PROBE_MAX_CREDITS}")
        print("PROBE ABORTED: credit cap reached (cumulative delta)")
        return True
    return False


def disarmed_ladder():
    """Print (never call) the full request ladder — the URL/body literals this script
    WOULD send, with the key redacted. Zero HTTP calls."""
    ladder = [
        ("P1 contacts shape A", "POST", CONTACTS_URL,
         {"contacts": [{"contactId": "1", **CONTACT_IDENTITY}]}),
        ("P1 contacts shape B", "POST", CONTACTS_URL,
         {"contacts": [{"contactId": "1",
                        "fullName": f"{CONTACT_IDENTITY['firstName']} {CONTACT_IDENTITY['lastName']}",
                        "companyName": CONTACT_IDENTITY["companyName"]}]}),
        ("P1 contacts shape C (flat, top-level)", "POST", CONTACTS_URL, dict(CONTACT_IDENTITY)),
        ("P1 contacts shape D (flat identity in contacts[], no contactId — CONFIRMED WINNER)",
         "POST", CONTACTS_URL, {"contacts": [dict(CONTACT_IDENTITY)]}),
    ]
    print("DISARMED — no HTTP calls made. Request ladder this script would send:")
    for name, method, url, body in ladder:
        print(json.dumps({
            "name": name, "method": method, "url": url,
            "headers": _redacted_headers(), "body": body,
        }, indent=2, default=str))
    print("(set ALLOW_LUSHA_PROBE=true to make live calls)")


def probe_contacts_lane(key, ledger):
    """P1, the tracer path — contacts lane, ONE identity, first HTTP 200 wins. Records
    EVERY attempt including failures — the 400 bodies are contract evidence.

    Live-confirmed 2026-07-30: shapes A/B/C (all carrying a `contactId` field, or a
    top-level flat body outside a `contacts` array) 400 with
    `"property contactId should not exist"` / `"property firstName should not exist"`.
    The winning shape is D: a `contacts` array of ONE plain identity object with NO
    `contactId` key at all — v3 dropped the v2 `contactId` indexing key entirely."""
    shapes = [
        ("shape_A", {"contacts": [{"contactId": "1", **CONTACT_IDENTITY}]}),
        ("shape_B", {"contacts": [{"contactId": "1",
                     "fullName": f"{CONTACT_IDENTITY['firstName']} {CONTACT_IDENTITY['lastName']}",
                     "companyName": CONTACT_IDENTITY["companyName"]}]}),
        ("shape_C_flat", dict(CONTACT_IDENTITY)),
        ("shape_D_no_contactId", {"contacts": [dict(CONTACT_IDENTITY)]}),
    ]
    winner = None
    for shape_name, body in shapes:
        if _cap_breached(ledger):
            break
        step = _record_billable_step(ledger, f"P1_contacts_{shape_name}", "POST",
                                      CONTACTS_URL, body, key)
        if step["status"] == 200:
            winner = shape_name
            break
    return winner


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    out_path = None
    if "--out" in argv:
        out_path = argv[argv.index("--out") + 1]

    key = os.getenv("LUSHA_API_KEY")
    if not key:
        skip_banner = "skipped (no " + "LUSHA_API_KEY" + ")"
        print(skip_banner)
        return 0

    allow_live = os.getenv("ALLOW_LUSHA_PROBE", "false").lower() == "true"
    if not allow_live:
        disarmed_ladder()
        return 0

    ledger = _new_ledger()
    credits_start = _get_credits(key)
    ledger["totals"]["credits_start"] = credits_start

    winner = probe_contacts_lane(key, ledger)
    print(f"contacts lane winner: {winner}")

    ledger["totals"]["credits_end"] = _get_credits(key)

    print(json.dumps(ledger, indent=2, default=str))
    if out_path:
        Path(out_path).write_text(json.dumps(ledger, indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
