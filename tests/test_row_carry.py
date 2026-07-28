# tests/test_row_carry.py
#
# Phase 16.8 — BUG 12. `n8n-nodes-base.set` typeVersion 3.x emits ONLY its assigned
# fields unless `options.includeOtherFields` is true. A Set node sitting mid-chain
# therefore silently deletes the row travelling through it.
#
# Found live 2026-07-29 (execution 13): `Merge Winners -> Set Data Quality + Gap Flag ->
# Decide Action`, and that Set node emitted exactly {data_quality, gap_flag}. `Decide
# Action` then resolved `row.existingRecord.hs_object_id` to null and
# `_buildContactPatch(undefined)` to {}, so `_writeSafetyAllows()` denied regardless of
# the allowlist, no `action` key was emitted, `IF Enrich` received zero items and
# `HubSpot Update` never ran. The contacts write path could not write to ANY record under
# ANY flag combination — and had been that way since at least execution 8 (2026-07-28),
# invisible because writes were disabled and the webhook still returned a plausible 200.
#
# This guard is structural because the defect is structural: it is a property of the node
# body in the committed artifact, checkable without a live run — which is the only kind of
# check that would have caught it before an armed window was spent.
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / "n8n").glob("wf_*_cloud.json"))

# Set nodes that legitimately REPLACE the row rather than augmenting it. Each entry is a
# deliberate decision with a reason, not a waiver — a new Set node is row-carrying until
# someone justifies adding it here.
ROW_REPLACING_BY_DESIGN = {
    # Emits the single marker `Build Response` turns into the webhook reply for an
    # unsupported object type. Carrying the inbound row would leak event internals into
    # the HTTP response.
    "Unsupported Object Type": "terminal marker consumed whole by Build Response",
    # Same shape for the skipped-enrichment branch: the reply IS {action: "skip"}.
    "Skip (NoOp)": "terminal marker consumed whole by Build Response",
    # Head-of-chain config seed in the ingest workflow — there is no upstream row yet.
    "Set Config": "head-of-chain config seed, no upstream row exists",
    # Terminal queue markers; nothing downstream consumes them.
    "Set Review": "terminal, no downstream consumer",
    "SJ-2 Skip (NoOp)": "terminal, no downstream consumer",
    "Review Stale (NoOp)": "terminal, no downstream consumer",
}


def _load(path):
    return json.loads(path.read_text())


def _downstream(wf, name):
    return [c["node"]
            for out in wf["connections"].get(name, {}).get("main", [])
            for c in (out or [])]


def _set_nodes(wf):
    return [n for n in wf["nodes"] if n["type"] == "n8n-nodes-base.set"]


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_mid_chain_set_nodes_carry_the_row_through(path):
    """A Set node with a downstream consumer must set includeOtherFields, or be listed —
    with a reason — as deliberately row-replacing."""
    wf = _load(path)
    offenders = []
    for node in _set_nodes(wf):
        name = node["name"]
        if not _downstream(wf, name):
            continue  # terminal: nothing downstream can be starved
        if name in ROW_REPLACING_BY_DESIGN:
            continue
        if node.get("parameters", {}).get("options", {}).get("includeOtherFields") is not True:
            offenders.append((name, _downstream(wf, name)))
    assert not offenders, (
        f"{path.name}: Set node(s) mid-chain without includeOtherFields — they DELETE the "
        f"row for everything downstream (BUG 12): {offenders}"
    )


def test_the_specific_bug_12_node_carries_the_row():
    """Pinned by name, because this is the node whose silence cost two live armed windows.

    It must NOT be an `n8n-nodes-base.set`. Adding `options.includeOtherFields: true` was
    tried and deployed; execution 14 read the option back as live and the node still
    emitted only its two assigned fields. The node is a Code node that spreads the row
    explicitly, so the row-carry property is a property of code we control rather than of
    an n8n parameter schema this repo cannot test offline.
    """
    wf = _load(ROOT / "n8n" / "wf_enrichment_cloud.json")
    node = next(n for n in wf["nodes"] if n["name"] == "Set Data Quality + Gap Flag")
    assert node["type"] == "n8n-nodes-base.code", "must not regress to a Set node"
    js = node["parameters"]["jsCode"]
    assert "...it.json" in js, "must spread the inbound row"
    assert 'data_quality: "scored_waterfall"' in js
    assert "gap_flag:" in js
    # And it must still sit exactly where the row-loss happened.
    assert _downstream(wf, "Set Data Quality + Gap Flag") == ["Decide Action"]
    feeders = [src for src in wf["connections"]
               if "Set Data Quality + Gap Flag" in _downstream(wf, src)]
    assert feeders == ["Merge Winners"]


def test_every_row_replacing_entry_is_still_a_real_node_somewhere():
    """Stops the waiver list rotting into a set of names that no longer exist, which would
    silently re-permit a future node that happens to reuse one of them."""
    live = set()
    for path in WORKFLOWS:
        live |= {n["name"] for n in _set_nodes(_load(path))}
    stale = sorted(set(ROW_REPLACING_BY_DESIGN) - live)
    assert not stale, f"waiver list names nodes that no longer exist: {stale}"
