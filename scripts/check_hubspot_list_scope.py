#!/usr/bin/env python3
"""scripts/check_hubspot_list_scope.py

Phase 25 Plan 01 Task 1 (D-02a) — READ-ONLY probe answering exactly one question:

    does this portal's HubSpot private-app token carry the `crm.lists.read` scope?

It answers that by asking HubSpot to resolve a list BY NAME and reading the HTTP status:

    200 -> GRANTED   the list resolved; its id comes back
    404 -> GRANTED   the request was AUTHORIZED and only the name failed to match.
                     A nonsense list name is therefore a perfectly valid input: a 404
                     answers the scope question just as well as a 200 does.
    403 -> DENIED    the credential lacks the scope
    401 ->           neither — a bad/absent token says nothing about scope
    else ->          inconclusive

Conflating 404 with 403 answers this backwards, so each is a separate named branch here
and each is covered by its own test.

WHAT THIS DOES *NOT* SETTLE: HubSpot **saved views** have no public API. Lists and saved
views are different concepts. A GRANTED verdict here means the credential can use the
*Lists* API — it says nothing about resolving a saved view, which remains an open decision
(25-01 Task 3).

SAFETY
- Read-only. Two GETs at most. No write, no arming, no deploy, no activation.
- The token is read from `HUBSPOT_PRIVATE_APP_TOKEN` in ONE place (`_auth_headers`) and is
  never interpolated into output, an exception, a URL, or a returned verdict (T-25-11).
- The memberships follow-up reports ONLY a member count and a paging-cursor boolean — no
  record id, no property, no raw body. This is a scope probe and a size probe, never a
  data extract (T-25-06).
- Never raises on a refusal: a 403 is a result, not an error.

EXIT CODES
    0  the scope question was answered (granted or denied), or skipped with no credentials
    2  the question could NOT be determined (401, 5xx, timeout, transport failure)

Live-only utility: lives in scripts/ with no `test_` prefix, so pytest never collects it —
same convention as scripts/check_provider_credits.py. Its pure functions are unit-tested
offline with MOCKED requests in tests/test_check_hubspot_list_scope.py; no live call ever
happens in the suite.

Usage (the repo's documented dotenv wrapper — a bare `python scripts/...` from a fresh
shell silently sees no credentials and skips):

    .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; \
runpy.run_path('scripts/check_hubspot_list_scope.py', run_name='__main__')" "<list name>"

This script deliberately does NOT call load_dotenv() itself — the wrapper owns that, so the
runbook command and the code agree.
"""
import argparse
import os
import sys
from urllib.parse import quote

HUBSPOT_BASE = "https://api.hubapi.com"
COMPANIES_OBJECT_TYPE_ID = "0-2"  # contacts would be 0-1
TIMEOUT_SECONDS = 15  # finite, and no retry: one shot per probe

GRANTED = "granted"
DENIED = "denied"
UNAUTHENTICATED = "unauthenticated"
INCONCLUSIVE = "inconclusive"

_ANSWERED = (GRANTED, DENIED)  # a determined answer -> exit 0

_REASONS = {
    GRANTED: {
        200: "the list resolved, so the credential can read the Lists API.",
        404: "the request was AUTHORIZED and only the list name failed to match — a 404 "
             "still proves the scope IS granted.",
    },
    DENIED: "HubSpot refused the request itself: the credential is missing crm.lists.read.",
    UNAUTHENTICATED: "the token was rejected outright. This is NOT evidence about scope in "
                     "either direction — fix the token and re-run.",
    INCONCLUSIVE: "the scope question could not be determined from this response.",
}


# --- pure classification (never sees the token, never touches the network) ----------------

def _extract_list_id(body):
    """Read the list id out of a 200 body, tolerating any shape mismatch."""
    if not isinstance(body, dict):
        return None
    inner = body.get("list")
    source = inner if isinstance(inner, dict) else body
    list_id = source.get("listId")
    return None if list_id is None else str(list_id)


def classify_scope(status, body=None) -> dict:
    """Turn an HTTP status (or None for a transport failure) plus a parsed body into a
    verdict mapping. Pure: no I/O, no environment, no token."""
    if status == 200:
        return {"verdict": GRANTED, "status": 200, "list_id": _extract_list_id(body),
                "reason": _REASONS[GRANTED][200]}
    if status == 404:
        return {"verdict": GRANTED, "status": 404, "list_id": None,
                "reason": _REASONS[GRANTED][404]}
    if status == 403:
        return {"verdict": DENIED, "status": 403, "list_id": None, "reason": _REASONS[DENIED]}
    if status == 401:
        return {"verdict": UNAUTHENTICATED, "status": 401, "list_id": None,
                "reason": _REASONS[UNAUTHENTICATED]}
    return {"verdict": INCONCLUSIVE, "status": status, "list_id": None,
            "reason": _REASONS[INCONCLUSIVE]}


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def summarize_memberships(status, body) -> dict:
    """Reduce a memberships response to a COUNT and a cursor boolean and nothing else.
    Pure. Deliberately drops every record id and property (T-25-06)."""
    results = body.get("results") if isinstance(body, dict) else None
    total = body.get("total") if isinstance(body, dict) else None

    if _is_number(total):
        count = int(total)
    elif isinstance(results, list):
        count = len(results)
    else:
        count = None

    paging = body.get("paging") if isinstance(body, dict) else None
    nxt = paging.get("next") if isinstance(paging, dict) else None
    has_cursor = bool(nxt.get("after")) if isinstance(nxt, dict) else False

    return {"status": status, "member_count": count, "has_paging_cursor": has_cursor}


# --- thin live callers (live-only; exercised in tests with `requests` patched) -------------

def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _auth_headers() -> dict:
    """The ONLY place the token is read. The value goes into a header and nowhere else."""
    return {"Authorization": "Bearer " + os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "")}


def _safe_json(response):
    try:
        return response.json()
    except Exception:
        return None


def probe_list_scope(list_name: str, object_type_id: str) -> dict:
    """GET the list-by-name endpoint and classify the status. Never raises: a transport
    failure degrades to an inconclusive verdict carrying only the exception TYPE name (an
    exception's own text is never printed, so a URL/header can never leak through it)."""
    import requests
    url = (f"{HUBSPOT_BASE}/crm/v3/lists/object-type-id/{quote(str(object_type_id), safe='')}"
           f"/name/{quote(list_name, safe='')}")
    try:
        response = requests.get(url, headers=_auth_headers(), timeout=TIMEOUT_SECONDS)
    except Exception as exc:
        return {**classify_scope(None), "error": type(exc).__name__}
    return classify_scope(response.status_code, _safe_json(response))


def probe_memberships(list_id: str) -> dict:
    """GET the memberships endpoint for a resolved list id and report only its size."""
    import requests
    url = f"{HUBSPOT_BASE}/crm/v3/lists/{quote(str(list_id), safe='')}/memberships"
    try:
        response = requests.get(url, headers=_auth_headers(), timeout=TIMEOUT_SECONDS)
    except Exception as exc:
        return {"status": None, "member_count": None, "has_paging_cursor": None,
                "error": type(exc).__name__}
    return summarize_memberships(response.status_code, _safe_json(response))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only probe: does this HubSpot token carry crm.lists.read?",
        epilog="A nonsense list name is a valid input — a 404 answers the scope question "
               "(granted) just as well as a 200 does, and a 403 answers it the other way. "
               "Run through the dotenv wrapper documented at the top of this file.")
    parser.add_argument("list_name", help="Name of a list in the portal (any string works).")
    parser.add_argument("object_type_id", nargs="?", default=COMPANIES_OBJECT_TYPE_ID,
                        help=f"HubSpot object type id (default {COMPANIES_OBJECT_TYPE_ID} = "
                             f"companies; contacts are 0-1).")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN is not set, so NO request "
              "was made and NOTHING was probed.")
        print("  This is NOT a scope verdict. The question is still unanswered — re-run "
              "through the dotenv wrapper documented at the top of this file.")
        return 0

    result = probe_list_scope(args.list_name, args.object_type_id)
    print(f"lists-scope: verdict={result['verdict']} status={result['status']} "
          f"list_id={result['list_id']}")
    print(f"  {result['reason']}")
    if result.get("error"):
        print(f"  transport failure: {result['error']} (no answer obtained)")

    if result["verdict"] == GRANTED and result["list_id"]:
        members = probe_memberships(result["list_id"])
        print(f"  memberships: status={members['status']} "
              f"member_count={members['member_count']} "
              f"has_paging_cursor={members['has_paging_cursor']}")
        if members.get("error"):
            print(f"  memberships transport failure: {members['error']}")

    print("  scope: this settles the LISTS API only. HubSpot saved views are a different "
          "concept with no public API; nothing here says a saved view can be resolved.")
    return 0 if result["verdict"] in _ANSWERED else 2


if __name__ == "__main__":
    sys.exit(main())
