"""The chunk ceiling is declared twice — pin the two copies together.

`ENRICH_MAX_LIST_RECORDS` (backend, `scripts/build_cloud_workflows.py`) bounds how many
list members the enrichment lane will expand before refusing. `max_records_per_chunk`
(client, `operator-claude-plugin/config/operator.local.example.json`) bounds how many
records the plugin will put in one POST. They are the same number for the same reason —
the ~100 s Cloudflare response ceiling at ~36 s/record — but they live in two files that
nothing forced to agree.

If they drift, the failure is quiet in the worst direction: a client that chunks to N
sends a batch the backend refuses at N-1, so the operator gets a refusal for a batch the
preview told them was fine. That is the second instance of this shape in Phase 25 — the
first was the list envelope, where the client emitted a flat body and the backend read a
nested one, and both halves' tests passed because neither crossed the boundary (D-19,
fixed in 13006fa).

This file reads the config as DATA, not as an import: the plugin must not import from the
repo-root `scripts/` package and vice versa (PLUGIN-04), so a shared constant is not
available. Reading the committed JSON is the seam that does not violate that.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILDER = ROOT / "scripts" / "build_cloud_workflows.py"
CLIENT_CONFIG = ROOT / "operator-claude-plugin" / "config" / "operator.local.example.json"


def _backend_ceiling():
    match = re.search(r"^ENRICH_MAX_LIST_RECORDS\s*=\s*(\d+)", BUILDER.read_text(), re.M)
    assert match, "ENRICH_MAX_LIST_RECORDS is gone from build_cloud_workflows.py"
    return int(match.group(1))


def _client_ceiling():
    config = json.loads(CLIENT_CONFIG.read_text())
    assert "max_records_per_chunk" in config, (
        "max_records_per_chunk is gone from the client's example config"
    )
    return config["max_records_per_chunk"]


def test_the_two_ceilings_agree():
    backend, client = _backend_ceiling(), _client_ceiling()
    assert backend == client, (
        f"chunk ceiling drift: backend ENRICH_MAX_LIST_RECORDS={backend} but client "
        f"max_records_per_chunk={client}. A client that chunks to {client} would have "
        f"batches refused by a backend that stops at {backend} — and the operator would "
        f"see a refusal for a batch the preview approved. Change both, or neither."
    )


def test_neither_ceiling_is_zero_or_negative():
    # A zero ceiling refuses every list while looking like configuration, not a bug.
    assert _backend_ceiling() >= 1
    assert _client_ceiling() >= 1


def test_the_client_ceiling_carries_its_measured_provenance():
    """D-06 cuts both ways. While B4 was unrun, this pinned the PROVISIONAL label so a
    derivation could not read as a measurement. B4 ran 2026-08-03 (37.44 s, one
    full-waterfall record) and confirmed the ceiling — so now the note must carry the
    measurement's date and figure, and must NOT still call the number provisional,
    which would misstate it in the other direction. A bare integer with no provenance
    reads as settled by fiat either way.
    """
    config = json.loads(CLIENT_CONFIG.read_text())
    notes = " ".join(
        str(v) for k, v in config.items() if k.startswith("_max_records_per_chunk")
    )
    assert notes, "the provenance notes beside max_records_per_chunk are gone"
    assert "PROVISIONAL" not in notes.upper()
    assert "CONFIRMED" in notes.upper()
    assert "37.44" in notes and "B4" in notes
