# tests/test_sync_hubspot_properties.py
#
# Phase 15 Task 3 — offline proof for the forward property-migration tool. Fully
# deterministic: no network. Mirrors tests/test_main.py's no_http sentinel pattern for the
# guard tests, and monkeypatches the live-call seams (_get_live_properties/_groups,
# _create_property_live/_create_group_live) for the diff/manifest tests.
import json

import pytest
import requests

import scripts.sync_hubspot_properties as sync


# --- compute_property_diff / compute_group_diff: pure functions, no I/O ------------

def test_create_list_is_desired_minus_actual():
    desired = [{"name": "lv_a", "type": "string", "fieldType": "text", "options": []},
               {"name": "lv_b", "type": "string", "fieldType": "text", "options": []}]
    actual = [{"name": "lv_a", "type": "string", "fieldType": "text", "options": [],
               "hubspotDefined": False}]
    diff = sync.compute_property_diff(desired, actual)
    assert [p["name"] for p in diff["create"]] == ["lv_b"]
    assert diff["drift"] == []


def test_idempotency_empty_create_list_when_everything_already_present():
    desired = [{"name": "lv_a", "type": "string", "fieldType": "text", "options": []}]
    actual = [{"name": "lv_a", "type": "string", "fieldType": "text", "options": [],
               "hubspotDefined": False}]
    diff = sync.compute_property_diff(desired, actual)
    assert diff["create"] == []
    assert diff["drift"] == []


def test_drift_on_mismatching_type_is_reported_never_created_never_autofixed():
    desired = [{"name": "lv_a", "type": "string", "fieldType": "text", "options": []}]
    actual = [{"name": "lv_a", "type": "number", "fieldType": "number", "options": [],
               "hubspotDefined": False}]
    diff = sync.compute_property_diff(desired, actual)
    assert diff["create"] == []
    assert len(diff["drift"]) == 1
    assert diff["drift"][0]["name"] == "lv_a"


def test_hubspot_defined_property_never_proposed_even_on_name_collision():
    desired = [{"name": "email", "type": "enumeration", "fieldType": "select",
                "options": [{"value": "x", "label": "X"}]}]
    actual = [{"name": "email", "type": "string", "fieldType": "text", "options": [],
               "hubspotDefined": True}]
    diff = sync.compute_property_diff(desired, actual)
    assert diff["create"] == []
    assert diff["drift"] == []


def test_group_diff_create_list():
    desired_groups = [{"name": "lv_enrichment", "label": "LV Enrichment"}]
    assert sync.compute_group_diff(desired_groups, []) == desired_groups
    assert sync.compute_group_diff(desired_groups, [{"name": "lv_enrichment"}]) == []


# --- guards + dry-run-by-default: exercised via main(), offline -------------------

def raise_http(*args, **kwargs):
    raise AssertionError("a live HubSpot request leaked past a guard/gate that should have refused")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)
    monkeypatch.delenv("HUBSPOT_PORTAL_ID", raising=False)
    monkeypatch.delenv("ALLOW_HUBSPOT_PROPERTY_WRITES", raising=False)
    monkeypatch.setattr(requests, "post", raise_http)
    monkeypatch.setattr(requests, "delete", raise_http)


def test_no_credentials_skips_cleanly(capsys):
    rc = sync.main([])
    assert rc == 0
    assert "skipped (no credentials)" in capsys.readouterr().out


def test_portal_mismatch_refuses_before_any_call(monkeypatch, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "99999999")
    rc = sync.main([])
    assert rc != 0
    assert "REFUSED" in capsys.readouterr().out


def test_dry_run_default_makes_zero_post_calls_deliberate_break_proof(monkeypatch, capsys):
    # DELIBERATE-BREAK proof: requests.post is monkeypatched to raise (hermetic fixture).
    # A default (dry-run) run must complete without ever tripping it — proves the two-key
    # gate holds even with real credentials + matching portal present.
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", sync.EXPECTED_PORTAL_ID)
    monkeypatch.setattr(sync, "_get_live_properties", lambda object_type: [])
    monkeypatch.setattr(sync, "_get_live_groups", lambda object_type: [])
    rc = sync.main([])  # DRY_RUN defaults "true"; ALLOW_HUBSPOT_PROPERTY_WRITES defaults "false"
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "Properties to create" in out


# --- undo manifest: only confirmed 201s ------------------------------------------

def test_manifest_records_only_confirmed_201s(monkeypatch, tmp_path):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", sync.EXPECTED_PORTAL_ID)
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_HUBSPOT_PROPERTY_WRITES", "true")

    get_props_calls = {"n": 0}

    def fake_get_properties(object_type):
        get_props_calls["n"] += 1
        if get_props_calls["n"] == 1:
            return []  # pre-diff GET: nothing exists yet
        return [{"name": "lv_ok"}]  # post-write confirmation GET: only the 201 landed

    get_groups_calls = {"n": 0}

    def fake_get_groups(object_type):
        get_groups_calls["n"] += 1
        if get_groups_calls["n"] == 1:
            return []
        return [{"name": "lv_enrichment"}]

    monkeypatch.setattr(sync, "_get_live_properties", fake_get_properties)
    monkeypatch.setattr(sync, "_get_live_groups", fake_get_groups)
    monkeypatch.setattr(sync, "_create_group_live", lambda object_type, group: (201, dict(group)))

    statuses = iter([201, 400])  # first property succeeds (201), second fails (400)

    def fake_create_property(object_type, prop):
        return next(statuses), dict(prop)

    monkeypatch.setattr(sync, "_create_property_live", fake_create_property)

    desired = {
        "groups": [{"name": "lv_enrichment", "label": "LV Enrichment"}],
        "properties": [
            {"name": "lv_ok", "type": "string", "fieldType": "text",
             "groupName": "lv_enrichment", "options": []},
            {"name": "lv_fail", "type": "string", "fieldType": "text",
             "groupName": "lv_enrichment", "options": []},
        ],
    }
    run_id = "test-run-1"
    sync.sync_object_type("companies", desired, run_id, live_writes=True, manifest_dir=tmp_path)

    manifest = json.loads((tmp_path / f"undo-manifest-{run_id}.json").read_text())
    prop_names = [e["name"] for e in manifest if e["kind"] == "property"]
    assert prop_names == ["lv_ok"]
    assert "lv_fail" not in prop_names
    group_names = [e["name"] for e in manifest if e["kind"] == "group"]
    assert group_names == ["lv_enrichment"]
