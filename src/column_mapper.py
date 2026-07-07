# src/column_mapper.py
#
# Pure header remap: arbitrary source headers -> canonical HubSpot contact props
# via config/column_mapping.yaml aliases. No value normalization, no identity
# logic (that is ingest_file's job).
from typing import Any, Dict


def _norm_header(header: str) -> str:
    # Match how the yaml keys are stored: trim, collapse internal whitespace, lowercase.
    return " ".join(header.split()).lower()


def map_row(raw_row: Dict[Any, Any], mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Remap raw source headers to canonical props, dropping unmapped columns.

    Accepts either the whole loaded yaml or just its aliases sub-map. Non-string
    keys (csv DictReader restkey None, xlsx blank header) are skipped so a
    malformed header never raises.
    """
    aliases = mapping.get("aliases", mapping)
    out: Dict[str, Any] = {}
    for key, value in raw_row.items():
        if not isinstance(key, str):
            continue
        canonical = aliases.get(_norm_header(key))
        if canonical:
            out[canonical] = value
    return out
