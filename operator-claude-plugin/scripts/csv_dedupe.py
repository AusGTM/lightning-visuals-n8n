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
and an apply mode that writes a corrected copy into the scratch dir and returns its path.
Comparison is exact, casefolded and trimmed only — no similarity score, no approximate
matcher; this codebase has none, deliberately (24-RESEARCH.md Pitfall 5).
"""
import csv
import json
from pathlib import Path

from extraction import _first_satisfied_key, identity_groups
from preview import label_headers, resolve_mapping_path
from tabular import read_table

SCRATCH_DIR = Path(__file__).resolve().parent.parent / "scratch"

DUPLICATE_OUTCOME = "duplicate_in_csv"


def _canonical_rows(headers, rows, mapping_path=None):
    """Map each raw row onto the canonical prop names `identity_groups()` speaks (e.g.
    "Email Address" -> "email"), through the SAME alias lookup `preview.py`'s own
    display labelling uses — never a second lookup of its own. A header with no
    canonical mapping contributes no key to the row."""
    labels = label_headers(headers, resolve_mapping_path(mapping_path))
    canonical_headers = [label["canonical"] for label in labels["labels"]]
    return [
        {c: v for c, v in zip(canonical_headers, row) if c is not None}
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


def apply_dedupe(path, mapping_path=None, scratch_dir=SCRATCH_DIR):
    """Write a corrected copy into `scratch_dir` carrying only the surviving rows —
    original column order, surviving rows' original order, winner fields untouched —
    and a sidecar JSON report of what was collapsed. Returns `{"deduped_path",
    "collapsed_path", "collapsed", "original_count", "kept_count"}`.
    """
    path = Path(path)
    headers, rows = read_table(path)
    kept, collapsed = find_duplicates(headers, rows, mapping_path)

    scratch_dir = Path(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    out_path = scratch_dir / f"deduped-{path.stem}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for i in kept:
            writer.writerow(rows[i])

    report_path = scratch_dir / f"dedupe-report-{path.stem}.json"
    report_path.write_text(json.dumps(collapsed), encoding="utf-8")

    return {
        "deduped_path": str(out_path),
        "collapsed_path": str(report_path),
        "collapsed": collapsed,
        "original_count": len(rows),
        "kept_count": len(kept),
    }


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
    try:
        if _mode == "--propose":
            print(json.dumps({"ok": True, **propose_dedupe(_path)}))
        else:
            print(json.dumps({"ok": True, **apply_dedupe(_path)}))
    except Exception as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)
