# tests/test_migrate_org_type_enum.py
#
# Phase 21 Task 2 — offline proof for the gated `lv_org_type` text-to-enumeration
# migration. Mirrors tests/test_org_type_probe_gates.py's no_http sentinel pattern:
# requests.* raises if a live call ever leaks past a guard that should have refused.
# Every refusal in migrate_org_type_enum.py fires BEFORE any HTTP call, so this suite
# never needs network mocking to exercise the gates.
import json

import pytest
import requests

import scripts.migrate_org_type_enum as migrate
from src import taxonomy


def raise_http(*args, **kwargs):
    raise AssertionError("a live HubSpot request leaked past a guard that should have refused")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)
    monkeypatch.delenv("HUBSPOT_PORTAL_ID", raising=False)
    monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.delenv("ALLOW_HUBSPOT_PROPERTY_WRITES", raising=False)
    monkeypatch.setattr(requests, "get", raise_http)
    monkeypatch.setattr(requests, "post", raise_http)
    monkeypatch.setattr(requests, "patch", raise_http)
    monkeypatch.setattr(requests, "delete", raise_http)


def _armed_env(monkeypatch):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", migrate.EXPECTED_PORTAL_ID)


VALID_RUNBOOK = """# ORG-TYPE-ENUM-MIGRATION.md

MIGRATION-SHAPE: in place (cheap reverse-PATCH rollback confirmed) -- verbatim verdict
ROLLBACK-COMMAND: DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true python scripts/migrate_org_type_enum.py --rollback
VERDICT-SOURCE: .planning/phases/21-transport-schema-hygiene/21-03-SUMMARY.md (commit abc1234)
REFERENCE-ARTIFACTS: baseline=config/hubspot_migration/baseline/portal-schema-companies-pre-orgtype-enum.json inventory=config/hubspot_migration/org_type_inventory-20260730T071919Z.json
"""


def _write_valid_inventory(path, out_of_vocab=None, taxonomy_version=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "taxonomy_version": taxonomy_version if taxonomy_version is not None else taxonomy.VERSION,
        "out_of_vocabulary": out_of_vocab or {},
        "value_counts": {},
        "total_companies_scanned": 712,
        "portal_reported_total": 712,
        "blank_count": 712,
    }))


# --- top-level guards --------------------------------------------------------------------

def test_no_credentials_skips_cleanly(capsys):
    rc = migrate.main([])
    assert rc == 0
    assert "skipped (no credentials)" in capsys.readouterr().out


def test_portal_mismatch_refuses_before_any_call(monkeypatch, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "99999999")
    rc = migrate.main([])
    assert rc != 0
    assert "REFUSED" in capsys.readouterr().out


# --- runbook gate (named so `-k runbook` selects every case here) -----------------------

def test_runbook_gate_refuses_on_missing_file(tmp_path):
    ok, message = migrate.runbook_gate_ok(tmp_path / "does-not-exist.md")
    assert ok is False
    assert "not found" in message


def test_runbook_gate_refuses_on_missing_marker(tmp_path):
    path = tmp_path / "runbook.md"
    # Drop the REFERENCE-ARTIFACTS line entirely.
    lines = [ln for ln in VALID_RUNBOOK.splitlines() if not ln.startswith("REFERENCE-ARTIFACTS:")]
    path.write_text("\n".join(lines))
    ok, message = migrate.runbook_gate_ok(path)
    assert ok is False
    assert "REFERENCE-ARTIFACTS" in message
    assert "missing" in message


def test_runbook_gate_refuses_on_placeholder_marker_value(tmp_path):
    path = tmp_path / "runbook.md"
    text = VALID_RUNBOOK.replace(
        "MIGRATION-SHAPE: in place (cheap reverse-PATCH rollback confirmed) -- verbatim verdict",
        "MIGRATION-SHAPE: TBD",
    )
    path.write_text(text)
    ok, message = migrate.runbook_gate_ok(path)
    assert ok is False
    assert "MIGRATION-SHAPE" in message
    assert "placeholder" in message


def test_runbook_gate_passes_with_all_four_real_markers(tmp_path):
    path = tmp_path / "runbook.md"
    path.write_text(VALID_RUNBOOK)
    ok, message = migrate.runbook_gate_ok(path)
    assert ok is True
    assert "ok" in message


def test_runbook_gate_observed_refusal_message_is_readable(tmp_path):
    # Non-vacuity check (plan acceptance criteria): blanking one marker's value produces
    # a readable, specific refusal — not a generic error.
    path = tmp_path / "runbook.md"
    text = VALID_RUNBOOK.replace(
        "ROLLBACK-COMMAND: DRY_RUN=false ALLOW_HUBSPOT_PROPERTY_WRITES=true python scripts/migrate_org_type_enum.py --rollback",
        "ROLLBACK-COMMAND:",
    )
    path.write_text(text)
    ok, message = migrate.runbook_gate_ok(path)
    assert ok is False
    assert "ROLLBACK-COMMAND" in message and "placeholder" in message


def test_parse_runbook_markers_extracts_all_four_keys():
    markers = migrate.parse_runbook_markers(VALID_RUNBOOK)
    assert set(markers.keys()) == set(migrate.MARKER_KEYS)
    for key in migrate.MARKER_KEYS:
        assert markers[key] is not None and markers[key].strip() != ""


# --- pre-flight inventory gate ------------------------------------------------------------

def test_inventory_gate_refuses_on_missing_artifact():
    ok, message = migrate.inventory_gate_ok(None)
    assert ok is False
    assert "no committed" in message


def test_inventory_gate_refuses_on_non_zero_out_of_vocab_and_prints_offenders(tmp_path):
    path = tmp_path / "org_type_inventory-20260101T000000Z.json"
    _write_valid_inventory(path, out_of_vocab={
        "weird_value": {"count": 3, "sample_record_ids": ["1", "2", "3"]},
    })
    ok, message = migrate.inventory_gate_ok(path)
    assert ok is False
    assert "weird_value" in message
    assert "1" in message


def test_inventory_gate_refuses_on_taxonomy_version_mismatch(tmp_path):
    path = tmp_path / "org_type_inventory-20260101T000000Z.json"
    _write_valid_inventory(path, taxonomy_version="some-stale-version")
    ok, message = migrate.inventory_gate_ok(path)
    assert ok is False
    assert "taxonomy version" in message


def test_inventory_gate_passes_on_clean_current_artifact(tmp_path):
    path = tmp_path / "org_type_inventory-20260101T000000Z.json"
    _write_valid_inventory(path)
    ok, message = migrate.inventory_gate_ok(path)
    assert ok is True


def test_find_latest_inventory_picks_the_lexicographically_last_file(tmp_path):
    (tmp_path / "org_type_inventory-20260101T000000Z.json").write_text("{}")
    latest = tmp_path / "org_type_inventory-20260201T000000Z.json"
    latest.write_text("{}")
    assert migrate.find_latest_inventory(tmp_path) == latest


def test_find_latest_inventory_returns_none_when_empty(tmp_path):
    assert migrate.find_latest_inventory(tmp_path) is None


# --- full forward-arm-path integration via main(), gates wired to a tmp environment ------

def test_forward_dry_run_default_prints_plan_and_makes_zero_http_calls(monkeypatch, tmp_path, capsys):
    _armed_env(monkeypatch)
    runbook = tmp_path / "runbook.md"
    runbook.write_text(VALID_RUNBOOK)
    inventory = tmp_path / "org_type_inventory-20260101T000000Z.json"
    _write_valid_inventory(inventory)
    monkeypatch.setattr(migrate, "RUNBOOK_PATH", runbook)
    monkeypatch.setattr(migrate, "MIGRATION_DIR", tmp_path)
    # DRY_RUN unset -> defaults to "true"; ALLOW_HUBSPOT_PROPERTY_WRITES unset -> "false".
    # requests.* raise if called, so this test IS the zero-HTTP-calls proof.
    rc = migrate.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "FORWARD" in out
    assert "Resolved option set" in out


def test_forward_arm_refuses_without_runbook_present(monkeypatch, tmp_path, capsys):
    _armed_env(monkeypatch)
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_HUBSPOT_PROPERTY_WRITES", "true")
    monkeypatch.setattr(migrate, "RUNBOOK_PATH", tmp_path / "missing-runbook.md")
    monkeypatch.setattr(migrate, "MIGRATION_DIR", tmp_path)
    rc = migrate.main([])  # even armed, the runbook gate refuses before any HTTP call
    assert rc != 0
    assert "REFUSED" in capsys.readouterr().out


def test_forward_arm_refuses_with_dirty_inventory(monkeypatch, tmp_path, capsys):
    _armed_env(monkeypatch)
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_HUBSPOT_PROPERTY_WRITES", "true")
    runbook = tmp_path / "runbook.md"
    runbook.write_text(VALID_RUNBOOK)
    monkeypatch.setattr(migrate, "RUNBOOK_PATH", runbook)
    monkeypatch.setattr(migrate, "MIGRATION_DIR", tmp_path)
    _write_valid_inventory(tmp_path / "org_type_inventory-20260101T000000Z.json",
                            out_of_vocab={"stray": {"count": 1, "sample_record_ids": ["1"]}})
    rc = migrate.main([])
    assert rc != 0
    assert "REFUSED" in capsys.readouterr().out


def test_rollback_dry_run_bypasses_runbook_and_inventory_gates(monkeypatch, tmp_path, capsys):
    # --rollback deliberately does not require the runbook/inventory gates (reverting to
    # a permissive text type cannot itself reject or orphan a value).
    _armed_env(monkeypatch)
    monkeypatch.setattr(migrate, "RUNBOOK_PATH", tmp_path / "missing-runbook.md")
    monkeypatch.setattr(migrate, "MIGRATION_DIR", tmp_path)
    rc = migrate.main(["--rollback"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "ROLLBACK" in out


# --- two-key write gate -------------------------------------------------------------------

def test_two_key_gate_requires_both_dry_run_false_and_write_flag(monkeypatch):
    monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.delenv("ALLOW_HUBSPOT_PROPERTY_WRITES", raising=False)
    assert migrate._writes_allowed() is False

    monkeypatch.setenv("DRY_RUN", "false")
    assert migrate._writes_allowed() is False

    monkeypatch.setenv("ALLOW_HUBSPOT_PROPERTY_WRITES", "true")
    assert migrate._writes_allowed() is True

    monkeypatch.setenv("DRY_RUN", "true")
    assert migrate._writes_allowed() is False


# --- taxonomy-derived option set -----------------------------------------------------------

def test_option_set_equals_the_live_taxonomy_vocabulary_lowercase():
    options = migrate.enum_options()
    values = {o["value"] for o in options}
    assert values == set(taxonomy.ORG_TYPES.keys())
    assert all(v == v.lower() for v in values)


def test_forward_patch_body_uses_the_derived_option_set():
    patch = migrate.forward_patch_body()
    assert patch["type"] == "enumeration"
    assert patch["fieldType"] == "select"
    assert {o["value"] for o in patch["options"]} == set(taxonomy.ORG_TYPES.keys())


def test_rollback_patch_body_is_plain_text_with_no_options():
    patch = migrate.rollback_patch_body()
    assert patch == {"type": "string", "fieldType": "text", "options": []}


def test_target_property_is_the_real_org_type_property():
    # This is the one script legitimately allowed to name it.
    assert migrate.TARGET_PROPERTY_NAME == "lv_org_type"
