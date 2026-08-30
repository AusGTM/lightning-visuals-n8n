"""operator-claude-plugin/tests/test_run_state.py

Phase 61 Plan 05. Task 1's premise re-assertion lives here (functions named with
"premises" so `pytest -q -k premises` selects exactly this section, per the plan's own
verify command) — a TEXT-ONLY read of `.planning/phases/*/61-SPIKE-VERDICT.md`, never an
import of anything under `scripts/`, mirroring `test_spike_verdict_61.py`'s own pure
text/AST-analysis discipline (never touching `no_durable_writes`, never importing what it
inspects).

WHY THIS DUPLICATES A SMALL AMOUNT OF `test_spike_verdict_61.py`'s PARSING RATHER THAN
IMPORTING IT: the plan's own Task 1 action text says "resolve the verdict doc's path the
SAME WAY test_spike_verdict_61.py does", not "import test_spike_verdict_61.py" — and this
file's own `_looks_forbidden`-style precedent throughout this plugin (`held_queue.py`
re-implementing `run_manifest.py`'s forbidden-name list rather than importing it) is
exactly this: a small, load-bearing predicate copied so a change to one test file's own
internals cannot silently change what THIS one enforces.

THE MECHANICAL HALT RULE (the plan's own words): "select the premises naming `61-05` and
halt on those. A premise this plan does not depend on may be `[unknown]` without blocking
anything." This module reads every premise's own `Dependents:` field (already present on
every numbered premise entry in `## Premises`, REVIEW-04's own addition) and asserts: a
premise naming `61-05` in its Dependents field never carries `[unknown]`. This is
MECHANICAL — a lookup over the doc's own text, never a judgement call about which
premises "feel" relevant.

Per Task 1's own action text: this is written so a LATER edit to the verdict doc that
retracts a premise's resolved status FAILS THIS SUITE, rather than leaving `run_state.py`
(Task 2) standing on a fact the doc no longer asserts.
"""
import glob
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

BASIS_TOKENS = ("measured", "derived", "documented", "unknown")
BASIS_RE = re.compile(r"\[(" + "|".join(BASIS_TOKENS) + r")\]")
_PREMISE_ID_RE = re.compile(r"\bP-(\d+)\b")
_NUMBERED_RE = re.compile(r"^\d+\.\s")

# The plan this test belongs to — the literal token every premise line's own Dependents
# field carries when this plan reads it.
THIS_PLAN = "61-05"


def _find_doc_path():
    """Same resolution as `test_spike_verdict_61.py::_find_doc_path` — globs BOTH
    `.planning/phases/` and `.planning/milestones/*-phases/`, because this repo archives
    a phase directory into the milestone tree at milestone completion (CLAUDE.md's
    as-built-delta discipline). A hardcoded phase path would fail this test spuriously
    the day that happens."""
    candidates = sorted(
        glob.glob(str(REPO_ROOT / ".planning/phases/*/61-SPIKE-VERDICT.md"))
        + glob.glob(str(REPO_ROOT / ".planning/milestones/*-phases/*/61-SPIKE-VERDICT.md"))
    )
    return candidates[0] if candidates else None


def _read_doc():
    path = _find_doc_path()
    if path is None:
        pytest.fail(
            "61-SPIKE-VERDICT.md not found under .planning/phases/*/ or "
            ".planning/milestones/*-phases/*/ — has it been created yet, or moved by a "
            "milestone archive?"
        )
    return Path(path).read_text(encoding="utf-8")


def _lines_with_fence_state(text):
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            yield line, True
            in_fence = not in_fence
            continue
        yield line, in_fence


def _is_claim_line(line):
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("|"):
        return False
    return stripped.startswith("- ") or bool(_NUMBERED_RE.match(stripped))


def _section_body(text, heading):
    """Text strictly between `heading` and the next heading of the same or a shallower
    level (or EOF) — same contract as `test_spike_verdict_61.py::_section_body`."""
    lines = text.splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    start = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for i in range(start, len(lines)):
        candidate = lines[i]
        if candidate.startswith("#"):
            candidate_level = len(candidate) - len(candidate.lstrip("#"))
            if candidate_level <= level:
                end = i
                break
    return "\n".join(lines[start:end])


def _premise_lines(text):
    body = _section_body(text, "## Premises")
    assert body is not None, "## Premises section not found in 61-SPIKE-VERDICT.md"
    return [
        line.strip()
        for line, in_fence in _lines_with_fence_state(body)
        if not in_fence and _is_claim_line(line)
    ]


def _premises_by_id(text):
    """{'P-01': full_line, ...} — one entry per numbered premise claim line."""
    by_id = {}
    for line in _premise_lines(text):
        ids = {f"P-{i}" for i in _PREMISE_ID_RE.findall(line)}
        for pid in ids:
            by_id.setdefault(pid, line)
    return by_id


def _dependents_field(line):
    """The text of a premise line's own `Dependents:` field (case-sensitive on the
    literal word, matching the doc's own convention) — everything from `Dependents:` to
    the end of the line, or `''` if the field is absent (a malformed premise entry the
    other premises-* tests in `test_spike_verdict_61.py` already forbid)."""
    marker = "Dependents:"
    idx = line.find(marker)
    return line[idx + len(marker):].strip() if idx != -1 else ""


def _basis_token(line):
    matches = BASIS_RE.findall(line)
    return matches[0] if matches else None


# =====================================================================================
# -k premises
# =====================================================================================

def test_premises_this_plan_depends_on_are_all_resolved():
    """The mechanical halt rule: every premise whose OWN `Dependents:` field names
    `61-05` must carry a resolved basis token (measured/derived/documented), never
    `[unknown]`. Per the plan's own words: "A premise this plan does not depend on may be
    `[unknown]` without blocking anything" — so this test does NOT assert anything about
    premises that do not name 61-05 (P-05 is the one premise in this doc that does not,
    per its own `dependents: none (context only)` line)."""
    text = _read_doc()
    by_id = _premises_by_id(text)
    assert by_id, "## Premises carries no premise entries at all"

    dependent_on_this_plan = {
        pid: line for pid, line in by_id.items()
        if THIS_PLAN in _dependents_field(line)
    }
    assert dependent_on_this_plan, (
        f"no premise in 61-SPIKE-VERDICT.md names {THIS_PLAN!r} in its Dependents field — "
        "either the doc changed shape or this plan's own dependency was never recorded"
    )

    unresolved = {
        pid: line for pid, line in dependent_on_this_plan.items()
        if _basis_token(line) == "unknown"
    }
    assert not unresolved, (
        f"HALT: premise(s) this plan depends on are still [unknown]: "
        f"{sorted(unresolved)} — per the plan's own Task 1, this must stop the plan "
        f"rather than proceed on a substitute mechanism. Lines: {list(unresolved.values())}"
    )


def test_premises_operator_run_state_decision_is_present_and_named():
    """Task 1's second halt condition: "the operator's run-state decision is absent".
    `## Operator Decision (Task 4)` must exist and name the actual decision (a HubSpot
    object plus the existing run_manifest.py), not merely the heading."""
    text = _read_doc()
    assert "## Operator Decision (Task 4)" in text, (
        "61-SPIKE-VERDICT.md carries no '## Operator Decision (Task 4)' section — the "
        "run-state decision this plan is written against is absent. HALT."
    )
    body = _section_body(text, "## Operator Decision (Task 4)")
    assert body is not None
    assert "HubSpot object" in body, (
        "the operator decision section exists but does not name a HubSpot object as "
        "part of the run-state store — has the decision changed shape?"
    )
    assert "run_manifest" in body, (
        "the operator decision section exists but does not name run_manifest.py as part "
        "of the run-state store — has the decision changed shape?"
    )


def test_premises_budget_premise_p11_fits_both_batch_sizes_and_is_resolved():
    """Task 1's third halt condition: "the selected substrate's own execution arithmetic
    exceeds the monthly budget for the batch sizes 61-01 costed". P-11 is the premise
    this doc's own dependents table names for exactly this check (`dependents: 61-05 T1
    (must_haves truth on budget), T4`)."""
    text = _read_doc()
    by_id = _premises_by_id(text)
    assert "P-11" in by_id, "P-11 (the budget-fits premise) not found in ## Premises"
    line = by_id["P-11"]
    assert _basis_token(line) != "unknown", f"P-11 must not be [unknown]: {line!r}"
    assert "fit" in line.lower(), (
        f"P-11 no longer states that both batch sizes fit the allowance — re-check the "
        f"budget before proceeding: {line!r}"
    )
    assert "2,500" in line or "2500" in line, (
        f"P-11 no longer names the 2,500/month allowance it is checked against: {line!r}"
    )


def test_premises_all_six_previously_open_premises_stay_resolved():
    """Belt on `test_spike_verdict_61.py::test_previously_unknown_premises_now_carry_a_
    non_unknown_basis` — this plan's own copy of the same six-id check, so a regression
    in the OTHER file's own assertion cannot silently let this plan proceed on a
    reopened premise between when that suite last ran and when this one does."""
    text = _read_doc()
    by_id = _premises_by_id(text)
    formerly_unknown = ("P-05", "P-07", "P-08", "P-09", "P-10", "P-13")
    for pid in formerly_unknown:
        assert pid in by_id, f"{pid} not found in ## Premises at all"
        token = _basis_token(by_id[pid])
        assert token in ("measured", "derived", "documented"), (
            f"{pid} must carry a resolved basis token: {by_id[pid]!r}"
        )
