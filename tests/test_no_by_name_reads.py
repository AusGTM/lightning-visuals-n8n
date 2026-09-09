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
# Every one of the six workflows `main()` writes now reports zero. Task 3's job is the
# ENFORCEMENT half — deleting nodeRunRecovery.js and wiring `assert_no_by_name_reads`
# into `main()` so a regression fails the build, not just this test file.
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_cloud_workflows as bcw  # noqa: E402

REQUIRED_KEYS = {"workflow", "node", "path", "form", "excerpt"}

ALL_BUILDERS = [
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
