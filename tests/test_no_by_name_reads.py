# tests/test_no_by_name_reads.py
#
# D-70-03/D-70-04 (Phase 70): proves `detect_by_name_reads`
# (scripts/build_cloud_workflows.py) sees all three by-name-read shapes — the quoted
# accessor form, the dynamic call form `recoverConvergedRun` uses when inlined (research
# Pitfall 2: an identifier held in a variable, no adjacent quote character for a
# literal-substring scan to catch), and `n8n/code/nodeRunRecovery.js` being inlined at
# all.
#
# Plan 70-04 Task 2 retires every remaining by-name read across all six built cloud
# workflows (the request-parsing/config-node reads, the review-decision/backend-status
# parse nodes, and the two straight-line credit/status chains) via the SAME
# splice_carry_merge_after carry-merge mechanism Task 1 used for the enrichment lane's
# HTTP hops. Starting inventory at Task 1 authoring time (2026-09-09), re-derived from
# the detector itself:
#
#   build_cloud()                       -> 10  violations (retired Plan 02 Task 3)
#   build_enrichment_cloud()            -> 119 violations (Task 1: -> 36; Task 2: -> 0)
#   build_enrichment_local_live()       -> 1   violation  (Task 2: -> 0, comment-only)
#   build_review_decision_cloud()       -> 12  violations (Task 2: -> 0)
#   build_backend_status_cloud()        -> 3   violations (Task 2: -> 0)
#   build_scheduled_maintenance_cloud() -> 1   violation  (Task 2: -> 0, dead-code by-name)
#
# Every one of the six workflows `main()` writes now reports zero. Task 3 (D-70-01) is
# the ENFORCEMENT half, done: `n8n/code/nodeRunRecovery.js` is deleted (never kept as a
# fallback — its per-inbound-edge run reasoning moved into `merge_node`'s own docstring),
# and `assert_no_by_name_reads` is wired into `main()` at every one of the eight write
# sites (composed with `_normalize_hubspot_auth`), so a regression fails the BUILD, not
# just this test file.
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_cloud_workflows as bcw  # noqa: E402

REQUIRED_KEYS = {"workflow", "node", "path", "form", "excerpt"}

ALL_BUILDERS = [
    "build_local",
    "build_cloud",
    "build_enrichment_cloud",
    "build_enrichment_local",
    "build_enrichment_local_live",
    "build_review_decision_cloud",
    "build_backend_status_cloud",
    "build_scheduled_maintenance_cloud",
]


def test_every_built_workflow_has_zero_by_name_reads():
    """Phase 70 Plan 04 Task 2's acceptance criterion: exactly zero violations for
    every one of the six workflows `main()` writes (plus `build_cloud()`, retired
    earlier in Plan 02 Task 3 and re-asserted here so a regression there also fails
    this file)."""
    for builder_name in ALL_BUILDERS:
        violations = bcw.detect_by_name_reads(getattr(bcw, builder_name)())
        assert violations == [], f"{builder_name}() still has by-name reads: {violations}"


def test_no_violation_is_a_research_or_judge_request_builder():
    """D-70-04's key_link: 'the build-time assertion ... must catch ... reads
    embedded in node parameters expressions, or a partially-migrated state passes
    vacuously' — named explicitly here for the research/judge request BUILDERS (the
    nodes that assemble the outgoing HTTP body), as distinct from the post-HTTP
    recovery nodes Pitfall 4 actually targets (Validate Research Output/Apply Judge
    Verdict and their contact-branch twins), which Task 1 also cleared."""
    request_builders = {
        "Build Research Request", "Build Judge Request",
        "Build Contact Research Request", "Build Contact Judge Request",
    }
    violations = bcw.detect_by_name_reads(bcw.build_enrichment_cloud())
    offending = [v for v in violations if v["node"] in request_builders]
    assert offending == [], offending


def test_detector_sees_parameter_expressions():
    """An IF condition string carries a quoted node lookup, with NO jsCode key anywhere
    in the workflow — a jsCode-only scan would find nothing here (research Pitfall 2)."""
    wf = {
        "name": "synthetic",
        "nodes": [
            {
                "name": "Splitter",
                "type": "n8n-nodes-base.if",
                "parameters": {
                    "conditions": {
                        "combinator": "and",
                        "conditions": [
                            {
                                "leftValue": "={{ $('Gate').item.json.action }}",
                                "rightValue": "update",
                                "operator": {"type": "string", "operation": "equals"},
                            }
                        ],
                    }
                },
            }
        ],
    }
    violations = bcw.detect_by_name_reads(wf)
    assert len(violations) == 1
    assert violations[0]["form"] == "quoted"
    assert violations[0]["node"] == "Splitter"


def test_detector_sees_dynamic_form():
    """The bare-identifier call form `(name) => $(name).all()` — no adjacent quote
    character, invisible to a literal-substring `$('` scan."""
    wf = {
        "name": "synthetic",
        "nodes": [
            {
                "name": "Reader",
                "type": "n8n-nodes-base.code",
                "parameters": {
                    "jsCode": "function nodeAll(name) { return $(name).all(); }\nreturn nodeAll('Gate');"
                },
            }
        ],
    }
    violations = bcw.detect_by_name_reads(wf)
    dynamic = [v for v in violations if v["form"] == "dynamic"]
    assert len(dynamic) == 1, violations


def test_detector_sees_inlined_run_recovery():
    """`nodeRunRecovery.js`'s own function-signature line, present verbatim in a node's
    jsCode, is reported as `run_recovery_inlined` — distinct from an ordinary by-name
    read, naming the module itself as a migrating call site."""
    marker = bcw._run_recovery_marker()
    wf = {
        "name": "synthetic",
        "nodes": [
            {
                "name": "Gate Reader",
                "type": "n8n-nodes-base.code",
                "parameters": {"jsCode": f"{marker}\n  return [];\n}}\nreturn recoverConvergedRun(() => [], 'Gate', 0, () => true);"},
            }
        ],
    }
    violations = bcw.detect_by_name_reads(wf)
    inlined = [v for v in violations if v["form"] == "run_recovery_inlined"]
    assert len(inlined) == 1, violations
    assert inlined[0]["node"] == "Gate Reader"


def test_assert_no_by_name_reads_raises_on_a_violating_workflow():
    """Phase 70 Plan 04 Task 3 (D-70-01): the raise itself, proven, never assumed. A
    hand-built workflow carrying one violation must stop generation with a `ValueError`
    naming the workflow label and the offending node — never silently ship."""
    wf = {
        "name": "synthetic",
        "nodes": [
            {
                "name": "Splitter",
                "type": "n8n-nodes-base.if",
                "parameters": {
                    "conditions": {
                        "combinator": "and",
                        "conditions": [
                            {
                                "leftValue": "={{ $('Gate').item.json.action }}",
                                "rightValue": "update",
                                "operator": {"type": "string", "operation": "equals"},
                            }
                        ],
                    }
                },
            }
        ],
    }
    with pytest.raises(ValueError) as excinfo:
        bcw.assert_no_by_name_reads(wf, "wf_synthetic_example")
    assert "wf_synthetic_example" in str(excinfo.value)
    assert "Splitter" in str(excinfo.value)


def test_assert_no_by_name_reads_passes_a_clean_workflow_through_unchanged():
    wf = {
        "name": "synthetic",
        "nodes": [{
            "name": "Passthrough", "type": "n8n-nodes-base.code",
            "parameters": {"jsCode": "return $input.all();"},
        }],
    }
    assert bcw.assert_no_by_name_reads(wf, "wf_synthetic_clean") is wf


def test_detector_clean_workflow_returns_empty():
    """A workflow whose jsCode reads only `$input` — no by-name lookup anywhere — is
    reported clean."""
    wf = {
        "name": "synthetic",
        "nodes": [
            {
                "name": "Passthrough",
                "type": "n8n-nodes-base.code",
                "parameters": {"jsCode": "return $input.all();"},
            }
        ],
    }
    assert bcw.detect_by_name_reads(wf) == []


# =====================================================================================
# Review WR-06 — the deleted module's fingerprint, pinned against git history.
# =====================================================================================

_RUN_RECOVERY_PATH = "n8n/code/nodeRunRecovery.js"
# The commit that deleted the module (Phase 70 Plan 04 Task 3, D-70-01). Its PARENT is
# the last revision that still carried the file's real content.
_RUN_RECOVERY_DELETED_AT = "60402f2ef164505ce9de9d6a1b68b8e44b589563"
_SIGNATURE_RE = re.compile(r"^function \w+\(all, nodeName, runIndex, keep, maxRuns\) \{$")


def _git(*args):
    return subprocess.run(("git",) + args, cwd=ROOT, capture_output=True, text=True)


def test_run_recovery_marker_still_matches_the_deleted_modules_real_signature():
    """`_run_recovery_marker` is a HAND-MAINTAINED copy of a line in a file that no
    longer exists, so nothing in the working tree can contradict it if it drifts — and a
    drifted fingerprint degrades `detect_by_name_reads` silently: a genuine reinlining of
    the retired mechanism would be reported as an ordinary `dynamic`/`quoted` miss
    instead of `run_recovery_inlined`, exactly when the distinction matters most.

    Pin it against the file's own last committed content. The retired function's bare
    name is never spelled here either — it is SELECTED from history by its argument
    list, so this test cannot drift with the marker it checks."""
    show = _git("show", f"{_RUN_RECOVERY_DELETED_AT}^:{_RUN_RECOVERY_PATH}")
    assert show.returncode == 0, (
        f"{_RUN_RECOVERY_PATH} must still be readable at {_RUN_RECOVERY_DELETED_AT}^ — "
        f"the fingerprint has no other source of truth: {show.stderr}")

    signatures = [line for line in show.stdout.splitlines() if _SIGNATURE_RE.match(line)]
    assert len(signatures) == 1, f"expected exactly one signature line, got {signatures}"
    assert signatures[0] == bcw._run_recovery_marker(), (
        "the hardcoded fingerprint no longer matches the deleted module's real "
        "signature — detect_by_name_reads would no longer recognise a reinlining")


def test_the_run_recovery_module_is_deleted_never_kept_as_a_fallback():
    """D-70-01: the module is gone at HEAD, not retained beside its replacement. If it
    ever comes back, the fingerprint stops being historical and this whole mechanism
    needs rethinking rather than quietly passing."""
    assert _git("cat-file", "-e", f"HEAD:{_RUN_RECOVERY_PATH}").returncode != 0, (
        f"{_RUN_RECOVERY_PATH} is back in the tree — see D-70-01")
