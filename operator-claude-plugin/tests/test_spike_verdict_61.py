"""operator-claude-plugin/tests/test_spike_verdict_61.py

Text-only completeness lint for
`.planning/phases/61-autonomous-batch-runs/61-SPIKE-VERDICT.md` (Phase 61 Plan 01). Reads the
doc as TEXT ONLY -- no import, no execution, no network -- the same pure text/AST-analysis
discipline `test_skill_sequence_coverage.py` already established for a different corpus (never
touching `no_durable_writes`, never importing what it inspects).

CLAIM LINE, DEFINED ONCE (REVIEW-A7, all three cycle-3 reviewers flagged "claim line is a
fragile heuristic" -- this is the one definition both this test and the doc's author read).
A claim line is a line whose STRIPPED text either:
  - starts with "- " (a bullet), or
  - matches r"^\\d+\\.\\s" (a numbered entry, e.g. "1. ")
AND is none of the following (all excluded even if they would otherwise match):
  - a heading (stripped text starts with "#")
  - blank
  - a table row (stripped text starts with "|")
  - a line inside a fenced code block (between a pair of ``` markers)
Prose paragraphs, bare commands, and formulas that are none of the above are NOT claim lines and
carry no basis-token obligation.

The doc's path is resolved by globbing BOTH `.planning/phases/` and
`.planning/milestones/*-phases/`, because this repo archives a phase directory into the
milestone tree at milestone completion (CLAUDE.md's as-built-delta discipline) -- a hardcoded
phase path would fail this test spuriously the day that happens.

Function-name groups, so `-k substrates` / `-k arithmetic` / `-k premises` each select at least
one test: every function below carries the keyword for the section(s) it checks in its own name.
"""
import glob
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

BASIS_TOKENS = ("measured", "derived", "documented", "unknown")
BASIS_RE = re.compile(r"\[(" + "|".join(BASIS_TOKENS) + r")\]")

REQUIRED_HEADINGS = (
    "## Substrates",
    "## Execution arithmetic",
    "## Premises",
    "## Unresolved",
)

SUBSTRATE_QUESTIONS = ("Q-01", "Q-02", "Q-03", "Q-04")
ARITHMETIC_QUESTIONS = ("Q-05", "Q-06")

BASELINE_LABEL = "BASELINE — not eligible"

PLACEHOLDER_BODIES = {"TBD", "TODO", ""}

_NUMBERED_RE = re.compile(r"^\d+\.\s")
_PREMISE_ID_RE = re.compile(r"\bP-(\d+)\b")


# =====================================================================================
# Pure helpers -- text in, data out. No filesystem writes, no imports of scripts/.
# =====================================================================================

def _find_doc_path():
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
            ".planning/milestones/*-phases/*/ -- has it been created yet, or moved by a "
            "milestone archive?"
        )
    return Path(path).read_text(encoding="utf-8")


def _lines_with_fence_state(text):
    """Yield (line, in_fence) for every physical line. A fence marker line itself counts
    as `in_fence=True` (excluded like any other fenced line); the flag toggles on it."""
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


def _claim_lines(section_text):
    """Claim lines in `section_text`, fence-aware. `section_text` may be None (section
    absent), in which case there are no claim lines to find."""
    if section_text is None:
        return []
    return [
        line.strip()
        for line, in_fence in _lines_with_fence_state(section_text)
        if not in_fence and _is_claim_line(line)
    ]


def _section_body(text, heading):
    """Text strictly between `heading` and the next heading of the same or a shallower
    level (or EOF). Returns None if `heading` is not found verbatim on its own line."""
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


_SUBSTRATE_HEADING_RE = re.compile(r"^### .+$", re.MULTILINE)


def _substrate_sections(text):
    body = _section_body(text, "## Substrates")
    if body is None:
        return []
    starts = [m.start() for m in _SUBSTRATE_HEADING_RE.finditer(body)]
    sections = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(body)
        sections.append(body[start:end])
    return sections


def _assert_claim_lines_carry_one_token(section_text, section_name):
    assert section_text is not None, f"{section_name} section not found"
    lines = _claim_lines(section_text)
    assert lines, f"{section_name} carries no claim lines to check"
    for line in lines:
        matches = BASIS_RE.findall(line)
        assert len(matches) == 1, (
            f"claim line in {section_name} must carry EXACTLY one basis token "
            f"{BASIS_TOKENS}, found {len(matches)}: {line!r}"
        )
        body_without_token = BASIS_RE.sub("", line).strip()
        assert body_without_token not in PLACEHOLDER_BODIES, (
            f"claim line in {section_name} is a placeholder: {line!r}"
        )


def _all_premise_ids(text):
    body = _section_body(text, "## Premises")
    ids = set()
    for line in _claim_lines(body):
        ids.update(_PREMISE_ID_RE.findall(line))
    return {f"P-{i}" for i in ids}


def _unknown_premise_ids(text):
    body = _section_body(text, "## Premises")
    ids = set()
    for line in _claim_lines(body):
        if "[unknown]" in line:
            ids.update(f"P-{i}" for i in _PREMISE_ID_RE.findall(line))
    return ids


# =====================================================================================
# Whole-document structural checks
# =====================================================================================

def test_required_headings_present():
    text = _read_doc()
    for heading in REQUIRED_HEADINGS:
        assert heading in text, f"missing required heading: {heading!r}"


def test_all_six_question_ids_present_by_literal_token():
    text = _read_doc()
    for q in SUBSTRATE_QUESTIONS + ARITHMETIC_QUESTIONS:
        assert q in text, f"missing required question id: {q!r}"


def test_no_placeholder_claim_lines_anywhere():
    text = _read_doc()
    for section_name in ("## Substrates", "## Execution arithmetic", "## Premises", "## Unresolved"):
        body = _section_body(text, section_name)
        for line in _claim_lines(body):
            body_without_token = BASIS_RE.sub("", line).strip()
            assert body_without_token not in PLACEHOLDER_BODIES, (
                f"placeholder claim line in {section_name}: {line!r}"
            )


# =====================================================================================
# -k substrates
# =====================================================================================

def test_substrates_four_subsections_with_baseline_labelled():
    text = _read_doc()
    sections = _substrate_sections(text)
    assert len(sections) == 4, f"expected 4 substrate subsections, found {len(sections)}"
    assert BASELINE_LABEL in sections[3], (
        f"the 4th substrate subsection must carry the literal label {BASELINE_LABEL!r} "
        "(REVIEW-C3) -- selecting the baseline is not an available outcome of this spike"
    )
    for i, section in enumerate(sections[:3], start=1):
        assert BASELINE_LABEL not in section, (
            f"substrate subsection {i} must not carry the baseline label"
        )


def test_substrates_answer_all_four_sub_questions():
    text = _read_doc()
    sections = _substrate_sections(text)
    assert sections, "no substrate subsections found"
    for i, section in enumerate(sections, start=1):
        for q in SUBSTRATE_QUESTIONS:
            assert q in section, f"substrate subsection {i} is missing {q}"


def test_substrates_claim_lines_carry_exactly_one_basis_token():
    text = _read_doc()
    body = _section_body(text, "## Substrates")
    _assert_claim_lines_carry_one_token(body, "## Substrates")


# =====================================================================================
# -k arithmetic
# =====================================================================================

def test_execution_arithmetic_section_present_and_ided():
    text = _read_doc()
    body = _section_body(text, "## Execution arithmetic")
    assert body is not None, "## Execution arithmetic section not found"
    for q in ARITHMETIC_QUESTIONS:
        assert q in body, f"## Execution arithmetic is missing {q}"


def test_execution_arithmetic_costs_both_batch_sizes_against_budget():
    text = _read_doc()
    body = _section_body(text, "## Execution arithmetic")
    assert body is not None, "## Execution arithmetic section not found"
    assert "40" in body, "## Execution arithmetic must cost a 40-record batch"
    assert "300" in body, "## Execution arithmetic must cost a 300-record batch"
    assert "2,500" in body or "2500" in body, (
        "## Execution arithmetic must compare against the 2,500/month execution budget"
    )


def test_execution_arithmetic_claim_lines_carry_exactly_one_basis_token():
    text = _read_doc()
    body = _section_body(text, "## Execution arithmetic")
    _assert_claim_lines_carry_one_token(body, "## Execution arithmetic")


# =====================================================================================
# -k premises
# =====================================================================================

def test_premises_section_non_empty_with_id_basis_and_dependents():
    text = _read_doc()
    body = _section_body(text, "## Premises")
    assert body is not None, "## Premises section not found"
    lines = _claim_lines(body)
    assert lines, "## Premises must carry at least one premise entry"
    for line in lines:
        assert _PREMISE_ID_RE.search(line), f"premise entry carries no P-NN id: {line!r}"
        assert BASIS_RE.search(line), f"premise entry carries no basis token: {line!r}"
        assert "dependents" in line.lower(), (
            f"premise entry carries no dependents field: {line!r}"
        )


def test_premises_claim_lines_carry_exactly_one_basis_token():
    text = _read_doc()
    body = _section_body(text, "## Premises")
    _assert_claim_lines_carry_one_token(body, "## Premises")


def test_premises_unknowns_appear_in_unresolved_with_a_command():
    """As of the 2026-08-30 operator decision, all six premises this spike once recorded as
    `[unknown]` (P-05, P-07, P-08, P-09, P-10, P-13) are answered -- three from n8n's own
    published documentation, three from a live disarmed probe. `_unknown_premise_ids` is
    therefore expected to be EMPTY today. This is the honest state, not a weaker one: the
    contract below still enforces both directions --

    - if a future edit reintroduces an `[unknown]` premise, it MUST appear in ## Unresolved
      with a command (the original per-unknown contract, unchanged); and
    - ## Unresolved itself must say, in words, that everything it once listed is resolved --
      an empty-of-unknowns section that goes silent about *why* it's empty reads as "nobody
      checked," which is exactly the failure REVIEW-04 named. Silence is not the same claim
      as "resolved."
    """
    text = _read_doc()
    unknown_ids = _unknown_premise_ids(text)

    unresolved_body = _section_body(text, "## Unresolved")
    assert unresolved_body is not None, "## Unresolved section not found"

    if unknown_ids:
        unresolved_lines = _claim_lines(unresolved_body)
        assert unresolved_lines, "## Unresolved must carry at least one entry"

        for premise_id in unknown_ids:
            assert premise_id in unresolved_body, (
                f"{premise_id} carries basis [unknown] but does not appear in ## Unresolved"
            )

        all_ids = _all_premise_ids(text)
        for line in unresolved_lines:
            ids_here = {f"P-{i}" for i in _PREMISE_ID_RE.findall(line)}
            assert ids_here, f"## Unresolved entry names no premise id: {line!r}"
            for pid in ids_here:
                assert pid in all_ids, (
                    f"## Unresolved names {pid!r}, which is not a real premise id in ## Premises"
                )
            assert "command" in line.lower(), (
                f"## Unresolved entry for {sorted(ids_here)} carries no read-only command: {line!r}"
            )
    else:
        assert re.search(r"\bresolved\b", unresolved_body, re.IGNORECASE), (
            "## Premises carries zero [unknown] entries, but ## Unresolved does not say so -- "
            "an empty-of-unknowns section must state explicitly that everything it once listed "
            "was resolved, not just go quiet"
        )


def test_previously_unknown_premises_now_carry_a_non_unknown_basis():
    """Names the six premise ids this spike's first pass recorded as `[unknown]`
    (P-05, P-07, P-08, P-09, P-10, P-13) and asserts each now carries a real basis token
    (measured/derived/documented), never the literal string `[unknown]` on its own line --
    the positive half of the contract above: not just "no unknowns exist" in aggregate, but
    specifically that the six the operator was asked to close ARE closed, by id."""
    text = _read_doc()
    body = _section_body(text, "## Premises")
    assert body is not None, "## Premises section not found"
    lines = _claim_lines(body)

    formerly_unknown = ("P-05", "P-07", "P-08", "P-09", "P-10", "P-13")
    lines_by_id = {}
    for line in lines:
        for pid in {f"P-{i}" for i in _PREMISE_ID_RE.findall(line)}:
            lines_by_id.setdefault(pid, line)

    for pid in formerly_unknown:
        assert pid in lines_by_id, f"{pid} not found in ## Premises at all"
        line = lines_by_id[pid]
        assert "[unknown]" not in line, (
            f"{pid} was one of the six premises the operator was asked to close and must not "
            f"still carry [unknown]: {line!r}"
        )
        matches = BASIS_RE.findall(line)
        assert matches and matches[0] in ("measured", "derived", "documented"), (
            f"{pid} must carry a resolved basis token (measured/derived/documented): {line!r}"
        )
