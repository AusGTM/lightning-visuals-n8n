# src/identity.py
#
# Phase 7: conservative identity/dedupe resolver. CLASSIFY ONLY -- never create or
# PATCH. Auto-match only on STRONG keys (email / linkedin_url); a no-email row can
# NEVER become net_new; everything uncertain routes to ambiguous (needs_review).
# HubSpot search is INJECTED (default = hubspot_client.search_records) so the whole
# module is pure/deterministic and testable offline with a canned-dict stub.
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from .schemas import IdentityResult
from .normalizer import normalize_email, normalize_phone
from .hubspot_client import search_records

# Properties requested on every contact search -- enough for downstream review.
_SEARCH_PROPS = ["email", "linkedin_url", "phone", "firstname", "lastname", "company"]


def canonicalize_linkedin(url) -> Optional[str]:
    # Deterministic LinkedIn key so an EQ search is stable across trivial variants:
    # lowercase scheme+host, strip a single trailing slash, drop query/fragment.
    if not url:
        return None
    s = str(url).strip()
    if not s:
        return None
    if "//" not in s:
        s = "https://" + s
    parts = urlsplit(s)
    path = parts.path[:-1] if parts.path.endswith("/") else parts.path
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def _search_ids(hs_search, filters) -> list:
    # AND-ed filters inside the single filterGroup that search_records builds, so a
    # multi-key weak search requires ALL keys to match. Returns string ids only.
    resp = hs_search(object_type="contacts", filters=filters, properties=_SEARCH_PROPS)
    results = resp.get("results", []) or []
    return [str(r["id"]) for r in results if isinstance(r, dict) and "id" in r]


def resolve_identity(row: dict, hs_search=search_records) -> IdentityResult:
    # Pure/deterministic given the injected hs_search: no time, randomness, or globals.
    email = normalize_email(row.get("email"))        # None if absent OR invalid
    linkedin = canonicalize_linkedin(row.get("linkedin_url"))
    phone = normalize_phone(row.get("phone"))
    firstname = str(row.get("firstname") or "").strip()
    lastname = str(row.get("lastname") or "").strip()
    company = str(row.get("company") or "").strip()

    # 1. Email (STRONG). A valid email is the ONLY route to net_new.
    if email:
        ids = _search_ids(hs_search, [{"propertyName": "email", "operator": "EQ", "value": email}])
        if len(ids) == 1:
            return IdentityResult(outcome="match", contact_id=ids[0], match_key="email",
                                  candidate_ids=ids, reason="single email match")
        if len(ids) > 1:
            return IdentityResult(outcome="ambiguous", match_key="email",
                                  candidate_ids=ids, reason="multiple email matches")
        return IdentityResult(outcome="net_new", candidate_ids=[], match_key=None,
                              reason="valid email, no existing match")

    # 2. Reaching here means NO valid email. LinkedIn (STRONG).
    if linkedin:
        ids = _search_ids(hs_search, [{"propertyName": "linkedin_url", "operator": "EQ", "value": linkedin}])
        if len(ids) == 1:
            return IdentityResult(outcome="match", contact_id=ids[0], match_key="linkedin_url",
                                  candidate_ids=ids, reason="single linkedin match")
        if len(ids) > 1:
            return IdentityResult(outcome="ambiguous", match_key="linkedin_url",
                                  candidate_ids=ids, reason="multiple linkedin matches")
        # 0 hits -> fall through to weak keys.

    # 3. Weak keys: a hit here is NEVER confident -> only ever ambiguous (review).
    if phone and lastname:
        ids = _search_ids(hs_search, [
            {"propertyName": "phone", "operator": "EQ", "value": phone},
            {"propertyName": "lastname", "operator": "EQ", "value": lastname},
        ])
        if ids:
            return IdentityResult(outcome="ambiguous", match_key="phone_lastname",
                                  candidate_ids=ids, reason="weak-key match requires review")

    if firstname and lastname and company:
        ids = _search_ids(hs_search, [
            {"propertyName": "firstname", "operator": "EQ", "value": firstname},
            {"propertyName": "lastname", "operator": "EQ", "value": lastname},
            {"propertyName": "company", "operator": "EQ", "value": company},
        ])
        if ids:
            return IdentityResult(outcome="ambiguous", match_key="name_company",
                                  candidate_ids=ids, reason="weak-key match requires review")

    # 4. THE HARD SAFETY RULE (core safety property of Milestone 2): no valid email AND
    # no confident match AND no weak-key candidate -> ambiguous, NEVER net_new. Returning
    # net_new here is exactly what would let Phase 8 auto-create a no-email duplicate.
    return IdentityResult(outcome="ambiguous", contact_id=None, match_key=None,
                          candidate_ids=[], reason="no email, insufficient identity")


def resolve_batch(rows: list, hs_search=search_records) -> list:
    # Phase-6 -> Phase-7 seam: one IdentityResult per IngestBatch.rows dict, in order.
    return [resolve_identity(r, hs_search=hs_search) for r in rows]
