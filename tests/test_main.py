# tests/test_main.py
#
# Phase 4 runnable proof for the end-to-end MVP runner (main.run_local_mvp).
# Fully OFFLINE and DETERMINISTIC — no Anthropic call, no network, no API key.
#
# Same two conventions as test_merge_policy.py:
#   1. Monkeypatch at the merge_policy IMPORT SITE (`src.merge_policy.classify_field_with_haiku`)
#      with promote_fake, so no live classifier fires. delenv ANTHROPIC_API_KEY in every test.
#   2. Fixtures/config load cwd-relative -> run from repo root.
#
# The requests.patch sentinel proves "no HubSpot write" at runtime (SC2/SC3): it raises
# if ever called; dry-run must short-circuit before it.
import pytest

from main import run_local_mvp


def promote_fake(record, field, current_value, candidates, policy):
    return {"decision": "promote", "confidence": 90, "reason": "test",
            "requires_sonnet_validation": False}


def no_http(*args, **kwargs):
    raise AssertionError("requests.patch was called — a live HubSpot write leaked in dry-run")


def base_setup(monkeypatch):
    """Hermetic baseline shared by every test: no key, no live classifier, no HTTP."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("src.merge_policy.classify_field_with_haiku", promote_fake)
    monkeypatch.setattr("src.hubspot_client.requests.patch", no_http)
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("USE_MOCK_WEB_RESEARCH", "true")
    monkeypatch.setenv("ALLOW_JUDGE_ESCALATION", "false")


def test_sc1_prints_four_sections(monkeypatch, capsys):
    base_setup(monkeypatch)
    monkeypatch.setenv("ALLOW_STAGING_WRITES", "true")
    monkeypatch.setenv("ALLOW_CANONICAL_WRITES", "false")
    monkeypatch.setenv("ALLOW_ICP_SCORE_WRITES", "true")

    run_local_mvp()
    out = capsys.readouterr().out
    assert "=== Provider + Research Results ===" in out
    assert "=== Field Decisions ===" in out
    assert "=== ICP Score ===" in out
    assert "=== HubSpot Patch Payload ===" in out


def test_sc2_promotes_only_icp_stages_firmographics(monkeypatch):
    base_setup(monkeypatch)
    monkeypatch.setenv("ALLOW_STAGING_WRITES", "true")
    monkeypatch.setenv("ALLOW_CANONICAL_WRITES", "false")
    monkeypatch.setenv("ALLOW_ICP_SCORE_WRITES", "true")

    patch = run_local_mvp()

    # Approach C (Phase 15 criterion 4): ICP outputs are NEVER written by the pipeline —
    # HubSpot owns them. These assertions prove the write path is GONE.
    assert "lv_icp_fit_score" not in patch
    assert "lv_icp_tier" not in patch
    # firmographics staged via the provenance blob, not promoted (Phase 15: no flat
    # zoominfo_-prefixed staging properties any more)
    assert "lv_enrichment_provenance" in patch
    # never a bare manual/firmographic canonical key
    assert "domain" not in patch
    assert "annualrevenue" not in patch
    # firmographic canonical withheld even though promote_fake promoted it upstream
    assert "lv_org_type" not in patch


def test_sc3_staging_flag_toggles(monkeypatch):
    base_setup(monkeypatch)
    monkeypatch.setenv("ALLOW_CANONICAL_WRITES", "false")
    monkeypatch.setenv("ALLOW_ICP_SCORE_WRITES", "true")

    monkeypatch.setenv("ALLOW_STAGING_WRITES", "false")
    patch = run_local_mvp()
    # Phase 15: staging folds into the provenance blob, gated the same way
    # ALLOW_STAGING_WRITES gated flat staging properties before.
    assert "lv_enrichment_provenance" not in patch
    # no flat per-field metadata survives anywhere; exclude the always-present status key
    # enrichment_primary_source (part of status_patch, not staging/metadata).
    assert [k for k in patch if k.endswith("_source") and k != "enrichment_primary_source"] == []
    # status survives regardless of staging flag; ICP outputs are never written (Approach C)
    assert "lv_icp_tier" not in patch
    assert "enrichment_status" in patch

    monkeypatch.setenv("ALLOW_STAGING_WRITES", "true")
    patch2 = run_local_mvp()
    assert "lv_enrichment_provenance" in patch2


def test_sc3_canonical_flag_toggles_firmographic(monkeypatch):
    base_setup(monkeypatch)
    monkeypatch.setenv("ALLOW_STAGING_WRITES", "true")
    monkeypatch.setenv("ALLOW_ICP_SCORE_WRITES", "true")

    monkeypatch.setenv("ALLOW_CANONICAL_WRITES", "false")
    patch = run_local_mvp()
    assert "lv_org_type" not in patch

    monkeypatch.setenv("ALLOW_CANONICAL_WRITES", "true")
    patch2 = run_local_mvp()
    assert patch2["lv_org_type"] == "governing_body_league"


def test_sc3_dry_run_no_http(monkeypatch):
    base_setup(monkeypatch)
    from src.hubspot_client import patch_record

    r = patch_record("companies", "789", {"x": "y"}, dry_run=True)
    assert r == {"dry_run": True, "payload": {"properties": {"x": "y"}}}
    # no_http sentinel was never triggered — dry-run short-circuits before requests.patch
