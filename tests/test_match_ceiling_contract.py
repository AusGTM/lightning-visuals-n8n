"""The match ceiling is declared twice — pin the two copies together.

`ENRICH_MAX_PROPOSE_RECORDS` (backend, `scripts/build_cloud_workflows.py`) bounds how
many rows a `mode:"propose"` match request may carry before the backend refuses it
whole. `max_rows_per_match_request` (client,
`operator-claude-plugin/config/operator.local.example.json`) bounds how many rows the
plugin will put in one match POST.

This is a SEPARATE pin from `test_chunk_ceiling_contract.py`'s, on purpose: the two
ceilings are bounded by different things. `max_records_per_chunk` survives the FULL
enrichment waterfall (provider calls + Haiku + Sonnet, measured 37.44 s/record) and is
2. `max_rows_per_match_request` survives two HubSpot searches with no provider or model
call in the path, and is bounded by `ENRICH_MAX_PROPOSE_RECORDS` — a much larger,
still-conservative number. Reusing `max_records_per_chunk` for match would make a match
refusal print waterfall-timing wording that is untrue of the call that raised it
(37-CONTEXT §4 point 2's explicit prohibition). The first live propose probe landed
2026-08-05 (37-09's operator checkpoint, 1.46 s/row) — the PROVISIONAL marker on this
key's provenance note is retired accordingly; the separation between the two keys never
changes.

This file reads the config and the builder source as DATA, not as an import: the plugin
must not import from the repo-root `scripts/` package and vice versa (PLUGIN-04), so a
shared constant is not available. Reading the committed JSON and regex-locating the
builder constant is the seam that does not violate that — the SAME locate this value was
derived from when it was written into the config, which is what makes the agreement
structural rather than a coincidence two files happen to share.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILDER = ROOT / "scripts" / "build_cloud_workflows.py"
CLIENT_CONFIG = ROOT / "operator-claude-plugin" / "config" / "operator.local.example.json"


def _backend_ceiling():
    match = re.search(r"^ENRICH_MAX_PROPOSE_RECORDS\s*=\s*(\d+)", BUILDER.read_text(), re.M)
    assert match, "ENRICH_MAX_PROPOSE_RECORDS is gone from build_cloud_workflows.py"
    return int(match.group(1))


def _client_config():
    return json.loads(CLIENT_CONFIG.read_text())


def _client_ceiling():
    config = _client_config()
    assert "max_rows_per_match_request" in config, (
        "max_rows_per_match_request is gone from the client's example config"
    )
    return config["max_rows_per_match_request"]


def test_the_client_ceiling_is_at_or_below_the_backend_ceiling():
    # `<=`, not `==`: the prescribed raise order moves the backend first and the client
    # second (37-CONTEXT §13 ceiling ruling), so an equality pin would make that correct
    # intermediate commit red. A client above the backend's bound is refused whole for a
    # batch the preview already approved — that is the failure shape this pin stops.
    backend, client = _backend_ceiling(), _client_ceiling()
    assert client <= backend, (
        f"match ceiling drift: client max_rows_per_match_request={client} exceeds "
        f"backend ENRICH_MAX_PROPOSE_RECORDS={backend}. A client above the backend's "
        f"bound gets a refusal for a batch the preview approved. Raise the backend "
        f"constant first, then this key."
    )


def test_the_match_ceiling_is_strictly_greater_than_the_write_path_ceiling():
    # A later edit that quietly collapses the two keys back onto one number is caught
    # here, not by the write-path pin (which asserts its own key's absence of the
    # provisional marker, not the separation).
    config = _client_config()
    assert config["max_rows_per_match_request"] > config["max_records_per_chunk"], (
        "the match ceiling must not collapse onto the write-path ceiling — they are "
        "bounded by different things (37-CONTEXT §4 point 2)"
    )


def test_neither_ceiling_is_zero_or_negative():
    assert _backend_ceiling() >= 1
    assert _client_ceiling() >= 1


def test_the_match_ceilings_provenance_note_carries_its_measured_provenance():
    """Mirrors `test_chunk_ceiling_contract.py::test_the_client_ceiling_carries_its_measured_provenance`:
    while the first live propose probe was unrun, this pinned the PROVISIONAL label so a
    derivation could not read as a measurement. That probe ran 2026-08-05 (37-09's operator
    checkpoint, live 9-row walk: 13.16 s / 9 rows = 1.46 s/row) — so now the note must carry
    the measurement's figure and must NOT still call the number provisional, which would
    misstate it in the other direction. Amended deliberately alongside the provenance note
    itself, not silenced: the walk that retires this label is exactly the one this test used
    to require be named."""
    config = _client_config()
    notes = " ".join(
        str(v) for k, v in config.items() if k.startswith("_max_rows_per_match_request")
    )
    assert notes, "the provenance notes beside max_rows_per_match_request are gone"
    assert "PROVISIONAL" not in notes.upper(), (
        "the first live propose probe ran 2026-08-05 (1.46 s/row) — the note must no "
        "longer call this number provisional now that it is backed by a measurement"
    )
    assert "MEASURED" in notes.upper() and "1.46" in notes, (
        "the note must carry the measurement itself, not just retire the provisional label"
    )


def test_the_provisional_marker_does_not_leak_onto_the_measured_neighbour():
    """The two keys carry opposite provenance claims. This mirrors
    `test_chunk_ceiling_contract.py::test_the_client_ceiling_carries_its_measured_provenance`
    from the other side — if this fails, that test's own PROVISIONAL-absence assertion
    would also be failing, so this is a second, independent guard on the same fact."""
    config = _client_config()
    write_path_notes = " ".join(
        str(v) for k, v in config.items() if k.startswith("_max_records_per_chunk")
    )
    assert "PROVISIONAL" not in write_path_notes.upper()
