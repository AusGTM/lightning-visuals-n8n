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
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Phase 44 Plan 01: scripts/build_cloud_workflows.py does `import gen_taxonomy_js`, a
# sibling-script import that resolves only with scripts/ on sys.path. The full suite got
# this for free from an earlier-collected module; standalone runs of THIS file did not.
sys.path.insert(0, str(ROOT / "scripts"))
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


# Phase 25 Plan 02 (D-14) — wf_backend_status_cloud.json is DELIBERATELY read-only: it
# reads provider usage endpoints only, never a HubSpot endpoint, and performs zero writes.
# It is excluded from the "every cloud workflow has a write node" vacuity assumption below
# — asserted, not just skipped, so a write node landing there unnoticed would still fail.
NO_WRITE_NODES_EXPECTED = {"wf_backend_status_cloud.json"}

# Phase 44 Plan 01 (D-05/D-06) — the SJ-3 drain write is exempted from the generic
# _writeSafetyAllows walk BY NAME, deliberately, because for this one node the walk
# INVERTS: its upstream "SJ-3 Dispatch Gate" embeds WRITE_SAFETY_GATE_JS verbatim (D-02),
# so the walker finds the literal `_writeSafetyAllows` and reports the drain as gated —
# but the drain write is reachable precisely on the rows _writeSafetyAllows DECLINED.
# The string the walker matches is, for this node, evidence of the OPPOSITE of what the
# generic test claims. The drain cannot use the shared allowlist at all (D-06: the stuck
# queue is overwhelmingly non-allowlisted records — that is the failure mode itself), so
# it carries its own authority (ALLOW_SJ3_DRAIN_WRITES, default "true" per D-05) and is
# covered instead by the strictly stronger dedicated assertions below: sole-feeder,
# D-06 negative grep on the drain gate, and a key+value patch allowlist.
DRAIN_EXEMPT_WRITE_NODES = {
    ("wf_scheduled_maintenance_cloud.json", "SJ-3 Drain Clear Flag"),
}


@pytest.mark.parametrize("path", CLOUD_WORKFLOWS, ids=lambda p: p.name)
def test_every_write_node_sits_behind_a_write_safety_gate(path):
    wf = _load(path)
    writes = [n for n in wf["nodes"] if _is_write_node(n)]
    if path.name in NO_WRITE_NODES_EXPECTED:
        assert not writes, (
            f"{path.name} is documented read-only (D-14) but now contains write node(s) "
            f"{[n['name'] for n in writes]} — widening NO_WRITE_NODES_EXPECTED must be a "
            "deliberate, reviewed act, not a silent pass"
        )
        return
    assert writes, f"{path.name}: no write node found — this guard would be vacuous"
    ungated = []
    for node in writes:
        if (path.name, node["name"]) in DRAIN_EXEMPT_WRITE_NODES:
            continue  # covered by the dedicated drain assertions below — see the set's comment
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
    from scripts.build_cloud_workflows import WRITE_SAFETY_DEFAULTS

    wf = _load(path)
    if not any(_is_write_node(n) for n in wf["nodes"]):
        pytest.skip("no write nodes in this workflow")
    blob = json.dumps(wf)
    # Driven off the builder's own set rather than a hardcoded tuple: a constant added
    # later (ALLOW_HUBSPOT_REVIEW_WRITES was the fifth, Phase 30 Plan 01) is covered the
    # moment it exists, instead of silently sitting outside this guarantee.
    for const in WRITE_SAFETY_DEFAULTS:
        assert f"const {const} = " in blob, f"{path.name}: {const} is never declared"


@pytest.mark.parametrize("path", CLOUD_WORKFLOWS, ids=lambda p: p.name)
def test_committed_write_safety_constants_are_all_disabled(path):
    """The committed artifact must never ship armed, in ANY workflow — the same invariant
    tests/test_enabled_build_invariants.py holds for the enrichment workflow, now that two
    more workflows carry these constants.

    Phase 44 Plan 01: the name is now imprecise — this verifies committed literals match
    their DECLARED DEFAULTS (the expected literal is derived from WRITE_SAFETY_DEFAULTS
    itself below), and one entry (ALLOW_SJ3_DRAIN_WRITES, D-05) now defaults "true". Not
    renamed: the name is referenced in prior phase notes."""
    import re

    from scripts.build_cloud_workflows import WRITE_SAFETY_DEFAULTS

    blob = json.dumps(_load(path))
    for const, value in WRITE_SAFETY_DEFAULTS.items():
        # The safe literal as it appears INSIDE the serialized workflow: the builder bakes
        # json.dumps(value) into jsCode, and jsCode is itself a JSON string here.
        disabled = json.dumps(json.dumps(value))[1:-1]
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


# Phase 44 Plan 01 (DRAIN-01/02/03, D-05/D-06) — the drain node's replacement coverage,
# strictly stronger than the generic walk it is exempt from (see DRAIN_EXEMPT_WRITE_NODES).
_DRAIN_GATE_NODE = "SJ-3 Drain Gate"
_DRAIN_WRITE_NODE = "SJ-3 Drain Clear Flag"
# DRAIN-02 as amended 2026-08-10 (operator decision): a KEY+VALUE allowlist, deliberately
# NOT a count of keys. The original "exactly one key" wording was amended because the
# same write is what stamps the provenance DRAIN-03 needs (lv_enrichment_status="skipped"
# — the one closed-enum option nothing else in the pipeline writes, D-08). Order matters:
# these are baked literals in the built JSON, so the exact list is the exact patch.
_DRAIN_ALLOWED_PATCH_PAIRS = [
    ("lv_enrichment_requested", "false"),
    ("lv_enrichment_status", "skipped"),
]


def _drain_wf():
    return _load(_maintenance_workflow_path())


def test_drain_write_nodes_sole_feeder_is_the_drain_gate():
    wf = _drain_wf()
    feeders = _feeders(wf, _DRAIN_WRITE_NODE)
    assert feeders == [_DRAIN_GATE_NODE], (
        f"{_DRAIN_WRITE_NODE} must be fed by {_DRAIN_GATE_NODE!r} and nothing else; found "
        f"{feeders} — a second feeder is an ungated path onto the one write node exempted "
        f"from the generic walk, and adding one must be a deliberate, reviewed act"
    )


def test_drain_gate_reads_only_its_own_authority():
    """Pins D-06 structurally: the drain gate compares ALLOW_SJ3_DRAIN_WRITES against the
    exact string "true" and never touches the shared write-safety helper or a record
    allowlist constant. Because a Code node's comments are part of its jsCode, the
    negative assertions below also constrain that node's PROSE — the drain gate documents
    its exclusions without naming the excluded identifiers, so a future editor must not
    "improve" its comment into naming them (that would fail this test, by design)."""
    wf = _drain_wf()
    js = _js(wf, _DRAIN_GATE_NODE)
    assert js, f"{_DRAIN_GATE_NODE}: no jsCode found"
    assert 'ALLOW_SJ3_DRAIN_WRITES !== "true"' in js, (
        f"{_DRAIN_GATE_NODE} must gate on an exact-string comparison of "
        f'ALLOW_SJ3_DRAIN_WRITES against "true" (CLAUDE.md §21)'
    )
    assert "_writeSafetyAllows" not in js, (
        f"{_DRAIN_GATE_NODE} must not reference the shared write-safety helper (D-06): "
        "its allowlist branch is unconditional, and an allowlisted drain would clear only "
        "records that were never stuck"
    )
    assert "TEST_RECORD" not in js, (
        f"{_DRAIN_GATE_NODE} must not reference a record-allowlist constant (D-06)"
    )


def test_drain_write_patch_is_exactly_the_two_pair_allowlist():
    """DRAIN-02, structural: the built node's customPropertiesValues is EXACTLY the two
    (property, value) literal pairs — this fails on any additional key AND on any other
    value, so widening the drain's blast radius is a builder diff that fails here, never
    a runtime surprise. Widening _DRAIN_ALLOWED_PATCH_PAIRS itself must be a deliberate,
    reviewed act (see its comment for why it is two pairs, not one key)."""
    wf = _drain_wf()
    node = next((n for n in wf["nodes"] if n["name"] == _DRAIN_WRITE_NODE), None)
    assert node, f"{_DRAIN_WRITE_NODE} not found"
    pairs = [(p["property"], p["value"]) for p in
             node["parameters"]["updateFields"]["customPropertiesUi"]["customPropertiesValues"]]
    assert pairs == _DRAIN_ALLOWED_PATCH_PAIRS, (
        f"{_DRAIN_WRITE_NODE} patch is {pairs}, expected exactly "
        f"{_DRAIN_ALLOWED_PATCH_PAIRS} — any other key or value here is a new, unreviewed "
        f"write surface on the ONLY write authority in this system enabled at rest (D-05)"
    )


def test_drain_exemption_set_names_exactly_one_node():
    """Widening DRAIN_EXEMPT_WRITE_NODES must be a reviewed act: every entry weakens the
    generic every-write-node-is-gated guarantee for one node, and each needs its own
    replacement assertions the way the drain has above."""
    assert DRAIN_EXEMPT_WRITE_NODES == {(_MAINTENANCE_WORKFLOW_NAME, _DRAIN_WRITE_NODE)}, (
        f"DRAIN_EXEMPT_WRITE_NODES is {DRAIN_EXEMPT_WRITE_NODES} — a new exemption here "
        "must arrive with its own dedicated replacement coverage, not silently"
    )


# Phase 36-04 Task 1 (T-36-16/T-36-17) — companion to the ordering assertion in
# tests/test_cloud_write_path.py: proving the assignment precedes the gate call is not
# enough on its own — this proves the return-only action strings ("proposed",
# "needs_match_review") are structurally UNMATCHABLE by either write router, so a propose
# row cannot reach a write node even if some future edit broke the ordering guarantee.

def test_decide_action_return_only_strings_never_match_a_write_router():
    wf = json.loads((ROOT / "n8n" / "wf_enrichment_cloud.json").read_text())
    nodes = {n["name"]: n for n in wf["nodes"]}
    routed = json.dumps(nodes["IF Create"]["parameters"]) + json.dumps(nodes["IF Enrich"]["parameters"])
    for action_string in ("proposed", "needs_match_review"):
        assert action_string not in routed, (
            f"{action_string!r} appears in IF Create/IF Enrich's own conditions — a propose "
            "or needs-match-review row could structurally reach a write node"
        )
