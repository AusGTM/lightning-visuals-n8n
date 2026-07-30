# tests/test_write_gate_coverage.py
#
# BUG 15 — `_writeSafetyAllows()` and the ALLOW_HUBSPOT_* constants existed ONLY in
# wf_enrichment_cloud.json. wf_scheduled_maintenance_cloud.json and
# wf_contact_ingest_cloud.json carried SIX write nodes between them with no allowlist
# check at all: SJ-1/SJ-2 Set Requested, Dedupe Set Needs Review, Review Apply Update,
# and contact ingest's HubSpot Update / HubSpot Create.
#
# Both workflows are INACTIVE, so there was never live exposure — but activating either
# would have written to HubSpot with nothing bounding the blast radius, which is exactly
# the guarantee the write-path canary was run to establish. Found 2026-07-29 while
# auditing coverage after that canary.
#
# The property this file defends is structural and applies to workflows nobody has run:
# EVERY write node in EVERY cloud workflow sits directly behind a gate that calls
# _writeSafetyAllows. A write node added later cannot quietly skip one.
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLOUD_WORKFLOWS = sorted((ROOT / "n8n").glob("wf_*_cloud.json"))


def _load(path):
    return json.loads(path.read_text())


def _is_write_node(node):
    """A node that can mutate a HubSpot record: either the native node doing
    create/update, or an httpRequest issuing a mutating method at a non-search CRM URL."""
    params = node.get("parameters", {})
    if node.get("type") == "n8n-nodes-base.hubspot":
        return params.get("operation") in ("create", "update")
    if node.get("type") == "n8n-nodes-base.httpRequest":
        url = str(params.get("url", ""))
        method = str(params.get("method", "")).upper()
        return ("hubapi.com" in url and "/search" not in url
                and method in ("POST", "PATCH", "PUT"))
    return False


def _feeders(wf, name):
    return [src for src, spec in wf["connections"].items()
            if any(c["node"] == name
                   for outputs in spec.get("main", []) for c in (outputs or []))]


def _all_paths_cross_a_gate(wf, write_name, max_hops=6):
    """True when every inbound path to `write_name`, walked up to `max_hops` back, passes
    through a node whose jsCode calls _writeSafetyAllows."""
    frontier = [(f, 0) for f in _feeders(wf, write_name)]
    while frontier:
        name, depth = frontier.pop()
        if "_writeSafetyAllows" in _js(wf, name):
            continue  # this path is gated
        if depth >= max_hops:
            return False
        parents = _feeders(wf, name)
        if not parents:
            return False  # reached a trigger without crossing a gate
        frontier.extend((p, depth + 1) for p in parents)
    return True


def _js(wf, name):
    node = next((n for n in wf["nodes"] if n["name"] == name), None)
    return (node or {}).get("parameters", {}).get("jsCode", "") or ""


@pytest.mark.parametrize("path", CLOUD_WORKFLOWS, ids=lambda p: p.name)
def test_every_write_node_sits_behind_a_write_safety_gate(path):
    wf = _load(path)
    writes = [n for n in wf["nodes"] if _is_write_node(n)]
    assert writes, f"{path.name}: no write node found — this guard would be vacuous"
    ungated = []
    for node in writes:
        feeders = _feeders(wf, node["name"])
        if not feeders:
            continue  # unreachable node cannot write
        # Walk upstream: the enrichment workflow gates INSIDE `Decide Action` (which sets
        # action="write_blocked" so the routing IF cannot match), while the other two use
        # a spliced gate node directly in front. Both are valid — what matters is that no
        # path from a trigger reaches the write without crossing _writeSafetyAllows.
        if not _all_paths_cross_a_gate(wf, node["name"]):
            ungated.append((node["name"], feeders))
    assert not ungated, (
        f"{path.name}: write node(s) reachable without passing a write-safety gate — "
        f"activating this workflow would write to HubSpot with no allowlist bounding it: "
        f"{ungated}"
    )


@pytest.mark.parametrize("path", CLOUD_WORKFLOWS, ids=lambda p: p.name)
def test_every_cloud_workflow_with_a_write_declares_the_safety_constants(path):
    """The gate is only meaningful if the constants it reads are actually declared in the
    same workflow — a gate whose ALLOW_HUBSPOT_RECORD_WRITES is undefined would throw
    rather than deny, which is a different failure but not a safe one."""
    wf = _load(path)
    if not any(_is_write_node(n) for n in wf["nodes"]):
        pytest.skip("no write nodes in this workflow")
    blob = json.dumps(wf)
    for const in ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE",
                  "TEST_RECORD_IDS", "TEST_RECORD_DOMAINS"):
        assert f"const {const} = " in blob, f"{path.name}: {const} is never declared"


@pytest.mark.parametrize("path", CLOUD_WORKFLOWS, ids=lambda p: p.name)
def test_committed_write_safety_constants_are_all_disabled(path):
    """The committed artifact must never ship armed, in ANY workflow — the same invariant
    tests/test_enabled_build_invariants.py holds for the enrichment workflow, now that two
    more workflows carry these constants."""
    import re
    blob = json.dumps(_load(path))
    for const, disabled in (("ALLOW_HUBSPOT_RECORD_WRITES", '\\"false\\"'),
                            ("ALLOW_HUBSPOT_CREATE", '\\"false\\"'),
                            ("TEST_RECORD_IDS", '\\"\\"'),
                            ("TEST_RECORD_DOMAINS", '\\"\\"')):
        for literal in re.findall(rf"const {const} = ([^;]+);", blob):
            assert literal == disabled, (
                f"{path.name}: {const} is committed as {literal!r}, not {disabled!r}")


# Phase 21 Plan 01 — pins the weekly dedupe lane (n8n/wf_scheduled_maintenance_cloud.json)
# as classify-only: exactly one write node, and its emitted property keys never widen past
# an explicit allowlist. dedupeSweep.js's own header says CLASSIFY ONLY; this is that
# guarantee turned into a predicate, so a second write or a widened key set fails the suite
# instead of shipping silently.
_MAINTENANCE_WORKFLOW_NAME = "wf_scheduled_maintenance_cloud.json"
_DEDUPE_WRITE_NODE = "Dedupe Set Needs Review"
_DEDUPE_SWEEP_NODE = "Dedupe Sweep"

# Derived from what n8n/code/dedupeSweep.js's wrapper (ENRICH_DEDUPE_SWEEP in
# scripts/build_cloud_workflows.py) actually assigns to `properties` — the ONLY thing
# _hs_http_patch_node's body serializes (`{"properties": $json.properties}`); the sibling
# `to_review_reason` field the wrapper also emits on the row is metadata that never reaches
# HubSpot, since the write node never reads it. If a future change genuinely widens this to
# a broader set (e.g. surfacing a reason property), update this allowlist as its own
# reviewed act, not silently.
_DEDUPE_LANE_ALLOWED_PROPERTY_KEYS = {
    "lv_enrichment_needs_review",  # the needs-review flag — the sweep's one write output
}


def _maintenance_workflow_path():
    match = [p for p in CLOUD_WORKFLOWS if p.name == _MAINTENANCE_WORKFLOW_NAME]
    assert match, f"{_MAINTENANCE_WORKFLOW_NAME} not found among {CLOUD_WORKFLOWS}"
    return match[0]


def test_dedupe_lane_has_exactly_one_gated_write_node():
    wf = _load(_maintenance_workflow_path())
    dedupe_writes = [n["name"] for n in wf["nodes"]
                     if n["name"].startswith("Dedupe ") and _is_write_node(n)]
    assert dedupe_writes == [_DEDUPE_WRITE_NODE], (
        f"expected exactly one write node in the Dedupe lane ({_DEDUPE_WRITE_NODE!r}); "
        f"found {dedupe_writes} instead — a second write node here is a new, unreviewed "
        f"write surface on a lane dedupeSweep.js documents as CLASSIFY ONLY"
    )


def test_dedupe_lane_emits_only_allowlisted_property_keys():
    import re
    wf = _load(_maintenance_workflow_path())
    sweep_node = next(n for n in wf["nodes"] if n["name"] == _DEDUPE_SWEEP_NODE)
    js_code = sweep_node["parameters"]["jsCode"]
    # The inlined dedupeSweep.js module (frozen, imported verbatim) carries its own
    # header comment mentioning "properties" in prose — scope the extraction to the n8n
    # wrapper appended after it, which is where the row actually PATCHed to HubSpot is
    # constructed, so a comment elsewhere in the frozen module can't feed a false match.
    marker = "n8n wrapper: Dedupe Sweep"
    wrapper_start = js_code.find(marker)
    assert wrapper_start != -1, f"{_DEDUPE_SWEEP_NODE}: wrapper marker {marker!r} not found"
    wrapper_code = js_code[wrapper_start:]
    # The wrapper builds TWO `properties: { ... }` object literals: the input `records`
    # passed INTO dedupeSweep() (email/phone/linkedin_url, read from HubSpot — never
    # written), and the output row's `properties`, which is the one _hs_http_patch_node
    # actually PATCHes. The output literal is the LAST one in source order (it's built
    # inside the `return report.to_review_ids.map(...)` that follows the sweep call).
    matches = list(re.finditer(r"properties:\s*\{([^}]*)\}", wrapper_code))
    assert matches, f"{_DEDUPE_SWEEP_NODE}: no `properties: {{ ... }}` literal found in jsCode"
    match = matches[-1]
    keys = set(re.findall(r"(\w+)\s*:", match.group(1)))
    assert keys, f"{_DEDUPE_SWEEP_NODE}: extracted zero property keys — extraction is broken"
    unexpected = keys - _DEDUPE_LANE_ALLOWED_PROPERTY_KEYS
    assert not unexpected, (
        f"{_DEDUPE_SWEEP_NODE} emits property key(s) {unexpected} outside the classify-only "
        f"allowlist {_DEDUPE_LANE_ALLOWED_PROPERTY_KEYS} — a new key here is a new, "
        f"unreviewed HubSpot write surface on a lane dedupeSweep.js documents as CLASSIFY ONLY"
    )
