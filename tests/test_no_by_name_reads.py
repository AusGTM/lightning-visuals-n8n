# tests/test_no_by_name_reads.py
#
# D-70-03/D-70-04 (Phase 70): proves `detect_by_name_reads`
# (scripts/build_cloud_workflows.py) sees all three by-name-read shapes — the quoted
# accessor form, the dynamic call form `recoverConvergedRun` uses when inlined (research
# Pitfall 2: an identifier held in a variable, no adjacent quote character for a
# literal-substring scan to catch), and `n8n/code/nodeRunRecovery.js` being inlined at
# all.
#
# This is the detector's own RED proof (mirrors D-70-18's requirement for the walker): a
# detector that found nothing today would pass plan 70-04's "flip to zero" gate
# vacuously, proving nothing. Starting inventory, re-derived from the detector itself
# (not the research doc's separately-counted "25 distinct literal targets" — a different
# unit of counting, one match per string vs one target name) at authoring time
# (2026-09-09):
#
#   build_cloud()                 -> 10 violations
#   build_enrichment_cloud()      -> 119 violations
#   build_review_decision_cloud() -> 12 violations
#
# Plan 70-02 Task 3 retires every by-name read on the ingest lane (build_cloud() below is
# the FIRST of the three to flip). build_enrichment_cloud()/build_review_decision_cloud()
# are plan 70-04's job — still non-zero here, still RED, so a real regression on those
# two workflows cannot silently hide behind this file's own edit.
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_cloud_workflows as bcw  # noqa: E402

REQUIRED_KEYS = {"workflow", "node", "path", "form", "excerpt"}


def test_ingest_lane_has_zero_by_name_reads():
    """D-70-03 (Phase 70 Plan 02 Task 3): the ingest lane's carry merges retire every
    by-name read the detector could see — the FIRST of the three cloud workflows to
    reach zero (build_enrichment_cloud()/build_review_decision_cloud() are plan 70-04)."""
    violations = bcw.detect_by_name_reads(bcw.build_cloud())
    assert violations == [], f"build_cloud() still has by-name reads: {violations}"


@pytest.mark.parametrize(
    "builder_name",
    ["build_enrichment_cloud", "build_review_decision_cloud"],
)
def test_detector_finds_todays_violations(builder_name):
    """The detector's own RED proof: a detector that found nothing today would pass
    plan 70-04's zero-count gate vacuously."""
    wf = getattr(bcw, builder_name)()
    violations = bcw.detect_by_name_reads(wf)
    assert len(violations) > 0, f"{builder_name}() has zero by-name reads today — detector is blind"
    for v in violations:
        assert REQUIRED_KEYS.issubset(v.keys()), v


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
