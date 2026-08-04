"""operator-claude-plugin/scripts/name_split.py

Propose a first/last split for a single full-name column, per row, for the operator to
review BEFORE anything is written. Nothing here is committed to the backend and nothing
here becomes a rule: the backend's `Map Columns` has no name-splitter, this module does
not add one to it, and no proposal reaches a file until the operator hands the resolved
rows back to `apply_name_split`.

Why this exists at all (operator decision, 2026-08-05): refusing outright was stricter
than the pattern immediately next to it. A header the alias table does not know is
PROPOSED and confirmed; a name column was simply refused. Both are "the tool cannot know,
the human can" — so both get the same shape. What has NOT changed is the thing the
refusal was protecting: a split is never silent, never assumed correct, and never applied
to a row the operator has not seen.

The honesty rule this module runs on: a name the heuristic cannot split confidently is
returned with `confidence: "low"` and a reason NAMING what is ambiguous about it — never
a confident-looking guess. "Maria de los Santos" and "Maria Jane Santos" are the same
shape to a machine and different to a person, which is exactly why the person decides.
"""
import csv
from pathlib import Path

SCRATCH_DIR = Path(__file__).resolve().parent.parent / "scratch"

# Surname particles: tokens that BELONG TO the surname rather than separating names.
# Lowercased, matched case-insensitively. "van der Berg" is one surname, not two names —
# splitting on whitespace is what turns it into fragments, and that failure is the whole
# reason this module reports confidence instead of just returning a pair.
PARTICLES = frozenset({
    "van", "von", "der", "den", "de", "del", "della", "di", "da", "das", "dos", "du",
    "la", "le", "el", "lo", "ter", "ten", "af", "av", "bin", "ibn", "abu", "st", "st.",
    "mac", "mc", "o'", "san", "santa", "vander", "vande",
})

# Stripped from the front; recorded, never silently discarded.
TITLES = frozenset({
    "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "miss", "dr", "dr.", "prof", "prof.",
    "sir", "dame", "rev", "rev.", "hon", "hon.",
})

# Stripped from the end; kept with the surname is wrong for some and right for others,
# so they are recorded separately and the operator sees them.
SUFFIXES = frozenset({
    "jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "phd", "ph.d.", "md", "m.d.", "esq",
    "esq.", "oam", "am", "ao",
})


class NameSplitError(Exception):
    """Raised when a write would misalign rows or overwrite a column that already holds
    data. Nothing is written."""


def _tokens(value):
    return [t for t in str(value or "").replace(" ", " ").split() if t]


def propose_split(value):
    """One row's proposal. Never raises; an unusable value comes back with both parts
    None and a reason.

    Returns:
        {"raw", "firstname", "lastname", "confidence": "high"|"low", "reason": str|None,
         "title": str|None, "suffix": str|None}
    """
    raw = "" if value is None else str(value)
    out = {"raw": raw, "firstname": None, "lastname": None,
           "confidence": "low", "reason": None, "title": None, "suffix": None}

    stripped = raw.strip()
    if not stripped:
        out["reason"] = "the cell is empty — nothing to split"
        return out

    # "Raman, Priya" — the comma is an explicit statement of which part is the surname,
    # and is the one form where the order is not a guess.
    if stripped.count(",") == 1:
        last_part, _, first_part = stripped.partition(",")
        last_tokens, first_tokens = _tokens(last_part), _tokens(first_part)
        if last_tokens and first_tokens:
            out.update(
                firstname=" ".join(first_tokens),
                lastname=" ".join(last_tokens),
                confidence="high",
                reason=None,
            )
            return out
    if stripped.count(",") > 1:
        out["reason"] = "more than one comma — the intended order cannot be read"
        return out

    tokens = _tokens(stripped)

    if tokens and tokens[0].lower() in TITLES:
        out["title"] = tokens[0]
        tokens = tokens[1:]
    if tokens and tokens[-1].lower().rstrip(",") in SUFFIXES:
        out["suffix"] = tokens[-1]
        tokens = tokens[:-1]

    if not tokens:
        out["reason"] = "nothing left after the title/suffix — no name to split"
        return out

    if len(tokens) == 1:
        # Deliberately NOT guessed into either field. A single token is a given name in
        # some files and a surname in others, and the identity rule needs both, so a
        # wrong guess here silently produces a row that looks complete and is not.
        out["firstname"] = tokens[0]
        out["reason"] = (
            f'"{tokens[0]}" is a single word — it could be a given name or a surname, '
            "so the surname is left blank rather than guessed"
        )
        return out

    if len(tokens) == 2:
        out.update(firstname=tokens[0], lastname=tokens[1], confidence="high")
        return out

    # 3+ tokens. A particle marks where the surname starts and is a real signal.
    particle_at = next(
        (i for i, t in enumerate(tokens) if i > 0 and t.lower() in PARTICLES), None
    )
    if particle_at is not None:
        out.update(
            firstname=" ".join(tokens[:particle_at]),
            lastname=" ".join(tokens[particle_at:]),
            confidence="high",
        )
        return out

    # No particle: a middle name and a two-word surname are indistinguishable here.
    out.update(
        firstname=tokens[0],
        lastname=" ".join(tokens[1:]),
        reason=(
            f"{len(tokens)} parts and no surname particle — a middle name and a "
            "two-word surname look identical, so check this one"
        ),
    )
    return out


def propose_column_split(values):
    """Proposals for a whole column, plus a summary the operator can act on."""
    proposals = [propose_split(v) for v in values]
    return {
        "proposals": proposals,
        "total": len(proposals),
        "high_confidence": sum(1 for p in proposals if p["confidence"] == "high"),
        "needs_attention": [
            {"index": i, **p} for i, p in enumerate(proposals) if p["confidence"] == "low"
        ],
    }


def apply_name_split(path, source_column, resolved_rows, scratch_dir=SCRATCH_DIR):
    """Write a corrected copy with `source_column` replaced by `firstname`/`lastname`,
    using the rows the OPERATOR resolved — never this module's own proposals.

    `resolved_rows` is a list of `(firstname, lastname)` aligned to the file's data rows.
    Taking the resolved values as an argument rather than re-deriving them is the whole
    safety property: the writer cannot apply a split the operator did not see, because it
    has no splitter of its own to fall back on.

    Both guards run before any file is opened, so a refused call leaves the disk untouched.
    """
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        raise NameSplitError(f"{path} has no header row — nothing to split.")

    headers, data = rows[0], rows[1:]

    if source_column not in headers:
        raise NameSplitError(
            f"{source_column!r} is not a column in this file: {headers}. Nothing was written."
        )

    # Guard 1: misalignment is the failure that silently attaches one person's surname to
    # another person's row, and it cannot be detected by looking at the output.
    if len(resolved_rows) != len(data):
        raise NameSplitError(
            f"got {len(resolved_rows)} resolved names for {len(data)} data rows — "
            "refusing to write a file whose names may not line up with their rows."
        )

    src = headers.index(source_column)

    # Guard 2: never overwrite a firstname/lastname column that already carries data.
    out_headers = [h for i, h in enumerate(headers) if i != src]
    for name in ("firstname", "lastname"):
        if name in [h.strip().lower() for h in out_headers]:
            col = [h.strip().lower() for h in out_headers].index(name)
            if any((r[col] if col < len(r) else "").strip() for r in
                   ([x for i, x in enumerate(row) if i != src] for row in data)):
                raise NameSplitError(
                    f"this file already has a populated {name!r} column — refusing to "
                    "overwrite it. Nothing was written."
                )
            out_headers = [h for h in out_headers if h.strip().lower() != name]

    out_headers = out_headers + ["firstname", "lastname"]

    scratch_dir = Path(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)
    out_path = scratch_dir / f"split-{path.stem}.csv"
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(out_headers)
        for row, (first, last) in zip(data, resolved_rows):
            kept = [c for i, c in enumerate(row) if i != src]
            kept = kept[: len(out_headers) - 2]
            writer.writerow(kept + [first or "", last or ""])
    return str(out_path)


if __name__ == "__main__":
    import json
    import sys

    from tabular import read_table

    args = sys.argv[1:]
    if len(args) < 2:
        print(json.dumps({
            "ok": False,
            "error": "usage: name_split.py <path> --propose <COLUMN> | "
                     "name_split.py <path> --apply <COLUMN> --resolved <resolved.json>",
        }))
        raise SystemExit(1)

    _path = args[0]
    _mode = None
    _column = None
    _resolved_path = None
    for _i, _a in enumerate(args):
        if _a == "--propose" and _i + 1 < len(args):
            _mode, _column = "propose", args[_i + 1]
        elif _a == "--apply" and _i + 1 < len(args):
            _mode, _column = "apply", args[_i + 1]
        elif _a == "--resolved" and _i + 1 < len(args):
            _resolved_path = args[_i + 1]

    try:
        _headers, _rows = read_table(_path)
        if _column not in _headers:
            raise NameSplitError(f"{_column!r} is not a column in this file: {_headers}")
        _idx = _headers.index(_column)
        _values = [(r[_idx] if _idx < len(r) else "") for r in _rows]

        if _mode == "propose":
            print(json.dumps({"ok": True, "column": _column,
                              "split": propose_column_split(_values)}))
        elif _mode == "apply":
            if not _resolved_path:
                raise NameSplitError(
                    "--apply needs --resolved <file.json>: a list of [firstname, lastname] "
                    "pairs the OPERATOR reviewed, one per data row. This tool never "
                    "re-derives them."
                )
            _resolved = json.loads(Path(_resolved_path).read_text(encoding="utf-8"))
            _pairs = [(r[0], r[1]) for r in _resolved]
            print(json.dumps({"ok": True,
                              "split_path": apply_name_split(_path, _column, _pairs),
                              "rows": len(_pairs)}))
        else:
            raise NameSplitError("expected --propose <COLUMN> or --apply <COLUMN>")
    except Exception as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)
