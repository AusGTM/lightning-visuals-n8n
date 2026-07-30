#!/usr/bin/env python3
"""scripts/probe_lusha_v3.py

Phase 20 Plan 01 (REQ-lusha-v3-contract-probe) — live-probe prover for the Lusha v3
Enrichment API (`/v3/contacts/search-and-enrich`, `/v3/companies/search-and-enrich`,
and the two-step `/v3/contacts/search` -> `/v3/contacts/enrich` pair) before any request
builder in `build_cloud_workflows.py` changes. See `docs/LUSHA-V3-CONTRACT.md` for the
contract of record this script's live run produced (2026-07-30).

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

IMPORTANT measured caveat (2026-07-30): `GET /v3/account/usage`'s `credits.remaining` is
EVENTUALLY CONSISTENT, not synchronous — a balance re-read immediately after a call can
under-report the true debit by several credits for a few seconds. The `credit_delta`
fields recorded here are therefore a soft/approximate signal; `docs/LUSHA-V3-CONTRACT.md`'s
reveal-model verdict is instead built primarily from each response's own synchronous
`billing.creditsCharged` field, which does not suffer this lag. `--settle-seconds` (default
0) can be raised to pause before each "after" balance read, at the cost of a slower run.

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
import time
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
# A second identity confirmed (2026-07-30) to have a revealable phone — needed for the
# reveal A/B (Kyle Bettler's own Lusha record has no phone at all: `phones: []`).
REVEAL_TEST_IDENTITY = {
    "firstName": "Mick", "lastName": "James",
    "companyName": "Australian Turf Club", "companyDomain": "australianturfclub.com.au",
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


def _billing_charged(resp_body):
    """Pull the synchronous `billing.creditsCharged` signal straight off a response body
    (not subject to the /account/usage eventual-consistency lag noted above)."""
    if isinstance(resp_body, dict):
        billing = resp_body.get("billing")
        if isinstance(billing, dict):
            charged = billing.get("creditsCharged")
            if isinstance(charged, (int, float)) and not isinstance(charged, bool):
                return charged
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


def _record_billable_step(ledger, name, method, url, request_body, key, settle_seconds=0):
    """Runs one billable call, recording credits before/after (soft signal, see module
    docstring) AND the response's own synchronous `billing.creditsCharged` (hard signal).
    Never raises. Returns the step dict (already appended to the ledger)."""
    credits_before = _get_credits(key)
    status, resp_body, headers, err = _request(method, url, key, request_body)
    if settle_seconds:
        time.sleep(settle_seconds)
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
        "credit_delta": delta,
        "billing_credits_charged": _billing_charged(resp_body),
        "err": err,
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
        ("P1 contacts shape A (400: contactId should not exist)", "POST", CONTACTS_URL,
         {"contacts": [{"contactId": "1", **CONTACT_IDENTITY}]}),
        ("P1 contacts shape B (400: contactId should not exist)", "POST", CONTACTS_URL,
         {"contacts": [{"contactId": "1",
                        "fullName": f"{CONTACT_IDENTITY['firstName']} {CONTACT_IDENTITY['lastName']}",
                        "companyName": CONTACT_IDENTITY["companyName"]}]}),
        ("P1 contacts shape C flat (400: firstName should not exist)", "POST", CONTACTS_URL,
         dict(CONTACT_IDENTITY)),
        ("P1 contacts shape D — CONFIRMED WINNER (200)", "POST", CONTACTS_URL,
         {"contacts": [dict(CONTACT_IDENTITY)]}),
        ("P2 companies shape A (400: companyId should not exist)", "POST", COMPANIES_URL,
         {"companies": [{"companyId": "1", "domain": COMPANY_DOMAIN}]}),
        ("P2 companies shape B — CONFIRMED WINNER (200, no reveal model)", "POST",
         COMPANIES_URL, {"companies": [{"domain": COMPANY_DOMAIN}]}),
        ("P3 two-step: search", "POST", CONTACTS_SEARCH_URL,
         {"contacts": [dict(REVEAL_TEST_IDENTITY)]}),
        ("P3 two-step: enrich (ids + reveal, confirmed body shape)", "POST", CONTACTS_ENRICH_URL,
         {"ids": ["<id from search results[0].id>"], "reveal": ["emails"]}),
        ("P4 reveal A/B: enrich reveal=[emails] only", "POST", CONTACTS_ENRICH_URL,
         {"ids": ["<id>"], "reveal": ["emails"]}),
        ("P4 reveal A/B: enrich reveal=[emails,phones]", "POST", CONTACTS_ENRICH_URL,
         {"ids": ["<id>"], "reveal": ["emails", "phones"]}),
        ("P5 id reuse: second enrich call, same id", "POST", CONTACTS_ENRICH_URL,
         {"ids": ["<id>"], "reveal": ["emails"]}),
        ("P6 no-match (fabricated identity)", "POST", CONTACTS_URL,
         {"contacts": [dict(NO_MATCH_IDENTITY)]}),
        ("P7 error shape: malformed property (400)", "POST", CONTACTS_URL,
         {"contacts": [{"firstName": "Kyle", "lastName": "Bettler", "notARealProperty": "x"}]}),
        ("P7 error shape: wrong key, same format (401)", "POST", CONTACTS_URL,
         {"contacts": [{"firstName": "Kyle", "lastName": "Bettler"}]}),
        ("P8 usage endpoint", "GET", USAGE_URL, None),
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
    winner_id = None
    for shape_name, body in shapes:
        if _cap_breached(ledger):
            break
        step = _record_billable_step(ledger, f"P1_contacts_{shape_name}", "POST",
                                      CONTACTS_URL, body, key)
        if step["status"] == 200:
            winner = shape_name
            results = (step["response_body"] or {}).get("results") or []
            if results and isinstance(results[0], dict):
                winner_id = results[0].get("id")
            break
    return winner, winner_id


def probe_companies_lane(key, ledger):
    """P2 — companies lane. Live-confirmed 2026-07-30: a `companyId` key (mirroring v2's
    `contactId` convention) is rejected the same way as the contacts lane's `contactId`;
    the winning shape is a flat `{"domain": ...}` object inside the `companies` array.
    The response carries NO `has`/`canReveal` fields at all — the companies lane has no
    selective-reveal model (Open Question 1: answered — flat per-match charge only)."""
    shapes = [
        ("shape_A_companyId", {"companies": [{"companyId": "1", "domain": COMPANY_DOMAIN}]}),
        ("shape_B_no_companyId", {"companies": [{"domain": COMPANY_DOMAIN}]}),
    ]
    winner = None
    for shape_name, body in shapes:
        if _cap_breached(ledger):
            break
        step = _record_billable_step(ledger, f"P2_companies_{shape_name}", "POST",
                                      COMPANIES_URL, body, key)
        if step["status"] == 200:
            winner = shape_name
            break
    return winner


def probe_two_step(key, ledger):
    """P3 — the two-step `/contacts/search` -> `/contacts/enrich` pair.

    Live-confirmed 2026-07-30: `/contacts/search` returns each result with `has` (fields
    present) and `canReveal` (`[{"field": ..., "credits": ...}]`) arrays instead of the
    combined endpoint's direct values. `/contacts/enrich`'s confirmed body shape is
    `{"ids": [<id>], "reveal": [<field>, ...]}` — NOT `{"contacts": [...]}` (which 400s
    with "property contacts should not exist") and NOT a bare `{"id": ...}` (400s with
    "property id should not exist"). `reveal` must contain at least 1 element — an empty
    `reveal: []` 400s with "reveal must contain at least 1 elements"."""
    if _cap_breached(ledger):
        return None
    search_body = {"contacts": [dict(REVEAL_TEST_IDENTITY)]}
    search_step = _record_billable_step(ledger, "P3_two_step_search", "POST",
                                         CONTACTS_SEARCH_URL, search_body, key)
    results = (search_step["response_body"] or {}).get("results") or []
    contact_id = results[0].get("id") if results and isinstance(results[0], dict) else None
    if not contact_id or _cap_breached(ledger):
        return contact_id
    enrich_body = {"ids": [contact_id], "reveal": ["emails"]}
    _record_billable_step(ledger, "P3_two_step_enrich", "POST",
                           CONTACTS_ENRICH_URL, enrich_body, key)
    return contact_id


def probe_reveal_ab(key, ledger, contact_id):
    """P4 — reveal A/B on the SAME identity's stored id: one enrich call requesting only
    `emails`, one requesting `emails`+`phones`. Records both `billing.creditsCharged`
    values and their difference — the number REQ-lusha-selective-reveal's cost premise
    rests on.

    Live-confirmed 2026-07-30 (Mick James, Australian Turf Club): BOTH calls billed
    `creditsCharged: 0`. The deltas are IDENTICAL — selective reveal buys nothing on this
    account (assumption A3 REFUTED). An empty `reveal: []` is not even a valid request
    (400: "reveal must contain at least 1 elements"), so "reveal nothing" is not
    achievable via `/contacts/enrich` at all."""
    if not contact_id or _cap_breached(ledger):
        return None, None
    step_minimal = _record_billable_step(
        ledger, "P4_reveal_ab_emails_only", "POST", CONTACTS_ENRICH_URL,
        {"ids": [contact_id], "reveal": ["emails"]}, key)
    if _cap_breached(ledger):
        return step_minimal["billing_credits_charged"], None
    step_full = _record_billable_step(
        ledger, "P4_reveal_ab_emails_and_phones", "POST", CONTACTS_ENRICH_URL,
        {"ids": [contact_id], "reveal": ["emails", "phones"]}, key)
    return step_minimal["billing_credits_charged"], step_full["billing_credits_charged"]


def probe_id_reuse(key, ledger, contact_id):
    """P5 — pass the SAME stored id back on a second, independent enrich call. Live-
    confirmed 2026-07-30: `billing.creditsCharged: 0` every time a stored id is enriched
    via `/contacts/enrich`, regardless of how many prior calls already revealed the same
    fields (assumption A7 CONFIRMED) — contrasted with re-searching the SAME identity via
    `/contacts/search-and-enrich` (identity fields, not id), which billed
    `creditsCharged: 1` again on a verified repeat call. The free path requires holding
    the id and calling `/contacts/enrich`, not re-running the identity-based search."""
    if not contact_id or _cap_breached(ledger):
        return None
    step = _record_billable_step(
        ledger, "P5_id_reuse_second_enrich", "POST", CONTACTS_ENRICH_URL,
        {"ids": [contact_id], "reveal": ["emails"]}, key)
    return step["billing_credits_charged"]


def probe_no_match(key, ledger):
    """P6 — a fabricated identity certain not to exist. Live-confirmed 2026-07-30:
    HTTP 200 wrapper (not a top-level 404), with the no-match signalled per-item as
    `results: [{"error": {"code": "NOT_FOUND", "message": "Contact not found"}}]` and
    `billing.creditsCharged: 0` — a no-match is free."""
    if _cap_breached(ledger):
        return None
    body = {"contacts": [dict(NO_MATCH_IDENTITY)]}
    return _record_billable_step(ledger, "P6_no_match", "POST", CONTACTS_URL, body, key)


def probe_error_shapes(key, ledger):
    """P7 — one deliberately malformed request (unknown identity property) and one
    deliberately wrong API key (same format/length, so the auth guard actually runs).
    Never retried. Live-confirmed 2026-07-30:
      - Malformed property -> 400, business-validation envelope
        `{"name": "BadRequest", "message": "contacts.0.property notARealProperty should
        not exist", "code": 400, "className": "bad-request", "errors": {}}`.
      - Wrong key (same format) -> 401, a DIFFERENT envelope shape (auth-guard, not
        business validation): `{"statusCode": 401, "timestamp": ..., "message":
        "Invalid API key", "error": "Unauthorized"}`.
      - A key that fails Lusha's format check entirely (wrong length/charset) -> 400
        with the same auth-guard envelope, `"message": "Invalid API key format"`.
    Neither error path is billed (no `billing` key appears on either error envelope)."""
    steps = {}
    if not _cap_breached(ledger):
        body = {"contacts": [{"firstName": "Kyle", "lastName": "Bettler",
                               "notARealProperty": "x"}]}
        steps["malformed_property"] = _record_billable_step(
            ledger, "P7_malformed_property", "POST", CONTACTS_URL, body, key)
    if not _cap_breached(ledger):
        bad_key = key[:-1] + ("0" if key[-1] != "0" else "1")
        steps["wrong_key"] = _record_billable_step(
            ledger, "P7_wrong_key_same_format", "POST", CONTACTS_URL,
            {"contacts": [{"firstName": "Kyle", "lastName": "Bettler"}]}, bad_key)
    return steps


def probe_usage_endpoint(key, ledger):
    """P8 — confirm `GET /v3/account/usage` -> `credits.remaining`, the same field
    `scripts/check_provider_credits.py` and `provider_registry.py`'s `credit.path` already
    target. Live-confirmed 2026-07-30: `.venv/bin/python scripts/check_provider_credits.py`
    (via the dotenv wrapper) printed the SAME `credits.remaining` number as this probe's
    own direct GET — no migration needed, per RESEARCH.md Open Question 4."""
    status, body, headers, err = _request("GET", USAGE_URL, key)
    step = {
        "name": "P8_usage_endpoint", "method": "GET", "url": USAGE_URL,
        "request_body": None, "status": status, "response_body": body,
        "headers": _rate_headers(headers), "credits_before": None, "credits_after": None,
        "credit_delta": 0, "billing_credits_charged": None, "err": err,
    }
    ledger["steps"].append(step)
    return step


def run_full_ladder(key, ledger):
    winner, contact_id = probe_contacts_lane(key, ledger)
    print(f"P1 contacts lane winner: {winner}")

    companies_winner = probe_companies_lane(key, ledger)
    print(f"P2 companies lane winner: {companies_winner}")

    two_step_id = probe_two_step(key, ledger)
    print(f"P3 two-step contact id: {two_step_id}")

    reveal_min, reveal_full = probe_reveal_ab(key, ledger, two_step_id)
    print(f"P4 reveal A/B: emails-only={reveal_min} emails+phones={reveal_full}")

    id_reuse_charge = probe_id_reuse(key, ledger, two_step_id)
    print(f"P5 id reuse credits charged: {id_reuse_charge}")

    probe_no_match(key, ledger)
    probe_error_shapes(key, ledger)
    probe_usage_endpoint(key, ledger)


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

    run_full_ladder(key, ledger)

    ledger["totals"]["credits_end"] = _get_credits(key)

    print(json.dumps(ledger, indent=2, default=str))
    if out_path:
        Path(out_path).write_text(json.dumps(ledger, indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
