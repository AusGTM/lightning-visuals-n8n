"""Phase 67 Plan 03 — the mandatory end-of-run report call-site contract (AUTO-06,
D-67-06, D-67-11, D-67-13).

Under autonomy the end-of-run report is the only account of what happened, so the two
batch skills that never called it — `contact-upload` and `suggest-contacts` — now do.
`enrich-before-ingest` and `enrich-records` already called it; both carried a paragraph
claiming `contact-upload` was deliberately NOT a call site (REVIEW-57-L5), reasoning
that its lane is watched in real time — a premise autonomy breaks. This module pins
the call sites (`build_run_report`/`record_audit`), the corrected paragraphs, and
(Task 3) the report's own idempotence and gap-honesty as the properties that make a
mandatory report safe to make mandatory.

`_text` / `_normalized` / `_numbered_step_spans` / `_step` / `_fence_containing` are
copied from `test_autonomy_switch_prose.py`'s own idiom (itself copied from
`test_implicit_approval_contract.py`), not imported — matching that file's own stated
reason for staying separate: independent evolution, no risk of colliding with work in
flight in the file it mirrors.

`review-triage` and `backend-control` are excluded from TABLE (Task 3 finalizes this
docstring with the full reason).
"""
import ast
import re
import textwrap
from pathlib import Path

import pytest

import run_report

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"

# The two batch skills this plan makes call sites for — Task 1 lands contact-upload;
# Task 2 adds suggest-contacts.
TABLE = {
    "contact-upload": {
        "path": SKILLS_DIR / "contact-upload" / "SKILL.md",
        "report_step": 7,
    },
}

# The two skills that already called the report before this plan — their "contact-upload
# is deliberately NOT a call site" paragraph is what this plan corrects.
ANALOG_PATHS = {
    "enrich-before-ingest": SKILLS_DIR / "enrich-before-ingest" / "SKILL.md",
    "enrich-records": SKILLS_DIR / "enrich-records" / "SKILL.md",
}


def _text(path):
    return path.read_text(encoding="utf-8")


def _normalized(text):
    """Same idiom as `test_autonomy_switch_prose.py`'s `_normalized()`: collapse
    whitespace, strip blockquote markers and bold markers, so a reflow cannot fail a
    wording assertion (and cannot hide one either)."""
    stripped = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)
    return re.sub(r"\s+", " ", stripped.replace("*", "")).strip()


def _numbered_step_spans(text):
    """Every top-level numbered step (`N. **...`) as `(step_number, span_text)`, a span
    running from its own heading to the next top-level heading or end of file."""
    matches = list(re.finditer(r"^(\d+)\. \*\*", text, flags=re.MULTILINE))
    assert matches, "expected at least one top-level numbered step in SKILL.md"
    spans = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        spans.append((match.group(1), text[start:end]))
    return spans


def _step(text, number):
    for n, span in _numbered_step_spans(text):
        if n == str(number):
            return span
    raise AssertionError(f"no top-level numbered step {number} found in SKILL.md")


_FENCE_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)
_PLACEHOLDER_RE = re.compile(r"<[^<>\n]*>")


def _fence_containing(text, marker):
    """The body of the first ```python fence in `text` that contains `marker`, or
    None."""
    for match in _FENCE_RE.finditer(text):
        body = match.group(1)
        if marker in body:
            return body
    return None


def _scripts_modules():
    return {p.stem for p in SCRIPTS_DIR.glob("*.py")}


def _scripts_module_call_count(fence_body, modules):
    """How many `module.function(...)` calls this fence body makes, `module` in
    `modules` — mirrors `test_skill_sequence_coverage.py`'s own `parse_calls`, kept as
    a fresh copy here rather than an import (this file's own stated reason: no risk of
    colliding with work in flight in the file it mirrors)."""
    substituted = _PLACEHOLDER_RE.sub("__PLACEHOLDER__", textwrap.dedent(fence_body))
    tree = ast.parse(substituted)
    calls = []

    class _Visitor(ast.NodeVisitor):
        def visit_Call(self, node):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id in modules
            ):
                calls.append(f"{func.value.id}.{func.attr}")
            self.generic_visit(node)

    _Visitor().visit(tree)
    return len(calls)


# =====================================================================================
# Call-site shape — parametrized over TABLE.
# =====================================================================================


@pytest.mark.parametrize("name", sorted(TABLE))
def test_exactly_one_build_run_report_call(name):
    text = _text(TABLE[name]["path"])
    count = text.count("run_report.build_run_report(")
    assert count == 1, f"{name}: expected exactly one build_run_report( call, found {count}"


@pytest.mark.parametrize("name", sorted(TABLE))
def test_build_run_report_sits_in_its_own_single_call_fence(name):
    text = _text(TABLE[name]["path"])
    body = _fence_containing(text, "run_report.build_run_report(")
    assert body is not None, f"{name}: no python fence found containing build_run_report"
    count = _scripts_module_call_count(body, _scripts_modules())
    assert count == 1, (
        f"{name}: the build_run_report fence must contain exactly one scripts-module "
        f"call (a second call in the same fence creates a new sequence identity for "
        f"test_skill_sequence_coverage.py to register), found {count}"
    )


@pytest.mark.parametrize("name", sorted(TABLE))
def test_build_run_report_is_in_the_report_step_and_after_the_run_handle(name):
    target = TABLE[name]
    text = _text(target["path"])
    span = _step(text, target["report_step"])
    assert "run_report.build_run_report(" in span, (
        f"{name}: build_run_report must appear in step {target['report_step']}"
    )
    # The run-handle paragraph ("print the run handle") is the existing per-record
    # report's own closing line — the new fence must come after it.
    handle_idx = span.find("print the run handle")
    report_idx = span.find("run_report.build_run_report(")
    assert handle_idx != -1, f"{name}: expected the existing run-handle paragraph"
    assert handle_idx < report_idx, (
        f"{name}: build_run_report must be added AFTER the existing per-record report, "
        f"never replacing or preceding it"
    )


@pytest.mark.parametrize("name", sorted(TABLE))
def test_build_run_report_call_args(name):
    target = TABLE[name]
    text = _text(target["path"])
    span = _step(text, target["report_step"])
    normalized = _normalized(span)
    assert (
        "run_report.build_run_report( run_id, cfg, outcomes=[outcome], disarm=disarm, "
        "balances=balances_at_grant, ceiling=ceiling)" in normalized
    ), f"{name}: unexpected build_run_report call shape"


@pytest.mark.parametrize("name", sorted(TABLE))
def test_no_icp_or_tier_substring(name):
    lowered = _text(TABLE[name]["path"]).lower()
    assert "icp" not in lowered, f"{name}: forbidden substring 'icp' found (D-10b)"
    assert "tier" not in lowered, f"{name}: forbidden substring 'tier' found (D-10b)"


# =====================================================================================
# contact-upload specific — the run handle, the two record_audit observations, and the
# ceiling-breach branch's own reportless account.
# =====================================================================================


def _contact_upload_text():
    return _text(TABLE["contact-upload"]["path"])


def test_contact_upload_has_exactly_two_record_audit_calls():
    text = _contact_upload_text()
    count = text.count("run_report.record_audit(")
    assert count == 2, f"expected exactly two record_audit( calls, found {count}"


def test_contact_upload_mints_run_id_once_before_the_would_be_check():
    text = _contact_upload_text()
    span6 = _step(text, 6)
    mint_idx = span6.find("run_id = run_state.new_run_id()")
    would_be_idx = span6.find("would_be = 1 + send_row_count")
    assert mint_idx != -1, "run_state.new_run_id() mint not found in step 6"
    assert would_be_idx != -1, "the would_be ceiling check not found in step 6"
    assert mint_idx < would_be_idx, "run_id must be minted BEFORE the ceiling branch"
    assert text.count("run_state.new_run_id()") == 1, (
        "run_id must be minted exactly once — a second mint would give the audit "
        "record and the dispatch two different handles"
    )


def test_contact_upload_passes_its_own_run_id_into_dispatch():
    text = _contact_upload_text()
    assert "dispatch.dispatch(send_path, True, cfg, run_id=run_id)" in text, (
        "dispatch.dispatch must be called with the minted run_id, not left to mint "
        "its own"
    )


def test_contact_upload_first_audit_call_runs_before_the_would_be_check_and_carries_ceiling_and_balances():
    text = _contact_upload_text()
    span6 = _step(text, 6)
    first_call = 'run_report.record_audit(run_id, ceiling=ceiling, balances=balances_at_grant)'
    call_idx = span6.find(first_call)
    would_be_idx = span6.find("would_be = 1 + send_row_count")
    assert call_idx != -1, "the first record_audit call (ceiling+balances) not found"
    assert call_idx < would_be_idx, (
        "the first record_audit call must run on BOTH branches — before the "
        "would_be/ceiling-breach check, not inside either branch"
    )


def test_contact_upload_second_audit_call_runs_in_the_finally_and_carries_disarm():
    text = _contact_upload_text()
    span6 = _step(text, 6)
    second_call = "run_report.record_audit(run_id, disarm=disarm)"
    call_idx = span6.find(second_call)
    finally_idx = span6.find("close_reason = write_grant.CLOSED_UNHANDLED_ERROR")
    assert call_idx != -1, "the second record_audit call (disarm) not found"
    assert finally_idx != -1, "the finally block's close_reason line not found"
    assert call_idx > finally_idx, (
        "the second record_audit call must run in the finally block, after "
        "record_dispatch_outcome closes the grant"
    )


def test_contact_upload_audit_calls_are_wrapped_against_run_report_error():
    text = _contact_upload_text()
    assert text.count("except run_report.RunReportError:") == 2, (
        "both record_audit calls must be wrapped so a bookkeeping failure can never "
        "halt a live dispatch (D-59-10)"
    )


def test_contact_upload_ceiling_breach_branch_states_it_has_no_report_call():
    text = _contact_upload_text()
    span6 = _step(text, 6)
    normalized = _normalized(span6)
    assert "stops before `dispatch.dispatch` is ever called" in normalized, (
        "the ceiling-breach branch must state it never arms and never dispatches"
    )
    assert "whole account" in normalized, (
        "the ceiling-breach branch's account (audit record + remainder queue + stop) "
        "must be named as its whole account"
    )
    assert "D-67-13" in normalized, "D-67-13 must be cited"


def test_contact_upload_step_numbering_is_unchanged():
    text = _contact_upload_text()
    assert re.search(r"^7\. \*\*", text, flags=re.MULTILINE), "step 7 must still exist"
    assert len(re.findall(r"^10\. \*\*", text, flags=re.MULTILINE)) == 1, (
        "the last numbered step must still be 10 — nothing renumbered"
    )


def test_contact_upload_pre_spend_pause_appears_exactly_once():
    text = _contact_upload_text()
    assert text.count("pre_spend_pause") == 1


# =====================================================================================
# The two analog skills — the corrected paragraph, not the retired one.
# =====================================================================================


@pytest.mark.parametrize("name", sorted(ANALOG_PATHS))
def test_analog_no_longer_claims_contact_upload_is_deliberately_excluded(name):
    text = _text(ANALOG_PATHS[name])
    assert "deliberately NOT a call site" not in text, (
        f"{name}: the retired REVIEW-57-L5 claim must be removed"
    )


@pytest.mark.parametrize("name", sorted(ANALOG_PATHS))
def test_analog_states_the_corrected_reason(name):
    text = _text(ANALOG_PATHS[name])
    normalized = _normalized(text)
    assert "AUTO-06" in normalized, f"{name}: AUTO-06 must be cited"
    assert "D-67-11" in normalized, f"{name}: D-67-11 must be cited"
    assert "REVIEW-57-L5" in normalized, f"{name}: REVIEW-57-L5 must still be cited"
    assert "now builds this report too" in normalized, (
        f"{name}: the corrected paragraph must state contact-upload now builds the "
        f"report too"
    )


@pytest.mark.parametrize("name", sorted(ANALOG_PATHS))
def test_analog_own_report_call_unchanged(name):
    text = _text(ANALOG_PATHS[name])
    assert text.count("run_report.build_run_report(") == 1, (
        f"{name}: its own existing report call must be unchanged (exactly one)"
    )
