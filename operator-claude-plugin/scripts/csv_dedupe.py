"""operator-claude-plugin/scripts/csv_dedupe.py

The plugin pre-flight collapse for within-batch duplicate CSV rows on the plain
`contact-upload` lane (D-73-03/D-73-04, F-A5). Attempt 2's Stage A CSV carried the same
person three times — one a case variant — and nothing collapsed them before the send, so
the batch reached HubSpot Create with a duplicate email and took a 409.

Clusters rows on `extraction.py`'s own identity-group rule (`identity_groups()`,
`_first_satisfied_key`, `_group_presence`, `_casefold_trim` — imported, never
re-implemented) so this module never carries a second identity rule. It deliberately
avoids the OTHER pair of functions that module ships (the ones behind its own
merge-and-conflict resolution) — that pair merges a cluster's fields and drops
disagreements as conflicts, which is the wrong semantics here. D-73-04 wants: the FIRST
occurrence wins byte-for-byte, no field merge, no batch refusal — and the loser is
reported with the outcome `duplicate_in_csv`, naming the winner's row number.

Row numbers are spreadsheet rows, as an operator sees them in the file's own gutter: the
header is row 1, so the first data row is row 2. This is NOT the same count as
SESSION-2026-09-15.md's own "rows 37/38 = row 3" prose, which counts data rows only and
excludes the header — checked against the real Stage A CSV, its "row 3" is this module's
row 4, and its "rows 37/38" are this module's rows 38/39 (off by one, the header row).

Mirrors `name_split.py`'s established idiom: a propose mode that reports without writing,
and an apply mode that writes a corrected copy and returns its path. Unlike
`name_split.py`, the write does NOT default into a fixed plugin-relative scratch dir
(WR-12): two different source files sharing a bare stem silently overwrote each other's
output and report there, so the default output location is the input's OWN resolved
parent directory instead — both files land beside the input unless a caller explicitly
overrides `scratch_dir`. Comparison is exact, casefolded and trimmed only — no
similarity score, no approximate matcher; this codebase has none, deliberately
(24-RESEARCH.md Pitfall 5).
"""
import csv
import json
from pathlib import Path

from extraction import _first_satisfied_key, identity_groups
from preview import label_headers, resolve_mapping_path
from tabular import read_table

DUPLICATE_OUTCOME = "duplicate_in_csv"


def _canonical_rows(headers, rows, mapping_path=None):
    """Map each raw row onto the canonical prop names `identity_groups()` speaks (e.g.
    "Email Address" -> "email"), through the SAME alias lookup `preview.py`'s own
    display labelling uses — never a second lookup of its own. A header with no
    canonical mapping contributes no key to the row.

    Indexed by position against `canonical_headers`, never `zip()` (WR-11): a row
    shorter than the header — an exporter that omits trailing empty cells produces
    exactly this shape — keeps every header column, with each missing trailing value
    keyed to an empty string, rather than losing it to a zip that stops at the shorter
    sequence. A row LONGER than the header is handled by the same walk without
    raising: anything past the header's own length is simply never read, never folded
    into the last column.
    """
    labels = label_headers(headers, resolve_mapping_path(mapping_path))
    canonical_headers = [label["canonical"] for label in labels["labels"]]
    return [
        {c: (row[i] if i < len(row) else "")
         for i, c in enumerate(canonical_headers) if c is not None}
        for row in rows
    ]


def find_duplicates(headers, rows, mapping_path=None, groups=None):
    """Cluster `rows` (raw, header-indexed) on the first identity group each fully
    satisfies. Never merges anything and never refuses the batch.

    Returns `(kept_indices, collapsed)`:
      kept_indices — positions in `rows` to keep, in original order (winners plus every
                     row that satisfies no identity group at all)
      collapsed    — one entry per loser: `{"row", "duplicate_of", "identity_key",
                     "outcome": "duplicate_in_csv"}`, row numbers counted with the header
                     as row 1 (so the first data row is row 2)
    """
    if groups is None:
        groups = identity_groups(mapping_path)
    canonical_rows = _canonical_rows(headers, rows, mapping_path)

    seen = {}
    kept = []
    collapsed = []
    for i, canonical_row in enumerate(canonical_rows):
        key = _first_satisfied_key(canonical_row, groups)
        if key is not None and key in seen:
            winner = seen[key]
            collapsed.append({
                "row": i + 2,
                "duplicate_of": winner + 2,
                "identity_key": "+".join(groups[key[0]]),
                "outcome": DUPLICATE_OUTCOME,
            })
            continue
        if key is not None:
            seen[key] = i
        kept.append(i)
    return kept, collapsed


def propose_dedupe(path, mapping_path=None):
    """Report the collapse `apply_dedupe` would make, without writing anything."""
    headers, rows = read_table(path)
    kept, collapsed = find_duplicates(headers, rows, mapping_path)
    return {
        "original_count": len(rows),
        "kept_count": len(kept),
        "collapsed_count": len(collapsed),
        "collapsed": collapsed,
    }


def apply_dedupe(path, mapping_path=None, scratch_dir=None):
    """Write a corrected copy carrying only the surviving rows — original column order,
    surviving rows' original order, winner fields untouched — and a sidecar JSON report
    of what was collapsed. Returns `{"deduped_path", "collapsed_path", "collapsed",
    "original_count", "kept_count"}`.

    `scratch_dir`, when given, is where both files are written, unchanged from before.
    Its DEFAULT is the input's own resolved parent directory (WR-12), not a fixed
    plugin-relative scratch dir keyed on the bare stem — that fixed-dir default let two
    unrelated sources sharing a stem overwrite each other's output and report. Deriving
    the default from the input's full resolved path means both files land beside the
    input, so a same-stem source living elsewhere is never touched.
    """
    path = Path(path).resolve()
    headers, rows = read_table(path)
    kept, collapsed = find_duplicates(headers, rows, mapping_path)

    out_dir = Path(scratch_dir) if scratch_dir is not None else path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"deduped-{path.stem}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for i in kept:
            writer.writerow(rows[i])

    report_path = out_dir / f"dedupe-report-{path.stem}.json"
    report_path.write_text(json.dumps(collapsed), encoding="utf-8")

    return {
        "deduped_path": str(out_path),
        "collapsed_path": str(report_path),
        "collapsed": collapsed,
        "original_count": len(rows),
        "kept_count": len(kept),
    }


def _resolve_configured_mapping_path():
    """The CLI's own column-mapping resolution (WR-03). Mirrors `preview.py`'s own
    `__main__`, which resolves through the SAME canonical reader —
    `config_gate.load_config().get("column_mapping_path")` — rather than a second,
    independent resolver for the same config key. Degrades to `None` (behaving exactly
    as an unconfigured mapping does today) when the config file is missing, unreadable,
    or the operator has not set a config at all."""
    try:
        import config_gate

        return config_gate.load_config().get("column_mapping_path")
    except Exception:
        return None


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if len(args) < 2 or args[1] not in ("--propose", "--apply"):
        print(json.dumps({
            "ok": False,
            "error": "usage: csv_dedupe.py <path> --propose | csv_dedupe.py <path> --apply",
        }))
        raise SystemExit(1)

    _path, _mode = args[0], args[1]
    _mapping_path = _resolve_configured_mapping_path()
    try:
        if _mode == "--propose":
            print(json.dumps({"ok": True, **propose_dedupe(_path, _mapping_path)}))
        else:
            print(json.dumps({"ok": True, **apply_dedupe(_path, _mapping_path)}))
    except Exception as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)
