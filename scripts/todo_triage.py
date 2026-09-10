"""Todo triage — the rule that stops `.planning/todos/pending/` growing without bound.

Every pending todo declares a `kind` in its frontmatter. Only `defect` counts as debt.

    kind: defect    -> needs `evidence:` (a test path or a recorded run/execution id)
    kind: question  -> needs `trigger:` (the observation that closes it) and `owner:`
    kind: design    -> needs `decision_needed:` (the ruling that turns it into a defect/phase)
    kind: accepted  -> won't-fix; belongs in completed/, never in pending/

Usage:
    todo_triage.py            counts by kind + one line per todo
    todo_triage.py --check    exit 1 on any untriaged/invalid todo (pinned by tests/test_todo_triage.py)
    todo_triage.py --since R  only todos added since git revision R (batch residual review)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PENDING = ROOT / ".planning" / "todos" / "pending"
KINDS = {"defect": ("evidence",), "question": ("trigger", "owner"), "design": ("decision_needed",)}


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    return yaml.safe_load(parts[1]) or {} if len(parts) >= 3 else {}


def validate(path: Path, fm: dict) -> list[str]:
    kind = fm.get("kind")
    if kind == "accepted":
        return ["kind: accepted belongs in completed/, not pending/"]
    if kind not in KINDS:
        return [f"kind missing or not one of {sorted(KINDS) + ['accepted']}"]
    return [f"kind: {kind} requires non-empty `{k}:`" for k in KINDS[kind] if not str(fm.get(k) or "").strip()]


def added_since(rev: str) -> set[Path]:
    out = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=A", rev, "--", str(PENDING.relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    return {ROOT / p for p in out}


def triage(pending: Path = PENDING, since: str | None = None) -> tuple[dict, list[str]]:
    paths = sorted(pending.glob("*.md"))
    if since:
        keep = added_since(since)
        paths = [p for p in paths if p in keep]
    counts: dict[str, int] = {}
    problems: list[str] = []
    for p in paths:
        fm = frontmatter(p)
        rel = p.relative_to(ROOT) if p.is_relative_to(ROOT) else p
        for msg in validate(p, fm):
            problems.append(f"{rel}: {msg}")
        counts[fm.get("kind") or "untriaged"] = counts.get(fm.get("kind") or "untriaged", 0) + 1
        print(f"{fm.get('kind') or 'UNTRIAGED':<10} {fm.get('severity', '-'):<8} {p.name}")
    return counts, problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--since", metavar="REV")
    args = ap.parse_args(argv)
    counts, problems = triage(since=args.since)
    print("counts:", counts, "| debt (defect):", counts.get("defect", 0))
    for msg in problems:
        print("INVALID", msg, file=sys.stderr)
    return 1 if (args.check and problems) else 0


if __name__ == "__main__":
    sys.exit(main())
