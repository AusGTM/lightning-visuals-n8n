# tests/test_rollback_property_migration.py
#
# Phase 15 Task 7 (+ Task 8 canary) — offline proof for the reverse-direction property
# migration tool. Fully deterministic: no network. Mirrors tests/test_main.py's no_http
# sentinel pattern for the guard tests.
import json

import pytest
import requests

import scripts.rollback_property_migration as rollback
import scripts.rollback_canary_proof as canary


def raise_http(*args, **kwargs):
    raise AssertionError("a live HubSpot request leaked past a guard that should have refused")


@pytest.fixture(autouse=True)
def hermetic(monkeypatch):
    monkeypatch.delenv("HUBSPOT_PRIVATE_APP_TOKEN", raising=False)
    monkeypatch.delenv("HUBSPOT_PORTAL_ID", raising=False)
    monkeypatch.setattr(requests, "get", raise_http)
    monkeypatch.setattr(requests, "post", raise_http)
    monkeypatch.setattr(requests, "delete", raise_http)


# --- guards: refuse without manifest+baseline, portal mismatch, no-credentials ------

def test_no_credentials_skips_cleanly(capsys):
    rc = rollback.main([])
    assert rc == 0
    assert "skipped (no credentials)" in capsys.readouterr().out


def test_portal_mismatch_refuses_before_any_call(monkeypatch, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", "99999999")
    rc = rollback.main([])
    assert rc != 0
    assert "REFUSED" in capsys.readouterr().out


def test_refuses_when_manifest_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", rollback.EXPECTED_PORTAL_ID)
    baseline_co = tmp_path / "portal-schema-companies-x.json"
    baseline_co.write_text(json.dumps({"results": []}))
    baseline_ct = tmp_path / "portal-schema-contacts-x.json"
    baseline_ct.write_text(json.dumps({"results": []}))
    rc = rollback.main([
        "--manifest", str(tmp_path / "does-not-exist.json"),
        "--baseline-companies", str(baseline_co),
        "--baseline-contacts", str(baseline_ct),
    ])
    assert rc != 0
    assert "no undo manifest found" in capsys.readouterr().out


def test_refuses_when_baseline_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", rollback.EXPECTED_PORTAL_ID)
    manifest = tmp_path / "undo-manifest-x.json"
    manifest.write_text(json.dumps([]))
    rc = rollback.main([
        "--manifest", str(manifest),
        "--baseline-companies", str(tmp_path / "missing-companies.json"),
        "--baseline-contacts", str(tmp_path / "missing-contacts.json"),
    ])
    assert rc != 0
    assert "no baseline snapshot found" in capsys.readouterr().out


def test_dry_run_default_makes_zero_delete_calls(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", rollback.EXPECTED_PORTAL_ID)
    manifest = tmp_path / "undo-manifest-x.json"
    manifest.write_text(json.dumps([
        {"kind": "property", "object_type": "companies", "name": "lv_content_type",
         "group_name": "lv_enrichment"},
    ]))
    baseline_co = tmp_path / "portal-schema-companies-x.json"
    baseline_co.write_text(json.dumps({"results": []}))
    baseline_ct = tmp_path / "portal-schema-contacts-x.json"
    baseline_ct.write_text(json.dumps({"results": []}))
    rc = rollback.main([
        "--manifest", str(manifest),
        "--baseline-companies", str(baseline_co),
        "--baseline-contacts", str(baseline_ct),
    ])  # no --live -> requests.delete would raise if ever called
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert "Would archive" in out


# --- pure functions: reverse-order sequencing, touch-nothing-outside-manifest, diff --

def test_reverse_archive_order_properties_before_empty_group():
    manifest = [
        {"kind": "group", "object_type": "companies", "name": "lv_enrichment"},
        {"kind": "property", "object_type": "companies", "name": "lv_content_type",
         "group_name": "lv_enrichment"},
        {"kind": "property", "object_type": "companies", "name": "lv_revenue_band",
         "group_name": "lv_enrichment"},
    ]
    ordered = rollback.reverse_archive_order(manifest)
    kinds = [(e["kind"], e["name"]) for e in ordered]
    # both properties come before the group, and the group only appears once all its
    # properties are accounted for.
    assert kinds[-1] == ("group", "lv_enrichment")
    assert {k for k, _ in kinds[:-1]} == {"property"}
    assert len(ordered) == 3


def test_reverse_archive_order_skips_group_with_remaining_properties():
    # A manifest that (incorrectly) only lists the group, no properties under it, still
    # includes the group in the archive order — remaining is computed FROM the manifest,
    # not a live schema, so "no properties in the manifest for this group" reads as "safe
    # to archive the group too."
    manifest = [{"kind": "group", "object_type": "companies", "name": "lv_enrichment"}]
    ordered = rollback.reverse_archive_order(manifest)
    assert ordered == manifest


def test_refuses_entries_outside_manifest():
    manifest = [
        {"kind": "property", "object_type": "companies", "name": "lv_content_type"},
    ]
    # A live portal fixture has both the manifested property AND an unrelated one this
    # migration never created — the unrelated one must be refused.
    refused = rollback.refuses_entries_outside_manifest(
        manifest, [("companies", "lv_content_type"), ("companies", "some_other_property")])
    assert refused == [("companies", "some_other_property")]


def test_diff_against_baseline_empty_for_clean_rollback():
    baseline = [{"name": "domain"}, {"name": "industry"}]
    live = [{"name": "domain"}, {"name": "industry"}]
    assert rollback.diff_against_baseline(live, baseline) == []


def test_diff_against_baseline_nonempty_for_residual():
    baseline = [{"name": "domain"}]
    live = [{"name": "domain"}, {"name": "lv_content_type"}]
    assert rollback.diff_against_baseline(live, baseline) == ["lv_content_type"]


# --- DELIBERATE-BREAK: a hubspotDefined property in the manifest is hard-refused ------

def test_hubspot_defined_property_in_manifest_is_hard_refused_even_under_live(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", rollback.EXPECTED_PORTAL_ID)

    manifest = tmp_path / "undo-manifest-x.json"
    # A corrupted/malicious manifest listing a NATIVE property — must be hard-refused
    # even with --live, belt-and-braces (RESEARCH.md §3.4 step 4).
    manifest.write_text(json.dumps([
        {"kind": "property", "object_type": "contacts", "name": "email", "group_name": None},
    ]))
    baseline_co = tmp_path / "portal-schema-companies-x.json"
    baseline_co.write_text(json.dumps({"results": []}))
    baseline_ct = tmp_path / "portal-schema-contacts-x.json"
    baseline_ct.write_text(json.dumps({"results": [{"name": "email", "hubspotDefined": True}]}))

    monkeypatch.setattr(rollback, "_get_property_live",
                         lambda object_type, name: {"name": name, "hubspotDefined": True})
    monkeypatch.setattr(rollback, "_archive_property_live",
                         lambda object_type, name: (_ for _ in ()).throw(
                             AssertionError("must never archive a hubspotDefined property")))
    monkeypatch.setattr(rollback, "_get_live_properties",
                         lambda object_type: [{"name": "email", "hubspotDefined": True}])

    rc = rollback.main([
        "--manifest", str(manifest),
        "--baseline-companies", str(baseline_co),
        "--baseline-contacts", str(baseline_ct),
        "--live", "--confirm", "yes",
    ])
    assert rc == 0
    assert "REFUSED to archive" in capsys.readouterr().out


# --- Task 8: canary proof — offline-only; the live run is the operator's proof --------

def test_canary_manifest_is_a_single_property_named_lv_rollback_canary():
    manifest = canary.build_canary_manifest("20260722T000000Z")
    assert len(manifest) == 1
    assert manifest[0]["kind"] == "property"
    assert manifest[0]["object_type"] == "companies"
    # Lowercased: HubSpot rejects any uppercase in an internal property name, and the UTC
    # stamp carries a literal T and Z. Caught live 2026-07-22 — the original assertion
    # encoded the bug ("...20260722T000000Z" 400s with "Property name must be lowercase").
    assert manifest[0]["name"] == "lv_rollback_canary_20260722t000000z"


def test_canary_property_name_is_lowercase_for_any_timestamp():
    """Regression guard for the live 400. Offline tests never hit the API, so nothing
    caught the uppercase stamp until the operator ran the migration."""
    spec = canary.build_canary_property_spec("20261231T235959Z")
    assert spec["name"] == spec["name"].lower(), spec["name"]


def test_canary_is_archived_reads_a_fixture_get_response():
    assert canary.is_archived({"archived": True}) is True
    assert canary.is_archived({"archived": False}) is False  # present, not archived -> FAIL
    assert canary.is_archived(None) is True  # 404 / absent from default listing -> PASS


def test_canary_no_credentials_skips_cleanly(capsys):
    rc = canary.main([])
    assert rc == 0
    assert "skipped (no credentials)" in capsys.readouterr().out


def test_canary_two_key_gate_holds_even_with_credentials(monkeypatch, capsys):
    # Credentials + matching portal present, but DRY_RUN stays default "true" -> the
    # two-key gate must skip before any live call (requests.post/get/delete would raise).
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", canary.EXPECTED_PORTAL_ID)
    rc = canary.main([])
    assert rc == 0
    assert "skipped" in capsys.readouterr().out
