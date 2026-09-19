"""operator-claude-plugin/scripts/preview.py

Builds the operator-facing preview: what will be sent, what will be dropped, and how
much there is — before a single byte goes over the wire (D-07/D-08/D-09/D-10,
PREVIEW-01, PREVIEW-04).

This module OWNS the one rule for FINDING config/column_mapping.yaml (extraction.py
calls resolve_mapping_path too). Its own use of the contents is a
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
# Shipped INSIDE the plugin package, so an installed copy with no repo beside it can still
# resolve it. Until 0.7.3 only a repo-root path existed, which meant every real install
# resolved to nothing: preview labels silently went unavailable and extraction REFUSED
# outright (`mapping_unavailable`), blocking every non-tabular adapter. Found by an operator
# walking UAT session 2 on the 0.7.2 install.
#
# 0.50.2: the repo-root fallback (`PLUGIN_ROOT.parent / "config" / ...`) is GONE from every
# runtime resolver in this plugin (here, preingest.py, review_queue.py). The plugin must
# behave identically with and without a repo checkout beside it — a fallback that only a
# dev machine can take hides a missing shipped file from every dev-machine test. The
# repo copy is now referenced by the parity TESTS only (test_column_mapping_shipped.py,
# test_preingest_merge.py), which compute the repo path themselves.
PLUGIN_MAPPING_PATH = PLUGIN_ROOT / "config" / "column_mapping.yaml"

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
    then the plugin's own shipped copy, then None (unavailable). Shared by this
    module's display-only labelling and extraction.py's canonical-prop/identity-group
    derivation, so exactly one rule for finding that file exists in the plugin — callers
    decide whether "unavailable" degrades gracefully (this module's labels) or is a hard
    error (extraction.py's validation allowlist)."""
    if mapping_path is not None:
        return Path(mapping_path)
    if PLUGIN_MAPPING_PATH.exists():
        return PLUGIN_MAPPING_PATH
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


def collapse_block(collapsed) -> dict:
    """The within-batch duplicate collapse summary for the operator's preview
    (D-73-03/D-73-04, F-A5): how many rows `csv_dedupe.py` collapsed before this file
    was previewed, and each one's own losing row number, winner row number, and the
    identity key that matched. Always returns the same shape — `count: 0`/`rows: []`
    when nothing collapsed, or `collapsed` was never supplied — so a caller renders one
    shape either way rather than branching on whether the key is present at all. This
    module never imports `csv_dedupe` (that import would run the wrong direction — the
    collapse already happened upstream; this is display of its result, not a second
    computation of it)."""
    collapsed = collapsed or []
    return {"count": len(collapsed), "rows": list(collapsed)}


class CollapsedBlockError(Exception):
    """`--collapsed <path>` was explicitly requested and the read failed — missing,
    unreadable, or malformed JSON (WR-04). Never raised when no path was requested at
    all; that stays the silent absent-block path `collapse_block(None)` already
    handles."""


def read_collapsed_block(collapsed_arg_path):
    """Read `csv_dedupe.py`'s `--apply` sidecar report for the CLI's `--collapsed` flag
    (WR-04). This module never re-derives the collapse itself — see `collapse_block`'s
    own docstring.

    Returns `None` — the absent-block path, unchanged — ONLY when no path was requested
    at all (`collapsed_arg_path` is falsy). A path that WAS requested but cannot be read
    for any reason (missing, unreadable, malformed JSON) is a genuine failure: silently
    returning `None` there would make `pre_collapse_row_count == row_count`, which reads
    exactly like a batch with no duplicates — the one case the operator most needs to be
    able to tell apart from "nothing collapsed". Raises `CollapsedBlockError` naming the
    offending path instead of swallowing it (73-REVIEW.md's own fix, D-74-10).
    """
    if not collapsed_arg_path:
        return None
    try:
        return json.loads(Path(collapsed_arg_path).read_text(encoding="utf-8"))
    except Exception as e:
        raise CollapsedBlockError(
            f"--collapsed {collapsed_arg_path} could not be read ({e})") from e


def tabular_cost_block(row_count) -> str:
    """This lane's cost block, rendered through the enrichment lane's SAME helper.

    Criterion 3 says every preview on both lanes. Contact-upload calls no provider and
    makes no model call, so its honest figures are zero credits and zero dollars WITH the
    reason stated — a real, explainable zero, unlike a balance that could not be read
    (D-16). Reusing the one helper is the point: two cost blocks that can drift apart is
    the second-source-of-truth pattern this milestone avoids everywhere else.
    """
    return cost_block(zero_cost_estimate(row_count), {}, reason=TABULAR_COST_REASON)


def build_preview(path, mapping_path=None, collapsed=None) -> dict:
    """Build the structured preview for one tabular file. Read-only end to end: no
    network call, and the source file's bytes are identical before and after.

    Mapping-file resolution order: an explicit `mapping_path` argument, then the repo's
    config/column_mapping.yaml, then unavailable (labels flagged, not guessed).

    `collapsed` (D-73-03/D-73-04, F-A5) is the `csv_dedupe.py` collapse list for
    whatever file was previewed BEFORE its duplicates were collapsed — `path` here is
    already the deduped file, so `row_count` alone cannot say how many rows the
    operator's own file started with. `pre_collapse_row_count` restores that
    reconciliation number (`row_count + len(collapsed)`) without this module ever
    re-deriving the collapse itself.
    """
    headers, rows = read_table(path)
    row_count = len(rows)
    collapsed = collapsed or []

    header_labels = label_headers(headers, resolve_mapping_path(mapping_path))

    preview = {
        "headers": headers,
        "row_count": row_count,
        "pre_collapse_row_count": row_count + len(collapsed),
        "collapsed_rows": collapse_block(collapsed),
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
    `.accepted`/`.rejected`/`.dropped_keys`/`.ambiguities` attributes, plus the optional
    `.resolvable` attribute added by D-59-08) — this module does not import
    extraction.py, so there is no import cycle with extraction.py importing
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
        # D-59-08: getattr with a default is required, not stylistic — this function's
        # duck-typing contract must keep working for a shim carrying only the four
        # original attributes; a bare `.resolvable` access would break every such caller.
        "resolvable": getattr(result, "resolvable", []),
        "cost_block": tabular_cost_block(len(accepted)),
    }


if __name__ == "__main__":
    import sys

    _args = sys.argv[1:]
    if not _args:
        print(json.dumps({
            "ok": False,
            "error": "usage: preview.py <path> [--collapsed <collapsed.json>]",
        }))
        raise SystemExit(1)

    _path = _args[0]
    _collapsed_arg_path = None
    for _i, _a in enumerate(_args):
        if _a == "--collapsed" and _i + 1 < len(_args):
            _collapsed_arg_path = _args[_i + 1]

    _mapping_path = None
    try:
        import config_gate

        _mapping_path = config_gate.load_config().get("column_mapping_path")
    except Exception:
        _mapping_path = None

    # csv_dedupe.py's own `--apply` sidecar report — read-only, never re-derived here
    # (this module never imports csv_dedupe; see collapse_block's docstring). A path
    # that was explicitly requested and could not be read is a genuine failure (WR-04);
    # only "no path requested" stays the silent absent-block path.
    try:
        _collapsed = read_collapsed_block(_collapsed_arg_path)
    except CollapsedBlockError as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    try:
        _preview = build_preview(_path, _mapping_path, collapsed=_collapsed)
    except Exception as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    print(json.dumps({"ok": True, "preview": _preview}))
