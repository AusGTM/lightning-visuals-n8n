# tests/test_org_type_probe_gates.py
#
# Phase 21 Task 1 — offline proof for the disposable-property org_type migration probe.
# Mirrors tests/test_snapshot_hubspot_schema.py's / tests/test_rollback_property_migration.py's
# no_http sentinel pattern: requests.* raises if a live call ever leaks past a guard that
# should have refused. Every refusal in probe_org_type_migration.py fires BEFORE any HTTP
# call, so this suite never needs network mocking to exercise the guards.
import pytest
import requests

import scripts.probe_org_type_migration as probe
from src import taxonomy


def raise_http(*args, **kwargs):
    raise AssertionError("a live HubSpot request leaked past a guard that should have refused")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)
    monkeypatch.delenv("HUBSPOT_PORTAL_ID", raising=False)
    monkeypatch.delenv("TEST_COMPANY_IDS", raising=False)
    monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.delenv("ALLOW_HUBSPOT_PROPERTY_WRITES", raising=False)
    monkeypatch.setattr(requests, "get", raise_http)
    monkeypatch.setattr(requests, "post", raise_http)
    monkeypatch.setattr(requests, "patch", raise_http)
    monkeypatch.setattr(requests, "delete", raise_http)


# --- top-level guards, in refusal order -------------------------------------------------

def test_no_credentials_skips_cleanly(capsys):
    rc = probe.main([])
    assert rc == 0
    assert "skipped (no credentials)" in capsys.readouterr().out


def test_portal_mismatch_refuses_before_any_call(monkeypatch, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "99999999")
    rc = probe.main([])
    assert rc != 0
    assert "REFUSED" in capsys.readouterr().out


def test_refuses_when_test_company_ids_env_var_is_empty(monkeypatch, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", probe.EXPECTED_PORTAL_ID)
    # TEST_COMPANY_IDS deliberately left unset by the hermetic fixture.
    rc = probe.main([])
    assert rc != 0
    out = capsys.readouterr().out
    assert "REFUSED" in out
    assert "TEST_COMPANY_IDS" in out


def test_dry_run_default_makes_zero_http_calls_and_prints_full_ladder(monkeypatch, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", probe.EXPECTED_PORTAL_ID)
    monkeypatch.setenv("TEST_COMPANY_IDS", "789")
    # DRY_RUN unset -> defaults to "true"; ALLOW_HUBSPOT_PROPERTY_WRITES unset -> "false".
    # requests.get/post/patch/delete are all wired to raise_http by the hermetic fixture,
    # so this test IS the proof that dry-run makes zero calls.
    rc = probe.main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    for n in range(1, 10):
        assert f"=== STEP {n}:" in out
    assert "=== VERDICT ===" in out
    for key in probe.VERDICT_KEYS:
        assert f"{key}: {probe.NOT_OBSERVED}" in out
    assert "=== RESIDUAL STATE ===" in out


def test_two_key_gate_requires_both_dry_run_false_and_write_flag(monkeypatch):
    monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.delenv("ALLOW_HUBSPOT_PROPERTY_WRITES", raising=False)
    assert probe._writes_allowed() is False  # both defaults -> disarmed

    monkeypatch.setenv("DRY_RUN", "false")
    assert probe._writes_allowed() is False  # write flag still off

    monkeypatch.setenv("ALLOW_HUBSPOT_PROPERTY_WRITES", "true")
    assert probe._writes_allowed() is True  # both keys now hold

    monkeypatch.setenv("DRY_RUN", "true")
    assert probe._writes_allowed() is False  # DRY_RUN flipped back on -> disarmed again


def test_script_accepts_no_arguments():
    with pytest.raises(SystemExit):
        probe.main(["--target", "lv_org_type"])


# --- property-name guard: structurally always the module constant ----------------------

def test_property_name_guard_rejects_anything_but_the_module_constant():
    assert probe._property_name_ok(probe.PROBE_PROPERTY_NAME) is True
    assert probe._property_name_ok("lv_org_type") is False
    assert probe._property_name_ok("something_else") is False


# --- test-company allowlist guard -------------------------------------------------------

def test_test_company_allowlist_membership(monkeypatch):
    monkeypatch.setenv("TEST_COMPANY_IDS", "789,111")
    assert probe._test_company_ok("789") is True
    assert probe._test_company_ok("111") is True
    assert probe._test_company_ok("999") is False
    assert probe._test_company_ok("") is False


def test_resolved_test_company_id_is_always_drawn_from_the_allowlist(monkeypatch):
    monkeypatch.setenv("TEST_COMPANY_IDS", "789,111")
    resolved = probe._resolved_test_company_id()
    assert probe._test_company_ok(resolved) is True


# --- option set is derived from the taxonomy module, never re-typed --------------------

def test_option_set_equals_the_live_taxonomy_vocabulary():
    option_values = {opt["value"] for opt in probe._enum_options()}
    assert option_values == set(taxonomy.ORG_TYPES.keys())


def test_in_vocab_and_out_of_vocab_probe_values_are_correctly_classified():
    assert probe.IN_VOCAB_PROBE_VALUE in taxonomy.ORG_TYPES
    assert probe.OUT_OF_VOCAB_PROBE_VALUE not in taxonomy.ORG_TYPES
