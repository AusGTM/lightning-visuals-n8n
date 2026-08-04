"""operator-claude-plugin/scripts/header_suggest.py

Half B of Phase 34: the client SUGGESTS a canonical prop for a header the backend's own
alias table does not recognise, the OPERATOR DECIDES per header, and the backend's
`Map Columns` node still performs the only real mapping. This module corrects the
header ROW of the file the client sends and never writes a canonical-prop value into a
data row itself (STRUCT-01, STRUCT-04).

Modelled explicitly on `_hintLabels` in n8n/code/hubspotEnums.js: "MESSAGE HINT ONLY ...
Never consulted by normalizeEnumValue; only used to make the refusal sentence
actionable." Same rule one layer up, headers instead of enum values: fuzzy logic lives
HERE, and only here — never inside preview.label_headers(), whose own comment
(preview.py:39-44) forbids adding fuzzy matching to it, because a smarter matcher there
would mislabel a column the backend really does map, the one thing the preview must
never do.
"""
import csv
import difflib
import json
import sys
from pathlib import Path

import preview
from tabular import read_table

# Reuse preview's own normalizer and alias-table loader rather than defining a second
# copy of either. A second normalizer, or a second YAML read, would be the same
# hand-maintained-drift class 34-RESEARCH.md Pitfall 4 describes one layer down (there
# it is two files disagreeing about a table; here it would be two functions
# disagreeing about what "normalized" means, or two readers of the same YAML that can
# silently diverge in how they fail).

SCRATCH_DIR = Path(__file__).resolve().parent.parent / "scratch"

# Measured (34-RESEARCH.md): the lowest cutoff that surfaces "ph." -> "phone" at all.
SUGGEST_CUTOFF = 0.5

# Normalized name-splitting header shapes: this system deliberately has no
# name-splitter, so none of these may ever reach the fuzzy matcher (task 2 wires the
# pre-check in; the membership is final as of this commit). Kept a small, named,
# greppable constant rather than a pattern — a regex chasing every name-shaped header
# starts refusing headers that are genuinely single-field.
REFUSE_NAME_SHAPES = frozenset(
    {"full name", "fullname", "full_name", "name", "contact name", "person name"}
)

# Task 2 writes this sentence.
NAME_REFUSAL_REASON = ""


class HeaderSuggestError(Exception):
    """Raised for a confirmed target outside the canonical props, or a confirmed
    source header that is name-shaped. Either way, nothing is written."""


def canonical_props(mapping_path=None):
    """The canonical props the backend's alias table defines, via preview's own
    loader — never a second YAML read. `None` when the mapping is unavailable."""
    _aliases, props = preview._load_aliases(preview.resolve_mapping_path(mapping_path))
    return props


def _sample_values(rows, index):
    """Up to three non-empty, stripped cells from column `index` of `rows` (empty list
    when `rows` is None or the column is empty). Load-bearing, not decoration:
    measured against the canonical props, "photo" scores 0.6 against "phone" — HIGHER
    than "ph." does. An operator asked to confirm Ph. -> phone without seeing what is
    in the column is being asked to rubber-stamp, which is the ceremony CONTEXT.md §3
    says this must not be.
    """
    if not rows:
        return []
    values = []
    for row in rows:
        if index >= len(row):
            continue
        value = str(row[index]).strip()
        if value:
            values.append(value)
        if len(values) == 3:
            break
    return values


def suggest_headers(headers, rows=None, mapping_path=None):
    """The per-header verdict set for a header row the operator is about to send.

    Returns:
        {
          "available": bool,
          "mapped": [{"header", "canonical"}],
          "suggestions": [{"header", "suggestion", "score", "sample_values"}],
          "refusals": [{"header", "reason", "sample_values"}],
          "unresolved": [{"header", "sample_values"}],
          "needs_confirmation": bool,
        }

    A suggester that cannot read the backend's own alias table has nothing honest to
    say, and guessing there would be the confidently-wrong direction this phase exists
    to close — `available` is False and every list stays empty when the mapping is
    unavailable. Never writes anything; that is `apply_confirmed_corrections`' job,
    only ever run after an explicit per-header confirmation.
    """
    aliases, props = preview._load_aliases(preview.resolve_mapping_path(mapping_path))
    result = {
        "available": aliases is not None,
        "mapped": [],
        "suggestions": [],
        "refusals": [],
        "unresolved": [],
        "needs_confirmation": False,
    }
    if aliases is None:
        return result

    for i, h in enumerate(headers):
        normalized = preview._normalize_header(h)
        sample_values = _sample_values(rows, i)

        canonical = aliases.get(normalized)
        if canonical:
            result["mapped"].append({"header": h, "canonical": canonical})
            continue

        # Task 2 inserts the name-shape refusal pre-check HERE, before difflib is ever
        # consulted (REFUSE_NAME_SHAPES / NAME_REFUSAL_REASON above). Order matters:
        # measured, "full name" scores 0.588 against "lastname" — HIGHER than "ph."
        # scores against its own correct answer (0.5) — so no cutoff below can
        # separate the two cases; only a pre-check that runs first can.

        matches = difflib.get_close_matches(normalized, props, n=1, cutoff=SUGGEST_CUTOFF)
        if matches:
            suggestion = matches[0]
            score = round(difflib.SequenceMatcher(None, normalized, suggestion).ratio(), 3)
            result["suggestions"].append(
                {
                    "header": h,
                    "suggestion": suggestion,
                    "score": score,
                    "sample_values": sample_values,
                }
            )
        else:
            result["unresolved"].append({"header": h, "sample_values": sample_values})

    result["needs_confirmation"] = bool(result["suggestions"])
    return result


def apply_confirmed_corrections(path, confirmed, scratch_dir=SCRATCH_DIR, mapping_path=None):
    """Write a corrected copy of `path` whose header row is the only thing that
    changed, under `scratch_dir`. `confirmed` maps the ORIGINAL header string to the
    corrected header string the operator approved (e.g. `{"Ph.": "phone"}`). A header
    absent from `confirmed` passes through untouched. Callers must always pass the
    ORIGINAL path, never a previously corrected one — this function does not track
    lineage. Returns the corrected file's path as a string.

    Mirrors extraction.write_dispatch_csv's SCRATCH_DIR + csv.writer idiom without
    importing it: that function takes rows-of-dicts and enforces a canonical header;
    this one changes header STRINGS only and must not restructure anything.
    """
    headers, rows = read_table(path)
    corrected = [confirmed.get(h, h) for h in headers]

    scratch_dir = Path(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    out_path = scratch_dir / f"corrected-{Path(path).stem}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(corrected)
        writer.writerows(rows)
    return str(out_path)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(
            json.dumps(
                {"ok": False, "error": "usage: header_suggest.py <path> [--confirm SRC=CANONICAL ...]"}
            )
        )
        raise SystemExit(1)

    _path = args[0]
    _confirmed = {}
    for _idx, _arg in enumerate(args[1:], start=1):
        if args[_idx - 1] == "--confirm":
            continue  # already consumed as the previous flag's value
        if _arg == "--confirm" and _idx + 1 < len(args):
            _src, _, _target = args[_idx + 1].partition("=")
            _confirmed[_src] = _target

    try:
        if _confirmed:
            _corrected_path = apply_confirmed_corrections(_path, _confirmed)
            print(
                json.dumps(
                    {"ok": True, "corrected_path": _corrected_path, "rewritten": _confirmed}
                )
            )
        else:
            _headers, _rows = read_table(_path)
            print(json.dumps({"ok": True, "suggest": suggest_headers(_headers, _rows)}))
    except Exception as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)
