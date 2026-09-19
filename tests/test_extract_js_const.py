# tests/test_extract_js_const.py
#
# Phase 74 Plan 05 Task 3 (WR-10, 73-REVIEW.md). `extract_js_const`
# (scripts/build_cloud_workflows.py) regex-extracts one top-level `const NAME = ...;`
# statement from a Wave-A module for splicing into a generated Code node. The
# non-greedy `.*?;` regex stops at the FIRST `;` that ends a line — it worked for every
# constant extracted so far only because none of their literals (or the `//` comment
# lines inside them) happened to contain a `;` at a line end. A comment ending in a
# semicolon silently truncates the extraction into a syntactically-broken prefix that
# would be spliced verbatim into a generated Code node, with nothing raising.
#
# `CODE` is monkeypatched to a tmp_path fixture module rather than writing a permanent,
# otherwise-unused module into n8n/code/ — the bug is in `extract_js_const` itself, not
# in any real constant, so no real module needs to carry the reproducing shape.
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_cloud_workflows  # noqa: E402
from build_cloud_workflows import extract_js_const  # noqa: E402

import pytest  # noqa: E402


def test_extraction_still_works_for_a_well_formed_constant(tmp_path, monkeypatch):
    (tmp_path / "fixture.js").write_text(
        'const FOO = ["a", "b"];\n'
    )
    monkeypatch.setattr(build_cloud_workflows, "CODE", tmp_path)
    assert extract_js_const("fixture.js", "FOO").strip() == 'const FOO = ["a", "b"];'


def test_a_semicolon_terminated_comment_line_inside_the_literal_no_longer_silently_truncates(
    tmp_path, monkeypatch
):
    # WR-10's exact reproducing shape: a `//` comment line ending in `;` sits INSIDE the
    # constant's own multi-line literal, before the statement's real terminating `;`.
    # The non-greedy regex used to stop at the comment's own `;`, yielding
    # `const FOO = [\n  // a comment that ends in a semicolon;` — an unbalanced,
    # syntactically-broken prefix, silently, with nothing raising.
    (tmp_path / "fixture.js").write_text(
        "const FOO = [\n"
        "  // a comment that ends in a semicolon;\n"
        '  "a",\n'
        '  "b",\n'
        "];\n"
    )
    monkeypatch.setattr(build_cloud_workflows, "CODE", tmp_path)
    with pytest.raises(ValueError, match="did not extract as a balanced statement"):
        extract_js_const("fixture.js", "FOO")


def test_a_missing_constant_still_raises_its_own_distinct_error(tmp_path, monkeypatch):
    (tmp_path / "fixture.js").write_text('const FOO = ["a"];\n')
    monkeypatch.setattr(build_cloud_workflows, "CODE", tmp_path)
    with pytest.raises(ValueError, match="no top-level"):
        extract_js_const("fixture.js", "BAR")


def test_freemail_domains_extraction_from_the_real_module_stays_balanced():
    # The one real call site (companyLink.js's FREEMAIL_DOMAINS, D-73-08/F-B3) must
    # still pass the new balance check against the actual committed source — the guard
    # must never fire a false positive on real, well-formed content.
    text = extract_js_const("companyLink.js", "FREEMAIL_DOMAINS")
    assert text.startswith("const FREEMAIL_DOMAINS")
    assert text.count("[") == text.count("]")
    assert text.count("{") == text.count("}")
    assert text.count("(") == text.count(")")
