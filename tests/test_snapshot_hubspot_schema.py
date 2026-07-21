# tests/test_snapshot_hubspot_schema.py
#
# Phase 15 Task 1 — offline proof for the read-only schema-snapshot + probe tool.
# Mirrors tests/test_main.py's no_http sentinel pattern: requests.* raises if a live call
# ever leaks through the no-credentials / portal-mismatch / DRY_RUN guards.
import json

import pytest
import requests

import scripts.snapshot_hubspot_schema as snap


def raise_http(*args, **kwargs):
    raise AssertionError("a live HubSpot request leaked past a guard that should have refused")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)
    monkeypatch.delenv("HUBSPOT_PORTAL_ID", raising=False)
    monkeypatch.delenv("TEST_COMPANY_IDS", raising=False)
    monkeypatch.setattr(requests, "get", raise_http)
    monkeypatch.setattr(requests, "patch", raise_http)


def test_no_credentials_skips_cleanly(capsys):
    rc = snap.main([])
    assert rc == 0
    assert "skipped (no credentials)" in capsys.readouterr().out


def test_portal_mismatch_refuses_before_any_call(monkeypatch, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "99999999")
    rc = snap.main([])
    assert rc != 0
    assert "REFUSED" in capsys.readouterr().out


def test_probe_flag_alone_does_not_fire_without_dry_run_false(monkeypatch, capsys):
    # Two-key gate: --probe without DRY_RUN=false must never reach requests.patch (the
    # hermetic fixture's raise_http would fail the test if it did). Also short-circuits
    # before the snapshot GETs by simulating no credentials — this test targets the
    # probe gate specifically, so isolate it via a direct _run_probe-adjacent check.
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", snap.EXPECTED_PORTAL_ID)
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setattr(snap, "_get_properties_raw", lambda object_type: '{"results": []}')
    monkeypatch.setattr(snap, "_write_snapshot", lambda *a, **k: snap.BASELINE_DIR)
    rc = snap.main(["--probe"])
    assert rc == 0
    assert "refusing (two-key gate)" in capsys.readouterr().out


def test_write_snapshot_never_leaks_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "pat-na1-super-secret-value")
    fixture_body = {
        "results": [
            {"name": "lv_org_type", "label": "Org Type", "type": "string",
             "fieldType": "text", "groupName": "companyinformation",
             "hubspotDefined": False, "options": []},
        ]
    }
    raw = json.dumps(fixture_body, indent=2)
    path = snap._write_snapshot("companies", raw, None, directory=tmp_path)
    text = path.read_text()
    assert "Authorization" not in text
    assert "pat-na1-super-secret-value" not in text
    assert "HUBSPOT_PRIVATE_APP_TOKEN" not in text
    assert json.loads(text) == fixture_body
