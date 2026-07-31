"""28-03 Task 3 — the repo invariant: nothing on disk is armed.

Phase 28 is the first in this repo that can write an ENABLED write-safety literal to a
live workflow. A mistake in a probe, a fixture written back over a template, or a
hand-edit during a debugging session are all ways such a literal reaches a committed file.
The invariant is cheap, and it is the difference between an armed backend being an
incident and being a caught test.

Deliberate overlap with `tests/test_n8n_read.py` (27-01), which reads the same files
through the same function: that test guards the READER's contract, this one guards the
REPO invariant. 28-06 re-runs this file as its closing gate after a live armed window.
"""
import json
from pathlib import Path

import pytest

import n8n_arming
import n8n_read

REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = REPO_ROOT / "operator-claude-plugin"

# Globbed, never hardcoded: a fourth deployed workflow is covered automatically. That is
# not hypothetical — 30-02 added wf_review_decision_cloud.json after this phase was
# planned, and a hardcoded three-file list would have skipped it silently.
CLOUD_WORKFLOWS = sorted((REPO_ROOT / "n8n").glob("wf_*_cloud.json"))


def _workflows():
    assert CLOUD_WORKFLOWS, "no cloud workflow artifacts found — did the glob break?"
    return CLOUD_WORKFLOWS


@pytest.mark.parametrize("path", _workflows(), ids=lambda p: p.name)
@pytest.mark.parametrize("flag", sorted(n8n_arming.OVERLAYABLE_FLAGS))
def test_every_committed_declaration_carries_its_disabled_literal(path, flag):
    workflow = json.loads(path.read_text())
    observed = n8n_read.read_write_safety(workflow, flag)

    if observed["value"] is None and not observed["nodes"]:
        pytest.skip(f"{path.name} does not declare {flag}")

    expected = n8n_arming.OVERLAY_DISABLED_LITERALS[flag].strip('"')

    assert observed["disagreement"] is None, (
        f"{path.name}: declaring nodes disagree on {flag} — {observed['disagreement']}"
    )
    assert observed["value"] == expected, (
        f"{path.name} ships {flag} = {observed['value']!r}, expected {expected!r}. "
        f"Declaring nodes: {observed['nodes']}"
    )


def test_the_invariant_actually_fails_on_an_armed_workflow():
    """Constructed in the test at runtime, never by editing a committed file. Without this,
    a scan that silently found nothing would pass just as happily as a correct one."""
    armed = {
        "name": "LV Contact Ingest (Cloud template)",
        "nodes": [{"name": "Create Write Gate",
                   "parameters": {"jsCode": 'const ALLOW_HUBSPOT_CREATE = "true";'}}],
    }
    observed = n8n_read.read_write_safety(armed, "ALLOW_HUBSPOT_CREATE")

    assert observed["value"] == "true"
    assert observed["nodes"] == ["Create Write Gate"]

    expected = n8n_arming.OVERLAY_DISABLED_LITERALS["ALLOW_HUBSPOT_CREATE"].strip('"')
    assert observed["value"] != expected, (
        "the invariant above would not catch an armed declaration"
    )


def test_the_scan_is_not_vacuous():
    """A zero-discovery scan must fail rather than pass quietly — the same lesson 23-07
    learned when verify_live_write_safety.py inspected 2 of 11 declaring nodes and
    reported PASS."""
    total = 0
    for path in _workflows():
        workflow = json.loads(path.read_text())
        for flag in n8n_arming.OVERLAYABLE_FLAGS:
            total += len(n8n_read.read_write_safety(workflow, flag).get("nodes") or [])
    assert total >= 20, f"only {total} declaring nodes discovered — the scan looks broken"


def test_no_committed_plugin_fixture_ships_an_armed_workflow():
    """Any fixture exercising the armed path must be constructed at runtime. One test file
    answers 'is anything armed on disk' for the whole repository."""
    offenders = []
    for path in PLUGIN_ROOT.rglob("*.json"):
        try:
            body = json.loads(path.read_text())
        except (ValueError, UnicodeDecodeError):
            continue
        if not isinstance(body, dict) or "nodes" not in body:
            continue
        for flag in n8n_arming.WRITE_ENABLING_FLAGS:
            observed = n8n_read.read_write_safety(body, flag)
            if observed["value"] not in (None, "false"):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{flag}={observed['value']}")

    assert not offenders, f"armed workflow JSON committed under the plugin: {offenders}"
