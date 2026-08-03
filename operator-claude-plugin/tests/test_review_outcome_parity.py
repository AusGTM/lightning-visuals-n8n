"""Phase 31 Plan 02 (BUG 30) — the two-sided pin for the review-decision outcome
vocabulary.

Per 31-CONTEXT.md's process invariant ("this milestone was burned five times by
contracts held in two places and tested on one"): the outcome word a review decision can
answer with is decided in TWO places — `n8n/code/reviewDecision.js` (the source module)
and `review_decision.OUTCOMES` (the client's tuple) — and a THIRD, derived place, the
COMMITTED `n8n/wf_review_decision_cloud.json`'s own inlined copy of that module. All three
are read here as TEXT (never imported across the client/backend boundary, PLUGIN-04) and
compared. A literal added to any one side alone fails this file.

Follows `test_control_flag_parity.py`'s read-the-other-side-as-text idiom.
"""
import re
from pathlib import Path

import review_decision as rd

REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_DECISION_JS = REPO_ROOT / "n8n" / "code" / "reviewDecision.js"
WF_REVIEW_DECISION_JSON = REPO_ROOT / "n8n" / "wf_review_decision_cloud.json"

# outcome: "value" — every return site in reviewDecision.js (the `refused` helper and every
# inline `return { ... outcome: "...", ... }`) uses exactly this shape.
_OUTCOME_LITERAL_RE = re.compile(r'outcome:\s*"([a-z_]+)"')


def _js_source_outcomes() -> set:
    text = REVIEW_DECISION_JS.read_text()
    return set(_OUTCOME_LITERAL_RE.findall(text))


def _committed_workflow_outcomes() -> set:
    import json

    wf = json.loads(WF_REVIEW_DECISION_JSON.read_text())
    node = next((n for n in wf["nodes"] if n["name"] == "Build Review Decision"), None)
    assert node is not None, "Build Review Decision must exist in the committed workflow"
    js_code = node["parameters"]["jsCode"]
    return set(_OUTCOME_LITERAL_RE.findall(js_code))


# --- the pin itself ---------------------------------------------------------------------

def test_the_source_modules_outcome_literals_match_the_clients_tuple():
    js_outcomes = _js_source_outcomes()
    assert js_outcomes == set(rd.OUTCOMES), (
        "n8n/code/reviewDecision.js's outcome literals have drifted from "
        f"review_decision.OUTCOMES: js-only={js_outcomes - set(rd.OUTCOMES)}, "
        f"client-only={set(rd.OUTCOMES) - js_outcomes}"
    )


def test_the_committed_workflows_own_copy_matches_the_clients_tuple_too():
    """The pin covers the DEPLOYED artifact, not only the source module — a build step
    that stripped or renamed an outcome while inlining would fail here even if
    reviewDecision.js itself still read correctly."""
    wf_outcomes = _committed_workflow_outcomes()
    assert wf_outcomes == set(rd.OUTCOMES), (
        "the committed wf_review_decision_cloud.json's Build Review Decision node has "
        f"drifted from review_decision.OUTCOMES: wf-only={wf_outcomes - set(rd.OUTCOMES)}, "
        f"client-only={set(rd.OUTCOMES) - wf_outcomes}"
    )


def test_not_allowlisted_is_registered_as_non_writing_and_only_non_writing():
    assert "not_allowlisted" in rd.NON_WRITING_OUTCOMES
    assert "not_allowlisted" not in rd.WRITING_OUTCOMES
    assert "not_allowlisted" in rd.OUTCOMES


# --- behavioural: verify_decision's handling of the two states this phase separates -----

def test_verify_decision_maps_not_allowlisted_to_not_written_and_passes_the_message_through():
    response = {"available": True, "outcome": "not_allowlisted",
                "message": "this record is not on the backend's TEST_RECORD_* allowlist"}
    verdict = rd.verify_decision({}, response)
    assert verdict["status"] == "not_written"
    assert verdict["message"] == response["message"]


def test_an_unparseable_response_verdict_names_execution_history_not_the_allowlist_first():
    response = {"available": False, "reason": "unparseable_response"}
    verdict = rd.verify_decision({}, response)
    assert verdict["status"] == "failed"
    assert "execution history" in verdict["message"]
    # The old (wrong) advice told the operator to check the allowlist before anything
    # else. It must be gone from this specific message.
    assert "TEST_RECORD_IDS" not in verdict["message"]


def test_a_no_response_verdict_also_names_execution_history():
    response = {"available": False, "reason": "no_response"}
    verdict = rd.verify_decision({}, response)
    assert "execution history" in verdict["message"]


def test_every_other_unavailable_reason_keeps_the_generic_wording():
    response = {"available": False, "reason": "endpoint_unreachable"}
    verdict = rd.verify_decision({}, response)
    assert "execution history" not in verdict["message"]
    assert "endpoint_unreachable" in verdict["message"]
