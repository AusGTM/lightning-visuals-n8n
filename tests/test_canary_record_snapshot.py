# tests/test_canary_record_snapshot.py
#
# Phase 22 Plan 01 Task 1 — offline proof for scripts/canary_record_snapshot.py.
# Fully hermetic: no network. `get_record` is monkeypatched at the module level (never
# `requests.*` directly, since the script never calls requests itself — it goes through
# src/hubspot_client.get_record, the only HubSpot function this module may call), and
# `requests.get`/`requests.post` are additionally poisoned as defense-in-depth, matching
# tests/test_snapshot_hubspot_schema.py's hermetic convention.
import json
from pathlib import Path

import pytest
import requests

import scripts.canary_record_snapshot as snap
from src import taxonomy


def _raise_http(*args, **kwargs):
    raise AssertionError("a live HubSpot request leaked past a guard that should have refused")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)
    monkeypatch.delenv("HUBSPOT_PORTAL_ID", raising=False)
    monkeypatch.setattr(requests, "get", _raise_http)
    monkeypatch.setattr(requests, "post", _raise_http)
    monkeypatch.setattr(requests, "patch", _raise_http)


# --- guard: no write path exists in this module (T-22-01) ---------------------------------

def test_module_source_has_no_write_call():
    text = Path(snap.__file__).read_text()
    for forbidden in ("patch_record", "create_record", "requests.patch", "requests.post"):
        assert forbidden not in text, f"{forbidden!r} must never appear in a read-only tool"


# --- guard: evidence-gated vocabulary is imported, never re-typed -------------------------

def test_predicted_evidence_gated_set_matches_taxonomy():
    assert set(snap.evidence_gated_org_types()) == set(taxonomy.EVIDENCE_GATED_ORG_TYPES)
    assert len(snap.evidence_gated_org_types()) > 0


# --- prediction truth table (must_haves behaviour table) ----------------------------------

@pytest.mark.parametrize("org_type", [None, "", "unknown"])
def test_prediction_fires_when_org_type_unresolved(org_type):
    result = snap.predict_research_gate({"lv_org_type": org_type, "lv_produces_content": True})
    assert result["research_gate_will_fire"] is True
    assert "unresolved" in result["reason"]


def test_prediction_fires_for_evidence_gated_org_type_even_with_content_present():
    # The case "most likely to be misjudged by eye": org type IS resolved to a real
    # taxonomy value, content IS present — but that value requires evidence, so research
    # still fires.
    gated = taxonomy.EVIDENCE_GATED_ORG_TYPES[0]
    result = snap.predict_research_gate({"lv_org_type": gated, "lv_produces_content": True})
    assert result["research_gate_will_fire"] is True
    assert "evidence-gated" in result["reason"]


def test_prediction_does_not_fire_when_org_type_resolved_non_gated_and_content_present():
    non_gated = next(k for k in taxonomy.ORG_TYPES if k not in taxonomy.EVIDENCE_GATED_ORG_TYPES
                      and k != taxonomy.DEFAULT_ORG_TYPE)
    result = snap.predict_research_gate({"lv_org_type": non_gated, "lv_produces_content": True})
    assert result["research_gate_will_fire"] is False


@pytest.mark.parametrize("content", [None, ""])
def test_prediction_fires_when_content_blank_regardless_of_org_type(content):
    non_gated = next(k for k in taxonomy.ORG_TYPES if k not in taxonomy.EVIDENCE_GATED_ORG_TYPES
                      and k != taxonomy.DEFAULT_ORG_TYPE)
    result = snap.predict_research_gate({"lv_org_type": non_gated, "lv_produces_content": content})
    assert result["research_gate_will_fire"] is True
    assert "blank" in result["reason"]


# --- compare mode: neighbour verdict -------------------------------------------------------

def _fixed_snapshot(target_props, neighbor_props):
    return {
        "label": "pre-canary",
        "target": {
            "object_type": "companies", "id": "9604614548",
            "requested_properties": ["lv_org_type", "hs_lastmodifieddate"],
            "properties": target_props,
            "modified_property": "hs_lastmodifieddate",
            "modified_value": target_props.get("hs_lastmodifieddate"),
        },
        "neighbors": [{
            "object_type": "contacts", "id": "201",
            "requested_properties": ["jobtitle", "lastmodifieddate"],
            "properties": neighbor_props,
            "modified_property": "lastmodifieddate",
            "modified_value": neighbor_props.get("lastmodifieddate"),
        }],
        "prediction": None,
    }


def test_compare_unchanged_neighbor_reports_zero_changed(monkeypatch):
    target_props = {"lv_org_type": "unknown", "hs_lastmodifieddate": "T1"}
    neighbor_props = {"jobtitle": "CEO", "lastmodifieddate": "N1"}
    snapshot = _fixed_snapshot(target_props, neighbor_props)

    def fake_get_record(object_type, record_id, properties):
        if object_type == "companies":
            return {"properties": dict(target_props)}  # target unchanged too
        return {"properties": dict(neighbor_props)}

    monkeypatch.setattr(snap, "get_record", fake_get_record)
    result = snap.compare_snapshot(snapshot)
    assert result["neighbors_changed"] == 0
    assert result["neighbors"][0]["changed"] is False


def test_compare_changed_neighbor_named_field_by_field(monkeypatch):
    target_props = {"lv_org_type": "unknown", "hs_lastmodifieddate": "T1"}
    neighbor_props_before = {"jobtitle": "CEO", "lastmodifieddate": "N1"}
    neighbor_props_after = {"jobtitle": "CFO", "lastmodifieddate": "N2"}
    snapshot = _fixed_snapshot(target_props, neighbor_props_before)

    def fake_get_record(object_type, record_id, properties):
        if object_type == "companies":
            return {"properties": dict(target_props)}
        return {"properties": dict(neighbor_props_after)}

    monkeypatch.setattr(snap, "get_record", fake_get_record)
    result = snap.compare_snapshot(snapshot)
    assert result["neighbors_changed"] == 1
    changed_fields = result["neighbors"][0]["changed_fields"]
    assert changed_fields["jobtitle"] == {"before": "CEO", "after": "CFO"}
    assert changed_fields["lastmodifieddate"] == {"before": "N1", "after": "N2"}


def test_compare_changed_target_is_reported_but_does_not_fail_the_run(monkeypatch):
    target_props_before = {"lv_org_type": "unknown", "hs_lastmodifieddate": "T1"}
    target_props_after = {"lv_org_type": "governing_body_league", "hs_lastmodifieddate": "T2"}
    neighbor_props = {"jobtitle": "CEO", "lastmodifieddate": "N1"}
    snapshot = _fixed_snapshot(target_props_before, neighbor_props)

    def fake_get_record(object_type, record_id, properties):
        if object_type == "companies":
            return {"properties": dict(target_props_after)}
        return {"properties": dict(neighbor_props)}  # neighbour untouched

    monkeypatch.setattr(snap, "get_record", fake_get_record)
    result = snap.compare_snapshot(snapshot)
    assert result["neighbors_changed"] == 0
    assert result["target"]["changed_fields"]["lv_org_type"] == {
        "before": "unknown", "after": "governing_body_league",
    }
    # main() exit code is driven only by neighbors_changed, never by the target diff.


def test_main_compare_exit_code_reflects_only_neighbor_changes(tmp_path, monkeypatch, capsys):
    target_props = {"lv_org_type": "unknown", "hs_lastmodifieddate": "T1"}
    neighbor_props_before = {"jobtitle": "CEO", "lastmodifieddate": "N1"}
    neighbor_props_after = {"jobtitle": "CFO", "lastmodifieddate": "N2"}
    snapshot = _fixed_snapshot(target_props, neighbor_props_before)
    snapshot_path = tmp_path / "snap.json"
    snapshot_path.write_text(json.dumps(snapshot))

    def fake_get_record(object_type, record_id, properties):
        if object_type == "companies":
            return {"properties": dict(target_props)}
        return {"properties": dict(neighbor_props_after)}

    monkeypatch.setattr(snap, "get_record", fake_get_record)
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", snap.EXPECTED_PORTAL_ID)

    rc = snap.main(["compare", "--snapshot", str(snapshot_path)])
    assert rc != 0
    out = capsys.readouterr().out
    assert "neighbors_changed: 1" in out


# --- no-credentials skip path: zero requests, exit 0 ---------------------------------------

def test_no_credentials_skips_cleanly_with_zero_requests(capsys):
    rc = snap.main([])
    assert rc == 0
    assert "skipped (no credentials)" in capsys.readouterr().out


def test_portal_mismatch_refuses_before_any_call(monkeypatch, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "99999999")
    rc = snap.main([])
    assert rc != 0
    assert "REFUSED" in capsys.readouterr().out


# --- snapshot mode: writes exactly one artifact, prints prediction -------------------------

def test_snapshot_mode_writes_one_artifact_and_prints_prediction(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", snap.EXPECTED_PORTAL_ID)
    monkeypatch.setattr(snap, "SNAPSHOT_DIR", tmp_path)

    def fake_get_record(object_type, record_id, properties):
        return {"properties": {p: None for p in properties}}

    monkeypatch.setattr(snap, "get_record", fake_get_record)
    rc = snap.main(["snapshot", "--label", "pre-canary"])
    assert rc == 0
    written = list(tmp_path.glob("pre-canary-*.json"))
    assert len(written) == 1
    out = capsys.readouterr().out
    assert "research_gate_will_fire: true" in out  # all-blank target -> fires
    written_snapshot = json.loads(written[0].read_text())
    assert written_snapshot["target"]["id"] == snap.DEFAULT_TARGET_ID
    assert [n["id"] for n in written_snapshot["neighbors"]] == snap.DEFAULT_NEIGHBOR_CONTACT_IDS
