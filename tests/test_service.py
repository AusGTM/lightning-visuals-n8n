# tests/test_service.py
#
# Phase 10 (P10-SC1): offline gate for the decision service. Hermetic conventions are
# copied verbatim from tests/test_e2e_ingest.py: no HUBSPOT token, no ANTHROPIC key,
# classify_field_with_haiku monkeypatched, and requests.get/post/patch sentinels that
# raise if any live call leaks. Reaching the assertions proves ZERO network.
import json

from fastapi.testclient import TestClient

import pytest

from src.service import app

client = TestClient(app)

CSV = "tests/fixtures/uploads/contacts_e2e.csv"


def promote_fake(record, field, current_value, candidates, policy):
    return {"decision": "promote", "confidence": 90, "reason": "test",
            "requires_sonnet_validation": False}


def raise_http(*args, **kwargs):
    raise AssertionError("a live HubSpot request leaked in the service")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ALLOW_JUDGE_ESCALATION", "false")
    monkeypatch.setattr("src.merge_policy.classify_field_with_haiku", promote_fake)
    monkeypatch.setattr("src.hubspot_client.requests.get", raise_http)
    monkeypatch.setattr("src.hubspot_client.requests.post", raise_http)
    monkeypatch.setattr("src.hubspot_client.requests.patch", raise_http)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ingest_dry_run_patch_and_create_gate_honored():
    r = client.post("/ingest", json={"path": CSV, "allow_create": False})
    assert r.status_code == 200
    report = r.json()
    assert isinstance(report, list)

    # Row A -> a dry-run PATCH: action "patch" carrying a non-empty payload (the PATCH
    # body that WOULD be sent). No live write happened (sentinels armed => zero network).
    match = next(e for e in report if e["outcome"] == "match")
    assert match["action"] == "patch"
    assert isinstance(match["payload"], dict) and match["payload"]
    # Phase 15: staged inside the provenance blob (no flat staging keys), never a bare
    # canonical email write.
    provenance = json.loads(match["payload"]["lv_contact_enrichment_provenance"])
    assert provenance["email"]["source"] == "csv"

    # SC3 gate: allow_create False => NO create action anywhere in the report.
    assert not any(e["action"] == "create" for e in report)


def test_ingest_gate_flips_when_allow_create_true():
    # Sanity: with the gate ON, Row B (alice@, net_new, clear recheck) becomes a create.
    r = client.post("/ingest", json={"path": CSV, "allow_create": True})
    report = r.json()
    creates = [e for e in report if e["action"] == "create"]
    assert len(creates) == 1 and creates[0]["outcome"] == "net_new"


def test_sweep_finds_duplicates_and_mangled():
    records = [
        {"id": "1", "properties": {"email": "dup@example.com", "phone": "0400 111 222"}},
        {"id": "2", "properties": {"email": "DUP@example.com", "phone": "0400 333 444"}},
        {"id": "3", "properties": {"email": "solo@example.com", "phone": "not-a-phone"}},
    ]
    r = client.post("/sweep", json={"records": records})
    assert r.status_code == 200
    rep = r.json()
    assert rep["duplicate_count"] >= 1          # ids 1 & 2 share one normalized email
    assert rep["mangled_count"] >= 1            # id 3 unparseable phone
    assert any(m["field"] == "phone" for m in rep["mangled"])
    assert set(rep["to_review_ids"]) >= {"1", "2", "3"}


def test_zero_network():
    # Reaching here with the autouse sentinels armed proves the service made zero live
    # HubSpot/LLM calls across the ingest (dry-run PATCH) and sweep paths.
    client.post("/ingest", json={"path": CSV, "allow_create": False})
