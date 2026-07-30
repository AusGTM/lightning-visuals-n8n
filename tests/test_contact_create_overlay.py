# tests/test_contact_create_overlay.py
#
# Phase 23 Plan 01 — D-15/D-16/D-16a/D-16b: Set Config used to hardcode
# `allow_create: false` unconditionally, forcing every net-new contact row to
# needs_review regardless of arming. Decide Action now reads the EXISTING overlayable
# ALLOW_HUBSPOT_CREATE constant instead (reused, not a fifth flag — see
# tests/test_enabled_build_invariants.py::test_overlayable_flags_is_a_strict_subset_of_config_flag_defaults),
# composed at the build_cloud() call site.
#
# This file proves the overlay actually reaches the contact-ingest workflow now: it can
# rewrite the create constant in three or more nodes (Decide Action plus the two write
# gates) with no fail-closed ValueError, and the committed artifact ships with the
# disabled literal only.
import json
from pathlib import Path

import scripts.deploy_n8n_workflows as deploy

ROOT = Path(__file__).resolve().parents[1]
CONTACT_WF_PATH = ROOT / "n8n" / "wf_contact_ingest_cloud.json"


def _wf() -> dict:
    return json.loads(CONTACT_WF_PATH.read_text())


def _decls(workflow: dict, flag: str) -> list:
    import re

    out = []
    for node in workflow.get("nodes", []):
        js = node.get("parameters", {}).get("jsCode")
        if isinstance(js, str):
            out += re.findall(rf"const\s+{flag}\s*=\s*([^;]+);", js)
    return out


def test_committed_contact_workflow_carries_the_disabled_create_literal_only():
    """Companion assertion required by Task 2: the committed file must carry ONLY the
    disabled literal, so this test and the rewrite test below cannot both pass on an
    accidentally armed artifact."""
    wf = _wf()
    literals = _decls(wf, "ALLOW_HUBSPOT_CREATE")
    assert literals, "ALLOW_HUBSPOT_CREATE is never declared — guard is vacuous"
    assert set(literals) == {'"false"'}, (
        f"committed n8n/wf_contact_ingest_cloud.json carries an armed ALLOW_HUBSPOT_CREATE "
        f"literal: {set(literals)}"
    )


def test_enable_baked_flags_rewrites_the_create_constant_in_three_or_more_nodes():
    """Non-vacuity + the behaviour this plan exists to deliver: Decide Action now carries
    its own declaration of the constant, on top of the two write gates that already had
    it — so the rewrite count for this workflow must exceed 2 (the two gates alone)."""
    requested = {
        "ALLOW_HUBSPOT_RECORD_WRITES": '"true"',
        "ALLOW_HUBSPOT_CREATE": '"true"',
        "TEST_RECORD_DOMAINS": '"exampleco.example"',
    }
    new_wf, counts = deploy.enable_baked_flags(_wf(), requested)

    assert counts["ALLOW_HUBSPOT_CREATE"] > 2, (
        f"expected the create constant to be rewritten in strictly more than the two "
        f"write-gate nodes alone (Decide Action must carry a third declaration); got "
        f"count={counts['ALLOW_HUBSPOT_CREATE']}"
    )
    assert set(_decls(new_wf, "ALLOW_HUBSPOT_CREATE")) == {'"true"'}
    assert set(_decls(new_wf, "ALLOW_HUBSPOT_RECORD_WRITES")) == {'"true"'}
    assert set(_decls(new_wf, "TEST_RECORD_DOMAINS")) == {'"exampleco.example"'}
    # Untouched by this request.
    assert set(_decls(new_wf, "TEST_RECORD_IDS")) == {'""'}


def test_enable_baked_flags_raises_nothing_for_the_contact_workflow():
    """The fail-closed re-scan in enable_baked_flags() must find every declaration it
    rewrote landed on the requested literal — a raise here would mean Decide Action's new
    declaration is spelled differently from what enable_baked_flags() expects."""
    requested = {
        "ALLOW_HUBSPOT_RECORD_WRITES": '"true"',
        "ALLOW_HUBSPOT_CREATE": '"true"',
        "TEST_RECORD_IDS": '"12345"',
    }
    # Must not raise.
    deploy.enable_baked_flags(_wf(), requested)
