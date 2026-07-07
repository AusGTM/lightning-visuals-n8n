# tests/test_identity.py
#
# Offline proof for Phase 7 identity/dedupe classification. No network, no API key,
# no HUBSPOT token: hs_search is a pure canned-dict stub injected into resolve_identity,
# so the real search_records (which would read HUBSPOT_PRIVATE_APP_TOKEN and hit the
# network) is NEVER constructed or called. Every classification outcome is asserted.
from src.identity import resolve_identity, resolve_batch, canonicalize_linkedin


def make_search(canned):
    # canned: {propertyName -> {"results": [...], "total": N}}. The stub keys off
    # filters[0]["propertyName"] and records every call so a test can prove injection.
    calls = []

    def hs_search(object_type, filters, properties, limit=100):
        calls.append({"object_type": object_type, "filters": filters, "properties": properties})
        prop = filters[0]["propertyName"]
        return canned.get(prop, {"results": [], "total": 0})

    hs_search.calls = calls
    return hs_search


# --- STRONG key: email --------------------------------------------------------

def test_email_single_hit_is_match():  # P7-SC1, P7-SC2
    s = make_search({"email": {"results": [{"id": "501"}], "total": 1}})
    r = resolve_identity({"email": "alice@example.com"}, hs_search=s)
    assert r.outcome == "match"
    assert r.contact_id == "501"
    assert r.match_key == "email"
    assert r.candidate_ids == ["501"]


def test_email_multi_hit_is_ambiguous():  # P7-SC3
    s = make_search({"email": {"results": [{"id": "501"}, {"id": "502"}], "total": 2}})
    r = resolve_identity({"email": "alice@example.com"}, hs_search=s)
    assert r.outcome == "ambiguous"
    assert r.contact_id is None
    assert r.candidate_ids == ["501", "502"]


def test_email_zero_hits_is_net_new():  # P7-SC3
    s = make_search({})  # everything returns 0 hits
    r = resolve_identity({"email": "alice@example.com"}, hs_search=s)
    assert r.outcome == "net_new"
    assert r.contact_id is None
    assert r.reason == "valid email, no existing match"


# --- STRONG key: linkedin (only reached with NO valid email) ------------------

def test_no_email_linkedin_single_hit_is_match():  # P7-SC1
    s = make_search({"linkedin_url": {"results": [{"id": "777"}], "total": 1}})
    r = resolve_identity({"linkedin_url": "https://LinkedIn.com/in/alice/"}, hs_search=s)
    assert r.outcome == "match"
    assert r.match_key == "linkedin_url"
    assert r.contact_id == "777"


def test_no_email_linkedin_multi_hit_is_ambiguous():  # P7-SC3
    s = make_search({"linkedin_url": {"results": [{"id": "777"}, {"id": "778"}], "total": 2}})
    r = resolve_identity({"linkedin_url": "https://linkedin.com/in/alice"}, hs_search=s)
    assert r.outcome == "ambiguous"
    assert r.match_key == "linkedin_url"
    assert r.candidate_ids == ["777", "778"]


# --- WEAK keys: a hit is NEVER confident -> only ambiguous --------------------

def test_no_email_phone_lastname_hit_is_ambiguous_not_match_or_net_new():  # P7-SC1
    s = make_search({"phone": {"results": [{"id": "900"}], "total": 1}})
    r = resolve_identity({"phone": "0412 345 678", "lastname": "Baker"}, hs_search=s)
    assert r.outcome == "ambiguous"
    assert r.outcome != "match"     # weak key alone is never a confident match
    assert r.outcome != "net_new"   # and a no-email row is never net_new
    assert r.match_key == "phone_lastname"
    assert r.contact_id is None


def test_no_email_name_company_hit_is_ambiguous():  # P7-SC1
    s = make_search({"firstname": {"results": [{"id": "950"}], "total": 1}})
    r = resolve_identity(
        {"firstname": "Alice", "lastname": "Baker", "company": "Example Racing League"},
        hs_search=s,
    )
    assert r.outcome == "ambiguous"
    assert r.match_key == "name_company"
    assert r.contact_id is None


# --- THE HARD RULE: the single most important safety property of Milestone 2 --

def test_no_email_no_hits_is_ambiguous_never_net_new():  # P7-SC2 -- HARD RULE
    # CORE SAFETY PROPERTY: a row with no valid email and no weak-key candidate must
    # resolve to ambiguous (review), NEVER net_new -- net_new would let Phase 8
    # auto-create a no-email duplicate. This test guards exactly that.
    s = make_search({})  # zero hits on every key
    r = resolve_identity({"phone": "0412 345 678", "lastname": "Baker"}, hs_search=s)
    assert r.outcome == "ambiguous"
    assert r.outcome != "net_new"
    assert r.reason == "no email, insufficient identity"
    assert r.contact_id is None
    assert r.candidate_ids == []


def test_invalid_email_takes_no_email_path_and_is_ambiguous():  # P7-SC2
    # An unparseable email string normalizes to None -> the no-email path. With no
    # other identity keys it must be ambiguous, NOT net_new.
    s = make_search({})
    r = resolve_identity({"email": "not-an-email"}, hs_search=s)
    assert r.outcome == "ambiguous"
    assert r.outcome != "net_new"
    assert r.reason == "no email, insufficient identity"


# --- Injection / offline guarantee -------------------------------------------

def test_resolver_uses_injected_search_no_network():  # P7-SC2, P7-SC3
    s = make_search({"email": {"results": [{"id": "501"}], "total": 1}})
    resolve_identity({"email": "alice@example.com"}, hs_search=s)
    assert len(s.calls) >= 1  # the injected stub was called; real search_records untouched
    assert s.calls[0]["object_type"] == "contacts"


# --- resolve_batch preserves order -------------------------------------------

def test_resolve_batch_maps_rows_in_order():  # P7-SC3
    s = make_search({"email": {"results": [{"id": "501"}], "total": 1}})
    rows = [
        {"email": "alice@example.com"},              # -> match
        {"phone": "0412 345 678", "lastname": "X"},  # -> ambiguous (no email, no hits)
    ]
    results = resolve_batch(rows, hs_search=s)
    assert [r.outcome for r in results] == ["match", "ambiguous"]
    assert results[0].contact_id == "501"
    assert results[1].reason == "no email, insufficient identity"


# --- canonicalize_linkedin ----------------------------------------------------

def test_canonicalize_linkedin_lowercases_host_and_strips_trailing_slash():
    out = canonicalize_linkedin("https://LinkedIn.com/in/Alice/")
    assert out == "https://linkedin.com/in/Alice"
    assert canonicalize_linkedin("") is None
    assert canonicalize_linkedin(None) is None
    # scheme-less input still normalizes to a stable https key
    assert canonicalize_linkedin("LinkedIn.com/in/Bob").startswith("https://linkedin.com")
