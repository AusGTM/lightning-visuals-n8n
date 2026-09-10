"""Every pending todo is triaged (rule 1, 2026-09-11). An untriaged todo fails the suite."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import todo_triage  # noqa: E402


def test_every_pending_todo_is_triaged():
    counts, problems = todo_triage.triage()
    assert problems == [], "\n".join(problems)
    assert "untriaged" not in counts


def test_an_untriaged_or_underspecified_todo_is_reported(tmp_path):
    (tmp_path / "a.md").write_text("---\ntitle: x\n---\nbody\n")
    (tmp_path / "b.md").write_text("---\nkind: question\ntrigger: a run\n---\nbody\n")
    (tmp_path / "c.md").write_text("---\nkind: accepted\n---\nbody\n")
    (tmp_path / "d.md").write_text("---\nkind: defect\nevidence: tests/x.py\n---\nbody\n")
    _, problems = todo_triage.triage(pending=tmp_path)
    assert len(problems) == 3
    assert any("a.md" in p and "kind missing" in p for p in problems)
    assert any("b.md" in p and "`owner:`" in p for p in problems)
    assert any("c.md" in p and "completed/" in p for p in problems)
