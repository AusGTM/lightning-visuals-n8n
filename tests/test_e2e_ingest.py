# tests/test_e2e_ingest.py
#
# Phase 9 (P9-SC1): ONE multi-row upload drives EVERY ingestion path at once, fully
# offline. Hermetic conventions are copied verbatim from tests/test_contact_ingest.py:
# no HUBSPOT token, no ANTHROPIC key, classify_field_with_haiku monkeypatched, and
# requests.get/post/patch sentinels that raise if any live call leaks in dry-run.
#
# The five rows map to the five paths (see contacts_e2e.csv). required_identity is
# email OR firstname+lastname+company, so:
#   Row A (bob.smith@ + full row) -> confident email match -> PATCH/enrich
#   Row B (alice@ + full row)     -> valid email, 0 hits   -> net_new -> CREATE
#   Row C (no email, phone+lastname+company) -> weak phone+lastname hit -> ambiguous
#   Row D (no email, name+company, NO phone) -> name+company miss -> hard no-email rule
#   Row E (only jobtitle+phone, no identity key) -> REJECTED at LOAD, never resolved
import json

import pytest

from src.ingest import run_contact_ingest

CSV = "tests/fixtures/uploads/contacts_e2e.csv"

# Value-routed search lookup keyed on NORMALIZED (propertyName, value). resolve_identity
# normalizes before searching, so keys here are already E.164 / lowercased-email. Value
# routing is inherently call-count-safe for the net_new recheck: the SAME "alice@" value
# yields the SAME empty result on both the resolve call and the pre-create recheck call,
# so the create proceeds without needing a per-call counter.
_LOOKUP = {
    ("email", "bob.smith@example.com"): [{"id": "123"}],   # Row A single match
    ("email", "alice@example.com"): [],                    # Row B net_new + clear recheck
    ("phone", "+61400222333"): [{"id": "777"}],            # Row C weak-key hit -> ambiguous
    # Everything else (Row D firstname EQ, linkedin, etc.) defaults to [] below.
}


def hs_search(object_type, filters, properties=None, limit=100):
    f0 = filters[0]
    return {"results": _LOOKUP.get((f0["propertyName"], f0["value"]), [])}


def hs_get(object_type, record_id, properties):
    # Row-A existing contact for the enrich invariants: present+DIFFERENT jobtitle
    # (stale_refreshable -> needs_review, withheld), BLANK phone (fill_blank_only fills),
    # PRESENT linkedin (fill_blank_only staged, never clobbered), present email
    # (manual_protected, never a bare canonical write).
    return {"id": "123", "properties": {
        "email": "bob.smith@example.com",
        "firstname": "Bob",
        "lastname": "Smith",
        "jobtitle": "Sales Manager",
        "phone": "",
        "linkedin_url": "https://linkedin.com/in/bob-existing",
    }}


def promote_fake(record, field, current_value, candidates, policy):
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


def _run():
    return run_contact_ingest(CSV, hs_search=hs_search, hs_get=hs_get,
                              allow_create=True, dry_run=True, upload_confidence=85)


def test_all_five_paths_have_exact_outcomes_and_actions():
    report = _run()

    matches = [e for e in report if e["outcome"] == "match"]
    creates = [e for e in report if e["action"] == "create"]
    reviews = [e for e in report if e["action"] == "review"]
    rejects = [e for e in report if e["outcome"] == "rejected"]

    assert len(matches) == 1 and matches[0]["action"] == "patch"
    assert len(creates) == 1 and creates[0]["outcome"] == "net_new"
    assert len(rejects) == 1 and rejects[0]["action"] == "skip"

    # Exactly two reviews: Row C weak-key match + Row D no-email hard rule.
    assert len(reviews) == 2
    reasons = sorted(r["reason"] for r in reviews)
    assert any("weak-key" in r for r in reasons)                 # Row C
    assert any("no email" in r for r in reasons)                 # Row D hard rule

    # Bound on writes: Row D (no email) must NOT create.
    assert len(creates) == 1


def test_match_row_field_invariants():
    report = _run()
    m = next(e for e in report if e["action"] == "patch")

    # Phase 15: staged INSIDE the provenance blob (no flat staging keys).
    provenance = json.loads(m["payload"]["lv_contact_enrichment_provenance"])
    # email: staged, but manual_protected -> NEVER canonical.
    assert provenance["email"]["source"] == "csv"
    assert "email" not in m["canonical_patch"]
    assert "email" not in m["payload"]
    # phone: blank on the record -> fill_blank_only promotes the upload phone.
    assert "phone" in m["canonical_patch"]
    # jobtitle: present + conflicting -> stale_refreshable needs_review, withheld.
    assert "jobtitle" not in m["canonical_patch"]
    # linkedin: present -> fill_blank_only stages but NEVER clobbers canonical.
    assert provenance["linkedin_url"]["source"] == "csv"
    assert "linkedin_url" not in m["canonical_patch"]


def test_create_writes_email_as_new_record_identity():
    report = _run()
    c = next(e for e in report if e["action"] == "create")
    # create bypasses the merge policy: email IS written as the new record's identity.
    assert c["payload"]["payload"]["properties"]["email"] == "alice@example.com"


def test_zero_network():
    # Reaching the end with the autouse sentinels armed proves zero live calls for both
    # the dry-run PATCH (match) and dry-run POST (create) paths.
    _run()
