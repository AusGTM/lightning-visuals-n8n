"""operator-claude-plugin/scripts/preview.py

Builds the operator-facing preview: what will be sent, what will be dropped, and how
much there is — before a single byte goes over the wire (D-07/D-08/D-09/D-10,
PREVIEW-01, PREVIEW-04).

This is the ONLY place in the plugin that reads config/column_mapping.yaml, and it is a
read-only DISPLAY LOOKUP: labelling headers for the operator, never transforming a row.
The wire payload (tabular.to_csv_bytes) is built straight from the file `read_table` and
this module both read unchanged — this module never feeds it anything derived from the
mapping.
"""
import json
import re
from pathlib import Path

from preview_enrichment import TABULAR_COST_REASON, cost_block, zero_cost_estimate
from tabular import read_table, to_csv_bytes

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PLUGIN_ROOT.parent
DEFAULT_MAPPING_PATH = REPO_ROOT / "config" / "column_mapping.yaml"

LEAD_ROWS = 10
TRAIL_ROWS = 3
ADAPTIVE_THRESHOLD = 20


def _normalize_header(header: str) -> str:
    """Mirror Map Columns' own rule exactly (see config/column_mapping.yaml's own
    comment): strip, collapse internal whitespace, lowercase. Do not improve on this with
    fuzzy matching — a smarter matcher would mislabel a column the backend really does
    map, which is the one thing the preview must never do."""
    return re.sub(r"\s+", " ", header.strip()).lower()


def resolve_mapping_path(mapping_path=None):
    """The one rule for finding config/column_mapping.yaml: an explicit path argument,
    then the repo's config/column_mapping.yaml, then None (unavailable). Shared by this
    module's display-only labelling and extraction.py's canonical-prop/identity-group
    derivation, so exactly one rule for finding that file exists in the plugin — callers
    decide whether "unavailable" degrades gracefully (this module's labels) or is a hard
    error (extraction.py's validation allowlist)."""
    if mapping_path is not None:
        return Path(mapping_path)
    if DEFAULT_MAPPING_PATH.exists():
        return DEFAULT_MAPPING_PATH
    return None


def _adaptive_sample(items):
    """First-10/last-3 sample above ADAPTIVE_THRESHOLD, every item at or below it
    (D-08). Shared by build_preview() and build_extracted_preview() so the two preview
    surfaces never disagree about the same batch."""
    if len(items) <= ADAPTIVE_THRESHOLD:
        return False, items
    return True, {"leading": items[:LEAD_ROWS], "trailing": items[-TRAIL_ROWS:]}


def _load_aliases(mapping_path):
    """Return (aliases, canonical_props) or (None, None) if the mapping file is absent,
    unreadable, or malformed. Read-only — never writes, never called by dispatch."""
    if mapping_path is None:
        return None, None
    mapping_path = Path(mapping_path)
    if not mapping_path.exists():
        return None, None
    try:
        import yaml

        with mapping_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        aliases = dict(data.get("aliases") or {})
        canonical_props = sorted(set(aliases.values()))
        return aliases, canonical_props
    except Exception:
        return None, None


def label_headers(headers: list[str], mapping_path=None) -> dict:
    """Label each source header with the canonical prop it maps to, or flag it dropped
    if the alias table does not recognize it. Display-only — never used to transform a
    row; the bytes sent over the wire never pass through this function.

    Returns:
        {
          "available": bool,
          "labels": [{"header": str, "canonical": str | None, "dropped": bool | None}],
          "unmapped_canonical_props": [str, ...],
        }
    """
    aliases, canonical_props = _load_aliases(mapping_path)
    if aliases is None:
        return {
            "available": False,
            "labels": [
                {"header": h, "canonical": None, "dropped": None} for h in headers
            ],
            "unmapped_canonical_props": [],
        }

    labels = []
    mapped_props = set()
    for h in headers:
        canonical = aliases.get(_normalize_header(h))
        labels.append({"header": h, "canonical": canonical, "dropped": canonical is None})
        if canonical:
            mapped_props.add(canonical)

    unmapped = sorted(p for p in canonical_props if p not in mapped_props)

    return {"available": True, "labels": labels, "unmapped_canonical_props": unmapped}


def _fill_rates(headers, rows) -> dict:
    """Non-empty cells over total rows, per source column — including dropped columns,
    since a column the backend will drop is exactly the one an operator wants to notice."""
    total = len(rows)
    rates = {}
    for i, h in enumerate(headers):
        if total == 0:
            rates[h] = 0.0
            continue
        filled = sum(1 for r in rows if i < len(r) and str(r[i]).strip() != "")
        rates[h] = round(filled / total, 4)
    return rates


def tabular_cost_block(row_count) -> str:
    """This lane's cost block, rendered through the enrichment lane's SAME helper.

    Criterion 3 says every preview on both lanes. Contact-upload calls no provider and
    makes no model call, so its honest figures are zero credits and zero dollars WITH the
    reason stated — a real, explainable zero, unlike a balance that could not be read
    (D-16). Reusing the one helper is the point: two cost blocks that can drift apart is
    the second-source-of-truth pattern this milestone avoids everywhere else.
    """
    return cost_block(zero_cost_estimate(row_count), {}, reason=TABULAR_COST_REASON)


def build_preview(path, mapping_path=None) -> dict:
    """Build the structured preview for one tabular file. Read-only end to end: no
    network call, and the source file's bytes are identical before and after.

    Mapping-file resolution order: an explicit `mapping_path` argument, then the repo's
    config/column_mapping.yaml, then unavailable (labels flagged, not guessed).
    """
    headers, rows = read_table(path)
    row_count = len(rows)

    header_labels = label_headers(headers, resolve_mapping_path(mapping_path))

    preview = {
        "headers": headers,
        "row_count": row_count,
        "outgoing_bytes": len(to_csv_bytes(path)),
        "header_labels": header_labels["labels"],
        "mapping_available": header_labels["available"],
        "unmapped_canonical_props": header_labels["unmapped_canonical_props"],
        "cost_block": tabular_cost_block(row_count),
    }

    adaptive, sample_rows = _adaptive_sample(rows)
    preview["adaptive"] = adaptive
    preview["sample_rows"] = sample_rows
    if adaptive:
        preview["fill_rates"] = _fill_rates(headers, rows)

    return preview


def build_extracted_preview(result) -> dict:
    """Structured preview for an extraction result (Phase 24): every accepted row
    alongside its provenance, every rejected row with its reason, every dropped
    non-canonical key, and the batch's ambiguities — the operator's one-stop view before
    approving. Returns structured data, not rendered markdown (D-09: the skill owns
    rendering). Read-only: no network call, no file write. Reuses _adaptive_sample(), the
    same sampling rule build_preview() applies, so the two preview surfaces never
    disagree about the same batch.

    `result` is duck-typed (an extraction.ExtractionResult or anything with the same
    `.accepted`/`.rejected`/`.dropped_keys`/`.ambiguities` attributes) — this module does
    not import extraction.py, so there is no import cycle with extraction.py importing
    resolve_mapping_path() above.
    """
    accepted = result.accepted

    adaptive, sample_rows = _adaptive_sample(accepted)

    return {
        "row_count": len(accepted),
        "adaptive": adaptive,
        "sample_rows": sample_rows,
        "rejected": result.rejected,
        "dropped_keys": result.dropped_keys,
        "ambiguities": result.ambiguities,
        "cost_block": tabular_cost_block(len(accepted)),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "error": "usage: preview.py <path>"}))
        raise SystemExit(1)

    _mapping_path = None
    try:
        import config_gate

        _mapping_path = config_gate.load_config().get("column_mapping_path")
    except Exception:
        _mapping_path = None

    try:
        _preview = build_preview(sys.argv[1], _mapping_path)
    except Exception as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    print(json.dumps({"ok": True, "preview": _preview}))
