# tests/test_node_name_uniqueness.py
#
# n8n's POST /api/v1/workflows REJECTS any workflow containing two nodes with the same
# name — HTTP 400, `duplicate_node_name`. This is a HARD deploy blocker, not a warning.
#
# Found the expensive way on the first live deploy (2026-07-28): `LV Enrichment (Cloud
# template)` and `LV Scheduled Maintenance (Cloud)` both 400'd because every sticky-note
# node was emitted with the literal name "Sticky Note". Nothing offline caught it — the
# whole suite builds and inspects these workflows constantly, but nothing asserted that
# node names are unique, because until a real deploy ran there was no reason to think
# n8n cared.
#
# Node names are also the ROW-RECOVERY mechanism this entire codebase depends on
# (`$('Some Node').all()` — the bd682a2 fix and every hop since). A duplicate name is
# therefore ambiguous at runtime as well as rejected at deploy: `$('Sticky Note')` has no
# single referent. Uniqueness is load-bearing twice over.
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
N8N_DIR = ROOT / "n8n"

WORKFLOW_FILES = sorted(N8N_DIR.glob("wf_*.json"))


def _duplicate_names(doc: dict) -> dict:
    seen: dict[str, int] = {}
    for node in doc.get("nodes", []):
        name = node.get("name")
        seen[name] = seen.get(name, 0) + 1
    return {name: count for name, count in seen.items() if count > 1}


@pytest.mark.parametrize("wf_path", WORKFLOW_FILES, ids=lambda p: p.name)
def test_every_workflow_has_unique_node_names(wf_path: Path):
    """A duplicate node name is a hard 400 from n8n's workflow-create API, and makes
    `$('Node Name')` row recovery ambiguous at runtime."""
    doc = json.loads(wf_path.read_text())
    dupes = _duplicate_names(doc)
    assert not dupes, (
        f"{wf_path.name} has duplicate node names {dupes} — n8n will reject this workflow "
        f"with HTTP 400 duplicate_node_name, and $('<name>') row recovery would be ambiguous."
    )


def test_the_guard_would_actually_catch_a_duplicate():
    """Vacuity guard: prove the detector fires on a known-bad document, so a future
    refactor that neuters `_duplicate_names` fails here rather than passing silently."""
    bad = {"nodes": [{"name": "Sticky Note"}, {"name": "Sticky Note"}, {"name": "Unique"}]}
    assert _duplicate_names(bad) == {"Sticky Note": 2}


def test_workflow_files_were_actually_discovered():
    """Vacuity guard: a glob that matched nothing would make the parametrized test above
    pass by collecting zero cases."""
    assert WORKFLOW_FILES, f"no wf_*.json found under {N8N_DIR} — the uniqueness sweep is vacuous"
