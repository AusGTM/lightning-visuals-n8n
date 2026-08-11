# tests/test_contact_ingest.py
#
# Phase 8 functional proof for the contact ingestion pipeline. Fully OFFLINE and
# DETERMINISTIC: no HUBSPOT token, no ANTHROPIC key, no network. HubSpot search/get are
# injected canned-dict stubs (test_identity convention); classify_field_with_haiku is
# monkeypatched at the merge_policy import site (test_main convention); requests.get/
# post/patch are sentinels that raise if a live call ever leaks in dry-run.
#
# The load-bearing correctness claim proven here is BOTH DIRECTIONS of email handling:
#   * ENRICH (match): email is manual_protected -> NEVER promoted to canonical from csv.
#   * CREATE (net_new): email IS written as the new record's identity (create bypasses
#     the merge policy — nothing to protect on a record that does not exist yet).
import json

import pytest

from src.ingest import run_contact_ingest

CSV = "tests/fixtures/uploads/contacts.csv"


def make_search(email_seq, other=None):
    # email_seq: a list of results-lists consumed one-per-email-EQ call, so a single
    # row can flip 0-hits (resolve -> net_new) to a hit (recheck -> dup). Non-email keys
    # (linkedin/phone/name) default to 0 hits so a no-email row lands ambiguous.
    other = other or {}
    seq = list(email_seq)
    state = {"i": 0}

    def hs_search(object_type, filters, properties=None, limit=100):
        prop = filters[0]["propertyName"]
        if prop == "email":
            i = state["i"]
            state["i"] += 1
            return {"results": seq[i] if i < len(seq) else []}
        return other.get(prop, {"results": []})

    return hs_search


def make_get():
    # A matched contact with a BLANK phone (fill_blank_only fills it) and a PRESENT
    # jobtitle (stale_refreshable -> needs_review) and a present email (manual_protected).
    def hs_get(object_type, record_id, properties):
        return {"id": "123", "properties": {
            "email": "bob.smith@example.com",
            "firstname": "Bob",
            "lastname": "Smith",
            "jobtitle": "Sales Manager",
            "phone": "",
        }}

    return hs_get


def promote_fake(record, field, current_value, candidates, policy):
    # Promote-style classifier (test_main convention). The deterministic gate still
    # reverts email (stage/needs_review) and jobtitle (needs_review) before promotion.
    return {"decision": "promote", "confidence": 90, "reason": "test",
            "requires_sonnet_validation": False}


def raise_http(*args, **kwargs):
    raise AssertionError("a live HubSpot request leaked in dry-run")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ALLOW_JUDGE_ESCALATION", "false")
    monkeypatch.setattr("src.merge_policy.classify_field_with_haiku", promote_fake)
    monkeypatch.setattr("src.hubspot_client.requests.get", raise_http)
    monkeypatch.setattr("src.hubspot_client.requests.post", raise_http)
    monkeypatch.setattr("src.hubspot_client.requests.patch", raise_http)


def test_matched_row_patches_without_canonical_email():
    # ENRICH direction: alice's email hits an existing contact -> PATCH.
    report = run_contact_ingest(
        CSV, hs_search=make_search([[{"id": "123"}]]), hs_get=make_get(),
        allow_create=False, dry_run=True, upload_confidence=85)

    patch = [e for e in report if e["action"] == "patch"]
    assert len(patch) == 1
    m = patch[0]
    # Phase 15: csv value is staged INSIDE the provenance blob (no flat staging keys) ...
    provenance = json.loads(m["payload"]["lv_contact_enrichment_provenance"])
    assert provenance["email"]["source"] == "csv"
    # ... but email is manual_protected: NEVER a bare canonical email write.
    assert "email" not in m["canonical_patch"]
    assert "email" not in m["payload"]
    # blank phone (fill_blank_only) is filled; present jobtitle (stale) is withheld.
    assert "phone" in m["canonical_patch"]
    assert "jobtitle" not in m["canonical_patch"]

    # whole-batch coverage: no-email bob -> ambiguous review; empty coordinator -> skip.
    assert any(e["outcome"] == "ambiguous" and e["action"] == "review" for e in report)
    assert any(e["action"] == "skip" for e in report)


def test_net_new_creates_with_email_when_flag_on_and_recheck_clear():
    # CREATE direction: alice resolves net_new (0 hits) and the recheck stays clear ->
    # create, with email written as the new record's identity.
    report = run_contact_ingest(
        CSV, hs_search=make_search([[], []]), hs_get=make_get(),
        allow_create=True, dry_run=True, upload_confidence=85)

    created = [e for e in report if e["action"] == "create"]
    assert len(created) == 1
    props = created[0]["payload"]["payload"]["properties"]
    assert props["email"] == "alice@example.com"


def test_net_new_create_payload_uses_live_property_names():
    # merge-policy-bare-name-400: the create path is the third live-write boundary.
    # `create_props` is keyed by candidate canonical_field, so alice's LinkedIn column
    # emitted bare "linkedin_url" — which is not a live property (PN-1 renamed it to
    # lv_linkedin_url) and 400s the create. The wire payload must carry the live name.
    report = run_contact_ingest(
        CSV, hs_search=make_search([[], []]), hs_get=make_get(),
        allow_create=True, dry_run=True, upload_confidence=85)

    props = [e for e in report if e["action"] == "create"][0]["payload"]["payload"]["properties"]
    assert props["lv_linkedin_url"] == "https://linkedin.com/in/alice"
    assert "linkedin_url" not in props  # the bare name must never reach HubSpot
    # native identity fields are genuinely native and must pass through untranslated
    assert props["email"] == "alice@example.com"


def test_net_new_downgraded_to_review_when_recheck_finds_dup():
    # A dup appearing between resolution and create must block the create.
    report = run_contact_ingest(
        CSV, hs_search=make_search([[], [{"id": "9"}]]), hs_get=make_get(),
        allow_create=True, dry_run=True, upload_confidence=85)

    assert not any(e["action"] == "create" for e in report)
    dup = [e for e in report if e["outcome"] == "net_new"]
    assert len(dup) == 1
    assert dup[0]["action"] == "review"
    assert "dup" in dup[0]["reason"]


def test_net_new_is_review_when_flag_off():
    # ALLOW_CONTACT_CREATE off => net_new never creates, even with a clear recheck.
    report = run_contact_ingest(
        CSV, hs_search=make_search([[], []]), hs_get=make_get(),
        allow_create=False, dry_run=True, upload_confidence=85)

    assert not any(e["action"] == "create" for e in report)
    net_new = [e for e in report if e["outcome"] == "net_new"]
    assert len(net_new) == 1
    assert net_new[0]["action"] == "review"


def test_no_network_across_scenarios():
    # The autouse sentinels raise if any requests.* fires; reaching here proves zero
    # live writes for both the match (dry-run PATCH) and create (dry-run POST) paths.
    run_contact_ingest(CSV, hs_search=make_search([[{"id": "123"}]]), hs_get=make_get(),
                       allow_create=False, dry_run=True, upload_confidence=85)
    run_contact_ingest(CSV, hs_search=make_search([[], []]), hs_get=make_get(),
                       allow_create=True, dry_run=True, upload_confidence=85)
